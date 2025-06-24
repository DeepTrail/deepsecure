from typing import Optional
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.credential import Secret
from app.schemas.credential import SecretStoreRequest

class CRUDSecret(CRUDBase[Secret, SecretStoreRequest, SecretStoreRequest]):
    """CRUD operations for Secret models."""
    
    def create_secret(self, db: Session, *, obj_in: SecretStoreRequest) -> Secret:
        """
        Create a new secret or update an existing one by name.

        Args:
            db: The database session.
            obj_in: The secret data from the API request.

        Returns:
            The created or updated Secret database object.
        """
        # Check if a secret with the same name already exists
        db_obj = db.query(Secret).filter(Secret.name == obj_in.name).first()
        
        if db_obj:
            # Update existing secret
            db_obj.value = obj_in.value
        else:
            # Create new secret
            db_obj = Secret(name=obj_in.name, value=obj_in.value)
            db.add(db_obj)
            
        db.commit()
        db.refresh(db_obj)
        return db_obj

# Create a secret object to be imported by other modules
secret = CRUDSecret(Secret) 