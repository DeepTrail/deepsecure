import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Union, List, Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
import base64
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import struct
import binascii

from app.core.config import settings

# Get logger for this module
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    *,
    actions: Optional[List[str]] = None,
    resources: Optional[List[str]] = None,
) -> str:
    """
    Generates a new JWT access token.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode: dict[str, Any] = {
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "agent_id": str(subject),
    }

    if actions:
        to_encode["scope"] = " ".join(actions)
    if resources:
        to_encode["resources"] = resources
        
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
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

def verify_signature(
    *,
    public_key_bytes: bytes,
    message: str,
    signature_b64: str
) -> bool:
    """
    Verify a signature against a message using a raw public key.
    
    :param public_key_bytes: The raw 32-byte Ed25519 public key.
    :param message: The original message that was signed (the nonce).
    :param signature_b64: The base64-encoded signature.
    :return: True if the signature is valid, False otherwise.
    """
    try:
        # Load the public key from raw bytes
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        
        # Decode the signature from base64
        signature_bytes = base64.b64decode(signature_b64)
        
        # The message must be encoded to bytes for verification
        message_bytes = message.encode('utf-8')
        
        # verify() will raise an InvalidSignature exception if the signature is bad
        public_key.verify(signature_bytes, message_bytes)
        
        return True
    except InvalidSignature:
        # Signature is not valid for the given message
        return False
    except (binascii.Error, ValueError):
        # Error decoding base64 signature
        return False
    except Exception:
        # Any other unexpected errors during verification
        return False 