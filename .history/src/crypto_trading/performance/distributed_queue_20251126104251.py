"""
Distributed Task Queue

This module provides a distributed task queue implementation using Redis as the
message broker for distributed task processing across multiple workers.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union

import aioredis
from pydantic import BaseModel, Field, validator

# Re-export Task and TaskStatus from async_processor
from ..performance.async_processor import Task, TaskStatus

logger = logging.getLogger(__name__)

# Type variables
T = TypeVar('T')

class QueueType(str, Enum):
    """Types of distributed queues"""
    REDIS = "redis"
    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"

class QueueConfig(BaseModel):
    """Configuration for a distributed queue"""
    queue_type: QueueType = QueueType.REDIS
    url: str = "redis://localhost:6379/0"
    queue_name: str = "crypto_trading_tasks"
    result_ttl: int = 86400  # 24 hours
    max_retries: int = 3
    visibility_timeout: int = 1800  # 30 minutes
    
    class Config:
        json_encoders = {
            QueueType: lambda v: v.value,
        }

class DistributedQueue(ABC):
    """Abstract base class for distributed task queues"""
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to the queue service"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the queue service"""
        pass
    
    @abstractmethod
    async def enqueue(self, task: Task) -> str:
        """Add a task to the queue"""
        pass
    
    @abstractmethod
    async def dequeue(self, timeout: float = 0) -> Optional[Task]:
        """Get a task from the queue"""
        pass
    
    @abstractmethod
    async def ack(self, task_id: str) -> None:
        """Acknowledge task completion"""
        pass
    
    @abstractmethod
    async def nack(self, task_id: str) -> None:
        """Negative acknowledge task (requeue)"""
        pass
    
    @abstractmethod
    async def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the result of a completed task"""
        pass
    
    @abstractmethod
    async def set_result(self, task_id: str, result: Dict[str, Any]) -> None:
        """Set the result of a completed task"""
        pass

class RedisQueue(DistributedQueue):
    """Redis-based distributed task queue"""
    
    def __init__(self, config: QueueConfig):
        self.config = config
        self.redis: Optional[aioredis.Redis] = None
        self._connected = False
    
    async def connect(self) -> None:
        """Connect to Redis"""
        if self._connected:
            return
            
        try:
            self.redis = await aioredis.from_url(
                self.config.url,
                encoding="utf-8",
                decode_responses=True
            )
            self._connected = True
            logger.info(f"Connected to Redis at {self.config.url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self.redis and self._connected:
            await self.redis.close()
            await self.redis.connection_pool.disconnect()
            self._connected = False
            logger.info("Disconnected from Redis")
    
    def _get_queue_key(self) -> str:
        """Get the Redis key for the task queue"""
        return f"queue:{self.config.queue_name}"
    
    def _get_result_key(self, task_id: str) -> str:
        """Get the Redis key for a task result"""
        return f"task:{task_id}:result"
    
    async def enqueue(self, task: Task) -> str:
        """Add a task to the queue"""
        if not self.redis or not self._connected:
            raise RuntimeError("Not connected to Redis")
        
        # Ensure task has an ID
        if not task.task_id:
            task.task_id = str(uuid.uuid4())
        
        # Serialize task data
        task_data = task.json()
        
        # Add to the queue
        await self.redis.lpush(self._get_queue_key(), task_data)
        logger.debug(f"Enqueued task {task.task_id}")
        
        return task.task_id
    
    async def dequeue(self, timeout: float = 0) -> Optional[Task]:
        """Get a task from the queue"""
        if not self.redis or not self._connected:
            raise RuntimeError("Not connected to Redis")
        
        # Get a task from the queue with timeout
        queue_key = self._get_queue_key()
        task_data = await self.redis.brpop(queue_key, timeout=timeout)
        
        if not task_data:
            return None
            
        # task_data is a tuple: (queue_name, task_data)
        _, task_json = task_data
        
        try:
            task_dict = json.loads(task_json)
            return Task(**task_dict)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse task data: {e}")
            return None
    
    async def ack(self, task_id: str) -> None:
        """Acknowledge task completion"""
        # In Redis, tasks are removed from the queue when dequeued,
        # so we just need to clean up any processing state
        logger.debug(f"Acknowledged task {task_id}")
    
    async def nack(self, task_id: str) -> None:
        """Negative acknowledge task (requeue)"""
        if not self.redis or not self._connected:
            raise RuntimeError("Not connected to Redis")
        
        # Get the task result to requeue
        result_key = self._get_result_key(task_id)
        task_data = await self.redis.get(result_key)
        
        if task_data:
            # Requeue the task
            await self.redis.lpush(self._get_queue_key(), task_data)
            logger.debug(f"Requeued task {task_id}")
    
    async def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the result of a completed task"""
        if not self.redis or not self._connected:
            raise RuntimeError("Not connected to Redis")
        
        result_key = self._get_result_key(task_id)
        result_data = await self.redis.get(result_key)
        
        if not result_data:
            return None
            
        try:
            return json.loads(result_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse result for task {task_id}: {e}")
            return None
    
    async def set_result(self, task_id: str, result: Dict[str, Any]) -> None:
        """Set the result of a completed task"""
        if not self.redis or not self._connected:
            raise RuntimeError("Not connected to Redis")
        
        result_key = self._get_result_key(task_id)
        await self.redis.set(
            result_key,
            json.dumps(result),
            ex=self.config.result_ttl
        )
        logger.debug(f"Set result for task {task_id}")


class DistributedTaskManager:
    """Manages distributed task execution across multiple workers"""
    
    def __init__(
        self,
        queue_config: QueueConfig,
        handler: Optional[Callable[[Task], Awaitable[Dict[str, Any]]]] = None,
        num_workers: int = 4,
        poll_interval: float = 0.1,
    ):
        self.queue_config = queue_config
        self.handler = handler
        self.num_workers = num_workers
        self.poll_interval = poll_interval
        
        self.queue: Optional[DistributedQueue] = None
        self._running = False
        self._workers: Set[asyncio.Task] = set()
    
    async def start(self) -> None:
        """Start the distributed task manager and workers"""
        if self._running:
            return
            
        # Initialize the queue based on config
        if self.queue_config.queue_type == QueueType.REDIS:
            self.queue = RedisQueue(self.queue_config)
        else:
            raise ValueError(f"Unsupported queue type: {self.queue_config.queue_type}")
        
        # Connect to the queue
        await self.queue.connect()
        
        # Start worker tasks
        self._running = True
        for i in range(self.num_workers):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.add(worker)
            worker.add_done_callback(self._workers.remove)
        
        logger.info(f"Started {self.num_workers} workers")
    
    async def stop(self) -> None:
        """Stop the distributed task manager and workers"""
        if not self._running:
            return
            
        self._running = False
        
        # Cancel all worker tasks
        for worker in list(self._workers):
            worker.cancel()
        
        # Wait for workers to finish
        if self._workers:
            await asyncio.wait(self._workers)
        
        # Disconnect from the queue
        if self.queue:
            await self.queue.disconnect()
        
        logger.info("Stopped all workers")
    
    async def _worker_loop(self, worker_id: str) -> None:
        """Worker task that processes tasks from the queue"""
        logger.info(f"Worker {worker_id} started")
        
        while self._running and self.queue:
            try:
                # Get a task from the queue with a small timeout
                task = await self.queue.dequeue(timeout=self.poll_interval)
                if not task:
                    continue
                
                logger.debug(f"Worker {worker_id} processing task {task.task_id}")
                
                try:
                    # Process the task
                    if self.handler:
                        result = await self.handler(task)
                    else:
                        result = {"status": "no_handler", "task_id": str(task.task_id)}
                    
                    # Store the result
                    await self.queue.set_result(str(task.task_id), result)
                    await self.queue.ack(str(task.task_id))
                    
                    logger.debug(f"Worker {worker_id} completed task {task.task_id}")
                    
                except Exception as e:
                    logger.error(f"Error processing task {task.task_id}: {e}", exc_info=True)
                    await self.queue.nack(str(task.task_id))
                
            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} received cancellation signal")
                break
                
            except Exception as e:
                logger.error(f"Error in worker {worker_id}: {e}", exc_info=True)
                await asyncio.sleep(1)  # Prevent tight loop on errors
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def submit_task(self, task: Task) -> str:
        """Submit a task to the distributed queue"""
        if not self.queue:
            raise RuntimeError("Queue not initialized")
        
        return await self.queue.enqueue(task)
    
    async def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the result of a task"""
        if not self.queue:
            return None
            
        return await self.queue.get_result(task_id)


# Example usage
if __name__ == "__main__":
    import random
    import signal
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    async def example_handler(task: Task) -> Dict[str, Any]:
        """Example task handler"""
        # Simulate work
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        # Process the task
        result = {
            "status": "completed",
            "task_id": str(task.task_id),
            "result": f"Processed {task.name} with args={task.args} and kwargs={task.kwargs}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return result
    
    async def run_example():
        # Create a queue config
        config = QueueConfig(
            queue_type=QueueType.REDIS,
            url="redis://localhost:6379/0",
            queue_name="example_tasks"
        )
        
        # Create and start the task manager
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
