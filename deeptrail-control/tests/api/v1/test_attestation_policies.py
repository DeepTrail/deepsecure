import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.tests.utils.utils import random_lower_string, random_uuid


def test_create_k8s_attestation_policy(
    client: TestClient, superuser_token_headers: dict, db: Session
) -> None:
    """
    Test creating a Kubernetes attestation policy.
    """
    agent_name = random_lower_string()
    namespace = "default"
    service_account = "test-sa"
    description = "Test K8s Policy"

    data = {
        "agent_name": agent_name,
        "platform": "kubernetes",
        "description": description,
        "policy_data": {
            "namespace": namespace,
            "service_account": service_account,
        },
    }
    response = client.post(
        f"{settings.API_V1_STR}/attestation-policies/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["agent_name"] == agent_name
    assert content["platform"] == "kubernetes"
    assert content["description"] == description
    assert content["policy_data"]["namespace"] == namespace
    assert content["policy_data"]["service_account"] == service_account
    assert "id" in content
    assert "created_at" in content


def test_create_aws_attestation_policy(
    client: TestClient, superuser_token_headers: dict, db: Session
) -> None:
    """
    Test creating an AWS attestation policy.
    """
    agent_name = random_lower_string()
    role_arn = f"arn:aws:iam::{random_uuid()}:role/test-role"
    description = "Test AWS Policy"

    data = {
        "agent_name": agent_name,
        "platform": "aws",
        "description": description,
        "policy_data": {"role_arn": role_arn},
    }
    response = client.post(
        f"{settings.API_V1_STR}/attestation-policies/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["agent_name"] == agent_name
    assert content["platform"] == "aws"
    assert content["description"] == description
    assert content["policy_data"]["role_arn"] == role_arn
    assert "id" in content


def test_read_attestation_policy(
    client: TestClient, superuser_token_headers: dict, db: Session
) -> None:
    """
    Test reading an attestation policy by ID.
    """
    agent_name = random_lower_string()
    data = {
        "agent_name": agent_name,
        "platform": "kubernetes",
        "policy_data": {"namespace": "default", "service_account": "read-sa"},
    }
    response = client.post(
        f"{settings.API_V1_STR}/attestation-policies/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    policy_id = response.json()["id"]

    response = client.get(
        f"{settings.API_V1_STR}/attestation-policies/{policy_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == policy_id
    assert content["agent_name"] == agent_name


def test_list_attestation_policies(
    client: TestClient, superuser_token_headers: dict, db: Session
) -> None:
    """
    Test listing all attestation policies.
    """
    # Create a couple of policies
    client.post(
        f"{settings.API_V1_STR}/attestation-policies/",
        headers=superuser_token_headers,
        json={
            "agent_name": "list-agent-1",
            "platform": "kubernetes",
            "policy_data": {"namespace": "ns1", "service_account": "sa1"},
        },
    )
    client.post(
        f"{settings.API_V1_STR}/attestation-policies/",
        headers=superuser_token_headers,
        json={
            "agent_name": "list-agent-2",
            "platform": "aws",
            "policy_data": {"role_arn": "arn:aws:iam:::role/test-role-2"},
        },
    )

    response = client.get(
        f"{settings.API_V1_STR}/attestation-policies/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert isinstance(content, list)
    assert len(content) >= 2


def test_delete_attestation_policy(
    client: TestClient, superuser_token_headers: dict, db: Session
) -> None:
    """
    Test deleting an attestation policy.
    """
    data = {
        "agent_name": "delete-me",
        "platform": "kubernetes",
        "policy_data": {"namespace": "to-delete", "service_account": "delete-sa"},
    }
    response = client.post(
        f"{settings.API_V1_STR}/attestation-policies/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    policy_id = response.json()["id"]

    # Delete it
    response = client.delete(
        f"{settings.API_V1_STR}/attestation-policies/{policy_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == policy_id

    # Verify it's gone
    response = client.get(
        f"{settings.API_V1_STR}/attestation-policies/{policy_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404 