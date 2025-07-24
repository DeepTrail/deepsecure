import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid

from app.core.config import settings
from app import crud
from app.schemas.credential import SecretStoreRequest

def test_get_secret_share_success(client: TestClient, db: Session):
    """
    Tests successfully retrieving a secret share and its metadata.
    """
    secret_name = f"component-test-secret-{uuid.uuid4()}"
    secret_value = "test-value"
    target_url = "http://my-target-service.com"
    metadata = {"target_base_url": target_url}

    # We need to create a secret in the DB first using the CRUD method
    # Note: This bypasses the splitting logic for this component test
    crud.secret.create(db, obj_in=SecretStoreRequest(name=secret_name, value=secret_value, metadata=metadata))

    headers = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}
    response = client.get(f"/api/v1/internal/secrets/{secret_name}/share", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["share_1"] is not None
    assert data["target_base_url"] == target_url

def test_get_secret_share_no_metadata(client: TestClient, db: Session):
    """
    Tests retrieving a secret share when no metadata is present.
    """
    secret_name = f"component-test-secret-no-meta-{uuid.uuid4()}"
    secret_value = "test-value"

    crud.secret.create(db, obj_in=SecretStoreRequest(name=secret_name, value=secret_value))

    headers = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}
    response = client.get(f"/api/v1/internal/secrets/{secret_name}/share", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["share_1"] is not None
    assert data["target_base_url"] is None

def test_get_secret_share_not_found(client: TestClient, db: Session):
    """
    Tests that a 404 is returned for a non-existent secret.
    """
    secret_name = "does-not-exist"
    headers = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}
    response = client.get(f"/api/v1/internal/secrets/{secret_name}/share", headers=headers)
    assert response.status_code == 404

def test_get_secret_share_wrong_auth(client: TestClient, db: Session):
    """
    Tests that the endpoint is protected against missing or incorrect auth.
    """
    # No token
    response_no_auth = client.get("/api/v1/internal/secrets/some-secret/share")
    assert response_no_auth.status_code == 401

    # Wrong token
    headers = {"X-Internal-API-Token": "wrong-token"}
    response_wrong_auth = client.get("/api/v1/internal/secrets/some-secret/share", headers=headers)
    assert response_wrong_auth.status_code == 401 