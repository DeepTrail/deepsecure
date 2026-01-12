from unittest.mock import MagicMock, patch

from deepsecure.client import Client


def test_openai_list_models_calls_gateway_request_with_correct_args(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client.gateway, 'request', return_value=MagicMock(status_code=200)) as mock_req:
        resp = client.openai.list_models(agent_id="agent-1")
        args, kwargs = mock_req.call_args
        assert kwargs['agent_id'] == "agent-1"
        assert kwargs['target_base_url'] == "https://api.openai.com"
        assert kwargs['path'] == "/v1/models"
        assert resp.status_code == 200


def test_openai_list_models_handles_invalid_api_key_401(monkeypatch):
    client = Client(silent_mode=True)
    fake_resp = MagicMock(status_code=401)
    with patch.object(client.openai, 'list_models', return_value=fake_resp):
        resp = client.openai.list_models(agent_id="agent-1")
        assert resp.status_code == 401


def test_openai_chat_completions_non_stream_and_stream_paths(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client.gateway, 'request', return_value=MagicMock(status_code=200)) as mock_req:
        body = {"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]}
        client.openai.chat_completions(agent_id="agent-1", body=body, stream=False)
        args, kwargs = mock_req.call_args
        assert kwargs['path'] == "/v1/chat/completions"
        assert kwargs['json']["model"] == "gpt-4o"
        # stream True
        client.openai.chat_completions(agent_id="agent-1", body=body, stream=True)
        args, kwargs = mock_req.call_args
        assert kwargs['stream'] is True

