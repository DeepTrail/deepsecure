"""
Tests for MCP Tool Aggregator (WS-B8).

Tests cover:
- AggregatedTool data class
- AggregationResult data class
- ToolAggregator core aggregation methods
- Namespace prefixing
- Permission-based filtering
- Backend registration
- Helper methods
- Global instance management
- Edge cases and error handling
"""

import pytest
from unittest.mock import MagicMock, patch

from app.mcp.aggregator import (
    AggregatedTool,
    AggregationResult,
    ToolAggregator,
    configure_tool_aggregator,
    get_tool_aggregator,
    reset_tool_aggregator,
)
from app.mcp.tool_cache import CachedTool, ToolCache


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_tool_cache():
    """Create mock tool cache with test data."""
    cache = MagicMock(spec=ToolCache)
    
    notion_tools = [
        CachedTool(
            name="search_pages",
            description="Search pages in workspace",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        ),
        CachedTool(
            name="read_page",
            description="Read a page by ID",
            inputSchema={"type": "object", "properties": {"id": {"type": "string"}}}
        ),
        CachedTool(
            name="create_page",
            description="Create a new page",
            inputSchema={"type": "object", "properties": {"title": {"type": "string"}}}
        ),
    ]
    
    slack_tools = [
        CachedTool(
            name="search_messages",
            description="Search messages",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        ),
        CachedTool(
            name="send_message",
            description="Send a message",
            inputSchema={"type": "object", "properties": {"text": {"type": "string"}}}
        ),
        CachedTool(
            name="list_channels",
            description="List channels",
            inputSchema={"type": "object"}
        ),
    ]
    
    hubspot_tools = [
        CachedTool(
            name="get_contact",
            description="Get a contact",
            inputSchema={"type": "object", "properties": {"id": {"type": "string"}}}
        ),
    ]
    
    def get_tools(backend_id):
        if backend_id == "notion":
            return notion_tools
        elif backend_id == "slack":
            return slack_tools
        elif backend_id == "hubspot":
            return hubspot_tools
        return []
    
    cache.get_tools.side_effect = get_tools
    return cache


@pytest.fixture
def aggregator(mock_tool_cache):
    """Create aggregator with mock cache."""
    return ToolAggregator(
        tool_cache=mock_tool_cache,
        registered_backends=["notion", "slack"]
    )


@pytest.fixture(autouse=True)
def reset_global_aggregator():
    """Reset global aggregator after each test."""
    yield
    reset_tool_aggregator()


# =============================================================================
# Test: AggregatedTool Data Class
# =============================================================================


class TestAggregatedTool:
    """Test AggregatedTool data class."""
    
    def test_to_dict_returns_mcp_format(self):
        """Test conversion to MCP format excludes internal fields."""
        tool = AggregatedTool(
            name="notion.search_pages",
            description="[Notion] Search pages in workspace",
            inputSchema={"type": "object"},
            backend="notion",
            original_name="search_pages"
        )
        
        result = tool.to_dict()
        
        assert result["name"] == "notion.search_pages"
        assert result["description"] == "[Notion] Search pages in workspace"
        assert "inputSchema" in result
        # Internal fields not in MCP format
        assert "backend" not in result
        assert "original_name" not in result
    
    def test_to_tool_returns_namespace_tool(self):
        """Test conversion to namespace.Tool."""
        tool = AggregatedTool(
            name="slack.send_message",
            description="[Slack] Send a message",
            inputSchema={"type": "object"},
            backend="slack",
            original_name="send_message"
        )
        
        namespace_tool = tool.to_tool()
        
        assert namespace_tool.name == "slack.send_message"
        assert namespace_tool.description == "[Slack] Send a message"
    
    def test_preserves_input_schema(self):
        """Test that inputSchema is preserved correctly."""
        schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["query"]
        }
        
        tool = AggregatedTool(
            name="notion.search_pages",
            description="Search pages",
            inputSchema=schema,
            backend="notion",
            original_name="search_pages"
        )
        
        assert tool.inputSchema == schema
        assert tool.to_dict()["inputSchema"] == schema


# =============================================================================
# Test: AggregationResult Data Class
# =============================================================================


class TestAggregationResult:
    """Test AggregationResult data class."""
    
    def test_total_tools_property(self):
        """Test total_tools property counts tools."""
        result = AggregationResult()
        assert result.total_tools == 0
        
        result.tools.append(MagicMock(spec=AggregatedTool))
        result.tools.append(MagicMock(spec=AggregatedTool))
        assert result.total_tools == 2
    
    def test_all_succeeded_true(self):
        """Test all_succeeded when no failures."""
        result = AggregationResult()
        result.backends_succeeded = ["notion", "slack"]
        
        assert result.all_succeeded is True
    
    def test_all_succeeded_false(self):
        """Test all_succeeded when there are failures."""
        result = AggregationResult()
        result.backends_succeeded = ["notion"]
        result.backends_failed = ["slack"]
        
        assert result.all_succeeded is False
    
    def test_to_tool_list(self):
        """Test conversion to list of tool dicts."""
        tool1 = AggregatedTool(
            name="notion.search_pages",
            description="Search",
            inputSchema={},
            backend="notion",
            original_name="search_pages"
        )
        tool2 = AggregatedTool(
            name="slack.send_message",
            description="Send",
            inputSchema={},
            backend="slack",
            original_name="send_message"
        )
        
        result = AggregationResult(tools=[tool1, tool2])
        tool_list = result.to_tool_list()
        
        assert len(tool_list) == 2
        assert tool_list[0]["name"] == "notion.search_pages"
        assert tool_list[1]["name"] == "slack.send_message"
    
    def test_get_tools_for_backend(self):
        """Test filtering tools by backend."""
        tool1 = AggregatedTool(
            name="notion.search",
            description="",
            inputSchema={},
            backend="notion",
            original_name="search"
        )
        tool2 = AggregatedTool(
            name="slack.send",
            description="",
            inputSchema={},
            backend="slack",
            original_name="send"
        )
        tool3 = AggregatedTool(
            name="notion.read",
            description="",
            inputSchema={},
            backend="notion",
            original_name="read"
        )
        
        result = AggregationResult(tools=[tool1, tool2, tool3])
        
        notion_tools = result.get_tools_for_backend("notion")
        assert len(notion_tools) == 2
        
        slack_tools = result.get_tools_for_backend("slack")
        assert len(slack_tools) == 1


# =============================================================================
# Test: ToolAggregator - Single Backend
# =============================================================================


class TestToolAggregatorSingleBackend:
    """Test aggregating from a single backend."""
    
    def test_aggregate_single_backend(self, aggregator):
        """Test aggregating from single backend."""
        result = aggregator.aggregate(["notion"])
        
        assert result.total_tools == 3
        assert "notion" in result.backends_succeeded
        assert len(result.backends_failed) == 0
    
    def test_aggregate_for_backend(self, aggregator):
        """Test convenience method for single backend."""
        result = aggregator.aggregate_for_backend("slack")
        
        assert result.total_tools == 3
        assert "slack" in result.backends_succeeded
    
    def test_namespace_prefix_applied(self, aggregator):
        """Test that namespace prefix is applied to all tools."""
        result = aggregator.aggregate(["notion"])
        
        for tool in result.tools:
            assert tool.name.startswith("notion.")
            assert tool.backend == "notion"
            assert not tool.original_name.startswith("notion.")
    
    def test_description_enhanced(self, aggregator):
        """Test that description is enhanced with backend prefix."""
        result = aggregator.aggregate(["notion"])
        
        for tool in result.tools:
            assert tool.description.startswith("[Notion]")
    
    def test_input_schema_preserved(self, aggregator):
        """Test that inputSchema is preserved unchanged."""
        result = aggregator.aggregate(["notion"])
        
        search_tool = next(t for t in result.tools if "search" in t.name)
        assert "query" in search_tool.inputSchema.get("properties", {})


# =============================================================================
# Test: ToolAggregator - Multiple Backends
# =============================================================================


class TestToolAggregatorMultipleBackends:
    """Test aggregating from multiple backends."""
    
    def test_aggregate_multiple_backends(self, aggregator):
        """Test aggregating from multiple backends."""
        result = aggregator.aggregate(["notion", "slack"])
        
        assert result.total_tools == 6  # 3 + 3
        assert "notion" in result.backends_succeeded
        assert "slack" in result.backends_succeeded
    
    def test_tools_from_both_backends(self, aggregator):
        """Test that tools from both backends are included."""
        result = aggregator.aggregate(["notion", "slack"])
        
        tool_names = [t.name for t in result.tools]
        
        # Notion tools
        assert "notion.search_pages" in tool_names
        assert "notion.read_page" in tool_names
        
        # Slack tools
        assert "slack.send_message" in tool_names
        assert "slack.list_channels" in tool_names
    
    def test_aggregate_all_registered(self, aggregator):
        """Test aggregate_all with registered backends."""
        result = aggregator.aggregate_all()
        
        assert result.total_tools == 6
        assert len(result.backends_succeeded) == 2


# =============================================================================
# Test: ToolAggregator - Filtering
# =============================================================================


class TestToolAggregatorFiltering:
    """Test aggregation filtering."""
    
    def test_filter_by_custom_function(self, aggregator):
        """Test filtering with custom function."""
        def search_only(tool: AggregatedTool) -> bool:
            return "search" in tool.name
        
        result = aggregator.aggregate(["notion", "slack"], filter_func=search_only)
        
        assert result.total_tools == 2
        tool_names = [t.name for t in result.tools]
        assert "notion.search_pages" in tool_names
        assert "slack.search_messages" in tool_names
    
    def test_filter_excludes_all(self, aggregator):
        """Test filter that excludes all tools."""
        def exclude_all(tool: AggregatedTool) -> bool:
            return False
        
        result = aggregator.aggregate(["notion"], filter_func=exclude_all)
        
        assert result.total_tools == 0
        # Backend still succeeded (tools were fetched, just filtered out)
        assert "notion" in result.backends_succeeded
    
    def test_aggregate_with_permissions(self, aggregator):
        """Test aggregation filtered by permissions."""
        permissions = ["notion:pages:search", "slack:messages:search"]
        
        result = aggregator.aggregate_with_permissions(
            ["notion", "slack"],
            permissions
        )
        
        # Only permitted tools included
        tool_names = [t.name for t in result.tools]
        assert "notion.search_pages" in tool_names
        assert "slack.search_messages" in tool_names
        # Unpermitted tools excluded
        assert "notion.create_page" not in tool_names
        assert "slack.send_message" not in tool_names
    
    def test_aggregate_with_empty_permissions(self, aggregator):
        """Test that empty permissions returns no tools."""
        result = aggregator.aggregate_with_permissions(
            ["notion", "slack"],
            []  # No permissions
        )
        
        assert result.total_tools == 0


# =============================================================================
# Test: ToolAggregator - Error Handling
# =============================================================================


class TestToolAggregatorErrorHandling:
    """Test error handling in aggregation."""
    
    def test_nonexistent_backend_fails(self, aggregator):
        """Test that nonexistent backend is tracked as failed."""
        result = aggregator.aggregate(["nonexistent"])
        
        assert result.total_tools == 0
        assert "nonexistent" in result.backends_failed
    
    def test_mixed_success_and_failure(self, aggregator):
        """Test aggregation with some backends failing."""
        result = aggregator.aggregate(["notion", "nonexistent"])
        
        assert "notion" in result.backends_succeeded
        assert "nonexistent" in result.backends_failed
        assert result.total_tools == 3  # Only notion tools
    
    def test_all_backends_fail_returns_empty(self, aggregator):
        """Test that all failures returns empty result."""
        result = aggregator.aggregate(["unknown1", "unknown2"])
        
        assert result.total_tools == 0
        assert result.all_succeeded is False
    
    def test_cache_exception_handled(self, mock_tool_cache):
        """Test that cache exceptions are handled gracefully."""
        mock_tool_cache.get_tools.side_effect = Exception("Cache error")
        
        aggregator = ToolAggregator(mock_tool_cache, ["notion"])
        result = aggregator.aggregate(["notion"])
        
        assert result.total_tools == 0
        assert "notion" in result.backends_failed


# =============================================================================
# Test: Backend Registration
# =============================================================================


class TestBackendRegistration:
    """Test backend registration methods."""
    
    def test_register_backend(self, mock_tool_cache):
        """Test registering new backend."""
        aggregator = ToolAggregator(mock_tool_cache)
        assert len(aggregator.get_registered_backends()) == 0
        
        aggregator.register_backend("notion")
        assert "notion" in aggregator.get_registered_backends()
    
    def test_register_duplicate_ignored(self, mock_tool_cache):
        """Test that duplicate registration is ignored."""
        aggregator = ToolAggregator(mock_tool_cache, ["notion"])
        
        aggregator.register_backend("notion")
        
        assert aggregator.get_registered_backends().count("notion") == 1
    
    def test_unregister_backend(self, aggregator):
        """Test unregistering backend."""
        assert aggregator.unregister_backend("notion") is True
        assert "notion" not in aggregator.get_registered_backends()
    
    def test_unregister_nonexistent_returns_false(self, aggregator):
        """Test unregistering nonexistent backend."""
        assert aggregator.unregister_backend("unknown") is False
    
    def test_aggregate_all_uses_registered(self, aggregator):
        """Test that aggregate_all uses registered backends."""
        # Unregister slack
        aggregator.unregister_backend("slack")
        
        result = aggregator.aggregate_all()
        
        # Only notion should be aggregated
        assert result.total_tools == 3
        assert "notion" in result.backends_succeeded
        assert "slack" not in result.backends_succeeded
    
    def test_aggregate_all_empty_registered(self, mock_tool_cache):
        """Test aggregate_all with no registered backends."""
        aggregator = ToolAggregator(mock_tool_cache)
        
        result = aggregator.aggregate_all()
        
        assert result.total_tools == 0


# =============================================================================
# Test: Helper Methods
# =============================================================================


class TestHelperMethods:
    """Test helper methods."""
    
    def test_get_backend_for_tool_valid(self, aggregator):
        """Test extracting backend from namespaced tool."""
        assert aggregator.get_backend_for_tool("notion.search_pages") == "notion"
        assert aggregator.get_backend_for_tool("slack.send_message") == "slack"
        assert aggregator.get_backend_for_tool("hub_spot.get_contact") == "hub_spot"
    
    def test_get_backend_for_tool_invalid(self, aggregator):
        """Test invalid tool name returns None."""
        assert aggregator.get_backend_for_tool("no_namespace") is None
        assert aggregator.get_backend_for_tool("") is None
    
    def test_get_original_name_valid(self, aggregator):
        """Test extracting original name from namespaced tool."""
        assert aggregator.get_original_name("notion.search_pages") == "search_pages"
        assert aggregator.get_original_name("slack.send_message") == "send_message"
    
    def test_get_original_name_with_dots(self, aggregator):
        """Test extracting original name when it contains dots."""
        assert aggregator.get_original_name("github.repos.create") == "repos.create"
    
    def test_get_original_name_invalid(self, aggregator):
        """Test invalid tool name returns None."""
        assert aggregator.get_original_name("no_namespace") is None
    
    def test_find_tool_exists(self, aggregator):
        """Test finding existing tool."""
        tool = aggregator.find_tool("notion.search_pages")
        
        assert tool is not None
        assert tool.name == "notion.search_pages"
        assert tool.backend == "notion"
        assert tool.original_name == "search_pages"
    
    def test_find_tool_not_found(self, aggregator):
        """Test finding nonexistent tool."""
        assert aggregator.find_tool("notion.nonexistent") is None
        assert aggregator.find_tool("unknown.tool") is None
    
    def test_find_tool_backend_not_registered(self, aggregator):
        """Test finding tool when backend not in search scope."""
        # hubspot is not registered
        assert aggregator.find_tool("hubspot.get_contact") is None
        
        # But can find with explicit backend list
        tool = aggregator.find_tool("hubspot.get_contact", backends=["hubspot"])
        assert tool is not None
    
    def test_tool_exists(self, aggregator):
        """Test tool_exists convenience method."""
        assert aggregator.tool_exists("notion.search_pages") is True
        assert aggregator.tool_exists("notion.nonexistent") is False


# =============================================================================
# Test: Global Instance
# =============================================================================


class TestGlobalInstance:
    """Test global instance management."""
    
    def test_get_without_configure_raises(self):
        """Test that get without configure raises error."""
        reset_tool_aggregator()
        
        with pytest.raises(RuntimeError, match="not initialized"):
            get_tool_aggregator()
    
    def test_configure_and_get(self, mock_tool_cache):
        """Test configuring and getting global instance."""
        aggregator = configure_tool_aggregator(mock_tool_cache, ["notion"])
        
        fetched = get_tool_aggregator()
        
        assert fetched is aggregator
        assert "notion" in fetched.get_registered_backends()
    
    def test_reset_clears_instance(self, mock_tool_cache):
        """Test that reset clears the global instance."""
        configure_tool_aggregator(mock_tool_cache)
        
        reset_tool_aggregator()
        
        with pytest.raises(RuntimeError):
            get_tool_aggregator()


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and unusual scenarios."""
    
    def test_empty_backends_list(self, aggregator):
        """Test aggregating with empty backends list."""
        result = aggregator.aggregate([])
        
        assert result.total_tools == 0
        assert len(result.backends_succeeded) == 0
    
    def test_backend_with_empty_tools(self, mock_tool_cache):
        """Test backend that returns empty tool list."""
        mock_tool_cache.get_tools.side_effect = lambda b: [] if b == "empty" else None
        
        aggregator = ToolAggregator(mock_tool_cache)
        result = aggregator.aggregate(["empty"])
        
        # Empty list is treated as failure (no tools)
        assert result.total_tools == 0
        assert "empty" in result.backends_failed
    
    def test_duplicate_backends_in_request(self, aggregator):
        """Test requesting same backend multiple times."""
        result = aggregator.aggregate(["notion", "notion"])
        
        # Should aggregate notion twice (6 tools)
        assert result.total_tools == 6
    
    def test_filter_with_none_returns_all(self, aggregator):
        """Test that None filter returns all tools."""
        result = aggregator.aggregate(["notion"], filter_func=None)
        
        assert result.total_tools == 3
    
    def test_concurrent_access_safe(self, aggregator):
        """Test that concurrent access doesn't cause issues."""
        import threading
        
        results = []
        errors = []
        
        def aggregate_notion():
            try:
                result = aggregator.aggregate(["notion"])
                results.append(result.total_tools)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=aggregate_notion) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert all(r == 3 for r in results)


# =============================================================================
# Test: Integration with PermissionMapper
# =============================================================================


class TestPermissionMapperIntegration:
    """Test integration with PermissionMapper."""
    
    def test_uses_permission_mapper(self, aggregator):
        """Test that aggregate_with_permissions uses PermissionMapper."""
        permissions = ["notion:pages:search"]
        
        result = aggregator.aggregate_with_permissions(["notion"], permissions)
        
        # Should only have search_pages
        assert result.total_tools == 1
        assert result.tools[0].name == "notion.search_pages"
    
    def test_multiple_permissions(self, aggregator):
        """Test with multiple specific permissions."""
        permissions = [
            "notion:pages:search",
            "notion:pages:read",
            "slack:messages:send"
        ]
        
        result = aggregator.aggregate_with_permissions(
            ["notion", "slack"],
            permissions
        )
        
        tool_names = [t.name for t in result.tools]
        assert "notion.search_pages" in tool_names
        assert "notion.read_page" in tool_names
        assert "slack.send_message" in tool_names
        assert result.total_tools == 3
    
    def test_permission_filtering_excludes_unpermitted(self, aggregator):
        """Test that unpermitted tools are excluded."""
        # Only grant search permission for notion
        permissions = ["notion:pages:search"]
        
        result = aggregator.aggregate_with_permissions(["notion"], permissions)
        
        tool_names = [t.name for t in result.tools]
        assert "notion.search_pages" in tool_names
        # These should be excluded
        assert "notion.read_page" not in tool_names
        assert "notion.create_page" not in tool_names
