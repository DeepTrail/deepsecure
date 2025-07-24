# tests/test_client.py
import pytest
from unittest.mock import patch, MagicMock

from deepsecure.client import DeepSecure
from deepsecure._core.identity_provider import (
    KubernetesIdentityProvider,
    AwsIdentityProvider,
    KeyringIdentityProvider,
)

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
        THEN the IdentityManager's provider chain should contain KubernetesIdentityProvider first.
        """
        # Arrange
        # Simulate being in Kubernetes by making the token path exist
        mock_path_exists.return_value = True

        # Act
        client = DeepSecure()

        # Assert
        assert client.identity_manager is not None
        providers = client.identity_manager.providers
        assert len(providers) == 2  # K8s + Keyring
        assert isinstance(providers[0], KubernetesIdentityProvider)
        assert isinstance(providers[1], KeyringIdentityProvider)
        # Verify the path check was for the correct K8s token file
        mock_path_exists.assert_called_with(KubernetesIdentityProvider.K8S_TOKEN_PATH)

    @patch("os.path.exists", return_value=False)
    @patch("os.environ.get")
    def test_initialization_in_aws_environment(self, mock_environ_get, mock_path_exists):
        """
        GIVEN the K8s token does NOT exist, but AWS env vars are set
        WHEN the DeepSecure client is initialized
        THEN the IdentityManager's provider chain should contain AwsIdentityProvider first.
        """
        # Arrange
        # Simulate being in AWS by providing a value for the env var
        mock_environ_get.return_value = "dummy-aws-iam-role"

        # Act
        client = DeepSecure()

        # Assert
        assert client.identity_manager is not None
        providers = client.identity_manager.providers
        assert len(providers) == 2  # AWS + Keyring
        assert isinstance(providers[0], AwsIdentityProvider)
        assert isinstance(providers[1], KeyringIdentityProvider)
        # Verify the env var check was for the correct AWS variable
        mock_environ_get.assert_called_with("AWS_ROLE_ARN")


    @patch("os.path.exists", return_value=False)
    @patch("os.environ.get", return_value=None)
    def test_initialization_in_local_environment(self, mock_environ_get, mock_path_exists):
        """
        GIVEN no K8s token exists and no AWS env vars are set
        WHEN the DeepSecure client is initialized
        THEN the IdentityManager's provider chain should ONLY contain the KeyringIdentityProvider.
        """
        # Arrange (all mocks are set to return False/None)
        
        # Act
        client = DeepSecure()

        # Assert
        assert client.identity_manager is not None
        providers = client.identity_manager.providers
        assert len(providers) == 1
        assert isinstance(providers[0], KeyringIdentityProvider)

    def test_identity_passed_directly(self):
        """
        GIVEN an AgentIdentity object is passed directly to the client
        WHEN the DeepSecure client is initialized
        THEN this identity is set on the client and no providers are created.
        """
        # Arrange
        mock_identity = MagicMock()
        
        # Act
        client = DeepSecure(identity=mock_identity)
        
        # Assert
        assert client.identity == mock_identity
        assert client.identity_manager is None # No providers needed 