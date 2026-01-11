import logging
import json
from typing import Optional, Any
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

    def _send_share_to_gateway(self, secret_name: str, share: Any, prime_mod: Optional[str] = None):
        """Sends a secret share to the deeptrail-gateway."""
        try:
            gateway_url = f"{settings.GATEWAY_URL}/internal/shares"
            headers = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}
            payload = {
                "secret_name": secret_name, 
                "share_value": share,
                "prime_mod": prime_mod,  # Top-level field for Shamir reassembly
                "metadata": {}
            }

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

    def _encode_share(self, share: Any) -> list:
        """
        Encode a share to a JSON-serializable format [index, hex_string].
        Handles both tuple (index, bytes) and other formats.
        """
        if isinstance(share, (list, tuple)) and len(share) == 2:
            index, value = share
            if isinstance(value, bytes):
                return [index, value.hex()]
            return [index, str(value)]
        elif isinstance(share, bytes):
            return [0, share.hex()]
        return share

    def create_secret(self, db: Session, *, obj_in: SecretStoreRequest) -> Secret:
        """
        Splits a secret into two shares, stores one locally, and sends the other
        to the deeptrail-gateway.
        """
        # 1. Split the secret
        # We need 2 shares to reconstruct, so we use a threshold of 2.
        try:
            shares_data = shamir.split_secret(obj_in.value.encode('utf-8'), 2, 2)
            
            # shamir.split_secret returns a dict like:
            # {'required_shares': 2, 'prime_mod': bytes, 'shares': [(1, bytes), (2, bytes)]}
            if isinstance(shares_data, dict) and 'shares' in shares_data:
                shares = shares_data['shares']
                # Extract prime_mod for reassembly later
                prime_mod = shares_data.get('prime_mod')
                prime_mod_hex = prime_mod.hex() if isinstance(prime_mod, bytes) else str(prime_mod)
            else:
                # If it's already a list/tuple
                shares = shares_data
                prime_mod_hex = None
            
            share_1 = self._encode_share(shares[0])
            share_2 = self._encode_share(shares[1])
            
            logger.info(f"Successfully split secret '{obj_in.name}' into two shares.")
        except Exception as e:
            logger.exception(f"Failed to split the secret using Shamir's algorithm: {e}")
            raise HTTPException(status_code=500, detail="Could not process secret.")

        # 2. Send the second share to the gateway (include prime_mod for reassembly)
        try:
            self._send_share_to_gateway(secret_name=obj_in.name, share=share_2, prime_mod=prime_mod_hex)
            logger.info(f"Successfully sent share_2 for secret '{obj_in.name}' to gateway.")
        except HTTPException as e:
            # Re-raise the exception from the gateway call to provide clear feedback
            raise e

        # 3. Store the first share and metadata in the local database
        # Include prime_mod in metadata for reassembly later
        enhanced_metadata = dict(obj_in.secret_metadata) if obj_in.secret_metadata else {}
        enhanced_metadata['_prime_mod'] = prime_mod_hex
        
        db_obj = Secret(
            name=obj_in.name,
            share_1=json.dumps(share_1),
            secret_metadata=enhanced_metadata
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

    def list_secrets(self, db: Session):
        """
        Returns all secrets (metadata only, no share values).
        
        Args:
            db: The database session.
            
        Returns:
            A list of all Secret database objects.
        """
        return db.query(Secret).order_by(Secret.created_at.desc()).all()

    def delete_secret(self, db: Session, *, name: str) -> bool:
        """
        Delete a secret by its name.
        
        Args:
            db: The database session.
            name: The name of the secret to delete.
            
        Returns:
            True if the secret was deleted, False if not found.
        """
        secret_obj = self.get_secret_by_name(db=db, name=name)
        if secret_obj:
            db.delete(secret_obj)
            db.commit()
            return True
        return False


# Create a secret object to be imported by other modules
secret = CRUDSecret(Secret) 