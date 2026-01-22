# Virtual MCP Server MVP: Two-Phase Implementation Plan

> **Design Document** | Version 1.0 | January 2026
>
> Based on: `deepsecure-comprehensive-architecture-consolidated.md` and `ai-agent-conference-2026-virtual-mcp-server-talk.md`

---

## Executive Summary

This document defines a **Minimal Viable Product (MVP)** for the Virtual MCP Server pattern, demonstrating end-to-end functionality with:

- **Phase 1**: 2 MCP Servers (Notion, Slack)
- **Phase 2**: 3 MCP Servers (Notion, Slack, HubSpot)

We use **Sarah** (employee at Acme Corp) as our persona to walk through every architectural component from user onboarding to agent task execution and audit.

---

## Table of Contents

1. [MVP Scope Definition](#1-mvp-scope-definition)
2. [Sarah's Journey: Phase 1 (Notion + Slack)](#2-sarahs-journey-phase-1-notion--slack)
3. [Sarah's Journey: Phase 2 (Adding HubSpot)](#3-sarahs-journey-phase-2-adding-hubspot)
4. [Architecture Components in MVP](#4-architecture-components-in-mvp)
5. [Minimal Proof of Value Demonstrations](#5-minimal-proof-of-value-demonstrations)
6. [Implementation Timeline](#6-implementation-timeline)
7. [What's Explicitly Out of Scope](#7-whats-explicitly-out-of-scope)

---

## 1. MVP Scope Definition

### 1.1 What We're Proving

| Value Proposition | How MVP Demonstrates It |
|-------------------|------------------------|
| **Unified MCP Connection** | Agent connects to ONE gateway, sees tools from 2-3 backends |
| **Delegation-Based Consent** | Sarah consents once in browser, agent uses her credentials |
| **Tool Filtering** | Agent sees only tools Sarah delegated (not all backend tools) |
| **Namespace Resolution** | `notion.search_pages` and `slack.search` are unambiguous |
| **Audit Trail** | Every action logged as "agent-X on behalf of Sarah" |
| **Fail-Closed Security** | Agent denied when gateway can't reach control plane |

### 1.2 MVP Backend Selection

| Backend | Why Selected | Tools in MVP |
|---------|--------------|--------------|
| **Notion** | Document/knowledge management, common enterprise tool | `search_pages`, `read_page`, `create_page` |
| **Slack** | Communication, complements Notion | `search_messages`, `send_message`, `list_channels` |
| **HubSpot** (Phase 2) | CRM, adds real business workflow | `get_contact`, `update_contact`, `list_deals` |

### 1.3 MVP Non-Functional Constraints

| Constraint | MVP Target | Production Target |
|------------|------------|-------------------|
| Concurrent agents | 5 | 1000+ |
| tools/list latency | <500ms | <50ms |
| Backends supported | 2-3 | 47+ |
| Session storage | In-memory | Redis |
| Token exchange | Simulated/Static keys | Keycloak RFC 8693 |

### 1.4 OAuth Compliance (MCP Authorization Spec)

Per the [MCP Authorization Specification (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization):

| Spec Requirement | MVP Status | Production Status |
|------------------|------------|-------------------|
| **PKCE** | ✅ Required | ✅ Required |
| **Resource Parameter (RFC 8707)** | ⏳ Static config | ✅ Dynamic |
| **WWW-Authenticate Header** | ⏳ Simplified | ✅ Full RFC 9728 |
| **Token Passthrough Prevention** | ✅ Required | ✅ Required |
| **Authorization Server Discovery (RFC 8414)** | ⏳ Static config | ✅ Full discovery |

**Critical MVP Security Requirement**: Gateway MUST NOT forward agent tokens to backends. Even in MVP, token exchange (or static backend tokens) is required.

---

## 2. Sarah's Journey: Phase 1 (Notion + Slack)

### 2.1 Persona Definition

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SARAH - ENTERPRISE EMPLOYEE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Name: Sarah Chen                                                            │
│  Role: Sales Development Representative (SDR)                                │
│  Company: Acme Corp (uses Okta as Enterprise IdP)                            │
│  Email: sarah@acme.com                                                       │
│                                                                              │
│  Services Sarah Uses:                                                        │
│  • Notion - Company wiki, playbooks, meeting notes                          │
│  • Slack - Team communication                                                │
│  • HubSpot (Phase 2) - CRM, lead tracking                                   │
│                                                                              │
│  Agent: "SDR-Assistant" (agent-sdr-001)                                      │
│  Agent Purpose: Help Sarah research prospects and draft outreach            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Step 1: Enterprise Registration (One-Time Setup)

**Architectural Components Touched**: Enterprise IdP, DeepTrail Control Plane

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     STEP 1: ENTERPRISE ONBOARDING                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Acme Corp IT Admin:                                                         │
│                                                                              │
│  1. Configures Okta → DeepTrail federation                                  │
│     POST /api/v1/organizations                                              │
│     {                                                                        │
│       "name": "Acme Corp",                                                   │
│       "idp_type": "okta",                                                    │
│       "idp_issuer": "https://acme.okta.com",                                │
│       "allowed_domains": ["acme.com"]                                        │
│     }                                                                        │
│                                                                              │
│  2. Registers "SDR-Assistant" agent in Okta                                 │
│     • Creates service account: agent-sdr-001@acme.com                       │
│     • Issues Agent-ID Token with owner claim set to Sarah                   │
│                                                                              │
│  3. DeepTrail stores organization config                                    │
│     • Trusts tokens from https://acme.okta.com                              │
│     • Maps Okta groups to DeepTrail policies                                │
│                                                                              │
│  RESULT: Acme Corp employees can use DeepTrail with SSO                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**MVP Simplification**: Use hardcoded organization config, skip full Okta integration.

### 2.3 Step 2: Sarah Authenticates (User Session Creation)

**Architectural Components Touched**: Layer 0 (User ID-Token), User Session Service

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 2: SARAH LOGS INTO DEEPSECURE CONSOLE               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Sarah's Browser:                                                            │
│                                                                              │
│  1. Visits https://console.deeptrail.io/login                               │
│  2. Clicks "Sign in with Okta"                                              │
│  3. Redirected to Acme Okta SSO                                             │
│  4. Enters credentials + MFA                                                 │
│  5. Okta issues User ID-Token:                                              │
│                                                                              │
│     {                                                                        │
│       "iss": "https://acme.okta.com",                                       │
│       "sub": "sarah@acme.com",                                              │
│       "email": "sarah@acme.com",                                            │
│       "groups": ["sales", "sdr-team"],                                      │
│       "mfa_verified": true,                                                  │
│       "exp": 1737907200  // 1 hour                                          │
│     }                                                                        │
│                                                                              │
│  6. DeepTrail Console creates User Session:                                 │
│                                                                              │
│     CREATE USER SESSION:                                                     │
│     {                                                                        │
│       "session_id": "usess-sarah-abc123",                                   │
│       "user_id": "sarah@acme.com",                                          │
│       "idp_issuer": "https://acme.okta.com",                                │
│       "permission_grants": {},      // Empty, will be populated              │
│       "connected_services": {},     // Empty, will be populated              │
│       "created_at": "2026-01-21T10:00:00Z",                                 │
│       "expires_at": "2026-01-21T18:00:00Z"  // 8 hour work day              │
│     }                                                                        │
│                                                                              │
│  RESULT: Sarah has an active User Session in DeepTrail                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.4 Step 3: Sarah Connects Notion & Slack (OAuth Consent)

**Architectural Components Touched**: Connected Services, OAuth Flow, Credential Storage

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 STEP 3: SARAH CONNECTS BACKEND SERVICES                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Sarah in DeepTrail Console → "Connected Services" page:                    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    CONNECT YOUR SERVICES                             │    │
│  │                                                                      │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐                    │    │
│  │  │   Notion   │  │   Slack    │  │  HubSpot   │                    │    │
│  │  │   [  ]     │  │   [  ]     │  │   [  ]     │                    │    │
│  │  │  Connect   │  │  Connect   │  │  (Phase 2) │                    │    │
│  │  └────────────┘  └────────────┘  └────────────┘                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Sarah clicks "Connect Notion":                                              │
│  1. Browser redirects to Notion OAuth                                        │
│  2. Sarah logs into Notion (if not already)                                 │
│  3. Notion consent screen:                                                   │
│     "DeepTrail wants to access your Notion workspace"                       │
│     ☑ Read pages  ☑ Search content  ☑ Create pages                         │
│  4. Sarah clicks "Allow"                                                     │
│  5. Notion returns OAuth tokens to DeepTrail                                │
│                                                                              │
│  DeepTrail stores connection:                                                │
│  INSERT INTO connected_services:                                             │
│  {                                                                           │
│    "user_id": "sarah@acme.com",                                             │
│    "service_id": "notion",                                                   │
│    "oauth_token_ref": "vault://sarah-notion-oauth-xyz",  // Encrypted       │
│    "scopes_granted": ["read_content", "search", "create_pages"],            │
│    "connected_at": "2026-01-21T10:05:00Z"                                   │
│  }                                                                           │
│                                                                              │
│  Sarah repeats for Slack.                                                    │
│                                                                              │
│  RESULT: DeepTrail holds Sarah's Notion & Slack OAuth tokens (securely)     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Security Property**: Sarah consented in HER browser. Agent will never do OAuth.

### 2.5 Step 4: Sarah Delegates to Agent (Delegation Token)

**Architectural Components Touched**: Layer 2 (Delegation Token), Permission Grants

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 STEP 4: SARAH DELEGATES TO SDR-ASSISTANT                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Sarah in Console → "My Agents" → "SDR-Assistant" → "Permissions"           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │            DELEGATE PERMISSIONS TO SDR-ASSISTANT                     │    │
│  │                                                                      │    │
│  │  NOTION PERMISSIONS:                                                │    │
│  │  ☑ Search pages (notion:pages:search)                                │    │
│  │  ☑ Read pages (notion:pages:read)                                    │    │
│  │  ☐ Create pages (notion:pages:create)  ← Sarah doesn't grant this   │    │
│  │                                                                      │    │
│  │  SLACK PERMISSIONS:                                                  │    │
│  │  ☑ Search messages (slack:messages:search)                           │    │
│  │  ☐ Send messages (slack:messages:send)   ← Agent can't send         │    │
│  │  ☑ List channels (slack:channels:list)                               │    │
│  │                                                                      │    │
│  │  CONSTRAINTS:                                                        │    │
│  │  • Delegation expires: 7 days                                        │    │
│  │  • Max actions per day: 100                                          │    │
│  │                                                                      │    │
│  │  [Save Delegation]                                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  DeepTrail issues Delegation Token:                                          │
│                                                                              │
│  LAYER 2: DELEGATION TOKEN                                                   │
│  {                                                                           │
│    "sub": "agent-sdr-001",                                                  │
│    "delegator": "sarah@acme.com",                                           │
│    "delegator_idp": "https://acme.okta.com",                                │
│    "user_token_hash": "sha256:abc...",     // Binds to Sarah's identity     │
│    "agent_token_hash": "sha256:def...",    // Binds to agent's identity     │
│    "delegated_permissions": [                                                │
│      "notion:pages:search",                                                  │
│      "notion:pages:read",                                                    │
│      "slack:messages:search",                                                │
│      "slack:channels:list"                                                   │
│    ],                                                                        │
│    "constraints": {                                                          │
│      "max_actions_per_day": 100                                              │
│    },                                                                        │
│    "exp": 1738512000,  // 7 days                                            │
│    "logging_uri": "https://audit.deeptrail.io/log",                         │
│    "revocation_uri": "https://deeptrail.io/revoke/del-sarah-sdr-001"        │
│  }                                                                           │
│                                                                              │
│  RESULT: Agent has bounded delegation from Sarah                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Monotonic Attenuation**:
- Sarah has: `notion:*`, `slack:*` (from her OAuth consent)
- Agent gets: `notion:pages:search`, `notion:pages:read`, `slack:messages:search`, `slack:channels:list`
- Agent permissions ⊂ Sarah's permissions ✓

### 2.6 Step 5: Agent Authenticates (Agent Session Creation)

**Architectural Components Touched**: Layer 3 (Agent Session JWT), Agent Session Service

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 5: AGENT STARTS SESSION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SDR-Assistant Agent (running somewhere):                                    │
│                                                                              │
│  1. Agent has Ed25519 keypair from registration                             │
│                                                                              │
│  2. Agent authenticates to DeepTrail Control Plane:                         │
│     POST /api/v1/auth/agent/challenge                                       │
│     { "agent_id": "agent-sdr-001" }                                         │
│                                                                              │
│     Response: { "challenge": "random-nonce-xyz" }                           │
│                                                                              │
│  3. Agent signs challenge with private key:                                 │
│     POST /api/v1/auth/agent/verify                                          │
│     {                                                                        │
│       "agent_id": "agent-sdr-001",                                          │
│       "challenge": "random-nonce-xyz",                                      │
│       "signature": "ed25519-signature-of-challenge"                          │
│     }                                                                        │
│                                                                              │
│  4. Control Plane validates and issues Agent Session JWT:                   │
│                                                                              │
│     LAYER 3: AGENT SESSION JWT                                              │
│     {                                                                        │
│       "sub": "agent-sdr-001",                                               │
│       "owner": "sarah@acme.com",          // From delegation                │
│       "idp_issuer": "https://acme.okta.com",                                │
│       "party_type": "first_party",                                          │
│       "delegated_permissions": [           // From delegation token         │
│         "notion:pages:search",                                              │
│         "notion:pages:read",                                                │
│         "slack:messages:search",                                            │
│         "slack:channels:list"                                               │
│       ],                                                                     │
│       "delegation_id": "del-sarah-sdr-001",                                 │
│       "groups": ["sales"],                 // Sarah's groups                │
│       "session_id": "asess-sdr-001-ghi789",                                 │
│       "exp": 1737936000                    // 8 hours                       │
│     }                                                                        │
│                                                                              │
│  5. Control Plane creates Agent Session:                                    │
│     {                                                                        │
│       "agent_session_id": "asess-sdr-001-ghi789",                           │
│       "parent_user_session_id": "usess-sarah-abc123",                       │
│       "agent_id": "agent-sdr-001",                                          │
│       "party_type": "first_party",                                          │
│       "scoped_permissions": [...delegated_permissions...],                  │
│       "mcp_sessions": {}   // Will be populated on first MCP call           │
│     }                                                                        │
│                                                                              │
│  RESULT: Agent has authenticated session linked to Sarah                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.7 Step 6: Agent Connects to Virtual MCP Server (MCP Session)

**Architectural Components Touched**: Gateway (Virtual MCP Server), MCP Session Service, Tool Aggregation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              STEP 6: AGENT CONNECTS TO VIRTUAL MCP SERVER                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Agent Code:                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  # Agent sees ONE MCP server - the gateway                           │    │
│  │  client = MCPClient("https://gateway.deeptrail.io/mcp")              │    │
│  │  client.set_auth_header(f"Bearer {agent_session_jwt}")               │    │
│  │                                                                      │    │
│  │  # MCP initialize handshake                                          │    │
│  │  await client.initialize()                                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Gateway (Virtual MCP Server) handles initialize:                           │
│                                                                              │
│  1. Validates Agent Session JWT                                             │
│  2. Extracts delegated_permissions                                          │
│  3. Looks up Sarah's connected services (Notion, Slack)                     │
│  4. Creates MCP Sessions for each backend:                                  │
│                                                                              │
│     MCP SESSION 1 (Notion):                                                 │
│     {                                                                        │
│       "mcp_session_id": "mcpsess-notion-jkl012",                            │
│       "parent_agent_session": "asess-sdr-001-ghi789",                       │
│       "server_id": "notion",                                                │
│       "connection_state": "initialized",                                     │
│       "allowed_tools": ["notion.search_pages", "notion.read_page"],         │
│       "injected_credentials": {                                              │
│         "type": "oauth",                                                     │
│         "ref": "vault://sarah-notion-oauth-xyz"   // Sarah's token         │
│       }                                                                      │
│     }                                                                        │
│                                                                              │
│     MCP SESSION 2 (Slack):                                                  │
│     {                                                                        │
│       "mcp_session_id": "mcpsess-slack-mno345",                             │
│       "parent_agent_session": "asess-sdr-001-ghi789",                       │
│       "server_id": "slack",                                                 │
│       "connection_state": "initialized",                                     │
│       "allowed_tools": ["slack.search_messages", "slack.list_channels"],    │
│       "injected_credentials": {                                              │
│         "type": "oauth",                                                     │
│         "ref": "vault://sarah-slack-oauth-abc"    // Sarah's token         │
│       }                                                                      │
│     }                                                                        │
│                                                                              │
│  5. Gateway responds to agent with initialize/initialized                   │
│                                                                              │
│  RESULT: Agent is connected to Virtual MCP Server with 2 backend sessions   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.8 Step 7: Agent Discovers Tools (Filtered tools/list)

**Architectural Components Touched**: Capability Aggregation, Namespace Prefixing, Tool Filtering

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 7: AGENT CALLS tools/list                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Agent Code:                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  tools = await client.tools_list()                                   │    │
│  │  print(f"Available tools: {[t.name for t in tools]}")                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Gateway Processing:                                                         │
│                                                                              │
│  1. AGGREGATE from backends (what backends offer):                          │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │ Notion MCP Server offers:                                        │     │
│     │   • search_pages    • read_page    • create_page    • ...       │     │
│     │                                                                  │     │
│     │ Slack MCP Server offers:                                         │     │
│     │   • search_messages • send_message • list_channels  • ...       │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  2. NAMESPACE PREFIX (avoid collisions):                                    │
│     • search_pages     → notion.search_pages                                │
│     • read_page        → notion.read_page                                   │
│     • search_messages  → slack.search_messages                              │
│     • list_channels    → slack.list_channels                                │
│                                                                              │
│  3. FILTER by agent's delegated permissions:                                │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │ Agent has: notion:pages:search, notion:pages:read,               │     │
│     │            slack:messages:search, slack:channels:list            │     │
│     │                                                                  │     │
│     │ Mapping:                                                         │     │
│     │ • notion.search_pages  → notion:pages:search   ✓ INCLUDE        │     │
│     │ • notion.read_page     → notion:pages:read     ✓ INCLUDE        │     │
│     │ • notion.create_page   → notion:pages:create   ✗ NOT DELEGATED  │     │
│     │ • slack.search_messages→ slack:messages:search ✓ INCLUDE        │     │
│     │ • slack.send_message   → slack:messages:send   ✗ NOT DELEGATED  │     │
│     │ • slack.list_channels  → slack:channels:list   ✓ INCLUDE        │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  4. RETURN filtered, namespaced tools to agent:                             │
│                                                                              │
│     {                                                                        │
│       "tools": [                                                             │
│         {                                                                    │
│           "name": "notion.search_pages",                                    │
│           "description": "[Notion] Search pages in workspace",              │
│           "inputSchema": { "type": "object", "properties": {...} }          │
│         },                                                                   │
│         {                                                                    │
│           "name": "notion.read_page",                                       │
│           "description": "[Notion] Read a specific page by ID",             │
│           "inputSchema": {...}                                               │
│         },                                                                   │
│         {                                                                    │
│           "name": "slack.search_messages",                                  │
│           "description": "[Slack] Search messages in channels",             │
│           "inputSchema": {...}                                               │
│         },                                                                   │
│         {                                                                    │
│           "name": "slack.list_channels",                                    │
│           "description": "[Slack] List available channels",                 │
│           "inputSchema": {...}                                               │
│         }                                                                    │
│       ]                                                                      │
│     }                                                                        │
│                                                                              │
│  Agent Output:                                                               │
│  > Available tools: ['notion.search_pages', 'notion.read_page',             │
│                      'slack.search_messages', 'slack.list_channels']        │
│                                                                              │
│  RESULT: Agent sees ONLY 4 tools (not all Notion+Slack tools)               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key MVP Demonstration**: Agent sees 4 tools, not 20+. This is the core value prop.

### 2.9 Step 8: Agent Executes Task (tools/call with Governance)

**Architectural Components Touched**: Action Control, Token Injection, Audit Trail

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 8: AGENT CALLS notion.search_pages                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Agent Code (responding to user request):                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  # User asked: "Find our competitor analysis docs"                   │    │
│  │  result = await client.tools_call(                                   │    │
│  │      "notion.search_pages",                                          │    │
│  │      {"query": "competitor analysis", "limit": 5}                    │    │
│  │  )                                                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Gateway Processing:                                                         │
│                                                                              │
│  1. PARSE namespace: "notion.search_pages" → server: "notion", tool: "search_pages"
│                                                                              │
│  2. VALIDATE permission:                                                    │
│     • Required permission: notion:pages:search                              │
│     • Agent has: [notion:pages:search, ...] ✓ ALLOWED                       │
│                                                                              │
│  3. VALIDATE constraints:                                                   │
│     • max_actions_per_day: 100                                              │
│     • Current count: 0 → Increment to 1 ✓ ALLOWED                           │
│                                                                              │
│  4. GET CREDENTIALS for Notion:                                             │
│     • Lookup MCP Session mcpsess-notion-jkl012                              │
│     • Get credential ref: vault://sarah-notion-oauth-xyz                    │
│     • Decrypt Sarah's Notion OAuth token                                    │
│                                                                              │
│  5. FORWARD to backend Notion MCP Server:                                   │
│     POST https://mcp.notion.com/tools/call                                  │
│     Authorization: Bearer {sarah's-notion-oauth-token}                      │
│     {                                                                        │
│       "method": "tools/call",                                               │
│       "params": {                                                            │
│         "name": "search_pages",   // Stripped namespace                     │
│         "arguments": {"query": "competitor analysis", "limit": 5}           │
│       }                                                                      │
│     }                                                                        │
│                                                                              │
│  6. RECEIVE response from Notion:                                           │
│     {                                                                        │
│       "content": [                                                           │
│         {"type": "text", "text": "Found 3 pages: ..."}                      │
│       ]                                                                      │
│     }                                                                        │
│                                                                              │
│  7. AUDIT LOG:                                                              │
│     {                                                                        │
│       "timestamp": "2026-01-21T10:15:32Z",                                  │
│       "event_type": "mcp_tool_call",                                        │
│       "agent_id": "agent-sdr-001",                                          │
│       "on_behalf_of": "sarah@acme.com",      // KEY: Attribution           │
│       "tool": "notion.search_pages",                                        │
│       "arguments": {"query": "competitor analysis", "limit": 5},            │
│       "result_summary": "3 pages found",                                    │
│       "session_id": "asess-sdr-001-ghi789",                                 │
│       "mcp_session_id": "mcpsess-notion-jkl012"                             │
│     }                                                                        │
│                                                                              │
│  8. RETURN result to agent (unmodified in MVP)                              │
│                                                                              │
│  RESULT: Tool executed with Sarah's credentials, fully audited              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.10 Step 9: Agent Denied (Permission Not Delegated)

**Architectural Components Touched**: Fail-Closed Security

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              STEP 9: AGENT TRIES UNAUTHORIZED ACTION                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Agent Code (agent tries to create a page):                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  # Agent decides to create a page - NOT DELEGATED                    │    │
│  │  result = await client.tools_call(                                   │    │
│  │      "notion.create_page",                                           │    │
│  │      {"title": "Competitor Summary", "content": "..."}               │    │
│  │  )                                                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Gateway Processing:                                                         │
│                                                                              │
│  1. PARSE: "notion.create_page" → notion:pages:create                       │
│                                                                              │
│  2. VALIDATE:                                                               │
│     • Required: notion:pages:create                                         │
│     • Agent has: [notion:pages:search, notion:pages:read, ...] ✗ DENIED     │
│                                                                              │
│  3. RETURN MCP Error (tool never reaches backend):                          │
│     {                                                                        │
│       "error": {                                                             │
│         "code": -32001,                                                     │
│         "message": "Permission denied: notion:pages:create not delegated"   │
│       }                                                                      │
│     }                                                                        │
│                                                                              │
│  4. AUDIT LOG (security event):                                             │
│     {                                                                        │
│       "timestamp": "2026-01-21T10:16:45Z",                                  │
│       "event_type": "permission_denied",                                    │
│       "agent_id": "agent-sdr-001",                                          │
│       "on_behalf_of": "sarah@acme.com",                                     │
│       "attempted_tool": "notion.create_page",                               │
│       "required_permission": "notion:pages:create",                         │
│       "reason": "Permission not in delegation"                              │
│     }                                                                        │
│                                                                              │
│  RESULT: Unauthorized action blocked, agent never sees Notion credentials   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Note**: Even though Notion MCP Server exposes `create_page`, agent can't use it because Sarah didn't delegate that permission.

### 2.11 Step 10: Sarah Reviews Audit Trail

**Architectural Components Touched**: Audit Service

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 10: SARAH REVIEWS AGENT ACTIVITY                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Sarah in Console → "Audit Logs" → Filter: agent-sdr-001                    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │              AGENT ACTIVITY: SDR-ASSISTANT                           │    │
│  │                                                                      │    │
│  │  Time         | Tool                  | Result    | Details          │    │
│  │  ─────────────┼───────────────────────┼───────────┼────────────────  │    │
│  │  10:15:32     │ notion.search_pages   │ ✓ Success │ 3 pages found   │    │
│  │  10:16:45     │ notion.create_page    │ ✗ Denied  │ Not delegated   │    │
│  │  10:17:12     │ slack.search_messages │ ✓ Success │ 12 messages     │    │
│  │  10:18:03     │ slack.list_channels   │ ✓ Success │ 8 channels      │    │
│  │                                                                      │    │
│  │  Actions Today: 3 of 100 allowed                                     │    │
│  │  Delegation Expires: 7 days                                          │    │
│  │                                                                      │    │
│  │  [Export Logs]  [Revoke Delegation]  [Adjust Permissions]            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  RESULT: Sarah has full visibility into agent actions on her behalf         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Sarah's Journey: Phase 2 (Adding HubSpot)

### 3.1 What Changes in Phase 2

Phase 2 adds HubSpot, demonstrating:

| New Capability | Why It Matters |
|----------------|----------------|
| **3-backend aggregation** | Shows tool list grows but stays filtered |
| **Cross-service workflow** | Agent uses Notion research + HubSpot CRM |
| **CRM-specific constraints** | Contact ID restrictions, deal access limits |

### 3.2 Sarah Connects HubSpot

Same flow as Notion/Slack:
1. Sarah clicks "Connect HubSpot" in console
2. OAuth flow with HubSpot consent
3. DeepTrail stores HubSpot OAuth tokens

### 3.3 Sarah Updates Agent Delegation

```
Sarah adds to SDR-Assistant delegation:
- hubspot:contacts:read (get_contact)
- hubspot:contacts:update (update_contact - but constrained!)
- hubspot:deals:list (list_deals)

With constraint: contact updates only for IDs agent discovers via search
```

### 3.4 Agent Now Sees 7 Tools

```
tools/list response with HubSpot:
[
  "notion.search_pages",
  "notion.read_page",
  "slack.search_messages",
  "slack.list_channels",
  "hubspot.get_contact",        // NEW
  "hubspot.update_contact",     // NEW (constrained)
  "hubspot.list_deals"          // NEW
]
```

### 3.5 Cross-Service Workflow Demo

```
User to Agent: "Find our competitor analysis in Notion, then update 
               any HubSpot contacts mentioned in those docs"

Agent Execution:
1. notion.search_pages("competitor analysis") → Returns page with "Contact: John Smith (HubSpot ID: 12345)"
2. hubspot.get_contact({"id": "12345"}) → Gets John's current info
3. hubspot.update_contact({"id": "12345", "notes": "Mentioned in competitor analysis"}) → ✓
4. hubspot.update_contact({"id": "99999", "notes": "..."}) → ✗ DENIED (ID not discovered)

Audit shows full chain of reasoning across all three services.
```

---

## 4. Architecture Components in MVP

### 4.1 Component Implementation Status

| Component | MVP Status | Implementation Notes |
|-----------|------------|---------------------|
| **Gateway (Virtual MCP Server)** | ✅ Required | Core of MVP |
| **MCP Protocol Handler** | ✅ Required | Handle initialize, tools/list, tools/call |
| **Namespace Prefixer** | ✅ Required | `{backend}.{tool}` naming |
| **Tool Aggregator** | ✅ Required | Combine tools from 2-3 backends |
| **Static Permission Filter** | ✅ Required | Filter by delegated_permissions |
| **Backend Connection Manager** | ✅ Required | Manage 2-3 MCP client connections |
| **Credential Injection** | ✅ Required | Use Sarah's OAuth tokens |
| **Audit Logger** | ✅ Required | Log every action |
| **User Session (simplified)** | ✅ Required | Store connected services |
| **Agent Session (simplified)** | ✅ Required | Store delegated permissions |
| **Delegation Token** | ✅ Required | Bind user → agent permissions |
| **Token Exchange (RFC 8693)** | ⏳ Simplified | Use static OAuth tokens in MVP |
| **PKCE for OAuth Flows** | ✅ Required | MCP clients MUST implement per spec |
| **Token Passthrough Prevention** | ✅ Required | Never forward agent tokens to backends |
| **Circuit Breakers** | ⏳ Post-MVP | Simple fail-fast acceptable |
| **Redis Session Store** | ⏳ Post-MVP | In-memory acceptable |
| **Bloom Filter Optimization** | ⏳ Post-MVP | Linear search acceptable for <20 tools |
| **Result Filtering (PII)** | ⏳ Post-MVP | Pass-through in MVP |
| **Streaming Support** | ⏳ Post-MVP | Buffer entire response |

### 4.2 Token Flow in MVP

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MVP TOKEN FLOW (SIMPLIFIED)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Sarah (Browser)                                                             │
│     │                                                                        │
│     │ 1. Login (Okta SSO)                                                   │
│     ▼                                                                        │
│  User Session ──────────────────────────────────┐                           │
│     │                                           │                           │
│     │ 2. Connect Services (OAuth)               │                           │
│     │    • Notion OAuth → vault                 │                           │
│     │    • Slack OAuth → vault                  │                           │
│     │                                           │                           │
│     │ 3. Delegate to Agent                      │                           │
│     ▼                                           │                           │
│  Delegation Token                               │                           │
│     │                                           │                           │
│     │                                           │                           │
│  Agent                                          │                           │
│     │                                           │                           │
│     │ 4. Authenticate (Ed25519)                 │                           │
│     ▼                                           │                           │
│  Agent Session JWT                              │                           │
│     │                                           │                           │
│     │ 5. Connect to Gateway                     │                           │
│     ▼                                           │                           │
│  Gateway (Virtual MCP Server)                   │                           │
│     │                                           │                           │
│     │ 6. tools/list → Filter by delegation      │                           │
│     │                                           │                           │
│     │ 7. tools/call                             │                           │
│     │    ├── Validate permission                │                           │
│     │    ├── Get Sarah's OAuth token from vault◀┘                           │
│     │    └── Forward to backend with token                                  │
│     │                                           │                           │
│     ▼                                           │                           │
│  Backend MCP Server (Notion/Slack)              │                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Minimal Proof of Value Demonstrations

### 5.1 Demo 1: Unified MCP Connection

**What to Show**: Agent connects to ONE endpoint, sees tools from MULTIPLE backends.

```python
# Demo script
from mcp_client import MCPClient

client = MCPClient("https://gateway.deeptrail.io/mcp")
client.authenticate(agent_session_jwt)
await client.initialize()

tools = await client.tools_list()
print(f"Connected to 1 server, can access {len(tools)} tools from 2 backends")
# Output: Connected to 1 server, can access 4 tools from 2 backends
```

**Success Criteria**: Agent code has NO awareness of Notion or Slack URLs.

### 5.2 Demo 2: Filtered Tool Visibility

**What to Show**: Agent sees ONLY delegated tools, not all backend tools.

```python
# Show what backends actually offer vs what agent sees
all_notion_tools = 15  # search, read, create, update, delete, share, ...
all_slack_tools = 22   # search, send, list, create_channel, ...

agent_sees = 4  # Only: notion.search_pages, notion.read_page, 
                #       slack.search_messages, slack.list_channels

print(f"Backends offer {all_notion_tools + all_slack_tools} tools")
print(f"Agent sees {agent_sees} tools (filtered by delegation)")
# Output: Backends offer 37 tools
#         Agent sees 4 tools (filtered by delegation)
```

**Success Criteria**: 90%+ reduction in visible tools.

### 5.3 Demo 3: Delegation-Based Execution

**What to Show**: Agent uses Sarah's credentials without seeing them.

```
# Agent calls tool
result = await client.tools_call("notion.search_pages", {"query": "test"})

# In gateway logs:
INFO: Executing notion.search_pages
INFO: Credentials: Using vault://sarah-notion-oauth-xyz
INFO: Agent agent-sdr-001 NEVER sees credential value
INFO: Request forwarded to Notion with Sarah's token
INFO: Action attributed to: agent-sdr-001 on behalf of sarah@acme.com
```

**Success Criteria**: Agent never receives OAuth tokens in response.

### 5.4 Demo 4: Permission Enforcement

**What to Show**: Unauthorized tools are blocked at gateway, never reach backend.

```python
# Agent tries unauthorized action
try:
    await client.tools_call("notion.create_page", {"title": "test"})
except MCPError as e:
    print(e)
# Output: MCPError(-32001): Permission denied: notion:pages:create not delegated

# Verify: Check Notion audit logs - NO request reached Notion
```

**Success Criteria**: Backend sees ZERO unauthorized requests.

### 5.5 Demo 5: Unified Audit Trail

**What to Show**: Single query answers "what did agent do?"

```sql
-- Query audit logs
SELECT timestamp, tool, result, on_behalf_of
FROM audit_logs
WHERE agent_id = 'agent-sdr-001'
  AND timestamp > NOW() - INTERVAL '1 day';

-- Result:
-- 10:15:32 | notion.search_pages   | success | sarah@acme.com
-- 10:16:45 | notion.create_page    | denied  | sarah@acme.com
-- 10:17:12 | slack.search_messages | success | sarah@acme.com
```

**Success Criteria**: Answer "what did agent X do?" in <1 second (not 4 hours).

### 5.6 Demo 6: Fail-Closed Security

**What to Show**: When control plane is unavailable, all requests denied.

```python
# Simulate control plane outage
gateway.control_plane.disconnect()

try:
    await client.tools_call("notion.search_pages", {"query": "test"})
except MCPError as e:
    print(e)
# Output: MCPError(-32000): Policy service unavailable - request denied

# When restored:
gateway.control_plane.reconnect()
result = await client.tools_call("notion.search_pages", {"query": "test"})
# Output: Success
```

**Success Criteria**: ZERO requests allowed during control plane outage.

---

## 6. Implementation Timeline

### 6.1 Phase 1: 2 Backends (Notion + Slack) - 3 Weeks

| Week | Focus | Deliverables |
|------|-------|--------------|
| **Week 1** | Gateway Core | MCP protocol handler, initialize/tools_list/tools_call |
| **Week 2** | Auth & Routing | Agent auth, namespace prefixing, backend routing |
| **Week 3** | Permissions & Audit | Permission filter, credential injection, audit logging |

**End of Phase 1**: Demo 1-6 working with Notion + Slack.

### 6.2 Phase 2: 3 Backends (+ HubSpot) - 1 Week

| Week | Focus | Deliverables |
|------|-------|--------------|
| **Week 4** | HubSpot Integration | Add HubSpot backend, cross-service workflow demo |

**End of Phase 2**: Demo with Notion + Slack + HubSpot.

### 6.3 Phase 3: Production Readiness - 2+ Weeks

| Week | Focus | Deliverables |
|------|-------|--------------|
| **Week 5-6** | Scale & Reliability | Redis sessions, circuit breakers, connection pooling |

---

## 7. What's Explicitly Out of Scope

### 7.1 MVP Does NOT Include

| Feature | Why Deferred | When to Add |
|---------|--------------|-------------|
| **Full Keycloak Token Exchange** | Complex OAuth setup | When backends require it |
| **Result Filtering (PII masking)** | Adds latency, not core value | For compliance customers |
| **SSE Streaming Support** | Complex state management | For LLM-heavy workloads |
| **Circuit Breakers** | Fail-fast acceptable for demo | Before production |
| **Bloom Filter Optimization** | <20 tools doesn't need it | At 100+ tools |
| **Redis Session Persistence** | In-memory fine for single instance | For horizontal scale |
| **Task Tokens (per-task scoping)** | Delegation sufficient for MVP | For least-privilege enforcement |
| **Execution Plan Validation** | Complex, MiniScope-specific | For high-security deployments |
| **Cross-Server Transactions** | No MCP standard | When workflows require it |
| **Federated Virtual Servers** | Enterprise-to-enterprise | When B2B scenarios emerge |

### 7.2 MVP Simplifications

| Full Architecture | MVP Simplification |
|-------------------|-------------------|
| 6-layer token hierarchy | 3 tokens: User Session, Delegation, Agent Session |
| Dynamic constraint evaluation | Static permission check |
| Per-task scoped permissions | Per-delegation permissions |
| Precomputed permission matrices | Linear permission lookup |
| Event-driven cache invalidation | TTL-based refresh |

---

## Summary

This MVP demonstrates the **core value proposition** of the Virtual MCP Server pattern:

1. **Single Connection**: Agent connects to ONE endpoint, accesses MULTIPLE backends
2. **Delegation-Based Security**: Sarah consents once, agent uses her credentials safely
3. **Filtered Visibility**: Agent sees 4 tools, not 37 (90% reduction)
4. **Permission Enforcement**: Unauthorized actions blocked at gateway
5. **Full Attribution**: Every action audited as "agent on behalf of user"
6. **Fail-Closed**: No access when policy service unavailable

**Sarah's complete journey** validates every layer of the comprehensive architecture in a minimal, demonstrable form. Phase 1 (Notion + Slack) proves the pattern; Phase 2 (+ HubSpot) proves it scales.

---

*Document Version: 1.1 | Last Updated: January 2026 | Added MCP Authorization Spec compliance (PKCE, token passthrough prevention)*
