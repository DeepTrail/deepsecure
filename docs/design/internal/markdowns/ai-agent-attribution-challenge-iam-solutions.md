# AI Agent Attribution Challenge: IAM Solutions and Business Opportunity

> **Document Type**: Strategic Analysis  
> **Date**: January 30, 2026  
> **Status**: Draft  
> **Authors**: DeepSecure Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [The Attribution Problem](#the-attribution-problem)
3. [IAM Requirements for AI Agents](#iam-requirements-for-ai-agents)
4. [Potential Solutions](#potential-solutions)
5. [Solution Deep-Dive: Agent Name Service (ANS)](#solution-deep-dive-agent-name-service-ans)
6. [Gap Analysis](#gap-analysis)
7. [Business Opportunity](#business-opportunity)
8. [DeepSecure's Role](#deepsecures-role)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Conclusion](#conclusion)

---

## Executive Summary

When AI agents perform actions on behalf of developers—PR comments, forking repositories, liking, issue triage, and other developer workflows—there is a critical lack of attribution to identify:

- **Who** authorized the agent (which human/developer)
- **Which organization** the agent represents
- **What intent** is behind the agent's actions

This creates a "shadow workforce" problem where valuable developer activity signals become invisible to platforms that rely on them for buyer intelligence (e.g., reo.dev), while enterprises lose credit for their AI-augmented contributions.

**The Solution**: A Public Agent Registry based on the Agent Name Service (ANS) architecture that provides verifiable, PKI-backed attribution linking agents to organizations and individual developers through cryptographic certificates.

**The Opportunity**: DeepSecure can serve as the enterprise on-ramp to ANS, operating as a Registration Authority (RA) gateway that makes adoption seamless for enterprises while creating a multi-sided revenue model from registration fees, platform query fees, and AI vendor integrations.

---

## The Attribution Problem

### The Current State: Invisible Agent Activity

AI agents are increasingly performing developer activities across platforms:

| Platform | Agent Actions | Current Attribution |
|----------|--------------|---------------------|
| GitHub | PR comments, code reviews, issue triage, forking | Bot tokens → No org mapping |
| GitLab | Merge requests, CI/CD automation | Service accounts → Anonymous |
| Slack | Message responses, workflow automations | App tokens → No user mapping |
| Linear/Jira | Issue creation, status updates | API keys → No developer mapping |
| NPM/PyPI | Package evaluations, dependency checks | Anonymous requests |

### What Information Is Lost

When an AI agent makes a PR comment on GitHub:

```
GitHub sees:     actor = "bot-token-xyz made a comment"
What's missing:  Which human authorized this?
                 What organization?
                 What was the intent?
```

**Example: Before vs After Agents**

```
Before Agents:
  Developer Jane @ AcmeCorp stars repo → Signal: "AcmeCorp evaluating this tool"
  
After Agents:
  Bot-xyz-123 clones repo      → Signal: ??? (lost)
  Bot-xyz-123 opens test PR    → Signal: ??? (lost)
  Bot-xyz-123 comments issues  → Signal: ??? (lost)
```

### Why This Matters

**For Developer Intelligence Platforms (e.g., reo.dev):**
- Business model relies on: `Developer Activity → Signal Extraction → Buyer Intent → Sales Intelligence`
- Conservative estimate: **20-40% of actionable developer signals** will be agent-generated within 2 years
- Without attribution, these signals disappear entirely

**For Enterprises:**
- AI-augmented developer contributions are invisible
- No credit for open source contributions made via agents
- Compliance/audit gaps for agent activity
- Security concerns about unattributed agents acting on their behalf

**For AI Tool Vendors:**
- Enterprise customers demand accountability and audit trails
- Unverified agents face rate limiting and blocking by platforms
- No differentiation between "trusted" and "untrusted" agents

---

## IAM Requirements for AI Agents

### The Core Challenge

AI agents operating on behalf of enterprises are not controlled by the platforms observing them. Traditional IAM assumes the identity provider and the relying party have a direct relationship. With AI agents:

```
Enterprise (controls agent) ─────┬───── Platform A (GitHub)
                                 ├───── Platform B (Slack)
                                 ├───── Platform C (Linear)
                                 └───── Observer D (reo.dev)
                                        ↑
                                        │
                                 Observer has no relationship
                                 with Enterprise's IdP
```

### What IAM Primitives Are Needed

#### 1. Agent-to-Human Binding (Delegation Chain)

```
Human (buyer) → Authorization → Agent → Action on Platform
     ↑
  This link is currently invisible to third parties
```

**Required Claims:**
- `delegating_principal_id` - The human who authorized the agent
- `delegation_scope` - What the agent is allowed to do
- `delegation_timestamp` - When authorization was granted
- `organization_id` - The org context

#### 2. Verifiable Organizational Identity

The agent's identity token should include verifiable claims about:
- Organization domain (e.g., `@acme.com`)
- Department/team (engineering, procurement, etc.)
- Corporate IdP attestation
- Legal entity verification

#### 3. Purpose/Intent Metadata

- `workflow_type`: "code_review", "dependency_evaluation", "security_audit"
- `project_context`: What repo/project is this for
- `evaluation_stage`: "discovery", "poc", "procurement"

#### 4. Auditability

- Third parties need to query this information
- Without requiring the agent to opt-in to each observer
- Cryptographic verification (not just self-declared)

---

## Potential Solutions

### Solution 1: Standardized Agent Identity Token (OAuth Extension)

Extend OAuth 2.0 with agent-specific claims:

```json
{
  "sub": "agent:cursor-ai-xyz",
  "iss": "https://enterprise-idp.acme.com",
  "aud": "github.com",
  "delegating_user": {
    "sub": "user:jane.doe@acme.com",
    "name": "Jane Doe",
    "department": "Engineering"
  },
  "organization": {
    "id": "org:acme-corp",
    "domain": "acme.com",
    "verified": true
  },
  "agent_metadata": {
    "agent_type": "coding_assistant",
    "vendor": "cursor.com",
    "workflow": "pr_review"
  }
}
```

| Pros | Cons |
|------|------|
| Standard OAuth infrastructure | Requires platform adoption (GitHub, etc. need to read/expose) |
| Enterprise IdPs can issue these | Slow standards process |
| Familiar to security teams | Doesn't solve cross-platform discovery |

### Solution 2: Public Agent Registry (WHOIS for AI Agents)

A queryable registry where:
- Enterprises register their agents
- Agents are linked to organizational domains
- Third parties can look up agent → organization mapping

```
Query: "Who owns bot-token-xyz on GitHub?"
Response: {
  "organization": "Acme Corp",
  "domain": "acme.com",
  "registered_by": "it-admin@acme.com",
  "agent_purpose": "code_review_automation"
}
```

| Pros | Cons |
|------|------|
| Doesn't require platform changes | Requires enterprise opt-in |
| Queryable by anyone | Could be gamed without verification |
| Can be built incrementally | Need to establish trust anchor |

### Solution 3: Reverse-Proxy Identity Injection (Gateway Model)

Enterprises route agent API calls through an identity-injecting proxy:

```
Agent → DeepSecure Gateway → GitHub API
                ↓
        Injects verifiable
        attribution headers
```

The gateway adds signed headers that platforms (or observers) can verify:

```http
X-Agent-Attribution: eyJhbGciOiJFZDI1NTE5...
X-Agent-Delegation-Chain: <signed JWT with human binding>
```

| Pros | Cons |
|------|------|
| Works today | Requires platforms to read custom headers |
| Enterprise-controlled | Adds latency to agent calls |
| Auditable | Requires agent traffic routing |

### Solution 4: Platform-Native Attribution APIs

Lobby platforms to expose attribution data:

```
GET /repos/acme/project/events?include=agent_metadata

{
  "events": [{
    "action": "pr_comment",
    "actor": "bot:cursor-ai",
    "actor_metadata": {
      "on_behalf_of": "jane.doe@acme.com",
      "organization": "acme.com"
    }
  }]
}
```

| Pros | Cons |
|------|------|
| First-party data, most reliable | Requires platform buy-in |
| Native integration | Slow to adopt (each platform separately) |
| No enterprise infrastructure needed | Fragmented across platforms |

### Solution 5: Behavioral + Heuristic Attribution

For cases where direct attribution isn't available:

1. **Correlation Analysis**: Match agent activity patterns to known developer patterns
2. **Repository Ownership**: Agent active in repos owned by specific org → likely that org
3. **Time-zone/Activity Patterns**: Correlate with known developer work patterns
4. **Network Analysis**: Which human accounts interact with this agent's outputs?

| Pros | Cons |
|------|------|
| Works without cooperation | Probabilistic, not verifiable |
| Fallback for unattributed agents | Privacy concerns |
| Can be applied retroactively | Can be gamed/spoofed |

### Recommended Multi-Layer Approach

| Layer | Approach | Coverage |
|-------|----------|----------|
| **Ideal** | Platform APIs with attribution | Requires GitHub/GitLab adoption |
| **Enterprise Opt-in** | Public agent registry (ANS) | Enterprises who want attribution |
| **Inference** | Behavioral correlation | Fallback for unattributed agents |

---

## Solution Deep-Dive: Agent Name Service (ANS)

### Overview

The Agent Name Service (ANS) is a DNS-like architecture for AI agents that provides:
- **Discovery**: Finding agents by name or capability
- **Identity verification**: PKI-based certificates
- **Capability advertisement**: What agents can do
- **Protocol-agnostic registry**: Works across A2A, MCP, ACP

ANS is essentially **Solution 2 (Public Agent Registry) with cryptographic guarantees**.

### The Core Innovation: ANSName Structure

ANS embeds attribution directly into the agent's identity:

```
Protocol://AgentID.Capability.Provider.Version.Extension
```

**Examples:**
```
a2a://prReviewer.CodeReview.AcmeCorp.v1.0.enterprise
mcp://sentimentAnalyzer.TextAnalysis.DataCo.v2.1.hipaa
acp://deployBot.CI-CD.StartupXYZ.v1.0.staging
```

**Components:**
- **Protocol**: Which agent communication standard (A2A, MCP, ACP)
- **AgentID**: Unique identifier for this specific agent
- **Capability**: What the agent does (critical for intent signals!)
- **Provider**: The organization (verified by CA)
- **Version**: Semantic versioning for compatibility
- **Extension**: Deployment-specific metadata (e.g., `hipaa`, `enterprise`)

### How ANS Addresses Each Attribution Gap

| Attribution Gap | How ANS Solves It |
|-----------------|-------------------|
| **Who authorized this agent?** | PKI certificate binds agent to organizational identity; RA validates "legal entity of the Requesting Agent" |
| **Which organization?** | `Provider` field in ANSName + certificate's organizational affiliation (e.g., `O=Acme Corp` in X.509) |
| **Is this identity verifiable?** | Yes - CA-signed certificate can be validated by anyone with the trust anchor |
| **What is the agent's purpose?** | `Capability` field + `protocolExtensions` for detailed metadata |
| **What protocol does it use?** | `Protocol` field enables cross-protocol discovery |

### PKI-Bound Identity: The Trust Chain

The ANS registration process creates cryptographic proof of organizational identity:

```
┌─────────────────────────────────────────────────────────────────┐
│                    ANS Registration Flow                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   1. Agent Owner submits registration request                    │
│      └─> Includes: metadata, protocol details, CSR               │
│                                                                  │
│   2. Registration Authority (RA) validates                       │
│      └─> Verifies legal entity of requesting organization       │
│      └─> Checks against registry policies                        │
│      └─> Similar to EV SSL organizational validation             │
│                                                                  │
│   3. RA requests certificate from CA                             │
│      └─> CA issues X.509 certificate                             │
│      └─> Certificate includes: O=AcmeCorp, CN=prReviewer         │
│                                                                  │
│   4. Agent registered in Agent Registry                          │
│      └─> ANSName assigned                                        │
│      └─> Certificate stored                                      │
│      └─> Endpoint published                                      │
│                                                                  │
│   Result: Agent cryptographically bound to verified org          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**The certificate cryptographically binds:**
- Agent's public key → Agent identity
- Agent identity → Organization (Provider)
- Organization → Verified legal entity

This is similar to how **EV SSL certificates** require organizational validation—the Registration Authority verifies that the requesting organization is a real, legally registered entity before issuing the certificate.

### What ANS Adds Beyond a Basic Registry

| Capability | Basic Registry | ANS |
|------------|---------------|-----|
| Agent → Org mapping | ✅ Database lookup | ✅ PKI-verified, offline-verifiable |
| Query API | ✅ REST endpoint | ✅ Formal resolution algorithm with JSON schema |
| Verification | ❌ Trust the database | ✅ Cryptographic certificate chain validation |
| Capability discovery | ❌ Not included | ✅ Capability field + protocolExtensions |
| Protocol support | ❌ Single protocol | ✅ Protocol-agnostic (A2A, MCP, ACP) |
| Lifecycle management | ❌ Manual | ✅ Registration, renewal, revocation |
| Version negotiation | ❌ Not included | ✅ Semantic versioning support |

### The Attribution Flow in Practice

How a platform like reo.dev would use ANS:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Attribution Flow                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   1. Agent makes PR comment on GitHub                            │
│      └─> GitHub logs: actor = "cursor-ai-bot-xyz"                │
│                                                                  │
│   2. Agent includes ANS identity in action metadata              │
│      └─> X-ANS-Name: mcp://prReviewer.CodeReview.AcmeCorp.v1.0   │
│      └─> X-ANS-Signature: <signed proof of identity>             │
│                                                                  │
│   3. reo.dev observes the PR activity                            │
│      └─> Extracts ANS name from metadata                         │
│                                                                  │
│   4. reo.dev queries ANS                                         │
│      └─> Resolve("mcp://prReviewer.CodeReview.AcmeCorp.v1.0")    │
│                                                                  │
│   5. ANS returns verified endpoint + certificate                 │
│      └─> Org: AcmeCorp (verified by CA)                          │
│      └─> Capability: CodeReview                                  │
│      └─> Certificate: CN=prReviewer, O=AcmeCorp, ...             │
│                                                                  │
│   6. reo.dev now knows:                                          │
│      └─> This PR activity is from AcmeCorp                       │
│      └─> It's a code review workflow (intent signal!)            │
│      └─> The identity is cryptographically verified              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Intent Signals from Capability Field

The `Capability` field in ANSName provides **intent signals** that basic bot identification cannot:

| ANSName | Intent Signal |
|---------|--------------|
| `mcp://evaluator.DependencyAudit.AcmeCorp.v1.0` | AcmeCorp is evaluating dependencies → potential buyer for dependency tools |
| `a2a://researcher.SecurityScan.FinTechCo.v2.0` | FinTechCo running security scans → potential buyer for security products |
| `acp://deployer.CI-CD.StartupXYZ.v1.0` | StartupXYZ automating CI/CD → potential buyer for DevOps tools |

### Protocol Adapter Support

ANS supports multiple agent protocols through Protocol Adapters:

| Protocol | Adapter Implementation | Security Features |
|----------|----------------------|-------------------|
| **A2A** (Google) | Native SDK integration | Agent Card verification, ZKP capability attestation |
| **MCP** (Anthropic) | Extension validation | Tool schema verification, resource access control |
| **ACP** (IBM) | Reference implementation | Role-based identity, delegation validation |

---

## Gap Analysis

### What ANS Solves vs. What Remains

| Requirement | ANS Coverage | Gap |
|-------------|--------------|-----|
| Organization identity | ✅ Full - Provider + PKI | None |
| Agent capability/intent | ✅ Full - Capability field + extensions | None |
| **Individual developer** | ⚠️ Partial | ANS focuses on org, not individual human delegation chain |
| **Real-time observability** | ⚠️ Not specified | Platforms must adopt ANS headers |
| **Retroactive attribution** | ❌ No | Only works if agent was ANS-registered |

### The Individual Developer Problem

ANS tells you "AcmeCorp's agent did this" but not "Jane Doe at AcmeCorp authorized this agent."

For platforms like reo.dev, this matters because:
- Individual developers are often the **initial buyer persona**
- Developer → Team → Organization is the sales motion
- "Who specifically should we reach out to?" remains unanswered

### Proposed Extension: Delegation Chain in protocolExtensions

To solve the "which developer authorized this agent" problem, ANS should include delegation metadata:

```json
{
  "protocolExtensions": {
    "delegation": {
      "delegating_principal": {
        "email": "jane.doe@acmecorp.com",
        "employee_id": "EMP-12345",
        "department": "Engineering"
      },
      "delegation_timestamp": "2026-01-30T10:00:00Z",
      "delegation_scope": ["github:pr:comment", "github:pr:review"],
      "workflow_context": "automated_code_review"
    }
  }
}
```

**The extended trust chain:**
```
CA → RA → Organization → IdP → Individual Developer → Agent
```

This would be verified by the organization's IdP during registration:
1. Developer authenticates via corporate SSO
2. IdP attests "Jane Doe is authorized to delegate to this agent"
3. Delegation claim is signed and included in agent's registration
4. Platforms can query ANS to get both org AND individual attribution

---

## Business Opportunity

### The Market Gap

| Need | Current State | With ANS + DeepSecure |
|------|---------------|----------------------|
| Agent → Org attribution | Doesn't exist | PKI-verified, queryable |
| Agent → Developer attribution | Doesn't exist | Delegation chains |
| Intent signals from agents | Lost | Capability field + extensions |
| Compliance/audit | Manual, incomplete | Cryptographic, automated |
| Cross-protocol identity | Fragmented | Protocol-agnostic standard |

### Why Enterprises Will Register Their Agents

#### Incentive 1: Contribution Credit & Visibility

> "Your engineers are 5x more productive with AI agents. Shouldn't your company get credit for that?"

```
Before: "cursor-bot-xyz submitted 500 PRs to kubernetes/kubernetes"
After:  "AcmeCorp (via a2a://prBot.OpenSource.AcmeCorp.v1.0) submitted 500 PRs"
```

#### Incentive 2: Security & Compliance

- PKI certificates for cryptographic audit trails
- Revocation via CRL/OCSP for compromised agents
- Scope control via delegation claims
- SOC 2 / ISO 27001 alignment

#### Incentive 3: Ecosystem Trust & Access

| Agent Type | API Rate Limit | Trust Status |
|------------|---------------|--------------|
| Anonymous bot | 100 calls/hour | Flagged for review |
| API key only | 1,000 calls/hour | Standard access |
| ANS-verified | 10,000 calls/hour | Trusted status |

**The enterprise incentive: Register or get blocked.**

### Why Platforms Want Attribution

#### The Developer Intelligence Business Model

```
Without ANS: Agent Activity → ??? → No buyer intent → No revenue
With ANS:    Agent Activity → ANS Query → Organization → Buyer Intent → Revenue
```

#### Quantifying the Platform Opportunity

| Metric | Without Attribution | With ANS Attribution |
|--------|--------------------|--------------------|
| Signals from agent activity | 0% captured | 100% captured |
| Contact discovery | Developer only | Developer + Organization + Buyer |
| Intent accuracy | N/A | Enhanced (Capability field reveals purpose) |
| Addressable market | Shrinking (as agents grow) | Expanding (agents are force multiplier) |

### Why AI Tool Vendors Will Integrate

#### The Enterprise Sales Unlock

> Enterprise Buyer: "We can't deploy your AI agent without audit trails"
> Vendor: "Our agents come with ANS-verified identity, PKI certificates, and full audit logging"

This becomes a **checkbox feature** for enterprise deals.

#### Differentiation: "Trusted Agent" Positioning

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Trust Spectrum                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Untrusted          Basic Auth           ANS-Verified            │
│  ─────────────────────────────────────────────────────────────  │
│  Anonymous bot      API key              PKI certificate         │
│  No attribution     Self-declared org    CA-verified org         │
│  Rate limited       Standard access      Premium access          │
│  Blocked by WAF     May be flagged       Trusted status          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### The Natural Flywheel (Win-Win-Win-Win)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Attribution Flywheel                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────┐         ┌──────────────┐                     │
│   │  Enterprises │ ──────> │ DeepSecure   │ ──────> ┌────────┐  │
│   │  (Register)  │         │ (RA Gateway) │         │  ANS   │  │
│   └──────────────┘         └──────────────┘         │Registry│  │
│          │                        │                 └────────┘  │
│          │ Get credit             │ Publish                ▲    │
│          │ Compliance             │ Identity               │    │
│          │ Trust                  ▼                        │    │
│          │                 ┌──────────────┐                │    │
│          │                 │  Platforms   │ ───────────────┘    │
│          │                 │  (reo.dev)   │   Query             │
│          │                 └──────────────┘                     │
│          │                        │                             │
│          │                        │ Demand                      │
│          │                        │ more data                   │
│          │                        ▼                             │
│          │                 ┌──────────────┐                     │
│          └───────────────> │  AI Vendors  │ ────────────────┐   │
│            Want verified   │  (Cursor)    │   Integrate     │   │
│            agents          └──────────────┘   for sales     │   │
│                                   │                         │   │
│                                   └─────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### The Four-Way Win

| Party | What They Do | What They Get |
|-------|--------------|---------------|
| **Enterprises** | Register agents via DeepSecure | Credit for contributions, compliance, ecosystem trust |
| **Platforms (reo.dev)** | Query ANS for attribution | Buyer signals, contact discovery, new data products |
| **AI Vendors (Cursor)** | Integrate DeepSecure SDK | Enterprise sales unlock, "trusted agent" positioning |
| **DeepSecure** | Operate RA gateway | Revenue from registration, queries, integrations |

### Compelling Events That Trigger Adoption

| Trigger | Who Moves First | Why |
|---------|-----------------|-----|
| **Compliance mandate** | Enterprises in regulated industries | "Our auditors require agent identity" |
| **Platform policy** | GitHub announces agent registration | "Register or get rate-limited" |
| **Competitive pressure** | Fast-follower enterprises | "Competitors' OSS contributions are visible, ours aren't" |
| **Enterprise sales** | AI vendors | "Our enterprise customers require it" |
| **Security incident** | Industry-wide | "Rogue agent caused breach; attribution now required" |

---

## DeepSecure's Role

### The Positioning

**DeepSecure becomes the enterprise on-ramp to ANS**, solving the "agents not controlled by you" problem by making it easy for enterprises to adopt ANS without building the infrastructure themselves.

### Core Functions

```
┌─────────────────────────────────────────────────────────────────┐
│                 DeepSecure ANS Gateway                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   1. REGISTERS agents with ANS on behalf of enterprises         │
│      └─> Enterprise connects their IdP                          │
│      └─> DeepSecure acts as Registration Authority (RA)         │
│      └─> Generates CSRs, obtains certificates                   │
│                                                                  │
│   2. INJECTS ANS headers into agent API calls                   │
│      └─> Agent calls route through DeepSecure gateway           │
│      └─> Gateway adds: X-ANS-Name, X-ANS-Signature              │
│      └─> No agent code changes required                         │
│                                                                  │
│   3. MANAGES delegation chains                                   │
│      └─> Integrates with enterprise IdP (Okta, Azure AD)        │
│      └─> Links agents to individual developers                  │
│      └─> Maintains delegation metadata in protocolExtensions    │
│                                                                  │
│   4. PROVIDES the RA function for enterprise-controlled agents  │
│      └─> Validates organizational identity                      │
│      └─> Enforces enterprise policies                           │
│      └─> Manages lifecycle (renewal, revocation)                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Architecture Integration

```
┌───────────────────────────────────────────────────────────────────┐
│                    Enterprise + DeepSecure + ANS                   │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│   Enterprise                    DeepSecure              ANS        │
│   ┌─────────┐                  ┌──────────┐         ┌─────────┐   │
│   │ Cursor  │──┐               │          │         │ Agent   │   │
│   │ Agent   │  │               │  Gateway │         │ Registry│   │
│   └─────────┘  │               │    +     │ ──────> │         │   │
│   ┌─────────┐  ├─────────────> │   RA     │         │   CA    │   │
│   │ Copilot │  │               │          │         │         │   │
│   │ Agent   │──┘               └──────────┘         └─────────┘   │
│   └─────────┘                       │                     │       │
│        │                            │                     │       │
│        │                            ▼                     ▼       │
│   ┌─────────┐                  ┌──────────┐         ┌─────────┐   │
│   │ Okta    │ ◄──────────────> │ Delegation│        │ Query   │   │
│   │ IdP     │                  │ Chain Mgr │        │ API     │   │
│   └─────────┘                  └──────────┘         └─────────┘   │
│                                      │                     ▲       │
│                                      │                     │       │
│                                      ▼                     │       │
│                               ┌──────────┐                 │       │
│                               │ Platforms│ ────────────────┘       │
│                               │ (reo.dev)│                         │
│                               └──────────┘                         │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### Competitive Advantage

| Capability | Build In-House | Use DeepSecure |
|------------|---------------|----------------|
| PKI infrastructure | 3-6 months | Day 1 |
| RA/CA integration | Complex | Managed |
| IdP integration | Per-provider work | Pre-built (Okta, Azure AD, etc.) |
| Delegation chain support | Custom development | Standard feature |
| Header injection | Modify each agent | Gateway handles it |
| Compliance reporting | Build from scratch | Dashboard included |

### Revenue Model

#### Stream 1: Enterprise Registration Fees

| Tier | Agents | Price/Year | Features |
|------|--------|------------|----------|
| **Startup** | 10 | Free | Basic ANS registration |
| **Team** | 100 | $5,000 | + Delegation chains, audit logs |
| **Enterprise** | 1,000+ | $50,000+ | + SSO integration, custom CA, SLA |

#### Stream 2: Platform Query Fees

| Model | Price | Use Case |
|-------|-------|----------|
| Per-query | $0.001/query | Low-volume platforms |
| Subscription | $10,000/month | Developer intelligence platforms |
| Enterprise API | Custom | Deep integration, real-time feeds |

#### Stream 3: AI Vendor Integration

| Model | Price | Value |
|-------|-------|-------|
| SDK License | Free | Market adoption |
| Verified Partner Badge | $25,000/year | "ANS-Verified" marketing |
| White-label | Custom | Enterprise customers self-host |

#### Stream 4: Premium Data Products

| Product | Price | Buyer |
|---------|-------|-------|
| Agent Activity Analytics | $50,000/year | AI tool vendors |
| Technology Adoption Trends | $100,000/year | Analyst firms |
| Intent Signal Feeds | Custom | Sales intelligence platforms |

---

## Implementation Roadmap

### Phase 1: ANS Foundation (Months 1-3)
- Implement ANS-compatible registry
- PKI infrastructure (CA/RA) with certificate management
- ANSName resolution API with JSON schema validation
- Protocol adapters for MCP (initial focus)
- Integration with DeepSecure gateway

### Phase 2: Enterprise Adoption (Months 4-6)
- SSO/SCIM integration (Okta, Azure AD, Google Workspace)
- Delegation chain support (protocolExtensions)
- Audit log export for compliance (SOC 2 format)
- Admin dashboard for agent lifecycle management
- First 10 enterprise customers

### Phase 3: Platform Integration (Months 7-9)
- Query API for platforms (reo.dev POC)
- Webhook feeds for real-time attribution
- Bulk lookup API for historical analysis
- Public agent lookup (WHOIS-style)
- Partnership with 2-3 developer intelligence platforms

### Phase 4: Ecosystem (Months 10-12)
- A2A and ACP protocol adapter support
- AI vendor SDK partnerships (Cursor, Windsurf, etc.)
- "ANS-Verified" badge program
- Developer platform discussions (GitHub, GitLab)
- Standards body engagement (OWASP, CNCF)

---

## Conclusion

### The Natural Incentive Alignment

The Public Agent Registry succeeds because **every party benefits from the same action**:

| Party | Action | Benefit |
|-------|--------|---------|
| Enterprise | Register agents | Credit, compliance, access |
| Platform | Query registry | Buyer signals, revenue |
| AI Vendor | Integrate SDK | Enterprise sales, trust |
| Developer Platform | Require registration | Security, accountability |
| DeepSecure | Operate infrastructure | Revenue from all parties |

This is not a "convince them to pay" business model. It's a **"the market naturally wants this"** opportunity where DeepSecure becomes critical infrastructure for the AI agent economy.

### Why Now

1. **Agent Explosion**: Cursor, Copilot, Claude, Devin — agent adoption is accelerating
2. **Enterprise AI Budgets**: Companies are investing in AI tooling at unprecedented scale
3. **Compliance Awareness**: AI governance is becoming a board-level concern
4. **Platform Anxiety**: GitHub/GitLab seeing agent traffic spike, need solutions
5. **No Incumbent**: WHOIS for agents doesn't exist yet

### The Bottom Line

**The question isn't whether agent attribution will happen—it's who will own the standard.**

DeepSecure is positioned to be that standard by serving as the enterprise-friendly on-ramp to ANS, making verifiable agent identity as easy to adopt as SSO.

---

## References

1. Agent Name Service (ANS) Specification - Huang et al.
2. A2A Protocol - Google
3. Model Context Protocol (MCP) - Anthropic
4. Agent Communication Protocol (ACP) - IBM
5. X.509 Certificate Standard - RFC 5280
6. OAuth 2.0 - RFC 6749

---

## Appendix A: ANS JSON Schemas

### AgentRegistrationRequest Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AgentRegistrationRequest",
  "type": "object",
  "properties": {
    "protocol": {
      "type": "string",
      "enum": ["a2a", "mcp", "acp"]
    },
    "agentID": {
      "type": "string"
    },
    "agentCapability": {
      "type": "string"
    },
    "provider": {
      "type": "string"
    },
    "version": {
      "type": "string",
      "pattern": "^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)$"
    },
    "certificate": {
      "type": "object",
      "properties": {
        "subject": { "type": "string" },
        "issuer": { "type": "string" },
        "pem": { "type": "string" }
      }
    },
    "protocolExtensions": {
      "type": "object"
    }
  },
  "required": ["protocol", "agentID", "agentCapability", "provider", "version", "certificate"]
}
```

### Delegation Chain Extension Schema

```json
{
  "protocolExtensions": {
    "delegation": {
      "delegating_principal": {
        "email": "jane.doe@acmecorp.com",
        "employee_id": "EMP-12345",
        "department": "Engineering"
      },
      "delegation_timestamp": "2026-01-30T10:00:00Z",
      "delegation_scope": ["github:pr:comment", "github:pr:review"],
      "workflow_context": "automated_code_review",
      "idp_attestation": {
        "issuer": "https://acmecorp.okta.com",
        "signature": "base64-encoded-signature"
      }
    }
  }
}
```

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **ANS** | Agent Name Service - DNS-like infrastructure for AI agents |
| **ANSName** | Structured identifier: `Protocol://AgentID.Capability.Provider.Version.Extension` |
| **CA** | Certificate Authority - Issues X.509 certificates |
| **RA** | Registration Authority - Validates agent registration requests |
| **PKI** | Public Key Infrastructure - Cryptographic identity framework |
| **A2A** | Agent-to-Agent Protocol (Google) |
| **MCP** | Model Context Protocol (Anthropic) |
| **ACP** | Agent Communication Protocol (IBM) |
| **Delegation Chain** | The trust path from CA to human authorizing an agent |
| **EV SSL** | Extended Validation SSL - Highest level of certificate validation |
