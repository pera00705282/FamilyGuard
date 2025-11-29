"""
Automation Service

Main service that ties together task scheduling, distributed processing,
and configuration management for the crypto trading automation system.
"""
import asyncio
import importlib
import json
import logging
import signal
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .config import AutomationConfig, TaskConfig
from ..performance.async_processor import Task, TaskPriority
from ..performance.distributed_queue import DistributedTaskManager, QueueConfig
from .task_scheduler import TaskScheduler, TaskSchedule

logger = logging.getLogger(__name__)

class AutomationService:
    """Main automation service that manages the entire automation system"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the automation service"""
        self.config_path = config_path or "config/automation.json"
        self.config: Optional[AutomationConfig] = None
        self.scheduler: Optional[TaskScheduler] = None
        self.task_manager: Optional[DistributedTaskManager] = None
        self.running = False
    
    async def initialize(self) -> None:
        """Initialize the automation service"""
        logger.info("Initializing automation service...")
        
        # Load configuration
        self.config = self.load_config()
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        # Initialize task manager
        queue_config = QueueConfig(
            queue_type="redis",
            url=self.config.redis_url,
            queue_name="crypto_trading_tasks"
        )
        self.task_manager = DistributedTaskManager(
            queue_config=queue_config,
            max_workers=self.config.max_workers
        )
        
        # Initialize scheduler
        self.scheduler = TaskScheduler(
            task_manager=self.task_manager,
            timezone=self.config.timezone
        )
        
        # Register signal handlers
        self._register_signal_handlers()
        
        logger.info("Automation service initialized")
    
    def load_config(self) -> AutomationConfig:
        """Load configuration from file"""
        config_path = Path(self.config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        return AutomationConfig(**config_data)
    
    async def start(self) -> None:
        """Start the automation service"""
        if self.running:
            logger.warning("Automation service is already running")
            return
        
        logger.info("Starting automation service...")
        
        # Start task manager
        if self.task_manager:
            await self.task_manager.start()
        
        # Start scheduler
        if self.scheduler:
            await self.scheduler.start()
            
            # Schedule all configured tasks
            await self._schedule_tasks()
        
        self.running = True
        logger.info("Automation service started")
    
    async def stop(self) -> None:
        """Stop the automation service"""
        if not self.running:
            return
            
        logger.info("Stopping automation service...")
        
        # Stop scheduler
        if self.scheduler:
            await self.scheduler.stop()
        
        # Stop task manager
        if self.task_manager:
            await self.task_manager.stop()
        
        self.running = False
        logger.info("Automation service stopped")
    
    async def _schedule_tasks(self) -> None:
        """Schedule all configured tasks"""
        if not self.config or not self.scheduler:
            return
            
        for task_config in self.config.tasks:
            if not task_config.enabled:
                logger.info(f"Skipping disabled task: {task_config.name}")
                continue
                
            await self._schedule_task(task_config)
    
    async def _schedule_task(self, task_config: TaskConfig) -> None:
        """Schedule a single task"""
        if not self.scheduler:
            return
            
        # Convert TaskConfig to TaskSchedule
        schedule = TaskSchedule(
            name=task_config.name,
            task_name=task_config.function,
            args=tuple(task_config.args),
            kwargs=task_config.kwargs,
            priority=TaskPriority[task_config.priority.upper()],
            enabled=task_config.enabled,
            max_instances=task_config.max_instances,
            misfire_grace_time=task_config.timeout,
            interval=task_config.interval if task_config.schedule_type == "interval" else None,
            cron=task_config.cron if task_config.schedule_type == "cron" else None,
            time_of_day=task_config.time_of_day if task_config.schedule_type == "time" else None,
            description=task_config.description,
            tags=task_config.tags
        )
        
        # Import and register the task handler
        self._register_task_handler(task_config.module, task_config.function)
        
        # Schedule the task
        self.scheduler.schedule_task(schedule)
        logger.info(f"Scheduled task: {task_config.name}")
    
    def _register_task_handler(self, module_path: str, function_name: str) -> None:
        """Dynamically import and register a task handler"""
        if not self.task_manager:
            return
            
        try:
            # Import the module
            module = importlib.import_module(module_path)
            
            # Get the function
            func = getattr(module, function_name, None)
            if not func or not callable(func):
                logger.error(f"Handler function not found: {module_path}.{function_name}")
                return
            
            # Register the function with the task manager
            self.task_manager.handler.register(function_name)(func)
            logger.debug(f"Registered task handler: {module_path}.{function_name}")
            
        except ImportError as e:
            logger.error(f"Failed to import module {module_path}: {e}")
        except Exception as e:
            logger.error(f"Error registering task handler {module_path}.{function_name}: {e}")
    
    def _register_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown"""
        loop = asyncio.get_running_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))


async def run_automation_service(config_path: Optional[str] = None) -> None:
    """Run the automation service"""
    service = AutomationService(config_path)
    
    try:
        await service.initialize()
        await service.start()
        
        # Keep the service running
        while service.running:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        logger.info("Received cancellation signal")
    except Exception as e:
        logger.error(f"Error in automation service: {e}", exc_info=True)
    finally:
        await service.stop()


def create_example_config(output_path: str = "config/automation.json") -> None:
    """Create an example configuration file"""
    example_config = {
        "timezone": "UTC",
        "log_level": "INFO",
        "redis_url": "redis://localhost:6379/0",
        "max_workers": 10,
        "tasks": [
            {
                "name": "fetch_btc_1h",
                "description": "Fetch BTC/USDT 1-hour candles",
                "enabled": True,
                "priority": "normal",
                "max_instances": 1,
                "timeout": 300,
                "retries": 3,
                "retry_delay": 60,
                "schedule_type": "interval",
                "interval": 3600,
                "module": "crypto_trading.automation.tasks.market_data",
                "function": "fetch_ohlcv",
                "args": ["BTC/USDT", "1h"],
                "kwargs": {"limit": 1000},
                "tags": ["market_data", "btc"]
            },
            {
                "name": "analyze_markets_daily",
                "description": "Daily technical analysis of major pairs",
                "enabled": True,
                "priority": "high",
                "schedule_type": "time",
                "time_of_day": "00:05",
                "module": "crypto_trading.automation.tasks.analysis",
                "function": "analyze_markets",
                "args": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
                "kwargs": {"indicators": ["rsi", "macd", "bollinger"]},
                "tags": ["analysis", "daily"]
            },
            {
                "name": "weekly_portfolio_rebalance",
                "description": "Weekly portfolio rebalancing",
                "enabled": True,
                "priority": "critical",
                "schedule_type": "cron",
                "cron": "0 0 * * 1",  # Every Monday at midnight
                "module": "crypto_trading.automation.tasks.portfolio",
                "function": "rebalance_portfolio",
                "tags": ["portfolio", "rebalancing"]
            }
        ]
    }
    
    # Create config directory if it doesn't exist
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write the example config
    with open(output_path, 'w') as f:
        json.dump(example_config, f, indent=2)
    
    print(f"Example configuration created at: {output_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Crypto Trading Automation Service")
    parser.add_argument(
        "--config",
        default="config/automation.json",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--create-config",
        action="store_true",
        help="Create an example configuration file and exit"
    )
    
    args = parser.parse_args()
    
    if args.create_config:
        create_example_config(args.config)
    else:
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        try:
            asyncio.run(run_automation_service(args.config))
        except KeyboardInterrupt:
            logger.info("Shutting down...")
