"""
Request Validation Module for DeepTrail Gateway

This module provides comprehensive validation for incoming proxy requests
to ensure security, format compliance, and policy adherence.
"""

import re
from typing import Dict, List, Optional, Tuple, Union, Any
from urllib.parse import urlparse

from fastapi import Request, HTTPException
from pydantic import BaseModel, Field, field_validator

from .proxy_config import config


class ValidationError(Exception):
    """Raised when request validation fails."""
    
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ProxyRequestInfo(BaseModel):
    """Information extracted from a proxy request."""
    
    target_url: str = Field(..., description="Target URL for the proxy request")
    method: str = Field(..., description="HTTP method")
    headers: Dict[str, str] = Field(default_factory=dict, description="Request headers")
    query_params: Dict[str, str] = Field(default_factory=dict, description="Query parameters")
    content_length: int = Field(default=0, description="Content length in bytes")
    content_type: Optional[str] = Field(default=None, description="Content type")
    
    @field_validator('target_url')
    @classmethod
    def validate_target_url(cls, v):
        """Validate target URL format."""
        if not v:
            raise ValueError("Target URL cannot be empty")
        
        try:
            parsed = urlparse(v)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Target URL must include scheme and hostname")
        except Exception as e:
            raise ValueError(f"Invalid target URL format: {e}")
        
        return v
    
    @field_validator('method')
    @classmethod
    def validate_method(cls, v):
        """Validate HTTP method."""
        allowed_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
        if v.upper() not in allowed_methods:
            raise ValueError(f"HTTP method {v} not allowed")
        return v.upper()


class RequestValidator:
    """
    Request validator for proxy requests.
    
    Validates:
    - Required headers presence
    - Request size limits
    - Content type restrictions
    - URL format and security
    - HTTP method allowlist
    """
    
    def __init__(self):
        self.max_request_size = self._parse_size_string(config.security.max_request_size)
        self.target_header = config.routing.target_header
        self.blocked_patterns = self._compile_blocked_patterns()
    
    def _parse_size_string(self, size_str: Union[str, int]) -> int:
        """
        Parse size string (e.g., '10MB', '1GB') to bytes.
        
        Args:
            size_str: Size string to parse or integer value
            
        Returns:
            Size in bytes
        """
        # If already an integer, return as-is
        if isinstance(size_str, int):
            return size_str
        
        size_str = size_str.upper().strip()
        
        # Extract number and unit
        match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?B?)$', size_str)
        if not match:
            raise ValueError(f"Invalid size format: {size_str}")
        
        number, unit = match.groups()
        number = float(number)
        
        # Convert to bytes
        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 ** 2,
            'GB': 1024 ** 3,
            'TB': 1024 ** 4,
            '': 1  # No unit means bytes
        }
        
        if unit not in multipliers:
            raise ValueError(f"Unknown size unit: {unit}")
        
        return int(number * multipliers[unit])
    
    def _compile_blocked_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for blocked URLs."""
        # Common patterns for potentially dangerous URLs
        patterns = [
            r'file://',  # File protocol
            r'ftp://',   # FTP protocol
            r'localhost',  # Localhost variations
            r'127\.0\.0\.1',  # Localhost IP
            r'0\.0\.0\.0',    # All interfaces
            r'::1',           # IPv6 localhost
            r'metadata\.google\.internal',  # GCP metadata
            r'169\.254\.169\.254',  # AWS metadata
            r'metadata\.azure\.com',  # Azure metadata
        ]
        
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    
    def validate_headers(self, request: Request) -> Dict[str, str]:
        """
        Validate request headers.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Validated headers dictionary
            
        Raises:
            ValidationError: If header validation fails
        """
        headers = dict(request.headers)
        
        # Check for required target header (case-insensitive)
        target_url = None
        for header_name, header_value in headers.items():
            if header_name.lower() == self.target_header.lower():
                target_url = header_value
                break
        
        if target_url is None:
            raise ValidationError(
                f"Missing required header: {self.target_header}",
                status_code=400
            )
        if not target_url.strip():
            raise ValidationError(
                f"Header {self.target_header} cannot be empty",
                status_code=400
            )
        
        # Validate target URL format
        try:
            parsed = urlparse(target_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValidationError(
                    "Target URL must include scheme and hostname",
                    status_code=400
                )
        except Exception as e:
            raise ValidationError(
                f"Invalid target URL format: {e}",
                status_code=400
            )
        
        # Check for blocked URL patterns
        for pattern in self.blocked_patterns:
            if pattern.search(target_url):
                raise ValidationError(
                    f"Target URL matches blocked pattern: {pattern.pattern}",
                    status_code=403
                )
        
        return headers
    
    def validate_content_size(self, request: Request) -> int:
        """
        Validate request content size.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Content length in bytes
            
        Raises:
            ValidationError: If content size validation fails
        """
        content_length = 0
        
        # Get content length from header
        if 'content-length' in request.headers:
            try:
                content_length = int(request.headers['content-length'])
            except ValueError:
                raise ValidationError(
                    "Invalid Content-Length header",
                    status_code=400
                )
        
        # Check against maximum allowed size
        if content_length > self.max_request_size:
            raise ValidationError(
                f"Request size {content_length} exceeds maximum allowed size {self.max_request_size}",
                status_code=413
            )
        
        return content_length
    
    def validate_content_type(self, request: Request) -> Optional[str]:
        """
        Validate request content type.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Content type if present
            
        Raises:
            ValidationError: If content type validation fails
        """
        content_type = request.headers.get('content-type')
        
        if content_type:
            # Parse content type (remove charset, boundary, etc.)
            main_type = content_type.split(';')[0].strip().lower()
            
            # Define allowed content types
            allowed_types = {
                'application/json',
                'application/xml',
                'application/x-www-form-urlencoded',
                'multipart/form-data',
                'text/plain',
                'text/html',
                'text/xml',
                'text/csv',
                'application/octet-stream',
                'application/pdf',
                'image/jpeg',
                'image/png',
                'image/gif',
                'image/svg+xml'
            }
            
            # Check if content type is allowed
            if main_type not in allowed_types:
                # Log but don't block - some APIs use custom content types
                pass
        
        return content_type
    
    def validate_http_method(self, method: str) -> str:
        """
        Validate HTTP method.
        
        Args:
            method: HTTP method to validate
            
        Returns:
            Validated method in uppercase
            
        Raises:
            ValidationError: If method validation fails
        """
        method = method.upper()
        
        # Define allowed methods
        allowed_methods = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'}
        
        if method not in allowed_methods:
            raise ValidationError(
                f"HTTP method {method} not allowed",
                status_code=405
            )
        
        return method
    
    def validate_query_params(self, request: Request) -> Dict[str, str]:
        """
        Validate query parameters.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Validated query parameters
            
        Raises:
            ValidationError: If query parameter validation fails
        """
        query_params = dict(request.query_params)
        
        # Check for potentially dangerous parameters
        dangerous_params = {'callback', 'jsonp', 'eval', 'exec'}
        for param in dangerous_params:
            if param in query_params:
                # Log but don't block - some legitimate APIs use these
                pass
        
        return query_params
    
    def validate_request(self, request: Request) -> ProxyRequestInfo:
        """
        Perform comprehensive request validation.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Validated proxy request information
            
        Raises:
            ValidationError: If any validation fails
        """
        try:
            # Validate HTTP method
            method = self.validate_http_method(request.method)
            
            # Validate headers
            headers = self.validate_headers(request)
            # Extract target URL from headers (case-insensitive)
            target_url = None
            for header_name, header_value in headers.items():
                if header_name.lower() == self.target_header.lower():
                    target_url = header_value
                    break
            
            # Validate content size
            content_length = self.validate_content_size(request)
            
            # Validate content type
            content_type = self.validate_content_type(request)
            
            # Validate query parameters
            query_params = self.validate_query_params(request)
            
            # Create and return validated request info
            return ProxyRequestInfo(
                target_url=target_url,
                method=method,
                headers=headers,
                query_params=query_params,
                content_length=content_length,
                content_type=content_type
            )
            
        except ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            # Catch any unexpected errors
            raise ValidationError(
                f"Request validation failed: {e}",
                status_code=500
            )
    
    def validate_response_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Validate and filter response headers.
        
        Args:
            headers: Original response headers
            
        Returns:
            Filtered response headers
        """
        filtered_headers = {}
        
        # Headers to remove from responses
        blocked_response_headers = {
            'server',  # Hide server information
            'x-powered-by',  # Hide technology stack
            'x-aspnet-version',  # Hide framework version
            'x-aspnetmvc-version',  # Hide MVC version
        }
        
        for name, value in headers.items():
            if name.lower() not in blocked_response_headers:
                filtered_headers[name] = value
        
        # Add security headers
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        }
        
        for name, value in security_headers.items():
            if name not in filtered_headers:
                filtered_headers[name] = value
        
        return filtered_headers


# Global validator instance
validator = RequestValidator() 