"""Key management utilities for handling cryptographic operations."""

from typing import Dict, Any
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
import base64
import uuid
import time
import os

class KeyManager:
    """Manages cryptographic key operations for DeepSecure.

    Handles generation of ephemeral (X25519) and identity (Ed25519)
    key pairs, signing data, verifying signatures, and formatting
    credential tokens (basic structure).
    """
    
    def generate_ephemeral_keypair(self) -> Dict[str, str]:
        """
        Generate a new X25519 ephemeral key pair.

        Used for establishing secure communication channels via Diffie-Hellman.
        Keys are returned in raw byte format, base64 encoded.

        Returns:
            A dictionary containing 'private_key' and 'public_key',
            both base64-encoded strings.
        """
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize keys to raw bytes
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        # Encode as base64 strings for easier handling (e.g., in JSON)
        return {
            "private_key": base64.b64encode(private_bytes).decode('ascii'),
            "public_key": base64.b64encode(public_bytes).decode('ascii')
        }
    
    def generate_identity_keypair(self) -> Dict[str, str]:
        """
        Generate a new Ed25519 identity key pair for long-term agent identity.

        Used for signing and verifying data to prove agent identity.
        Keys are returned in raw byte format, base64 encoded.

        Returns:
            A dictionary containing 'private_key' and 'public_key',
            both base64-encoded strings.
        """
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize keys to raw bytes
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        # Encode as base64 strings
        return {
            "private_key": base64.b64encode(private_bytes).decode('ascii'),
            "public_key": base64.b64encode(public_bytes).decode('ascii')
        }
    
    def generate_identity_keypair_pem(self) -> tuple[str, str]:
        """
        Generate a new Ed25519 identity key pair for long-term agent identity,
        returning keys in PEM format.

        Returns:
            A tuple containing the private key and public key, both as PEM-encoded strings.
        """
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        return public_pem, private_pem
    
    def sign_ephemeral_key(self, ephemeral_public_key: str, identity_private_key: str) -> str:
        """
        Sign the raw bytes of an ephemeral public key using an identity private key.

        This binds the ephemeral key to the agent's long-term identity.

        Args:
            ephemeral_public_key: The base64-encoded ephemeral public key (X25519).
            identity_private_key: The base64-encoded identity private key (Ed25519).

        Returns:
            The base64-encoded Ed25519 signature.
            
        Raises:
            TypeError: If key decoding fails.
            ValueError: If private key bytes are invalid.
        """
        # TODO: Implement sign_context_bound_key as per plan to optionally sign context hash.
        
        # Decode keys from base64 to raw bytes
        ephemeral_pub_bytes = base64.b64decode(ephemeral_public_key)
        identity_priv_bytes = base64.b64decode(identity_private_key)
        
        # Load the Ed25519 private key
        signing_key = ed25519.Ed25519PrivateKey.from_private_bytes(identity_priv_bytes)
        
        # Sign the raw bytes of the ephemeral public key
        signature = signing_key.sign(ephemeral_pub_bytes)
        
        # Return base64-encoded signature
        return base64.b64encode(signature).decode('ascii')
    
    def verify_signature(self, ephemeral_public_key: str, signature: str, identity_public_key: str) -> bool:
        """
        Verify a signature over an ephemeral public key using the identity public key.

        Checks if the ephemeral public key was indeed signed by the corresponding
        identity private key.

        Args:
            ephemeral_public_key: Base64-encoded ephemeral public key (the message).
            signature: Base64-encoded signature to verify.
            identity_public_key: Base64-encoded identity public key (Ed25519).

        Returns:
            True if the signature is valid, False otherwise.
        """
        # TODO: Adapt for verifying context-bound signatures if implemented.
        try:
            # Decode from base64
            ephemeral_pub_bytes = base64.b64decode(ephemeral_public_key)
            signature_bytes = base64.b64decode(signature)
            identity_pub_bytes = base64.b64decode(identity_public_key)
            
            # Load the Ed25519 public key
            verifying_key = ed25519.Ed25519PublicKey.from_public_bytes(identity_pub_bytes)
            
            # Verify the signature against the raw ephemeral public key bytes
            verifying_key.verify(signature_bytes, ephemeral_pub_bytes)
            return True
        except (InvalidSignature, ValueError, TypeError):
            # ValueError for invalid key bytes, TypeError for bad base64, InvalidSignature
            return False
    
    def create_credential_token(self, agent_id: str, ephemeral_public_key: str, 
                               signature: str, scope: str, expiry: int) -> Dict[str, Any]:
        """
        Create a basic formatted dictionary representing a credential token.

        Note: This is a simple structure, not a standardized format like JWT.
        It omits the origin context, which is handled by VaultClient._create_credential.

        Args:
            agent_id: Identifier for the agent.
            ephemeral_public_key: Base64-encoded ephemeral public key.
            signature: Base64-encoded signature.
            scope: Scope of access granted.
            expiry: Expiration timestamp (Unix epoch).

        Returns:
            A dictionary containing the credential details.
        """
        # TODO: Consider generating a standardized token (JWT/PASETO) here.
        credential_id = f"cred-{uuid.uuid4()}"
        
        credential = {
            "id": credential_id,
            "agent_id": agent_id,
            "ephemeral_public_key": ephemeral_public_key,
            "signature": signature,
            "scope": scope,
            "issued_at": int(time.time()),
            "expires_at": expiry
            # Note: Origin context is added by the calling VaultClient method
        }
        
        return credential

    def decode_public_key_b64(self, public_key_b64: str) -> ed25519.Ed25519PublicKey:
        """Decodes a base64-encoded public key into a cryptography key object."""
        try:
            key_bytes = base64.b64decode(public_key_b64)
            if len(key_bytes) != 32:
                raise ValueError("Public key bytes must be 32 bytes long for Ed25519.")
            return ed25519.Ed25519PublicKey.from_public_bytes(key_bytes)
        except Exception as e:
            # Re-raise as a more specific error if desired, or just ValueError
            raise ValueError(f"Failed to decode or parse public key: {e}") from e
    
    def derive_public_key(self, private_key_b64: str) -> str:
        """
        Derive the public key from a private key.
        
        Args:
            private_key_b64: Base64-encoded private key.
            
        Returns:
            Base64-encoded public key.
        """
        try:
            private_key_bytes = base64.b64decode(private_key_b64)
            if len(private_key_bytes) != 32:
                raise ValueError("Private key bytes must be 32 bytes long for Ed25519.")
            
            # Load the private key
            private_key_obj = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            
            # Derive the public key
            public_key_obj = private_key_obj.public_key()
            
            # Serialize to raw bytes
            public_key_bytes = public_key_obj.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            
            # Return base64-encoded public key
            return base64.b64encode(public_key_bytes).decode('ascii')
        except Exception as e:
            raise ValueError(f"Failed to derive public key from private key: {e}") from e

# Singleton instance for easy access across the application.
key_manager = KeyManager() 