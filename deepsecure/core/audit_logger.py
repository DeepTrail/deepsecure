"""Audit logging functionality for the DeepSecure CLI."""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# TODO: Consider adding log rotation (e.g., using logging.handlers.RotatingFileHandler).
# TODO: Allow configuration of log level and format.

class AuditLogger:
    """Logger for auditable events in DeepSecure CLI.

    Writes structured JSON logs to a file (default: ~/.deepsecure/logs/audit.log).
    Provides specific methods for common events like credential issuance/revocation.
    """
    
    def __init__(self, log_dir: Optional[str] = None, log_file_name: str = "audit.log"):
        """
        Initialize the audit logger and set up the log file handler.
        
        Args:
            log_dir: Directory to store audit logs. Defaults to `~/.deepsecure/logs`.
            log_file_name: Name of the audit log file. Defaults to `audit.log`.
        """
        if log_dir is None:
            log_dir = os.path.expanduser("~/.deepsecure/logs")
        
        self.log_dir = Path(log_dir)
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # TODO: Handle cases where log directory creation fails gracefully.
            print(f"[Error] Could not create log directory {self.log_dir}: {e}")
            # Fallback or raise an exception?
            raise
        
        # Use a specific logger name
        self.logger = logging.getLogger("deepsecure.audit")
        self.logger.setLevel(logging.INFO) # Log INFO level and above
        
        # Prevent adding multiple handlers if AuditLogger is instantiated multiple times
        if not self.logger.handlers:
            log_file = self.log_dir / log_file_name
            try:
                # Use a file handler
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                
                # Format logs as JSON strings
                # Each log record message will be a complete JSON object
                formatter = logging.Formatter("%(message)s")
                file_handler.setFormatter(formatter)
                
                # Add the handler to the logger
                self.logger.addHandler(file_handler)
            except IOError as e:
                # TODO: Handle log file opening errors.
                print(f"[Error] Could not open log file {log_file}: {e}")
                # Should we disable logging or raise?
                raise
    
    def log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """
        Log a generic auditable event with a structured JSON payload.
        
        Args:
            event_type: A string identifying the type of event 
                        (e.g., 'credential_issue', 'login_attempt').
            details: A dictionary containing specific details about the event.
                     This dictionary is merged into the final log entry.
        """
        timestamp = int(time.time())
        # ISO 8601 format is standard and includes timezone info if available
        formatted_time = datetime.fromtimestamp(timestamp).isoformat() 
        
        # Base log structure
        log_entry = {
            "timestamp": timestamp,
            "timestamp_iso": formatted_time,
            "event_type": event_type,
            # TODO: Add user context (e.g., authenticated user ID) if available.
            # TODO: Add invocation context (e.g., command-line arguments).
            **details # Merge event-specific details
        }
        
        try:
            # Log the JSON string as a single log message
            self.logger.info(json.dumps(log_entry, ensure_ascii=False))
        except Exception as e:
            # Failsafe: Log error if JSON serialization fails
            self.logger.error(f"Failed to log structured event: {e}. Event details: {details}")
            # TODO: Consider logging the raw details in a fallback format.
    
    def log_credential_issuance(self, credential_id: str, agent_id: str,
                               scope: str, ttl: str,
                               backend_issued: Optional[bool] = None) -> None:
        """
        Log a specific event for credential issuance.

        Args:
            credential_id: The unique ID of the issued credential.
            agent_id: The ID of the agent the credential was issued to.
            scope: The scope string granted to the credential.
            ttl: The time-to-live string specified for the credential.
            backend_issued: Optional flag indicating if issued via backend.
        """
        details = {
            "credential_id": credential_id,
            "agent_id": agent_id,
            "scope": scope,
            "ttl": ttl
        }
        if backend_issued is not None:
            details["backend_issued"] = backend_issued
        self.log_event("credential_issue", details)
    
    def log_credential_revocation(self, credential_id: str, revoked_by: str,
                               backend_revoked: Optional[bool] = None) -> None:
        """
        Log a specific event for credential revocation.

        Args:
            credential_id: The unique ID of the credential being revoked.
            revoked_by: Identifier for the entity initiating the revocation.
            backend_revoked: Optional flag indicating if revoked via backend.
        """
        details = {
            "credential_id": credential_id,
            "revoked_by": revoked_by
        }
        if backend_revoked is not None:
            details["backend_revoked"] = backend_revoked
        self.log_event("credential_revoke", details)

    def log_credential_rotation(self, agent_id: str, credential_type: str,
                               new_credential_ref: str, rotated_by: str,
                               backend_notified: Optional[bool] = None) -> None:
        """Log a specific event for credential rotation.

        Args:
            agent_id: The ID of the agent whose credential/key was rotated.
            credential_type: The type of credential rotated (e.g., 'agent-identity').
            new_credential_ref: A reference to the new credential/key.
            rotated_by: Identifier for the entity initiating the rotation.
            backend_notified: Optional flag indicating if backend was notified.
        """
        details = {
            "agent_id": agent_id,
            "credential_type": credential_type,
            "new_credential_ref": new_credential_ref,
            "rotated_by": rotated_by
        }
        if backend_notified is not None:
            details["backend_notified"] = backend_notified
        self.log_event("credential_rotate", details)

    def log_credential_issuance_failed(self, agent_id: str, scope: str, reason: str) -> None:
        """Log a failed credential issuance attempt."""
        self.log_event("credential_issue_failed", {
            "agent_id": agent_id,
            "scope": scope,
            "reason": reason
        })

    def log_credential_revocation_failed(self, credential_id: str, reason: str) -> None:
        """Log a failed credential revocation attempt."""
        self.log_event("credential_revoke_failed", {
            "credential_id": credential_id,
            "reason": reason
        })

    def log_credential_rotation_failed(self, agent_id: str, credential_type: str, reason: str) -> None:
        """Log a failed credential rotation attempt."""
        self.log_event("credential_rotate_failed", {
            "agent_id": agent_id,
            "credential_type": credential_type,
            "reason": reason
        })

# Singleton instance for easy global access.
# Consider using dependency injection in larger applications.
audit_logger = AuditLogger() 