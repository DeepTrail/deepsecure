# DeepSecure: Open Source vs. Enterprise Split Strategy

> **Design Document** | Version 1.0 | January 2026
>
> Strategic analysis for splitting DeepSecure into an open-source core and enterprise offering

---

## Executive Summary

This document outlines a comprehensive strategy for splitting the DeepSecure codebase into an **open-source community edition** and an **enterprise/closed-source offering**. The split follows a **developer-first open source core** model (similar to HashiCorp, MongoDB, or Elastic): provide enough value in open source to drive adoption and community, while reserving governance, scale, and compliance features for enterprise customers.

### Core Principle

| Layer | Target | Value Proposition |
|-------|--------|-------------------|
| **Open Source** | Individual developers, small teams | Developer productivity - replace static secrets |
| **Enterprise** | Organizations, regulated industries | Organizational governance - control, audit, compliance |

---

## Table of Contents

1. [Open Source Repository (Community Edition)](#open-source-repository-community-edition)
2. [Enterprise Repository (Closed Source)](#enterprise-repository-closed-source)
3. [Recommended Repository Structure](#recommended-repository-structure)
4. [Migration Path](#migration-path)
5. [Pricing Tier Alignment](#pricing-tier-alignment)
6. [Implementation Checklist](#implementation-checklist)

---

## Open Source Repository (Community Edition)

### 1. CLI/SDK Core (`deepsecure/`)

| Component | Path | Rationale |
|-----------|------|-----------|
| **Public Client API** | `deepsecure/client.py` | Core SDK interface - drives adoption |
| **Commands (Basic)** | `deepsecure/commands/` | CLI tooling for developers |
| **Basic Identity Manager** | `deepsecure/_core/identity_manager.py` | Local keyring-based identity |
| **Crypto/Key Manager** | `deepsecure/_core/crypto/` | Ed25519 key generation/signing |
| **Keyring Provider** | `deepsecure/_core/identity_provider.py` (KeyringIdentityProvider only) | Local development identity |
| **Basic Vault Client** | `deepsecure/_core/vault_client.py` | Credential issuance/verification |
| **Configuration** | `deepsecure/_core/config.py` | Environment variable handling |
| **Framework Integrations** | `deepsecure/integrations/` | LangChain, CrewAI, OpenAI, Anthropic |
| **Types & Exceptions** | `deepsecure/types.py`, `deepsecure/exceptions.py` | Core type definitions |
| **Utilities** | `deepsecure/utils.py` | Shared utilities |

### 2. Basic Control Plane (Self-Hosted)

| Component | Path | Rationale |
|-----------|------|-----------|
| **Agent CRUD** | `deeptrail-control/app/api/v1/endpoints/agents.py` | Basic agent management |
| **Auth (Challenge-Response)** | `deeptrail-control/app/api/v1/endpoints/auth.py` | Ed25519 authentication |
| **Basic Vault** | `deeptrail-control/app/api/v1/endpoints/vault.py` | Secret storage (single-node) |
| **Basic Policies** | `deeptrail-control/app/api/v1/endpoints/policies.py` | Simple CRUD policies |
| **Database Models** | `deeptrail-control/app/models/` | PostgreSQL schema |
| **CRUD Operations** | `deeptrail-control/app/crud/` | Database access layer |
| **Core Configuration** | `deeptrail-control/app/core/config.py` | Service configuration |
| **Database Session** | `deeptrail-control/app/db/` | Database connectivity |

### 3. Basic Gateway (Self-Hosted)

| Component | Path | Rationale |
|-----------|------|-----------|
| **Proxy Core** | `deeptrail-gateway/app/proxy.py` | Basic request proxying |
| **JWT Validation** | `deeptrail-gateway/app/middleware/jwt_validation.py` | Token verification |
| **Secret Injection (Basic)** | `deeptrail-gateway/app/middleware/secret_injection.py` | Header-based injection |
| **Request Logging** | `deeptrail-gateway/app/core/request_logger.py` | Audit trail (local) |
| **HTTP Client** | `deeptrail-gateway/app/core/http_client.py` | Outbound requests |
| **Proxy Config** | `deeptrail-gateway/app/core/proxy_config.py` | Routing configuration |

### 4. Documentation & Examples

| Component | Rationale |
|-----------|-----------|
| All examples in `examples/` | Drives adoption and demonstrates value |
| Basic setup guides | Get developers started quickly |
| CLI reference docs (`docs/cli_reference.md`) | Essential for usability |
| API documentation (`docs/openapi.yaml`) | Developer experience |
| SDK reference (`docs/sdk-reference.md`) | SDK usage documentation |
| Configuration guide (`docs/configuration.md`) | Setup instructions |

### 5. Tests (Basic Coverage)

| Component | Path | Rationale |
|-----------|------|-----------|
| **SDK Tests** | `tests/sdk/` | SDK functionality validation |
| **Command Tests** | `tests/commands/` | CLI command testing |
| **Core Tests** | `tests/_core/` | Core module unit tests |
| **Example Validation** | `tests/test_examples.py` | Ensure examples work |

### Open Source Value Proposition

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    OPEN SOURCE: INDIVIDUAL DEVELOPER VALUE                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ✓ Replace static API keys with dynamic credentials                        │
│  ✓ Ed25519 identity for AI agents                                          │
│  ✓ Local keyring-based key storage                                         │
│  ✓ Challenge-response authentication                                       │
│  ✓ Basic credential scoping and TTL                                        │
│  ✓ Framework integrations (LangChain, CrewAI, OpenAI, Anthropic)           │
│  ✓ Self-hosted control plane + gateway                                     │
│  ✓ Local audit logging                                                     │
│  ✓ Docker Compose deployment                                               │
│                                                                              │
│  Target: Individual developers, small teams, POCs, learning                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Enterprise Repository (Closed Source)

### 1. Virtual MCP Server (The Core Enterprise Feature)

Based on the design docs, this is the **flagship enterprise capability**:

| Component | Description | Why Enterprise |
|-----------|-------------|----------------|
| **MCP Protocol Handler** | Full MCP server implementation | Complex, high-value |
| **Tool Aggregation** | Combine tools from multiple backends | N×M connection value |
| **Namespace Prefixing** | `notion.search_pages`, `slack.send` | Enterprise-scale tooling |
| **Backend Pool Manager** | Connection management for 47+ MCP servers | Scale feature |
| **Session Management (Redis)** | Distributed session state | Production scalability |
| **Capability Filtering** | Agent sees only delegated tools | Core governance |

### 2. Advanced Identity & Bootstrap

| Component | Current Path | Why Enterprise |
|-----------|--------------|----------------|
| **Kubernetes Provider** | `identity_provider.py` (KubernetesIdentityProvider) | Enterprise deployment |
| **AWS Provider** | `identity_provider.py` (AwsIdentityProvider) | Enterprise cloud |
| **Azure Provider** | `identity_provider.py` (AzureIdentityProvider) | Enterprise cloud |
| **Docker Provider** | `identity_provider.py` (DockerIdentityProvider) | Container deployments |
| **Environment Detector** | `environment_detector.py` | Intelligent bootstrap |
| **Bootstrap Endpoints** | `deeptrail-control/app/api/v1/endpoints/bootstrap.py` | Platform-native identity |
| **Attestation Policies** | `attestation_policies.py` | Workload identity verification |
| **Attestation Service** | `attestation_service.py` | Attestation validation |
| **Bootstrap Service** | `bootstrap_service.py` | Bootstrap orchestration |

### 3. Delegation System (Macaroons)

| Component | Current Path | Why Enterprise |
|-----------|--------------|----------------|
| **Macaroon Service** | `deeptrail-control/app/services/macaroon_service.py` | Cryptographic delegation |
| **Delegation Endpoints** | `deeptrail-control/app/api/v1/endpoints/delegation.py` | User→Agent delegation |
| **Caveat System** | `deepsecure/_core/delegation.py` | Attenuable permissions |
| **Chain Validation** | Multi-level delegation (A→B→C) | Enterprise workflows |
| **Monotonic Attenuation** | Permissions can only narrow | Security guarantee |

### 4. Advanced Policy Engine

| Component | Description | Why Enterprise |
|-----------|-------------|----------------|
| **RBAC Engine** | Role-based access control | Enterprise governance |
| **ABAC Engine** | Attribute-based policies | Fine-grained control |
| **Policy Fetching from Control** | Real-time policy sync | Central governance |
| **Constraint Evaluation** | `max_actions_per_day`, time windows | Usage limits |
| **Dynamic Policy Reload** | Hot-reload without restart | Zero-downtime ops |
| **Advanced Security Validators** | `security_validators.py` | Enhanced validation |

### 5. Enterprise IdP Integration

| Component | Description | Why Enterprise |
|-----------|-------------|----------------|
| **Okta Federation** | SSO integration | Enterprise SSO |
| **Azure AD Integration** | Microsoft identity | Enterprise SSO |
| **SAML/OIDC Support** | Standard protocols | Enterprise requirements |
| **Organization Registry** | Multi-tenant org config | SaaS capability |
| **Group→Role Mapping** | IdP groups to DeepTrail roles | Enterprise governance |
| **User Session Management** | Browser-based user sessions | Web console |

### 6. Governance & Compliance

| Component | Description | Why Enterprise |
|-----------|-------------|----------------|
| **Unified Audit Trail** | Centralized, queryable logs | SOC2/HIPAA |
| **Audit API** | Query: "What did agent X do?" | Compliance reporting |
| **Audit Client** | `audit_client.py` | Audit log access |
| **PII Filtering** | Result sanitization | Data protection |
| **Anomaly Detection** | Unusual access patterns | Security monitoring |
| **Circuit Breaker** | Emergency agent suspension | Incident response |
| **Export for SIEM** | Log shipping to Splunk/etc | Enterprise security |
| **Risk Scoring** | `risk_client.py` | Risk assessment |

### 7. Split-Key Architecture

| Component | Current Path | Why Enterprise |
|-----------|--------------|----------------|
| **Share Storage** | `deeptrail-gateway/app/core/share_storage.py` | Redis-backed secrets |
| **JIT Reassembly** | `deeptrail-gateway/app/core/jit_reassembly.py` | Secret never at rest |
| **Coordinated Deletion** | Cross-service secret deletion | Security feature |
| **Security Filters** | `security_filters.py` | Advanced filtering |

### 8. Production Scalability

| Component | Description | Why Enterprise |
|-----------|-------------|----------------|
| **Redis Session Store** | Distributed state | Horizontal scaling |
| **Connection Pooling** | Backend connection management | Performance |
| **Rate Limiting** | Per-agent, per-resource limits | Protection |
| **Health Monitoring** | Gateway/Control health | Operations |
| **Metrics/Observability** | Prometheus, OpenTelemetry | Enterprise ops |
| **Retry Utilities** | `retry_utils.py` | Resilience |

### 9. Advanced CLI Features

| Component | Current Path | Why Enterprise |
|-----------|--------------|----------------|
| **Deployment Commands** | `commands/deploy.py` | Enterprise deployment |
| **Hardening Commands** | `commands/harden.py` | Security hardening |
| **Sandbox Commands** | `commands/sandbox.py` | Sandboxed execution |
| **Scorecard Commands** | `commands/scorecard.py` | Security scoring |
| **Inventory Commands** | `commands/inventory.py` | Asset inventory |
| **Risk Commands** | `commands/risk.py` | Risk assessment |
| **Audit Commands** | `commands/audit.py` | Audit log access |

### Enterprise Value Proposition

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE: ORGANIZATION-WIDE VALUE                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Virtual MCP Server (Core Differentiator):                                  │
│  ✓ Single gateway connection for agents → 47+ backends                     │
│  ✓ Tool filtering by delegation (4 tools vs 37)                            │
│  ✓ Namespace resolution (notion.search vs slack.search)                    │
│  ✓ Credential injection (agents never see backend tokens)                  │
│                                                                              │
│  Delegation & Governance:                                                   │
│  ✓ User-to-agent delegation with macaroons                                 │
│  ✓ Monotonic attenuation (permissions can only narrow)                     │
│  ✓ Time-bounded access (TTL, working hours)                                │
│  ✓ Constraint enforcement (max actions/day)                                │
│                                                                              │
│  Enterprise Identity:                                                       │
│  ✓ Okta/Azure AD SSO integration                                           │
│  ✓ Kubernetes/AWS/Azure workload identity                                  │
│  ✓ Automatic revocation on offboarding                                     │
│  ✓ Organization registry (multi-tenant)                                    │
│                                                                              │
│  Compliance & Audit:                                                        │
│  ✓ Unified audit trail ("agent X on behalf of Sarah")                      │
│  ✓ SOC2/HIPAA compliance reports                                           │
│  ✓ PII filtering in responses                                              │
│  ✓ Circuit breaker (instant agent suspension)                              │
│                                                                              │
│  Target: Enterprises, regulated industries, security-conscious teams       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Recommended Repository Structure

### Open Source Repository: `deepsecure`

```
deepsecure/                           # Open source CLI/SDK
├── deepsecure/
│   ├── __init__.py
│   ├── __main__.py
│   ├── main.py
│   ├── client.py                     # Public SDK client
│   ├── auth.py                       # Basic auth utilities
│   ├── vault.py                      # Vault utilities
│   ├── policy.py                     # Basic policy utilities
│   ├── types.py                      # Type definitions
│   ├── exceptions.py                 # Exception classes
│   ├── utils.py                      # Shared utilities
│   ├── _core/
│   │   ├── __init__.py
│   │   ├── base_client.py            # HTTP client
│   │   ├── vault_client.py           # Basic vault operations
│   │   ├── agent_client.py           # Agent CRUD
│   │   ├── policy_client.py          # Basic policy operations
│   │   ├── config.py                 # Configuration
│   │   ├── exceptions.py             # Core exceptions
│   │   ├── schemas.py                # Data schemas
│   │   ├── crypto/
│   │   │   ├── __init__.py
│   │   │   └── key_manager.py        # Ed25519 operations
│   │   ├── identity_manager.py       # Basic identity management
│   │   └── identity_provider.py      # KeyringIdentityProvider ONLY
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── agent.py                  # Agent commands
│   │   ├── auth.py                   # Auth commands
│   │   ├── configure.py              # Configuration commands
│   │   ├── gateway.py                # Basic gateway commands
│   │   ├── policy.py                 # Basic policy commands
│   │   ├── vault.py                  # Vault commands
│   │   └── ide.py                    # IDE integration
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── base.py                   # Base integration class
│   │   ├── gateway.py                # Gateway client
│   │   ├── openai.py                 # OpenAI integration
│   │   ├── anthropic.py              # Anthropic integration
│   │   ├── langchain.py              # LangChain integration
│   │   └── crewai.py                 # CrewAI integration
│   └── resources/
│       ├── agent.py                  # Agent resource
│       ├── agents.py                 # Agents collection
│       └── credential.py             # Credential resource
├── deeptrail-control-oss/            # Basic self-hosted control plane
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py               # Dependencies
│   │   │   └── v1/
│   │   │       ├── api.py            # API router
│   │   │       └── endpoints/
│   │   │           ├── agents.py     # Agent CRUD
│   │   │           ├── auth.py       # Authentication
│   │   │           ├── vault.py      # Basic vault (no split-key)
│   │   │           └── policies.py   # Basic CRUD policies
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py             # Configuration
│   │   │   ├── security.py           # Basic security
│   │   │   └── exceptions.py         # Exceptions
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py              # Agent model
│   │   │   ├── credential.py         # Credential model
│   │   │   ├── nonce.py              # Nonce model
│   │   │   └── policy.py             # Policy model
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py              # Agent schemas
│   │   │   ├── auth.py               # Auth schemas
│   │   │   ├── credential.py         # Credential schemas
│   │   │   ├── policy.py             # Policy schemas
│   │   │   └── token.py              # Token schemas
│   │   ├── crud/
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # Base CRUD
│   │   │   ├── crud_agent.py         # Agent CRUD
│   │   │   ├── crud_credential.py    # Credential CRUD
│   │   │   ├── crud_nonce.py         # Nonce CRUD
│   │   │   └── crud_policy.py        # Policy CRUD
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── base.py               # Database base
│   │       └── session.py            # Session management
│   ├── alembic/                      # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── deeptrail-gateway-oss/            # Basic gateway
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── proxy.py                  # Basic proxy
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── http_client.py        # HTTP client
│   │   │   ├── proxy_config.py       # Proxy configuration
│   │   │   ├── request_logger.py     # Request logging
│   │   │   └── request_validator.py  # Request validation
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── jwt_validation.py     # JWT validation
│   │       ├── logging.py            # Logging middleware
│   │       ├── secret_injection.py   # Basic injection
│   │       └── security.py           # Basic security
│   ├── Dockerfile
│   └── requirements.txt
├── examples/                         # All examples
│   ├── README.md
│   ├── 01_create_agent_and_issue_credential.py
│   ├── 02_sdk_secret_fetch.py
│   ├── 03_crewai_secure_tools.py
│   ├── 04_crewai_secure_tools_without_finegrain_control.py
│   ├── 05_langchain_secure_tools.py
│   ├── 06_langchain_secure_tools_without_finegrain_control.py
│   ├── 07_multi_agent_communication.py
│   ├── 08_gateway_secret_injection_demo.py
│   ├── 13_quickstart_openai_list_models.py
│   └── 14_quickstart_openai_policy_enforcement.py
├── docs/
│   ├── README.md
│   ├── cli_reference.md
│   ├── configuration.md
│   ├── sdk-reference.md
│   ├── openapi.yaml
│   └── guides/
│       └── getting-started.md
├── tests/
│   ├── conftest.py
│   ├── _core/
│   ├── commands/
│   ├── sdk/
│   └── test_examples.py
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   ├── test.txt
│   └── frameworks.txt
├── scripts/
│   ├── setup_dev.sh
│   └── build_package.sh
├── docker-compose.yml                # Self-hosted deployment
├── pyproject.toml
├── pytest.ini
├── Makefile
├── LICENSE                           # Apache 2.0 or similar
├── README.md
├── CONTRIBUTING.md
└── CHANGELOG.md
```

### Enterprise Repository: `deepsecure-enterprise`

```
deepsecure-enterprise/
├── deeptrail-control/                # Full control plane
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/v1/endpoints/
│   │   │   ├── agents.py             # (extends OSS)
│   │   │   ├── auth.py               # (extends OSS)
│   │   │   ├── vault.py              # (extends OSS with split-key)
│   │   │   ├── policies.py           # (extends OSS with RBAC/ABAC)
│   │   │   ├── bootstrap.py          # Platform identity bootstrap
│   │   │   ├── delegation.py         # Macaroon delegation
│   │   │   ├── attestation_policies.py
│   │   │   └── internal.py           # Gateway coordination
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── macaroon_service.py   # Macaroon minting
│   │   │   ├── attestation_service.py
│   │   │   └── bootstrap_service.py
│   │   ├── core/
│   │   │   ├── audit_logger.py       # Advanced audit logging
│   │   │   ├── retry_utils.py        # Retry utilities
│   │   │   └── security_validators.py
│   │   ├── models/
│   │   │   └── attestation_policy.py
│   │   ├── schemas/
│   │   │   ├── attestation_policy.py
│   │   │   ├── bootstrap.py
│   │   │   ├── delegation.py
│   │   │   └── nonce.py
│   │   └── crud/
│   │       ├── crud_attestation_policy.py
│   │       └── crud_secret.py        # Split-key secrets
│   └── tests/
├── deeptrail-gateway/                # Full gateway
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── proxy.py                  # (extends OSS)
│   │   ├── core/
│   │   │   ├── jit_reassembly.py     # Split-key reassembly
│   │   │   ├── share_storage.py      # Redis shares
│   │   │   ├── security_filters.py   # Advanced security
│   │   │   └── request_sanitizer.py  # Request sanitization
│   │   └── middleware/
│   │       ├── policy_enforcement.py # RBAC/ABAC enforcement
│   │       └── sanitization.py       # PII filtering
│   └── tests/
├── virtual-mcp-server/               # The flagship feature
│   ├── __init__.py
│   ├── server.py                     # MCP server implementation
│   ├── protocol/
│   │   ├── __init__.py
│   │   ├── handler.py                # MCP protocol handler
│   │   ├── messages.py               # MCP message types
│   │   └── transport.py              # Transport layer
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── aggregator.py             # Tool aggregation
│   │   ├── namespace_manager.py      # Namespace prefixing
│   │   └── filter.py                 # Permission-based filtering
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── pool_manager.py           # Backend connection pool
│   │   ├── notion.py                 # Notion MCP adapter
│   │   ├── slack.py                  # Slack MCP adapter
│   │   └── hubspot.py                # HubSpot MCP adapter
│   ├── sessions/
│   │   ├── __init__.py
│   │   ├── manager.py                # Session management
│   │   ├── redis_store.py            # Redis session store
│   │   └── user_session.py           # User session handling
│   └── tests/
├── enterprise-identity/              # Cloud identity providers
│   ├── __init__.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── kubernetes_provider.py
│   │   ├── aws_provider.py
│   │   ├── azure_provider.py
│   │   └── docker_provider.py
│   ├── idp/
│   │   ├── __init__.py
│   │   ├── okta_integration.py
│   │   ├── azure_ad_integration.py
│   │   └── saml_handler.py
│   ├── environment_detector.py
│   └── tests/
├── enterprise-sdk/                   # Enterprise SDK extensions
│   ├── __init__.py
│   ├── delegation.py                 # Full delegation support
│   ├── audit_client.py               # Audit log access
│   ├── risk_client.py                # Risk scoring
│   ├── deployment_client.py          # Deployment management
│   ├── hardening_manager.py          # Security hardening
│   ├── sandbox_manager.py            # Sandbox execution
│   └── scanner.py                    # Security scanning
├── enterprise-commands/              # Enterprise CLI commands
│   ├── __init__.py
│   ├── audit.py                      # Audit commands
│   ├── deploy.py                     # Deployment commands
│   ├── harden.py                     # Hardening commands
│   ├── inventory.py                  # Inventory commands
│   ├── risk.py                       # Risk commands
│   ├── sandbox.py                    # Sandbox commands
│   └── scorecard.py                  # Scorecard commands
├── governance/                       # Enterprise governance
│   ├── __init__.py
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── audit_service.py          # Audit trail management
│   │   ├── compliance_reporter.py    # SOC2/HIPAA reports
│   │   └── siem_exporter.py          # SIEM integration
│   ├── security/
│   │   ├── __init__.py
│   │   ├── anomaly_detector.py       # Unusual access patterns
│   │   ├── circuit_breaker.py        # Emergency suspension
│   │   └── pii_filter.py             # PII detection/masking
│   └── policy/
│       ├── __init__.py
│       ├── rbac_engine.py            # Role-based access
│       ├── abac_engine.py            # Attribute-based access
│       └── constraint_evaluator.py   # Constraint enforcement
├── console/                          # Web console (optional)
│   ├── frontend/                     # React/Vue frontend
│   └── api/                          # Console backend API
├── helm-charts/                      # Enterprise deployment
│   └── deepsecure-enterprise/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
├── terraform/                        # Infrastructure as Code
│   ├── aws/
│   ├── azure/
│   └── gcp/
├── docs/
│   ├── enterprise-setup.md
│   ├── idp-integration.md
│   ├── compliance-guide.md
│   └── architecture.md
├── tests/
│   ├── integration/
│   └── e2e/
├── docker-compose.yml
├── pyproject.toml
├── LICENSE                           # Proprietary/Commercial
└── README.md
```

---

## Migration Path

### Files to Move to Enterprise Repo

#### From `deepsecure/_core/`:

| File | Action | Notes |
|------|--------|-------|
| `identity_provider.py` | **Split** | Keep only `KeyringIdentityProvider` in OSS |
| `environment_detector.py` | **Move** | Enterprise only |
| `delegation.py` | **Move** | Enterprise only |
| `audit_client.py` | **Move** | Enterprise only |
| `audit_logger.py` | **Move** | Enterprise only |
| `risk_client.py` | **Move** | Enterprise only |
| `deployment_client.py` | **Move** | Enterprise only |
| `hardening_manager.py` | **Move** | Enterprise only |
| `sandbox_manager.py` | **Move** | Enterprise only |
| `scanner.py` | **Move** | Enterprise only |

#### From `deepsecure/commands/`:

| File | Action | Notes |
|------|--------|-------|
| `audit.py` | **Move** | Enterprise only |
| `deploy.py` | **Move** | Enterprise only |
| `harden.py` | **Move** | Enterprise only |
| `inventory.py` | **Move** | Enterprise only |
| `risk.py` | **Move** | Enterprise only |
| `sandbox.py` | **Move** | Enterprise only |
| `scorecard.py` | **Move** | Enterprise only |
| `scan.py` | **Move** | Enterprise only |

#### From `deeptrail-control/`:

| File | Action | Notes |
|------|--------|-------|
| `app/api/v1/endpoints/bootstrap.py` | **Move** | Enterprise only |
| `app/api/v1/endpoints/delegation.py` | **Move** | Enterprise only |
| `app/api/v1/endpoints/attestation_policies.py` | **Move** | Enterprise only |
| `app/api/v1/endpoints/internal.py` | **Move** | Enterprise only |
| `app/services/macaroon_service.py` | **Move** | Enterprise only |
| `app/services/attestation_service.py` | **Move** | Enterprise only |
| `app/services/bootstrap_service.py` | **Move** | Enterprise only |
| `app/core/security_validators.py` | **Move** | Enterprise only |
| `app/core/retry_utils.py` | **Move** | Enterprise only |
| `app/models/attestation_policy.py` | **Move** | Enterprise only |
| `app/schemas/attestation_policy.py` | **Move** | Enterprise only |
| `app/schemas/bootstrap.py` | **Move** | Enterprise only |
| `app/schemas/delegation.py` | **Move** | Enterprise only |
| `app/crud/crud_attestation_policy.py` | **Move** | Enterprise only |
| `app/crud/crud_secret.py` | **Move** | Split-key secrets are enterprise |

#### From `deeptrail-gateway/`:

| File | Action | Notes |
|------|--------|-------|
| `app/core/jit_reassembly.py` | **Move** | Enterprise only |
| `app/core/share_storage.py` | **Move** | Enterprise only |
| `app/core/security_filters.py` | **Move** | Enterprise only |
| `app/core/request_sanitizer.py` | **Move** | Enterprise only |
| `app/middleware/policy_enforcement.py` | **Split** | Keep basic version in OSS; advanced RBAC/ABAC in enterprise |
| `app/middleware/sanitization.py` | **Move** | Enterprise only |

#### From `examples/`:

| File | Action | Notes |
|------|--------|-------|
| `09_langchain_delegation_workflow.py` | **Move** | Enterprise delegation feature |
| `10_crewai_delegation_workflow.py` | **Move** | Enterprise delegation feature |
| `11_advanced_delegation_patterns.py` | **Move** | Enterprise delegation feature |
| `12_platform_expansion_bootstrap.py` | **Move** | Enterprise bootstrap feature |

---

## Pricing Tier Alignment

| Tier | Features | Target | Pricing Model |
|------|----------|--------|---------------|
| **Open Source (Free)** | CLI/SDK, basic auth, local keyring, self-hosted, basic gateway | Individual devs, small teams, POCs | Free forever |
| **Team ($)** | + Enterprise identity (K8s, AWS, Azure), + Basic delegation | Startups, growing teams | Per-seat/month |
| **Enterprise ($$)** | + Virtual MCP Server, + Full delegation/macaroons, + Audit/compliance | Mid-market, regulated | Annual contract |
| **Enterprise Plus ($$$)** | + Multi-tenant, + Advanced anomaly detection, + SLA/Support, + SSO | Large enterprises | Custom pricing |

### Feature Matrix

| Feature | Open Source | Team | Enterprise | Enterprise Plus |
|---------|:-----------:|:----:|:----------:|:---------------:|
| CLI/SDK | ✓ | ✓ | ✓ | ✓ |
| Ed25519 Identity | ✓ | ✓ | ✓ | ✓ |
| Local Keyring | ✓ | ✓ | ✓ | ✓ |
| Basic Auth | ✓ | ✓ | ✓ | ✓ |
| Framework Integrations | ✓ | ✓ | ✓ | ✓ |
| Self-Hosted Control | ✓ | ✓ | ✓ | ✓ |
| Self-Hosted Gateway | ✓ | ✓ | ✓ | ✓ |
| Kubernetes Identity | | ✓ | ✓ | ✓ |
| AWS Identity | | ✓ | ✓ | ✓ |
| Azure Identity | | ✓ | ✓ | ✓ |
| Basic Delegation | | ✓ | ✓ | ✓ |
| Virtual MCP Server | | | ✓ | ✓ |
| Full Macaroon Delegation | | | ✓ | ✓ |
| Tool Aggregation | | | ✓ | ✓ |
| Unified Audit Trail | | | ✓ | ✓ |
| RBAC/ABAC Policies | | | ✓ | ✓ |
| Split-Key Secrets | | | ✓ | ✓ |
| Enterprise IdP (Okta/AAD) | | | | ✓ |
| Multi-Tenant | | | | ✓ |
| Anomaly Detection | | | | ✓ |
| PII Filtering | | | | ✓ |
| Circuit Breaker | | | | ✓ |
| SIEM Integration | | | | ✓ |
| SLA Support | | | | ✓ |

---

## Implementation Checklist

### Phase 1: Repository Setup

- [ ] Create new `deepsecure` repository for open source
- [ ] Create new `deepsecure-enterprise` repository (private)
- [ ] Set up CI/CD for both repositories
- [ ] Configure dependency management between repos

### Phase 2: Code Extraction (Open Source)

- [ ] Extract core CLI/SDK to open source repo
- [ ] Extract basic control plane endpoints
- [ ] Extract basic gateway functionality
- [ ] Extract all examples (basic)
- [ ] Extract public documentation
- [ ] Remove enterprise features from OSS codebase

### Phase 3: Code Migration (Enterprise)

- [ ] Move enterprise identity providers
- [ ] Move delegation/macaroon system
- [ ] Move advanced policy engine
- [ ] Move split-key architecture
- [ ] Move governance components
- [ ] Move enterprise CLI commands
- [ ] Move enterprise examples

### Phase 4: Integration Layer

- [ ] Create extension point system in OSS
- [ ] Implement enterprise plugin loader
- [ ] Document extension APIs
- [ ] Create enterprise installer that adds to OSS base

### Phase 5: Documentation

- [ ] Update OSS README with feature scope
- [ ] Create enterprise documentation
- [ ] Document upgrade path from OSS to Enterprise
- [ ] Create comparison matrix for marketing

### Phase 6: Testing & Validation

- [ ] Verify OSS works standalone
- [ ] Verify enterprise extends OSS correctly
- [ ] Run full test suite on both repos
- [ ] Validate all examples work

### Phase 7: Release

- [ ] Publish OSS to PyPI
- [ ] Set up OSS Docker Hub images
- [ ] Create enterprise distribution channel
- [ ] Launch documentation sites

---

## Summary

The split follows a clear boundary:

**Open Source = Developer Productivity**
- Replace static secrets with dynamic credentials
- Secure local identity management
- Framework integrations for rapid development
- Self-hosted deployment option

**Enterprise = Organizational Governance**
- Virtual MCP Server (unified agent→tools connection)
- Delegation with cryptographic attenuation
- Compliance, audit, and enterprise identity
- Production scalability and operations

This approach:
1. **Maximizes adoption** through a useful open-source core
2. **Creates clear upgrade path** when teams hit enterprise needs
3. **Protects enterprise value** in differentiated governance features
4. **Aligns with industry standards** (similar to HashiCorp, Elastic, MongoDB models)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | — | Initial strategy document |
