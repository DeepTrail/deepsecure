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
                               scope: str, ttl: str) -> None:
        """
        Log a specific event for credential issuance.
        
        Args:
            credential_id: The unique ID of the issued credential.
            agent_id: The ID of the agent the credential was issued to.
            scope: The scope string granted to the credential.
            ttl: The time-to-live string specified for the credential.
        """
        self.log_event("credential_issue", {
            "credential_id": credential_id,
            "agent_id": agent_id,
            "scope": scope,
            "ttl": ttl
            # TODO: Add origin context details if relevant for auditing.
        })
    
    def log_credential_revocation(self, credential_id: str, revoked_by: str) -> None:
        """
        Log a specific event for credential revocation.
        
        Args:
            credential_id: The unique ID of the credential being revoked.
            revoked_by: Identifier for the entity initiating the revocation 
                        (e.g., user ID, system process).
        """
        self.log_event("credential_revoke", {
            "credential_id": credential_id,
            "revoked_by": revoked_by
            # TODO: Add reason for revocation if available.
        })

# Singleton instance for easy global access.
# Consider using dependency injection in larger applications.
audit_logger = AuditLogger() 