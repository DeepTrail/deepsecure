'''Custom exceptions for DeepSecure CLI.

These provide more specific error types than standard Python exceptions.
'''

from typing import Optional

class DeepSecureError(Exception):
    """Base exception class for all DeepSecure CLI custom errors."""
    pass

class ApiError(DeepSecureError):
    """Raised when a backend API call fails or returns an error status."""
    def __init__(self, message, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message # Store message for easier access

    def __str__(self):
        if self.status_code:
            return f"(Status {self.status_code}) {self.message}"
        return self.message

class AuthenticationError(DeepSecureError):
    """Raised for authentication related issues, such as invalid tokens or failed login."""
    pass

class ConfigurationError(DeepSecureError):
    """Raised for errors related to loading or validating configuration."""
    # TODO: Add specific context to the error message (e.g., file path, setting name).
    pass

class VaultError(DeepSecureError):
    """Raised for errors specific to vault operations (e.g., credential issuance/revocation).
    
    Used for issues like failing to load/save local identities or invalid credential state.
    """
    pass

class CryptoError(DeepSecureError):
    """Raised for cryptographic operation failures (e.g., signing, verification, key generation)."""
    # TODO: Implement this exception where crypto operations might fail in KeyManager.
    pass

class AuditLoggerError(DeepSecureError):
    # ... existing code ...
    pass

class IdentityManagerError(DeepSecureError):
    """Raised for errors specific to identity management operations."""
    pass

class DeepSecureClientError(DeepSecureError):
    """Raised for general client-side errors not covered by more specific exceptions."""
    pass

# TODO: Add more specific exceptions as needed (e.g., PolicyError, SandboxError). 