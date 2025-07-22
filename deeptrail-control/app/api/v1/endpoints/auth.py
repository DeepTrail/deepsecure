from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import schemas, crud
from app.api import deps
from app.core import security
import base64
from app.schemas.auth import KubernetesBootstrapRequest, AWSBootstrapRequest, AzureBootstrapRequest, DockerBootstrapRequest, BootstrapResponse
from app.core.config import settings
from app.services.bootstrap_service import bootstrap_service
import httpx
import uuid
from app.core.exceptions import TokenValidationError, PolicyNotFoundError, ExternalServiceError, NetworkTimeoutError, ConfigurationError, BootstrapError
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


router = APIRouter()
# bootstrap_service is already imported as singleton instance from app.services.bootstrap_service

@router.post("/challenge", response_model=schemas.ChallengeResponse)
def request_challenge(
    *,
    db: deps.DbDep,
    challenge_request: schemas.ChallengeRequest
):
    """
    Generate and return a single-use challenge nonce for an agent to sign.
    """
    agent = crud.agent.get_by_agent_id(db, agent_id=challenge_request.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    # Create and store a new nonce for this agent
    nonce_obj = crud.nonce.create_for_agent(db, agent_id=agent.agent_id)
    
    return schemas.ChallengeResponse(nonce=nonce_obj.nonce)

@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    *,
    db: deps.DbDep,
    token_request: schemas.TokenRequest
):
    """
    Authenticate an agent by verifying a signed nonce and return a JWT access token.
    """
    # 1. Retrieve the agent's public key
    agent = crud.agent.get_by_agent_id(db, agent_id=token_request.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # 2. Check for a valid, unexpired nonce and consume it
    db_nonce = crud.nonce.get_and_delete(db, nonce=token_request.nonce, agent_id=token_request.agent_id)
    if not db_nonce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already used nonce.",
        )
        
    # 3. Verify the signature against the nonce
    try:
        is_valid_signature = security.verify_signature(
            public_key_bytes=agent.public_key,
            message=token_request.nonce,
            signature_b64=token_request.signature
        )
    except Exception:
        # Broad exception to catch any potential crypto errors
        is_valid_signature = False

    if not is_valid_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Aggregate permissions from all policies associated with the agent
    policies = crud.policy.get_multi_by_agent(db, agent_id=agent.agent_id)
    all_actions = set()
    all_resources = set()
    for p in policies:
        if p.effect == "allow":
            for action in p.actions:
                all_actions.add(action)
            for resource in p.resources:
                all_resources.add(resource)

    # Convert sets to lists for JWT encoding
    scope_actions = list(all_actions) if all_actions else ["*"]
    scope_resources = list(all_resources) if all_resources else ["*"]

    # Generate JWT token with agent claims and permissions
    access_token = security.create_access_token(
        subject=agent.agent_id,
        actions=scope_actions,
        resources=scope_resources
    )

    return schemas.Token(access_token=access_token, token_type="bearer") 


@router.post("/bootstrap/kubernetes", response_model=BootstrapResponse)
def bootstrap_kubernetes(
    *,
    db: deps.DbDep,
    bootstrap_request: KubernetesBootstrapRequest,
):
    """
    Bootstrap an agent identity using a Kubernetes Service Account Token.
    Enhanced with comprehensive error handling and structured error responses.
    """
    correlation_id = str(uuid.uuid4())
    logger.info(f"[{correlation_id}] Starting Kubernetes bootstrap request")
    
    try:
        # Use the bootstrap service to handle the complete flow
        response = bootstrap_service.bootstrap_kubernetes_agent(
            db=db,
            token=bootstrap_request.token
        )
        
        logger.info(f"[{correlation_id}] Kubernetes bootstrap completed successfully")
        return response
        
    except TokenValidationError as e:
        logger.warning(f"[{correlation_id}] Token validation failed: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_validation_failed",
                "message": e.message,
                "error_code": e.error_code,
                "platform": e.platform,
                "validation_step": getattr(e, 'validation_step', None),
                "correlation_id": correlation_id
            }
        )
    except PolicyNotFoundError as e:
        logger.warning(f"[{correlation_id}] Policy not found: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "policy_not_found",
                "message": e.message,
                "error_code": e.error_code,
                "platform": e.platform,
                "selector": e.details.get("selector"),
                "correlation_id": correlation_id
            }
        )
    except ExternalServiceError as e:
        logger.error(f"[{correlation_id}] External service error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "external_service_error",
                "message": "External service temporarily unavailable",
                "error_code": e.error_code,
                "service": e.service_name,
                "correlation_id": correlation_id
            }
        )
    except NetworkTimeoutError as e:
        logger.error(f"[{correlation_id}] Network timeout: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": "network_timeout",
                "message": e.message,
                "error_code": e.error_code,
                "timeout_seconds": e.timeout_seconds,
                "correlation_id": correlation_id
            }
        )
    except ConfigurationError as e:
        logger.error(f"[{correlation_id}] Configuration error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "configuration_error",
                "message": "Service configuration error",
                "error_code": e.error_code,
                "correlation_id": correlation_id
            }
        )
    except BootstrapError as e:
        logger.error(f"[{correlation_id}] Bootstrap error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "bootstrap_error",
                "message": e.message,
                "error_code": e.error_code,
                "platform": e.platform,
                "correlation_id": correlation_id
            }
        )
    except Exception as e:
        logger.error(f"[{correlation_id}] Unexpected error during bootstrap: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
                "error_code": "INTERNAL_ERROR",
                "correlation_id": correlation_id
            }
        )


@router.post("/bootstrap/aws", response_model=BootstrapResponse)
def bootstrap_aws(
    *,
    db: deps.DbDep,
    bootstrap_request: AWSBootstrapRequest,
):
    """
    Bootstrap an agent identity using an AWS STS GetCallerIdentity token.
    """
    try:
        # Use the bootstrap service to handle the complete flow
        response = bootstrap_service.bootstrap_aws_agent(
            db=db,
            token=bootstrap_request.token
        )
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bootstrap failed: {str(e)}"
        )


@router.post("/bootstrap/azure", response_model=BootstrapResponse)
def bootstrap_azure(
    *,
    db: deps.DbDep,
    bootstrap_request: AzureBootstrapRequest,
):
    """
    Bootstrap an agent identity using an Azure Managed Identity token.
    """
    try:
        # Use the bootstrap service to handle the complete flow
        response = bootstrap_service.bootstrap_azure_agent(
            db=db,
            token=bootstrap_request.token
        )
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bootstrap failed: {str(e)}"
        )


@router.post("/bootstrap/docker", response_model=BootstrapResponse)
def bootstrap_docker(
    *,
    db: deps.DbDep,
    bootstrap_request: DockerBootstrapRequest,
):
    """
    Bootstrap an agent identity using Docker container identity.
    """
    try:
        # Use the bootstrap service to handle the complete flow
        response = bootstrap_service.bootstrap_docker_agent(
            db=db,
            container_id=bootstrap_request.container_id,
            runtime_token=bootstrap_request.runtime_token
        )
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bootstrap failed: {str(e)}"
        ) 