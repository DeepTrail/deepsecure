from unittest.mock import MagicMock, patch

from deepsecure.client import Client


def test_credentials_issue_delegates_and_returns_expected_model(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client.vault, 'issue', return_value=MagicMock(credential_id="cred-1")) as mock_issue:
        resp = client.credentials.issue(agent_id="agent-1", scope="s:read")
        assert resp.credential_id == "cred-1"


def test_credentials_verify_and_revoke_delegation(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client.vault, 'verify', return_value=MagicMock(status="valid")) as mock_verify:
        ver = client.credentials.verify("cred-1")
        assert ver.status in ("valid", "revoked", "invalid")
    with patch.object(client.vault, 'revoke', return_value=MagicMock(status="revoked")) as mock_revoke:
        rev = client.credentials.revoke("cred-1")
        assert rev.status == "revoked"

