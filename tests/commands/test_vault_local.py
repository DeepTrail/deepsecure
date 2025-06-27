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
    secret_value = "postgres://user:pass@host:5432/db"
    created_at = "2024-01-01T12:00:00Z"
    
    # --- Setup the mock SDK client ---
    # The current implementation uses get_secret_direct which returns a dict
    mock_secret_data = {
        "name": secret_name,
        "value": secret_value,
        "created_at": created_at
    }
    mock_sdk_client.get_secret_direct.return_value = mock_secret_data
    
    # --- Action ---
    result = runner.invoke(app, [
        "vault",
        "get-secret",
        secret_name
    ])
    
    # --- Verification ---
    assert result.exit_code == 0
    # The command should print the secret value in a table format
    assert secret_value in result.stdout
    assert secret_name in result.stdout
    
    # Verify that the CLI called the SDK correctly
    mock_sdk_client.get_secret_direct.assert_called_once_with(name=secret_name)

def test_vault_get_secret_json_output(mock_sdk_client: MagicMock):
    """
    Tests the `vault get-secret` command with JSON output.
    """
    secret_name = "API_KEY"
    secret_value = "super-secret-key"
    created_at = "2024-01-01T12:00:00Z"

    # --- Setup ---
    mock_secret_data = {
        "name": secret_name,
        "value": secret_value,
        "created_at": created_at
    }
    mock_sdk_client.get_secret_direct.return_value = mock_secret_data
    
    # --- Action ---
    result = runner.invoke(app, [
        "vault",
        "get-secret",
        secret_name,
        "--output",
        "json"
    ])
    
    # --- Verification ---
    assert result.exit_code == 0
    import json
    output_data = json.loads(result.stdout)
    
    assert output_data["name"] == secret_name
    assert output_data["value"] == secret_value
    assert output_data["created_at"] == created_at

def test_vault_get_secret_sdk_error(mock_sdk_client: MagicMock):
    """
    Tests that the CLI handles errors from the SDK gracefully.
    """
    secret_name = "NONEXISTENT_KEY"
    
    # --- Setup ---
    error_message = "Secret not found: NONEXISTENT_KEY"
    mock_sdk_client.get_secret_direct.side_effect = DeepSecureError(error_message)
    
    # --- Action ---
    result = runner.invoke(app, [
        "vault",
        "get-secret",
        secret_name
    ])
    
    # --- Verification ---
    assert result.exit_code == 1
    
    # Check that the error message is displayed
    stdout_lower = result.stdout.lower()
    assert "failed to get secret" in stdout_lower
    assert "secret not found" in stdout_lower

def test_vault_store_secret_success(mock_sdk_client: MagicMock):
    """
    Tests the `vault store` command on a successful SDK call.
    """
    secret_name = "NEW_SECRET"
    secret_value = "new-secret-value"
    
    # --- Setup the mock SDK client ---
    mock_sdk_client.store_secret.return_value = None  # store_secret doesn't return anything
    
    # --- Action ---
    result = runner.invoke(app, [
        "vault",
        "store",
        secret_name,
        "--value",
        secret_value
    ])
    
    # --- Verification ---
    assert result.exit_code == 0
    assert f"Secret '{secret_name}' stored successfully" in result.stdout
    
    # Verify that the CLI called the SDK correctly
    mock_sdk_client.store_secret.assert_called_once_with(name=secret_name, value=secret_value)

def test_vault_store_secret_error(mock_sdk_client: MagicMock):
    """
    Tests that the CLI handles store errors gracefully.
    """
    secret_name = "FAILING_SECRET"
    secret_value = "test-value"
    
    # --- Setup ---
    error_message = "Storage backend unavailable"
    mock_sdk_client.store_secret.side_effect = DeepSecureError(error_message)
    
    # --- Action ---
    result = runner.invoke(app, [
        "vault",
        "store",
        secret_name,
        "--value",
        secret_value
    ])
    
    # --- Verification ---
    assert result.exit_code == 1
    
    # Check that the error message is displayed
    stdout_lower = result.stdout.lower()
    assert "failed to store secret" in stdout_lower
    assert "storage backend unavailable" in stdout_lower 