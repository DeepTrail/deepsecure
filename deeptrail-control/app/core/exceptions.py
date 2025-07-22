"""Exception classes for the application."""
from typing import Optional, Dict, Any


class BootstrapError(Exception):
    """Base exception for bootstrap-related errors."""
    def __init__(
        self, 
        message: str, 
        error_code: str = "BOOTSTRAP_ERROR",
        details: Optional[Dict[str, Any]] = None,
        platform: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.platform = platform
        super().__init__(self.message)


class TokenValidationError(BootstrapError):
    """Raised when platform token validation fails."""
    def __init__(
        self, 
        message: str, 
        platform: str,
        token_type: Optional[str] = None,
        validation_step: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.token_type = token_type
        self.validation_step = validation_step
        super().__init__(
            message=message,
            error_code="TOKEN_VALIDATION_FAILED",
            details=details,
            platform=platform
        )


class PolicyNotFoundError(BootstrapError):
    """Raised when no matching attestation policy is found."""
    def __init__(
        self, 
        platform: str,
        selector: str,
        available_policies: Optional[int] = None
    ):
        message = f"No attestation policy found for {platform} with selector: {selector}"
        details = {
            "selector": selector,
            "available_policies_count": available_policies
        }
        super().__init__(
            message=message,
            error_code="POLICY_NOT_FOUND",
            details=details,
            platform=platform
        )


class ExternalServiceError(BootstrapError):
    """Raised when external service calls fail."""
    def __init__(
        self, 
        service_name: str,
        operation: str,
        message: str,
        status_code: Optional[int] = None,
        retry_count: int = 0,
        platform: Optional[str] = None
    ):
        self.service_name = service_name
        self.operation = operation
        self.status_code = status_code
        self.retry_count = retry_count
        
        details = {
            "service": service_name,
            "operation": operation,
            "status_code": status_code,
            "retry_count": retry_count
        }
        
        super().__init__(
            message=f"{service_name} {operation} failed: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            details=details,
            platform=platform
        )


class AgentCreationError(BootstrapError):
    """Raised when agent creation in database fails."""
    def __init__(
        self, 
        agent_id: str,
        message: str,
        validation_errors: Optional[Dict[str, str]] = None
    ):
        self.agent_id = agent_id
        self.validation_errors = validation_errors or {}
        
        details = {
            "agent_id": agent_id,
            "validation_errors": self.validation_errors
        }
        
        super().__init__(
            message=f"Agent creation failed for {agent_id}: {message}",
            error_code="AGENT_CREATION_FAILED",
            details=details
        )


class NetworkTimeoutError(BootstrapError):
    """Raised when network operations timeout."""
    def __init__(
        self, 
        operation: str,
        timeout_seconds: float,
        platform: Optional[str] = None
    ):
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        
        details = {
            "operation": operation,
            "timeout_seconds": timeout_seconds
        }
        
        super().__init__(
            message=f"Network timeout after {timeout_seconds}s for operation: {operation}",
            error_code="NETWORK_TIMEOUT",
            details=details,
            platform=platform
        )


class RateLimitExceededError(BootstrapError):
    """Raised when rate limits are exceeded."""
    def __init__(
        self, 
        resource: str,
        limit: int,
        window_seconds: int,
        platform: Optional[str] = None
    ):
        self.resource = resource
        self.limit = limit
        self.window_seconds = window_seconds
        
        details = {
            "resource": resource,
            "limit": limit,
            "window_seconds": window_seconds
        }
        
        super().__init__(
            message=f"Rate limit exceeded for {resource}: {limit} requests per {window_seconds}s",
            error_code="RATE_LIMIT_EXCEEDED",
            details=details,
            platform=platform
        )


class ConfigurationError(BootstrapError):
    """Raised when bootstrap configuration is invalid."""
    def __init__(
        self, 
        setting: str,
        message: str,
        expected_value: Optional[str] = None
    ):
        self.setting = setting
        self.expected_value = expected_value
        
        details = {
            "setting": setting,
            "expected_value": expected_value
        }
        
        super().__init__(
            message=f"Configuration error for {setting}: {message}",
            error_code="CONFIGURATION_ERROR",
            details=details
        ) 