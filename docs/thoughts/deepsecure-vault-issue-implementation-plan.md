# DeepSecure Vault Issue Command Implementation Plan

This document outlines the implementation plan for the `deepsecure vault issue` command, which generates ephemeral credentials for AI agents and tools based on the design principles from `deepsecure-cli-ephermeral-creds-design.md`.

## Overview

The `vault issue` command will:

1. Generate ephemeral key pairs using Curve25519
2. Sign the ephemeral public key with the agent's long-term identity key
3. Format credentials as tokens with appropriate scope and TTL
4. Return credentials in a secure, usable format
5. Log the issuance for audit purposes

## Implementation Components

### 1. Core Components

- **VaultClient**: Core client for credential operations
- **KeyManager**: Manages key generation and signing operations
- **CredentialFormatter**: Formats credentials for output
- **AuditLogger**: Records credential issuance events

### 2. Command Interface

- **Command Parser**: Processes CLI arguments
- **Output Formatter**: Formats responses for user viewing

## Implementation Steps

### Phase 1: Basic Structure

1. Update `deepsecure/core/vault_client.py` with ephemeral credential functionality
2. Create `deepsecure/core/crypto/key_manager.py` for cryptographic operations
3. Enhance `vault.py` command implementation

### Phase 2: Cryptographic Implementation

1. Implement Curve25519 key generation
2. Add signing capabilities using Ed25519
3. Create secure credential format with JWT or similar

### Phase 3: Audit and Validation

1. Add audit logging for credential issuance
2. Implement validation hooks
3. Configure policy enforcement for credential issuance

## Detailed Implementation

### 1. Update vault_client.py

```python
class VaultClient:
    def issue_credential(self, scope: str, ttl: str, agent_id: Optional[str] = None, 
                        origin_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Issue an ephemeral credential with the specified scope and TTL.
        
        Args:
            scope: Scope of access (e.g., 'db:readonly', 'api:full')
            ttl: Time-to-live for the credential (e.g., '5m', '1h')
            agent_id: Optional agent identifier
            origin_context: Optional origin context for origin binding
            
        Returns:
            Dictionary with credential details
        """
        # 1. Get or create agent identity
        agent_identity = self._get_agent_identity(agent_id)
        
        # 2. Get origin context if not provided
        if not origin_context:
            origin_context = self._capture_origin_context()
        
        # 3. Generate ephemeral keypair
        ephemeral_keys = self.key_manager.generate_ephemeral_keypair()
        
        # 4. Create a context-bound message to sign
        context_message = self._create_context_bound_message(
            ephemeral_keys["public_key"], 
            origin_context
        )
        
        # 5. Sign with long-term identity key
        signature = self.key_manager.sign_context_bound_key(
            context_message, 
            agent_identity["private_key"]
        )
        
        # 6. Create credential with appropriate TTL
        expiry = self._calculate_expiry(ttl)
        credential = self._create_credential(
            agent_identity["id"],
            ephemeral_keys["public_key"],
            signature,
            scope,
            expiry,
            origin_context  # Include the origin context
        )
        
        # 7. Log issuance for audit
        self.audit_logger.log_credential_issuance(
            credential_id=credential["id"],
            agent_id=agent_identity["id"],
            scope=scope,
            ttl=ttl
        )
        
        return credential

    def verify_credential(self, credential: Dict[str, Any]) -> bool:
        """Verify that a credential is valid for the current origin context."""
        # Extract components from credential
        ephemeral_public_key = credential.get("ephemeral_public_key")
        signature = credential.get("signature")
        origin_context = credential.get("origin_context", {})
        agent_id = credential.get("agent_id")
        
        # Get the agent's identity public key
        agent_public_key = self._get_agent_public_key(agent_id)
        
        # Capture current context
        current_context = self._capture_origin_context()
        
        # Compare critical origin elements
        if not self._verify_origin_match(origin_context, current_context):
            return False
        
        # Recreate the context-bound message
        context_message = self.key_manager.create_context_bound_message(
            ephemeral_public_key, 
            origin_context
        )
        
        # Verify the signature
        try:
            identity_pub_bytes = base64.b64decode(agent_public_key)
            signature_bytes = base64.b64decode(signature)
            
            verifying_key = ed25519.Ed25519PublicKey.from_public_bytes(identity_pub_bytes)
            verifying_key.verify(signature_bytes, context_message)
            return True
        except Exception:
            return False

    def _verify_origin_match(self, original_context: Dict[str, Any], 
                            current_context: Dict[str, Any]) -> bool:
        """
        Verify the current origin context matches the original context
        according to the configured policy.
        """
        # Get the policy for origin verification
        policy = self._get_origin_verification_policy()
        
        # Enforce required match fields
        for field in policy.get("required_match", []):
            if original_context.get(field) != current_context.get(field):
                return False
        
        # Check if we have enough matching fields for "sufficient match" policy
        sufficient_fields = policy.get("sufficient_match", [])
        sufficient_threshold = policy.get("sufficient_threshold", len(sufficient_fields))
        
        if sufficient_fields:
            matches = sum(1 for field in sufficient_fields 
                          if original_context.get(field) == current_context.get(field))
            if matches < sufficient_threshold:
                return False
        
        return True
```

### 2. Create key_manager.py

```python
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519
from cryptography.hazmat.primitives import serialization
import base64
import uuid
import time
import json
import hashlib

class KeyManager:
    def generate_ephemeral_keypair(self) -> Dict[str, str]:
        """Generate a new X25519 ephemeral key pair"""
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize keys to bytes
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        # Encode as base64
        return {
            "private_key": base64.b64encode(private_bytes).decode('ascii'),
            "public_key": base64.b64encode(public_bytes).decode('ascii')
        }
    
    def sign_ephemeral_key(self, ephemeral_public_key: str, identity_private_key: str) -> str:
        """Sign an ephemeral public key with an identity private key"""
        # Decode keys from base64
        ephemeral_pub_bytes = base64.b64decode(ephemeral_public_key)
        identity_priv_bytes = base64.b64decode(identity_private_key)
        
        # Load the private key
        signing_key = ed25519.Ed25519PrivateKey.from_private_bytes(identity_priv_bytes)
        
        # Sign the ephemeral public key
        signature = signing_key.sign(ephemeral_pub_bytes)
        
        # Return base64-encoded signature
        return base64.b64encode(signature).decode('ascii')
    
    def create_credential_token(self, agent_id: str, ephemeral_public_key: str, 
                               signature: str, scope: str, expiry: int) -> Dict[str, Any]:
        """Create a formatted credential token"""
        credential_id = f"cred-{uuid.uuid4()}"
        
        credential = {
            "id": credential_id,
            "agent_id": agent_id,
            "ephemeral_public_key": ephemeral_public_key,
            "signature": signature,
            "scope": scope,
            "issued_at": int(time.time()),
            "expires_at": expiry
        }
        
        return credential
    
    def create_context_bound_message(self, ephemeral_public_key: str, 
                                    origin_context: Dict[str, Any]) -> bytes:
        """Create a context-bound message from the ephemeral key and origin context."""
        # Serialize the context with the ephemeral key
        context_data = {
            "ephemeral_public_key": ephemeral_public_key,
            "origin_context": origin_context
        }
        
        # Create a deterministic serialization
        serialized_data = json.dumps(context_data, sort_keys=True).encode('utf-8')
        
        # Hash the data to create a fixed-length message
        return hashlib.sha256(serialized_data).digest()
    
    def sign_context_bound_key(self, context_message: bytes, 
                              identity_private_key: str) -> str:
        """Sign a context-bound message with the identity private key."""
        # Decode private key from base64
        identity_priv_bytes = base64.b64decode(identity_private_key)
        
        # Load the private key
        signing_key = ed25519.Ed25519PrivateKey.from_private_bytes(identity_priv_bytes)
        
        # Sign the context-bound message
        signature = signing_key.sign(context_message)
        
        # Return base64-encoded signature
        return base64.b64encode(signature).decode('ascii')
```

### 3. Enhance vault.py Command

```python
@app.command("issue")
def issue(
    scope: str = typer.Option(..., help="Scope for the issued credential (e.g., db:readonly)"),
    ttl: str = typer.Option("5m", help="Time-to-live for the credential (e.g., 5m, 1h)"),
    agent_id: Optional[str] = typer.Option(None, help="Agent identifier (generated if not provided)"),
    output: str = typer.Option("text", help="Output format (text, json)")
):
    """Generate ephemeral credentials for AI agents and tools."""
    from deepsecure.core import vault_client
    from deepsecure import utils
    
    try:
        # Issue the credential
        credential = vault_client.client.issue_credential(
            scope=scope,
            ttl=ttl,
            agent_id=agent_id
        )
        
        # Format the output based on user preference
        if output.lower() == "json":
            utils.console.print_json(data=credential)
        else:
            utils.console.print(f"[bold green]Credential issued successfully![/]")
            utils.console.print(f"[bold]ID:[/] {credential['id']}")
            utils.console.print(f"[bold]Agent ID:[/] {credential['agent_id']}")
            utils.console.print(f"[bold]Scope:[/] {credential['scope']}")
            utils.console.print(f"[bold]Expires:[/] {utils.format_timestamp(credential['expires_at'])}")
            
            # Print the credential secret in a secure way
            utils.console.print("\n[bold yellow]Ephemeral Token (sensitive):[/]")
            utils.console.print(credential['ephemeral_public_key'])
            
    except Exception as e:
        utils.print_error(f"Error issuing credential: {str(e)}")
        raise typer.Exit(code=1)
```

## Testing Strategy

1. **Unit Tests**:
   - Test key generation and signing
   - Test TTL parsing and expiry calculation
   - Test credential formatting

2. **Integration Tests**:
   - Test end-to-end command execution
   - Test with various scope and TTL combinations
   - Verify audit logging

3. **Security Tests**:
   - Verify cryptographic implementation
   - Check credential revocation works
   - Test against replay attacks

## Next Steps

1. Implement the local version of the command with file-based storage
2. Add support for integration with external key management systems (HashiCorp Vault)
3. Implement the Noise Protocol integration for secure agent-to-agent communication
4. Add support for more advanced identity attestation methods

# Example policy configuration

origin_verification_policy = {
    # These fields must match exactly
    "required_match": ["device_id", "user_id"],

    # Need at least 2 of these fields to match
    "sufficient_match": ["ip_address", "network_id", "hostname", "process_id"],
    "sufficient_threshold": 2,
    
    # Maximum age of credential before origin needs to be reverified
    "max_age_without_reverification": 3600  # seconds
}
