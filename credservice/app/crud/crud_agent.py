from typing import Optional, List, Any
import base64
import uuid # For generating agent_id
import logging
import traceback # Import traceback

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError # For handling unique constraint violations
from fastapi.encoders import jsonable_encoder

from app.crud.base import CRUDBase, UpdateSchemaType # Import UpdateSchemaType
from app.models.agent import Agent as AgentModel # Rename import to avoid clash
from app.schemas.agent import AgentCreate, AgentUpdate, Agent as AgentSchema # Rename import

# Get logger for this module
logger = logging.getLogger(__name__)

class CRUDAgent(CRUDBase[AgentModel, AgentCreate, AgentUpdate]): # Use AgentUpdate for UpdateSchemaType
    """CRUD operations for Agent models.

    Handles the specific logic for creating agents, including parsing and
    storing the public key bytes from the input SSH-formatted string.
    """
    def get_by_agent_id(self, db: Session, *, agent_id: str) -> Optional[AgentModel]:
        """Fetch an agent by its unique agent_id.

        Args:
            db: The database session.
            agent_id: The agent ID to search for.

        Returns:
            The AgentModel instance if found, otherwise None.
        """
        return db.query(self.model).filter(self.model.agent_id == agent_id).first()

    def get_by_public_key(self, db: Session, *, public_key_bytes: bytes) -> Optional[AgentModel]:
        """Fetch an agent by its unique public key bytes."""
        return db.query(self.model).filter(self.model.current_public_key == public_key_bytes).first()

    def create(self, db: Session, *, obj_in: AgentCreate) -> AgentModel:
        """
        Creates a new Agent in the database.
        - agent_id is generated here.
        - obj_in.public_key is expected to be raw bytes (validated by AgentCreate schema).
        - name and description are taken from obj_in.
        - status defaults to 'active' from the model.
        """
        # The obj_in.public_key should already be bytes due to Pydantic validation
        if not isinstance(obj_in.public_key, bytes) or len(obj_in.public_key) != 32:
            error_message = (
                f"CRUDAgent.create received invalid public key (not 32 bytes) from input schema. "
                f"Type: {type(obj_in.public_key)}, Length: {len(obj_in.public_key) if isinstance(obj_in.public_key, bytes) else 'N/A'}."
            )
            logger.error(error_message)
            # This should ideally be caught by Pydantic, but good to double check.
            raise ValueError("Public key for agent creation must be 32 bytes after base64 decoding.")

        # Check if public key already exists to prevent IntegrityError for unique constraint
        existing_agent_by_key = self.get_by_public_key(db, public_key_bytes=obj_in.public_key)
        if existing_agent_by_key:
            logger.warning(f"Attempt to create agent with already existing public key. Agent ID: {existing_agent_by_key.agent_id}")
            raise IntegrityError(
                "Agent with this public key already exists.", 
                params=None, orig=None # Simulating IntegrityError structure
            )

        generated_agent_id = f"agent-{uuid.uuid4()}"
        logger.info(f"CRUD: Creating agent with generated agent_id: {generated_agent_id}, name: {obj_in.name}")

        db_obj_data = {
            "agent_id": generated_agent_id,
            "name": obj_in.name,
            "description": obj_in.description,
            "current_public_key": obj_in.public_key,
            # status will use the model's server_default ('active')
        }
        # db_obj = self.model(**jsonable_encoder(obj_in)) # Old way
        db_obj = self.model(**db_obj_data)

        db.add(db_obj)
        try:
            db.commit()
        except IntegrityError as e: # Catch unique constraint violations (e.g. agent_id somehow duplicated)
            db.rollback()
            logger.error(f"Database integrity error during agent creation for {generated_agent_id}: {e}", exc_info=True)
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Database commit failed during agent creation for {generated_agent_id}: {e}", exc_info=True)
            raise
        db.refresh(db_obj)
        logger.info(f"Successfully created and refreshed agent: {db_obj.agent_id}")
        return db_obj

    def update(
        self, 
        db: Session, 
        *, 
        db_obj: AgentModel, 
        obj_in: AgentUpdate # Use AgentUpdate schema
    ) -> AgentModel:
        """
        Updates an existing Agent in the database.
        Uses the generic update from CRUDBase.
        `obj_in` is an AgentUpdate schema, so only fields defined there are updated.
        """
        logger.info(f"CRUD: Attempting to update agent: {db_obj.agent_id}")
        # CRUDBase.update will handle converting obj_in (AgentUpdate schema) 
        # to a dict and applying only set fields.
        updated_db_obj = super().update(db, db_obj=db_obj, obj_in=obj_in)
        logger.info(f"Successfully updated agent: {updated_db_obj.agent_id}")
        return updated_db_obj
    
    # get_multi is inherited from CRUDBase
    # remove (by agent_id) is inherited from CRUDBase, relying on its get(id=agent_id) logic

# Instantiate with the SQLAlchemy MODEL class
agent = CRUDAgent(AgentModel) 