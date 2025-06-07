# DeepSecure: Effortless Identity & Access for AI Agents

<p align="center"><img src="assets/deeptrail_logo.png" width="200"></p>

[![GitHub stars](https://img.shields.io/github/stars/DeepTrail/deepsecure?style=social)](https://github.com/DeepTrail/deepsecure/stargazers)
[![PyPI version](https://badge.fury.io/py/deepsecure.svg)](https://badge.fury.io/py/deepsecure)
[![Python Version](https://img.shields.io/pypi/pyversions/deepsecure)](https://pypi.org/project/deepsecure/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
<!-- TODO: Add Build Status Badge once CI is set up e.g. GitHub Actions -->
<!-- [![Build Status](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/ci.yml) -->
<!-- TODO: Update with your actual repo path for Discussions -->
[![GitHub Discussions](https://img.shields.io/github/discussions/DeepTrail/deepsecure)](https://github.com/DeepTrail/deepsecure/discussions)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/DeepTrail/deepsecure/pulls)

Stop wrestling with auth & scattered API keys. DeepSecure provides Identity-as-Code for your AI agents, giving them unique identity to fetch their own ephemeral credentials programmatically.

🚀 Build AI Agents Faster. Security? Solved.  
You're building rapidly and deploying quickly—but scattered API keys and messy auth logic slow you down.
Why build your agent only for prototype — when you can secure it from prototype to production?

DeepSecure instantly provides your AI agents with secure identities and short-lived credentials — zero friction, zero expertise needed.

✅ Replaces API key chaos & auth boilerplate with secure, programmatic access.  
✅ Instant setup—be secure in minutes.  
✅ Integrates instantly—perfect for LangChain, CrewAI, and more.

## ⚙️ Getting Started

Get fully set up with DeepSecure in under 5 minutes—secure your AI agents instantly!

### Prerequisites

*   Python 3.9+
*   `pip` (Python package installer)
*   Access to an OS keyring (macOS Keychain, Linux Secret Service, Windows Credential Vault) for default secure key storage of agent private keys.
*   **Docker and Docker Compose** for [Running the Credential Service (Backend)](#️-running-the-credential-service-backend).

### Installation

Install DeepSecure using pip:

```bash
pip install deepsecure
```

## 🚀 Quick Start

Get up and running with DeepSecure in minutes!

The `deepsecure` package you just installed is the client. To use it, you also need its backend service running.   
First, let's get the service running.

### 1. Start the `credservice` backend
Before using the SDK or CLI to issue credentials, you need the backend service running.
Refer to the [Running the Credential Service (Backend)](#️-running-the-credential-service-backend) section for detailed instructions.

### 2. Configure the CLI to connect to your `credservice`
*(You only need to do this once, or when your `credservice` details change.)*
```bash
# Set the URL of your credservice instance (default from Docker Compose is http://localhost:8001)
deepsecure configure set-url http://localhost:8001

# Securely store your credservice API token
# When prompted, enter the token (default from Docker Compose: DEFAULT_QUICKSTART_TOKEN)
deepsecure configure set-token
```

### 3. Using the Python SDK (Primary Workflow)

This is the recommended way to integrate DeepSecure into your AI agents. Credentials (especially private keys) are best handled in memory by the agent process.

```python
import asyncio
from deepsecure import register_agent, issue_credential_ext_async
from deepsecure.core.types import CredentialRequestContext, CredentialRequestExt

async def main():
    # Register your agent with a unique, human-readable name.
    # This creates a keypair; the private key is stored in your OS keyring.
    agent_name = "my_billing_agent_001" 
    agent_identity = await register_agent(name=agent_name, auto_generate_keys=True)
    print(f"Agent registered: {agent_identity.id}. Name: '{agent_name}'.")

    # To request a credential, you provide a structured context.
    # This is the SDK equivalent of the CLI's simple '--scope' flag,
    # but allows for richer, more fine-grained authorization details.
    try:
        context = CredentialRequestContext(
            resource_id="billing_api_v1",
            action="read_invoices",
            # origin_context={"ip": "192.168.1.100"} # Optional: for origin-bound credentials
        )
        request_ext = CredentialRequestExt(context=context)

        # Issue an ephemeral credential for the agent by its registered ID
        cred_response = await issue_credential_ext_async(
            agent_id=agent_identity.id,
            request=request_ext,
            ttl=3600 # seconds
        )

        print("\nEphemeral Credential Issued:")
        print(f"  Access Token: {cred_response.access_token[:30]}...")
        print(f"  Public Key (Ephemeral): {cred_response.public_key_ephemeral}")
        # The ephemeral private key is in cred_response.private_key_ephemeral
        # Handle it securely in memory for the agent's operation.
        print("  (Ephemeral Private Key is in response; manage securely in memory)")

    except Exception as e:
        print(f"\nError issuing credential: {e}")
        print("  Ensure credservice is running & CLI/SDK is configured (URL, token).")
```
**Note:** The Python SDK manages agent identity keys. For ephemeral credentials, the SDK returns the full credential (including the private key), which your application code must handle securely (ideally, only in memory for its lifetime).

### 4. Using the DeepSecure CLI (for Testing & Debugging)

The CLI is great for initial setup, testing integrations, and direct management.

**Step 1: Register an Agent (if not done via SDK)**

This command will generate a new Ed25519 key pair for your agent. The private key will be stored securely in your system's keyring, and the public key will be registered with `credservice`.
```bash
deepsecure agent register --name "MyFirstAgent" --description "An agent for quick start testing"
```
*Output will include an `Agent ID` (e.g., `agent-xxxx-xxxx`). Note this ID.*

**Step 2: Issue an Ephemeral Credential**

Replace `<Your_Agent_ID_Here>` with the actual `Agent ID` from the previous step.
```bash
deepsecure vault issue --scope "database:orders:read" --agent-id "<Your_Agent_ID_Here>" --ttl "5m"
```
Your agent can now use these ephemeral credential details to interact with target resources.

**A Note on Scope vs. Context:** The CLI's `--scope` flag (e.g., `"database:orders:read"`) is a simple string format for defining permissions. The SDK's `CredentialRequestContext` provides a more structured way to pass richer authorization data, like `resource_id`, `action`, and `origin_context`. Both are used by the backend to make authorization decisions.

## 🤔 Why DeepSecure? (Stop Wrestling with Auth & Secrets)

As you build AI agents, you'll quickly run into a familiar, two-part problem: how do you give your agents access to other APIs, and how do you prove *which* agent is making the request? The common approach—hardcoding static `API_KEY`s in `.env` files and writing custom auth logic for every interaction—is simple at first, but it quickly becomes a fragile, insecure mess that slows you down.

### The Problem: The Mess of Static Keys & Manual Auth

*   **Leaky Keys & Brittle Auth:** A single leaked key compromises an entire system. Your custom token validation logic becomes another surface to attack and a nightmare to maintain and update across services.
*   **Painful Rotation & No Audit Trail:** Rotating keys is a manual headache. When all agents share a key, you have no idea *which* agent performed an action, making debugging and auditing impossible.
*   **All-or-Nothing Access:** Static keys are often over-privileged. Writing the boilerplate code for fine-grained permissions for every agent and every resource is complex and slows down feature development.
*   **Boilerplate Everywhere:** You end up writing the same authentication and authorization logic over and over for each new service your agent needs to talk to, pulling focus away from your core product.

This problem gets exponentially worse as you add more agents and more services. You end up with a complex, fragile web of hardcoded secrets and repetitive auth code that creates security nightmares and kills development velocity.

```mermaid
graph LR
    subgraph "Before DeepSecure: The Mess"
        Agent1["Agent 1"] -- "API_KEY_DATABASE" --> Database
        Agent2["Agent 2"] -- "API_KEY_DATABASE" --> Database
        Agent1 -- "API_KEY_BILLING" --> BillingAPI
        Agent3["Agent 3"] -- "API_KEY_BILLING" --> BillingAPI
        Agent2 -- "API_KEY_THIRD_PARTY" --> ThirdPartyAPI

        style Agent1 fill:#f9f,stroke:#333,stroke-width:2px
        style Agent2 fill:#f9f,stroke:#333,stroke-width:2px
        style Agent3 fill:#f9f,stroke:#333,stroke-width:2px
    end
```

### The Solution: Programmatic Identity and Access

DeepSecure treats **identity as code**. Instead of managing keys, you manage agents.

1.  **Register Agent:** You give each agent a strong, unique identity that is registered once.
2.  **Request Credential:** When an agent needs to access a resource, it uses its identity to request a temporary, scoped credential from the DeepSecure service.
3.  **Use & Expire:** The agent uses that short-lived credential and it expires automatically.

This workflow eliminates static secrets and custom auth boilerplate, provides a clear audit trail, and lets you build more complex, multi-agent systems securely from the start.

```mermaid
graph TD
    subgraph "The DeepSecure Way: Clean & Scalable"
        Agent1["Agent 1"] -->|"Request Credential"| DeepSecure
        Agent2["Agent 2"] -->|"Request Credential"| DeepSecure
        Agent3["Agent 3"] -->|"Request Credential"| DeepSecure

        DeepSecure -->|"Issue Short-Lived Token"| Agent1
        DeepSecure -->|"Issue Short-Lived Token"| Agent2
        DeepSecure -->|"Issue Short-Lived Token"| Agent3

        Agent1 -->|"Access with Token"| Database
        Agent2 -->|"Access with Token"| BillingAPI
        Agent3 -->|"Access with Token"| ThirdPartyAPI

        style DeepSecure fill:#ccf,stroke:#333,stroke-width:2px
    end
```

By adopting this pattern from day one, you avoid painful architectural rework later and can scale your agent workforce with confidence.

## ✨ Key Features

*   **🤖 Programmatic Identity for Agents:** Stop managing shared secrets. Give every AI agent its own unique, verifiable identity.
*   **🔑 Dynamic Credentials:** Agents can request short-lived, single-purpose credentials on-demand, drastically reducing the risk of leaked static API keys.
*   **💻 Developer-Friendly CLI & SDK:** A simple and intuitive Python SDK and command-line interface for managing agents and credentials.
*   **🛡️ Secure by Default:** Leverages your OS keyring for local private key storage, preventing unencrypted keys from sitting in files.
*   **🌐 Framework Agnostic:** Designed for easy integration with any AI agent framework, including LangChain, CrewAI, and more.
*   **🔌 Pluggable & Open Source:** Easy to deploy and built by the community.

## 🔌 Integrations

DeepSecure is designed to work seamlessly within your existing AI development ecosystem.

### Integrating with AI Agent Frameworks

We aim for effortless integration with popular AI agent frameworks, promoting "secure-by-default" development practices.

*   **Agentic Frameworks (e.g., LangChain, CrewAI, Microsoft Agent Squad, AWS Strands, Google ADK):** We are actively developing `deepsecure.init()` helper functions to make integration a one-line operation. Our vision is to make securing your agents as simple as:

    ```python
    import deepsecure
    deepsecure.init(agent_framework="LangChain")
    # Your agents are now instantly secure—it's that easy!
    ```

*   Check the `deepsecure/integrations` directory in our repository and join the conversation on [GitHub Discussions](https://github.com/DeepTrail/deepsecure/discussions) for the latest status, to request support for new frameworks, or to share your own integration experiences.

_This is an active area of development, and contributions or feedback are highly welcome!_


## 🏗️ How It Works (The Big Picture)

The following diagram illustrates the high-level architecture of DeepSecure and how its components interact:

```mermaid
        graph LR
            subgraph "User Space"
                Developer["Developer/User"]
                AIAgent["AI Agent / Application <br/> (uses DeepSecure SDK)"]
                CLI["DeepSecure CLI"]
            end

            subgraph "Local System"
                SDK["DeepSecure Python SDK"]
                Keyring["OS Keyring <br/> (Agent Private Keys)"]
            end

            subgraph "Backend Infrastructure"
                CredService["DeepSecure credservice <br/> (API Backend)"]
                DB["Database <br/> (Agent Info, Credential Metadata)"]
            end

            Developer -->|"Manages/Uses"| CLI
            Developer -->|"Integrates"| SDK
            AIAgent -->|"Uses"| SDK

            CLI -->|"Manages/Uses"| Keyring
            SDK -->|"Manages/Uses"| Keyring

            CLI -->|"HTTP API Calls <br/> (Agent Mgmt, Credential Issuance)"| CredService
            SDK -->|"HTTP API Calls <br/> (Agent Registration, Credential Issuance)"| CredService

            CredService -->|"Stores/Retrieves Data"| DB
```

*   **Agent Identity:** A persistent, unique identity for each AI agent, backed by a public/private key pair. The agent's primary private key is securely stored (default: OS keyring).
*   **Ephemeral Credentials:** Short-lived credentials (an access token paired with an ephemeral public/private key pair) issued to agents for specific tasks, resources, or interactions.
*   **Secure Key Storage:** DeepSecure prioritizes secure local storage for agent private keys using the operating system's native keyring/keychain by default.
*   **Credential Service (`credservice`):** The backend API service responsible for issuing, validating, and revoking ephemeral credentials. This service runs independently.
*   **Origin Binding:** An optional security feature where ephemeral credentials can be "bound" to specific network origins (e.g., IP address, user agent) from which they are allowed to be used.


## 💻 CLI Command Reference

The `deepsecure` CLI offers commands for agent and credential lifecycle management.

*   Access help: `deepsecure --help`, `deepsecure agent --help`, `deepsecure vault --help`.
*   **Key Agent Commands:**
    *   `register`: Create and register a new agent identity.
    *   `list`: View registered agents.
    *   `describe <agent_id>`: Get details for a specific agent.
    *   `delete <agent_id>`: Deactivate an agent. Use `--purge-local-keys` to also remove its keys from the local OS keyring.
*   **Key Vault Commands:**
    *   `issue`: Request a new ephemeral credential for a registered agent.
    *   `revoke --credential-id <credential_id>`: Revoke an active ephemeral credential.
    *   `rotate <agent-id>`: Rotate the long-lived identity key for a specified agent.

## 🛠️ Running the Credential Service (Backend)

To fully test DeepSecure (issuing credentials via SDK or CLI), the **DeepSecure Credential Service (`credservice`)** must be running. This backend handles credential minting and validation.

The `credservice` is located in the `credservice/` directory of this repository.

**Start the `credservice` backend using Docker Compose:**
Open a terminal, navigate to the `credservice` directory within your cloned `deepsecure` repository, and run:
```bash
cd credservice
docker-compose up -d
cd ..
```
This command will build the `credservice` Docker image (the first time) and start both the `credservice` application and its PostgreSQL database in the background.
*   `credservice` will be available at `http://localhost:8001`.
*   The default API token for `credservice` (as set in `credservice/docker-compose.yml`) is `DEFAULT_QUICKSTART_TOKEN`.

Remember to [configure the CLI to connect to this service](#2-configure-the-cli-to-connect-to-your-credservice).

(Refer to `credservice/README.md` for more detailed setup instructions if available, e.g., for non-Docker setup or advanced configuration.)

## 🛣️ Roadmap & Vision

DeepSecure is on a mission to provide a holistic, developer-centric security platform for the AI agent ecosystem. We're excited about the journey ahead and believe that community collaboration is key to building impactful solutions.

**We're actively seeking your feedback and contributions on our evolving roadmap!**   Here are some key areas we're exploring or currently working on:

*   **Seamless Framework Integrations:** Deepening our support for popular AI agent frameworks (like LangChain, CrewAI, Microsoft - Agent Squad, AWS - Strands Library, Google - Agent Developement Kit ) to make secure development even more intuitive.
*   **Interoperability with Agentic Protocols:** Exploring integrations with emerging AI agent communication standards (e.g., MCP, A2A) to ensure DeepSecure works well within the broader agent ecosystem.
*   **Granular Access Control:** Implementing advanced authorization policies (potentially using Open Policy Agent - OPA) for fine-grained control over agent permissions.
*   **Actionable Audit Trails:** Enhancing our logging capabilities to provide secure, detailed, and easily understandable audit trails for all identity and access events.
*   **Developer Experience Enhancements:**
    *   **Management Dashboard:** Building a user-friendly interface for easier monitoring and management of agents and credentials.
    *   **Expanded Key Management Options:** Investigating support for Hardware Security Modules (HSMs) and other Key Management Services (KMS).
*   **Enterprise System Integration:** Planning future integrations with enterprise Key Management Systems (KMS) and Identity Providers (IdP) for enhanced security and management in corporate environments.

**This roadmap is driven by you!** Your insights, use cases, and contributions are invaluable in shaping the future of DeepSecure. Please share your thoughts, suggestions, and what you'd like to see:

*   **Join the discussion:** Head over to [GitHub Discussions](https://github.com/DeepTrail/deepsecure/discussions) to talk about these roadmap items or propose new ones.
*   **Suggest specific features or report issues:** Use [GitHub Issues](https://github.com/DeepTrail/deepsecure/issues) for more concrete proposals or to let us know if something isn't working as expected.

Let's build a more secure AI future, together!

## 🤝 Contributing

DeepSecure is open source, and your contributions are vital! Help us build the future of AI agent security.

*   🌟 **Star our GitHub Repository!**
*   🐛 **Report Bugs or Feature Requests:** Use [GitHub Issues](https://github.com/DeepTrail/deepsecure/issues).
*   💡 **Suggest Features:** Share ideas on [GitHub Issues](https://github.com/DeepTrail/deepsecure/issues) or [GitHub Discussions](https://github.com/DeepTrail/deepsecure/discussions).
*   📝 **Improve Documentation:** Help us make our guides clearer.
*   💻 **Write Code:** Tackle bugs, add features, improve integrations.

For details on how to set up your development environment and contribute, please see our [Contributing Guide](CONTRIBUTING.md).

## 💬 Community & Support

*   **[GitHub Discussions](https://github.com/DeepTrail/deepsecure/discussions):** The primary forum for questions, sharing use cases, brainstorming ideas, and general discussions about DeepSecure and AI agent security. This is where we want to build our community!
*   **[GitHub Issues](https://github.com/DeepTrail/deepsecure/issues):** For bug reports and specific, actionable feature requests.

We're committed to fostering an open and welcoming community.

## 📜 License

DeepSecure is licensed under the [Apache License 2.0](LICENSE).
