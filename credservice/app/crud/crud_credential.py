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

    def get_by_credential_id(self, db: Session, *, credential_id: str) -> Optional[CredentialModel]:
        """Fetch a credential by its unique credential_id."""
        return db.query(self.model).filter(self.model.credential_id == credential_id).first()

    def get_multi_by_agent(self, db: Session, *, agent_id: str, skip: int = 0, limit: int = 100) -> List[CredentialModel]:
        """Fetch multiple credentials associated with a specific agent_id."""
        return (
            db.query(self.model)
            .filter(self.model.agent_id == agent_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(self, db: Session, *, obj_in: CredentialIssueRequest) -> CredentialModel:
        """Creates a new credential record in the database.

        Handles conversion of base64 keys/signatures and calculates expiry.
        Note: Signature verification should happen *before* calling this.
        """
        logger.info(f"Creating credential for agent: {obj_in.agent_id}")

        # Decode base64 fields (validation already done in schema)
        try:
            ephemeral_public_key_bytes = base64.b64decode(obj_in.ephemeral_public_key)
            signature_bytes = base64.b64decode(obj_in.signature)
        except Exception as e:
            logger.error(f"Failed to decode base64 data during CRUD create: {e}")
            raise ValueError("Invalid base64 data provided for key or signature")

        # Calculate expiry time
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=obj_in.ttl)

        # Prepare data for the model, excluding schema-only and byte fields handled separately
        obj_in_data = jsonable_encoder(obj_in, exclude={
            'ephemeral_public_key',
            'signature',
            'ttl',
            'ephemeral_public_key_bytes', # Exclude the schema helper field
            'signature_bytes'           # Exclude the schema helper field
        })

        # Generate credential ID
        credential_id = str(uuid.uuid4())
        logger.info(f"Generated credential ID: {credential_id}")

        db_obj = self.model(
            **obj_in_data,
            credential_id=credential_id,
            ephemeral_public_key=ephemeral_public_key_bytes, # Pass bytes directly
            signature=signature_bytes,                      # Pass bytes directly
            issued_at=now, # Use the calculated timestamp
            expires_at=expires_at
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
        """Marks a credential as revoked by setting the revoked_at timestamp."""
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