from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps

router = APIRouter()


@router.get("/", response_model=List[schemas.AttestationPolicy])
def read_attestation_policies(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> List[models.AttestationPolicy]:
    """
    Retrieve attestation policies.
    """
    policies = crud.attestation_policy.get_multi(db, skip=skip, limit=limit)
    return policies


@router.post("/", response_model=schemas.AttestationPolicy)
def create_attestation_policy(
    *,
    db: Session = Depends(deps.get_db),
    policy_in: schemas.AttestationPolicyCreate,
) -> models.AttestationPolicy:
    """
    Create new attestation policy.
    """
    policy = crud.attestation_policy.create(db, obj_in=policy_in)
    return policy


@router.get("/{policy_id}", response_model=schemas.AttestationPolicy)
def read_attestation_policy(
    *,
    db: Session = Depends(deps.get_db),
    policy_id: uuid.UUID,
) -> models.AttestationPolicy:
    """
    Get attestation policy by ID.
    """
    policy = crud.attestation_policy.get(db=db, id=policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Attestation policy not found")
    return policy


@router.put("/{policy_id}", response_model=schemas.AttestationPolicy)
def update_attestation_policy(
    *,
    db: Session = Depends(deps.get_db),
    policy_id: uuid.UUID,
    policy_in: schemas.AttestationPolicyUpdate,
) -> models.AttestationPolicy:
    """
    Update an attestation policy.
    """
    policy = crud.attestation_policy.get(db=db, id=policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Attestation policy not found")
    policy = crud.attestation_policy.update(db=db, db_obj=policy, obj_in=policy_in)
    return policy


@router.delete("/{policy_id}", response_model=schemas.AttestationPolicy)
def delete_attestation_policy(
    *,
    db: Session = Depends(deps.get_db),
    policy_id: uuid.UUID,
) -> models.AttestationPolicy:
    """
    Delete an attestation policy.
    """
    policy = crud.attestation_policy.get(db=db, id=policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Attestation policy not found")
    policy = crud.attestation_policy.remove(db=db, id=policy_id)
    return policy 