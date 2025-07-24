"""
Sanitization middleware for the DeepTrail Gateway.

This middleware integrates request sanitization into the FastAPI request processing pipeline,
providing comprehensive request cleaning and validation for all incoming requests.
"""

import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.request_sanitizer import (
    RequestSanitizer, 
    SanitizationConfig, 
    SanitizationLevel,
    SanitizationResult
)
from ..core.proxy_config import ProxyConfig

logger = logging.getLogger(__name__)

class SanitizationMiddleware(BaseHTTPMiddleware):
    """
    Sanitization middleware that cleans and validates all requests.
    
    This middleware:
    - Sanitizes request headers and removes dangerous ones
    - Cleans request content based on content type
    - Validates and sanitizes query parameters
    - Enforces character encoding standards
    - Removes malicious patterns and content
    - Logs sanitization violations and warnings
    """
    
    def __init__(self, app: ASGIApp, config: Optional[ProxyConfig] = None):
        super().__init__(app)
        self.config = config or ProxyConfig()
        
        # Create sanitization configuration based on security level
        sanitization_config = SanitizationConfig(
            level=SanitizationLevel.MODERATE,  # Default to moderate
            normalize_headers=True,
            remove_dangerous_headers=True,
            validate_header_encoding=True,
            sanitize_json=True,
            sanitize_form_data=True,
            sanitize_query_params=True,
            escape_html_entities=True,
            remove_null_bytes=True,
            enforce_utf8=True,
            remove_control_chars=True,
            normalize_unicode=True,
            validate_content_type=True
        )
        
        self.sanitizer = RequestSanitizer(sanitization_config)
        
        logger.info("Sanitization middleware initialized")
        logger.info(f"Sanitization level: {sanitization_config.level}")
        logger.info(f"Header sanitization: {sanitization_config.normalize_headers}")
        logger.info(f"Content sanitization: {sanitization_config.sanitize_json}")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through sanitization filters."""
        start_time = time.time()
        
        # Skip sanitization for health check endpoints
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return await call_next(request)
        
        try:
            # Read request body for sanitization
            body = b""
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
            
            # Sanitize the request
            sanitization_result = await self.sanitizer.sanitize_request(request, body)
            
            # Check for critical violations
            if sanitization_result.violations:
                critical_violations = [
                    v for v in sanitization_result.violations 
                    if any(keyword in v.lower() for keyword in [
                        'blocked content type', 'failed to convert encoding',
                        'invalid json', 'too many parameters'
                    ])
                ]
                
                if critical_violations:
                    processing_time = time.time() - start_time
                    
                    # Log critical violations
                    client_ip = request.client.host if request.client else "unknown"
                    logger.error(
                        f"Sanitization block: {client_ip} {request.method} {request.url.path} "
                        f"- Critical violations: {critical_violations} in {processing_time:.3f}s"
                    )
                    
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "Request sanitization failed",
                            "message": "Request contains content that cannot be safely processed",
                            "violations": critical_violations,
                            "timestamp": time.time()
                        },
                        headers={
                            "X-Content-Type-Options": "nosniff",
                            "X-Frame-Options": "DENY",
                            "X-Processing-Time": f"{processing_time:.3f}s"
                        }
                    )
            
            # Create sanitized request
            sanitized_request = self._create_sanitized_request(
                request, 
                sanitization_result
            )
            
            # Continue with sanitized request
            response = await call_next(sanitized_request)
            
            processing_time = time.time() - start_time
            
            # Add sanitization info to response headers
            if sanitization_result.changes_made:
                response.headers["X-Request-Sanitized"] = "true"
                response.headers["X-Sanitization-Warnings"] = str(len(sanitization_result.warnings))
            
            response.headers["X-Sanitization-Time"] = f"{processing_time:.3f}s"
            
            # Log sanitization results
            client_ip = request.client.host if request.client else "unknown"
            if sanitization_result.violations or sanitization_result.warnings:
                logger.info(
                    f"Sanitization applied: {client_ip} {request.method} {request.url.path} "
                    f"- Violations: {len(sanitization_result.violations)}, "
                    f"Warnings: {len(sanitization_result.warnings)} in {processing_time:.3f}s"
                )
            else:
                logger.debug(
                    f"Sanitization passed: {client_ip} {request.method} {request.url.path} "
                    f"- No issues in {processing_time:.3f}s"
                )
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            client_ip = request.client.host if request.client else "unknown"
            
            logger.error(
                f"Sanitization middleware error: {client_ip} {request.method} {request.url.path} "
                f"- Error: {str(e)} in {processing_time:.3f}s"
            )
            
            # Return error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal sanitization error",
                    "message": "An error occurred while sanitizing the request",
                    "timestamp": time.time()
                },
                headers={
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": "DENY",
                    "X-Processing-Time": f"{processing_time:.3f}s"
                }
            )
    
    def _create_sanitized_request(self, original_request: Request, 
                                 sanitization_result: SanitizationResult) -> Request:
        """Create a new request with sanitized content."""
        # Store sanitized data in request state for downstream middleware
        original_request.state.sanitized_headers = sanitization_result.sanitized_headers
        original_request.state.sanitized_body = sanitization_result.sanitized_body
        original_request.state.sanitized_query_params = sanitization_result.sanitized_query_params
        original_request.state.sanitization_result = sanitization_result
        
        # Update request headers with sanitized versions
        # Note: This is a simplified approach. In a full implementation,
        # you might need to create a new Request object with sanitized data
        for header_name, header_value in sanitization_result.sanitized_headers.items():
            original_request.headers.__dict__['_list'] = [
                (name, value) for name, value in original_request.headers.items()
                if name.lower() != header_name.lower()
            ]
            original_request.headers.__dict__['_list'].append((header_name, header_value))
        
        return original_request

class ContentValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for validating content types and enforcing content policies.
    
    This middleware enforces content type restrictions and validates
    that requests contain only allowed content types.
    """
    
    def __init__(self, app: ASGIApp, allowed_content_types: Optional[list] = None):
        super().__init__(app)
        self.allowed_content_types = allowed_content_types or [
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
            "text/plain",
            "application/xml"
        ]
        
        logger.info("Content validation middleware initialized")
        logger.info(f"Allowed content types: {self.allowed_content_types}")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate request content type."""
        # Skip validation for GET requests and health endpoints
        if request.method in ["GET", "HEAD", "OPTIONS"] or request.url.path in ["/health", "/ready", "/metrics"]:
            return await call_next(request)
        
        # Check content type
        content_type = request.headers.get("content-type", "").lower()
        if content_type:
            # Extract main content type (ignore parameters)
            main_content_type = content_type.split(';')[0].strip()
            
            if main_content_type not in self.allowed_content_types:
                logger.warning(f"Blocked request with unsupported content type: {content_type}")
                return JSONResponse(
                    status_code=415,
                    content={
                        "error": "Unsupported Media Type",
                        "message": f"Content type '{main_content_type}' is not allowed",
                        "allowed_types": self.allowed_content_types
                    }
                )
        
        return await call_next(request)

class EncodingNormalizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for normalizing character encoding in requests.
    
    This middleware ensures all text content is properly encoded
    and normalized to UTF-8.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        logger.info("Encoding normalization middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Normalize character encoding in requests."""
        # Skip for non-text content types
        content_type = request.headers.get("content-type", "").lower()
        if not any(text_type in content_type for text_type in ["text/", "application/json", "application/xml"]):
            return await call_next(request)
        
        try:
            # Check if request has body
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                
                if body:
                    # Try to decode and re-encode as UTF-8
                    try:
                        # Try UTF-8 first
                        decoded_body = body.decode('utf-8')
                        normalized_body = decoded_body.encode('utf-8')
                        
                        # Store normalized body in request state
                        request.state.normalized_body = normalized_body
                        
                    except UnicodeDecodeError:
                        # Try other common encodings
                        for encoding in ['latin-1', 'iso-8859-1', 'windows-1252']:
                            try:
                                decoded_body = body.decode(encoding)
                                normalized_body = decoded_body.encode('utf-8')
                                request.state.normalized_body = normalized_body
                                
                                # Update content-type header to indicate UTF-8
                                if 'charset=' not in content_type:
                                    new_content_type = f"{content_type}; charset=utf-8"
                                    request.headers.__dict__['_list'] = [
                                        (name, value) for name, value in request.headers.items()
                                        if name.lower() != 'content-type'
                                    ]
                                    request.headers.__dict__['_list'].append(('content-type', new_content_type))
                                
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            # If all encodings fail, log warning but continue
                            logger.warning(f"Failed to normalize encoding for request to {request.url.path}")
            
            return await call_next(request)
            
        except Exception as e:
            logger.error(f"Encoding normalization error: {str(e)}")
            return await call_next(request)

# Utility functions for sanitization middleware
def get_sanitization_stats(request: Request) -> dict:
    """Get sanitization statistics from request state."""
    if hasattr(request.state, 'sanitization_result'):
        result = request.state.sanitization_result
        return {
            "changes_made": result.changes_made,
            "violations_count": len(result.violations),
            "warnings_count": len(result.warnings),
            "content_type": result.content_type,
            "encoding": result.encoding,
            "violations": result.violations,
            "warnings": result.warnings
        }
    return {}

def is_request_sanitized(request: Request) -> bool:
    """Check if request has been sanitized."""
    return hasattr(request.state, 'sanitization_result')

def get_sanitized_body(request: Request) -> bytes:
    """Get sanitized request body."""
    if hasattr(request.state, 'sanitized_body'):
        return request.state.sanitized_body
    return b""

def get_sanitized_headers(request: Request) -> dict:
    """Get sanitized request headers."""
    if hasattr(request.state, 'sanitized_headers'):
        return request.state.sanitized_headers
    return {}

def get_sanitized_query_params(request: Request) -> dict:
    """Get sanitized query parameters."""
    if hasattr(request.state, 'sanitized_query_params'):
        return request.state.sanitized_query_params
    return {} 