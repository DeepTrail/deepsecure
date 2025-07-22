"""
Tests for request sanitization in the DeepTrail Gateway.

These tests verify that the request sanitizer properly:
- Sanitizes and normalizes request headers
- Cleans request content based on content type
- Validates and sanitizes query parameters
- Enforces character encoding standards
- Removes malicious patterns and content
- Handles various content types correctly
"""

import pytest
import json
import urllib.parse
from unittest.mock import Mock, patch
from fastapi import Request, FastAPI
from fastapi.testclient import TestClient
from starlette.datastructures import Headers, QueryParams

from app.core.request_sanitizer import (
    RequestSanitizer,
    SanitizationConfig,
    SanitizationLevel,
    HeaderSanitizer,
    ContentSanitizer,
    ParameterSanitizer,
    ContentType,
    sanitize_filename,
    sanitize_email,
    sanitize_url
)
from app.middleware.sanitization import SanitizationMiddleware


class TestSanitizationConfig:
    """Test sanitization configuration."""
    
    def test_default_config(self):
        """Test default sanitization configuration."""
        config = SanitizationConfig()
        
        assert config.level == SanitizationLevel.MODERATE
        assert config.normalize_headers is True
        assert config.remove_dangerous_headers is True
        assert config.validate_header_encoding is True
        assert config.sanitize_json is True
        assert config.sanitize_form_data is True
        assert config.sanitize_query_params is True
        assert config.escape_html_entities is True
        assert config.remove_null_bytes is True
        assert config.enforce_utf8 is True
        assert config.remove_control_chars is True
        assert config.normalize_unicode is True
        assert config.validate_content_type is True
        
        # Check limits
        assert config.max_header_value_length == 8192
        assert config.max_param_name_length == 256
        assert config.max_param_value_length == 4096
        assert config.max_params_count == 100
        
        # Check content types
        assert ContentType.JSON in config.allowed_content_types
        assert ContentType.FORM_URLENCODED in config.allowed_content_types
        assert ContentType.TEXT_PLAIN in config.allowed_content_types
    
    def test_strict_config(self):
        """Test strict sanitization configuration."""
        config = SanitizationConfig(level=SanitizationLevel.STRICT)
        
        assert config.level == SanitizationLevel.STRICT
        # Strict mode should have more restrictive settings
        assert config.remove_dangerous_headers is True
        assert config.validate_header_encoding is True
        assert config.escape_html_entities is True
    
    def test_lenient_config(self):
        """Test lenient sanitization configuration."""
        config = SanitizationConfig(level=SanitizationLevel.LENIENT)
        
        assert config.level == SanitizationLevel.LENIENT
        # Lenient mode should still maintain basic security


class TestHeaderSanitizer:
    """Test header sanitization functionality."""
    
    def test_sanitize_header_name(self):
        """Test header name sanitization."""
        config = SanitizationConfig()
        sanitizer = HeaderSanitizer(config)
        
        # Valid header names
        assert sanitizer.sanitize_header_name("Content-Type") == "content-type"
        assert sanitizer.sanitize_header_name("X-Custom-Header") == "x-custom-header"
        assert sanitizer.sanitize_header_name("Authorization") == "authorization"
        
        # Invalid header names
        assert sanitizer.sanitize_header_name("") is None
        assert sanitizer.sanitize_header_name("Invalid Header Name") is None
        assert sanitizer.sanitize_header_name("Header@Name") is None
        assert sanitizer.sanitize_header_name("Header Name") is None
        
        # Dangerous headers
        assert sanitizer.sanitize_header_name("X-Forwarded-Host") is None
        assert sanitizer.sanitize_header_name("X-Rewrite-URL") is None
        assert sanitizer.sanitize_header_name("X-Original-URL") is None
        
        # Too long header name
        long_name = "x-" + "a" * 300
        assert sanitizer.sanitize_header_name(long_name) is None
    
    def test_sanitize_header_value(self):
        """Test header value sanitization."""
        config = SanitizationConfig()
        sanitizer = HeaderSanitizer(config)
        
        # Valid header values
        assert sanitizer.sanitize_header_value("application/json") == "application/json"
        assert sanitizer.sanitize_header_value("Bearer token123") == "Bearer token123"
        
        # Header values with control characters
        assert sanitizer.sanitize_header_value("value\x00with\x01null") == "valuewithNull"
        assert sanitizer.sanitize_header_value("value\nwith\rnewlines") == "value\nwith\rnewlines"
        
        # Empty or whitespace values
        assert sanitizer.sanitize_header_value("") is None
        assert sanitizer.sanitize_header_value("   ") is None
        assert sanitizer.sanitize_header_value("  value  ") == "value"
        
        # Too long header value
        long_value = "a" * 10000
        result = sanitizer.sanitize_header_value(long_value)
        assert len(result) == config.max_header_value_length
    
    def test_sanitize_headers(self):
        """Test complete header sanitization."""
        config = SanitizationConfig()
        sanitizer = HeaderSanitizer(config)
        
        # Create mock headers
        headers = Headers([
            ("Content-Type", "application/json"),
            ("Authorization", "Bearer token123"),
            ("X-Forwarded-Host", "evil.com"),  # Should be removed
            ("X-Custom-Header", "custom\x00value"),  # Should be cleaned
            ("", "empty-name"),  # Should be removed
            ("Valid-Header", ""),  # Should be removed
        ])
        
        sanitized_headers, violations = sanitizer.sanitize_headers(headers)
        
        # Check that valid headers are preserved
        assert "content-type" in sanitized_headers
        assert sanitized_headers["content-type"] == "application/json"
        assert "authorization" in sanitized_headers
        assert sanitized_headers["authorization"] == "Bearer token123"
        
        # Check that dangerous headers are removed
        assert "x-forwarded-host" not in sanitized_headers
        
        # Check that cleaned headers are processed
        assert "x-custom-header" in sanitized_headers
        assert sanitized_headers["x-custom-header"] == "customvalue"
        
        # Check violations
        assert len(violations) > 0
        assert any("dangerous" in v.lower() for v in violations)


class TestContentSanitizer:
    """Test content sanitization functionality."""
    
    def test_detect_content_type(self):
        """Test content type detection."""
        config = SanitizationConfig()
        sanitizer = ContentSanitizer(config)
        
        # Test with headers
        headers = {"content-type": "application/json; charset=utf-8"}
        content_type = sanitizer.detect_content_type(headers, b'{"key": "value"}')
        assert content_type == "application/json"
        
        # Test JSON detection from body
        headers = {}
        json_body = b'{"key": "value"}'
        content_type = sanitizer.detect_content_type(headers, json_body)
        assert content_type == ContentType.JSON
        
        # Test XML detection from body
        xml_body = b'<?xml version="1.0"?><root></root>'
        content_type = sanitizer.detect_content_type(headers, xml_body)
        assert content_type == ContentType.XML
        
        # Test form data detection
        form_body = b'key1=value1&key2=value2'
        content_type = sanitizer.detect_content_type(headers, form_body)
        assert content_type == ContentType.FORM_URLENCODED
        
        # Test binary content
        binary_body = b'\x00\x01\x02\x03'
        content_type = sanitizer.detect_content_type(headers, binary_body)
        assert content_type == ContentType.BINARY
    
    def test_sanitize_string(self):
        """Test string sanitization."""
        config = SanitizationConfig()
        sanitizer = ContentSanitizer(config)
        
        # Test XSS removal
        malicious_string = "<script>alert('xss')</script>Hello"
        sanitized = sanitizer.sanitize_string(malicious_string)
        assert "<script>" not in sanitized
        assert "Hello" in sanitized
        
        # Test HTML escaping
        html_string = "<div>content</div>"
        sanitized = sanitizer.sanitize_string(html_string)
        assert "&lt;div&gt;" in sanitized
        assert "&lt;/div&gt;" in sanitized
        
        # Test null byte removal
        null_string = "text\x00with\x00nulls"
        sanitized = sanitizer.sanitize_string(null_string)
        assert "\x00" not in sanitized
        assert sanitized == "textwithnulls"
        
        # Test unicode normalization
        unicode_string = "café"  # Contains composed characters
        sanitized = sanitizer.sanitize_string(unicode_string)
        assert sanitized == "café"  # Should be normalized
    
    def test_sanitize_json(self):
        """Test JSON content sanitization."""
        config = SanitizationConfig()
        sanitizer = ContentSanitizer(config)
        
        # Test malicious JSON
        malicious_json = {
            "name": "<script>alert('xss')</script>",
            "description": "Normal text",
            "nested": {
                "value": "javascript:alert('xss')"
            },
            "array": ["<iframe src='evil.com'>", "safe value"]
        }
        
        json_body = json.dumps(malicious_json).encode('utf-8')
        sanitized_body, violations = sanitizer.sanitize_json(json_body)
        
        # Parse sanitized JSON
        sanitized_data = json.loads(sanitized_body.decode('utf-8'))
        
        # Check that malicious content is removed/escaped
        assert "<script>" not in sanitized_data["name"]
        assert "javascript:" not in sanitized_data["nested"]["value"]
        assert "<iframe" not in sanitized_data["array"][0]
        
        # Check that safe content is preserved
        assert sanitized_data["description"] == "Normal text"
        assert sanitized_data["array"][1] == "safe value"
    
    def test_sanitize_form_data(self):
        """Test form data sanitization."""
        config = SanitizationConfig()
        sanitizer = ContentSanitizer(config)
        
        # Test malicious form data
        form_data = {
            "username": ["<script>alert('xss')</script>"],
            "email": ["user@example.com"],
            "comment": ["<iframe src='evil.com'>malicious</iframe>"]
        }
        
        form_body = urllib.parse.urlencode(form_data, doseq=True).encode('utf-8')
        sanitized_body, violations = sanitizer.sanitize_form_data(form_body)
        
        # Parse sanitized form data
        sanitized_data = urllib.parse.parse_qs(sanitized_body.decode('utf-8'))
        
        # Check that malicious content is removed/escaped
        assert "<script>" not in sanitized_data["username"][0]
        assert "<iframe" not in sanitized_data["comment"][0]
        
        # Check that safe content is preserved
        assert sanitized_data["email"][0] == "user@example.com"
    
    def test_sanitize_text(self):
        """Test plain text sanitization."""
        config = SanitizationConfig()
        sanitizer = ContentSanitizer(config)
        
        # Test malicious text
        malicious_text = "Hello <script>alert('xss')</script> World"
        text_body = malicious_text.encode('utf-8')
        
        sanitized_body, violations = sanitizer.sanitize_text(text_body)
        sanitized_text = sanitized_body.decode('utf-8')
        
        # Check that malicious content is removed
        assert "<script>" not in sanitized_text
        assert "Hello" in sanitized_text
        assert "World" in sanitized_text
    
    def test_sanitize_content_by_type(self):
        """Test content sanitization based on content type."""
        config = SanitizationConfig()
        sanitizer = ContentSanitizer(config)
        
        # Test JSON sanitization
        json_body = b'{"name": "<script>alert(1)</script>"}'
        sanitized_body, violations = sanitizer.sanitize_content(json_body, ContentType.JSON)
        sanitized_data = json.loads(sanitized_body.decode('utf-8'))
        assert "<script>" not in sanitized_data["name"]
        
        # Test form data sanitization
        form_body = b'name=%3Cscript%3Ealert%281%29%3C%2Fscript%3E'
        sanitized_body, violations = sanitizer.sanitize_content(form_body, ContentType.FORM_URLENCODED)
        assert b"<script>" not in sanitized_body
        
        # Test binary content (should only remove null bytes)
        binary_body = b'\x00\x01\x02\x03'
        sanitized_body, violations = sanitizer.sanitize_content(binary_body, ContentType.BINARY)
        assert b'\x00' not in sanitized_body
        assert b'\x01\x02\x03' == sanitized_body


class TestParameterSanitizer:
    """Test parameter sanitization functionality."""
    
    def test_sanitize_query_params(self):
        """Test query parameter sanitization."""
        config = SanitizationConfig()
        sanitizer = ParameterSanitizer(config)
        
        # Create mock query parameters
        query_params = QueryParams([
            ("search", "<script>alert('xss')</script>"),
            ("category", "electronics"),
            ("page", "1"),
            ("filter", "javascript:alert('xss')"),
            ("safe_param", "normal value")
        ])
        
        sanitized_params, violations = sanitizer.sanitize_query_params(query_params)
        
        # Check that malicious content is removed/escaped
        assert "<script>" not in sanitized_params["search"]
        assert "javascript:" not in sanitized_params["filter"]
        
        # Check that safe content is preserved
        assert sanitized_params["category"] == "electronics"
        assert sanitized_params["page"] == "1"
        assert sanitized_params["safe_param"] == "normal value"
    
    def test_parameter_limits(self):
        """Test parameter count and size limits."""
        config = SanitizationConfig(max_params_count=3, max_param_name_length=10, max_param_value_length=20)
        sanitizer = ParameterSanitizer(config)
        
        # Create parameters that exceed limits
        query_params = QueryParams([
            ("param1", "value1"),
            ("param2", "value2"),
            ("param3", "value3"),
            ("param4", "value4"),  # Should be ignored due to count limit
            ("very_long_parameter_name", "value"),  # Should be truncated
            ("param5", "a" * 50)  # Should be truncated
        ])
        
        sanitized_params, violations = sanitizer.sanitize_query_params(query_params)
        
        # Check parameter count limit
        assert len(sanitized_params) <= config.max_params_count
        
        # Check violations
        assert len(violations) > 0
        assert any("Too many parameters" in v for v in violations)


class TestRequestSanitizer:
    """Test the main request sanitizer functionality."""
    
    def create_mock_request(self, method: str = "GET", path: str = "/test", 
                           headers: dict = None, query_params: dict = None):
        """Create a mock request for testing."""
        mock_request = Mock(spec=Request)
        mock_request.method = method
        mock_request.url.path = path
        mock_request.headers = Headers(headers or {})
        mock_request.query_params = QueryParams(query_params or {})
        mock_request.client = Mock()
        mock_request.client.host = "203.0.113.1"
        return mock_request
    
    @pytest.mark.asyncio
    async def test_sanitize_request_basic(self):
        """Test basic request sanitization."""
        config = SanitizationConfig()
        sanitizer = RequestSanitizer(config)
        
        request = self.create_mock_request(
            method="POST",
            path="/api/data",
            headers={"Content-Type": "application/json"},
            query_params={"search": "test"}
        )
        
        body = b'{"message": "Hello World"}'
        result = await sanitizer.sanitize_request(request, body)
        
        assert result.sanitized_body == body  # Should be unchanged
        assert result.content_type == "application/json"
        assert result.encoding == "utf-8"
        assert not result.changes_made
    
    @pytest.mark.asyncio
    async def test_sanitize_request_with_malicious_content(self):
        """Test request sanitization with malicious content."""
        config = SanitizationConfig()
        sanitizer = RequestSanitizer(config)
        
        request = self.create_mock_request(
            method="POST",
            path="/api/data",
            headers={"Content-Type": "application/json"},
            query_params={"search": "<script>alert('xss')</script>"}
        )
        
        malicious_body = b'{"message": "<script>alert(1)</script>"}'
        result = await sanitizer.sanitize_request(request, malicious_body)
        
        # Check that malicious content is removed
        sanitized_data = json.loads(result.sanitized_body.decode('utf-8'))
        assert "<script>" not in sanitized_data["message"]
        assert "<script>" not in result.sanitized_query_params["search"]
        
        assert result.changes_made
        assert len(result.violations) == 0  # Should be warnings, not violations
    
    @pytest.mark.asyncio
    async def test_sanitize_request_encoding_conversion(self):
        """Test request sanitization with encoding conversion."""
        config = SanitizationConfig(enforce_utf8=True)
        sanitizer = RequestSanitizer(config)
        
        request = self.create_mock_request(
            method="POST",
            path="/api/data",
            headers={"Content-Type": "text/plain; charset=latin-1"}
        )
        
        # Latin-1 encoded body
        latin1_body = "Café".encode('latin-1')
        result = await sanitizer.sanitize_request(request, latin1_body)
        
        # Should be converted to UTF-8
        assert result.encoding == "utf-8"
        assert result.sanitized_body.decode('utf-8') == "Café"
        assert result.changes_made
        assert len(result.warnings) > 0
    
    @pytest.mark.asyncio
    async def test_sanitize_request_blocked_content_type(self):
        """Test request sanitization with blocked content type."""
        config = SanitizationConfig(
            validate_content_type=True,
            allowed_content_types=["application/json"]
        )
        sanitizer = RequestSanitizer(config)
        
        request = self.create_mock_request(
            method="POST",
            path="/api/data",
            headers={"Content-Type": "application/x-dangerous"}
        )
        
        body = b'dangerous content'
        result = await sanitizer.sanitize_request(request, body)
        
        # Should be blocked
        assert len(result.violations) > 0
        assert any("Blocked content type" in v for v in result.violations)
        assert result.changes_made


class TestUtilityFunctions:
    """Test utility functions for sanitization."""
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        # Valid filename
        assert sanitize_filename("document.txt") == "document.txt"
        
        # Filename with dangerous characters
        assert sanitize_filename("../../../etc/passwd") == "______etc_passwd"
        assert sanitize_filename("file<>name.txt") == "file__name.txt"
        assert sanitize_filename("file:name.txt") == "file_name.txt"
        
        # Empty or invalid filenames
        assert sanitize_filename("") == "unnamed"
        assert sanitize_filename("   ") == "unnamed"
        assert sanitize_filename("...") == "unnamed"
        
        # Long filename
        long_name = "a" * 300 + ".txt"
        sanitized = sanitize_filename(long_name)
        assert len(sanitized) <= 255
        assert sanitized.endswith(".txt")
    
    def test_sanitize_email(self):
        """Test email sanitization."""
        # Valid emails
        assert sanitize_email("user@example.com") == "user@example.com"
        assert sanitize_email("User@Example.COM") == "user@example.com"
        
        # Invalid emails
        assert sanitize_email("invalid-email") is None
        assert sanitize_email("user@") is None
        assert sanitize_email("@example.com") is None
        assert sanitize_email("user@example") is None
        
        # Empty or whitespace
        assert sanitize_email("") is None
        assert sanitize_email("   ") is None
        
        # Too long email
        long_email = "a" * 300 + "@example.com"
        assert sanitize_email(long_email) is None
    
    def test_sanitize_url(self):
        """Test URL sanitization."""
        # Valid URLs
        assert sanitize_url("https://example.com") == "https://example.com"
        assert sanitize_url("http://example.com/path?query=value") == "http://example.com/path?query=value"
        
        # Dangerous URLs
        assert sanitize_url("javascript:alert('xss')") is None
        assert sanitize_url("vbscript:alert('xss')") is None
        assert sanitize_url("data:text/html,<script>alert(1)</script>") is None
        assert sanitize_url("file:///etc/passwd") is None
        
        # Invalid URLs
        assert sanitize_url("not-a-url") is None
        assert sanitize_url("ftp://example.com") is None  # Only http/https allowed
        
        # Empty or whitespace
        assert sanitize_url("") is None
        assert sanitize_url("   ") is None


class TestSanitizationMiddleware:
    """Test sanitization middleware integration."""
    
    def test_middleware_initialization(self):
        """Test sanitization middleware initialization."""
        app = FastAPI()
        
        # Test that middleware can be initialized
        middleware = SanitizationMiddleware(app)
        assert middleware.sanitizer is not None
        assert middleware.config is not None
    
    @pytest.mark.asyncio
    async def test_middleware_skips_health_endpoints(self):
        """Test that middleware skips sanitization for health endpoints."""
        app = FastAPI()
        middleware = SanitizationMiddleware(app)
        
        # Mock request to health endpoint
        request = Mock(spec=Request)
        request.url.path = "/health"
        
        # Mock call_next
        async def mock_call_next(req):
            return Mock(status_code=200)
        
        response = await middleware.dispatch(request, mock_call_next)
        assert response.status_code == 200
    
    def test_sanitization_middleware_with_app(self):
        """Test sanitization middleware with FastAPI app."""
        app = FastAPI()
        app.add_middleware(SanitizationMiddleware)
        
        @app.post("/test")
        async def test_endpoint(request: Request):
            return {"message": "test"}
        
        client = TestClient(app)
        
        # Test with clean request
        response = client.post("/test", json={"message": "clean data"})
        assert response.status_code == 200
        
        # Test with malicious request would require more complex setup
        # This is a basic test to ensure the middleware doesn't break the app
        assert app is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 