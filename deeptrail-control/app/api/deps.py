"""API endpoint dependencies.

Functions defined here can be used with FastAPI's dependency injection system
to provide shared logic or resources (like database sessions) to endpoints.
"""

# Placeholder for dependency injection functions
# Example:
# from app.db.session import SessionLocal
#
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from typing import Annotated, Generator
from sqlalchemy.orm import Session
import logging # Import logging

from app.core.config import settings
from app.db.session import SessionLocal # Import the session factory
from app.core import security
from app import crud, models


logger = logging.getLogger(__name__) # Define logger for this module

# --- Database Dependency ---

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DbDep = Annotated[Session, Depends(get_db)]

# --- Authentication Dependency (API Key) ---

# Define the header scheme
api_key_header_scheme = APIKeyHeader(name="Authorization", auto_error=False) # auto_error=False to handle missing header manually

def verify_api_key(api_key_header: str = Depends(api_key_header_scheme)):
    """Dependency to verify the static API key in the Authorization header.

    Expects header format: "Authorization: Bearer <YOUR_STATIC_TOKEN>"
    """
    if not api_key_header or not api_key_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Authorization header (Bearer token expected)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = api_key_header.split(" ")[1]

    # Temporary debug logging (disabled)
    # logger.info(f"[AUTH_DEBUG] Token received by deeptrail-control: '{token}'")
    # logger.info(f"[AUTH_DEBUG] Token expected by deeptrail-control (settings.BACKEND_API_TOKEN): '{settings.BACKEND_API_TOKEN}'")

    if token != settings.BACKEND_API_TOKEN:
        # logger.warning(f"[AUTH_DEBUG] Token mismatch: Received '{token}' vs Expected '{settings.BACKEND_API_TOKEN}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # logger.info(f"[AUTH_DEBUG] Token validation successful for: '{token}'")
    return

# Type alias for the dependency
APIKeyDep = Depends(verify_api_key)

# --- END Authentication Dependencies ---

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token")

def get_current_active_agent(
    db: DbDep, token: str = Depends(oauth2_scheme)
) -> models.Agent:
    """
    Dependency to get the current authenticated agent from a JWT token.
    
    1. Decodes the JWT token from the Authorization header.
    2. Validates the token's signature and expiration.
    3. Fetches the agent from the database based on the 'agent_id' claim.
    4. Returns the active agent object.
    
    Raises HTTPException for any validation failures.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = security.decode_token(token)
    if payload is None:
        raise credentials_exception
        
    agent_id = payload.get("agent_id")
    if agent_id is None:
        raise credentials_exception
        
    agent = crud.agent.get(db, id=agent_id)
    if agent is None:
        raise credentials_exception
        
    # TODO: Add check for agent.is_active if you have such a field
    # if not agent.is_active:
    #     raise HTTPException(status_code=400, detail="Inactive agent")
        
    return agent


# (Removed commented out OAuth2 code)

# You can add more dependencies here later, e.g., for role checks
# def get_current_active_admin(...): ... 