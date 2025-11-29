"""
Task Scheduler for Crypto Trading Automation

This module provides a flexible task scheduling system that integrates with the
asynchronous task processing and distributed queue systems.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import BaseModel, Field

from ..performance.async_processor import Task, TaskPriority, TaskStatus
from ..performance.distributed_queue import DistributedTaskManager, QueueConfig

logger = logging.getLogger(__name__)

class TaskSchedule(BaseModel):
    """Configuration for a scheduled task"""
    name: str
    task_name: str
    args: Tuple[Any, ...] = Field(default_factory=tuple)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    enabled: bool = True
    max_instances: int = 1
    misfire_grace_time: int = 60  # seconds
    
    # Schedule configuration (one of these should be set)
    interval: Optional[Union[int, float]] = None  # seconds
    cron: Optional[str] = None  # cron expression
    time_of_day: Optional[str] = None  # HH:MM
    
    # Task metadata
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

class TaskScheduler:
    """Schedules and manages automated tasks"""
    
    def __init__(
        self,
        task_manager: Optional[DistributedTaskManager] = None,
        queue_config: Optional[QueueConfig] = None,
        timezone: str = "UTC"
    ):
        """Initialize the task scheduler"""
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.task_manager = task_manager or self._create_default_task_manager(queue_config)
        # Map schedule_id to job_id
        self.scheduled_jobs: Dict[str, str] = {}
        self.running = False
    
    def _create_default_task_manager(self, queue_config: Optional[QueueConfig]) -> DistributedTaskManager:
        """Create a default task manager if none is provided"""
        if queue_config is None:
            queue_config = QueueConfig(
                queue_type="redis",
                url="redis://localhost:6379/0",
                queue_name="crypto_trading_tasks"
            )
        return DistributedTaskManager(queue_config=queue_config)
    
    async def start(self) -> None:
        """Start the scheduler and task manager"""
        if self.running:
            return
            
        logger.info("Starting task scheduler...")
        await self.task_manager.start()
        self.scheduler.start()
        self.running = True
        logger.info("Task scheduler started")
    
    async def stop(self) -> None:
        """Stop the scheduler and task manager"""
        if not self.running:
            return
            
        logger.info("Stopping task scheduler...")
        self.scheduler.shutdown()
        await self.task_manager.stop()
        self.running = False
        logger.info("Task scheduler stopped")
    
    def schedule_task(self, schedule: TaskSchedule) -> str:
        """Schedule a new task"""
        if not schedule.enabled:
            return ""
            
        # Create a unique ID for this schedule
        schedule_id = f"{schedule.name}_{len(self.scheduled_jobs)}"
        
        # Determine the trigger
        trigger = self._create_trigger(schedule)
        if not trigger:
            raise ValueError("No valid schedule configuration provided")
        
        # Create the job
        job = self.scheduler.add_job(
            self._execute_task,
            trigger=trigger,
            args=(schedule,),
            id=schedule_id,
            name=schedule.name,
            max_instances=schedule.max_instances,
            misfire_grace_time=schedule.misfire_grace_time,
            replace_existing=True
        )
        
        self.scheduled_jobs[schedule_id] = job.id
        logger.info(f"Scheduled task '{schedule.name}' with ID {schedule_id}")
        return schedule_id
    
    def _create_trigger(self, schedule: TaskSchedule):
        """Create an APScheduler trigger from a schedule configuration"""
        if schedule.interval is not None:
            return IntervalTrigger(seconds=schedule.interval)
        elif schedule.cron is not None:
            return CronTrigger.from_crontab(schedule.cron)
        elif schedule.time_of_day is not None:
            # Parse HH:MM format
            hour, minute = map(int, schedule.time_of_day.split(':'))
            return CronTrigger(hour=hour, minute=minute)
        return None
    
    async def _execute_task(self, schedule: TaskSchedule) -> None:
        """Execute a scheduled task"""
        if not self.running:
            return
            
        logger.info(f"Executing scheduled task: {schedule.name}")
        
        # Create and submit the task
        task = Task(
            name=schedule.task_name,
            args=schedule.args,
            kwargs=schedule.kwargs,
            priority=schedule.priority,
            metadata={
                "scheduled": True,
                "schedule_name": schedule.name,
                "tags": schedule.tags
            }
        )
        
        try:
            await self.task_manager.submit_task(task)
            logger.debug(f"Submitted task {task.task_id} for schedule '{schedule.name}'")
        except Exception as e:
            logger.error(f"Failed to submit task for schedule '{schedule.name}': {e}")
    
    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a scheduled task"""
        if schedule_id not in self.scheduled_jobs:
            return False
            
        job_id = self.scheduled_jobs[schedule_id]
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            
        del self.scheduled_jobs[schedule_id]
        logger.info(f"Removed schedule: {schedule_id}")
        return True
    
    def list_schedules(self) -> List[Dict[str, Any]]:
        """List all scheduled tasks"""
        schedules = []
        for schedule_id, job_id in self.scheduled_jobs.items():
            job = self.scheduler.get_job(job_id)
            if job:
                schedules.append({
                    "id": schedule_id,
                    "name": job.name,
                    "next_run": str(job.next_run_time),
                    "trigger": str(job.trigger)
                })
        return schedules

# Example task handlers that can be registered with the task manager
class TaskHandlers:
    """Example task handlers for common operations"""
    
    @staticmethod
    async def fetch_market_data(symbol: str, interval: str = "1h") -> dict:
        """Fetch market data for a symbol"""
        # This would be implemented to fetch actual market data
        logger.info(f"Fetching {interval} market data for {symbol}")
        await asyncio.sleep(1)  # Simulate API call
        return {
            "symbol": symbol,
            "interval": interval,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {"open": 50000, "high": 51000, "low": 49500, "close": 50500, "volume": 1000}
        }
    
    @staticmethod
    async def analyze_market(symbol: str, indicators: List[str]) -> dict:
        """Analyze market data with specified indicators"""
        logger.info(f"Analyzing {symbol} with indicators: {indicators}")
        await asyncio.sleep(2)  # Simulate analysis
        return {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "analysis": {
                "rsi": 65.5,
                "macd": {"value": 125.3, "signal": 120.1, "histogram": 5.2},
                "bollinger": {"upper": 52000, "middle": 50000, "lower": 48000}
            }
        }
    
    @staticmethod
    async def execute_trade(
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET"
    ) -> dict:
        """Execute a trade"""
        logger.info(f"Executing {order_type} {side} order for {quantity} {symbol}")
        await asyncio.sleep(1)  # Simulate exchange API call
        return {
            "order_id": f"order_{int(datetime.utcnow().timestamp())}",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "type": order_type,
            "status": "FILLED",
            "timestamp": datetime.utcnow().isoformat()
        }

# Example usage
async def example_usage():
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create a task scheduler
    scheduler = TaskScheduler()
    
    # Define some example schedules
    schedules = [
        TaskSchedule(
            name="fetch_btc_1h",
            task_name="fetch_market_data",
            kwargs={"symbol": "BTC/USDT", "interval": "1h"},
            interval=3600,  # Every hour
            description="Fetch BTC/USDT 1h candles",
            tags=["market_data", "btc"]
        ),
        TaskSchedule(
            name="analyze_btc_daily",
            task_name="analyze_market",
            kwargs={"symbol": "BTC/USDT", "indicators": ["rsi", "macd", "bollinger"]},
            time_of_day="00:05",  # 5 minutes past midnight UTC
            description="Daily technical analysis for BTC/USDT",
            tags=["analysis", "btc"]
        ),
        TaskSchedule(
            name="weekly_portfolio_rebalance",
            task_name="rebalance_portfolio",
            cron="0 0 * * 1",  # Every Monday at midnight
            description="Weekly portfolio rebalancing",
            tags=["portfolio", "rebalancing"],
            priority=TaskPriority.HIGH
        )
    ]
    
    try:
        # Start the scheduler
        await scheduler.start()
        
        # Register task handlers
        handlers = TaskHandlers()
        for name, method in TaskHandlers.__dict__.items():
            if callable(method) and not name.startswith('_'):
                scheduler.task_manager.handler.register(name)(method)
        
        # Schedule tasks
        for schedule in schedules:
            scheduler.schedule_task(schedule)
        
        # Keep the scheduler running
        while True:
            await asyncio.sleep(1)
            
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        await scheduler.stop()

if __name__ == "__main__":
    asyncio.run(example_usage())
