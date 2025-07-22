'''DeepSecure SDK Package'''

__version__ = "0.1.10"

from .client import Client
from .exceptions import (
    DeepSecureError,
    ApiError,
    VaultError,
    IdentityManagerError,
    DeepSecureClientError,
)

__all__ = [
    "Client",
    "DeepSecureError",
    "ApiError",
    "VaultError",
    "IdentityManagerError",
    "DeepSecureClientError",
    "__version__",
]

# Placeholder for package initialization 

# deepsecure package 
