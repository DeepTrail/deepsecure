"""
Test Phase 2 Task 2.2: Basic Request Proxying

This test suite validates the basic request proxying functionality in deeptrail-gateway
to ensure proxy.py correctly handles:
1. HTTP method forwarding (GET, POST, PUT, DELETE)
2. Header preservation and forwarding
3. Request body handling
4. Response forwarding and status codes
5. Error handling and edge cases
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, Optional

from fastapi import Request, Response, HTTPException
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse
from starlette.datastructures import Headers, QueryParams

# Import the proxy handler
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'deeptrail-gateway'))

from app.proxy import ProxyHandler
from app.core.request_validator import ValidationError
from app.core.http_client import SecurityError


class TestBasicRequestProxying:
    """Test suite for basic request proxying functionality."""
    
    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.proxy_handler = ProxyHandler()
        self.test_target_url = "https://api.example.com/v1/test"
        self.test_headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token",
            "User-Agent": "DeepTrail-Gateway/1.0"
        }
    
    def create_mock_request(self, method: str = "GET", url: str = "http://localhost:8002/proxy/test", 
                           headers: Optional[Dict[str, str]] = None, body: Optional[bytes] = None) -> Mock:
        """Create a mock FastAPI request object."""
        request = Mock(spec=Request)
        request.method = method
        request.url = url
        request.headers = Headers(headers or {})
        request.client = Mock()
        request.client.host = "127.0.0.1"
        
        if body:
            request.body = AsyncMock(return_value=body)
        else:
            request.body = AsyncMock(return_value=b"")
        
        return request
    
    def create_mock_response(self, status_code: int = 200, content: bytes = b"test response", 
                            headers: Optional[Dict[str, str]] = None) -> Mock:
        """Create a mock HTTP response object."""
        response = Mock()
        response.status_code = status_code
        response.headers = headers or {"Content-Type": "application/json"}
        response.aread = AsyncMock(return_value=content)
        response.aclose = AsyncMock()
        response.aiter_bytes = AsyncMock()
        
        async def mock_aiter_bytes():
            yield content
        
        response.aiter_bytes.return_value = mock_aiter_bytes()
        return response
    
    # Test 1: HTTP Method Forwarding
    
    @pytest.mark.asyncio
    async def test_get_request_forwarding(self):
        """Test GET request forwarding."""
        request = self.create_mock_request("GET", "http://localhost:8002/proxy/test")
        
        with patch('app.proxy.validator') as mock_validator, \
             patch('app.proxy.get_http_client') as mock_get_client:
            
            # Mock validator
            mock_request_info = Mock()
            mock_request_info.method = "GET"
            mock_request_info.target_url = self.test_target_url
            mock_request_info.headers = self.test_headers
            mock_request_info.query_params = {}
            mock_request_info.content_length = 0
            mock_request_info.content_type = None
            mock_validator.validate_request.return_value = mock_request_info
            mock_validator.validate_response_headers.return_value = {"Content-Type": "application/json"}
            
            # Mock HTTP client
            mock_client = Mock()
            mock_response = self.create_mock_response(200, b'{"result": "success"}')
            mock_client.proxy_request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Execute request
            response = await self.proxy_handler.handle_proxy_request(request)
            
            # Verify HTTP client was called with correct method
            mock_client.proxy_request.assert_called_once_with(
                method="GET",
                target_url=self.test_target_url,
                headers=self.test_headers,
                params={},
                content=None,
                stream=False
            )
            
            # Verify response
            assert response.status_code == 200
            assert response.body == b'{"result": "success"}'
    
    @pytest.mark.asyncio
    async def test_post_request_with_body_forwarding(self):
        """Test POST request with JSON body forwarding."""
        request_body = b'{"test": "data"}'
        request = self.create_mock_request("POST", body=request_body)
        
        with patch('app.proxy.validator') as mock_validator, \
             patch('app.proxy.get_http_client') as mock_get_client:
            
            # Mock validator
            mock_request_info = Mock()
            mock_request_info.method = "POST"
            mock_request_info.target_url = self.test_target_url
            mock_request_info.headers = self.test_headers
            mock_request_info.query_params = {}
            mock_request_info.content_length = len(request_body)
            mock_request_info.content_type = "application/json"
            mock_validator.validate_request.return_value = mock_request_info
            mock_validator.validate_response_headers.return_value = {"Content-Type": "application/json"}
            
            # Mock HTTP client
            mock_client = Mock()
            mock_response = self.create_mock_response(201, b'{"created": "success"}')
            mock_client.proxy_request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Execute request
            response = await self.proxy_handler.handle_proxy_request(request)
            
            # Verify HTTP client was called with correct method and body
            mock_client.proxy_request.assert_called_once_with(
                method="POST",
                target_url=self.test_target_url,
                headers=self.test_headers,
                params={},
                content=request_body,
                stream=False
            )
            
            # Verify response
            assert response.status_code == 201
            assert response.body == b'{"created": "success"}'
    
    @pytest.mark.asyncio
    async def test_put_request_forwarding(self):
        """Test PUT request forwarding."""
        request_body = b'{"update": "data"}'
        request = self.create_mock_request("PUT", body=request_body)
        
        with patch('app.proxy.validator') as mock_validator, \
             patch('app.proxy.get_http_client') as mock_get_client:
            
            # Mock validator
            mock_request_info = Mock()
            mock_request_info.method = "PUT"
            mock_request_info.target_url = self.test_target_url
            mock_request_info.headers = self.test_headers
            mock_request_info.query_params = {}
            mock_request_info.content_length = len(request_body)
            mock_request_info.content_type = "application/json"
            mock_validator.validate_request.return_value = mock_request_info
            mock_validator.validate_response_headers.return_value = {"Content-Type": "application/json"}
            
            # Mock HTTP client
            mock_client = Mock()
            mock_response = self.create_mock_response(200, b'{"updated": "success"}')
            mock_client.proxy_request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Execute request
            response = await self.proxy_handler.handle_proxy_request(request)
            
            # Verify HTTP client was called with PUT method
            mock_client.proxy_request.assert_called_once_with(
                method="PUT",
                target_url=self.test_target_url,
                headers=self.test_headers,
                params={},
                content=request_body,
                stream=False
            )
            
            # Verify response
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_delete_request_forwarding(self):
        """Test DELETE request forwarding."""
        request = self.create_mock_request("DELETE")
        
        with patch('app.proxy.validator') as mock_validator, \
             patch('app.proxy.get_http_client') as mock_get_client:
            
            # Mock validator
            mock_request_info = Mock()
            mock_request_info.method = "DELETE"
            mock_request_info.target_url = self.test_target_url
            mock_request_info.headers = self.test_headers
            mock_request_info.query_params = {}
            mock_request_info.content_length = 0
            mock_request_info.content_type = None
            mock_validator.validate_request.return_value = mock_request_info
            mock_validator.validate_response_headers.return_value = {}
            
            # Mock HTTP client
            mock_client = Mock()
            mock_response = self.create_mock_response(204, b'')
            mock_client.proxy_request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Execute request
            response = await self.proxy_handler.handle_proxy_request(request)
            
            # Verify HTTP client was called with DELETE method
            mock_client.proxy_request.assert_called_once_with(
                method="DELETE",
                target_url=self.test_target_url,
                headers=self.test_headers,
                params={},
                content=None,
                stream=False
            )
            
            # Verify response
            assert response.status_code == 204
    
    # Test 2: Header Management
    
    @pytest.mark.asyncio
    async def test_header_preservation(self):
        """Test that headers are properly preserved and forwarded."""
        custom_headers = {
            "Authorization": "Bearer custom-token",
            "X-Custom-Header": "custom-value",
            "Content-Type": "application/json",
            "User-Agent": "Custom-Agent/1.0"
        }
        
        request = self.create_mock_request("GET", headers=custom_headers)
        
        with patch('app.proxy.validator') as mock_validator, \
             patch('app.proxy.get_http_client') as mock_get_client:
            
            # Mock validator
            mock_request_info = Mock()
            mock_request_info.method = "GET"
            mock_request_info.target_url = self.test_target_url
            mock_request_info.headers = custom_headers
            mock_request_info.query_params = {}
            mock_request_info.content_length = 0
            mock_request_info.content_type = "application/json"
            mock_validator.validate_request.return_value = mock_request_info
            mock_validator.validate_response_headers.return_value = {"Content-Type": "application/json"}
            
            # Mock HTTP client
            mock_client = Mock()
            mock_response = self.create_mock_response(200, b'{"result": "success"}')
            mock_client.proxy_request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Execute request
            response = await self.proxy_handler.handle_proxy_request(request)
            
            # Verify headers were forwarded
            call_args = mock_client.proxy_request.call_args
            assert call_args[1]["headers"] == custom_headers
    
    @pytest.mark.asyncio
    async def test_response_header_forwarding(self):
        """Test that response headers are properly forwarded."""
        request = self.create_mock_request("GET")
        
        response_headers = {
            "Content-Type": "application/json",
            "X-Response-ID": "12345",
            "Cache-Control": "no-cache"
        }
        
        with patch('app.proxy.validator') as mock_validator, \
             patch('app.proxy.get_http_client') as mock_get_client:
            
            # Mock validator
            mock_request_info = Mock()
            mock_request_info.method = "GET"
            mock_request_info.target_url = self.test_target_url
            mock_request_info.headers = self.test_headers
            mock_request_info.query_params = {}
            mock_request_info.content_length = 0
            mock_request_info.content_type = None
            mock_validator.validate_request.return_value = mock_request_info
            mock_validator.validate_response_headers.return_value = response_headers
            
            # Mock HTTP client
            mock_client = Mock()
            mock_response = self.create_mock_response(200, b'{"result": "success"}', response_headers)
            mock_client.proxy_request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Execute request
            response = await self.proxy_handler.handle_proxy_request(request)
            
            # Verify response headers are forwarded
            assert response.headers["Content-Type"] == "application/json"
            assert response.headers["X-Response-ID"] == "12345"
            assert response.headers["Cache-Control"] == "no-cache"
    
    # Test 3: Request Body Handling
    
    @pytest.mark.asyncio
    async def test_large_request_body_handling(self):
        """Test handling of large request bodies."""
        # Create a large request body (1MB)
        large_body = b"x" * (1024 * 1024)
        request = self.create_mock_request("POST", body=large_body)
        
        with patch('app.proxy.validator') as mock_validator, \
             patch('app.proxy.get_http_client') as mock_get_client:
            
            # Mock validator
            mock_request_info = Mock()
            mock_request_info.method = "POST"
            mock_request_info.target_url = self.test_target_url
            mock_request_info.headers = self.test_headers
            mock_request_info.query_params = {}
            mock_request_info.content_length = len(large_body)
            mock_request_info.content_type = "application/octet-stream"
            mock_validator.validate_request.return_value = mock_request_info
            mock_validator.validate_response_headers.return_value = {"Content-Type": "application/json"}
            
            # Mock HTTP client
            mock_client = Mock()
            mock_response = self.create_mock_response(200, b'{"uploaded": "success"}')
            mock_client.proxy_request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Execute request
            response = await self.proxy_handler.handle_proxy_request(request)
            
            # Verify large body was forwarded
            call_args = mock_client.proxy_request.call_args
            assert call_args[1]["content"] == large_body
            assert call_args[1]["stream"] is True  # Should use streaming for large bodies
    
    @pytest.mark.asyncio
    async def test_empty_request_body_handling(self):
        """Test handling of requests with no body."""
        request = self.create_mock_request("GET")
        
        with patch('app.proxy.validator') as mock_validator, \
             patch('app.proxy.get_http_client') as mock_get_client:
            
            # Mock validator
            mock_request_info = Mock()
            mock_request_info.method = "GET"
            mock_request_info.target_url = self.test_target_url
            mock_request_info.headers = self.test_headers
            mock_request_info.query_params = {}
            mock_request_info.content_length = 0
            mock_request_info.content_type = None
            mock_validator.validate_request.return_value = mock_request_info
            mock_validator.validate_response_headers.return_value = {"Content-Type": "application/json"}
            
            # Mock HTTP client
            mock_client = Mock()
            mock_response = self.create_mock_response(200, b'{"result": "success"}')
            mock_client.proxy_request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Execute request
            response = await self.proxy_handler.handle_proxy_request(request)
            
            # Verify no body was sent
            call_args = mock_client.proxy_request.call_args
            assert call_args[1]["content"] is None
    
    # Test 4: Response Handling
    
    @pytest.mark.asyncio
    async def test_response_status_code_forwarding(self):
        """Test that response status codes are properly forwarded."""
        test_cases = [
            (200, "OK"),
            (201, "Created"),
            (400, "Bad Request"),
            (401, "Unauthorized"),
            (404, "Not Found"),
            (500, "Internal Server Error")
        ]
        
        for status_code, description in test_cases:
            request = self.create_mock_request("GET")
            
            with patch('app.proxy.validator') as mock_validator, \
                 patch('app.proxy.get_http_client') as mock_get_client:
                
                # Mock validator
                mock_request_info = Mock()
                mock_request_info.method = "GET"
                mock_request_info.target_url = self.test_target_url
                mock_request_info.headers = self.test_headers
                mock_request_info.query_params = {}
                mock_request_info.content_length = 0
                mock_request_info.content_type = None
                mock_validator.validate_request.return_value = mock_request_info
                mock_validator.validate_response_headers.return_value = {"Content-Type": "application/json"}
                
                # Mock HTTP client
                mock_client = Mock()
                mock_response = self.create_mock_response(status_code, f'{{"status": "{description}"}}'.encode())
                mock_client.proxy_request = AsyncMock(return_value=mock_response)
                mock_get_client.return_value = mock_client
                
                # Execute request
                response = await self.proxy_handler.handle_proxy_request(request)
                
                # Verify status code is forwarded
                assert response.status_code == status_code
    
    @pytest.mark.asyncio
    async def test_streaming_response_handling(self):
        """Test handling of streaming responses."""
        request = self.create_mock_request("GET")
        
        with patch('app.proxy.validator') as mock_validator, \
             patch('app.proxy.get_http_client') as mock_get_client:
            
            # Mock validator
            mock_request_info = Mock()
            mock_request_info.method = "GET"
            mock_request_info.target_url = self.test_target_url
            mock_request_info.headers = self.test_headers
            mock_request_info.query_params = {}
            mock_request_info.content_length = 2 * 1024 * 1024  # 2MB - triggers streaming
            mock_request_info.content_type = "application/octet-stream"
            mock_validator.validate_request.return_value = mock_request_info
            mock_validator.validate_response_headers.return_value = {"Content-Type": "application/octet-stream"}
            
            # Mock HTTP client
            mock_client = Mock()
            mock_response = self.create_mock_response(200, b'streaming content')
            mock_client.proxy_request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Execute request
            response = await self.proxy_handler.handle_proxy_request(request)
            
            # Verify streaming response is used
            assert isinstance(response, StreamingResponse)
            assert response.status_code == 200
    
    # Test 5: Error Handling
    
    @pytest.mark.asyncio
    async def test_validation_error_handling(self):
        """Test handling of request validation errors."""
        request = self.create_mock_request("GET")
        
        with patch('app.proxy.validator') as mock_validator:
            # Mock validator to raise validation error
            mock_validator.validate_request.side_effect = ValidationError("Invalid request", 400)
            
            # Execute request and expect HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await self.proxy_handler.handle_proxy_request(request)
            
            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "Invalid request"
    
    @pytest.mark.asyncio
    async def test_security_error_handling(self):
        """Test handling of security errors."""
        request = self.create_mock_request("GET")
        
        with patch('app.proxy.validator') as mock_validator, \
             patch('app.proxy.get_http_client') as mock_get_client:
            
            # Mock validator
            mock_request_info = Mock()
            mock_request_info.method = "GET"
            mock_request_info.target_url = self.test_target_url
            mock_request_info.headers = self.test_headers
            mock_request_info.query_params = {}
            mock_request_info.content_length = 0
            mock_request_info.content_type = None
            mock_validator.validate_request.return_value = mock_request_info
            
            # Mock HTTP client to raise security error
            mock_client = Mock()
            mock_client.proxy_request = AsyncMock(side_effect=SecurityError("Security violation"))
            mock_get_client.return_value = mock_client
            
            # Execute request and expect HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await self.proxy_handler.handle_proxy_request(request)
            
            assert exc_info.value.status_code == 403
            assert "Security violation" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self):
        """Test handling of unexpected errors."""
        request = self.create_mock_request("GET")
        
        with patch('app.proxy.validator') as mock_validator:
            # Mock validator to raise unexpected error
            mock_validator.validate_request.side_effect = Exception("Unexpected error")
            
            # Execute request and expect HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await self.proxy_handler.handle_proxy_request(request)
            
            assert exc_info.value.status_code == 500
            assert exc_info.value.detail == "Internal server error"
    
    # Test 6: Health Check and Statistics
    
    @pytest.mark.asyncio
    async def test_health_check_functionality(self):
        """Test health check functionality."""
        with patch('app.proxy.get_http_client') as mock_get_client, \
             patch('app.proxy.config') as mock_config:
            
            # Mock HTTP client
            mock_client = Mock()
            mock_get_client.return_value = mock_client
            
            # Mock config
            mock_config.proxy_type = "http"
            mock_config.routing.target_header = "X-Target"
            mock_config.security.max_request_size = 1024 * 1024
            mock_config.security.request_timeout = 30
            mock_config.authentication.jwt_validation = True
            
            # Execute health check
            health_status = await self.proxy_handler.health_check()
            
            # Verify health check response
            assert health_status["status"] == "healthy"
            assert health_status["requests_processed"] == 0
            assert health_status["configuration"]["proxy_type"] == "http"
            assert health_status["configuration"]["jwt_validation"] is True
    
    @pytest.mark.asyncio
    async def test_request_counter_tracking(self):
        """Test that request counter is properly tracked."""
        request = self.create_mock_request("GET")
        
        with patch('app.proxy.validator') as mock_validator, \
             patch('app.proxy.get_http_client') as mock_get_client:
            
            # Mock validator
            mock_request_info = Mock()
            mock_request_info.method = "GET"
            mock_request_info.target_url = self.test_target_url
            mock_request_info.headers = self.test_headers
            mock_request_info.query_params = {}
            mock_request_info.content_length = 0
            mock_request_info.content_type = None
            mock_validator.validate_request.return_value = mock_request_info
            mock_validator.validate_response_headers.return_value = {"Content-Type": "application/json"}
            
            # Mock HTTP client
            mock_client = Mock()
            mock_response = self.create_mock_response(200, b'{"result": "success"}')
            mock_client.proxy_request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Execute multiple requests
            initial_count = self.proxy_handler.request_counter
            await self.proxy_handler.handle_proxy_request(request)
            await self.proxy_handler.handle_proxy_request(request)
            
            # Verify request counter incremented
            assert self.proxy_handler.request_counter == initial_count + 2


class TestProxyHandlerIntegration:
    """Integration tests for the proxy handler."""
    
    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.proxy_handler = ProxyHandler()
    
    @pytest.mark.asyncio
    async def test_end_to_end_proxy_flow(self):
        """Test complete end-to-end proxy flow."""
        # This test validates the complete flow from request to response
        # without breaking down into individual components
        request = Mock(spec=Request)
        request.method = "POST"
        request.url = "http://localhost:8002/proxy/api/v1/test"
        request.headers = Headers({"Content-Type": "application/json"})
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.body = AsyncMock(return_value=b'{"test": "data"}')
        
        with patch('app.proxy.validator') as mock_validator, \
             patch('app.proxy.get_http_client') as mock_get_client, \
             patch('app.proxy.config') as mock_config:
            
            # Mock configuration
            mock_config.logging.enable_request_logging = True
            
            # Mock validator
            mock_request_info = Mock()
            mock_request_info.method = "POST"
            mock_request_info.target_url = "https://api.example.com/v1/test"
            mock_request_info.headers = {"Content-Type": "application/json"}
            mock_request_info.query_params = {}
            mock_request_info.content_length = 16
            mock_request_info.content_type = "application/json"
            mock_validator.validate_request.return_value = mock_request_info
            mock_validator.validate_response_headers.return_value = {"Content-Type": "application/json"}
            
            # Mock HTTP client
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.aread = AsyncMock(return_value=b'{"result": "success"}')
            mock_client.proxy_request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Execute request
            response = await self.proxy_handler.handle_proxy_request(request)
            
            # Verify complete flow
            assert response.status_code == 200
            assert b'{"result": "success"}' in response.body
            assert response.headers["Content-Type"] == "application/json"


# Test execution and validation
if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 