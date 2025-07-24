#!/usr/bin/env python3
"""
Test script for validating enhanced environment detection logic.
Tests intelligent bootstrap method selection across all supported platforms.
"""
import sys
import os
import logging
from unittest.mock import patch, MagicMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

try:
    from deepsecure._core.environment_detector import (
        EnvironmentDetector,
        EnvironmentType,
        EnvironmentInfo,
        environment_detector
    )
    from deepsecure._core.identity_manager import IdentityManager
except ImportError as e:
    print(f"Import error: {e}")
    print("This test requires the deepsecure package to be available")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnvironmentDetectionTester:
    """Test class for validating environment detection functionality."""
    
    def __init__(self):
        self.detector = EnvironmentDetector()
        
    def test_kubernetes_detection(self):
        """Test Kubernetes environment detection."""
        logger.info("=== Testing Kubernetes Environment Detection ===")
        
        test_scenarios = [
            {
                "name": "Full Kubernetes Environment",
                "mock_files": {
                    "/var/run/secrets/kubernetes.io/serviceaccount/token": "mock-k8s-token",
                    "/var/run/secrets/kubernetes.io/serviceaccount/namespace": "default"
                },
                "mock_env": {
                    "KUBERNETES_SERVICE_HOST": "10.96.0.1",
                    "KUBERNETES_SERVICE_PORT": "443"
                },
                "expected_confidence": 0.8,
                "expected_bootstrap_capable": True
            },
            {
                "name": "Minimal Kubernetes Environment", 
                "mock_files": {
                    "/var/run/secrets/kubernetes.io/serviceaccount/token": "mock-k8s-token"
                },
                "mock_env": {},
                "expected_confidence": 0.6,
                "expected_bootstrap_capable": True
            },
            {
                "name": "Non-Kubernetes Environment",
                "mock_files": {},
                "mock_env": {},
                "expected_confidence": 0.0,
                "expected_bootstrap_capable": False
            }
        ]
        
        success_count = 0
        
        for scenario in test_scenarios:
            with patch('os.path.exists') as mock_exists, \
                 patch.dict(os.environ, scenario["mock_env"], clear=True):
                
                # Mock file existence
                def mock_exists_func(path):
                    return path in scenario["mock_files"]
                mock_exists.side_effect = mock_exists_func
                
                # Mock file reading
                with patch('builtins.open', create=True) as mock_open:
                    def mock_open_func(path, mode='r'):
                        if path in scenario["mock_files"]:
                            mock_file = MagicMock()
                            mock_file.__enter__.return_value.read.return_value = scenario["mock_files"][path]
                            return mock_file
                        raise FileNotFoundError()
                    
                    mock_open.side_effect = mock_open_func
                    
                    # Test detection
                    env_info = self.detector._detect_kubernetes()
                    
                    if scenario["expected_confidence"] > 0:
                        if env_info and env_info.environment_type == EnvironmentType.KUBERNETES:
                            if (abs(env_info.confidence - scenario["expected_confidence"]) < 0.1 and
                                env_info.bootstrap_capable == scenario["expected_bootstrap_capable"]):
                                logger.info(f"✓ {scenario['name']}: Detection successful")
                                success_count += 1
                            else:
                                logger.error(f"✗ {scenario['name']}: Confidence or capability mismatch")
                        else:
                            logger.error(f"✗ {scenario['name']}: Failed to detect Kubernetes")
                    else:
                        if env_info is None:
                            logger.info(f"✓ {scenario['name']}: Correctly detected no Kubernetes")
                            success_count += 1
                        else:
                            logger.error(f"✗ {scenario['name']}: False positive detection")
        
        logger.info(f"Kubernetes detection: {success_count}/{len(test_scenarios)} tests passed")
        return success_count == len(test_scenarios)
    
    def test_aws_detection(self):
        """Test AWS environment detection.""" 
        logger.info("=== Testing AWS Environment Detection ===")
        
        test_scenarios = [
            {
                "name": "EC2 Instance Environment",
                "mock_env": {
                    "AWS_REGION": "us-east-1",
                    "AWS_EXECUTION_ENV": "EC2-Instance"
                },
                "mock_requests": [
                    {"url": "http://169.254.169.254/latest/meta-data/instance-id", 
                     "response": "i-1234567890abcdef0", "status": 200}
                ],
                "expected_confidence": 1.2,  # Will be capped at 1.0
                "expected_bootstrap_capable": True
            },
            {
                "name": "Lambda Environment",
                "mock_env": {
                    "AWS_LAMBDA_FUNCTION_NAME": "my-function",
                    "AWS_REGION": "us-west-2"
                },
                "mock_requests": [],
                "expected_confidence": 0.8,
                "expected_bootstrap_capable": True
            },
            {
                "name": "Non-AWS Environment",
                "mock_env": {},
                "mock_requests": [],
                "expected_confidence": 0.0,
                "expected_bootstrap_capable": False
            }
        ]
        
        success_count = 0
        
        for scenario in test_scenarios:
            with patch.dict(os.environ, scenario["mock_env"], clear=True):
                with patch('requests.get') as mock_requests_get:
                    # Setup request mocking
                    def mock_request_func(url, timeout=None):
                        for req in scenario["mock_requests"]:
                            if req["url"] == url:
                                mock_response = MagicMock()
                                mock_response.status_code = req["status"]
                                mock_response.text = req["response"]
                                return mock_response
                        # Default to connection error
                        raise ConnectionError("Mocked connection error")
                    
                    mock_requests_get.side_effect = mock_request_func
                    
                    # Test detection
                    env_info = self.detector._detect_aws()
                    
                    if scenario["expected_confidence"] > 0:
                        if env_info and env_info.environment_type == EnvironmentType.AWS:
                            actual_confidence = min(env_info.confidence, 1.0)
                            expected_confidence = min(scenario["expected_confidence"], 1.0)
                            
                            if (abs(actual_confidence - expected_confidence) < 0.1 and
                                env_info.bootstrap_capable == scenario["expected_bootstrap_capable"]):
                                logger.info(f"✓ {scenario['name']}: Detection successful")
                                success_count += 1
                            else:
                                logger.error(f"✗ {scenario['name']}: Confidence or capability mismatch")
                        else:
                            logger.error(f"✗ {scenario['name']}: Failed to detect AWS")
                    else:
                        if env_info is None:
                            logger.info(f"✓ {scenario['name']}: Correctly detected no AWS")
                            success_count += 1
                        else:
                            logger.error(f"✗ {scenario['name']}: False positive detection")
        
        logger.info(f"AWS detection: {success_count}/{len(test_scenarios)} tests passed")
        return success_count == len(test_scenarios)
    
    def test_azure_detection(self):
        """Test Azure environment detection."""
        logger.info("=== Testing Azure Environment Detection ===")
        
        test_scenarios = [
            {
                "name": "Azure VM with IMDS",
                "mock_env": {
                    "AZURE_TENANT_ID": "tenant-id-123"
                },
                "mock_requests": [
                    {
                        "url": "http://169.254.169.254/metadata/instance?api-version=2021-02-01",
                        "response": {"compute": {"vmId": "vm-123", "resourceGroupName": "rg-test"}},
                        "status": 200
                    }
                ],
                "expected_confidence": 0.9,
                "expected_bootstrap_capable": True
            },
            {
                "name": "Azure App Service",
                "mock_env": {
                    "MSI_ENDPOINT": "http://127.0.0.1:41741/MSI/token/",
                    "IDENTITY_HEADER": "header-value"
                },
                "mock_requests": [],
                "expected_confidence": 0.7,
                "expected_bootstrap_capable": True
            },
            {
                "name": "Non-Azure Environment",
                "mock_env": {},
                "mock_requests": [],
                "expected_confidence": 0.0,
                "expected_bootstrap_capable": False
            }
        ]
        
        success_count = 0
        
        for scenario in test_scenarios:
            with patch.dict(os.environ, scenario["mock_env"], clear=True):
                with patch('requests.get') as mock_requests_get:
                    # Setup request mocking
                    def mock_request_func(url, headers=None, timeout=None):
                        for req in scenario["mock_requests"]:
                            if req["url"] == url:
                                mock_response = MagicMock()
                                mock_response.status_code = req["status"]
                                mock_response.json.return_value = req["response"]
                                return mock_response
                        # Default to connection error
                        raise ConnectionError("Mocked connection error")
                    
                    mock_requests_get.side_effect = mock_request_func
                    
                    # Test detection
                    env_info = self.detector._detect_azure()
                    
                    if scenario["expected_confidence"] > 0:
                        if env_info and env_info.environment_type == EnvironmentType.AZURE:
                            if (abs(env_info.confidence - scenario["expected_confidence"]) < 0.1 and
                                env_info.bootstrap_capable == scenario["expected_bootstrap_capable"]):
                                logger.info(f"✓ {scenario['name']}: Detection successful")
                                success_count += 1
                            else:
                                logger.error(f"✗ {scenario['name']}: Confidence or capability mismatch")
                        else:
                            logger.error(f"✗ {scenario['name']}: Failed to detect Azure")
                    else:
                        if env_info is None:
                            logger.info(f"✓ {scenario['name']}: Correctly detected no Azure")
                            success_count += 1
                        else:
                            logger.error(f"✗ {scenario['name']}: False positive detection")
        
        logger.info(f"Azure detection: {success_count}/{len(test_scenarios)} tests passed")
        return success_count == len(test_scenarios)
    
    def test_docker_detection(self):
        """Test Docker container detection."""
        logger.info("=== Testing Docker Environment Detection ===")
        
        test_scenarios = [
            {
                "name": "Docker Container with .dockerenv",
                "mock_files": {
                    "/.dockerenv": ""
                },
                "mock_file_reads": {
                    "/proc/1/cgroup": "1:name=systemd:/docker/abcdef123456"
                },
                "mock_env": {"HOSTNAME": "abcdef123456"},
                "expected_confidence": 1.0,
                "expected_bootstrap_capable": True
            },
            {
                "name": "Docker Container without .dockerenv",
                "mock_files": {},
                "mock_file_reads": {
                    "/proc/1/cgroup": "1:name=systemd:/docker/fedcba654321"
                },
                "mock_env": {"HOSTNAME": "container123"},
                "expected_confidence": 0.4,
                "expected_bootstrap_capable": False
            },
            {
                "name": "Non-Docker Environment",
                "mock_files": {},
                "mock_file_reads": {
                    "/proc/1/cgroup": "1:name=systemd:/"
                },
                "mock_env": {"HOSTNAME": "my-laptop"},
                "expected_confidence": 0.0,
                "expected_bootstrap_capable": False
            }
        ]
        
        success_count = 0
        
        for scenario in test_scenarios:
            with patch('os.path.exists') as mock_exists, \
                 patch.dict(os.environ, scenario["mock_env"], clear=True):
                
                # Mock file existence
                def mock_exists_func(path):
                    return path in scenario["mock_files"]
                mock_exists.side_effect = mock_exists_func
                
                # Mock file reading
                with patch('builtins.open', create=True) as mock_open:
                    def mock_open_func(path, mode='r'):
                        if path in scenario["mock_file_reads"]:
                            mock_file = MagicMock()
                            mock_file.__enter__.return_value.read.return_value = scenario["mock_file_reads"][path]
                            return mock_file
                        elif path in scenario["mock_files"]:
                            mock_file = MagicMock()
                            mock_file.__enter__.return_value.read.return_value = scenario["mock_files"][path]
                            return mock_file
                        raise FileNotFoundError()
                    
                    mock_open.side_effect = mock_open_func
                    
                    # Test detection
                    env_info = self.detector._detect_docker()
                    
                    if scenario["expected_confidence"] > 0:
                        if env_info and env_info.environment_type == EnvironmentType.DOCKER:
                            if (abs(env_info.confidence - scenario["expected_confidence"]) < 0.1 and
                                env_info.bootstrap_capable == scenario["expected_bootstrap_capable"]):
                                logger.info(f"✓ {scenario['name']}: Detection successful")
                                success_count += 1
                            else:
                                logger.error(f"✗ {scenario['name']}: Confidence or capability mismatch")
                        else:
                            logger.error(f"✗ {scenario['name']}: Failed to detect Docker")
                    else:
                        if env_info is None:
                            logger.info(f"✓ {scenario['name']}: Correctly detected no Docker")
                            success_count += 1
                        else:
                            logger.error(f"✗ {scenario['name']}: False positive detection")
        
        logger.info(f"Docker detection: {success_count}/{len(test_scenarios)} tests passed")
        return success_count == len(test_scenarios)
    
    def test_intelligent_provider_ordering(self):
        """Test intelligent provider ordering based on environment detection."""
        logger.info("=== Testing Intelligent Provider Ordering ===")
        
        test_scenarios = [
            {
                "name": "Kubernetes Environment",
                "environment_setup": {
                    "files": {"/var/run/secrets/kubernetes.io/serviceaccount/token": "token"},
                    "env": {"KUBERNETES_SERVICE_HOST": "10.96.0.1"}
                },
                "expected_first_provider": "kubernetes"
            },
            {
                "name": "AWS Environment", 
                "environment_setup": {
                    "files": {},
                    "env": {"AWS_REGION": "us-east-1", "AWS_EXECUTION_ENV": "EC2-Instance"}
                },
                "expected_first_provider": "aws"
            },
            {
                "name": "Local Environment",
                "environment_setup": {
                    "files": {},
                    "env": {}
                },
                "expected_first_provider": "keyring"  # Should fall back to keyring
            }
        ]
        
        success_count = 0
        
        for scenario in test_scenarios:
            # Setup environment
            with patch('os.path.exists') as mock_exists, \
                 patch.dict(os.environ, scenario["environment_setup"]["env"], clear=True):
                
                # Mock file existence
                def mock_exists_func(path):
                    return path in scenario["environment_setup"]["files"]
                mock_exists.side_effect = mock_exists_func
                
                with patch('builtins.open', create=True) as mock_open:
                    def mock_open_func(path, mode='r'):
                        if path in scenario["environment_setup"]["files"]:
                            mock_file = MagicMock()
                            mock_file.__enter__.return_value.read.return_value = scenario["environment_setup"]["files"][path]
                            return mock_file
                        raise FileNotFoundError()
                    
                    mock_open.side_effect = mock_open_func
                    
                    # Mock requests for AWS/Azure detection
                    with patch('requests.get') as mock_requests:
                        mock_requests.side_effect = ConnectionError("Mocked error")
                        
                        # Create identity manager to test provider ordering
                        mock_client = MagicMock()
                        identity_manager = IdentityManager(api_client=mock_client, silent_mode=True)
                        
                        # Check if first provider matches expectation
                        if identity_manager.providers:
                            first_provider_name = identity_manager.providers[0].name
                            if first_provider_name == scenario["expected_first_provider"]:
                                logger.info(f"✓ {scenario['name']}: First provider is {first_provider_name} as expected")
                                success_count += 1
                            else:
                                logger.error(f"✗ {scenario['name']}: Expected {scenario['expected_first_provider']}, got {first_provider_name}")
                        else:
                            logger.error(f"✗ {scenario['name']}: No providers found")
        
        logger.info(f"Provider ordering: {success_count}/{len(test_scenarios)} tests passed")
        return success_count == len(test_scenarios)
    
    def test_environment_summary(self):
        """Test environment summary generation."""
        logger.info("=== Testing Environment Summary ===")
        
        try:
            # Test in current environment
            summary = environment_detector.get_environment_summary()
            
            required_fields = [
                "detected_environment",
                "confidence", 
                "bootstrap_capable",
                "recommended_method",
                "metadata",
                "detection_details"
            ]
            
            missing_fields = [field for field in required_fields if field not in summary]
            
            if not missing_fields:
                logger.info("✓ Environment summary has all required fields")
                logger.info(f"  Environment: {summary['detected_environment']}")
                logger.info(f"  Confidence: {summary['confidence']:.2f}")
                logger.info(f"  Bootstrap capable: {summary['bootstrap_capable']}")
                logger.info(f"  Recommended method: {summary['recommended_method']}")
                return True
            else:
                logger.error(f"✗ Environment summary missing fields: {missing_fields}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Environment summary generation failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all environment detection tests."""
        logger.info("🔍 Starting Enhanced Environment Detection Tests")
        logger.info("=" * 60)
        
        test_results = []
        
        try:
            # Run all test methods
            test_results.append(("Kubernetes Detection", self.test_kubernetes_detection()))
            test_results.append(("AWS Detection", self.test_aws_detection()))
            test_results.append(("Azure Detection", self.test_azure_detection()))
            test_results.append(("Docker Detection", self.test_docker_detection()))
            test_results.append(("Provider Ordering", self.test_intelligent_provider_ordering()))
            test_results.append(("Environment Summary", self.test_environment_summary()))
            
            # Summary
            passed = sum(1 for _, result in test_results if result)
            total = len(test_results)
            
            logger.info("=" * 60)
            logger.info(f"Environment Detection Tests: {passed}/{total} passed")
            logger.info("")
            
            for test_name, result in test_results:
                status = "✅ PASS" if result else "❌ FAIL"
                logger.info(f"  {status} {test_name}")
            
            if passed == total:
                logger.info("")
                logger.info("🎉 All environment detection tests passed!")
                logger.info("")
                logger.info("Enhanced environment detection provides:")
                logger.info("  🔍 Intelligent platform detection")
                logger.info("  📊 Confidence scoring for reliability")
                logger.info("  🎯 Automatic bootstrap method selection") 
                logger.info("  🔄 Smart provider ordering")
                logger.info("  🌐 Multi-platform support (K8s, AWS, Azure, Docker)")
                logger.info("  📈 Detailed environment metadata")
                logger.info("  🚀 Production-ready decision logic")
            else:
                logger.error(f"❌ {total - passed} tests failed. Please review the implementation.")
                
        except Exception as e:
            logger.error(f"Test execution failed: {e}")

if __name__ == "__main__":
    tester = EnvironmentDetectionTester()
    tester.run_all_tests() 