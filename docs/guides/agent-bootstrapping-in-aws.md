# Agent Identity Bootstrapping in AWS

This guide explains how to configure DeepSecure to allow AI agents running in AWS (e.g., on EC2, ECS, or Lambda) to automatically and securely acquire their identity using their native IAM role.

## The "Secret Zero" Problem in Production

Similar to Kubernetes, deploying agents in AWS presents the "Secret Zero" problem. Manually configuring keys on every EC2 instance or in every Lambda function's environment is not secure, scalable, or auditable.

DeepSecure solves this by integrating with AWS Identity and Access Management (IAM), allowing your agent workloads to bootstrap their identity based on the IAM role they are already configured to use.

## The Attestation Model

The attestation flow for AWS is as follows:

1.  **Platform Identity**: AWS provides every compute resource with a way to get a cryptographically signed identity document or token that proves which IAM role it is assuming.
2.  **Attestation Policy**: As an administrator, you create an **Attestation Policy** in DeepSecure. This policy declares, "I trust any AWS workload assuming the IAM role `arn:aws:iam::123456789012:role/MyAgentRole` to act as the agent named `production-data-processor`."
3.  **Bootstrapping**: When your agent starts, the DeepSecure SDK automatically:
    a. Detects it's running in an AWS environment.
    b. Uses the AWS SDK (Boto3) to acquire an identity document from the instance metadata service or environment.
    c. Sends this identity document to the `deeptrail-control` bootstrap endpoint.
4.  **Validation**: `deeptrail-control` validates the identity document and checks if an attestation policy exists that matches the IAM role ARN.
5.  **Identity Issuance**: If validation succeeds, `deeptrail-control` creates a new cryptographic identity for the agent and securely returns the private key directly to the SDK.
6.  **Secure Storage**: The SDK immediately stores this new private key in the local OS keyring. For EC2 instances, this provides a durable cache. For ephemeral environments like Lambda, the key is held in memory for the duration of the execution.

## How to Set It Up

### Step 1: Create an Attestation Policy

Use the DeepSecure CLI to create a policy that links an AWS IAM role to a DeepSecure agent name.

```bash
deepsecure policy attestation create-aws \
  --agent-name "production-data-processor" \
  --role-arn "arn:aws:iam::123456789012:role/MyAgentRole" \
  --description "Policy for the production data processing agent."
```

This command authorizes any AWS workload that can assume this IAM role to become the `production-data-processor` agent.

### Step 2: Configure Your AWS Workload

Ensure your AWS workload (e.g., your EC2 launch template or ECS task definition) is configured to use the IAM role you specified in the policy.

For example, in an **ECS Task Definition**:

```json
{
  "family": "data-processor",
  "taskRoleArn": "arn:aws:iam::123456789012:role/MyAgentRole",
  "containerDefinitions": [
    {
      "name": "agent",
      "image": "your-agent-image:latest",
      "environment": [
        {
          "name": "DEEPSECURE_AGENT_NAME",
          "value": "production-data-processor"
        }
      ]
    }
  ]
}
```

### Step 3: Initialize the SDK in Your Agent Code

Your agent's Python code remains simple. The SDK handles the entire bootstrap flow automatically.

```python
import os
from deepsecure import DeepSecure

# You must have the 'boto3' library installed for this to work
# pip install boto3

# Read the configured agent name from the environment
agent_name = os.environ.get("DEEPSECURE_AGENT_NAME")

# The SDK will automatically perform the AWS bootstrap process
client = DeepSecure(agent_id=agent_name)

print(f"Successfully initialized as agent: {client.agent_id}")
print(f"Identity was sourced from: {client._identity.provider_name}")

# Now you can use the client to access secrets, etc.
# secret = client.vault.get("some-secret-from-vault")
```

With this setup, you have a zero-touch, secure identity provisioning system for your agents in AWS. You have eliminated the need to manage API keys or other secrets for your agents, instead relying on the strong, managed identity foundation of AWS IAM. 