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
    
    # Mock Agent object
    mock_agent = MagicMock()
    mock_agent.id = mock_agent_id
    mock_agent.name = agent_name
    
    with patch('deepsecure.Client') as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.agent.return_value = mock_agent
        
        result = runner.invoke(app, ["agent", "create", "--name", agent_name])
    
    assert result.exit_code == 0
    assert f"Agent '{agent_name}' created successfully." in result.stdout
    assert f"Agent ID: {mock_agent_id}" in result.stdout
    
    # Verify the SDK was called correctly
    mock_client.agent.assert_called_once_with(agent_name, auto_create=True)

def test_agent_create_fails_on_api_error(runner: CliRunner):
    """
    Tests that the `agent create` command handles DeepSecureError gracefully.
    """
    agent_name = "failing-agent"
    error_message = "Backend registration failed"
    
    with patch('deepsecure.Client') as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.agent.side_effect = DeepSecureError(error_message)
        
        result = runner.invoke(app, ["agent", "create", "--name", agent_name])
    
    assert result.exit_code == 1
    assert "Failed to create agent" in result.stdout
    assert error_message in result.stdout

def test_agent_list_success(runner: CliRunner):
    """
    Tests the `agent list` command on a successful SDK call.
    """
    mock_agents = [
        {"agent_id": "agent-1", "name": "Agent One", "status": "active", "created_at": "2025-01-01T00:00:00"},
        {"agent_id": "agent-2", "name": "Agent Two", "status": "active", "created_at": "2025-01-01T01:00:00"},
    ]
    
    with patch('deepsecure.Client') as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.list_agents.return_value = mock_agents
        
        result = runner.invoke(app, ["agent", "list"])
    
    assert result.exit_code == 0
    assert "Agent One" in result.stdout
    assert "Agent Two" in result.stdout
    assert "agent-1" in result.stdout
    assert "agent-2" in result.stdout
    
    # Verify the SDK was called correctly
    mock_client.list_agents.assert_called_once()

def test_agent_create_sdk_error(runner: CliRunner):
    """
    Tests that `agent create` handles a DeepSecureError from the SDK.
    """
    agent_name = "failing-agent"
    error_message = "Backend registration failed: 500 Server Error"
    
    with patch('deepsecure.Client') as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.agent.side_effect = DeepSecureError(error_message)
        
        result = runner.invoke(app, ["agent", "create", "--name", agent_name])
    
    assert result.exit_code == 1
    assert "Failed to create agent" in result.stdout
    assert error_message in result.stdout 