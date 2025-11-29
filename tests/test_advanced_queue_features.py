""
Tests for advanced queue features.
"""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch

from src.crypto_trading.performance.queue.advanced_features import (
    RateLimiter,
    BatchProcessor,
    BatchConfig,
    PriorityQueue,
    RateLimitedQueue
)

@pytest.fixture
def redis_mock():
    """Mock Redis client."""
    with patch('redis.asyncio.Redis') as mock:
        yield mock

@pytest.mark.asyncio
async def test_rate_limiter():
    """Test the rate limiter functionality."""
    # Test with 10 tokens per second, capacity 20
    limiter = RateLimiter(rate=10, capacity=20)
    
    # Should allow 20 tokens immediately (up to capacity)
    results = await asyncio.gather(*[limiter.acquire() for _ in range(20)])
    assert all(results)  # All should be True
    
    # Should not allow any more tokens immediately
    assert not await limiter.acquire()
    
    # After 0.1 seconds, should allow 1 more token
    await asyncio.sleep(0.11)
    assert await limiter.acquire()

@pytest.mark.asyncio
async def test_batch_processor():
    """Test the batch processor."""
    results = []
    
    async def process_batch(batch):
        results.append(batch)
    
    # Configure to batch up to 3 items or 0.1 seconds
    processor = BatchProcessor(
        process_batch=process_batch,
        config=BatchConfig(max_size=3, max_wait=0.1)
    )
    
    # Start the processor
    await processor.start()
    
    # Add 5 items
    for i in range(5):
        await processor.add(f"item_{i}")
    
    # Wait for processing
    await asyncio.sleep(0.15)
    
    # Should have processed at least one batch of 3
    assert len(results) >= 1
    assert len(results[0]) == 3
    
    # Clean up
    remaining = await processor.stop()
    assert len(remaining) <= 2  # Up to 2 items might remain

@pytest.mark.asyncio
async def test_priority_queue(redis_mock):
    """Test the priority queue."""
    # Setup mock Redis
    mock_redis = AsyncMock()
    redis_mock.return_value = mock_redis
    
    # Test pushing items
    queue = PriorityQueue(mock_redis, "test_queue")
    await queue.push("item1", priority=1)
    await queue.push("item2", priority=0)  # Higher priority
    
    # Should call LPUSH on the correct priority queue
    assert mock_redis.lpush.call_count == 2
    
    # Test popping items
    mock_redis.rpop.return_value = b"item2"
    item = await queue.pop()
    assert item == "item2"
    
    # Test size
    mock_redis.llen.return_value = 5
    size = await queue.size()
    assert size == 5 * 10  # 10 priority levels

@pytest.mark.asyncio
async def test_rate_limited_queue(redis_mock):
    """Test the rate-limited queue."""
    # Setup mock Redis
    mock_redis = AsyncMock()
    redis_mock.return_value = mock_redis
    
    # Mock Redis responses
    mock_redis.get.side_effect = [
        str(time.time() - 1).encode(),  # last_update
        b"5"  # tokens
    ]
    
    # Initialize queue with rate 10/s, burst 20
    queue = RateLimitedQueue(mock_redis, "test_queue", rate=10, burst=20)
    await queue.initialize()
    
    # Test can_process
    can_process = await queue.can_process()
    assert can_process
    
    # Test wait_until_ready
    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        await queue.wait_until_ready()
        mock_sleep.assert_not_called()  # Should not sleep if tokens available

if __name__ == "__main__":
    pytest.main(["-v", "test_advanced_queue_features.py"])
