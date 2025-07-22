class DeepSecureError(Exception):
    """Base exception for all DeepSecure client errors."""
    pass

class DeepSecureClientError(DeepSecureError):
    """Specific exception for client-side errors."""
    def __init__(self, message, response=None, error_details=None):
        super().__init__(message)
        self.response = response
        self.error_details = error_details

    def __str__(self):
        base_str = super().__str__()
        if self.response is not None:
            return f"{base_str} (Status: {self.response.status_code}, Response: {self.response.text})"
        return base_str

class IdentityManagerError(DeepSecureError):
    """Exceptions related to the IdentityManager."""
    pass

class ApiError(DeepSecureClientError):
    """Raised for general API errors."""
    pass

class AuthenticationError(DeepSecureClientError):
    """Raised for authentication specific errors."""
    pass 