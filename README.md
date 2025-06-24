<div align="center">
  <h1 style="display: flex; align-items: center;">
    <img src="assets/deeptrail_logo.png" alt="DeepSecure Logo" height="24" style="transform: translateY(2px);" />
    <span style="margin-left: 15px;">DeepSecure: Effortless Identity & Auth for AI Agents</span>
  </h1>
  <a href="https://pypi.org/project/deepsecure/">
    <img src="https://img.shields.io/pypi/v/deepsecure?style=flat-square" alt="PyPI version"/>
  </a>
  <a href="https://pepy.tech/projects/deepsecure">
    <img src="https://static.pepy.tech/badge/deepsecure" alt="PyPI Downloads"/>
  </a>
  <a href="https://pypi.org/project/deepsecure/">
    <img src="https://img.shields.io/pypi/pyversions/deepsecure?style=flat-square" alt="Python Version"/>
  </a>
  <a href="https://opensource.org/licenses/Apache-2.0">
    <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square" alt="License"/>
  </a>
  <br/>
  <a href="https://github.com/DeepTrail/deepsecure/stargazers">
    <img src="https://img.shields.io/github/stars/DeepTrail/deepsecure?style=flat-square" alt="GitHub stars"/>
  </a>
  <a href="https://github.com/DeepTrail/deepsecure/discussions">
    <img src="https://img.shields.io/github/discussions/DeepTrail/deepsecure?style=flat-square" alt="GitHub Discussions"/>
  </a>
  <a href="https://github.com/DeepTrail/deepsecure/pulls">
    <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square" alt="PRs Welcome"/>
  </a>
  <a href="https://x.com/imaxxs">
    <img src="https://img.shields.io/badge/Follow-Mahendra-blue?style=flat-square&logo=x" alt="Follow on X"/>
  </a>
  <a href="https://x.com/0xdeeptrail">
    <img src="https://img.shields.io/badge/Follow-@0xdeeptrail-blue?style=flat-square&logo=x" alt="Follow on X"/>
  </a>
  <a href="https://www.linkedin.com/company/deeptrail">
    <img src="https://img.shields.io/badge/Follow-DeepTrail-blue?style=flat-square&logo=linkedin" alt="Follow on LinkedIn"/>
  </a>
</div>
<br/>

Stop wrestling with auth & scattered API keys. DeepSecure provides Identity-as-Code for your AI agents, giving them unique identity to fetch their own ephemeral credentials programmatically.

🚀 Build AI Agents Faster. Security? Solved.  
You're building rapidly and deploying quickly—but scattered API keys and messy auth logic slow you down.
Why build your agent only for prototype — when you can secure it from prototype to production?

DeepSecure instantly provides your AI agents with secure identities and short-lived credentials — zero friction, zero expertise needed.

✅ Replaces API key chaos & auth boilerplate with secure, programmatic access.  
✅ Instant setup—be secure in minutes.  
✅ Integrates instantly—perfect for LangChain, CrewAI, and more.

---

**Table of Contents**
- [🤔 Why DeepSecure?](#-why-deepsecure-stop-wrestling-with-auth--secrets)
- [⚙️ Getting Started](#️-getting-started)
- [🚀 Quick Start](#-quick-start)
- [🤝 Contributing](#-contributing)
- [🫂 Community & Support](#-community--support)
- [📜 License](#-license)

---

## 🤔 Why DeepSecure? (Stop Wrestling with Auth & Secrets)

As you build AI agents, you'll quickly run into a familiar, two-part problem:  
1. How do you give your agents access to external APIs securely?  
2. How do you verify *which* agent is making each request?  

The common approach—hardcoding static `API_KEY`s in `.env` files and writing custom auth logic for every interaction—is simple at first, but it quickly becomes a fragile, insecure mess that slows you down.

### The Problem: The Mess of Static Keys & Manual Auth

*   **Leaky Keys & Brittle Auth:** A single leaked key compromises an entire system. Your custom token validation logic becomes another surface to attack and a nightmare to maintain and update across services.
*   **Painful Rotation & No Audit Trail:** Rotating keys is a manual headache. When all agents share a key, you have no idea *which* agent performed an action, making debugging and auditing impossible.
*   **All-or-Nothing Access:** Static keys are often over-privileged. Writing the boilerplate code for fine-grained permissions for every agent and every resource is complex and slows down feature development.
*   **Boilerplate Everywhere:** You end up writing the same authentication and authorization logic over and over for each new service your agent needs to talk to, pulling focus away from your core product.

This problem gets exponentially worse as you add more agents and more services. You end up with a complex, fragile web of hardcoded secrets and repetitive auth code that creates security nightmares and kills development velocity.

Before DeepSecure, agent credentials are a tangled mess. Static, long-lived API keys are often shared between multiple agents and manually embedded in configurations. This is not scalable, creates a high risk of key leakage, and makes auditing nearly impossible.

```mermaid
graph LR
    classDef agentNode fill:#2c3e50,stroke:#1a252f,color:#eee,stroke-width:2px,font-size:12px;
    classDef apiNode fill:#34495e,stroke:#2a3b4d,color:#ddd,stroke-width:2px,font-size:12px;

    subgraph "Before DeepSecure: The Interconnected Mess"
        Agent1["Feedback<br/>Polling Agent"] -- "passes data" --> Agent2["Sentiment<br/>Analysis Agent"]
        Agent2 -- "passes data" --> Agent3["Triage &<br/>Alerting Agent"]

        Agent1 -- "uses DB_CONNECTION_STRING" --> ProductionDB["Production DB"]
        Agent1 -- "uses OPENAI_API_KEY" --> OpenAI["OpenAI API"]
        Agent2 -- "uses OPENAI_API_KEY" --> OpenAI
        Agent3 -- "uses OPENAI_API_KEY" --> OpenAI
        Agent3 -- "uses JIRA_API_TOKEN" --> Jira["Jira API"]
        Agent3 -- "uses SLACK_BOT_TOKEN" --> Slack["Slack API"]
        
        class Agent1,Agent2,Agent3 agentNode;
        class ProductionDB,OpenAI,Jira,Slack apiNode;
    end
```

### The DeepSecure Way: Identity-as-Code

DeepSecure solves this by treating **Identity as Code**. Instead of scattering keys, you give each agent a unique, verifiable identity. Your agents then use this identity to request their own short-lived, narrowly-scoped credentials directly from a central service, just-in-time.

With DeepSecure, each agent has its own identity, fetches its own ephemeral credentials, and access is governed by clear, centralized policies. This is scalable, secure, and fully auditable.

```mermaid
graph TD
    classDef agentNode fill:#16a085,stroke:#117a65,color:#fff,stroke-width:2px;
    classDef clientNode fill:#2980b9,stroke:#216797,color:#fff,stroke-width:2px;
    classDef serviceNode fill:#34495e,stroke:#2a3b4d,color:#ddd,stroke-width:2px;
    classDef dataFlow color:black,font-weight:bold;

    subgraph "With DeepSecure: Secure & Decoupled"
        subgraph "Agent Workflow (Data Passing)"
            direction LR
            PollingAgent["Feedback<br/>Polling Agent"] -->|passes data| AnalysisAgent["Sentiment<br/>Analysis Agent"]
            AnalysisAgent -->|passes data| AlertingAgent["Triage &<br/>Alerting Agent"]
            class PollingAgent,AnalysisAgent,AlertingAgent agentNode;
            linkStyle 0,1 dataFlow;
        end

        subgraph "Secure Credential Fetching (via DeepSecure)"
            Client["DeepSecure<br/>Client"]
            class Client clientNode;
        end
        
        subgraph "External Services"
            direction LR
            ProductionDB["Production DB"]
            OpenAI["OpenAI API"]
            Jira["Jira API"]
            Slack["Slack API"]
            class ProductionDB,OpenAI,Jira,Slack serviceNode;
        end

        PollingAgent -- "requests creds for<br/>DB & OpenAI" --> Client
        AnalysisAgent -- "requests creds for<br/>OpenAI" --> Client
        AlertingAgent -- "requests creds for<br/>OpenAI, Jira & Slack" --> Client

        Client -- "issues ephemeral credentials" --> PollingAgent
        Client -- "issues ephemeral credentials" --> AnalysisAgent
        Client -- "issues ephemeral credentials" --> AlertingAgent

        PollingAgent -.-> ProductionDB
        PollingAgent -.-> OpenAI
        AnalysisAgent -.-> OpenAI
        AlertingAgent -.-> OpenAI
        AlertingAgent -.-> Jira
        AlertingAgent -.-> Slack
    end
```

## ⚙️ Getting Started

Get fully set up with DeepSecure in under 5 minutes—secure your AI agents instantly!

### Prerequisites

*   Python 3.9+
*   `pip` (Python package installer)
*   Access to an OS keyring (macOS Keychain) for default secure key storage of agent private keys.
*   **Docker and Docker Compose** for running the backend service.

<details>
<summary><b>► Click here for backend `credservice` setup instructions</b></summary>

For a complete, step-by-step guide on how to run the backend service, including database setup and Docker commands, please see our [**Credservice Setup Guide**](./docs/credservice-setup.md).

</details>

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
Before using the SDK or CLI to issue credentials, you need the backend service running. For detailed setup instructions, please follow the [**Credservice Setup Guide**](./docs/credservice-setup.md).

### 2. Configure the CLI to connect to your `credservice`
*(You only need to do this once, or when your `credservice` details change.)*
```bash
# Set the URL of your credservice instance (the default from the Setup Guide is http://localhost:8000)
deepsecure configure set-url http://localhost:8000

# Securely store your credservice API token
# When prompted, enter the token (default from Docker Compose: DEFAULT_QUICKSTART_TOKEN)
deepsecure configure set-token
```

### 3. Store a Secret (via CLI)

Next, you'll need to securely store a long-lived secret (like an API key) in the DeepSecure vault. This is typically an administrative task performed once by a privileged AI developer or an admin on the team.

The CLI will securely prompt you for the secret value so it doesn't appear in your shell history.

```bash
# Store your OpenAI API key in the vault
deepsecure vault store OPENAI_API_KEY
```

### 4. For the AI Agent Developer (Primary Workflow)

This is the recommended way to integrate DeepSecure into your AI agents. You should use the **Python SDK** to handle credentials, as it's safest to keep private keys in memory within the agent's process.

The new SDK is fully object-oriented. You start by creating a `Client`. The examples below show the two main patterns for using it.

**Pattern 1: Basic Workflow**
This pattern is explicit and shows the full sequence of creating a client, ensuring an agent identity exists, and then fetching a secret on its behalf.

```python
import deepsecure

# 1. Initialize the client.
client = deepsecure.Client()

# 2. Ensure an agent identity exists, creating it if it doesn't.
#    This returns an Agent object, which is a handle to the identity.
agent = client.agent("my-first-agent", auto_create=True)

# 3. Use the agent's identity to securely fetch a secret.
try:
    api_key_secret = client.get_secret(
        name="OPENAI_API_KEY",
        agent_name=agent.name
    )
    # The .value property gives you the secret. The object itself won't
    # print the value, to prevent accidental logging.
    print(f"Secret fetched! Value starts with: '{api_key_secret.value[:4]}...'")

except deepsecure.DeepSecureError as e:
    print(f"Error: {e}")
```

**Pattern 2: Recommended Workflow (Cleaner & More Scoped)**

For cleaner code, especially when an agent performs multiple actions, create an agent-specific client context using `.with_agent()`.

```python
import deepsecure

# 1. Initialize the main client.
client = deepsecure.Client()

# 2. Create a client scoped specifically to the "my-first-agent" identity.
#    All subsequent calls on `agent_client` act on behalf of this agent.
agent_client = client.with_agent("my-first-agent", auto_create=True)

# 3. Now, you don't need to pass `agent_name` to `get_secret`.
api_key_secret = agent_client.get_secret("OPENAI_API_KEY")

print(f"Secret fetched with agent-specific client! Value starts with: '{api_key_secret.value[:4]}...'")
```

### What's Next?

You've now seen the core workflow! Ready to dive deeper?

- 🐍 **[Python SDK Guide](./docs/README.md)** - Build secure AI agents with our SDK
- 🔧 **[CLI Reference](./docs/cli_reference.md)** - Master the command-line interface  
- ⚙️ **[Backend Setup](./docs/credservice-setup.md)** - Deploy your own credservice
- 🤝 **[Contributing](./CONTRIBUTING.md)** - Help improve DeepSecure

For hands-on examples, explore our [`examples/`](./examples/) directory with LangChain, CrewAI, and multi-agent patterns.

## 🤝 Contributing

DeepSecure is open source, and your contributions are vital! Help us build the future of AI agent security.

🌟 **Star our GitHub Repository!**  
🐛 **Report Bugs or Feature Requests:** Use [GitHub Issues](https://github.com/DeepTrail/deepsecure/issues).  
💡 **Suggest Features:** Share ideas on [GitHub Issues](https://github.com/DeepTrail/deepsecure/issues) or [GitHub Discussions](https://github.com/DeepTrail/deepsecure/discussions).  
📝 **Improve Documentation:** Help us make our guides clearer.  
💻 **Write Code:** Tackle bugs, add features, improve integrations.  

For details on how to set up your development environment and contribute, please see our [Contributing Guide](CONTRIBUTING.md).

## 🫂 Community & Support

**GitHub Discussions:** The primary forum for questions, sharing use cases, brainstorming ideas, and general discussions about DeepSecure and AI agent security. This is where we want to build our community!  
**GitHub Issues:** For bug reports and specific, actionable feature requests.

We're committed to fostering an open and welcoming community.

## 📜 License

This project is licensed under the terms of the [Apache 2.0 License](LICENSE).
