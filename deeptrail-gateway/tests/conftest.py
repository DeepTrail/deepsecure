"""
Pytest configuration for DeepTrail Gateway tests.

This module provides common fixtures and configuration for testing
the core PEP functionality of the gateway.
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import test dependencies
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

# Test configuration
@pytest.fixture(scope="function")
def event_loop():
    """Create a new event loop for each test function."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def cleanup_http_client():
    """Reset the global HTTP client state between tests."""
    yield
    # Reset the global HTTP client reference (avoid async cleanup in tests)
    import app.core.http_client
    app.core.http_client._http_client = None

@pytest.fixture
def valid_jwt_payload():
    """Provide a valid JWT payload for testing."""
    from datetime import datetime, timezone, timedelta
    return {
        "sub": "agent-test-123",
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        "permissions": ["domain:httpbin.org", "method:GET", "method:POST"],
        "allowed_domains": ["httpbin.org"],
        "allowed_methods": ["GET", "POST"]
    }

@pytest.fixture
def mock_jwt_validation():
    """Provide a properly configured JWT validation mock."""
    with patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token') as mock:
        # Configure as AsyncMock that returns the dict directly
        async def mock_validate_jwt(*args, **kwargs):
            return {
                "sub": "agent-test-123",
                "permissions": ["domain:httpbin.org", "method:GET", "method:POST"],
                "allowed_domains": ["httpbin.org"],
                "allowed_methods": ["GET", "POST"]
            }
        mock.side_effect = mock_validate_jwt
        yield mock

@pytest.fixture
def test_config():
    """Provide test configuration for the gateway."""
    return {
        "proxy_type": "deeptrail-gateway",
        "host": "127.0.0.1",
        "port": 8002,
        "control_plane_url": "http://localhost:8000",
        "security": {
            "block_internal_ips": True,
            "max_request_size": 10485760,  # 10MB
            "request_timeout": 30
        },
        "routing": {
            "target_header": "X-Target-Base-URL",
            "path_prefix": "/proxy"
        },
        "authentication": {
            "jwt_validation": True
        },
        "policy": {
            "enforcement_mode": "strict"
        },
        "logging": {
            "enable_request_logging": True,
            "log_level": "INFO"
        }
    }

@pytest.fixture
def mock_http_client():
    """Provide a mock HTTP client for testing."""
    # Reset the global client first
    import app.core.http_client
    app.core.http_client._http_client = None
    
    with patch('app.core.http_client.get_http_client') as mock_get_client:
        # Create a mock client instance with proper async methods
        mock_client_instance = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content = b'{"test": "response"}'
        
        # Set up async methods
        mock_client_instance.proxy_request = AsyncMock(return_value=mock_response)
        mock_client_instance.proxy_stream_request = AsyncMock(return_value=mock_response)
        mock_client_instance.close = AsyncMock()
        
        # Make get_http_client return the mock instance
        async def mock_get_http_client():
            return mock_client_instance
        
        mock_get_client.side_effect = mock_get_http_client
        yield mock_get_client

@pytest.fixture
def test_client():
    """Provide a test client for the FastAPI application."""
    from app.main import app
    return TestClient(app)

# Test markers
# pytest_plugins moved to root conftest.py to avoid deprecation warning

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    ) 