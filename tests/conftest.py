import pytest
import subprocess
import time
import os
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner

from deepsecure.client import Client as DeepSecureClient
from deepsecure._core.agent_client import AgentClient
from deepsecure._core.identity_manager import IdentityManager, IdentityManagerError
from deepsecure.exceptions import DeepSecureError, DeepSecureClientError

COMPOSE_FILE = os.path.join(os.path.dirname(__file__), '..', 'deeptrail-control', 'docker-compose.test.yml')

# Mock key data for consistent testing
MOCK_PRIVATE_KEY_B64 = "cHJpdmF0ZV9rZXlfYnl0ZXNfZm9yX3Rlc3RpbmdfMzI="
MOCK_PUBLIC_KEY_B64 = "cHVibGljX2tleV9ieXRlc19mb3JfdGVzdGluZ18zMg=="
MOCK_SIGNATURE = "bW9ja19zaWduYXR1cmVfZm9yX3Rlc3RpbmdfNjQ="

@pytest.fixture
def runner():
    """Fixture providing a CliRunner for testing CLI commands."""
    return CliRunner()

@pytest.fixture
def identity_manager_mock():
    """Fixture providing a mocked IdentityManager for testing."""
    mock_identity_manager = MagicMock(spec=IdentityManager)
    
    # Mock common methods
    mock_identity_manager.get_private_key.return_value = MOCK_PRIVATE_KEY_B64
    mock_identity_manager.generate_ed25519_keypair_raw_b64.return_value = {
        'private_key': MOCK_PRIVATE_KEY_B64,
        'public_key': MOCK_PUBLIC_KEY_B64
    }
    mock_identity_manager.sign.return_value = MOCK_SIGNATURE
    mock_identity_manager.store_private_key_directly.return_value = None
    mock_identity_manager.delete_private_key.return_value = None
    
    return mock_identity_manager

@pytest.fixture
def mock_client_class():
    """Fixture providing a mocked Client class for testing."""
    with patch('deepsecure.client.Client', autospec=True) as mock_client:
        yield mock_client

def is_service_ready(port):
    """Check if a service is ready by trying to connect to its port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect(('localhost', port))
            return True
        except ConnectionRefusedError:
            return False

@pytest.fixture(scope="session")
def test_environment(request):
    """
    Manages the lifecycle of the test environment using docker-compose.
    Spins up the services before tests and tears them down after.
    """
    try:
        # Forcefully tear down any lingering environment to ensure a clean slate
        print("\nEnsuring clean test environment by running docker-compose down...")
        subprocess.run(
            ["docker-compose", "-f", COMPOSE_FILE, "down", "-v", "--remove-orphans"],
            check=True,
            capture_output=True,
            text=True
        )

        print(f"\nStarting test environment from {COMPOSE_FILE}...")
        # Add a check to ensure docker-compose.test.yml exists
        if not os.path.exists(COMPOSE_FILE):
            pytest.fail(f"Test compose file not found: {COMPOSE_FILE}")

        # Execute docker-compose up
        up_process = subprocess.run(
            ["docker-compose", "-f", COMPOSE_FILE, "up", "-d", "--build"],
            check=True,
            capture_output=True,
            text=True
        )
        print(up_process.stdout)
        if up_process.stderr:
            print("Errors during docker-compose up:")
            print(up_process.stderr)


        # Wait for the API service to be ready
        api_port = 8000
        max_wait_seconds = 60
        start_time = time.time()
        while not is_service_ready(api_port):
            if time.time() - start_time > max_wait_seconds:
                # Before failing, capture logs for debugging
                logs_process = subprocess.run(
                    ["docker-compose", "-f", COMPOSE_FILE, "logs"],
                    capture_output=True,
                    text=True
                )
                print("API service logs:")
                print(logs_process.stdout)
                print(logs_process.stderr)
                raise TimeoutError(f"Service on port {api_port} did not become available within {max_wait_seconds} seconds.")
            time.sleep(2)
        
        print("Test environment is ready.")
        yield
    
    finally:
        print("\nCapturing container logs...")
        logs_process = subprocess.run(
            ["docker-compose", "-f", COMPOSE_FILE, "logs"],
            capture_output=True,
            text=True
        )
        print("--- API Service Logs ---")
        print(logs_process.stdout)
        if logs_process.stderr:
            print("--- Log Capture Errors ---")
            print(logs_process.stderr)
        print("------------------------")

        print("\nStopping test environment...")
        down_process = subprocess.run(
            ["docker-compose", "-f", COMPOSE_FILE, "down", "-v"],
            check=True,
            capture_output=True,
            text=True
        )
        print("Test environment stopped.")
        print(down_process.stdout)
        if down_process.stderr:
            print("Errors during docker-compose down:")
            print(down_process.stderr)


@pytest.fixture
def test_services(test_environment):
    """
    Provides an initialized and AUTHENTICATED DeepSecureClient for admin tasks.
    It creates a dedicated 'test-runner' agent to perform its actions.
    """
    admin_agent_name = "test-runner-agent"
    client = DeepSecureClient(
        deeptrail_control_url="http://localhost:8000",
        deeptrail_gateway_url="http://localhost:8001"
    )
    agent_client = AgentClient()
    admin_agent_id = None

    # Find admin agent by name by listing all agents (unauthenticated)
    # This is inefficient but necessary without a get_by_name endpoint.
    try:
        all_agents_response = agent_client.list_agents(limit=500)
    except DeepSecureClientError as e:
        # Handle case where the service is not ready yet, though sleep should prevent this
        pytest.fail(f"Failed to connect to the API service to list agents: {e}")

    found_agent = next((agent for agent in all_agents_response.get("agents", []) if agent.get("name") == admin_agent_name), None)

    if found_agent:
        admin_agent_id = found_agent['agent_id']
        print(f"Found existing admin agent: {admin_agent_id}")
    else:
        print("Admin agent not found, creating a new one...")
        # Use the identity_manager from the client instance
        keys = client._identity_manager.generate_ed25519_keypair_raw_b64()
        admin_agent_data = agent_client.create_agent_unauthenticated(
            public_key=keys['public_key'],
            name=admin_agent_name
        )
        admin_agent_id = admin_agent_data['agent_id']
        client._identity_manager.store_private_key_directly(admin_agent_id, keys['private_key'])
        print(f"Created new admin agent: {admin_agent_id}")

    # Authenticate the main client as this admin agent
    try:
        print(f"Authenticating client as admin agent: {admin_agent_id}...")
        client._get_access_token(admin_agent_id)
        print(f"Client authenticated successfully.")
    except DeepSecureError as e:
        pytest.fail(
            f"Failed to authenticate as admin agent {admin_agent_id}: {e}"
        )

    return client 