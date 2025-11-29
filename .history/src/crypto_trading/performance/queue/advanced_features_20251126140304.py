"""
Advanced queue features including rate limiting, batching, and priority handling.
"""
import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Deque, Callable, Awaitable, TypeVar, Generic, Union
import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

T = TypeVar('T')

class RateLimiter:
    """Token bucket rate limiter for controlling access to resources."""
    
    def __init__(self, rate: float, capacity: int):
        """
        Initialize the rate limiter.
        
        Args:
            rate: Number of tokens added per second
            capacity: Maximum number of tokens in the bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens from the bucket."""
        async with self._lock:
            now = time.monotonic()
            time_passed = now - self.last_update
            self.last_update = now
            
            # Add tokens based on time passed
            self.tokens = min(
                self.capacity,
                self.tokens + time_passed * self.rate
            )
            
            # Check if we have enough tokens
            if tokens <= self.tokens:
                self.tokens -= tokens
                return True
            return False
    
    async def wait(self, tokens: int = 1) -> None:
        """Wait until tokens are available."""
        while not await self.acquire(tokens):
            # Calculate how long to wait for the next token
            wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(max(0, wait_time))


@dataclass
class BatchConfig:
    """Configuration for message batching."""
    max_size: int = 100
    max_wait: float = 1.0  # seconds
    

class BatchProcessor(Generic[T]):
    """Processes messages in batches for improved throughput."""
    
    def __init__(
        self,
        process_batch: Callable[[List[T]], Awaitable[Any]],
        config: Optional[BatchConfig] = None
    ):
        """
        Initialize the batch processor.
        
        Args:
            process_batch: Async function to process a batch of messages
            config: Batch configuration
        """
        self.process_batch = process_batch
        self.config = config or BatchConfig()
        self.queue: asyncio.Queue[T] = asyncio.Queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def add(self, item: T) -> None:
        """Add an item to be processed."""
        await self.queue.put(item)
    
    async def start(self) -> None:
        """Start the batch processing loop."""
        if self._running:
            return
            
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
    
    async def stop(self) -> List[T]:
        """Stop processing and return any remaining items."""
        if not self._running or not self._task:
            return []
            
        self._running = False
        self._task.cancel()
        
        try:
            await self._task
        except asyncio.CancelledError:
            pass
            
        # Return any remaining items
        remaining = []
        while not self.queue.empty():
            remaining.append(await self.queue.get())
        return remaining
    
    async def _process_loop(self) -> None:
        """Process items in batches."""
        batch: List[T] = []
        last_process = time.monotonic()
        
        while self._running:
            try:
                # Wait for the next item with a timeout
                try:
                    timeout = max(0, last_process + self.config.max_wait - time.monotonic())
                    item = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                    batch.append(item)
                except asyncio.TimeoutError:
                    pass
                
                # Check if we should process the batch
                current_time = time.monotonic()
                if (len(batch) >= self.config.max_size or 
                    (batch and current_time - last_process >= self.config.max_wait)):
                    if batch:
                        await self._safe_process_batch(batch)
                        batch = []
                        last_process = current_time
                        
            except asyncio.CancelledError:
                # Process any remaining items before exiting
                if batch:
                    await self._safe_process_batch(batch)
                raise
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on errors
    
    async def _safe_process_batch(self, batch: List[T]) -> None:
        """Safely process a batch, handling any errors."""
        try:
            await self.process_batch(batch)
        except Exception as e:
            logger.error(f"Failed to process batch: {e}")


class PriorityQueue:
    """A priority queue implementation using Redis sorted sets."""
    
    def __init__(
        self,
        redis: Redis,
        key: str,
        max_priority: int = 10
    ):
        """
        Initialize the priority queue.
        
        Args:
            redis: Redis client
            key: Redis key for the queue
            max_priority: Maximum priority level (higher is more important)
        """
        self.redis = redis
        self.key = key
        self.max_priority = max_priority
        self.priority_queues = [f"{key}:{i}" for i in range(max_priority)]
    
    async def push(self, item: str, priority: int = 0) -> None:
        """Push an item to the queue with the given priority."""
        priority = max(0, min(priority, self.max_priority - 1))
        queue_key = self.priority_queues[priority]
        await self.redis.lpush(queue_key, item)
    
    async def pop(self, timeout: float = 0) -> Optional[str]:
        """Pop the highest priority item from the queue."""
        # Try each priority queue in order
        for queue_key in self.priority_queues:
            item = await self.redis.rpop(queue_key)
            if item is not None:
                return item.decode()
        
        # If no items, wait for one with timeout
        if timeout > 0:
            result = await self.redis.brpop(
                *self.priority_queues,
                timeout=timeout
            )
            if result:
                return result[1].decode()
        
        return None
    
    async def size(self) -> int:
        """Get the total number of items in all priority queues."""
        total = 0
        for queue in self.priority_queues:
            total += await self.redis.llen(queue)
        return total


class RateLimitedQueue:
    """A queue with rate limiting capabilities."""
    
    def __init__(
        self,
        redis: Redis,
        queue_name: str,
        rate: float = 10.0,  # items per second
        burst: int = 100
    ):
        """
        Initialize the rate-limited queue.
        
        Args:
            redis: Redis client
            queue_name: Base name for Redis keys
            rate: Maximum processing rate (items/second)
            burst: Maximum burst capacity
        """
        self.redis = redis
        self.queue_name = queue_name
        self.rate = rate
        self.burst = burst
        self.last_update_key = f"{queue_name}:last_update"
        self.tokens_key = f"{queue_name}:tokens"
    
    async def initialize(self) -> None:
        """Initialize the rate limiter state in Redis."""
        now = time.time()
        async with self.redis.pipeline() as pipe:
            await (pipe
                .set(self.last_update_key, now, nx=True)
                .set(self.tokens_key, self.burst, nx=True)
                .execute()
            )
    
    async def can_process(self, tokens: int = 1) -> bool:
        """Check if we can process an item without waiting."""
        now = time.time()
        
        async with self.redis.pipeline() as pipe:
            results = await (pipe
                .get(self.last_update_key)
                .get(self.tokens_key)
                .execute()
            )
            
        last_update = float(results[0] or now)
        current_tokens = float(results[1] or self.burst)
        
        # Add tokens based on time passed
        time_passed = now - last_update
        new_tokens = time_passed * self.rate
        current_tokens = min(
            self.burst,
            current_tokens + new_tokens
        )
        
        # Check if we have enough tokens
        if tokens <= current_tokens:
            # Update tokens and last update time
            await self.redis.set(self.tokens_key, current_tokens - tokens)
            await self.redis.set(self.last_update_key, now)
            return True
            
        return False
    
    async def wait_until_ready(self, tokens: int = 1) -> None:
        """Wait until we can process an item."""
        while not await self.can_process(tokens):
            # Calculate how long to wait
            now = time.time()
            last_update = float(await self.redis.get(self.last_update_key) or now)
            current_tokens = float(await self.redis.get(self.tokens_key) or self.burst)
            
            # Calculate when we'll have enough tokens
            tokens_needed = tokens - current_tokens
            wait_time = max(0, tokens_needed / self.rate - (now - last_update))
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)


# Example usage
async def example():
    # Initialize Redis
    redis_client = Redis.from_url("redis://localhost:6379/0")
    
    # Rate limiting example
    rate_limiter = RateLimiter(rate=10, capacity=100)
    
    # Batch processing example
    async def process_messages(messages):
        print(f"Processing batch of {len(messages)} messages")
        
    batch_processor = BatchProcessor(process_messages, BatchConfig(max_size=10, max_wait=1.0))
    await batch_processor.start()
    
    # Priority queue example
    priority_queue = PriorityQueue(redis_client, "my_priority_queue")
    
    # Rate-limited queue example
    rate_limited_queue = RateLimitedQueue(redis_client, "my_rate_limited_queue", rate=5.0)
    await rate_limited_queue.initialize()
    
    # Clean up
    await redis_client.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(example())
