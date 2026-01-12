import datetime
from datetime import timezone
import pytest
from pymacaroons import Macaroon

from app.services.macaroon_service import MacaroonService

# This key is for testing purposes only and matches the default in the service
TEST_MACAROON_KEY = "a-super-secret-key-for-testing"


@pytest.fixture
def macaroon_service() -> MacaroonService:
    return MacaroonService()


def test_mint_delegation_macaroon_creates_valid_token(macaroon_service: MacaroonService):
    """
    Test that a valid, serialized macaroon is created.
    """
    serialized_macaroon = macaroon_service.mint_delegation_macaroon(
        target_agent_id="test-agent-delegatee",
        resource="secret:my-secret",
        permissions=["read"],
        ttl_seconds=60,
    )
    assert isinstance(serialized_macaroon, str)
    # A simple check to ensure it's likely base64
    assert len(serialized_macaroon) > 50

    # Ensure it can be deserialized
    deserialized = Macaroon.deserialize(serialized_macaroon)
    assert isinstance(deserialized, Macaroon)


def test_minted_macaroon_contains_correct_caveats(macaroon_service: MacaroonService):
    """
    Test that the minted macaroon contains all the correct, verifiable caveats.
    """
    target_agent_id = "test-agent-delegatee-002"
    resource = "secret:financial-report"
    permissions = ["read", "query"]
    ttl = 300

    serialized_macaroon = macaroon_service.mint_delegation_macaroon(
        target_agent_id=target_agent_id,
        resource=resource,
        permissions=permissions,
        ttl_seconds=ttl,
    )

    m = Macaroon.deserialize(serialized_macaroon)
    caveats = {c.to_dict()['cid'] for c in m.caveats}

    # 1. Check for the time caveat
    time_caveat_found = False
    for cav in caveats:
        if cav.startswith("time < "):
            time_caveat_found = True
            expires_str = cav.split(" < ")[1].rstrip("Z")
            expires = datetime.datetime.fromisoformat(expires_str)
            # Check if expiry is roughly correct (within a few seconds)
            assert datetime.datetime.now(timezone.utc).replace(tzinfo=None) + datetime.timedelta(seconds=ttl - 5) < expires
            break
    assert time_caveat_found, "Time caveat was not found in the macaroon"

    # 2. Check for other exact match caveats
    assert f"target_agent_id = {target_agent_id}" in caveats
    assert f"resource = {resource}" in caveats
    for p in permissions:
        assert f"permission = {p}" in caveats 