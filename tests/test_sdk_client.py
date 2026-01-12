# tests/test_client.py
"""
Tests for DeepSecure client initialization and identity provider detection.

NOTE: These tests require backend services for full integration testing.
"""
import pytest
import os
import httpx
from unittest.mock import patch, MagicMock

from deepsecure.client import DeepSecure
from deepsecure._core.identity_provider import (
    KubernetesIdentityProvider,
    AwsIdentityProvider,
    AzureIdentityProvider,
    DockerIdentityProvider,
    KeyringIdentityProvider,
)


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


def backend_is_running() -> bool:
    """Check if backend services are running."""
    try:
        httpx.get("http://localhost:8000/health", timeout=2)
        return True
    except Exception:
        return False


@pytest.fixture(scope="module", autouse=True)
def setup_env_and_check_backend():
    """Set up environment variables and skip if backend not running."""
    # Set required environment variables
    os.environ.setdefault("DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://localhost:8000")
    os.environ.setdefault("DEEPSECURE_DEEPTRAIL_GATEWAY_URL", "http://localhost:8002")
    
    if not backend_is_running():
        pytest.skip("Backend services not running - skipping SDK client tests")
    
    yield


class TestDeepSecureClientInitialization:
    """
    Tests the initialization of the main DeepSecure client, specifically its
    ability to auto-detect the environment and construct the correct chain
    of identity providers.
    """

    @patch("os.path.exists")
    def test_initialization_in_kubernetes_environment(self, mock_path_exists):
        """
        GIVEN the Kubernetes service account token file exists
        WHEN the DeepSecure client is initialized
        THEN the IdentityManager's provider chain should contain all providers,
        with KubernetesIdentityProvider first (it will be the one that activates).
        """
        # Arrange
        # Simulate being in Kubernetes by making the token path exist
        mock_path_exists.return_value = True

        # Act
        client = DeepSecure()

        # Assert
        assert client.identity_manager is not None
        providers = client.identity_manager.providers
        # Current architecture: all 5 providers are always created (K8s, AWS, Azure, Docker, Keyring)
        assert len(providers) == 5
        # K8s should be first in the chain
        assert isinstance(providers[0], KubernetesIdentityProvider)
        # Keyring should be the last fallback
        assert isinstance(providers[-1], KeyringIdentityProvider)

    @patch("os.path.exists", return_value=False)
    @patch("os.environ.get")
    def test_initialization_in_aws_environment(self, mock_environ_get, mock_path_exists):
        """
        GIVEN the K8s token does NOT exist, but AWS env vars are set
        WHEN the DeepSecure client is initialized
        THEN the IdentityManager's provider chain should contain all providers,
        with AwsIdentityProvider second (after K8s which won't activate).
        """
        # Arrange
        # Simulate being in AWS by providing a value for the env var
        mock_environ_get.return_value = "dummy-aws-iam-role"

        # Act
        client = DeepSecure()

        # Assert
        assert client.identity_manager is not None
        providers = client.identity_manager.providers
        # Current architecture: all 5 providers are always created
        assert len(providers) == 5
        # AWS is second in the chain (after K8s)
        assert isinstance(providers[1], AwsIdentityProvider)
        # Keyring should be the last fallback
        assert isinstance(providers[-1], KeyringIdentityProvider)


    @patch("os.path.exists", return_value=False)
    def test_initialization_in_local_environment(self, mock_path_exists, monkeypatch):
        """
        GIVEN no K8s token exists and no AWS env vars are set
        WHEN the DeepSecure client is initialized
        THEN the IdentityManager's provider chain should contain all providers,
        with KeyringIdentityProvider as the fallback (and only one that will activate).
        """
        # Arrange - use monkeypatch to selectively set env vars
        # This avoids breaking Rich console which needs TERM to be set
        monkeypatch.delenv("AWS_ROLE_ARN", raising=False)
        monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
        
        # Act
        client = DeepSecure()

        # Assert
        assert client.identity_manager is not None
        providers = client.identity_manager.providers
        # Current architecture: all 5 providers are always created
        assert len(providers) == 5
        # KeyringIdentityProvider should be the last fallback
        assert isinstance(providers[-1], KeyringIdentityProvider)

    def test_identity_passed_directly(self):
        """
        GIVEN an AgentIdentity object is passed directly to the client
        WHEN the DeepSecure client is initialized
        THEN this identity is set on the client directly.
        """
        # Arrange
        mock_identity = MagicMock()
        
        # Act
        client = DeepSecure(identity=mock_identity)
        
        # Assert
        assert client.identity == mock_identity
        # identity_manager is still created (always created in current arch)
        assert client.identity_manager is not None 