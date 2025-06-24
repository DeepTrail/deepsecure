# tests/commands/test_vault_local.py
import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from datetime import datetime

from deepsecure.main import app
from deepsecure.client import Client
from deepsecure.types import Secret
from deepsecure.exceptions import DeepSecureError

runner = CliRunner()

@pytest.fixture
def mock_sdk_client():
    """Mocks the deepsecure.Client class used by the CLI commands."""
    with patch('deepsecure.commands.vault.deepsecure.Client', autospec=True) as mock_client_class:
        mock_instance = mock_client_class.return_value
        yield mock_instance

def test_vault_get_secret_success(mock_sdk_client: MagicMock):
    """
    Tests the `vault get-secret` command on a successful SDK call.
    """
    secret_name = "DATABASE_URL"
    agent_name = "db-agent"
    secret_value = "postgres://user:pass@host:5432/db"
    
    # --- Setup the mock SDK client ---
    mock_secret = Secret(
        name=secret_name,
        _value=secret_value,
        expires_at=datetime.now()
    )
    mock_sdk_client.get_secret.return_value = mock_secret
    
    # --- Action ---
    result = runner.invoke(app, [
        "vault",
        "get-secret",
        secret_name,
        "--agent-name",
        agent_name
    ])
    
    # --- Verification ---
    assert result.exit_code == 0
    # The command should print the secret value directly to stdout
    assert secret_value in result.stdout
    
    # Verify that the CLI called the SDK correctly
    mock_sdk_client.get_secret.assert_called_once_with(name=secret_name, agent_name=agent_name)

def test_vault_get_secret_json_output(mock_sdk_client: MagicMock):
    """
    Tests the `vault get-secret` command with JSON output.
    """
    secret_name = "API_KEY"
    agent_name = "api-agent"
    secret_value = "super-secret-key"
    expires_at = datetime.now()

    # --- Setup ---
    mock_secret = Secret(name=secret_name, _value=secret_value, expires_at=expires_at)
    mock_sdk_client.get_secret.return_value = mock_secret
    
    # --- Action ---
    result = runner.invoke(app, [
        "vault",
        "get-secret",
        secret_name,
        "--agent-name",
        agent_name,
        "--output",
        "json"
    ])
    
    # --- Verification ---
    assert result.exit_code == 0
    import json
    output_data = json.loads(result.stdout)
    
    assert output_data["name"] == secret_name
    assert output_data["value"] == secret_value
    assert output_data["expires_at"] == expires_at.isoformat()

def test_vault_get_secret_sdk_error(mock_sdk_client: MagicMock):
    """
    Tests that the CLI handles errors from the SDK gracefully.
    """
    secret_name = "FORBIDDEN_KEY"
    agent_name = "unauthorized-agent"
    
    # --- Setup ---
    error_message = "Access denied: agent is not authorized for this secret."
    mock_sdk_client.get_secret.side_effect = DeepSecureError(error_message)
    
    # --- Action ---
    result = runner.invoke(app, [
        "vault",
        "get-secret",
        secret_name,
        "--agent-name",
        agent_name
    ])
    
    # --- Verification ---
    assert result.exit_code == 1
    
    # Sanitize the output for a robust check
    stdout_lower = result.stdout.lower()
    
    assert "failed to get secret" in stdout_lower
    assert "access denied" in stdout_lower
    assert "not authorized" in stdout_lower 