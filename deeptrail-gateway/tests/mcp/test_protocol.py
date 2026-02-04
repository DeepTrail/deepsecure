"""
Comprehensive Unit Tests for MCP JSON-RPC 2.0 Protocol Handler

This test suite validates the MCP protocol implementation including:
- JSON-RPC 2.0 request parsing and validation
- Response formatting
- Error code handling
- Method routing with pluggable handlers
- Batch request handling
- Security measures (size limits, error message sanitization)

Test Organization:
1. Model Tests: JsonRpcRequest, JsonRpcResponse, JsonRpcError
2. Error Code Tests: All JSON-RPC 2.0 and MCP-specific error codes
3. Protocol Handler Tests: Request handling and method routing
4. Security Tests: Size limits, error message sanitization
5. Integration Tests: Full request/response cycle
"""

import pytest
import json
from typing import Any

from app.mcp.protocol import (
    MCPProtocolHandler,
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcError,
    JsonRpcErrorCode,
    MCPMethod,
    MCPError,
    MAX_REQUEST_SIZE,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestJsonRpcRequest:
    """Tests for JsonRpcRequest model validation."""
    
    def test_valid_request_minimal(self):
        """Test parsing minimal valid request."""
        request = JsonRpcRequest(method="test")
        assert request.jsonrpc == "2.0"
        assert request.method == "test"
        assert request.id is None
        assert request.params is None
        assert request.is_notification is True
    
    def test_valid_request_with_id(self):
        """Test parsing request with integer id."""
        request = JsonRpcRequest(method="test", id=1)
        assert request.id == 1
        assert request.is_notification is False
    
    def test_valid_request_with_string_id(self):
        """Test parsing request with string id."""
        request = JsonRpcRequest(method="test", id="abc-123")
        assert request.id == "abc-123"
        assert request.is_notification is False
    
    def test_valid_request_with_params(self):
        """Test parsing request with params."""
        params = {"key": "value", "nested": {"a": 1}}
        request = JsonRpcRequest(method="test", id=1, params=params)
        assert request.params == params
    
    def test_invalid_jsonrpc_version(self):
        """Test that non-2.0 jsonrpc version is rejected."""
        with pytest.raises(ValueError, match="jsonrpc must be '2.0'"):
            JsonRpcRequest(jsonrpc="1.0", method="test")
    
    def test_invalid_empty_method(self):
        """Test that empty method is rejected."""
        with pytest.raises(ValueError, match="method must not be empty"):
            JsonRpcRequest(method="")
    
    def test_invalid_whitespace_method(self):
        """Test that whitespace-only method is rejected."""
        with pytest.raises(ValueError, match="method must not be empty"):
            JsonRpcRequest(method="   ")
    
    def test_mcp_methods_recognized(self):
        """Test that MCP methods are valid."""
        for method in MCPMethod:
            request = JsonRpcRequest(method=method.value, id=1)
            assert request.method == method.value


class TestJsonRpcError:
    """Tests for JsonRpcError model."""
    
    def test_error_with_code_and_message(self):
        """Test creating error with code and message."""
        error = JsonRpcError(code=-32600, message="Invalid Request")
        assert error.code == -32600
        assert error.message == "Invalid Request"
        assert error.data is None
    
    def test_error_with_data(self):
        """Test creating error with additional data."""
        error = JsonRpcError(
            code=-32602,
            message="Invalid params",
            data={"missing": ["required_field"]}
        )
        assert error.data == {"missing": ["required_field"]}
    
    def test_error_code_enum(self):
        """Test using JsonRpcErrorCode enum."""
        error = JsonRpcError(
            code=JsonRpcErrorCode.PARSE_ERROR,
            message="Parse error"
        )
        assert error.code == -32700


class TestJsonRpcResponse:
    """Tests for JsonRpcResponse model."""
    
    def test_success_response(self):
        """Test creating success response with result."""
        response = JsonRpcResponse(id=1, result={"status": "ok"})
        assert response.jsonrpc == "2.0"
        assert response.id == 1
        assert response.result == {"status": "ok"}
        assert response.error is None
    
    def test_error_response(self):
        """Test creating error response."""
        error = JsonRpcError(code=-32600, message="Invalid Request")
        response = JsonRpcResponse(id=1, error=error)
        assert response.result is None
        assert response.error.code == -32600
    
    def test_null_result_is_valid(self):
        """Test that null result is valid (e.g., for void methods)."""
        # When result is explicitly set to something (even None for void methods)
        # and error is None, the response should be valid
        response = JsonRpcResponse(id=1, result=None, error=None)
        assert response.result is None
        assert response.error is None
    
    def test_response_with_both_result_and_error_invalid(self):
        """Test that response with both result and error is rejected."""
        error = JsonRpcError(code=-32600, message="Invalid")
        with pytest.raises(ValueError, match="cannot have both result and error"):
            JsonRpcResponse(id=1, result={"data": "test"}, error=error)
    
    def test_model_dump_excludes_null_result_on_error(self):
        """Test that serialization excludes null result when error is present."""
        error = JsonRpcError(code=-32600, message="Invalid")
        response = JsonRpcResponse(id=1, error=error)
        data = response.model_dump()
        assert "result" not in data
        assert "error" in data
    
    def test_model_dump_excludes_null_error_on_success(self):
        """Test that serialization excludes null error when result is present."""
        response = JsonRpcResponse(id=1, result={"status": "ok"})
        data = response.model_dump()
        assert "error" not in data
        assert "result" in data


# =============================================================================
# Error Code Tests
# =============================================================================


class TestJsonRpcErrorCodes:
    """Tests for JSON-RPC 2.0 error codes."""
    
    def test_parse_error_code(self):
        """Test PARSE_ERROR code value."""
        assert JsonRpcErrorCode.PARSE_ERROR == -32700
    
    def test_invalid_request_code(self):
        """Test INVALID_REQUEST code value."""
        assert JsonRpcErrorCode.INVALID_REQUEST == -32600
    
    def test_method_not_found_code(self):
        """Test METHOD_NOT_FOUND code value."""
        assert JsonRpcErrorCode.METHOD_NOT_FOUND == -32601
    
    def test_invalid_params_code(self):
        """Test INVALID_PARAMS code value."""
        assert JsonRpcErrorCode.INVALID_PARAMS == -32602
    
    def test_internal_error_code(self):
        """Test INTERNAL_ERROR code value."""
        assert JsonRpcErrorCode.INTERNAL_ERROR == -32603
    
    def test_mcp_policy_unavailable_code(self):
        """Test MCP POLICY_UNAVAILABLE code value."""
        assert JsonRpcErrorCode.POLICY_UNAVAILABLE == -32000
    
    def test_mcp_permission_denied_code(self):
        """Test MCP PERMISSION_DENIED code value."""
        assert JsonRpcErrorCode.PERMISSION_DENIED == -32001
    
    def test_mcp_session_invalid_code(self):
        """Test MCP SESSION_INVALID code value."""
        assert JsonRpcErrorCode.SESSION_INVALID == -32002
    
    def test_mcp_credential_error_code(self):
        """Test MCP CREDENTIAL_ERROR code value."""
        assert JsonRpcErrorCode.CREDENTIAL_ERROR == -32003


class TestMCPMethod:
    """Tests for MCP method constants."""
    
    def test_initialize_method(self):
        """Test initialize method value."""
        assert MCPMethod.INITIALIZE == "initialize"
    
    def test_tools_list_method(self):
        """Test tools/list method value."""
        assert MCPMethod.TOOLS_LIST == "tools/list"
    
    def test_tools_call_method(self):
        """Test tools/call method value."""
        assert MCPMethod.TOOLS_CALL == "tools/call"


# =============================================================================
# MCPError Exception Tests
# =============================================================================


class TestMCPError:
    """Tests for MCPError exception class."""
    
    def test_mcp_error_basic(self):
        """Test creating basic MCP error."""
        error = MCPError(JsonRpcErrorCode.PERMISSION_DENIED, "Access denied")
        assert error.code == -32001
        assert error.message == "Access denied"
        assert error.data is None
        assert str(error) == "Access denied"
    
    def test_mcp_error_with_data(self):
        """Test creating MCP error with data."""
        error = MCPError(
            JsonRpcErrorCode.INVALID_PARAMS,
            "Invalid params",
            data={"field": "missing_required"}
        )
        assert error.data == {"field": "missing_required"}
    
    def test_mcp_error_with_int_code(self):
        """Test creating MCP error with int code."""
        error = MCPError(-32600, "Test error")
        assert error.code == -32600


# =============================================================================
# Protocol Handler Tests
# =============================================================================


class TestMCPProtocolHandler:
    """Tests for MCPProtocolHandler request handling."""
    
    @pytest.fixture
    def handler(self):
        """Create a fresh protocol handler for each test."""
        return MCPProtocolHandler()
    
    @pytest.fixture
    def echo_handler(self, handler):
        """Register an echo handler that returns the params."""
        async def echo(params: dict[str, Any]) -> dict[str, Any]:
            return {"echo": params}
        handler.register_handler("echo", echo)
        return handler
    
    # --- Handler Registration Tests ---
    
    def test_register_handler(self, handler):
        """Test registering a method handler."""
        async def dummy_handler(params):
            return {}
        
        handler.register_handler("test/method", dummy_handler)
        assert "test/method" in handler.get_registered_methods()
    
    def test_unregister_handler(self, handler):
        """Test unregistering a method handler."""
        async def dummy_handler(params):
            return {}
        
        handler.register_handler("test/method", dummy_handler)
        assert handler.unregister_handler("test/method") is True
        assert "test/method" not in handler.get_registered_methods()
    
    def test_unregister_nonexistent_handler(self, handler):
        """Test unregistering a handler that doesn't exist."""
        assert handler.unregister_handler("nonexistent") is False
    
    def test_get_registered_methods_empty(self, handler):
        """Test getting registered methods when none registered."""
        assert handler.get_registered_methods() == []
    
    # --- Valid Request Parsing Tests ---
    
    @pytest.mark.asyncio
    async def test_parse_valid_request(self, echo_handler):
        """Test parsing a valid JSON-RPC request."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "echo",
            "params": {"message": "hello"}
        }
        raw = json.dumps(request).encode()
        
        response = await echo_handler.handle_request(raw)
        
        assert response.id == 1
        assert response.result == {"echo": {"message": "hello"}}
        assert response.error is None
    
    @pytest.mark.asyncio
    async def test_parse_request_without_params(self, echo_handler):
        """Test parsing request without params."""
        request = {"jsonrpc": "2.0", "id": 1, "method": "echo"}
        raw = json.dumps(request).encode()
        
        response = await echo_handler.handle_request(raw)
        
        assert response.result == {"echo": {}}
    
    @pytest.mark.asyncio
    async def test_parse_request_with_string_id(self, echo_handler):
        """Test parsing request with string id."""
        request = {"jsonrpc": "2.0", "id": "uuid-123", "method": "echo"}
        raw = json.dumps(request).encode()
        
        response = await echo_handler.handle_request(raw)
        
        assert response.id == "uuid-123"
    
    # --- Error Response Tests ---
    
    @pytest.mark.asyncio
    async def test_parse_error_invalid_json(self, handler):
        """Test PARSE_ERROR (-32700) for invalid JSON."""
        raw = b"not valid json {"
        
        response = await handler.handle_request(raw)
        
        assert response.id is None
        assert response.error.code == JsonRpcErrorCode.PARSE_ERROR
        assert response.error.message == "Parse error"
    
    @pytest.mark.asyncio
    async def test_invalid_request_not_object(self, handler):
        """Test INVALID_REQUEST (-32600) for non-object request."""
        raw = json.dumps("just a string").encode()
        
        response = await handler.handle_request(raw)
        
        assert response.error.code == JsonRpcErrorCode.INVALID_REQUEST
        assert response.error.message == "Invalid Request"
    
    @pytest.mark.asyncio
    async def test_invalid_request_missing_method(self, handler):
        """Test INVALID_REQUEST (-32600) for missing method."""
        request = {"jsonrpc": "2.0", "id": 1}
        raw = json.dumps(request).encode()
        
        response = await handler.handle_request(raw)
        
        assert response.error.code == JsonRpcErrorCode.INVALID_REQUEST
    
    @pytest.mark.asyncio
    async def test_invalid_request_wrong_version(self, handler):
        """Test INVALID_REQUEST (-32600) for wrong jsonrpc version."""
        request = {"jsonrpc": "1.0", "id": 1, "method": "test"}
        raw = json.dumps(request).encode()
        
        response = await handler.handle_request(raw)
        
        assert response.error.code == JsonRpcErrorCode.INVALID_REQUEST
    
    @pytest.mark.asyncio
    async def test_method_not_found(self, handler):
        """Test METHOD_NOT_FOUND (-32601) for unregistered method."""
        request = {"jsonrpc": "2.0", "id": 1, "method": "unknown/method"}
        raw = json.dumps(request).encode()
        
        response = await handler.handle_request(raw)
        
        assert response.error.code == JsonRpcErrorCode.METHOD_NOT_FOUND
        assert response.error.message == "Method not found"
    
    @pytest.mark.asyncio
    async def test_internal_error_handler_exception(self, handler):
        """Test INTERNAL_ERROR (-32603) when handler raises exception."""
        async def failing_handler(params):
            raise RuntimeError("Something went wrong internally")
        
        handler.register_handler("fail", failing_handler)
        request = {"jsonrpc": "2.0", "id": 1, "method": "fail"}
        raw = json.dumps(request).encode()
        
        response = await handler.handle_request(raw)
        
        assert response.error.code == JsonRpcErrorCode.INTERNAL_ERROR
        # Security: Internal error details should NOT be exposed
        assert response.error.message == "Internal error"
        assert "Something went wrong" not in str(response.error.message)
    
    @pytest.mark.asyncio
    async def test_mcp_error_passed_through(self, handler):
        """Test that MCPError exceptions are passed through correctly."""
        async def permission_handler(params):
            raise MCPError(
                JsonRpcErrorCode.PERMISSION_DENIED,
                "Access denied to tool: notion/create_page"
            )
        
        handler.register_handler("restricted", permission_handler)
        request = {"jsonrpc": "2.0", "id": 1, "method": "restricted"}
        raw = json.dumps(request).encode()
        
        response = await handler.handle_request(raw)
        
        assert response.error.code == JsonRpcErrorCode.PERMISSION_DENIED
        assert "Access denied" in response.error.message
    
    # --- Notification Tests ---
    
    @pytest.mark.asyncio
    async def test_notification_no_response(self, echo_handler):
        """Test that notifications (no id) return None."""
        request = {"jsonrpc": "2.0", "method": "echo", "params": {"test": 1}}
        raw = json.dumps(request).encode()
        
        response = await echo_handler.handle_request(raw)
        
        assert response is None
    
    @pytest.mark.asyncio
    async def test_notification_null_id_no_response(self, echo_handler):
        """Test that explicit null id is treated as notification."""
        request = {"jsonrpc": "2.0", "id": None, "method": "echo"}
        raw = json.dumps(request).encode()
        
        response = await echo_handler.handle_request(raw)
        
        assert response is None
    
    # --- Batch Request Tests ---
    
    @pytest.mark.asyncio
    async def test_batch_request(self, echo_handler):
        """Test handling batch of requests."""
        batch = [
            {"jsonrpc": "2.0", "id": 1, "method": "echo", "params": {"a": 1}},
            {"jsonrpc": "2.0", "id": 2, "method": "echo", "params": {"b": 2}},
        ]
        raw = json.dumps(batch).encode()
        
        responses = await echo_handler.handle_request(raw)
        
        assert isinstance(responses, list)
        assert len(responses) == 2
        assert responses[0].id == 1
        assert responses[1].id == 2
    
    @pytest.mark.asyncio
    async def test_batch_with_notifications_excluded(self, echo_handler):
        """Test that notifications are excluded from batch response."""
        batch = [
            {"jsonrpc": "2.0", "id": 1, "method": "echo"},
            {"jsonrpc": "2.0", "method": "echo"},  # notification
            {"jsonrpc": "2.0", "id": 2, "method": "echo"},
        ]
        raw = json.dumps(batch).encode()
        
        responses = await echo_handler.handle_request(raw)
        
        assert len(responses) == 2
        response_ids = [r.id for r in responses]
        assert 1 in response_ids
        assert 2 in response_ids
    
    @pytest.mark.asyncio
    async def test_batch_all_notifications_empty_response(self, echo_handler):
        """Test that batch of only notifications returns empty list."""
        batch = [
            {"jsonrpc": "2.0", "method": "echo"},
            {"jsonrpc": "2.0", "method": "echo"},
        ]
        raw = json.dumps(batch).encode()
        
        responses = await echo_handler.handle_request(raw)
        
        assert responses == []
    
    @pytest.mark.asyncio
    async def test_batch_empty_array(self, handler):
        """Test INVALID_REQUEST for empty batch."""
        raw = json.dumps([]).encode()
        
        response = await handler.handle_request(raw)
        
        assert response.error.code == JsonRpcErrorCode.INVALID_REQUEST
        assert "empty batch" in response.error.message
    
    @pytest.mark.asyncio
    async def test_batch_mixed_valid_invalid(self, echo_handler):
        """Test batch with mix of valid and invalid requests."""
        batch = [
            {"jsonrpc": "2.0", "id": 1, "method": "echo"},
            {"jsonrpc": "2.0", "id": 2, "method": "nonexistent"},
            {"jsonrpc": "2.0", "id": 3, "method": "echo"},
        ]
        raw = json.dumps(batch).encode()
        
        responses = await echo_handler.handle_request(raw)
        
        assert len(responses) == 3
        assert responses[0].result is not None
        assert responses[1].error.code == JsonRpcErrorCode.METHOD_NOT_FOUND
        assert responses[2].result is not None
    
    # --- Context Passing Tests ---
    
    @pytest.mark.asyncio
    async def test_context_passed_to_handler(self, handler):
        """Test that context is passed to handler."""
        received_context = {}
        
        async def context_handler(params):
            nonlocal received_context
            received_context = params.get("_context", {})
            return {"received": True}
        
        handler.register_handler("context_test", context_handler)
        request = {"jsonrpc": "2.0", "id": 1, "method": "context_test"}
        raw = json.dumps(request).encode()
        
        context = {"session_id": "abc", "agent_id": "agent-123"}
        await handler.handle_request(raw, context=context)
        
        assert received_context == context


# =============================================================================
# Security Tests
# =============================================================================


class TestSecurityMeasures:
    """Tests for security measures in the protocol handler."""
    
    @pytest.fixture
    def handler(self):
        """Create handler with default size limit."""
        return MCPProtocolHandler()
    
    @pytest.mark.asyncio
    async def test_request_size_limit_exceeded(self, handler):
        """Test that oversized requests are rejected."""
        # Create request larger than MAX_REQUEST_SIZE
        large_data = "x" * (MAX_REQUEST_SIZE + 1000)
        request = {"jsonrpc": "2.0", "id": 1, "method": "test", "params": {"data": large_data}}
        raw = json.dumps(request).encode()
        
        response = await handler.handle_request(raw)
        
        assert response.error.code == JsonRpcErrorCode.INVALID_REQUEST
        assert "too large" in response.error.message.lower()
    
    @pytest.mark.asyncio
    async def test_custom_size_limit(self):
        """Test custom request size limit."""
        small_handler = MCPProtocolHandler(max_request_size=100)
        
        request = {"jsonrpc": "2.0", "id": 1, "method": "test", "params": {"data": "x" * 200}}
        raw = json.dumps(request).encode()
        
        response = await small_handler.handle_request(raw)
        
        assert response.error.code == JsonRpcErrorCode.INVALID_REQUEST
    
    @pytest.mark.asyncio
    async def test_internal_errors_not_exposed(self, handler):
        """Test that internal error details are not exposed."""
        async def secret_handler(params):
            # Simulate internal error with sensitive info
            raise Exception("Database password: secret123 - Connection failed")
        
        handler.register_handler("internal", secret_handler)
        request = {"jsonrpc": "2.0", "id": 1, "method": "internal"}
        raw = json.dumps(request).encode()
        
        response = await handler.handle_request(raw)
        
        # Should get generic error, not the secret details
        assert response.error.code == JsonRpcErrorCode.INTERNAL_ERROR
        assert "secret123" not in str(response.error.message)
        assert "Database" not in str(response.error.message)
        assert response.error.message == "Internal error"
    
    @pytest.mark.asyncio
    async def test_error_response_has_correct_id(self, handler):
        """Test that error responses include the request id."""
        request = {"jsonrpc": "2.0", "id": 42, "method": "nonexistent"}
        raw = json.dumps(request).encode()
        
        response = await handler.handle_request(raw)
        
        assert response.id == 42


# =============================================================================
# MCP-Specific Method Tests
# =============================================================================


class TestMCPMethods:
    """Tests for MCP-specific method handling."""
    
    @pytest.fixture
    def mcp_handler(self):
        """Create handler with MCP method stubs."""
        handler = MCPProtocolHandler()
        
        async def initialize(params):
            return {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True}
                },
                "serverInfo": {
                    "name": "DeepSecure Virtual MCP Server",
                    "version": "0.1.0"
                }
            }
        
        async def tools_list(params):
            return {
                "tools": [
                    {
                        "name": "notion/create_page",
                        "description": "Create a page in Notion",
                        "inputSchema": {"type": "object"}
                    }
                ]
            }
        
        async def tools_call(params):
            tool_name = params.get("name")
            if not tool_name:
                raise MCPError(
                    JsonRpcErrorCode.INVALID_PARAMS,
                    "Missing required parameter: name"
                )
            return {"content": [{"type": "text", "text": f"Executed {tool_name}"}]}
        
        handler.register_handler(MCPMethod.INITIALIZE, initialize)
        handler.register_handler(MCPMethod.TOOLS_LIST, tools_list)
        handler.register_handler(MCPMethod.TOOLS_CALL, tools_call)
        
        return handler
    
    @pytest.mark.asyncio
    async def test_initialize_method(self, mcp_handler):
        """Test MCP initialize method."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-agent", "version": "1.0.0"}
            }
        }
        raw = json.dumps(request).encode()
        
        response = await mcp_handler.handle_request(raw)
        
        assert response.result["protocolVersion"] == "2024-11-05"
        assert "capabilities" in response.result
        assert "serverInfo" in response.result
    
    @pytest.mark.asyncio
    async def test_tools_list_method(self, mcp_handler):
        """Test MCP tools/list method."""
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        raw = json.dumps(request).encode()
        
        response = await mcp_handler.handle_request(raw)
        
        assert "tools" in response.result
        assert len(response.result["tools"]) > 0
        assert response.result["tools"][0]["name"] == "notion/create_page"
    
    @pytest.mark.asyncio
    async def test_tools_call_method(self, mcp_handler):
        """Test MCP tools/call method."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "notion/create_page",
                "arguments": {"title": "Test Page"}
            }
        }
        raw = json.dumps(request).encode()
        
        response = await mcp_handler.handle_request(raw)
        
        assert "content" in response.result
        assert "Executed notion/create_page" in response.result["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_tools_call_missing_name(self, mcp_handler):
        """Test tools/call with missing name parameter."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"arguments": {}}
        }
        raw = json.dumps(request).encode()
        
        response = await mcp_handler.handle_request(raw)
        
        assert response.error.code == JsonRpcErrorCode.INVALID_PARAMS
        assert "name" in response.error.message


# =============================================================================
# Integration Tests
# =============================================================================


class TestProtocolIntegration:
    """End-to-end integration tests for the protocol handler."""
    
    @pytest.mark.asyncio
    async def test_full_mcp_session_flow(self):
        """Test a complete MCP session flow: initialize -> list -> call."""
        handler = MCPProtocolHandler()
        
        # Register handlers
        session_initialized = False
        
        async def initialize(params):
            nonlocal session_initialized
            session_initialized = True
            return {"protocolVersion": "2024-11-05"}
        
        async def tools_list(params):
            if not session_initialized:
                raise MCPError(JsonRpcErrorCode.SESSION_INVALID, "Session not initialized")
            return {"tools": [{"name": "test_tool"}]}
        
        handler.register_handler("initialize", initialize)
        handler.register_handler("tools/list", tools_list)
        
        # Step 1: Initialize
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        response = await handler.handle_request(json.dumps(init_req).encode())
        assert response.result is not None
        
        # Step 2: List tools
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        response = await handler.handle_request(json.dumps(list_req).encode())
        assert response.result["tools"][0]["name"] == "test_tool"
    
    @pytest.mark.asyncio
    async def test_response_serialization(self):
        """Test that responses serialize correctly to JSON."""
        handler = MCPProtocolHandler()
        
        async def test_handler(params):
            return {
                "string": "value",
                "number": 42,
                "float": 3.14,
                "boolean": True,
                "null": None,
                "array": [1, 2, 3],
                "nested": {"a": {"b": "c"}}
            }
        
        handler.register_handler("test", test_handler)
        request = {"jsonrpc": "2.0", "id": 1, "method": "test"}
        
        response = await handler.handle_request(json.dumps(request).encode())
        
        # Verify response can be serialized to JSON
        serialized = json.dumps(response.model_dump())
        deserialized = json.loads(serialized)
        
        assert deserialized["jsonrpc"] == "2.0"
        assert deserialized["id"] == 1
        assert deserialized["result"]["string"] == "value"
        assert deserialized["result"]["nested"]["a"]["b"] == "c"
