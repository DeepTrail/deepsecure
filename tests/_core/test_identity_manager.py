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
        mock_k8s_provider.get_identity.return_value = MOCK_AGENT_IDENTITY
        providers = [mock_k8s_provider, mock_aws_provider, mock_keyring_provider]
        manager = IdentityManager(providers=providers, silent_mode=True)

        # Act
        result = manager.get_identity("any-agent-id")

        # Assert
        assert result == MOCK_AGENT_IDENTITY
        mock_k8s_provider.get_identity.assert_called_once_with("any-agent-id")
        mock_aws_provider.get_identity.assert_not_called()
        mock_keyring_provider.get_identity.assert_not_called()

    def test_get_identity_aws_provider_success(
        self, mock_k8s_provider, mock_aws_provider, mock_keyring_provider
    ):
        """
        GIVEN an identity manager with a K8s, AWS, and Keyring provider
        WHEN the K8s provider fails but the AWS provider finds an identity
        THEN the AWS provider's identity is returned
        AND the keyring provider is not called.
        """
        # Arrange
        mock_k8s_provider.get_identity.return_value = None
        mock_aws_provider.get_identity.return_value = MOCK_AGENT_IDENTITY
        providers = [mock_k8s_provider, mock_aws_provider, mock_keyring_provider]
        manager = IdentityManager(providers=providers, silent_mode=True)

        # Act
        result = manager.get_identity("any-agent-id")

        # Assert
        assert result == MOCK_AGENT_IDENTITY
        mock_k8s_provider.get_identity.assert_called_once_with("any-agent-id")
        mock_aws_provider.get_identity.assert_called_once_with("any-agent-id")
        mock_keyring_provider.get_identity.assert_not_called()

    def test_get_identity_keyring_fallback_success(
        self, mock_k8s_provider, mock_aws_provider, mock_keyring_provider
    ):
        """
        GIVEN an identity manager with a K8s, AWS, and Keyring provider
        WHEN the K8s and AWS providers fail but the Keyring provider succeeds
        THEN the Keyring provider's identity is returned.
        """
        # Arrange
        mock_k8s_provider.get_identity.return_value = None
        mock_aws_provider.get_identity.return_value = None
        mock_keyring_provider.get_identity.return_value = MOCK_AGENT_IDENTITY
        providers = [mock_k8s_provider, mock_aws_provider, mock_keyring_provider]
        manager = IdentityManager(providers=providers, silent_mode=True)

        # Act
        result = manager.get_identity("any-agent-id")

        # Assert
        assert result == MOCK_AGENT_IDENTITY
        mock_k8s_provider.get_identity.assert_called_once_with("any-agent-id")
        mock_aws_provider.get_identity.assert_called_once_with("any-agent-id")
        mock_keyring_provider.get_identity.assert_called_once_with("any-agent-id")

    def test_get_identity_no_providers_succeed(
        self, mock_k8s_provider, mock_aws_provider, mock_keyring_provider
    ):
        """
        GIVEN an identity manager with a K8s, AWS, and Keyring provider
        WHEN all providers fail to find an identity
        THEN None is returned.
        """
        # Arrange
        mock_k8s_provider.get_identity.return_value = None
        mock_aws_provider.get_identity.return_value = None
        mock_keyring_provider.get_identity.return_value = None
        providers = [mock_k8s_provider, mock_aws_provider, mock_keyring_provider]
        manager = IdentityManager(providers=providers, silent_mode=True)

        # Act
        result = manager.get_identity("any-agent-id")

        # Assert
        assert result is None
        mock_k8s_provider.get_identity.assert_called_once_with("any-agent-id")
        mock_aws_provider.get_identity.assert_called_once_with("any-agent-id")
        mock_keyring_provider.get_identity.assert_called_once_with("any-agent-id")

    def test_get_identity_with_no_providers(self):
        """
        GIVEN an identity manager with no providers configured
        WHEN get_identity is called
        THEN None is returned.
        """
        # Arrange
        manager = IdentityManager(providers=[], silent_mode=True)

        # Act
        result = manager.get_identity("any-agent-id")

        # Assert
        assert result is None 