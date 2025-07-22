# tests/commands/test_agent.py
import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from respx import MockRouter
import httpx

from deepsecure.main import app
from deepsecure.exceptions import DeepSecureError
from deepsecure.client import Agent

runner = CliRunner()

@pytest.fixture
def mock_client_class():
    """Mocks the deepsecure.Client class."""
    with patch('deepsecure.client.Client', autospec=True) as mock_client:
        yield mock_client

def test_agent_create_success(runner: CliRunner):
    """
    Tests the `agent create` command on a successful SDK call.
    """
    agent_name = "test-agent"
    mock_agent_id = "agent-12345678"
    mock_public_key = "mock-public-key"
    
    # Mock Agent object
    mock_agent = MagicMock()
    mock_agent.id = mock_agent_id
    mock_agent.name = agent_name
    mock_agent.public_key = mock_public_key
    
    with patch('deepsecure.commands.agent.deepsecure.Client') as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_agents_resource = MagicMock()
        mock_agents_resource.create.return_value = mock_agent
        mock_client.agents = mock_agents_resource
        
        # Mock the identity manager since the command accesses it
        mock_identity_manager = MagicMock()
        mock_identity_manager.get_private_key.return_value = "mock-private-key"
        mock_client._identity_manager = mock_identity_manager
        
        result = runner.invoke(app, ["agent", "create", "--name", agent_name])
    
    assert result.exit_code == 0
    assert f"Agent '{agent_name}' created successfully." in result.stdout
    assert f"Agent ID: {mock_agent_id}" in result.stdout
    
    # Verify the SDK was called correctly  
    mock_agents_resource.create.assert_called_once_with(name=agent_name, description=None)

def test_agent_create_fails_on_api_error(runner: CliRunner):
    """
    Tests the `agent create` command when the SDK raises an API error.
    """
    agent_name = "test-agent"
    error_message = "Agent creation failed"
    
    with patch('deepsecure.commands.agent.deepsecure.Client') as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_agents_resource = MagicMock()
        mock_agents_resource.create.side_effect = DeepSecureError(error_message)
        mock_client.agents = mock_agents_resource
        
        result = runner.invoke(app, ["agent", "create", "--name", agent_name])
    
    assert result.exit_code == 1
    assert error_message in result.stdout


def test_agent_list_success(runner: CliRunner):
    """
    Tests the `agent list` command on a successful SDK call.
    """
    mock_agents_data = {
        "agents": [
            {"agent_id": "agent-001", "name": "Agent One", "status": "active", "created_at": "2023-01-01T00:00:00Z"},
            {"agent_id": "agent-002", "name": "Agent Two", "status": "active", "created_at": "2023-01-02T00:00:00Z"},
        ]
    }
    
    with patch('deepsecure.commands.agent.deepsecure.Client') as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_agents_resource = MagicMock()
        mock_agents_resource.list_agents.return_value = mock_agents_data
        mock_client.agents = mock_agents_resource
        
        result = runner.invoke(app, ["agent", "list"])
    
    assert result.exit_code == 0
    assert "Agent One" in result.stdout
    assert "Agent Two" in result.stdout


def test_agent_create_sdk_error(runner: CliRunner):
    """
    Tests the `agent create` command when the SDK raises a different error.
    """
    agent_name = "test-agent"
    
    with patch('deepsecure.commands.agent.deepsecure.Client') as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_agents_resource = MagicMock()
        mock_agents_resource.create.side_effect = Exception("Unexpected error")
        mock_client.agents = mock_agents_resource
        
        result = runner.invoke(app, ["agent", "create", "--name", agent_name])
    
    assert result.exit_code == 1 