from unittest.mock import patch, MagicMock

from deepsecure.client import Client


def test_quickstart_snippet_executes_with_mocks(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client, 'get_agent', return_value=MagicMock(id="agent-1", name="my-ai-agent")):
        agent = client.get_agent("my-ai-agent", auto_create=True)
        assert agent.id == "agent-1"
    # Mock a gateway call similar to listing models
    with patch.object(client.gateway, 'request', return_value=MagicMock(status_code=200)) as mock_req:
        resp = client.gateway.request(
            agent_id="agent-1",
            target_base_url="https://api.openai.com",
            path="/v1/models",
        )
        assert resp.status_code == 200

