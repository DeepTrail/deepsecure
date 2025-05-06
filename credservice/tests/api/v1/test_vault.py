import base64
import uuid
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

from app import schemas, crud
from app.core.config import settings
from app.models.agent import Agent as AgentModel

# --- Test Data and Helpers ---

# Use a known, valid API token for testing authentication
TEST_API_TOKEN = settings.BACKEND_API_TOKEN
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_API_TOKEN}"}
INVALID_AUTH_HEADERS = {"Authorization": "Bearer invalidtoken"}

def generate_ed25519_key_pair():
    """Generates a new Ed25519 key pair."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    # Serialize public key to bytes (raw format)
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return private_key, public_key_bytes

def generate_x25519_key_pair():
    """Generates a new X25519 key pair."""
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return private_key, public_key_bytes

def sign_message(private_key: ed25519.Ed25519PrivateKey, message: bytes) -> bytes:
    """Signs a message using an Ed25519 private key."""
    return private_key.sign(message)

@pytest.fixture(scope="function")
def test_agent_keys(db: Session) -> tuple[AgentModel, ed25519.Ed25519PrivateKey]:
    """Fixture to create a test agent and return the model and private key."""
    agent_id = f"test-vault-agent-{uuid.uuid4()}"
    private_key, public_key_bytes = generate_ed25519_key_pair()
    agent = AgentModel(agent_id=agent_id, current_public_key=public_key_bytes)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent, private_key

# --- Authentication Tests ---

def test_issue_credential_no_auth(client: TestClient):
    response = client.post(f"{settings.API_V1_STR}/vault/credentials", json={})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED # Expect 401 due to missing dep

def test_issue_credential_invalid_auth(client: TestClient):
    response = client.post(f"{settings.API_V1_STR}/vault/credentials", json={}, headers=INVALID_AUTH_HEADERS)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_revoke_credential_no_auth(client: TestClient):
    response = client.post(f"{settings.API_V1_STR}/vault/credentials/some-id/revoke")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_revoke_credential_invalid_auth(client: TestClient):
    response = client.post(f"{settings.API_V1_STR}/vault/credentials/some-id/revoke", headers=INVALID_AUTH_HEADERS)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_rotate_agent_no_auth(client: TestClient):
    response = client.post(f"{settings.API_V1_STR}/vault/agents/some-agent/rotate-identity", json={})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_rotate_agent_invalid_auth(client: TestClient):
    response = client.post(f"{settings.API_V1_STR}/vault/agents/some-agent/rotate-identity", json={}, headers=INVALID_AUTH_HEADERS)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_verify_credential_no_auth_allowed(client: TestClient):
    # Verification endpoint is public
    response = client.get(f"{settings.API_V1_STR}/vault/credentials/nonexistent-id/verify")
    # Expect 200 OK with not_found status, not 401
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "not_found"

# --- Endpoint Tests --- #

# --- Issue Credential Tests --- #

def test_issue_credential_success(client: TestClient, db: Session, test_agent_keys: tuple[AgentModel, ed25519.Ed25519PrivateKey]):
    agent, agent_priv_key = test_agent_keys
    _, eph_pub_key_bytes = generate_x25519_key_pair()
    signature_bytes = sign_message(agent_priv_key, eph_pub_key_bytes)

    issue_data = {
        "agent_id": agent.agent_id,
        "ephemeral_public_key": base64.b64encode(eph_pub_key_bytes).decode('utf-8'),
        "signature": base64.b64encode(signature_bytes).decode('utf-8'),
        "ttl": 60,
        "scope": "test_scope"
    }

    response = client.post(
        f"{settings.API_V1_STR}/vault/credentials",
        json=issue_data,
        headers=AUTH_HEADERS
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["agent_id"] == agent.agent_id
    assert data["scope"] == "test_scope"
    assert data["ephemeral_public_key"] == issue_data["ephemeral_public_key"]
    assert "credential_id" in data
    assert "expires_at" in data

    # Verify expiry is roughly correct (allow some clock skew)
    expires_at_str = data["expires_at"]
    expires_at = datetime.fromisoformat(expires_at_str)
    # Ensure the parsed datetime is offset-aware (assume UTC if naive from isoformat)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    expected_expiry = datetime.now(timezone.utc) + timedelta(seconds=60)
    assert abs(expires_at - expected_expiry) < timedelta(seconds=5)

def test_issue_credential_invalid_signature(client: TestClient, db: Session, test_agent_keys: tuple[AgentModel, ed25519.Ed25519PrivateKey]):
    agent, _ = test_agent_keys # Use agent_id but wrong key for signing
    wrong_priv_key, _ = generate_ed25519_key_pair()
    _, eph_pub_key_bytes = generate_x25519_key_pair()
    signature_bytes = sign_message(wrong_priv_key, eph_pub_key_bytes) # Sign with wrong key

    issue_data = {
        "agent_id": agent.agent_id,
        "ephemeral_public_key": base64.b64encode(eph_pub_key_bytes).decode('utf-8'),
        "signature": base64.b64encode(signature_bytes).decode('utf-8'),
        "ttl": 60
    }

    response = client.post(f"{settings.API_V1_STR}/vault/credentials", json=issue_data, headers=AUTH_HEADERS)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid signature" in response.json()["detail"]

def test_issue_credential_agent_not_found(client: TestClient, db: Session):
    agent_priv_key, _ = generate_ed25519_key_pair() # Get the actual key object
    _, eph_pub_key_bytes = generate_x25519_key_pair()
    signature_bytes = sign_message(agent_priv_key, eph_pub_key_bytes)

    issue_data = {
        "agent_id": "nonexistent-agent",
        "ephemeral_public_key": base64.b64encode(eph_pub_key_bytes).decode('utf-8'),
        "signature": base64.b64encode(signature_bytes).decode('utf-8'),
        "ttl": 60
    }
    response = client.post(f"{settings.API_V1_STR}/vault/credentials", json=issue_data, headers=AUTH_HEADERS)
    assert response.status_code == status.HTTP_404_NOT_FOUND

# --- Revoke Credential Tests --- #

def test_revoke_credential_success(client: TestClient, db: Session, test_agent_keys: tuple[AgentModel, ed25519.Ed25519PrivateKey]):
    # First, issue a credential
    agent, agent_priv_key = test_agent_keys
    _, eph_pub_key_bytes = generate_x25519_key_pair()
    signature_bytes = sign_message(agent_priv_key, eph_pub_key_bytes)
    issue_data = {
        "agent_id": agent.agent_id,
        "ephemeral_public_key": base64.b64encode(eph_pub_key_bytes).decode('utf-8'),
        "signature": base64.b64encode(signature_bytes).decode('utf-8'),
        "ttl": 300 # Longer TTL
    }
    issue_response = client.post(f"{settings.API_V1_STR}/vault/credentials", json=issue_data, headers=AUTH_HEADERS)
    assert issue_response.status_code == status.HTTP_201_CREATED
    credential_id = issue_response.json()["credential_id"]

    # Now, revoke it
    revoke_response = client.post(f"{settings.API_V1_STR}/vault/credentials/{credential_id}/revoke", headers=AUTH_HEADERS)
    assert revoke_response.status_code == status.HTTP_200_OK
    data = revoke_response.json()
    assert data["credential_id"] == credential_id
    assert data["status"] == "revoked"

    # Verify it shows as revoked
    verify_response = client.get(f"{settings.API_V1_STR}/vault/credentials/{credential_id}/verify")
    assert verify_response.status_code == status.HTTP_200_OK
    verify_data = verify_response.json()
    assert verify_data["is_valid"] is False
    assert verify_data["status"] == "revoked"

def test_revoke_credential_not_found(client: TestClient, db: Session):
    response = client.post(f"{settings.API_V1_STR}/vault/credentials/nonexistent-cred-id/revoke", headers=AUTH_HEADERS)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_revoke_credential_already_revoked(client: TestClient, db: Session, test_agent_keys: tuple[AgentModel, ed25519.Ed25519PrivateKey]):
    # Issue
    agent, agent_priv_key = test_agent_keys
    _, eph_pub_key_bytes = generate_x25519_key_pair()
    signature_bytes = sign_message(agent_priv_key, eph_pub_key_bytes)
    issue_data = {"agent_id": agent.agent_id, "ephemeral_public_key": base64.b64encode(eph_pub_key_bytes).decode('utf-8'), "signature": base64.b64encode(signature_bytes).decode('utf-8'), "ttl": 300}
    issue_response = client.post(f"{settings.API_V1_STR}/vault/credentials", json=issue_data, headers=AUTH_HEADERS)
    credential_id = issue_response.json()["credential_id"]

    # Revoke 1st time
    client.post(f"{settings.API_V1_STR}/vault/credentials/{credential_id}/revoke", headers=AUTH_HEADERS)
    time.sleep(1.1) # Ensure time passes for the check in the endpoint

    # Revoke 2nd time
    revoke_response = client.post(f"{settings.API_V1_STR}/vault/credentials/{credential_id}/revoke", headers=AUTH_HEADERS)
    assert revoke_response.status_code == status.HTTP_200_OK
    assert revoke_response.json()["status"] == "already_revoked"

# --- Rotate Agent Key Tests --- #

def test_rotate_agent_key_success(client: TestClient, db: Session, test_agent_keys: tuple[AgentModel, ed25519.Ed25519PrivateKey]):
    agent, _ = test_agent_keys
    _, new_pub_key_bytes = generate_ed25519_key_pair()

    rotate_data = {
        "new_public_key": base64.b64encode(new_pub_key_bytes).decode('utf-8')
    }

    response = client.post(
        f"{settings.API_V1_STR}/vault/agents/{agent.agent_id}/rotate-identity",
        json=rotate_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify in DB
    db.refresh(agent)
    assert agent.current_public_key == new_pub_key_bytes

def test_rotate_agent_key_agent_not_found(client: TestClient, db: Session):
    _, new_pub_key_bytes = generate_ed25519_key_pair()
    rotate_data = {"new_public_key": base64.b64encode(new_pub_key_bytes).decode('utf-8')}
    response = client.post(f"{settings.API_V1_STR}/vault/agents/nonexistent-agent/rotate-identity", json=rotate_data, headers=AUTH_HEADERS)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_rotate_agent_key_invalid_key_format(client: TestClient, db: Session, test_agent_keys: tuple[AgentModel, ed25519.Ed25519PrivateKey]):
    agent, _ = test_agent_keys
    rotate_data = {"new_public_key": "this is not base64"}
    response = client.post(f"{settings.API_V1_STR}/vault/agents/{agent.agent_id}/rotate-identity", json=rotate_data, headers=AUTH_HEADERS)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    rotate_data = {"new_public_key": base64.b64encode(b"short key").decode('utf-8')}
    response = client.post(f"{settings.API_V1_STR}/vault/agents/{agent.agent_id}/rotate-identity", json=rotate_data, headers=AUTH_HEADERS)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

# --- Verify Credential Tests --- #

def test_verify_credential_valid(client: TestClient, db: Session, test_agent_keys: tuple[AgentModel, ed25519.Ed25519PrivateKey]):
    # Issue
    agent, agent_priv_key = test_agent_keys
    _, eph_pub_key_bytes = generate_x25519_key_pair()
    signature_bytes = sign_message(agent_priv_key, eph_pub_key_bytes)
    issue_data = {"agent_id": agent.agent_id, "ephemeral_public_key": base64.b64encode(eph_pub_key_bytes).decode('utf-8'), "signature": base64.b64encode(signature_bytes).decode('utf-8'), "ttl": 60, "scope": "verify_scope"}
    issue_response = client.post(f"{settings.API_V1_STR}/vault/credentials", json=issue_data, headers=AUTH_HEADERS)
    credential_id = issue_response.json()["credential_id"]

    # Verify
    verify_response = client.get(f"{settings.API_V1_STR}/vault/credentials/{credential_id}/verify")
    assert verify_response.status_code == status.HTTP_200_OK
    data = verify_response.json()
    assert data["credential_id"] == credential_id
    assert data["is_valid"] is True
    assert data["status"] == "valid"
    assert data["scope"] == "verify_scope"
    assert data["agent_id"] == agent.agent_id
    assert "expires_at" in data

def test_verify_credential_expired(client: TestClient, db: Session, test_agent_keys: tuple[AgentModel, ed25519.Ed25519PrivateKey]):
    # Issue with short TTL
    agent, agent_priv_key = test_agent_keys
    _, eph_pub_key_bytes = generate_x25519_key_pair()
    signature_bytes = sign_message(agent_priv_key, eph_pub_key_bytes)
    issue_data = {"agent_id": agent.agent_id, "ephemeral_public_key": base64.b64encode(eph_pub_key_bytes).decode('utf-8'), "signature": base64.b64encode(signature_bytes).decode('utf-8'), "ttl": 1} # 1 second TTL
    issue_response = client.post(f"{settings.API_V1_STR}/vault/credentials", json=issue_data, headers=AUTH_HEADERS)
    credential_id = issue_response.json()["credential_id"]

    time.sleep(1.1) # Wait for expiry

    # Verify
    verify_response = client.get(f"{settings.API_V1_STR}/vault/credentials/{credential_id}/verify")
    assert verify_response.status_code == status.HTTP_200_OK
    data = verify_response.json()
    assert data["is_valid"] is False
    assert data["status"] == "expired"

def test_verify_credential_revoked(client: TestClient, db: Session, test_agent_keys: tuple[AgentModel, ed25519.Ed25519PrivateKey]):
    # Issue
    agent, agent_priv_key = test_agent_keys
    _, eph_pub_key_bytes = generate_x25519_key_pair()
    signature_bytes = sign_message(agent_priv_key, eph_pub_key_bytes)
    issue_data = {"agent_id": agent.agent_id, "ephemeral_public_key": base64.b64encode(eph_pub_key_bytes).decode('utf-8'), "signature": base64.b64encode(signature_bytes).decode('utf-8'), "ttl": 60}
    issue_response = client.post(f"{settings.API_V1_STR}/vault/credentials", json=issue_data, headers=AUTH_HEADERS)
    credential_id = issue_response.json()["credential_id"]

    # Revoke
    client.post(f"{settings.API_V1_STR}/vault/credentials/{credential_id}/revoke", headers=AUTH_HEADERS)

    # Verify
    verify_response = client.get(f"{settings.API_V1_STR}/vault/credentials/{credential_id}/verify")
    assert verify_response.status_code == status.HTTP_200_OK
    data = verify_response.json()
    assert data["is_valid"] is False
    assert data["status"] == "revoked"

def test_verify_credential_not_found(client: TestClient, db: Session):
    response = client.get(f"{settings.API_V1_STR}/vault/credentials/nonexistent-cred-id/verify")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "not_found" 