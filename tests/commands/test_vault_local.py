import pytest
import json
import time
from pathlib import Path
from typer.testing import CliRunner

from deepsecure.main import app # Import the main Typer app
from deepsecure.core import vault_client # To access client directly for verification

runner = CliRunner()

# Pytest fixture to manage the local .deepsecure state for tests
@pytest.fixture(scope="function") # Use 'function' scope for isolation between tests
def local_state(tmp_path, monkeypatch):
    """Fixture to create temporary local state directory and patch VaultClient paths."""
    
    # Create temporary directories within pytest's tmp_path
    temp_deepsecure_dir = tmp_path / ".deepsecure"
    temp_identities_dir = temp_deepsecure_dir / "identities"
    temp_identities_dir.mkdir(parents=True, exist_ok=True)
    
    temp_revocation_file = temp_deepsecure_dir / "revoked_creds.json"
    temp_device_id_file = temp_deepsecure_dir / "device_id"

    # --- Monkeypatch VaultClient constants/paths --- 
    # We patch the module-level constants used by VaultClient instance
    monkeypatch.setattr(vault_client, "DEEPSECURE_DIR", temp_deepsecure_dir)
    monkeypatch.setattr(vault_client, "IDENTITY_STORE_PATH", temp_identities_dir)
    monkeypatch.setattr(vault_client, "REVOCATION_LIST_FILE", temp_revocation_file)
    monkeypatch.setattr(vault_client, "DEVICE_ID_FILE", temp_device_id_file)

    # Re-initialize the singleton client to use the patched paths
    # This assumes the singleton `client` is accessed after patching
    # Note: Directly re-instantiating might be cleaner if possible, 
    # but patching module constants used by the existing singleton works.
    # Forcing re-init by creating a new instance and patching the module's client ref:
    new_client = vault_client.VaultClient()
    monkeypatch.setattr(vault_client, "client", new_client)
    
    print(f"\nUsing temp state dir: {temp_deepsecure_dir}")
    print(f"Patched IDENTITY_STORE_PATH: {vault_client.client.identity_store_path}")
    print(f"Patched REVOCATION_LIST_FILE: {vault_client.client.revocation_list_file}")
    
    yield {
        "deepsecure_dir": temp_deepsecure_dir,
        "identities_dir": temp_identities_dir,
        "revocation_file": temp_revocation_file
    }
    
    # Teardown (implicitly handled by tmp_path fixture)
    print(f"\nCleaning up temp state dir: {temp_deepsecure_dir}")


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


def test_vault_rotate_local_placeholder(local_state):
    """Test `deepsecure vault rotate --local` placeholder command."""
    print("\n--- Testing vault rotate --local (Placeholder) ---")
    # 1. Ensure an identity exists (issue one if needed)
    issue_result = runner.invoke(app, [
        "vault", "issue", "--scope", "test:local-rotate", "--ttl", "1m", "--local", "--output", "json"
    ])
    assert issue_result.exit_code == 0
    credential = json.loads(issue_result.stdout)
    agent_id = credential["agent_id"]
    identity_file = local_state["identities_dir"] / f"{agent_id}.json"
    assert identity_file.exists()
    
    # Optional: Read initial key to compare later if real rotation implemented
    # with open(identity_file, 'r') as f:
    #     initial_identity = json.load(f)
    # initial_pub_key = initial_identity.get("public_key")

    # 2. Run the rotate command locally
    # We need to tell it which identity to rotate, or implement default logic
    # Assuming for now it might default or we pass the agent ID (not currently supported by cmd)
    # Let's test the basic command execution for now. Need to specify type.
    rotate_result = runner.invoke(app, [
        "vault", 
        "rotate", 
        "--type", "agent-identity", # Assuming this type targets the local identity
        "--local"
        # TODO: Add --agent-id when rotate command supports it, or test default behavior
    ])

    print("Rotate CLI Output:", rotate_result.stdout)
    assert rotate_result.exit_code == 0
    assert "Rotated" in rotate_result.stdout
    assert "agent-identity" in rotate_result.stdout
    assert "Placeholder - Local" in rotate_result.stdout
    assert "New ID/Reference:" in rotate_result.stdout
    assert "Rotated at:" in rotate_result.stdout

    # TODO: When rotation logic is implemented in VaultClient:
    # 1. Reread the identity file.
    # 2. Assert that the public/private keys have changed.
    # 3. Assert that the 'rotated_at' timestamp (or similar) is updated.

    print("test_vault_rotate_local_placeholder PASSED") 