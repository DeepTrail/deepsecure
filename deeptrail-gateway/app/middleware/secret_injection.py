"""
Secret Injection Middleware for DeepTrail Gateway

Core PEP Functionality:
This middleware injects secrets (API keys, tokens) into outbound requests
to external services, keeping credentials centralized and secure.

The middleware implements split-key secret management:
1. Fetches share_1 from the Control Plane
2. Retrieves share_2 from local Redis storage
3. Reassembles the secret using Shamir's Secret Sharing
4. Injects the reassembled secret into the request headers
5. Clears the secret from memory after injection
"""

import logging
from typing import Optional, Dict, Any
import httpx
from urllib.parse import urlparse

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.datastructures import MutableHeaders

from sslib import shamir

from ..core.proxy_config import config
from ..core.share_storage import ShareStorageManager

logger = logging.getLogger(__name__)


class SecretInjectionMiddleware(BaseHTTPMiddleware):
    """
    Core PEP: Secret injection middleware with split-key architecture.
    
    This middleware retrieves secret shares from the Control Plane and
    local Redis storage, reassembles them using Shamir's Secret Sharing,
    and injects the resulting secret into outbound requests.
    """
    
    def __init__(self, app: ASGIApp, control_plane_url: str = "http://deeptrail-control:8000"):
        super().__init__(app)
        self.control_plane_url = control_plane_url
        self.bypass_paths = {"/", "/health", "/ready", "/metrics", "/config", "/docs", "/redoc", "/openapi.json"}
        
        # Initialize share storage for retrieving share_2
        try:
            self.share_storage = ShareStorageManager(
                redis_url=config.redis_url,
                encryption_key=config.internal_api_token
            )
        except Exception as e:
            logger.error(f"Failed to initialize share storage: {e}")
            self.share_storage = None
        
        logger.info("Secret injection middleware initialized")
        logger.info(f"Control plane URL: {control_plane_url}")
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and inject secrets if needed.
        """
        # Skip secret injection for health checks and docs
        if request.url.path in self.bypass_paths:
            return await call_next(request)
        
        # Skip secret injection for non-proxy requests
        if not request.url.path.startswith("/proxy"):
            return await call_next(request)
        
        # Get target URL from request
        target_url = request.headers.get("X-Target-Base-URL")
        if not target_url:
            # Let the request continue - validation will catch this
            return await call_next(request)
        
        # Get agent information
        agent_id = getattr(request.state, "agent_id", None)
        if not agent_id:
            # Let the request continue - JWT validation will catch this
            return await call_next(request)
        
        # Get secret name from header (if specified)
        secret_name = request.headers.get("X-Deeptrail-Secret-Name")
        
        # Inject secrets
        try:
            await self._inject_secrets(request, target_url, agent_id, secret_name)
            logger.info(f"Secret injection completed for agent {agent_id} to {target_url}")
            
        except Exception as e:
            logger.error(f"Secret injection error: {e}", exc_info=True)
            # Continue without secrets (let the target service handle auth errors)
        
        # Continue with request processing
        return await call_next(request)
    
    async def _inject_secrets(self, request: Request, target_url: str, agent_id: str, secret_name: Optional[str] = None):
        """
        Core PEP: Inject secrets using split-key architecture.
        
        This method:
        1. Determines the secret to use based on domain or explicit secret name
        2. Fetches share_1 from the Control Plane
        3. Retrieves share_2 from local Redis storage
        4. Reassembles the secret using Shamir's Secret Sharing
        5. Injects the secret into the request headers
        """
        
        # Parse target URL to get domain
        parsed_url = urlparse(target_url)
        target_domain = parsed_url.netloc.lower()
        
        # Use explicit secret name if provided, otherwise try to determine from domain
        if not secret_name:
            # Map common domains to secret names
            domain_to_secret = {
                "api.openai.com": "openai-api-key",
                "api.anthropic.com": "anthropic-api-key",
            }
            secret_name = domain_to_secret.get(target_domain)
        
        if not secret_name:
            logger.debug(f"No secret name determined for domain {target_domain}")
            return
        
        # Reassemble the secret from shares
        reassembled_secret = await self._reassemble_secret(secret_name)
        
        if not reassembled_secret:
            logger.warning(f"Could not reassemble secret for '{secret_name}'")
            return
        
        # Inject the secret as Bearer token (most common case for API keys)
        self._inject_bearer_token(request, reassembled_secret)
        logger.debug(f"Injected secret for {target_domain}")
    
    async def _reassemble_secret(self, secret_name: str) -> Optional[str]:
        """
        Reassemble a secret from its shares using Shamir's Secret Sharing.
        
        Args:
            secret_name: Name of the secret to reassemble
            
        Returns:
            The reassembled secret string, or None if reassembly fails
        """
        try:
            # 1. Fetch share_1 from Control Plane
            share_1_data = await self._fetch_share_from_control_plane(secret_name)
            if not share_1_data:
                logger.error(f"Failed to fetch share_1 for '{secret_name}' from control plane")
                return None
            
            share_1 = share_1_data.get("share_1")
            prime_mod_hex = share_1_data.get("prime_mod")
            
            # 2. Retrieve share_2 from local Redis storage
            if not self.share_storage:
                logger.error("Share storage not initialized")
                return None
            
            share_2_data = await self.share_storage.retrieve_share(secret_name)
            if not share_2_data:
                logger.error(f"Failed to retrieve share_2 for '{secret_name}' from Redis")
                return None
            
            share_2 = share_2_data.get("share_value")
            gateway_prime_mod = share_2_data.get("prime_mod")
            
            # Use control plane's prime_mod if available, fallback to gateway's
            if not prime_mod_hex and gateway_prime_mod:
                prime_mod_hex = gateway_prime_mod
            
            if not share_1 or not share_2:
                logger.error(f"Missing shares for '{secret_name}'")
                return None
            
            # 3. Prepare shares for Shamir reconstruction
            # Shares are stored as [index, hex_string]
            share_1_bytes = (share_1[0], bytes.fromhex(share_1[1]))
            share_2_bytes = (share_2[0], bytes.fromhex(share_2[1]))
            
            # Convert prime_mod from hex to bytes
            if prime_mod_hex:
                prime_mod = bytes.fromhex(prime_mod_hex)
            else:
                # Fallback: estimate prime_mod (less reliable)
                share_len = len(share_1_bytes[1])
                prime_mod = b'\x07' + b'\xff' * (share_len - 1)
                logger.warning(f"Prime modulus not stored for '{secret_name}'. Using estimate.")
            
            # 4. Reconstruct the secret using Shamir's algorithm
            recovery_data = {
                'required_shares': 2,
                'prime_mod': prime_mod,
                'shares': [share_1_bytes, share_2_bytes]
            }
            
            recovered_secret = shamir.recover_secret(recovery_data)
            
            logger.info(f"Successfully reassembled secret for {secret_name}")
            return recovered_secret.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error reassembling secret '{secret_name}': {e}", exc_info=True)
            return None
    
    async def _fetch_share_from_control_plane(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch share_1 and prime_mod from the Control Plane.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Dictionary with share_1 and prime_mod, or None if fetch fails
        """
        try:
            # NOTE: The internal endpoint is at /api/v1/internal/secrets/{name}/share
            url = f"{self.control_plane_url}/api/v1/internal/secrets/{secret_name}/share"
            headers = {
                "X-Internal-API-Token": config.internal_api_token
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching share_1 for '{secret_name}': {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error fetching share_1 for '{secret_name}': {e}")
            return None
    
    def _inject_bearer_token(self, request: Request, token: str):
        """
        Inject Bearer token into Authorization header using MutableHeaders.
        
        This uses Starlette's MutableHeaders to properly modify the request
        scope headers, ensuring the change propagates to downstream handlers.
        """
        # Mask the token for logging
        masked_token = token[:10] + "..." if len(token) > 10 else token
        logger.info(f"Injecting Bearer token (masked: {masked_token})")
        
        # Use MutableHeaders to properly modify scope headers
        # This is the Starlette-recommended way to modify request headers
        mutable_headers = MutableHeaders(scope=request.scope)
        mutable_headers["Authorization"] = f"Bearer {token}"
        
        logger.debug(f"Headers after injection: Authorization header set to Bearer {masked_token}")
    
    def _inject_api_key_header(self, request: Request, header_name: str, api_key: str):
        """Inject API key into specified header using MutableHeaders."""
        mutable_headers = MutableHeaders(scope=request.scope)
        mutable_headers[header_name] = api_key
    
    def _inject_basic_auth(self, request: Request, credentials: str):
        """Inject Basic authentication header using MutableHeaders."""
        mutable_headers = MutableHeaders(scope=request.scope)
        mutable_headers["Authorization"] = f"Basic {credentials}"
