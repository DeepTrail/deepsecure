from pydantic import BaseModel, Field
import uuid

# --- Schemas for Challenge-Response Authentication --- #

class ChallengeRequest(BaseModel):
    agent_id: str

class ChallengeResponse(BaseModel):
    """Schema for the response containing the challenge nonce."""
    nonce: str = Field(..., description="The single-use nonce that the agent must sign.")

class TokenRequest(BaseModel):
    """Schema for requesting an access token using a signed nonce."""
    agent_id: str = Field(..., description="The agent's unique identifier.")
    nonce: str = Field(..., description="The nonce that was signed.")
    signature: str = Field(..., description="The base64-encoded signature of the nonce.")

class KubernetesBootstrapRequest(BaseModel):
    """Schema for requesting agent identity using a Kubernetes Service Account Token."""
    sat: str = Field(..., description="The Kubernetes Service Account Token.")


class AWSBootstrapRequest(BaseModel):
    """Schema for requesting agent identity using an AWS STS GetCallerIdentity token."""
    token: str = Field(..., description="The base64 encoded, presigned AWS STS GetCallerIdentity request.")


class AzureBootstrapRequest(BaseModel):
    """Schema for requesting agent identity using an Azure Managed Identity token."""
    token: str = Field(..., description="The Azure Instance Metadata Service (IMDS) token.")


class DockerBootstrapRequest(BaseModel):
    """Schema for requesting agent identity using Docker container metadata."""
    container_id: str = Field(..., description="The Docker container ID.")
    runtime_token: str = Field(..., description="Runtime-generated token for container identity verification.")


class BootstrapResponse(BaseModel):
    """Schema for bootstrap response returning agent identity and keys."""
    agent_id: str = Field(..., description="The unique agent identifier.")
    private_key_b64: str = Field(..., description="Base64 encoded private key (returned only once).")
    public_key_b64: str = Field(..., description="Base64 encoded public key.") 