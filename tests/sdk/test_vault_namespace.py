from unittest.mock import MagicMock, patch

from deepsecure.client import Client


def test_vault_store_secret_includes_target_base_url_and_labels(monkeypatch):
    client = Client(silent_mode=True)
    # Mock underlying _request used by VaultClient.store_secret
    with patch.object(client, '_request', create=True) as mock_req:
        mock_resp = MagicMock(); mock_resp.json.return_value = {"ok": True}
        mock_req.return_value = mock_resp

        res = client.vault.store_secret(
            name="openai-api-key",
            value="sk-...",
            target_base_url="https://api.openai.com",
            labels={"env": "prod"},
            metadata={"note": "k1"},
        )
        args, kwargs = mock_req.call_args
        body = kwargs['json']
        assert body['secret_metadata']['target_base_url'] == "https://api.openai.com"
        assert body['secret_metadata']['labels']["env"] == "prod"
        assert res["ok"] is True


def test_vault_get_secret_admin_fetches_directly(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client, '_request', create=True) as mock_req:
        mock_resp = MagicMock(); mock_resp.json.return_value = {"name": "x", "value": "v"}
        mock_req.return_value = mock_resp
        res = client.vault.get_secret_admin("x")
        assert res["name"] == "x"


def test_vault_list_secrets_admin_optional(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client, '_request', create=True) as mock_req:
        mock_resp = MagicMock(); mock_resp.json.return_value = {"secrets": []}
        mock_req.return_value = mock_resp
        res = client.vault.list_secrets_admin()
        assert "secrets" in res

