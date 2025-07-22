"""
Data migration script to convert existing secrets to the split-key format.

!! IMPORTANT !!
This script is intended to be run AFTER deploying the new code but BEFORE
running the alembic migration that renames the 'value' column to 'share_1'
in the 'secrets' table of the deeptrail-control database.

The script performs the following actions:
1. Connects directly to the deeptrail-control PostgreSQL database.
2. Reads each secret where the 'value' column is not null.
3. Splits the secret 'value' into two shares using Shamir's Secret Sharing.
4. Updates the 'secrets' table, storing the first share in the 'share_1' column
   and setting 'value' to NULL.
5. Makes an internal API call to the deeptrail-gateway to store the second share.

Required Environment Variables:
- DATABASE_URL: The connection string for the deeptrail-control database.
  (e.g., postgresql://user:password@localhost/deepsecure_db)
- GATEWAY_URL: The URL for the deeptrail-gateway service.
  (e.g., http://localhost:8001)
- GATEWAY_INTERNAL_API_TOKEN: The secret token for internal communication.
"""

import os
import sys
import httpx
from sslib import shamir
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

# --- Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
GATEWAY_URL = os.getenv("GATEWAY_URL")
GATEWAY_INTERNAL_API_TOKEN = os.getenv("GATEWAY_INTERNAL_API_TOKEN")

def check_config():
    """Checks if all required environment variables are set."""
    if not all([DATABASE_URL, GATEWAY_URL, GATEWAY_INTERNAL_API_TOKEN]):
        print("Error: Missing required environment variables.", file=sys.stderr)
        print("Please set DATABASE_URL, GATEWAY_URL, and GATEWAY_INTERNAL_API_TOKEN.", file=sys.stderr)
        sys.exit(1)

def send_share_to_gateway(secret_name: str, share: str):
    """Sends a secret share to the deeptrail-gateway."""
    gateway_endpoint = f"{GATEWAY_URL}/api/v1/internal/shares"
    headers = {"X-Internal-API-Token": GATEWAY_INTERNAL_API_TOKEN}
    payload = {"secret_name": secret_name, "share_value": share}

    with httpx.Client() as client:
        try:
            response = client.post(gateway_endpoint, json=payload, headers=headers)
            response.raise_for_status()
            print(f"Successfully sent share for '{secret_name}' to gateway.")
        except httpx.HTTPStatusError as e:
            print(f"Error sending share for '{secret_name}' to gateway. Status: {e.response.status_code}, Body: {e.response.text}", file=sys.stderr)
            raise
        except httpx.RequestError as e:
            print(f"Network error connecting to gateway: {e}", file=sys.stderr)
            raise

def migrate_secrets():
    """Performs the secret migration."""
    print("Starting secret migration to split-key format...")
    engine = create_engine(DATABASE_URL)

    with engine.connect() as connection:
        # We need a transaction to ensure atomicity
        with connection.begin():
            # Find all secrets that have not been migrated yet
            select_query = text("SELECT id, name, value FROM secrets WHERE value IS NOT NULL")
            secrets_to_migrate = connection.execute(select_query).fetchall()

            if not secrets_to_migrate:
                print("No secrets found to migrate.")
                return

            print(f"Found {len(secrets_to_migrate)} secrets to migrate.")

            for secret in secrets_to_migrate:
                secret_id, secret_name, secret_value = secret
                print(f"Migrating secret: '{secret_name}' (ID: {secret_id})")

                # 1. Split the secret
                try:
                    shares = shamir.split_secret(secret_value.encode('utf-8'), 2, 2)
                    share_1, share_2 = shares
                except Exception as e:
                    print(f"  - FAILED to split secret '{secret_name}'. Error: {e}", file=sys.stderr)
                    # We will rollback the transaction by raising the exception
                    raise RuntimeError(f"Migration failed for secret '{secret_name}'") from e

                # 2. Send share 2 to the gateway
                try:
                    send_share_to_gateway(secret_name, share_2)
                except Exception as e:
                    print(f"  - FAILED to send share to gateway for '{secret_name}'. Error: {e}", file=sys.stderr)
                    raise RuntimeError(f"Migration failed for secret '{secret_name}'") from e

                # 3. Update the local database record
                update_query = text("""
                    UPDATE secrets
                    SET share_1 = :share_1, value = NULL
                    WHERE id = :secret_id
                """)
                connection.execute(update_query, {"share_1": share_1, "secret_id": secret_id})
                print(f"  - Successfully updated local record for '{secret_name}'.")

    print("\nMigration completed successfully!")

if __name__ == "__main__":
    check_config()
    migrate_secrets() 