from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps

router = APIRouter()

@router.get("/", response_model=List[schemas.Policy])
def read_policies(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> List[models.Policy]:
    """
    Retrieve policies.
    """
    policies = crud.policy.get_multi(db, skip=skip, limit=limit)
    return policies

@router.post("/", response_model=schemas.Policy)
def create_policy(
    *,
    db: Session = Depends(deps.get_db),
    policy_in: schemas.PolicyCreate,
) -> models.Policy:
    """
    Create new policy.
    """
    # Check if agent exists
    agent = crud.agent.get(db=db, id=policy_in.agent_id)
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent with id {policy_in.agent_id} not found",
        )
    policy = crud.policy.create(db, obj_in=policy_in)
    return policy

@router.get("/{policy_id}", response_model=schemas.Policy)
def read_policy(
    *,
    db: Session = Depends(deps.get_db),
    policy_id: uuid.UUID,
) -> models.Policy:
    """
    Get policy by ID.
    """
    policy = crud.policy.get(db=db, id=policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy

@router.put("/{policy_id}", response_model=schemas.Policy)
def update_policy(
    *,
    db: Session = Depends(deps.get_db),
    policy_id: uuid.UUID,
    policy_in: schemas.PolicyUpdate,
) -> models.Policy:
    """
    Update a policy.
    """
    policy = crud.policy.get(db=db, id=policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    policy = crud.policy.update(db=db, db_obj=policy, obj_in=policy_in)
    return policy

@router.delete("/{policy_id}", response_model=schemas.Policy)
def delete_policy(
    *,
    db: Session = Depends(deps.get_db),
    policy_id: uuid.UUID,
) -> models.Policy:
    """
    Delete a policy.
    """
    policy = crud.policy.get(db=db, id=policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    policy = crud.policy.remove(db=db, id=policy_id)
    return policy 