"""
Asynchronous Task Processing System

This module provides a high-performance asynchronous task processing system
with task queuing, worker pools, and distributed execution capabilities.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import (
    Any,
    Awaitable,
    Callable,
    Deque,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID, uuid4

import aio_pika
from pydantic import BaseModel, Field, validator

# Configure logging
logger = logging.getLogger(__name__)

# Type variables for generic task handling
T = TypeVar("T")
R = TypeVar("R")


class TaskStatus(str, Enum):
    """Status of an asynchronous task"""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(int, Enum):
    """Priority levels for task execution"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class TaskResult(BaseModel):
    """Result of a task execution"""

    task_id: UUID = Field(default_factory=uuid4)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    retries: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def duration(self) -> Optional[float]:
        """Get the task execution duration in seconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the task result to a dictionary"""
        return self.dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskResult":
        """Create a TaskResult from a dictionary"""
        return cls(**data)


class Task(BaseModel):
    """Represents an asynchronous task"""

    task_id: UUID = Field(default_factory=uuid4)
    name: str
    args: Tuple[Any, ...] = Field(default_factory=tuple)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    max_retries: int = 3
    timeout: Optional[float] = None  # seconds
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    depends_on: List[UUID] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: str,
        }

    @validator("task_id", pre=True, always=True)
    def validate_task_id(cls, v):
        """Ensure task_id is a UUID"""
        if isinstance(v, str):
            return UUID(v)
        return v or uuid4()

    def to_dict(self) -> Dict[str, Any]:
        """Convert the task to a dictionary"""
        return self.dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create a Task from a dictionary"""
        return cls(**data)

    def set_result(
        self, result: Any = None, error: Optional[Exception] = None
    ) -> None:
        """Set the task result"""
        now = datetime.utcnow()
        
        if not self.result:
            self.result = TaskResult(task_id=self.task_id)
            
        self.result.end_time = now
        
        if error:
            self.status = TaskStatus.FAILED
            self.result.status = TaskStatus.FAILED
            self.result.error = str(error)
        else:
            self.status = TaskStatus.COMPLETED
            self.result.status = TaskStatus.COMPLETED
            self.result.result = result


class TaskHandler(ABC):
    """Base class for task handlers"""

    @abstractmethod
    async def handle(self, task: Task) -> Any:
        """Process the task and return the result"""
        pass


class TaskQueue(ABC):
    """Abstract base class for task queues"""

    @abstractmethod
    async def enqueue(self, task: Task) -> None:
        """Add a task to the queue"""
        pass

    @abstractmethod
    async def dequeue(self) -> Optional[Task]:
        """Get the next task from the queue"""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get the number of tasks in the queue"""
        pass


class InMemoryTaskQueue(TaskQueue):
    """In-memory implementation of a task queue"""

    def __init__(self):
        self._queues = {
            priority: deque() for priority in TaskPriority
        }
        self._lock = asyncio.Lock()
        self._task_map: Dict[UUID, asyncio.Future] = {}

    async def enqueue(self, task: Task) -> None:
        """Add a task to the queue"""
        async with self._lock:
            self._queues[task.priority].append(task)
            # Create a future that will be set when the task is complete
            if task.task_id not in self._task_map:
                self._task_map[task.task_id] = asyncio.Future()

    async def dequeue(self) -> Optional[Task]:
        """Get the next task from the queue"""
        async with self._lock:
            # Get the highest priority non-empty queue
            for priority in sorted(TaskPriority, reverse=True):
                if self._queues[priority]:
                    return self._queues[priority].popleft()
            return None

    async def size(self) -> int:
        """Get the total number of tasks in the queue"""
        async with self._lock:
            return sum(len(q) for q in self._queues.values())

    async def get_task_future(self, task_id: UUID) -> asyncio.Future:
        """Get the future associated with a task"""
        async with self._lock:
            if task_id not in self._task_map:
                self._task_map[task_id] = asyncio.Future()
            return self._task_map[task_id]

    async def set_task_result(self, task_id: UUID, result: Any) -> None:
        """Set the result for a task"""
        async with self._lock:
            if task_id in self._task_map and not self._task_map[task_id].done():
                self._task_map[task_id].set_result(result)

    async def set_task_exception(self, task_id: UUID, exc: Exception) -> None:
        """Set an exception for a task"""
        async with self._lock:
            if task_id in self._task_map and not self._task_map[task_id].done():
                self._task_map[task_id].set_exception(exc)


class TaskWorker:
    """Worker that processes tasks from a queue"""

    def __init__(
        self,
        queue: TaskQueue,
        handler: TaskHandler,
        worker_id: Optional[str] = None,
        max_concurrent_tasks: int = 10,
    ):
        self.queue = queue
        self.handler = handler
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.max_concurrent_tasks = max_concurrent_tasks
        self._running = False
        self._current_tasks: Set[asyncio.Task] = set()
        self._task_handlers: Dict[str, Callable[[Task], Awaitable[Any]]] = {}

    async def start(self) -> None:
        """Start the worker"""
        self._running = True
        logger.info(f"Starting worker {self.worker_id}")
        
        while self._running:
            try:
                # Limit concurrent tasks
                if len(self._current_tasks) >= self.max_concurrent_tasks:
                    await asyncio.sleep(0.1)
                    continue

                # Get the next task
                task = await self.queue.dequeue()
                if not task:
                    await asyncio.sleep(0.1)
                    continue

                # Process the task
                task.status = TaskStatus.RUNNING
                task_result = TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.RUNNING,
                    start_time=datetime.utcnow(),
                )

                # Create a task to process in the background
                task_future = asyncio.create_task(self._process_task(task))
                self._current_tasks.add(task_future)
                task_future.add_done_callback(
                    lambda f, t=task: self._current_tasks.discard(t)
                )

            except asyncio.CancelledError:
                logger.info(f"Worker {self.worker_id} received cancellation signal")
                self._running = False
                break
            except Exception as e:
                logger.error(f"Error in worker {self.worker_id}: {e}", exc_info=True)
                await asyncio.sleep(1)  # Prevent tight loop on errors

    async def _process_task(self, task: Task) -> None:
        """Process a single task"""
        task_id = task.task_id
        logger.info(f"Processing task {task_id}")

        try:
            # Handle the task
            result = await self.handler.handle(task)
            
            # Update task status and result
            task.set_result(result=result)
            
            # Set the future result
            if isinstance(self.queue, InMemoryTaskQueue):
                await self.queue.set_task_result(task_id, result)
                
            logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}", exc_info=True)
            
            # Update task status with error
            task.set_result(error=e)
            
            # Set the future exception
            if isinstance(self.queue, InMemoryTaskQueue):
                await self.queue.set_task_exception(task_id, e)

    async def stop(self) -> None:
        """Stop the worker"""
        self._running = False
        # Wait for current tasks to complete
        if self._current_tasks:
            await asyncio.wait(self._current_tasks)


class TaskManager:
    """Manages task execution with multiple workers"""

    def __init__(
        self,
        queue: Optional[TaskQueue] = None,
        num_workers: int = 4,
        max_concurrent_tasks: int = 10,
        handler: Optional[TaskHandler] = None,
    ):
        self.queue = queue or InMemoryTaskQueue()
        self.num_workers = num_workers
        self.max_concurrent_tasks = max_concurrent_tasks
        self.handler = handler or DefaultTaskHandler()
        self.workers: List[TaskWorker] = []
        self._running = False

    async def start(self) -> None:
        """Start the task manager and all workers"""
        if self._running:
            return

        self._running = True
        logger.info(f"Starting task manager with {self.num_workers} workers")

        # Create and start workers
        self.workers = [
            TaskWorker(
                queue=self.queue,
                handler=self.handler,
                worker_id=f"worker-{i}",
                max_concurrent_tasks=self.max_concurrent_tasks,
            )
            for i in range(self.num_workers)
        ]

        # Start all workers
        for worker in self.workers:
            asyncio.create_task(worker.start())

    async def stop(self) -> None:
        """Stop the task manager and all workers"""
        if not self._running:
            return

        logger.info("Stopping task manager and workers")
        self._running = False

        # Stop all workers
        await asyncio.gather(
            *(worker.stop() for worker in self.workers), return_exceptions=True
        )
        self.workers.clear()

    async def submit_task(
        self,
        name: str,
        *args: Any,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> UUID:
        """Submit a new task to the queue"""
        task = Task(
            name=name,
            args=args,
            kwargs=kwargs,
            priority=priority,
            max_retries=max_retries,
            timeout=timeout,
        )
        
        await self.queue.enqueue(task)
        logger.debug(f"Submitted task {task.task_id} ({name})")
        return task.task_id

    async def get_task_result(self, task_id: UUID) -> Optional[TaskResult]:
        """Get the result of a task"""
        if isinstance(self.queue, InMemoryTaskQueue):
            try:
                future = await self.queue.get_task_future(task_id)
                if future.done():
                    if future.exception():
                        return TaskResult(
                            task_id=task_id,
                            status=TaskStatus.FAILED,
                            error=str(future.exception()),
                        )
                    return future.result()
            except Exception as e:
                logger.error(f"Error getting task result: {e}")
        return None

    async def wait_for_task(
        self, task_id: UUID, timeout: Optional[float] = None
    ) -> Any:
        """Wait for a task to complete and return its result"""
        if not isinstance(self.queue, InMemoryTaskQueue):
            raise NotImplementedError("wait_for_task is only supported with InMemoryTaskQueue")

        future = await self.queue.get_task_future(task_id)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Task {task_id} timed out after {timeout} seconds")


class DefaultTaskHandler(TaskHandler):
    """Default task handler that executes Python functions"""

    def __init__(self):
        self.registry: Dict[str, Callable[..., Awaitable[Any]]] = {}

    def register(self, name: Optional[str] = None):
        """Decorator to register a function as a task handler"""
        def decorator(func: Callable[..., Awaitable[Any]]):
            task_name = name or func.__name__
            self.registry[task_name] = func
            return func
        return decorator

    async def handle(self, task: Task) -> Any:
        """Handle a task by executing the registered function"""
        if task.name not in self.registry:
            raise ValueError(f"No handler registered for task '{task.name}'")

        handler = self.registry[task.name]
        return await handler(*task.args, **task.kwargs)


# Example usage
if __name__ == "__main__":
    import random
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create a task handler
    handler = DefaultTaskHandler()
    
    # Register some tasks
    @handler.register("add_numbers")
    async def add(a: int, b: int) -> int:
        """Add two numbers"""
        await asyncio.sleep(random.uniform(0.1, 0.5))  # Simulate work
        return a + b
    
    @handler.register("multiply_numbers")
    async def multiply(a: int, b: int) -> int:
        """Multiply two numbers"""
        await asyncio.sleep(random.uniform(0.1, 0.5))  # Simulate work
        return a * b
    
    async def main():
        # Create a task manager
        manager = TaskManager(num_workers=4, handler=handler)
        
        try:
            # Start the task manager
            await manager.start()
            
            # Submit some tasks
            tasks = []
            for i in range(10):
                task_name = random.choice(["add_numbers", "multiply_numbers"])
                a, b = random.randint(1, 100), random.randint(1, 100)
                
                task_id = await manager.submit_task(
                    name=task_name,
                    a=a,
                    b=b,
                    priority=random.choice(list(TaskPriority)),
                )
                tasks.append((task_id, task_name, a, b))
            
            # Wait for tasks to complete and print results
            for task_id, task_name, a, b in tasks:
                try:
                    result = await manager.wait_for_task(task_id, timeout=10)
                    print(f"{task_name}({a}, {b}) = {result}")
                except Exception as e:
                    print(f"Task {task_name}({a}, {b}) failed: {e}")
        finally:
            # Clean up
            await manager.stop()
    
    # Run the example
    asyncio.run(main())
