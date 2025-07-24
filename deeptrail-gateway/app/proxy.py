"""
Core Proxy Handler for DeepTrail Gateway

This module provides the main proxy functionality that handles incoming requests,
validates them, and forwards them to target services using the HTTP client.
"""

import logging
from typing import Dict, Any, Optional

from fastapi import Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from .core.http_client import get_http_client, SecurityError
from .core.request_validator import validator, ValidationError
from .core.proxy_config import config


logger = logging.getLogger(__name__)


class ProxyHandler:
    """
    Main proxy handler that orchestrates request validation, forwarding, and response handling.
    
    This handler is designed to be the central component that:
    1. Validates incoming proxy requests
    2. Forwards them to target services
    3. Streams responses back to clients
    4. Handles errors gracefully
    """
    
    def __init__(self):
        self.request_counter = 0
    
    async def handle_proxy_request(
        self,
        request: Request,
        path: str = ""
    ) -> Response:
        """
        Handle a proxy request end-to-end.
        
        Args:
            request: FastAPI request object
            path: Optional path component from the URL
            
        Returns:
            Response from the target service
            
        Raises:
            HTTPException: If the request fails validation or processing
        """
        self.request_counter += 1
        request_id = f"req_{self.request_counter}"
        
        try:
            # Log the incoming request
            if config.logging.enable_request_logging:
                logger.info(
                    f"[{request_id}] Incoming proxy request: {request.method} {request.url}",
                    extra={
                        'request_id': request_id,
                        'method': request.method,
                        'url': str(request.url),
                        'client_ip': request.client.host if request.client else 'unknown',
                        'user_agent': request.headers.get('user-agent', 'unknown')
                    }
                )
            
            # Validate the request
            try:
                request_info = validator.validate_request(request)
            except ValidationError as e:
                logger.warning(f"[{request_id}] Request validation failed: {e.message}")
                raise HTTPException(status_code=e.status_code, detail=e.message)
            
            # Read request body if present
            request_body = None
            if request_info.content_length > 0:
                request_body = await request.body()
                
                # Verify actual content length matches header
                if len(request_body) != request_info.content_length:
                    logger.warning(
                        f"[{request_id}] Content-Length mismatch: "
                        f"header={request_info.content_length}, actual={len(request_body)}"
                    )
            
            # Get HTTP client
            http_client = await get_http_client()
            
            # Determine if we should stream the response
            should_stream = self._should_stream_response(request_info)
            
            if should_stream:
                # Handle streaming response
                return await self._handle_streaming_response(
                    request_id, http_client, request_info, request_body
                )
            else:
                # Handle regular response
                return await self._handle_regular_response(
                    request_id, http_client, request_info, request_body
                )
                
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except SecurityError as e:
            logger.error(f"[{request_id}] Security error: {e}")
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            logger.error(f"[{request_id}] Unexpected error in proxy handler: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    def _should_stream_response(self, request_info) -> bool:
        """
        Determine if the response should be streamed.
        
        Args:
            request_info: Validated request information
            
        Returns:
            True if response should be streamed
        """
        # Stream for large requests
        if request_info.content_length > 1024 * 1024:  # 1MB
            return True
        
        # Stream for specific content types
        streaming_content_types = {
            'application/octet-stream',
            'video/',
            'audio/',
            'image/',
            'text/event-stream'
        }
        
        if request_info.content_type:
            for stream_type in streaming_content_types:
                if request_info.content_type.startswith(stream_type):
                    return True
        
        return False
    
    async def _handle_regular_response(
        self,
        request_id: str,
        http_client,
        request_info,
        request_body: Optional[bytes]
    ) -> Response:
        """
        Handle a regular (non-streaming) proxy response.
        
        Args:
            request_id: Unique request identifier
            http_client: HTTP client instance
            request_info: Validated request information
            request_body: Request body content
            
        Returns:
            Response from the target service
        """
        try:
            # Make the proxy request
            response = await http_client.proxy_request(
                method=request_info.method,
                target_url=request_info.target_url,
                headers=request_info.headers,
                params=request_info.query_params,
                content=request_body,
                stream=False
            )
            
            # Read response content
            response_content = await response.aread()
            
            # Filter response headers
            filtered_headers = validator.validate_response_headers(dict(response.headers))
            
            # Log the response
            if config.logging.enable_request_logging:
                logger.info(
                    f"[{request_id}] Response: {response.status_code} "
                    f"({len(response_content)} bytes)",
                    extra={
                        'request_id': request_id,
                        'status_code': response.status_code,
                        'response_size': len(response_content),
                        'content_type': response.headers.get('content-type', 'unknown')
                    }
                )
            
            # Create and return response
            return Response(
                content=response_content,
                status_code=response.status_code,
                headers=filtered_headers,
                media_type=response.headers.get('content-type')
            )
            
        except Exception as e:
            logger.error(f"[{request_id}] Error in regular response handling: {e}")
            raise
    
    async def _handle_streaming_response(
        self,
        request_id: str,
        http_client,
        request_info,
        request_body: Optional[bytes]
    ) -> StreamingResponse:
        """
        Handle a streaming proxy response.
        
        Args:
            request_id: Unique request identifier
            http_client: HTTP client instance
            request_info: Validated request information
            request_body: Request body content
            
        Returns:
            Streaming response from the target service
        """
        try:
            # Make the streaming proxy request
            response = await http_client.proxy_request(
                method=request_info.method,
                target_url=request_info.target_url,
                headers=request_info.headers,
                params=request_info.query_params,
                content=request_body,
                stream=True
            )
            
            # Filter response headers
            filtered_headers = validator.validate_response_headers(dict(response.headers))
            
            # Log the streaming response start
            if config.logging.enable_request_logging:
                logger.info(
                    f"[{request_id}] Starting streaming response: {response.status_code}",
                    extra={
                        'request_id': request_id,
                        'status_code': response.status_code,
                        'content_type': response.headers.get('content-type', 'unknown')
                    }
                )
            
            # Create streaming response generator
            async def generate_response():
                try:
                    async for chunk in response.aiter_bytes():
                        yield chunk
                except Exception as e:
                    logger.error(f"[{request_id}] Error in streaming response: {e}")
                    raise
                finally:
                    # Ensure response is closed
                    await response.aclose()
            
            # Create background task to log completion
            def log_completion():
                if config.logging.enable_request_logging:
                    logger.info(
                        f"[{request_id}] Streaming response completed",
                        extra={'request_id': request_id}
                    )
            
            return StreamingResponse(
                generate_response(),
                status_code=response.status_code,
                headers=filtered_headers,
                media_type=response.headers.get('content-type'),
                background=BackgroundTask(log_completion)
            )
            
        except Exception as e:
            logger.error(f"[{request_id}] Error in streaming response handling: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the proxy handler.
        
        Returns:
            Health check status and statistics
        """
        try:
            # Check HTTP client health
            http_client = await get_http_client()
            
            # Basic statistics
            stats = {
                'status': 'healthy',
                'requests_processed': self.request_counter,
                'configuration': {
                    'proxy_type': config.proxy_type,
                    'target_header': config.routing.target_header,
                    'max_request_size': config.security.max_request_size,
                    'request_timeout': config.security.request_timeout,
                    'jwt_validation': config.authentication.jwt_validation
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'requests_processed': self.request_counter
            }


# Global proxy handler instance
proxy_handler = ProxyHandler() 