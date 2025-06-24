# tests/_core/test_client.py
import pytest
from unittest.mock import MagicMock, patch
import uuid
import requests

from deepsecure._core.client import VaultClient as CoreVaultClient
from deepsecure._core.agent_client import AgentClient as CoreAgentClient
from deepsecure._core.schemas import CredentialIssueRequest, CredentialResponse, AgentDetailsResponse
from deepsecure.exceptions import DeepSecureError, DeepSecureClientError, ApiError

# A sample JWT token for testing
MOCK_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-N7zB0_T-4c"

# Mock key data for consistent testing
MOCK_PRIVATE_KEY_B64 = "cHJpdmF0ZV9rZXlfYnl0ZXNfZm9yX3Rlc3RpbmdfMzI="

@pytest.fixture
def mock_base_request():
    """Fixture to mock the BaseClient._request method."""
    with patch('deepsecure._core.base_client.BaseClient._request') as mock_request:
        yield mock_request

@pytest.fixture
def core_vault_client(monkeypatch):
    """Fixture to get an instance of the CoreVaultClient with a mocked token."""
    # Set the backend URL via monkeypatching the environment variable
    monkeypatch.setenv("DEEPSECURE_CREDSERVICE_URL", "http://test-credservice.dsv.local")
    with patch('deepsecure.auth.get_token', return_value=MOCK_TOKEN):
        client = CoreVaultClient()
        yield client

@pytest.fixture
def core_agent_client(monkeypatch):
    """Fixture to get an instance of the CoreAgentClient with a mocked token."""
    # Set the backend URL via monkeypatching the environment variable
    monkeypatch.setenv("DEEPSECURE_CREDSERVICE_URL", "http://test-credservice.dsv.local")
    with patch('deepsecure.auth.get_token', return_value=MOCK_TOKEN):
        client = CoreAgentClient()
        yield client

# --- CoreVaultClient Tests ---

def test_vault_client_issue_credential_success(core_vault_client, mock_base_request):
    """Test successful credential issuance from the CoreVaultClient."""
    mock_base_request.return_value = {
        "credential_id": "cred-123",
        "agent_id": "agent-123",
        "scope": "secret:my_secret",
        "expires_at": "2024-01-01T00:05:00Z",
        "issued_at": "2024-01-01T00:00:00Z",
        "status": "issued"
    }

    # Mock the identity manager to return a valid identity
    with patch('deepsecure._core.client.identity_manager.load_identity') as mock_load_identity:
        mock_load_identity.return_value = {
            "id": "agent-123",
            "public_key": "mock_public_key",
            "private_key": MOCK_PRIVATE_KEY_B64
        }

        # Note: The `issue` method constructs the request internally now
        cred_response = core_vault_client.issue(
            scope="secret:my_secret",
            agent_id="agent-123",
            ttl=300
        )

    assert isinstance(cred_response, CredentialResponse)
    assert cred_response.credential_id == "cred-123"
    mock_base_request.assert_called_once()
    call_args = mock_base_request.call_args
    assert call_args.kwargs['data']['scope'] == "secret:my_secret"

def test_vault_client_http_error(core_vault_client, mock_base_request):
    """Test that an HTTP error is correctly raised."""
    mock_base_request.side_effect = ApiError("API Error 401: Invalid token", status_code=401)

    with pytest.raises(ApiError, match="API Error 401: Invalid token"):
        # We still need to mock the identity to get past the first check
        with patch('deepsecure._core.client.identity_manager.load_identity', return_value={"private_key": MOCK_PRIVATE_KEY_B64}):
            core_vault_client.issue(scope="secret:my_secret", agent_id="agent-123")

# --- CoreAgentClient Tests ---

def test_agent_client_get_agent_success(core_agent_client, mock_base_request):
    """Test successfully fetching agent details."""
    agent_id = f"agent-{uuid.uuid4()}"
    mock_base_request.return_value = {
        "agent_id": agent_id,
        "publicKey": "test_public_key",
        "name": "test-agent",
        "created_at": "2024-01-01T00:00:00Z",
        "status": "active"
    }

    agent_details = core_agent_client.describe_agent(agent_id=agent_id)

    assert agent_details is not None
    assert isinstance(agent_details, dict)
    assert agent_details['agent_id'] == agent_id
    assert agent_details['publicKey'] == "test_public_key"

def test_agent_client_register_agent_client_error(core_agent_client):
    """Test that a client-side error is raised if public key is missing."""
    # This test now expects an ApiError because the validation is on the server
    with pytest.raises(ApiError):
        core_agent_client.register_agent(public_key=None, name="test-agent", description="test-desc") 