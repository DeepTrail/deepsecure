from unittest.mock import MagicMock, patch

from deepsecure.client import Client


def test_gateway_request_sets_x_target_base_url_and_proxy_path(monkeypatch):
    client = Client(silent_mode=True)
    # Mock underlying authenticated request on the internal BaseClient
    with patch.object(client, '_authenticated_request', create=True, return_value=MagicMock()) as mock_auth_req:
        client.gateway.request(
            agent_id="agent-1",
            target_base_url="https://api.example.com",
            path="/v1/models",
        )
        args, kwargs = mock_auth_req.call_args
        assert args[1].startswith("/proxy/")
        assert kwargs['headers']["X-Target-Base-URL"] == "https://api.example.com"


def test_gateway_request_handles_get_post_json_data_params(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client, '_authenticated_request', create=True, return_value=MagicMock()) as mock_auth_req:
        client.gateway.request(
            agent_id="agent-1",
            target_base_url="https://api.example.com",
            path="/v1/items",
            method="POST",
            json={"a": 1},
            params={"q": "x"},
            headers={"X-Req": "1"},
        )
        args, kwargs = mock_auth_req.call_args
        assert kwargs['json']["a"] == 1
        assert kwargs['params']["q"] == "x"
        assert kwargs['headers']["X-Req"] == "1"


def test_gateway_request_streaming_flag_pass_through(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client, '_authenticated_request', create=True, return_value=MagicMock()) as mock_auth_req:
        client.gateway.request(
            agent_id="agent-1",
            target_base_url="https://api.example.com",
            path="/v1/stream",
            method="GET",
            stream=True,
        )
        args, kwargs = mock_auth_req.call_args
        assert kwargs['stream'] is True

