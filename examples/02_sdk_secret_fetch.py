# examples/02_sdk_secret_fetch.py
import deepsecure
import os

def main():
    """
    Demonstrates the new SDK workflow for fetching a secret.
    
    This example assumes:
    1. The DeepSecure backend (`deeptrail-control`) is running.
    2. The CLI has been configured with `deepsecure configure`.
    3. A secret named 'my-test-api-key' has been stored in the vault, e.g.,
       `deepsecure vault store my-test-api-key --value "super-secret-value"`
    """
    print("--- DeepSecure SDK: Secret Fetch Example ---")
    
    try:
        # 1. Initialize the client. Configuration is loaded automatically.
        print("1. Initializing DeepSecure client...")
        client = deepsecure.Client()
        print("   Client initialized successfully.")

        # 2. Define the agent name for this workflow.
        agent_name = "sdk-secret-fetcher-agent"
        print(f"2. Using agent name: '{agent_name}'")

        # 3. Get a handle for the agent, creating it if it doesn't exist.
        print(f"3. Ensuring agent '{agent_name}' exists (auto_create=True)...")
        # In a real app, you might create the agent once during setup.
        # Here, `auto_create=True` makes the script self-contained and runnable.
        agent = client.agent(agent_name, auto_create=True)
        print(f"   Agent handle retrieved. Agent ID: {agent.id}")

        # 4. Securely fetch the secret.
        secret_name = "my-test-api-key"
        print(f"4. Fetching secret '{secret_name}' for agent '{agent_name}'...")
        secret = client.get_secret(agent.id, secret_name, "/")
        print("   Secret fetched successfully.")

        # 5. Use the secret's value.
        # The secret object itself does not print the value to avoid accidental logging.
        print("\n--- Usage ---")
        print(f"Secret Object: {secret}")
        print(f"Secret Value:  '{secret.value}'")
        print(f"Expires At:    {secret.expires_at.isoformat()}")

        print("\nExample finished successfully.")

    except deepsecure.DeepSecureError as e:
        print(f"\n[ERROR] A DeepSecure error occurred: {e}")
        print("Please ensure the backend is running and configured correctly.")
        
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    # For this example to work, you must first store a secret:
    # deepsecure vault store my-test-api-key --value "super-secret-value"
    # The client will use the configuration from `deepsecure configure`.
    main() 