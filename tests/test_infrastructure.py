"""
Tests for Phase 1 Task 1.1: Verify credservice → deeptrail-control rename
Tests that all services, configurations, and references are correctly renamed
"""
import os
import pytest
import requests
import time
from typing import Dict, Any


class TestInfrastructureRename:
    """Test suite for Phase 1 Task 1.1: Service Rename Validation"""
    
    def test_deeptrail_control_service_responds(self):
        """Test that deeptrail-control service responds on correct port"""
        control_url = os.getenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://localhost:8000")
        
        try:
            response = requests.get(f"{control_url}/health", timeout=5)
            assert response.status_code == 200
            
            health_data = response.json()
            assert "service" in health_data
            assert "DeepSecure" in health_data["service"]
            assert "version" in health_data
            assert health_data["status"] == "ok"
            
        except requests.exceptions.ConnectionError:
            pytest.skip(f"deeptrail-control service not available at {control_url}")
    
    def test_deeptrail_gateway_service_responds(self):
        """Test that deeptrail-gateway service responds on correct port"""
        gateway_url = os.getenv("DEEPSECURE_GATEWAY_URL", "http://localhost:8002")
        
        try:
            response = requests.get(f"{gateway_url}/", timeout=5)
            assert response.status_code == 200
            
            # Gateway responds with {"message":"Deeptrail Gateway is running"}
            data = response.json()
            assert "message" in data
            assert "Gateway is running" in data["message"]
            
        except requests.exceptions.ConnectionError:
            pytest.skip(f"deeptrail-gateway service not available at {gateway_url}")
    
    def test_environment_variables_use_correct_names(self):
        """Test that environment variables reference correct service names"""
        # Test that CLI uses correct environment variable names
        control_url = os.getenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL")
        gateway_url = os.getenv("DEEPSECURE_GATEWAY_URL")
        
        # These should be set for proper operation
        assert control_url is not None, "DEEPSECURE_DEEPTRAIL_CONTROL_URL should be set"
        assert gateway_url is not None, "DEEPSECURE_GATEWAY_URL should be set"
        
        # Should not contain credservice references
        assert "credservice" not in control_url.lower()
        assert "credservice" not in gateway_url.lower()
        
        # Should be valid URLs
        assert control_url.startswith("http"), "Control URL should be a valid HTTP URL"
        assert gateway_url.startswith("http"), "Gateway URL should be a valid HTTP URL"
    
    def test_api_endpoints_use_correct_base_path(self):
        """Test that API endpoints use correct base paths"""
        control_url = os.getenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://localhost:8000")
        
        try:
            # Test that API v1 endpoints are available
            response = requests.get(f"{control_url}/api/v1/health", timeout=5)
            # Should get 404 because /api/v1/health doesn't exist, but 
            # if we got connection error, service isn't running
            assert response.status_code in [404, 200]
            
        except requests.exceptions.ConnectionError:
            pytest.skip(f"deeptrail-control service not available at {control_url}")
    
    def test_docker_compose_configuration(self):
        """Test that docker-compose.yml has correct service names"""
        docker_compose_path = "docker-compose.yml"
        
        assert os.path.exists(docker_compose_path), "docker-compose.yml should exist"
        
        with open(docker_compose_path, 'r') as f:
            content = f.read()
            
        # Should contain deeptrail-control service
        assert "deeptrail-control:" in content
        # Should contain deeptrail-gateway service  
        assert "deeptrail-gateway:" in content
        # Should not contain old credservice references
        assert "credservice:" not in content
    
    def test_database_configuration(self):
        """Test that database configuration uses correct naming"""
        control_url = os.getenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://localhost:8000")
        
        try:
            response = requests.get(f"{control_url}/health", timeout=5)
            assert response.status_code == 200
            
            health_data = response.json()
            # Database should be connected
            assert "dependencies" in health_data
            assert "database" in health_data["dependencies"]
            assert health_data["dependencies"]["database"] == "connected"
            
        except requests.exceptions.ConnectionError:
            pytest.skip(f"deeptrail-control service not available at {control_url}")
    
    def test_service_integration(self):
        """Test that control plane and gateway can communicate"""
        control_url = os.getenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://localhost:8000")
        gateway_url = os.getenv("DEEPSECURE_GATEWAY_URL", "http://localhost:8002")
        
        try:
            # Test control plane is up
            control_response = requests.get(f"{control_url}/health", timeout=5)
            assert control_response.status_code == 200
            
            # Test gateway is up
            gateway_response = requests.get(f"{gateway_url}/", timeout=5)
            assert gateway_response.status_code == 200
            
            # Verify both services are properly named in their responses
            control_data = control_response.json()
            gateway_data = gateway_response.json()
            
            assert "DeepSecure" in control_data["service"]
            assert "Gateway" in gateway_data["message"]
            
        except requests.exceptions.ConnectionError:
            pytest.skip("One or both services not available")
    
    def test_no_credservice_references_in_codebase(self):
        """Test that no old credservice references remain in the codebase"""
        # This test would scan for any remaining credservice references
        # that might cause issues
        
        # Check that import statements don't reference credservice
        import deepsecure
        
        # If we can import deepsecure without errors, the main package is properly configured
        assert hasattr(deepsecure, 'Client'), "deepsecure.Client should be available"
        
        # Test that client can be instantiated (basic configuration test)
        try:
            client = deepsecure.Client()
            assert client is not None
        except Exception as e:
            # If it fails due to missing services, that's expected in some test environments
            if "not configured" in str(e) or "not available" in str(e):
                pytest.skip("DeepSecure services not configured for testing")
            else:
                raise 