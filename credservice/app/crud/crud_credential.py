from typing import Optional, List
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.credential import Credential as CredentialModel # Rename import
# Use the *Create* schema for creation, and the full schema for update (for now)
from app.schemas.credential import CredentialCreate, Credential as CredentialUpdateSchema # Use CredentialCreate

class CRUDCredential(CRUDBase[CredentialModel, CredentialCreate, CredentialUpdateSchema]):
    def get_by_credential_id(self, db: Session, *, credential_id: str) -> Optional[CredentialModel]: # Return model
        """Fetch a credential by its unique credential_id."""
        return db.query(self.model).filter(self.model.credential_id == credential_id).first()

    def get_multi_by_agent(self, db: Session, *, agent_id: str, skip: int = 0, limit: int = 100) -> List[CredentialModel]: # Return list of models
        """Fetch multiple credentials associated with a specific agent_id."""
        return (
            db.query(self.model)
            .filter(self.model.agent_id == agent_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def revoke(self, db: Session, *, db_obj: CredentialModel) -> CredentialModel: # Takes/returns model
        """Mark a credential as revoked."""
        if not db_obj.is_revoked:
            db_obj.is_revoked = True
            db_obj.revoked_at = datetime.now(timezone.utc)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
        return db_obj

    # You might add other methods like:
    # - find_active_by_agent_id
    # - prune_expired_credentials

# Instantiate with the SQLAlchemy MODEL class
credential = CRUDCredential(CredentialModel) 