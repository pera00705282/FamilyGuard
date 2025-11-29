"""
Monitoring and queue configuration.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class OpenTelemetryConfig(BaseModel):
    """OpenTelemetry configuration."""
    enabled: bool = True
    service_name: str = "crypto-trading"
    endpoint: Optional[str] = None  # OTLP endpoint
    insecure: bool = False
    headers: Dict[str, str] = Field(default_factory=dict)
    resource_attributes: Dict[str, str] = Field(default_factory=dict)

class MetricsConfig(BaseModel):
    """Metrics configuration."""
    enabled: bool = True
    port: int = 8000
    host: str = "0.0.0.0"
    endpoint: str = "/metrics"

class HealthCheckConfig(BaseModel):
    """Health check configuration."""
    enabled: bool = True
    endpoint: str = "/health"
    live_endpoint: str = "/health/live"
    ready_endpoint: str = "/health/ready"
    external_services: List[Dict[str, Any]] = Field(default_factory=list)

class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    enabled: bool = True
    default_rate: float = 10.0  # requests per second
    default_burst: int = 100
    rules: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

class BatchConfig(BaseModel):
    """Batch processing configuration."""
    default_batch_size: int = 100
    default_max_wait: float = 1.0  # seconds

class PriorityQueueConfig(BaseModel):
    """Priority queue configuration."""
    enabled: bool = True
    max_priority: int = 10

class MonitoringConfig(BaseModel):
    """Monitoring configuration."""
    opentelemetry: OpenTelemetryConfig = Field(default_factory=OpenTelemetryConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    health: HealthCheckConfig = Field(default_factory=HealthCheckConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    batch: BatchConfig = Field(default_factory=BatchConfig)
    priority_queue: PriorityQueueConfig = Field(default_factory=PriorityQueueConfig)

# Default configuration
default_config = MonitoringConfig()
