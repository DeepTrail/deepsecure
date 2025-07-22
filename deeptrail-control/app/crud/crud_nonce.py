from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timedelta

from .base import CRUDBase
from app.models.nonce import Nonce
from app.schemas.nonce import NonceCreate, NonceUpdate

class CRUDNonce(CRUDBase[Nonce, NonceCreate, NonceUpdate]):
    def create_for_agent(self, db: Session, *, agent_id: str) -> Nonce:
        """
        Creates a new nonce for a given agent.
        """
        nonce_obj = Nonce(
            agent_id=agent_id,
            nonce=uuid.uuid4().hex,
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        db.add(nonce_obj)
        db.commit()
        db.refresh(nonce_obj)
        return nonce_obj

    def get_and_delete(self, db: Session, *, nonce: str, agent_id: str) -> Nonce | None:
        """
        Retrieves a nonce if it's valid and unexpired, then deletes it to prevent reuse.
        """
        now = datetime.utcnow()
        nonce_obj = db.query(Nonce).filter(
            Nonce.nonce == nonce,
            Nonce.agent_id == agent_id,
            Nonce.expires_at > now
        ).first()

        if nonce_obj:
            db.delete(nonce_obj)
            db.commit()
        
        return nonce_obj

nonce = CRUDNonce(Nonce) 