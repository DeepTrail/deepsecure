import pytest
import uuid
import json

from deepsecure import Client
from deepsecure.exceptions import DeepSecureClientError

# This test requires both deeptrail-control and deeptrail-gateway to be running.
# It also requires an external service (httpbin.org) to be available.

@pytest.mark.e2e
def test_split_key_secret_storage_and_jit_reassembly():
    """
    Tests the full end-to-end flow of storing a secret via split-key
    and retrieving it via the JIT reassembly gateway.
    """
    client = Client()
    
    # 1. Store a new secret. This will be split between the control plane and gateway.
    secret_name = f"e2e-test-secret-{uuid.uuid4()}"
    secret_value = f"e2e-test-value-{uuid.uuid4()}"
    # We will use httpbin to echo back headers, so we can verify the injection.
    target_base_url = "https://httpbin.org"
    
    try:
        store_response = client.store_secret_direct(
            name=secret_name,
            value=secret_value,
            target_base_url=target_base_url
        )
        assert store_response["name"] == secret_name
    except Exception as e:
        pytest.fail(f"Failed to store secret for E2E test: {e}")

    # 2. Create a test agent to make the authenticated request to the gateway.
    agent_name = f"e2e-test-agent-{uuid.uuid4()}"
    try:
        agent = client.agent(name=agent_name, auto_create=True)
        assert agent.id is not None
    except Exception as e:
        pytest.fail(f"Failed to create agent for E2E test: {e}")

    # 3. Use the agent to request the secret via the gateway.
    # The gateway will reassemble the secret and inject it into a call to httpbin.org/get.
    try:
        # The 'path' is the path on the target service (httpbin.org)
        secret_resource = client.get_secret(
            agent_id=agent.id,
            secret_name=secret_name,
            path="/get"
        )
        
        # The 'value' of the secret resource is the response body from the target service.
        response_body = secret_resource.value
        response_data = json.loads(response_body)
        
        # 4. Assert that the secret was correctly injected.
        # httpbin.org/get returns the request headers in the response body.
        injected_auth_header = response_data.get("headers", {}).get("Authorization")
        
        assert injected_auth_header is not None
        assert injected_auth_header == f"Bearer {secret_value}"
        
    except DeepSecureClientError as e:
        pytest.fail(f"E2E test failed during get_secret call: {e} - {e.detail}")
    except (json.JSONDecodeError, KeyError) as e:
        pytest.fail(f"Failed to parse response from httpbin.org: {e}")
    finally:
        # Clean up the agent
        try:
            agent.delete()
        except:
            pass # Ignore cleanup failures 