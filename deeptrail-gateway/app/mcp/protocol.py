"""
MCP JSON-RPC 2.0 Protocol Handler

This module implements the JSON-RPC 2.0 protocol parser for MCP (Model Context Protocol)
communication. It provides:
- Request/response parsing and validation
- Method routing with pluggable handlers
- Standard JSON-RPC 2.0 error codes
- Security-conscious error messages (no internal details exposed)
- Request size limits to prevent DoS attacks

JSON-RPC 2.0 Specification: https://www.jsonrpc.org/specification
MCP Protocol Specification: https://modelcontextprotocol.io/specification

Supported MCP methods (handlers implemented in subsequent tasks):
- initialize: MCP session handshake
- tools/list: List available tools
- tools/call: Execute a tool
"""

import json
import logging
from enum import IntEnum, StrEnum
from typing import Any, Callable, Awaitable, Union

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# Maximum request size in bytes (1 MB to prevent DoS)
MAX_REQUEST_SIZE = 1024 * 1024


class JsonRpcErrorCode(IntEnum):
    """
    Standard JSON-RPC 2.0 error codes and MCP-specific extensions.
    
    Standard codes:
    - PARSE_ERROR (-32700): Invalid JSON
    - INVALID_REQUEST (-32600): Invalid JSON-RPC request
    - METHOD_NOT_FOUND (-32601): Method not found
    - INVALID_PARAMS (-32602): Invalid method parameters
    - INTERNAL_ERROR (-32603): Internal server error
    
    MCP-specific codes (reserved range -32000 to -32099):
    - POLICY_UNAVAILABLE (-32000): Policy service unavailable
    - PERMISSION_DENIED (-32001): Agent lacks permission for operation
    - SESSION_INVALID (-32002): Invalid or expired MCP session
    - CREDENTIAL_ERROR (-32003): Credential injection failed
    """
    # Standard JSON-RPC 2.0 error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # MCP-specific error codes (server error range)
    POLICY_UNAVAILABLE = -32000
    PERMISSION_DENIED = -32001
    SESSION_INVALID = -32002
    CREDENTIAL_ERROR = -32003


class MCPMethod(StrEnum):
    """
    Supported MCP methods.
    
    These are the core methods required for Virtual MCP Server MVP:
    - initialize: Establish MCP session
    - tools/list: List available tools (filtered by permissions)
    - tools/call: Execute a tool with credential injection
    """
    INITIALIZE = "initialize"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    
    # Notifications (no response expected)
    INITIALIZED = "notifications/initialized"
    CANCELLED = "notifications/cancelled"


class JsonRpcRequest(BaseModel):
    """
    JSON-RPC 2.0 request model.
    
    Attributes:
        jsonrpc: Protocol version, must be "2.0"
        id: Request identifier (string, int, or null for notifications)
        method: The method name to invoke
        params: Optional parameters for the method
    """
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Union[str, int, None] = Field(default=None, description="Request ID")
    method: str = Field(..., description="Method name to invoke")
    params: dict[str, Any] | None = Field(default=None, description="Method parameters")
    
    @field_validator("jsonrpc")
    @classmethod
    def validate_jsonrpc_version(cls, v: str) -> str:
        """Validate that jsonrpc version is exactly '2.0'."""
        if v != "2.0":
            raise ValueError("jsonrpc must be '2.0'")
        return v
    
    @field_validator("method")
    @classmethod
    def validate_method_not_empty(cls, v: str) -> str:
        """Validate that method is not empty."""
        if not v or not v.strip():
            raise ValueError("method must not be empty")
        return v

    @property
    def is_notification(self) -> bool:
        """Check if this is a notification (no id means no response expected)."""
        return self.id is None


class JsonRpcError(BaseModel):
    """
    JSON-RPC 2.0 error object.
    
    Attributes:
        code: Error code (standard or MCP-specific)
        message: Short error description
        data: Optional additional error data
    """
    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: Any | None = Field(default=None, description="Additional error data")


class JsonRpcResponse(BaseModel):
    """
    JSON-RPC 2.0 response model.
    
    Either result or error must be present, but not both.
    
    Attributes:
        jsonrpc: Protocol version, always "2.0"
        id: Request identifier (matches the request id)
        result: Success result (mutually exclusive with error)
        error: Error object (mutually exclusive with result)
    """
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Union[str, int, None] = Field(default=None, description="Request ID")
    result: Any | None = Field(default=None, description="Method result")
    error: JsonRpcError | None = Field(default=None, description="Error object")
    
    @model_validator(mode="after")
    def validate_result_xor_error(self) -> "JsonRpcResponse":
        """Validate that exactly one of result or error is present."""
        has_result = self.result is not None
        has_error = self.error is not None
        
        # Both present is invalid
        if has_result and has_error:
            raise ValueError("response cannot have both result and error")
        
        return self
    
    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """
        Serialize response, excluding null result/error fields.
        
        JSON-RPC 2.0 requires that:
        - On success: result is present, error is absent
        - On error: error is present, result is absent
        """
        data = super().model_dump(**kwargs)
        # Remove null fields that shouldn't be in the response
        if self.result is None and self.error is not None:
            data.pop("result", None)
        elif self.error is None and self.result is not None:
            data.pop("error", None)
        return data


# Type alias for handler functions
HandlerFunc = Callable[[dict[str, Any]], Awaitable[Any]]


class MCPProtocolHandler:
    """
    Handles MCP JSON-RPC 2.0 protocol parsing and method routing.
    
    This class is the entry point for all MCP communication. It:
    - Parses raw JSON-RPC 2.0 requests
    - Validates request structure and size
    - Routes methods to registered handlers
    - Returns properly formatted JSON-RPC 2.0 responses
    - Ensures security by not exposing internal errors
    
    Usage:
        handler = MCPProtocolHandler(max_request_size=1024*1024)
        
        # Register method handlers
        handler.register_handler("initialize", initialize_handler)
        handler.register_handler("tools/list", tools_list_handler)
        handler.register_handler("tools/call", tools_call_handler)
        
        # Handle incoming request
        response = await handler.handle_request(raw_body)
    """
    
    def __init__(self, max_request_size: int = MAX_REQUEST_SIZE):
        """
        Initialize the protocol handler.
        
        Args:
            max_request_size: Maximum allowed request size in bytes.
                              Defaults to 1 MB.
        """
        self._handlers: dict[str, HandlerFunc] = {}
        self._max_request_size = max_request_size
        logger.debug(f"MCPProtocolHandler initialized with max_request_size={max_request_size}")
    
    def register_handler(self, method: str, handler: HandlerFunc) -> None:
        """
        Register a handler for an MCP method.
        
        Args:
            method: The method name (e.g., "initialize", "tools/list")
            handler: Async function that takes params dict and returns result
        
        Note:
            Handlers are implemented in subsequent tasks (B2, B6, B7).
            This method allows pluggable handler registration.
        """
        self._handlers[method] = handler
        logger.debug(f"Registered handler for method: {method}")
    
    def unregister_handler(self, method: str) -> bool:
        """
        Unregister a handler for an MCP method.
        
        Args:
            method: The method name to unregister
            
        Returns:
            True if handler was removed, False if not found
        """
        if method in self._handlers:
            del self._handlers[method]
            logger.debug(f"Unregistered handler for method: {method}")
            return True
        return False
    
    def get_registered_methods(self) -> list[str]:
        """
        Get list of registered method names.
        
        Returns:
            List of method names that have handlers registered
        """
        return list(self._handlers.keys())
    
    async def handle_request(
        self,
        raw_body: bytes,
        context: dict[str, Any] | None = None
    ) -> JsonRpcResponse | list[JsonRpcResponse] | None:
        """
        Parse and route an MCP request.
        
        This is the main entry point for handling incoming MCP requests.
        
        Args:
            raw_body: Raw request body as bytes
            context: Optional context dict passed to handlers (e.g., session info)
        
        Returns:
            JsonRpcResponse for single requests
            list[JsonRpcResponse] for batch requests
            None for notifications (no response expected)
        
        Security:
            - Validates request size to prevent DoS
            - Does not expose internal error details
            - Logs errors for debugging without exposing to client
        """
        # Security: Check request size before parsing
        if len(raw_body) > self._max_request_size:
            logger.warning(f"Request size {len(raw_body)} exceeds limit {self._max_request_size}")
            return self._error_response(
                None,
                JsonRpcErrorCode.INVALID_REQUEST,
                "Request too large"
            )
        
        # Parse JSON
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return self._error_response(
                None,
                JsonRpcErrorCode.PARSE_ERROR,
                "Parse error"
            )
        
        # Handle batch requests (array of requests)
        if isinstance(data, list):
            return await self._handle_batch(data, context)
        
        # Handle single request
        return await self._handle_single(data, context)
    
    async def _handle_batch(
        self,
        requests: list[Any],
        context: dict[str, Any] | None
    ) -> list[JsonRpcResponse] | JsonRpcResponse:
        """
        Handle a batch of JSON-RPC requests.
        
        Args:
            requests: List of request objects
            context: Optional context passed to handlers
            
        Returns:
            List of responses (excluding notifications)
        """
        if not requests:
            return self._error_response(
                None,
                JsonRpcErrorCode.INVALID_REQUEST,
                "Invalid Request: empty batch"
            )
        
        responses: list[JsonRpcResponse] = []
        
        for request_data in requests:
            response = await self._handle_single(request_data, context)
            # Only include non-notification responses
            if response is not None:
                responses.append(response)
        
        # If all requests were notifications, return empty array
        return responses if responses else []
    
    async def _handle_single(
        self,
        data: Any,
        context: dict[str, Any] | None
    ) -> JsonRpcResponse | None:
        """
        Handle a single JSON-RPC request.
        
        Args:
            data: Parsed request data (dict expected)
            context: Optional context passed to handler
            
        Returns:
            JsonRpcResponse or None for notifications
        """
        # Validate request is a dict
        if not isinstance(data, dict):
            return self._error_response(
                None,
                JsonRpcErrorCode.INVALID_REQUEST,
                "Invalid Request"
            )
        
        # Parse and validate request structure
        try:
            request = JsonRpcRequest(**data)
        except Exception as e:
            # Get request id if present for error response
            request_id = data.get("id") if isinstance(data, dict) else None
            logger.debug(f"Request validation error: {e}")
            return self._error_response(
                request_id,
                JsonRpcErrorCode.INVALID_REQUEST,
                "Invalid Request"
            )
        
        # Notifications don't get responses
        if request.is_notification:
            logger.debug(f"Received notification: {request.method}")
            # Still try to handle notification methods
            await self._invoke_handler(request, context)
            return None
        
        # Route to handler
        handler = self._handlers.get(request.method)
        if not handler:
            logger.debug(f"Method not found: {request.method}")
            return self._error_response(
                request.id,
                JsonRpcErrorCode.METHOD_NOT_FOUND,
                "Method not found"
            )
        
        # Invoke handler
        try:
            result = await self._invoke_handler(request, context)
            return JsonRpcResponse(id=request.id, result=result)
        except MCPError as e:
            # MCP-specific errors can include their message
            logger.warning(f"MCP error in {request.method}: {e.message}")
            return self._error_response(
                request.id,
                e.code,
                e.message,
                e.data
            )
        except Exception as e:
            # Generic errors - don't expose internal details
            logger.error(f"Internal error handling {request.method}: {e}", exc_info=True)
            return self._error_response(
                request.id,
                JsonRpcErrorCode.INTERNAL_ERROR,
                "Internal error"
            )
    
    async def _invoke_handler(
        self,
        request: JsonRpcRequest,
        context: dict[str, Any] | None
    ) -> Any:
        """
        Invoke the registered handler for a request.
        
        Args:
            request: Validated JSON-RPC request
            context: Optional context dict
            
        Returns:
            Handler result
            
        Raises:
            MCPError: For MCP-specific errors
            Exception: For unexpected errors
        """
        handler = self._handlers.get(request.method)
        if not handler:
            raise MCPError(
                JsonRpcErrorCode.METHOD_NOT_FOUND,
                "Method not found"
            )
        
        params = request.params or {}
        
        # Add context to params if provided
        if context:
            params = {**params, "_context": context}
        
        return await handler(params)
    
    def _error_response(
        self,
        request_id: str | int | None,
        code: int,
        message: str,
        data: Any = None
    ) -> JsonRpcResponse:
        """
        Create a JSON-RPC error response.
        
        Args:
            request_id: The request ID (None if unknown)
            code: Error code from JsonRpcErrorCode
            message: Human-readable error message
            data: Optional additional error data
            
        Returns:
            Formatted JsonRpcResponse with error
        """
        error = JsonRpcError(code=code, message=message, data=data)
        return JsonRpcResponse(id=request_id, error=error)


class MCPError(Exception):
    """
    Exception class for MCP-specific errors.
    
    Use this to raise errors that should be returned to the client
    with specific error codes and messages.
    
    Usage:
        raise MCPError(JsonRpcErrorCode.PERMISSION_DENIED, "Access denied to tool")
    """
    
    def __init__(
        self,
        code: int | JsonRpcErrorCode,
        message: str,
        data: Any = None
    ):
        """
        Initialize MCP error.
        
        Args:
            code: Error code from JsonRpcErrorCode
            message: Human-readable error message
            data: Optional additional error data
        """
        super().__init__(message)
        self.code = int(code)
        self.message = message
        self.data = data
