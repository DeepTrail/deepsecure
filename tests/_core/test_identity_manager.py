# tests/_core/test_identity_manager.py
import pytest
from unittest.mock import patch, MagicMock

from deepsecure._core.identity_manager import IdentityManager
from deepsecure._core.identity_provider import (
    AgentIdentity,
    KubernetesIdentityProvider,
    AwsIdentityProvider,
    KeyringIdentityProvider,
)

# A sample agent identity for mocking
MOCK_AGENT_IDENTITY = AgentIdentity(
    agent_id="agent-mock-123",
    private_key_b64="mock_private_key",
    public_key_b64="mock_public_key",
    provider_name="mock_provider",
)

@pytest.fixture
def mock_k8s_provider():
    """Fixture for a mocked KubernetesIdentityProvider."""
    return MagicMock(spec=KubernetesIdentityProvider)

@pytest.fixture
def mock_aws_provider():
    """Fixture for a mocked AwsIdentityProvider."""
    return MagicMock(spec=AwsIdentityProvider)

@pytest.fixture
def mock_keyring_provider():
    """Fixture for a mocked KeyringIdentityProvider."""
    return MagicMock(spec=KeyringIdentityProvider)


class TestChainedIdentityManager:
    """
    Test suite for the new IdentityManager that uses a chain of providers.
    """

    def test_get_identity_kubernetes_provider_success(
        self, mock_k8s_provider, mock_aws_provider, mock_keyring_provider
    ):
        """
        GIVEN an identity manager with a K8s, AWS, and Keyring provider
        WHEN the K8s provider finds an identity
        THEN the K8s provider's identity is returned
        AND the other providers are not called.
        """
        # Arrange
        mock_api_client = MagicMock()
        mock_k8s_provider.get_identity.return_value = MOCK_AGENT_IDENTITY
        providers = [mock_k8s_provider, mock_aws_provider, mock_keyring_provider]
        manager = IdentityManager(api_client=mock_api_client, providers=providers, silent_mode=True)

        # Act
        result = manager.get_identity("any-agent-id")

        # Assert
        assert result == MOCK_AGENT_IDENTITY
        mock_k8s_provider.get_identity.assert_called_once_with("any-agent-id")
        mock_aws_provider.get_identity.assert_not_called()
        mock_keyring_provider.get_identity.assert_not_called()

    def test_get_identity_aws_provider_success(self, mock_k8s_provider, mock_aws_provider, mock_keyring_provider):
        """
        Test that the IdentityManager correctly uses the AWS provider when Kubernetes fails.
        """
        # Arrange
        mock_api_client = MagicMock()
        mock_k8s_provider.get_identity.return_value = None
        mock_aws_provider.get_identity.return_value = MOCK_AGENT_IDENTITY
        providers = [mock_k8s_provider, mock_aws_provider, mock_keyring_provider]
        manager = IdentityManager(api_client=mock_api_client, providers=providers, silent_mode=True)

        # Act
        result = manager.get_identity("any-agent-id")

        # Assert
        assert result == MOCK_AGENT_IDENTITY
        mock_k8s_provider.get_identity.assert_called_once()
        mock_aws_provider.get_identity.assert_called_once()
        mock_keyring_provider.get_identity.assert_not_called()

    def test_get_identity_keyring_provider_success(self, mock_k8s_provider, mock_aws_provider, mock_keyring_provider):
        """
        Test that the IdentityManager falls back to keyring provider when cloud providers fail.
        """
        # Arrange
        mock_api_client = MagicMock()
        mock_k8s_provider.get_identity.return_value = None
        mock_aws_provider.get_identity.return_value = None
        mock_keyring_provider.get_identity.return_value = MOCK_AGENT_IDENTITY
        providers = [mock_k8s_provider, mock_aws_provider, mock_keyring_provider]
        manager = IdentityManager(api_client=mock_api_client, providers=providers, silent_mode=True)

        # Act
        result = manager.get_identity("any-agent-id")

        # Assert
        assert result == MOCK_AGENT_IDENTITY
        mock_k8s_provider.get_identity.assert_called_once()
        mock_aws_provider.get_identity.assert_called_once()
        mock_keyring_provider.get_identity.assert_called_once()

    def test_get_identity_no_providers_match(self, mock_k8s_provider, mock_aws_provider, mock_keyring_provider):
        """
        Test that the IdentityManager returns None when no providers can provide an identity.
        """
        # Arrange
        mock_api_client = MagicMock()
        mock_k8s_provider.get_identity.return_value = None
        mock_aws_provider.get_identity.return_value = None
        mock_keyring_provider.get_identity.return_value = None
        providers = [mock_k8s_provider, mock_aws_provider, mock_keyring_provider]
        manager = IdentityManager(api_client=mock_api_client, providers=providers, silent_mode=True)

        # Act
        result = manager.get_identity("any-agent-id")

        # Assert
        assert result is None
        mock_k8s_provider.get_identity.assert_called_once()
        mock_aws_provider.get_identity.assert_called_once()
        mock_keyring_provider.get_identity.assert_called_once()

    def test_get_identity_empty_providers_list(self):
        """
        Test that the IdentityManager handles an empty providers list gracefully.
        """
        # Arrange
        mock_api_client = MagicMock()
        manager = IdentityManager(api_client=mock_api_client, providers=[], silent_mode=True)

        # Act
        result = manager.get_identity("any-agent-id")

        # Assert
        assert result is None 