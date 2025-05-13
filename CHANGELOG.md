# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.6] - 2025-05-13

### Added
- **New `deepsecure agent` Command Group:**
    - `deepsecure agent register`: Allows explicit registration of new agents. Supports generating local Ed25519 key pairs or using a provided public key. Registers agent with the `credservice` backend.
    - `deepsecure agent list`: Lists agents known locally and/or registered with the `credservice` backend. Supports `--local`, `--remote`, `--skip`, `--limit` options and various output formats (table, json, text).
    - `deepsecure agent describe <agent_id>`: Shows detailed information for a specific agent, combining backend data and local identity information.
    - `deepsecure agent delete <agent_id>`: Deactivates an agent in the `credservice` backend (soft delete). Supports `--purge-local-keys` to remove local identity files (with confirmation or `--force`).
- **Backend Integration for Agent Management:**
    - `credservice` now has API endpoints (`/api/v1/agents/`) for creating, listing, describing, and deactivating (soft deleting) agents.
    - Includes database schema updates (new fields in `agents` table) and corresponding CRUD operations and Pydantic schemas in `credservice`.
- **Local Agent Identity Management (`IdentityManager`):
    - Centralized logic in `deepsecure-cli` for creating, loading, listing, and deleting local agent identity files (storing Ed25519 key pairs) in `~/.deepsecure/identities/`.
- **Updated `AgentClient`:**
    - `deepsecure-cli`'s `AgentClient` now makes live HTTP calls to the `credservice` backend for agent management, inheriting from `BaseClient`.

### Changed
- Agent identity is no longer implicitly created by `deepsecure vault issue`. Agents must now be explicitly registered using `deepsecure agent register` before they can be used with `deepsecure vault issue --agent-id ...` for backend-integrated credential issuance.
- Agent deletion is now a "soft delete" (sets status to `inactive` in `credservice`) to preserve referential integrity with associated credentials.

### Fixed
- Resolved various startup and runtime errors in `credservice` related to module imports (logging, typing.List, pydantic_settings, psycopg2), database migrations (Alembic template rendering and revision ID quoting), and Pydantic schema validation/serialization for agent data (particularly UTF-8 decoding of binary public keys and string vs. bytes handling for public keys in Pydantic models).
- Corrected `AttributeError` and `TypeError` issues in `deepsecure-cli` related to `key_manager` usage and argument passing in client/command layers for agent commands. 