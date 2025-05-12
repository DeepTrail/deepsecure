# DeepSecure CLI: Design for `deepsecure agent` Command Group

This document outlines the design for the `deepsecure agent` command group, focusing on providing explicit control over the agent lifecycle.

## Core `deepsecure agent` Commands Design

The main goal is to provide explicit control over the agent lifecycle, moving away from implicit registration during `vault issue`.

1.  **`deepsecure agent register [--name <name>] [--description <description>] [--public-key <key_path>] [--output json|text]`**
    *   **Purpose:** Explicitly registers a new agent with `credservice`.
    *   **Functionality:**
        *   If `--public-key <key_path>` is provided:
            *   The CLI will read the public key from the specified file path.
            *   This public key is sent to `credservice` for registration.
            *   It's assumed the user manages the corresponding private key separately.
        *   If `--public-key` is *not* provided:
            *   The CLI generates a new Ed25519 key pair.
            *   The public key is sent to `credservice` for registration.
            *   The private key is stored locally (e.g., in `~/.deepsecure/identities/<agent_id>.json` or, ideally, using the system `keyring` as per future enhancements).
        *   `--name <name>` (optional): Assigns a human-readable name to the agent.
        *   `--description <description>` (optional): Provides a description for the agent.
    *   **Interaction with `credservice`:**
        *   Sends the public key (and optional metadata like name/description) to a new endpoint (e.g., `POST /api/v1/agents`).
        *   `credservice` generates a unique `agent_id` for the new agent, stores the public key and metadata.
    *   **Output:**
        *   The unique `agent_id` assigned by `credservice`.
        *   If a new key pair was generated, the path where the local private key is stored (or a confirmation if stored in keyring).
        *   A confirmation message.
        *   Supports `--output json` for programmatic use or `text` for human readability.

2.  **`deepsecure agent list [--local | --remote] [--filter <expression>] [--output json|text|table]`**
    *   **Purpose:** Lists agents known to the system.
    *   **Functionality:**
        *   `--local`: Displays agents whose identities (private keys) are stored locally (e.g., in `~/.deepsecure/identities/` or system keyring).
        *   `--remote`: Displays agents registered with `credservice` (this would be the default if no flags are specified).
        *   Both flags can be used, or the command can intelligently merge/distinguish if an agent is both local and remote.
        *   `--filter <expression>` (optional): Allows server-side or client-side filtering based on agent attributes (e.g., `--filter "name=BillingAgent"` or `--filter "status=active"`).
    *   **Interaction with `credservice`:**
        *   For remote listing, calls an endpoint like `GET /api/v1/agents` (potentially with filter parameters).
    *   **Interaction with local storage:**
        *   For local listing, scans the local identity store.
    *   **Output:**
        *   A list of agents, with columns such as: `Agent ID`, `Name`, `Public Key (fingerprint)`, `Registration Date`, `Status` (e.g., active, revoked), `Source (local/remote)`.
        *   Supports `--output json`, `text`, or `table` format.

3.  **`deepsecure agent describe <agent_id> [--output json|text|table]`**
    *   **Purpose:** Provides detailed information about a specific agent.
    *   **Arguments:**
        *   `<agent_id>` (required): The ID of the agent to describe.
    *   **Interaction with `credservice`:**
        *   Calls an endpoint like `GET /api/v1/agents/<agent_id>`.
    *   **Interaction with local storage:**
        *   May also retrieve local information, such as the path to the private key if stored locally.
    *   **Output:**
        *   Detailed agent information: `Agent ID`, `Name`, `Description`, `Full Public Key`, `Registration Timestamp`, `Last Rotation Timestamp` (if applicable), `Status`, `Local Private Key Path` (if known), and any other relevant metadata.
        *   Supports `--output json`, `text`, or `table` format.

4.  **`deepsecure agent delete <agent_id> [--revoke-credentials] [--purge-local-keys] [--force]`**
    *   **Purpose:** Decommissions/deregisters an agent.
    *   **Arguments:**
        *   `<agent_id>` (required): The ID of the agent to delete.
        *   `--revoke-credentials` (optional, defaults to true, but should prompt if interactive and not specified): Instructs `credservice` to revoke all active credentials previously issued to this agent.
        *   `--purge-local-keys` (optional, defaults to false for safety): If specified, the CLI will attempt to delete the agent's local private key. This action should require confirmation if `--force` is not used.
        *   `--force` (optional): Suppresses interactive confirmation prompts for destructive actions like purging local keys.
    *   **Interaction with `credservice`:**
        *   Calls an endpoint like `DELETE /api/v1/agents/<agent_id>`.
        *   `credservice` should mark the agent as inactive/deleted and handle credential revocation if requested.
    *   **Interaction with local storage:**
        *   If `--purge-local-keys` is active, removes the local identity files or keyring entries.
    *   **Output:**
        *   Confirmation message of the action taken.

## Additional Features for Agent Management (for consideration)

As requested, here's a list of other features that would complement the core agent management commands and align with the broader goals outlined in your documents:

1.  **`deepsecure agent update <agent_id> [--name <new_name>] [--description <new_description>]`**:
    *   Allows modification of mutable agent metadata (like name or description) after registration.

2.  **Secure Local Key Storage Integration**:
    *   This is an underlying enhancement rather than a new command. It involves modifying `agent register` (and any command generating/handling private keys) to use the system's secure keyring (e.g., macOS Keychain, Freedesktop Secret Service) instead of storing private keys in plaintext JSON files in `~/.deepsecure/identities/`. This directly addresses the "More Secure Local Key Storage" point in your plan.

3.  **Agent Identity Import/Export**:
    *   `deepsecure agent export <agent_id> --file <path> [--password <password_for_encryption>]`: Exports an agent's identity (including its private key if managed by `deepsecure` and locally available) to an encrypted or plain file.
    *   `deepsecure agent import --file <path> [--password <password_for_decryption>]`: Imports an agent's identity from a file. This would involve registering the public key with `credservice` if it's not already known by `agent_id` (if present in file) or by public key.

4.  **Enhanced Metadata Association (e.g., Ownership, Project Tags)**:
    *   Extend `agent register` and `agent update` to allow associating agents with owner information (e.g., user ID, email) or project tags. This would be useful for auditing, policy enforcement, and filtering in the `agent list` command. `credservice` would need to support storing this additional metadata.

5.  **Explicit Local Key Management Commands**:
    *   For advanced users or troubleshooting:
        *   `deepsecure agent local-keys list`: Lists all agent identities for which private keys are stored locally.
        *   `deepsecure agent local-keys delete <agent_id | key_fingerprint> [--force]`: Deletes a specific local private key.

6.  **Agent Identity Rotation Command Clarification**:
    *   The document mentions `deepsecure vault rotate --agent-id <agent_id>`. For consistency, consider if this should eventually be aliased or moved to `deepsecure agent rotate-identity <agent_id>`. This command would handle generating a new key pair for the agent, updating local storage, and notifying `credservice` of the new public key. For now, we can proceed with the existing command structure as per the document.

This design aims to provide a comprehensive set of commands for managing agent identities explicitly. 