# tests/_core/test_identity_manager.py
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import base64
import uuid
import unittest

from deepsecure._core.identity_manager import IdentityManager, _get_keyring_service_name_for_agent
from deepsecure.exceptions import IdentityManagerError

# Mock key data for consistent testing
MOCK_PUBLIC_KEY_B64 = base64.b64encode(b'public_key_bytes_for_testing_32').decode('utf-8')
MOCK_PRIVATE_KEY_B64 = base64.b64encode(b'private_key_bytes_for_testing_32').decode('utf-8')

@pytest.fixture
def mock_path():
    """Fixture to mock pathlib.Path."""
    with patch('deepsecure._core.identity_manager.Path') as mock_path_class:
        mock_identities_dir = MagicMock(spec=Path)
        # Mock the chained calls: Path.home().joinpath()
        mock_path_class.home.return_value.joinpath.return_value = mock_identities_dir
        yield mock_identities_dir

@pytest.fixture
def mock_key_manager():
    """Fixture to mock the internal key manager."""
    with patch('deepsecure._core.identity_manager.key_manager_module.key_manager') as mock_km:
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
def identity_manager(mock_path, mock_key_manager, mock_keyring):
    """Provides an IdentityManager instance with all dependencies mocked."""
    # We pass the mocked fixtures here, but the IdentityManager will import and use the patched versions
    return IdentityManager(silent_mode=True, identity_store_path_override=mock_path)

def test_create_identity_success(identity_manager, mock_path, mock_keyring):
    """Test the successful creation of a new agent identity."""
    agent_name = "test-agent"
    agent_uuid = "some-uuid"
    agent_id = f"agent-{agent_uuid}"
    
    mock_identity_file = mock_path / f"{agent_id}.json"
    mock_identity_file.exists.return_value = False

    # Mock the file writing context manager
    mock_file_handle = MagicMock()
    mock_open_context = MagicMock()
    mock_open_context.__enter__.return_value = mock_file_handle
    
    # When `open` is called on the path, return our context manager
    (mock_path / f"{agent_id}.json").open.return_value = mock_open_context

    with patch('deepsecure._core.identity_manager.uuid.uuid4', return_value=agent_uuid):
        with patch('deepsecure._core.identity_manager.json.dump') as mock_json_dump:
            identity = identity_manager.create_identity(name=agent_name)

    # 1. Verify returned identity object
    assert identity['name'] == agent_name
    assert identity['id'] == agent_id
    assert identity['public_key'] == MOCK_PUBLIC_KEY_B64

    # 2. Verify keyring call
    expected_service_name = _get_keyring_service_name_for_agent(agent_id)
    mock_keyring.set_password.assert_called_once_with(
        expected_service_name, agent_id, MOCK_PRIVATE_KEY_B64
    )

    # 3. Verify metadata file was written correctly
    (mock_path / f"{agent_id}.json").chmod.assert_called_once_with(0o600)
    
    saved_data = mock_json_dump.call_args[0][0]
    assert saved_data['id'] == agent_id
    assert 'private_key' not in saved_data

def test_load_identity_success(identity_manager, mock_path, mock_keyring):
    """Test successfully loading an existing identity."""
    agent_id = "agent-existing-uuid"
    
    mock_identity_file = mock_path / f"{agent_id}.json"
    mock_identity_file.exists.return_value = True
    
    mock_file_content = {
        "id": agent_id,
        "name": "existing-agent",
        "public_key": MOCK_PUBLIC_KEY_B64
    }
    
    mock_keyring.get_password.return_value = MOCK_PRIVATE_KEY_B64
    
    with patch('builtins.open', unittest.mock.mock_open(read_data=json.dumps(mock_file_content))):
        identity = identity_manager.load_identity(agent_id=agent_id)

    assert identity is not None
    assert identity['id'] == agent_id
    assert identity['private_key'] == MOCK_PRIVATE_KEY_B64

    expected_service_name = _get_keyring_service_name_for_agent(agent_id)
    mock_keyring.get_password.assert_called_once_with(expected_service_name, agent_id)

def test_delete_identity(identity_manager, mock_path, mock_keyring):
    """Test deleting an identity's file and keyring entry."""
    agent_id = "agent-to-delete"
    
    mock_identity_file = mock_path / f"{agent_id}.json"
    mock_identity_file.exists.return_value = True

    result = identity_manager.delete_identity(agent_id)

    assert result is True
    mock_identity_file.unlink.assert_called_once()
    
    expected_service_name = _get_keyring_service_name_for_agent(agent_id)
    mock_keyring.delete_password.assert_called_once_with(expected_service_name, agent_id)

def test_create_identity_keyring_fails(identity_manager, mock_keyring, mock_path):
    """Test that identity creation is aborted if keyring fails."""
    # Prevent the file from already existing
    mock_identity_file = mock_path / "agent-fail-agent.json"
    mock_identity_file.exists.return_value = False
    
    mock_keyring.set_password.side_effect = Exception("Keyring is locked")

    with pytest.raises(IdentityManagerError, match="An unexpected error occurred while storing private key"):
        identity_manager.create_identity(name="fail-agent")

def test_get_keyring_service_name_for_agent():
    """Test the helper function for generating keyring service names."""
    assert _get_keyring_service_name_for_agent("agent-12345678-abcd-1234-abcd-1234567890ab") == "deepsecure_agent-12345678_private_key"
    with pytest.raises(ValueError):
        _get_keyring_service_name_for_agent("invalid-agent-id")

if __name__ == '__main__':
    pytest.main() 