"""
JWT Validation Middleware for DeepTrail Gateway

Core PEP Functionality:
This middleware validates JWT tokens from the control plane to ensure
only authenticated agents can access the proxy.

Key Features:
- Proper JWT signature validation using shared SECRET_KEY
- JWT claims validation (exp, iat, agent_id)
- Token expiration and timing validation
- Comprehensive error handling and logging
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import JSONResponse
from jose import jwt, JWTError

from ..core.proxy_config import config

logger = logging.getLogger(__name__)


class JWTValidationError(Exception):
    """Custom exception for JWT validation errors."""
    def __init__(self, status_code: int, detail: str, headers: Optional[Dict[str, str]] = None):
        self.status_code = status_code
        self.detail = detail
        self.headers = headers or {}
        super().__init__(detail)


class JWTValidationMiddleware(BaseHTTPMiddleware):
    """
    JWT validation middleware with proper signature verification.
    
    This middleware validates JWT tokens using the shared SECRET_KEY
    to ensure only authenticated agents can access the proxy.
    """
    
    def __init__(self, app: ASGIApp, control_plane_url: str = "http://deeptrail-control:8000"):
        super().__init__(app)
        self.control_plane_url = control_plane_url
        self.bypass_paths = {"/", "/health", "/ready", "/metrics", "/config", "/docs", "/redoc", "/openapi.json"}
        
        # JWT configuration from proxy config
        self.jwt_secret_key = config.security.jwt_secret_key
        self.jwt_algorithm = config.security.jwt_algorithm
        self.jwt_access_token_expire_minutes = config.security.jwt_access_token_expire_minutes
        
        logger.info("JWT validation middleware initialized")
        logger.info(f"Control plane URL: {control_plane_url}")
        logger.info(f"JWT algorithm: {self.jwt_algorithm}")
        logger.info(f"JWT token expiration: {self.jwt_access_token_expire_minutes} minutes")
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and validate JWT if required.
        """
        # Skip JWT validation for health checks and docs
        if request.url.path in self.bypass_paths:
            return await call_next(request)
        
        # Skip JWT validation for non-proxy requests (for now)
        if not request.url.path.startswith("/proxy"):
            return await call_next(request)
        
        # Extract JWT token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning(f"Missing Authorization header for {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing Authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Parse Bearer token
        try:
            scheme, token = auth_header.split(" ", 1)
            if scheme.lower() != "bearer":
                raise ValueError("Invalid scheme")
        except ValueError:
            logger.warning(f"Invalid Authorization header format for {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid Authorization header format"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Validate JWT token
        try:
            jwt_payload = await self._validate_jwt_token(token)
            
            # Add validated agent information to request state
            request.state.agent_id = jwt_payload.get("agent_id")
            request.state.agent_permissions = jwt_payload.get("scope", "").split() if jwt_payload.get("scope") else []
            request.state.jwt_payload = jwt_payload
            
            logger.info(f"JWT validated for agent {request.state.agent_id}")
            
        except JWTValidationError as e:
            logger.warning(f"JWT validation failed: {e.detail}")
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
                headers=e.headers,
            )
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid JWT token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Continue with request processing
        return await call_next(request)
    
    async def _validate_jwt_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token with proper signature verification.
        
        This method validates the JWT token using the shared SECRET_KEY
        to ensure the token was issued by the trusted control plane.
        """
        try:
            # Decode and validate JWT token with signature verification
            payload = jwt.decode(
                token,
                self.jwt_secret_key,
                algorithms=[self.jwt_algorithm]
            )
            
            # Additional validation
            current_time = datetime.now(timezone.utc).timestamp()
            
            # Check required claims
            if "agent_id" not in payload:
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="JWT token missing agent_id claim"
                )
            
            # Check expiration (this is also done by jwt.decode, but we do it explicitly for better error messages)
            if "exp" in payload:
                if payload["exp"] < current_time:
                    raise JWTValidationError(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="JWT token expired"
                    )
            
            # Check not before
            if "nbf" in payload:
                if payload["nbf"] > current_time:
                    raise JWTValidationError(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="JWT token not yet valid"
                    )
            
            # Check issued at
            if "iat" in payload:
                if payload["iat"] > current_time:
                    raise JWTValidationError(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="JWT token issued in the future"
                    )
            
            logger.debug(f"JWT token validated successfully for agent {payload.get('agent_id')}")
            return payload
            
        except JWTError as e:
            # Handle JWT-specific errors
            error_msg = str(e)
            if "expired" in error_msg.lower():
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="JWT token expired"
                )
            elif "invalid" in error_msg.lower():
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid JWT token"
                )
            else:
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="JWT token validation failed"
                )
        except JWTValidationError:
            raise
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            raise JWTValidationError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid JWT token format"
            )
    
    # Methods for future enterprise enhancements
    async def _fetch_public_key(self) -> str:
        """For Future - Enterprise Grade: Fetch public key from control plane."""
        # This would be used for RSA/ECDSA signature validation
        # with public key cryptography instead of shared secrets
        pass
    
    async def _validate_jwt_with_public_key(self, token: str, public_key: str) -> bool:
        """For Future - Enterprise Grade: Validate JWT signature with public key."""
        # This would be used for RSA/ECDSA signature validation
        pass
    
    async def _check_token_revocation(self, token: str) -> bool:
        """For Future - Enterprise Grade: Check if token is revoked."""
        # This would check against a revocation list or cache
        pass
    
    async def _refresh_token_if_needed(self, token: str) -> Optional[str]:
        """For Future - Enterprise Grade: Refresh token if it's about to expire."""
        # This would automatically refresh tokens that are close to expiration
        pass 