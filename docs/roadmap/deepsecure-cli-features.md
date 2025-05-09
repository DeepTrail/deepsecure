# deepsecure CLI: Features Overview

The `deepsecure` CLI will act as the command-line interface and security control plane for developers and security engineers building secure AI agents, MCP servers, and apps. It offers tools for managing credentials, enforcing policy, auditing behavior, and integrating security into development and deployment workflows.

## 🔐 1. Credential Management

### `deepsecure vault issue`

* **Purpose:** Generate ephemeral credentials (short-lived, scoped tokens) for AI agents and tools.
* **What it helps with:** Prevents long-lived credential leaks and enforces least privilege.
* **Example:**

    ```bash
    deepsecure vault issue --scope=db:readonly --ttl=5m
    ```

### `deepsecure vault revoke`

* **Purpose:** Revoke a credential issued to an agent/tool.
* **What it helps with:** Clears unused or risky credentials immediately.
* **Example:**

    ```bash
    deepsecure vault revoke --id=cred-abc123
    ```

### `deepsecure vault rotate`

* **Purpose:** Rotate the long-lived **agent identity key** (Ed25519) associated with a specific agent ID.
* **What it helps with:** Improves security hygiene by periodically changing the primary signing key for an agent.
* **Example:**

    ```bash
    deepsecure vault rotate --agent-id=agent-0053e159-5fb5-4e19-924f-7abdb26d8901
    # --type defaults to 'agent-identity'
    ```

## 🧠 2. Identity Risk & Behavior Monitoring

### `deepsecure audit start`

* **Purpose:** Start capturing and logging AI identity actions (tool use, data access).
* **What it helps with:** Provides a full audit trail for forensics and compliance.
* **Example:**

    ```bash
    deepsecure audit start --identity=ai-agent-1
    ```

### `deepsecure audit tail`

* **Purpose:** Stream audit logs in real-time.
* **What it helps with:** Observe live AI behavior and detect suspicious activity.
* **Example:**

    ```bash
    deepsecure audit tail --filter="access:file"
    ```

### `deepsecure risk score`

* **Purpose:** Get the dynamic risk score for an AI identity or tool.
* **What it helps with:** Identify high-risk agents that may require isolation or revocation.
* **Example:**

    ```bash
    deepsecure risk score --identity=agent1
    ```

### `deepsecure risk list`

* **Purpose:** List all AI identities with their current risk levels.
* **What it helps with:** Prioritizes where to enforce stricter security or rotate keys.
* **Example:**

    ```bash
    deepsecure risk list
    ```

## 🛡️ 3. Policy Enforcement

### `deepsecure policy init`

* **Purpose:** Bootstrap a runtime policy template for an agent or server.
* **What it helps with:** Enforces least privilege on AI behavior at runtime.
* **Example:**

    ```bash
    deepsecure policy init --template=read-only
    ```

### `deepsecure policy apply`

* **Purpose:** Apply a runtime policy to an AI agent or server.
* **What it helps with:** Blocks unauthorized actions like shell commands or file writes.
* **Example:**

    ```bash
    deepsecure policy apply --identity=agent1 --policy=./policy.yaml
    ```

### `deepsecure sandbox run`

* **Purpose:** Execute an AI agent or server in a sandboxed environment with enforced policies.
* **What it helps with:** Prevents rogue behavior or prompt injection exploits.
* **Example:**

    ```bash
    deepsecure sandbox run ./agent.py --policy=./policy.yaml
    ```

## 🔎 4. Credential Scanning & Hygiene

### `deepsecure scan`

* **Purpose:** Scan code, configs, or logs for exposed secrets or credentials.
* **What it helps with:** Detects leaks and hardcoded keys during development or CI/CD.
* **Example:**

    ```bash
    deepsecure scan ./src/
    ```

### `deepsecure scan live`

* **Purpose:** Scan running processes or environment for secrets in memory.
* **What it helps with:** Detects runtime leaks or insecure environment variables.
* **Example:**

    ```bash
    deepsecure scan live --pid=1234
    ```

## 🧰 5. Server Hardening & Secure Defaults

### `deepsecure harden server`

* **Purpose:** Secure an existing MCP server (add auth, TLS, logging).
* **What it helps with:** Turns insecure open MCP tools into hardened services.
* **Example:**

    ```bash
    deepsecure harden server --target=router-server --tls --auth=token
    ```

### `deepsecure deploy secure`

* **Purpose:** Deploy a secure containerized instance of an AI agent or MCP server.
* **What it helps with:** Offers secure-by-default environments for dev/test/prod.
* **Example:**

    ```bash
    deepsecure deploy secure --type=mcp-router --vault --audit
    ```

## 📊 6. Security Scorecard & Visibility

### `deepsecure scorecard`

* **Purpose:** Generate a security score for an AI agent, app, or server.
* **What it helps with:** Identifies gaps in auth, logging, sandboxing, credential usage.
* **Example:**

    ```bash
    deepsecure scorecard ./agent.py
    ```

### `deepsecure inventory list`

* **Purpose:** List all AI identities, MCP servers, and their config/status.
* **What it helps with:** Helps track shadow AI agents and orphaned services.
* **Example:**

    ```bash
    deepsecure inventory list --orphans
    ```

## 🧩 7. IDE Integration Support (Cursor, VSCode)

### `deepsecure ide init`

* **Purpose:** Set up a development environment with DeepSecure hooks in an IDE.
* **What it helps with:** Brings runtime security and vault access to dev workflows.
* **Example:**

    ```bash
    deepsecure ide init --cursor
    ```

### `deepsecure ide suggest`

* **Purpose:** Lint current codebase for secure agent practices (policy, vault usage, etc.).
* **What it helps with:** Educates and nudges developers toward secure defaults.
* **Example:**

    ```bash
    deepsecure ide suggest ./agent.py
    ```

## 🧭 Summary Table

| CLI Command                  | Category                | Purpose                                          |
| :--------------------------- | :---------------------- | :----------------------------------------------- |
| `vault issue/revoke/rotate`  | Credential Management   | Manage short-lived secure credentials            |
| `audit start/tail`           | Behavior Monitoring     | Log and trace identity/tool activity             |
| `risk score/list`            | Risk Profiling          | Evaluate and visualize risky AI identities       |
| `policy init/apply`          | Runtime Enforcement     | Enforce access controls and limits               |
| `sandbox run`                | Runtime Enforcement     | Run agents inside sandbox with active policies   |
| `scan` / `scan live`         | Leak Detection          | Catch secrets in code, logs, or memory           |
| `harden server`/`deploy secure` | Server Hardening        | Lock down MCP servers and AI agents in production |
| `scorecard`/`inventory list` | Visibility & Audit      | Visualize security posture of AI stack           |
| `ide init`/`ide suggest`     | Developer IDE Support | Bring secure-by-default authoring to AI dev tools |
