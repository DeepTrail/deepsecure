from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from app import crud, schemas
from app.core.config import settings

class AttestationService:
    def attest_gcp_and_create_agent(self, db: Session, *, token: str) -> tuple[str, str]:
        """
        Verifies a GCP identity token, checks it against policy, and creates a new agent.
        """
        # 1. Verify the GCP identity token
        try:
            # The audience must be the URL of our control plane
            audience = settings.SERVER_HOST
            id_info = id_token.verify_token(token, google_requests.Request(), audience=audience)
        except ValueError as e:
            # This will catch invalid tokens, signatures, expiration, etc.
            raise Exception(f"Invalid GCP token: {e}")

        gcp_project_id = id_info.get("project_id")
        gcp_service_account = id_info.get("email")

        if not gcp_project_id or not gcp_service_account:
            raise Exception("GCP token is missing required claims (project_id, email).")

        # 2. (Placeholder for Task 1.3) Check against Attestation Policy
        # Here, we would query the database for an AttestationPolicy that matches
        # the claims from the token (e.g., gcp_project_id, gcp_service_account).
        # If no matching policy is found, we would raise an exception.
        # For now, we will proceed as if authorized.
        print(f"Verified GCP identity: project='{gcp_project_id}', service_account='{gcp_service_account}'")

        # 3. (Task 1.4) Generate a new Ed25519 key pair for the agent
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        # 4. Create the new agent in the database
        agent_in = schemas.AgentCreate(
            name=f"gcp-agent-{gcp_project_id[:8]}-{gcp_service_account.split('@')[0][:8]}",
            public_key=public_key_bytes.hex(),
            # Description can be enhanced to include more context
            description=f"Agent bootstrapped from GCP project {gcp_project_id}"
        )
        new_agent = crud.agent.create(db=db, obj_in=agent_in)

        # 5. Return the agent ID and the private key (one-time only)
        return str(new_agent.id), private_key_pem.decode("utf-8")


attestation_service = AttestationService() 