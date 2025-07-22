from pydantic import BaseModel, Field

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenRequest(BaseModel):
    """Schema for token request payload."""
    agent_id: str = Field(..., example="agent_f3b4c1a9")
    signed_nonce: str = Field(..., example="base64_encoded_signed_nonce")

# Potentially add TokenData schema if needed for decoding
# class TokenData(BaseModel):
#     sub: str | None = None # Subject (e.g., agent_id or credential_id)
#     # Add other expected claims like agent_id if needed

class AgentLogin(BaseModel):
    agent_id: str = Field(..., example="agent_f3b4c1a9")
    # Signature is typically base64 encoded bytes
    signature: str = Field(..., example="base64_encoded_signature_string") 