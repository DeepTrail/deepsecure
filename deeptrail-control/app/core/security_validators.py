"""
Security validation utilities for bootstrap operations.
Enhanced with comprehensive audit logging for security events.
"""
import time
import hashlib
import hmac
import uuid
import logging
from typing import Dict, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from threading import Lock
from collections import defaultdict

from .exceptions import TokenValidationError, ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class SecurityContext:
    """Security context for token validation."""
    platform: str
    token_type: str
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    request_time: Optional[float] = None
    correlation_id: Optional[str] = None  # Add correlation ID for audit logging
    

class ReplayDetector:
    """
    In-memory replay detection for bootstrap tokens.
    Enhanced with audit logging for security monitoring.
    """
    
    def __init__(self, max_age_seconds: int = 300, max_entries: int = 10000):
        self.max_age_seconds = max_age_seconds  # 5 minutes
        self.max_entries = max_entries
        self.used_tokens: Dict[str, float] = {}
        self.lock = Lock()
    
    def is_replay(self, token_hash: str, context: SecurityContext = None) -> bool:
        """Check if a token hash has been used before (replay attack)."""
        with self.lock:
            current_time = time.time()
            
            # Clean up old entries
            self._cleanup_old_entries(current_time)
            
            # Check if token was already used
            if token_hash in self.used_tokens:
                used_time = self.used_tokens[token_hash]
                time_since_use = current_time - used_time
                
                logger.warning(f"Replay detected: token used {time_since_use:.2f}s ago")
                
                # Log security violation if context available
                if context and context.correlation_id:
                    from .audit_logger import bootstrap_auditor, AuditSeverity
                    bootstrap_auditor.log_security_violation(
                        correlation_id=context.correlation_id,
                        platform=context.platform,
                        violation_type="replay_attack",
                        details={
                            "token_hash": token_hash[:16] + "...",
                            "time_since_first_use": time_since_use,
                            "client_ip": context.client_ip,
                            "user_agent": context.user_agent
                        },
                        client_ip=context.client_ip,
                        severity=AuditSeverity.CRITICAL
                    )
                
                return True
            
            # Record this token usage
            self.used_tokens[token_hash] = current_time
            return False
    
    def _cleanup_old_entries(self, current_time: float):
        """Remove entries older than max_age_seconds."""
        cutoff_time = current_time - self.max_age_seconds
        old_hashes = [h for h, t in self.used_tokens.items() if t < cutoff_time]
        
        for old_hash in old_hashes:
            del self.used_tokens[old_hash]
        
        # If still too many entries, remove oldest
        if len(self.used_tokens) > self.max_entries:
            sorted_items = sorted(self.used_tokens.items(), key=lambda x: x[1])
            excess_count = len(self.used_tokens) - self.max_entries
            
            for hash_to_remove, _ in sorted_items[:excess_count]:
                del self.used_tokens[hash_to_remove]


class RateLimiter:
    """
    Rate limiter for bootstrap attempts.
    Enhanced with audit logging for security monitoring.
    """
    
    def __init__(self, max_attempts: int = 10, window_seconds: int = 300):
        self.max_attempts = max_attempts  # 10 attempts
        self.window_seconds = window_seconds  # 5 minutes
        self.attempts: Dict[str, list] = defaultdict(list)
        self.lock = Lock()
    
    def is_rate_limited(self, identifier: str, context: SecurityContext = None) -> Tuple[bool, int]:
        """
        Check if identifier is rate limited.
        
        Args:
            identifier: Client identifier (IP, user ID, etc.)
            context: Security context for audit logging
            
        Returns:
            Tuple of (is_limited, remaining_attempts)
        """
        with self.lock:
            current_time = time.time()
            cutoff_time = current_time - self.window_seconds
            
            # Clean up old attempts
            self.attempts[identifier] = [
                attempt_time for attempt_time in self.attempts[identifier]
                if attempt_time > cutoff_time
            ]
            
            attempt_count = len(self.attempts[identifier])
            
            if attempt_count >= self.max_attempts:
                # Log rate limit violation if context available
                if context and context.correlation_id:
                    from .audit_logger import bootstrap_auditor, AuditSeverity
                    bootstrap_auditor.log_security_violation(
                        correlation_id=context.correlation_id,
                        platform=context.platform,
                        violation_type="rate_limit_exceeded",
                        details={
                            "identifier": identifier,
                            "attempt_count": attempt_count,
                            "max_attempts": self.max_attempts,
                            "window_seconds": self.window_seconds,
                            "client_ip": context.client_ip,
                            "user_agent": context.user_agent
                        },
                        client_ip=context.client_ip,
                        severity=AuditSeverity.HIGH
                    )
                
                return True, 0
            
            # Record this attempt
            self.attempts[identifier].append(current_time)
            return False, self.max_attempts - attempt_count - 1


class SecurityValidator:
    """
    Comprehensive security validator for bootstrap operations.
    Enhanced with audit logging for all security events.
    """
    
    def __init__(self):
        self.replay_detector = ReplayDetector()
        self.rate_limiter = RateLimiter()
        
        # Security configuration
        self.max_token_age_seconds = 3600  # 1 hour
        self.max_future_skew_seconds = 300  # 5 minutes
        self.min_token_length = 50
        self.max_token_length = 100000  # 100KB
    
    def validate_token_security(
        self, 
        token: str, 
        security_context: SecurityContext,
        decoded_claims: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive security validation on a token with audit logging.
        
        Args:
            token: Raw token string
            security_context: Security context for validation and audit logging
            decoded_claims: Pre-decoded token claims (if available)
            
        Returns:
            Dictionary with validation results and security metadata
            
        Raises:
            TokenValidationError: If validation fails
        """
        validation_results = {
            "replay_check": False,
            "rate_limit_check": False,
            "format_validation": False,
            "timing_validation": False,
            "signature_validation": False,
            "security_metadata": {}
        }
        
        logger.info(f"Starting security validation for {security_context.platform} token")
        
        # 1. Basic format validation
        self._validate_token_format(token, security_context)
        validation_results["format_validation"] = True
        
        # 2. Rate limiting check with audit logging
        client_id = security_context.client_ip or "unknown"
        is_limited, remaining = self.rate_limiter.is_rate_limited(client_id, security_context)
        
        if is_limited:
            raise TokenValidationError(
                message="Rate limit exceeded for bootstrap attempts",
                platform=security_context.platform,
                token_type=security_context.token_type,
                validation_step="rate_limiting",
                details={
                    "client_id": client_id,
                    "max_attempts": self.rate_limiter.max_attempts,
                    "window_seconds": self.rate_limiter.window_seconds
                }
            )
        
        validation_results["rate_limit_check"] = True
        validation_results["security_metadata"]["remaining_attempts"] = remaining
        
        # 3. Replay detection with audit logging
        token_hash = self._compute_token_hash(token)
        
        if self.replay_detector.is_replay(token_hash, security_context):
            raise TokenValidationError(
                message="Token replay detected",
                platform=security_context.platform,
                token_type=security_context.token_type,
                validation_step="replay_detection",
                details={"token_hash": token_hash[:16] + "..."}  # Partial hash for logging
            )
        
        validation_results["replay_check"] = True
        
        # 4. Timing validation (if claims available)
        if decoded_claims:
            self._validate_token_timing(decoded_claims, security_context)
            validation_results["timing_validation"] = True
        
        # 5. Additional security checks with metadata
        validation_results["security_metadata"].update({
            "token_length": len(token),
            "token_hash": token_hash[:16] + "...",
            "validation_time": time.time(),
            "client_ip": security_context.client_ip,
            "user_agent": security_context.user_agent,
            "correlation_id": security_context.correlation_id
        })
        
        logger.info(f"Security validation completed for {security_context.platform} token")
        return validation_results
    
    def _validate_token_format(self, token: str, context: SecurityContext):
        """Validate basic token format and structure."""
        if not token or not isinstance(token, str):
            raise TokenValidationError(
                message="Token must be a non-empty string",
                platform=context.platform,
                token_type=context.token_type,
                validation_step="format_validation"
            )
        
        if len(token) < self.min_token_length:
            raise TokenValidationError(
                message=f"Token too short (minimum {self.min_token_length} characters)",
                platform=context.platform,
                token_type=context.token_type,
                validation_step="length_validation",
                details={"token_length": len(token)}
            )
        
        if len(token) > self.max_token_length:
            raise TokenValidationError(
                message=f"Token too long (maximum {self.max_token_length} characters)",
                platform=context.platform,
                token_type=context.token_type,
                validation_step="length_validation",
                details={"token_length": len(token)}
            )
        
        # Check for suspicious characters
        if any(char in token for char in ['\x00', '\n', '\r']):
            raise TokenValidationError(
                message="Token contains invalid characters",
                platform=context.platform,
                token_type=context.token_type,
                validation_step="character_validation"
            )
    
    def _validate_token_timing(self, claims: Dict[str, Any], context: SecurityContext):
        """Validate token timing claims (exp, iat, nbf)."""
        current_time = int(time.time())
        
        # Check expiration time
        exp = claims.get('exp')
        if exp:
            if current_time >= exp:
                expired_seconds = current_time - exp
                raise TokenValidationError(
                    message=f"Token expired {expired_seconds} seconds ago",
                    platform=context.platform,
                    token_type=context.token_type,
                    validation_step="expiry_check",
                    details={
                        "current_time": current_time,
                        "expires_at": exp,
                        "expired_seconds": expired_seconds
                    }
                )
        
        # Check issued at time
        iat = claims.get('iat')
        if iat:
            # Token issued too far in the past
            age_seconds = current_time - iat
            if age_seconds > self.max_token_age_seconds:
                raise TokenValidationError(
                    message=f"Token too old ({age_seconds} seconds)",
                    platform=context.platform,
                    token_type=context.token_type,
                    validation_step="age_validation",
                    details={
                        "current_time": current_time,
                        "issued_at": iat,
                        "age_seconds": age_seconds,
                        "max_age_seconds": self.max_token_age_seconds
                    }
                )
            
            # Token issued in the future (allowing for clock skew)
            if iat > current_time + self.max_future_skew_seconds:
                future_seconds = iat - current_time
                raise TokenValidationError(
                    message=f"Token issued {future_seconds} seconds in the future",
                    platform=context.platform,
                    token_type=context.token_type,
                    validation_step="future_validation",
                    details={
                        "current_time": current_time,
                        "issued_at": iat,
                        "future_seconds": future_seconds
                    }
                )
        
        # Check not before time
        nbf = claims.get('nbf')
        if nbf and current_time < nbf:
            early_seconds = nbf - current_time
            raise TokenValidationError(
                message=f"Token not valid for {early_seconds} more seconds",
                platform=context.platform,
                token_type=context.token_type,
                validation_step="not_before_validation",
                details={
                    "current_time": current_time,
                    "not_before": nbf,
                    "early_seconds": early_seconds
                }
            )
    
    def _compute_token_hash(self, token: str) -> str:
        """Compute a hash of the token for replay detection."""
        return hashlib.sha256(token.encode('utf-8')).hexdigest()
    
    def validate_audience(
        self, 
        claims: Dict[str, Any], 
        expected_audience: str,
        context: SecurityContext
    ):
        """Validate token audience claim."""
        aud = claims.get('aud')
        if not aud:
            raise TokenValidationError(
                message="Token missing audience claim",
                platform=context.platform,
                token_type=context.token_type,
                validation_step="audience_validation"
            )
        
        # Handle both string and list audiences
        audiences = [aud] if isinstance(aud, str) else aud
        
        if expected_audience not in audiences:
            raise TokenValidationError(
                message=f"Invalid audience. Expected: {expected_audience}",
                platform=context.platform,
                token_type=context.token_type,
                validation_step="audience_validation",
                details={
                    "expected_audience": expected_audience,
                    "token_audiences": audiences
                }
            )
    
    def validate_issuer(
        self, 
        claims: Dict[str, Any], 
        expected_issuer: str,
        context: SecurityContext
    ):
        """Validate token issuer claim."""
        iss = claims.get('iss')
        if not iss:
            raise TokenValidationError(
                message="Token missing issuer claim",
                platform=context.platform,
                token_type=context.token_type,
                validation_step="issuer_validation"
            )
        
        if iss != expected_issuer:
            raise TokenValidationError(
                message=f"Invalid issuer. Expected: {expected_issuer}",
                platform=context.platform,
                token_type=context.token_type,
                validation_step="issuer_validation",
                details={
                    "expected_issuer": expected_issuer,
                    "token_issuer": iss
                }
            )


# Global security validator instance
security_validator = SecurityValidator() 