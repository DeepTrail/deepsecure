"""
Unit Tests for MCP Initialize Handler

This test suite validates the initialize handler implementation:
- Valid initialize requests with all parameters
- Protocol version validation and negotiation
- Client info validation
- Error handling for invalid requests
- Integration with MCPProtocolHandler

Test Organization:
1. InitializeParams Model Tests
2. InitializeResult Model Tests
3. Handler Function Tests
4. Error Handling Tests
5. Integration Tests with MCPProtocolHandler
"""

import pytest
import json
from typing import Any

from app.mcp.handlers.initialize import (
    handle_initialize,
    InitializeParams,
    InitializeResult,
    ClientInfo,
    SUPPORTED_PROTOCOL_VERSIONS,
    SERVER_INFO,
    SERVER_CAPABILITIES,
)
from app.mcp.protocol import (
    MCPProtocolHandler,
    JsonRpcErrorCode,
    MCPError,
    MCPMethod,
)


# =============================================================================
# ClientInfo Model Tests
# =============================================================================


class TestClientInfo:
    """Tests for ClientInfo model validation."""
    
    def test_valid_client_info(self):
        """Test creating valid ClientInfo."""
        info = ClientInfo(name="TestClient", version="1.0.0")
        assert info.name == "TestClient"
        assert info.version == "1.0.0"
    
    def test_client_info_without_version(self):
        """Test ClientInfo with missing version defaults to empty string."""
        info = ClientInfo(name="TestClient")
        assert info.name == "TestClient"
        assert info.version == ""
    
    def test_client_info_empty_name_rejected(self):
        """Test that empty name is rejected."""
        with pytest.raises(ValueError, match="must not be empty"):
            ClientInfo(name="", version="1.0.0")
    
    def test_client_info_whitespace_name_rejected(self):
        """Test that whitespace-only name is rejected."""
        with pytest.raises(ValueError, match="must not be empty"):
            ClientInfo(name="   ", version="1.0.0")


# =============================================================================
# InitializeParams Model Tests
# =============================================================================


class TestInitializeParams:
    """Tests for InitializeParams model validation."""
    
    def test_valid_params(self):
        """Test creating valid InitializeParams."""
        params = InitializeParams(
            protocolVersion="2024-11-05",
            capabilities={"roots": {"listChanged": True}},
            clientInfo=ClientInfo(name="TestClient", version="1.0.0")
        )
        assert params.protocolVersion == "2024-11-05"
        assert params.capabilities == {"roots": {"listChanged": True}}
        assert params.clientInfo.name == "TestClient"
    
    def test_params_from_dict(self):
        """Test creating InitializeParams from dict (as received from JSON-RPC)."""
        data = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "TestClient", "version": "1.0.0"}
        }
        params = InitializeParams(**data)
        assert params.protocolVersion == "2024-11-05"
        assert params.clientInfo.name == "TestClient"
    
    def test_params_empty_capabilities_defaults(self):
        """Test that empty capabilities defaults to empty dict."""
        params = InitializeParams(
            protocolVersion="2024-11-05",
            clientInfo=ClientInfo(name="TestClient")
        )
        assert params.capabilities == {}
    
    def test_params_empty_protocol_version_rejected(self):
        """Test that empty protocolVersion is rejected."""
        with pytest.raises(ValueError, match="must not be empty"):
            InitializeParams(
                protocolVersion="",
                clientInfo=ClientInfo(name="TestClient")
            )
    
    def test_params_invalid_protocol_version_format(self):
        """Test that invalid protocolVersion format is rejected."""
        with pytest.raises(ValueError, match="Invalid protocolVersion format"):
            InitializeParams(
                protocolVersion="invalid",
                clientInfo=ClientInfo(name="TestClient")
            )
    
    def test_params_missing_client_info_rejected(self):
        """Test that missing clientInfo is rejected."""
        with pytest.raises(Exception):  # Pydantic validation error
            InitializeParams(protocolVersion="2024-11-05")


# =============================================================================
# InitializeResult Model Tests
# =============================================================================


class TestInitializeResult:
    """Tests for InitializeResult model."""
    
    def test_valid_result(self):
        """Test creating valid InitializeResult."""
        result = InitializeResult(
            protocolVersion="2024-11-05",
            capabilities=SERVER_CAPABILITIES,
            serverInfo=SERVER_INFO
        )
        assert result.protocolVersion == "2024-11-05"
        assert result.capabilities == SERVER_CAPABILITIES
        assert result.serverInfo == SERVER_INFO
    
    def test_result_to_dict(self):
        """Test serializing InitializeResult to dict."""
        result = InitializeResult(
            protocolVersion="2024-11-05",
            capabilities={"tools": {}},
            serverInfo={"name": "Test", "version": "1.0"}
        )
        data = result.model_dump(by_alias=True)
        assert data["protocolVersion"] == "2024-11-05"
        assert data["capabilities"] == {"tools": {}}
        assert data["serverInfo"] == {"name": "Test", "version": "1.0"}


# =============================================================================
# Handler Function Tests
# =============================================================================


class TestHandleInitialize:
    """Tests for the handle_initialize function."""
    
    @pytest.fixture
    def valid_params(self) -> dict[str, Any]:
        """Create valid initialize params."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"roots": {"listChanged": True}},
            "clientInfo": {"name": "TestClient", "version": "1.0.0"}
        }
    
    @pytest.mark.asyncio
    async def test_valid_initialize(self, valid_params):
        """Test successful initialize with valid params."""
        result = await handle_initialize(valid_params)
        
        assert result["protocolVersion"] == "2024-11-05"
        assert "capabilities" in result
        assert "tools" in result["capabilities"]
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "DeepTrail Virtual MCP Server"
    
    @pytest.mark.asyncio
    async def test_initialize_returns_server_capabilities(self, valid_params):
        """Test that initialize returns correct server capabilities."""
        result = await handle_initialize(valid_params)
        
        assert result["capabilities"] == SERVER_CAPABILITIES
        assert result["capabilities"]["tools"]["listChanged"] is True
    
    @pytest.mark.asyncio
    async def test_initialize_returns_server_info(self, valid_params):
        """Test that initialize returns correct server info."""
        result = await handle_initialize(valid_params)
        
        assert result["serverInfo"] == SERVER_INFO
        assert "name" in result["serverInfo"]
        assert "version" in result["serverInfo"]
    
    @pytest.mark.asyncio
    async def test_initialize_negotiates_protocol_version(self, valid_params):
        """Test that initialize echoes back the requested protocol version."""
        valid_params["protocolVersion"] = "2024-10-07"
        result = await handle_initialize(valid_params)
        
        assert result["protocolVersion"] == "2024-10-07"
    
    @pytest.mark.asyncio
    async def test_initialize_minimal_capabilities(self):
        """Test initialize with minimal (empty) client capabilities."""
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "MinimalClient", "version": "1.0"}
        }
        result = await handle_initialize(params)
        
        assert result["protocolVersion"] == "2024-11-05"
        assert result["capabilities"] == SERVER_CAPABILITIES
    
    @pytest.mark.asyncio
    async def test_initialize_strips_internal_context(self):
        """Test that internal context (_context) is stripped from params."""
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "TestClient", "version": "1.0"},
            "_context": {"agent_id": "secret-123"}  # Should be stripped
        }
        result = await handle_initialize(params)
        
        # Should succeed without error
        assert result["protocolVersion"] == "2024-11-05"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestInitializeErrors:
    """Tests for error handling in initialize handler."""
    
    @pytest.mark.asyncio
    async def test_unsupported_protocol_version(self):
        """Test error for unsupported protocol version."""
        params = {
            "protocolVersion": "1999-01-01",
            "capabilities": {},
            "clientInfo": {"name": "TestClient", "version": "1.0"}
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_initialize(params)
        
        assert exc_info.value.code == JsonRpcErrorCode.INVALID_PARAMS
        assert "Unsupported protocol version" in exc_info.value.message
        assert "2024-11-05" in exc_info.value.message  # Lists supported versions
    
    @pytest.mark.asyncio
    async def test_missing_protocol_version(self):
        """Test error for missing protocolVersion."""
        params = {
            "capabilities": {},
            "clientInfo": {"name": "TestClient", "version": "1.0"}
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_initialize(params)
        
        assert exc_info.value.code == JsonRpcErrorCode.INVALID_PARAMS
    
    @pytest.mark.asyncio
    async def test_missing_client_info(self):
        """Test error for missing clientInfo."""
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {}
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_initialize(params)
        
        assert exc_info.value.code == JsonRpcErrorCode.INVALID_PARAMS
    
    @pytest.mark.asyncio
    async def test_missing_client_name(self):
        """Test error for missing clientInfo.name."""
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"version": "1.0"}  # Missing name
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_initialize(params)
        
        assert exc_info.value.code == JsonRpcErrorCode.INVALID_PARAMS
    
    @pytest.mark.asyncio
    async def test_empty_client_name(self):
        """Test error for empty clientInfo.name."""
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "", "version": "1.0"}
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_initialize(params)
        
        assert exc_info.value.code == JsonRpcErrorCode.INVALID_PARAMS
    
    @pytest.mark.asyncio
    async def test_invalid_protocol_version_format(self):
        """Test error for invalid protocolVersion format."""
        params = {
            "protocolVersion": "not-a-date",
            "capabilities": {},
            "clientInfo": {"name": "TestClient", "version": "1.0"}
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_initialize(params)
        
        assert exc_info.value.code == JsonRpcErrorCode.INVALID_PARAMS


# =============================================================================
# Integration Tests with MCPProtocolHandler
# =============================================================================


class TestInitializeIntegration:
    """Integration tests with MCPProtocolHandler."""
    
    @pytest.fixture
    def handler(self) -> MCPProtocolHandler:
        """Create protocol handler with initialize registered."""
        handler = MCPProtocolHandler()
        handler.register_handler(MCPMethod.INITIALIZE, handle_initialize)
        return handler
    
    @pytest.mark.asyncio
    async def test_full_initialize_request(self, handler):
        """Test full JSON-RPC initialize request through protocol handler."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "IntegrationTest", "version": "1.0.0"}
            }
        }
        raw = json.dumps(request).encode()
        
        response = await handler.handle_request(raw)
        
        assert response.id == 1
        assert response.error is None
        assert response.result["protocolVersion"] == "2024-11-05"
        assert response.result["serverInfo"]["name"] == "DeepTrail Virtual MCP Server"
    
    @pytest.mark.asyncio
    async def test_initialize_error_propagates(self, handler):
        """Test that initialize errors are properly returned as JSON-RPC errors."""
        # Use a valid format but unsupported version
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "1999-01-01",  # Valid format but unsupported
                "capabilities": {},
                "clientInfo": {"name": "Test", "version": "1.0"}
            }
        }
        raw = json.dumps(request).encode()
        
        response = await handler.handle_request(raw)
        
        assert response.id == 1
        assert response.error is not None
        assert response.error.code == JsonRpcErrorCode.INVALID_PARAMS
        assert "Unsupported protocol version" in response.error.message
    
    @pytest.mark.asyncio
    async def test_initialize_with_context(self, handler):
        """Test initialize with context passed from protocol handler."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ContextTest", "version": "1.0"}
            }
        }
        raw = json.dumps(request).encode()
        
        context = {"agent_id": "agent-123", "session_id": "sess-456"}
        response = await handler.handle_request(raw, context=context)
        
        # Should succeed - context is stripped before validation
        assert response.error is None
        assert response.result["protocolVersion"] == "2024-11-05"


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""
    
    def test_supported_protocol_versions_not_empty(self):
        """Test that SUPPORTED_PROTOCOL_VERSIONS is not empty."""
        assert len(SUPPORTED_PROTOCOL_VERSIONS) > 0
    
    def test_supported_protocol_versions_contains_latest(self):
        """Test that latest protocol version is supported."""
        assert "2024-11-05" in SUPPORTED_PROTOCOL_VERSIONS
    
    def test_server_info_has_required_fields(self):
        """Test that SERVER_INFO has required fields."""
        assert "name" in SERVER_INFO
        assert "version" in SERVER_INFO
        assert len(SERVER_INFO["name"]) > 0
    
    def test_server_capabilities_has_tools(self):
        """Test that SERVER_CAPABILITIES includes tools."""
        assert "tools" in SERVER_CAPABILITIES
        assert "listChanged" in SERVER_CAPABILITIES["tools"]
