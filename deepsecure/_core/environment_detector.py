"""
Environment detection utilities for automatic bootstrap method selection.
Provides intelligent detection of runtime environments and platform-specific features.
"""
import os
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EnvironmentType(Enum):
    """Types of detected environments."""
    KUBERNETES = "kubernetes"
    AWS = "aws"
    AZURE = "azure"
    DOCKER = "docker"
    LOCAL = "local"
    UNKNOWN = "unknown"


@dataclass
class EnvironmentInfo:
    """Information about the detected environment."""
    environment_type: EnvironmentType
    confidence: float  # 0.0 to 1.0
    metadata: Dict[str, str]
    bootstrap_capable: bool
    detection_details: List[str]


class EnvironmentDetector:
    """
    Intelligent environment detector for automatic bootstrap method selection.
    Uses multiple signals to detect the runtime environment with confidence scoring.
    """
    
    def __init__(self):
        self.detection_methods = [
            self._detect_kubernetes,
            self._detect_aws,
            self._detect_azure,
            self._detect_docker,
            self._detect_local
        ]
    
    def detect_environment(self) -> EnvironmentInfo:
        """
        Detect the current runtime environment with confidence scoring.
        
        Returns:
            EnvironmentInfo with the most likely environment and metadata
        """
        logger.info("Starting environment detection...")
        
        # Run all detection methods
        detections = []
        for method in self.detection_methods:
            try:
                env_info = method()
                if env_info:
                    detections.append(env_info)
                    logger.debug(f"Detection method {method.__name__} found: {env_info.environment_type} (confidence: {env_info.confidence})")
            except Exception as e:
                logger.warning(f"Detection method {method.__name__} failed: {e}")
        
        # Sort by confidence (highest first)
        detections.sort(key=lambda x: x.confidence, reverse=True)
        
        if detections:
            best_detection = detections[0]
            logger.info(f"Environment detected: {best_detection.environment_type} (confidence: {best_detection.confidence:.2f})")
            return best_detection
        else:
            # Fallback to unknown environment
            logger.warning("No environment detected, falling back to unknown")
            return EnvironmentInfo(
                environment_type=EnvironmentType.UNKNOWN,
                confidence=0.0,
                metadata={},
                bootstrap_capable=False,
                detection_details=["No environment signals detected"]
            )
    
    def _detect_kubernetes(self) -> Optional[EnvironmentInfo]:
        """Detect Kubernetes environment."""
        detection_details = []
        metadata = {}
        confidence = 0.0
        
        # Check for service account token
        token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        if os.path.exists(token_path):
            confidence += 0.6
            detection_details.append("Kubernetes service account token found")
            metadata["token_path"] = token_path
        
        # Check for namespace file
        namespace_path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        if os.path.exists(namespace_path):
            confidence += 0.2
            detection_details.append("Kubernetes namespace file found")
            try:
                with open(namespace_path, 'r') as f:
                    namespace = f.read().strip()
                    metadata["namespace"] = namespace
            except:
                pass
        
        # Check for Kubernetes environment variables
        k8s_env_vars = [
            "KUBERNETES_SERVICE_HOST",
            "KUBERNETES_SERVICE_PORT",
            "KUBERNETES_PORT"
        ]
        
        for env_var in k8s_env_vars:
            if env_var in os.environ:
                confidence += 0.1
                detection_details.append(f"Kubernetes environment variable {env_var} found")
                metadata[env_var.lower()] = os.environ[env_var]
        
        # Check for kubectl config (lower confidence as it might be mounted)
        if os.path.exists("/root/.kube/config") or os.path.exists(os.path.expanduser("~/.kube/config")):
            confidence += 0.05
            detection_details.append("kubectl config found")
        
        if confidence > 0.3:  # Minimum threshold for Kubernetes detection
            return EnvironmentInfo(
                environment_type=EnvironmentType.KUBERNETES,
                confidence=min(confidence, 1.0),
                metadata=metadata,
                bootstrap_capable=confidence > 0.5,  # Need token for bootstrap
                detection_details=detection_details
            )
        
        return None
    
    def _detect_aws(self) -> Optional[EnvironmentInfo]:
        """Detect AWS environment."""
        detection_details = []
        metadata = {}
        confidence = 0.0
        
        # Check for AWS environment variables
        aws_env_vars = {
            "AWS_REGION": 0.3,
            "AWS_DEFAULT_REGION": 0.2,
            "AWS_EXECUTION_ENV": 0.4,
            "AWS_LAMBDA_FUNCTION_NAME": 0.5,
            "ECS_CONTAINER_METADATA_URI": 0.4,
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": 0.3
        }
        
        for env_var, weight in aws_env_vars.items():
            if env_var in os.environ:
                confidence += weight
                detection_details.append(f"AWS environment variable {env_var} found")
                metadata[env_var.lower()] = os.environ[env_var]
        
        # Check for EC2 instance metadata service
        try:
            import requests
            response = requests.get(
                "http://169.254.169.254/latest/meta-data/instance-id",
                timeout=2
            )
            if response.status_code == 200:
                confidence += 0.5
                detection_details.append("EC2 instance metadata accessible")
                metadata["instance_id"] = response.text
        except:
            pass
        
        # Check for AWS credentials files
        aws_creds_path = os.path.expanduser("~/.aws/credentials")
        if os.path.exists(aws_creds_path):
            confidence += 0.1
            detection_details.append("AWS credentials file found")
        
        # Check for common AWS IAM role indicators
        if "AWS_ROLE_ARN" in os.environ:
            confidence += 0.2
            detection_details.append("AWS role ARN found")
            metadata["role_arn"] = os.environ["AWS_ROLE_ARN"]
        
        if confidence > 0.2:  # Minimum threshold for AWS detection
            return EnvironmentInfo(
                environment_type=EnvironmentType.AWS,
                confidence=min(confidence, 1.0),
                metadata=metadata,
                bootstrap_capable=confidence > 0.4,  # Need IAM role or instance for bootstrap
                detection_details=detection_details
            )
        
        return None
    
    def _detect_azure(self) -> Optional[EnvironmentInfo]:
        """Detect Azure environment."""
        detection_details = []
        metadata = {}
        confidence = 0.0
        
        # Check for Azure environment variables
        azure_env_vars = {
            "AZURE_TENANT_ID": 0.3,
            "AZURE_CLIENT_ID": 0.3,
            "AZURE_CLIENT_SECRET": 0.2,
            "AZURE_SUBSCRIPTION_ID": 0.2,
            "MSI_ENDPOINT": 0.4,
            "IDENTITY_ENDPOINT": 0.4,
            "IDENTITY_HEADER": 0.3
        }
        
        for env_var, weight in azure_env_vars.items():
            if env_var in os.environ:
                confidence += weight
                detection_details.append(f"Azure environment variable {env_var} found")
                metadata[env_var.lower()] = os.environ[env_var]
        
        # Check for Azure Instance Metadata Service (IMDS)
        try:
            import requests
            response = requests.get(
                "http://169.254.169.254/metadata/instance?api-version=2021-02-01",
                headers={"Metadata": "true"},
                timeout=2
            )
            if response.status_code == 200:
                confidence += 0.6
                detection_details.append("Azure IMDS accessible")
                try:
                    instance_data = response.json()
                    if "compute" in instance_data:
                        compute = instance_data["compute"]
                        metadata["vm_id"] = compute.get("vmId", "")
                        metadata["resource_group"] = compute.get("resourceGroupName", "")
                        metadata["subscription_id"] = compute.get("subscriptionId", "")
                except:
                    pass
        except:
            pass
        
        # Check for Azure CLI configuration
        azure_config_path = os.path.expanduser("~/.azure/config")
        if os.path.exists(azure_config_path):
            confidence += 0.1
            detection_details.append("Azure CLI config found")
        
        if confidence > 0.2:  # Minimum threshold for Azure detection
            return EnvironmentInfo(
                environment_type=EnvironmentType.AZURE,
                confidence=min(confidence, 1.0),
                metadata=metadata,
                bootstrap_capable=confidence > 0.4,  # Need IMDS for bootstrap
                detection_details=detection_details
            )
        
        return None
    
    def _detect_docker(self) -> Optional[EnvironmentInfo]:
        """Detect Docker container environment."""
        detection_details = []
        metadata = {}
        confidence = 0.0
        
        # Check for .dockerenv file (most reliable indicator)
        if os.path.exists("/.dockerenv"):
            confidence += 0.6
            detection_details.append("Docker .dockerenv file found")
        
        # Check cgroup for container indicators
        try:
            with open("/proc/1/cgroup", "r") as f:
                cgroup_content = f.read()
                if "docker" in cgroup_content:
                    confidence += 0.4
                    detection_details.append("Docker cgroup detected")
                elif "containerd" in cgroup_content:
                    confidence += 0.3
                    detection_details.append("containerd cgroup detected")
                elif any(indicator in cgroup_content for indicator in ["kubepods", "pod"]):
                    confidence += 0.2
                    detection_details.append("Kubernetes pod cgroup detected")
        except:
            pass
        
        # Check for container-specific environment variables
        container_env_vars = {
            "HOSTNAME": 0.1,  # Often set to container ID
            "PATH": 0.05,     # Often minimal in containers
        }
        
        for env_var, weight in container_env_vars.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                metadata[env_var.lower()] = value
                
                # HOSTNAME often looks like container ID (12 hex chars)
                if env_var == "HOSTNAME" and len(value) == 12 and all(c in "0123456789abcdef" for c in value):
                    confidence += 0.2
                    detection_details.append("Container-like hostname detected")
        
        # Check for init process (PID 1 is often not systemd in containers)
        try:
            with open("/proc/1/comm", "r") as f:
                init_process = f.read().strip()
                if init_process not in ["systemd", "init"]:
                    confidence += 0.1
                    detection_details.append(f"Non-standard init process: {init_process}")
                    metadata["init_process"] = init_process
        except:
            pass
        
        # Check for minimal filesystem (containers often have fewer files in /usr/bin)
        try:
            usr_bin_count = len(os.listdir("/usr/bin"))
            if usr_bin_count < 100:  # Arbitrary threshold for minimal system
                confidence += 0.1
                detection_details.append("Minimal filesystem detected")
                metadata["usr_bin_count"] = str(usr_bin_count)
        except:
            pass
        
        if confidence > 0.2:  # Minimum threshold for Docker detection
            return EnvironmentInfo(
                environment_type=EnvironmentType.DOCKER,
                confidence=min(confidence, 1.0),
                metadata=metadata,
                bootstrap_capable=confidence > 0.4,  # Need container metadata for bootstrap
                detection_details=detection_details
            )
        
        return None
    
    def _detect_local(self) -> Optional[EnvironmentInfo]:
        """Detect local development environment."""
        detection_details = []
        metadata = {}
        confidence = 0.5  # Default assumption for non-containerized environments
        
        # Check for typical development environment indicators
        dev_indicators = [
            ("/home", "Home directory present"),
            ("/usr/local", "Local installation directory present"),
            ("/opt", "Optional software directory present")
        ]
        
        for path, description in dev_indicators:
            if os.path.exists(path):
                confidence += 0.1
                detection_details.append(description)
        
        # Check for development tools
        dev_tools = [
            "/usr/bin/git",
            "/usr/bin/python3", 
            "/usr/bin/node",
            "/usr/bin/docker"
        ]
        
        found_tools = []
        for tool in dev_tools:
            if os.path.exists(tool):
                found_tools.append(os.path.basename(tool))
        
        if found_tools:
            confidence += 0.2
            detection_details.append(f"Development tools found: {', '.join(found_tools)}")
            metadata["dev_tools"] = ",".join(found_tools)
        
        # Check for interactive shell
        if os.isatty(0):  # stdin is a terminal
            confidence += 0.1
            detection_details.append("Interactive terminal detected")
        
        # Check for display environment (GUI)
        if "DISPLAY" in os.environ:
            confidence += 0.1
            detection_details.append("Display environment detected")
            metadata["display"] = os.environ["DISPLAY"]
        
        # Lower confidence if we detect cloud/container indicators
        cloud_indicators = [
            "AWS_REGION",
            "AZURE_TENANT_ID", 
            "KUBERNETES_SERVICE_HOST",
            "/.dockerenv"
        ]
        
        for indicator in cloud_indicators:
            if (indicator.startswith("/") and os.path.exists(indicator)) or \
               (not indicator.startswith("/") and indicator in os.environ):
                confidence -= 0.3
                detection_details.append(f"Cloud indicator detected: {indicator}")
        
        return EnvironmentInfo(
            environment_type=EnvironmentType.LOCAL,
            confidence=max(confidence, 0.1),  # Minimum confidence
            metadata=metadata,
            bootstrap_capable=False,  # Local environments can't bootstrap automatically
            detection_details=detection_details
        )
    
    def get_recommended_bootstrap_method(self) -> Tuple[Optional[str], EnvironmentInfo]:
        """
        Get the recommended bootstrap method based on environment detection.
        
        Returns:
            Tuple of (recommended_method, environment_info)
        """
        env_info = self.detect_environment()
        
        if not env_info.bootstrap_capable:
            return None, env_info
        
        method_mapping = {
            EnvironmentType.KUBERNETES: "kubernetes",
            EnvironmentType.AWS: "aws", 
            EnvironmentType.AZURE: "azure",
            EnvironmentType.DOCKER: "docker"
        }
        
        recommended_method = method_mapping.get(env_info.environment_type)
        return recommended_method, env_info
    
    def get_environment_summary(self) -> Dict[str, any]:
        """Get a summary of the environment detection results."""
        env_info = self.detect_environment()
        recommended_method, _ = self.get_recommended_bootstrap_method()
        
        return {
            "detected_environment": env_info.environment_type.value,
            "confidence": env_info.confidence,
            "bootstrap_capable": env_info.bootstrap_capable,
            "recommended_method": recommended_method,
            "metadata": env_info.metadata,
            "detection_details": env_info.detection_details
        }


# Global environment detector instance
environment_detector = EnvironmentDetector() 