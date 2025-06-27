# examples/04_multi_agent_communication.py
"""
This example demonstrates secure agent-to-agent (A2A) communication
using JWTs signed by DeepSecure agent identities.

Scenario:
1. An "issuer" agent needs to call a protected API endpoint.
2. A "verifier" service protects that endpoint.
3. The issuer agent generates a short-lived JWT for the verifier.
4. The verifier service receives the token, fetches the issuer's public key
   from the DeepSecure backend, and verifies the token's signature and claims.

Prerequisites:
1. `pip install 'deepsecure[frameworks]'` (to install fastapi and uvicorn)
2. A running DeepSecure `credservice` backend.
3. Your DeepSecure CLI is configured (`deepsecure configure`).
"""
import deepsecure
import jwt
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
import uvicorn
import threading
import time
import requests

# --- Verifier Service (Simulated API) ---

# This simulates a service that needs to verify tokens.
# It uses the DeepSecure client to get the public key of the token issuer.
verifier_client = deepsecure.Client()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # tokenUrl is a dummy value

app = FastAPI()

@app.get("/protected")
async def protected_endpoint(token: str = Depends(oauth2_scheme)):
    """A protected endpoint that requires a valid agent JWT."""
    print(f"\\n[Verifier Service] Received request with token: {token[:30]}...")
    
    try:
        # 1. Decode the token without verification to inspect its claims,
        # especially the issuer ('iss').
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
        issuer_agent_id = unverified_claims.get("iss")
        audience = unverified_claims.get("aud")
        
        if not issuer_agent_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing 'iss' claim in token")

        print(f"[Verifier Service] Token issuer identified as: {issuer_agent_id}")
        print(f"[Verifier Service] Token audience is: {audience}")

        # In a real app, you would verify the audience matches your service's identity.
        if audience != "my-secure-api":
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token audience")

        # 2. Fetch the issuer agent's details to get their public key.
        # This is a critical step: the verifier trusts the DeepSecure backend
        # as the source of truth for public keys.
        print(f"[Verifier Service] Fetching public key for agent '{issuer_agent_id}' from backend...")
        # Note: In a real high-performance service, you would cache this public key.
        issuer_agent_details = verifier_client._agent_client.describe_agent(issuer_agent_id)
        if not issuer_agent_details:
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Issuer agent not found")
        
        public_key_b64 = issuer_agent_details.get("publicKey")  # Use the correct field name from API response
        public_key = verifier_client._identity_manager.key_manager.decode_public_key_b64(public_key_b64)
        print("[Verifier Service] Public key fetched successfully.")

        # 3. Now, verify the token's signature and claims.
        jwt.decode(
            token,
            public_key,
            algorithms=["EdDSA"],
            audience="my-secure-api" # Verify audience again
        )
        print("[Verifier Service] ✅ Token signature and claims are valid.")
        
        return {"message": f"Hello, agent {issuer_agent_id}! Your token is valid."}

    except jwt.ExpiredSignatureError:
        print("[Verifier Service] ❌ Token has expired.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        print(f"[Verifier Service] ❌ Invalid token: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")
    except Exception as e:
        print(f"[Verifier Service] ❌ An unexpected error occurred: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

def run_api():
    """Function to run the FastAPI server in a separate thread."""
    uvicorn.run(app, host="0.0.0.0", port=8008, log_level="warning")


# --- Issuer Agent (Client) ---

def client_workflow():
    """Simulates a client agent issuing a token and calling the API."""
    print("--- DeepSecure A2A Communication Example ---")

    try:
        # 1. Initialize the client for the issuer.
        issuer_client = deepsecure.Client()
        issuer_agent_name = "a2a-issuer-agent"
        print(f"✅ Issuer client initialized. Ensuring agent '{issuer_agent_name}' exists...")
        issuer_agent = issuer_client.agent(issuer_agent_name, auto_create=True)
        print(f"   Issuer agent ID: {issuer_agent.id}")

        # 2. The issuer agent issues a token for the target API.
        audience = "my-secure-api"
        print(f"\\n✅ Issuing token for audience: '{audience}'...")
        token = issuer_agent.issue_token_for(audience=audience, expiry_minutes=1)
        print("   Token issued successfully.")

        # 3. The client makes an authenticated request to the protected service.
        print("\\n✅ Making authenticated request to the verifier service...")
        time.sleep(1) # Give the server a moment to start
        
        response = requests.get(
            "http://localhost:8008/protected",
            headers={"Authorization": f"Bearer {token}"}
        )

        print(f"\\n--- Verifier Response ---")
        print(f"Status Code: {response.status_code}")
        print(f"Response JSON: {response.json()}")
        print("--------------------------")
        
        if response.ok:
            print("\\n✅ A2A communication successful!")
        else:
            print("\\n❌ A2A communication failed.")

    except deepsecure.DeepSecureError as e:
        print(f"\\n[ERROR] A DeepSecure error occurred in the client workflow: {e}")
    except Exception as e:
        print(f"\\n[ERROR] An unexpected error occurred in the client workflow: {e}")


# --- Main Execution ---

if __name__ == "__main__":
    # Run the FastAPI server in a background thread
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    
    # Run the client workflow
    client_workflow() 