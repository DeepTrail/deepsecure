import logging
from typing import Optional
import httpx
from sslib import shamir
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.crud.base import CRUDBase
from app.models.credential import Secret
from app.schemas.credential import SecretStoreRequest
from app.core.config import settings

logger = logging.getLogger(__name__)

class CRUDSecret(CRUDBase[Secret, SecretStoreRequest, SecretStoreRequest]):
    """CRUD operations for Secret models."""

    def _send_share_to_gateway(self, secret_name: str, share: str):
        """Sends a secret share to the deeptrail-gateway."""
        try:
            gateway_url = f"{settings.GATEWAY_URL}/internal/shares"
            headers = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}
            payload = {"secret_name": secret_name, "share_value": share}

            with httpx.Client() as client:
                response = client.post(gateway_url, json=payload, headers=headers)
                response.raise_for_status()
            logger.info(f"Successfully sent share for secret '{secret_name}' to gateway.")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error sending share for '{secret_name}' to gateway: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to store secret share in gateway: {e.response.text}"
            )
        except httpx.RequestError as e:
            logger.error(f"Request error sending share for '{secret_name}' to gateway: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not connect to the gateway to store secret share."
            )

    def create_secret(self, db: Session, *, obj_in: SecretStoreRequest) -> Secret:
        """
        Splits a secret into two shares, stores one locally, and sends the other
        to the deeptrail-gateway.
        """
        # 1. Split the secret
        # We need 2 shares to reconstruct, so we use a threshold of 2.
        try:
            shares = shamir.split_secret(obj_in.value.encode('utf-8'), 2, 2)
            share_1, share_2 = shares
            logger.info(f"Successfully split secret '{obj_in.name}' into two shares.")
        except Exception:
            logger.exception("Failed to split the secret using Shamir's algorithm.")
            raise HTTPException(status_code=500, detail="Could not process secret.")

        # 2. Send the second share to the gateway
        try:
            self._send_share_to_gateway(secret_name=obj_in.name, share=share_2)
            logger.info(f"Successfully sent share_2 for secret '{obj_in.name}' to gateway.")
        except HTTPException as e:
            # Re-raise the exception from the gateway call to provide clear feedback
            raise e

        # 3. Store the first share and metadata in the local database
        db_obj = Secret(
            name=obj_in.name,
            share_1=share_1,
            secret_metadata=obj_in.secret_metadata
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        logger.info(f"Successfully stored share_1 and metadata for secret '{obj_in.name}' in control plane.")
        return db_obj

    def get_secret_by_name(self, db: Session, *, name: str) -> Optional[Secret]:
        """
        Retrieve a secret by its name.

        Args:
            db: The database session.
            name: The name of the secret to retrieve.

        Returns:
            The Secret database object if found, None otherwise.
        """
        return db.query(Secret).filter(Secret.name == name).first()

# Create a secret object to be imported by other modules
secret = CRUDSecret(Secret) 