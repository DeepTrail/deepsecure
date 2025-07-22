"""
DeepTrail Gateway - Main Application

This is the main FastAPI application that serves as the central proxy gateway
for all outbound agent traffic, providing authentication, policy enforcement,
and secret injection capabilities.

Core PEP Functionality:
- JWT validation middleware
- Basic policy enforcement
- HTTP request proxying
- Simple secret injection

For Future - Enterprise Grade:
- Advanced security middleware
- Comprehensive logging and audit
- Sophisticated sanitization
- Performance monitoring
- Rate limiting and throttling
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any
from urllib.parse import urlparse

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .proxy import proxy_handler
from .core.proxy_config import config, get_project_version
from .core.http_client import close_http_client
from .core.request_validator import ValidationError
from .core.request_logger import LoggingConfig, configure_request_logging

# For Future - Enterprise Grade: Advanced middleware imports
# from .middleware.logging import setup_logging_middleware, get_logging_stats
# from .middleware.security import SecurityMiddleware, SecurityHeadersMiddleware
# from .middleware.sanitization import SanitizationMiddleware, ContentValidationMiddleware

# Core PEP: Essential middleware imports
from .middleware.jwt_validation import JWTValidationMiddleware
from .middleware.policy_enforcement import PolicyEnforcementMiddleware
from .middleware.secret_injection import SecretInjectionMiddleware

# Configure basic logging
logging.basicConfig(
    level=getattr(logging, config.logging.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown tasks.
    """
    # Startup
    logger.info("Starting DeepTrail Gateway...")
    logger.info(f"Configuration: {config.proxy_type} on {config.host}:{config.port}")
    logger.info(f"Target header: {config.routing.target_header}")
    logger.info(f"Path prefix: {config.routing.path_prefix}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down DeepTrail Gateway...")
    await close_http_client()
    logger.info("DeepTrail Gateway stopped")


# Create FastAPI application
app = FastAPI(
    title="DeepTrail Gateway",
    description="Secure proxy gateway for AI agent outbound traffic",
    version=get_project_version(),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure basic logging (not enterprise-grade structured logging)
logging_config = LoggingConfig(
    enabled=True,
    log_level="INFO",
    log_headers=False,  # For Future - Enterprise Grade
    log_body=False,     # For Future - Enterprise Grade
    log_response_body=False,  # For Future - Enterprise Grade
    audit_mode=False    # For Future - Enterprise Grade
)

# Configure global request logging
configure_request_logging(logging_config)

# For Future - Enterprise Grade: Advanced middleware stack
# app = setup_logging_middleware(app, logging_config)
# app.add_middleware(SecurityHeadersMiddleware)
# app.add_middleware(SecurityMiddleware, config=config)
# app.add_middleware(ContentValidationMiddleware)
# app.add_middleware(SanitizationMiddleware, config=config)

# TODO: Add JWT validation middleware (essential for core PEP)
# TODO: Add basic policy enforcement middleware (essential for core PEP)

# Core PEP: Essential middleware stack
# Order matters: JWT validation -> Policy enforcement -> Secret injection
app.add_middleware(SecretInjectionMiddleware, control_plane_url=config.control_plane_url)
app.add_middleware(PolicyEnforcementMiddleware, enforcement_mode=config.policy.enforcement_mode)
app.add_middleware(JWTValidationMiddleware, control_plane_url=config.control_plane_url)

# Global exception handlers
@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle request validation errors."""
    logger.warning(f"Validation error: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Validation Error",
            "message": exc.message,
            "type": "validation_error"
        }
    )

@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI request validation errors."""
    logger.warning(f"Request validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Request Validation Error",
            "message": str(exc),
            "type": "request_validation_error"
        }
    )

@app.exception_handler(HTTPException)
async def fastapi_http_exception_handler(request: Request, exc: HTTPException):
    """Handle FastAPI HTTP exceptions."""
    logger.info(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "message": exc.detail,
            "type": "http_error"
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    logger.error(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "message": exc.detail,
            "type": "http_error"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "type": "internal_error"
        }
    )


# Health check endpoints
@app.get("/")
async def root():
    """
    Root endpoint for basic health checks.
    """
    return {
        "message": "DeepTrail Gateway is running",
        "status": "healthy",
        "version": config.version,
        "proxy_type": config.proxy_type
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    """
    # Check control plane connectivity
    control_plane_status = "connected"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{config.control_plane_url}/health")
            if response.status_code != 200:
                control_plane_status = "disconnected"
    except Exception as e:
        logger.error(f"Control plane health check failed: {e}")
        control_plane_status = "disconnected"
    
    # Check Redis connectivity
    redis_status = "connected"
    try:
        # Parse Redis URL from config
        redis_url = getattr(config, 'redis_url', 'redis://redis:6379')
        parsed = urlparse(redis_url)
        
        redis_client = redis.Redis(
            host=parsed.hostname or 'redis',
            port=parsed.port or 6379,
            decode_responses=True
        )
        
        # Test connection with ping
        await redis_client.ping()
        await redis_client.aclose()
        
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_status = "disconnected"
    
    return {
        "service": "DeepSecure Gateway",
        "version": config.version,
        "status": "ok",
        "dependencies": {
            "control_plane": control_plane_status,
            "redis": redis_status
        }
    }


@app.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint for Kubernetes and container orchestrators.
    """
    try:
        # Check if all components are ready
        health_status = await proxy_handler.health_check()
        
        if health_status.get("status") == "healthy":
            return {
                "status": "ready",
                "message": "Gateway is ready to accept requests"
            }
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "message": "Gateway is not ready to accept requests"
                }
            )
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "error": str(e),
                "message": "Gateway is not ready to accept requests"
            }
        )


# For Future - Enterprise Grade: Advanced monitoring endpoints
@app.get("/metrics")
async def metrics():
    """
    For Future - Enterprise Grade: Metrics endpoint for Prometheus monitoring.
    
    Current Implementation: Basic metrics only.
    """
    try:
        health_status = await proxy_handler.health_check()
        
        # Basic metrics only (not full Prometheus format)
        return {
            "requests_processed": health_status.get('requests_processed', 0),
            "gateway_status": 1 if health_status.get('status') == 'healthy' else 0,
            "version": config.version,
            "proxy_type": config.proxy_type
        }
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Error collecting metrics"}
        )


# For Future - Enterprise Grade: Advanced configuration endpoint
@app.get("/config")
async def get_configuration():
    """
    For Future - Enterprise Grade: Get current gateway configuration.
    
    Current Implementation: Basic configuration only.
    """
    return {
        "proxy_type": config.proxy_type,
        "routing": {
            "target_header": config.routing.target_header,
            "path_prefix": config.routing.path_prefix
        },
        "authentication": {
            "jwt_validation": config.authentication.jwt_validation
        },
        "logging": {
            "enable_request_logging": config.logging.enable_request_logging,
            "log_level": config.logging.log_level
        }
    }


# For Future - Enterprise Grade: Advanced logging endpoints
@app.get("/logging/stats")
async def get_logging_stats():
    """For Future - Enterprise Grade: Get logging statistics."""
    return {"message": "For Future - Enterprise Grade"}

@app.get("/logging/config")
async def get_logging_config():
    """For Future - Enterprise Grade: Get logging configuration."""
    return {"message": "For Future - Enterprise Grade"}

@app.get("/logging/active")
async def get_active_requests():
    """For Future - Enterprise Grade: Get active request information."""
    return {"message": "For Future - Enterprise Grade"}


# Main proxy routes
@app.api_route(
    config.routing.path_prefix + "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    summary="Proxy requests to external services",
    description="Main proxy endpoint that forwards requests to external services based on the X-Target-Base-URL header"
)
async def proxy_request(request: Request, path: str = ""):
    """
    Main proxy endpoint that handles all HTTP methods and forwards requests
    to external services based on the X-Target-Base-URL header.
    
    Core PEP Functionality (Implemented):
    - JWT validation (✓ implemented via JWTValidationMiddleware)
    - Policy enforcement (✓ implemented via PolicyEnforcementMiddleware)
    - Request proxying (✓ implemented via proxy_handler)
    - Secret injection (✓ implemented via SecretInjectionMiddleware)
    
    Args:
        request: The incoming HTTP request
        path: The path component from the URL
        
    Returns:
        Response from the target service
        
    Raises:
        HTTPException: If the request fails validation or processing
    """
    try:
        # Core PEP functionality is handled by middleware:
        # 1. JWTValidationMiddleware validates the JWT token
        # 2. PolicyEnforcementMiddleware enforces access policies
        # 3. SecretInjectionMiddleware injects appropriate secrets
        # 4. proxy_handler forwards the request to the target service
        
        # Handle the proxy request
        response = await proxy_handler.handle_proxy_request(request, path)
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in proxy request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# Catch-all route for requests that don't match the proxy prefix
@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    include_in_schema=False
)
async def catch_all(request: Request, path: str):
    """
    Catch-all route for requests that don't match other endpoints.
    Provides helpful error messages for misconfigured requests.
    """
    if path.startswith("proxy/"):
        # Likely a misconfigured proxy request
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid proxy request",
                "message": f"Proxy requests must use the '{config.routing.path_prefix}' prefix",
                "correct_format": f"{config.routing.path_prefix}/your-path",
                "required_header": config.routing.target_header,
                "type": "configuration_error"
            }
        )
    
    # Regular 404 for other paths
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"Path '{path}' not found",
            "available_endpoints": [
                "/",
                "/health",
                "/ready", 
                "/metrics",
                "/config",
                f"{config.routing.path_prefix}/{{path:path}}"
            ],
            "type": "not_found"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        reload=True,
        log_level=config.logging.log_level.lower()
    )
