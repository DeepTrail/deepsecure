# tests/commands/test_agent.py
import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from deepsecure.main import app
from deepsecure.client import Agent
from deepsecure.exceptions import DeepSecureError

runner = CliRunner()

@pytest.fixture
def mock_sdk_client():
    """Mocks the deepsecure.Client class used by the agent commands."""
    with patch('deepsecure.commands.agent.deepsecure.Client', autospec=True) as mock_client_class:
        mock_instance = mock_client_class.return_value
        yield mock_instance

def test_agent_create_success(mock_sdk_client: MagicMock):
    """
    Tests the `agent create` command on a successful SDK call.
    """
    agent_name = "newly-created-agent"
    agent_id = "agent-create-success-123"
    
    # --- Setup the mock SDK client ---
    # The `agent` method is called by the command
    mock_agent_handle = Agent(id=agent_id, name=agent_name, client=mock_sdk_client)
    mock_sdk_client.agent.return_value = mock_agent_handle
    
    # --- Action ---
    result = runner.invoke(app, [
        "agent",
        "create",
        "--name",
        agent_name
    ])
    
    # --- Verification ---
    assert result.exit_code == 0
    assert f"Agent '{agent_name}' created successfully" in result.stdout
    assert agent_id in result.stdout
    
    # Verify that the CLI called the SDK correctly
    mock_sdk_client.agent.assert_called_once_with(agent_name, auto_create=True)

def test_agent_list_success(mock_sdk_client: MagicMock):
    """
    Tests the `agent list` command.
    """
    # --- Setup ---
    mock_sdk_client.list_agents.return_value = [
        {"agent_id": "agent-1", "name": "Agent One", "status": "active", "created_at": "2025-01-01T00:00:00"},
        {"agent_id": "agent-2", "name": "Agent Two", "status": "active", "created_at": "2025-01-01T01:00:00"},
    ]

    # --- Action ---
    result = runner.invoke(app, ["agent", "list"])
    
    # --- Verification ---
    assert result.exit_code == 0
    assert "Agent One" in result.stdout
    assert "Agent Two" in result.stdout
    assert "agent-1" in result.stdout
    
    mock_sdk_client.list_agents.assert_called_once()

def test_agent_create_sdk_error(mock_sdk_client: MagicMock):
    """
    Tests that `agent create` handles an error from the SDK.
    """
    agent_name = "failing-agent"
    error_message = "Backend registration failed: 500 Server Error"
    mock_sdk_client.agent.side_effect = DeepSecureError(error_message)
    
    # --- Action ---
    result = runner.invoke(app, ["agent", "create", "--name", agent_name])
    
    # --- Verification ---
    assert result.exit_code == 1
    assert "Failed to create agent" in result.stdout
    assert error_message in result.stdout 