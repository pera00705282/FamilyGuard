"""
Configuration for the trading automation system
"""
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator
from datetime import time
from enum import Enum

class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

class ScheduleType(str, Enum):
    INTERVAL = "interval"  # Run at fixed intervals (in seconds)
    CRON = "cron"          # Cron-style scheduling
    TIME = "time"          # Specific time of day

class TaskConfig(BaseModel):
    """Configuration for an automated task"""
    name: str
    description: str = ""
    enabled: bool = True
    priority: TaskPriority = TaskPriority.NORMAL
    max_instances: int = 1
    timeout: int = 300  # seconds
    retries: int = 3
    retry_delay: int = 60  # seconds
    
    # Schedule configuration (one of these should be set)
    schedule_type: ScheduleType
    interval: Optional[int] = None  # seconds
    cron: Optional[str] = None      # cron expression
    time_of_day: Optional[str] = None  # HH:MM format
    
    # Task parameters
    module: str  # e.g., "crypto_trading.automation.tasks"
    function: str  # Name of the function to call
    args: List[Union[str, int, float, bool]] = Field(default_factory=list)
    kwargs: Dict[str, Union[str, int, float, bool]] = Field(default_factory=dict)
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    
    @validator('time_of_day')
    def validate_time_format(cls, v):
        if v is not None:
            try:
                hours, minutes = map(int, v.split(':'))
                if not (0 <= hours < 24 and 0 <= minutes < 60):
                    raise ValueError("Invalid time format. Use HH:MM")
            except (ValueError, AttributeError):
                raise ValueError("Time must be in HH:MM format")
        return v
    
    @validator('cron')
    def validate_cron(cls, v, values):
        if v is not None and values.get('schedule_type') == ScheduleType.CRON:
            # Simple validation - could be enhanced with croniter
            parts = v.split()
            if len(parts) != 5:
                raise ValueError("Cron expression must have 5 fields")
        return v
    
    @validator('interval')
    def validate_interval(cls, v, values):
        if v is not None and values.get('schedule_type') == ScheduleType.INTERVAL:
            if v < 1:
                raise ValueError("Interval must be at least 1 second")
        return v

class AutomationConfig(BaseModel):
    """Top-level configuration for the automation system"""
    tasks: List[TaskConfig]
    
    # Global settings
    timezone: str = "UTC"
    log_level: str = "INFO"
    redis_url: str = "redis://localhost:6379/0"
    max_workers: int = 10
    
    def get_task(self, name: str) -> Optional[TaskConfig]:
        """Get a task configuration by name"""
        for task in self.tasks:
            if task.name == name:
                return task
        return None
    
    def get_tasks_by_tag(self, tag: str) -> List[TaskConfig]:
        """Get all tasks with the given tag"""
        return [task for task in self.tasks if tag in task.tags]
