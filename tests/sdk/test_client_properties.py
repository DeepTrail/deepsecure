from deepsecure.client import Client
from deepsecure import __version__


def test_control_and_gateway_urls_from_env_and_defaults(monkeypatch):
    # Defaults if not set are in BaseClient; set env to custom values
    monkeypatch.setenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://control.test:8001")
    monkeypatch.setenv("DEEPSECURE_DEEPTRAIL_GATEWAY_URL", "http://gateway.test:8002")

    client = Client(silent_mode=True)

    assert client.control_url.startswith("http://")
    assert client.gateway_url.startswith("http://")


def test_client_version_matches_package_version():
    client = Client(silent_mode=True)
    assert client.version == __version__

