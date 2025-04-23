'''Custom exceptions for DeepSecure CLI.'''

class DeepSecureError(Exception):
    """Base exception for DeepSecure CLI errors."""
    pass

class ApiError(DeepSecureError):
    """Raised when a backend API call fails."""
    pass

class AuthenticationError(DeepSecureError):
    """Raised for authentication related issues."""
    pass

class ConfigurationError(DeepSecureError):
    """Raised for configuration loading or validation errors."""
    pass

class VaultError(DeepSecureError):
    """Raised for vault specific operations."""
    pass

# Add more specific exceptions as needed 