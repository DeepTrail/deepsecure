import requests
import json
import time

# Configuration
DEEPSECURE_PDP_URL = "http://localhost:8001/v1/credentials"
KONG_PROXY_URL = "http://localhost:8000"
API_TOKEN = "DEFAULT_QUICKSTART_TOKEN" # This is the default token in the docker-compose setup

def get_fine_grained_credential(resource_uri: str, actions: list):
    """Requests a fine-grained credential from the DeepSecure PDP."""
    payload = {
        "resources": [
            {
                "uri": resource_uri,
                "actions": actions
            }
        ],
        "principal": {
            "id": "agent- simulated-example",
            "roles": ["api-agent"]
        },
        "ttl": 300 # 5 minute expiry
    }
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(DEEPSECURE_PDP_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        credential = response.json().get("credential")
        if not credential:
            raise ValueError("Credential not found in response")
        print(f"Credential obtained successfully for resource: {resource_uri}")
        return credential
    except requests.exceptions.RequestException as e:
        print(f"Error getting credential: {e}")
        if e.response:
            print(f"Response body: {e.response.text}")
        return None

def call_api_via_kong(path: str, credential: str):
    """Makes an API call to the protected service via the Kong gateway."""
    url = f"{KONG_PROXY_URL}{path}"
    headers = {
        "Authorization": f"Bearer {credential}"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print(f"SUCCESS! API call to {url} returned status {response.status_code}")
        else:
            print(f"FAILURE! API call to {url} returned status {response.status_code}")
        
        print(f"Response: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"Error calling API: {e}")


def main():
    print("--- DeepSecure API Gateway Integration Example ---")
    
    # Wait for services to be ready
    print("Waiting for services to start... (15s)")
    time.sleep(15)

    # --- Scenario 1: Authorized Access ---
    print("\n--> Scenario 1: Agent requests access to a resource it IS authorized for (/invoices/123)")
    
    # Get a credential specifically for invoice 123
    authorized_resource = "ds:api:invoices/123"
    credential_for_123 = get_fine_grained_credential(authorized_resource, ["read"])

    if credential_for_123:
        print("Making request to Kong with valid credential...")
        call_api_via_kong("/invoices/123", credential_for_123)
    else:
        print("Skipping API call due to failure in getting credential.")


    # --- Scenario 2: Unauthorized Access ---
    print("\n--> Scenario 2: Agent attempts to access a resource it is NOT authorized for (/invoices/456)")
    print("Using the SAME credential to access a different resource...")

    if credential_for_123:
        print("Making request to Kong with credential for wrong resource...")
        # Attempt to use the credential for invoice 123 to access invoice 456
        call_api_via_kong("/invoices/456", credential_for_123)
    else:
        print("Skipping API call as we could not get the initial credential.")


if __name__ == "__main__":
    main()


