"""Endpoints for internal, service-to-service communication."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app import crud
from app.api import deps
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-Internal-API-Token", auto_error=True)

async def verify_internal_api_key(api_key: str = Security(api_key_header)):
    """Dependency to verify the internal API key."""
    if not api_key or api_key != settings.GATEWAY_INTERNAL_API_TOKEN:
        logger.warning("Invalid or missing internal API token received.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal API key"
        )
    return api_key

class SecretShareResponse(BaseModel):
    share_1: str
    target_base_url: Optional[str] = None

@router.get("/secrets/{secret_name}/share", response_model=SecretShareResponse)
def get_secret_share(
    secret_name: str,
    db: Session = Depends(deps.get_db),
    api_key: str = Depends(verify_internal_api_key)
):
    """
    Retrieves the control plane's share of a secret and its target_base_url.
    This is an internal-only endpoint for the gateway.
    """
    logger.info(f"Gateway request for share of secret: {secret_name}")
    secret = crud.secret.get_by_name(db, name=secret_name)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secret not found in control plane."
        )
    
    target_url = None
    if secret.metadata and "target_base_url" in secret.metadata:
        target_url = secret.metadata["target_base_url"]

    return SecretShareResponse(share_1=secret.share_1, target_base_url=target_url) 