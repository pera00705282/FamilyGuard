import time
import asyncio
from collections import defaultdict, deque
from typing import Dict, Deque, Optional
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Implements rate limiting for API requests."""
    
    def __init__(self, requests_per_minute: int = 60, burst_capacity: int = 5):
        self.requests_per_second = max(1, requests_per_minute / 60)
        self.burst_capacity = max(1, burst_capacity)
        self.request_times = defaultdict(deque)
        self.lock = asyncio.Lock()
        
    async def acquire(self, key: str = 'default') -> None:
        async with self.lock:
            now = time.time()
            self._cleanup_old_requests(key, now)
            
            if len(self.request_times[key]) >= self.burst_capacity:
                oldest_request = self.request_times[key][0]
                min_interval = 1.0 / self.requests_per_second
                next_allowed = oldest_request + min_interval
                
                if now < next_allowed:
                    sleep_time = next_allowed - now
                    logger.warning(
                        "Rate limit exceeded for %s, sleeping for %.2f seconds",
                        key, sleep_time
                    )
                    await asyncio.sleep(sleep_time)
            
            self.request_times[key].append(time.time())
            self._cleanup_old_requests(key, time.time())
    
    def _cleanup_old_requests(self, key: str, now: float) -> None:
        window_size = 60.0
        while (self.request_times[key] and 
               now - self.request_times[key][0] > window_size):
            self.request_times[key].popleft()
    
    def get_remaining_requests(self, key: str = 'default') -> int:
        now = time.time()
        self._cleanup_old_requests(key, now)
        return max(0, self.burst_capacity - len(self.request_times[key]))
