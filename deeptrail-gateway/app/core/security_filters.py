"""
Security filters for the DeepTrail Gateway.

For Future - Enterprise Grade:
This module implements comprehensive security filtering including:
- Advanced IP address filtering and blocking
- Sophisticated request size and rate limiting
- Header validation and sanitization
- Malicious payload detection
- Security policy enforcement

Current Implementation: Basic security filters for core PEP functionality
Based on OWASP security guidelines and industry WAF patterns.
"""

import re
import ipaddress
import time
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json
import logging

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

@dataclass
class SecurityConfig:
    """Configuration for security filters."""
    
    # IP filtering
    blocked_ip_ranges: List[str] = field(default_factory=lambda: [
        "127.0.0.0/8",      # Localhost
        "10.0.0.0/8",       # Private Class A
        "172.16.0.0/12",    # Private Class B
        "192.168.0.0/16",   # Private Class C
        "169.254.0.0/16",   # Link-local
        "::1/128",          # IPv6 localhost
        "fc00::/7",         # IPv6 private
        "fe80::/10"         # IPv6 link-local
    ])
    allowed_ip_ranges: List[str] = field(default_factory=list)
    
    # Request limits
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    max_header_size: int = 8192  # 8KB
    max_headers_count: int = 50
    max_url_length: int = 2048
    
    # Rate limiting
    rate_limit_requests: int = 100  # requests per window
    rate_limit_window: int = 60     # seconds
    rate_limit_burst: int = 20      # burst allowance
    
    # Content filtering
    blocked_file_extensions: Set[str] = field(default_factory=lambda: {
        ".exe", ".bat", ".cmd", ".scr", ".pif", ".com", ".jar", ".war"
    })
    
    # Header security
    required_headers: Set[str] = field(default_factory=lambda: {
        "X-Target-Base-URL"
    })
    
    blocked_headers: Set[str] = field(default_factory=lambda: {
        "X-Forwarded-Host",  # Prevent host header injection
        "X-Rewrite-URL",     # Prevent URL rewriting attacks
        "X-Original-URL"     # Prevent URL override attacks
    })
    
    # Malicious pattern detection
    enable_xss_protection: bool = True
    enable_sql_injection_protection: bool = True
    enable_command_injection_protection: bool = True
    enable_path_traversal_protection: bool = True

@dataclass
class SecurityViolation:
    """Represents a security violation."""
    violation_type: str
    severity: str  # "low", "medium", "high", "critical"
    message: str
    client_ip: str
    timestamp: datetime
    request_path: str
    user_agent: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

class RateLimiter:
    """Token bucket rate limiter with burst support."""
    
    def __init__(self, requests_per_window: int, window_seconds: int, burst_allowance: int):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.burst_allowance = burst_allowance
        self.clients: Dict[str, deque] = defaultdict(deque)
        self.burst_tokens: Dict[str, int] = defaultdict(lambda: burst_allowance)
        self.last_refill: Dict[str, float] = defaultdict(time.time)
    
    def is_allowed(self, client_ip: str) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is allowed under rate limiting."""
        now = time.time()
        client_requests = self.clients[client_ip]
        
        # Remove old requests outside the window
        cutoff = now - self.window_seconds
        while client_requests and client_requests[0] < cutoff:
            client_requests.popleft()
        
        # Refill burst tokens
        time_since_refill = now - self.last_refill[client_ip]
        if time_since_refill > 1.0:  # Refill every second
            tokens_to_add = int(time_since_refill * (self.burst_allowance / 60))
            self.burst_tokens[client_ip] = min(
                self.burst_allowance, 
                self.burst_tokens[client_ip] + tokens_to_add
            )
            self.last_refill[client_ip] = now
        
        # Check if request is allowed
        current_requests = len(client_requests)
        
        # Allow if under normal rate limit
        if current_requests < self.requests_per_window:
            client_requests.append(now)
            return True, {
                "requests_remaining": self.requests_per_window - current_requests - 1,
                "reset_time": cutoff + self.window_seconds,
                "burst_tokens": self.burst_tokens[client_ip]
            }
        
        # Allow if burst tokens available
        if self.burst_tokens[client_ip] > 0:
            self.burst_tokens[client_ip] -= 1
            client_requests.append(now)
            return True, {
                "requests_remaining": 0,
                "reset_time": cutoff + self.window_seconds,
                "burst_tokens": self.burst_tokens[client_ip],
                "burst_used": True
            }
        
        # Rate limited
        return False, {
            "requests_remaining": 0,
            "reset_time": cutoff + self.window_seconds,
            "burst_tokens": 0,
            "retry_after": int(cutoff + self.window_seconds - now)
        }

class MaliciousPatternDetector:
    """Detects malicious patterns in requests."""
    
    def __init__(self):
        # XSS patterns
        self.xss_patterns = [
            re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
            re.compile(r'javascript:', re.IGNORECASE),
            re.compile(r'on\w+\s*=', re.IGNORECASE),
            re.compile(r'<iframe[^>]*>', re.IGNORECASE),
            re.compile(r'<object[^>]*>', re.IGNORECASE),
            re.compile(r'<embed[^>]*>', re.IGNORECASE),
            re.compile(r'<link[^>]*>', re.IGNORECASE),
            re.compile(r'<meta[^>]*>', re.IGNORECASE),
        ]
        
        # SQL injection patterns
        self.sql_patterns = [
            re.compile(r'\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b', re.IGNORECASE),
            re.compile(r'[\'"]\s*;\s*--', re.IGNORECASE),
            re.compile(r'[\'"]\s*\|\|', re.IGNORECASE),
            re.compile(r'\b(and|or)\s+[\'"]\d+[\'"]?\s*=\s*[\'"]\d+[\'"]?', re.IGNORECASE),
            re.compile(r'[\'"]\s*\)\s*;\s*(drop|delete|update)', re.IGNORECASE),
        ]
        
        # Command injection patterns
        self.command_patterns = [
            re.compile(r'[;&|`$(){}[\]]', re.IGNORECASE),
            re.compile(r'\b(cat|ls|pwd|id|whoami|uname|ps|netstat|ifconfig|ping|curl|wget|nc|ncat|telnet|ssh|ftp|scp|rsync)\b', re.IGNORECASE),
            re.compile(r'[<>|&;`$(){}[\]]', re.IGNORECASE),
        ]
        
        # Path traversal patterns
        self.path_traversal_patterns = [
            re.compile(r'\.\./', re.IGNORECASE),
            re.compile(r'\.\.\\', re.IGNORECASE),
            re.compile(r'%2e%2e%2f', re.IGNORECASE),
            re.compile(r'%2e%2e%5c', re.IGNORECASE),
            re.compile(r'%252e%252e%252f', re.IGNORECASE),
        ]
    
    def detect_xss(self, content: str) -> List[str]:
        """Detect XSS patterns in content."""
        violations = []
        for pattern in self.xss_patterns:
            if pattern.search(content):
                violations.append(f"XSS pattern detected: {pattern.pattern}")
        return violations
    
    def detect_sql_injection(self, content: str) -> List[str]:
        """Detect SQL injection patterns in content."""
        violations = []
        for pattern in self.sql_patterns:
            if pattern.search(content):
                violations.append(f"SQL injection pattern detected: {pattern.pattern}")
        return violations
    
    def detect_command_injection(self, content: str) -> List[str]:
        """Detect command injection patterns in content."""
        violations = []
        for pattern in self.command_patterns:
            if pattern.search(content):
                violations.append(f"Command injection pattern detected: {pattern.pattern}")
        return violations
    
    def detect_path_traversal(self, content: str) -> List[str]:
        """Detect path traversal patterns in content."""
        violations = []
        for pattern in self.path_traversal_patterns:
            if pattern.search(content):
                violations.append(f"Path traversal pattern detected: {pattern.pattern}")
        return violations

class SecurityFilter:
    """Main security filter class."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.rate_limiter = RateLimiter(
            config.rate_limit_requests,
            config.rate_limit_window,
            config.rate_limit_burst
        )
        self.pattern_detector = MaliciousPatternDetector()
        self.violations: List[SecurityViolation] = []
        
        # Compile IP ranges
        self.blocked_networks = []
        for ip_range in config.blocked_ip_ranges:
            try:
                self.blocked_networks.append(ipaddress.ip_network(ip_range))
            except ValueError as e:
                logger.warning(f"Invalid IP range in blocked list: {ip_range}: {e}")
        
        self.allowed_networks = []
        for ip_range in config.allowed_ip_ranges:
            try:
                self.allowed_networks.append(ipaddress.ip_network(ip_range))
            except ValueError as e:
                logger.warning(f"Invalid IP range in allowed list: {ip_range}: {e}")
    
    def get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check X-Forwarded-For header first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to client host
        return request.client.host if request.client else "unknown"
    
    def is_ip_blocked(self, ip_str: str) -> bool:
        """Check if IP is blocked."""
        try:
            ip = ipaddress.ip_address(ip_str)
            
            # If allowed networks are specified, only allow those
            if self.allowed_networks:
                return not any(ip in network for network in self.allowed_networks)
            
            # Otherwise, check blocked networks
            return any(ip in network for network in self.blocked_networks)
        
        except ValueError:
            logger.warning(f"Invalid IP address: {ip_str}")
            return True  # Block invalid IPs
    
    def validate_headers(self, request: Request) -> List[SecurityViolation]:
        """Validate request headers."""
        violations = []
        client_ip = self.get_client_ip(request)
        
        # Check header count
        if len(request.headers) > self.config.max_headers_count:
            violations.append(SecurityViolation(
                violation_type="excessive_headers",
                severity="medium",
                message=f"Too many headers: {len(request.headers)} > {self.config.max_headers_count}",
                client_ip=client_ip,
                timestamp=datetime.now(),
                request_path=str(request.url.path),
                user_agent=request.headers.get("User-Agent"),
                details={"header_count": len(request.headers)}
            ))
        
        # Check for required headers
        for required_header in self.config.required_headers:
            if required_header not in request.headers:
                violations.append(SecurityViolation(
                    violation_type="missing_required_header",
                    severity="high",
                    message=f"Missing required header: {required_header}",
                    client_ip=client_ip,
                    timestamp=datetime.now(),
                    request_path=str(request.url.path),
                    user_agent=request.headers.get("User-Agent"),
                    details={"missing_header": required_header}
                ))
        
        # Check for blocked headers
        for header_name in request.headers:
            if header_name.lower() in {h.lower() for h in self.config.blocked_headers}:
                violations.append(SecurityViolation(
                    violation_type="blocked_header",
                    severity="high",
                    message=f"Blocked header detected: {header_name}",
                    client_ip=client_ip,
                    timestamp=datetime.now(),
                    request_path=str(request.url.path),
                    user_agent=request.headers.get("User-Agent"),
                    details={"blocked_header": header_name}
                ))
        
        # Check header sizes
        for header_name, header_value in request.headers.items():
            if len(header_value) > self.config.max_header_size:
                violations.append(SecurityViolation(
                    violation_type="oversized_header",
                    severity="medium",
                    message=f"Header too large: {header_name} ({len(header_value)} bytes)",
                    client_ip=client_ip,
                    timestamp=datetime.now(),
                    request_path=str(request.url.path),
                    user_agent=request.headers.get("User-Agent"),
                    details={"header_name": header_name, "size": len(header_value)}
                ))
        
        return violations
    
    def validate_url(self, request: Request) -> List[SecurityViolation]:
        """Validate request URL."""
        violations = []
        client_ip = self.get_client_ip(request)
        url_str = str(request.url)
        
        # Check URL length
        if len(url_str) > self.config.max_url_length:
            violations.append(SecurityViolation(
                violation_type="oversized_url",
                severity="medium",
                message=f"URL too long: {len(url_str)} > {self.config.max_url_length}",
                client_ip=client_ip,
                timestamp=datetime.now(),
                request_path=str(request.url.path),
                user_agent=request.headers.get("User-Agent"),
                details={"url_length": len(url_str)}
            ))
        
        # Check for blocked file extensions
        path = request.url.path.lower()
        for ext in self.config.blocked_file_extensions:
            if path.endswith(ext):
                violations.append(SecurityViolation(
                    violation_type="blocked_file_extension",
                    severity="high",
                    message=f"Blocked file extension: {ext}",
                    client_ip=client_ip,
                    timestamp=datetime.now(),
                    request_path=str(request.url.path),
                    user_agent=request.headers.get("User-Agent"),
                    details={"extension": ext}
                ))
        
        return violations
    
    def detect_malicious_patterns(self, request: Request, body: str = "") -> List[SecurityViolation]:
        """Detect malicious patterns in request."""
        violations = []
        client_ip = self.get_client_ip(request)
        
        # Combine all text content for analysis
        content_parts = [
            str(request.url),
            body,
            json.dumps(dict(request.headers)),
            str(request.query_params)
        ]
        content = " ".join(content_parts)
        
        # XSS detection
        if self.config.enable_xss_protection:
            xss_violations = self.pattern_detector.detect_xss(content)
            for violation_msg in xss_violations:
                violations.append(SecurityViolation(
                    violation_type="xss_attempt",
                    severity="high",
                    message=violation_msg,
                    client_ip=client_ip,
                    timestamp=datetime.now(),
                    request_path=str(request.url.path),
                    user_agent=request.headers.get("User-Agent"),
                    details={"pattern_type": "xss"}
                ))
        
        # SQL injection detection
        if self.config.enable_sql_injection_protection:
            sql_violations = self.pattern_detector.detect_sql_injection(content)
            for violation_msg in sql_violations:
                violations.append(SecurityViolation(
                    violation_type="sql_injection_attempt",
                    severity="critical",
                    message=violation_msg,
                    client_ip=client_ip,
                    timestamp=datetime.now(),
                    request_path=str(request.url.path),
                    user_agent=request.headers.get("User-Agent"),
                    details={"pattern_type": "sql_injection"}
                ))
        
        # Command injection detection
        if self.config.enable_command_injection_protection:
            cmd_violations = self.pattern_detector.detect_command_injection(content)
            for violation_msg in cmd_violations:
                violations.append(SecurityViolation(
                    violation_type="command_injection_attempt",
                    severity="critical",
                    message=violation_msg,
                    client_ip=client_ip,
                    timestamp=datetime.now(),
                    request_path=str(request.url.path),
                    user_agent=request.headers.get("User-Agent"),
                    details={"pattern_type": "command_injection"}
                ))
        
        # Path traversal detection
        if self.config.enable_path_traversal_protection:
            path_violations = self.pattern_detector.detect_path_traversal(content)
            for violation_msg in path_violations:
                violations.append(SecurityViolation(
                    violation_type="path_traversal_attempt",
                    severity="high",
                    message=violation_msg,
                    client_ip=client_ip,
                    timestamp=datetime.now(),
                    request_path=str(request.url.path),
                    user_agent=request.headers.get("User-Agent"),
                    details={"pattern_type": "path_traversal"}
                ))
        
        return violations
    
    async def filter_request(self, request: Request, body: bytes = b"") -> Optional[JSONResponse]:
        """
        Apply security filters to request.
        
        Returns:
            None if request is allowed, JSONResponse with error if blocked.
        """
        client_ip = self.get_client_ip(request)
        all_violations = []
        
        # IP filtering
        if self.is_ip_blocked(client_ip):
            violation = SecurityViolation(
                violation_type="blocked_ip",
                severity="high",
                message=f"IP address blocked: {client_ip}",
                client_ip=client_ip,
                timestamp=datetime.now(),
                request_path=str(request.url.path),
                user_agent=request.headers.get("User-Agent")
            )
            all_violations.append(violation)
            self.violations.append(violation)
            
            logger.warning(f"Blocked request from IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Access denied",
                    "message": "Your IP address is not allowed to access this resource",
                    "violation_id": f"ip_block_{int(time.time())}"
                }
            )
        
        # Rate limiting
        is_allowed, rate_info = self.rate_limiter.is_allowed(client_ip)
        if not is_allowed:
            violation = SecurityViolation(
                violation_type="rate_limit_exceeded",
                severity="medium",
                message=f"Rate limit exceeded for IP: {client_ip}",
                client_ip=client_ip,
                timestamp=datetime.now(),
                request_path=str(request.url.path),
                user_agent=request.headers.get("User-Agent"),
                details=rate_info
            )
            all_violations.append(violation)
            self.violations.append(violation)
            
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests from your IP address",
                    "retry_after": rate_info.get("retry_after", 60),
                    "violation_id": f"rate_limit_{int(time.time())}"
                },
                headers={"Retry-After": str(rate_info.get("retry_after", 60))}
            )
        
        # Request size validation
        if len(body) > self.config.max_request_size:
            violation = SecurityViolation(
                violation_type="oversized_request",
                severity="medium",
                message=f"Request too large: {len(body)} > {self.config.max_request_size}",
                client_ip=client_ip,
                timestamp=datetime.now(),
                request_path=str(request.url.path),
                user_agent=request.headers.get("User-Agent"),
                details={"request_size": len(body)}
            )
            all_violations.append(violation)
            self.violations.append(violation)
            
            logger.warning(f"Oversized request from IP: {client_ip} ({len(body)} bytes)")
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": "Request too large",
                    "message": f"Request size {len(body)} exceeds limit {self.config.max_request_size}",
                    "violation_id": f"size_limit_{int(time.time())}"
                }
            )
        
        # Header validation
        header_violations = self.validate_headers(request)
        all_violations.extend(header_violations)
        
        # URL validation
        url_violations = self.validate_url(request)
        all_violations.extend(url_violations)
        
        # Malicious pattern detection
        body_str = body.decode("utf-8", errors="ignore") if body else ""
        pattern_violations = self.detect_malicious_patterns(request, body_str)
        all_violations.extend(pattern_violations)
        
        # Check for critical violations
        critical_violations = [v for v in all_violations if v.severity == "critical"]
        if critical_violations:
            # Log all violations
            for violation in all_violations:
                self.violations.append(violation)
                logger.error(f"Security violation: {violation.violation_type} - {violation.message}")
            
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Security violation",
                    "message": "Request blocked due to security policy violation",
                    "violation_count": len(critical_violations),
                    "violation_id": f"security_{int(time.time())}"
                }
            )
        
        # Check for high severity violations
        high_violations = [v for v in all_violations if v.severity == "high"]
        if high_violations:
            # Log violations but potentially allow request based on policy
            for violation in all_violations:
                self.violations.append(violation)
                logger.warning(f"Security violation: {violation.violation_type} - {violation.message}")
            
            # For now, block high severity violations
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Security violation",
                    "message": "Request blocked due to security policy violation",
                    "violation_count": len(high_violations),
                    "violation_id": f"security_{int(time.time())}"
                }
            )
        
        # Log medium/low violations but allow request
        if all_violations:
            for violation in all_violations:
                self.violations.append(violation)
                logger.info(f"Security notice: {violation.violation_type} - {violation.message}")
        
        # Request is allowed
        return None
    
    def get_recent_violations(self, hours: int = 24) -> List[SecurityViolation]:
        """Get security violations from the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [v for v in self.violations if v.timestamp >= cutoff]
    
    def get_violation_stats(self) -> Dict[str, Any]:
        """Get statistics about security violations."""
        if not self.violations:
            return {"total_violations": 0}
        
        recent_violations = self.get_recent_violations(24)
        
        # Count by type
        type_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        ip_counts = defaultdict(int)
        
        for violation in recent_violations:
            type_counts[violation.violation_type] += 1
            severity_counts[violation.severity] += 1
            ip_counts[violation.client_ip] += 1
        
        return {
            "total_violations": len(self.violations),
            "recent_violations_24h": len(recent_violations),
            "violations_by_type": dict(type_counts),
            "violations_by_severity": dict(severity_counts),
            "top_violating_ips": dict(sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        } 