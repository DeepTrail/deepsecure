"""
Unit Tests for MCP Namespace Prefixer

This test suite validates the namespace prefixer implementation:
- Basic prefixing/unprefixing of tool names
- Backend ID validation
- Description prefixing
- Tool model operations
- Edge cases (dots in names, special characters, empty values)

Test Organization:
1. Backend ID Validation Tests
2. Tool Name Validation Tests
3. Prefix/Unprefix Tests
4. Description Prefixing Tests
5. Tool Model Tests
6. Edge Cases and Security Tests
"""

import pytest

from app.mcp.namespace import (
    # Constants
    NAMESPACE_SEPARATOR,
    BACKEND_ID_PATTERN,
    MAX_BACKEND_ID_LENGTH,
    MAX_TOOL_NAME_LENGTH,
    # Exceptions
    NamespaceError,
    # Validation
    validate_backend_id,
    validate_tool_name,
    # Core functions
    prefix_tool_name,
    unprefix_tool_name,
    get_backend_from_tool_name,
    is_namespaced,
    # Description
    prefix_description,
    # Tool operations
    Tool,
    prefix_tool,
    prefix_tools,
    unprefix_tool,
)


# =============================================================================
# Backend ID Validation Tests
# =============================================================================


class TestValidateBackendId:
    """Tests for backend ID validation."""
    
    def test_valid_simple_backend_id(self):
        """Test valid simple backend IDs."""
        validate_backend_id("notion")  # Should not raise
        validate_backend_id("slack")
        validate_backend_id("hubspot")
    
    def test_valid_backend_id_with_underscore(self):
        """Test valid backend IDs with underscores."""
        validate_backend_id("hub_spot")
        validate_backend_id("my_backend")
        validate_backend_id("a_b_c")
    
    def test_valid_backend_id_with_numbers(self):
        """Test valid backend IDs with numbers."""
        validate_backend_id("api2")
        validate_backend_id("v1_api")
        validate_backend_id("backend123")
    
    def test_empty_backend_id_rejected(self):
        """Test that empty backend ID is rejected."""
        with pytest.raises(NamespaceError, match="cannot be empty"):
            validate_backend_id("")
    
    def test_uppercase_backend_id_rejected(self):
        """Test that uppercase letters are rejected."""
        with pytest.raises(NamespaceError, match="lowercase"):
            validate_backend_id("Notion")
        with pytest.raises(NamespaceError, match="lowercase"):
            validate_backend_id("SLACK")
        with pytest.raises(NamespaceError, match="lowercase"):
            validate_backend_id("hubSpot")
    
    def test_backend_id_starting_with_number_rejected(self):
        """Test that backend IDs starting with numbers are rejected."""
        with pytest.raises(NamespaceError, match="start with lowercase letter"):
            validate_backend_id("123abc")
        with pytest.raises(NamespaceError, match="start with lowercase letter"):
            validate_backend_id("1notion")
    
    def test_backend_id_starting_with_underscore_rejected(self):
        """Test that backend IDs starting with underscore are rejected."""
        with pytest.raises(NamespaceError, match="start with lowercase letter"):
            validate_backend_id("_notion")
    
    def test_backend_id_with_special_chars_rejected(self):
        """Test that special characters are rejected."""
        with pytest.raises(NamespaceError):
            validate_backend_id("notion-api")  # Hyphen
        with pytest.raises(NamespaceError):
            validate_backend_id("notion.api")  # Dot
        with pytest.raises(NamespaceError):
            validate_backend_id("notion api")  # Space
        with pytest.raises(NamespaceError):
            validate_backend_id("notion@api")  # At sign
    
    def test_backend_id_too_long_rejected(self):
        """Test that overly long backend IDs are rejected."""
        long_id = "a" * (MAX_BACKEND_ID_LENGTH + 1)
        with pytest.raises(NamespaceError, match="too long"):
            validate_backend_id(long_id)
    
    def test_backend_id_at_max_length_accepted(self):
        """Test that backend ID at max length is accepted."""
        max_id = "a" * MAX_BACKEND_ID_LENGTH
        validate_backend_id(max_id)  # Should not raise


# =============================================================================
# Tool Name Validation Tests
# =============================================================================


class TestValidateToolName:
    """Tests for tool name validation."""
    
    def test_valid_tool_name(self):
        """Test valid tool names."""
        validate_tool_name("search_pages")
        validate_tool_name("send_message")
        validate_tool_name("get-contact")  # Hyphen OK in tool names
    
    def test_tool_name_with_dots(self):
        """Test tool names containing dots."""
        validate_tool_name("repos.create")
        validate_tool_name("api.v2.search")
    
    def test_empty_tool_name_rejected(self):
        """Test that empty tool name is rejected."""
        with pytest.raises(NamespaceError, match="cannot be empty"):
            validate_tool_name("")
    
    def test_whitespace_only_tool_name_rejected(self):
        """Test that whitespace-only tool name is rejected."""
        with pytest.raises(NamespaceError, match="whitespace only"):
            validate_tool_name("   ")
        with pytest.raises(NamespaceError, match="whitespace only"):
            validate_tool_name("\t\n")
    
    def test_tool_name_too_long_rejected(self):
        """Test that overly long tool names are rejected."""
        long_name = "a" * (MAX_TOOL_NAME_LENGTH + 1)
        with pytest.raises(NamespaceError, match="too long"):
            validate_tool_name(long_name)


# =============================================================================
# Prefix Tool Name Tests
# =============================================================================


class TestPrefixToolName:
    """Tests for prefix_tool_name function."""
    
    def test_basic_prefix(self):
        """Test basic tool name prefixing."""
        assert prefix_tool_name("notion", "search_pages") == "notion.search_pages"
        assert prefix_tool_name("slack", "send_message") == "slack.send_message"
    
    def test_prefix_with_underscore_backend(self):
        """Test prefixing with underscore in backend ID."""
        assert prefix_tool_name("hub_spot", "get_contact") == "hub_spot.get_contact"
    
    def test_prefix_with_numbers_in_backend(self):
        """Test prefixing with numbers in backend ID."""
        assert prefix_tool_name("api2", "list") == "api2.list"
    
    def test_prefix_preserves_tool_name_dots(self):
        """Test that dots in tool name are preserved."""
        result = prefix_tool_name("github", "repos.create")
        assert result == "github.repos.create"
    
    def test_prefix_empty_backend_raises(self):
        """Test that empty backend ID raises error."""
        with pytest.raises(NamespaceError):
            prefix_tool_name("", "search")
    
    def test_prefix_empty_tool_name_raises(self):
        """Test that empty tool name raises error."""
        with pytest.raises(NamespaceError):
            prefix_tool_name("notion", "")
    
    def test_prefix_invalid_backend_raises(self):
        """Test that invalid backend ID raises error."""
        with pytest.raises(NamespaceError):
            prefix_tool_name("Notion", "search")  # Uppercase


# =============================================================================
# Unprefix Tool Name Tests
# =============================================================================


class TestUnprefixToolName:
    """Tests for unprefix_tool_name function."""
    
    def test_basic_unprefix(self):
        """Test basic tool name unprefixing."""
        assert unprefix_tool_name("slack.send_message") == ("slack", "send_message")
        assert unprefix_tool_name("notion.search_pages") == ("notion", "search_pages")
    
    def test_unprefix_with_underscore_backend(self):
        """Test unprefixing with underscore in backend ID."""
        assert unprefix_tool_name("hub_spot.get_contact") == ("hub_spot", "get_contact")
    
    def test_unprefix_with_dots_in_tool_name(self):
        """Test that dots in tool name are preserved."""
        # Only split on first dot - tool name can contain dots
        assert unprefix_tool_name("github.repos.create") == ("github", "repos.create")
    
    def test_unprefix_multiple_dots_in_tool(self):
        """Test tool name with multiple dots."""
        result = unprefix_tool_name("api.v2.users.list")
        assert result == ("api", "v2.users.list")
    
    def test_unprefix_empty_string_raises(self):
        """Test that empty string raises error."""
        with pytest.raises(NamespaceError, match="cannot be empty"):
            unprefix_tool_name("")
    
    def test_unprefix_no_separator_raises(self):
        """Test that name without separator raises error."""
        with pytest.raises(NamespaceError, match="Missing namespace separator"):
            unprefix_tool_name("search_pages")
    
    def test_unprefix_invalid_backend_raises(self):
        """Test that invalid backend prefix raises error."""
        with pytest.raises(NamespaceError):
            unprefix_tool_name("Notion.search")  # Uppercase
        with pytest.raises(NamespaceError):
            unprefix_tool_name("123.search")  # Starts with number
    
    def test_unprefix_empty_tool_name_raises(self):
        """Test that empty tool name after prefix raises error."""
        with pytest.raises(NamespaceError, match="cannot be empty"):
            unprefix_tool_name("notion.")


# =============================================================================
# Get Backend From Tool Name Tests
# =============================================================================


class TestGetBackendFromToolName:
    """Tests for get_backend_from_tool_name function."""
    
    def test_get_backend_basic(self):
        """Test basic backend extraction."""
        assert get_backend_from_tool_name("notion.search_pages") == "notion"
        assert get_backend_from_tool_name("slack.send_message") == "slack"
    
    def test_get_backend_with_dots_in_tool(self):
        """Test backend extraction when tool has dots."""
        assert get_backend_from_tool_name("github.repos.create") == "github"
    
    def test_get_backend_invalid_raises(self):
        """Test that invalid namespaced name raises error."""
        with pytest.raises(NamespaceError):
            get_backend_from_tool_name("search_pages")


# =============================================================================
# Is Namespaced Tests
# =============================================================================


class TestIsNamespaced:
    """Tests for is_namespaced function."""
    
    def test_namespaced_returns_true(self):
        """Test that namespaced names return True."""
        assert is_namespaced("notion.search_pages") is True
        assert is_namespaced("slack.send_message") is True
        assert is_namespaced("hub_spot.get_contact") is True
    
    def test_non_namespaced_returns_false(self):
        """Test that non-namespaced names return False."""
        assert is_namespaced("search_pages") is False
        assert is_namespaced("send_message") is False
    
    def test_empty_returns_false(self):
        """Test that empty string returns False."""
        assert is_namespaced("") is False
    
    def test_invalid_backend_returns_false(self):
        """Test that invalid backend prefix returns False."""
        # Uppercase - not a valid backend ID
        assert is_namespaced("Notion.search") is False
        # Starts with number
        assert is_namespaced("123.search") is False
    
    def test_dot_only_returns_false(self):
        """Test that just a dot returns False."""
        assert is_namespaced(".") is False
        assert is_namespaced("..") is False


# =============================================================================
# Description Prefixing Tests
# =============================================================================


class TestPrefixDescription:
    """Tests for prefix_description function."""
    
    def test_basic_description_prefix(self):
        """Test basic description prefixing."""
        result = prefix_description("notion", "Search pages in workspace")
        assert result == "[Notion] Search pages in workspace"
    
    def test_description_prefix_with_underscore(self):
        """Test description prefixing with underscore backend."""
        result = prefix_description("hub_spot", "Get contact details")
        assert result == "[Hub Spot] Get contact details"
    
    def test_description_prefix_multiple_underscores(self):
        """Test description prefixing with multiple underscores."""
        result = prefix_description("my_custom_api", "Do something")
        assert result == "[My Custom Api] Do something"
    
    def test_description_prefix_empty_description(self):
        """Test description prefixing with empty description."""
        result = prefix_description("notion", "")
        assert result == "[Notion]"
    
    def test_description_prefix_invalid_backend_raises(self):
        """Test that invalid backend raises error."""
        with pytest.raises(NamespaceError):
            prefix_description("Notion", "Search")


# =============================================================================
# Tool Model Tests
# =============================================================================


class TestToolModel:
    """Tests for Tool model."""
    
    def test_create_tool(self):
        """Test creating a Tool."""
        tool = Tool(
            name="search_pages",
            description="Search pages in workspace",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )
        assert tool.name == "search_pages"
        assert tool.description == "Search pages in workspace"
        assert "properties" in tool.inputSchema
    
    def test_tool_default_values(self):
        """Test Tool with default values."""
        tool = Tool(name="simple")
        assert tool.name == "simple"
        assert tool.description == ""
        assert tool.inputSchema == {}
    
    def test_tool_from_dict(self):
        """Test creating Tool from dict."""
        data = {
            "name": "search",
            "description": "Search items",
            "inputSchema": {"type": "object"}
        }
        tool = Tool(**data)
        assert tool.name == "search"


# =============================================================================
# Prefix Tool Tests
# =============================================================================


class TestPrefixTool:
    """Tests for prefix_tool function."""
    
    def test_prefix_tool_basic(self):
        """Test basic tool prefixing."""
        tool = Tool(
            name="search_pages",
            description="Search pages",
            inputSchema={"type": "object"}
        )
        prefixed = prefix_tool("notion", tool)
        
        assert prefixed.name == "notion.search_pages"
        assert prefixed.description == "[Notion] Search pages"
        assert prefixed.inputSchema == {"type": "object"}
    
    def test_prefix_tool_preserves_schema(self):
        """Test that prefix_tool preserves input schema exactly."""
        schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["query"]
        }
        tool = Tool(name="search", description="Search", inputSchema=schema)
        prefixed = prefix_tool("notion", tool)
        
        assert prefixed.inputSchema == schema
    
    def test_prefix_tool_empty_description(self):
        """Test prefixing tool with empty description."""
        tool = Tool(name="action", description="")
        prefixed = prefix_tool("backend", tool)
        
        assert prefixed.name == "backend.action"
        assert prefixed.description == "[Backend]"


# =============================================================================
# Prefix Tools (List) Tests
# =============================================================================


class TestPrefixTools:
    """Tests for prefix_tools function."""
    
    def test_prefix_tools_list(self):
        """Test prefixing a list of tools."""
        tools = [
            Tool(name="search", description="Search items"),
            Tool(name="read", description="Read item"),
            Tool(name="create", description="Create item"),
        ]
        prefixed = prefix_tools("notion", tools)
        
        assert len(prefixed) == 3
        assert prefixed[0].name == "notion.search"
        assert prefixed[1].name == "notion.read"
        assert prefixed[2].name == "notion.create"
        assert all("[Notion]" in t.description for t in prefixed)
    
    def test_prefix_tools_empty_list(self):
        """Test prefixing empty list."""
        prefixed = prefix_tools("notion", [])
        assert prefixed == []
    
    def test_prefix_tools_single_tool(self):
        """Test prefixing single-element list."""
        tools = [Tool(name="single", description="Single tool")]
        prefixed = prefix_tools("backend", tools)
        
        assert len(prefixed) == 1
        assert prefixed[0].name == "backend.single"


# =============================================================================
# Unprefix Tool Tests
# =============================================================================


class TestUnprefixTool:
    """Tests for unprefix_tool function."""
    
    def test_unprefix_tool_basic(self):
        """Test basic tool unprefixing."""
        tool = Tool(
            name="notion.search_pages",
            description="[Notion] Search pages",
            inputSchema={"type": "object"}
        )
        backend_id, unprefixed = unprefix_tool(tool)
        
        assert backend_id == "notion"
        assert unprefixed.name == "search_pages"
        assert unprefixed.description == "Search pages"
        assert unprefixed.inputSchema == {"type": "object"}
    
    def test_unprefix_tool_preserves_schema(self):
        """Test that unprefix preserves input schema."""
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        tool = Tool(
            name="api.action",
            description="[Api] Do action",
            inputSchema=schema
        )
        _, unprefixed = unprefix_tool(tool)
        
        assert unprefixed.inputSchema == schema
    
    def test_unprefix_tool_without_description_prefix(self):
        """Test unprefixing tool without description prefix."""
        tool = Tool(
            name="notion.search",
            description="Original description without prefix",
            inputSchema={}
        )
        backend_id, unprefixed = unprefix_tool(tool)
        
        assert backend_id == "notion"
        assert unprefixed.description == "Original description without prefix"
    
    def test_unprefix_tool_with_underscore_backend(self):
        """Test unprefixing with underscore backend ID."""
        tool = Tool(
            name="hub_spot.get_contact",
            description="[Hub Spot] Get contact details",
            inputSchema={}
        )
        backend_id, unprefixed = unprefix_tool(tool)
        
        assert backend_id == "hub_spot"
        assert unprefixed.name == "get_contact"
        assert unprefixed.description == "Get contact details"


# =============================================================================
# Round-Trip Tests
# =============================================================================


class TestRoundTrip:
    """Tests for prefix/unprefix round-trip consistency."""
    
    def test_tool_name_round_trip(self):
        """Test that prefix → unprefix returns original values."""
        backend = "notion"
        original = "search_pages"
        
        namespaced = prefix_tool_name(backend, original)
        result_backend, result_name = unprefix_tool_name(namespaced)
        
        assert result_backend == backend
        assert result_name == original
    
    def test_tool_round_trip(self):
        """Test that prefix_tool → unprefix_tool returns equivalent tool."""
        original = Tool(
            name="search",
            description="Search for items",
            inputSchema={"type": "object", "properties": {"q": {"type": "string"}}}
        )
        
        prefixed = prefix_tool("notion", original)
        backend_id, unprefixed = unprefix_tool(prefixed)
        
        assert backend_id == "notion"
        assert unprefixed.name == original.name
        assert unprefixed.description == original.description
        assert unprefixed.inputSchema == original.inputSchema


# =============================================================================
# Edge Cases and Security Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and security considerations."""
    
    def test_tool_name_with_many_dots(self):
        """Test tool name with many dots."""
        result = prefix_tool_name("api", "v1.users.profiles.get")
        assert result == "api.v1.users.profiles.get"
        
        backend, name = unprefix_tool_name(result)
        assert backend == "api"
        assert name == "v1.users.profiles.get"
    
    def test_unicode_in_tool_name(self):
        """Test that unicode in tool name is handled."""
        # Tool names can have unicode
        result = prefix_tool_name("backend", "search_日本語")
        assert result == "backend.search_日本語"
    
    def test_single_char_backend(self):
        """Test single character backend ID."""
        result = prefix_tool_name("a", "tool")
        assert result == "a.tool"
    
    def test_single_char_tool(self):
        """Test single character tool name."""
        result = prefix_tool_name("backend", "x")
        assert result == "backend.x"
    
    def test_separator_constant(self):
        """Test that separator is a dot."""
        assert NAMESPACE_SEPARATOR == "."
    
    def test_pattern_rejects_injection(self):
        """Test that pattern rejects potential injection attempts."""
        dangerous_inputs = [
            "notion; drop table",  # SQL injection attempt
            "notion\n\rbackend",   # CRLF injection
            "notion\x00backend",   # Null byte
            "../../../etc",        # Path traversal
        ]
        for dangerous in dangerous_inputs:
            with pytest.raises(NamespaceError):
                validate_backend_id(dangerous)
