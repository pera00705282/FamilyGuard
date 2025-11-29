"""
FastAPI application with monitoring and health checks.
"""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from ..monitoring.health import setup_health_routes
from ..monitoring.metrics import start_metrics_server, MetricsCollector
from ..monitoring.tracing import setup_tracing, get_tracer
from ..config.monitoring import default_config as monitoring_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Crypto Trading API",
        description="API for crypto trading operations",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize monitoring
    initialize_monitoring(app)

    # Add exception handlers
    add_exception_handlers(app)

    # Add middleware for request/response logging and metrics
    add_middleware(app)

    # Add health check endpoints
    setup_health_routes(app)

    # Add a simple root endpoint
    @app.get("/")
    async def root():
        """Root endpoint that returns a welcome message."""
        return {"message": "Welcome to Crypto Trading API"}

    return app


def initialize_monitoring(app: FastAPI) -> MetricsCollector:
    """Initialize monitoring components."""
    # Initialize metrics
    metrics_collector = MetricsCollector()

    # Start metrics server if enabled
    if monitoring_config.metrics.enabled:
        start_metrics_server(
            port=monitoring_config.metrics.port,
            addr=monitoring_config.metrics.host,
            endpoint=monitoring_config.metrics.endpoint
        )

    # Initialize OpenTelemetry tracing if enabled
    if monitoring_config.opentelemetry.enabled:
        setup_tracing(
            service_name=monitoring_config.opentelemetry.service_name,
            endpoint=monitoring_config.opentelemetry.endpoint,
            insecure=monitoring_config.opentelemetry.insecure,
            headers=monitoring_config.opentelemetry.headers,
            resource_attributes=monitoring_config.opentelemetry.resource_attributes
        )
    
    return metrics_collector


def add_exception_handlers(app: FastAPI) -> None:
    """Add exception handlers to the FastAPI app."""
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all uncaught exceptions."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors."""
        logger.warning("Validation error: %s", exc)
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )


def add_middleware(app: FastAPI, metrics_collector: MetricsCollector) -> None:
    """Add custom middleware for request/response handling.

    Args:
        app: The FastAPI application
        metrics_collector: The metrics collector instance
    """
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        """Middleware for logging requests and responses."""
        # Get tracer
        tracer = get_tracer()

        # Start span for this request
        with tracer.start_as_current_span(f"HTTP {request.method} {request.url.path}") as span:
            # Log request
            logger.info("Request: %s %s", request.method, request.url)

            try:
                # Process request
                response = await call_next(request)

                # Add tracing headers to response
                response.headers["X-Trace-Id"] = str(span.get_span_context().trace_id)

                # Log response
                logger.info("Response: %s", response.status_code)

                # Record metrics
                metrics_collector.http_requests_total.labels(
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code
                ).inc()

                return response

            except Exception:  # noqa: BLE001
                logger.exception("Error processing request")
                raise

# Create the FastAPI app
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "crypto_trading.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
