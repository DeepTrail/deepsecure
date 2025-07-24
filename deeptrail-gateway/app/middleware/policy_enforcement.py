"""
Policy Enforcement Middleware for DeepTrail Gateway

Core PEP Functionality:
This middleware enforces basic access policies based on JWT claims
to ensure agents can only access authorized resources.

For Future - Enterprise Grade:
- Advanced policy languages (RBAC, ABAC)
- Dynamic policy evaluation
- Policy caching and optimization
- Fine-grained resource permissions
- Policy audit and compliance
"""

import logging
from typing import Optional, Dict, Any, List
import re
from urllib.parse import urlparse

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class PolicyEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Core PEP: Simple policy enforcement middleware.
    
    This middleware enforces basic access policies based on JWT claims
    to control which external services agents can access.
    
    For Future - Enterprise Grade: Advanced policy features will be added.
    """
    
    def __init__(self, app: ASGIApp, enforcement_mode: str = "strict"):
        super().__init__(app)
        self.enforcement_mode = enforcement_mode  # strict, permissive, disabled
        self.bypass_paths = {"/", "/health", "/ready", "/metrics", "/config", "/docs", "/redoc", "/openapi.json"}
        
        logger.info("Policy enforcement middleware initialized")
        logger.info(f"Enforcement mode: {enforcement_mode}")
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and enforce policies.
        """
        # Skip policy enforcement for health checks and docs
        if request.url.path in self.bypass_paths:
            return await call_next(request)
        
        # Skip policy enforcement for non-proxy requests
        if not request.url.path.startswith("/proxy"):
            return await call_next(request)
        
        # Skip policy enforcement if disabled
        if self.enforcement_mode == "disabled":
            return await call_next(request)
        
        # Get target URL from request
        target_url = request.headers.get("X-Target-Base-URL")
        if not target_url:
            logger.warning("Missing X-Target-Base-URL header for policy enforcement")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Missing X-Target-Base-URL header"}
            )
        
        # Get agent information from JWT validation
        agent_id = getattr(request.state, "agent_id", None)
        agent_permissions = getattr(request.state, "agent_permissions", [])
        jwt_payload = getattr(request.state, "jwt_payload", {})
        
        if not agent_id:
            logger.warning("Missing agent information for policy enforcement")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing agent authentication"}
            )
        
        # Enforce policy
        try:
            policy_result = await self._enforce_policy(
                agent_id=agent_id,
                agent_permissions=agent_permissions,
                jwt_payload=jwt_payload,
                target_url=target_url,
                request_method=request.method,
                request_path=request.url.path
            )
            
            if not policy_result.allowed:
                logger.warning(f"Policy denied access for agent {agent_id} to {target_url}: {policy_result.reason}")
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": f"Access denied: {policy_result.reason}"}
                )
            
            logger.info(f"Policy allowed access for agent {agent_id} to {target_url}")
            
            # Add policy information to request state
            request.state.policy_result = policy_result
            
        except Exception as e:
            logger.error(f"Policy enforcement error: {e}")
            if self.enforcement_mode == "strict":
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Policy enforcement error"}
                )
            else:
                logger.warning("Policy enforcement error in permissive mode, allowing request")
        
        # Continue with request processing
        return await call_next(request)
    
    async def _enforce_policy(
        self,
        agent_id: str,
        agent_permissions: List[str],
        jwt_payload: Dict[str, Any],
        target_url: str,
        request_method: str,
        request_path: str
    ) -> 'PolicyResult':
        """
        Core PEP: Basic policy enforcement.
        
        For Future - Enterprise Grade: This will be replaced with a sophisticated
        policy engine supporting RBAC, ABAC, and dynamic policy evaluation.
        """
        
        # Parse target URL
        parsed_url = urlparse(target_url)
        target_domain = parsed_url.netloc.lower()
        
        # Core PEP: Basic domain-based policy
        allowed_domains = self._get_allowed_domains(agent_permissions, jwt_payload)
        
        # Check if target domain is allowed
        if allowed_domains and target_domain not in allowed_domains:
            return PolicyResult(
                allowed=False,
                reason=f"Domain {target_domain} not in allowed domains: {allowed_domains}"
            )
        
        # Core PEP: Basic method-based policy
        allowed_methods = self._get_allowed_methods(agent_permissions, jwt_payload)
        
        # Check if request method is allowed
        if allowed_methods and request_method.upper() not in allowed_methods:
            return PolicyResult(
                allowed=False,
                reason=f"Method {request_method} not in allowed methods: {allowed_methods}"
            )
        
        # For Future - Enterprise Grade: Advanced policy checks
        # - Resource-specific permissions
        # - Time-based access control
        # - Rate limiting per agent
        # - Contextual access control
        
        return PolicyResult(
            allowed=True,
            reason="Basic policy checks passed"
        )
    
    def _get_allowed_domains(self, permissions: List[str], jwt_payload: Dict[str, Any]) -> List[str]:
        """
        Core PEP: Extract allowed domains from JWT claims.
        
        For Future - Enterprise Grade: This will be replaced with proper
        policy evaluation from the control plane.
        """
        # Check for domain permissions in JWT
        allowed_domains = []
        
        # Look for domain permissions in JWT payload
        if "allowed_domains" in jwt_payload:
            allowed_domains.extend(jwt_payload["allowed_domains"])
        
        # Look for domain permissions in permissions list
        for perm in permissions:
            if perm.startswith("domain:"):
                domain = perm.split(":", 1)[1]
                allowed_domains.append(domain.lower())
        
        # Default allowed domains for development
        if not allowed_domains:
            # For Future - Enterprise Grade: Remove these defaults
            allowed_domains = [
                "api.openai.com",
                "httpbin.org",
                "jsonplaceholder.typicode.com",
                "reqres.in"
            ]
        
        return allowed_domains
    
    def _get_allowed_methods(self, permissions: List[str], jwt_payload: Dict[str, Any]) -> List[str]:
        """
        Core PEP: Extract allowed HTTP methods from JWT claims.
        """
        # Check for method permissions in JWT
        allowed_methods = []
        
        # Look for method permissions in JWT payload
        if "allowed_methods" in jwt_payload:
            allowed_methods.extend(jwt_payload["allowed_methods"])
        
        # Look for method permissions in permissions list
        for perm in permissions:
            if perm.startswith("method:"):
                method = perm.split(":", 1)[1]
                allowed_methods.append(method.upper())
        
        # Default allowed methods for development
        if not allowed_methods:
            # For Future - Enterprise Grade: More restrictive defaults
            allowed_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        
        return allowed_methods
    
    # For Future - Enterprise Grade: Advanced policy methods
    async def _fetch_policy_from_control_plane(self, agent_id: str) -> Dict[str, Any]:
        """For Future - Enterprise Grade: Fetch policy from control plane."""
        pass
    
    async def _evaluate_rbac_policy(self, agent_id: str, resource: str, action: str) -> bool:
        """For Future - Enterprise Grade: Evaluate RBAC policy."""
        pass
    
    async def _evaluate_abac_policy(self, context: Dict[str, Any]) -> bool:
        """For Future - Enterprise Grade: Evaluate ABAC policy."""
        pass


class PolicyResult:
    """Result of policy evaluation."""
    
    def __init__(self, allowed: bool, reason: str):
        self.allowed = allowed
        self.reason = reason
    
    def __str__(self):
        return f"PolicyResult(allowed={self.allowed}, reason='{self.reason}')" 