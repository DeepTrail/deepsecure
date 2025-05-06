import pytest
import json
import time
import os
from pathlib import Path
from unittest.mock import patch, MagicMock # Import patch and MagicMock
from typer.testing import CliRunner
import uuid
from datetime import datetime, timedelta
import requests # Import requests for exception

from deepsecure.main import app # Import the main Typer app
from deepsecure.core import vault_client, base_client # Import base_client for mocking
from deepsecure import exceptions # Import exceptions

runner = CliRunner()

# Define constants for testing backend interaction
MOCK_BACKEND_URL = "http://mock-backend.test" # Base URL without /api/v1
MOCK_API_TOKEN = "mock_secret_token_for_testing"

# Pytest fixture to manage the local .deepsecure state for tests
@pytest.fixture(scope="function")
def local_state(tmp_path, monkeypatch):
    """Fixture to create temporary local state directory and patch VaultClient paths."""
    temp_deepsecure_dir = tmp_path / ".deepsecure"
    temp_identities_dir = temp_deepsecure_dir / "identities"
    temp_identities_dir.mkdir(parents=True, exist_ok=True)
    temp_revocation_file = temp_deepsecure_dir / "revoked_creds.json"
    temp_device_id_file = temp_deepsecure_dir / "device_id"

    monkeypatch.setattr(vault_client, "DEEPSECURE_DIR", temp_deepsecure_dir)
    monkeypatch.setattr(vault_client, "IDENTITY_STORE_PATH", temp_identities_dir)
    monkeypatch.setattr(vault_client, "REVOCATION_LIST_FILE", temp_revocation_file)
    monkeypatch.setattr(vault_client, "DEVICE_ID_FILE", temp_device_id_file)

    # Re-initialize the singleton client to use the patched paths
    # Create a new instance to pick up patched paths AND clear any prior state
    new_client = vault_client.VaultClient()
    monkeypatch.setattr(vault_client, "client", new_client)

    print(f"\nUsing temp state dir: {temp_deepsecure_dir}")
    yield {
        "deepsecure_dir": temp_deepsecure_dir,
        "identities_dir": temp_identities_dir,
        "revocation_file": temp_revocation_file,
    }
    print(f"\nCleaning up temp state dir: {temp_deepsecure_dir}")

# Fixture to configure mock backend environment variables
@pytest.fixture(scope="function")
def mock_backend_env(monkeypatch):
    monkeypatch.setenv("DEEPSECURE_CREDSERVICE_URL", MOCK_BACKEND_URL)
    monkeypatch.setenv("DEEPSECURE_CREDSERVICE_API_TOKEN", MOCK_API_TOKEN)
    # Clear cached properties in the singleton client instance before the test
    # relies on the singleton being accessible via vault_client.client
    if hasattr(vault_client.client, '_backend_url'):
        vault_client.client._backend_url = None
    if hasattr(vault_client.client, '_backend_api_token'):
        vault_client.client._backend_api_token = None
    yield
    monkeypatch.delenv("DEEPSECURE_CREDSERVICE_URL", raising=False)
    monkeypatch.delenv("DEEPSECURE_CREDSERVICE_API_TOKEN", raising=False)


# --- Test Functions ---

def test_vault_issue_local(local_state):
    """Test `deepsecure vault issue --local` command."""
    print("\n--- Testing vault issue --local ---")
    result = runner.invoke(app, [
        "vault",
        "issue",
        "--scope", "test:local-issue",
        "--ttl", "1m",
        "--local",
        "--output", "json" # Use JSON for easier parsing in tests
    ])
    
    print("CLI Output:", result.stdout)
    assert result.exit_code == 0
    
    try:
        credential = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Failed to parse JSON output: {result.stdout}")

    assert "id" in credential
    assert "agent_id" in credential
    assert credential["scope"] == "test:local-issue"
    assert "ephemeral_public_key" in credential
    assert "ephemeral_private_key" in credential # Included for immediate use
    assert "signature" in credential
    assert "expires_at" in credential
    
    # Check if identity file was created
    agent_id = credential["agent_id"]
    identity_file = local_state["identities_dir"] / f"{agent_id}.json"
    assert identity_file.exists(), f"Identity file not found at {identity_file}"
    
    # Basic check on identity file content
    with open(identity_file, 'r') as f:
        identity_data = json.load(f)
    assert identity_data.get("id") == agent_id
    assert "private_key" in identity_data
    assert "public_key" in identity_data
    
    print("test_vault_issue_local PASSED")


@patch('deepsecure.core.base_client.BaseClient._request')
def test_vault_issue_backend(mock_request, local_state, mock_backend_env):
    """Test `deepsecure vault issue` (backend interaction)."""
    print("\n--- Testing vault issue (backend) ---")
    
    # Define the mock response from the backend
    mock_credential_id = f"cred-{uuid.uuid4()}"
    mock_agent_id = f"agent-{uuid.uuid4()}" # Get agent ID created locally by issue command
    mock_expiry = datetime.now() + timedelta(minutes=5)
    mock_response = {
        "credential_id": mock_credential_id,
        "agent_id": mock_agent_id, # Backend confirms agent_id
        "scope": "test:backend-issue",
        "ephemeral_public_key": "mock_eph_pub_key_b64", # Backend returns key sent
        "expires_at": mock_expiry.isoformat() # Backend calculates expiry
    }
    mock_request.return_value = mock_response
    
    # --- Run CLI command (without --local) ---
    result = runner.invoke(app, [
        "vault",
        "issue",
        "--scope", "test:backend-issue",
        "--ttl", "5m",
        # "--agent-id", mock_agent_id, # Let the command create/get one
        "--output", "json"
    ])
    
    print("CLI Output:", result.stdout)
    assert result.exit_code == 0
    
    # --- Assertions ---
    # 1. Check CLI Output (includes ephemeral private key)
    try:
        output_credential = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Failed to parse JSON output: {result.stdout}")
    
    assert output_credential["credential_id"] == mock_credential_id
    assert output_credential["scope"] == "test:backend-issue"
    assert output_credential["expires_at"] is not None # Check it's populated
    assert "ephemeral_private_key" in output_credential # Must be added back by client
    
    # 2. Check that the mock _request was called correctly
    assert mock_request.call_count == 1
    call_args, call_kwargs = mock_request.call_args
    
    assert call_args[0] == "POST" # method
    assert call_args[1] == "/api/v1/vault/credentials" # path
    assert call_kwargs.get("is_backend_request") is True
    
    # Check payload sent to backend
    sent_data = call_kwargs.get("data")
    assert sent_data is not None
    assert sent_data["scope"] == "test:backend-issue"
    assert sent_data["ttl"] == 300 # 5 minutes in seconds
    assert "agent_id" in sent_data
    assert "ephemeral_public_key" in sent_data
    assert "signature" in sent_data
    
    print("test_vault_issue_backend PASSED")


# TODO: Add test_vault_issue_backend_failure (mock raises ApiError, check fallback/error)

def test_vault_revoke_local(local_state):
    """Test `deepsecure vault revoke --local` command."""
    print("\n--- Testing vault revoke --local ---")
    # 1. Issue a credential first
    issue_result = runner.invoke(app, [
        "vault", "issue", "--scope", "test:local-revoke", "--ttl", "5m", "--local", "--output", "json"
    ])
    assert issue_result.exit_code == 0
    credential = json.loads(issue_result.stdout)
    cred_id = credential["id"]
    agent_id = credential["agent_id"] # Needed for verification later

    # Ensure revocation file doesn't exist or is empty initially
    revocation_file = local_state["revocation_file"]
    assert not revocation_file.exists() or revocation_file.read_text() == "[]"

    # 2. Revoke the credential locally
    revoke_result = runner.invoke(app, [
        "vault", 
        "revoke", 
        "--id", cred_id, 
        "--local"
    ])
    
    print("Revoke CLI Output:", revoke_result.stdout)
    assert revoke_result.exit_code == 0
    # Don't check stdout content as it has ANSI color codes that interfere with text matching
    # assert cred_id in revoke_result.stdout 
    # assert "to local revocation list" in revoke_result.stdout

    # 3. Verify revocation file content - this is the important check
    assert revocation_file.exists()
    with open(revocation_file, 'r') as f:
        revoked_ids = json.load(f)
    assert isinstance(revoked_ids, list)
    assert cred_id in revoked_ids, f"Credential ID {cred_id} not found in revocation list"

    # 4. Verify using the client method that the credential is now invalid
    # Remove private key before verification
    credential.pop('ephemeral_private_key', None) 
    is_valid = vault_client.client.verify_local_credential(credential)
    assert not is_valid, "Credential should be invalid after local revocation"
    
    # 5. Test revoking an already revoked ID
    revoke_again_result = runner.invoke(app, [
         "vault", "revoke", "--id", cred_id, "--local"
    ])
    assert revoke_again_result.exit_code == 0 # Should still succeed, but indicate already revoked
    # Note: Checking stderr/info logs for the 'already revoked' message is tricky in tests
    # Rely on the exit code and the list still containing the ID.

    print("test_vault_revoke_local PASSED")


# TODO: Add test_vault_revoke_backend (mock _request)
# TODO: Add test_vault_revoke_backend_not_found (mock raises 404 ApiError)

def test_vault_rotate_local(local_state):
    """Test `deepsecure vault rotate --local` command."""
    # Rename test from placeholder
    print("\n--- Testing vault rotate --local ---")
    # 1. Ensure an identity exists (issue one if needed)
    issue_result = runner.invoke(app, [
        "vault", "issue", "--scope", "test:local-rotate", "--ttl", "1m", "--local", "--output", "json"
    ])
    assert issue_result.exit_code == 0
    try:
        credential = json.loads(issue_result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Failed to parse JSON from issue command: {issue_result.stdout}")
        
    agent_id = credential["agent_id"]
    identity_file = local_state["identities_dir"] / f"{agent_id}.json"
    assert identity_file.exists(), f"Identity file for {agent_id} not found."

    # 2. Run the rotate command locally
    rotate_result = runner.invoke(app, [
        "vault",
        "rotate",
        "--agent-id", agent_id,
        "--local"
    ])

    print("Rotate CLI Output:", rotate_result.stdout)
    assert rotate_result.exit_code == 0
    # Check new output format - more specific check
    assert "Local rotation complete" in rotate_result.stdout
    assert f"for agent \n{agent_id}" in rotate_result.stdout # Check for newline and agent id
    assert "Backend Notified: False" in rotate_result.stdout

    # Verify local file was updated (check timestamp exists)
    with open(identity_file, 'r') as f:
        rotated_identity = json.load(f)
    assert "rotated_at" in rotated_identity
    assert isinstance(rotated_identity["rotated_at"], int)

    print("test_vault_rotate_local PASSED")

@patch('deepsecure.core.base_client.BaseClient._request')
def test_vault_rotate_backend(mock_request, local_state, mock_backend_env):
    """Test `deepsecure vault rotate` (backend interaction)."""
    print("\n--- Testing vault rotate (backend) ---")
    # 1. Issue locally to create identity file
    issue_result = runner.invoke(app, [
        "vault", "issue", "--local", "--output", "json", "--ttl", "1m", "--scope", "setup-scope"
    ]) # Added missing --scope
    assert issue_result.exit_code == 0, f"Prerequisite issue command failed: {issue_result.stdout}"
    agent_id = json.loads(issue_result.stdout)["agent_id"]
    identity_file = local_state["identities_dir"] / f"{agent_id}.json"
    assert identity_file.exists()

    # 2. Configure mock backend response (204 No Content -> handled as success dict)
    mock_request.return_value = {"status": "success", "data": None}

    # 3. Run rotate command (no --local)
    result = runner.invoke(app, ["vault", "rotate", "--agent-id", agent_id])
    print("CLI Output:", result.stdout)
    assert result.exit_code == 0
    assert "Local rotation complete" in result.stdout
    assert "Backend Notified: True" in result.stdout # Check backend was notified

    # 4. Verify mock request
    assert mock_request.call_count == 1
    call_args, call_kwargs = mock_request.call_args
    assert call_args[0] == "POST"
    assert call_args[1] == f"/api/v1/vault/agents/{agent_id}/rotate-identity"
    assert call_kwargs.get("is_backend_request") is True
    sent_data = call_kwargs.get("data")
    assert sent_data is not None
    assert "new_public_key" in sent_data # Check key was sent

    # 5. Verify local identity file was still updated
    with open(identity_file, 'r') as f:
        rotated_identity = json.load(f)
    assert "rotated_at" in rotated_identity

    print("test_vault_rotate_backend PASSED")

@patch('deepsecure.core.base_client.BaseClient._request')
def test_vault_rotate_backend_failure(mock_request, local_state, mock_backend_env):
    """Test `deepsecure vault rotate` when backend notification fails."""
    print("\n--- Testing vault rotate (backend failure) ---")
    # 1. Issue locally to create identity file
    issue_result = runner.invoke(app, [
        "vault", "issue", "--local", "--output", "json", "--ttl", "1m", "--scope", "setup-scope"
    ])
    assert issue_result.exit_code == 0, f"Prerequisite issue command failed: {issue_result.stdout}"
    agent_id = json.loads(issue_result.stdout)["agent_id"]
    identity_file = local_state["identities_dir"] / f"{agent_id}.json"
    assert identity_file.exists()

    # 2. Configure mock to directly raise the expected ApiError
    # This simulates what _request would raise after _handle_response processes an HTTPError
    error_message = "API Error 500: Server exploded"
    mock_request.side_effect = exceptions.ApiError(error_message)
    # We need to manually set the status_code on the exception instance if the handler uses it
    # However, the command handler currently just prints str(e)

    # 3. Run rotate command (no --local)
    result = runner.invoke(app, ["vault", "rotate", "--agent-id", agent_id])
    print("CLI Output:", result.stdout)

    # Expect failure because backend notification failed
    assert result.exit_code != 0
    # Check that the specific ApiError message was caught and printed
    assert "Backend API error during rotation notification" in result.stdout
    assert error_message in result.stdout # Check specific error

    # 4. Verify mock request was called
    mock_request.assert_called_once()

    # 5. Verify local identity file was STILL updated (local happens first)
    with open(identity_file, 'r') as f:
        rotated_identity = json.load(f)
    assert "rotated_at" in rotated_identity

    print("test_vault_rotate_backend_failure PASSED") 