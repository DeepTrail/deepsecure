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
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from typing import Annotated, Generator
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.db.session import SessionLocal # Import the session factory

# --- Database Dependency ---

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DbDep = Annotated[Session, Depends(get_db)]

# --- Authentication Dependencies ---

# Define the OAuth2 scheme, pointing to the future token URL
# This URL doesn't have to exist yet, but it's where clients *should* get tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")

def get_current_identity(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    """Dependency to get the current identity (e.g., agent_id) from the token.

    Raises:
        HTTPException 401: If token is invalid, expired, or missing credentials.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = security.decode_token(token)
    if payload is None:
        raise credentials_exception

    identity: str | None = payload.get("sub")
    if identity is None:
        # Should not happen if token creation is correct, but good to check
        raise credentials_exception

    # Here you could add logic to fetch the agent/user from DB if needed
    # For now, we just return the identity string (agent_id)
    return identity

# Type alias for the dependency
CurrentUser = Annotated[str, Depends(get_current_identity)]

# You can add more dependencies here later, e.g., for role checks
# def get_current_active_admin(...): ... 