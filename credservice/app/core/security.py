import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Union

from jose import jwt, JWTError
from passlib.context import CryptContext
import base64
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from app.core.config import settings

# Get logger for this module
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """Creates a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

# Function to decode token (will be used in dependencies)
def decode_token(token: str) -> dict | None:
    """Decodes the JWT token.
    Returns the payload if valid, None otherwise.
    """
    try:
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM]
        )
        return payload
    except JWTError:
        return None

# --- Signature Verification ---

def verify_signature(public_key_str: str, message: str, signature_b64: str) -> bool:
    """Verifies an Ed25519 signature against a public key.

    Args:
        public_key_str: The public key in OpenSSH format (e.g., "ssh-ed25519 AAAAC3...").
        message: The original message that was signed (expected to be utf-8 encoded).
        signature_b64: The base64 encoded signature.

    Returns:
        True if the signature is valid, False otherwise.
    """
    try:
        # 1. Decode Base64 signature
        signature_bytes = base64.b64decode(signature_b64)

        # 2. Load public key from OpenSSH format
        #    This expects the format "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAID..... comment"
        #    The actual key material is the base64 part after the type.
        parts = public_key_str.split()
        if len(parts) < 2 or parts[0] != "ssh-ed25519":
            # Basic format check
            logger.error(f"Invalid public key format: {public_key_str}")
            return False

        key_b64 = parts[1]
        key_bytes = base64.b64decode(key_b64)

        # The raw public key in Ed25519 is typically the last 32 bytes of the decoded blob
        # after skipping the key type identifier noise within the blob.
        # A more robust parser might be needed for complex cases, but this handles typical keys.
        # A simple heuristic: Ed25519 public keys are 32 bytes.
        # Find the start of the 32-byte key within the decoded structure.
        # This part is tricky and might need refinement based on exact key structure nuances.
        # Let's assume the key bytes decoded are structured like:
        # 4 bytes: length of key type string ("ssh-ed25519")
        # N bytes: key type string
        # 4 bytes: length of public key bytes (32)
        # 32 bytes: the actual public key
        # We try to parse this structure
        import struct
        offset = 0
        try:
            key_type_len = struct.unpack(">I", key_bytes[offset:offset+4])[0]
            offset += 4 + key_type_len
            pub_key_len = struct.unpack(">I", key_bytes[offset:offset+4])[0]
            offset += 4
            if pub_key_len != 32:
                 logger.error(f"Parsed public key length is not 32 bytes: {pub_key_len}")
                 return False
            raw_public_key_bytes = key_bytes[offset:offset+pub_key_len]

        except struct.error as e:
            logger.error(f"Could not parse SSH public key structure: {e}. Key bytes (decoded): {key_bytes!r}")
            # Fallback: Assume the key is just the raw base64 decoded value if simple
            # if len(key_bytes) == 32: # Simple case, maybe just base64 of raw key?
            #    raw_public_key_bytes = key_bytes
            # else:
            #    logger.error(f"Could not determine raw public key from: {public_key_str}")
            return False

        public_key = ed25519.Ed25519PublicKey.from_public_bytes(raw_public_key_bytes)

        # 3. Encode message to bytes
        message_bytes = message.encode('utf-8')

        # 4. Verify
        public_key.verify(signature_bytes, message_bytes)
        return True  # Signature is valid

    except (base64.binascii.Error, ValueError) as e:
        logger.error(f"Error decoding base64 signature or key: {e}")
        return False # Invalid base64 encoding
    except InvalidSignature:
        logger.warning(f"Invalid signature provided for message: {message}")
        return False # Signature does not match
    except Exception as e:
        # Catch any other unexpected errors during key loading or verification
        logger.error(f"Unexpected error during signature verification: {e}")
        return False 