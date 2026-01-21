# Virtual MCP Server: Enterprise Use Cases

**Document Type:** Product Use Cases & Value Propositions  
**Last Updated:** January 2026  
**Status:** Draft

---

## Executive Summary

This document outlines three primary use cases for the Virtual MCP Server pattern, demonstrating how it solves critical enterprise challenges when deploying AI agents at scale. Each use case represents a distinct persona and set of requirements, but all converge on the same architectural solution.

| Use Case | Persona | Core Problem | Virtual MCP Server Solution |
|----------|---------|--------------|----------------------------|
| **Vendor Integration** | AI Agent Vendor | N×M connections, credential handling, attribution | Single gateway connection, delegation tokens, unified audit |
| **MCP Server Rollout** | Enterprise Platform Team | Safe exposure, policy testing, anomaly detection | Registry + sandbox + policy enforcement + circuit breakers |
| **Agent Onboarding** | Enterprise IT + Employees | Control, delegation, accountability, revocation | IdP integration + organization registry + scoped delegation + emergency controls |

---

## Use Case 1: AI Agent Vendor Connecting to Enterprise Tools

### Scenario

An AI agent vendor (e.g., a sales automation startup, customer support AI company, or code assistant provider) needs to integrate their agent product with enterprise customer environments to access CRM, documentation, communication, and internal tools.

### The Problem

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     VENDOR INTEGRATION CHALLENGES                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  AI Agent Vendor                          Enterprise Customer               │
│  ┌──────────────────┐                     ┌──────────────────────────────┐  │
│  │                  │                     │                              │  │
│  │  Sales AI Agent  │ ──── Needs ────────>│  HubSpot (CRM)              │  │
│  │                  │      Access         │  Salesforce (CRM)           │  │
│  │                  │      To:            │  Notion (Docs)              │  │
│  │                  │                     │  Slack (Communication)      │  │
│  │                  │                     │  Google Calendar            │  │
│  │                  │                     │  Internal APIs (47+ total)  │  │
│  └──────────────────┘                     └──────────────────────────────┘  │
│                                                                              │
│  CHALLENGES:                                                                 │
│                                                                              │
│  1. N×M CONNECTION EXPLOSION                                                 │
│     - Vendor must implement OAuth flows for each SaaS service               │
│     - Each enterprise customer has different tool configurations            │
│     - 10 customers × 47 tools = 470 integration points to maintain          │
│                                                                              │
│  2. CREDENTIAL MANAGEMENT NIGHTMARE                                          │
│     - Enterprise must share API keys or OAuth tokens with vendor            │
│     - Tokens stored in vendor's infrastructure = security risk              │
│     - Credential rotation requires coordination with vendor                 │
│                                                                              │
│  3. OVER-PRIVILEGED ACCESS                                                   │
│     - Enterprise gives vendor agent broad, long-lived permissions           │
│     - Agent has access 24/7, even when not performing tasks                 │
│     - No way to scope access to "only during this specific task"            │
│                                                                              │
│  4. ATTRIBUTION GAP                                                          │
│     - Audit logs show: "vendor-agent-001 created contact"                   │
│     - Missing: which user initiated this? what was the context?             │
│     - Compliance team cannot answer: "who is responsible?"                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Stakeholder Requirements

| Stakeholder | Requirements |
|-------------|--------------|
| **AI Agent Vendor** | Simple integration (not 47 OAuth implementations), secure credential handling, clear documentation |
| **Enterprise Security Team** | No long-lived credentials shared externally, full audit trail, ability to revoke instantly |
| **Enterprise Compliance** | Every action attributed to a responsible human, audit reports for SOC2/HIPAA |
| **Enterprise IT** | Control over which tools are accessible, no shadow integrations |
| **End Users** | Ability to delegate their access to the agent, confidence their permissions aren't exceeded |

### Solution: Virtual MCP Server as Enterprise Gateway

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VENDOR INTEGRATION VIA VIRTUAL MCP SERVER                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  AI Agent Vendor                          Enterprise Environment            │
│  ┌──────────────────┐                     ┌──────────────────────────────┐  │
│  │                  │                     │                              │  │
│  │  Sales AI Agent  │                     │  ┌────────────────────────┐  │  │
│  │                  │   Single MCP        │  │  Virtual MCP Server    │  │  │
│  │  ┌────────────┐  │   Connection        │  │  (DeepTrail Gateway)   │  │  │
│  │  │ MCP Client │──┼───────────────────>─┼──│                        │  │  │
│  │  └────────────┘  │   + Delegation      │  │  • Policy enforcement  │  │  │
│  │                  │     Token           │  │  • Token exchange      │  │  │
│  │                  │                     │  │  • Audit logging       │  │  │
│  └──────────────────┘                     │  │  • Tool filtering      │  │  │
│                                           │  └───────────┬────────────┘  │  │
│                                           │              │               │  │
│                                           │              │ Backend       │  │
│                                           │              │ Connections   │  │
│                                           │              ▼               │  │
│                                           │  ┌────────────────────────┐  │  │
│                                           │  │  HubSpot │ Salesforce  │  │  │
│                                           │  │  Notion  │ Slack       │  │  │
│                                           │  │  Calendar│ Internal    │  │  │
│                                           │  └────────────────────────┘  │  │
│                                           └──────────────────────────────┘  │
│                                                                              │
│  KEY PROPERTIES:                                                             │
│                                                                              │
│  ✓ Vendor connects to ONE endpoint (gateway.enterprise.com/mcp)            │
│  ✓ Vendor never receives backend credentials                                │
│  ✓ Gateway exchanges delegation token for backend OAuth tokens              │
│  ✓ All actions logged as "agent on behalf of user via delegation"          │
│  ✓ Delegation tokens expire (hours to days, not months)                     │
│  ✓ Enterprise can revoke delegation instantly                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### The Delegation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DELEGATION-BASED VENDOR ACCESS                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 1: User Connects Services (One-Time Setup)                            │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                              │
│  Sarah (Sales Rep) logs into DeepTrail Console                              │
│      │                                                                       │
│      ├── Clicks "Connect HubSpot" → Browser OAuth flow                      │
│      │   └── Sarah consents on HubSpot consent screen                       │
│      │   └── HubSpot OAuth tokens stored in DeepTrail (not shared)          │
│      │                                                                       │
│      ├── Clicks "Connect Salesforce" → Browser OAuth flow                   │
│      │   └── Salesforce tokens stored in DeepTrail                          │
│      │                                                                       │
│      └── Clicks "Connect Slack" → Browser OAuth flow                        │
│          └── Slack tokens stored in DeepTrail                               │
│                                                                              │
│  STEP 2: User Delegates to Vendor Agent                                      │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                              │
│  Sarah creates delegation for vendor's Sales AI Agent:                       │
│                                                                              │
│  POST /delegations                                                           │
│  {                                                                           │
│    "agent_id": "vendor-sales-agent-001",                                    │
│    "permissions": [                                                          │
│      "hubspot:contacts:read",                                               │
│      "hubspot:contacts:create",                                             │
│      "salesforce:opportunities:read",                                       │
│      "slack:messages:read:channel=sales-team"                               │
│    ],                                                                        │
│    "constraints": {                                                          │
│      "max_contacts_per_day": 100,                                           │
│      "allowed_hours": "09:00-18:00 EST"                                     │
│    },                                                                        │
│    "ttl": "7d",                                                              │
│    "purpose": "Q1 sales outreach campaign"                                  │
│  }                                                                           │
│                                                                              │
│  Returns: Delegation Token (Macaroon with attenuated permissions)           │
│                                                                              │
│  STEP 3: Vendor Agent Operates                                               │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                              │
│  Vendor's Sales AI Agent:                                                    │
│      │                                                                       │
│      ├── Connects to gateway with delegation token                          │
│      ├── Calls tools/list → Sees ONLY: hubspot.*, salesforce.*, slack.*    │
│      ├── Calls hubspot.get_contacts → Gateway validates, forwards           │
│      └── Every action logged as:                                            │
│          "vendor-sales-agent-001 ON BEHALF OF sarah@enterprise.com          │
│           via delegation-xyz123 for purpose: Q1 sales outreach"             │
│                                                                              │
│  STEP 4: Automatic Expiration & Revocation                                   │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                              │
│  • Delegation expires after 7 days automatically                             │
│  • If Sarah's enterprise permissions change → delegation re-evaluated       │
│  • If Sarah leaves company → all her delegations invalidated instantly      │
│  • If security incident → IT clicks "Revoke" → immediate effect             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Results

| Metric | Before Virtual MCP Server | After Virtual MCP Server |
|--------|---------------------------|--------------------------|
| **Vendor integration points** | 47 OAuth flows per customer | 1 gateway connection per customer |
| **Credential exposure** | Vendor holds backend API keys | Vendor never sees backend credentials |
| **Permission model** | Long-lived API keys (months/years) | Time-bounded delegation tokens (hours/days) |
| **Permission scope** | Broad ("all CRM access") | Fine-grained ("read contacts in segment X") |
| **Attribution in audit logs** | "vendor-agent did X" | "vendor-agent did X on behalf of Sarah via delegation-123" |
| **Time to audit agent actions** | 4+ hours (query 47 systems) | 12 seconds (unified audit log) |
| **Revocation speed** | Hours (find all credentials, revoke individually) | Seconds (revoke delegation token) |
| **Blast radius of credential compromise** | All customer data accessible | Only delegated permissions, time-limited |

### Key Security Properties

1. **Credential Isolation**: Vendor agent never receives HubSpot/Salesforce/Slack credentials. Gateway performs token exchange at runtime.

2. **Attenuated Permissions**: Agent permissions ⊆ Delegation permissions ⊆ User permissions ⊆ Role permissions. The chain can only narrow, never widen.

3. **Human Accountability**: Every agent action traces to a responsible human who created the delegation. Compliance can always answer "who approved this?"

4. **Just-in-Time Access**: Agent has permissions only when actively performing delegated tasks. No standing privileges accumulating over time.

5. **Automatic Revocation**: When the delegating user's permissions change (offboarding, role change), dependent delegations are automatically invalidated.

---

## Use Case 2: Enterprise Safely Rolling Out a New MCP Server

### Scenario

An enterprise platform team has built a new MCP server exposing internal capabilities (e.g., financial data API, customer database, internal knowledge base). Before allowing customer agents or third-party vendor agents to access it, they need to validate security policies, test access patterns, and monitor for anomalies.

### The Problem

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MCP SERVER ROLLOUT CHALLENGES                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Platform Team builds:                                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Financial Data MCP Server                                            │   │
│  │  • get_account_balance(account_id)                                    │   │
│  │  • get_transaction_history(account_id, date_range)                    │   │
│  │  • initiate_transfer(from, to, amount)  ← DANGEROUS                  │   │
│  │  • get_customer_pii(customer_id)        ← SENSITIVE                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  QUESTIONS BEFORE PRODUCTION:                                                │
│                                                                              │
│  1. "Which agents should be able to call initiate_transfer?"                │
│     → Need policy framework, not just "allow all or deny all"               │
│                                                                              │
│  2. "What if an agent calls get_transaction_history for all accounts?"      │
│     → Need rate limiting, scope constraints                                 │
│                                                                              │
│  3. "How do we detect if an agent is exfiltrating PII?"                     │
│     → Need anomaly detection, access pattern monitoring                     │
│                                                                              │
│  4. "What if something goes wrong after launch?"                            │
│     → Need circuit breaker, instant rollback                                │
│                                                                              │
│  5. "How do we test policies before they affect real agents?"               │
│     → Need sandbox environment with production-like traffic                 │
│                                                                              │
│  WITHOUT VIRTUAL MCP SERVER:                                                 │
│  • Deploy MCP server directly, hope nothing goes wrong                      │
│  • Manually configure each client agent's access                            │
│  • No unified visibility into who's calling what                            │
│  • Rollback = "turn off the server" (breaking all agents)                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Stakeholder Requirements

| Stakeholder | Requirements |
|-------------|--------------|
| **Platform Team** | Easy registration, hot-reload without restart, clear error messages |
| **Security Team** | Policy testing before production, anomaly detection, PII monitoring |
| **Compliance Team** | Audit trail of all access, data classification awareness |
| **Operations Team** | Circuit breakers, health monitoring, gradual rollout capability |
| **End Users (Agents)** | Seamless access once approved, clear error messages when denied |

### Solution: Staged Rollout via Virtual MCP Server

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STAGED MCP SERVER ROLLOUT                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: REGISTRATION                                                       │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  Platform team registers MCP server with gateway:                            │
│                                                                              │
│  POST /mcp-registry/servers                                                  │
│  {                                                                           │
│    "id": "financial-data-api",                                              │
│    "display_name": "Financial Data API",                                    │
│    "endpoint": "https://internal.corp/mcp/financial",                       │
│    "transport": "http+sse",                                                 │
│    "auth": {                                                                 │
│      "type": "mtls",                                                        │
│      "client_cert": "..."                                                   │
│    },                                                                        │
│    "data_classification": "confidential",                                   │
│    "status": "sandbox"  ← Starts in sandbox, not production                │
│  }                                                                           │
│                                                                              │
│  Gateway automatically:                                                       │
│  • Connects to server, discovers tools via tools/list                       │
│  • Caches tool schemas with namespace prefix: financial.*                   │
│  • Marks all tools as "sandbox only" (not visible to production agents)    │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 2: POLICY CONFIGURATION                                               │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  Security team defines policies:                                             │
│                                                                              │
│  Policy 1: "Agents can read balances for accounts they're assigned"        │
│  {                                                                           │
│    "effect": "allow",                                                       │
│    "resource": "financial.get_account_balance",                             │
│    "condition": "request.params.account_id IN agent.assigned_accounts"      │
│  }                                                                           │
│                                                                              │
│  Policy 2: "Only trusted agents can initiate transfers, max $10k"          │
│  {                                                                           │
│    "effect": "allow",                                                       │
│    "resource": "financial.initiate_transfer",                               │
│    "condition": "agent.trust_level == 'high'",                              │
│    "constraints": { "amount": { "max": 10000 } }                            │
│  }                                                                           │
│                                                                              │
│  Policy 3: "PII access requires explicit delegation + logging"             │
│  {                                                                           │
│    "effect": "allow",                                                       │
│    "resource": "financial.get_customer_pii",                                │
│    "condition": "delegation.includes('pii:read')",                          │
│    "audit_level": "detailed"                                                │
│  }                                                                           │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 3: SANDBOX TESTING (1-2 Weeks)                                       │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  Test agents operate against sandbox:                                        │
│                                                                              │
│  • Real agent traffic (or simulated) flows through gateway                  │
│  • Policies enforced, but in "log + allow" mode for testing                │
│  • All requests logged with would-be-denied vs actually-allowed flags       │
│                                                                              │
│  Gateway produces analytics:                                                 │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Sandbox Report: financial-data-api (7 days)                        │     │
│  │                                                                     │     │
│  │  Total requests: 12,847                                             │     │
│  │  Unique agents: 23                                                  │     │
│  │                                                                     │     │
│  │  Tool Usage:                                                        │     │
│  │  • get_account_balance:     8,234 (64%)  ✓ Normal                  │     │
│  │  • get_transaction_history: 4,102 (32%)  ✓ Normal                  │     │
│  │  • get_customer_pii:          487 (4%)   ⚠ Review: high volume     │     │
│  │  • initiate_transfer:          24 (0.2%) ✓ Normal                  │     │
│  │                                                                     │     │
│  │  Policy Evaluation:                                                 │     │
│  │  • Would allow: 12,234 (95.2%)                                     │     │
│  │  • Would deny:     613 (4.8%)                                      │     │
│  │    └── Reason breakdown:                                           │     │
│  │        • account_id not in assigned: 412                           │     │
│  │        • missing delegation: 156                                   │     │
│  │        • rate limit exceeded: 45                                   │     │
│  │                                                                     │     │
│  │  Anomalies Detected:                                                │     │
│  │  ⚠ Agent "analytics-bot" accessed 2,847 unique account_ids        │     │
│  │    → Flagged for review (unusual breadth)                          │     │
│  │                                                                     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 4: SECURITY REVIEW                                                    │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  Security team reviews sandbox report:                                       │
│                                                                              │
│  ✓ 95.2% allow rate indicates policies are not too restrictive             │
│  ✓ 4.8% deny rate indicates policies are catching unauthorized access      │
│  ⚠ analytics-bot needs investigation → found to be legitimate, update policy│
│  ⚠ High PII access volume → add additional constraint (require reason)     │
│                                                                              │
│  Policy updates applied, re-run sandbox for 3 more days                     │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 5: PRODUCTION PROMOTION                                               │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  PUT /mcp-registry/servers/financial-data-api                               │
│  { "status": "production" }                                                 │
│                                                                              │
│  Gateway immediately:                                                        │
│  • Makes financial.* tools visible to production agents                     │
│  • Enforces policies in deny mode (not just log)                           │
│  • Starts production monitoring and alerting                                │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 6: ONGOING MONITORING + CIRCUIT BREAKER                               │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  If issues detected:                                                         │
│                                                                              │
│  POST /mcp-registry/servers/financial-data-api/circuit-breaker              │
│  { "action": "open", "reason": "Suspected data exfiltration" }              │
│                                                                              │
│  Gateway immediately:                                                        │
│  • Stops routing requests to financial-data-api                             │
│  • Removes financial.* tools from all agents' tools/list                   │
│  • Returns graceful error for in-flight requests                            │
│  • Generates incident alert                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Results

| Metric | Before Virtual MCP Server | After Virtual MCP Server |
|--------|---------------------------|--------------------------|
| **Time to safely expose new MCP server** | Weeks of ad-hoc testing | Structured 1-2 week sandbox with metrics |
| **Policy confidence before go-live** | Guesswork, hope for the best | Data-driven (10,000+ test requests analyzed) |
| **Anomaly detection** | Discovered after breach | Flagged during sandbox testing |
| **Rollback mechanism** | "Turn off the server" (breaks all agents) | Circuit breaker (graceful denial, agents continue working with other tools) |
| **Policy iteration cycle** | Deploy, discover issue, rollback, fix, redeploy | Test in sandbox, refine, promote |
| **Visibility into access patterns** | Scattered logs across systems | Unified dashboard per MCP server |

### Rollout Checklist

- [ ] **Register** MCP server with gateway (status: sandbox)
- [ ] **Define policies** for each tool (allow/deny conditions, constraints)
- [ ] **Configure data classification** (public, internal, confidential, restricted)
- [ ] **Run sandbox traffic** for minimum 7 days
- [ ] **Review analytics** — allow/deny rates, unique agents, anomalies
- [ ] **Address anomalies** — investigate flagged patterns, update policies
- [ ] **Re-test** after policy changes (minimum 3 days)
- [ ] **Security sign-off** — documented approval with policy snapshot
- [ ] **Promote to production** — change status, enable production monitoring
- [ ] **Set up alerts** — unusual volume, new agents, policy violations
- [ ] **Document circuit breaker procedure** — who can trigger, escalation path

---

## Use Case 3: Enterprise Securely Onboarding AI Agents for Employees

### Scenario

An enterprise IT team needs to enable employees to use AI agents (for productivity, automation, analysis) while maintaining security, compliance, and accountability. Employees should be able to connect agents to enterprise tools, but only within IT-approved boundaries.

### The Problem

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EMPLOYEE AGENT ONBOARDING CHALLENGES                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  WHAT EMPLOYEES WANT:                                                        │
│  • Use AI agents to automate repetitive tasks                               │
│  • Connect agents to CRM, docs, calendar, communication tools               │
│  • Delegate their access to agents without IT tickets for each tool         │
│                                                                              │
│  WHAT IT TEAMS FEAR:                                                         │
│                                                                              │
│  1. SHADOW AI                                                                │
│     "Employees connecting random AI tools to company data"                  │
│     → Unapproved agents with unknown security posture                       │
│     → Data flowing to unknown third-party services                          │
│                                                                              │
│  2. OVER-DELEGATION                                                          │
│     "Employee gives agent 'admin' access to everything"                     │
│     → Agent has more permissions than needed for the task                   │
│     → Blast radius if agent is compromised                                  │
│                                                                              │
│  3. ACCOUNTABILITY GAP                                                       │
│     "Agent did something wrong, but who set it up?"                         │
│     → Cannot trace agent actions back to responsible human                  │
│     → Compliance audit fails                                                │
│                                                                              │
│  4. ZOMBIE AGENTS                                                            │
│     "Employee left, but their agents still have access"                     │
│     → No automatic revocation on offboarding                                │
│     → Dormant agents with valid credentials                                 │
│                                                                              │
│  5. NO EMERGENCY STOP                                                        │
│     "Agent is misbehaving, how do we stop it NOW?"                          │
│     → Must find and revoke credentials across multiple systems              │
│     → Takes hours during an active incident                                 │
│                                                                              │
│  WITHOUT GOVERNANCE:                                                         │
│  • IT says "no AI agents" → employees work around it                        │
│  • IT says "yes" without controls → security incidents                      │
│  • No middle ground between "forbidden" and "uncontrolled"                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Stakeholder Requirements

| Stakeholder | Requirements |
|-------------|--------------|
| **Employees** | Self-service agent registration, easy tool connection, minimal friction |
| **IT Security** | Approved agent/tool lists only, scoped permissions, audit trail |
| **IT Operations** | Central visibility, emergency controls, IdP integration |
| **Compliance** | Human accountability, automatic revocation, exportable audit logs |
| **Management** | Productivity gains without security incidents |

### Solution: IT-Governed Agent Onboarding

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IT-GOVERNED AGENT ONBOARDING FLOW                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  IT ADMIN PRE-CONFIGURATION (One-Time Setup)                            ││
│  ├─────────────────────────────────────────────────────────────────────────┤│
│  │                                                                          ││
│  │  1. Configure Organization MCP Registry                                  ││
│  │     ┌──────────────────────────────────────────────────────────────┐    ││
│  │     │  Approved MCP Servers for "Acme Corp"                         │    ││
│  │     │                                                               │    ││
│  │     │  ✓ hubspot-mcp         (CRM)           - Sales, Marketing    │    ││
│  │     │  ✓ notion-mcp          (Docs)          - All employees       │    ││
│  │     │  ✓ slack-mcp           (Communication) - All employees       │    ││
│  │     │  ✓ calendar-mcp        (Scheduling)    - All employees       │    ││
│  │     │  ✓ internal-kb-mcp     (Knowledge)     - All employees       │    ││
│  │     │  ✗ financial-data-mcp  (Finance)       - Finance only        │    ││
│  │     │  ✗ hr-records-mcp      (HR)            - HR only             │    ││
│  │     └──────────────────────────────────────────────────────────────┘    ││
│  │                                                                          ││
│  │  2. Define Maximum Delegable Permissions by Role                         ││
│  │     ┌──────────────────────────────────────────────────────────────┐    ││
│  │     │  Role: "Sales Rep"                                            │    ││
│  │     │  Can delegate to agents:                                      │    ││
│  │     │  • hubspot:contacts:read, hubspot:contacts:create            │    ││
│  │     │  • hubspot:deals:read, hubspot:deals:update                  │    ││
│  │     │  • slack:messages:read, slack:messages:send                  │    ││
│  │     │  • calendar:events:read, calendar:events:create              │    ││
│  │     │  Cannot delegate:                                             │    ││
│  │     │  • hubspot:contacts:delete (destructive)                     │    ││
│  │     │  • hubspot:settings:* (admin)                                │    ││
│  │     └──────────────────────────────────────────────────────────────┘    ││
│  │                                                                          ││
│  │  3. Configure IdP Integration                                            ││
│  │     • Sync users from Okta/Azure AD                                     ││
│  │     • Map IdP groups → DeepTrail roles                                 ││
│  │     • Enable automatic revocation on user deactivation                  ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  EMPLOYEE SELF-SERVICE ONBOARDING                                       ││
│  ├─────────────────────────────────────────────────────────────────────────┤│
│  │                                                                          ││
│  │  STEP 1: Employee Authenticates                                          ││
│  │  ─────────────────────────────────────────────────────────────────────  ││
│  │                                                                          ││
│  │  Sarah (Sales Rep) → SSO Login via Okta → DeepTrail Console            ││
│  │                                                                          ││
│  │  DeepTrail knows:                                                       ││
│  │  • Sarah's identity (sarah@acme.com)                                    ││
│  │  • Sarah's role (Sales Rep)                                             ││
│  │  • Sarah's maximum delegable permissions (from role config)             ││
│  │                                                                          ││
│  │  ─────────────────────────────────────────────────────────────────────  ││
│  │  STEP 2: Employee Registers Agent                                        ││
│  │  ─────────────────────────────────────────────────────────────────────  ││
│  │                                                                          ││
│  │  Sarah clicks "Register New Agent"                                       ││
│  │  ┌────────────────────────────────────────────────────────────────┐     ││
│  │  │  Agent Name: "My Sales Assistant"                               │     ││
│  │  │  Agent Type: [Vendor Agent ▼]                                   │     ││
│  │  │  Vendor: [SalesBot Inc ▼] (from approved vendor list)          │     ││
│  │  │  Purpose: "Automate lead follow-up and meeting scheduling"     │     ││
│  │  │                                                                 │     ││
│  │  │  [ Register Agent ]                                             │     ││
│  │  └────────────────────────────────────────────────────────────────┘     ││
│  │                                                                          ││
│  │  Agent gets unique identity: agent-sarah-salesassist-001                ││
│  │  Registered as: "Owned by sarah@acme.com"                               ││
│  │                                                                          ││
│  │  ─────────────────────────────────────────────────────────────────────  ││
│  │  STEP 3: Employee Connects Services                                      ││
│  │  ─────────────────────────────────────────────────────────────────────  ││
│  │                                                                          ││
│  │  Sarah sees only IT-approved services for her role:                      ││
│  │  ┌────────────────────────────────────────────────────────────────┐     ││
│  │  │  Available Services:                                            │     ││
│  │  │                                                                 │     ││
│  │  │  [x] HubSpot CRM      [Connect] ← Browser OAuth                │     ││
│  │  │  [ ] Salesforce       [Connect]                                 │     ││
│  │  │  [x] Slack            [Connect] ← Browser OAuth                │     ││
│  │  │  [x] Google Calendar  [Connect] ← Browser OAuth                │     ││
│  │  │  [ ] Notion           [Connect]                                 │     ││
│  │  │                                                                 │     ││
│  │  │  🔒 Financial Data API - Not available for your role           │     ││
│  │  └────────────────────────────────────────────────────────────────┘     ││
│  │                                                                          ││
│  │  Sarah's OAuth credentials stored in DeepTrail (never shared)          ││
│  │                                                                          ││
│  │  ─────────────────────────────────────────────────────────────────────  ││
│  │  STEP 4: Employee Delegates to Agent                                     ││
│  │  ─────────────────────────────────────────────────────────────────────  ││
│  │                                                                          ││
│  │  Sarah configures what agent can do:                                     ││
│  │  ┌────────────────────────────────────────────────────────────────┐     ││
│  │  │  Delegate Permissions to "My Sales Assistant":                  │     ││
│  │  │                                                                 │     ││
│  │  │  HubSpot:                                                       │     ││
│  │  │  [x] Read contacts                                              │     ││
│  │  │  [x] Create contacts                                            │     ││
│  │  │  [ ] Update contacts  ← Sarah chose not to enable              │     ││
│  │  │  [🔒] Delete contacts ← Not available (role restriction)       │     ││
│  │  │                                                                 │     ││
│  │  │  Slack:                                                         │     ││
│  │  │  [x] Read messages in #sales-team                               │     ││
│  │  │  [x] Send messages (DM only)                                    │     ││
│  │  │                                                                 │     ││
│  │  │  Calendar:                                                      │     ││
│  │  │  [x] Read my calendar                                           │     ││
│  │  │  [x] Create meetings                                            │     ││
│  │  │                                                                 │     ││
│  │  │  Expiration: [7 days ▼]                                        │     ││
│  │  │                                                                 │     ││
│  │  │  [ Create Delegation ]                                          │     ││
│  │  └────────────────────────────────────────────────────────────────┘     ││
│  │                                                                          ││
│  │  Agent receives delegation token → begins operating                      ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  ONGOING GOVERNANCE                                                      ││
│  ├─────────────────────────────────────────────────────────────────────────┤│
│  │                                                                          ││
│  │  AUTOMATIC REVOCATION TRIGGERS:                                          ││
│  │                                                                          ││
│  │  ┌────────────────────────────────────────────────────────────────┐     ││
│  │  │  Trigger                    │  Result                          │     ││
│  │  │  ─────────────────────────────────────────────────────────────│     ││
│  │  │  Delegation TTL expires     │  Agent loses access automatically│     ││
│  │  │  Sarah deactivated in Okta  │  All Sarah's delegations void    │     ││
│  │  │  Sarah's role changes       │  Delegations re-evaluated        │     ││
│  │  │  HubSpot OAuth revoked      │  Agent can't use HubSpot tools  │     ││
│  │  │  IT revokes delegation      │  Immediate effect                │     ││
│  │  │  Vendor agent removed       │  All delegations to it void      │     ││
│  │  └────────────────────────────────────────────────────────────────┘     ││
│  │                                                                          ││
│  │  IT ADMIN EMERGENCY CONTROLS:                                            ││
│  │                                                                          ││
│  │  ┌────────────────────────────────────────────────────────────────┐     ││
│  │  │  Admin Console: Agent Management                                │     ││
│  │  │                                                                 │     ││
│  │  │  Search: [agent-sarah-salesassist-001__________]  [Search]     │     ││
│  │  │                                                                 │     ││
│  │  │  ┌──────────────────────────────────────────────────────────┐  │     ││
│  │  │  │  Agent: agent-sarah-salesassist-001                      │  │     ││
│  │  │  │  Owner: sarah@acme.com                                   │  │     ││
│  │  │  │  Vendor: SalesBot Inc                                    │  │     ││
│  │  │  │  Status: Active ●                                        │  │     ││
│  │  │  │  Last active: 2 minutes ago                              │  │     ││
│  │  │  │  Actions today: 847                                      │  │     ││
│  │  │  │                                                          │  │     ││
│  │  │  │  [ Suspend Agent ]  [ Revoke All Delegations ]           │  │     ││
│  │  │  │  [ View Audit Log ] [ Contact Owner ]                    │  │     ││
│  │  │  └──────────────────────────────────────────────────────────┘  │     ││
│  │  │                                                                 │     ││
│  │  │  GLOBAL CONTROLS:                                               │     ││
│  │  │  [ Suspend All Vendor Agents ]  ← Incident response            │     ││
│  │  │  [ Disable All Delegations ]    ← Nuclear option               │     ││
│  │  └────────────────────────────────────────────────────────────────┘     ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Results

| Requirement | How Virtual MCP Server Delivers |
|-------------|--------------------------------|
| **IT controls available tools** | Organization MCP Registry: only IT-approved servers appear in employee's console |
| **Scoped delegation** | Delegation tokens enforce: agent permissions ⊆ user-selected ⊆ role max ⊆ user permissions |
| **No shadow AI** | Agents must be registered; unregistered agents can't get delegation tokens |
| **Human accountability** | Every agent action logged as: `agent-X on behalf of employee-Y via delegation-Z` |
| **Automatic revocation on offboarding** | IdP integration: when employee deactivated, all their delegation tokens immediately invalidated |
| **Role change handling** | Policy re-evaluation: if employee loses CRM access, agent's CRM tools disappear from next `tools/list` |
| **Emergency circuit breaker** | One-click "suspend agent" in admin console → all requests denied, audit event generated |
| **Compliance audit** | Single query: "Show all actions by employees in Finance department's agents in Q4" |

### Metrics: Before vs. After

| Metric | Before Governance | After Virtual MCP Server |
|--------|-------------------|--------------------------|
| **Agent onboarding time** | Days (IT approval, manual credential distribution) | Minutes (self-service with guardrails) |
| **Shadow AI risk** | Unknown agents connecting to data | All agents registered, visible in console |
| **Permission sprawl** | Agents accumulate permissions over time | Permissions expire with TTL, automatically pruned |
| **Offboarding completeness** | Manual audit to find all agent access | Automatic: IdP deactivation → all delegations void |
| **Time to suspend misbehaving agent** | Hours (find all credentials, revoke one by one) | Seconds (single circuit breaker toggle) |
| **Audit query: "What did this person's agents do?"** | 4+ hours (query 47 systems) | 12 seconds (unified audit log) |
| **Compliance report generation** | Days of manual log aggregation | Automated reports from unified audit trail |

### Employee Onboarding Checklist

- [ ] **Authenticate** via enterprise IdP (Okta, Azure AD, etc.)
- [ ] **Register agent** with name, type, vendor (if applicable), purpose
- [ ] **Connect services** via browser OAuth (only IT-approved services visible)
- [ ] **Configure delegation** — select permissions, constraints, TTL
- [ ] **Share delegation token** with agent/vendor securely
- [ ] **Monitor agent activity** in personal dashboard
- [ ] **Renew or revoke** delegation as needed

### IT Admin Governance Checklist

- [ ] **Configure IdP integration** — user sync, group→role mapping
- [ ] **Define approved MCP servers** — per-role visibility
- [ ] **Set maximum delegable permissions** — per role
- [ ] **Configure approved vendor list** — vetted agent providers
- [ ] **Set default delegation TTL** — org-wide policy
- [ ] **Configure alerting** — unusual activity, new agents, policy violations
- [ ] **Document emergency procedures** — who can suspend, escalation path
- [ ] **Schedule periodic reviews** — dormant agents, over-permissioned delegations

---

## Appendix: How the Three Use Cases Interconnect

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VIRTUAL MCP SERVER: UNIFIED ARCHITECTURE                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                         ┌─────────────────────────────────────────────────┐ │
│                         │           VIRTUAL MCP SERVER                     │ │
│                         │           (DeepTrail Gateway)                    │ │
│                         │                                                  │ │
│  USE CASE 1             │  ┌──────────────────────────────────────────┐   │ │
│  Vendor Agents ─────────┼─>│  MCP Protocol Layer                      │   │ │
│  (Single connection,    │  │  • Agent authentication                  │   │ │
│   delegation tokens)    │  │  • tools/list aggregation & filtering   │   │ │
│                         │  │  • tools/call routing                    │   │ │
│                         │  └──────────────────────────────────────────┘   │ │
│                         │                      │                          │ │
│  USE CASE 3             │  ┌──────────────────────────────────────────┐   │ │
│  Employee Agents ───────┼─>│  Governance Layer                         │   │ │
│  (IT-approved tools,    │  │  • Policy enforcement                    │   │ │
│   scoped delegation)    │  │  • Delegation validation                 │   │ │
│                         │  │  • Constraint checking                   │   │ │
│                         │  │  • Audit logging                         │   │ │
│                         │  └──────────────────────────────────────────┘   │ │
│                         │                      │                          │ │
│  USE CASE 2             │  ┌──────────────────────────────────────────┐   │ │
│  MCP Servers ───────────┼─>│  MCP Registry & Backend Pool              │   │ │
│  (Staged rollout,       │  │  • Server registration (sandbox/prod)    │   │ │
│   policy testing)       │  │  • Connection pooling                    │   │ │
│                         │  │  • Circuit breakers                      │   │ │
│                         │  │  • Health monitoring                     │   │ │
│                         │  └──────────────────────────────────────────┘   │ │
│                         │                      │                          │ │
│                         │                      ▼                          │ │
│                         │  ┌──────────────────────────────────────────┐   │ │
│                         │  │  Backend MCP Servers                      │   │ │
│                         │  │  HubSpot │ Salesforce │ Notion │ ...     │   │ │
│                         │  └──────────────────────────────────────────┘   │ │
│                         │                                                  │ │
│                         └─────────────────────────────────────────────────┘ │
│                                                                              │
│  SHARED BENEFITS ACROSS ALL USE CASES:                                       │
│                                                                              │
│  ✓ Single point of governance for all agent↔tool interactions              │
│  ✓ Unified audit trail across all agents and all backends                  │
│  ✓ Consistent policy enforcement regardless of agent source                │
│  ✓ Central circuit breaker for incident response                           │
│  ✓ Token exchange (agents never hold backend credentials)                  │
│  ✓ Attribution chain (every action → agent → user → delegation)           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | January 2026 | — | Initial draft with three use cases |
