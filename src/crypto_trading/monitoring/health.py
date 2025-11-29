"""
Health check endpoints and monitoring for the trading system.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Callable, Awaitable, Any
from datetime import datetime, timedelta

import aiohttp
import psutil
import redis.asyncio as redis
from fastapi import HTTPException

from ..config import config

logger = logging.getLogger(__name__)

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "name": self.name,
            "status": self.status.value,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }

class HealthChecker:
    """Performs health checks on system components."""
    
    def __init__(self):
        """Initialize the health checker."""
        self.checks: List[Callable[[], Awaitable[HealthCheckResult]]] = [
            self.check_system_resources,
            self.check_redis_connection,
            self.check_database_connection,
        ]
        
        # Add external service checks from config
        self.external_services = config.get("health_checks", {}).get("external_services", [])
        if self.external_services:
            self.checks.append(self.check_external_services)
    
    async def check_system_resources(self) -> HealthCheckResult:
        """Check system resource usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            details = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": round(memory.used / (1024 ** 3), 2),
                "memory_total_gb": round(memory.total / (1024 ** 3), 2),
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / (1024 ** 3), 2),
                "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            }
            
            # Determine status based on thresholds
            status = HealthStatus.HEALTHY
            if cpu_percent > 90 or memory.percent > 90 or disk.percent > 90:
                status = HealthStatus.DEGRADED
            if cpu_percent > 95 or memory.percent > 95 or disk.percent > 95:
                status = HealthStatus.UNHEALTHY
                
            return HealthCheckResult("system_resources", status, details)
            
        except Exception as e:
            logger.error(f"System resources check failed: {e}")
            return HealthCheckResult(
                "system_resources",
                HealthStatus.UNHEALTHY,
                {"error": str(e)}
            )
    
    async def check_redis_connection(self) -> HealthCheckResult:
        """Check Redis connection health."""
        try:
            redis_url = config.get("redis", {}).get("url", "redis://localhost:6379/0")
            conn = redis.from_url(redis_url, socket_timeout=1, socket_connect_timeout=1)
            
            # Test connection
            start_time = datetime.utcnow()
            pong = await conn.ping()
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000  # ms
            
            await conn.close()
            
            if not pong:
                raise Exception("Redis did not respond with PONG")
                
            return HealthCheckResult(
                "redis",
                HealthStatus.HEALTHY,
                {"latency_ms": round(latency, 2)}
            )
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return HealthCheckResult(
                "redis",
                HealthStatus.UNHEALTHY,
                {"error": str(e)}
            )
    
    async def check_database_connection(self) -> HealthCheckResult:
        """Check database connection health."""
        try:
            # This is a placeholder - implement actual database check
            # based on your database setup
            return HealthCheckResult(
                "database",
                HealthStatus.HEALTHY,
                {"status": "ok"}
            )
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return HealthCheckResult(
                "database",
                HealthStatus.UNHEALTHY,
                {"error": str(e)}
            )
    
    async def check_external_services(self) -> HealthCheckResult:
        """Check health of external services."""
        results = []
        async with aiohttp.ClientSession() as session:
            for service in self.external_services:
                try:
                    name = service["name"]
                    url = service["url"]
                    timeout = service.get("timeout", 5)
                    
                    start_time = datetime.utcnow()
                    async with session.get(url, timeout=timeout) as response:
                        status = response.status
                        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                        
                        result = {
                            "service": name,
                            "status": "healthy" if status < 400 else "unhealthy",
                            "status_code": status,
                            "latency_ms": round(latency, 2)
                        }
                        results.append(result)
                        
                except Exception as e:
                    results.append({
                        "service": name,
                        "status": "unhealthy",
                        "error": str(e)
                    })
        
        # Determine overall status
        if not results:
            status = HealthStatus.HEALTHY
        elif any(r.get("status") == "unhealthy" for r in results):
            status = HealthStatus.UNHEALTHY
        else:
            status = HealthStatus.HEALTHY
            
        return HealthCheckResult("external_services", status, {"services": results})
    
    async def get_health(self) -> Dict[str, Any]:
        """Run all health checks and return results."""
        results = await asyncio.gather(
            *(check() for check in self.checks),
            return_exceptions=True
        )
        
        # Process results
        health_results = []
        overall_status = HealthStatus.HEALTHY
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Health check failed: {result}")
                health_results.append({
                    "name": "unknown",
                    "status": HealthStatus.UNHEALTHY.value,
                    "error": str(result)
                })
                overall_status = HealthStatus.UNHEALTHY
            else:
                health_results.append(result.to_dict())
                if result.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif result.status == HealthStatus.DEGRADED and overall_status != HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.DEGRADED
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": health_results
        }

# Global health checker instance
health_checker = HealthChecker()

# FastAPI router for health endpoints
def setup_health_routes(app):
    """Add health check endpoints to a FastAPI app."""
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        health_data = await health_checker.get_health()
        status_code = 200 if health_data["status"] == "healthy" else 503
        return health_data, status_code
    
    @app.get("/health/live")
    async def liveness():
        """Liveness probe endpoint."""
        return {"status": "alive"}
    
    @app.get("/health/ready")
    async def readiness():
        """Readiness probe endpoint."""
        health_data = await health_checker.get_health()
        status_code = 200 if health_data["status"] == "healthy" else 503
        return health_data, status_code
