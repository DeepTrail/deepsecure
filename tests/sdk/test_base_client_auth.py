# tests/sdk/test_base_client_auth.py
import pytest
from unittest.mock import MagicMock

from deepsecure._core.base_client import BaseClient


def make_client(api_url="http://control.local"):  # helper
    client = BaseClient(api_url=api_url)
    # Provide a fake identity manager expected by _authenticated_request
    client._identity_manager = MagicMock()
    client._identity_manager.get_private_key.return_value = "fake_private_key_b64"
    client._identity_manager.sign.return_value = "signed-nonce"
    # Replace underlying httpx.Client with a MagicMock so we can set side effects
    client.client = MagicMock()
    return client


def test_authenticated_request_obtains_token_when_missing(monkeypatch):
    client = make_client()

    mock_challenge = MagicMock()
    mock_challenge.json.return_value = {"nonce": "abc"}
    mock_challenge.raise_for_status.return_value = None

    mock_token = MagicMock()
    mock_token.json.return_value = {"access_token": "jwt-123"}
    mock_token.raise_for_status.return_value = None

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}

    client.client.post.side_effect = [mock_challenge, mock_token]
    client.client.request.return_value = mock_resp

    resp = client._authenticated_request("GET", "/api/v1/ping", agent_id="agent-1")
    assert resp.json()["ok"] is True
    assert client._access_token == "jwt-123"


def test_authenticated_request_reuses_existing_token(monkeypatch):
    from datetime import datetime, timedelta
    
    client = make_client()
    client._access_token = "existing-token"
    # Also set a valid expiry time so token is considered valid
    client._token_expires_at = datetime.now() + timedelta(hours=1)

    mock_resp = MagicMock()
    client.client.request.return_value = mock_resp

    client._authenticated_request("GET", "/api/v1/ping", agent_id="agent-1")
    # Should not perform challenge/token calls
    assert client.client.post.call_count == 0


def test_authenticated_request_attaches_bearer_header(monkeypatch):
    client = make_client()

    mock_challenge = MagicMock(); mock_challenge.json.return_value = {"nonce": "abc"}; mock_challenge.raise_for_status.return_value = None
    mock_token = MagicMock(); mock_token.json.return_value = {"access_token": "jwt-xyz"}; mock_token.raise_for_status.return_value = None
    client.client.post.side_effect = [mock_challenge, mock_token]

    mock_resp = MagicMock()
    client.client.request.return_value = mock_resp

    client._authenticated_request("GET", "/api/v1/resource", agent_id="agent-1")
    args, kwargs = client.client.request.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer jwt-xyz"


def test_authenticated_request_routes_to_gateway_with_base_override(monkeypatch):
    client = make_client(api_url="http://control")

    mock_challenge = MagicMock(); mock_challenge.json.return_value = {"nonce": "abc"}; mock_challenge.raise_for_status.return_value = None
    mock_token = MagicMock(); mock_token.json.return_value = {"access_token": "jwt-xyz"}; mock_token.raise_for_status.return_value = None
    client.client.post.side_effect = [mock_challenge, mock_token]

    mock_resp = MagicMock(); client.client.request.return_value = mock_resp

    client._authenticated_request(
        "GET",
        "/proxy/x",
        agent_id="agent-1",
        base_url_override="http://gateway:8002"
    )
    args, kwargs = client.client.request.call_args
    assert args[1].startswith("http://gateway:8002")


def test_authenticated_request_propagates_headers_params_and_body(monkeypatch):
    client = make_client()

    mock_challenge = MagicMock(); mock_challenge.json.return_value = {"nonce": "abc"}; mock_challenge.raise_for_status.return_value = None
    mock_token = MagicMock(); mock_token.json.return_value = {"access_token": "jwt-xyz"}; mock_token.raise_for_status.return_value = None
    client.client.post.side_effect = [mock_challenge, mock_token]

    mock_resp = MagicMock(); client.client.request.return_value = mock_resp

    client._authenticated_request(
        "POST",
        "/api/v1/resource",
        agent_id="agent-1",
        headers={"X-Test": "1"},
        params={"q": "x"},
        json={"a": 1},
        data=None,
        content=None,
        timeout=5.0,
    )
    args, kwargs = client.client.request.call_args
    assert kwargs["headers"]["X-Test"] == "1"
    assert kwargs["params"]["q"] == "x"
    assert kwargs["json"]["a"] == 1
    assert kwargs["timeout"] == 5.0

