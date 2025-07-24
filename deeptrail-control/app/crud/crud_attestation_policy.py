from app.crud.base import CRUDBase
from app.models.attestation_policy import AttestationPolicy
from app.schemas.attestation_policy import (
    AttestationPolicyCreate,
    AttestationPolicyUpdate,
)


class CRUDAttestationPolicy(
    CRUDBase[AttestationPolicy, AttestationPolicyCreate, AttestationPolicyUpdate]
):
    pass


attestation_policy = CRUDAttestationPolicy(AttestationPolicy) 