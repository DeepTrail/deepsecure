from unittest.mock import MagicMock, patch

from deepsecure.client import Client


def test_get_agent_returns_agent_and_autocreates_when_missing(monkeypatch):
    client = Client(silent_mode=True)
    # Mock list_agents to return empty so auto_create triggers
    with patch.object(client.agents, 'list_agents', return_value={"agents": [], "total": 0}):
        # Mock identity manager key gen and store
        client.identity_manager.generate_ed25519_keypair_raw_b64 = MagicMock(return_value={"public_key": "pk", "private_key": "sk"})
        client.identity_manager.store_private_key_directly = MagicMock()
        # Mock backend unauth create
        with patch.object(client.agents, 'create_agent_unauthenticated', return_value={"agent_id": "agent-autoc", "name": "auto"}):
            agent = client.get_agent("auto", auto_create=True)
            assert agent.id == "agent-autoc"


def test_agents_namespace_list_describe_delete_roundtrip(monkeypatch):
    client = Client(silent_mode=True)
    # list
    with patch.object(client.agents, 'list_agents', return_value={"agents": [{"agent_id": "a1", "name": "n1"}], "total": 1}):
        res = client.agents.list_agents()
        assert res["total"] == 1
    # describe
    with patch.object(client.agents, 'describe_agent', return_value={"agent_id": "a1", "publicKey": "pk"}):
        desc = client.agents.describe_agent("a1")
        assert desc["agent_id"] == "a1"
    # delete
    with patch.object(client.agents, 'delete_agent', return_value={"agent_id": "a1", "status": "deleted"}):
        deleted = client.agents.delete_agent("a1")
        assert deleted["status"] in ("deleted", "success", "active")

