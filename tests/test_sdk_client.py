# tests/test_client.py
import pytest
from unittest.mock import patch, MagicMock

from deepsecure.client import Client, Agent
from deepsecure.exceptions import IdentityManagerError
from deepsecure.types import Secret
from deepsecure._core.client import VaultClient as CoreVaultClient
from deepsecure._core.agent_client import AgentClient as CoreAgentClient
from deepsecure._core.identity_manager import IdentityManager as CoreIdentityManager

@pytest.fixture
def mock_core_clients():
    """Mocks all the core clients and managers used by the public Client."""
    with patch('deepsecure.client.CoreVaultClient', autospec=True) as mock_vault_class, \
         patch('deepsecure.client.CoreAgentClient', autospec=True) as mock_agent_class, \
         patch('deepsecure.client.identity_manager', autospec=True) as mock_id_manager:
        
        # Configure the mock classes to return a mock *instance* when called
        mock_vault_class.return_value = MagicMock(spec=CoreVaultClient)
        mock_agent_class.return_value = MagicMock(spec=CoreAgentClient)
        # identity_manager is already an instance, so we can use it directly
        
        yield {
            "vault": mock_vault_class,
            "agent": mock_agent_class,
            "identity": mock_id_manager,
        }

@pytest.fixture
def public_client(mock_core_clients: dict) -> Client:
    """Provides a Client instance with all its dependencies mocked."""
    # We can pass dummy values here because the mocks will intercept everything.
    return Client(base_url="http://mock-url", api_token="mock-token")

def test_client_agent_auto_create_flow(public_client: Client, mock_core_clients: dict):
    """
    Tests the `agent()` method with `auto_create=True`.
    Verifies the correct sequence of calls to the core components when an agent
    does not exist and needs to be created.
    """
    mock_id_manager = mock_core_clients["identity"]
    mock_agent_client = public_client._agent_client # The instance on the client
    
    agent_name = "new-test-agent"
    
    # --- Setup Mocks ---
    # 1. Simulate that the identity does not exist initially
    mock_id_manager.find_identity_by_name.return_value = None
    
    # 2. Simulate the creation of a new local identity
    new_agent_id = "agent-new-uuid-456"
    new_public_key = "new_public_key_b64"
    mock_id_manager.create_identity.return_value = {
        "id": new_agent_id,
        "public_key": new_public_key,
    }
    
    # 3. Simulate a successful backend registration
    mock_agent_client.register_agent.return_value = {
        "agent_id": new_agent_id # Backend confirms the same ID
    }
    
    # --- Action ---
    agent_handle = public_client.agent(name=agent_name, auto_create=True)
    
    # --- Verification ---
    # Verify the sequence of calls
    mock_id_manager.find_identity_by_name.assert_called_once_with(agent_name)
    mock_id_manager.create_identity.assert_called_once_with(name=agent_name)
    
    mock_agent_client.register_agent.assert_called_once_with(
        public_key=new_public_key,
        name=agent_name,
        description="Automatically created by DeepSecure SDK.",
        agent_id=new_agent_id
    )
    
    # Verify the returned handle
    assert isinstance(agent_handle, Agent)
    assert agent_handle.id == new_agent_id
    assert agent_handle.name == agent_name

def test_client_get_secret_flow(public_client: Client, mock_core_clients: dict):
    """
    Tests the `get_secret()` method flow.
    Verifies that it loads an identity and then issues a credential.
    """
    mock_id_manager = mock_core_clients["identity"]
    mock_vault_client = public_client._vault_client
    
    agent_name = "secret-fetcher"
    agent_id = "agent-secret-fetcher-123"
    secret_name = "DATABASE_URL"
    
    # --- Setup Mocks ---
    # 1. Simulate finding an existing agent
    mock_id_manager.find_identity_by_name.return_value = {"id": agent_id}
    
    # 2. Simulate a successful credential issuance from the vault client
    # We need a mock response object that has the necessary attributes
    mock_cred_response = MagicMock()
    mock_cred_response.secret_value = "super-secret-db-connection-string"
    from datetime import datetime
    mock_cred_response.expires_at = datetime.now()
    
    mock_vault_client.issue.return_value = mock_cred_response
    
    # --- Action ---
    secret = public_client.get_secret(name=secret_name, agent_name=agent_name)
    
    # --- Verification ---
    mock_id_manager.find_identity_by_name.assert_called_once_with(agent_name)
    
    # Verify that the vault client was called to issue a credential with the correct scope
    mock_vault_client.issue.assert_called_once()
    # We can inspect the args it was called with
    call_args, call_kwargs = mock_vault_client.issue.call_args
    assert call_kwargs["scope"] == f"secret:{secret_name}"
    assert call_kwargs["agent_id"] == agent_id
    
    # Verify the returned Secret object
    assert secret.value == "super-secret-db-connection-string"

def test_client_with_agent_context(public_client: Client, mock_core_clients: dict):
    """
    Tests that `with_agent()` creates a new client with the correct agent context,
    and that `get_secret` then uses this context automatically.
    """
    mock_id_manager = mock_core_clients["identity"]
    
    agent_name = "context-agent"
    agent_id = "agent-context-uuid-789"
    
    # --- Setup ---
    # 1. Simulate finding the agent to create the handle
    mock_id_manager.find_identity_by_name.return_value = {"id": agent_id, "name": agent_name}
    
    # --- Action ---
    # Create the agent-scoped client
    agent_scoped_client = public_client.with_agent(agent_name)
    
    # --- Verification ---
    # 1. Verify the new client has the context set
    assert agent_scoped_client._agent_context is not None
    assert agent_scoped_client._agent_context.id == agent_id
    
    # 2. Now, use this new client to get a secret and verify it uses the context
    mock_vault_client = agent_scoped_client._vault_client
    
    # Create a more complete mock that has the attributes the code expects
    mock_cred_response = MagicMock()
    mock_cred_response.credential_id = "cred-from-context-test"
    mock_cred_response.secret_value = "a-secret-from-the-context"
    from datetime import datetime
    mock_cred_response.expires_at = datetime.now()
    
    mock_vault_client.issue.return_value = mock_cred_response
    
    agent_scoped_client.get_secret("some-secret")
    
    # 3. Verify that `get_secret` used the agent_id from the context
    mock_vault_client.issue.assert_called_once()
    call_args, call_kwargs = mock_vault_client.issue.call_args
    assert call_kwargs["agent_id"] == agent_id
    
    # 4. Verify the original client does NOT have the context
    assert public_client._agent_context is None 