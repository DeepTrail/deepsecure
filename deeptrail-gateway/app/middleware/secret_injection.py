"""
Secret Injection Middleware for DeepTrail Gateway

Core PEP Functionality:
This middleware injects secrets (API keys, tokens) into outbound requests
to external services, keeping credentials centralized and secure.

For Future - Enterprise Grade:
- Dynamic secret retrieval from multiple backends
- Secret rotation and lifecycle management
- Conditional secret injection based on policies
- Secret usage audit and monitoring
- Support for multiple authentication schemes
"""

import logging
from typing import Optional, Dict, Any, List
import json
from urllib.parse import urlparse

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class SecretInjectionMiddleware(BaseHTTPMiddleware):
    """
    Core PEP: Simple secret injection middleware.
    
    This middleware injects appropriate secrets into outbound requests
    based on the target URL and agent permissions.
    
    For Future - Enterprise Grade: Advanced secret management features will be added.
    """
    
    def __init__(self, app: ASGIApp, control_plane_url: str = "http://deeptrail-control:8000"):
        super().__init__(app)
        self.control_plane_url = control_plane_url
        self.bypass_paths = {"/", "/health", "/ready", "/metrics", "/config", "/docs", "/redoc", "/openapi.json"}
        
        # Core PEP: Simple secret store (in-memory for development)
        # For Future - Enterprise Grade: This will be replaced with proper secret management
        self.secret_store = {
            "api.openai.com": {
                "type": "bearer",
                "value": "OPENAI_API_KEY_PLACEHOLDER"
            },
            "httpbin.org": {
                "type": "none",
                "value": None
            },
            "jsonplaceholder.typicode.com": {
                "type": "none",
                "value": None
            }
        }
        
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
        
        # Inject secrets
        try:
            await self._inject_secrets(request, target_url, agent_id)
            logger.info(f"Secret injection completed for agent {agent_id} to {target_url}")
            
        except Exception as e:
            logger.error(f"Secret injection error: {e}")
            # For Future - Enterprise Grade: Decide whether to fail or continue
            # For now, continue without secrets (let the target service handle auth errors)
        
        # Continue with request processing
        return await call_next(request)
    
    async def _inject_secrets(self, request: Request, target_url: str, agent_id: str):
        """
        Core PEP: Basic secret injection.
        
        For Future - Enterprise Grade: This will be replaced with sophisticated
        secret management supporting multiple backends and rotation.
        """
        
        # Parse target URL
        parsed_url = urlparse(target_url)
        target_domain = parsed_url.netloc.lower()
        
        # Get secret for target domain
        secret_config = await self._get_secret_for_domain(target_domain, agent_id)
        
        if not secret_config:
            logger.debug(f"No secret configured for domain {target_domain}")
            return
        
        # Inject secret based on type
        secret_type = secret_config.get("type", "none")
        secret_value = secret_config.get("value")
        
        if secret_type == "bearer" and secret_value:
            # Inject Bearer token
            self._inject_bearer_token(request, secret_value)
            logger.debug(f"Injected Bearer token for {target_domain}")
            
        elif secret_type == "api_key" and secret_value:
            # Inject API key header
            api_key_header = secret_config.get("header", "X-API-Key")
            self._inject_api_key_header(request, api_key_header, secret_value)
            logger.debug(f"Injected API key header {api_key_header} for {target_domain}")
            
        elif secret_type == "basic" and secret_value:
            # Inject Basic auth
            self._inject_basic_auth(request, secret_value)
            logger.debug(f"Injected Basic auth for {target_domain}")
            
        elif secret_type == "none":
            logger.debug(f"No secret injection needed for {target_domain}")
            
        else:
            logger.warning(f"Unknown secret type '{secret_type}' for {target_domain}")
    
    async def _get_secret_for_domain(self, domain: str, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Core PEP: Get secret configuration for a domain.
        
        For Future - Enterprise Grade: This will fetch secrets from the control plane
        with proper access control and audit logging.
        """
        
        # Core PEP: Simple lookup in local store
        secret_config = self.secret_store.get(domain)
        
        if secret_config:
            return secret_config
        
        # For Future - Enterprise Grade: Fetch from control plane
        # secret_config = await self._fetch_secret_from_control_plane(domain, agent_id)
        
        return None
    
    def _inject_bearer_token(self, request: Request, token: str):
        """Inject Bearer token into Authorization header."""
        # Create mutable headers
        headers = dict(request.headers)
        headers["Authorization"] = f"Bearer {token}"
        
        # Replace request headers
        request._headers = headers
        request.scope["headers"] = [
            (key.encode(), value.encode()) for key, value in headers.items()
        ]
    
    def _inject_api_key_header(self, request: Request, header_name: str, api_key: str):
        """Inject API key into specified header."""
        # Create mutable headers
        headers = dict(request.headers)
        headers[header_name] = api_key
        
        # Replace request headers
        request._headers = headers
        request.scope["headers"] = [
            (key.encode(), value.encode()) for key, value in headers.items()
        ]
    
    def _inject_basic_auth(self, request: Request, credentials: str):
        """Inject Basic authentication header."""
        # Create mutable headers
        headers = dict(request.headers)
        headers["Authorization"] = f"Basic {credentials}"
        
        # Replace request headers
        request._headers = headers
        request.scope["headers"] = [
            (key.encode(), value.encode()) for key, value in headers.items()
        ]
    
    # For Future - Enterprise Grade: Advanced secret management methods
    async def _fetch_secret_from_control_plane(self, domain: str, agent_id: str) -> Optional[Dict[str, Any]]:
        """For Future - Enterprise Grade: Fetch secret from control plane."""
        pass
    
    async def _rotate_secret(self, domain: str, agent_id: str) -> bool:
        """For Future - Enterprise Grade: Rotate secret for domain."""
        pass
    
    async def _audit_secret_usage(self, domain: str, agent_id: str, secret_type: str):
        """For Future - Enterprise Grade: Audit secret usage."""
        pass
    
    async def _validate_secret_permissions(self, domain: str, agent_id: str) -> bool:
        """For Future - Enterprise Grade: Validate agent has permission to use secret."""
        pass 