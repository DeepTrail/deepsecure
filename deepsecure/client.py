# deepsecure/client.py
from __future__ import annotations
from typing import Optional
import logging
from dataclasses import dataclass
import copy
from datetime import datetime, timedelta, timezone
import jwt

from ._core.config import get_effective_credservice_url, get_effective_api_token
from ._core.client import VaultClient as CoreVaultClient
from ._core.agent_client import AgentClient as CoreAgentClient
from ._core.identity_manager import identity_manager
from .exceptions import DeepSecureClientError, IdentityManagerError
from .types import Secret
from .utils import parse_ttl_to_seconds

logger = logging.getLogger(__name__)


@dataclass
class Agent:
    """A handle to a DeepSecure Agent identity."""
    id: str
    name: str
    client: 'Client'

    def issue_token_for(self, audience: str, expiry_minutes: int = 5) -> str:
        """
        Issues a short-lived JWT signed by this agent for a specific audience.

        Args:
            audience: The identifier of the service or agent that this token is for (the 'aud' claim).
            expiry_minutes: The number of minutes until the token expires.

        Returns:
            A signed JWT string.
        """
        logger.info(f"Agent '{self.name}' ({self.id}) issuing token for audience '{audience}'.")
        
        # 1. Load the agent's private key from keychain
        private_key_b64 = self.client._identity_manager.get_private_key(self.id)
        if not private_key_b64:
            raise IdentityManagerError(f"Could not load private key for agent '{self.name}' to issue token.")
        
        # 2. Prepare JWT claims
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(minutes=expiry_minutes)
        
        payload = {
            "iss": self.id,  # Issuer is the agent's ID
            "aud": audience, # Audience for the token
            "iat": issued_at,
            "exp": expires_at,
        }
        
        # 3. Sign the token
        # The key needs to be decoded from base64
        private_key = self.client._identity_manager.decode_private_key(private_key_b64)
        
        token = jwt.encode(
            payload,
            private_key,
            algorithm="EdDSA"
        )
        
        logger.info(f"Successfully issued token for audience '{audience}'.")
        return token


class Client:
    """
    The main DeepSecure client for interacting with the DeepSecure platform.

    This client provides a high-level, developer-friendly interface for managing
    agent identities, fetching secrets, and performing other security operations.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_token: Optional[str] = None,
        _agent_context: Optional[Agent] = None, # Internal use for with_agent
    ):
        """
        Initializes the DeepSecure client.
        
        Configuration is automatically loaded from environment variables
        or the local configuration file created by the CLI (`deepsecure configure`).
        You can override this by passing `base_url` and `api_token` directly.
        """
        self.base_url = base_url or get_effective_credservice_url()
        self.api_token = api_token or get_effective_api_token()
        self._agent_context = _agent_context # Storing the agent context

        if not self.base_url:
            raise DeepSecureClientError(
                "CredService URL is not set. Please configure it via `deepsecure configure set-url` "
                "or set the DEEPSECURE_CREDSERVICE_URL environment variable."
            )
        
        if not self.api_token:
            raise DeepSecureClientError(
                "API token is not set. Please configure it via `deepsecure configure set-token` "
                "or set the DEEPSECURE_CREDSERVICE_API_TOKEN environment variable."
            )
            
        # Internal clients that do the actual work
        self._vault_client = CoreVaultClient()
        self._vault_client.base_url = self.base_url
        self._vault_client.token = self.api_token
        
        self._agent_client = CoreAgentClient()
        self._agent_client.base_url = self.base_url
        self._agent_client.token = self.api_token
        
        self._identity_manager = identity_manager

    def agent(self, name: str, auto_create: bool = False) -> Agent:
        """
        Retrieves a handle to an existing agent by name, or creates one.

        This is the primary method for establishing an agent's identity for use
        with the SDK.

        Args:
            name: The human-readable name of the agent. This is used to find
                  the corresponding agent in the backend.
            auto_create: If True, a new agent identity will be created and
                         registered with the backend if one with the specified
                         name is not found. Defaults to False.

        Returns:
            An `Agent` handle object, which can be used for further operations.

        Raises:
            IdentityManagerError: If the agent is not found and `auto_create` is False.
            DeepSecureClientError: If there is an issue communicating with the backend.
        """
        # 1. Try to find the agent in the backend by name
        try:
            backend_agents = self._agent_client.list_agents()
            agents_list = backend_agents.get("agents", []) if isinstance(backend_agents, dict) else backend_agents
            
            found_agent = None
            for agent in agents_list:
                if agent.get("name") == name:
                    found_agent = agent
                    break
                    
            if found_agent:
                agent_id = found_agent['agent_id']
                logger.info(f"Found backend agent '{name}' with ID: {agent_id}")
                
                # 1.1. Verify we have the private key for this agent
                private_key = self._identity_manager.get_private_key(agent_id)
                if private_key:
                    logger.info(f"Agent '{name}' has private key in keychain. Ready to use.")
                    return Agent(id=agent_id, name=name, client=self)
                else:
                    logger.warning(f"Backend agent '{name}' (ID: {agent_id}) found but no private key in keychain.")
                    if auto_create:
                        raise DeepSecureClientError(
                            f"Agent '{name}' exists in backend but private key is missing from keychain. "
                            f"This indicates a corrupted state. Please delete the backend agent and recreate, "
                            f"or restore the private key to the keychain."
                        )
                    else:
                        raise DeepSecureClientError(
                            f"Agent '{name}' exists in backend but private key is missing from keychain. "
                            f"Use `auto_create=True` to handle this, or manually fix the keychain."
                        )
            else:
                logger.info(f"No backend agent found with name '{name}'.")
                
        except Exception as e:
            logger.error(f"Failed to search for agent '{name}' in backend: {e}")
            if not auto_create:
                raise DeepSecureClientError(f"Failed to search for agent '{name}' in backend: {e}") from e

        # 2. If not found, decide whether to create it
        if not auto_create:
            raise IdentityManagerError(f"No backend agent found for name '{name}'. Use `auto_create=True` to create one.")
        
        logger.info(f"No backend agent for '{name}' found. Creating a new one with `auto_create=True`...")
        
        # 3. Create new agent with backend-first approach
        # 3.1. Generate a temporary agent ID for key generation
        temp_agent_id = self._identity_manager._generate_agent_id()
        
        # 3.2. Generate keypair
        keypair = self._identity_manager.create_keypair_for_agent(temp_agent_id)
        public_key = keypair["public_key"]
        
        # 3.3. Register with backend (backend may assign a different agent_id)
        try:
            reg_response = self._agent_client.register_agent(
                public_key=public_key,
                name=name,
                description=f"Auto-created by DeepSecure SDK for application use."
            )
            backend_agent_id = reg_response.get("agent_id")
            if not backend_agent_id:
                raise DeepSecureClientError("Backend registration failed - no agent_id returned.")
                
            logger.info(f"Successfully registered new agent '{name}' with backend. Agent ID: {backend_agent_id}")
            
            # 3.4. If backend assigned a different ID, we need to move the private key
            if backend_agent_id != temp_agent_id:
                logger.info(f"Backend assigned different agent ID ({backend_agent_id}) than temporary ({temp_agent_id}). Moving private key.")
                
                # Get the private key from temp location
                temp_private_key = self._identity_manager.get_private_key(temp_agent_id)
                if temp_private_key:
                    # Store it under the correct agent ID
                    self._identity_manager.store_private_key_directly(backend_agent_id, temp_private_key)
                    # Clean up the temporary entry
                    self._identity_manager.delete_private_key(temp_agent_id)
                else:
                    raise DeepSecureClientError("Failed to retrieve temporary private key during agent ID migration.")
            
            return Agent(id=backend_agent_id, name=name, client=self)
            
        except Exception as e:
            logger.error(f"Failed to register new agent '{name}' with backend: {e}")
            # Clean up the temporary keypair
            self._identity_manager.delete_private_key(temp_agent_id)
            raise DeepSecureClientError(f"Failed to register new agent '{name}' with backend: {e}") from e

    def with_agent(self, name: str, auto_create: bool = False) -> Client:
        """
        Creates a new client instance with a specific agent context.
        
        This is useful for multi-agent scenarios where different parts of your
        code need to operate as different agents.
        
        Args:
            name: The name of the agent to use as context for this client.
            auto_create: Whether to create the agent if it doesn't exist.
            
        Returns:
            A new Client instance with the specified agent as context.
        """
        agent = self.agent(name, auto_create=auto_create)
        
        # Create a new client with the same configuration but different agent context
        new_client = Client(
            base_url=self.base_url,
            api_token=self.api_token,
            _agent_context=agent
        )
        
        return new_client

    def get_secret(self, name: str, agent_name: Optional[str] = None, ttl: str = "5m") -> Secret:
        """
        Fetches a secret from the DeepSecure vault.
        
        Args:
            name: The name of the secret to fetch.
            agent_name: The name of the agent to use for this request. If not provided,
                       uses the agent context from `with_agent()` or raises an error.
            ttl: Time-to-live for the credential (e.g., "5m", "1h", "30s").
            
        Returns:
            A Secret object containing the secret value and metadata.
            
        Raises:
            DeepSecureClientError: If no agent context is available or if the secret fetch fails.
        """
        # Determine which agent to use
        if agent_name:
            agent = self.agent(agent_name, auto_create=False)
        elif self._agent_context:
            agent = self._agent_context
        else:
            raise DeepSecureClientError(
                "No agent specified. Either provide `agent_name` or use `client.with_agent(name)` "
                "to set an agent context."
            )
        
        logger.info(f"Agent '{agent.name}' ({agent.id}) fetching secret '{name}' with TTL '{ttl}'")
        
        # Issue a credential for this secret
        try:
            response = self._vault_client.issue(
                scope=name,
                agent_id=agent.id,
                ttl=parse_ttl_to_seconds(ttl)
            )
            
            # Create and return the Secret object
            secret = Secret(
                name=name,
                expires_at=response.expires_at,
                _value=response.secret_value or ''
            )
            
            logger.info(f"Successfully fetched secret '{name}' for agent '{agent.name}'")
            return secret
            
        except Exception as e:
            logger.error(f"Failed to fetch secret '{name}' for agent '{agent.name}': {e}")
            raise DeepSecureClientError(f"Failed to fetch secret '{name}': {e}") from e

    @property
    def vault(self):
        """Access to vault operations."""
        return self._vault_client

    def list_agents(self) -> list[dict]:
        """
        Lists all agents from the backend.
        
        Returns:
            List of agent dictionaries from the backend.
        """
        try:
            response = self._agent_client.list_agents()
            return response.get("agents", []) if isinstance(response, dict) else response
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            raise DeepSecureClientError(f"Failed to list agents: {e}") from e

    def describe_agent(self, agent_id: str) -> Optional[dict]:
        """
        Gets detailed information about a specific agent from the backend.
        
        Args:
            agent_id: The ID of the agent to describe.
            
        Returns:
            Agent information dictionary or None if not found.
        """
        try:
            return self._agent_client.describe_agent(agent_id)
        except Exception as e:
            logger.error(f"Failed to describe agent {agent_id}: {e}")
            raise DeepSecureClientError(f"Failed to describe agent {agent_id}: {e}") from e

    def delete_agent(self, agent_id: str):
        """
        Deletes an agent from both backend and local keychain.
        
        Args:
            agent_id: The ID of the agent to delete.
        """
        try:
            # Delete from backend first
            self._agent_client.delete_agent(agent_id)
            logger.info(f"Successfully deleted agent {agent_id} from backend")
            
            # Then delete private key from keychain
            self._identity_manager.delete_private_key(agent_id)
            logger.info(f"Successfully deleted private key for agent {agent_id} from keychain")
            
        except Exception as e:
            logger.error(f"Failed to delete agent {agent_id}: {e}")
            raise DeepSecureClientError(f"Failed to delete agent {agent_id}: {e}") from e

    def store_secret(self, name: str, value: str):
        """
        Stores a secret in the vault.
        
        Args:
            name: The name of the secret.
            value: The secret value to store.
        """
        try:
            self._vault_client.store_secret(name, value)
            logger.info(f"Successfully stored secret '{name}'")
        except Exception as e:
            logger.error(f"Failed to store secret '{name}': {e}")
            raise DeepSecureClientError(f"Failed to store secret '{name}': {e}") from e

    def get_secret_direct(self, name: str) -> dict:
        """
        Retrieves a secret directly from the vault without requiring an agent.
        
        This method is intended for CLI/administrative use and bypasses the ephemeral
        credential system. For programmatic agent access, use get_secret() instead.
        
        Args:
            name: The name of the secret to retrieve.
            
        Returns:
            A dictionary containing the secret data (name, value, created_at).
        """
        try:
            secret_data = self._vault_client.get_secret_direct(name)
            logger.info(f"Successfully retrieved secret '{name}' directly")
            return secret_data
        except Exception as e:
            logger.error(f"Failed to retrieve secret '{name}': {e}")
            raise DeepSecureClientError(f"Failed to retrieve secret '{name}': {e}") from e 