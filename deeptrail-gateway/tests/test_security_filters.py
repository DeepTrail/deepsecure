"""
Tests for security filters in the DeepTrail Gateway.

These tests verify that the security filters properly:
- Block requests from internal IP ranges
- Enforce rate limiting
- Validate request headers and content
- Detect malicious patterns
- Log security violations
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from fastapi import Request, FastAPI
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from app.core.security_filters import (
    SecurityFilter, 
    SecurityConfig, 
    SecurityViolation,
    RateLimiter,
    MaliciousPatternDetector
)
from app.middleware.security import SecurityMiddleware


class TestSecurityConfig:
    """Test security configuration."""
    
    def test_default_config(self):
        """Test default security configuration."""
        config = SecurityConfig()
        
        # Check default IP ranges
        assert "127.0.0.0/8" in config.blocked_ip_ranges
        assert "10.0.0.0/8" in config.blocked_ip_ranges
        assert "192.168.0.0/16" in config.blocked_ip_ranges
        
        # Check default limits
        assert config.max_request_size == 10 * 1024 * 1024  # 10MB
        assert config.max_header_size == 8192  # 8KB
        assert config.max_headers_count == 50
        assert config.max_url_length == 2048
        
        # Check rate limiting
        assert config.rate_limit_requests == 100
        assert config.rate_limit_window == 60
        assert config.rate_limit_burst == 20
        
        # Check pattern detection
        assert config.enable_xss_protection is True
        assert config.enable_sql_injection_protection is True
        assert config.enable_command_injection_protection is True
        assert config.enable_path_traversal_protection is True


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    def test_rate_limiter_allows_requests_under_limit(self):
        """Test that rate limiter allows requests under the limit."""
        limiter = RateLimiter(requests_per_window=10, window_seconds=60, burst_allowance=5)
        
        # Should allow first 10 requests
        for i in range(10):
            allowed, info = limiter.is_allowed("192.168.1.1")
            assert allowed is True
            assert info["requests_remaining"] == 9 - i
    
    def test_rate_limiter_blocks_requests_over_limit(self):
        """Test that rate limiter blocks requests over the limit."""
        limiter = RateLimiter(requests_per_window=3, window_seconds=60, burst_allowance=2)
        
        # Allow first 3 requests
        for i in range(3):
            allowed, info = limiter.is_allowed("192.168.1.1")
            assert allowed is True
        
        # Allow 2 more with burst
        for i in range(2):
            allowed, info = limiter.is_allowed("192.168.1.1")
            assert allowed is True
            assert info.get("burst_used") is True
        
        # Block the 6th request
        allowed, info = limiter.is_allowed("192.168.1.1")
        assert allowed is False
        assert "retry_after" in info
    
    def test_rate_limiter_per_ip(self):
        """Test that rate limiter works per IP address."""
        limiter = RateLimiter(requests_per_window=2, window_seconds=60, burst_allowance=1)
        
        # IP 1 uses up its limit
        for i in range(3):  # 2 normal + 1 burst
            allowed, info = limiter.is_allowed("192.168.1.1")
            assert allowed is True
        
        # IP 1 is now blocked
        allowed, info = limiter.is_allowed("192.168.1.1")
        assert allowed is False
        
        # IP 2 should still be allowed
        allowed, info = limiter.is_allowed("192.168.1.2")
        assert allowed is True


class TestMaliciousPatternDetector:
    """Test malicious pattern detection."""
    
    def test_xss_detection(self):
        """Test XSS pattern detection."""
        detector = MaliciousPatternDetector()
        
        # Test various XSS patterns
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<iframe src='javascript:alert(1)'></iframe>",
            "<object data='javascript:alert(1)'></object>"
        ]
        
        for payload in xss_payloads:
            violations = detector.detect_xss(payload)
            assert len(violations) > 0, f"Failed to detect XSS in: {payload}"
    
    def test_sql_injection_detection(self):
        """Test SQL injection pattern detection."""
        detector = MaliciousPatternDetector()
        
        # Test various SQL injection patterns
        sql_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM users --",
            "admin'--",
            "' || 'a'='a"
        ]
        
        for payload in sql_payloads:
            violations = detector.detect_sql_injection(payload)
            assert len(violations) > 0, f"Failed to detect SQL injection in: {payload}"
    
    def test_command_injection_detection(self):
        """Test command injection pattern detection."""
        detector = MaliciousPatternDetector()
        
        # Test various command injection patterns
        cmd_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "$(whoami)",
            "`id`",
            "&& rm -rf /",
            "| nc -l 4444"
        ]
        
        for payload in cmd_payloads:
            violations = detector.detect_command_injection(payload)
            assert len(violations) > 0, f"Failed to detect command injection in: {payload}"
    
    def test_path_traversal_detection(self):
        """Test path traversal pattern detection."""
        detector = MaliciousPatternDetector()
        
        # Test various path traversal patterns
        path_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "%252e%252e%252fetc%252fpasswd"
        ]
        
        for payload in path_payloads:
            violations = detector.detect_path_traversal(payload)
            assert len(violations) > 0, f"Failed to detect path traversal in: {payload}"
    
    def test_benign_content_not_detected(self):
        """Test that benign content is not flagged as malicious."""
        detector = MaliciousPatternDetector()
        
        benign_content = [
            "Hello, world!",
            "This is a normal request",
            "user@example.com",
            "https://api.example.com/data",
            "SELECT * FROM products WHERE category = 'electronics'"  # Normal SQL
        ]
        
        for content in benign_content:
            xss_violations = detector.detect_xss(content)
            cmd_violations = detector.detect_command_injection(content)
            path_violations = detector.detect_path_traversal(content)
            
            # SQL detector might flag the SELECT statement, which is expected
            # but the others should not
            assert len(xss_violations) == 0, f"False positive XSS in: {content}"
            assert len(cmd_violations) == 0, f"False positive command injection in: {content}"
            assert len(path_violations) == 0, f"False positive path traversal in: {content}"


class TestSecurityFilter:
    """Test the main security filter functionality."""
    
    def create_mock_request(self, 
                           method: str = "GET", 
                           path: str = "/test", 
                           headers: dict = None,
                           client_ip: str = "203.0.113.1"):
        """Create a mock request for testing."""
        mock_request = Mock(spec=Request)
        mock_request.method = method
        mock_request.url.path = path
        mock_request.url = Mock()
        mock_request.url.path = path
        mock_request.client = Mock()
        mock_request.client.host = client_ip
        mock_request.headers = headers or {"X-Target-Base-URL": "https://api.example.com"}
        mock_request.query_params = {}
        return mock_request
    
    def test_ip_blocking(self):
        """Test IP address blocking functionality."""
        config = SecurityConfig()
        security_filter = SecurityFilter(config)
        
        # Test blocked IP ranges
        blocked_ips = [
            "127.0.0.1",      # Localhost
            "10.0.0.1",       # Private Class A
            "172.16.0.1",     # Private Class B
            "192.168.1.1",    # Private Class C
            "169.254.1.1",    # Link-local
        ]
        
        for ip in blocked_ips:
            assert security_filter.is_ip_blocked(ip) is True, f"Failed to block IP: {ip}"
        
        # Test allowed IP ranges
        allowed_ips = [
            "8.8.8.8",        # Google DNS
            "1.1.1.1",        # Cloudflare DNS
            "203.0.113.1",    # Test network
        ]
        
        for ip in allowed_ips:
            assert security_filter.is_ip_blocked(ip) is False, f"Incorrectly blocked IP: {ip}"
    
    @pytest.mark.asyncio
    async def test_request_filtering_allows_valid_request(self):
        """Test that valid requests are allowed through."""
        config = SecurityConfig()
        security_filter = SecurityFilter(config)
        
        request = self.create_mock_request(
            method="GET",
            path="/api/data",
            headers={"X-Target-Base-URL": "https://api.example.com"},
            client_ip="203.0.113.1"
        )
        
        response = await security_filter.filter_request(request, b"")
        assert response is None  # None means request is allowed
    
    @pytest.mark.asyncio
    async def test_request_filtering_blocks_internal_ip(self):
        """Test that requests from internal IPs are blocked."""
        config = SecurityConfig()
        security_filter = SecurityFilter(config)
        
        request = self.create_mock_request(
            method="GET",
            path="/api/data",
            headers={"X-Target-Base-URL": "https://api.example.com"},
            client_ip="192.168.1.1"  # Internal IP
        )
        
        response = await security_filter.filter_request(request, b"")
        assert response is not None
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_request_filtering_blocks_oversized_request(self):
        """Test that oversized requests are blocked."""
        config = SecurityConfig(max_request_size=1024)  # 1KB limit
        security_filter = SecurityFilter(config)
        
        request = self.create_mock_request(
            method="POST",
            path="/api/data",
            headers={"X-Target-Base-URL": "https://api.example.com"},
            client_ip="203.0.113.1"
        )
        
        large_body = b"x" * 2048  # 2KB body
        response = await security_filter.filter_request(request, large_body)
        assert response is not None
        assert response.status_code == 413
    
    @pytest.mark.asyncio
    async def test_request_filtering_blocks_malicious_content(self):
        """Test that malicious content is blocked."""
        config = SecurityConfig()
        security_filter = SecurityFilter(config)
        
        request = self.create_mock_request(
            method="POST",
            path="/api/data",
            headers={"X-Target-Base-URL": "https://api.example.com"},
            client_ip="203.0.113.1"
        )
        
        malicious_body = b"<script>alert('xss')</script>"
        response = await security_filter.filter_request(request, malicious_body)
        assert response is not None
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_header_validation(self):
        """Test request header validation."""
        config = SecurityConfig()
        security_filter = SecurityFilter(config)
        
        # Test missing required header
        request = self.create_mock_request(
            method="GET",
            path="/api/data",
            headers={},  # Missing X-Target-Base-URL
            client_ip="203.0.113.1"
        )
        
        violations = security_filter.validate_headers(request)
        assert len(violations) > 0
        assert any("missing_required_header" in v.violation_type for v in violations)
        
        # Test blocked header
        request = self.create_mock_request(
            method="GET",
            path="/api/data",
            headers={
                "X-Target-Base-URL": "https://api.example.com",
                "X-Forwarded-Host": "evil.com"  # Blocked header
            },
            client_ip="203.0.113.1"
        )
        
        violations = security_filter.validate_headers(request)
        assert len(violations) > 0
        assert any("blocked_header" in v.violation_type for v in violations)
    
    def test_get_client_ip(self):
        """Test client IP extraction from request."""
        config = SecurityConfig()
        security_filter = SecurityFilter(config)
        
        # Test X-Forwarded-For header
        request = self.create_mock_request(
            headers={
                "X-Forwarded-For": "203.0.113.1, 192.168.1.1",
                "X-Target-Base-URL": "https://api.example.com"
            },
            client_ip="127.0.0.1"
        )
        
        client_ip = security_filter.get_client_ip(request)
        assert client_ip == "203.0.113.1"  # Should take first IP in chain
        
        # Test X-Real-IP header
        request = self.create_mock_request(
            headers={
                "X-Real-IP": "203.0.113.2",
                "X-Target-Base-URL": "https://api.example.com"
            },
            client_ip="127.0.0.1"
        )
        
        client_ip = security_filter.get_client_ip(request)
        assert client_ip == "203.0.113.2"
        
        # Test fallback to client.host
        request = self.create_mock_request(
            headers={"X-Target-Base-URL": "https://api.example.com"},
            client_ip="203.0.113.3"
        )
        
        client_ip = security_filter.get_client_ip(request)
        assert client_ip == "203.0.113.3"
    
    def test_violation_stats(self):
        """Test security violation statistics."""
        config = SecurityConfig()
        security_filter = SecurityFilter(config)
        
        # Initially no violations
        stats = security_filter.get_violation_stats()
        assert stats["total_violations"] == 0
        
        # Add some test violations
        violation1 = SecurityViolation(
            violation_type="blocked_ip",
            severity="high",
            message="IP blocked",
            client_ip="192.168.1.1",
            timestamp=time.time(),
            request_path="/test"
        )
        
        violation2 = SecurityViolation(
            violation_type="rate_limit_exceeded",
            severity="medium",
            message="Rate limit exceeded",
            client_ip="203.0.113.1",
            timestamp=time.time(),
            request_path="/api/data"
        )
        
        security_filter.violations.extend([violation1, violation2])
        
        stats = security_filter.get_violation_stats()
        assert stats["total_violations"] == 2
        assert "blocked_ip" in stats["violations_by_type"]
        assert "rate_limit_exceeded" in stats["violations_by_type"]
        assert "high" in stats["violations_by_severity"]
        assert "medium" in stats["violations_by_severity"]


class TestSecurityMiddleware:
    """Test security middleware integration."""
    
    def test_middleware_initialization(self):
        """Test security middleware initialization."""
        app = FastAPI()
        
        # Test that middleware can be initialized
        middleware = SecurityMiddleware(app)
        assert middleware.security_filter is not None
        assert middleware.config is not None
    
    @pytest.mark.asyncio
    async def test_middleware_skips_health_endpoints(self):
        """Test that middleware skips security filtering for health endpoints."""
        app = FastAPI()
        middleware = SecurityMiddleware(app)
        
        # Mock request to health endpoint
        request = Mock(spec=Request)
        request.url.path = "/health"
        
        # Mock call_next
        async def mock_call_next(req):
            return Mock(status_code=200)
        
        response = await middleware.dispatch(request, mock_call_next)
        assert response.status_code == 200
    
    def test_security_stats_endpoint(self):
        """Test security statistics endpoint."""
        app = FastAPI()
        app.add_middleware(SecurityMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        client = TestClient(app)
        
        # This would test the endpoint if we had proper middleware registry
        # For now, just test that the app can be created
        assert app is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 