class DeepSecureClientError(Exception):
    """Base class for exceptions in the DeepSecure client."""
    pass

class NetworkError(DeepSecureClientError):
    """Raised for network-related issues (e.g., connection, timeout)."""
    def __init__(self, message: str, original_exception: Exception):
        super().__init__(f"{message}: {original_exception}")
        self.original_exception = original_exception

class APIError(DeepSecureClientError):
    """Raised when the API returns an error response."""
    def __init__(self, message: str, status_code: int = None, error_details: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_details = error_details if error_details else {}

    def __str__(self):
        if self.status_code:
            return f"API Error (Status {self.status_code}): {self.args[0]}. Details: {self.error_details}"
        return f"API Error: {self.args[0]}. Details: {self.error_details}"

class AuthenticationError(APIError):
    """Raised for authentication failures (401, 403)."""
    def __init__(self, message: str = "Authentication failed. Check your API token and permissions.", status_code: int = None, error_details: dict = None):
        super().__init__(message, status_code, error_details)

class NotFoundError(APIError):
    """Raised when a resource is not found (404)."""
    def __init__(self, resource_type: str = "Resource", resource_id: str = None, status_code: int = 404, error_details: dict = None):
        message = f"{resource_type} not found."
        if resource_id:
            message = f"{resource_type} with ID '{resource_id}' not found."
        super().__init__(message, status_code, error_details)

class InvalidRequestError(APIError):
    """Raised for invalid requests (400, 422). Typically validation errors."""
    def __init__(self, message: str = "Invalid request. Check parameters and payload.", status_code: int = None, error_details: dict = None):
        super().__init__(message, status_code, error_details)

class ServiceUnavailableError(APIError):
    """Raised when the service is unavailable (5xx)."""
    def __init__(self, message: str = "Service is currently unavailable. Please try again later.", status_code: int = None, error_details: dict = None):
        super().__init__(message, status_code, error_details)

class IdentityManagerError(DeepSecureClientError):
    """Raised for errors specific to local identity management operations (keyring, local files)."""
    pass 