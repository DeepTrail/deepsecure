"""Endpoints for internal, service-to-service communication."""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import Optional, List, Any
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
    share_1: Any  # Can be list [index, hex_string] or string
    prime_mod: Optional[str] = None  # Prime modulus as hex string for Shamir reassembly
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
    
    Returns:
        share_1: The control plane's share of the secret [index, hex_string]
        prime_mod: The prime modulus for Shamir secret recovery (hex string)
        target_base_url: The target URL for this secret's API
    """
    logger.info(f"Gateway request for share of secret: {secret_name}")
    secret = crud.secret.get_secret_by_name(db, name=secret_name)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secret not found in control plane."
        )
    
    # Parse share_1 from JSON string to list
    try:
        share_1_data = json.loads(secret.share_1) if isinstance(secret.share_1, str) else secret.share_1
    except json.JSONDecodeError:
        logger.error(f"Failed to parse share_1 for secret '{secret_name}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid share data in control plane."
        )
    
    # Get prime_mod from secret_metadata
    prime_mod = None
    target_url = None
    if secret.secret_metadata:
        prime_mod = secret.secret_metadata.get("_prime_mod")
        target_url = secret.secret_metadata.get("target_base_url")

    logger.debug(f"Returning share_1 and prime_mod for secret '{secret_name}'")
    return SecretShareResponse(share_1=share_1_data, prime_mod=prime_mod, target_base_url=target_url) 