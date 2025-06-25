# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.8] - 2025-07-31

### Added
- **Automated Database Migrations**: The `credservice` now automatically runs database migrations on startup, eliminating the need for manual `alembic upgrade head` commands.
- **Dynamic Backend Versioning**: The `credservice` `/health` endpoint now dynamically reports the project version from `pyproject.toml`, ensuring version consistency.
- **Official Release Process**: Created a new `docs/deepsecure-release-process.md` to standardize the release workflow.
- **Comprehensive Requirements**: Added a full suite of dependency groups (`[dev]`, `[test]`, `[docs]`, etc.) to `pyproject.toml` and a corresponding `requirements/` directory for flexible development setups.
- **Developer `Makefile`**: Introduced a `Makefile` with convenient commands (`make test`, `make build`, etc.) to streamline common development tasks.
- **Troubleshooting Guide**: Added a troubleshooting section to the `credservice-setup.md` guide with instructions for checking Docker logs.

### Changed
- **Simplified `credservice` Setup**: Completely overhauled `docs/credservice-setup.md` to be fully container-centric. The setup process is now a single `docker compose up` command.
- **Improved `README.md` Clarity**: Refactored the main `README.md` to correct the Quick Start workflow, remove confusing instructions, and provide a clear "What's Next?" section for different user journeys.
- **Enhanced Health Check**: The `/health` endpoint now provides a richer JSON response, including database connection status, for easier debugging.
- **Standardized Release Testing**: The official release process now includes explicit, copy-pasteable commands for end-to-end testing of documentation and example scripts.

### Fixed
- **Corrected Port and URL Mismatches**: Resolved all inconsistencies for the `credservice` port (`8001`) and URL across all documentation.
- **Resolved Test Suite Failures**: Fixed numerous longstanding test failures, ensuring the test suite is stable and reliable.

### Removed
- **Removed Manual Database Setup**: Removed all instructions for `createdb` and manual `alembic` commands from user-facing documentation, as this is now fully automated.
- **Removed Redundant Setup Instructions**: Removed duplicate and out-of-sync setup details from the SDK documentation, pointing instead to a single source of truth.

## [0.1.7] - 2025-07-28

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
- **`422 Unprocessable Entity` Errors**: Fixed API tests in `credservice/tests/api/v1/test_agents.py` by sending the correct `public_key` payload and using valid base64-encoded keys.
- **`TypeError` in Client Tests**: Resolved `TypeError: __init__() got an unexpected keyword argument 'backend_url'` in `tests/_core/test_client.py` by using `monkeypatch` to set the environment variable instead.
- **`409 Conflict` Assertion**: Corrected the expected status code for duplicate agent registration from `400` to `409`.
- **Pydantic Deprecation Warnings**: Updated `FieldValidationInfo` to the modern `ValidationInfo` in `credservice` schemas to resolve deprecation warnings.

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
    - A new "Architecture" section featuring a Mermaid diagram was added to visually explain the interaction between DeepSecure components (CLI, SDK, OS Keyring, `credservice`, Database).
    - The main title of the `README.md` was updated to "DeepSecure: Simple Security for Your AI Agents & AI-powered Workflows" for better impact.
    - Prerequisites and backend setup instructions were clarified, especially regarding Docker Compose for the `credservice` and CLI configuration steps.
    - Quick Start examples were refined for both Python SDK and CLI usage.
    - The "CLI Command Reference" section header now includes a 💻 icon for better visual organization.

## [0.1.4] - 2025-06-01

### Added
- Dockerized `credservice` backend with PostgreSQL for simplified developer setup and testing (via `docker-compose up`). See `README.md` and `credservice/` directory.
- CLI command `deepsecure configure set-log-level` to allow users to set local CLI logging verbosity (DEBUG, INFO, WARNING, etc.). The `show` command now also displays the current log level.
- More specific keyring service naming convention for agent private keys: `deepsecure_agent-<agent_id_prefix>_private_key`, improving clarity in system keychain utilities.

### Changed
- Updated `README.md` with instructions for Dockerized `credservice` and a new section explaining `deepsecure vault issue` behavior regarding ephemeral private keys (hidden in text output, available in JSON output).
- `deepsecure agent delete` command now has a unified confirmation prompt before any action (backend deactivation or local key purge) if `--force` is not used, clearly stating what will happen.

### Fixed
- **`origin_context`** in credential issuance now correctly flows from CLI client, through the `credservice` backend, and is included in the final credential response.
- **`deepsecure agent list`**: 
    - Correctly handles and exits gracefully (exit code 0) with a "No agents found" message when the backend returns an empty list of agents, instead of throwing an error.
    - Fixed underlying issues that led to the backend (incorrectly) reporting 0 agents when agents did exist in the database (related to ensuring correct database instance was queried and Pydantic serialization of agent list in `credservice`).
- **User-Agent Header**: The `deepsecure` CLI now sends a dynamic User-Agent string including the correct package version (e.g., `DeepSecureCLI/0.1.4`).
- **Credential Revocation**: `credservice` now correctly updates the `status` field to "revoked" in the database when a credential is revoked, in addition to setting `revoked_at`.
- Resolved `ImportError` in `deepsecure commands/agent.py` related to `KEYRING_SERVICE_NAME_AGENT_KEYS` after refactoring keyring service name logic.
- Corrected various `NameError` and `AttributeError` issues in `deepsecure` CLI commands related to client instance naming and method calls (e.g., `agent_client` vs `agent_service_client`, `agent_client.client.method_name`).
- Addressed `AttributeError: module 'keyring.errors' has no attribute 'PasswordNotFoundError'` by updating exception handling in `deepsecure/core/config.py` to use `keyring.errors.PasswordDeleteError`.
- Ensured Python environment and editable installs correctly pick up latest source code changes, resolving version inconsistencies and stale code execution.
- Fixed various Python package dependencies and import errors in `credservice` for Docker build (e.g., `pydantic-settings`, `python-jose`, `passlib`).
- Ensured Alembic migrations can find the `alembic/` script directory within the `credservice` Docker container.

## [0.1.3] - 2025-05-28

### Changed
- Updated project description in `pyproject.toml` to: "DeepSecure: Secure your AI agent and agentic AI application ecosystem with DeepSecure."

## [0.1.2] - 2025-05-27

### Changed
- Agent identity is no longer implicitly created by `deepsecure vault issue`. Agents must now be explicitly registered using `deepsecure agent register` before they can be used with `deepsecure vault issue --agent-id ...` for backend-integrated credential issuance.
- Agent deletion is now a "soft delete" (sets status to `inactive` in `credservice`) to preserve referential integrity with associated credentials.
- **`deepsecure vault issue` Command:**
    - The `--agent-id` option is now strictly required to identify which agent's local private key (from keyring) should be used for signing the credential request.
    - Removed internal fallback to implicit agent registration if an `agent_id` was not found locally; agent must be pre-registered using `deepsecure agent register`.
- **Internal Key Handling:** Standardized on base64 encoded raw bytes for key exchange between components and for storage format of private keys in keyring / public keys in metadata files.

### Added
- **Mandatory Signature Verification for Credential Issuance:**
    - `credservice` now requires and cryptographically verifies agent signatures on all requests to issue credentials (`POST /api/v1/vault/credentials`).
    - `deepsecure vault issue` CLI command now performs client-side signing: loads the specified agent's private key (from system keyring via `IdentityManager`), generates ephemeral keys, signs the ephemeral public key, and includes the signature in the request to `credservice`.
- **Secure Local Storage for Agent Private Keys:**
    - `IdentityManager` in `deepsecure` now stores agent private keys in the system's secure keyring (e.g., macOS Keychain, Freedesktop Secret Service) instead of plaintext in local JSON files.
    - Local JSON identity files (`~/.deepsecure/identities/`) now only store public metadata (agent ID, name, public key).
- **New `deepsecure agent` Command Group:**
    - `deepsecure agent register`: Allows explicit registration of new agents. Supports generating local Ed25519 key pairs or using a provided public key. Registers agent with the `credservice` backend.
    - `deepsecure agent list`: Lists agents known locally and/or registered with the `credservice` backend. Supports `--local`, `--remote`, `--skip`, `--limit` options and various output formats (table, json, text).
    - `deepsecure agent describe <agent_id>`: Shows detailed information for a specific agent, combining backend data and local identity information.
    - `deepsecure agent delete <agent_id>`: Deactivates an agent in the `credservice` backend (soft delete). Supports `--purge-local-keys` to remove local identity files (with confirmation or `--force`).
- **Backend Integration for Agent Management:**
    - `credservice` now has API endpoints (`/api/v1/agents/`) for creating, listing, describing, and deactivating (soft deleting) agents.
    - Includes database schema updates (new fields in `agents` table) and corresponding CRUD operations and Pydantic schemas in `credservice`.
- **Local Agent Identity Management (`IdentityManager`):**
    - Centralized logic in `deepsecure` for creating, loading, listing, and deleting local agent identity files (storing Ed25519 key pairs) in `~/.deepsecure/identities/`.
- **Updated `AgentClient`:**
    - `deepsecure`'s `AgentClient` now makes live HTTP calls to the `credservice` backend for agent management, inheriting from `BaseClient`.

### Fixed
- Resolved numerous `ImportError`, `AttributeError`, `TypeError`, `KeyError`, and Pydantic/SQLAlchemy issues across `deepsecure` and `credservice` to enable end-to-end functioning of agent registration (with keyring), signed credential issuance, and server-side signature verification.
- Corrected issues with `deepsecure/client.py` test script to ensure it uses the correct client implementations, keyring-aware identity management, and accurately reflects current API contracts for successful test execution.
- Ensured Pydantic schemas (client and server-side) for credential issuance and verification correctly handle `bytes` vs. `str` types for cryptographic keys/signatures and `datetime` serialization.
- Resolved various startup and runtime errors in `credservice` related to module imports (logging, typing.List, pydantic_settings, psycopg2), database migrations (Alembic template rendering and revision ID quoting), and Pydantic schema validation/serialization for agent data (particularly UTF-8 decoding of binary public keys and string vs. bytes handling for public keys in Pydantic models).
- Corrected `AttributeError` and `TypeError` issues in `deepsecure` related to `key_manager` usage and argument passing in client/command layers for agent commands.