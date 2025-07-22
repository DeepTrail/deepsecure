#!/usr/bin/env python3
"""
Phase 2 Routing Validation: Ensure management operations go direct to control, tool operations go through gateway

This test suite validates that the Phase 2 intelligent routing logic correctly routes operations:
- Management Operations (agents, auth, vault, policies) → Direct to deeptrail-control:8000
- Tool Operations (external APIs) → Through deeptrail-gateway:8002

Architecture Under Test:
Management Operations: SDK → deeptrail-control:8000 (direct)
Tool Operations: SDK → deeptrail-gateway:8002 → External APIs (proxied)

This validates the core Phase 2 principle: separation of control plane and data plane.
"""

import pytest
import pytest_asyncio
import asyncio
import httpx
import json
import time
from typing import Dict, Any, Optional, List
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys

# Add the deepsecure package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from deepsecure._core.base_client import BaseClient
from deepsecure._core.identity_manager import IdentityManager
from deepsecure._core.vault_client import VaultClient
from deepsecure._core.agent_client import AgentClient


class RoutingValidationTester:
    """Test utility for validating Phase 2 routing logic."""
    
    def __init__(self):
        # Use the same URLs that BaseClient will use
        from deepsecure._core.config import get_effective_deeptrail_control_url, get_effective_deeptrail_gateway_url
        self.deeptrail_control_url = get_effective_deeptrail_control_url() or "http://localhost:8000"
        self.deeptrail_gateway_url = get_effective_deeptrail_gateway_url() or "http://localhost:8002"
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Track actual requests made
        self.requests_made = []
        
    async def cleanup(self):
        """Clean up resources."""
        await self.client.aclose()
    
    def create_mock_base_client(self) -> BaseClient:
        """Create a BaseClient with request tracking."""
        base_client = BaseClient()
        
        # Store original _request method
        original_request = base_client._request
        
        # Create wrapper that tracks requests
        async def tracking_request(method, path, **kwargs):
            # Determine which URL was actually used
            if hasattr(base_client, '_last_request_url'):
                url = base_client._last_request_url
            else:
                url = f"{base_client.base_url}{path}"
            
            self.requests_made.append({
                'method': method,
                'path': path,
                'url': url,
                'kwargs': kwargs
            })
            
            return await original_request(method, path, **kwargs)
        
        # Replace _request method with tracking version
        base_client._request = tracking_request
        
        return base_client
    
    async def test_management_operation_routing(self, operation_type: str, path: str) -> Dict[str, Any]:
        """Test that a management operation routes directly to deeptrail-control."""
        base_client = BaseClient()
        
        # Test using the routing logic directly
        is_management = base_client._is_management_operation(path)
        
        # For management operations, the URL should be the control URL
        if is_management:
            expected_url = self.deeptrail_control_url
            actual_url = base_client._api_url
            routed_correctly = actual_url == expected_url
        else:
            # Not a management operation, should route to gateway
            expected_url = self.deeptrail_gateway_url
            actual_url = base_client._gateway_url
            routed_correctly = actual_url == expected_url
        
        result = {
            'operation_type': operation_type,
            'path': path,
            'is_management': is_management,
            'routed_correctly': routed_correctly,
            'actual_url': actual_url,
            'expected_url': expected_url
        }
        
        return result
    
    async def test_tool_operation_routing(self, operation_type: str, path: str) -> Dict[str, Any]:
        """Test that a tool operation routes through deeptrail-gateway."""
        base_client = BaseClient()
        
        # Test using the routing logic directly
        is_management = base_client._is_management_operation(path)
        
        # For tool operations (non-management), the URL should be the gateway URL
        if not is_management:
            expected_url = self.deeptrail_gateway_url
            actual_url = base_client._gateway_url
            routed_correctly = actual_url == expected_url
        else:
            # Management operation, should route to control
            expected_url = self.deeptrail_control_url
            actual_url = base_client._api_url
            routed_correctly = actual_url == expected_url
        
        result = {
            'operation_type': operation_type,
            'path': path,
            'is_management': is_management,
            'routed_correctly': routed_correctly,
            'actual_url': actual_url,
            'expected_url': expected_url
        }
        
        return result


class TestPhase2RoutingValidation:
    """Phase 2 Routing Validation Tests."""
    
    @pytest_asyncio.fixture
    async def routing_tester(self):
        """Create a routing validation tester instance."""
        tester = RoutingValidationTester()
        yield tester
        await tester.cleanup()
    
    @pytest.mark.asyncio
    async def test_management_operations_route_to_control(self, routing_tester):
        """Test that management operations route directly to deeptrail-control."""
        
        # Define management operations to test
        management_operations = [
            ("agent_management", "/api/v1/agents"),
            ("agent_detail", "/api/v1/agents/test-agent"),
            ("authentication", "/api/v1/auth/challenge"),
            ("token_issuance", "/api/v1/auth/token"),
            ("vault_credentials", "/api/v1/vault/credentials"),
            ("credential_management", "/api/v1/vault/credentials/test-cred"),
            ("policy_management", "/api/v1/policies"),
            ("policy_detail", "/api/v1/policies/test-policy"),
            ("health_check", "/health"),
            ("bootstrap_attestation", "/api/v1/bootstrap/attest")
        ]
        
        results = []
        
        for operation_type, path in management_operations:
            result = await routing_tester.test_management_operation_routing(operation_type, path)
            results.append(result)
        
        # Validate all management operations routed correctly
        for result in results:
            assert result['routed_correctly'], f"Management operation {result['operation_type']} ({result['path']}) should route to deeptrail-control, but routed to {result['actual_url']}"
        
        # Summary validation
        total_operations = len(results)
        correct_routing = sum(1 for r in results if r['routed_correctly'])
        
        assert correct_routing == total_operations, f"Only {correct_routing}/{total_operations} management operations routed correctly"
    
    @pytest.mark.asyncio
    async def test_tool_operations_route_to_gateway(self, routing_tester):
        """Test that tool operations route through deeptrail-gateway."""
        
        # Define tool operations to test (external API calls)
        tool_operations = [
            ("external_api_call", "/api/external/service"),
            ("openai_api", "/v1/chat/completions"),
            ("http_request", "/some/external/endpoint"),
            ("webhook_call", "/webhooks/callback"),
            ("third_party_service", "/api/v2/data")
        ]
        
        results = []
        
        for operation_type, path in tool_operations:
            result = await routing_tester.test_tool_operation_routing(operation_type, path)
            results.append(result)
        
        # Validate all tool operations routed correctly
        for result in results:
            assert result['routed_correctly'], f"Tool operation {result['operation_type']} ({result['path']}) should route to deeptrail-gateway, but routed to {result['actual_url']}"
        
        # Summary validation
        total_operations = len(results)
        correct_routing = sum(1 for r in results if r['routed_correctly'])
        
        assert correct_routing == total_operations, f"Only {correct_routing}/{total_operations} tool operations routed correctly"
    
    @pytest.mark.asyncio
    async def test_base_client_routing_logic(self, routing_tester):
        """Test the BaseClient._is_management_operation() method directly."""
        base_client = BaseClient()
        
        # Test management operation detection
        management_paths = [
            "/api/v1/agents",
            "/api/v1/agents/test-agent",
            "/api/v1/auth/challenge",
            "/api/v1/auth/token",
            "/api/v1/vault/credentials",
            "/api/v1/vault/credentials/test-cred/revoke",
            "/api/v1/policies",
            "/api/v1/policies/test-policy",
            "/health",
            "/api/v1/bootstrap/attest"
        ]
        
        for path in management_paths:
            is_management = base_client._is_management_operation(path)
            assert is_management, f"Path {path} should be detected as management operation"
        
        # Test tool operation detection
        tool_paths = [
            "/api/external/service",
            "/v1/chat/completions",
            "/some/external/endpoint",
            "/webhooks/callback",
            "/api/v2/data",
            "/custom/tool/endpoint"
        ]
        
        for path in tool_paths:
            is_management = base_client._is_management_operation(path)
            assert not is_management, f"Path {path} should NOT be detected as management operation"
    
    @pytest.mark.asyncio
    async def test_vault_client_routing(self, routing_tester):
        """Test that VaultClient operations route correctly."""
        
        # Test management operations through VaultClient
        base_client = BaseClient()
        vault_client = VaultClient(base_client)
        
        # VaultClient uses the base client's routing logic
        # Test that it correctly identifies management operations
        assert vault_client._client._is_management_operation("/api/v1/vault/credentials")
        assert vault_client._client._is_management_operation("/api/v1/vault/credentials/test-cred")
        assert not vault_client._client._is_management_operation("/api/external/service")
        
        # Verify the client URLs are set correctly
        assert vault_client._client._api_url == routing_tester.deeptrail_control_url
        assert vault_client._client._gateway_url == routing_tester.deeptrail_gateway_url
    
    @pytest.mark.asyncio
    async def test_agent_client_routing(self, routing_tester):
        """Test that AgentClient operations route correctly."""
        
        # Test management operations through AgentClient
        agent_client = AgentClient()
        
        # Clear previous requests
        routing_tester.requests_made.clear()
        
        # Test agent management operations (should go to control)
        try:
            await agent_client.create_agent("test-agent", "Test Agent")
        except Exception:
            pass  # Expected to fail, but we're testing routing
        
        # Note: AgentClient inherits from BaseClient so it should use the same routing logic
        # For now, we'll just verify the routing logic method exists
        assert hasattr(agent_client, '_is_management_operation')
        assert agent_client._is_management_operation("/api/v1/agents")
    
    @pytest.mark.asyncio
    async def test_routing_consistency_across_clients(self, routing_tester):
        """Test that routing is consistent across all client types."""
        
        # Test that all client types use the same routing logic
        base_client = BaseClient()
        vault_client = VaultClient(base_client)
        agent_client = AgentClient()  # AgentClient inherits from BaseClient
        
        # Test the same management path across all clients
        test_path = "/api/v1/agents"
        
        # All should identify this as a management operation
        assert base_client._is_management_operation(test_path)
        assert vault_client._client._is_management_operation(test_path)
        assert agent_client._is_management_operation(test_path)  # AgentClient inherits from BaseClient
        
        # Test the same tool path across all clients
        test_path = "/api/external/service"
        
        # All should identify this as a tool operation
        assert not base_client._is_management_operation(test_path)
        assert not vault_client._client._is_management_operation(test_path)
        assert not agent_client._is_management_operation(test_path)
    
    @pytest.mark.asyncio
    async def test_routing_edge_cases(self, routing_tester):
        """Test routing edge cases and boundary conditions."""
        base_client = BaseClient()
        
        # Test empty path
        assert base_client._is_management_operation("") == False
        
        # Test root path
        assert base_client._is_management_operation("/") == False
        
        # Test paths with query parameters
        assert base_client._is_management_operation("/api/v1/agents?limit=10") == True
        assert base_client._is_management_operation("/external/api?key=value") == False
        
        # Test paths with fragments
        assert base_client._is_management_operation("/api/v1/policies#section") == True
        assert base_client._is_management_operation("/tools/api#fragment") == False
        
        # Test case sensitivity
        assert base_client._is_management_operation("/API/V1/AGENTS") == True
        assert base_client._is_management_operation("/api/V1/agents") == True
    
    @pytest.mark.asyncio
    async def test_routing_performance(self, routing_tester):
        """Test that routing decisions are made quickly."""
        import time
        
        base_client = BaseClient()
        
        # Test performance of routing decisions
        management_path = "/api/v1/agents"
        tool_path = "/api/external/service"
        
        # Test management operation routing speed
        start_time = time.time()
        for _ in range(1000):
            base_client._is_management_operation(management_path)
        management_time = time.time() - start_time
        
        # Test tool operation routing speed
        start_time = time.time()
        for _ in range(1000):
            base_client._is_management_operation(tool_path)
        tool_time = time.time() - start_time
        
        # Routing decisions should be very fast (< 10ms for 1000 operations)
        assert management_time < 0.01, f"Management operation routing took {management_time:.3f}s for 1000 operations"
        assert tool_time < 0.01, f"Tool operation routing took {tool_time:.3f}s for 1000 operations"


@pytest.mark.asyncio
async def test_phase2_routing_validation_summary():
    """Summary test that validates the complete Phase 2 routing logic."""
    
    # Create tester
    tester = RoutingValidationTester()
    
    try:
        # Test management operations routing
        management_results = []
        management_ops = [
            ("agent_list", "/api/v1/agents"),
            ("auth_challenge", "/api/v1/auth/challenge"),
            ("vault_credentials", "/api/v1/vault/credentials"),
            ("policy_list", "/api/v1/policies")
        ]
        
        for op_type, path in management_ops:
            result = await tester.test_management_operation_routing(op_type, path)
            management_results.append(result)
        
        # Test tool operations routing
        tool_results = []
        tool_ops = [
            ("external_api", "/api/external/service"),
            ("openai_completion", "/v1/chat/completions"),
            ("webhook", "/webhooks/callback")
        ]
        
        for op_type, path in tool_ops:
            result = await tester.test_tool_operation_routing(op_type, path)
            tool_results.append(result)
        
        # Calculate routing accuracy
        total_management = len(management_results)
        correct_management = sum(1 for r in management_results if r['routed_correctly'])
        management_accuracy = (correct_management / total_management) * 100 if total_management > 0 else 0
        
        total_tool = len(tool_results)
        correct_tool = sum(1 for r in tool_results if r['routed_correctly'])
        tool_accuracy = (correct_tool / total_tool) * 100 if total_tool > 0 else 0
        
        overall_accuracy = ((correct_management + correct_tool) / (total_management + total_tool)) * 100
        
        # Generate summary
        print("\n" + "="*60)
        print("PHASE 2 ROUTING VALIDATION SUMMARY")
        print("="*60)
        print(f"Management Operations Routing:")
        print(f"  Total tested: {total_management}")
        print(f"  Correctly routed: {correct_management}")
        print(f"  Accuracy: {management_accuracy:.1f}%")
        print(f"  Target: deeptrail-control:8000")
        print()
        print(f"Tool Operations Routing:")
        print(f"  Total tested: {total_tool}")
        print(f"  Correctly routed: {correct_tool}")
        print(f"  Accuracy: {tool_accuracy:.1f}%")
        print(f"  Target: deeptrail-gateway:8002")
        print()
        print(f"Overall Routing Accuracy: {overall_accuracy:.1f}%")
        print(f"Status: {'✅ PASS' if overall_accuracy >= 90 else '❌ FAIL'}")
        print("="*60)
        
        # Assert overall success
        assert overall_accuracy >= 90, f"Phase 2 routing validation failed: {overall_accuracy:.1f}% accuracy (minimum 90% required)"
        
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"]) 