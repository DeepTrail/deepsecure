from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import settings

# Use base64 strings with correct structure and padding (even if not real keys)
# Format: AAAAC3NzaC1lZDI1NTE5AAAAIDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (base64 encoding of type + 32 byte key)
VALID_SSH_PUB_KEY_B64_1 = "AAAAC3NzaC1lZDI1NTE5AAAAIDAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
VALID_SSH_PUB_KEY_B64_2 = "AAAAC3NzaC1lZDI1NTE5AAAAIGBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB="
VALID_SSH_PUB_KEY_B64_3 = "AAAAC3NzaC1lZDI1NTE5AAAAIGCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC="

VALID_PUB_KEY_STR_1 = f"ssh-ed25519 {VALID_SSH_PUB_KEY_B64_1} test1@example.com"
VALID_PUB_KEY_STR_2 = f"ssh-ed25519 {VALID_SSH_PUB_KEY_B64_2} test2@example.com"
VALID_PUB_KEY_STR_3 = f"ssh-ed25519 {VALID_SSH_PUB_KEY_B64_3} test3@example.com"

# Basic test to ensure the endpoint works
def test_register_agent_success(client: TestClient, db: Session):
    agent_id = "test-agent-001"
    public_key = VALID_PUB_KEY_STR_1 # Use the full SSH string
    data = {"agent_id": agent_id, "current_public_key": public_key}

    response = client.post(f"{settings.API_V1_STR}/agents/", json=data)

    assert response.status_code == 201
    content = response.json()
    assert content["agent_id"] == agent_id
    # The response schema should format it back to the full SSH string
    assert content["current_public_key"].startswith("ssh-ed25519 ")
    assert VALID_SSH_PUB_KEY_B64_1 in content["current_public_key"]
    assert "created_at" in content

def test_register_agent_duplicate(client: TestClient, db: Session):
    agent_id = "test-agent-002"
    public_key = VALID_PUB_KEY_STR_2 # Use the full SSH string
    data = {"agent_id": agent_id, "current_public_key": public_key}

    # First registration should succeed
    response1 = client.post(f"{settings.API_V1_STR}/agents/", json=data)
    assert response1.status_code == 201 # Expecting this to pass now

    # Second registration with the same ID should fail
    response2 = client.post(f"{settings.API_V1_STR}/agents/", json=data)
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"]

def test_read_agent_success(client: TestClient, db: Session):
    # Register an agent first
    agent_id = "test-agent-003"
    public_key = VALID_PUB_KEY_STR_3 # Use the full SSH string
    register_data = {"agent_id": agent_id, "current_public_key": public_key}
    reg_response = client.post(f"{settings.API_V1_STR}/agents/", json=register_data)
    assert reg_response.status_code == 201 # Ensure registration worked

    # Now read the agent
    response = client.get(f"{settings.API_V1_STR}/agents/{agent_id}")

    assert response.status_code == 200
    content = response.json()
    assert content["agent_id"] == agent_id
    # Check response formatting
    assert content["current_public_key"].startswith("ssh-ed25519 ")
    assert VALID_SSH_PUB_KEY_B64_3 in content["current_public_key"]

def test_read_agent_not_found(client: TestClient, db: Session):
    response = client.get(f"{settings.API_V1_STR}/agents/nonexistent-agent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found" 