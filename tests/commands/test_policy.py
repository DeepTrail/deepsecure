import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch

from deepsecure.main import app
from deepsecure._core.schemas import PolicyResponse

runner = CliRunner()

@pytest.fixture
def mock_policy_client():
    """Mocks the policy client."""
    with patch("deepsecure.commands.policy.policy_client", autospec=True) as mock_client:
        yield mock_client

def test_policy_create_success(mock_policy_client: MagicMock):
    """Test successful policy creation."""
    mock_policy_client.create.return_value = PolicyResponse(
        id="policy-123",
        name="test-policy",
        agent_id="agent-abc",
        actions=["secret:read"],
        resources=["arn:*:secret:*:*:*:my-secret"],
        effect="allow",
    )

    result = runner.invoke(
        app,
        [
            "policy",
            "create",
            "--name", "test-policy",
            "--agent-id", "agent-abc",
            "--action", "secret:read",
            "--resource", "arn:*:secret:*:*:*:my-secret",
        ],
    )
    assert result.exit_code == 0
    assert "Policy 'test-policy' created with ID: policy-123" in result.stdout
    mock_policy_client.create.assert_called_once()

def test_policy_list_success(mock_policy_client: MagicMock):
    """Test successful listing of policies."""
    mock_policy_client.list.return_value = [
        PolicyResponse(
            id="policy-123",
            name="test-policy-1",
            agent_id="agent-abc",
            actions=["secret:read"],
            resources=["arn:*:secret:*:*:*:secret1"],
            effect="allow",
        ),
        PolicyResponse(
            id="policy-456",
            name="test-policy-2",
            agent_id="agent-def",
            actions=["db:query"],
            resources=["arn:*:db:*:*:*:users"],
            effect="allow",
        ),
    ]

    result = runner.invoke(app, ["policy", "list"])
    assert result.exit_code == 0
    assert "policy-123" in result.stdout
    assert "test-policy-2" in result.stdout
    assert "agent-def" in result.stdout
    mock_policy_client.list.assert_called_once()

def test_policy_list_empty(mock_policy_client: MagicMock):
    """Test listing policies when none exist."""
    mock_policy_client.list.return_value = []
    result = runner.invoke(app, ["policy", "list"])
    assert result.exit_code == 0
    assert "No policies found" in result.stdout

def test_policy_get_success(mock_policy_client: MagicMock):
    """Test successfully getting a single policy."""
    mock_policy_client.get.return_value = PolicyResponse(
        id="policy-123",
        name="test-policy",
        agent_id="agent-abc",
        actions=["secret:read"],
        resources=["arn:*:secret:*:*:*:my-secret"],
        effect="allow",
    )
    result = runner.invoke(app, ["policy", "get", "policy-123"])
    assert result.exit_code == 0
    assert "'id': 'policy-123'" in result.stdout
    mock_policy_client.get.assert_called_once_with("policy-123")

def test_policy_delete_success(mock_policy_client: MagicMock):
    """Test successful policy deletion."""
    mock_policy_client.delete.return_value = {"message": "Policy policy-123 deleted successfully."}
    result = runner.invoke(app, ["policy", "delete", "policy-123"])
    assert result.exit_code == 0
    assert "Policy policy-123 deleted successfully." in result.stdout
    mock_policy_client.delete.assert_called_once_with("policy-123") 