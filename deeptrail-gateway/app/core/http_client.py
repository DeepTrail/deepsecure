"""
HTTP Client Manager for DeepTrail Gateway

This module provides a robust HTTP client for proxying requests to external services
with proper connection pooling, timeout handling, and security features.
"""

import asyncio
import ipaddress
import logging
import time
from typing import Dict, Any, Optional, AsyncGenerator
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from .proxy_config import config


logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Raised when a security policy is violated."""
    pass


class ProxyHTTPClient:
    """
    Async HTTP client for proxying requests with security and performance features.
    
    Features:
    - Connection pooling and reuse
    - Configurable timeouts
    - IP address blocking for security
    - Request size limits
    - Comprehensive error handling
    - Streaming support for large payloads
    """
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client with proper configuration."""
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    # Create client with connection pooling and timeout configuration
                    timeout = httpx.Timeout(
                        connect=5.0,  # Connection timeout
                        read=config.security.request_timeout,  # Read timeout
                        write=10.0,   # Write timeout
                        pool=2.0      # Pool timeout
                    )
                    
                    limits = httpx.Limits(
                        max_keepalive_connections=config.security.max_connections,
                        max_connections=config.security.max_connections * 2,
                        keepalive_expiry=30.0
                    )
                    
                    self._client = httpx.AsyncClient(
                        timeout=timeout,
                        limits=limits,
                        follow_redirects=True,
                        max_redirects=5,
                        verify=True  # Always verify SSL certificates
                    )
        
        return self._client
    
    async def close(self):
        """Close the HTTP client and clean up resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _validate_target_url(self, url: str) -> str:
        """
        Validate and normalize the target URL for security.
        
        Args:
            url: The target URL to validate
            
        Returns:
            Normalized URL
            
        Raises:
            SecurityError: If the URL violates security policies
        """
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise SecurityError(f"Invalid URL format: {e}")
        
        # Ensure we have a scheme
        if not parsed.scheme:
            raise SecurityError("URL must include a scheme (http:// or https://)")
        
        # Only allow HTTP/HTTPS
        if parsed.scheme not in ('http', 'https'):
            raise SecurityError(f"Unsupported scheme: {parsed.scheme}")
        
        # Ensure we have a hostname
        if not parsed.hostname:
            raise SecurityError("URL must include a hostname")
        
        # Check if IP blocking is enabled
        if config.security.block_internal_ips:
            self._check_ip_blocking(parsed.hostname)
        
        # Check allowed domains if configured
        if config.security.allowed_domains:
            if parsed.hostname not in config.security.allowed_domains:
                raise SecurityError(f"Domain {parsed.hostname} not in allowed list")
        
        return url
    
    def _check_ip_blocking(self, hostname: str):
        """
        Check if the hostname resolves to a blocked IP range.
        
        Args:
            hostname: The hostname to check
            
        Raises:
            SecurityError: If the hostname resolves to a blocked IP
        """
        try:
            # Try to parse as IP address first
            ip = ipaddress.ip_address(hostname)
            
            # Check against blocked ranges
            for blocked_range in config.security.blocked_ip_ranges:
                if ip in ipaddress.ip_network(blocked_range):
                    raise SecurityError(f"IP {ip} is in blocked range {blocked_range}")
                    
        except ValueError:
            # Not an IP address, it's a hostname
            # In production, you might want to resolve the hostname and check the IP
            # For now, we'll allow hostnames through
            pass
    
    def _prepare_headers(self, original_headers: Dict[str, str], target_url: str) -> Dict[str, str]:
        """
        Prepare headers for the proxied request.
        
        Args:
            original_headers: Original request headers
            target_url: Target URL for the request
            
        Returns:
            Prepared headers for the proxied request
        """
        headers = {}
        parsed_target = urlparse(target_url)
        
        # Copy allowed headers
        for header_name, header_value in original_headers.items():
            header_lower = header_name.lower()
            
            # Skip blocked headers
            if header_lower in [h.lower() for h in config.routing.blocked_headers]:
                continue
            
            # Preserve specific headers
            if header_lower in [h.lower() for h in config.routing.preserve_headers]:
                headers[header_name] = header_value
        
        # Set the correct Host header for the target
        headers['Host'] = parsed_target.netloc
        
        # Add forwarded headers
        for header_name, header_value in config.routing.forwarded_headers.items():
            headers[header_name] = header_value
        
        # Add User-Agent if not present
        if 'User-Agent' not in headers:
            headers['User-Agent'] = 'DeepTrail-Gateway/1.0'
        
        return headers
    
    async def proxy_request(
        self,
        method: str,
        target_url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        content: Optional[bytes] = None,
        stream: bool = False
    ) -> httpx.Response:
        """
        Proxy a request to the target URL.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            target_url: Target URL to proxy to
            headers: Request headers
            params: Query parameters
            content: Request body content
            stream: Whether to stream the response
            
        Returns:
            HTTP response from the target service
            
        Raises:
            SecurityError: If the request violates security policies
            HTTPException: If the request fails
        """
        start_time = time.time()
        
        try:
            # Validate the target URL
            validated_url = self._validate_target_url(target_url)
            
            # Prepare headers
            prepared_headers = self._prepare_headers(headers or {}, validated_url)
            
            # Get the HTTP client
            client = await self._get_client()
            
            # Log the request (sanitized)
            if config.logging.enable_request_logging:
                sanitized_headers = self._sanitize_headers_for_logging(prepared_headers)
                logger.info(
                    f"Proxying {method} request to {validated_url}",
                    extra={
                        'method': method,
                        'target_url': validated_url,
                        'headers': sanitized_headers,
                        'has_content': content is not None,
                        'content_length': len(content) if content else 0
                    }
                )
            
            # Make the request
            if stream:
                # For streaming responses, use the stream method
                response = await client.stream(
                    method=method,
                    url=validated_url,
                    headers=prepared_headers,
                    params=params,
                    content=content
                )
            else:
                # For regular responses, use the request method
                response = await client.request(
                    method=method,
                    url=validated_url,
                    headers=prepared_headers,
                    params=params,
                    content=content
                )
            
            # Log the response
            if config.logging.enable_request_logging:
                duration = time.time() - start_time
                logger.info(
                    f"Received response from {validated_url}",
                    extra={
                        'status_code': response.status_code,
                        'duration_ms': round(duration * 1000, 2),
                        'content_length': response.headers.get('content-length', 'unknown')
                    }
                )
            
            return response
            
        except SecurityError:
            # Re-raise security errors
            raise
        except httpx.TimeoutException as e:
            logger.error(f"Request timeout to {target_url}: {e}")
            raise HTTPException(status_code=504, detail="Gateway timeout")
        except httpx.ConnectError as e:
            logger.error(f"Connection error to {target_url}: {e}")
            raise HTTPException(status_code=502, detail="Bad gateway")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from {target_url}: {e}")
            # Pass through the original error
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error proxying to {target_url}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def proxy_stream_request(
        self,
        method: str,
        target_url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        content: Optional[AsyncGenerator[bytes, None]] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Proxy a streaming request to the target URL.
        
        Args:
            method: HTTP method
            target_url: Target URL to proxy to
            headers: Request headers
            params: Query parameters
            content: Async generator for request body content
            
        Yields:
            Response content chunks
            
        Raises:
            SecurityError: If the request violates security policies
            HTTPException: If the request fails
        """
        try:
            # Validate the target URL
            validated_url = self._validate_target_url(target_url)
            
            # Prepare headers
            prepared_headers = self._prepare_headers(headers or {}, validated_url)
            
            # Get the HTTP client
            client = await self._get_client()
            
            # Make the streaming request
            async with client.stream(
                method=method,
                url=validated_url,
                headers=prepared_headers,
                params=params,
                content=content
            ) as response:
                # Check for HTTP errors
                response.raise_for_status()
                
                # Stream the response
                async for chunk in response.aiter_bytes():
                    yield chunk
                    
        except SecurityError:
            # Re-raise security errors
            raise
        except httpx.TimeoutException as e:
            logger.error(f"Stream timeout to {target_url}: {e}")
            raise HTTPException(status_code=504, detail="Gateway timeout")
        except httpx.ConnectError as e:
            logger.error(f"Stream connection error to {target_url}: {e}")
            raise HTTPException(status_code=502, detail="Bad gateway")
        except Exception as e:
            logger.error(f"Unexpected streaming error to {target_url}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    def _sanitize_headers_for_logging(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Sanitize headers for logging by removing sensitive information.
        
        Args:
            headers: Original headers
            
        Returns:
            Sanitized headers safe for logging
        """
        sanitized = {}
        for name, value in headers.items():
            if name.lower() in [h.lower() for h in config.logging.sanitize_headers]:
                sanitized[name] = "[REDACTED]"
            else:
                sanitized[name] = value
        return sanitized


# Global HTTP client instance
_http_client: Optional[ProxyHTTPClient] = None


async def get_http_client() -> ProxyHTTPClient:
    """Get the global HTTP client instance."""
    global _http_client
    if _http_client is None:
        _http_client = ProxyHTTPClient()
    return _http_client


async def close_http_client():
    """Close the global HTTP client instance."""
    global _http_client
    if _http_client:
        await _http_client.close()
        _http_client = None 