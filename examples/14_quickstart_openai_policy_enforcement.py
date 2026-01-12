"""
Quickstart: Policy enforcement demo (allow list models, deny chat completions).

What this demonstrates:
- Minimal allow policy bound to an agent
- Successful GET /v1/models and denied POST /v1/chat/completions via the Gateway
- Path-level enforcement using control-plane policies fetched and cached by the gateway

Prerequisites:
- DeepSecure services running locally (Control Plane :8000, Gateway :8002)
- Admin API token configured via CLI: `deepsecure configure set-token <YOUR_TOKEN>`
- An OpenAI API key stored in Vault as 'openai-api-key' (see guidance below)
"""

import sys
import json

import deepsecure


def main():
    client = deepsecure.Client(silent_mode=True)

    # 1) Create (or fetch) an agent
    agent = client.agents.get_by_name("quickstart-openai-policy-agent", auto_create=True)
    print(f"Agent ready: {agent.id} ({agent.name})")
    print("Step 1: Agent created")
    # Authenticate agent for control-plane operations (policy create, etc.)
    client.login(agent.id)
    print("Step 2: Agent authenticated")
    # 2) Ensure the OpenAI API key exists in the Vault (admin action)
    # We try to read it; if missing, instruct the user to store it via CLI.
    try:
        secret_preview = client.vault.get_secret_admin("openai-api-key")
        if secret_preview and secret_preview.get("name") == "openai-api-key":
            print("Found 'openai-api-key' in Vault.")
        else:
            raise KeyError
    except Exception:
        print(
            "[INFO] 'openai-api-key' not found in Vault. Store it (admin action):\n"
            "  deepsecure vault store openai-api-key --value \"$OPENAI_API_KEY\" --target-base-url 'https://api.openai.com'",
            file=sys.stderr,
        )
    print("Step 3: OpenAI API key not found in Vault")
    # 3) Create a restrictive allow policy: ONLY GET /v1/models on api.openai.com
    policy_name = "allow-openai-list-models-policy-enforcement-demo"
    existing = client.policy.get_by_name(policy_name)
    if existing and getattr(existing, "agent_id", None) == agent.id:
        policy = existing
        print(f"Policy exists: {policy.id}")
    else:
        policy = client.policy.create(
            name=policy_name,
            agent_id=agent.id,
            actions=["GET"],
            resources=["https://api.openai.com/v1/models"],
            effect="allow",
        )
        print(f"Policy created: {policy.id}")
    print("Step 4: Policy created")
    # 4A) Allowed call -> list models via helper (GET /v1/models)
    ok_resp = client.openai.list_models(agent_id=agent.id)
    print("list_models status:", ok_resp.status_code)
    try:
        data = ok_resp.json()
        models = data.get("data", []) if isinstance(data, dict) else []
        print("Num models:", len(models))
        for m in models[:3]:
            model_name = m.get("name") or m.get("id")
            print(f"- {model_name} (id={m.get('id')})")
    except Exception:
        print(ok_resp.text[:300])
    print("Step 5: Allowed call -> list models via helper (GET /v1/models)")
    # 4B) Denied call -> GET files (path-level denial: GET allowed, but path not allowed)
    deny_resp = client.gateway.request(
        agent_id=agent.id,
        target_base_url="https://api.openai.com",
        path="/v1/files",
        method="GET",
    )
    print("files_list status:", deny_resp.status_code)
    if deny_resp.status_code == 403:
        print("As expected, access was denied by policy (path not allowed).")
    else:
        print("Unexpected status for denied call:", deny_resp.status_code)
    print("Step 6: Denied call -> GET files (path-level denial: GET allowed, but path not allowed)")

if __name__ == "__main__":
    main()

