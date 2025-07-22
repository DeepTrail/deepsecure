from fastapi import APIRouter

from app.api.v1.endpoints import agents, auth, vault, policies, delegation, internal, attestation_policies, bootstrap

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(delegation.router, prefix="/auth", tags=["auth"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(vault.router, prefix="/vault", tags=["vault"])
api_router.include_router(policies.router, prefix="/policies", tags=["policies"])
api_router.include_router(
    attestation_policies.router,
    prefix="/policies/attestation",
    tags=["policies"],
)
api_router.include_router(internal.router, prefix="/internal", tags=["internal"], include_in_schema=False)
api_router.include_router(bootstrap.router, prefix="/bootstrap", tags=["bootstrap"]) 