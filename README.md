# DeepSecure

[![PyPI version](https://badge.fury.io/py/deepsecure.svg)](https://badge.fury.io/py/deepsecure)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
<!-- TODO: Add build status badge e.g., [![Build Status](https://img.shields.io/github/actions/workflow/status/DeepTrail/deepsecure/main.yml?branch=main)](https://github.com/DeepTrail/deepsecure/actions) -->
<!-- TODO: Add code coverage badge -->

Secure your AI agent ecosystem with DeepSecure. DeepSecure offers tools and a framework for establishing strong agent identities, issuing dynamic, short-lived credentials based on verifiable signatures, and laying the foundation for comprehensive security governance. Move beyond risky static secrets and embrace a modern, identity-centric approach to protecting your AI agent operations.

## Why DeepSecure?

Building and deploying AI agents presents unique security challenges, especially around managing their identities and access to sensitive resources. DeepSecure (in conjunction with its backend `credservice`) helps you:

*   🛡️ **Enhance Agent Security:** Replace static, long-lived secrets with dynamic, short-lived, cryptographically signed credentials, significantly reducing the attack surface and the risk of credential leakage.
*   🆔 **Establish Strong Agent Identities:** Explicitly register and manage each AI agent with a unique, verifiable Ed25519-based identity.
*   🔑 **Secure Private Key Storage:** Agent long-term private keys are stored securely in your system's keyring (e.g., macOS Keychain, Freedesktop Secret Service, Windows Credential Manager), not in plaintext files.
*   ⚙️ **Simplify Credential Management:** Easily issue and manage the lifecycle of credentials agents need to interact with your backend services (`credservice`), ensuring credentials are only valid for the necessary scope and duration.
*   🔍 **Improve Auditability (Foundation):** By ensuring agents have distinct identities and use signed requests for credentials, you lay the groundwork for more comprehensive auditing of agent actions. (Full audit trail features are part of the roadmap).
*   🧑‍💻 **Facilitate Secure Development:** Provides developers with command-line tools and underlying Python components to integrate security best practices directly into their AI agent development workflow.

For a deeper dive into the project's vision, see the [Comprehensive Agent Security and Governance Platform Vision](docs/design/deepsecure-cli-comprehensive-agent-security-and-governance-platform.md) and [Secretless Identity & Authentication for AI Agents](docs/design/deepsecure-identity-authentication-for-ai-agents-architecture-design-guidance.md).

## Key Features (v0.1.4)

*   **Agent Identity Management (`deepsecure agent ...`):**
    *   `register`: Explicitly register new AI agents with the `credservice` backend.
        *   Automatically generates a local Ed25519 key pair if no public key is provided.
        *   Securely stores the generated private key in the system keyring.
        *   Saves public metadata (ID, name, public key) to a local JSON file.
        *   Supports registration using an externally provided public key (private key managed by user).
    *   `list`: List locally known identities and agents registered with `credservice`. Supports table, JSON, and text output.
    *   `describe <agent_id>`: Show detailed information for a specific agent, combining backend data and local identity information (including fingerprint and keyring status).
    *   `delete <agent_id>`: Deactivate agents (soft delete) in `credservice` and optionally purge local keys/metadata from file and keyring. Includes an option to attempt revocation of associated credentials (backend logic for actual revocation is on the roadmap).
*   **Dynamic Credential Issuance (`deepsecure vault issue ...`):**
    *   Issue short-lived, scoped credentials for registered agents.
    *   Requires `--agent-id` for identifying the signing agent.
    *   Performs client-side signing of credential requests using the agent's private key (retrieved from the system keyring).
    *   Communicates with a `credservice` backend that performs mandatory signature verification.
*   **Credential Lifecycle Management (`deepsecure vault ...`):**
    *   `revoke`: Revoke active credentials via `credservice`.
    *   `rotate`: Rotate an agent's long-term identity key (notifies `credservice` of the new public key).
*   **Configuration Management (`deepsecure configure ...`):**
    *   `set-url`, `get-url`: Manage the URL for the `credservice` backend.
    *   `set-token`, `get-token`, `delete-token`: Securely store and manage the `credservice` API token in the system keyring.
    *   `set-log-level`: Manage CLI logging verbosity.
    *   `show`: Display current CLI configuration.
*   **Core Python Components (for library use and CLI foundation):**
    *   `IdentityManager`: Handles local agent identity creation, loading (with keyring for private keys), listing, and deletion.
    *   `KeyManager`: Manages cryptographic key pair generation and signing operations.
    *   `AgentClient`: Client for DeepSecure to interact with `credservice` agent management APIs.
    *   `VaultClient`: Client for DeepSecure to interact with `credservice` vault APIs (handles client-side signing for credential issuance).
    *   Custom Pydantic schemas and exceptions for robust API interaction.

## Installation

### Prerequisites
*   Python 3.9+
*   `pip` (Python package installer)
*   **Docker and Docker Compose** (for running the backend `credservice`)
*   For secure storage of agent private keys and the `credservice` API token, a system keyring backend should be available:
    *   **macOS:** Usually works out-of-the-box (uses Keychain).
    *   **Windows:** Usually works out-of-the-box (uses Windows Credential Manager).
    *   **Linux:** Often requires setup. Common backends include `SecretService` (requires a D-Bus service like `gnome-keyring-daemon` or `keepassxc`) or `KWallet`. You may need to install Python packages like `keyrings.alt` or `secretstorage`. `deepsecure` will raise an error during operations requiring secure key storage if a backend is not found.

### From PyPI (Recommended)
The easiest way to install DeepSecure (version 0.1.4) is from PyPI:
```bash
pip install deepsecure==0.1.4
```

To verify installation:
```bash
deepsecure version
```

### From Source
For development or to contribute:
```bash
git clone https://github.com/DeepTrail/deepsecure.git
cd deepsecure
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

## Quick Start

Here's a quick example of how to get started with `deepsecure`, using a Dockerized `credservice` backend.

1.  **Start the `credservice` backend using Docker Compose:**
    Open a terminal, navigate to the `credservice` directory within your cloned `deepsecure` repository, and run:
    ```bash
    cd credservice
    docker-compose up -d
    cd ..
    ```
    This command will build the `credservice` Docker image (the first time) and start both the `credservice` application and its PostgreSQL database in the background.
    *   `credservice` will be available at `http://localhost:8001`.
    *   The default API token for `credservice` (as set in `credservice/docker-compose.yml`) is `DEFAULT_QUICKSTART_TOKEN`.

2.  **Configure the CLI to connect to your `credservice`:**
    *(You only need to do this once, or when your `credservice` details change.)*
    ```bash
    # Set the URL of your credservice instance
    deepsecure configure set-url http://localhost:8001

    # Securely store your credservice API token
    # When prompted, enter: DEFAULT_QUICKSTART_TOKEN
    deepsecure configure set-token
    ```

3.  **Register a new AI agent:**
    This command will generate a new Ed25519 key pair for your agent. The private key will be stored securely in your system's keyring, and the public key will be registered with `credservice`.
    ```bash
    deepsecure agent register --name "MyFirstAgent" --description "An agent for quick start testing"
    ```
    *Output will include an `Agent ID` (e.g., `agent-xxxx-xxxx`). Note this ID.*
    ```
    [IdentityManager] Private key for agent agent-xxxx... securely stored/updated in system keyring.
    [IdentityManager] Saved identity metadata for agent-xxxx...
    ✅ Success: Agent 'MyFirstAgent' registered with backend.
      Agent ID: agent-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
      ...
      Local private key stored in system keyring.
      Local public metadata at: /Users/youruser/.deepsecure/identities/agent-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.json
    ```

4.  **Issue a short-lived credential for your agent:**
    Replace `<Your_Agent_ID_Here>` with the actual `Agent ID` from the previous step.
    ```bash
    deepsecure vault issue --scope "database:orders:read" --agent-id "<Your_Agent_ID_Here>" --ttl "5m"
    ```
    *Output will include:*
    ```
    ✅ Success: Credential issued successfully! (Backend)

    Credential details:
    ID: cred-yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy
    Agent ID: <Your_Agent_ID_Here>
    Scope: database:orders:read
    Status: issued
    Issued At: <timestamp>
    Expires At: <timestamp>
      Ephemeral Public Key (b64): <ephemeral_public_key_string>
      Ephemeral Private Key (b64): <ephemeral_private_key_string>
      Warning: Handle the ephemeral private key securely...
    ```
    Your agent can now use these ephemeral credential details to interact with target resources. The ephemeral private key is used for client-side cryptographic operations like establishing a secure channel.

## Integrating with AI Agent Frameworks

DeepSecure's core functionality can be integrated into your AI agent's tools to dynamically fetch short-lived, signed credentials, enhancing security by eliminating static secrets.

**Core Integration Pattern:**

1.  **Agent Registration (Out-of-Band):** Before your AI agent runs, ensure it has a registered identity with `credservice` using `deepsecure agent register`. The agent's private key will be stored in the system keyring of the environment where the agent's code executes. The agent's code will need to know its `agent_id`.
2.  **Dynamic Credential Issuance (In-Tool):** Within your agent's tool, when access to a protected resource is needed, use the `deepsecure` Python library components (`VaultClient` from `deepsecure.core.vault_client`) to call the `issue_credential` method.
3.  **Use Ephemeral Credential:** The tool then uses the `credential_id` and `ephemeral_private_key` to interact with the target resource.

### Conceptual Python Example (using `deepsecure.core.vault_client`)

This snippet illustrates how an agent's tool might use the `VaultClient` (the same one used by the `deepsecure vault issue` CLI command) to fetch a credential.

```python
# Ensure DeepSecure is installed in your agent's Python environment
# and configured to point to your credservice.

# Note: For library usage, ensure your PYTHONPATH includes the DeepSecure project root
# or that DeepSecure is installed as a package.
from deepsecure.core.vault_client import client as deepsecure_vault_client
from deepsecure.exceptions import DeepSecureError # Use the base error for broader catch

# This AGENT_ID must correspond to an agent registered via `deepsecure agent register`
# on the machine where this code is running, so its private key is in the keyring.
AGENT_ID_FOR_TOOL = "agent-xxxxxxxx-your-registered-agent-id"
REQUIRED_SCOPE = "database:orders:read_sensitive"
CREDENTIAL_TTL_STRING = "5m" # e.g., 5 minutes, as expected by CLI's VaultClient

def access_secure_database(query: str) -> str:
    try:
        print(f"Requesting credential for agent '{AGENT_ID_FOR_TOOL}' with scope '{REQUIRED_SCOPE}'...")

        # The vault_client instance is a pre-configured singleton.
        # Its issue_credential method handles loading the private key from keyring,
        # signing, and calling the backend.
        credential_data = deepsecure_vault_client.issue_credential(
            agent_id=AGENT_ID_FOR_TOOL,
            scope=REQUIRED_SCOPE,
            ttl=CREDENTIAL_TTL_STRING
        )

        # credential_data is a dictionary matching the CLI's JSON output for `vault issue`
        credential_id = credential_data.get("credential_id")
        # ephemeral_private_key = credential_data.get("ephemeral_private_key_b64")

        print(f"Successfully obtained credential ID: {credential_id}")

        # Placeholder: Use the credential_id (and potentially ephemeral keys for a secure channel)
        # to make the actual call to the database or internal API.
        # e.g., db_response = db_client.query(query, auth_token=credential_id)

        return f"Database query executed with credential {credential_id}. Result: ... (mocked)"

    except DeepSecureError as e: # Catch base DeepSecureError or more specific ones
        print(f"DeepSecure Error obtaining credential: {e}")
        return f"Failed to execute secure database query due to DeepSecure error."
    except Exception as e:
        print(f"An unexpected error occurred: {type(e).__name__} - {e}")
        return "Failed to execute secure database query."

# Example usage within an agent's tool:
# result = access_secure_database("SELECT * FROM orders WHERE id=123;")
# print(result)
```
**Note:** For frameworks like AutoGen, CrewAI, LangGraph, Google ADK, etc., you would embed similar logic within their respective custom tool/function/node implementations. The key is to replace static secret usage with a call to obtain a dynamic credential via `deepsecure vault issue` (using `--agent-id`) or the Python client as shown.

*(Links to detailed guides for each framework will be added in the `/docs/integrations/` directory as they are developed).*

## Command Overview

DeepSecure provides the following core command groups and commands:

| Command Group | Description                                       | Commands                                                                 | Status      | Core Responsibilities (Current v0.1.4)                                                                                                                                                                                                                                                                |
|---------------|---------------------------------------------------|--------------------------------------------------------------------------|-------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `agent`       | Manage AI agent identities & lifecycle            | `register`, `list`, `describe`, `delete`                                   | Implemented | • Register new agents with `credservice`. <br> • Generate local Ed25519 key pairs, storing private keys in system keyring (service name per agent: `deepsecure_agent-<agent_id_prefix>_private_key`). <br> • Manage local metadata files. <br> • List & describe agents. <br> • Deactivate (soft delete) agents in `credservice` & purge local identity. Prompts for confirmation. |
| `vault`       | Manage secure credentials for AI agents           | `issue`, `revoke`, `rotate`                                              | Implemented | • Issue dynamic, short-lived credentials signed by a registered agent\'s private key (from keyring). Includes `origin_context`. <br> • Revoke active credentials via `credservice`. <br> • Rotate an agent\\\'s long-term identity key (notifies `credservice`).                                                                                              |
| `configure`   | Configure `deepsecure` local settings       | `set-url`, `get-url`, `set-token`, `get-token`, `delete-token`, `set-log-level`, `show` | Implemented | • Manage `credservice` URL. <br> • Securely store/retrieve API token in system keyring. <br> • Manage CLI logging verbosity. <br>• Display current configuration.                 |
| `version`     | Display CLI version                               |                                                                          | Implemented | • Shows the installed version of DeepSecure.                                                                                                                                                                                                                                                                                   |

Use `deepsecure <command-group> --help` or `deepsecure <command-group> <command> --help` for more details on specific commands and their options.

### Understanding `deepsecure vault issue` and Ephemeral Keys

The `deepsecure vault issue` command is a powerful tool for obtaining short-lived, dynamic credentials for your AI agents. It's important to understand its intended usage patterns, especially concerning the handling of the ephemeral private key that is generated as part of the issued credential.

**1. Programmatic Use (Primary Use Case for Ephemeral Credentials):**

The most common and secure way to use ephemeral credentials is for an AI agent or application process to request them programmatically using the `deepsecure` Python library.

*   When your agent's code calls the library function (e.g., `from deepsecure.client import client; client.vault.issue(...)`), it receives a response object (typically a Pydantic model like `CredentialResponse` or a dictionary derived from it). This response **includes the ephemeral private key**.
*   The agent's code should then hold this ephemeral private key in memory for its immediate operational needs, such as establishing a secure mTLS connection or signing a request to a target resource.
*   Crucially, the agent should discard this ephemeral private key once the operation is complete or when the credential itself expires. It should **not** be logged or persisted to disk.

For this primary programmatic use case, the `deepsecure vault issue` CLI command *not* displaying the ephemeral private key in its default text output is a deliberate security measure. A human operator running the CLI typically does not need to see or handle this key if the agent code is managing it correctly.

**2. CLI for Testing, Debugging, and Initial Setup (Secondary Use Cases):**

The `deepsecure vault issue` CLI command serves valuable secondary purposes:

*   **Testing and Debugging `credservice`:** It provides a direct way to test the end-to-end credential issuance flow of your `credservice` backend. You can verify that `credservice` correctly handles signature verification, database interactions, and credential generation logic without needing to write and run a full AI agent. For this, seeing the public attributes of the credential (ID, scope, expiry, ephemeral *public* key) and a success status in the CLI is often sufficient.
*   **Manual "Bootstrapping" or Advanced Debugging (with caution):** In some limited scenarios, a developer might need to manually inspect the full credential, including the ephemeral private key, perhaps to quickly test an agent that expects to receive the full credential details via an environment variable or to debug the raw credential format.

**Reconciling CLI Utility with Security:**

To balance utility with security, `deepsecure vault issue` behaves as follows:

*   **Default Text Output:**
    *   When run without specific output formatting (`deepsecure vault issue ...`), the command **does not display the ephemeral private key**.
    *   Instead, it shows other credential details and a warning: `"Warning: An ephemeral private key was generated. Handle it securely if obtained programmatically. It will not be displayed here."`
    *   This is the recommended mode for most interactive CLI use, as it avoids accidental exposure of the ephemeral private key.

*   **JSON Output (`--output json`):**
    *   When run with `deepsecure vault issue --output json ...`, the command **outputs the complete credential data as a JSON object, including the `ephemeral_private_key_b64`**.
    *   This allows developers or scripts that *explicitly* request the raw JSON data to access the ephemeral private key for legitimate advanced debugging or specific trusted scripting scenarios.
    *   **The responsibility then shifts entirely to the user to handle this JSON output securely**, ensuring the ephemeral private key is not improperly stored, logged, or exposed.

In summary, while the `deepsecure` Python library provides the ephemeral private key to the calling code for programmatic use by agents, the CLI tool prioritizes security in its default output by not displaying it. It offers the `--output json` option for advanced scenarios where a developer consciously decides they need access to the full credential data.

## Security Considerations

*   **`credservice` API Token:** The API token used to authenticate the CLI to the `credservice` backend (`DEEPSECURE_CREDSERVICE_API_TOKEN`) is a powerful secret.
    *   **Recommendation:** Use `deepsecure configure set-token` to store it securely in your system's keyring for local development. Avoid placing it directly in shell profiles or plaintext files.
    *   For headless environments (CI/CD, servers), use secure environment variable injection mechanisms.
*   **Agent Private Keys:** When `deepsecure agent register` generates keys, the private key is stored in your system's keyring. Ensure your system keyring is adequately protected (e.g., by your user login password).
*   **Ephemeral Private Keys:** The `deepsecure vault issue` command outputs an ephemeral private key. This key is highly sensitive and is intended for immediate use by the agent.
    *   **Never log or store this ephemeral private key.**
    *   It should be held in memory by the agent process only for the duration it's needed and then discarded.
*   **Principle of Least Privilege:** Always use narrowly defined scopes when issuing credentials with `deepsecure vault issue --scope ...`.
*   **Short TTLs:** Use the shortest practical Time-To-Live (`--ttl`) for ephemeral credentials.

## Roadmap

DeepSecure aims to be a comprehensive security and governance platform for AI agents. Future development will focus on expanding capabilities in the following areas:

*   **Advanced Audit & Risk Management:**
    *   `deepsecure audit start, tail`: Centralized, queryable audit trails.
    *   `deepsecure risk score, list`: Agent risk scoring and monitoring.
*   **Granular Policy Enforcement:**
    *   `deepsecure policy init, apply, get`: Define and apply runtime policies.
*   **Secure Execution Environments:**
    *   `deepsecure sandbox run`: Isolated environments for agent tasks.
*   **Proactive Security Scanning & Hardening:**
    *   `deepsecure scan local, live`: Credential scanning.
    *   `deepsecure harden server`: Tools for securing MCP server deployments.
*   **Deployment and Operational Tooling:**
    *   `deepsecure deploy secure`: Package and deploy agents securely.
*   **Visibility and Governance Dashboards:**
    *   `deepsecure scorecard`: Security posture assessment.
    *   `deepsecure inventory list`: Discovery of AI services and agent resources.
*   **Enhanced Developer Experience:**
    *   `deepsecure ide init, suggest`: Deeper IDE integration.
    *   Mature, stable Python library facade (e.g., `from deepsecure import DeepSecureClient`).
*   **Feature Enhancements:**
    *   Full implementation of `--revoke-credentials` during `deepsecure agent delete` (including backend logic for revoking credentials).
    *   `deepsecure agent update` command for modifying registered agent details.
    *   Accurate `total` count for pagination in `deepsecure agent list` from backend.

Contributions in these areas are welcome! Please see our [Contributing Guidelines](#contributing).

## Contributing

Contributions are highly welcome to make DeepSecure a robust and comprehensive tool for the community!

1.  **Found a Bug or Have a Feature Request?** Please [open an issue](https://github.com/DeepTrail/deepsecure/issues) on our GitHub repository.
2.  **Want to Contribute Code?**
    *   Please fork the repository and submit a pull request against the `main` or `dev` branch.
    *   Ensure your contributions adhere to good coding practices and include tests where applicable.
    *   For major changes, it's best to open an issue first to discuss your proposed approach.
3.  **Development Setup:** See the [Development](#development) section below.

*(A more detailed `CONTRIBUTING.md` file will be added to outline coding standards, testing procedures, and the contribution workflow.)*

## Development

Setup your development environment:
```bash
# Clone the repository (if not already done)
# git clone https://github.com/DeepTrail/deepsecure.git
# cd deepsecure

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate # On Windows: .venv\Scripts\activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

Run tests:
```