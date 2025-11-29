"""
Distributed tracing with OpenTelemetry for the trading system.
"""
import os
from typing import Optional, Dict, Any, Callable, TypeVar, cast
from functools import wraps
import logging
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, DEPLOYMENT_ENVIRONMENT
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.context import Context

from ..config import config

logger = logging.getLogger(__name__)

# Type variable for generic function wrapping
F = TypeVar('F', bound=Callable[..., Any])

class TracingConfig:
    """Configuration for OpenTelemetry tracing."""
    def __init__(
        self,
        service_name: str = "crypto-trading",
        environment: str = "development",
        endpoint: Optional[str] = None,
        enabled: bool = True,
        console_debug: bool = False
    ):
        self.service_name = service_name
        self.environment = environment
        self.endpoint = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        self.enabled = enabled and (self.endpoint is not None or console_debug)
        self.console_debug = console_debug

class OpenTelemetryTracer:
    """A wrapper around OpenTelemetry tracing functionality."""
    
    def __init__(self, config: TracingConfig):
        """Initialize the tracer."""
        self.config = config
        self.tracer_provider: Optional[TracerProvider] = None
        self._initialized = False
        
    def initialize(self) -> None:
        """Initialize the OpenTelemetry tracer provider."""
        if self._initialized or not self.config.enabled:
            return
            
        try:
            # Create tracer provider
            resource = Resource(attributes={
                SERVICE_NAME: self.config.service_name,
                DEPLOYMENT_ENVIRONMENT: self.config.environment,
            })
            
            self.tracer_provider = TracerProvider(resource=resource)
            
            # Add exporters
            if self.config.endpoint:
                otlp_exporter = OTLPSpanExporter(endpoint=self.config.endpoint)
                self.tracer_provider.add_span_processor(
                    BatchSpanProcessor(otlp_exporter)
                )
                
            if self.config.console_debug:
                console_exporter = ConsoleSpanExporter()
                self.tracer_provider.add_span_processor(
                    BatchSpanProcessor(console_exporter)
                )
            
            # Set the global tracer provider
            trace.set_tracer_provider(self.tracer_provider)
            self._initialized = True
            logger.info("OpenTelemetry tracer initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry tracer: {e}")
            self.tracer_provider = None
    
    def get_tracer(self, name: str) -> trace.Tracer:
        """Get a named tracer instance."""
        if not self._initialized or self.tracer_provider is None:
            return trace.NoOpTracer()
        return self.tracer_provider.get_tracer(name)
    
    def shutdown(self) -> None:
        """Shut down the tracer provider."""
        if self.tracer_provider is not None:
            self.tracer_provider.shutdown()
            self._initialized = False
    
    def trace(self, name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
        """Decorator to trace a function.
        
        Args:
            name: Optional name for the span (defaults to function name)
            attributes: Optional attributes to add to the span
        """
        def decorator(func: F) -> F:
            if not self._initialized:
                return func
                
            span_name = name or f"{func.__module__}.{func.__name__}"
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                with self.start_as_current_span(span_name, attributes=attributes):
                    return await func(*args, **kwargs)
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self.start_as_current_span(span_name, attributes=attributes):
                    return func(*args, **kwargs)
            
            return cast(F, async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper)
        return decorator
    
    @contextmanager
    def start_as_current_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Context manager for creating a span."""
        if not self._initialized or self.tracer_provider is None:
            yield
            return
            
        tracer = self.get_tracer(__name__)
        with tracer.start_as_current_span(name) as span:
            try:
                if attributes:
                    for k, v in attributes.items():
                        if v is not None:
                            span.set_attribute(k, str(v))
                yield span
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

# Default tracer instance
tracer_config = TracingConfig(
    service_name="crypto-trading",
    environment=config.get("environment", "development"),
    endpoint=config.get("tracing", {}).get("endpoint"),
    console_debug=config.get("tracing", {}).get("console_debug", False)
)
tracer = OpenTelemetryTracer(tracer_config)

# Initialize on import
try:
    tracer.initialize()
except Exception as e:
    logger.error(f"Failed to initialize tracer: {e}")

# Helper functions
def trace_function(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """Decorator to trace a function using the global tracer."""
    return tracer.trace(name, attributes)

def start_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Start a new span."""
    return tracer.start_as_current_span(name, attributes)

def set_span_attribute(key: str, value: Any) -> None:
    """Set an attribute on the current span."""
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_attribute(key, str(value))

def record_exception(exception: Exception) -> None:
    """Record an exception on the current span."""
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.record_exception(exception)
        current_span.set_status(Status(StatusCode.ERROR, str(exception)))

def shutdown_tracer() -> None:
    """Shut down the tracer provider."""
    tracer.shutdown()

# Initialize on module import
import atexit
atexit.register(shutdown_tracer)
