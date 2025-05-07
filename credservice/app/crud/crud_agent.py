from typing import Optional
import base64
import struct # Import struct
import logging # Import logging
import traceback # Import traceback

from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder

from app.crud.base import CRUDBase
from app.models.agent import Agent as AgentModel # Rename import to avoid clash
from app.schemas.agent import AgentCreate, Agent as AgentSchema # Rename import

# Get logger for this module
logger = logging.getLogger(__name__)

# Use AgentSchema for UpdateSchemaType for now
class CRUDAgent(CRUDBase[AgentModel, AgentCreate, AgentSchema]):
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

    def create(self, db: Session, *, obj_in: AgentCreate) -> AgentModel:
        """
        Creates a new Agent in the database.
        The `current_public_key` in `obj_in` is expected to be raw bytes
        as processed by the AgentCreate schema validator.
        """
        logger.info(f"CRUD: Attempting to create agent with agent_id: {obj_in.agent_id}")

        if not isinstance(obj_in.current_public_key, bytes) or len(obj_in.current_public_key) != 32:
            error_message = (
                f"CRUD create: obj_in.current_public_key is not 32 bytes. \\n"
                f"Type: {type(obj_in.current_public_key)}, \\n"
                f"Length: {len(obj_in.current_public_key) if isinstance(obj_in.current_public_key, bytes) else 'N/A'}. \\n"
                f"This indicates an issue with the schema validator not returning raw bytes correctly."
            )
            logger.error(error_message)
            raise ValueError("CRUDAgent.create received invalid public key (not 32 bytes) from schema validator.")

        public_key_bytes_for_db = obj_in.current_public_key

        db_obj = self.model(
            agent_id=obj_in.agent_id,
            current_public_key=public_key_bytes_for_db
        )
        
        info_message = (
            f"Creating AgentModel instance with agent_id={db_obj.agent_id}, \\n"
            f"and current_public_key (bytes) of length {len(db_obj.current_public_key)}\""
        )
        logger.info(info_message)

        db.add(db_obj)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Database commit failed during agent creation for {obj_in.agent_id}: {e}", exc_info=True)
            raise
        db.refresh(db_obj)
        logger.info(f"Successfully created and refreshed agent: {db_obj.agent_id}")
        return db_obj

# Instantiate with the SQLAlchemy MODEL class
agent = CRUDAgent(AgentModel) 