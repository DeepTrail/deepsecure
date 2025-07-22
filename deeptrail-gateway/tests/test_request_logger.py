"""
Tests for the Request Logger System

This module tests the comprehensive request/response logging capabilities
including configuration, sanitization, middleware integration, and audit trails.
"""

import json
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.request_logger import (
    RequestLogger,
    LoggingConfig,
    HeaderSanitizer,
    RequestMetadata,
    ResponseMetadata,
    TimingMetadata,
    SecurityMetadata,
    ProxyMetadata,
    RequestLogEntry,
    RequestPhase,
    LogLevel,
    get_request_logger,
    configure_request_logging
)
from app.middleware.logging import (
    LoggingMiddleware,
    SecurityAuditMiddleware,
    ProxyLoggingMiddleware,
    ResponseLoggingMiddleware,
    MetricsLoggingMiddleware,
    setup_logging_middleware
)


class TestLoggingConfig:
    """Test logging configuration functionality"""
    
    def test_default_config(self):
        """Test default logging configuration"""
        config = LoggingConfig()
        
        assert config.enabled is True
        assert config.log_level == LogLevel.INFO
        assert config.log_headers is True
        assert config.log_body is False
        assert config.log_response_body is False
        assert config.max_body_size == 1024
        assert config.sanitize_headers is True
        assert config.log_timing is True
        assert config.log_ip_address is True
        assert config.audit_mode is False
        
        # Check default sanitized headers
        expected_headers = [
            "authorization",
            "x-api-key",
            "x-auth-token",
            "cookie",
            "x-forwarded-authorization",
            "x-deepsecure-secret"
        ]
        assert config.sanitized_headers == expected_headers
    
    def test_custom_config(self):
        """Test custom logging configuration"""
        config = LoggingConfig(
            enabled=False,
            log_level=LogLevel.DEBUG,
            log_body=True,
            max_body_size=2048,
            sanitized_headers=["custom-header"]
        )
        
        assert config.enabled is False
        assert config.log_level == LogLevel.DEBUG
        assert config.log_body is True
        assert config.max_body_size == 2048
        assert config.sanitized_headers == ["custom-header"]


class TestHeaderSanitizer:
    """Test header sanitization functionality"""
    
    def test_header_sanitization(self):
        """Test that sensitive headers are sanitized"""
        config = LoggingConfig()
        sanitizer = HeaderSanitizer(config)
        
        headers = {
            "authorization": "Bearer secret-token",
            "x-api-key": "secret-key",
            "content-type": "application/json",
            "user-agent": "test-agent"
        }
        
        sanitized = sanitizer.sanitize_headers(headers)
        
        assert sanitized["authorization"] == "[REDACTED]"
        assert sanitized["x-api-key"] == "[REDACTED]"
        assert sanitized["content-type"] == "application/json"
        assert sanitized["user-agent"] == "test-agent"
    
    def test_header_sanitization_disabled(self):
        """Test that sanitization can be disabled"""
        config = LoggingConfig(sanitize_headers=False)
        sanitizer = HeaderSanitizer(config)
        
        headers = {
            "authorization": "Bearer secret-token",
            "x-api-key": "secret-key"
        }
        
        sanitized = sanitizer.sanitize_headers(headers)
        
        assert sanitized["authorization"] == "Bearer secret-token"
        assert sanitized["x-api-key"] == "secret-key"
    
    def test_body_sanitization_json(self):
        """Test JSON body sanitization"""
        config = LoggingConfig()
        sanitizer = HeaderSanitizer(config)
        
        body = json.dumps({
            "username": "testuser",
            "password": "secret123",
            "api_key": "secret-key",
            "data": {
                "value": "normal-data",
                "secret": "hidden-secret"
            }
        })
        
        sanitized = sanitizer.sanitize_body(body, "application/json")
        sanitized_data = json.loads(sanitized)
        
        assert sanitized_data["username"] == "testuser"
        assert sanitized_data["password"] == "[REDACTED]"
        assert sanitized_data["api_key"] == "[REDACTED]"
        assert sanitized_data["data"]["value"] == "normal-data"
        assert sanitized_data["data"]["secret"] == "[REDACTED]"
    
    def test_body_truncation(self):
        """Test that large bodies are truncated"""
        config = LoggingConfig(max_body_size=10)
        sanitizer = HeaderSanitizer(config)
        
        body = "This is a very long body that should be truncated"
        sanitized = sanitizer.sanitize_body(body, "text/plain")
        
        assert sanitized == "This is a ...[TRUNCATED]"
    
    def test_invalid_json_handling(self):
        """Test handling of invalid JSON"""
        config = LoggingConfig()
        sanitizer = HeaderSanitizer(config)
        
        body = "invalid json {"
        sanitized = sanitizer.sanitize_body(body, "application/json")
        
        # Should return original body if JSON parsing fails
        assert sanitized == body


class TestRequestLogger:
    """Test request logger functionality"""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request object"""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url = Mock()
        request.url.path = "/test"
        request.url.query = "param=value"
        request.url.__str__ = Mock(return_value="https://example.com/test?param=value")
        request.headers = {
            "authorization": "Bearer token",
            "content-type": "application/json",
            "user-agent": "test-agent"
        }
        request.query_params = {"param": "value"}
        request.client = Mock()
        request.client.host = "192.168.1.100"
        request.body = AsyncMock(return_value=b'{"test": "data"}')
        return request
    
    @pytest.fixture
    def logger(self):
        """Create a request logger instance"""
        config = LoggingConfig()
        return RequestLogger(config)
    
    @pytest.mark.asyncio
    async def test_log_request_start(self, logger, mock_request):
        """Test logging request start"""
        request_id = await logger.log_request_start(mock_request)
        
        assert request_id is not None
        assert request_id in logger.active_requests
        
        log_entry = logger.active_requests[request_id]
        assert log_entry.phase == RequestPhase.RECEIVED
        assert log_entry.request_metadata.method == "GET"
        assert log_entry.request_metadata.path == "/test"
        assert log_entry.request_metadata.client_ip == "192.168.1.100"
        assert log_entry.timing_metadata.start_time is not None
    
    @pytest.mark.asyncio
    async def test_log_request_start_with_forwarded_ip(self, logger):
        """Test IP extraction with forwarded headers"""
        request = Mock(spec=Request)
        request.method = "POST"
        request.url = Mock()
        request.url.path = "/api/test"
        request.url.__str__ = Mock(return_value="https://example.com/api/test")
        request.headers = {
            "x-forwarded-for": "10.0.0.1, 192.168.1.1",
            "x-real-ip": "10.0.0.1"
        }
        request.query_params = {}
        request.client = Mock()
        request.client.host = "192.168.1.100"
        request.body = AsyncMock(return_value=b'')
        
        request_id = await logger.log_request_start(request)
        log_entry = logger.active_requests[request_id]
        
        # Should use the first IP from x-forwarded-for
        assert log_entry.request_metadata.client_ip == "10.0.0.1"
    
    def test_log_authentication(self, logger):
        """Test authentication logging"""
        request_id = "test-request-id"
        
        # Create a mock log entry
        log_entry = Mock()
        log_entry.timing_metadata = TimingMetadata(start_time=time.time())
        log_entry.security_metadata = SecurityMetadata()
        logger.active_requests[request_id] = log_entry
        
        logger.log_authentication(request_id, "agent-123", True)
        
        assert log_entry.security_metadata.agent_id == "agent-123"
        assert log_entry.security_metadata.jwt_valid is True
        assert log_entry.timing_metadata.auth_time is not None
    
    def test_log_authorization(self, logger):
        """Test authorization logging"""
        request_id = "test-request-id"
        
        # Create a mock log entry
        log_entry = Mock()
        log_entry.timing_metadata = TimingMetadata(start_time=time.time())
        log_entry.security_metadata = SecurityMetadata()
        logger.active_requests[request_id] = log_entry
        
        violations = ["policy_violation_1", "policy_violation_2"]
        logger.log_authorization(request_id, "deny", violations)
        
        assert log_entry.security_metadata.policy_decision == "deny"
        assert log_entry.security_metadata.security_violations == violations
        assert log_entry.timing_metadata.policy_time is not None
    
    def test_log_proxy_start(self, logger):
        """Test proxy logging"""
        request_id = "test-request-id"
        
        # Create a mock log entry
        log_entry = Mock()
        log_entry.timing_metadata = TimingMetadata(start_time=time.time())
        log_entry.proxy_metadata = ProxyMetadata()
        logger.active_requests[request_id] = log_entry
        
        target_url = "https://api.external.com/endpoint"
        logger.log_proxy_start(request_id, target_url)
        
        assert log_entry.proxy_metadata.target_url == target_url
        assert log_entry.proxy_metadata.target_host == "api.external.com"
        assert log_entry.timing_metadata.proxy_time is not None
    
    @pytest.mark.asyncio
    async def test_log_request_complete_success(self, logger):
        """Test successful request completion logging"""
        request_id = "test-request-id"
        
        # Create a mock log entry
        log_entry = Mock()
        log_entry.timing_metadata = TimingMetadata(start_time=time.time())
        log_entry.proxy_metadata = ProxyMetadata()
        logger.active_requests[request_id] = log_entry
        
        # Mock response
        response = Mock()
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        
        await logger.log_request_complete(request_id, response, upstream_status=200)
        
        assert log_entry.timing_metadata.end_time is not None
        assert log_entry.timing_metadata.total_duration is not None
        assert log_entry.proxy_metadata.upstream_status == 200
        assert request_id not in logger.active_requests  # Should be cleaned up
    
    @pytest.mark.asyncio
    async def test_log_request_complete_error(self, logger):
        """Test error request completion logging"""
        request_id = "test-request-id"
        
        # Create a mock log entry
        log_entry = Mock()
        log_entry.timing_metadata = TimingMetadata(start_time=time.time())
        logger.active_requests[request_id] = log_entry
        
        # Mock response
        response = Mock()
        response.status_code = 500
        response.headers = {}
        
        error = Exception("Test error")
        await logger.log_request_complete(request_id, response, error=error)
        
        assert log_entry.phase == RequestPhase.FAILED
        assert log_entry.level == LogLevel.ERROR
        assert log_entry.error_details is not None
        assert log_entry.error_details["error_type"] == "Exception"
        assert log_entry.error_details["error_message"] == "Test error"
    
    def test_log_security_violation(self, logger):
        """Test security violation logging"""
        request_id = "test-request-id"
        
        # Create a mock log entry
        log_entry = Mock()
        log_entry.security_metadata = SecurityMetadata()
        logger.active_requests[request_id] = log_entry
        
        with patch('app.core.request_logger.logger') as mock_logger:
            logger.log_security_violation(request_id, "xss_attempt", "Script injection detected")
            
            # Should add to active request violations
            assert "xss_attempt: Script injection detected" in log_entry.security_metadata.security_violations
            
            # Should also emit immediate log
            mock_logger.warning.assert_called_once()
    
    def test_get_request_stats(self, logger):
        """Test request statistics"""
        # Add some mock active requests
        for i in range(3):
            request_id = f"request-{i}"
            log_entry = Mock()
            log_entry.timing_metadata = TimingMetadata(start_time=time.time() - i)
            logger.active_requests[request_id] = log_entry
        
        stats = logger.get_request_stats()
        
        assert stats["active_requests"] == 3
        assert stats["average_processing_time"] > 0
        assert stats["logging_enabled"] is True
        assert stats["log_level"] == "INFO"
    
    def test_disabled_logging(self):
        """Test that logging can be disabled"""
        config = LoggingConfig(enabled=False)
        logger = RequestLogger(config)
        
        # Should not log anything when disabled
        logger.log_security_violation("test-id", "test", "test")
        
        assert len(logger.active_requests) == 0


class TestLoggingMiddleware:
    """Test logging middleware functionality"""
    
    def test_logging_middleware_setup(self):
        """Test that logging middleware can be set up"""
        app = FastAPI()
        config = LoggingConfig()
        
        # Setup middleware
        app_with_logging = setup_logging_middleware(app, config)
        
        assert app_with_logging is not None
    
    @pytest.mark.asyncio
    async def test_logging_middleware_request_processing(self):
        """Test that logging middleware processes requests correctly"""
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        # Add logging middleware
        config = LoggingConfig()
        middleware = LoggingMiddleware(app, config)
        
        # Mock request and response
        request = Mock(spec=Request)
        request.method = "GET"
        request.url = Mock()
        request.url.path = "/test"
        request.url.__str__ = Mock(return_value="https://example.com/test")
        request.headers = {}
        request.query_params = {}
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.body = AsyncMock(return_value=b'')
        request.state = Mock()
        
        # Mock call_next
        response = Mock()
        response.status_code = 200
        response.headers = {}
        
        call_next = AsyncMock(return_value=response)
        
        # Process request
        result = await middleware.dispatch(request, call_next)
        
        assert result == response
        assert hasattr(request.state, 'request_id')
        call_next.assert_called_once_with(request)
    
    @pytest.mark.asyncio
    async def test_security_audit_middleware(self):
        """Test security audit middleware"""
        app = FastAPI()
        config = LoggingConfig()
        middleware = SecurityAuditMiddleware(app, config)
        
        # Mock request with auth header
        request = Mock(spec=Request)
        request.headers = {"authorization": "Bearer valid-token"}
        request.url = Mock()
        request.url.query = ""
        request.state = Mock()
        request.state.request_id = "test-request-id"
        
        # Mock call_next
        response = Mock()
        call_next = AsyncMock(return_value=response)
        
        # Process request
        result = await middleware.dispatch(request, call_next)
        
        assert result == response
        call_next.assert_called_once_with(request)
    
    @pytest.mark.asyncio
    async def test_proxy_logging_middleware(self):
        """Test proxy logging middleware"""
        app = FastAPI()
        middleware = ProxyLoggingMiddleware(app)
        
        # Mock proxy request
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/proxy/test"
        request.headers = {"x-target-base-url": "https://api.example.com"}
        request.state = Mock()
        request.state.request_id = "test-request-id"
        
        # Mock call_next
        response = Mock()
        call_next = AsyncMock(return_value=response)
        
        # Process request
        result = await middleware.dispatch(request, call_next)
        
        assert result == response
        call_next.assert_called_once_with(request)
    
    @pytest.mark.asyncio
    async def test_metrics_logging_middleware(self):
        """Test metrics logging middleware"""
        app = FastAPI()
        middleware = MetricsLoggingMiddleware(app)
        
        # Mock request
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.request_id = "test-request-id"
        
        # Mock slow call_next (> 5 seconds)
        response = Mock()
        
        async def slow_call_next(req):
            await asyncio.sleep(0.1)  # Simulate processing time
            return response
        
        # Process request
        result = await middleware.dispatch(request, slow_call_next)
        
        assert result == response


class TestGlobalConfiguration:
    """Test global configuration functionality"""
    
    def test_configure_request_logging(self):
        """Test global logging configuration"""
        config = LoggingConfig(log_level=LogLevel.DEBUG)
        configure_request_logging(config)
        
        logger = get_request_logger()
        assert logger.config.log_level == LogLevel.DEBUG
    
    def test_get_request_logger_singleton(self):
        """Test that request logger is a singleton"""
        logger1 = get_request_logger()
        logger2 = get_request_logger()
        
        assert logger1 is logger2


class TestIntegration:
    """Integration tests for the logging system"""
    
    def test_full_logging_stack_integration(self):
        """Test complete logging middleware stack"""
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        # Setup full logging stack
        config = LoggingConfig()
        app_with_logging = setup_logging_middleware(app, config)
        
        # Test with TestClient
        client = TestClient(app_with_logging)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert response.json() == {"message": "test"}
    
    def test_logging_with_errors(self):
        """Test logging behavior with errors"""
        app = FastAPI()
        
        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")
        
        # Setup logging
        config = LoggingConfig()
        app_with_logging = setup_logging_middleware(app, config)
        
        # Test error handling
        client = TestClient(app_with_logging)
        response = client.get("/error")
        
        assert response.status_code == 500
    
    def test_logging_endpoints_integration(self):
        """Test logging monitoring endpoints"""
        from app.main import app
        
        client = TestClient(app)
        
        # Test logging stats endpoint
        response = client.get("/logging/stats")
        assert response.status_code == 200
        
        stats = response.json()
        assert "active_requests" in stats
        assert "logging_enabled" in stats
        
        # Test logging config endpoint
        response = client.get("/logging/config")
        assert response.status_code == 200
        
        config = response.json()
        assert "enabled" in config
        assert "log_level" in config
        
        # Test active requests endpoint
        response = client.get("/logging/active")
        assert response.status_code == 200
        
        active = response.json()
        assert "active_requests" in active
        assert "total_count" in active


if __name__ == "__main__":
    pytest.main([__file__]) 