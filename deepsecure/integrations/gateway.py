"""
Model-agnostic gateway client for proxying requests through DeepSecure.

The GatewayClient provides a clean, discoverable API for making proxied requests
to any external API through the DeepSecure Gateway. The gateway:
- Validates the agent's JWT
- Enforces access policies
- Injects secrets (API keys) just-in-time
- Logs all requests for audit

This is the foundation for model-specific integrations (OpenAI, Anthropic, etc.)
"""

from typing import Any, Dict, Optional, Union
import logging
import httpx

logger = logging.getLogger(__name__)


# Well-known API base URLs and their default secret names
KNOWN_SERVICES = {
    "https://api.openai.com": "openai-api-key",
    "https://api.anthropic.com": "anthropic-api-key",
    "https://generativelanguage.googleapis.com": "google-ai-api-key",
    "https://api.cohere.ai": "cohere-api-key",
    "https://api.mistral.ai": "mistral-api-key",
    "https://api.together.xyz": "together-api-key",
    "https://api.groq.com": "groq-api-key",
}


class GatewayClient:
    """
    Model-agnostic gateway client for proxying requests through DeepSecure.
    
    The gateway provides:
    - JWT validation for agent authentication
    - Policy enforcement for access control
    - Just-in-time secret injection
    - Complete audit logging
    
    Example usage:
        # Generic request
        resp = client.gateway.request(
            "GET", "/v1/models",
            target_base_url="https://api.openai.com"
        )
        
        # Using convenience methods
        resp = client.gateway.get("/v1/models", "https://api.openai.com")
        
        # With explicit secret name
        resp = client.gateway.post(
            "/v1/messages",
            "https://api.anthropic.com",
            secret_name="anthropic-api-key",
            json={"model": "claude-3-opus", "messages": [...]}
        )
    """
    
    def __init__(self, parent_client: 'Client'):
        """
        Initialize the GatewayClient.
        
        Args:
            parent_client: The main DeepSecure Client instance
        """
        self._client = parent_client
        self._gateway_url = getattr(parent_client, 'gateway_url', None) or \
                           getattr(parent_client, '_gateway_url', 'http://localhost:8002')
    
    def _get_default_secret_name(self, target_base_url: str) -> Optional[str]:
        """
        Get the default secret name for a well-known service.
        
        Args:
            target_base_url: The base URL of the target API
            
        Returns:
            The default secret name, or None if not a known service
        """
        # Normalize URL (remove trailing slash)
        normalized_url = target_base_url.rstrip('/')
        return KNOWN_SERVICES.get(normalized_url)
    
    def request(
        self,
        *,
        agent_id: str,
        target_base_url: str,
        path: str,
        method: str = "GET",
        secret_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[bytes] = None,
        content: Optional[bytes] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        stream: bool = False,
    ) -> httpx.Response:
        """
        Make a proxied request through the DeepSecure Gateway.
        
        The gateway will:
        1. Validate the agent's JWT token
        2. Check if the request is allowed by policy
        3. Inject the appropriate secret (API key) into the request
        4. Forward the request to the target API
        5. Log the request for audit purposes
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH, etc.)
            path: API path (e.g., "/v1/models", "/v1/chat/completions")
            target_base_url: Base URL of target API (e.g., "https://api.openai.com")
            agent_id: Agent making the request. Uses current session if None.
            secret_name: Name of secret to inject. Auto-detected from target_base_url if None.
            headers: Additional headers to include in the request
            json: JSON body for POST/PUT/PATCH requests
            data: Raw body bytes for POST/PUT/PATCH requests
            params: Query parameters
            timeout: Request timeout in seconds (default: 30)
            stream: Whether to stream the response (default: False)
            
        Returns:
            httpx.Response from the target API
            
        Raises:
            httpx.HTTPStatusError: If the request fails with an HTTP error
            
        Example:
            # List OpenAI models
            resp = client.gateway.request(
                "GET", "/v1/models",
                target_base_url="https://api.openai.com"
            )
            
            # Call Anthropic API
            resp = client.gateway.request(
                "POST", "/v1/messages",
                target_base_url="https://api.anthropic.com",
                secret_name="anthropic-api-key",
                json={
                    "model": "claude-3-opus-20240229",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": "Hello!"}]
                },
                headers={"anthropic-version": "2023-06-01"}
            )
        """
        # Determine secret name if not provided
        if secret_name is None:
            secret_name = self._get_default_secret_name(target_base_url)
        
        # Build gateway headers
        gateway_headers = headers.copy() if headers else {}
        gateway_headers["X-Target-Base-URL"] = target_base_url
        
        if secret_name:
            gateway_headers["X-Deeptrail-Secret-Name"] = secret_name
        
        # Normalize path (ensure it starts with /)
        if not path.startswith('/'):
            path = f'/{path}'
        
        # Build the proxy path
        proxy_path = f"/proxy{path}"
        
        # Determine which agent_id to use
        effective_agent_id = agent_id
        if effective_agent_id is None:
            # Try to get from current session
            effective_agent_id = getattr(self._client, '_current_agent_id', None)
        
        if effective_agent_id is None:
            raise ValueError(
                "agent_id is required. Either pass it explicitly or call client.login() first."
            )
        
        logger.debug(
            f"Gateway request: {method} {target_base_url}{path} "
            f"(agent={effective_agent_id}, secret={secret_name})"
        )
        
        # Make the authenticated request through the gateway
        response = self._client._authenticated_request(
            method,
            proxy_path,
            agent_id=effective_agent_id,
            headers=gateway_headers,
            json=json,
            data=data,
            content=content,
            params=params,
            base_url_override=self._gateway_url,
            stream=stream,
        )
        
        return response
    
    # Convenience methods for common HTTP verbs
    
    def get(
        self,
        path: str,
        target_base_url: str,
        **kwargs
    ) -> httpx.Response:
        """
        Make a GET request through the gateway.
        
        Args:
            path: API path (e.g., "/v1/models")
            target_base_url: Base URL of target API
            **kwargs: Additional arguments passed to request()
            
        Returns:
            httpx.Response from the target API
        """
        return self.request(method="GET", path=path, target_base_url=target_base_url, **kwargs)
    
    def post(
        self,
        path: str,
        target_base_url: str,
        **kwargs
    ) -> httpx.Response:
        """
        Make a POST request through the gateway.
        
        Args:
            path: API path (e.g., "/v1/chat/completions")
            target_base_url: Base URL of target API
            **kwargs: Additional arguments passed to request()
            
        Returns:
            httpx.Response from the target API
        """
        return self.request(method="POST", path=path, target_base_url=target_base_url, **kwargs)
    
    def put(
        self,
        path: str,
        target_base_url: str,
        **kwargs
    ) -> httpx.Response:
        """
        Make a PUT request through the gateway.
        
        Args:
            path: API path
            target_base_url: Base URL of target API
            **kwargs: Additional arguments passed to request()
            
        Returns:
            httpx.Response from the target API
        """
        return self.request(method="PUT", path=path, target_base_url=target_base_url, **kwargs)
    
    def delete(
        self,
        path: str,
        target_base_url: str,
        **kwargs
    ) -> httpx.Response:
        """
        Make a DELETE request through the gateway.
        
        Args:
            path: API path
            target_base_url: Base URL of target API
            **kwargs: Additional arguments passed to request()
            
        Returns:
            httpx.Response from the target API
        """
        return self.request(method="DELETE", path=path, target_base_url=target_base_url, **kwargs)
    
    def patch(
        self,
        path: str,
        target_base_url: str,
        **kwargs
    ) -> httpx.Response:
        """
        Make a PATCH request through the gateway.
        
        Args:
            path: API path
            target_base_url: Base URL of target API
            **kwargs: Additional arguments passed to request()
            
        Returns:
            httpx.Response from the target API
        """
        return self.request(method="PATCH", path=path, target_base_url=target_base_url, **kwargs)
