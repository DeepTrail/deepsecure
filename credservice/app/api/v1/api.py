from fastapi import APIRouter

# Import endpoint modules
from app.api.v1.endpoints import agents
from app.api.v1.endpoints import credentials # Add credentials router
from app.api.v1.endpoints import login # Add login router
# from app.api.v1.endpoints import login # Add later for token endpoint

api_router = APIRouter()

# Include routers from endpoint modules
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(credentials.router, prefix="/credentials", tags=["credentials"])
api_router.include_router(login.router, prefix="/login", tags=["login"])
# api_router.include_router(login.router, prefix="/login", tags=["login"]) # Add later 