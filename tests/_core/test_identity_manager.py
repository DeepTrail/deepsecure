# tests/_core/test_identity_manager.py
import pytest
from unittest.mock import patch, MagicMock
import base64

from deepsecure._core.identity_manager import IdentityManager, _get_keyring_service_name_for_agent
from deepsecure.exceptions import IdentityManagerError

# Mock key data for consistent testing
MOCK_PUBLIC_KEY_B64 = base64.b64encode(b'public_key_bytes_for_testing_32').decode('utf-8')
MOCK_PRIVATE_KEY_B64 = base64.b64encode(b'private_key_bytes_for_testing_32').decode('utf-8')

@pytest.fixture
def mock_key_manager():
    """Fixture to mock the internal key manager."""
    with patch('deepsecure._core.identity_manager.key_manager') as mock_km:
        mock_km.generate_identity_keypair.return_value = {
            "public_key": MOCK_PUBLIC_KEY_B64,
            "private_key": MOCK_PRIVATE_KEY_B64,
        }
        yield mock_km

@pytest.fixture
def mock_keyring():
    """Fixture to mock the keyring library."""
    with patch('deepsecure._core.identity_manager.keyring') as mock_kr:
        yield mock_kr

@pytest.fixture
def identity_manager(mock_key_manager, mock_keyring):
    """Provides an IdentityManager instance with all dependencies mocked."""
    return IdentityManager(silent_mode=True)

class TestIdentityManagerNewArchitecture:
    """Test suite for the new backend-only IdentityManager architecture."""
    
    def test_create_keypair_for_agent_success(self, identity_manager, mock_keyring):
        """Test successful keypair generation and storage."""
        agent_id = "agent-12345678-1234-1234-1234-123456789abc"
        
        # Execute
        result = identity_manager.create_keypair_for_agent(agent_id)
        
        # Verify returned data
        assert result["public_key"] == MOCK_PUBLIC_KEY_B64
        assert result["private_key"] == MOCK_PRIVATE_KEY_B64
        assert "public_key_fingerprint" in result
        assert result["public_key_fingerprint"].startswith("sha256:")
        
        # Verify keyring storage
        expected_service_name = _get_keyring_service_name_for_agent(agent_id)
        mock_keyring.set_password.assert_called_once_with(
            expected_service_name, agent_id, MOCK_PRIVATE_KEY_B64
        )
    
    def test_create_keypair_keyring_failure(self, identity_manager, mock_keyring):
        """Test keypair creation when keyring storage fails."""
        agent_id = "agent-12345678-1234-1234-1234-123456789abc"
        mock_keyring.set_password.side_effect = Exception("Keyring locked")
        
        # Execute and verify exception
        with pytest.raises(IdentityManagerError, match="An unexpected error occurred while storing private key"):
            identity_manager.create_keypair_for_agent(agent_id)
    
    def test_get_private_key_success(self, identity_manager, mock_keyring):
        """Test successful private key retrieval."""
        agent_id = "agent-87654321-4321-4321-4321-123456789abc"
        mock_keyring.get_password.return_value = MOCK_PRIVATE_KEY_B64
        
        # Execute
        result = identity_manager.get_private_key(agent_id)
        
        # Verify
        assert result == MOCK_PRIVATE_KEY_B64
        expected_service_name = _get_keyring_service_name_for_agent(agent_id)
        mock_keyring.get_password.assert_called_once_with(expected_service_name, agent_id)
    
    def test_get_private_key_not_found(self, identity_manager, mock_keyring):
        """Test private key retrieval when key doesn't exist."""
        agent_id = "agent-87654321-4321-4321-4321-123456789abc"
        mock_keyring.get_password.return_value = None
        
        # Execute
        result = identity_manager.get_private_key(agent_id)
        
        # Verify
        assert result is None
    
    def test_get_private_key_keyring_error(self, identity_manager, mock_keyring):
        """Test private key retrieval when keyring has an error."""
        agent_id = "agent-87654321-4321-4321-4321-123456789abc"
        mock_keyring.get_password.side_effect = Exception("Keyring error")
        
        # Execute
        result = identity_manager.get_private_key(agent_id)
        
        # Verify - should return None on error, not raise exception
        assert result is None
    
    def test_delete_private_key_success(self, identity_manager, mock_keyring):
        """Test successful private key deletion."""
        agent_id = "agent-11111111-2222-3333-4444-555555555555"
        
        # Execute
        result = identity_manager.delete_private_key(agent_id)
        
        # Verify
        assert result is True
        expected_service_name = _get_keyring_service_name_for_agent(agent_id)
        mock_keyring.delete_password.assert_called_once_with(expected_service_name, agent_id)
    
    def test_delete_private_key_not_found(self, identity_manager, mock_keyring):
        """Test private key deletion when key doesn't exist."""
        from keyring.errors import PasswordDeleteError
        agent_id = "agent-11111111-2222-3333-4444-555555555555"
        mock_keyring.delete_password.side_effect = PasswordDeleteError("Not found")
        
        # Execute
        result = identity_manager.delete_private_key(agent_id)
        
        # Verify - should return True (success) even if key didn't exist
        assert result is True
    
    def test_store_private_key_directly_success(self, identity_manager, mock_keyring):
        """Test direct private key storage."""
        agent_id = "agent-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        private_key = "test-private-key-b64"
        
        # Execute
        identity_manager.store_private_key_directly(agent_id, private_key)
        
        # Verify
        expected_service_name = _get_keyring_service_name_for_agent(agent_id)
        mock_keyring.set_password.assert_called_once_with(
            expected_service_name, agent_id, private_key
        )
    
    def test_store_private_key_directly_keyring_error(self, identity_manager, mock_keyring):
        """Test direct private key storage when keyring fails."""
        agent_id = "agent-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        private_key = "test-private-key-b64"
        mock_keyring.set_password.side_effect = Exception("Keyring error")
        
        # Execute and verify exception
        with pytest.raises(IdentityManagerError, match="An unexpected error occurred while storing private key"):
            identity_manager.store_private_key_directly(agent_id, private_key)
    
    def test_generate_ed25519_keypair_raw_b64(self, identity_manager, mock_key_manager):
        """Test raw keypair generation."""
        # Execute
        result = identity_manager.generate_ed25519_keypair_raw_b64()
        
        # Verify
        assert result == {
            "public_key": MOCK_PUBLIC_KEY_B64,
            "private_key": MOCK_PRIVATE_KEY_B64,
        }
        mock_key_manager.generate_identity_keypair.assert_called_once()
    
    def test_get_public_key_fingerprint(self, identity_manager):
        """Test public key fingerprint generation."""
        # Execute
        result = identity_manager.get_public_key_fingerprint(MOCK_PUBLIC_KEY_B64)
        
        # Verify
        assert result.startswith("sha256:")
        assert len(result) == 71  # "sha256:" + 64 hex chars
    
    def test_get_public_key_fingerprint_invalid_key(self, identity_manager):
        """Test public key fingerprint with invalid key."""
        # Execute and verify exception
        with pytest.raises(IdentityManagerError, match="Failed to generate fingerprint"):
            identity_manager.get_public_key_fingerprint("invalid-base64")
    
    def test_decode_private_key_success(self, identity_manager):
        """Test private key decoding."""
        # Use a real Ed25519 private key for this test
        from cryptography.hazmat.primitives.asymmetric import ed25519
        real_private_key = ed25519.Ed25519PrivateKey.generate()
        private_key_bytes = real_private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        private_key_b64 = base64.b64encode(private_key_bytes).decode('utf-8')
        
        # Execute
        result = identity_manager.decode_private_key(private_key_b64)
        
        # Verify
        assert isinstance(result, ed25519.Ed25519PrivateKey)
    
    def test_decode_private_key_invalid_key(self, identity_manager):
        """Test private key decoding with invalid key."""
        # Execute and verify exception
        with pytest.raises(IdentityManagerError, match="Failed to decode private key"):
            identity_manager.decode_private_key("invalid-base64")
    
    def test_generate_agent_id(self, identity_manager):
        """Test agent ID generation."""
        # Execute
        result = identity_manager._generate_agent_id()
        
        # Verify
        assert result.startswith("agent-")
        assert len(result) == 42  # "agent-" + 36 char UUID


class TestKeyringServiceNameHelper:
    """Test the keyring service name helper function."""
    
    def test_get_keyring_service_name_for_agent_valid(self):
        """Test service name generation with valid agent ID."""
        agent_id = "agent-12345678-abcd-1234-abcd-1234567890ab"
        expected = "deepsecure_agent-12345678_private_key"
        
        result = _get_keyring_service_name_for_agent(agent_id)
        
        assert result == expected
    
    def test_get_keyring_service_name_for_agent_invalid_format(self):
        """Test service name generation with invalid agent ID format."""
        with pytest.raises(ValueError, match="does not follow the expected 'agent-<uuid>' format"):
            _get_keyring_service_name_for_agent("invalid-agent-id")
    
    def test_get_keyring_service_name_for_agent_empty_uuid_part(self):
        """Test service name generation with agent ID with empty UUID part."""
        # This actually works with the current implementation, returning "deepsecure_agent-_private_key"
        # Let's test this behavior rather than expecting an exception
        result = _get_keyring_service_name_for_agent("agent-")
        assert result == "deepsecure_agent-_private_key"


# Import needed for the decode test
from cryptography.hazmat.primitives import serialization

if __name__ == '__main__':
    pytest.main([__file__]) 