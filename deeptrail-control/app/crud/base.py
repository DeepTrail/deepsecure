import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import Base # Correct path to the declarative base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

logger = logging.getLogger(__name__)

# Custom encoder to handle bytes (e.g., encode as base64)
def bytes_encoder(obj):
    if isinstance(obj, bytes):
        # Decide how to represent bytes: base64 is common for JSON
        import base64
        return base64.b64encode(obj).decode('utf-8')
    # For other types, raise TypeError so default handling continues
    raise TypeError

CUSTOM_ENCODERS = {bytes: bytes_encoder}

class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**

        * `model`: A SQLAlchemy model class
        * `schema`: A Pydantic model (schema) class
        """
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        try:
            # Assuming the primary key column is named 'id'
            # If it's different (like 'agent_id' or 'credential_id'),
            # this method might need to be overridden in subclasses or made more generic
            pk = getattr(self.model, 'id', None) # Default check for 'id'
            if pk is None:
                 # Try common alternatives or raise error if primary key name is unknown
                 pk_name = 'agent_id' if hasattr(self.model, 'agent_id') else 'credential_id' if hasattr(self.model, 'credential_id') else None
                 if pk_name:
                     pk = getattr(self.model, pk_name)
                 else:
                     logger.error(f"Could not determine primary key for model {self.model.__name__} in CRUDBase.get")
                     raise AttributeError(f"CRUDBase.get could not determine primary key for {self.model.__name__}")

            return db.query(self.model).filter(pk == id).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error occurred while getting {self.model.__name__} by id {id}: {e}")
            return None
        except AttributeError as ae:
             logger.error(f"Attribute error during get: {ae}")
             return None # Or re-raise

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        try:
            return db.query(self.model).offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Database error occurred while getting multiple {self.model.__name__}s: {e}")
            return []

    # Default create method - may be overridden by subclasses (like CRUDCredential)
    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        try:
            obj_in_data = jsonable_encoder(obj_in)
            db_obj = self.model(**obj_in_data)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            logger.error(f"Database error occurred during creation of {self.model.__name__}: {e}")
            db.rollback()
            raise

    def update(
        self, db: Session, *, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        try:
            # Use jsonable_encoder on the *input* data, not the db_obj
            if isinstance(obj_in, dict):
                update_data = obj_in
            else:
                # Use exclude_unset=True to only update fields explicitly passed
                update_data = jsonable_encoder(
                    obj_in, # Encode the input schema/dict
                    exclude_unset=True,
                    custom_encoder=CUSTOM_ENCODERS # Use custom encoder if needed for input
                )

            # Iterate through the fields of the *database object*
            # and update them if the corresponding key exists in update_data
            current_obj_data = jsonable_encoder(db_obj, custom_encoder=CUSTOM_ENCODERS)
            for field in current_obj_data:
                if field in update_data:
                    setattr(db_obj, field, update_data[field])

            db.add(db_obj) # Add the existing object back to the session to mark it dirty
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            # Attempt to get primary key for logging
            pk_value = getattr(db_obj, 'id', getattr(db_obj, 'agent_id', getattr(db_obj, 'credential_id', 'UNKNOWN_ID')))
            logger.error(f"Database error occurred during update of {self.model.__name__} {pk_value}: {e}")
            db.rollback()
            raise

    def remove(self, db: Session, *, id: Any) -> Optional[ModelType]:
        """Removes an object by its primary key."""
        try:
            # Use the improved get method to find the object
            obj = self.get(db=db, id=id)
            if obj:
                db.delete(obj)
                db.commit()
                logger.info(f"Successfully removed {self.model.__name__} with id {id}")
            else:
                logger.warning(f"Attempted to remove non-existent {self.model.__name__} with id {id}")
            return obj
        except SQLAlchemyError as e:
            logger.error(f"Database error occurred during removal of {self.model.__name__} {id}: {e}")
            db.rollback()
            raise 