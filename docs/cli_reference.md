# DeepSecure CLI Command Reference

Welcome to the command-line interface (CLI) reference for DeepSecure. The `deepsecure` CLI is the primary tool for administrators and developers to manage agent identities, secrets, and access control policies in the `credservice` backend.

## Global Options

- `--output {text,json}`: Sets the output format. `text` is human-readable, while `json` provides detailed, machine-readable output.
- `--help`: Shows help for any command or subcommand.

---

## `deepsecure configure`

Commands for setting up the CLI's connection to the `credservice`.

### `deepsecure configure set-url <URL>`

Sets and saves the URL for the `credservice` API endpoint.

- **`URL`**: The full URL of the `credservice` (e.g., `http://localhost:8001`).

### `deepsecure configure set-token`

Securely prompts for and saves the API authentication token required to communicate with `credservice`.

---

## `deepsecure agent`

Commands for managing agent identities. An agent is a unique, auditable identity that your AI code uses to authenticate.

### `deepsecure agent register --name <AGENT_NAME>`

Creates a new agent identity, generating a public/private key pair. The private key is stored securely in the local OS keyring.

-   **`--name <AGENT_NAME>`** (Required): A unique name for the agent (e.g., "data-analysis-agent").
-   **`--public-key-file <PATH>`**: (Optional) Path to an existing public key file to register instead of generating a new one.

### `deepsecure agent list`

Lists all agent identities that have been created locally.

### `deepsecure agent delete --name <AGENT_NAME>`

Deletes an agent identity from the `credservice` backend and removes its private key from the local OS keyring.

-   **`--name <AGENT_NAME>`** (Required): The name of the agent to delete.
-   **`--force`**: (Optional) Skips the confirmation prompt.

---

## `deepsecure vault`

Commands for managing secrets stored securely in the `credservice` vault.

### `deepsecure vault store <SECRET_NAME>`

Stores a new secret in the vault. The value is read securely from a prompt.

-   **`<SECRET_NAME>`**: The name of the secret to store (e.g., "OPENAI_API_KEY").
-   **`--value <VALUE>`**: (Optional) Provide the secret value directly as an argument. **Warning:** This may expose the secret in your shell history.

### `deepsecure vault get-credential <SECRET_NAME> --agent-name <AGENT_NAME>`

Issues an ephemeral, short-lived credential for a secret on behalf of a specific agent. This is the core command for providing your agent with just-in-time access to secrets.

-   **`<SECRET_NAME>`** (Required): The name of the secret to access.
-   **`--agent-name <AGENT_NAME>`** (Required): The name of the agent requesting the secret. The agent must have a policy allowing access.

### `deepsecure vault revoke --credential-id <ID>`

Immediately revokes an issued credential, making it invalid.

-   **`--credential-id <ID>`** (Required): The unique ID of the credential to revoke (obtained from the `get-credential` JSON output).

---

## `deepsecure policy`

Commands for managing the access control policies that determine which agents can access which secrets.

### `deepsecure policy create --agent-name <AGENT_NAME> --secret-name <SECRET_NAME> --action <ACTION>`

Creates a new policy granting an agent permission to perform an action on a secret.

-   **`--agent-name <AGENT_NAME>`** (Required): The name of the agent.
-   **`--secret-name <SECRET_NAME>`** (Required): The name of the secret.
-   **`--action <ACTION>`** (Required): The permission to grant. Currently, the primary action is `read`. 