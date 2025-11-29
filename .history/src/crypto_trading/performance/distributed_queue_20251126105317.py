"""
Distributed Task Queue

This module provides a distributed task queue implementation using Redis as the message broker.
"""
import asyncio
import logging
import random
import signal
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, Type

import redis.asyncio as redis
from pydantic import BaseModel, Field, validator

from ..performance.async_processor import Task, TaskResult, TaskStatus, TaskHandler

logger = logging.getLogger(__name__)


class QueueType(str, Enum):
    """Supported queue types"""
    REDIS = "redis"
    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"


class QueueConfig(BaseModel):
    """Configuration for the distributed queue"""
    queue_type: QueueType = Field(
        default=QueueType.REDIS,
        description="Type of queue to use"
    )
    url: str = Field(
        default="redis://localhost:6379/0",
        description="Connection URL for the queue"
    )
    queue_name: str = Field(
        default="crypto_trading_tasks",
        description="Name of the queue"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries for failed tasks"
    )
    visibility_timeout: int = Field(
        default=300,  # 5 minutes
        description="Visibility timeout in seconds"
    )

    @validator('url')
    def validate_url(cls, v, values):
        if values.get('queue_type') == QueueType.REDIS and not v.startswith('redis://'):
            raise ValueError("Redis URL must start with 'redis://'")
        return v


class DistributedQueue(ABC):
    """Abstract base class for distributed queues"""
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to the queue"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the queue"""
        pass
    
    @abstractmethod
    async def enqueue(self, task: Task) -> str:
        """Enqueue a task"""
        pass
    
    @abstractmethod
    async def dequeue(self, timeout: int = 0) -> Optional[Task]:
        """Dequeue a task"""
        pass
    
    @abstractmethod
    async def ack(self, task_id: str) -> None:
        """Acknowledge task completion"""
        pass
    
    @abstractmethod
    async def nack(self, task_id: str, delay: int = 0) -> None:
        """Negative acknowledgment for task failure"""
        pass
    
    @abstractmethod
    async def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the result of a completed task"""
        pass


class RedisQueue(DistributedQueue):
    """Redis-based distributed queue implementation"""
    
    def __init__(self, config: QueueConfig):
        self.config = config
        self.redis: Optional[redis.Redis] = None
        self._result_prefix = f"{config.queue_name}:result:"
        self._processing_queue = f"{config.queue_name}:processing"
    
    async def connect(self) -> None:
        """Connect to Redis"""
        self.redis = redis.from_url(
            self.config.url,
            decode_responses=True
        )
        # Test the connection
        await self.redis.ping()
        logger.info(f"Connected to Redis at {self.config.url}")
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
            await self.redis.connection_pool.disconnect()
            logger.info("Disconnected from Redis")
    
    async def enqueue(self, task: Task) -> str:
        """Enqueue a task"""
        if not self.redis:
            raise RuntimeError("Not connected to Redis")
        
        task_data = task.json()
        task_id = task.task_id or str(uuid.uuid4())
        
        # Add to the main queue
        await self.redis.lpush(self.config.queue_name, task_data)
        logger.debug(f"Enqueued task {task_id}")
        
        return task_id
    
    async def dequeue(self, timeout: int = 0) -> Optional[Task]:
        """Dequeue a task"""
        if not self.redis:
            raise RuntimeError("Not connected to Redis")
        
        # Move a task from the main queue to the processing queue
        task_data = await self.redis.brpoplpush(
            self.config.queue_name,
            self._processing_queue,
            timeout=timeout or 0
        )
        
        if not task_data:
            return None
        
        task = Task.parse_raw(task_data)
        logger.debug(f"Dequeued task {task.task_id}")
        return task
    
    async def ack(self, task_id: str) -> None:
        """Acknowledge task completion"""
        if not self.redis:
            raise RuntimeError("Not connected to Redis")
        
        # Remove from processing queue
        await self.redis.lrem(self._processing_queue, 1, task_id)
        logger.debug(f"Acknowledged task {task_id}")
    
    async def nack(self, task_id: str, delay: int = 0) -> None:
        """Negative acknowledgment for task failure"""
        if not self.redis:
            raise RuntimeError("Not connected to Redis")
        
        if delay > 0:
            # Add back to the main queue with a delay
            task_data = await self.redis.lindex(self._processing_queue, -1)
            if task_data:
                task = Task.parse_raw(task_data)
                task.retries = (task.retries or 0) + 1
                
                if task.retries > self.config.max_retries:
                    logger.warning(f"Task {task_id} exceeded max retries")
                    await self.ack(task_id)
                    return
                
                # Schedule for later retry
                await self.redis.rpush(
                    f"{self.config.queue_name}:delayed",
                    task.json()
                )
                await self.redis.expire(
                    f"{self.config.queue_name}:delayed",
                    delay + 60  # Keep for at least delay + 1 minute
                )
        
        # Remove from processing queue
        await self.ack(task_id)
        logger.debug(f"Negative acknowledgment for task {task_id}")
    
    async def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the result of a completed task"""
        if not self.redis:
            raise RuntimeError("Not connected to Redis")
        
        result_data = await self.redis.get(f"{self._result_prefix}{task_id}")
        if not result_data:
            return None
        
        return TaskResult.parse_raw(result_data)
    
    async def set_result(self, task_id: str, result: TaskResult) -> None:
        """Store the result of a completed task"""
        if not self.redis:
            raise RuntimeError("Not connected to Redis")
        
        await self.redis.set(
            f"{self._result_prefix}{task_id}",
            result.json(),
            ex=86400  # Keep results for 24 hours
        )


class DistributedTaskManager:
    """Manages distributed task execution across multiple workers"""
    
    def __init__(
        self,
        queue_config: QueueConfig,
        max_workers: int = 5,
        poll_interval: float = 1.0
    ):
        self.queue_config = queue_config
        self.max_workers = max_workers
        self.poll_interval = poll_interval
        self.queue: Optional[DistributedQueue] = None
        self.handler = TaskHandler()
        self._workers: List[asyncio.Task] = []
        self._running = False
    
    async def start(self) -> None:
        """Start the task manager and worker pool"""
        if self._running:
            return
        
        # Initialize the queue based on configuration
        if self.queue_config.queue_type == QueueType.REDIS:
            self.queue = RedisQueue(self.queue_config)
        else:
            raise ValueError(f"Unsupported queue type: {self.queue_config.queue_type}")
        
        # Connect to the queue
        await self.queue.connect()
        
        # Start worker tasks
        self._running = True
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i + 1}"))
            self._workers.append(worker)
        
        logger.info(f"Started {self.max_workers} workers")
    
    async def stop(self, timeout: float = 5.0) -> None:
        """Stop the task manager and all workers"""
        if not self._running:
            return
        
        logger.info("Stopping task manager...")
        self._running = False
        
        # Cancel all worker tasks
        for worker in self._workers:
            worker.cancel()
        
        # Wait for workers to complete
        if self._workers:
            await asyncio.wait(self._workers, timeout=timeout)
        
        # Disconnect from the queue
        if self.queue:
            await self.queue.disconnect()
        
        logger.info("Task manager stopped")
    
    async def _worker_loop(self, worker_id: str) -> None:
        """Worker task that processes tasks from the queue"""
        logger.info(f"Worker {worker_id} started")
        
        while self._running:
            try:
                # Get a task from the queue
                task = await self.queue.dequeue(timeout=int(self.poll_interval))
                if not task:
                    continue
                
                logger.info(f"Worker {worker_id} processing task {task.task_id}")
                
                try:
                    # Process the task
                    result = await self.handler.handle(task)
                    
                    # Store the result
                    if self.queue:
                        await self.queue.ack(task.task_id)
                        await self.queue.set_result(task.task_id, result)
                    
                    logger.info(f"Task {task.task_id} completed successfully")
                    
                except Exception as e:
                    logger.error(f"Error processing task {task.task_id}: {e}", exc_info=True)
                    
                    # Handle task failure
                    if self.queue:
                        await self.queue.nack(
                            task.task_id,
                            delay=min(60 * (task.retries or 1), 3600)  # Exponential backoff, max 1 hour
                        )
                    
                    logger.warning(f"Task {task.task_id} failed and will be retried")
            
            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} stopping...")
                break
            
            except Exception as e:
                logger.error(f"Error in worker {worker_id}: {e}", exc_info=True)
                await asyncio.sleep(1)  # Prevent tight loop on errors
        
        logger.info(f"Worker {worker_id} stopped")


#if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(example_usage()))
    
    try:
        loop.run_until_complete(example_usage())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        loop.close()

async def example_usage():
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create a queue configuration
    config = QueueConfig(
        queue_type="redis",
        url="redis://localhost:6379/0",
        queue_name="example_tasks"
    )
    
    # Create a task manager
    manager = DistributedTaskManager(
        queue_config=config,
        max_workers=3
    )
    
    # Define a task handler
    @manager.handler.register("example_task")
    async def example_handler(name: str) -> str:
        await asyncio.sleep(random.uniform(0.5, 2.0))  # Random delay
        return f"Processed: {name}"
    
    try:
        # Start the manager
        await manager.start()
        
        # Submit some tasks
        tasks = [
            {"name": "example_task", "args": [f"Task-{i}"]}
            for i in range(5)
        ]
        
        for task_data in tasks:
            task = Task(
                name=task_data["name"],
                args=task_data.get("args", []),
                kwargs=task_data.get("kwargs", {})
            )
            await manager.queue.enqueue(task)
            logger.info(f"Submitted task {task.task_id}")
        
        # Wait for tasks to complete
        await asyncio.sleep(5)
        
    except asyncio.CancelledError:
        logger.info("Received cancellation signal")
    except Exception as e:
        logger.error(f"Error in example: {e}", exc_info=True)
    finally:
        await manager.stop()
        manager = DistributedTaskManager(
            queue_config=config,
            handler=example_handler,
            num_workers=3
        )
        
        # Handle shutdown signals
        def handle_signal():
            print("\nShutting down...")
            asyncio.create_task(manager.stop())
        
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)
        
        try:
            # Start the manager
            await manager.start()
            
            # Submit some tasks
            tasks = []
            for i in range(10):
                task = Task(
                    name=f"task_{i}",
                    args=(i, i * 2),
                    kwargs={"priority": random.choice(["low", "normal", "high"])}
                )
                task_id = await manager.submit_task(task)
                tasks.append(task_id)
                print(f"Submitted task {task_id}")
            
            # Wait for tasks to complete
            print("Waiting for tasks to complete...")
            for task_id in tasks:
                while True:
                    result = await manager.get_task_result(task_id)
                    if result:
                        print(f"Task {task_id} result: {result}")
                        break
                    await asyncio.sleep(0.5)
            
            print("All tasks completed")
            
        except asyncio.CancelledError:
            print("Received cancellation signal")
        finally:
            # Clean up
            await manager.stop()
    
    # Run the example
    try:
        asyncio.run(run_example())
    except KeyboardInterrupt:
        print("\nShutting down...")
