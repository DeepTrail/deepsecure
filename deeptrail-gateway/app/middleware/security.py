"""
Security middleware for the DeepTrail Gateway.

This middleware integrates security filters into the FastAPI request processing pipeline,
providing comprehensive security filtering for all incoming requests.
"""

import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.security_filters import SecurityFilter, SecurityConfig
from ..core.proxy_config import ProxyConfig

logger = logging.getLogger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware that applies security filters to all requests.
    
    This middleware:
    - Applies IP filtering and blocking
    - Enforces rate limiting
    - Validates request headers and content
    - Detects malicious patterns
    - Blocks suspicious requests
    - Logs security violations
    """
    
    def __init__(self, app: ASGIApp, config: Optional[ProxyConfig] = None):
        super().__init__(app)
        self.config = config or ProxyConfig()
        self.security_filter = SecurityFilter(self.config.security)
        
        logger.info("Security middleware initialized with configuration")
        logger.info(f"Blocked IP ranges: {len(self.config.security.blocked_ip_ranges)}")
        logger.info(f"Rate limit: {self.config.security.rate_limit_requests} requests per {self.config.security.rate_limit_window}s")
        logger.info(f"Max request size: {self.config.security.max_request_size} bytes")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security filters."""
        start_time = time.time()
        
        # Skip security filtering for health check endpoints
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return await call_next(request)
        
        try:
            # Read request body for content filtering
            body = b""
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
            
            # Apply security filters
            security_response = await self.security_filter.filter_request(request, body)
            
            if security_response is not None:
                # Request was blocked by security filters
                processing_time = time.time() - start_time
                
                # Add security headers to blocked response
                security_response.headers["X-Content-Type-Options"] = "nosniff"
                security_response.headers["X-Frame-Options"] = "DENY"
                security_response.headers["X-XSS-Protection"] = "1; mode=block"
                security_response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                security_response.headers["X-Processing-Time"] = f"{processing_time:.3f}s"
                
                # Log security block
                client_ip = self.security_filter.get_client_ip(request)
                logger.warning(
                    f"Security block: {client_ip} {request.method} {request.url.path} "
                    f"- {security_response.status_code} in {processing_time:.3f}s"
                )
                
                return security_response
            
            # Request passed security filters, continue processing
            # Recreate request with body for downstream middleware
            if body:
                # Store body in request state for downstream middleware
                request.state.body = body
            
            response = await call_next(request)
            
            # Add security headers to successful responses
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Content-Security-Policy"] = "default-src 'self'"
            
            processing_time = time.time() - start_time
            response.headers["X-Processing-Time"] = f"{processing_time:.3f}s"
            
            # Log successful request
            client_ip = self.security_filter.get_client_ip(request)
            logger.info(
                f"Security passed: {client_ip} {request.method} {request.url.path} "
                f"- {response.status_code} in {processing_time:.3f}s"
            )
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            client_ip = self.security_filter.get_client_ip(request)
            
            logger.error(
                f"Security middleware error: {client_ip} {request.method} {request.url.path} "
                f"- Error: {str(e)} in {processing_time:.3f}s"
            )
            
            # Return error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal security error",
                    "message": "An error occurred while processing security filters",
                    "timestamp": time.time()
                },
                headers={
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": "DENY",
                    "X-XSS-Protection": "1; mode=block",
                    "Referrer-Policy": "strict-origin-when-cross-origin",
                    "X-Processing-Time": f"{processing_time:.3f}s"
                }
            )
    
    def get_security_stats(self) -> dict:
        """Get security statistics from the filter."""
        return self.security_filter.get_violation_stats()
    
    def get_recent_violations(self, hours: int = 24) -> list:
        """Get recent security violations."""
        return self.security_filter.get_recent_violations(hours)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all responses.
    
    This is a lightweight middleware that ensures all responses include
    proper security headers, even if they bypass other security filters.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        logger.info("Security headers middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to all responses."""
        response = await call_next(request)
        
        # Add comprehensive security headers
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "X-Permitted-Cross-Domain-Policies": "none",
            "X-Download-Options": "noopen",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        
        # Only add CSP for HTML responses
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            security_headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
        
        # Add headers to response
        for header_name, header_value in security_headers.items():
            response.headers[header_name] = header_value
        
        return response

# Custom request body reader for security filtering
class SecurityRequestBodyReader:
    """
    Helper class to read request body for security filtering while preserving
    it for downstream middleware.
    """
    
    @staticmethod
    async def read_body(request: Request) -> bytes:
        """Read request body and store it in request state."""
        if hasattr(request.state, "body"):
            return request.state.body
        
        body = await request.body()
        request.state.body = body
        return body
    
    @staticmethod
    def get_cached_body(request: Request) -> bytes:
        """Get cached body from request state."""
        return getattr(request.state, "body", b"")

# Security configuration validator
class SecurityConfigValidator:
    """Validates security configuration for common issues."""
    
    @staticmethod
    def validate_config(config: SecurityConfig) -> list:
        """Validate security configuration and return any issues."""
        issues = []
        
        # Validate IP ranges
        for ip_range in config.blocked_ip_ranges:
            try:
                import ipaddress
                ipaddress.ip_network(ip_range)
            except ValueError:
                issues.append(f"Invalid blocked IP range: {ip_range}")
        
        for ip_range in config.allowed_ip_ranges:
            try:
                import ipaddress
                ipaddress.ip_network(ip_range)
            except ValueError:
                issues.append(f"Invalid allowed IP range: {ip_range}")
        
        # Validate rate limiting
        if config.rate_limit_requests <= 0:
            issues.append("Rate limit requests must be positive")
        
        if config.rate_limit_window <= 0:
            issues.append("Rate limit window must be positive")
        
        if config.rate_limit_burst < 0:
            issues.append("Rate limit burst must be non-negative")
        
        # Validate size limits
        if config.max_request_size <= 0:
            issues.append("Max request size must be positive")
        
        if config.max_header_size <= 0:
            issues.append("Max header size must be positive")
        
        if config.max_headers_count <= 0:
            issues.append("Max headers count must be positive")
        
        if config.max_url_length <= 0:
            issues.append("Max URL length must be positive")
        
        return issues 