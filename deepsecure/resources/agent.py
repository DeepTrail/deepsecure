"""
Represents a single Agent resource.
"""
from typing import Optional, Dict, Any, TYPE_CHECKING

from .credential import Credential

if TYPE_CHECKING:
    from ..types import SecretResourceType

# Forward reference for type hinting
if False:
    from .agents import Agents

class Agent:
    """
    Represents a single DeepSecure agent.

    This object is returned by the client and provides methods to interact
    with the agent, such as issuing credentials.
    """
    def __init__(self, client_ref: "Agents", agent_data: Dict[str, Any]):
        self._client_ref = client_ref
        
        self.id: str = agent_data["agent_id"]
        self.name: Optional[str] = agent_data.get("name")
        self.description: Optional[str] = agent_data.get("description")
        self.status: str = agent_data.get("status", "unknown")
        self.created_at: str = agent_data.get("created_at")
        self.public_key: str = agent_data.get("public_key")
        # Other fields can be added as needed

    def issue_credential(self, scope: str, ttl: int = 300) -> Credential:
        """
        Issues a new credential for this agent.

        This method simplifies the process of issuing a credential by handling
        the agent ID automatically.

        Args:
            scope: The scope of the credential (e.g., "read:files").
            ttl: The time-to-live for the credential in seconds.

        Returns:
            A Credential object containing the token and key material.
        """
        # Access the low-level vault client through the reference to the main DeepSecure client.
        vault_client = self._client_ref._client.vault
        
        # The low-level client handles the API call and returns a Pydantic model.
        credential_response = vault_client.issue(
            scope=scope, 
            agent_id=self.id, 
            ttl=ttl
        )
        
        # Convert the Pydantic model response to a dictionary and then
        # instantiate our high-level Credential resource object.
        return Credential(credential_data=credential_response.model_dump())

    def get_secret(self, secret_name: str, path: str = "/") -> "SecretResourceType":
        """
        Retrieve a secret using this agent's identity.
        
        This is a convenience method that calls the main client's get_secret
        method with this agent's ID automatically.
        
        Args:
            secret_name: The name of the secret to retrieve
            path: The path for the secret request (default: "/")
            
        Returns:
            The secret resource from the main client
        """
        return self._client_ref._parent_client.get_secret(
            agent_id=self.id,
            secret_name=secret_name,
            path=path
        )

    def to_dict(self) -> Dict[str, Any]:
        """Returns the agent's data as a dictionary."""
        return {
            "agent_id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "public_key": self.public_key,
        }

    def __repr__(self):
        return f"<Agent(id='{self.id}', name='{self.name}')>" 