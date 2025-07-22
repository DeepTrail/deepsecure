"""
Logging Middleware for DeepTrail Gateway

This middleware automatically logs all requests and responses passing through
the gateway, providing comprehensive audit trails and debugging information.
"""

import time
from typing import Callable, Dict, Any
from contextlib import asynccontextmanager

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from starlette.types import ASGIApp

from ..core.request_logger import (
    RequestLogger,
    LoggingConfig,
    get_request_logger,
    RequestPhase,
    LogLevel
)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic request/response logging"""
    
    def __init__(self, app: ASGIApp, config: LoggingConfig = None):
        super().__init__(app)
        self.config = config or LoggingConfig()
        self.logger = RequestLogger(self.config)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details"""
        if not self.config.enabled:
            return await call_next(request)
        
        # Generate request ID and start logging
        request_id = await self.logger.log_request_start(request)
        
        # Add request ID to request state for other middleware
        request.state.request_id = request_id
        
        # Process request
        start_time = time.time()
        response = None
        error = None
        
        try:
            response = await call_next(request)
            
            # Log successful completion
            await self.logger.log_request_complete(
                request_id=request_id,
                response=response,
                upstream_status=getattr(response, 'upstream_status', None)
            )
            
        except Exception as e:
            error = e
            
            # Create error response
            if isinstance(e, HTTPException):
                response = Response(
                    content=str(e.detail),
                    status_code=e.status_code,
                    headers=getattr(e, 'headers', {})
                )
            else:
                response = Response(
                    content="Internal Server Error",
                    status_code=500
                )
            
            # Log error
            await self.logger.log_request_complete(
                request_id=request_id,
                response=response,
                error=error
            )
            
            # Re-raise if not HTTP exception
            if not isinstance(e, HTTPException):
                raise
        
        return response


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware for security audit logging"""
    
    def __init__(self, app: ASGIApp, config: LoggingConfig = None):
        super().__init__(app)
        self.config = config or LoggingConfig()
        self.logger = get_request_logger()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with enhanced security logging"""
        if not self.config.enabled:
            return await call_next(request)
        
        request_id = getattr(request.state, 'request_id', None)
        if not request_id:
            # If no request ID from logging middleware, create one
            request_id = self.logger.generate_request_id()
            request.state.request_id = request_id
        
        # Log authentication attempts
        auth_header = request.headers.get("authorization")
        if auth_header:
            # Extract agent ID from JWT (simplified)
            agent_id = self._extract_agent_id(auth_header)
            jwt_valid = self._validate_jwt(auth_header)
            
            self.logger.log_authentication(
                request_id=request_id,
                agent_id=agent_id,
                jwt_valid=jwt_valid
            )
        
        # Check for security violations
        await self._check_security_violations(request, request_id)
        
        # Process request
        response = await call_next(request)
        
        # Log authorization decisions
        if hasattr(request.state, 'policy_decision'):
            self.logger.log_authorization(
                request_id=request_id,
                policy_decision=request.state.policy_decision,
                violations=getattr(request.state, 'security_violations', [])
            )
        
        return response
    
    def _extract_agent_id(self, auth_header: str) -> str:
        """Extract agent ID from JWT token"""
        try:
            # This is a simplified version - in practice, you'd decode the JWT
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                # In real implementation, decode JWT and extract agent_id claim
                return "agent-extracted-from-jwt"
        except Exception:
            pass
        return "unknown"
    
    def _validate_jwt(self, auth_header: str) -> bool:
        """Validate JWT token"""
        try:
            # This is a simplified version - in practice, you'd validate the JWT
            return auth_header.startswith("Bearer ") and len(auth_header) > 20
        except Exception:
            return False
    
    async def _check_security_violations(self, request: Request, request_id: str):
        """Check for potential security violations"""
        violations = []
        
        # Check for suspicious headers
        suspicious_headers = [
            "x-forwarded-host",
            "x-original-url",
            "x-rewrite-url"
        ]
        
        for header in suspicious_headers:
            if header in request.headers:
                violations.append(f"Suspicious header: {header}")
        
        # Check for suspicious query parameters
        suspicious_params = ["../", "..\\", "<script", "javascript:", "data:"]
        query_string = str(request.url.query)
        
        for param in suspicious_params:
            if param in query_string:
                violations.append(f"Suspicious query parameter: {param}")
        
        # Check for unusual request sizes
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB
            violations.append(f"Large request body: {content_length} bytes")
        
        # Log violations
        for violation in violations:
            self.logger.log_security_violation(
                request_id=request_id,
                violation_type="request_analysis",
                details=violation
            )


class ProxyLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware specifically for proxy request logging"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = get_request_logger()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log proxy-specific information"""
        request_id = getattr(request.state, 'request_id', None)
        if not request_id:
            return await call_next(request)
        
        # Log proxy target if this is a proxy request
        if request.url.path.startswith("/proxy/") or "x-target-base-url" in request.headers:
            target_url = request.headers.get("x-target-base-url", "unknown")
            self.logger.log_proxy_start(request_id, target_url)
        
        return await call_next(request)


class ResponseLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for enhanced response logging"""
    
    def __init__(self, app: ASGIApp, config: LoggingConfig = None):
        super().__init__(app)
        self.config = config or LoggingConfig()
        self.logger = get_request_logger()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log response details"""
        response = await call_next(request)
        
        if not self.config.enabled:
            return response
        
        request_id = getattr(request.state, 'request_id', None)
        if not request_id:
            return response
        
        # Log response body if configured
        if self.config.log_response_body and hasattr(response, 'body'):
            try:
                # This is complex for streaming responses
                if isinstance(response, StreamingResponse):
                    # Don't log streaming response bodies
                    pass
                else:
                    # Log first part of response body
                    body_content = getattr(response, 'body', b'')
                    if body_content:
                        body_str = body_content.decode('utf-8', errors='replace')[:self.config.max_body_size]
                        # Store in request state for final logging
                        request.state.response_body_preview = body_str
            except Exception:
                pass
        
        return response


class MetricsLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for performance metrics logging"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = get_request_logger()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log performance metrics"""
        start_time = time.time()
        
        response = await call_next(request)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Log slow requests
        if duration > 5.0:  # 5 seconds threshold
            request_id = getattr(request.state, 'request_id', 'unknown')
            self.logger.log_security_violation(
                request_id=request_id,
                violation_type="performance",
                details=f"Slow request: {duration:.3f}s"
            )
        
        return response


# Utility functions for middleware setup
def setup_logging_middleware(app: ASGIApp, config: LoggingConfig = None) -> ASGIApp:
    """Setup all logging middleware"""
    config = config or LoggingConfig()
    
    # Add middleware in reverse order (last added = first executed)
    app = MetricsLoggingMiddleware(app)
    app = ResponseLoggingMiddleware(app, config)
    app = ProxyLoggingMiddleware(app)
    app = SecurityAuditMiddleware(app, config)
    app = LoggingMiddleware(app, config)
    
    return app


def get_logging_stats() -> Dict[str, Any]:
    """Get current logging statistics"""
    logger = get_request_logger()
    return logger.get_request_stats()


@asynccontextmanager
async def request_context(request: Request):
    """Context manager for request logging"""
    logger = get_request_logger()
    request_id = await logger.log_request_start(request)
    
    try:
        yield request_id
    except Exception as e:
        await logger.log_request_complete(
            request_id=request_id,
            response=None,
            error=e
        )
        raise
    else:
        # Normal completion will be handled by middleware
        pass 