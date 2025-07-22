import uuid
from typing import List

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.policy import Policy
from app.schemas.policy import PolicyCreate, PolicyUpdate


class CRUDPolicy(CRUDBase[Policy, PolicyCreate, PolicyUpdate]):
    def get_multi_by_agent(
        self, db: Session, *, agent_id: str
    ) -> List[Policy]:
        return db.query(self.model).filter(self.model.agent_id == agent_id).all()


policy = CRUDPolicy(Policy) 