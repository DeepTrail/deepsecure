# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2024-05-29

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
- Corrected `AttributeError` and `TypeError` issues in `deepsecure` related to `key_manager` usage and argument passing in client/command layers for agent commands