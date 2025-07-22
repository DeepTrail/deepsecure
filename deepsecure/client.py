# deepsecure/client.py
from __future__ import annotations
import os
import time
import logging
from typing import Optional, List, Dict, Any, Tuple

from ._core.base_client import BaseClient
from ._core.vault_client import VaultClient
from ._core.agent_client import AgentClient
from ._core.exceptions import (
    ApiError,
    AuthenticationError,
    DeepSecureClientError,
    IdentityManagerError
)
from ._core.identity_provider import (
    AgentIdentity,
    IdentityProvider,
    KeyringIdentityProvider,
    KubernetesIdentityProvider,
    AwsIdentityProvider,
)
from ._core.config import get_effective_deeptrail_control_url, get_effective_deeptrail_gateway_url
from .resources.agent import Agent
from .exceptions import DeepSecureClientError
from .types import Secret as SecretResourceType

logger = logging.getLogger(__name__)

class Client(BaseClient):
    """
    High-level client for interacting with the DeepSecure backend (deeptrail-control).
    """
    def __init__(
        self, 
        deeptrail_control_url: Optional[str] = None,
        deeptrail_gateway_url: Optional[str] = None,
        silent_mode: bool = False
    ):
        base_url = deeptrail_control_url or get_effective_deeptrail_control_url()
        self.gateway_url = deeptrail_gateway_url or get_effective_deeptrail_gateway_url()
        
        if not base_url:
            raise DeepSecureClientError(
                "Deeptrail Control URL is not configured. "
                "Please set the DEEPSECURE_DEEPTRAIL_CONTROL_URL environment variable."
            )
        super().__init__(api_url=base_url, silent_mode=silent_mode)
        # The Agent resource collection is a separate client that uses the same env vars
        self.agents = AgentClient(api_url=base_url, silent_mode=silent_mode)
        # Share authentication state with the AgentClient
        self.agents._parent_client = self

    def agent(self, name: str, auto_create: bool = True) -> Agent:
        """
        Get a handle for a specific agent by name.
        If auto_create is True, the agent will be created if it doesn't exist.
        """
        # This part of the logic remains high-level, Agent class will use the client
        return self.agents.get_by_name(name, auto_create=auto_create)

    # --- Raw Backend Methods ---

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents registered with the backend."""
        response = self._request("GET", "/api/v1/agents/")
        return response.json().get("agents", [])

    def _create_agent_backend(self, agent_id: str, name: Optional[str], public_key_b64: str) -> Dict[str, Any]:
        """Call the backend to register a new agent."""
        response = self._request(
            "POST",
            "/api/v1/agents/",
            json={
                "agent_id": agent_id,
                "name": name,
                "public_key": public_key_b64
            }
        )
        return response.json()

    def _get_agent_backend(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single agent's details from the backend."""
        try:
            response = self._request("GET", f"/api/v1/agents/{agent_id}")
            return response.json()
        except DeepSecureClientError as e:
            # Handle 404 case gracefully
            if hasattr(e, 'response') and e.response.status_code == 404:
                return None
            raise e

    def _delete_agent_backend(self, agent_id: str):
        """Delete an agent from the backend."""
        self._request("DELETE", f"/api/v1/agents/{agent_id}")
        return

    # --- Vault / Secret Methods ---

    def store_secret(self, agent_id: str, name: str, secret_value: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Store a secret for a specific agent.
        """
        return self._request(
            "POST",
            f"/api/v1/agents/{agent_id}/secrets",
            json={"name": name, "value": secret_value, "metadata": metadata or {}}
        ).json()

    def get_secret(self, agent_id: str, secret_name: str, path: str) -> SecretResourceType:
        """
        Retrieves a secret's value by proxying through the deeptrail-gateway.

        This is the secure method for agents to access secrets. The agent never
        sees the full secret; the gateway injects it into the final request.

        Args:
            agent_id: The ID of the agent making the request.
            secret_name: The name of the secret to be injected by the gateway.
            path: The path of the target API endpoint (e.g., "/v1/completions").

        Returns:
            A SecretResourceType object containing the response from the target service.
        """
        # For now, use a placeholder target URL since we're just demonstrating the flow
        # In a real implementation, this would be derived from the secret configuration
        target_base_url = "https://api.example.com"  # Placeholder for demonstration
        
        headers = {
            "X-Deeptrail-Secret-Name": secret_name,
            "X-Target-Base-URL": target_base_url  # Required by gateway proxy
        }
        
        # The response from the gateway is the actual response from the target service
        response = self._authenticated_request(
            "GET",
            f"/proxy/{path.lstrip('/')}",
            agent_id=agent_id,
            headers=headers,
            base_url_override=self.gateway_url # IMPORTANT: This request must go to the gateway
        )
        
        # We don't know the secret's value here, which is the point.
        # We return a resource object representing the successful call.
        return SecretResourceType(
            name=secret_name,
            # We don't have expiry info from this call, so we can't populate it.
            # The 'value' is the content from the proxied API call.
            value=response.text
        )

    def store_secret_direct(
        self,
        name: str,
        value: str,
        target_base_url: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Store a secret directly in the vault, including its target URL for the gateway.
        This is used for administrative access via the CLI.
        """
        if metadata is None:
            metadata = {}
        
        metadata["target_base_url"] = target_base_url
        
        return self._request(
            "POST",
            "/api/v1/vault/secrets",
            json={"name": name, "value": value, "metadata": metadata}
        ).json()

    def delete_secret(self, agent_id: str, name: str, delegation_token: Optional[str] = None) -> None:
        """Deletes a secret from the vault."""
        path = f"/api/v1/vault/secrets/{name}"
        self._authenticated_request("DELETE", path, agent_id=agent_id, delegation_token=delegation_token)
        return

    def list_secrets(self, agent_id: str, delegation_token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all secrets accessible to the agent."""
        path = "/api/v1/vault/secrets"
        response = self._authenticated_request("GET", path, agent_id=agent_id, delegation_token=delegation_token)
        return response.json().get("secrets", [])

    def get_secret_direct(self, name: str) -> Dict[str, Any]:
        """
        Retrieves a secret directly from the backend vault without requiring an agent.
        
        This method is intended for CLI/administrative use and bypasses the ephemeral
        credential system. For programmatic agent access with gateway proxy, use get_secret().
        
        Args:
            name: The name of the secret to retrieve.
            
        Returns:
            A dictionary containing the secret data (name, value, created_at).
            
        Raises:
            DeepSecureClientError: If the secret is not found or retrieval fails.
        """
        logger.info(f"Retrieving secret directly with name: {name}")
        try:
            response = self._request("GET", f"/api/v1/vault/secrets/{name}")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to retrieve secret {name}: {e}")
            raise DeepSecureClientError(f"Failed to retrieve secret '{name}': {e}") from e

    def delegate_access(
        self,
        delegator_agent_id: str,
        target_agent_id: str,
        resource: str,
        permissions: List[str],
        ttl_seconds: int = 300,
        additional_restrictions: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Delegates access from one agent to another using cryptographic macaroons.

        This implements the core DeepSecure delegation principle: secure, auditable,
        and attenuable agent-to-agent authorization with least-privilege enforcement.

        Args:
            delegator_agent_id: The ID of the agent granting the permissions.
                                This agent must possess a valid macaroon to delegate from.
            target_agent_id: The ID of the agent receiving the delegated permissions.
            resource: The resource to which access is being delegated (e.g., API endpoint).
            permissions: A list of specific actions the target agent can perform.
            ttl_seconds: The time-to-live for the delegated token in seconds.
            additional_restrictions: Optional additional caveats like IP restrictions.

        Returns:
            A serialized macaroon string representing the delegated credential.
            
        Raises:
            DeepSecureClientError: If delegation fails due to authorization or crypto errors.
        """
        from ._core.delegation import delegation_manager, Caveat, CaveatType, MacaroonLocation
        
        # Validate input parameters
        if not delegator_agent_id or not delegator_agent_id.strip():
            raise DeepSecureClientError("delegator_agent_id cannot be empty")
        if not target_agent_id or not target_agent_id.strip():
            raise DeepSecureClientError("target_agent_id cannot be empty")
        if not permissions:
            raise DeepSecureClientError("permissions list cannot be empty")
        if ttl_seconds <= 0:
            raise DeepSecureClientError("ttl_seconds must be positive")
        
        try:
            # 1. Get the delegator's current macaroon (root or delegated)
            # This would typically come from the agent's current session
            delegator_macaroon = self._get_agent_macaroon(delegator_agent_id)
            
            if not delegator_macaroon:
                # Create a root macaroon if none exists (for testing/demo)
                location = MacaroonLocation('deeptrail-control', '/auth')
                delegator_macaroon = delegation_manager.create_root_macaroon(
                    delegator_agent_id, location
                )
            
            # 2. Build delegation caveats (restrictions)
            delegation_caveats = []
            
            # Add resource prefix restriction
            if resource:
                delegation_caveats.append(Caveat(CaveatType.RESOURCE_PREFIX, resource))
            
            # Add action limitations
            if permissions:
                actions_str = ','.join(permissions)
                delegation_caveats.append(Caveat(CaveatType.ACTION_LIMIT, actions_str))
            
            # Add time-based expiration
            expiry_time = time.time() + ttl_seconds
            delegation_caveats.append(Caveat(CaveatType.TIME_BEFORE, str(expiry_time)))
            
            # Add any additional restrictions
            if additional_restrictions:
                if 'ip_address' in additional_restrictions:
                    delegation_caveats.append(
                        Caveat(CaveatType.IP_ADDRESS, additional_restrictions['ip_address'])
                    )
                if 'request_count' in additional_restrictions:
                    delegation_caveats.append(
                        Caveat(CaveatType.REQUEST_COUNT, str(additional_restrictions['request_count']))
                    )
            
            # 3. Create the delegated macaroon with attenuation
            delegated_macaroon = delegation_manager.delegate_macaroon(
                delegator_macaroon,
                target_agent_id,
                delegation_caveats
            )
            
            # 4. Serialize the macaroon for transport
            delegation_token = delegated_macaroon.serialize()
            
            logger.info(f"Delegated access from {delegator_agent_id} to {target_agent_id} "
                       f"for resource '{resource}' with permissions {permissions}")
            
            return delegation_token
            
        except Exception as e:
            raise DeepSecureClientError(f"Failed to delegate access: {str(e)}") from e

    def create_delegation_chain(
        self,
        chain_spec: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Create a multi-level delegation chain with progressive attenuation.
        
        This enables complex workflows like A → B → C where each level adds restrictions.
        
        Args:
            chain_spec: List of delegation specifications, each containing:
                       - from_agent_id: The delegating agent
                       - to_agent_id: The receiving agent  
                       - resource: The resource being delegated
                       - permissions: List of allowed actions
                       - ttl_seconds: Time to live for this level
                       - restrictions: Additional caveats (optional)
        
        Returns:
            Dict mapping agent_id to their delegation token in the chain
            
        Example:
            ```python
            chain = client.create_delegation_chain([
                {
                    'from_agent_id': 'agent-alpha',
                    'to_agent_id': 'agent-beta', 
                    'resource': 'https://api.example.com/data',
                    'permissions': ['read:data', 'write:data'],
                    'ttl_seconds': 3600
                },
                {
                    'from_agent_id': 'agent-beta',
                    'to_agent_id': 'agent-charlie',
                    'resource': 'https://api.example.com/data/readonly',
                    'permissions': ['read:data'],
                    'ttl_seconds': 1800
                }
            ])
            ```
        """
        from ._core.delegation import delegation_manager, Caveat, CaveatType, MacaroonLocation, Macaroon
        
        delegation_tokens = {}
        current_macaroon = None
        
        try:
            for i, spec in enumerate(chain_spec):
                from_agent_id = spec['from_agent_id']
                to_agent_id = spec['to_agent_id']
                
                # For the first delegation, get or create the root macaroon
                if i == 0:
                    current_macaroon = self._get_agent_macaroon(from_agent_id)
                    if not current_macaroon:
                        location = MacaroonLocation('deeptrail-control', '/auth')
                        current_macaroon = delegation_manager.create_root_macaroon(
                            from_agent_id, location
                        )
                
                # Build delegation caveats for this level
                delegation_caveats = []
                
                # Add resource prefix restriction
                if spec.get('resource'):
                    delegation_caveats.append(Caveat(CaveatType.RESOURCE_PREFIX, spec['resource']))
                
                # Add action limitations
                if spec.get('permissions'):
                    actions_str = ','.join(spec['permissions'])
                    delegation_caveats.append(Caveat(CaveatType.ACTION_LIMIT, actions_str))
                
                # Add time-based expiration
                ttl_seconds = spec.get('ttl_seconds', 300)
                expiry_time = time.time() + ttl_seconds
                delegation_caveats.append(Caveat(CaveatType.TIME_BEFORE, str(expiry_time)))
                
                # Add any additional restrictions
                if spec.get('restrictions'):
                    restrictions = spec['restrictions']
                    if 'ip_address' in restrictions:
                        delegation_caveats.append(
                            Caveat(CaveatType.IP_ADDRESS, restrictions['ip_address'])
                        )
                    if 'request_count' in restrictions:
                        delegation_caveats.append(
                            Caveat(CaveatType.REQUEST_COUNT, str(restrictions['request_count']))
                        )
                
                # Create the delegated macaroon using the current macaroon as parent
                delegated_macaroon = delegation_manager.delegate_macaroon(
                    current_macaroon,
                    to_agent_id,
                    delegation_caveats
                )
                
                # Serialize and store the delegation token
                delegation_token = delegated_macaroon.serialize()
                delegation_tokens[to_agent_id] = delegation_token
                
                # Update current macaroon for next iteration
                current_macaroon = delegated_macaroon
                
                logger.info(f"Delegated from {from_agent_id} to {to_agent_id} in chain (level {i+1})")
            
            logger.info(f"Created delegation chain with {len(chain_spec)} levels")
            return delegation_tokens
            
        except Exception as e:
            raise DeepSecureClientError(f"Failed to create delegation chain: {str(e)}") from e

    def verify_delegation(
        self,
        delegation_token: str,
        request_context: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Verify a delegation token and extract its permissions.
        
        Args:
            delegation_token: The serialized macaroon to verify
            request_context: Context for caveat verification (agent_id, resource, action, etc.)
            
        Returns:
            Tuple of (is_valid, reason, delegation_info)
        """
        from ._core.delegation import delegation_manager, Macaroon
        
        try:
            # Deserialize the macaroon
            macaroon = Macaroon.deserialize(delegation_token, delegation_manager.root_key)
            
            # Verify the macaroon
            is_valid, reason = delegation_manager.verify_macaroon(macaroon, request_context)
            
            # Extract delegation information
            delegation_info = {
                'macaroon_id': macaroon.identifier,
                'location': macaroon.location.to_string(),
                'caveats': [caveat.to_string() for caveat in macaroon.caveats],
                'delegation_chain': delegation_manager.get_delegation_chain(macaroon.identifier),
                'creation_time': macaroon.creation_time,
                'parent_signature': macaroon.parent_signature
            }
            
            return is_valid, reason, delegation_info
            
        except Exception as e:
            return False, f"Verification error: {str(e)}", {}

    def _get_agent_macaroon(self, agent_id: str) -> Optional['Macaroon']:
        """
        Get the current macaroon for an agent.
        
        In a full implementation, this would retrieve the agent's current session
        macaroon from secure storage or the current JWT token.
        
        For now, this returns None to trigger root macaroon creation.
        """
        # TODO: Implement macaroon retrieval from agent session
        return None 

class DeepSecure:
    """The main client for interacting with the DeepSecure API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        agent_id: Optional[str] = None,
        identity: Optional[AgentIdentity] = None,
        silent_mode: bool = False,
        **kwargs,
    ):
        
        # Use environment variable if no base_url is provided
        import os
        self.base_url = base_url or os.environ.get("DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://localhost:8000")
        self.silent_mode = silent_mode
        self._agent_id = agent_id
        self._identity = identity
        
        # Central API client that all sub-clients will use
        self._client = BaseClient(api_url=self.base_url, silent_mode=self.silent_mode)
        
        # Create custom identity manager with our provider chain
        from ._core.identity_manager import IdentityManager
        from ._core.identity_provider import KeyringIdentityProvider, KubernetesIdentityProvider, AwsIdentityProvider
        
        providers = self._create_identity_providers()
        self.identity_manager = IdentityManager(providers=providers, api_client=self._client, silent_mode=self.silent_mode)
        
        # Replace the BaseClient's identity manager with our custom one
        self._client._identity_manager = self.identity_manager

        # Authenticate if an agent_id is provided
        if self._agent_id:
            self.authenticate(self._agent_id)

        # Initialize sub-clients, passing the authenticated BaseClient instance
        self.agents = AgentClient(api_url=self.base_url, silent_mode=self.silent_mode)
        self.vault = VaultClient(self._client)

    def _create_identity_providers(self) -> List[IdentityProvider]:
        """
        Creates and returns a list of identity providers based on the
        detected environment, in the correct order of precedence.
        Enhanced with Azure and Docker support.
        """
        providers: List[IdentityProvider] = []
        
        # Environment-specific providers go first
        # These need the API client to talk to the backend bootstrap endpoints.
        from ._core.identity_provider import (
            KubernetesIdentityProvider, 
            AwsIdentityProvider,
            AzureIdentityProvider,
            DockerIdentityProvider,
            KeyringIdentityProvider
        )
        
        k8s_provider = KubernetesIdentityProvider(client=self._client, silent_mode=self.silent_mode)
        aws_provider = AwsIdentityProvider(client=self._client, silent_mode=self.silent_mode)
        azure_provider = AzureIdentityProvider(client=self._client, silent_mode=self.silent_mode)
        docker_provider = DockerIdentityProvider(client=self._client, silent_mode=self.silent_mode)
        
        # Order of precedence for platform-native identity providers
        # Kubernetes and AWS are most common in production, so they go first
        providers.append(k8s_provider)
        providers.append(aws_provider)
        providers.append(azure_provider)
        providers.append(docker_provider)
        
        # The default local provider should come last as a fallback.
        providers.append(KeyringIdentityProvider(silent_mode=self.silent_mode))
        
        return providers

    def authenticate(self, agent_id: str) -> None:
        """
        Authenticates the agent and stores the session token.
        This is typically called automatically if an agent_id is provided
        on initialization.
        """
        if not self._identity:
            self._identity = self.identity_manager.get_identity(agent_id)

        if not self._identity:
            raise AuthenticationError(
                f"Could not find identity for agent '{agent_id}'. "
                f"Ensure the agent has been created and its keys are accessible."
            )
        
        # Use the identity manager to perform the full challenge-response flow
        self._client.get_access_token(agent_id)
        
        # Store the agent_id for future reference
        self._agent_id = agent_id

    @property
    def agent_id(self) -> Optional[str]:
        return self._agent_id