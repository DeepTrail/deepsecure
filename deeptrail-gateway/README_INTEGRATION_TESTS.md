# DeepTrail Gateway Integration Tests

This document describes the integration tests for the DeepTrail Gateway, which verify end-to-end functionality between the gateway and the DeepTrail Control service.

## Overview

The integration tests verify:
- **Gateway-Control Plane Communication**: Authentication, policy enforcement, and secret injection
- **DeepSecure SDK Integration**: End-to-end workflows using the Python SDK
- **Security Features**: JWT validation, policy enforcement, and access control
- **Performance**: Response times and concurrent request handling

## Test Structure

### Test Categories

1. **Gateway-Control Plane Integration** (`TestGatewayControlPlaneIntegration`)
   - Health checks for both services
   - Authentication flows (valid/invalid JWT)
   - Basic proxy functionality

2. **DeepSecure SDK Integration** (`TestDeepSecureSDKIntegration`)
   - SDK client initialization
   - Agent creation and management
   - Credential issuance and secret fetching

3. **End-to-End Workflows** (`TestEndToEndWorkflow`)
   - Complete authentication → policy → secret injection → proxy flow
   - Policy enforcement (allow/deny scenarios)
   - Multi-step security workflows

4. **Performance Testing** (`TestPerformanceIntegration`)
   - Response time validation
   - Concurrent request handling
   - Load testing scenarios

5. **Security Testing** (`TestSecurityIntegration`)
   - Internal IP blocking
   - Request validation
   - Size limits and security boundaries

## Running the Tests

### Prerequisites

1. **Python Dependencies**:
   ```bash
   pip install pytest pytest-asyncio httpx
   ```

2. **Services Running**:
   - DeepTrail Control service at `http://localhost:8000`
   - DeepTrail Gateway service at `http://localhost:8002`

### Running Tests Locally

For tests against already running services:

```bash
# Run all integration tests
python run_integration_tests.py --mode local

# Run specific test pattern
python run_integration_tests.py --mode local --pattern "test_gateway_health"

# Run with custom URLs
python run_integration_tests.py --mode local --control-url http://localhost:8000 --gateway-url http://localhost:8002
```

### Running Tests with Docker Compose

For automated setup and teardown:

```bash
# Run tests with docker-compose (builds and starts services)
python run_integration_tests.py --mode docker

# Run specific tests with docker
python run_integration_tests.py --mode docker --pattern "test_sdk"
```

### Running Tests Directly with pytest

```bash
# Run all integration tests
pytest -v -m integration tests/test_integration.py

# Run specific test class
pytest -v -m integration tests/test_integration.py::TestGatewayControlPlaneIntegration

# Run with specific markers
pytest -v -m "integration and e2e" tests/test_integration.py

# Run performance tests
pytest -v -m "integration and performance" tests/test_integration.py

# Run security tests
pytest -v -m "integration and security" tests/test_integration.py
```

## Test Configuration

### Environment Variables

The tests use the following environment variables:

- `DEEPTRAIL_CONTROL_URL`: URL for the control plane service (default: `http://localhost:8000`)
- `DEEPTRAIL_GATEWAY_URL`: URL for the gateway service (default: `http://localhost:8002`)

### Test Fixtures

Key fixtures available in the tests:

- `integration_config`: Configuration dictionary for test parameters
- `http_client`: Async HTTP client for making requests
- `mock_deepsecure_client`: Mocked DeepSecure SDK client for testing

## Test Scenarios

### 1. Basic Health Checks

```python
async def test_gateway_health_check(self, http_client, integration_config):
    """Verify gateway is healthy and responding."""
    response = await http_client.get(f"{integration_config['gateway_url']}/health")
    assert response.status_code == 200
```

### 2. Authentication Flow

```python
async def test_gateway_proxy_without_auth(self, http_client, integration_config):
    """Test that gateway rejects unauthenticated requests."""
    response = await http_client.get(f"{integration_config['gateway_url']}/proxy/get")
    assert response.status_code == 401
```

### 3. End-to-End Proxy Workflow

```python
async def test_complete_proxy_workflow(self, mock_jwt_validation, mock_secret_injection, http_client, integration_config):
    """Test complete workflow: auth → policy → secret injection → proxy."""
    # Mock JWT validation and secret injection
    # Make request through gateway
    # Verify complete workflow execution
```

### 4. SDK Integration

```python
def test_sdk_client_initialization(self, mock_deepsecure_client, integration_config):
    """Test SDK client initialization with gateway URL."""
    client = Client(
        deeptrail_control_url=integration_config["control_plane_url"],
        deeptrail_gateway_url=integration_config["gateway_url"]
    )
    assert client.gateway_url == integration_config["gateway_url"]
```

## Test Results and Reporting

### Success Criteria

- ✅ All health checks pass
- ✅ Authentication flows work correctly
- ✅ Policy enforcement functions as expected
- ✅ Secret injection operates properly
- ✅ Proxy forwarding works end-to-end
- ✅ SDK integration is functional
- ✅ Security boundaries are enforced
- ✅ Performance is within acceptable limits

### Expected Test Output

```
========================== test session starts ==========================
collecting ... collected 20 items

tests/test_integration.py::TestGatewayControlPlaneIntegration::test_gateway_health_check PASSED
tests/test_integration.py::TestGatewayControlPlaneIntegration::test_control_plane_health_check PASSED
tests/test_integration.py::TestGatewayControlPlaneIntegration::test_gateway_proxy_without_auth PASSED
tests/test_integration.py::TestGatewayControlPlaneIntegration::test_gateway_proxy_with_valid_jwt PASSED
tests/test_integration.py::TestDeepSecureSDKIntegration::test_sdk_client_initialization PASSED
tests/test_integration.py::TestDeepSecureSDKIntegration::test_sdk_agent_creation PASSED
tests/test_integration.py::TestEndToEndWorkflow::test_complete_proxy_workflow PASSED
tests/test_integration.py::TestEndToEndWorkflow::test_policy_enforcement_workflow PASSED
tests/test_integration.py::TestPerformanceIntegration::test_gateway_response_time PASSED
tests/test_integration.py::TestSecurityIntegration::test_blocked_internal_ips PASSED

========================== 20 passed in 15.23s ==========================
```

## Troubleshooting

### Common Issues

1. **Services Not Ready**:
   ```
   ❌ Services did not become ready within the timeout period
   ```
   - Check that both services are running
   - Verify URLs are correct
   - Increase timeout in the test runner

2. **Authentication Failures**:
   ```
   AssertionError: Expected 200 but got 401
   ```
   - Verify JWT validation is properly mocked
   - Check that the control plane is issuing valid tokens
   - Ensure the gateway has the correct JWT secret

3. **Import Errors**:
   ```
   ModuleNotFoundError: No module named 'deepsecure'
   ```
   - Install the deepsecure package: `pip install -e ../`
   - Verify PYTHONPATH includes the parent directory

### Debug Mode

Run tests with verbose output and debugging:

```bash
# Run with maximum verbosity
pytest -vvv -s --tb=long -m integration tests/test_integration.py

# Run with debugging output
PYTHONPATH=.. python -m pytest -vvv -s --tb=long -m integration tests/test_integration.py
```

## Contributing

When adding new integration tests:

1. Follow the existing test structure and naming conventions
2. Use appropriate test markers (`@pytest.mark.integration`, `@pytest.mark.e2e`, etc.)
3. Mock external dependencies appropriately
4. Include both positive and negative test cases
5. Add documentation for new test scenarios
6. Ensure tests are deterministic and can run in any order

## Future Enhancements

Planned improvements for the integration test suite:

- **Real Service Testing**: Tests against actual running services (not mocked)
- **Load Testing**: Comprehensive performance and stress testing
- **Security Scanning**: Automated security vulnerability testing
- **Chaos Engineering**: Failure injection and resilience testing
- **Metrics Validation**: Verify monitoring and metrics collection
- **Multi-Environment**: Testing across different deployment environments 