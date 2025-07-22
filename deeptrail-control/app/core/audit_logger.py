"""
Audit logging system for bootstrap operations.
Provides comprehensive security event logging with structured data,
compliance features, and integration with security monitoring systems.
"""
import json
import time
import uuid
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""
    BOOTSTRAP_ATTEMPT = "bootstrap_attempt"
    BOOTSTRAP_SUCCESS = "bootstrap_success"
    BOOTSTRAP_FAILURE = "bootstrap_failure"
    TOKEN_VALIDATION_START = "token_validation_start"
    TOKEN_VALIDATION_SUCCESS = "token_validation_success"
    TOKEN_VALIDATION_FAILURE = "token_validation_failure"
    SECURITY_VIOLATION = "security_violation"
    RATE_LIMIT_TRIGGERED = "rate_limit_triggered"
    REPLAY_DETECTED = "replay_detected"
    AGENT_CREATED = "agent_created"
    POLICY_MATCHED = "policy_matched"
    POLICY_NOT_FOUND = "policy_not_found"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Structured audit event for bootstrap operations."""
    
    # Core event identification
    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: str
    correlation_id: str
    
    # Platform and authentication context
    platform: str
    token_type: str
    operation: str
    
    # Request context
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    
    # Security context
    security_metadata: Optional[Dict[str, Any]] = None
    
    # Bootstrap-specific data
    agent_id: Optional[str] = None
    policy_id: Optional[str] = None
    namespace: Optional[str] = None
    service_account: Optional[str] = None
    
    # Result and error information
    success: Optional[bool] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    validation_steps: Optional[Dict[str, bool]] = None
    
    # Performance metrics
    duration_ms: Optional[float] = None
    
    # Additional context
    additional_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary for logging."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def to_json(self) -> str:
        """Convert audit event to JSON string."""
        event_dict = self.to_dict()
        # Convert enum values to strings
        if isinstance(event_dict.get('event_type'), AuditEventType):
            event_dict['event_type'] = event_dict['event_type'].value
        if isinstance(event_dict.get('severity'), AuditSeverity):
            event_dict['severity'] = event_dict['severity'].value
        return json.dumps(event_dict, ensure_ascii=False)


class BootstrapAuditor:
    """Audit logger for bootstrap operations."""
    
    def __init__(self, audit_logger_name: str = "bootstrap.audit"):
        self.audit_logger = logging.getLogger(audit_logger_name)
        
        # Configure structured logging for audit events
        if not self.audit_logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.INFO)
            
            # Use structured JSON format for audit logs
            formatter = logging.Formatter(
                '%(asctime)s | AUDIT | %(message)s'
            )
            handler.setFormatter(formatter)
            self.audit_logger.addHandler(handler)
            self.audit_logger.setLevel(logging.INFO)
            self.audit_logger.propagate = False  # Don't propagate to root logger
    
    def create_event_id(self) -> str:
        """Generate a unique event ID."""
        return f"audit-{uuid.uuid4()}"
    
    def get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()
    
    def log_bootstrap_attempt(
        self,
        correlation_id: str,
        platform: str,
        token_type: str,
        client_ip: str = None,
        user_agent: str = None,
        additional_data: Dict[str, Any] = None
    ) -> str:
        """Log a bootstrap attempt."""
        event_id = self.create_event_id()
        
        event = AuditEvent(
            event_id=event_id,
            event_type=AuditEventType.BOOTSTRAP_ATTEMPT,
            severity=AuditSeverity.MEDIUM,
            timestamp=self.get_timestamp(),
            correlation_id=correlation_id,
            platform=platform,
            token_type=token_type,
            operation="bootstrap",
            client_ip=client_ip,
            user_agent=user_agent,
            additional_data=additional_data
        )
        
        self.audit_logger.info(event.to_json())
        return event_id
    
    def log_bootstrap_success(
        self,
        correlation_id: str,
        platform: str,
        agent_id: str,
        policy_id: str = None,
        duration_ms: float = None,
        validation_steps: Dict[str, bool] = None,
        security_metadata: Dict[str, Any] = None,
        additional_data: Dict[str, Any] = None
    ):
        """Log successful bootstrap completion."""
        event = AuditEvent(
            event_id=self.create_event_id(),
            event_type=AuditEventType.BOOTSTRAP_SUCCESS,
            severity=AuditSeverity.LOW,
            timestamp=self.get_timestamp(),
            correlation_id=correlation_id,
            platform=platform,
            token_type="validated",
            operation="bootstrap",
            agent_id=agent_id,
            policy_id=policy_id,
            success=True,
            duration_ms=duration_ms,
            validation_steps=validation_steps,
            security_metadata=security_metadata,
            additional_data=additional_data
        )
        
        self.audit_logger.info(event.to_json())
    
    def log_bootstrap_failure(
        self,
        correlation_id: str,
        platform: str,
        error_code: str,
        error_message: str,
        validation_step: str = None,
        duration_ms: float = None,
        security_metadata: Dict[str, Any] = None,
        additional_data: Dict[str, Any] = None
    ):
        """Log bootstrap failure."""
        # Determine severity based on error type
        severity = AuditSeverity.HIGH
        if any(keyword in error_code.lower() for keyword in ['rate_limit', 'replay', 'security']):
            severity = AuditSeverity.CRITICAL
        
        event = AuditEvent(
            event_id=self.create_event_id(),
            event_type=AuditEventType.BOOTSTRAP_FAILURE,
            severity=severity,
            timestamp=self.get_timestamp(),
            correlation_id=correlation_id,
            platform=platform,
            token_type="invalid",
            operation="bootstrap",
            success=False,
            error_code=error_code,
            error_message=error_message,
            duration_ms=duration_ms,
            security_metadata=security_metadata,
            additional_data={
                "validation_step": validation_step,
                **(additional_data or {})
            }
        )
        
        self.audit_logger.error(event.to_json())
    
    def log_security_violation(
        self,
        correlation_id: str,
        platform: str,
        violation_type: str,
        details: Dict[str, Any],
        client_ip: str = None,
        severity: AuditSeverity = AuditSeverity.CRITICAL
    ):
        """Log security violations (replay, rate limit, etc.)."""
        event = AuditEvent(
            event_id=self.create_event_id(),
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=severity,
            timestamp=self.get_timestamp(),
            correlation_id=correlation_id,
            platform=platform,
            token_type="suspicious",
            operation="security_check",
            client_ip=client_ip,
            success=False,
            error_code=violation_type.upper(),
            error_message=f"Security violation: {violation_type}",
            additional_data=details
        )
        
        self.audit_logger.critical(event.to_json())
    
    def log_token_validation(
        self,
        correlation_id: str,
        platform: str,
        token_type: str,
        success: bool,
        validation_steps: Dict[str, bool] = None,
        error_details: Dict[str, Any] = None,
        duration_ms: float = None
    ):
        """Log token validation events."""
        event_type = (AuditEventType.TOKEN_VALIDATION_SUCCESS if success 
                     else AuditEventType.TOKEN_VALIDATION_FAILURE)
        severity = AuditSeverity.LOW if success else AuditSeverity.MEDIUM
        
        event = AuditEvent(
            event_id=self.create_event_id(),
            event_type=event_type,
            severity=severity,
            timestamp=self.get_timestamp(),
            correlation_id=correlation_id,
            platform=platform,
            token_type=token_type,
            operation="token_validation",
            success=success,
            duration_ms=duration_ms,
            validation_steps=validation_steps,
            additional_data=error_details
        )
        
        if success:
            self.audit_logger.info(event.to_json())
        else:
            self.audit_logger.warning(event.to_json())
    
    def log_agent_creation(
        self,
        correlation_id: str,
        agent_id: str,
        platform: str,
        policy_id: str = None,
        namespace: str = None,
        service_account: str = None
    ):
        """Log agent creation events."""
        event = AuditEvent(
            event_id=self.create_event_id(),
            event_type=AuditEventType.AGENT_CREATED,
            severity=AuditSeverity.MEDIUM,
            timestamp=self.get_timestamp(),
            correlation_id=correlation_id,
            platform=platform,
            token_type="validated",
            operation="agent_creation",
            agent_id=agent_id,
            policy_id=policy_id,
            namespace=namespace,
            service_account=service_account,
            success=True
        )
        
        self.audit_logger.info(event.to_json())
    
    def log_policy_match(
        self,
        correlation_id: str,
        platform: str,
        policy_id: str,
        selector: str,
        agent_name: str = None
    ):
        """Log policy matching events."""
        event = AuditEvent(
            event_id=self.create_event_id(),
            event_type=AuditEventType.POLICY_MATCHED,
            severity=AuditSeverity.LOW,
            timestamp=self.get_timestamp(),
            correlation_id=correlation_id,
            platform=platform,
            token_type="validated",
            operation="policy_matching",
            policy_id=policy_id,
            success=True,
            additional_data={
                "selector": selector,
                "agent_name": agent_name
            }
        )
        
        self.audit_logger.info(event.to_json())
    
    def log_policy_not_found(
        self,
        correlation_id: str,
        platform: str,
        selector: str,
        available_policies: int = None
    ):
        """Log policy not found events."""
        event = AuditEvent(
            event_id=self.create_event_id(),
            event_type=AuditEventType.POLICY_NOT_FOUND,
            severity=AuditSeverity.HIGH,
            timestamp=self.get_timestamp(),
            correlation_id=correlation_id,
            platform=platform,
            token_type="validated",
            operation="policy_matching",
            success=False,
            error_code="POLICY_NOT_FOUND",
            error_message=f"No matching policy found for selector: {selector}",
            additional_data={
                "selector": selector,
                "available_policies": available_policies
            }
        )
        
        self.audit_logger.warning(event.to_json())
    
    def create_bootstrap_context(
        self, 
        platform: str, 
        client_ip: str = None,
        user_agent: str = None
    ) -> Dict[str, Any]:
        """Create a bootstrap context for correlation across multiple audit events."""
        correlation_id = str(uuid.uuid4())
        
        context = {
            "correlation_id": correlation_id,
            "platform": platform,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "start_time": time.time()
        }
        
        return context


# Global audit logger instance
bootstrap_auditor = BootstrapAuditor() 