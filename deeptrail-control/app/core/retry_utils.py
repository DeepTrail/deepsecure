"""
Utility functions for handling retries, timeouts, and circuit breaker patterns
in bootstrap operations.
"""
import asyncio
import time
import logging
from typing import Callable, Any, Optional, Dict, Union
from functools import wraps
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import ExternalServiceError, NetworkTimeoutError

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker for external service calls."""
    
    def __init__(
        self, 
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == 'open':
                if self.last_failure_time and \
                   time.time() - self.last_failure_time < self.recovery_timeout:
                    raise ExternalServiceError(
                        service_name="circuit_breaker",
                        operation=func.__name__,
                        message="Circuit breaker is OPEN - service unavailable"
                    )
                else:
                    self.state = 'half-open'
            
            try:
                result = func(*args, **kwargs)
                self.reset()
                return result
            except self.expected_exception as e:
                self.record_failure()
                raise
                
        return wrapper
    
    def record_failure(self):
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def reset(self):
        """Reset the circuit breaker."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'


def with_retry(
    max_attempts: int = 3,
    backoff_factor: float = 1.0,
    backoff_max: float = 60.0,
    retry_exceptions: tuple = (Exception,)
):
    """
    Decorator to add retry logic with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Factor for exponential backoff (seconds)
        backoff_max: Maximum backoff time (seconds)
        retry_exceptions: Tuple of exceptions that should trigger retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        # Final attempt failed
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    
                    # Calculate backoff time
                    backoff_time = min(backoff_factor * (2 ** attempt), backoff_max)
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} for {func.__name__} failed: {e}. "
                        f"Retrying in {backoff_time:.2f}s"
                    )
                    time.sleep(backoff_time)
                
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def create_requests_session_with_retry(
    total_retries: int = 3,
    backoff_factor: float = 0.3,
    status_forcelist: Optional[list] = None,
    timeout: float = 30.0
) -> requests.Session:
    """
    Create a requests session with built-in retry logic.
    
    Args:
        total_retries: Total number of retries
        backoff_factor: Backoff factor for retries
        status_forcelist: List of HTTP status codes to retry on
        timeout: Default timeout for requests
    
    Returns:
        Configured requests session
    """
    if status_forcelist is None:
        status_forcelist = [500, 502, 503, 504]
    
    retry_strategy = Retry(
        total=total_retries,
        status_forcelist=status_forcelist,
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        backoff_factor=backoff_factor
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Set default timeout
    original_request = session.request
    def request_with_timeout(*args, **kwargs):
        kwargs.setdefault('timeout', timeout)
        return original_request(*args, **kwargs)
    session.request = request_with_timeout
    
    return session


def timeout_handler(timeout_seconds: float):
    """
    Decorator to add timeout handling to functions.
    
    Args:
        timeout_seconds: Maximum time allowed for function execution
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                # For now, we'll use a simple approach
                # In production, this could use asyncio or threading for true timeouts
                result = func(*args, **kwargs)
                
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    logger.warning(
                        f"Function {func.__name__} took {elapsed:.2f}s "
                        f"(exceeded timeout of {timeout_seconds}s)"
                    )
                
                return result
                
            except Exception as e:
                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    raise NetworkTimeoutError(
                        operation=func.__name__,
                        timeout_seconds=timeout_seconds
                    )
                raise
                
        return wrapper
    return decorator


class ExternalServiceConfig:
    """Configuration for external service integrations."""
    
    # Kubernetes API configuration
    KUBERNETES_TIMEOUT = 10.0
    KUBERNETES_MAX_RETRIES = 3
    
    # AWS STS configuration  
    AWS_STS_TIMEOUT = 15.0
    AWS_STS_MAX_RETRIES = 3
    
    # Azure IMDS configuration
    AZURE_IMDS_TIMEOUT = 10.0
    AZURE_IMDS_MAX_RETRIES = 3
    AZURE_JWKS_CACHE_TTL = 3600  # 1 hour
    
    # Docker API configuration
    DOCKER_API_TIMEOUT = 5.0
    DOCKER_API_MAX_RETRIES = 2
    
    # Circuit breaker configuration
    CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60


# Pre-configured circuit breakers for external services
kubernetes_circuit_breaker = CircuitBreaker(
    failure_threshold=ExternalServiceConfig.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    recovery_timeout=ExternalServiceConfig.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    expected_exception=(requests.RequestException, Exception)
)

aws_circuit_breaker = CircuitBreaker(
    failure_threshold=ExternalServiceConfig.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    recovery_timeout=ExternalServiceConfig.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    expected_exception=Exception
)

azure_circuit_breaker = CircuitBreaker(
    failure_threshold=ExternalServiceConfig.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    recovery_timeout=ExternalServiceConfig.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    expected_exception=(requests.RequestException, Exception)
)

docker_circuit_breaker = CircuitBreaker(
    failure_threshold=ExternalServiceConfig.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    recovery_timeout=ExternalServiceConfig.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    expected_exception=Exception
) 