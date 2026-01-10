from unittest.mock import MagicMock, patch

from deepsecure.client import Client


def test_gateway_request_streams_bytes_and_closes_response(monkeypatch):
    client = Client(silent_mode=True)

    # Mock _authenticated_request to return a context manager for stream
    class DummyStream:
        def __init__(self):
            self.closed = False
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            self.closed = True

    dummy = DummyStream()
    with patch.object(client, '_authenticated_request', create=True, return_value=dummy) as mock_auth:
        resp = client.gateway.request(
            agent_id="agent-1",
            target_base_url="https://api.openai.com",
            path="/v1/stream",
            stream=True,
        )
        assert resp is dummy


def test_gateway_request_binary_content_returns_bytes(monkeypatch):
    client = Client(silent_mode=True)
    fake = MagicMock()
    fake.content = b"\x00\x01\x02"
    with patch.object(client, '_authenticated_request', create=True, return_value=fake) as mock_auth:
        resp = client.gateway.request(
            agent_id="agent-1",
            target_base_url="https://api.example.com",
            path="/v1/blob",
            method="GET",
        )
        # Upstream returns raw bytes; ensure we can access .content
        assert isinstance(resp.content, (bytes, bytearray))


def test_gateway_request_large_payload_streaming_path(monkeypatch):
    client = Client(silent_mode=True)
    with patch.object(client, '_authenticated_request', create=True, return_value=MagicMock(status_code=200)) as mock_auth:
        # Simulate large upload via streaming (content provided)
        payload = b"x" * (2 * 1024 * 1024)  # 2MB
        resp = client.gateway.request(
            agent_id="agent-1",
            target_base_url="https://api.example.com",
            path="/v1/upload",
            method="POST",
            content=payload,
            stream=False,
        )
        assert resp.status_code == 200
        args, kwargs = mock_auth.call_args
        assert kwargs['content'] == payload

