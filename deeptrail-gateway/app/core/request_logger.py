"""
Request/Response Logging System for DeepTrail Gateway

For Future - Enterprise Grade:
This module provides comprehensive logging capabilities including:
- Structured logging with JSON format
- Security-aware sanitization of sensitive data
- Comprehensive audit trails
- Performance metrics and monitoring
- Advanced log aggregation and analysis

Current Implementation: Basic request logging for core PEP functionality
"""

import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from fastapi import Request, Response
from starlette.types import Message

# For Future - Enterprise Grade: Structured logging with structlog
# import structlog
# structlog.configure(...)

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """Log levels for request logging"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class RequestPhase(str, Enum):
    """For Future - Enterprise Grade: Request processing phases"""
    RECEIVED = "received"
    AUTHENTICATED = "authenticated"
    AUTHORIZED = "authorized"
    FORWARDED = "forwarded"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class LoggingConfig:
    """Configuration for request logging."""
    
    # Basic configuration
    enabled: bool = True
    log_level: str = "INFO"
    
    # For Future - Enterprise Grade: Advanced logging features
    log_headers: bool = False
    log_body: bool = False
    log_response_body: bool = False
    max_body_size: int = 1024
    sanitize_headers: bool = True
    log_timing: bool = True
    log_ip_address: bool = True
    audit_mode: bool = False

# For Future - Enterprise Grade: Header sanitization
class HeaderSanitizer:
    """For Future - Enterprise Grade: Sanitize headers for logging."""
    
    def __init__(self):
        # For Future - Enterprise Grade: Comprehensive sensitive header patterns
        self.sensitive_patterns = [
            r'.*authorization.*',
            r'.*token.*',
            r'.*key.*',
            r'.*secret.*',
            r'.*password.*',
            r'.*credential.*'
        ]
    
    def sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """For Future - Enterprise Grade: Sanitize sensitive headers."""
        # Current: Basic implementation
        sanitized = {}
        for key, value in headers.items():
            if any(pattern in key.lower() for pattern in ['authorization', 'token', 'key']):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        return sanitized

# For Future - Enterprise Grade: Metadata classes for structured logging
@dataclass
class RequestMetadata:
    """Metadata about the incoming request."""
    request_id: str
    method: str
    path: str
    client_ip: str
    user_agent: Optional[str] = None
    content_type: Optional[str] = None
    content_length: Optional[int] = None

@dataclass
class ResponseMetadata:
    """Metadata about the outgoing response."""
    status_code: int
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    headers: Optional[Dict[str, str]] = None

@dataclass
class TimingMetadata:
    """Timing information for request processing."""
    start_time: float
    end_time: Optional[float] = None
    processing_time: Optional[float] = None
    upstream_time: Optional[float] = None

@dataclass
class SecurityMetadata:
    """Security-related metadata."""
    jwt_valid: bool = False
    agent_id: Optional[str] = None
    policy_applied: bool = False
    sanitized: bool = False
    violations: List[str] = None

    def __post_init__(self):
        if self.violations is None:
            self.violations = []

@dataclass
class ProxyMetadata:
    """Proxy operation metadata."""
    target_url: Optional[str] = None
    target_host: Optional[str] = None
    upstream_status: Optional[int] = None
    retries: int = 0
    cache_hit: bool = False

@dataclass
class RequestLogEntry:
    """Complete log entry for a request."""
    request_metadata: RequestMetadata
    response_metadata: Optional[ResponseMetadata] = None
    timing_metadata: Optional[TimingMetadata] = None
    security_metadata: Optional[SecurityMetadata] = None
    proxy_metadata: Optional[ProxyMetadata] = None
    error_message: Optional[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "request": asdict(self.request_metadata),
            "response": asdict(self.response_metadata) if self.response_metadata else None,
            "timing": asdict(self.timing_metadata) if self.timing_metadata else None,
            "security": asdict(self.security_metadata) if self.security_metadata else None,
            "proxy": asdict(self.proxy_metadata) if self.proxy_metadata else None,
            "error": self.error_message,
            "warnings": self.warnings
        }

# For Future - Enterprise Grade: Request tracking
@dataclass
class RequestInfo:
    """For Future - Enterprise Grade: Comprehensive request information."""
    request_id: str
    method: str
    url: str
    client_ip: str
    user_agent: str
    headers: Dict[str, str]
    timestamp: datetime
    phase: RequestPhase
    processing_time: Optional[float] = None
    response_status: Optional[int] = None
    error_message: Optional[str] = None

# For Future - Enterprise Grade: Advanced request logger
class RequestLogger:
    """
    For Future - Enterprise Grade: Advanced request logger with structured logging.
    
    Current Implementation: Basic request logging for core PEP functionality.
    """
    
    def __init__(self, config: LoggingConfig = None):
        self.config = config or LoggingConfig()
        self.header_sanitizer = HeaderSanitizer()
        self.active_requests: Dict[str, RequestInfo] = {}
        
        # For Future - Enterprise Grade: Structured logger setup
        # self.logger = structlog.get_logger(__name__)
        self.logger = logging.getLogger(__name__)
    
    def log_request_start(self, request: Request) -> str:
        """Log the start of a request processing."""
        request_id = str(uuid.uuid4())[:8]
        
        # Current: Basic logging
        self.logger.info(
            f"[{request_id}] {request.method} {request.url.path} - Started",
            extra={
                'request_id': request_id,
                'method': request.method,
                'path': request.url.path,
                'client_ip': request.client.host if request.client else 'unknown'
            }
        )
        
        return request_id
    
    def log_request_end(self, request_id: str, status_code: int, processing_time: float):
        """Log the end of request processing."""
        self.logger.info(
            f"[{request_id}] Completed - Status: {status_code}, Time: {processing_time:.3f}s",
            extra={
                'request_id': request_id,
                'status_code': status_code,
                'processing_time': processing_time
            }
        )
    
    def log_request_error(self, request_id: str, error: Exception):
        """Log request processing errors."""
        self.logger.error(
            f"[{request_id}] Error: {str(error)}",
            extra={
                'request_id': request_id,
                'error': str(error),
                'error_type': type(error).__name__
            }
        )
    
    # For Future - Enterprise Grade: Advanced logging methods
    def track_request_phase(self, request_id: str, phase: RequestPhase):
        """For Future - Enterprise Grade: Track request processing phases."""
        pass
    
    def log_security_violation(self, request_id: str, violation: str):
        """For Future - Enterprise Grade: Log security violations."""
        pass
    
    def log_performance_metrics(self, request_id: str, metrics: Dict[str, Any]):
        """For Future - Enterprise Grade: Log performance metrics."""
        pass
    
    def get_request_stats(self) -> Dict[str, Any]:
        """For Future - Enterprise Grade: Get request statistics."""
        return {
            'active_requests': len(self.active_requests),
            'total_requests': 0,  # For Future - Enterprise Grade
            'average_response_time': 0.0  # For Future - Enterprise Grade
        }

# Current Implementation: Basic logger instance
_request_logger = None

def get_request_logger() -> RequestLogger:
    """Get the global request logger instance."""
    global _request_logger
    if _request_logger is None:
        _request_logger = RequestLogger()
    return _request_logger

def configure_request_logging(config: LoggingConfig):
    """Configure global request logging."""
    global _request_logger
    _request_logger = RequestLogger(config)

# For Future - Enterprise Grade: Advanced configuration functions
def setup_structured_logging():
    """For Future - Enterprise Grade: Setup structured logging with structlog."""
    pass

def setup_audit_logging():
    """For Future - Enterprise Grade: Setup audit logging."""
    pass

def setup_metrics_collection():
    """For Future - Enterprise Grade: Setup metrics collection."""
    pass 