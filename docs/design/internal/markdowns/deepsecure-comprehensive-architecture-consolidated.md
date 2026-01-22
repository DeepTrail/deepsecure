# DeepSecure Comprehensive Architecture: Token Model, MCP Gateway, and Enterprise IdP Integration

> **Design Document** | Version 3.0 (Consolidated) | January 2026
>
> Comprehensive analysis combining Enterprise IdP integration, Token Architecture, MCP Gateway Design, and Architectural Tradeoffs

---

## Executive Summary

This **consolidated document** provides the **definitive architecture** for DeepSecure combining:

1. **Enterprise IdP Integration** (Okta/Microsoft Entra ID)
2. **Token Model Architecture** (Six-layer hierarchy with full claims)
3. **MCP Gateway Design** (The "Best of Both Worlds" approach)
4. **Architectural Tradeoffs** (HTTP Proxy vs Virtual MCP Server)
5. **Missing Components and Roadmap** (Priority-ranked additions)

The architecture addresses four key challenges:
- **Identity**: When enterprises have Okta/Entra ID as their IdP, how does the token model change?
- **Governance**: How does the Gateway provide MCP governance (tools visibility, result filtering)?
- **Standards Compliance**: How does the Gateway talk to OAuth-compliant backend MCP servers?
- **Architectural Choice**: HTTP Proxy vs Virtual MCP Server - what are the tradeoffs?

**The Answer**: Implement **two complementary layers**:
- **MCP Protocol Layer** - For governance, aggregation, and agent experience
- **OAuth Authorization Layer** - For standards-compliant backend MCP server communication

The Gateway acts as **three roles simultaneously**:
- **MCP Server** (to agents) - Virtual server presenting aggregated capabilities
- **MCP Host** (internal) - Coordinator managing multiple backend connections
- **MCP Client** (to backends) - Client connections to each real MCP server

---

## Table of Contents

**Part I: MCP Gateway Design**

1. [MCP Gateway Design Comparison](#1-mcp-gateway-design-comparison)
2. [The OAuth Challenge for Virtual MCP Server Design](#2-the-oauth-challenge-for-virtual-mcp-server-design)
3. [Best of Both Worlds: Unified Architecture](#3-best-of-both-worlds-unified-architecture)
4. [Gateway's Three MCP Roles](#4-gateways-three-mcp-roles)
5. [Gateway Architecture Tradeoffs](#5-gateway-architecture-tradeoffs)

**Part II: Token Architecture**

6. [Token Hierarchy Overview](#6-token-hierarchy-overview)
7. [Complete Six-Layer Token Hierarchy (Detailed)](#7-complete-six-layer-token-hierarchy-detailed)
8. [Token Model Comparison](#8-token-model-comparison)

**Part III: Per-Task Scoped Permissions**

9. [Per-Task Permission Architecture](#9-per-task-permission-architecture)
10. [Control Plane Components for Per-Task Permissions](#10-control-plane-components-for-per-task-permissions)
11. [Gateway Components for Action Control](#11-gateway-components-for-action-control)

**Part IV: Session Hierarchy Architecture**

12. [Session Hierarchy Overview](#12-session-hierarchy-overview)
13. [User Session Service](#13-user-session-service)
14. [Agent Session Service](#14-agent-session-service)
15. [MCP Session Service](#15-mcp-session-service)

**Part V: Non-MCP Agent Support**

16. [Agents Without MCP Client: Issues and Solutions](#16-agents-without-mcp-client-issues-and-solutions)

**Part VI: Configuration & Components**

17. [Component Comparison: Approach 1 vs Approach 2](#17-component-comparison-approach-1-oauth-http-proxy-vs-approach-2-mcp-governance--protocol)
18. [Missing Components and Roadmap](#18-missing-components-and-roadmap)

**Part VII: Key Improvements**

19. [Key Improvements](#19-key-improvements)

**Part VIII: Virtual MCP Server Implementation Challenges**

20. [Connection & Session Management Challenges](#20-connection--session-management-challenges)
21. [Cache & Performance Challenges](#21-cache--performance-challenges)
22. [User Consent & OAuth Challenges](#22-user-consent--oauth-challenges)
23. [Open Problems (Future)](#23-open-problems-future)

**[Summary](#summary)**

---

# Part I: MCP Gateway Design

## 1. MCP Gateway Design Comparison

The MCP Gateway architecture emerged from two complementary design approaches, each solving a distinct problem in the AI agent ecosystem. Understanding these approaches is critical before examining how they can be combined.

---

### Approach 1: OAuth HTTP Proxy (Agent Authorization Focus)

**Problem Solved**: How to securely talk to "Real" MCP servers (like HubSpot, Notion, Google Drive) that require standards-compliant OAuth tokens.

**Core Insight**: Backend MCP servers are **OAuth-protected resources**. They require:
- Audience-bound tokens (`aud: https://mcp.hubspot.com`)
- Standard OAuth 2.0/2.1 scopes
- RFC 9728 Protected Resource Metadata
- Dynamic Client Registration (RFC 7591)

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    APPROACH 1: OAUTH HTTP PROXY                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  AI Agent                                                                        │
│     │                                                                            │
│     │ Agent JWT + Task Token                                                     │
│     ▼                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    DEEPTRAIL GATEWAY                                      │    │
│  │                    (OAuth Client/Exchanger)                               │    │
│  │                                                                          │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ OAuth Token Exchange Middleware                                     │  │    │
│  │  │                                                                    │  │    │
│  │  │ 1. Validate Agent JWT + Task Token                                  │  │    │
│  │  │ 2. Extract scoped_permissions from Task Token                       │  │    │
│  │  │ 3. Call Keycloak Token Exchange (RFC 8693)                          │  │    │
│  │  │ 4. Get backend-specific OAuth token                                 │  │    │
│  │  │    - aud: mcp.hubspot.com                                           │  │    │
│  │  │    - scope: hubspot:contacts:read                                   │  │    │
│  │  │ 5. Cache token (TTL: 4 min for 5 min tokens)                        │  │    │
│  │  └────────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                          │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ MCP Action Control Middleware                                       │  │    │
│  │  │                                                                    │  │    │
│  │  │ • Parse JSON-RPC request                                            │  │    │
│  │  │ • Route to correct backend based on tool name                       │  │    │
│  │  │ • Inject OAuth token into request                                   │  │    │
│  │  │ • Proxy request to backend                                          │  │    │
│  │  └────────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                          │    │
│  └──────────────────────────────────┬───────────────────────────────────────┘    │
│                                     │                                             │
│                  ┌──────────────────┼──────────────────┐                         │
│                  │                  │                  │                         │
│                  ▼                  ▼                  ▼                         │
│           ┌───────────┐      ┌───────────┐      ┌───────────┐                    │
│           │ HubSpot   │      │ Notion    │      │ GDrive    │                    │
│           │ MCP Server│      │ MCP Server│      │ MCP Server│                    │
│           │           │      │           │      │           │                    │
│           │ OAuth 2.1 │      │ OAuth 2.1 │      │ OAuth 2.1 │                    │
│           └───────────┘      └───────────┘      └───────────┘                    │
│                                                                                  │
│  KEYCLOAK (Authorization Server)                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ • Token Exchange Endpoint (RFC 8693)                                     │    │
│  │ • Custom Token Validator for Task Tokens                                 │    │
│  │ • Audience Mappers per backend                                           │    │
│  │ • Scope Registration per MCP server                                      │    │
│  │ • Dynamic Client Registration (RFC 7591)                                 │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Key Components**:
- `OAuthTokenExchangeMiddleware` - Exchanges Task Token for OAuth tokens
- `MCPActionControlMiddleware` - Routes and proxies MCP requests
- `KeycloakMCPClient` - Python client for Keycloak integration
- `mcp_server_scopes` DB table - Maps scopes to tools per server
- `BackendOAuthTokenManager` - Caches and refreshes OAuth tokens

**Standards Implemented**:
- RFC 8693 (Token Exchange)
- RFC 7591 (Dynamic Client Registration)
- RFC 9728 (OAuth Protected Resource Metadata)
- RFC 8707 (Resource Indicators for audience binding)

---

### Approach 2: MCP Governance & Protocol (Virtual MCP Server)

**Problem Solved**: How to govern the AI agent's experience - what tools they see, how results are filtered, and how the protocol is parsed.

**Core Insight**: The Gateway should present itself as an **MCP Server** to agents, aggregating and governing access to multiple backend MCP servers.

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    APPROACH 2: VIRTUAL MCP SERVER                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  AI Agent (with MCP Client)                                                      │
│     │                                                                            │
│     │ MCP Protocol: initialize, tools/list, tools/call                          │
│     │ Transport: JSON-RPC 2.0 over HTTP/SSE                                     │
│     ▼                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    DEEPTRAIL GATEWAY                                      │    │
│  │                    (Virtual MCP Server)                                   │    │
│  │                                                                          │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ MCP PROTOCOL LAYER                                                  │  │    │
│  │  │                                                                    │  │    │
│  │  │ class MCPProtocolHandler:                                           │  │    │
│  │  │     async def handle_initialize(self, params):                      │  │    │
│  │  │         # Respond with Gateway's serverInfo                         │  │    │
│  │  │         return {                                                    │  │    │
│  │  │             "protocolVersion": "2024-11-05",                        │  │    │
│  │  │             "serverInfo": {"name": "DeepTrail Gateway"},            │  │    │
│  │  │             "capabilities": {"tools": {}, "resources": {}}          │  │    │
│  │  │         }                                                           │  │    │
│  │  │                                                                    │  │    │
│  │  │     async def handle_tools_list(self, agent_id):                    │  │    │
│  │  │         # Aggregate tools from all backends                         │  │    │
│  │  │         # Apply capability filtering per agent policy               │  │    │
│  │  │         # Add namespace prefixes (hubspot.get_contact)              │  │    │
│  │  │         return filtered_tools                                       │  │    │
│  │  │                                                                    │  │    │
│  │  │     async def handle_tools_call(self, tool_name, arguments):        │  │    │
│  │  │         # Route to correct backend based on namespace               │  │    │
│  │  │         # Apply governance rules                                    │  │    │
│  │  │         return result                                               │  │    │
│  │  └────────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                          │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ MCP GOVERNANCE LAYER                                                │  │    │
│  │  │                                                                    │  │    │
│  │  │ @dataclass                                                          │  │    │
│  │  │ class MCPPolicy:                                                    │  │    │
│  │  │     agent_id: str                                                   │  │    │
│  │  │     tool_rules: List[MCPToolRule]                                   │  │    │
│  │  │     resource_rules: List[MCPResourceRule]                           │  │    │
│  │  │     rate_limits: MCPRateLimits                                      │  │    │
│  │  │     content_filters: MCPContentFilters                              │  │    │
│  │  │                                                                    │  │    │
│  │  │ @dataclass                                                          │  │    │
│  │  │ class MCPToolRule:                                                  │  │    │
│  │  │     pattern: str          # "hubspot.*" or "notion.search_*"        │  │    │
│  │  │     action: str           # "allow", "deny", "require_approval"     │  │    │
│  │  │     constraints: dict     # {"max_results": 100}                    │  │    │
│  │  │                                                                    │  │    │
│  │  │ async def evaluate_tool_call(self, tool_name, arguments, policy):   │  │    │
│  │  │     # 1. Check tool visibility                                      │  │    │
│  │  │     # 2. Validate parameters against constraints                    │  │    │
│  │  │     # 3. Check rate limits                                          │  │    │
│  │  │     # 4. Apply input content filters                                │  │    │
│  │  │     # 5. Execute tool                                               │  │    │
│  │  │     # 6. Apply output content filters (PII masking)                 │  │    │
│  │  │     # 7. Log audit event                                            │  │    │
│  │  │     # 8. Update usage counters                                      │  │    │
│  │  └────────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                          │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ CAPABILITY AGGREGATOR                                               │  │    │
│  │  │                                                                    │  │    │
│  │  │ • Connects to multiple backend MCP servers                          │  │    │
│  │  │ • Collects tools/list from each backend                             │  │    │
│  │  │ • Applies namespace prefixing:                                      │  │    │
│  │  │   - hubspot.get_contact                                             │  │    │
│  │  │   - notion.search_pages                                             │  │    │
│  │  │   - gdrive.list_files                                               │  │    │
│  │  │ • Filters based on agent policy                                     │  │    │
│  │  │ • Returns aggregated capability list                                │  │    │
│  │  └────────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                          │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ ENVOY EXT_AUTHZ INTEGRATION                                         │  │    │
│  │  │                                                                    │  │    │
│  │  │ • DeepSecure Control Plane as Policy Decision Point (PDP)           │  │    │
│  │  │ • Validates Agent JWT via gRPC ext_authz                            │  │    │
│  │  │ • Returns allowed tools/permissions in response headers             │  │    │
│  │  │ • Injects credentials into upstream requests                        │  │    │
│  │  └────────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                          │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  DEEPSECURE CONTROL PLANE (Policy Decision Point)                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ • Agent identity and authentication                                      │    │
│  │ • Policy storage and evaluation                                          │    │
│  │ • Task Token issuance                                                    │    │
│  │ • Secret vault (split-key storage)                                       │    │
│  │ • Audit trail                                                            │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Key Components**:
- `MCPProtocolHandler` - Handles MCP JSON-RPC methods
- `MCPPolicy` / `MCPToolRule` / `MCPResourceRule` - Policy data classes
- `MCPRateLimits` / `MCPContentFilters` - Governance configurations
- `CapabilityAggregator` - Collects and namespaces tools from backends
- `ResponseFilteringMiddleware` - Masks PII, removes sensitive fields
- `UsageTrackingMiddleware` - Token/action accounting

**Governance Features**:
- **Capability Filtering**: Agent only sees allowed tools
- **Namespace Prefixing**: `hubspot.get_contact`, `notion.search_pages`
- **Parameter Validation**: Enforce constraints from task policy
- **Result Filtering**: Mask PII, remove sensitive fields
- **Prompt Injection Detection**: Block malicious tool arguments
- **Rate Limiting**: Per-tool, per-task quotas

---

### Why Both Approaches Are Needed

| Approach | What It Solves | What It Doesn't Solve |
|----------|---------------|----------------------|
| **Approach 1 (OAuth HTTP Proxy)** | Secure communication with OAuth-compliant MCP servers | Governance, capability filtering, result masking |
| **Approach 2 (Virtual MCP Server)** | Agent experience governance, protocol handling | Getting valid OAuth tokens for real MCP servers |

**The Problem**: If you only implement Approach 2, the Gateway can govern what agents see, but it can't actually **talk to** backend MCP servers like HubSpot because:
- Agent's internal tokens have wrong `aud` (audience)
- Backend servers expect OAuth 2.0/2.1 tokens
- Scopes need to be translated from internal URNs to OAuth scopes

**The Solution**: Implement **both approaches as layers** in the same Gateway:
1. **Upper Layer (Approach 2)**: Virtual MCP Server for governance
2. **Lower Layer (Approach 1)**: OAuth client for backend communication

---

### 1.1 Comparison of Two Design Approaches

| Feature | OAuth-HTTP Proxy (Agent Authorization Focus) | MCP Governance & Protocol (Virtual MCP Server) |
|---------|--------------------------|----------------------------------|
| **Primary Role** | Gateway is an OAuth Client/Exchanger | Gateway is a Virtual MCP Server |
| **Auth Strategy** | Keycloak integration, RFC 8693 (Token Exchange), RFC 7591 (DCR) | Envoy ext_authz, DeepSecure Control Plane as PDP |
| **Backend View** | Backend MCP servers are external OAuth resources | Backend MCP servers are "capabilities" to aggregate |
| **Key Protocols** | OAuth 2.0/2.1, RFC 9728 (Protected Resource Metadata) | JSON-RPC 2.0 (MCP), SSE, Envoy/gRPC |
| **Agent View** | Agent provides Task Token → gets specialized access to specific APIs | Agent sees single "DeepTrail MCP Server" exposing filtered tools |
| **Protocol Handling** | HTTP proxy with MCP-aware middleware | Native MCP protocol (initialize, tools/list, tools/call) |
| **Tool Disambiguation** | Task specifies the server directly | Namespace prefixing (hubspot.create_task) |

### 1.2 Architectural Intersection: What Each Approach Solves

- **Approach 1 (OAuth HTTP Proxy)** solves: How to securely talk to "Real" MCP servers (like HubSpot or Notion) that require standards-compliant OAuth tokens.
- **Approach 2 (MCP Governance & Protocol)** solves: How to govern the AI agent's experience (what tools they see, how results are filtered, protocol parsing).

### 1.3 Gateway Identity Comparison

**Approach 1 (OAuth HTTP Proxy)** designs the gateway as an **OAuth-aware HTTP proxy**:

```
Agent → Gateway → [OAuth Exchange] → Backend MCP Server
              ↓
         Keycloak (AS)
```

**Approach 2 (MCP Governance & Protocol)** designs the gateway as a **Virtual MCP Server** itself:

```
Agent → DeepTrail Gateway (presents as MCP Server)
              ↓
         [Aggregates multiple backends]
              ↓
         Backend MCP Servers (HubSpot, Notion, etc.)
```

---

## 2. The OAuth Challenge for Virtual MCP Server Design

When the Gateway acts as a Virtual MCP Server (Approach 2), it successfully governs the agent's MCP experience. However, the Gateway still needs to communicate with real backend MCP servers (HubSpot, Notion, etc.) that require OAuth authentication. This section describes how the Virtual MCP Server design addresses OAuth requirements.

### 2.1 The Challenge: Backend MCP Servers Require OAuth

While the agent connects to the Gateway using MCP protocol, the Gateway then needs to connect to real backend MCP servers like HubSpot, which:

1. **Require OAuth tokens with correct audience** (`aud: https://mcp.hubspot.com`)
2. **Validate tokens per RFC 9728** - they won't accept tokens meant for the Gateway
3. **May require Dynamic Client Registration** (RFC 7591) - the Gateway must be registered as a client
4. **Enforce scope validation** - scopes must map to their tool permissions

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     MCP AUTHORIZATION ARCHITECTURE (from spec)                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  MCP Client (Agent/Host) ────────► MCP Server (Resource Server)                 │
│        │                                     │                                   │
│        │                                     │                                   │
│        └───────► Authorization Server ◄──────┘                                  │
│                  (OAuth 2.0/2.1)                                                │
│                                                                                  │
│  Key Requirements from MCP Spec:                                                │
│  • MCP servers MUST implement RFC 9728 (OAuth 2.0 Protected Resource Metadata)  │
│  • MCP clients MUST use resource parameter (RFC 8707) for audience binding      │
│  • Authorization servers MUST support PKCE (OAuth 2.1)                          │
│  • Tokens MUST be audience-bound to specific MCP servers                        │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Technical Challenges for Virtual MCP Server OAuth Integration

The Virtual MCP Server design must address these OAuth-related challenges when connecting to backend MCP servers:

| Challenge | Description | Severity |
|-----------|-------------|----------|
| **Audience Mismatch** | Agent's token has `aud: gateway.deeptrail.io`, but HubSpot expects `aud: mcp.hubspot.com` | Critical |
| **Token Exchange Gap** | Gateway needs to exchange internal tokens for backend-specific OAuth tokens | High |
| **Scope Translation** | Internal URN-based permissions must map to OAuth scopes | High |
| **DCR Requirements** | Gateway must be pre-registered or use RFC 7591 with each backend | Medium |
| **Token Lifecycle** | Backend tokens are short-lived (5-15 min per MCP spec), need refresh | Medium |
| **Consent Flow** | Some backends require user consent - Gateway can't do this on behalf of agent | High |

### 2.3 Solution: OAuth Authorization Layer

The solution to these OAuth challenges is to implement an **OAuth Authorization Layer** within the Gateway. This layer sits between the Virtual MCP Server (which handles agent governance) and the backend MCP servers (which require OAuth tokens).

**Key Insight**: Token Exchange (RFC 8693) is the *core mechanism*, but the complete solution requires a full OAuth Authorization Layer that:

| Component | Purpose |
|-----------|---------|
| **Token Validator** | Validates incoming Agent JWT and Task Token from the agent |
| **Token Exchange Client** | Calls Keycloak/IdP using RFC 8693 to exchange internal tokens for backend-specific OAuth tokens |
| **Audience Mapper** | Maps internal permissions to correct `aud` claim for each backend (e.g., `mcp.hubspot.com`) |
| **Scope Translator** | Converts internal URN-based permissions to OAuth scopes (e.g., `urn:deepsecure:hubspot:contacts:read` → `hubspot:contacts:read`) |
| **Token Cache** | Caches backend OAuth tokens with TTL (4 min for 5 min tokens) to avoid repeated exchanges |
| **OAuth Client Registry** | Manages pre-registered or dynamically registered OAuth client credentials per backend |

**Token Exchange Flow (RFC 8693)**:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         TOKEN EXCHANGE FLOW (RFC 8693)                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Agent ─────────────────► DeepTrail Gateway ─────────────► HubSpot MCP Server   │
│    │                           │                                   │            │
│    │ Agent JWT                 │                                   │            │
│    │ + Task Token              │                                   │            │
│    │                           │                                   │            │
│    │                     ┌─────▼─────┐                             │            │
│    │                     │ Keycloak  │                             │            │
│    │                     │           │                             │            │
│    │                     │ RFC 8693  │                             │            │
│    │                     │ Token     │                             │            │
│    │                     │ Exchange  │                             │            │
│    │                     └─────┬─────┘                             │            │
│    │                           │                                   │            │
│    │                           │ OAuth Token with:                 │            │
│    │                           │ - aud: mcp.hubspot.com            │            │
│    │                           │ - scope: hubspot:contacts:read    │            │
│    │                           │ - sub: agent-sales-001            │            │
│    │                           │                                   │            │
│    │                           └───────────────────────────────────►            │
│    │                                     Bearer {oauth_token}                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Does the Virtual MCP Server Need a Separate HTTP Proxy?**

No. The OAuth Authorization Layer capabilities are **embedded within the Gateway** rather than being a separate HTTP proxy in front of backend servers:

- **Embedded Approach (Recommended)**: The Gateway's OAuth Authorization Layer directly exchanges tokens and makes authenticated HTTP calls to backend MCP servers. The Gateway acts as an **MCP Client** (not an HTTP proxy) to each backend.
- **Separate HTTP Proxy (Approach 1 standalone)**: A pure HTTP proxy approach would intercept all HTTP traffic and inject OAuth tokens, but wouldn't understand MCP semantics or provide governance.

The OAuth Authorization Layer provides the *authorization capabilities* of Approach 1 (OAuth HTTP Proxy) while being integrated into the Virtual MCP Server architecture. This leads naturally to the unified architecture in Section 3, which combines both approaches.

---

## 3. Best of Both Worlds: Unified Architecture

The recommended approach is to implement **both layers** within the Gateway:

1. **MCP Protocol Layer** - For governance, aggregation, and agent experience
2. **OAuth Authorization Layer** - For standards-compliant backend communication

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                   UNIFIED ARCHITECTURE                                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                           AI AGENT                                       │    │
│  │                                                                          │    │
│  │  Agent sees ONE MCP Server: "DeepTrail Virtual MCP Server"               │    │
│  │  Connects via: MCP Protocol (JSON-RPC over HTTP/SSE)                     │    │
│  └──────────────────────────────────┬───────────────────────────────────────┘    │
│                                     │                                            │
│                                     ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐     │
│  │              DEEPTRAIL GATEWAY: VIRTUAL MCP SERVER LAYER                 │    │
│  │              (MCP Governance & Orchestration)                            │    │
│  │                                                                          │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ MCP PROTOCOL LAYER                                                  │  │    │
│  │  │ • Handles initialize/initialized handshake                          │  │    │
│  │  │ • Maintains session state (initializing → ready)                    │  │    │
│  │  │ • Presents its own serverInfo: {name: "DeepTrail Gateway"}          │  │    │
│  │  │ • Responds to tools/list, resources/list, prompts/list             │  │    │
│  │  │ • Routes tools/call to appropriate backend                          │  │    │
│  │  └────────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                          │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ MCP GOVERNANCE LAYER                                                │  │    │
│  │  │ • Capability Filtering: Agent only sees allowed tools               │  │    │
│  │  │ • Namespace Prefixing: hubspot.get_contact, notion.search_pages    │  │    │
│  │  │ • Parameter Validation: Enforce constraints from task policy        │  │    │
│  │  │ • Result Filtering: Mask PII, remove sensitive fields               │  │    │
│  │  │ • Prompt Injection Detection: Block malicious tool arguments        │  │    │
│  │  │ • Rate Limiting: Per-tool, per-task quotas                          │  │    │
│  │  └────────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                          │    │
│  └──────────────────────────────────┬───────────────────────────────────────┘    │
│                                     │                                             │
│                                     ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │              DEEPTRAIL GATEWAY: OAUTH CLIENT/EXCHANGER LAYER             │    │
│  │              (OAuth Http Proxy - Standards-Compliant Auth)                   │    │
│  │                                                                          │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ MCP AUTHORIZATION LAYER                                             │  │    │
│  │  │ • Exposes /.well-known/oauth-protected-resource (RFC 9728)          │  │    │
│  │  │ • Token Exchange: Task Token → OAuth token (RFC 8693)               │  │    │
│  │  │ • OAuth Client to each backend MCP server                           │  │    │
│  │  │ • Audience binding per RFC 8707 (resource indicators)               │  │    │
│  │  │ • Scope mapping: internal URNs → OAuth scopes                       │  │    │
│  │  │ • Token caching with short TTL (4 min for 5 min tokens)             │  │    │
│  │  └────────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                          │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ KEYCLOAK INTEGRATION                                                │  │    │
│  │  │ • Token Exchange Endpoint: /protocol/openid-connect/token           │  │    │
│  │  │ • Custom Token Validator: DeepTrail Task Token                      │  │    │
│  │  │ • Audience Mappers: Per-backend server configuration                │  │    │
│  │  │ • Scope Registration: MCP-specific scopes per server                │  │    │
│  │  └────────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                          │    │
│  └──────────────────────────────────┬───────────────────────────────────────┘    │
│                                     │                                             │
│         ┌───────────────────────────┼───────────────────────────┐                │
│         │                           │                           │                │
│         ▼                           ▼                           ▼                │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐              │
│  │ HubSpot MCP     │    │ Notion MCP      │    │ Custom MCP      │              │
│  │ Server          │    │ Server          │    │ Server          │              │
│  │                 │    │                 │    │                 │              │
│  │ OAuth Required: │    │ OAuth Required: │    │ OAuth Required: │              │
│  │ aud: mcp.hubspot│    │ aud: mcp.notion │    │ aud: mcp.custom │              │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Gateway's Three MCP Roles

In the "Gateway as Virtual MCP Server" model, the Gateway plays **three roles simultaneously**:

### 4.1 Official MCP Architecture (from spec)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     OFFICIAL MCP ARCHITECTURE                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        MCP HOST (AI Application)                         │    │
│  │                                                                          │    │
│  │  Examples: Claude Desktop, VS Code, Cursor                               │    │
│  │  • Coordinates and manages one or multiple MCP Clients                   │    │
│  │  • Provides UI for user interaction                                      │    │
│  │  • Integrates with LLM for tool use decisions                            │    │
│  │                                                                          │    │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                │    │
│  │  │ MCP Client 1  │  │ MCP Client 2  │  │ MCP Client 3  │                │    │
│  │  │               │  │               │  │               │                │    │
│  │  │ Maintains     │  │ Maintains     │  │ Maintains     │                │    │
│  │  │ dedicated     │  │ dedicated     │  │ dedicated     │                │    │
│  │  │ connection    │  │ connection    │  │ connection    │                │    │
│  │  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘                │    │
│  └──────────┼──────────────────┼──────────────────┼─────────────────────────┘    │
│             │                  │                  │                              │
│             ▼                  ▼                  ▼                              │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                        │
│  │ MCP Server A  │  │ MCP Server B  │  │ MCP Server C  │                        │
│  │ (Filesystem)  │  │ (Database)    │  │ (Sentry)      │                        │
│  │ Local/STDIO   │  │ Local/STDIO   │  │ Remote/HTTP   │                        │
│  └───────────────┘  └───────────────┘  └───────────────┘                        │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 DeepTrail Gateway Role Mapping

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     DEEPTRAIL GATEWAY ROLE MAPPING                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    AI AGENT FRAMEWORK (e.g., LangChain, CrewAI)          │    │
│  │                                                                          │    │
│  │  Acts as: MCP HOST + MCP CLIENT                                          │    │
│  │                                                                          │    │
│  │  • The agent framework is the "AI application"                           │    │
│  │  • It instantiates an MCP Client to connect to DeepTrail Gateway         │    │
│  │  • It decides which tools to call based on LLM reasoning                 │    │
│  │                                                                          │    │
│  │  ┌───────────────────────────────────────────────────────────────────┐   │    │
│  │  │  MCP Client (SDK-provided, e.g., mcp-python-sdk)                  │   │    │
│  │  │                                                                   │   │    │
│  │  │  • Single connection to DeepTrail Gateway                         │   │    │
│  │  │  • Sees aggregated tools from all backends                        │   │    │
│  │  │  • Uses HTTP Streamable transport (remote)                        │   │    │
│  │  └───────────────────────────────────────────────────────────────────┘   │    │
│  └──────────────────────────────────┬───────────────────────────────────────┘    │
│                                     │                                             │
│                                     │ MCP Protocol (JSON-RPC)                    │
│                                     │ Transport: HTTP + SSE                      │
│                                     ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    DEEPTRAIL GATEWAY                                      │    │
│  │                                                                          │    │
│  │  Acts as: MCP SERVER (to agents) + MCP HOST + MCP CLIENT (to backends)  │    │
│  │                                                                          │    │
│  │  ┌───────────────────────────────────────────────────────────────────┐   │    │
│  │  │  AS MCP SERVER (facing agents):                                   │   │    │
│  │  │                                                                   │   │    │
│  │  │  • Handles initialize requests, responds with serverInfo          │   │    │
│  │  │  • Responds to tools/list with AGGREGATED + FILTERED list         │   │    │
│  │  │  • Receives tools/call and routes to backend                      │   │    │
│  │  │  • Implements MCP Authorization (RFC 9728 metadata)               │   │    │
│  │  │  • This is the "Virtual MCP Server"                               │   │    │
│  │  └───────────────────────────────────────────────────────────────────┘   │    │
│  │                                                                          │    │
│  │  ┌───────────────────────────────────────────────────────────────────┐   │    │
│  │  │  AS MCP HOST (internal coordinator):                              │   │    │
│  │  │                                                                   │   │    │
│  │  │  • Manages multiple MCP Clients (one per backend server)          │   │    │
│  │  │  • Coordinates capability aggregation                              │   │    │
│  │  │  • Applies governance policies                                     │   │    │
│  │  │  • Routes tools/call to correct backend                           │   │    │
│  │  └───────────────────────────────────────────────────────────────────┘   │    │
│  │                                                                          │    │
│  │  ┌───────────────────────────────────────────────────────────────────┐   │    │
│  │  │  AS MCP CLIENT(S) (facing backends):                              │   │    │
│  │  │                                                                   │   │    │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │   │    │
│  │  │  │ MCP Client  │  │ MCP Client  │  │ MCP Client  │               │   │    │
│  │  │  │ → HubSpot   │  │ → Notion    │  │ → GDrive    │               │   │    │
│  │  │  │             │  │             │  │             │               │   │    │
│  │  │  │ OAuth token │  │ OAuth token │  │ OAuth token │               │   │    │
│  │  │  │ for HubSpot │  │ for Notion  │  │ for GDrive  │               │   │    │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘               │   │    │
│  │  └───────────────────────────────────────────────────────────────────┘   │    │
│  │                                                                          │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│         ┌───────────────────────────┼───────────────────────────┐                │
│         │                           │                           │                │
│         ▼                           ▼                           ▼                │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐              │
│  │ HubSpot MCP     │    │ Notion MCP      │    │ GDrive MCP      │              │
│  │ Server          │    │ Server          │    │ Server          │              │
│  │                 │    │                 │    │                 │              │
│  │ Real MCP Server │    │ Real MCP Server │    │ Real MCP Server │              │
│  │ OAuth Protected │    │ OAuth Protected │    │ OAuth Protected │              │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Key Insight: Gateway Has Three MCP Roles

| Role | Direction | Description |
|------|-----------|-------------|
| **MCP Server** | Facing Agent | Gateway IS the MCP server from the agent's perspective. It handles `initialize`, responds to `tools/list` with governed results, receives `tools/call`. |
| **MCP Host** | Internal | Gateway coordinates multiple MCP clients (one per backend). It aggregates capabilities, applies governance policies, routes requests. |
| **MCP Client** | Facing Backends | Gateway creates MCP client connections to each backend MCP server (HubSpot, Notion, etc.). Each client has its own OAuth token. |

---

## 5. Gateway Architecture Tradeoffs

This section compares the **implementation tradeoffs** between the two gateway design approaches described in Section 1. While Section 3 recommends combining both approaches (Unified Architecture), understanding these tradeoffs helps with:

- **Phased implementation decisions**: Which layer to build first
- **Resource allocation**: Estimated development effort for each approach
- **Performance expectations**: Latency and complexity overhead
- **Capability gaps**: What each approach provides vs. requires

### 5.1 Token Flow Differences

| Aspect | OAuth-HTTP Proxy (Agent Authorization Focus) | MCP Governance & Protocol (Virtual MCP Server) |
|--------|----------------------------------------------|------------------------------------------------|
| **Primary Token** | Task Token (internal) exchanged for OAuth | Agent JWT validated via ext_authz |
| **Token Exchange** | RFC 8693 via Keycloak | Not emphasized (uses existing JWTs) |
| **Backend Auth** | OAuth 2.1 access tokens per MCP server | Handled by existing secret injection |

### 5.2 Capability Discovery

| Aspect | OAuth-HTTP Proxy (Agent Authorization Focus) | MCP Governance & Protocol (Virtual MCP Server) |
|--------|----------------------------------------------|------------------------------------------------|
| **Tool Discovery** | MCP servers declare scopes in Keycloak | Gateway aggregates via Capability Aggregator |
| **Namespace Strategy** | Not explicitly defined | Server prefix: `hubspot.get_contact`, `notion.search` |
| **Filtering** | Scope-based (OAuth scopes) | Policy-based capability filtering |

### 5.3 MCP Protocol Handling

**OAuth-HTTP Proxy (Agent Authorization Focus)** treats MCP as an HTTP API:
- Uses `OAuthTokenExchangeMiddleware`
- Uses `MCPActionControlMiddleware`
- Proxies JSON-RPC requests

**MCP Governance & Protocol (Virtual MCP Server)** implements native MCP protocol:
- `MCPProtocolHandler` with method handlers
- `initialize` handshake with capability negotiation
- MCP session state management (`initializing → ready → closed`)

### 5.4 Architecture Tradeoffs Summary

| Tradeoff | OAuth-HTTP Proxy (Agent Authorization Focus) | MCP Governance & Protocol (Virtual MCP Server) | Combined |
|----------|----------------------------------------------|------------------------------------------------|----------|
| **Complexity** | Adds Keycloak dependency | Adds MCP protocol handler | Higher, but complete |
| **Latency** | Token exchange adds ~50-100ms | Protocol parsing adds ~10ms | ~60-110ms added |
| **Flexibility** | Works with any OAuth MCP server | Full governance control | Both |
| **Standards Compliance** | RFC 9728, 8693, 7591 | MCP JSON-RPC 2.0 | Full compliance |
| **Development Effort** | 4-6 weeks for OAuth layer | 6-8 weeks for MCP layer | 10-14 weeks total |

---

# Part II: Token Architecture

## Why DeepSecure Needs a Token Architecture

When AI agents act on behalf of users, traditional authentication models break down. A single OAuth token or API key cannot answer critical questions that enterprises need to answer:

| Problem | Traditional Auth | DeepSecure Token Architecture |
|---------|------------------|-------------------------------|
| **Who authorized this action?** | Unknown - just "valid token" | Full chain: User → Agent → Task → Action |
| **What can this agent do?** | All-or-nothing scopes | Layered, attenuated permissions per task |
| **Can the agent exceed user permissions?** | Yes, if given broad scopes | No - monotonic attenuation enforced cryptographically |
| **Who is accountable for agent actions?** | Unclear | Always traces back to delegating user |
| **How do we integrate with enterprise IdP?** | Separate systems | Federation with Okta/Entra ID as identity source |
| **How do we talk to OAuth-protected MCP servers?** | Manual token management | Automatic token exchange (RFC 8693) |

### Problems Solved by the Token Architecture

1. **Authenticated Delegation**: Users explicitly delegate specific permissions to specific agents. The delegation is cryptographically bound - an agent cannot claim permissions it wasn't granted.

2. **Monotonic Attenuation**: Permissions can only **decrease** as you go down the token chain (User → Agent → Task → MCP). An agent cannot grant a task more permissions than the agent has, and a task cannot request more from an MCP server than the task allows.

3. **Audit Attribution**: Every action can be traced back through the token chain to the human user who authorized it. This is critical for compliance (SOC2, GDPR) and incident response.

4. **Least Privilege Enforcement**: Task Tokens scope permissions to exactly what's needed for a specific task. An agent authorized for "CRM read" cannot suddenly write to the database.

5. **Enterprise IdP Integration**: The token architecture federates with existing enterprise identity systems (Okta, Microsoft Entra ID) rather than replacing them. User identity comes from the IdP; DeepSecure adds the delegation and agent layers.

6. **MCP OAuth Compliance**: Backend MCP servers require standards-compliant OAuth tokens with correct audience binding. The token architecture provides automatic token exchange from internal Task Tokens to MCP OAuth tokens.

### Token Hierarchy at a Glance

```
User ID-Token (IdP)          ← "I am Sarah from Acme Corp"
    │
    ▼
Agent-ID Token (IdP)         ← "Agent SDR-001 is owned by Sarah"
    │
    ▼
Delegation Token (DeepTrail) ← "Sarah grants SDR-001 these permissions"
    │
    ▼
Agent Session JWT (DeepTrail)← "SDR-001 authenticated for this session"
    │
    ▼
Task Token (DeepTrail)       ← "This specific task can do X, Y, Z"
    │
    ▼
MCP OAuth Token (Keycloak)   ← "Standards-compliant token for HubSpot"
```

Each layer **attenuates** (narrows) permissions from the layer above. The MCP OAuth Token at the bottom can never have more permissions than the User ID-Token at the top authorized.

---

## 6. Token Hierarchy Overview

The token hierarchy involves **three different systems** (Enterprise IdP, DeepTrail Control Plane, and Keycloak), each responsible for different token types. Understanding which system manages what is critical for:

- **Architecture decisions**: Where to implement new features
- **Troubleshooting**: Which system to investigate when tokens fail validation
- **Security boundaries**: Which system holds sensitive keys and secrets
- **Integration planning**: What APIs and protocols each system exposes

This section answers the operational question: **"When something goes wrong with authentication, which system do I look at?"**

### 6.1 Who Manages What

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                       AUTHENTICATION & TOKEN HIERARCHY                                    │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                      WHO MANAGES WHAT                                            │    │
│  ├─────────────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                                  │    │
│  │  ENTERPRISE IDP (Okta/Entra) manages:                                           │    │
│  │  ┌────────────────────────────────────────────────────────────────────────────┐ │    │
│  │  │  ✓ User identity (OIDC)                                                    │ │    │
│  │  │  ✓ User authentication (SSO, MFA)                                          │ │    │
│  │  │  ✓ User groups/roles                                                       │ │    │
│  │  │  ✓ Agent registration (via DCR or custom app)                              │ │    │
│  │  │  ✓ Agent-ID token issuance (with owner claim)                              │ │    │
│  │  │  ✓ Agent lifecycle (SCIM provisioning)                                     │ │    │
│  │  └────────────────────────────────────────────────────────────────────────────┘ │    │
│  │                                                                                  │    │
│  │  DEEPTRAIL CONTROL PLANE manages:                                               │    │
│  │  ┌────────────────────────────────────────────────────────────────────────────┐ │    │
│  │  │  ✓ IdP token validation (trusts Okta/Entra)                                │ │    │
│  │  │  ✓ Agent Authentication (Ed25519 challenge-response)                       │ │    │
│  │  │  ✓ Agent JWT (issued after auth, contains standing permissions)            │ │    │
│  │  │  ✓ Delegation Token issuance (binds IdP user → agent)                      │ │    │
│  │  │  ✓ Task Tokens (scoped permissions for specific tasks)                     │ │    │
│  │  │  ✓ Delegation Tokens (macaroon-based, attenuation)                         │ │    │
│  │  │  ✓ Policy Engine (what permissions agents have)                            │ │    │
│  │  │  ✓ Secret Vault (split-key storage)                                        │ │    │
│  │  │  ✓ Audit trail (with IdP user attribution)                                 │ │    │
│  │  └────────────────────────────────────────────────────────────────────────────┘ │    │
│  │                                                                                  │    │
│  │  KEYCLOAK manages:                                                               │    │
│  │  ┌────────────────────────────────────────────────────────────────────────────┐ │    │
│  │  │  ✓ MCP OAuth Tokens (standards-compliant OAuth 2.0/2.1)                    │ │    │
│  │  │  ✓ Token Exchange (RFC 8693: Task Token → OAuth Access Token)             │ │    │
│  │  │  ✓ OAuth Scopes (mcp:tools, hubspot:contacts:read, etc.)                   │ │    │
│  │  │  ✓ Audience Binding (per RFC 8707, per MCP server)                         │ │    │
│  │  │  ✓ User SSO (for human users, federated with Okta/Azure AD)               │ │    │
│  │  │  ✓ MCP Server Registration (dynamic client registration)                   │ │    │
│  │  └────────────────────────────────────────────────────────────────────────────┘ │    │
│  │                                                                                  │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Key Answers

| Question | Answer |
|----------|--------|
| Does agent get auth per session with multiple tasks? | **Yes.** Agent authenticates ONCE to get an Agent JWT (session). Within that session, agent can create MULTIPLE tasks, each with its own Task Token. |
| Who manages Agent Auth? | **DeepTrail Control Plane.** Agent auth uses Ed25519 challenge-response (cryptographic identity), NOT OAuth. |
| Who manages MCP Auth? | **Keycloak.** MCP servers require standards-compliant OAuth 2.0/2.1. Keycloak handles token exchange. |
| How are they connected? | **Gateway bridges them.** It validates Agent JWT + Task Token, then exchanges Task Token for OAuth tokens via Keycloak. |

---

## 7. Complete Six-Layer Token Hierarchy (Detailed)

While Section 6 explained *who manages what*, this section provides the **complete technical specification** for each token layer. This detailed view is essential for:

- **Implementers**: What claims to include when issuing tokens, what to validate when receiving them
- **Security auditors**: Verifying the cryptographic binding chain is intact
- **Debuggers**: Understanding what each claim means when inspecting tokens in logs
- **Compliance teams**: Documenting what data flows through each token for privacy reviews

**Why Six Layers?** The research paper "Authenticated Delegation and Authorized AI Agents" proposes a three-token model (User ID-Token, Agent-ID Token, Delegation Token). DeepSecure extends this to six layers because:

| Research Model | DeepSecure Extension | Why Needed |
|----------------|---------------------|------------|
| User ID-Token | ✓ Layer 0: User ID-Token | Same - human identity from IdP |
| Agent-ID Token | ✓ Layer 1: Agent-ID Token | Same - agent identity with owner binding |
| Delegation Token | ✓ Layer 2: Delegation Token | Same - user grants permissions to agent |
| *(not in paper)* | **Layer 3: Agent Session JWT** | Needed for session management - agent authenticates once, gets session token |
| *(not in paper)* | **Layer 4: Task Token** | Needed for least privilege - each task gets only the permissions it needs |
| *(not in paper)* | **Layer 5: MCP OAuth Token** | Needed for MCP compliance - backend servers require standards-compliant OAuth |

With enterprise IdP, the token hierarchy includes **6 layers** with complete claim specifications:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│              COMPLETE TOKEN HIERARCHY (WITH ENTERPRISE IDP)                              │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  LAYER 0: USER ID-TOKEN (from Enterprise IdP)                                           │
│  ┌────────────────────────────────────────────────────────────────────────────────┐     │
│  │  Issuer: Enterprise IdP (Okta/Entra)                                            │     │
│  │  Obtained: User login via SSO (OIDC)                                            │     │
│  │  Claims: sub, email, groups, roles, mfa_verified                                │     │
│  │  Purpose: Prove human user identity, basis for all delegation                   │     │
│  │  Lifetime: ~1 hour (standard OIDC)                                               │     │
│  └────────────────────────────────────────────────────────────────────────────────┘     │
│                              │                                                           │
│                              │ User registers agent (one-time)                           │
│                              ▼                                                           │
│  LAYER 1: AGENT-ID TOKEN (from Enterprise IdP)                                          │
│  ┌────────────────────────────────────────────────────────────────────────────────┐     │
│  │  Issuer: Enterprise IdP (Okta/Entra)                                            │     │
│  │  Obtained: Via OAuth2 Dynamic Client Registration (RFC 7591) or custom flow     │     │
│  │  Claims: {                                                                      │     │
│  │    sub: "agent-sdr-001",                                                        │     │
│  │    owner: "sarah@company.com",        ← CRITICAL: explicit user-agent binding  │     │
│  │    party_type: "first_party",                                                   │     │
│  │    public_key: "ed25519:abc123...",   ← Agent's Ed25519 public key              │     │
│  │    metadata_uri: "https://deeptrail.io/agents/sdr-001/profile.json",            │     │
│  │    iss: "https://company.okta.com",                                             │     │
│  │    aud: "https://deeptrail.io"                                                  │     │
│  │  }                                                                              │     │
│  │  Purpose: Agent identity linked to owning user                                  │     │
│  │  Lifetime: Days to weeks (agent validity)                                        │     │
│  │                                                                                 │     │
│  │  NEW FROM PAPER: metadata_uri for agent capabilities discovery                  │     │
│  │  KEY INSIGHT: Can embed W3C Verifiable Credential for richer metadata           │     │
│  └────────────────────────────────────────────────────────────────────────────────┘     │
│                              │                                                           │
│                              │ User delegates permissions (per delegation grant)         │
│                              ▼                                                           │
│  LAYER 2: DELEGATION TOKEN (from DeepTrail CP, with IdP bindings)                       │
│  ┌────────────────────────────────────────────────────────────────────────────────┐     │
│  │  Issuer: DeepTrail Control Plane                                                │     │
│  │  Obtained: User consent flow (optionally via IdP)                               │     │
│  │  Claims: {                                                                      │     │
│  │    sub: "agent-sdr-001",                                                        │     │
│  │    delegator: "sarah@company.com",                                              │     │
│  │    delegator_idp: "https://company.okta.com",                                   │     │
│  │    user_token_hash: "sha256:...",     ← CRYPTOGRAPHIC BINDING (from paper)      │     │
│  │    agent_token_hash: "sha256:...",    ← CRYPTOGRAPHIC BINDING (from paper)      │     │
│  │    delegated_permissions: [                                                     │     │
│  │      "urn:deepsecure:mcp:hubspot:contacts:read",                                │     │
│  │      "urn:deepsecure:service:openai:chat"                                       │     │
│  │    ],                                                                           │     │
│  │    constraints: { max_actions_per_day: 100, budget_usd: 500 },                  │     │
│  │    consent_ref: "okta-consent-12345", ← OPTIONAL: IdP consent tracking          │     │
│  │    logging_uri: "https://audit.deeptrail.io/log",  ← FROM PAPER                 │     │
│  │    revocation_uri: "https://deeptrail.io/revoke",  ← FROM PAPER                 │     │
│  │    exp: 1737820800                                                              │     │
│  │  }                                                                              │     │
│  │  Purpose: "User X delegated rights Y to Agent Z"                                │     │
│  │  Lifetime: Days to weeks                                                         │     │
│  │                                                                                 │     │
│  │  ALTERNATIVE (from paper): Macaroon for attenuable delegation chains            │     │
│  │  ALTERNATIVE: OAuth 2.0 UMA (User-Managed Access) for multi-agent               │     │
│  │  ALTERNATIVE: W3C Verifiable Credentials for decentralized delegation           │     │
│  └────────────────────────────────────────────────────────────────────────────────┘     │
│                              │                                                           │
│                              │ Agent authenticates (per session)                         │
│                              ▼                                                           │
│  LAYER 3: AGENT SESSION JWT (from DeepTrail CP, includes IdP context)                   │
│  ┌────────────────────────────────────────────────────────────────────────────────┐     │
│  │  Issuer: DeepTrail Control Plane                                                │     │
│  │  Obtained: Ed25519 challenge-response + IdP token validation                    │     │
│  │  Claims: {                                                                      │     │
│  │    sub: "agent-sdr-001",                                                        │     │
│  │    owner: "sarah@company.com",        ← PRESERVED from IdP for audit            │     │
│  │    idp_issuer: "https://company.okta.com",                                      │     │
│  │    party_type: "first_party",                                                   │     │
│  │    delegated_permissions: [...],      ← From delegation token                   │     │
│  │    delegation_id: "del-12345",                                                  │     │
│  │    groups: ["sales", "engineering"]   ← FROM IdP groups claim                   │     │
│  │  }                                                                              │     │
│  │  Purpose: Active agent session with standing permissions                        │     │
│  │  Lifetime: Hours to days                                                         │     │
│  │                                                                                 │     │
│  │  PAPER DOESN'T HAVE THIS - DeepSecure unique layer                              │     │
│  └────────────────────────────────────────────────────────────────────────────────┘     │
│                              │                                                           │
│                              │ Agent creates task (per task)                             │
│                              ▼                                                           │
│  LAYER 4: TASK TOKEN (DeepSecure UNIQUE - PAPER DOESN'T HAVE THIS)                      │
│  ┌────────────────────────────────────────────────────────────────────────────────┐     │
│  │  Issuer: DeepTrail Control Plane                                                │     │
│  │  Claims: {                                                                      │     │
│  │    task_id: "task-outreach-lead-12345",                                         │     │
│  │    agent_id: "agent-sdr-001",                                                   │     │
│  │    scoped_permissions: [                                                        │     │
│  │      { urn: "hubspot:contacts:read", constraints: { id: "12345" } }             │     │
│  │    ],                                                                           │     │
│  │    deadline: "2026-01-15T12:00:00Z",                                            │     │
│  │    auto_revoke_on_complete: true                                                │     │
│  │  }                                                                              │     │
│  │  Purpose: Per-task least privilege - KEY DIFFERENTIATOR                         │     │
│  │  Lifetime: Minutes to hours (task duration)                                      │     │
│  └────────────────────────────────────────────────────────────────────────────────┘     │
│                              │                                                           │
│                              │ Gateway exchanges (per MCP server)                        │
│                              ▼                                                           │
│  LAYER 5: MCP OAUTH TOKEN (from Keycloak - PAPER DOESN'T HAVE THIS)                     │
│  ┌────────────────────────────────────────────────────────────────────────────────┐     │
│  │  Issuer: Keycloak (federated with Enterprise IdP)                               │     │
│  │  Obtained: Token exchange (RFC 8693) from Task Token                            │     │
│  │  Claims: { iss, sub, aud, scope, task_id }                                      │     │
│  │  Purpose: Standards-compliant MCP server auth (per RFC 9728)                    │     │
│  │  Lifetime: 5-15 minutes                                                          │     │
│  └────────────────────────────────────────────────────────────────────────────────┘     │
│                                                                                          │
│  KEY PRINCIPLE: Monotonic Attenuation                                                   │
│  User Perms ≥ Delegation Perms ≥ Session Perms ≥ Task Perms ≥ MCP Token Scope         │
│                                                                                          │
│  KEY CHARACTERISTIC: HYBRID DEEPSECURE + IdP                                            │
│  • User identity from enterprise IdP                                                    │
│  • Agent identity can be from IdP or DeepSecure                                         │
│  • Task scoping and secrets from DeepSecure (unique value)                              │
│  • MCP OAuth from Keycloak (federated)                                                  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 7.1 Complete Claims Reference Table

This table serves as a **quick reference for developers and security reviewers**. Use it to:

- **Validate tokens**: Check that required claims are present and correctly formatted
- **Issue tokens**: Include all required claims when creating tokens
- **Debug auth failures**: Identify missing or malformed claims
- **Plan token storage**: Understand what sensitive data each token contains

**Reading the table**: Each row represents one token layer. The "Complete Claims" column lists the JWT claims that MUST be present for that token type.

| Layer | Token | Issuer | Lifetime | Complete Claims |
|-------|-------|--------|----------|-----------------|
| **0** | User ID-Token | Enterprise IdP | ~1 hour | `sub`, `email`, `groups`, `roles`, `mfa_verified` |
| **1** | Agent-ID Token | Enterprise IdP | Days-weeks | `sub`, `owner`, `party_type`, `public_key`, `metadata_uri`, `iss`, `aud` |
| **2** | Delegation Token | DeepTrail CP | Days-weeks | `sub`, `delegator`, `delegator_idp`, `user_token_hash`, `agent_token_hash`, `delegated_permissions`, `constraints`, `consent_ref`, `logging_uri`, `revocation_uri`, `exp` |
| **3** | Agent Session JWT | DeepTrail CP | Hours-days | `sub`, `owner`, `idp_issuer`, `party_type`, `delegated_permissions`, `delegation_id`, `groups` |
| **4** | Task Token | DeepTrail CP | Mins-hours | `task_id`, `agent_id`, `scoped_permissions`, `deadline`, `auto_revoke_on_complete` |
| **5** | MCP OAuth Token | Keycloak | 5-15 min | `iss`, `sub`, `aud`, `scope`, `task_id` |

---

## 8. Token Model Comparison

DeepSecure's token architecture didn't emerge in a vacuum—it builds upon academic research in authenticated delegation for AI agents. This section compares DeepSecure's model to the foundational research to:

- **Validate design decisions**: Ensure DeepSecure follows proven security patterns from research
- **Identify gaps**: Find where DeepSecure extends beyond the research (and why)
- **Enable interoperability**: Understand how DeepSecure could work with systems that implement the research model
- **Guide future development**: Know which research concepts to adopt next

**Key Question This Section Answers**: *"How does DeepSecure's token model relate to the academic 'Authenticated Delegation and Authorized AI Agents' paper, and where does DeepSecure add unique value?"*

### 8.1 Three-Token Model

The research paper "Authenticated Delegation and Authorized AI Agents" proposes a foundational three-token model for AI agent authorization. Understanding this model is important because:

- **It establishes the theoretical foundation** for authenticated delegation that DeepSecure builds upon
- **It defines key concepts** like `owner` claim, `user_token_hash`, and `metadata_uri` that DeepSecure adopts
- **It proposes alternatives** (W3C Verifiable Credentials, OAuth UMA) that DeepSecure may consider in future versions
- **It is IdP-centric**, which influences how DeepSecure integrates with enterprise identity providers

The paper proposes:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    Research THREE-TOKEN MODEL (COMPLETE)                                   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  TOKEN 1: USER ID-TOKEN (Standard OIDC)                                                 │
│  ┌────────────────────────────────────────────────────────────────────────────────┐     │
│  │  • Standard OIDC JWT from IdP                                                   │     │
│  │  • Claims: sub, name, email, iat, exp                                           │     │
│  │  • Purpose: Human user identity                                                 │     │
│  └────────────────────────────────────────────────────────────────────────────────┘     │
│                                                                                          │
│  TOKEN 2: AGENT-ID TOKEN (NEW in Paper)                                                 │
│  ┌────────────────────────────────────────────────────────────────────────────────┐     │
│  │  • JWT signed by IdP                                                            │     │
│  │  • Registration: Via OAuth2 Dynamic Client Registration (RFC 7591)              │     │
│  │  • Claims:                                                                      │     │
│  │    - sub: agent identifier                                                      │     │
│  │    - owner: user who registered the agent    ← EXPLICIT OWNERSHIP               │     │
│  │    - azp: authorized party                                                      │     │
│  │    - metadata_uri: profile describing capabilities/limitations                  │     │
│  │    - public_key: agent's public key for proof-of-possession                     │     │
│  │  • KEY INSIGHT: Can embed W3C Verifiable Credential for richer metadata         │     │
│  └────────────────────────────────────────────────────────────────────────────────┘     │
│                                                                                          │
│  TOKEN 3: DELEGATION TOKEN (NEW in Paper)                                               │
│  ┌────────────────────────────────────────────────────────────────────────────────┐     │
│  │  • Signed by: Human delegator's key OR IdP on user's behalf                     │     │
│  │  • Claims:                                                                      │     │
│  │    - sub: agent_id (the delegate)                                               │     │
│  │    - iss: user's identifier or IdP                                              │     │
│  │    - aud: intended services/APIs                                                │     │
│  │    - scope: permitted actions                                                   │     │
│  │    - usr: user_id (delegator reference)                                         │     │
│  │    - user_token_hash: sha256(user_id_token)   ← CRYPTOGRAPHIC BINDING           │     │
│  │    - agent_token_hash: sha256(agent_id_token) ← CRYPTOGRAPHIC BINDING           │     │
│  │    - logging_uri: audit endpoint                                                │     │
│  │    - revocation_uri: revocation endpoint                                        │     │
│  │  • ALTERNATIVE: OAuth 2.0 UMA (User-Managed Access) for multi-agent             │     │
│  │  • ALTERNATIVE: W3C Verifiable Credentials for decentralized delegation         │     │
│  └────────────────────────────────────────────────────────────────────────────────┘     │
│                                                                                          │
│  KEY CHARACTERISTIC: IdP-CENTRIC                                                        │
│  • Everything flows through enterprise IdP                                              │
│  • Agent registration happens AT the IdP                                                │
│  • Services verify tokens against IdP's JWKS                                            │
│  • Designed for cross-domain interoperability                                           │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Three-Token Model Proposed vs DeepSecure Token Model

This comparison table answers: *"Where does DeepSecure align with the research, and where does it go beyond?"*

Understanding this mapping is critical for:

- **Security reviews**: Auditors can verify that DeepSecure implements research-backed patterns (Layers 0-2)
- **Differentiation**: Product teams can articulate DeepSecure's unique value (Layers 3-5)
- **Roadmap planning**: Engineering can identify which research concepts aren't yet implemented
- **Interoperability**: Integration teams can map DeepSecure tokens to external systems expecting the research model

| Layer | Token | Research Proposed? | DeepSecure Has? | Notes |
|-------|-------|-----------|-----------------|-------|
| 0 | User ID-Token | ✅ Yes | ✅ Yes | Identical - standard OIDC from enterprise IdP |
| 1 | Agent-ID Token | ✅ Yes | ✅ Yes (now aligned) | Added `metadata_uri` from paper |
| 2 | Delegation Token | ✅ Yes | ✅ Yes (enhanced) | Added cryptographic binding (`user_token_hash`, `agent_token_hash`) from paper |
| 3 | Agent Session JWT | ❌ No | ✅ Yes | **DeepSecure unique** - enables session management without repeated auth |
| 4 | Task Token | ❌ No | ✅ Yes | **DeepSecure key differentiator** - enables per-task least privilege |
| 5 | MCP OAuth Token | ❌ No | ✅ Yes | **MCP-specific** - enables standards-compliant backend communication |

**DeepSecure's Unique Value (Layers 3-5)**:
- **Layer 3 (Agent Session JWT)**: Research assumes agents authenticate per-request. DeepSecure adds session management so agents authenticate once and perform multiple tasks efficiently.
- **Layer 4 (Task Token)**: Research doesn't address task-level scoping. DeepSecure's Task Tokens enable true least privilege—each task gets only the permissions it needs, not the full delegation.
- **Layer 5 (MCP OAuth Token)**: Research doesn't address MCP protocol. DeepSecure adds automatic token exchange to communicate with OAuth-protected MCP servers.

---

# Part III: Per-Task Scoped Permissions

## Why Per-Task Scoped Permissions Matter

### The Problem: Static Permissions Don't Work for AI Agents

Traditional permission systems were designed for humans and static applications:
- **Static roles** assigned at provisioning time
- **Session-based** access with human-controlled duration
- **Broad permissions** that remain active until explicitly revoked

AI agents break these assumptions because they:
1. **Execute rapidly** - hundreds of actions per second
2. **Operate autonomously** - without human oversight for each action
3. **Perform diverse tasks** - each with different permission needs
4. **Present new risks** - over-privileged agents can cause significant damage

### Why DeepSecure Needs Per-Task Permissions

| Without Per-Task Scoping | With Per-Task Scoping |
|--------------------------|------------------------|
| Agent has `openai:*` forever | Agent gets `openai:chat:gpt-4` only for current task |
| Can access any data anytime | Can only access Q3 sales data for this summary task |
| Permissions never expire | Permissions auto-revoke when task completes |
| Difficult to audit what was used for what | Full audit trail: permission → task → action |
| Over-privilege by default | Least-privilege by design |

### How This Fits the Comprehensive Architecture

Per-task permissions connect to other architectural components:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PER-TASK PERMISSIONS IN ARCHITECTURE CONTEXT                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  TOKEN HIERARCHY (Part II)          PER-TASK PERMISSIONS (Part VI)              │
│  ┌────────────────────────┐         ┌────────────────────────────────────────┐ │
│  │ Layer 5: Task Token    │◄────────│ Scoped permissions stored here         │ │
│  │ • task_id              │         │ • permission_urn                       │ │
│  │ • scoped_permissions[] │         │ • constraints (time, volume, data)     │ │
│  │ • constraints          │         │ • usage_count / max_usage              │ │
│  └────────────────────────┘         └────────────────────────────────────────┘ │
│                                                                                  │
│  MCP GATEWAY (Part I)               SESSION HIERARCHY (Part VII)                │
│  ┌────────────────────────┐         ┌────────────────────────────────────────┐ │
│  │ Action Control         │◄────────│ Agent Session                          │ │
│  │ Middleware validates   │         │ • execution_plan                       │ │
│  │ against scoped perms   │         │ • scoped_permissions                   │ │
│  └────────────────────────┘         │ • derives from User + Agent base       │ │
│                                      └────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Per-Task Permission Architecture

### 13.1 Current State vs Required State

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CURRENT vs REQUIRED COMPONENTS                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  CONTROL PLANE (deeptrail-control)                                              │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────────┐ │
│  │     CURRENT (Exists)        │    │           REQUIRED (New)                │ │
│  ├─────────────────────────────┤    ├─────────────────────────────────────────┤ │
│  │ ✓ Agent CRUD               │    │ ○ Permission Tree Service               │ │
│  │ ✓ Basic Policy CRUD        │    │ ○ Task Management Service               │ │
│  │ ✓ JWT Token Issuance       │    │ ○ Dynamic Scoping Engine                │ │
│  │ ✓ Macaroon Delegation      │    │ ○ Constraint Definition Store           │ │
│  │ ✓ Secret Split-Key Store   │    │ ○ Party Type Registry                   │ │
│  │ ✓ Attestation Policies     │    │ ○ Capability Token Service              │ │
│  └─────────────────────────────┘    │ ○ Task Permission Store                 │ │
│                                      │ ○ Usage Quota Tracker                   │ │
│                                      └─────────────────────────────────────────┘ │
│                                                                                  │
│  GATEWAY (deeptrail-gateway)                                                     │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────────┐ │
│  │     CURRENT (Exists)        │    │           REQUIRED (New)                │ │
│  ├─────────────────────────────┤    ├─────────────────────────────────────────┤ │
│  │ ✓ JWT Validation           │    │ ○ Task Context Middleware               │ │
│  │ ✓ Basic Policy Enforcement │    │ ○ Party-Aware Enforcement               │ │
│  │   (domain/method only)     │    │ ○ Constraint Evaluation Engine          │ │
│  │ ✓ Secret Injection (JIT)   │    │ ○ Action Control Middleware             │ │
│  │ ✓ Request Proxying         │    │ ○ Usage Tracking Middleware             │ │
│  │ ✓ Streaming Support        │    │ ○ Response Filtering                    │ │
│  └─────────────────────────────┘    │ ○ Real-time Policy Cache                │ │
│                                      │ ○ Scoped Permission Validator           │ │
│                                      └─────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 13.2 Task-Based Permission Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           TASK-BASED PERMISSION FLOW                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  1. TASK CREATION                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ Agent → Control Plane: "I need to summarize Q3 sales"                   │    │
│  │                                                                         │    │
│  │ Task Request:                                                           │    │
│  │ {                                                                       │    │
│  │   "name": "Summarize Q3 Sales",                                         │    │
│  │   "required_permissions": [                                             │    │
│  │     {"urn": "urn:deepsecure:service:openai:chat",                       │    │
│  │      "constraints": {"model": "gpt-4", "max_tokens": 4000}},            │    │
│  │     {"urn": "urn:deepsecure:data:sales:read",                           │    │
│  │      "constraints": {"date_range": "Q3_2025"}}                          │    │
│  │   ],                                                                    │    │
│  │   "deadline": "2025-01-15T12:00:00Z"                                    │    │
│  │ }                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  2. PERMISSION SCOPING                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ Control Plane → Dynamic Scoping Engine:                                 │    │
│  │                                                                         │    │
│  │ 1. Get agent's base permissions from policy                             │    │
│  │ 2. Intersect with requested permissions                                 │    │
│  │ 3. Apply more restrictive constraints                                   │    │
│  │ 4. Check party-type restrictions                                        │    │
│  │ 5. Create time-bounded scoped permissions                               │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  3. TASK TOKEN ISSUANCE                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ Control Plane → Agent: Task Token JWT                                   │    │
│  │                                                                         │    │
│  │ {                                                                       │    │
│  │   "task_id": "task-q3-summary-12345",                                   │    │
│  │   "agent_id": "agent-analytics-001",                                    │    │
│  │   "scoped_permission_ids": ["sp-001", "sp-002"],                        │    │
│  │   "exp": "2025-01-15T12:00:00Z"                                         │    │
│  │ }                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  4. GATEWAY ENFORCEMENT                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ Agent Request → Gateway:                                                │    │
│  │                                                                         │    │
│  │ Headers: X-Task-Token: eyJ...                                           │    │
│  │                                                                         │    │
│  │ Gateway validates:                                                      │    │
│  │ ✓ Task token not expired                                                │    │
│  │ ✓ Request matches scoped permission                                     │    │
│  │ ✓ Constraints satisfied (model, tokens, date range)                     │    │
│  │ ✓ Usage limits not exceeded                                             │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  5. AUTOMATIC REVOCATION                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ Task Complete → Control Plane:                                          │    │
│  │                                                                         │    │
│  │ ✓ All scoped permissions revoked                                        │    │
│  │ ✓ Audit report generated                                                │    │
│  │ ✓ Usage metrics recorded                                                │    │
│  │ ✓ Initiator notified                                                    │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Control Plane Components for Per-Task Permissions

### Why These Components Are Critical

The Control Plane components form the **policy decision point** for per-task permissions. Without them, the gateway can only enforce static domain/method rules, not dynamic task-scoped constraints.

### 14.1 Permission Tree Service

**Why DeepSecure Needs This**: Permissions need hierarchy to support inheritance (parent grants child) and specificity (specific overrides general). Without a tree structure, every permission must be explicitly granted.

```python
# Key Responsibilities:
# - CRUD for permission nodes with inheritance
# - Resolve effective permissions applying inheritance rules
# - Validate permission URNs exist in tree
# - Get applicable constraints for a permission

class PermissionTreeService:
    async def resolve_effective_permissions(
        self, 
        agent_id: str,
        requested_permissions: List[str]
    ) -> List[ResolvedPermission]:
        """
        Inheritance Rules:
        1. Grant propagation (parent grants child)
        2. Deny propagation (parent deny blocks child)
        3. Deny takes precedence over grant
        4. Specific overrides general
        """
```

**Database Schema**:
```sql
CREATE TABLE permission_nodes (
    id UUID PRIMARY KEY,
    parent_id UUID REFERENCES permission_nodes(id),
    urn VARCHAR(512) UNIQUE NOT NULL,
    risk_level VARCHAR(20) DEFAULT 'medium',
    requires_approval BOOLEAN DEFAULT FALSE,
    applicable_constraints JSONB DEFAULT '[]'
);
```

### 14.2 Task Management Service

**Why DeepSecure Needs This**: Tasks are the atomic unit of agent work. Without task tracking, permissions cannot be scoped to specific work units and automatically revoked.

```python
# Key Responsibilities:
# - Create tasks with permission requirements
# - Evaluate permissions against agent's base policy
# - Issue time-bounded scoped permissions
# - Revoke all permissions on task completion/timeout

class TaskService:
    async def create_task(
        self,
        agent_id: str,
        task: TaskCreate,
        initiated_by: str
    ) -> Task:
        """
        Steps:
        1. Validate agent exists and is active
        2. Validate all requested permissions exist in tree
        3. Evaluate permissions against agent's base policy
        4. Apply task-specific constraints
        5. Calculate minimal permission set
        6. Store task with scoped permissions
        """
    
    async def complete_task(self, task_id: str) -> Task:
        """
        Steps:
        1. Revoke all scoped permissions
        2. Generate audit report
        3. Update task status to 'completed'
        """
```

**Database Schema**:
```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY,
    agent_id VARCHAR(256) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    deadline TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE scoped_permissions (
    id UUID PRIMARY KEY,
    task_id UUID REFERENCES tasks(id),
    permission_urn VARCHAR(512) NOT NULL,
    constraints JSONB DEFAULT '{}',
    valid_until TIMESTAMP NOT NULL,
    usage_count INTEGER DEFAULT 0,
    max_usage INTEGER,
    revoked BOOLEAN DEFAULT FALSE
);
```

### 14.3 Dynamic Scoping Engine

**Why DeepSecure Needs This**: The core principle of least privilege requires computing the **minimum** permission set for each task. This is a constraint satisfaction problem that needs a dedicated engine.

```python
# Key Responsibilities:
# - Evaluate requested permissions against base policy
# - Apply the more restrictive of base and requested constraints
# - Calculate minimal permission set using ILP/greedy algorithm
# - Apply party-type-specific restrictions

class DynamicScopingEngine:
    async def apply_constraints(
        self,
        base_constraints: Dict,
        requested_constraints: Dict
    ) -> Dict:
        """
        Constraint Rules:
        - Numeric limits: take minimum
        - Time bounds: take intersection
        - Allowed values: take intersection
        - Denied values: take union
        """
```

### 14.4 Party Type Registry

**Why DeepSecure Needs This**: Different agent types (1st party, 2nd party vendor, 3rd party) have fundamentally different trust levels and permission models.

| Party Type | Trust Level | Delegation | Secret Access | Audit Level |
|------------|-------------|------------|---------------|-------------|
| 1st Party | High | Allowed (depth 3) | Direct (JIT) | Standard |
| 2nd Party Vendor-Managed | Medium | Disabled | Token Exchange | Enhanced |
| 2nd Party Vendor-Integrated | Medium | Limited (depth 2) | Direct (sandboxed) | Full |
| 3rd Party | Untrusted | Disabled | Never | Full |

---

## 11. Gateway Components for Action Control

### Why These Components Are Critical

The Gateway components form the **policy enforcement point**. Without them, even perfectly scoped permissions would not be enforced at runtime.

### 15.1 Task Context Middleware

**Why DeepSecure Needs This**: Every request must be associated with a task to apply scoped permissions. This middleware extracts and validates task context.

```python
class TaskContextMiddleware:
    """
    For each request:
    1. Extract X-Task-Token header
    2. Validate task token (signature, expiration)
    3. Load scoped permissions from cache/control plane
    4. Attach task context to request state
    """
    
    async def _load_task_context(self, task_token: str) -> TaskContext:
        # Check cache first (30 second TTL)
        # Fetch from control plane if not cached
        # Return TaskContext with scoped_permissions
```

### 15.2 Scoped Permission Validator

**Why DeepSecure Needs This**: Validates that each request matches one of the task's scoped permissions and satisfies all constraints.

```python
class ScopedPermissionValidator:
    """
    For each request:
    1. Extract target resource (domain, path, method)
    2. Find matching scoped permission
    3. Validate constraints are satisfied
    4. Track usage
    """
    
    async def _validate_request(
        self,
        task_context: TaskContext,
        target_url: str,
        method: str,
        path: str
    ) -> ValidationResult:
        # Find permission that matches request
        # Validate all constraints pass
        # Return allowed/denied with reason
```

### 15.3 Constraint Evaluation Engine

**Why DeepSecure Needs This**: Constraints are the mechanism for fine-grained control. Different constraint types need different evaluation logic.

| Constraint Type | What It Controls | Example |
|-----------------|------------------|---------|
| **Temporal** | When permission is valid | `valid_from`, `valid_until`, `business_hours` |
| **Volume** | How much can be used | `rate_limit`, `max_tokens`, `row_limit` |
| **Data** | What data can be accessed | `allowed_columns`, `row_filter`, `pii_masking` |
| **Contextual** | Where/how it can be used | `ip_restriction`, `purpose_binding` |

```python
class ConstraintEngine:
    evaluators = {
        "temporal": TemporalConstraintEvaluator(),
        "volume": VolumeConstraintEvaluator(redis_client),
        "data": DataConstraintEvaluator(),
    }
    
    async def evaluate_all_constraints(
        self,
        constraints: Dict,
        request_context: Dict
    ) -> Tuple[bool, List[str]]:
        # All constraints must pass
        # Returns (passed, failure_reasons)
```

### 15.4 Action Control Middleware

**Why DeepSecure Needs This**: Beyond domain/method, DeepSecure needs to control specific actions like which LLM model, which MCP tool, which database operation.

```python
class ActionControlMiddleware:
    """
    Fine-grained action control for:
    - LLM APIs: model selection, token limits, content filtering
    - MCP protocol: tool/resource permissions
    - Database: query type restrictions
    """
    
    ACTION_EXTRACTORS = {
        "api.openai.com": OpenAIActionExtractor(),
        "api.anthropic.com": AnthropicActionExtractor(),
        "mcp": MCPActionExtractor(),
    }
```

### 15.5 Usage Tracking Middleware

**Why DeepSecure Needs This**: Quota enforcement and billing require accurate usage tracking at the task level.

```python
class UsageTrackingMiddleware:
    """
    Tracks:
    - Request count per task/permission
    - Token usage for LLM calls
    - Data volume for data access
    - Cost estimation
    """
```

---

# Part IV: Session Hierarchy Architecture

## Why Session Hierarchy Matters

### The Problem: Stateless Tokens Are Insufficient

The current architecture uses stateless JWTs for authentication. While efficient, this approach has limitations for AI agent workloads:

1. **No Execution Context**: JWTs don't track what the agent is currently doing
2. **No Permission History**: Can't know what permissions have been used/granted previously
3. **No Credential Binding**: User's OAuth credentials aren't linked to agent's session
4. **No MCP Connection State**: Each MCP request is independent

### The MiniScope Insight

The MiniScope paper provides the key insight:

> "MiniScope serves as the 'firewall' between the agent and the services. It keeps track of **all previously granted permissions** and the **user's credentials for connecting to services**."

This requires **session state** - persistent tracking of:
- What permissions have been granted (ALLOWED/ONCE/DENIED)
- What credentials are available
- What the current execution context is

### Why DeepSecure Needs Session Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       SESSION HIERARCHY NECESSITY                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  WITHOUT SESSION HIERARCHY:                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ Agent ──► JWT ──► Gateway ──► MCP Server                                │    │
│  │                                                                         │    │
│  │ Problems:                                                               │    │
│  │ ✗ Every request re-validates from scratch                               │    │
│  │ ✗ Can't implement "ONCE" permission grants                              │    │
│  │ ✗ Can't track MCP connection state                                      │    │
│  │ ✗ Can't bind user credentials to agent work                             │    │
│  │ ✗ Can't implement execution plan validation                             │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  WITH SESSION HIERARCHY:                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ User Session                                                            │    │
│  │ ├── Permission grants (ALLOWED/ONCE)                                    │    │
│  │ ├── Connected services (OAuth tokens)                                   │    │
│  │ │                                                                       │    │
│  │ └── Agent Session (spawned within user context)                         │    │
│  │     ├── Execution plan                                                  │    │
│  │     ├── Scoped permissions (user ∩ agent policy ∩ task needs)           │    │
│  │     │                                                                   │    │
│  │     └── MCP Session (per backend server)                                │    │
│  │         ├── Allowed tools (derived from scoped permissions)             │    │
│  │         ├── Allowed resources                                           │    │
│  │         └── Injected credentials (from user's connected services)       │    │
│  │                                                                         │    │
│  │ Benefits:                                                               │    │
│  │ ✓ Fast permission lookups (cached session state)                        │    │
│  │ ✓ ONCE permissions automatically consumed                               │    │
│  │ ✓ MCP connections are stateful                                          │    │
│  │ ✓ Full audit trail: user → agent → MCP → action                         │    │
│  │ ✓ Execution plans can be validated before execution                     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Session Hierarchy Overview

### 16.1 Three-Layer Session Model

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SESSION HIERARCHY                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                          USER SESSION                                       │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │ │
│  │  │ • session_id: "usess-abc123"                                        │  │ │
│  │  │ • user_id: "user-alice-123"                                         │  │ │
│  │  │ • permission_grants: {scope: ALLOWED|ONCE|DENIED, granted_at: ...}  │  │ │
│  │  │ • connected_services: [{service: "google", oauth_token_ref: ...}]   │  │ │
│  │  │ • preferences: {auto_approve_low_risk: true}                        │  │ │
│  │  └─────────────────────────────────────────────────────────────────────┘  │ │
│  │                                     │                                       │ │
│  │                                     │ spawns                                │ │
│  │                                     ▼                                       │ │
│  │  ┌────────────────────────────────────────────────────────────────────────┐│ │
│  │  │                       AGENT SESSION                                    ││ │
│  │  │  ┌──────────────────────────────────────────────────────────────────┐ ││ │
│  │  │  │ • agent_session_id: "asess-def456"                               │ ││ │
│  │  │  │ • parent_user_session: "usess-abc123"                            │ ││ │
│  │  │  │ • agent_id: "agent-assistant-001"                                │ ││ │
│  │  │  │ • party_type: "first_party"                                      │ ││ │
│  │  │  │ • execution_plan: [{tool: "gmail.list", params: {...}}, ...]     │ ││ │
│  │  │  │ • scoped_permissions: [user grants ∩ agent policy ∩ task needs]  │ ││ │
│  │  │  │ • expires_at: "2025-01-15T10:35:00Z"                             │ ││ │
│  │  │  └──────────────────────────────────────────────────────────────────┘ ││ │
│  │  │                                    │                                   ││ │
│  │  │                                    │ creates                           ││ │
│  │  │                                    ▼                                   ││ │
│  │  │  ┌──────────────────────────────────────────────────────────────────┐ ││ │
│  │  │  │                      MCP SESSION                                 │ ││ │
│  │  │  │  ┌────────────────────────────────────────────────────────────┐ │ ││ │
│  │  │  │  │ • mcp_session_id: "mcpsess-ghi789"                         │ │ ││ │
│  │  │  │  │ • parent_agent_session: "asess-def456"                     │ │ ││ │
│  │  │  │  │ • server_id: "mcp-gmail-server"                            │ │ ││ │
│  │  │  │  │ • connection_state: "connected"                            │ │ ││ │
│  │  │  │  │ • allowed_tools: ["gmail.list", "gmail.read"]              │ │ ││ │
│  │  │  │  │ • allowed_resources: ["mailbox://inbox/*"]                 │ │ ││ │
│  │  │  │  │ • injected_credentials: {type: "oauth", ref: "cred-xyz"}   │ │ ││ │
│  │  │  │  │ • tool_call_count: 5                                       │ │ ││ │
│  │  │  │  └────────────────────────────────────────────────────────────┘ │ ││ │
│  │  │  └──────────────────────────────────────────────────────────────────┘ ││ │
│  │  └────────────────────────────────────────────────────────────────────────┘│ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 16.2 Session State Relationships

| Attribute | User Session | Agent Session | MCP Session |
|-----------|--------------|---------------|-------------|
| **Lifetime** | Hours-Days | Minutes-Hours | Request-based |
| **Created By** | User login | Agent task start | First MCP call to server |
| **Stores Permissions** | User's grants (ALLOWED/ONCE) | Scoped permissions (intersection) | Allowed tools/resources |
| **Stores Credentials** | OAuth token refs | Credential ref (inherited) | Injected credentials |
| **Parent** | None | User Session | Agent Session |

---

## 13. User Session Service

### Why DeepSecure Needs User Sessions

User sessions implement the **MiniScope paradigm**:
- User is ground-truth authority for permissions
- Mobile-style ALLOWED/ONCE/DENIED permission model
- Tracks all granted permissions and credentials across agent sessions

### 17.1 Permission Grant Types

```python
class PermissionGrantType(str, Enum):
    """Mobile-style permission grant types (from MiniScope paper)"""
    ALLOWED = "allowed"      # Permanent grant until revoked
    ONCE = "once"            # One-time grant for current task
    DENIED = "denied"        # Explicitly denied
    PENDING = "pending"      # Awaiting user decision
```

### 17.2 User Session Data Model

```python
@dataclass
class UserSession:
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    
    # Permission grants (MiniScope's permission tracking)
    permission_grants: Dict[str, PermissionGrant]
    
    # Connected services (MiniScope's credential tracking)
    connected_services: Dict[str, ConnectedService]
    
    # Active agent sessions spawned from this user session
    active_agent_sessions: List[str]
```

### 17.3 Permission Request Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       PERMISSION REQUEST FLOW (MiniScope-style)                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Agent: "I need calendar.read to check your schedule"                           │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ User Session Service:                                                   │    │
│  │                                                                         │    │
│  │ 1. Check if permission already exists:                                  │    │
│  │    ├── ALLOWED → Return immediately ✓                                   │    │
│  │    ├── DENIED → Reject immediately ✗                                    │    │
│  │    └── ONCE (still valid) → Return ✓                                    │    │
│  │                                                                         │    │
│  │ 2. If not exists, prompt user:                                          │    │
│  │    ┌─────────────────────────────────────────────────────────────┐      │    │
│  │    │ "Agent wants access to: calendar.read"                      │      │    │
│  │    │                                                             │      │    │
│  │    │  [ALLOW]     [ALLOW ONCE]     [DENY]                        │      │    │
│  │    └─────────────────────────────────────────────────────────────┘      │    │
│  │                                                                         │    │
│  │ 3. Record user decision in session                                      │    │
│  │                                                                         │    │
│  │ 4. Return grant to requesting agent                                     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 17.4 Database Schema

```sql
CREATE TABLE user_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(256) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT NOW(),
    preferences JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE permission_grants (
    id UUID PRIMARY KEY,
    session_id VARCHAR(64) REFERENCES user_sessions(session_id),
    user_id VARCHAR(256) NOT NULL,
    scope VARCHAR(512) NOT NULL,
    grant_type VARCHAR(20) NOT NULL,  -- allowed, once, denied, pending
    granted_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    max_usage INTEGER,
    is_standing BOOLEAN DEFAULT FALSE,  -- ALLOWED grants persist across sessions
    UNIQUE(session_id, scope)
);

CREATE TABLE connected_services (
    id UUID PRIMARY KEY,
    user_id VARCHAR(256) NOT NULL,
    service_id VARCHAR(256) NOT NULL,
    oauth_token_ref VARCHAR(256) NOT NULL,  -- Reference to vault
    scopes_granted JSONB DEFAULT '[]',
    connected_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, service_id)
);
```

---

## 14. Agent Session Service

### Why DeepSecure Needs Agent Sessions

Agent sessions are the **execution context** for agent work. They:
- Link agent actions to user authorization
- Store execution plans for validation
- Compute scoped permissions (user ∩ agent policy ∩ task needs)
- Manage MCP sessions for backend connections

### 18.1 Execution Plan Model

From MiniScope: *"For each user request, MiniScope takes the execution plan submitted by the untrusted agent and determines the minimal set of permissions required."*

```python
@dataclass
class ExecutionPlan:
    plan_id: str
    agent_id: str
    user_request: str              # Natural language request
    tool_calls: List[Dict]         # Planned tool calls
    required_permissions: List[str] # Computed minimal permissions
    estimated_duration: Optional[timedelta]
```

### 18.2 Agent Session Data Model

```python
@dataclass
class AgentSession:
    agent_session_id: str
    parent_user_session_id: str
    agent_id: str
    party_type: str
    
    # Task context
    task_id: Optional[str]
    execution_plan: Optional[ExecutionPlan]
    
    # Scoped permissions (user grants ∩ agent policy ∩ task needs)
    scoped_permissions: List[str]
    
    # Active MCP sessions
    mcp_sessions: Dict[str, str]  # server_id -> mcp_session_id
    
    # Lifecycle
    created_at: datetime
    expires_at: Optional[datetime]
    status: str  # active, completed, expired, cancelled
```

### 18.3 Permission Computation (ILP-based)

The MiniScope paper uses Integer Linear Programming to find the **minimal** permission set. DeepSecure implements a greedy approximation:

```python
async def _compute_session_permissions(
    self,
    user_session: UserSession,
    agent: Agent,
    execution_plan: ExecutionPlan
) -> List[str]:
    """
    Steps:
    1. Extract required scopes from tools in plan
    2. Get user's available permissions (ALLOWED/ONCE grants)
    3. Get agent's base policy permissions
    4. Find intersection of all three sets
    5. Request missing permissions from user
    6. Apply party-type restrictions
    7. Use greedy algorithm to find minimal covering set
    """
    
    required_scopes = extract_from_plan(execution_plan)
    user_available = user_session.permission_grants
    agent_policy = agent.base_permissions
    
    # Intersection
    available = required_scopes & user_available & agent_policy
    
    # Request missing from user
    for missing in required_scopes - available:
        grant = await user_session_service.request_permission(
            scope=missing,
            justification=f"Required for: {execution_plan.user_request}"
        )
        if grant.grant_type in [ALLOWED, ONCE]:
            available.add(missing)
    
    # Minimize using greedy set cover
    return minimize_permission_set(available, required_scopes)
```

---

## 15. MCP Session Service

### Why DeepSecure Needs MCP Sessions

MCP sessions track the **connection state** to individual MCP servers:
- Which tools are allowed (derived from agent session permissions)
- Which resources can be accessed
- Credential injection for server authentication
- Usage tracking per server

### 19.1 MCP Session Data Model

```python
@dataclass
class MCPSession:
    mcp_session_id: str
    parent_agent_session_id: str
    server_id: str
    server_config: MCPServerConfig
    
    # Connection state
    connection_state: str  # disconnected, connecting, connected, error
    
    # Allowed operations (derived from agent session permissions)
    allowed_tools: List[str]
    allowed_resources: List[str]
    
    # Credential injection
    injected_credential_ref: Optional[str]
    
    # Usage tracking
    tool_call_count: int
    resource_read_count: int
```

### 19.2 MCP Session Creation Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       MCP SESSION CREATION FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Agent Session: "I need to connect to Gmail MCP server"                         │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ MCP Session Service:                                                    │    │
│  │                                                                         │    │
│  │ 1. Get server configuration from MCP registry                           │    │
│  │    └── server_id: "mcp-gmail-server"                                    │    │
│  │    └── available_tools: ["gmail.list", "gmail.read", "gmail.send"]      │    │
│  │    └── scope_mapping: {gmail.readonly: [list, read], gmail.send: [send]}│    │
│  │                                                                         │    │
│  │ 2. Derive allowed tools from agent session's scoped permissions         │    │
│  │    └── agent has: ["gmail.readonly"]                                    │    │
│  │    └── allowed_tools: ["gmail.list", "gmail.read"]                      │    │
│  │                                                                         │    │
│  │ 3. Get credentials from user's connected services                       │    │
│  │    └── user_session.connected_services["google"].oauth_token_ref        │    │
│  │                                                                         │    │
│  │ 4. Create MCP session with scoped access                                │    │
│  │    └── Only allowed tools can be called                                 │    │
│  │    └── Credentials injected for server authentication                   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 19.3 Tool Call Validation

From MiniScope: *"For each tool call issued by the agent, MiniScope enforces a mechanical check to prevent unauthorized invocations."*

```python
async def validate_tool_call(
    self,
    mcp_session_id: str,
    tool_name: str,
    arguments: Dict
) -> Dict:
    """
    Validates tool call against MCP session permissions.
    """
    session = await self.get_session(mcp_session_id)
    
    # Check tool is in allowed list
    if tool_name not in session.allowed_tools:
        return {
            "allowed": False,
            "reason": f"Tool '{tool_name}' not in allowed tools",
            "allowed_tools": session.allowed_tools
        }
    
    # Validate arguments (e.g., resource URI patterns)
    if not await self._validate_arguments(session, tool_name, arguments):
        return {"allowed": False, "reason": "Argument validation failed"}
    
    # Increment usage counter
    session.tool_call_count += 1
    
    return {"allowed": True}
```

### 19.4 Gateway Session Context Middleware

The gateway uses a unified session context that combines all three layers:

```python
@dataclass
class SessionContext:
    """Combined session context for request processing"""
    user_session_id: Optional[str]
    agent_session_id: str
    mcp_session_id: Optional[str]
    
    # Flattened permissions
    scoped_permissions: List[str]
    allowed_tools: List[str]
    allowed_resources: List[str]
    
    # Credential reference
    credential_ref: Optional[str]
    
    # Session metadata
    party_type: str
    expires_at: datetime

class SessionContextMiddleware:
    """
    Extracts session context from:
    - Authorization: Bearer <session_token>
    - X-User-Session / X-Agent-Session / X-MCP-Session headers
    
    Validates and caches session state for fast request processing.
    """
```

---

# Part V: Non-MCP Agent Support

## 16. Agents Without MCP Client: Issues and Solutions

The architecture heavily assumes that AI agents implement an MCP Client, enabling the DeepTrail Gateway to act as a Virtual MCP Server. This section analyzes what happens when an AI agent **does not** implement an MCP client.

### 16.1 The Core Assumption That Breaks

The architecture assumes:

```
AI Agent (with MCP Client) ──MCP Protocol──► DeepTrail Gateway (Virtual MCP Server)
                            JSON-RPC 2.0
                            HTTP/SSE
```

Without an MCP client, the agent **cannot**:
- Perform `initialize` handshake
- Call `tools/list` to discover capabilities
- Execute `tools/call` with proper JSON-RPC formatting
- Maintain MCP session state (`initializing → ready`)

---

### 16.2 Issues and Challenges

#### 16.2.1 Protocol Incompatibility

| Issue | Impact |
|-------|--------|
| **No MCP handshake** | Gateway expects `initialize` request with `clientInfo`; agent can't provide it |
| **No JSON-RPC 2.0** | Agent may use REST/HTTP but Gateway expects `{"jsonrpc": "2.0", "method": "tools/call", ...}` |
| **No SSE support** | Agent can't receive streaming responses or notifications |
| **No capability negotiation** | Agent can't declare its capabilities; Gateway can't filter based on agent profile |

#### 16.2.2 Tool Discovery Breaks

The architecture relies on:
```
tools/list → Gateway returns filtered, namespaced tools (hubspot.get_contact, notion.search)
```

**Without MCP client:**
- Agent has no standard way to discover available tools
- Namespace prefixing (`hubspot.get_contact`) has no consumer
- Capability filtering (what tools agent CAN see) cannot be communicated

#### 16.2.3 Governance Layer Loses Context

| Governance Feature | Why It Breaks |
|-------------------|---------------|
| **Capability Filtering** | `tools/list` response filtering has no recipient |
| **Parameter Validation** | No `tools/call` with structured `arguments` object |
| **Result Filtering** | No standard response envelope to filter |
| **Rate Limiting** | Can't track tool call counts per MCP session |
| **Session State** | No `initialize` → no session → no state to track |

#### 16.2.4 Token Flow Complications

Current flow assumes:
```
Agent JWT + Task Token ──► Gateway validates ──► MCP Protocol Handler ──► Backend
```

**Without MCP client:**
- How does agent present Agent JWT and Task Token?
- Where in the HTTP request do credentials go if not in MCP context?
- Task-to-MCP-session binding is undefined

#### 16.2.5 Backend Communication Still Works, But...

The OAuth Authorization Layer (RFC 8693 token exchange, Keycloak integration) can still work because it's protocol-agnostic. But:
- Gateway can't route without `tools/call` method name
- Gateway can't apply tool-specific governance rules
- Gateway doesn't know which backend to forward to

---

### 16.3 Architecture Breakdown Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    ARCHITECTURE BREAKDOWN: NON-MCP AGENT                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    AI AGENT (NO MCP CLIENT)                              │    │
│  │                                                                          │    │
│  │  ❌ Cannot speak MCP Protocol (JSON-RPC 2.0)                             │    │
│  │  ❌ Cannot perform initialize handshake                                   │    │
│  │  ❌ Cannot call tools/list for discovery                                 │    │
│  │  ❌ Cannot format tools/call correctly                                   │    │
│  │                                                                          │    │
│  │  ✅ CAN make HTTP requests                                               │    │
│  │  ✅ CAN present JWT/tokens in headers                                    │    │
│  │  ✅ CAN call REST APIs directly                                          │    │
│  └──────────────────────────────────┬───────────────────────────────────────┘    │
│                                     │                                             │
│                          ??? How to connect ???                                  │
│                                     │                                             │
│                                     ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │              DEEPTRAIL GATEWAY: VIRTUAL MCP SERVER LAYER                 │    │
│  │                                                                          │    │
│  │  ❌ MCP PROTOCOL LAYER - UNUSABLE                                       │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ • initialize handshake - NO REQUEST ARRIVES                         │  │    │
│  │  │ • tools/list - NO REQUEST ARRIVES                                   │  │    │
│  │  │ • tools/call routing - NO STANDARD FORMAT                           │  │    │
│  │  └────────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                          │    │
│  │  ⚠️ MCP GOVERNANCE LAYER - PARTIALLY BROKEN                             │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ • Capability Filtering - NO tools/list to filter                   │  │    │
│  │  │ • Namespace Prefixing - No consumer                                 │  │    │
│  │  │ • Parameter Validation - COULD work with different format          │  │    │
│  │  │ • Result Filtering - COULD work with different format              │  │    │
│  │  └────────────────────────────────────────────────────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │              OAUTH CLIENT/EXCHANGER LAYER                                │    │
│  │                                                                          │    │
│  │  ✅ Token Exchange (RFC 8693) - STILL WORKS                             │    │
│  │  ✅ Keycloak Integration - STILL WORKS                                  │    │
│  │  ✅ Audience Binding - STILL WORKS                                      │    │
│  │  ❌ But... no way to trigger it without MCP context                     │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### 16.4 Potential Solutions

#### 16.4.1 Solution 1: REST-to-MCP Translation Layer

Add a **REST API facade** in front of the Gateway that translates REST calls to MCP protocol internally:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      REST-TO-MCP TRANSLATION LAYER                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Non-MCP Agent                                                              │
│       │                                                                      │
│       │ REST: POST /api/v1/tools/hubspot.get_contact                        │
│       │       Authorization: Bearer {agent_jwt}                             │
│       │       X-Task-Token: {task_token}                                    │
│       │       Content-Type: application/json                                │
│       │       {"id": "12345"}                                               │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  REST FACADE                                                         │    │
│  │  • Exposes: GET  /api/v1/tools                                       │    │
│  │  • Exposes: POST /api/v1/tools/{tool_name}                           │    │
│  │  • Translates REST → MCP JSON-RPC                                    │    │
│  │  • Manages implicit MCP session per agent JWT                        │    │
│  └──────────────────────────────────┬──────────────────────────────────┘    │
│                                     │                                        │
│                                     │ Internal MCP Protocol                 │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  DEEPTRAIL GATEWAY (MCP Virtual Server)                              │    │
│  │  • All MCP governance still applies                                  │    │
│  │  • Token exchange still works                                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Pros:**
- Full governance preserved
- No changes to core Gateway
- Familiar REST interface for non-MCP agents

**Cons:**
- Additional translation layer (latency)
- Session management complexity
- Lose native MCP streaming benefits

---

#### 16.4.2 Solution 2: HTTP Proxy Mode (Bypass MCP Layer)

Route non-MCP agents directly to the **OAuth Authorization Layer**, bypassing MCP protocol handling:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DUAL-MODE GATEWAY                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MCP Agents ──────────► MCP Protocol Layer ──────► OAuth Layer ──► Backends │
│       │                        │                                             │
│       │                        │ Full MCP governance                        │
│       │                        ▼                                             │
│  ┌────┴────────────────────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │                    ┌─────────────────────────┐                       │    │
│  │                    │   MCP GOVERNANCE        │                       │    │
│  │                    │   (Full capabilities)   │                       │    │
│  │                    └─────────────────────────┘                       │    │
│  │                                                                      │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Non-MCP Agents ──────────────────────────────► OAuth Layer ──► Backends    │
│       │                                              │                       │
│       │ Direct REST/HTTP                             │                       │
│       │                                              ▼                       │
│  ┌────┴────────────────────────────────────────────────────────────────┐    │
│  │                    ┌─────────────────────────┐                       │    │
│  │                    │   BASIC GOVERNANCE      │                       │    │
│  │                    │   (Limited)             │                       │    │
│  │                    │   • Auth validation     │                       │    │
│  │                    │   • Rate limiting       │                       │    │
│  │                    │   • Basic audit         │                       │    │
│  │                    │   ❌ No tool filtering  │                       │    │
│  │                    │   ❌ No result masking  │                       │    │
│  │                    └─────────────────────────┘                       │    │
│  │                                                                      │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Pros:**
- Simple to implement
- Keeps MCP path clean
- Non-MCP agents can work immediately

**Cons:**
- **Reduced governance** for non-MCP agents
- Two code paths to maintain
- Feature parity issues

---

#### 16.4.3 Solution 3: Embedded MCP Client in DeepSecure SDK

Provide a **DeepSecure SDK** that embeds an MCP client, so any agent using the SDK automatically speaks MCP:

```python
# Agent code - SDK handles MCP protocol internally
from deepsecure import SecureAgent

agent = SecureAgent(
    agent_id="agent-sdr-001",
    gateway_url="https://gateway.deeptrail.io"
)

# SDK internally: initialize → tools/list → tools/call
result = agent.call_tool("hubspot.get_contact", {"id": "12345"})
```

**Pros:**
- **Full governance** for all SDK users
- Clean developer experience
- Single integration path

**Cons:**
- Requires SDK adoption
- Language-specific SDKs needed (Python, JS, Go, etc.)
- Doesn't help third-party agents

---

#### 16.4.4 Solution 4: Hybrid Gateway with Content-Type Detection

Gateway auto-detects protocol based on request format:

| Request Format | Detection | Processing Path |
|---------------|-----------|-----------------|
| `Content-Type: application/json` with `{"jsonrpc": "2.0", ...}` | MCP Protocol | Full MCP governance |
| `Content-Type: application/json` with REST-style body | REST/HTTP | REST translation → MCP |
| `Accept: text/event-stream` | SSE | MCP with streaming |

**Pros:**
- Single endpoint
- Automatic handling
- Supports both agent types

**Cons:**
- Complex detection logic
- Edge cases in format detection
- REST agents still need tool routing info

---

### 16.5 Solution Comparison Matrix

| Solution | Governance Preserved | Implementation Effort | Agent Adoption Friction |
|----------|---------------------|----------------------|------------------------|
| **1. REST-to-MCP Translation** | ✅ Full | Medium (4-6 weeks) | Low |
| **2. HTTP Proxy Mode** | ⚠️ Limited | Low (2-3 weeks) | Low |
| **3. Embedded SDK** | ✅ Full | High (8-12 weeks per language) | Medium |
| **4. Hybrid Detection** | ✅ Full | Medium (4-6 weeks) | Low |

### 16.6 Recommended Approach: Phased Rollout

**Recommended**: **Solution 1 (REST-to-MCP Translation)** combined with **Solution 3 (SDK)** for a phased rollout:

1. **Phase 1**: Add REST facade for immediate non-MCP agent support
2. **Phase 2**: Release SDKs that embed MCP client
3. **Phase 3**: Encourage migration to SDK for full governance benefits

### 16.7 REST Facade API Specification

For Phase 1, the REST facade should expose:

| Endpoint | Method | Description | MCP Equivalent |
|----------|--------|-------------|----------------|
| `/api/v1/tools` | GET | List available tools | `tools/list` |
| `/api/v1/tools/{tool_name}` | POST | Execute a tool | `tools/call` |
| `/api/v1/resources` | GET | List available resources | `resources/list` |
| `/api/v1/resources/{uri}` | GET | Read a resource | `resources/read` |
| `/api/v1/prompts` | GET | List available prompts | `prompts/list` |
| `/api/v1/prompts/{name}` | POST | Get a prompt | `prompts/get` |

---

# Part VI: Configuration & Components

This section provides **implementation-level detail** for engineers and architects planning the DeepTrail Gateway build. While previous Parts described *what* the architecture does and *why*, Part VI answers:

- **What components need to be built?** - Concrete classes, services, and middleware
- **Which components come from which approach?** - Understanding the heritage of each component helps prioritize and sequence development
- **What's missing?** - Gap analysis identifying components that exist in design but aren't yet in the comprehensive architecture
- **What's the implementation roadmap?** - Priority-ranked list of missing pieces

---

## 17. Component Comparison: Approach 1 (OAuth HTTP Proxy) vs Approach 2 (MCP Governance & Protocol)

This comparison helps implementation teams understand:
- **What to build first**: Components present in both approaches are likely core requirements
- **What's unique to each approach**: Components only in one approach may be optional or phased
- **Integration points**: Where components from different approaches must work together

### 17.1 Components Present in Approach 1 (OAuth HTTP Proxy) Only

| Component | Purpose | Why Missing from Approach 2 |
|-----------|---------|-------------------------|
| RFC 7591 Dynamic Client Registration | Auto-register MCP servers with Keycloak | Approach 2 uses ext_authz, not Keycloak |
| `/.well-known/mcp-configuration` | MCP-specific gateway metadata | Approach 2 doesn't expose gateway as discoverable resource |
| `KeycloakMCPClient` | Python client for Keycloak token exchange | Different auth model |
| `mcp_server_scopes` DB table | Scope-to-tool mapping | Uses capability aggregation instead |
| Circuit Breaker | Backend health management | Not discussed in Approach 2 |
| Backend OAuth Token Manager | Manage per-backend OAuth tokens | Uses ext_authz header injection |

### 17.2 Components Present in Approach 2 (MCP Governance & Protocol) Only

| Component | Purpose | Why Missing from Approach 1 |
|-----------|---------|-------------------------|
| `MCPPolicy` dataclass | Full MCP policy model with rules | Approach 1 uses task-scoped permissions |
| `MCPToolRule` / `MCPResourceRule` | Pattern-based access rules | Uses OAuth scopes instead |
| `MCPRateLimits` / `MCPContentFilters` | Fine-grained MCP governance | Relies on Keycloak rate limiting |
| `evaluate_tool_call()` pipeline | 8-step governance evaluation | Uses middleware chain |
| Prompt Template Governance | Control over `prompts/get` | Not covered |
| Constraint Evaluation Engine | Runtime constraint validation | Embedded in scoping engine |
| Party-Aware Enforcement | Different rules per agent party type | Uses trust levels in Keycloak |
| Response Filtering Middleware | Output content filtering | Not covered |
| Usage Tracking Middleware | Token/action accounting | Not covered |

### 17.3 Components Present in Both Approaches

| Component | Approach 1 (OAuth HTTP Proxy) | Approach 2 (MCP Governance & Protocol) |
|-----------|-------------------------------|----------------------------------------|
| MCP Session Manager | Task-bound sessions with Keycloak tokens | Protocol-level MCP sessions |
| Capability Aggregation | Via MCP Server Registry | Via Capability Aggregator |
| Tool Visibility Filtering | OAuth scope-based | Policy-based filtering |
| MCP Governance Engine | Basic action control | Full governance pipeline |
| Audit Logging | Standard logging | MCP-level audit events |

---

## 18. Missing Components and Roadmap

This section identifies components that were **designed in the original approaches but not yet fully specified** in this comprehensive architecture document. The missing components were identified through:

1. **AI Gateway Evolution Analysis** - Gap analysis comparing the current DeepTrail HTTP proxy gateway to full MCP support requirements
2. **Approach 1 vs Approach 2 Comparison** - Components that exist in one design approach but need to be carried forward to the unified architecture
3. **Research Paper Requirements** - Features from "Authenticated Delegation and Authorized AI Agents" that DeepSecure should implement

**Priority Legend**:
- **P0** = Critical for MVP - must be implemented for basic functionality
- **P1** = High priority - needed for production readiness
- **P2** = Medium priority - can be phased in after initial release

### 18.1 Category A: Authorization Infrastructure (Priority 0-1)

| Missing Piece | Description | Priority |
|---------------|-------------|----------|
| RFC 7591 Dynamic Client Registration | Process for auto-registering new MCP servers with Keycloak without manual config | P1 |
| `/.well-known/mcp-configuration` | MCP-specific discovery endpoint (complements RFC 9728) | P2 |
| Token Exchange Flow Details | Full RFC 8693 token exchange sequence diagrams | P1 |
| Circuit Breaker Pattern | Handling backend MCP server failures gracefully | P2 |
| Health Monitor Component | Tracking backend MCP server health status | P2 |

### 18.2 Category B: MCP Policy Model (Priority 0)

| Missing Piece | Description | Priority |
|---------------|-------------|----------|
| `MCPPolicy` dataclass | Full policy structure with tool/resource rules, rate limits, content filters | P0 |
| `MCPToolRule` / `MCPResourceRule` | Pattern-based access rules with glob matching | P0 |
| `MCPRateLimits` configuration | Per-tool/per-agent rate limiting structure | P1 |
| `MCPContentFilters` configuration | Input/output content filtering rules | P1 |
| `MCPPolicyStore` service | Database-backed policy storage and retrieval | P0 |

### 18.3 Category C: Protocol-Level Governance (Priority 0-1)

| Missing Piece | Description | Priority |
|---------------|-------------|----------|
| Capability Negotiation | Removing capabilities (tools, prompts, resources) from `initialize` response if agent lacks permissions | P0 |
| Multi-Server Namespace Strategy | Explicit documentation of `server_id.tool_name` prefixing | P0 |
| `prompts/get` Governance | Validating prompt template arguments to prevent hijacking | P1 |
| Prompt Template Governance | Controlling which prompt templates are available per agent | P1 |

### 18.4 Category D: Audit & Observability (Priority 0-1)

| Missing Piece | Description | Priority |
|---------------|-------------|----------|
| Delegator Audit Attribution | Document must specify Gateway injects `delegator` ID (human user) into audit log | P0 |
| Audit Metadata Structure | Explicit schema: `{sub, delegator, task_id, tool_name, outcome}` | P1 |
| MCP-Specific Metrics | Tool call counts, resource reads, prompt usage | P2 |

### 18.5 Category E: Resilience & Failure Modes (Priority 0-1)

| Missing Piece | Description | Priority |
|---------------|-------------|----------|
| Failure Mode Section | What happens to active MCP sessions if Control Plane / Keycloak is unavailable | P1 |
| Fail-Closed Behavior | Document the "deny by default" behavior when policy can't be fetched | P0 |
| Session Recovery | How MCP sessions are restored after gateway restart | P2 |
| Token Cache Behavior | Graceful degradation when Keycloak is unavailable | P1 |

### 18.6 Summary: Component Coverage

This matrix shows which components exist in each source versus what's documented in this comprehensive architecture ("Final Doc"). The **Research Proposal** column tracks components from the "Authenticated Delegation and Authorized AI Agents" paper.

Use this to:

- **Track implementation progress**: Mark components as covered when they're fully specified
- **Identify documentation gaps**: "MISSING" items need to be added to this document
- **Validate research alignment**: Ensure DeepSecure implements research-backed patterns
- **Plan sprints**: Group related missing components for implementation

**Legend**:
- ✅ = Fully covered in that source/document
- ⚠️ = Partially covered or implied
- ❌ = Not present in that source
- **MISSING** = Exists in source designs but not yet in this comprehensive doc

#### Token & Identity Components (from Research Paper)

| Component/Concept | Research Proposal | Approach 1 | Approach 2 | Final Doc | Gap Status |
|-------------------|-------------------|------------|------------|-----------|------------|
| User ID-Token (OIDC) | ✅ | ✅ | ✅ | ✅ | Covered |
| Agent-ID Token (with `owner` claim) | ✅ | ✅ | ✅ | ✅ | Covered |
| Delegation Token | ✅ | ✅ | ⚠️ | ✅ | Covered |
| `metadata_uri` claim | ✅ | ⚠️ | ❌ | ✅ | Covered |
| `user_token_hash` / `agent_token_hash` | ✅ | ⚠️ | ❌ | ✅ | Covered |
| `logging_uri` / `revocation_uri` | ✅ | ⚠️ | ❌ | ✅ | Covered |
| W3C Verifiable Credentials Option | ✅ | ❌ | ❌ | ⚠️ | **NEEDS DETAIL** |
| OAuth UMA (User-Managed Access) | ✅ | ❌ | ❌ | ❌ | **MISSING** |
| Monotonic Attenuation | ✅ | ⚠️ | ⚠️ | ✅ | Covered |

#### Policy & Governance Components (from Research Paper)

| Component/Concept | Research Proposal | Approach 1 | Approach 2 | Final Doc | Gap Status |
|-------------------|-------------------|------------|------------|-----------|------------|
| Structured Permission Language (XACML/ODRL) | ✅ | ❌ | ❌ | ❌ | **MISSING** |
| Natural Language to Policy Conversion | ✅ | ❌ | ❌ | ❌ | **MISSING** |
| Human-in-the-Loop Approval Flows | ✅ | ❌ | ⚠️ | ❌ | **MISSING** |
| Task Scoping vs Resource Scoping | ✅ | ⚠️ | ✅ | ⚠️ | Needs Emphasis |
| Inter-Agent Scoping (Agent-to-Agent) | ✅ | ❌ | ❌ | ❌ | **MISSING** |

#### MCP Gateway Components (from Approach 1 & 2)

| Component/Concept | Research Proposal | Approach 1 | Approach 2 | Final Doc | Gap Status |
|-------------------|-------------------|------------|------------|-----------|------------|
| Three-Layer Session Model | ❌ | ✅ | ⚠️ | ✅ | Covered |
| Keycloak Integration | ❌ | ✅ | ❌ | ✅ | Covered |
| Envoy ext_authz | ❌ | ❌ | ✅ | ✅ | Covered |
| RFC 7591 DCR | ❌ | ✅ | ❌ | ❌ | **MISSING** |
| `/.well-known/mcp-configuration` | ❌ | ✅ | ❌ | ❌ | **MISSING** |
| `MCPPolicy` dataclass | ❌ | ❌ | ✅ | ❌ | **MISSING** |
| `MCPToolRule`/`ResourceRule` | ❌ | ❌ | ✅ | ❌ | **MISSING** |
| Capability Aggregator | ❌ | ✅ | ✅ | ✅ | Covered |
| Namespace prefixing (`hubspot.tool`) | ❌ | ⚠️ | ✅ | ⚠️ | Needs Emphasis |
| Protocol-level Capability Filtering | ❌ | ❌ | ✅ | ⚠️ | Needs Detail |
| Circuit Breaker | ❌ | ✅ | ❌ | ❌ | **MISSING** |
| Health Monitor | ❌ | ✅ | ✅ | ❌ | **MISSING** |
| Prompt Template Governance | ❌ | ❌ | ✅ | ❌ | **MISSING** |

#### Audit & Operations Components

| Component/Concept | Research Proposal | Approach 1 | Approach 2 | Final Doc | Gap Status |
|-------------------|-------------------|------------|------------|-----------|------------|
| Delegator Audit Attribution | ✅ | ⚠️ | ✅ | ⚠️ | Needs Emphasis |
| Audit Metadata Structure | ✅ | ⚠️ | ✅ | ⚠️ | Needs Detail |
| Failure Mode Section | ❌ | ❌ | ❌ | ❌ | **MISSING** |
| Fail-Closed Behavior | ❌ | ⚠️ | ⚠️ | ❌ | **MISSING** |
| Token Revocation Mechanism | ✅ | ✅ | ⚠️ | ⚠️ | Needs Detail |

### 18.7 Research Paper Components Roadmap

The following components are proposed in the research paper "Authenticated Delegation and Authorized AI Agents" but not yet fully implemented in DeepSecure. These represent potential future enhancements.

| Research Paper Component | Description | DeepSecure Status | Recommendation |
|--------------------------|-------------|-------------------|----------------|
| **W3C Verifiable Credentials** | Alternative to OIDC tokens for decentralized, privacy-preserving delegation | Not implemented | Consider for future federated identity scenarios |
| **OAuth UMA (User-Managed Access)** | Protocol for user to manage multiple agents from single policy point | Not implemented | Evaluate for multi-agent management use cases |
| **Natural Language to Policy Conversion** | Translate user instructions into XACML/ODRL policies | Not implemented | High value for UX - consider LLM-assisted policy generation |
| **Structured Permission Language (XACML)** | Machine-readable, auditable policy definitions | Not implemented | Needed for compliance and enterprise adoption |
| **Human-in-the-Loop Approval Flows** | Runtime confirmation prompts for sensitive actions | Not implemented | Critical for high-risk operations |
| **Inter-Agent Scoping** | Agent-to-agent delegation with scope inheritance | Not implemented | Needed for multi-agent orchestration |

**Source Documents**:
- Research Paper: `docs/design/internal/pdfs/Authenticated_Delegation_and_Authorized_AI_Agents.pdf`
- Analysis: `docs/design/internal/pdfs/Authenticated_AI_Agent_Delegation_Framework_and_DeepSecure_Analysis.pdf`

---

# Part VII: Key Improvements

## 19. Key Improvements

### 19.1 Improvements Over Research's Model

| Gap in Research | DeepSecure Solution |
|--------------|---------------------|
| **No cryptographic agent identity** | Ed25519 keypairs with challenge-response authentication |
| **No per-task scoping** | Task Tokens with scoped_permissions[] and constraints |
| **No split-key secret management** | Shamir's Secret Sharing with JIT reassembly |
| **No MCP-specific OAuth** | Keycloak token exchange to audience-bound MCP tokens |
| **No attestation** | Party-type classification (1st/2nd/3rd party) |
| **Generic delegation** | Macaroon-based delegation with attenuation |

### 19.2 Improvements Over Original DeepTrail

| Gap in Original DeepTrail | Updated Solution |
|---------------------------|------------------|
| **No enterprise IdP integration** | User identity and agent registration moved to enterprise IdP |
| **No cryptographic binding** | Added `user_token_hash`, `agent_token_hash` in delegation tokens |
| **No agent metadata endpoint** | Added `metadata_uri` claim for capability discovery |
| **No logging/revocation URIs** | Added `logging_uri`, `revocation_uri` in delegation tokens |
| **Groups not preserved** | IdP groups flow through to Agent Session JWT |
| **No consent tracking** | Added `consent_ref` for IdP consent correlation |

---

# Part VIII: Virtual MCP Server Implementation Challenges

The Virtual MCP Server pattern introduces significant engineering challenges that must be addressed for production deployment. These challenges were identified through six months of production experience and are documented here to guide implementation.

**Source**: These challenges are derived from the AI Agent Conference 2026 talk "The Virtual MCP Server Pattern: Securing Multi-Tool AI Agents at Scale" and production experience with the DeepTrail Gateway.

### Transport Protocol Context

> **Important**: The MCP specification defines two transports:
> - **stdio**: For local subprocess communication
> - **Streamable HTTP** (2025-06-18): Replaces the deprecated HTTP+SSE transport (2024-11-05)
>
> **Streamable HTTP is a hybrid transport** that supports:
> - **JSON mode**: Simple request → JSON response (stateless)
> - **SSE mode**: Request → SSE stream response (streaming)
> - **GET + SSE**: Server-initiated push via GET endpoint
>
> The challenges below were identified with the older HTTP+SSE transport. **With Streamable HTTP (JSON mode)**, many connection/session challenges are simplified. See the [SSE vs HTTP Transport Analysis](deepsecure-sse-vs-http-transport-analysis.md) for detailed comparison.
>
> **Reference**: [MCP Specification - Transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)

---

## 20. Connection & Session Management Challenges

### Why These Challenges Matter

When the Gateway acts as a Virtual MCP Server managing connections to 47+ backend MCP servers for 100+ concurrent agents, connection and session management becomes the primary scalability bottleneck. These challenges must be solved before production deployment.

### 20.1 The N×M Connection Explosion Problem

**The Challenge**: Each agent × each backend server = one potential MCP connection.

```
THE N×M PROBLEM:

100 concurrent agents × 47 backend MCP servers = 4,700 potential connections

But MCP connections are NOT lightweight:
├── Each connection requires initialize handshake (~100ms)
├── Each connection maintains session state (server capabilities, protocol version)
├── Each connection needs an OAuth token (5-15 min TTL)
├── Each connection can fail independently
├── Each connection consumes memory and file descriptors

Reality: You CANNOT maintain 4,700 active connections.
```

**Impact**: Without solving this, the Gateway cannot scale beyond a handful of agents.

### 20.2 Solution: Connection Pooling per Backend

**Key Insight**: Pool connections per BACKEND, not per agent. OAuth tokens are per-agent, but connections can be shared.

```python
class MCPConnectionPool:
    def __init__(self):
        # Pool connections per BACKEND, not per agent
        # 100 agents sharing 47 backends = 47 pools, not 4,700 connections
        self.pools: dict[str, BackendConnectionPool] = {}
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
    
    async def get_connection(
        self, 
        backend_id: str, 
        agent_token: str
    ) -> MCPConnection:
        # Step 1: Check circuit breaker BEFORE attempting connection
        breaker = self.circuit_breakers.get(backend_id)
        if breaker and breaker.is_open:
            raise BackendUnavailableError(
                f"{backend_id} is temporarily unavailable",
                retry_after=breaker.reset_time
            )
        
        # Step 2: Get or create pool for this backend
        pool = self.pools.get(backend_id)
        if not pool:
            pool = BackendConnectionPool(
                backend_id=backend_id,
                min_connections=2,
                max_connections=10
            )
            self.pools[backend_id] = pool
        
        # Step 3: Acquire connection from pool
        conn = await pool.acquire(timeout=5.0)
        
        # Step 4: Inject agent-specific OAuth token
        # Connection is shared, but auth is per-request
        oauth_token = await self.token_service.get_backend_token(
            agent_token, backend_id
        )
        conn.set_authorization(oauth_token)
        
        return conn
    
    async def release_connection(self, backend_id: str, conn: MCPConnection):
        """Return connection to pool for reuse."""
        conn.clear_authorization()  # Remove agent-specific token
        await self.pools[backend_id].release(conn)
```

**Results**:

| Approach | Connections Required |
|----------|---------------------|
| Naive (per agent × backend) | 100 × 47 = 4,700 |
| Pooled (per backend, 10 max each) | 47 × 10 = 470 |
| **Reduction** | **90%** |

**Critical Gotcha**: OAuth tokens are per-agent, but connections are shared. You inject the agent's token at request time, not at connection time. Connection setup is amortized, but auth overhead remains per-request.

### 20.3 Session State Machine with Lazy Initialization

**The Challenge**: MCP is stateful. Each connection has a session. When you have one gateway managing 47 backend sessions per agent, state management becomes complex.

```
SESSION STATE CHALLENGE:

Gateway maintains:
├── Agent Session #1 (agent-sales-001)
│   ├── MCP Session → HubSpot (initialized, ready)
│   ├── MCP Session → Notion (initialized, ready)
│   └── MCP Session → Slack (connection lost, reconnecting)
│
├── Agent Session #2 (agent-support-002)
│   ├── MCP Session → Zendesk (initialized, ready)
│   ├── MCP Session → Slack (initialized, ready)
│   └── MCP Session → PagerDuty (rate limited, backoff)
│
└── Agent Session #3 (agent-data-003)
    ├── MCP Session → BigQuery (initialized, ready)
    └── MCP Session → Snowflake (auth expired, re-authenticating)

PROBLEMS:
1. Session per agent × backends = N×M connections
2. Backend failures shouldn't break agent session
3. Re-initialization must be transparent to agent
```

**Solution: Session State Machine with Lazy Initialization**

```python
class MCPSessionManager:
    def __init__(self):
        self.sessions: dict[str, dict[str, MCPSession]] = {}  # agent_id -> {server_id -> session}
    
    async def get_or_create_session(
        self, 
        agent_id: str, 
        server_id: str
    ) -> MCPSession:
        if agent_id not in self.sessions:
            self.sessions[agent_id] = {}
        
        if server_id not in self.sessions[agent_id]:
            # Lazy initialization - only connect when first needed
            session = await self._create_session(agent_id, server_id)
            self.sessions[agent_id][server_id] = session
        
        session = self.sessions[agent_id][server_id]
        
        # Handle session recovery
        if session.state == SessionState.DISCONNECTED:
            await session.reconnect()
        
        if session.state == SessionState.AUTH_EXPIRED:
            token = await self.token_service.refresh(agent_id, server_id)
            await session.reauthenticate(token)
        
        return session
```

### 20.4 Session State Persistence with Redis

**Production Insight**: Use Redis for session state to enable horizontal scaling. Gateway instances are stateless; all session data lives in Redis with TTLs.

```python
class RedisSessionStore:
    async def save_session(self, agent_id: str, server_id: str, session: MCPSession):
        key = f"mcp_session:{agent_id}:{server_id}"
        await self.redis.setex(
            key,
            ttl=session.ttl,
            value=session.serialize()
        )
    
    async def get_session(self, agent_id: str, server_id: str) -> Optional[MCPSession]:
        key = f"mcp_session:{agent_id}:{server_id}"
        data = await self.redis.get(key)
        return MCPSession.deserialize(data) if data else None
```

### 20.5 Failure Modes and Mitigation

| Failure Scenario | Impact | Mitigation |
|-----------------|--------|------------|
| **Backend MCP server down** | `tools/call` fails for that backend | Circuit breaker + graceful MCP error response |
| **Control Plane unavailable** | Can't validate policies | **Fail-closed**: deny ALL requests |
| **Keycloak unavailable** | Can't exchange tokens | Use cached tokens if valid; else fail-closed |
| **Gateway restart** | In-memory sessions lost | Session state in Redis survives restarts |
| **Redis unavailable** | Session lookups fail | Fallback to stateless mode (re-validate each request) |

**Additional Failure Modes (MCP Spec 2025-06-18)**:

| Failure Scenario | HTTP Status | Client Action |
|-----------------|-------------|---------------|
| **Session expired or invalid** | 404 Not Found | Client MUST re-initialize without session ID |
| **Unsupported protocol version** | 400 Bad Request | Client must use supported version |
| **Invalid Origin header** | 403 Forbidden | Request rejected (DNS rebinding protection) |
| **SSE stream disconnected** | N/A | Client reconnects with `Last-Event-ID` header |

**The Fail-Closed Principle (Non-Negotiable for Security)**:

```python
async def authorize_request(self, agent_token: str, tool_name: str) -> AuthzResult:
    try:
        result = await self.control_plane.authorize(agent_token, tool_name)
        return result
    except ControlPlaneUnavailableError:
        # CRITICAL: Default to DENY, not ALLOW
        logger.error("Control plane unavailable - failing closed")
        return AuthzResult(
            allowed=False,
            reason="Policy service unavailable - request denied",
            retry_after=30
        )
    except Exception as e:
        # Unknown errors also fail closed
        logger.error(f"Authorization error: {e} - failing closed")
        return AuthzResult(allowed=False, reason="Internal error")
```

> **Never fail open.** An agent that can't reach the policy service should be unable to do anything. This is the security equivalent of "when in doubt, don't."

### 20.6 MCP Spec Compliance Requirements (Streamable HTTP)

Per the [MCP Specification 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports), the Gateway must implement these requirements:

#### 20.6.1 Session Management via `Mcp-Session-Id` Header

Sessions are managed via HTTP headers, not connection state:

```python
class MCPSessionManager:
    """MCP Spec compliant session management."""
    
    def __init__(self):
        self.sessions: dict[str, SessionData] = {}  # session_id -> data
    
    async def handle_initialize(self, request: MCPRequest) -> MCPResponse:
        """Assign session ID on initialize."""
        # Generate cryptographically secure session ID
        session_id = secrets.token_urlsafe(32)
        
        # Store session data
        self.sessions[session_id] = SessionData(
            agent_id=request.agent_id,
            created_at=datetime.utcnow(),
            capabilities=self._negotiate_capabilities(request)
        )
        
        # Return session ID in response header
        response = MCPResponse(result=InitializeResult(...))
        response.headers["Mcp-Session-Id"] = session_id
        return response
    
    async def validate_session(self, request: Request) -> SessionData:
        """Validate session ID on subsequent requests."""
        session_id = request.headers.get("Mcp-Session-Id")
        
        if not session_id:
            raise HTTPException(400, "Mcp-Session-Id header required")
        
        session = self.sessions.get(session_id)
        if not session:
            # Spec: Return 404 for expired/invalid session
            raise HTTPException(404, "Session not found or expired")
        
        if session.is_expired():
            del self.sessions[session_id]
            raise HTTPException(404, "Session expired")
        
        return session
    
    async def terminate_session(self, request: Request):
        """Handle explicit session termination via DELETE."""
        session_id = request.headers.get("Mcp-Session-Id")
        if session_id and session_id in self.sessions:
            del self.sessions[session_id]
        return Response(status_code=200)
```

**Session Lifecycle**:

| Event | Client Action | Server Action |
|-------|--------------|---------------|
| **Initialize** | POST with `initialize` method | Return `Mcp-Session-Id` header |
| **Subsequent requests** | Include `Mcp-Session-Id` header | Validate, return 404 if invalid |
| **Session expiry** | Receives 404 | Client re-initializes without session ID |
| **Explicit close** | DELETE with `Mcp-Session-Id` | Remove session, return 200 (or 405) |

#### 20.6.2 Protocol Version Header

All HTTP requests must include the protocol version:

```python
SUPPORTED_PROTOCOL_VERSIONS = {"2025-06-18", "2025-03-26"}

async def validate_protocol_version(request: Request):
    """Validate MCP-Protocol-Version header."""
    version = request.headers.get("MCP-Protocol-Version")
    
    # If header present, must be supported
    if version and version not in SUPPORTED_PROTOCOL_VERSIONS:
        raise HTTPException(400, f"Unsupported protocol version: {version}")
    
    # For backwards compatibility: if no header, assume 2025-03-26
    return version or "2025-03-26"
```

#### 20.6.3 Origin Header Validation (DNS Rebinding Prevention)

**Security Requirement**: Servers MUST validate the Origin header to prevent DNS rebinding attacks:

```python
ALLOWED_ORIGINS = {
    "https://console.deeptrail.io",
    "https://app.enterprise.com",
    # For local development
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}

async def validate_origin(request: Request):
    """Prevent DNS rebinding attacks per MCP spec."""
    origin = request.headers.get("Origin")
    
    if origin and origin not in ALLOWED_ORIGINS:
        logger.warning(f"Rejected request with invalid Origin: {origin}")
        raise HTTPException(403, "Invalid origin")
    
    # No Origin header is allowed (e.g., server-to-server calls)
    return origin
```

**Why This Matters**: Without Origin validation, an attacker could:
1. Register a domain that initially resolves to their server
2. Serve malicious JavaScript
3. Change DNS to resolve to `127.0.0.1`
4. Browser sends requests to local MCP server with attacker's cookies/context

#### 20.6.4 Stream Resumability (SSE Mode Only)

When using SSE responses, implement resumability via event IDs:

```python
class ResumableSSEStream:
    """Support stream resumption per MCP spec."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.event_counter = 0
        self.event_buffer: deque[SSEEvent] = deque(maxlen=100)  # Buffer for replay
    
    async def send_event(self, event_type: str, data: dict) -> None:
        """Send SSE event with ID for resumability."""
        self.event_counter += 1
        event_id = f"{self.session_id}-{self.event_counter}"
        
        event = SSEEvent(
            id=event_id,
            event=event_type,
            data=json.dumps(data)
        )
        
        # Buffer for potential replay
        self.event_buffer.append(event)
        
        await self._write_event(event)
    
    async def resume_from(self, last_event_id: str) -> None:
        """Replay events after client reconnection."""
        # Parse the event counter from the ID
        _, last_counter = last_event_id.rsplit("-", 1)
        last_counter = int(last_counter)
        
        # Replay buffered events after the last received
        for event in self.event_buffer:
            _, event_counter = event.id.rsplit("-", 1)
            if int(event_counter) > last_counter:
                await self._write_event(event)
```

**Resumability Flow**:

```
1. Client receives events with IDs: evt-001, evt-002, evt-003
2. Connection drops after evt-002
3. Client reconnects: GET /mcp with Last-Event-ID: evt-002
4. Server replays evt-003 and continues stream
```

---

## 21. Cache & Performance Challenges

### Why These Challenges Matter

When 47 backends collectively expose 312 tools, and each agent should only see their authorized subset, filtering and caching must be fast. Without optimization, every `tools/list` request becomes a performance bottleneck.

### 21.1 Tools/List Filtering at Scale

**The Scale Problem**:

```
Total tools across all backends: 312
Agents in system: 2,847
Policies (agent → tools): 15,234

Naive approach:
  For each tools/list request:
    For each tool (312):
      For each policy (15,234):
        Check if policy grants access
  
  = 312 × 15,234 = 4.75M policy evaluations per request
  = 200ms+ latency (unacceptable for tools/list)
```

**Solution: Precomputed Permission Matrices + Bloom Filters**

```python
class ToolFilterEngine:
    def __init__(self):
        # Precomputed: agent_id → set of allowed tool names
        self.permission_matrix: dict[str, set[str]] = {}
        
        # Bloom filter for fast negative checks
        self.tool_bloom_filters: dict[str, BloomFilter] = {}
    
    async def refresh_permissions(self, agent_id: str):
        """Called when agent authenticates or policies change."""
        
        # Fetch all policies for this agent
        policies = await self.policy_store.get_policies(agent_id)
        
        allowed_tools = set()
        for policy in policies:
            if policy.effect == "allow":
                # Expand wildcards: "hubspot:*" → ["hubspot.create_contact", ...]
                expanded = self._expand_permission(policy.resource)
                allowed_tools.update(expanded)
        
        # Store precomputed set
        self.permission_matrix[agent_id] = allowed_tools
        
        # Build bloom filter for O(1) negative checks
        bf = BloomFilter(capacity=len(allowed_tools), error_rate=0.001)
        for tool in allowed_tools:
            bf.add(tool)
        self.tool_bloom_filters[agent_id] = bf
    
    def filter_tools(self, agent_id: str, tools: list[Tool]) -> list[Tool]:
        """Filter tools in O(n) instead of O(n×m)."""
        
        allowed = self.permission_matrix.get(agent_id, set())
        bloom = self.tool_bloom_filters.get(agent_id)
        
        filtered = []
        for tool in tools:
            # Fast bloom filter check (O(1))
            if bloom and not bloom.might_contain(tool.name):
                continue  # Definitely not allowed
            
            # Exact check only if bloom says maybe
            if tool.name in allowed:
                filtered.append(tool)
        
        return filtered
```

**Results**:

| Metric | Before | After |
|--------|--------|-------|
| tools/list latency (p50) | 180ms | 12ms |
| tools/list latency (p99) | 450ms | 35ms |
| Policy evaluations per request | 4.75M | 312 |

### 21.2 Capability Cache Invalidation

**The Challenge**: When you aggregate tools from 47 backends, you cache the aggregated response. But when do you invalidate that cache? This is one of the two hard problems in computer science.

```
CACHE INVALIDATION TRIGGERS:

1. Backend adds/removes tools      → You don't know this happened!
2. Agent's permissions change      → Policy update from Control Plane
3. Backend goes down               → Tools should disappear from list
4. Backend comes back up           → Tools should reappear
5. OAuth token expires             → Can't refresh tools from that backend
6. Backend rate limits you         → Temporarily hide tools?
```

**Solution: Layered Caching with Event-Driven Invalidation**

```python
class CapabilityAggregator:
    def __init__(self):
        # Layer 1: Per-backend capability cache (TTL-based refresh)
        self.backend_capabilities: TTLCache[str, list[Tool]] = TTLCache(ttl=300)  # 5 min
        
        # Layer 2: Per-agent filtered view (invalidated on policy change)
        self.agent_tool_views: dict[str, CacheEntry] = {}
        
        # Layer 3: Backend health status (affects what we aggregate)
        self.backend_health: dict[str, HealthStatus] = {}
    
    async def get_tools_for_agent(self, agent_id: str) -> list[Tool]:
        # Check if agent's view is cached and still valid
        cached = self.agent_tool_views.get(agent_id)
        if cached and not cached.is_stale:
            return cached.tools
        
        # Rebuild: aggregate from healthy backends only
        all_tools = []
        for backend_id, health in self.backend_health.items():
            if health.status != "healthy":
                continue  # Skip unhealthy backends
            
            backend_tools = await self._get_backend_tools(backend_id)
            all_tools.extend(backend_tools)
        
        # Apply agent's policy filter
        policy = await self.policy_store.get_policy(agent_id)
        filtered = self._filter_by_policy(all_tools, policy)
        
        # Cache the filtered view
        self.agent_tool_views[agent_id] = CacheEntry(tools=filtered, ttl=60)
        return filtered
    
    async def handle_policy_change(self, agent_id: str):
        """Called by Control Plane webhook when agent's policy changes."""
        # Invalidate only this agent's view - O(1) operation
        self.agent_tool_views.pop(agent_id, None)
        logger.info(f"Invalidated tool cache for agent {agent_id}")
    
    async def handle_backend_health_change(self, backend_id: str, is_healthy: bool):
        """Called by Health Monitor when backend state changes."""
        self.backend_health[backend_id].status = "healthy" if is_healthy else "unhealthy"
        
        # Invalidate ALL agent views - backend availability affects everyone
        self.agent_tool_views.clear()
        logger.info(f"Backend {backend_id} health changed - cleared all agent caches")
```

**Caching Strategy Summary**:

| Cache Layer | Scope | TTL | Invalidation Trigger |
|-------------|-------|-----|---------------------|
| **Backend Capabilities** | Per backend | 5 min | TTL expiry |
| **Agent Filtered Views** | Per agent | 60 sec | Policy change webhook, backend health change |
| **Backend Health** | Per backend | N/A | Health check failure/recovery |

**Thundering Herd Mitigation**: When a backend comes back up, batch cache invalidation with a 10-second delay to avoid thundering herd on backend recovery.

---

## 22. User Consent & OAuth Challenges

### 22.1 The User Consent Problem for Headless Agents

**The Challenge**: Some MCP servers require user consent. OAuth flows expect a browser. Agents don't have browsers.

```
THE CONSENT PROBLEM:

Standard OAuth for MCP (from spec):

User → Browser → Authorization Server → Consent Screen → Redirect → Token

For agents:

Agent → ??? → There is no browser → ???

If HubSpot MCP server requires user consent for an agent to access
CRM data, how does the agent obtain that consent?
```

### 22.2 Solution: Delegation-Based Consent

**Key Insight**: Separate consent-time from runtime. Human user consents once (via browser), then delegates to agent.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DELEGATION-BASED CONSENT MODEL                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CONSENT TIME (Human performs OAuth):                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  1. Human user (Sarah) logs into DeepTrail Console                      │ │
│  │  2. Sarah clicks "Connect HubSpot" → Browser OAuth flow                 │ │
│  │  3. Sarah consents on HubSpot's consent screen                          │ │
│  │  4. HubSpot returns OAuth tokens to DeepTrail                           │ │
│  │  5. DeepTrail stores tokens, associated with Sarah's account            │ │
│  │                                                                          │ │
│  │  Sarah then DELEGATES to agent:                                          │ │
│  │  POST /delegate                                                          │ │
│  │  {                                                                       │ │
│  │    "agent_id": "agent-sdr-001",                                         │ │
│  │    "permissions": ["hubspot:contacts:read", "hubspot:contacts:update"], │ │
│  │    "ttl": "7d"                                                           │ │
│  │  }                                                                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                               │
│                              │ Delegation Token (Macaroon)                  │
│                              ▼                                               │
│  RUNTIME (Agent uses delegated access):                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  1. Agent presents Delegation Token to gateway                          │ │
│  │  2. Gateway validates token, extracts delegator (Sarah)                 │ │
│  │  3. Gateway uses Sarah's stored HubSpot credentials                     │ │
│  │  4. All actions audited as "agent-sdr-001 on behalf of Sarah"          │ │
│  │                                                                          │ │
│  │  Agent NEVER does OAuth. Agent NEVER sees HubSpot credentials.          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  SECURITY PROPERTIES:                                                        │
│  ✓ User consents once, in their browser                                     │
│  ✓ Agent permissions are subset of user's permissions (attenuation)         │
│  ✓ Delegation can be revoked at any time                                    │
│  ✓ All agent actions attributed to delegating user                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Implementation Notes**:

| Component | Responsibility |
|-----------|---------------|
| **DeepTrail Console** | Web UI for user OAuth flows and delegation management |
| **Credential Vault** | Secure storage of user's OAuth tokens (per service) |
| **Delegation Service** | Issue/validate/revoke delegation tokens (macaroons) |
| **Gateway** | Map delegation token → user credentials → backend auth |

---

## 23. Open Problems (Future)

These are real engineering problems that the MCP ecosystem hasn't fully solved yet. They are documented here for awareness and future planning.

### 23.1 Streaming Through a Virtual Server

**The Problem**: MCP supports SSE streaming for long-running tool calls. The Gateway must handle dual SSE connections.

```
STREAMING AGGREGATION PROBLEM:

Agent calls: notion.export_database (streams 1000 rows over 30 seconds)

Without Virtual Server:
  Agent ←────────── SSE stream ────────── Notion MCP Server
  (Direct, simple)

With Virtual Server:
  Agent ←── SSE ── Gateway ←── SSE ── Notion MCP Server
                      ↑
            Gateway must:
            1. Maintain SSE connection to agent
            2. Maintain SSE connection to backend
            3. Forward events in real-time
            4. Apply governance to EACH streamed chunk
            5. Handle backpressure (slow agent, fast backend)
            6. Timeout handling for stalled streams
            7. Clean up both connections on error
```

**Current Workaround**: Buffer small responses (<1MB) and stream large ones unfiltered with a security warning. True stream-level governance (filtering each chunk) adds 5-10ms per chunk latency, which is often unacceptable for LLM token streaming.

**Status**: Partially solved. Needs stream-aware governance that doesn't add unacceptable latency.

### 23.2 Cross-Server Transactions

**The Problem**: What if an agent needs to atomically update HubSpot AND Salesforce? MCP has no transaction protocol.

**Current Workaround**: Exploring saga patterns with compensating actions.

**Status**: Unsolved. No MCP standard for distributed transactions.

### 23.3 Tool Schema Evolution

**The Problem**: When HubSpot updates their tool schema, the Gateway's cached tools/list is stale. There's no MCP mechanism for backends to notify clients of schema changes.

**Impact**: Agents may call tools with outdated parameter schemas, causing failures.

**Status**: Unsolved. Need schema versioning and proactive invalidation mechanism.

### 23.4 Federated Virtual Servers

**The Problem**: Enterprise A has a Virtual MCP Server. Enterprise B has another. Agent needs tools from both. Do we need Virtual-Virtual MCP Servers?

**Status**: The "MCP mesh" problem is unsolved. May require MCP-level federation protocol.

### 23.5 Hot-Reloading Backend Configurations

**The Problem**: When you add a new backend MCP server, how do you hot-reload without restarting the gateway?

**Current Solution**: Dynamic configuration with watch/reload.

**Gap**: The MCP spec doesn't define how to notify clients of new capabilities mid-session. Agents connected to the Gateway won't see new tools until their session restarts.

### 23.6 Challenge Summary Matrix

| Challenge | Severity | Solution Status | Priority |
|-----------|----------|-----------------|----------|
| **N×M Connection Explosion** | Critical | ✅ Solved (connection pooling) | P0 |
| **Session State Management** | High | ✅ Solved (Redis + state machine) | P0 |
| **Tools/List Filtering** | High | ✅ Solved (bloom filters + precompute) | P0 |
| **Cache Invalidation** | High | ✅ Solved (layered caching + events) | P0 |
| **User Consent** | Medium | ✅ Solved (delegation-based) | P1 |
| **SSE Streaming Governance** | Medium | ⚠️ Partial (buffer small, stream large) | P1 |
| **Cross-Server Transactions** | Low | ❌ Unsolved | P2 |
| **Tool Schema Evolution** | Low | ❌ Unsolved | P2 |
| **Federated Virtual Servers** | Low | ❌ Unsolved | P2 |
| **Hot-Reload Configurations** | Low | ⚠️ Partial (needs MCP spec support) | P2 |

---

## Summary

This architecture provides:

1. **Agent-native identity** - Not forcing OAuth on autonomous agents; using Ed25519 cryptographic identity
2. **Standards-compliant MCP auth** - OAuth 2.0/2.1 for backend MCP servers per RFC 9728
3. **Clean separation** - Internal auth (DeepTrail) vs external auth (Keycloak) vs identity (Enterprise IdP)
4. **Enterprise IdP integration** - Seamless integration with Okta/Entra for user identity and agent registration
5. **Per-task least privilege** - Task Tokens with scoped permissions and automatic revocation
6. **Minimal attack surface** - Short-lived, scoped tokens at every layer
7. **Full auditability** - Every token exchange is logged with user attribution
8. **MCP Governance** - Capability filtering, namespace prefixing, parameter validation, result filtering
9. **Session Hierarchy** - User Session → Agent Session → MCP Session for stateful permission tracking
10. **Action Control** - Fine-grained enforcement of constraints at the gateway layer
11. **Scalable Connection Management** - Connection pooling per backend (not per agent) reducing N×M to M×max_pool connections
12. **Production-Ready Caching** - Layered caching with precomputed permission matrices and bloom filters for O(1) tool filtering

The recommended approach is to implement **both layers**:
- **MCP Protocol Layer** - For governance, aggregation, and agent experience
- **OAuth Authorization Layer** - For standards-compliant backend communication

**Implementation Challenges Addressed**:

| Category | Challenges Documented | Solution Status |
|----------|----------------------|-----------------|
| Connection & Session Management | N×M explosion, pooling, state machine, Redis persistence | ✅ Solved |
| Cache & Performance | Tools/list filtering, capability cache invalidation | ✅ Solved |
| User Consent & OAuth | Headless agent consent, delegation-based model | ✅ Solved |
| Open Problems | Streaming governance, cross-server transactions, schema evolution | ⚠️ Partial/Future |

---

*Document Version: 5.1 (Consolidated) | Last Updated: January 2026 | Updated with MCP Spec 2025-06-18 compliance requirements*
