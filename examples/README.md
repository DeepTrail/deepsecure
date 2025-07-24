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
# 1. Start the DeepSecure backend services (Skip if you've already followed the main README)
docker compose up deeptrail-control deeptrail-gateway -d

# 2. Verify both services are running (Skip if you've already verified this)
curl http://localhost:8000/health  # Control plane
curl http://localhost:8002/health  # Gateway

# 3. Configure DeepSecure CLI for dual-service architecture
deepsecure configure set-url http://localhost:8000
deepsecure configure set-gateway-url http://localhost:8002
deepsecure configure set-token  # Use: DEFAULT_QUICKSTART_TOKEN

# 4. Set environment variables (alternative to CLI configuration)
export DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002
export DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN=DEFAULT_QUICKSTART_TOKEN

# 5. Install framework dependencies (for examples 3-6)
pip install 'deepsecure[frameworks]'

# 6. Store test secrets for gateway-proxied API calls
deepsecure vault store example-api-key --value "demo-api-key-12345"
deepsecure vault store openai-api-key --value "sk-demo-openai-key"
deepsecure vault store notion-api-key --value "secret_demo-notion-key"
deepsecure vault store tavily-api-key --value "tvly-demo-tavily-key"
```

**Why Steps 1-2**: These ensure both DeepSecure backend services are running:
- **Control Plane** (`deeptrail-control`): Handles agent identity, authentication, and policies
- **Gateway** (`deeptrail-gateway`): Proxies external API calls with automatic secret injection

**Why Steps 3-4**: The CLI and SDK need to know where both services are running. The gateway enables secure external API calls with automatic secret injection. This is a one-time setup per environment.

**Why Step 5**: Framework dependencies (CrewAI, LangChain) are optional but needed for examples 03-06. Installing `deepsecure[frameworks]` gets everything at once.

**Why Step 6**: These secrets will be automatically injected by the gateway when your agents make external API calls. The gateway handles the secure injection based on agent identity and policies.

**Ready to go!** Now you can run any example below.

## 🌐 Gateway Architecture & Real API Calls

All examples demonstrate **real external API calls** through the DeepSecure gateway. Here's how it works:

### 🔄 How Gateway Routing Works

1. **Agent Makes Request**: Your agent code makes an API call (e.g., to OpenAI)
2. **Gateway Intercepts**: The call is routed through `deeptrail-gateway:8002`
3. **Authentication**: Gateway validates the agent's JWT token
4. **Secret Injection**: Gateway automatically injects the appropriate API key
5. **Policy Enforcement**: Gateway checks agent policies before allowing the call
6. **API Call**: Gateway makes the actual call to the external service
7. **Response**: Gateway returns the response to your agent

### 🔐 Security Benefits You'll See

- **Zero API Key Exposure**: Your agents never see the actual API keys
- **Automatic Secret Rotation**: Gateway handles key rotation without agent changes
- **Fine-Grained Access Control**: Different agents can have different API access levels
- **Complete Audit Trail**: All external API calls are logged with agent identity
- **Policy Enforcement**: Real-time access control based on agent identity

### 🚀 What Makes These Examples Special

Unlike traditional examples that use hardcoded API keys:

- **No API Keys in Code**: All secrets are injected automatically
- **Real External Calls**: Examples make actual HTTP requests to external services
- **Production-Ready Patterns**: Shows how to build secure agents from day one
- **Scalable Architecture**: Same pattern works for 1 agent or 1000 agents

## 📚 Examples Overview

| Example | Status | Framework | Gateway Features | Complexity | Runtime |
|---------|--------|-----------|------------------|------------|---------|
| [01 - Basic Agent & Secrets](#01-basic-agent--secret-management) | ✅ Working | None | Secret Management | Beginner | 30s |
| [02 - Simple Secret Fetch](#02-simple-secret-fetching) | ✅ Working | None | Gateway Routing | Beginner | 15s |
| [03 - CrewAI (Work in Progress)](#03-crewai-with-fine-grained-policies-work-in-progress) | 🚧 Work in Progress | CrewAI | Policy Enforcement | Advanced | N/A |
| [04 - CrewAI (Working)](#04-crewai-integration-working) | ✅ Working | CrewAI | Auto Secret Injection | Intermediate | 45s |
| [05 - LangChain (Work in Progress)](#05-langchain-with-fine-grained-policies-work-in-progress) | 🚧 Work in Progress | LangChain | Policy Enforcement | Advanced | N/A |
| [06 - LangChain (Working)](#06-langchain-integration-working) | ✅ Working | LangChain | Auto Secret Injection | Intermediate | 45s |
| [07 - Agent Communication](#07-multi-agent-communication) | ✅ Working | None | JWT Token Exchange | Advanced | 60s |
| [08 - Gateway Secret Injection Demo](#08-gateway-secret-injection-demo) | ✅ Working | None | Real External API Calls | Intermediate | 45s |

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

### 08 - Gateway Secret Injection Demo
**File**: `08_gateway_secret_injection_demo.py`  
**Purpose**: Comprehensive demonstration of gateway secret injection with real external API calls

**What You'll Learn**:
- How the gateway automatically injects secrets into external API calls
- Real external API calls through the gateway (using httpbin.org)
- Multiple authentication patterns (API keys, Bearer tokens)
- Security benefits of the gateway architecture
- Complete audit trail capabilities

**Expected Behavior**:
- ✅ Initialize DeepSecure client with gateway configuration
- ✅ Create agent identity and store test secrets
- ✅ Make real GET request through gateway with automatic secret injection
- ✅ Make real POST request with bearer token injection
- ✅ Demonstrate security benefits and audit trail
- ✅ Show comparison with traditional hardcoded key approach

**Run Command**:
```bash
python examples/08_gateway_secret_injection_demo.py
```

**Prerequisites**:
- Both `deeptrail-control` and `deeptrail-gateway` services running
- Gateway URL configured: `deepsecure configure set-gateway-url http://localhost:8002`
- Internet connectivity for httpbin.org calls

**Expected Output**:
```
--- DeepSecure Gateway Secret Injection Demo ---

🚀 Step 1: Initializing DeepSecure client...
   ✅ Client initialized successfully.
   🏗️  Control Plane: http://localhost:8000
   🌐 Gateway URL: http://localhost:8002

🤖 Step 2: Creating agent identity 'gateway-demo-agent'...
   ✅ Agent ready: agent-abc123...
   📛 Agent name: gateway-demo-agent

... (Real API calls with automatic secret injection)

✅ GATEWAY SECRET INJECTION DEMO COMPLETED!
```

**Success Criteria**: 
- Real external API calls succeed through the gateway
- Secrets are automatically injected without code exposure
- Complete audit trail is demonstrated
- Multiple authentication patterns work correctly

**Key Features Demonstrated**:
- 🌐 **Real External API Calls**: Makes actual HTTP requests to httpbin.org
- 🔐 **Automatic Secret Injection**: Gateway injects API keys and tokens automatically
- 📊 **Multiple Auth Patterns**: Shows API key and Bearer token injection
- 🛡️ **Zero Key Exposure**: Agent code never sees actual API keys
- 📝 **Audit Trail**: Complete logging of all external API calls
- 🔄 **Scalable Security**: Same pattern works for any external service

---

## 🔗 Delegation Examples (Phase 4: Advanced Features)

The delegation examples demonstrate **enterprise-grade agent-to-agent delegation** using DeepSecure's macaroon-based cryptographic delegation system. These examples showcase production-ready patterns for secure multi-agent workflows.

### 07 - Multi-Agent Communication with Delegation ⭐ UPDATED
**File**: `07_multi_agent_communication.py`  
**Purpose**: **Production-ready agent delegation** with cryptographic macaroons

**What You'll Learn**:
- **Macaroon-based delegation** with cryptographic signatures
- **Time-limited access tokens** with automatic expiration
- **Resource-specific permissions** (read vs write vs execute)
- **Delegation verification** and status checking
- **Advanced failure scenarios** and error handling
- **Multi-level delegation chains** with progressive attenuation

**Key Features**:
- 🔐 **Cryptographic Security**: Unforgeable delegation tokens
- ⏰ **Time Boundaries**: Automatic expiration prevents long-term exposure
- 🎯 **Least Privilege**: Fine-grained permission control
- 📊 **Audit Trail**: Complete delegation tracking
- 🛡️ **Attack Resistance**: Invalid tokens properly rejected

**Run Command**:
```bash
python examples/07_multi_agent_communication.py
```

**Expected Output**:
```
🎯 DeepSecure Advanced Delegation Example
==========================================
🏢 Manager Agent ready. ID: delegation-manager-agent
💰 Finance Agent ready. ID: delegation-finance-agent

🔄 [Manager] Delegating stock analysis for 'MSFT' to Finance Agent...
✅ [Manager] Successfully created delegation token (Macaroon)
📊 [Finance] Starting stock analysis for 'MSFT'
✅ [Finance] Using delegated access for secret:tavily-api-key:search
💹 [Finance] Stock analysis completed for MSFT
🎉 [SUCCESS] Delegation workflow completed successfully!
```

---

### 09 - LangChain Delegation Workflow 🆕
**File**: `09_langchain_delegation_workflow.py`  
**Purpose**: **Secure LangChain agents** with delegation capabilities

**What You'll Learn**:
- **LangChain + DeepSecure integration** patterns
- **Secure tool creation** with delegation validation
- **Multi-agent research workflows** with secure handoffs
- **Agent-specific delegation contexts** and audit trails
- **Research coordination** with time-limited delegations

**Advanced Features**:
- 🤖 **Framework Integration**: Native LangChain compatibility
- 🔄 **Workflow Orchestration**: Research Coordinator → Data Analyst → Report Writer
- 🔧 **Secure Tools**: LangChain tools with delegation checking
- 📋 **Context Tracking**: Comprehensive delegation audit
- ⚡ **Performance Optimized**: Efficient delegation validation

**Run Command**:
```bash
# Install LangChain first
pip install langchain langchain-community

python examples/09_langchain_delegation_workflow.py
```

**Dependencies**: `langchain`, `langchain-community`

---

### 10 - CrewAI Delegation Workflow 🆕
**File**: `10_crewai_delegation_workflow.py`  
**Purpose**: **Secure CrewAI crews** with cryptographic delegation

**What You'll Learn**:
- **CrewAI + DeepSecure integration** for secure crews
- **Multi-phase crew workflows** with delegation handoffs
- **Cross-delegation patterns** between crew members
- **Usage limit enforcement** and permission granularity
- **Comprehensive crew audit trails** and security testing

**Crew Roles**:
- 🏢 **Research Manager**: Coordinates and delegates resources
- 📊 **Market Analyst**: Performs financial data analysis
- 🛡️ **Risk Assessor**: Evaluates investment risks
- 📝 **Report Compiler**: Creates final deliverables

**Run Command**:
```bash
# Install CrewAI first  
pip install crewai

python examples/10_crewai_delegation_workflow.py
```

**Dependencies**: `crewai`

---

### 11 - Advanced Delegation Patterns 🆕
**File**: `11_advanced_delegation_patterns.py`  
**Purpose**: **Enterprise-grade delegation patterns** for complex workflows

**What You'll Learn**:
- **Delegation Chains**: Linear A→B→C→D workflows with attenuation
- **Temporal Delegation**: Business hours and time-window restrictions
- **Emergency Protocols**: Break-glass access with audit requirements
- **Multi-Party Approval**: Requiring multiple approvals before activation
- **Conditional Delegation**: Context-aware delegation with dynamic rules
- **Hierarchical Patterns**: Role-based delegation with inheritance

**Enterprise Scenarios**:
- 💰 **Financial Trading**: Approval chains for high-value trades
- 🚨 **Emergency Access**: Break-glass protocols for critical incidents
- ⏰ **Temporal Access**: Business-hours-only delegation windows
- 🤝 **Multi-Approval**: Requiring 2-of-3 approvals for sensitive resources

**Run Command**:
```bash
python examples/11_advanced_delegation_patterns.py
```

**Key Features**:
- 🔗 **Complex Chains**: Multi-level delegation with progressive restrictions
- ⏰ **Time Controls**: Fine-grained temporal access patterns
- 🚨 **Emergency Protocols**: Secure break-glass with mandatory audit
- 🤝 **Multi-Party Workflows**: Collaborative approval processes
- 📊 **Comprehensive Audit**: Enterprise-grade audit trails

---

### Delegation Security Features

All delegation examples demonstrate these **production-ready security features**:

🔐 **Cryptographic Integrity**
- Macaroon-based tokens with HMAC-SHA256 signatures
- Unforgeable delegation tokens prevent impersonation
- Progressive attenuation enforces least-privilege

⏰ **Temporal Security**  
- Time-based expiration limits exposure windows
- Business-hours restrictions for sensitive resources
- Emergency time limits with automatic revocation

🎯 **Fine-Grained Control**
- Resource-specific permissions (read vs write vs execute)
- Action limitations and usage count restrictions
- Context-aware delegation with dynamic conditions

📊 **Enterprise Audit**
- Complete delegation chain tracking
- Mandatory audit trails for compliance
- Real-time security event monitoring

🛡️ **Attack Resistance**
- Invalid delegation tokens properly rejected
- Expired tokens automatically cleaned up
- Permission violations logged and blocked

---

## 💡 Troubleshooting
A table of common errors and their solutions to help users self-diagnose issues.

| Error Message | Meaning | Solution |
|---------------|---------|----------|
| **Backend Not Running** | `Connection refused`, `Backend URL not set` | Run `docker compose up deeptrail-control deeptrail-gateway -d` |
| **Gateway Connection Failed** | `Gateway unavailable`, `Connection refused :8002` | Verify gateway is running: `curl http://localhost:8002/health` |
| **Permission Errors** | `Unauthorized`, `Invalid token` | Check API token matches deeptrail-control setup |
| **Missing Secrets** | `Secret not found` | Run `deepsecure vault store ...` commands from setup |
| **Gateway Routing Issues** | `External API calls fail`, `Secret injection failed` | Check gateway configuration: `echo $DEEPSECURE_GATEWAY_URL` |
| **Policy Enforcement** | `Access denied`, `Policy violation` | Verify agent has proper policies for external API access |

### Gateway-Specific Troubleshooting

**Problem**: External API calls fail with "Gateway connection failed"  
**Solution**: 
```bash
# Check if gateway is running
curl http://localhost:8002/health

# Verify gateway URL is set
echo $DEEPSECURE_GATEWAY_URL

# Restart gateway if needed
docker compose restart deeptrail-gateway
```

**Problem**: "Secret injection failed" or "API key not found"  
**Solution**:
```bash
# Verify secrets are stored
deepsecure vault list

# Check agent policies
deepsecure policy list

# Test gateway connectivity
curl http://localhost:8002/health
```

**Problem**: "External API calls are blocked"  
**Solution**:
```bash
# Check gateway logs
docker compose logs deeptrail-gateway

# Verify agent authentication
deepsecure agent list

# Check policy enforcement
deepsecure policy list
```

## 📚 Further Reading
1. **Understand [Core Concepts](../docs/README.md)** for a deeper dive
2. **Review [CLI Reference](../docs/cli_reference.md)** for all commands
3. **Review [Backend Setup Guide](../docs/backend-services-setup.md)** for production deployment

## 🎓 Learning Path

**Recommended Order for New Users**:
1. **Start Here**: Example 01 - Learn the basics
2. **Core Concepts**: Example 02 - Master secret fetching
3. **Gateway Features**: Example 08 - See real external API calls and secret injection
4. **Framework Integration**: Example 04 (CrewAI) or 06 (LangChain)
5. **Advanced Delegation**: Example 07 - Multi-agent communication with delegation
6. **Enterprise Patterns**: Example 11 - Advanced delegation patterns

**For Framework-Specific Users**:
- **CrewAI Developers**: Examples 01 → 08 → 04 → 07 → 10 → 11
- **LangChain Developers**: Examples 01 → 08 → 06 → 07 → 09 → 11
- **Multi-Agent Systems**: Examples 01 → 02 → 08 → 07 → 09 → 10 → 11
- **Enterprise Security**: Examples 01 → 02 → 07 → 11
- **Delegation Focus**: Examples 07 → 09 → 10 → 11

## 🔐 Security Notes

- **Never log or print `secret.value`** - Examples show safe handling patterns
- **Secrets have TTL** - Check `secret.expires_at` before use
- **Agent identities are cryptographically secured** - Keys stored in OS keychain
- **Audit trails** - All secret access is logged with agent identity

## 📝 What's Next?

After running these examples:
1. **Read the [SDK Documentation](../docs/README.md)** for comprehensive API reference
2. **Check out [CLI Reference](../docs/cli_reference.md)** for administrative commands
3. **Review [Backend Setup Guide](../docs/backend-services-setup.md)** for production deployment
4. **Explore [Contributing Guide](../CONTRIBUTING.md)** to help improve DeepSecure

## 🆘 Getting Help

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **Documentation**: [Main README](../README.md)

---

**Happy Coding!** 🚀 Your AI agents are now more secure than ever. 