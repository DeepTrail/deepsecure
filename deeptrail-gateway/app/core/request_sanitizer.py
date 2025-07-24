"""
Request Sanitization Module for DeepTrail Gateway

For Future - Enterprise Grade:
This module provides comprehensive request sanitization including:
- Advanced header cleaning and normalization
- Content sanitization and escaping
- Parameter validation and encoding
- Content-type validation
- Character encoding validation
- Malicious content removal

Current Implementation: Basic header sanitization for core PEP functionality
Based on OWASP Security Guidelines and Red Hat OpenShift WAF patterns.
"""

import re
import html
import json
import urllib.parse
import base64
import binascii
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

from fastapi import Request
from starlette.datastructures import Headers, QueryParams

logger = logging.getLogger(__name__)

class SanitizationLevel(str, Enum):
    """Sanitization levels for different security requirements."""
    STRICT = "strict"      # Maximum security, may break some functionality
    MODERATE = "moderate"  # Balanced security and functionality
    LENIENT = "lenient"    # Minimal sanitization, maximum compatibility

class ContentType(str, Enum):
    """Supported content types for sanitization."""
    JSON = "application/json"
    FORM_URLENCODED = "application/x-www-form-urlencoded"
    MULTIPART_FORM = "multipart/form-data"
    TEXT_PLAIN = "text/plain"
    TEXT_HTML = "text/html"
    XML = "application/xml"
    BINARY = "application/octet-stream"

@dataclass
class SanitizationConfig:
    """Configuration for request sanitization."""
    
    # For Future - Enterprise Grade: Advanced sanitization levels
    level: SanitizationLevel = SanitizationLevel.MODERATE
    
    # For Future - Enterprise Grade: Content type handling
    allowed_content_types: List[ContentType] = field(default_factory=lambda: [
        ContentType.JSON,
        ContentType.FORM_URLENCODED,
        ContentType.MULTIPART_FORM,
        ContentType.TEXT_PLAIN
    ])
    
    # For Future - Enterprise Grade: Character encoding
    allowed_encodings: List[str] = field(default_factory=lambda: [
        "utf-8", "ascii", "latin-1"
    ])
    
    # For Future - Enterprise Grade: Header sanitization
    blocked_headers: List[str] = field(default_factory=lambda: [
        "x-forwarded-for",
        "x-real-ip",
        "x-forwarded-proto",
        "host"
    ])
    
    # For Future - Enterprise Grade: Parameter limits
    max_param_length: int = 1024
    max_param_count: int = 100
    
    # For Future - Enterprise Grade: Content sanitization
    enable_html_escaping: bool = True
    enable_sql_injection_detection: bool = True
    enable_xss_detection: bool = True
    enable_script_removal: bool = True
    
    # For Future - Enterprise Grade: URL validation
    max_url_length: int = 2048
    allowed_url_schemes: List[str] = field(default_factory=lambda: ["http", "https"])
    blocked_url_patterns: List[str] = field(default_factory=list)

# For Future - Enterprise Grade: Malicious pattern detection
MALICIOUS_PATTERNS = {
    'sql_injection': [
        r'(\bunion\b.*\bselect\b)',
        r'(\bselect\b.*\bfrom\b)',
        r'(\binsert\b.*\binto\b)',
        r'(\bupdate\b.*\bset\b)',
        r'(\bdelete\b.*\bfrom\b)',
        r'(\bdrop\b.*\btable\b)',
        r'(\balter\b.*\btable\b)',
        r'(\bcreate\b.*\btable\b)',
        r'(\bexec\b.*\b\()',
        r'(\bsp_\w+)',
        r'(\bxp_\w+)',
    ],
    'xss': [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>',
        r'<link[^>]*>',
        r'<meta[^>]*>',
        r'<form[^>]*>',
        r'<input[^>]*>',
    ],
    'command_injection': [
        r'[;&|`$]',
        r'\.\./.*',
        r'/etc/passwd',
        r'/proc/.*',
        r'cmd\.exe',
        r'powershell',
        r'bash',
        r'sh\s',
    ],
    'path_traversal': [
        r'\.\./',
        r'\.\.\\',
        r'%2e%2e%2f',
        r'%2e%2e%5c',
        r'%252e%252e%252f',
        r'%252e%252e%255c',
    ]
}

# For Future - Enterprise Grade: Advanced sanitization result
@dataclass
class SanitizationResult:
    """Result of request sanitization."""
    sanitized_headers: Dict[str, str]
    sanitized_params: Dict[str, str]
    sanitized_body: Optional[bytes]
    warnings: List[str]
    violations: List[str]
    is_safe: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'sanitized_headers': self.sanitized_headers,
            'sanitized_params': self.sanitized_params,
            'warnings': self.warnings,
            'violations': self.violations,
            'is_safe': self.is_safe
        }

# For Future - Enterprise Grade: Request sanitizer class
class RequestSanitizer:
    """
    For Future - Enterprise Grade: Advanced request sanitizer.
    
    Current Implementation: Basic header sanitization only.
    """
    
    def __init__(self, config: SanitizationConfig = None):
        self.config = config or SanitizationConfig()
        self._compile_patterns()
    
    def _compile_patterns(self):
        """For Future - Enterprise Grade: Compile regex patterns for performance."""
        self.compiled_patterns = {}
        for category, patterns in MALICIOUS_PATTERNS.items():
            self.compiled_patterns[category] = [
                re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                for pattern in patterns
            ]
    
    def sanitize_request(self, request: Request) -> SanitizationResult:
        """
        For Future - Enterprise Grade: Comprehensive request sanitization.
        
        Current Implementation: Basic header sanitization only.
        """
        # For Future - Enterprise Grade: Full implementation
        # Current: Basic header sanitization
        sanitized_headers = self._sanitize_headers_basic(dict(request.headers))
        
        return SanitizationResult(
            sanitized_headers=sanitized_headers,
            sanitized_params={},  # For Future - Enterprise Grade
            sanitized_body=None,  # For Future - Enterprise Grade
            warnings=[],  # For Future - Enterprise Grade
            violations=[],  # For Future - Enterprise Grade
            is_safe=True  # For Future - Enterprise Grade: Proper validation
        )
    
    def _sanitize_headers_basic(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Basic header sanitization for core PEP functionality."""
        sanitized = {}
        
        for key, value in headers.items():
            # Convert to lowercase for consistent handling
            key_lower = key.lower()
            
            # Skip dangerous headers
            if key_lower in ['host', 'x-forwarded-for', 'x-real-ip']:
                continue
            
            # Basic value sanitization
            if value and len(value) < 8192:  # Basic length check
                sanitized[key] = value
        
        return sanitized
    
    # For Future - Enterprise Grade: Advanced methods
    def _sanitize_headers_advanced(self, headers: Dict[str, str]) -> Dict[str, str]:
        """For Future - Enterprise Grade: Advanced header sanitization."""
        pass
    
    def _sanitize_query_params(self, params: QueryParams) -> Dict[str, str]:
        """For Future - Enterprise Grade: Query parameter sanitization."""
        pass
    
    def _sanitize_body(self, body: bytes, content_type: str) -> Optional[bytes]:
        """For Future - Enterprise Grade: Body content sanitization."""
        pass
    
    def _detect_malicious_patterns(self, content: str) -> List[str]:
        """For Future - Enterprise Grade: Malicious pattern detection."""
        pass
    
    def _validate_encoding(self, content: str) -> bool:
        """For Future - Enterprise Grade: Character encoding validation."""
        pass
    
    def _escape_html(self, content: str) -> str:
        """For Future - Enterprise Grade: HTML escaping."""
        pass
    
    def _validate_url(self, url: str) -> bool:
        """For Future - Enterprise Grade: URL validation."""
        pass

# For Future - Enterprise Grade: Content-specific sanitizers
class JSONSanitizer:
    """For Future - Enterprise Grade: JSON content sanitization."""
    pass

class FormSanitizer:
    """For Future - Enterprise Grade: Form data sanitization."""
    pass

class XMLSanitizer:
    """For Future - Enterprise Grade: XML content sanitization."""
    pass

# Current Implementation: Basic sanitizer instance
sanitizer = RequestSanitizer()

# For Future - Enterprise Grade: Advanced sanitizer configurations
def get_strict_sanitizer() -> RequestSanitizer:
    """For Future - Enterprise Grade: Get strict sanitizer configuration."""
    pass

def get_lenient_sanitizer() -> RequestSanitizer:
    """For Future - Enterprise Grade: Get lenient sanitizer configuration."""
    pass 