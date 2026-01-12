from unittest.mock import MagicMock, patch

from deepsecure.client import Client


def test_agent_gateway_request_uses_agent_id_and_gateway(monkeypatch):
    client = Client(silent_mode=True)
    # Fake agent resource mimicking client.get_agent
    # Build a minimal Agent-like object using the real Agent class to exercise sugar
    from deepsecure.resources.agent import Agent as AgentClass
    dummy_agents_ref = MagicMock(_parent_client=client)
    agent = AgentClass(client_ref=dummy_agents_ref, agent_data={"agent_id": "agent-1"})
    # Mock gateway.request to return a fake response
    with patch.object(client.gateway, 'request', return_value=MagicMock(status_code=200)) as mock_req:
        # Call through sugar
        resp = agent.gateway_request(target_base_url="https://api.openai.com", path="/v1/models")
        assert resp.status_code == 200
        args, kwargs = mock_req.call_args
        assert kwargs['agent_id'] == "agent-1"
        assert kwargs['target_base_url'] == "https://api.openai.com"


def test_agent_openai_list_models_delegates_correctly(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client.openai, 'list_models', return_value=MagicMock(status_code=200)) as mock_list:
        from deepsecure.resources.agent import Agent as AgentClass
        dummy_agents_ref = MagicMock(_parent_client=client)
        agent = AgentClass(client_ref=dummy_agents_ref, agent_data={"agent_id": "agent-1"})
        resp2 = agent.openai_list_models()
        assert resp2.status_code == 200
        mock_list.assert_called_once_with(agent_id="agent-1")

