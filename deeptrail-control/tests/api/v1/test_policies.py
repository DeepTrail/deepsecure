import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud
from app.core.config import settings
from app.schemas.agent import AgentCreate
from tests.utils.utils import random_lower_string

def test_create_policy(client: TestClient, db: Session) -> None:
    # First create an agent to associate the policy with
    agent_in = AgentCreate(name="test-policy-agent", description="An agent for policy testing")
    agent = crud.agent.create(db, obj_in=agent_in)

    policy_name = random_lower_string()
    data = {
        "name": policy_name,
        "description": "A test policy",
        "agent_id": str(agent.id),
        "effect": "allow",
        "actions": ["proxy:request"],
        "resources": ["ds:secret:test-secret"]
    }
    response = client.post(
        f"{settings.API_V1_STR}/policies/",
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == policy_name
    assert content["agent_id"] == str(agent.id)
    assert "id" in content

def test_read_policy(client: TestClient, db: Session) -> None:
    agent_in = AgentCreate(name="test-policy-agent-2", description="Another agent for policy testing")
    agent = crud.agent.create(db, obj_in=agent_in)
    
    policy_name = random_lower_string()
    policy_in = schemas.PolicyCreate(
        name=policy_name,
        agent_id=agent.id,
        actions=["proxy:request"],
        resources=["ds:secret:another-secret"]
    )
    policy = crud.policy.create(db, obj_in=policy_in)

    response = client.get(
        f"{settings.API_V1_STR}/policies/{policy.id}"
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == policy_name
    assert content["id"] == str(policy.id)

def test_read_policies(client: TestClient, db: Session) -> None:
    response = client.get(f"{settings.API_V1_STR}/policies/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_update_policy(client: TestClient, db: Session) -> None:
    agent_in = AgentCreate(name="test-policy-agent-3")
    agent = crud.agent.create(db, obj_in=agent_in)
    
    policy_in = schemas.PolicyCreate(
        name=random_lower_string(),
        agent_id=agent.id,
        actions=["proxy:request"],
        resources=["ds:secret:updatable-secret"]
    )
    policy = crud.policy.create(db, obj_in=policy_in)

    updated_description = "An updated description"
    data = {"description": updated_description}
    response = client.put(
        f"{settings.API_V1_STR}/policies/{policy.id}",
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["description"] == updated_description
    assert content["id"] == str(policy.id)

def test_delete_policy(client: TestClient, db: Session) -> None:
    agent_in = AgentCreate(name="test-policy-agent-4")
    agent = crud.agent.create(db, obj_in=agent_in)
    
    policy_in = schemas.PolicyCreate(
        name=random_lower_string(),
        agent_id=agent.id,
        actions=["proxy:request"],
        resources=["ds:secret:deletable-secret"]
    )
    policy = crud.policy.create(db, obj_in=policy_in)

    response = client.delete(
        f"{settings.API_V1_STR}/policies/{policy.id}"
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(policy.id)

    response_get = client.get(f"{settings.API_V1_STR}/policies/{policy.id}")
    assert response_get.status_code == 404 