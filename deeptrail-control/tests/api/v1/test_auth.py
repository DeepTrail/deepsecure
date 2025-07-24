import uuid
from unittest.mock import patch

from jose import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from nacl.signing import SigningKey
from nacl.encoding import Base64Encoder

from app import crud, schemas
from app.core.config import settings
from tests.utils.utils import random_lower_string


def test_get_access_token_with_policy_claims(client: TestClient, db: Session) -> None:
    # 1. Create an agent with a key pair
    private_key = SigningKey.generate()
    public_key_b64 = private_key.verify_key.encode(encoder=Base64Encoder).decode("utf-8")
    
    agent_in = schemas.AgentCreate(name="test-policy-claims-agent", current_public_key=public_key_b64)
    agent = crud.agent.create(db, obj_in=agent_in)

    # 2. Create a policy for that agent
    policy_in = schemas.PolicyCreate(
        name=random_lower_string(),
        agent_id=agent.id,
        actions=["proxy:request", "other:action"],
        resources=["ds:secret:one", "ds:secret:two"]
    )
    crud.policy.create(db, obj_in=policy_in)

    # 3. Request a challenge
    challenge_resp = client.post(
        f"{settings.API_V1_STR}/auth/challenge", json={"agent_id": str(agent.id)}
    )
    assert challenge_resp.status_code == 200
    nonce = challenge_resp.json()["nonce"]

    # 4. Sign the nonce and request a token
    signed_nonce = private_key.sign(nonce.encode("utf-8")).signature
    signed_nonce_b64 = Base64Encoder.encode(signed_nonce).decode("utf-8")

    token_resp = client.post(
        f"{settings.API_V1_STR}/auth/token",
        json={"agent_id": str(agent.id), "signed_nonce": signed_nonce_b64},
    )
    assert token_resp.status_code == 200
    token_data = token_resp.json()
    access_token = token_data["access_token"]

    # 5. Decode the token and verify claims
    payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    
    assert payload["sub"] == str(agent.id)
    assert "scope" in payload
    assert "resources" in payload

    # Scope is a space-delimited string
    token_scopes = set(payload["scope"].split(" "))
    assert token_scopes == {"proxy:request", "other:action"}
    
    # Resources is a list
    assert set(payload["resources"]) == {"ds:secret:one", "ds:secret:two"} 


def test_delegate_access_endpoint(client: TestClient, db: Session) -> None:
    """
    Test the POST /auth/delegate endpoint.
    It should call the macaroon service with the correct parameters and return a token.
    """
    # 1. Create a delegator agent to make the request
    private_key = SigningKey.generate()
    public_key_b64 = private_key.verify_key.encode(encoder=Base64Encoder).decode("utf-8")
    agent_in = schemas.AgentCreate(name="delegator-agent", current_public_key=public_key_b64)
    delegator_agent = crud.agent.create(db, obj_in=agent_in)

    # 2. Get a standard access token for the delegator agent to authenticate with
    challenge_resp = client.post(
        f"{settings.API_V1_STR}/auth/challenge", json={"agent_id": str(delegator_agent.id)}
    )
    nonce = challenge_resp.json()["nonce"]
    signed_nonce = private_key.sign(nonce.encode("utf-8")).signature
    signed_nonce_b64 = Base64Encoder.encode(signed_nonce).decode("utf-8")
    token_resp = client.post(
        f"{settings.API_V1_STR}/auth/token",
        json={"agent_id": str(delegator_agent.id), "signed_nonce": signed_nonce_b64},
    )
    access_token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 3. Define the delegation request
    delegation_payload = {
        "target_agent_id": "finance-agent-007",
        "resource": "secret:tavily-api-key",
        "permissions": ["read"],
        "ttl_seconds": 3600,
    }

    # 4. Mock the macaroon service and call the endpoint
    with patch("app.api.v1.endpoints.delegation.macaroon_service") as mock_macaroon_service:
        mock_macaroon_service.mint_delegation_macaroon.return_value = "mock_macaroon_token"

        response = client.post(
            f"{settings.API_V1_STR}/auth/delegate",
            json=delegation_payload,
            headers=headers,
        )

    # 5. Assert the results
    assert response.status_code == 200
    assert response.json() == {"delegation_token": "mock_macaroon_token"}

    mock_macaroon_service.mint_delegation_macaroon.assert_called_once_with(
        target_agent_id="finance-agent-007",
        resource="secret:tavily-api-key",
        permissions=["read"],
        ttl_seconds=3600,
    )


def test_bootstrap_kubernetes(client: TestClient, db: Session) -> None:
    """
    Test agent identity bootstrapping with a Kubernetes Service Account Token.
    """
    # 1. Create an attestation policy for a K8s identity
    agent_name = "k8s-bootstrapped-agent"
    namespace = "production"
    service_account = "my-app-sa"
    policy_in = schemas.AttestationPolicyCreate(
        agent_name=agent_name,
        platform="kubernetes",
        policy_data={"namespace": namespace, "service_account": service_account},
    )
    crud.attestation_policy.create(db, obj_in=policy_in)

    # 2. Mock the K8s token verification call
    mock_k8s_token_payload = {
        "iss": "https://accounts.google.com",
        "aud": "my-gcp-project-id",
        "sub": "system:serviceaccount:production:my-app-sa",
        "iat": 1615852800,
        "exp": 1615856400,
        "kubernetes.io": {
            "namespace": namespace,
            "serviceaccount": {"name": service_account, "uid": str(uuid.uuid4())},
        },
    }

    with patch("google.oauth2.id_token.verify_oauth2_token") as mock_verify_token:
        mock_verify_token.return_value = mock_k8s_token_payload

        # 3. Call the bootstrap endpoint
        bootstrap_payload = {"k8s_token": "fake-k8s-token"}
        response = client.post(
            f"{settings.API_V1_STR}/auth/bootstrap/kubernetes", json=bootstrap_payload
        )

    # 4. Assert the response
    assert response.status_code == 200
    content = response.json()
    assert "agent_id" in content
    assert "private_key_b64" in content
    assert "public_key_b64" in content
    
    # 5. Verify agent was created in DB
    agent = crud.agent.get(db, id=content["agent_id"])
    assert agent is not None
    assert agent.name == agent_name


def test_bootstrap_aws(client: TestClient, db: Session) -> None:
    """
    Test agent identity bootstrapping with an AWS IAM role.
    """
    # 1. Create an attestation policy for an AWS identity
    agent_name = "aws-bootstrapped-agent"
    role_arn = f"arn:aws:iam::{random_lower_string(12)}:role/MyWebAppRole"
    policy_in = schemas.AttestationPolicyCreate(
        agent_name=agent_name,
        platform="aws",
        policy_data={"role_arn": role_arn},
    )
    crud.attestation_policy.create(db, obj_in=policy_in)

    # 2. Mock the AWS STS get_caller_identity call
    with patch("boto3.client") as mock_boto_client:
        mock_sts_client = mock_boto_client.return_value
        mock_sts_client.get_caller_identity.return_value = {"Arn": role_arn}

        # 3. Call the bootstrap endpoint
        bootstrap_payload = {"iam_token": "fake-iam-token"} # Token is passed to STS
        response = client.post(
            f"{settings.API_V1_STR}/auth/bootstrap/aws", json=bootstrap_payload
        )

    # 4. Assert the response
    assert response.status_code == 200
    content = response.json()
    assert "agent_id" in content
    assert "private_key_b64" in content
    assert "public_key_b64" in content

    # 5. Verify agent was created in DB
    agent = crud.agent.get(db, id=content["agent_id"])
    assert agent is not None
    assert agent.name == agent_name 