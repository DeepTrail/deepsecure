import datetime
from datetime import timezone
from typing import List

from pymacaroons import Macaroon

from app.core.config import settings


class MacaroonService:
    """
    A service for minting and handling Macaroons for delegation.
    """

    def mint_delegation_macaroon(
        self,
        target_agent_id: str,
        resource: str,
        permissions: List[str],
        ttl_seconds: int,
    ) -> str:
        """
        Mints a new, attenuated Macaroon for delegation purposes.

        This Macaroon contains caveats that restrict its use to a specific agent,
        resource, and time window.

        Args:
            target_agent_id: The ID of the agent the token is being delegated to.
            resource: The resource the delegatee is granted access to.
            permissions: A list of specific actions the delegatee can perform.
            ttl_seconds: The time-to-live for the macaroon in seconds.

        Returns:
            A serialized (base64 encoded) Macaroon string.
        """
        # For now, we will use a placeholder key and location from settings.
        # These will need to be properly configured in the environment.
        macaroon_key = getattr(settings, "MACAROON_SECRET_KEY", "a-super-secret-key-for-testing")
        gateway_location = getattr(settings, "DEEPTRAIL_GATEWAY_URL", "http://deeptrail-gateway")
        key_identifier = "deeptrail-control-v1"

        macaroon = Macaroon(
            location=gateway_location,
            identifier=key_identifier,
            key=macaroon_key,
        )

        # Add standard time-based caveat
        expires_at = datetime.datetime.now(timezone.utc).replace(tzinfo=None) + datetime.timedelta(
            seconds=ttl_seconds
        )
        macaroon.add_first_party_caveat(f"time < {expires_at.isoformat()}Z")

        # Add delegation-specific caveats
        macaroon.add_first_party_caveat(f"target_agent_id = {target_agent_id}")
        macaroon.add_first_party_caveat(f"resource = {resource}")
        for perm in permissions:
            macaroon.add_first_party_caveat(f"permission = {perm}")

        return macaroon.serialize()


macaroon_service = MacaroonService() 