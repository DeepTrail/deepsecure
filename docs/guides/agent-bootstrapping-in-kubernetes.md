# Agent Identity Bootstrapping in Kubernetes

This guide explains how to configure DeepSecure to allow AI agents running in a Kubernetes cluster to automatically and securely acquire their identity without any manual key distribution.

## The "Secret Zero" Problem in Production

In a local development environment, it's acceptable for a developer to manually create an agent and have its private key stored in their local OS keyring. However, this manual process does not scale to production. You cannot manually SSH into every pod to run `deepsecure agent create`. This is often called the "Secret Zero" or "Day 0" trust problem: how does an application (in this case, an AI agent) securely get its very first secret?

DeepSecure solves this by leveraging the native identity mechanisms of trusted compute platforms like Kubernetes.

## The Attestation Model

The process of proving an agent's workload identity to a trusted authority is called **attestation**. The flow works as follows:

1.  **Platform Identity**: Kubernetes automatically provides every pod with a unique, short-lived identity token (a Service Account Token or SAT).
2.  **Attestation Policy**: As an administrator, you create an **Attestation Policy** in DeepSecure. This policy declares, "I trust any workload running in the `my-app` namespace with the `my-app-agent` service account to act as the agent named `production-billing-agent`."
3.  **Bootstrapping**: When your agent pod starts, the DeepSecure SDK automatically:
    a. Detects it's running in Kubernetes.
    b. Reads the SAT from the pod's filesystem (`/var/run/secrets/kubernetes.io/serviceaccount/token`).
    c. Sends this token to the `deeptrail-control` bootstrap endpoint.
4.  **Validation**: `deeptrail-control` validates the SAT and checks if an attestation policy exists that matches the token's claims (namespace and service account).
5.  **Identity Issuance**: If validation succeeds, `deeptrail-control` creates a new cryptographic identity for the agent and securely returns the private key directly to the SDK.
6.  **Secure Storage**: The SDK immediately stores this new private key in the pod's local keyring for the lifetime of the pod. Subsequent calls will use this cached key, avoiding the bootstrap process on every run.

## How to Set It Up

### Step 1: Create an Attestation Policy

First, use the DeepSecure CLI to create a policy that links a Kubernetes service account to a DeepSecure agent name.

```bash
deepsecure policy attestation create-k8s \
  --agent-name "production-billing-agent" \
  --namespace "my-app" \
  --service-account "my-app-agent" \
  --description "Policy for the production billing agent in the my-app namespace."
```

This command tells DeepSecure that any pod matching this profile is authorized to become the `production-billing-agent`.

### Step 2: Configure Your Kubernetes Deployment

Ensure your Kubernetes deployment `yaml` for your agent specifies the `serviceAccountName` you used in the policy.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: billing-agent-deployment
  namespace: my-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: billing-agent
  template:
    metadata:
      labels:
        app: billing-agent
    spec:
      serviceAccountName: my-app-agent # Must match the policy
      containers:
      - name: agent
        image: your-agent-image:latest
        env:
        - name: DEEPSECURE_AGENT_NAME
          value: "production-billing-agent" # Tell the SDK which agent to be
```

### Step 3: Initialize the SDK in Your Agent Code

In your agent's Python code, you only need to tell the SDK which agent it's supposed to be by reading an environment variable. The SDK handles the rest automatically.

```python
import os
from deepsecure import DeepSecure

# Read the configured agent name from the environment
agent_name = os.environ.get("DEEPSECURE_AGENT_NAME")

# The SDK will automatically perform the bootstrap process on first run
# and use the cached key on subsequent runs.
client = DeepSecure(agent_id=agent_name)

print(f"Successfully initialized as agent: {client.agent_id}")
print(f"Identity was sourced from: {client._identity.provider_name}")

# Now you can use the client to access secrets, etc.
# secret = client.vault.get("my-secret")
```

With this setup, you have achieved a zero-touch, secure identity provisioning system for your agents in Kubernetes. There are no long-lived secrets stored in your environment, and identity is automatically provisioned and rotated based on trusted, platform-native identities. 