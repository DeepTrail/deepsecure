"""
Represents a single Credential resource.
"""
from typing import Dict, Any

class Credential:
    """
    Represents a credential issued by the DeepSecure vault.
    
    This object holds the token and other metadata about the credential.
    It also contains the ephemeral key pair associated with the credential.
    """
    def __init__(self, credential_data: Dict[str, Any]):
        self.id: str = credential_data["credential_id"]
        self.token: str = credential_data["token"]
        self.status: str = credential_data["status"]
        self.scope: str = credential_data["scope"]
        self.expires_at: str = credential_data["expires_at"]
        self.ephemeral_public_key_b64: str = credential_data["ephemeral_public_key_b64"]
        self.ephemeral_private_key_b64: str = credential_data["ephemeral_private_key_b64"]
        
    def __repr__(self):
        return f"<Credential(id='{self.id}', scope='{self.scope}', status='{self.status}')>" 