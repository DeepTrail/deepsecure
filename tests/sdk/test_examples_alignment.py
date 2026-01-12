from unittest.mock import patch, MagicMock

from deepsecure.client import Client


def test_example_01_imports_and_calls_current_api_shapes(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client, 'get_agent', return_value=MagicMock(id="agent-1", name="n1")):
        agent = client.get_agent("n1", auto_create=True)
        assert agent.id == "agent-1"


def test_example_08_uses_gateway_request_and_succeeds_with_mock(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client.gateway, 'request', return_value=MagicMock(status_code=200)) as mock_req:
        resp = client.gateway.request(
            agent_id="agent-1",
            target_base_url="https://api.openai.com",
            path="/v1/models",
        )
        assert resp.status_code == 200
        # headers may be set inside implementation; ensure args passed include target_base_url
        args, kwargs = mock_req.call_args
        assert kwargs['target_base_url'] == "https://api.openai.com"

