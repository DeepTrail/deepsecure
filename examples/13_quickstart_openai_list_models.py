"""
Quickstart: Programmatic OpenAI "list models" via the DeepSecure Gateway.

What this demonstrates:
- Create an agent identity (keys stored securely in OS keyring)
- Store the OpenAI API key in DeepSecure Vault (admin action)
- Create a minimal policy to allow GET /v1/models for this agent
- Call OpenAI "list models" through the Gateway with secret injection

Prerequisites:
- DeepSecure services running locally (Control Plane :8000, Gateway :8002)
- Admin API token configured via CLI: `deepsecure configure set-token <YOUR_TOKEN>`
- An OpenAI API key available to store in the Vault (env var OPENAI_API_KEY recommended)
"""

import os
import sys
import json

import deepsecure


def main():
    client = deepsecure.Client(silent_mode=True)
    print("Step 0: DeepSecure client created")

    # 1) Create (or fetch) an agent
    agent = client.agents.get_by_name("quickstart-openai-agent", auto_create=True)
    print(f"Step 1: Agent registered and ready: {agent.id} ({agent.name})")
    # Authenticate the agent for control-plane operations (e.g., policy create)
    client.login(agent.id)
    print("Step 2: Agent authenticated")
    # 2) Ensure the OpenAI API key exists in the Vault (admin action required once)
    # We try to read it; if missing, instruct the user to store it via CLI.
    try:
        secret_preview = client.vault.get_secret_admin("openai-api-key")
        if secret_preview and secret_preview.get("name") == "openai-api-key":
            print("Step 3: OpenAI API key found in Vault")
        else:
            raise KeyError
    except Exception:
        print(
            "[INFO] 'openai-api-key' not found in Vault. Store it (admin action):\n"
            "  deepsecure vault store openai-api-key --value \"$OPENAI_API_KEY\" --target-base-url 'https://api.openai.com'",
            file=sys.stderr,
        )
        print("Step 4: OpenAI API key not found in Vault")
    # 3) Create a minimal allow policy for listing models
    policy_name = "allow-openai-list-models"
    existing = client.policy.get_by_name(policy_name)
    if existing and getattr(existing, 'agent_id', None) == agent.id:
        policy = existing
        print(f"Step 5: Policy exists: {policy.id}")
    else:
        policy = client.policy.create(
            name=policy_name,
            agent_id=agent.id,
            actions=["GET"],
            resources=["https://api.openai.com/v1/models"],
            effect="allow",
        )
        print(f"Step 5: Policy created: {policy.id}")
    # 4) Call OpenAI via the gateway
    resp = client.openai.list_models(agent_id=agent.id)
    print(f"Step 6: Gateway response: {resp.status_code}")
    try:
        data = resp.json()
        models = data.get("data", []) if isinstance(data, dict) else []
        print("Num models:", len(models))
        for m in models[:3]:
            model_name = m.get("name") or m.get("id")
            print(f"- {model_name} (id={m.get('id')})")
    except Exception:
        print(resp.text[:300])
        print("Step 7: Gateway response not processed")


if __name__ == "__main__":
    main()

