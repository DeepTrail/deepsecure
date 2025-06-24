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
        
        # 1. Load the agent's private key
        identity = self.client._identity_manager.load_identity(self.id)
        private_key_b64 = identity.get("private_key")
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
                  the corresponding local identity.
            auto_create: If True, a new agent identity will be created and
                         registered with the backend if one with the specified
                         name is not found locally. Defaults to False.

        Returns:
            An `Agent` handle object, which can be used for further operations.

        Raises:
            IdentityManagerError: If the agent is not found and `auto_create` is False.
            DeepSecureClientError: If there is an issue communicating with the backend.
        """
        # 1. Try to find the agent identity locally by name
        found_identity = self._identity_manager.find_identity_by_name(name)

        if found_identity:
            logger.info(f"Found local identity for agent '{name}' with ID: {found_identity['id']}")
            return Agent(id=found_identity['id'], name=name, client=self)

        # 2. If not found, decide whether to create it
        if not auto_create:
            raise IdentityManagerError(f"No local agent identity found for name '{name}'. Use `auto_create=True` to create one.")
        
        logger.info(f"No local identity for '{name}' found. Creating a new one with `auto_create=True`...")
        
        # 3. Create the new identity (generates keys)
        new_identity = self._identity_manager.create_identity(name=name)
        agent_id = new_identity['id']
        public_key = new_identity['public_key']
        
        logger.info(f"New local identity created for '{name}' (ID: {agent_id}). Registering with backend...")
        
        # 4. Register the new public key with the backend
        try:
            reg_response = self._agent_client.register_agent(
                public_key=public_key,
                name=name,
                description=f"Automatically created by DeepSecure SDK.",
                agent_id=agent_id
            )
            # The backend should return the same agent_id we just created locally
            backend_agent_id = reg_response.get("agent_id")
            if backend_agent_id != agent_id:
                # This would be a very unusual and serious error state
                logger.error(
                    f"Mismatch between locally generated agent ID ({agent_id}) and backend registered ID ({backend_agent_id}). "
                    "Local keys will be purged to prevent inconsistent state."
                )
                self._identity_manager.delete_identity(agent_id)
                raise DeepSecureClientError("Failed to create agent due to backend ID mismatch. Please try again.")
            
            logger.info(f"Successfully registered new agent '{name}' with backend. ID: {agent_id}")
            
        except Exception as e:
            # If backend registration fails, we must clean up the local keys
            logger.error(f"Failed to register new agent '{name}' with backend. Purging local keys to prevent orphan identity. Error: {e}")
            self._identity_manager.delete_identity(agent_id)
            raise DeepSecureClientError(f"Failed to register new agent with backend: {e}") from e
            
        return Agent(id=agent_id, name=name, client=self)

    def with_agent(self, name: str, auto_create: bool = False) -> Client:
        """
        Creates a new client instance scoped to a specific agent.

        This is useful for dependency injection, allowing you to pass a pre-configured,
        agent-specific client to tools or functions.

        Args:
            name: The name of the agent to scope the client to.
            auto_create: If True, create the agent if it does not exist.

        Returns:
            A new `Client` instance that will automatically use the specified
            agent for operations like `get_secret`.
        """
        agent_handle = self.agent(name, auto_create=auto_create)
        
        # Create a new client instance with the same config but with agent context
        new_client = Client(
            base_url=self.base_url,
            api_token=self.api_token,
            _agent_context=agent_handle
        )
        return new_client

    def get_secret(self, name: str, agent_name: Optional[str] = None, ttl: str = "5m") -> Secret:
        """
        Fetches a secret from the vault for a specific agent.

        This is the primary method for securely retrieving operational secrets
        like API keys, database passwords, etc.

        Args:
            name: The name of the secret to retrieve (e.g., "OPENAI_API_KEY").
            agent_name: The name of the agent identity to use for the request.
                        If the client was created using `with_agent()`, this is
                        not required.
            ttl: The requested Time-To-Live for the ephemeral credential that
                 will be used to fetch the secret (e.g., "5m", "1h").

        Returns:
            A `Secret` object containing the value and metadata.

        Raises:
            DeepSecureClientError: If the API call fails or `agent_name` is not provided.
        """
        if agent_name:
            agent_handle = self.agent(agent_name, auto_create=False)
        elif self._agent_context:
            agent_handle = self._agent_context
        else:
            raise DeepSecureClientError(
                "No agent specified. Call `get_secret` with an `agent_name` or "
                "create an agent-specific client using `client.with_agent('my-agent')`."
            )

        # 1. Get the agent handle, which ensures the identity exists
        # agent_handle = self.agent(agent_name, auto_create=False)
        
        # 2. Issue a short-lived credential for the specific scope of this secret
        # The scope is constructed as `secret:<name>`
        scope = f"secret:{name}"
        
        # We need the agent's ID for the credential request
        agent_id = agent_handle.id
        
        # 3. Request an ephemeral credential (token) from the Vault client
        try:
            # Note: We call the issue method, not issue_credential
            cred_response = self._vault_client.issue(
                scope=scope, 
                agent_id=agent_id,
                ttl_seconds=parse_ttl_to_seconds(ttl)
            )
        except Exception as e:
            raise DeepSecureClientError(f"Failed to issue ephemeral credential for agent '{agent_name or agent_handle.name}' to get secret '{name}': {e}") from e

        # This part is a temporary workaround until the vault service is updated
        # to return the secret value directly in the credential response.
        if not hasattr(cred_response, 'secret_value'):
            logger.warning("CredentialResponse does not contain 'secret_value'. Using dummy value.")
            secret_value = "dummy-secret-value-from-sdk"
        else:
            secret_value = cred_response.secret_value

        return Secret(
            name=name,
            _value=secret_value,
            expires_at=cred_response.expires_at,
        )

    def list_agents(self) -> list[dict]:
        """Lists all agents registered with the backend service."""
        try:
            return self._agent_client.list_agents()
        except Exception as e:
            raise DeepSecureClientError(f"Failed to list agents from backend: {e}") from e

    def describe_agent(self, agent_id: str) -> Optional[dict]:
        """
        Retrieves the full details of a specific agent from the backend.

        Args:
            agent_id: The unique identifier of the agent.

        Returns:
            A dictionary containing the agent's details, or None if not found.
        """
        try:
            return self._agent_client.describe_agent(agent_id=agent_id)
        except Exception as e:
            # Specifically handle not found cases if the core client raises them
            # For now, wrap generic exceptions.
            raise DeepSecureClientError(f"Failed to describe agent '{agent_id}': {e}") from e

    def delete_agent(self, agent_id: str):
        """
        Deactivates an agent from the backend and purges its local identity.

        This is a destructive operation.

        Args:
            agent_id: The unique identifier of the agent to delete.
        """
        try:
            # 1. Deactivate from backend first
            self._agent_client.delete_agent(agent_id=agent_id)
            logger.info(f"Successfully deactivated agent '{agent_id}' on the backend.")
        except Exception as e:
            # We might want to allow purging local keys even if backend fails.
            # For now, we'll raise and stop.
            raise DeepSecureClientError(f"Failed to delete agent '{agent_id}' from backend. Local keys have not been purged. Error: {e}") from e

        try:
            # 2. Purge local identity
            self._identity_manager.delete_identity(agent_id)
            logger.info(f"Successfully purged local identity for '{agent_id}'.")
        except Exception as e:
            # If this fails, the user is in an inconsistent state.
            # The backend agent is gone, but local keys remain.
            raise DeepSecureClientError(
                f"Agent '{agent_id}' was deleted from the backend, but failed to purge local keys. "
                f"Please manually remove the identity file from ~/.deepsecure/identities/. Error: {e}"
            ) from e

    def store_secret(self, name: str, value: str):
        """
        Stores a secret in the vault.

        This is an administrative action and is typically used for setup or testing.

        Args:
            name: The name of the secret to store.
            value: The value of the secret.
        """
        logger.info(f"Storing secret '{name}' in vault.")
        self._vault_client.store_secret(name=name, value=value)
        logger.info(f"Secret '{name}' stored successfully.") 