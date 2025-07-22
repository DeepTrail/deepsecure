# tests/_core/test_client.py
import pytest
from unittest.mock import MagicMock, patch
import uuid
import requests
import respx
import httpx

from deepsecure._core.client import VaultClient as CoreVaultClient
from deepsecure._core.agent_client import AgentClient as CoreAgentClient
from deepsecure._core.schemas import CredentialIssueRequest, CredentialResponse, AgentDetailsResponse
from deepsecure.exceptions import DeepSecureError, DeepSecureClientError, ApiError
from deepsecure._core.base_client import BaseClient
from deepsecure.client import Client

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
def mock_httpx_client():
    with patch('httpx.Client', autospec=True) as mock_client:
        yield mock_client

@pytest.fixture
def core_vault_client(monkeypatch):
    """Fixture to get an instance of the CoreVaultClient with a mocked token."""
    # Set the backend URL via monkeypatching the environment variable
    monkeypatch.setenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://test-deeptrail-control.dsv.local")
    client = CoreVaultClient()
    # Directly set the token to avoid authentication during tests
    client._token = MOCK_TOKEN
    yield client

@pytest.fixture
def core_agent_client(monkeypatch):
    """Fixture to get an instance of the CoreAgentClient with a mocked token."""
    # Set the backend URL via monkeypatching the environment variable
    monkeypatch.setenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://test-deeptrail-control.dsv.local")
    client = CoreAgentClient()
    # Directly set the token to avoid authentication during tests
    client._token = MOCK_TOKEN
    yield client

def test_authenticated_request_happy_path(mock_httpx_client):
    """
    Tests that _authenticated_request correctly performs the challenge-response flow
    when called for the first time.
    """
    api_url = "http://test.server"
    client = BaseClient(api_url=api_url)
    
    agent_id = "agent-test-123"
    nonce = "a_unique_nonce"
    signature = "a_valid_signature"
    access_token = "a.jwt.token"

    # Mock the identity manager
    client.identity_manager = MagicMock()
    client.identity_manager.get_private_key.return_value = "fake_private_key_b64"
    client.identity_manager.sign.return_value = signature

    # Mock the sequence of httpx responses
    mock_challenge_response = MagicMock()
    mock_challenge_response.json.return_value = {"nonce": nonce}
    
    mock_token_response = MagicMock()
    mock_token_response.json.return_value = {"access_token": access_token, "token_type": "bearer"}
    
    mock_authed_response = MagicMock()
    mock_authed_response.json.return_value = {"data": "secret_info"}

    # The client's internal httpx instance will have this side_effect
    client._client.request.side_effect = [
        mock_challenge_response,
        mock_token_response,
        mock_authed_response
    ]
    
    # Action: Make the authenticated request
    response = client._authenticated_request("GET", "/some/secret/path", agent_id=agent_id)

    # Verification
    assert response.json()["data"] == "secret_info"
    
    # Check that the identity manager was used correctly
    client.identity_manager.get_private_key.assert_called_once_with(agent_id)
    client.identity_manager.sign.assert_called_once_with("fake_private_key_b64", nonce)
    
    # Verify the calls to the mock httpx client
    assert client._client.request.call_count == 3
    
    # Call 1: Challenge
    challenge_call = client._client.request.call_args_list[0]
    assert challenge_call.args == ('POST', '/auth/challenge')
    assert challenge_call.kwargs['json'] == {'agent_id': agent_id}
    
    # Call 2: Token
    token_call = client._client.request.call_args_list[1]
    assert token_call.args == ('POST', '/auth/token')
    assert token_call.kwargs['json'] == {'agent_id': agent_id, 'nonce': nonce, 'signature': signature}
    
    # Call 3: The actual authenticated request
    authed_call = client._client.request.call_args_list[2]
    assert authed_call.args == ('GET', '/some/secret/path')
    assert authed_call.kwargs['headers']['Authorization'] == f"Bearer {access_token}"

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

    # Mock the identity manager to return a valid private key
    with patch('deepsecure._core.client.identity_manager.get_private_key') as mock_get_private_key:
        mock_get_private_key.return_value = MOCK_PRIVATE_KEY_B64

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
        with patch('deepsecure._core.client.identity_manager.get_private_key', return_value=MOCK_PRIVATE_KEY_B64):
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

@respx.mock
def test_client_agent_creation(identity_manager_mock):
    mock_agent_id = "agent-1234"
    mock_public_key = "some_public_key"
    mock_token = "mock-jwt-token"
    gateway_url = "http://localhost:8002"
    control_plane_url = "http://localhost:8001"

    # Mock the gateway proxy endpoint for agent creation
    respx_mock.post(f"{gateway_url}/proxy/api/v1/agents/").mock(
        return_value=httpx.Response(
            201,
            json={"id": mock_agent_id, "current_public_key": mock_public_key},
        )
    )
    # Mock the challenge-response flow via the gateway
    respx_mock.post(f"{gateway_url}/proxy/api/v1/auth/challenge").mock(
        return_value=httpx.Response(200, json={"nonce": "test-nonce"})
    )
    respx_mock.post(f"{gateway_url}/proxy/api/v1/auth/token").mock(
        return_value=httpx.Response(200, json={"access_token": mock_token, "token_type": "bearer"})
    )

    client = Client()
    agent = client.agents.create(public_key=mock_public_key, name="test-agent")

    assert agent.id == mock_agent_id
    assert agent.public_key == mock_public_key

    # Check that the request to the gateway was made correctly
    create_agent_call = respx_mock.calls[0]
    assert create_agent_call.request.url == f"{gateway_url}/proxy/api/v1/agents/"
    assert create_agent_call.request.headers["x-target-base-url"] == control_plane_url


@respx.mock
def test_client_authentication_flow(identity_manager_mock):
    mock_agent_id = "agent-for-auth"
    mock_token = "authenticated-jwt-token"
    gateway_url = "http://localhost:8002"
    control_plane_url = "http://localhost:8001"

    # Setup mocks for identity manager
    identity_manager_mock.get_or_create_agent_identity.return_value = (mock_agent_id, "pub_key")
    identity_manager_mock.get_private_key.return_value = "priv_key_b64"
    identity_manager_mock.sign.return_value = "signed-nonce"

    # Mock gateway endpoints for auth flow
    respx.post(f"{gateway_url}/proxy/api/v1/auth/challenge").mock(
        return_value=httpx.Response(200, json={"nonce": "a-real-nonce"})
    )
    respx.post(f"{gateway_url}/proxy/api/v1/auth/token").mock(
        return_value=httpx.Response(200, json={"access_token": mock_token, "token_type": "bearer"})
    )

    # This call should trigger the authentication flow
    client = Client(agent_id=mock_agent_id)
    client._authenticate()

    assert client._token == mock_token
    
    # Verify the challenge request
    challenge_call = respx.calls[0]
    assert challenge_call.request.url == f"{gateway_url}/proxy/api/v1/auth/challenge"
    assert challenge_call.request.headers["x-target-base-url"] == control_plane_url

    # Verify the token request
    token_call = respx.calls[1]
    assert token_call.request.url == f"{gateway_url}/proxy/api/v1/auth/token"
    assert token_call.request.headers["x-target-base-url"] == control_plane_url