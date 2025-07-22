import pytest
from unittest.mock import patch
from sqlalchemy.orm import Session
import uuid

from app import crud
from app.schemas.credential import SecretStoreRequest
from app.models.credential import Secret

@patch("app.crud.crud_secret.CRUDSecret._send_share_to_gateway")
def test_create_secret_splits_correctly(mock_send_share, db: Session):
    """
    Tests that the create_secret CRUD method correctly splits the secret,
    stores one share locally, and calls the gateway with the other.
    """
    secret_name = f"unit-test-secret-{uuid.uuid4()}"
    secret_value = "my-super-secret-value-that-should-not-be-stored"
    request_obj = SecretStoreRequest(name=secret_name, value=secret_value)

    # Execute the method
    created_secret = crud.secret.create(db, obj_in=request_obj)

    # 1. Verify the object returned and stored in the DB is correct
    assert created_secret.name == secret_name
    # The crucial check: the stored value should NOT be the original secret
    assert created_secret.share_1 != secret_value
    assert isinstance(created_secret.share_1, str)

    # 2. Verify the gateway was called correctly
    mock_send_share.assert_called_once()
    # Check the arguments passed to the mocked function
    args, kwargs = mock_send_share.call_args
    assert kwargs.get("secret_name") == secret_name
    sent_share = kwargs.get("share")
    assert sent_share is not None
    assert sent_share != secret_value

    # 3. (Optional but good) Verify we can recombine the shares
    from sslib import shamir
    stored_share = created_secret.share_1
    recombined = shamir.combine_shares([stored_share, sent_share])
    assert recombined.decode('utf-8') == secret_value 