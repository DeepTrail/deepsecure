from fastapi import APIRouter

# Import endpoint modules
from app.api.v1.endpoints import agents
# from app.api.v1.endpoints import credentials # No longer needed
from app.api.v1.endpoints import login # Keep login router
from app.api.v1.endpoints import vault # Import the new vault router
# from app.api.v1.endpoints import login # Add later for token endpoint

api_router = APIRouter()

# Include routers from endpoint modules
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
# api_router.include_router(credentials.router, prefix="/credentials", tags=["credentials"])
api_router.include_router(login.router, prefix="/login", tags=["login"])
# api_router.include_router(login.router, prefix="/login", tags=["login"]) # Add later 

# Decide if the old credentials router is still needed
# api_router.include_router(credentials.router, prefix="/credentials", tags=["credentials"])

# Include the new vault router with the /v1/vault prefix
api_router.include_router(vault.router, prefix="/vault", tags=["vault"]) 