# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.11] - 2026-01-11

### 🚀 **MODEL-AGNOSTIC GATEWAY INTERFACE + ANTHROPIC INTEGRATION**
**New unified gateway abstraction for seamless integration with any AI model provider**

### Added

#### **Model-Agnostic Gateway Client**
- **`GatewayClient` class** (`deepsecure/integrations/gateway.py`): New unified interface for proxying requests through the DeepSecure Gateway
  - Generic `request()` method supporting all HTTP verbs (GET, POST, PUT, DELETE, PATCH)
  - Convenience methods: `gateway.get()`, `gateway.post()`, `gateway.put()`, `gateway.delete()`, `gateway.patch()`
  - Auto-detection of secret names for well-known services based on `target_base_url`
  - Support for custom APIs with explicit `secret_name` parameter
- **`client.gateway`**: New top-level client attribute for model-agnostic API proxying
  ```python
  # Generic gateway access
  resp = client.gateway.get("/v1/models", "https://api.openai.com")
  resp = client.gateway.post("/v1/messages", "https://api.anthropic.com", json={...})
  ```

#### **Well-Known Service Auto-Detection**
- Automatic secret name resolution for popular AI providers:
  | Target Base URL | Auto-detected Secret |
  |-----------------|---------------------|
  | `https://api.openai.com` | `openai-api-key` |
  | `https://api.anthropic.com` | `anthropic-api-key` |
  | `https://generativelanguage.googleapis.com` | `google-ai-api-key` |
  | `https://api.cohere.ai` | `cohere-api-key` |
  | `https://api.mistral.ai` | `mistral-api-key` |
  | `https://api.together.xyz` | `together-api-key` |
  | `https://api.groq.com` | `groq-api-key` |

#### **Anthropic/Claude Integration**
- **`AnthropicIntegration` class** (`deepsecure/integrations/anthropic.py`): Full Anthropic API support
  - `create_message()`: Create messages using Claude models (Messages API)
  - `count_tokens()`: Count tokens before sending to manage context window
  - `complete()`: Legacy completions API support
  - Support for all Claude models: `claude-sonnet-4-20250514`, `claude-3-opus-20240229`, `claude-3-haiku-20240307`
- **`client.anthropic`**: New top-level client attribute for Anthropic API access
  ```python
  resp = client.anthropic.create_message(
      messages=[{"role": "user", "content": "Hello, Claude!"}],
      model="claude-sonnet-4-20250514",
      max_tokens=1024
  )
  ```

#### **Design Documentation**
- Added autonomy control proposal documentation (`docs/design/deepsecure-autonomy-control.md`)
- Updated design documentation for new capabilities including web auth and user-agent delegation
- Updated comparison documentation with OpenFGA

### Changed

#### **OpenAI Integration Refactoring**
- **Refactored `OpenAIIntegration`** to use `GatewayClient` underneath for consistent behavior
  - Added new convenience methods: `chat_completion()`, `create_embedding()`, `list_files()`
  - All methods now delegate to `client.gateway` for unified request handling
  - Cleaner, more maintainable code with shared gateway infrastructure

### Fixed

#### **Example Scripts**
- **Fixed Example 13** (`examples/13_quickstart_openai_list_models.py`): 
  - Resolved `AttributeError: 'PolicyClient' object has no attribute 'get_by_name'`
  - Fixed authentication token handling in PolicyClient
  - Corrected agent_id format handling for policy creation
- **Fixed Example 14** (`examples/14_quickstart_openai_policy_enforcement.py`):
  - Resolved `AttributeError: 'Client' object has no attribute 'gateway'`
  - Added `client.gateway` interface with `request()` method for generic gateway access

#### **PolicyClient Fixes**
- Added missing `get_by_name()` method for policy lookup by name
- Fixed authentication to use admin API token instead of agent JWT for policy management operations
- Corrected agent_id format handling (strips "agent-" prefix before sending to backend)

#### **Documentation Cleanup**
- Fixed file locations and visibility issues in documentation
- Cleaned up and organized documentation structure

### Technical Details

#### **New Files**
- `deepsecure/integrations/gateway.py` - Model-agnostic GatewayClient (294 lines)
- `deepsecure/integrations/anthropic.py` - Anthropic integration (252 lines)

#### **Modified Files**
- `deepsecure/client.py` - Added `client.gateway` and `client.anthropic` attributes
- `deepsecure/integrations/openai.py` - Refactored to use GatewayClient

### Test Summary

| Metric | Value |
|--------|-------|
| Total Tests | 292 |
| Passed | 270 |
| Failed | 0 |
| Skipped | 22 |
| Errors | 0 |
| Duration | 62.04 seconds |
| Coverage | 46.85% |

**Status: ✅ All tests passed** - 72 new tests added vs v0.1.10

#### **Critical Tests Verified**
- ✅ Agent authentication flow
- ✅ Vault secret storage and retrieval
- ✅ Policy creation and enforcement
- ✅ Gateway request proxying
- ✅ Delegation with split-key workflow
- ✅ OpenAI integration
- ✅ Anthropic integration (new)

#### **New Feature Tests Added**
- `GatewayClient` initialization and request methods
- Generic HTTP request proxying through gateway
- Auto-detection of secret names for known services
- Streaming response support
- `AnthropicIntegration` class initialization
- `client.credentials` namespace methods
- `client.identity_manager` property
- `client.get_agent()` method

#### **Test Infrastructure Improvements**
- Added environment variable mocking fixtures for integration tests
- Marked integration tests with `@pytest.mark.integration` for selective execution
- Added `TERM` environment variable setup to fix `rich.console` errors
- New Makefile targets: `make test-unit`, `make test-integration`, `make test-report`
- Fixed `test_sdk_example_integration_pattern` - added missing `_skip_if_backend_unavailable()` guard
- Added `model_dump()` method to mock Policy classes in test files (Pydantic V2 compatibility)
- Added `strip_ansi()` helper function to handle Rich console ANSI escape codes in 6 test files

#### **Deprecation Warnings Fixed (55 total warnings eliminated)**

| Warning Type | Occurrences Fixed | Files Modified | Status |
|--------------|-------------------|----------------|--------|
| `datetime.utcnow()` deprecated | 25 | 10 | ✅ Fixed |
| `Field(example=...)` deprecated | 18 | 3 | ✅ Fixed |
| `sslib.shamir` missing `required_shares` | 6 | 1 | ✅ Fixed |
| `orm_mode` deprecated | 3 | 3 | ✅ Fixed |
| `.dict()` deprecated | 2 | 1 | ✅ Fixed |
| **Total** | **55** | **18** | ✅ |

**Files Modified:**
- **datetime.utcnow()**: `test_policy_enforcement.py`, `test_policy_enforcement_examples.py`, `test_policy_jwt_*.py`, `test_cli_policy_*.py`, `test_policies_examples.py`, `macaroon_service.py`, `crud_nonce.py`
- **Pydantic schemas**: `credential.py`, `agent.py`, `token.py`, `policy.py`, `nonce.py`, `attestation_policy.py`
- **CLI commands**: `deepsecure/commands/policy.py`
- **Test fixes**: `test_delegation_split_key_integration.py`

#### **Remaining Warnings (~59)**
Only external library warnings remain (passlib, pytest-asyncio, etc.) - these cannot be fixed directly and will resolve when those libraries are updated.

Full test report: [`test-results/v0.1.11/test-report.md`](test-results/v0.1.11/test-report.md)

## [0.1.10] - 2025-07-21

### 🏗️ **MAJOR ARCHITECTURAL TRANSFORMATION + CRITICAL STABILITY FIXES**
**Complete evolution from monolithic to enterprise-grade dual-service architecture with advanced security features and comprehensive test infrastructure overhaul**

### Fixed

#### **P0 Critical Production Issues Resolved**
- **Database Schema Compatibility**: Fixed critical PostgreSQL/SQLite compatibility issue where JSONB columns caused test failures
  - Implemented database-aware column types using SQLAlchemy `.with_variant()` 
  - PostgreSQL production now uses high-performance JSONB, SQLite tests use compatible JSON
  - Affected models: `Secret.secret_metadata`, `Credential.origin_context`, `Policy.actions/resources`
- **Gateway Core Implementation**: Resolved missing class imports that blocked Gateway tests
  - Implemented `RequestMetadata`, `HeaderSanitizer`, `RequestLogEntry` classes in `deeptrail-gateway/app/core/request_logger.py`
  - Added comprehensive metadata classes for structured logging and request processing
  - Fixed all import errors preventing Gateway test execution
- **Backend Service Dependencies**: Resolved integration test failures and import path issues
  - Fixed test utility imports and path resolution across moved test files
  - Added missing utility functions (`random_uuid()`) to test helpers
  - Corrected service-to-service communication paths

#### **Documentation Consistency**
- **Removed Legacy References**: Eliminated all outdated "credservice" references from documentation
  - Updated `docs/README.md` to reference "Backend Services Setup" instead of "Credservice Setup"
  - Changed environment variables from `DEEPSECURE_CREDSERVICE_URL` to `DEEPSECURE_CONTROL_PLANE_URL`
  - Updated troubleshooting guides and setup instructions for dual-service architecture

### Added

#### **Dual-Service Architecture**
- **🧠 Control Plane (`deeptrail-control`)** - Port 8000: Policy Decision Point (PDP) and agent lifecycle management
  - Agent identity registration and management with Ed25519 cryptographic signatures
  - Challenge-response authentication system with nonce-based signature verification
  - JWT token issuance with embedded agent permissions and resource scopes
  - Policy definition and storage with JSON-based policy engine
  - Audit logging and compliance tracking for all security events
  - RESTful API with comprehensive OpenAPI specification
- **🚀 Data Plane (`deeptrail-gateway`)** - Port 8002: Policy Enforcement Point (PEP) and runtime operations
  - Real-time policy enforcement middleware with JWT validation
  - Automatic secret injection for external API calls
  - HTTP request proxying with transparent credential management
  - Security filtering, rate limiting, and request sanitization
  - Health monitoring and metrics collection

#### **Split-Key Security Architecture**
- **Shamir's Secret Sharing Implementation**: Secrets split into two shares for defense-in-depth security
  - `share_1` stored in Control Plane PostgreSQL database
  - `share_2` stored in Gateway Redis with AES-256-GCM encryption
- **JIT (Just-In-Time) Reassembly Engine**: Runtime secret reconstruction with secure memory cleanup
  - Parallel share retrieval with 5-second timeout protection
  - HMAC-SHA256 request signatures for internal authentication
  - Automatic memory cleanup after secret usage
- **SecretStorageManager**: Encrypted share management with TTL support

#### **Advanced Authentication & Authorization**
- **Ed25519 Cryptographic Agent Identities**: Unique cryptographic identity per AI agent
- **Challenge-Response Authentication Flow**: 
  - Nonce generation and signature verification
  - Single-use nonce consumption to prevent replay attacks
  - Agent public key validation and storage
- **JWT-Based Authorization**: Claims-based access control with signature verification
- **Macaroon Delegation System**: Cryptographic delegation tokens with attenuation caveats
- **Multi-Platform Agent Bootstrapping**:
  - Kubernetes Service Account Token (SAT) validation
  - AWS STS GetCallerIdentity token verification  
  - Azure Managed Identity token validation
  - Docker container identity bootstrapping

#### **Policy Engine & Enforcement**
- **Policy Decision Point (PDP)**: Centralized policy definition and storage
  - JSON-based policy syntax with actions, resources, and conditions
  - Agent-specific policy assignment and evaluation
  - Effect-based policies (allow/deny) with fine-grained permissions
- **Policy Enforcement Point (PEP)**: Runtime policy enforcement at the gateway
  - Domain-based access control for external services
  - HTTP method restrictions and validation
  - JWT claims validation and permission checking
  - Policy result caching for performance optimization

#### **Runtime Security Middleware Stack**
- **JWTValidationMiddleware**: Signature-based JWT token validation
  - Shared SECRET_KEY validation with Control Plane
  - Token expiration, timing, and claims validation
  - Agent identity extraction and state management
- **PolicyEnforcementMiddleware**: Real-time access control decisions
  - Domain and method-based policy enforcement
  - JWT claims-based permission validation
  - Policy violation logging and response
- **SecretInjectionMiddleware**: Automatic credential injection
  - Bearer token injection for API authentication
  - Domain-specific secret retrieval and application
  - Multiple authentication scheme support
- **SecurityMiddleware**: Request filtering and validation
  - IP filtering and rate limiting
  - Request size limits and timeout enforcement
  - Malicious pattern detection and blocking

#### **Comprehensive API Architecture**
- **RESTful Control Plane API**: Complete CRUD operations for agents, policies, and credentials
  - Agent registration: `POST /api/v1/agents`
  - Authentication: `POST /api/v1/auth/challenge`, `POST /api/v1/auth/token`
  - Policy management: `GET/POST /api/v1/policies`
  - Credential issuance: `POST /api/v1/vault/credentials`
  - Delegation: `POST /api/v1/auth/delegate`
- **Gateway Proxy API**: HTTP method support with transparent credential injection
  - Proxy endpoint: `/{method} /proxy/{path}` with `X-Target-Base-URL` header
  - Health checks: `GET /health`, `GET /ready`
  - Metrics: `GET /metrics`, `GET /config`
- **Internal Service API**: Secure service-to-service communication
  - Secret sharing: `GET /api/v1/internal/secrets/{name}/share`
  - Internal authentication with `X-Internal-API-Token` header

#### **Advanced Security Features**
- **Replay Attack Prevention**: Token hash tracking with time-based cleanup
- **Rate Limiting**: Client-based request throttling with configurable windows
- **Request Sanitization**: Header cleaning, content validation, and size limits
- **Security Headers**: Comprehensive security header injection (CSP, HSTS, etc.)
- **Audit Logging**: Structured security event logging with correlation IDs
- **Circuit Breakers**: External service protection with retry logic and backoff

#### **Agent Lifecycle Management**
- **Agent Registration**: Public key validation and unique agent ID generation
- **Agent Authentication**: Ed25519 signature verification with challenge-response
- **Agent Status Management**: Active/inactive status tracking with last-seen timestamps  
- **Agent Bootstrapping**: Automated identity provisioning from cloud platforms
- **Agent Delegation**: Cryptographic delegation with macaroon attenuation

### Fixed
- **Critical Gateway Version Bug**: Fixed deeptrail-gateway service to properly read version from `DEEPSECURE_VERSION` environment variable instead of using hardcoded version numbers in health endpoints, FastAPI app configuration, and metrics endpoints.
- **Version Consistency Across Dual Architecture**: Both Control Plane and Gateway services now consistently return the same version number from their respective health check endpoints (`/health`) by reading from the shared environment variable.
- **Dynamic Version Configuration**: Implemented proper version configuration pattern in `deeptrail-gateway/app/core/proxy_config.py` with `get_project_version()` function that reads from environment variable first, then falls back to `pyproject.toml` for local development.
- **Test Suite Flexibility**: Updated all gateway-related tests to validate version presence rather than checking hardcoded version strings, ensuring tests remain stable across version updates.

### Changed
- **Environment Variable Propagation**: Added missing `DEEPSECURE_VERSION=0.1.10` environment variable to `deeptrail-gateway` service in `docker-compose.yml`, ensuring both services receive proper version information.
- **Version Documentation**: Updated example health check responses in `docs/backend-services-setup.md` to show version 0.1.10 for both Control Plane and Gateway services.
- **OpenAPI Specification Rewrite**: Completely rewrote `docs/openapi.yaml` to accurately document the dual-service architecture with comprehensive API specification including all Control Plane endpoints (agent management, authentication, bootstrapping, vault operations, policies) and Gateway endpoints (health checks, proxy operations, metrics), proper security schemes, detailed schemas, and extensive examples.

### Technical Implementation Details

#### **Database Schema**
- **agents** table: Ed25519 public keys, agent metadata, status tracking
- **credentials** table: Ephemeral credential tracking with expiration
- **policies** table: JSON-based policy definitions with agent associations
- **secrets** table: Split secret storage with share_1 and metadata
- **nonces** table: Challenge-response nonce management

#### **Security Architecture**
- **Cryptographic Functions**: Ed25519 signature generation/verification, SHA-256 hashing
- **Encryption**: AES-256-GCM for share storage, HMAC-SHA256 for message authentication  
- **JWT Configuration**: HS256 algorithm with shared secret validation
- **Secret Sharing**: 2-of-2 Shamir's Secret Sharing with python-sslib library

#### **Service Communication**
- **Control Plane ↔ Gateway**: Internal API with token-based authentication
- **Client ↔ Control Plane**: RESTful API with API key authentication
- **Client ↔ Gateway**: JWT-based authentication with proxy forwarding
- **Gateway ↔ External Services**: Transparent proxying with credential injection

#### **Comprehensive Test Documentation**
- **`docs/test-architecture-mapping.md`**: Complete mapping of 64 tests to architectural components
- **`docs/test-results-report.md`**: Detailed analysis of test results across all components
- **`docs/p0-critical-issues-resolution.md`**: Documentation of critical fixes implemented
- **`docs/jsonb-to-json-impact-analysis.md`**: Technical analysis of database compatibility solution

#### **Test Result Tracking**
- Created systematic approach to track test results by architectural component
  - Main CLI/SDK Tests: 247 tests with 89% pass rate  
  - Control Plane Tests: Previously blocked, now functional with database fixes
  - Gateway Tests: Previously blocked, now functional with missing class implementations

### Changed

#### **Test Infrastructure Overhaul**
- **Complete Test Reorganization**: Moved all test files from project root to proper architectural locations
  - Policy CLI tests: `test_policy_cli_*.py` → `tests/commands/` (3 files)
  - Core functionality tests: `test_*_detection.py`, `test_keyring_*.py` → `tests/_core/` (2 files)  
  - SDK integration tests: `test_sdk_bootstrap_integration.py` → `tests/` (1 file)
  - Updated all import paths to use relative paths instead of hardcoded absolute paths
- **Enhanced Test Architecture Mapping**: Created comprehensive documentation showing how all 64 test files map to architectural components
  - Control Plane (PDP): 24 test files covering policy decisions and agent management
  - Data Plane (PEP): 16 test files covering policy enforcement and secret injection
  - CLI/SDK: 14 test files covering user interfaces and developer experience

### Technical Implementation Details

#### **Database Compatibility Solution**
```python
# Applied to all JSON columns across models
secret_metadata = Column(
    JSON().with_variant(postgresql.JSONB(), 'postgresql'),
    nullable=True
)
```
- **Production (PostgreSQL)**: Uses JSONB for high performance and indexing
- **Testing (SQLite)**: Uses JSON for compatibility and test speed
- **Zero Breaking Changes**: Existing queries and functionality preserved

#### **Test Organization Strategy**
- **By Architectural Layer**: Tests organized by the component they validate
- **Import Path Standardization**: All tests use relative imports for portability
- **Comprehensive Coverage**: Every major architectural component has dedicated test coverage

## [0.1.9] - 2025-06-26

### Added
- **Comprehensive Examples Documentation**: Created detailed `examples/README.md` with user-friendly setup instructions, learning objectives, expected behaviors, and troubleshooting guidance for all 7 SDK examples.
- **Enhanced Release Process Documentation**: Added `deeptrail-control/docker-compose.yml` version management to the official release process, ensuring all three version locations stay synchronized.
- **Automated Example Testing**: Implemented complete test coverage for all 7 examples in `tests/test_examples.py` with proper environment setup and error reporting.
- **Streamlined Release Validation**: Replaced manual example execution with automated pytest-based testing for faster and more reliable release validation.

### Changed
- **Examples Status Updates**: Updated examples 03 and 05 from "Future" to "Work in Progress" status, providing more accurate development timeline expectations.
- **Improved Setup Instructions**: Enhanced setup documentation with clear explanations of why each step is needed and optional skip conditions for users who have already completed main README setup.
- **Better Learning Experience**: Added dual documentation approach with both "What You'll Learn" (educational) and "Expected Behavior" (validation) sections for each example.
- **Release Process Efficiency**: Updated release testing workflow from 5+ individual commands to a single automated test command that covers all 7 examples.

### Fixed
- **Test Coverage Gaps**: Corrected `tests/test_examples.py` to include all 7 examples (was missing examples 04, 06, 07) with proper file path formatting.
- **Version Management**: Added missing `DEEPSECURE_VERSION` environment variable documentation in release process to prevent version drift between package and Docker container.
- **Documentation Consistency**: Aligned example descriptions and status indicators across all documentation files for better user experience.
- **Pytest Failures and Architecture Cleanup**: Completely resolved all test failures by removing deprecated identity manager methods and modernizing the test suite for the new backend-only architecture.
- **Identity Manager Architecture**: Removed all deprecated file-based identity methods (`create_identity`, `load_identity`, `list_identities`, `delete_identity`, `persist_generated_identity`, `find_identity_by_name`) and replaced with clean backend-first implementation.
- **Test Suite Modernization**: Rewrote 43 tests across multiple test files to match the current backend-only architecture, achieving 100% test pass rate with comprehensive coverage of all functionality.
- **Example Test Self-Containment**: Enhanced `tests/test_examples.py` with automatic environment setup, backend health checking, and secret provisioning, eliminating the need for manual environment configuration.
- **Development Environment Sync**: Added `pip install -e .` step to release process documentation to prevent version mismatch issues between source code and installed package during testing.

## [0.1.8] - 2025-06-25

### Added
- **Automated Database Migrations**: The `deeptrail-control` now automatically runs database migrations on startup, eliminating the need for manual `alembic upgrade head` commands.
- **Dynamic Backend Versioning**: The `deeptrail-control` `/health` endpoint now dynamically reports the project version from `pyproject.toml`, ensuring version consistency.
- **Official Release Process**: Created a new `docs/deepsecure-release-process.md` to standardize the release workflow.
- **Comprehensive Requirements**: Added a full suite of dependency groups (`[dev]`, `[test]`, `[docs]`, etc.) to `pyproject.toml` and a corresponding `requirements/` directory for flexible development setups.
- **Developer `Makefile`**: Introduced a `Makefile` with convenient commands (`make test`, `make build`, etc.) to streamline common development tasks.
- **Troubleshooting Guide**: Added a troubleshooting section to the `deeptrail-control-setup.md` guide with instructions for checking Docker logs.

### Changed
- **Simplified `deeptrail-control` Setup**: Completely overhauled `docs/deeptrail-control-setup.md` to be fully container-centric. The setup process is now a single `docker compose up` command.
- **Improved `README.md` Clarity**: Refactored the main `README.md` to correct the Quick Start workflow, remove confusing instructions, and provide a clear "What's Next?" section for different user journeys.
- **Enhanced Health Check**: The `/health` endpoint now provides a richer JSON response, including database connection status, for easier debugging.
- **Standardized Release Testing**: The official release process now includes explicit, copy-pasteable commands for end-to-end testing of documentation and example scripts.

### Fixed
- **Corrected Port and URL Mismatches**: Resolved all inconsistencies for the `deeptrail-control` port (`8001`) and URL across all documentation.
- **Resolved Test Suite Failures**: Fixed numerous longstanding test failures, ensuring the test suite is stable and reliable.

### Removed
- **Removed Manual Database Setup**: Removed all instructions for `createdb` and manual `alembic` commands from user-facing documentation, as this is now fully automated.
- **Removed Redundant Setup Instructions**: Removed duplicate and out-of-sync setup details from the SDK documentation, pointing instead to a single source of truth.

## [0.1.7] - 2025-06-23

### Added
- **`CONTRIBUTING.md`**: Created a comprehensive guide for contributors, detailing modern and traditional development setups.
- **`scripts/setup_dev.sh`**: Added a new development setup script to simplify environment preparation for contributors.
- **`requirements/` Directory**: Introduced a full `requirements` directory structure (`base.txt`, `dev.txt`, `test.txt`, etc.) for traditional, file-based dependency management.
- **Optional Dependencies in `pyproject.toml`**: Added modern, optional dependency groups like `[test]`, `[lint]`, `[docs]`, and `[build]` to `pyproject.toml`.
- **Makefile**: Added a `Makefile` to provide standardized, easy-to-use commands for common development tasks like `make install-dev`, `make test`, and `make build`.

### Changed
- **Improved Build Script**: Enhanced `./scripts/build_package.sh` to automatically check for and install required build tools like `build` and `twine`.
- **Modernized `CONTRIBUTING.md`**: Updated the contributing guide to showcase the new, flexible dependency management workflows.
- **Corrected License Configuration**: Updated `pyproject.toml` to use the modern `license = "Apache-2.0"` SPDX format, resolving deprecation warnings.

### Fixed
- **`422 Unprocessable Entity` Errors**: Fixed API tests in `deeptrail-control/tests/api/v1/test_agents.py` by sending the correct `public_key` payload and using valid base64-encoded keys.
- **`TypeError` in Client Tests**: Resolved `TypeError: __init__() got an unexpected keyword argument 'backend_url'` in `tests/_core/test_client.py` by using `monkeypatch` to set the environment variable instead.
- **`409 Conflict` Assertion**: Corrected the expected status code for duplicate agent registration from `400` to `409`.
- **Pydantic Deprecation Warnings**: Updated `FieldValidationInfo` to the modern `ValidationInfo` in `deeptrail-control` schemas to resolve deprecation warnings.

## [0.1.6] - 2025-06-06

### Added
- **New `CONTRIBUTING.md`:** Moved detailed development and contribution guidelines out of the `README.md` and into a dedicated `CONTRIBUTING.md` to keep the main readme focused on the user.

### Changed
- **Complete `README.md` Overhaul:** Restructured and rewrote the main `README.md` from the ground up to be more concise, developer-centric, and compelling for a startup audience.
    - Moved "Getting Started" and "Quick Start" to the top for immediate value.
    - Reframed the narrative to focus on solving developer pain points ("Stop wrestling with auth & scattered API keys").
    - Added "Before vs. After" diagrams to visually communicate the value proposition.
    - Consolidated lengthy security problem descriptions into a more digestible `🤔 Why DeepSecure?` section.
    - Streamlined the `README.md` by removing redundant information and verbose command outputs.

## [0.1.5] - 2025-06-04

### Changed
- **Enhanced `README.md` for Improved Developer Experience:**
    - Completely restructured `README.md` for significantly improved clarity, navigability, and developer engagement. The new structure includes dedicated sections for Key Features, a detailed Table of Contents, a compelling Overview, clear Getting Started instructions (Prerequisites, Installation), actionable Quick Start guides (for both SDK and CLI primary workflows), Core Concepts, a new Architecture section with a visual diagram, details on Integrations, a 💻 CLI Command Reference, instructions for Running the Credential Service (Backend), a project Roadmap & Vision, Contributing guidelines, and Community & Support information.
    - The "Overview" section has been rewritten to clearly articulate the problems DeepSecure solves, its target audience, and its core value proposition, drawing content from `deepsecure-landing.md` and previous README versions.
    - A new "Architecture" section featuring a Mermaid diagram was added to visually explain the interaction between DeepSecure components (CLI, SDK, OS Keyring, `deeptrail-control`, Database).
    - The main title of the `README.md` was updated to "DeepSecure: Simple Security for Your AI Agents & AI-powered Workflows" for better impact.
    - Prerequisites and backend setup instructions were clarified, especially regarding Docker Compose for the `deeptrail-control` and CLI configuration steps.
    - Quick Start examples were refined for both Python SDK and CLI usage.
    - The "CLI Command Reference" section header now includes a 💻 icon for better visual organization.

## [0.1.4] - 2025-06-01

### Added
- Dockerized `deeptrail-control` backend with PostgreSQL for simplified developer setup and testing (via `docker-compose up`). See `README.md` and `deeptrail-control/` directory.
- CLI command `deepsecure configure set-log-level` to allow users to set local CLI logging verbosity (DEBUG, INFO, WARNING, etc.). The `show` command now also displays the current log level.
- More specific keyring service naming convention for agent private keys: `deepsecure_agent-<agent_id_prefix>_private_key`, improving clarity in system keychain utilities.

### Changed
- Updated `README.md` with instructions for Dockerized `deeptrail-control` and a new section explaining `deepsecure vault issue` behavior regarding ephemeral private keys (hidden in text output, available in JSON output).
- `deepsecure agent delete` command now has a unified confirmation prompt before any action (backend deactivation or local key purge) if `--force` is not used, clearly stating what will happen.

### Fixed
- **`origin_context`** in credential issuance now correctly flows from CLI client, through the `deeptrail-control` backend, and is included in the final credential response.
- **`deepsecure agent list`**: 
    - Correctly handles and exits gracefully (exit code 0) with a "No agents found" message when the backend returns an empty list of agents, instead of throwing an error.
    - Fixed underlying issues that led to the backend (incorrectly) reporting 0 agents when agents did exist in the database (related to ensuring correct database instance was queried and Pydantic serialization of agent list in `deeptrail-control`).
- **User-Agent Header**: The `deepsecure` CLI now sends a dynamic User-Agent string including the correct package version (e.g., `DeepSecureCLI/0.1.4`).
- **Credential Revocation**: `deeptrail-control` now correctly updates the `status` field to "revoked" in the database when a credential is revoked, in addition to setting `revoked_at`.
- Resolved `ImportError` in `deepsecure commands/agent.py` related to `KEYRING_SERVICE_NAME_AGENT_KEYS` after refactoring keyring service name logic.
- Corrected various `NameError` and `AttributeError` issues in `deepsecure` CLI commands related to client instance naming and method calls (e.g., `agent_client` vs `agent_service_client`, `agent_client.client.method_name`).
- Addressed `AttributeError: module 'keyring.errors' has no attribute 'PasswordNotFoundError'` by updating exception handling in `deepsecure/core/config.py` to use `keyring.errors.PasswordDeleteError`.
- Ensured Python environment and editable installs correctly pick up latest source code changes, resolving version inconsistencies and stale code execution.
- Fixed various Python package dependencies and import errors in `deeptrail-control` for Docker build (e.g., `pydantic-settings`, `python-jose`, `passlib`).
- Ensured Alembic migrations can find the `alembic/` script directory within the `deeptrail-control` Docker container.

## [0.1.3] - 2025-05-28

### Changed
- Updated project description in `pyproject.toml` to: "DeepSecure: Secure your AI agent and agentic AI application ecosystem with DeepSecure."

## [0.1.2] - 2025-05-27

### Changed
- Agent identity is no longer implicitly created by `deepsecure vault issue`. Agents must now be explicitly registered using `deepsecure agent register` before they can be used with `deepsecure vault issue --agent-id ...` for backend-integrated credential issuance.
- Agent deletion is now a "soft delete" (sets status to `inactive` in `deeptrail-control`) to preserve referential integrity with associated credentials.
- **`deepsecure vault issue` Command:**
    - The `--agent-id` option is now strictly required to identify which agent's local private key (from keyring) should be used for signing the credential request.
    - Removed internal fallback to implicit agent registration if an `agent_id` was not found locally; agent must be pre-registered using `deepsecure agent register`.
- **Internal Key Handling**: Standardized on base64 encoded raw bytes for key exchange between components and for storage format of private keys in keyring / public keys in metadata files.

### Added
- **Mandatory Signature Verification for Credential Issuance:**
    - `deeptrail-control` now requires and cryptographically verifies agent signatures on all requests to issue credentials (`POST /api/v1/vault/credentials`).
    - `deepsecure vault issue` CLI command now performs client-side signing: loads the specified agent's private key (from system keyring via `IdentityManager`), generates ephemeral keys, signs the ephemeral public key, and includes the signature in the request to `deeptrail-control`.
- **Secure Local Storage for Agent Private Keys:**
    - `IdentityManager` in `deepsecure` now stores agent private keys in the system's secure keyring (e.g., macOS Keychain, Freedesktop Secret Service) instead of plaintext in local JSON files.
    - Local JSON identity files (`~/.deepsecure/identities/`) now only store public metadata (agent ID, name, public key).
- **New `deepsecure agent` Command Group:**
    - `deepsecure agent register`: Allows explicit registration of new agents. Supports generating local Ed25519 key pairs or using a provided public key. Registers agent with the `deeptrail-control` backend.
    - `deepsecure agent list`: Lists agents known locally and/or registered with the `deeptrail-control` backend. Supports `--local`, `--remote`, `--skip`, `--limit` options and various output formats (table, json, text).
    - `deepsecure agent describe <agent_id>`: Shows detailed information for a specific agent, combining backend data and local identity information.
    - `deepsecure agent delete <agent_id>`: Deactivates an agent in the `deeptrail-control` backend (soft delete). Supports `--purge-local-keys` to remove local identity files (with confirmation or `--force`).
- **Backend Integration for Agent Management:**
    - `deeptrail-control` now has API endpoints (`/api/v1/agents/`) for creating, listing, describing, and deactivating (soft deleting) agents.
    - Includes database schema updates (new fields in `agents` table) and corresponding CRUD operations and Pydantic schemas in `deeptrail-control`.
- **Local Agent Identity Management (`IdentityManager`):**
    - Centralized logic in `deepsecure` for creating, loading, listing, and deleting local agent identity files (storing Ed25519 key pairs) in `~/.deepsecure/identities/`.
- **Updated `AgentClient`:**
    - `deepsecure`'s `AgentClient` now makes live HTTP calls to the `deeptrail-control` backend for agent management, inheriting from `BaseClient`.

### Fixed
- Resolved numerous `ImportError`, `AttributeError`, `TypeError`, `KeyError`, and Pydantic/SQLAlchemy issues across `deepsecure` and `deeptrail-control` to enable end-to-end functioning of agent registration (with keyring), signed credential issuance, and server-side signature verification.
- Corrected issues with `deepsecure/client.py` test script to ensure it uses the correct client implementations, keyring-aware identity management, and accurately reflects current API contracts for successful test execution.
- Ensured Pydantic schemas (client and server-side) for credential issuance and verification correctly handle `bytes` vs. `str` types for cryptographic keys/signatures and `datetime` serialization.
- Resolved various startup and runtime errors in `deeptrail-control` related to module imports (logging, typing.List, pydantic_settings, psycopg2), database migrations (Alembic template rendering and revision ID quoting), and Pydantic schema validation/serialization for agent data (particularly UTF-8 decoding of binary public keys and string vs. bytes handling for public keys in Pydantic models).
- Corrected `AttributeError` and `TypeError` issues in `deepsecure` related to `key_manager` usage and argument passing in client/command layers for agent commands.