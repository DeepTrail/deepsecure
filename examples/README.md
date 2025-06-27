# DeepSecure SDK Examples

Welcome to the DeepSecure SDK examples! These examples demonstrate how to integrate effortlessly secure identity and auth into your AI agent applications using the DeepSecure platform.

## 🎯 Purpose & Target Audience

These examples are designed for **AI developers and engineers** who want to:
- Learn how to secure their AI agents with verifiable identity, short lived credentials, and dynamic auth
- Integrate DeepSecure with popular frameworks like CrewAI and LangChain
- Understand best practices for agent identity and auth
- Get up and running quickly with minimal setup

**Perfect for**: Developers new to DeepSecure, teams evaluating agentic security solutions, anyone building multi-agent systems

## 🚀 Quick Start (5 Minutes)

### Prerequisites
1. **Python 3.9+** installed
2. **Docker** installed and running
3. **DeepSecure package** installed: `pip install deepsecure`

### Setup Steps
```bash
# 1. Start the backend service (Skip if you've already followed the main README)
docker compose -f credservice/docker-compose.yml up -d --build

# 2. Verify service is running (Skip if you've already verified this)
curl http://127.0.0.1:8001/health

# 3. Configure DeepSecure CLI
deepsecure configure set-url http://127.0.0.1:8001
deepsecure configure set-token  # Use: DEFAULT_QUICKSTART_TOKEN

# 4. Install framework dependencies (for examples 3-6)
pip install 'deepsecure[frameworks]'

# 5. Store test secrets
deepsecure vault store example-api-key --value "demo-api-key-12345"
deepsecure vault store openai-api-key --value "sk-demo-openai-key"
deepsecure vault store notion-api-key --value "secret_demo-notion-key"
deepsecure vault store tavily-api-key --value "tvly-demo-tavily-key"
```

**Why Steps 1-2**: These ensure the DeepSecure backend service is running. If you've already followed the [main README](../README.md) setup, you can skip these steps.

**Why Step 3**: The CLI needs to know where your backend service is running and how to authenticate with it. This is a one-time setup per environment.

**Why Step 4**: Framework dependencies (CrewAI, LangChain) are optional but needed for examples 03-06. Installing `deepsecure[frameworks]` gets everything at once.

**Ready to go!** Now you can run any example below.

## 📚 Examples Overview

| Example | Status | Framework | Complexity | Runtime |
|---------|--------|-----------|------------|---------|
| [01 - Basic Agent & Secrets](#01-basic-agent--secret-management) | ✅ Working | None | Beginner | 30s |
| [02 - Simple Secret Fetch](#02-simple-secret-fetching) | ✅ Working | None | Beginner | 15s |
| [03 - CrewAI (Work in Progress)](#03-crewai-with-fine-grained-policies-work-in-progress) | 🚧 Work in Progress | CrewAI | Advanced | N/A |
| [04 - CrewAI (Working)](#04-crewai-integration-working) | ✅ Working | CrewAI | Intermediate | 45s |
| [05 - LangChain (Work in Progress)](#05-langchain-with-fine-grained-policies-work-in-progress) | 🚧 Work in Progress | LangChain | Advanced | N/A |
| [06 - LangChain (Working)](#06-langchain-integration-working) | ✅ Working | LangChain | Intermediate | 45s |
| [07 - Agent Communication](#07-multi-agent-communication) | ✅ Working | None | Advanced | 60s |

---

## 📖 Example Details

### 01 - Basic Agent & Secret Management
**File**: `01_create_agent_and_issue_credential.py`  
**Purpose**: "Hello World" example showing core DeepSecure workflow

**What You'll Learn**:
- Client initialization and configuration
- Agent identity creation with auto_create
- Secret storage and secure retrieval
- Proper secret handling patterns

**Expected Behavior**:
- ✅ Initialize client successfully
- ✅ Create agent identity with auto_create=True
- ✅ Store demo secret if it doesn't exist
- ✅ Fetch secret using agent identity
- ✅ Display security demonstration (6 steps total)

**Run Command**:
```bash
python examples/01_create_agent_and_issue_credential.py
```

**Expected Output**:
```
--- DeepSecure SDK: Basic Agent & Secret Example ---

🚀 Step 1: Initializing DeepSecure client...
   ✅ Client initialized successfully.
   📡 Connected to: http://127.0.0.1:8001

🤖 Step 2: Creating agent identity 'hello-world-agent'...
   ✅ Agent ready: agent-abc123...
   📛 Agent name: hello-world-agent

... (6 steps total)

✅ EXAMPLE COMPLETED SUCCESSFULLY!
```

**Success Criteria**: Completes all 6 steps without errors, shows proper secret handling

**Common Issues**:
- `Backend URL env var DEEPSECURE_CREDSERVICE_URL is not set` → Run setup steps above
- `Connection refused` → Ensure credservice is running with `docker compose up -d`

---

### 02 - Simple Secret Fetching
**File**: `02_sdk_secret_fetch.py`  
**Purpose**: Focused demonstration of secret fetching workflow

**What You'll Learn**:
- Streamlined secret retrieval
- Agent context usage
- Secret object properties and metadata

**Expected Behavior**:
- ✅ Initialize client
- ✅ Create agent identity
- ✅ Fetch existing secret
- ✅ Display secret metadata (not value)

**Run Command**:
```bash
python examples/02_sdk_secret_fetch.py
```

**Prerequisites**: Ensure `openai-api-key` secret exists (created in setup steps)

**Success Criteria**: Successfully fetches secret and displays metadata without errors

---

### 03 - CrewAI with Fine-Grained Policies (Work in Progress)
**File**: `03_crewai_secure_tools.py`  
**Status**: 🚧 **Work in Progress** - Requires policy system implementation

**Purpose**: Advanced CrewAI integration with fine-grained access control  
**Note**: This example demonstrates functionality under development and will show warnings when run.

---

### 04 - CrewAI Integration (Working)
**File**: `04_crewai_secure_tools_without_finegrain_control.py`  
**Purpose**: Practical CrewAI integration that works immediately

**What You'll Learn**:
- Tool factory pattern with dependency injection
- Agent-specific contexts for audit trails
- Secure secret retrieval within CrewAI tools
- Professional integration patterns

**Expected Behavior**:
- ✅ Initialize DeepSecure client
- ✅ Create agent-specific contexts
- ✅ Create secure tools with dependency injection
- ✅ Demonstrate tool factory pattern
- ✅ Show audit trail capabilities

**Run Command**:
```bash
python examples/04_crewai_secure_tools_without_finegrain_control.py
```

**Dependencies**: 
- `pip install 'deepsecure[frameworks]'` (includes CrewAI)
- Secrets: `notion-api-key`, `tavily-api-key` (created in setup)

**Expected Output**:
```
--- DeepSecure CrewAI Integration Example (Permissive Mode) ---
✅ Initializing DeepSecure client...
✅ Ensuring agent 'crew-researcher' exists...
✅ Ensuring agent 'crew-writer' exists...
✅ Secure, agent-specific tools created using factory pattern.
...
✅ CrewAI integration with DeepSecure completed successfully!
```

**Success Criteria**: Tools created successfully, security patterns demonstrated

---

### 05 - LangChain with Fine-Grained Policies (Work in Progress)
**File**: `05_langchain_secure_tools.py`  
**Status**: 🚧 **Work in Progress** - Requires policy system implementation

**Purpose**: Advanced LangChain integration with fine-grained access control  
**Note**: This example demonstrates functionality under development and will show warnings when run.

---

### 06 - LangChain Integration (Working)
**File**: `06_langchain_secure_tools_without_finegrain_control.py`  
**Purpose**: Practical LangChain integration that works immediately

**What You'll Learn**:
- LangChain tool factory pattern
- Secure secret injection into tools
- Agent-specific contexts
- Professional LangChain integration

**Expected Behavior**:
- ✅ Initialize DeepSecure client
- ✅ Create agent-specific contexts
- ✅ Create secure LangChain tools
- ✅ Demonstrate tool factory pattern
- ✅ Show dependency injection patterns

**Run Command**:
```bash
python examples/06_langchain_secure_tools_without_finegrain_control.py
```

**Dependencies**:
- `pip install 'deepsecure[frameworks]'` (includes LangChain Community)
- Secrets: `tavily-api-key`, `notion-api-key` (created in setup)

**Success Criteria**: Tools created successfully, security patterns demonstrated

---

### 07 - Multi-Agent Communication
**File**: `07_multi_agent_communication.py`  
**Purpose**: Advanced agent-to-agent (A2A) communication and token exchange

**What You'll Learn**:
- Agent-to-agent authentication
- JWT token issuance and verification
- Secure inter-agent communication
- Token-based authorization patterns

**Expected Behavior**:
- ✅ Initialize multiple agent identities
- ✅ Issue JWT tokens between agents
- ✅ Verify cryptographic signatures
- ✅ Demonstrate secure A2A communication
- ✅ Show token-based authorization

**Run Command**:
```bash
python examples/07_multi_agent_communication.py
```

**Success Criteria**: Demonstrates successful A2A communication with cryptographic verification

---

## 🔧 Troubleshooting

### Common Issues & Solutions

| Issue | Symptoms | Solution |
|-------|----------|----------|
| **Backend Not Running** | `Connection refused`, `Backend URL not set` | Run `docker compose -f credservice/docker-compose.yml up -d` |
| **Configuration Missing** | `Backend URL env var not set` | Run `deepsecure configure set-url` and `set-token` |
| **Framework Dependencies** | `ModuleNotFoundError: No module named 'crewai'` | Run `pip install 'deepsecure[frameworks]'` |
| **Missing Secrets** | `Secret not found` | Pre-store secrets using setup commands above |
| **Permission Errors** | `Unauthorized`, `Invalid token` | Check API token matches credservice setup |

### Dependency Conflicts

When installing `deepsecure[frameworks]`, you may see warnings like:
```
streamlit 1.32.2 requires protobuf<5,>=3.20, but you have protobuf 5.29.5
```

**For Testing**: These conflicts are generally safe to ignore - examples should still work.

**For Production**: Consider using a virtual environment:
```bash
python -m venv deepsecure-test
source deepsecure-test/bin/activate  # On Windows: deepsecure-test\Scripts\activate
pip install deepsecure
```

### Debug Mode

Enable detailed logging to troubleshoot issues:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

import deepsecure
client = deepsecure.Client()
# Now you'll see detailed API calls and responses
```

## 🎓 Learning Path

**Recommended Order for New Users**:
1. **Start Here**: Example 01 - Learn the basics
2. **Core Concepts**: Example 02 - Master secret fetching
3. **Framework Integration**: Example 04 (CrewAI) or 06 (LangChain)
4. **Advanced Topics**: Example 07 - Multi-agent communication

**For Framework-Specific Users**:
- **CrewAI Developers**: Examples 01 → 04 → 07
- **LangChain Developers**: Examples 01 → 06 → 07
- **Multi-Agent Systems**: Examples 01 → 02 → 07

## 🔐 Security Notes

- **Never log or print `secret.value`** - Examples show safe handling patterns
- **Secrets have TTL** - Check `secret.expires_at` before use
- **Agent identities are cryptographically secured** - Keys stored in OS keychain
- **Audit trails** - All secret access is logged with agent identity

## 📝 What's Next?

After running these examples:
1. **Read the [SDK Documentation](../docs/README.md)** for comprehensive API reference
2. **Check out [CLI Reference](../docs/cli_reference.md)** for administrative commands
3. **Review [Backend Setup Guide](../docs/credservice-setup.md)** for production deployment
4. **Explore [Contributing Guide](../CONTRIBUTING.md)** to help improve DeepSecure

## 🆘 Getting Help

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **Documentation**: [Main README](../README.md)

---

**Happy Coding!** 🚀 Your AI agents are now more secure than ever. 