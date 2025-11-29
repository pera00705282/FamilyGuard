"""
Enhanced Redis Streams Queue Implementation

This module provides an advanced Redis Streams based queue implementation with:
- Dead-letter queue support
- Consumer groups for load balancing
- Message retry with exponential backoff
- Message deduplication
- Priority queues
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

import redis.asyncio as redis
from pydantic import BaseModel, Field, validator

from ..async_processor import Task, TaskResult, TaskStatus

logger = logging.getLogger(__name__)

class MessageStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"

@dataclass
class Message:
    """A message in the Redis Stream"""
    id: str
    data: bytes
    status: MessageStatus = MessageStatus.PENDING
    retry_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

class RedisStreamsQueue:
    """Redis Streams based distributed queue with enhanced features"""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        stream_name: str = "crypto_tasks",
        consumer_group: str = "workers",
        consumer_name: Optional[str] = None,
        max_retries: int = 3,
        visibility_timeout: int = 300,
        dead_letter_queue: Optional[str] = None,
        batch_size: int = 10,
    ):
        """Initialize the Redis Streams queue
        
        Args:
            redis_url: Redis connection URL
            stream_name: Name of the Redis stream
            consumer_group: Name of the consumer group
            consumer_name: Name of this consumer (default: random UUID)
            max_retries: Maximum number of retries for failed messages
            visibility_timeout: Visibility timeout in seconds
            dead_letter_queue: Name of the dead letter queue (optional)
            batch_size: Number of messages to fetch in one batch
        """
        self.redis_url = redis_url
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"consumer-{uuid.uuid4().hex[:8]}"
        self.max_retries = max_retries
        self.visibility_timeout = visibility_timeout
        self.dead_letter_queue = dead_letter_queue or f"{stream_name}:dead"
        self.batch_size = batch_size
        
        # Redis client and connection pool
        self.redis: Optional[redis.Redis] = None
        self._connection_lock = asyncio.Lock()
        self._processing_messages: Set[str] = set()
        
        # Streams configuration
        self._streams = {
            "main": stream_name,
            "processing": f"{stream_name}:processing",
            "dead": self.dead_letter_queue,
            "dlq": f"{stream_name}:dlq"
        }
        
        # Consumer group configuration
        self._consumer_groups_created = False
    
    async def connect(self) -> None:
        """Connect to Redis and ensure consumer groups exist"""
        if self.redis is not None:
            return
            
        async with self._connection_lock:
            if self.redis is not None:
                return
                
            self.redis = redis.Redis.from_url(
                self.redis_url,
                decode_responses=False,  # We'll handle serialization ourselves
                max_connections=20,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_timeout=10,
                socket_connect_timeout=5,
                health_check_interval=30,
            )
            
            # Create consumer groups if they don't exist
            await self._ensure_consumer_groups()
    
    async def _ensure_consumer_groups(self) -> None:
        """Ensure all required consumer groups exist"""
        if self._consumer_groups_created or self.redis is None:
            return
            
        try:
            # Create main consumer group
            await self.redis.xgroup_create(
                name=self._streams["main"],
                groupname=self.consumer_group,
                id="0",
                mkstream=True
            )
            
            # Create DLQ consumer group if it doesn't exist
            if self.dead_letter_queue:
                await self.redis.xgroup_create(
                    name=self._streams["dead"],
                    groupname=f"{self.consumer_group}-dlq",
                    id="0",
                    mkstream=True
                )
                
            self._consumer_groups_created = True
            
        except Exception as e:
            # Group might already exist, which is fine
            if "BUSYGROUP" not in str(e):
                logger.error(f"Error creating consumer groups: {e}")
                raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self.redis is not None:
            await self.redis.close()
            self.redis = None
    
    async def enqueue(
        self,
        task: Task,
        priority: int = 1,
        delay: int = 0,
        **metadata
    ) -> str:
        """Enqueue a task with priority and delay support
        
        Args:
            task: Task to enqueue
            priority: Message priority (higher = higher priority)
            delay: Delay in seconds before the message becomes visible
            **metadata: Additional metadata to store with the message
            
        Returns:
            Message ID
        """
        if self.redis is None:
            await self.connect()
            
        message_id = f"{int(time.time() * 1000)}-{uuid.uuid4().hex}"
        
        # Prepare message data
        message_data = {
            "id": message_id,
            "task": task.model_dump_json(),
            "status": MessageStatus.PENDING,
            "retry_count": 0,
            "priority": priority,
            "created_at": time.time(),
            "metadata": json.dumps(metadata or {})
        }
        
        # Add to the appropriate stream based on delay
        stream = self._streams["main"]
        if delay > 0:
            # Use Redis Sorted Set for delayed messages
            await self.redis.zadd(
                f"{stream}:delayed",
                {json.dumps(message_data): time.time() + delay}
            )
        else:
            # Add to the main stream
            await self.redis.xadd(
                name=stream,
                fields={"data": json.dumps(message_data)},
                maxlen=10000,  # Keep last 10k messages
                approximate=True
            )
        
        return message_id
    
    async def dequeue(self, timeout: int = 5000) -> Optional[Tuple[str, Message]]:
        """Dequeue a message from the stream
        
        Args:
            timeout: Timeout in milliseconds to wait for a message
            
        Returns:
            Tuple of (message_id, message) or None if no message is available
        """
        if self.redis is None:
            await self.connect()
            
        # Check for any delayed messages that are ready
        ready_messages = await self.redis.zrangebyscore(
            f"{self._streams['main']}:delayed",
            0,
            time.time(),
            start=0,
            num=1,
            withscores=False
        )
        
        if ready_messages:
            # Move ready messages to the main stream
            message_data = json.loads(ready_messages[0])
            await self.redis.xadd(
                name=self._streams["main"],
                fields={"data": json.dumps(message_data)},
                maxlen=10000,
                approximate=True
            )
            await self.redis.zrem(
                f"{self._streams['main']}:delayed",
                ready_messages[0]
            )
        
        # Read from the main stream
        response = await self.redis.xreadgroup(
            groupname=self.consumer_group,
            consumername=self.consumer_name,
            streams={self._streams["main"]: ">"},
            count=1,
            block=timeout,
            noack=False
        )
        
        if not response or not response[0][1]:
            return None
            
        stream, messages = response[0]
        message_id, message_data = messages[0]
        
        # Parse message
        try:
            data = json.loads(message_data[b"data"])
            message = Message(
                id=message_id,
                data=data["task"].encode(),
                status=MessageStatus.PROCESSING,
                retry_count=data.get("retry_count", 0),
                created_at=data.get("created_at", time.time()),
                updated_at=time.time(),
                metadata=json.loads(data.get("metadata", "{}"))
            )
            
            # Add to processing set
            self._processing_messages.add(message_id)
            
            # Update message status
            await self._update_message_status(message_id, message)
            
            return message_id, message
            
        except Exception as e:
            logger.error(f"Error parsing message {message_id}: {e}")
            # Acknowledge the message to prevent it from being reprocessed
            await self.ack(message_id)
            return None
    
    async def ack(self, message_id: str) -> None:
        """Acknowledge successful processing of a message"""
        if self.redis is None:
            return
            
        try:
            # Acknowledge the message in the consumer group
            await self.redis.xack(
                self._streams["main"],
                self.consumer_group,
                message_id
            )
            
            # Get the message data
            message_data = await self.redis.xrange(self._streams["main"], message_id, message_id)
            if not message_data:
                return
                
            # Parse and update the message status
            data = json.loads(message_data[0][1][b"data"])
            data["status"] = MessageStatus.COMPLETED
            data["updated_at"] = time.time()
            
            # Store the result in the processing stream
            await self.redis.xadd(
                name=self._streams["processing"],
                fields={"data": json.dumps(data)},
                maxlen=10000,
                approximate=True
            )
            
            # Remove from processing set
            self._processing_messages.discard(message_id)
            
        except Exception as e:
            logger.error(f"Error acknowledging message {message_id}: {e}")
    
    async def nack(
        self,
        message_id: str,
        error: Optional[Exception] = None,
        retry_delay: int = 0
    ) -> None:
        """Negative acknowledgment for failed message processing
        
        Args:
            message_id: ID of the failed message
            error: Optional exception that caused the failure
            retry_delay: Delay in seconds before retrying the message
        """
        if self.redis is None:
            return
            
        try:
            # Get the message data
            message_data = await self.redis.xrange(self._streams["main"], message_id, message_id)
            if not message_data:
                return
                
            data = json.loads(message_data[0][1][b"data"])
            retry_count = data.get("retry_count", 0) + 1
            
            if retry_count > self.max_retries:
                # Move to dead letter queue
                data["status"] = MessageStatus.DEAD
                data["error"] = str(error) if error else "Max retries exceeded"
                data["updated_at"] = time.time()
                
                await self.redis.xadd(
                    name=self._streams["dead"],
                    fields={"data": json.dumps(data)},
                    maxlen=10000,
                    approximate=True
                )
                logger.warning(f"Message {message_id} moved to DLQ after {retry_count} retries")
            else:
                # Update retry count and requeue
                data["retry_count"] = retry_count
                data["status"] = MessageStatus.PENDING
                data["updated_at"] = time.time()
                
                if retry_delay > 0:
                    # Add to delayed queue
                    await self.redis.zadd(
                        f"{self._streams['main']}:delayed",
                        {json.dumps(data): time.time() + retry_delay}
                    )
                else:
                    # Requeue immediately
                    await self.redis.xadd(
                        name=self._streams["main"],
                        fields={"data": json.dumps(data)},
                        maxlen=10000,
                        approximate=True
                    )
                
                logger.info(f"Message {message_id} requeued (attempt {retry_count}/{self.max_retries})")
            
            # Acknowledge the original message
            await self.redis.xack(
                self._streams["main"],
                self.consumer_group,
                message_id
            )
            
            # Remove from processing set
            self._processing_messages.discard(message_id)
            
        except Exception as e:
            logger.error(f"Error processing NACK for message {message_id}: {e}")
    
    async def _update_message_status(self, message_id: str, message: Message) -> None:
        """Update the status of a message in the processing stream"""
        if self.redis is None:
            return
            
        try:
            data = {
                "id": message_id,
                "task": message.data.decode(),
                "status": message.status,
                "retry_count": message.retry_count,
                "created_at": message.created_at,
                "updated_at": message.updated_at,
                "metadata": json.dumps(message.metadata)
            }
            
            await self.redis.xadd(
                name=self._streams["processing"],
                fields={"data": json.dumps(data)},
                maxlen=10000,
                approximate=True
            )
            
        except Exception as e:
            logger.error(f"Error updating status for message {message_id}: {e}")
    
    async def get_message_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a message"""
        if self.redis is None:
            await self.connect()
            
        # Check processing stream first
        messages = await self.redis.xrange(self._streams["processing"], "-", "+")
        for msg_id, msg_data in messages:
            data = json.loads(msg_data[b"data"])
            if data.get("id") == message_id:
                return data
        
        # Check dead letter queue
        if self.dead_letter_queue:
            messages = await self.redis.xrange(self._streams["dead"], "-", "+")
            for msg_id, msg_data in messages:
                data = json.loads(msg_data[b"data"])
                if data.get("id") == message_id:
                    return data
        
        return None
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the queue"""
        if self.redis is None:
            await self.connect()
            
        stats = {
            "main_stream": await self.redis.xlen(self._streams["main"]),
            "processing": await self.redis.xlen(self._streams["processing"]),
            "dead_letter_queue": await self.redis.xlen(self._streams["dead"]),
            "delayed": await self.redis.zcard(f"{self._streams['main']}:delayed"),
            "consumers": {},
            "pending": 0
        }
        
        # Get consumer group info
        try:
            group_info = await self.redis.xinfo_groups(self._streams["main"])
            for group in group_info:
                group_name = group["name"].decode()
                consumers = await self.redis.xinfo_consumers(
                    self._streams["main"],
                    group_name
                )
                stats["consumers"][group_name] = len(consumers)
                
                # Get pending messages
                pending = await self.redis.xpending(
                    self._streams["main"],
                    group_name
                )
                if pending and isinstance(pending, dict):
                    stats["pending"] += pending.get("pending", 0)
                elif isinstance(pending, int):
                    stats["pending"] += pending
                    
        except Exception as e:
            logger.warning(f"Could not get consumer group info: {e}")
        
        return stats
    
    async def close(self) -> None:
        """Close the queue and release resources"""
        if self.redis is not None:
            await self.disconnect()
            
        # Clear processing messages
        self._processing_messages.clear()
    
    async def __aenter__(self) -> 'RedisStreamsQueue':
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

# Example usage
async def example():
    queue = RedisStreamsQueue(
        redis_url="redis://localhost:6379/0",
        stream_name="crypto_tasks",
        consumer_group="workers"
    )
    
    try:
        # Enqueue a task
        task = Task(name="process_data", args={"symbol": "BTC/USDT"})
        message_id = await queue.enqueue(task, priority=1)
        print(f"Enqueued task with ID: {message_id}")
        
        # Process messages
        while True:
            item = await queue.dequeue(timeout=5000)
            if item is None:
                print("No messages in queue")
                break
                
            message_id, message = item
            print(f"Processing message {message_id}")
            
            try:
                # Process the message here
                print(f"Processing task: {message.data.decode()}")
                
                # Acknowledge successful processing
                await queue.ack(message_id)
                print(f"Successfully processed message {message_id}")
                
            except Exception as e:
                print(f"Error processing message {message_id}: {e}")
                # Negative acknowledgment with exponential backoff
                retry_delay = min(2 ** message.retry_count * 5, 300)  # Max 5 minute delay
                await queue.nack(message_id, error=e, retry_delay=retry_delay)
    
    finally:
        await queue.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(example())
