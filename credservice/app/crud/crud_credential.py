import uuid
from datetime import datetime, timedelta, timezone
import base64
import logging
from typing import Optional, List

from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder

from app.crud.base import CRUDBase
from app.models.credential import Credential as CredentialModel
from app.schemas.credential import CredentialIssueRequest, Credential as CredentialUpdateSchema

logger = logging.getLogger(__name__)

class CRUDCredential(CRUDBase[CredentialModel, CredentialIssueRequest, CredentialUpdateSchema]):
    """CRUD operations for Credential models."""

    def get_by_credential_id(self, db: Session, *, credential_id: str) -> Optional[CredentialModel]:
        """Fetch a credential by its unique credential_id.

        Args:
            db: The database session.
            credential_id: The credential ID to search for.

        Returns:
            The CredentialModel instance if found, otherwise None.
        """
        return db.query(self.model).filter(self.model.credential_id == credential_id).first()

    def get_multi_by_agent(self, db: Session, *, agent_id: str, skip: int = 0, limit: int = 100) -> List[CredentialModel]:
        """Fetch multiple credentials associated with a specific agent_id.

        Args:
            db: The database session.
            agent_id: The agent ID whose credentials to fetch.
            skip: Number of records to skip (for pagination).
            limit: Maximum number of records to return (for pagination).

        Returns:
            A list of CredentialModel instances.
        """
        return (
            db.query(self.model)
            .filter(self.model.agent_id == agent_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(self, db: Session, *, obj_in: CredentialIssueRequest) -> CredentialModel:
        """Creates a new credential record in the database.

        Handles conversion of base64 keys/signatures from input schema
        and calculates the `expires_at` timestamp based on the provided TTL.

        Note: Signature verification logic resides in the API endpoint,
              this method assumes the signature is already verified.

        Args:
            db: The database session.
            obj_in: The CredentialIssueRequest schema object containing input data.

        Returns:
            The newly created CredentialModel instance.

        Raises:
            ValueError: If base64 decoding fails.
            SQLAlchemyError: If a database commit error occurs.
        """
        logger.info(f"Creating credential for agent: {obj_in.agent_id}")

        try:
            ephemeral_public_key_bytes = base64.b64decode(obj_in.ephemeral_public_key)
        except Exception as e:
            logger.error(f"CRUD: Failed to decode ephemeral_public_key '{obj_in.ephemeral_public_key}': {e}")
            raise ValueError("Invalid base64 for ephemeral_public_key in CRUD") from e

        signature_bytes: Optional[bytes] = None # Default to None
        if obj_in.signature is not None: # <--- ADD THIS CHECK
            try:
                signature_bytes = base64.b64decode(obj_in.signature)
            except Exception as e:
                logger.error(f"CRUD: Failed to decode signature '{obj_in.signature}': {e}")
                raise ValueError("Invalid base64 for signature in CRUD") from e

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=obj_in.ttl)
        
        obj_in_data = jsonable_encoder(obj_in, exclude={
            'agent_id', # <--- ADD agent_id TO EXCLUDE
            'scope', # <--- ADD scope TO EXCLUDE 
            'ephemeral_public_key',
            'signature',
            'ttl',
            #'ephemeral_public_key_bytes',
            #'signature_bytes'
        })
        
        credential_id = str(uuid.uuid4())
        logger.info(f"Generated credential ID: {credential_id}")

        db_obj = self.model(
            **obj_in_data,
            credential_id=credential_id,
            agent_id=obj_in.agent_id, # This is now the sole source for agent_id
            scope=obj_in.scope, # This is now the sole source for scope
            ephemeral_public_key=ephemeral_public_key_bytes,
            signature=signature_bytes,
            issued_at=now,
            expires_at=expires_at,
            status="issued"
            # Ensure origin_context from obj_in_data is handled or explicitly passed if needed
            # If origin_context is in obj_in (and thus in obj_in_data), it will be passed by **obj_in_data.
        )
        
        logger.debug(f"Adding CredentialModel instance to session: ID {credential_id}")
        db.add(db_obj)
        try:
            db.commit()
            logger.info(f"Committed credential {credential_id} successfully.")
        except Exception as e:
            logger.error(f"Database commit failed for credential {credential_id}: {e}", exc_info=True)
            db.rollback()
            raise
        db.refresh(db_obj)
        logger.debug(f"Refreshed credential instance {credential_id}")
        return db_obj

    def revoke(self, db: Session, *, credential_id: str) -> Optional[CredentialModel]:
        """Marks a credential as revoked by setting the `revoked_at` timestamp.

        Args:
            db: The database session.
            credential_id: The ID of the credential to revoke.

        Returns:
            The updated CredentialModel instance if found and revoked,
            None if the credential was not found.
            Returns the existing object if already revoked.

        Raises:
            SQLAlchemyError: If a database commit error occurs during update.
        """
        db_obj = self.get_by_credential_id(db=db, credential_id=credential_id)
        if not db_obj:
            logger.warning(f"Attempted to revoke non-existent credential: {credential_id}")
            return None

        if db_obj.revoked_at is None:
            logger.info(f"Revoking credential: {credential_id}")
            db_obj.revoked_at = datetime.now(timezone.utc)
            db.add(db_obj)
            try:
                db.commit()
                db.refresh(db_obj)
                logger.info(f"Successfully revoked credential: {credential_id}")
            except Exception as e:
                logger.error(f"Database commit failed during revocation of {credential_id}: {e}", exc_info=True)
                db.rollback()
                raise
        else:
            logger.info(f"Credential {credential_id} was already revoked at {db_obj.revoked_at}")

        return db_obj

    # You might add other methods like:
    # - find_active_by_agent_id
    # - prune_expired_credentials

# Instantiate the CRUD object with the SQLAlchemy model
credential = CRUDCredential(CredentialModel) 