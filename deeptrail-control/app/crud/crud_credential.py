import uuid
from datetime import datetime, timedelta, timezone
import base64
import logging
from typing import Optional, List, Any

from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder

from app.crud.base import CRUDBase
from app.models.credential import Credential as CredentialModel
from app.schemas.credential import CredentialIssueRequest, Credential as CredentialUpdateSchema

logger = logging.getLogger(__name__)

class CRUDCredential(CRUDBase[CredentialModel, CredentialIssueRequest, Any]):
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
        logger.info(f"CRUD: Creating credential for agent: {obj_in.agent_id}")

        # obj_in.ephemeral_public_key and obj_in.signature are already BYTES
        # due to the Pydantic validator in schemas.credential.CredentialIssueRequest
        ephemeral_public_key_bytes = obj_in.ephemeral_public_key
        signature_bytes = obj_in.signature

        # Optional: Add defensive type/length checks here again if paranoid, 
        # but Pydantic should have enforced this.
        if not isinstance(ephemeral_public_key_bytes, bytes) or len(ephemeral_public_key_bytes) != 32:
            err_msg = f"CRUD layer received invalid ephemeral_public_key (expected 32 bytes, got {type(ephemeral_public_key_bytes)} len {len(ephemeral_public_key_bytes) if isinstance(ephemeral_public_key_bytes,bytes) else 'N/A'})"
            logger.error(err_msg)
            raise ValueError(err_msg)
        if not isinstance(signature_bytes, bytes) or len(signature_bytes) != 64:
            err_msg = f"CRUD layer received invalid signature (expected 64 bytes, got {type(signature_bytes)} len {len(signature_bytes) if isinstance(signature_bytes,bytes) else 'N/A'})"
            logger.error(err_msg)
            raise ValueError(err_msg)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=obj_in.ttl)
        
        # Exclude fields that are now bytes and handled manually, or calculated (ttl -> expires_at)
        create_data = jsonable_encoder(obj_in, exclude={'ephemeral_public_key', 'signature', 'ttl'})

        credential_id = str(uuid.uuid4())
        logger.info(f"CRUD: Generated credential ID: {credential_id}")

        db_obj = self.model(
            **create_data, # Contains agent_id, scope, origin_context (if present)
            credential_id=credential_id,
            ephemeral_public_key=ephemeral_public_key_bytes, # Pass the bytes directly
            signature=signature_bytes,                   # Pass the bytes directly
            issued_at=now,
            expires_at=expires_at,
            status="issued" 
        )
        
        logger.debug(f"CRUD: Adding CredentialModel instance to session: ID {credential_id}")
        db.add(db_obj)
        try:
            db.commit()
            logger.info(f"CRUD: Committed credential {credential_id} successfully.")
        except Exception as e: 
            logger.error(f"CRUD: Database commit failed for credential {credential_id}: {e}", exc_info=True)
            db.rollback()
            raise
        db.refresh(db_obj)
        logger.debug(f"CRUD: Refreshed credential instance {credential_id}")
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
            db_obj.status = "revoked"
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