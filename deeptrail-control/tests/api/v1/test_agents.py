from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import settings

# Valid base64 encoded strings representing raw 32-byte Ed25519 keys
VALID_SSH_PUB_KEY_B64_1 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
VALID_SSH_PUB_KEY_B64_2 = "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB="
VALID_SSH_PUB_KEY_B64_3 = "L4KxV99pIdFc9866h0X1hdEG5Rux/CmcpHRAvyxJ/aY="

# Basic test to ensure the endpoint works
def test_register_agent_success(client: TestClient, db: Session):
    agent_id = "test-agent-001"
    public_key = VALID_SSH_PUB_KEY_B64_1
    data = {"agent_id": agent_id, "public_key": public_key}

    response = client.post(f"{settings.API_V1_STR}/agents/", json=data)

    assert response.status_code == 201
    content = response.json()
    assert content["agent_id"] == agent_id
    assert content["publicKey"] == public_key
    assert "created_at" in content

def test_register_agent_duplicate(client: TestClient, db: Session):
    agent_id = "test-agent-002"
    public_key = VALID_SSH_PUB_KEY_B64_2
    data = {"agent_id": agent_id, "public_key": public_key}

    # First registration should succeed
    response1 = client.post(f"{settings.API_V1_STR}/agents/", json=data)
    assert response1.status_code == 201

    # Second registration with the same ID should fail with 409 Conflict
    response2 = client.post(f"{settings.API_V1_STR}/agents/", json=data)
    assert response2.status_code == 409 # Use 409 for Conflict
    assert "already exists" in response2.json()["detail"]

def test_read_agent_success(client: TestClient, db: Session):
    # Register an agent first
    agent_id = "test-agent-003"
    public_key = VALID_SSH_PUB_KEY_B64_3
    register_data = {"agent_id": agent_id, "public_key": public_key}
    reg_response = client.post(f"{settings.API_V1_STR}/agents/", json=register_data)
    assert reg_response.status_code == 201

    # Now read the agent
    response = client.get(f"{settings.API_V1_STR}/agents/{agent_id}")

    assert response.status_code == 200
    content = response.json()
    assert content["agent_id"] == agent_id
    assert content["publicKey"] == public_key

def test_read_agent_not_found(client: TestClient, db: Session):
    response = client.get(f"{settings.API_V1_STR}/agents/nonexistent-agent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found" 