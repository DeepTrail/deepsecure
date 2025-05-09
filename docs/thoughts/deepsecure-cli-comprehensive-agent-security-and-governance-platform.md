# DeepSecure CLI: Comprehensive Agent Security and Governance Platform Vision

This document outlines the broader vision for `deepsecure-cli` as a comprehensive platform for agent security and governance, detailing how current functionality helps and what future steps are needed.

## Helping Developers Build More Secure AI Agents (Current Functionality & Vision)

The current implementation, while focused on replacing static secrets with dynamic credentials, lays the groundwork for a more comprehensive agent security and governance platform.

### How Current Functionality Helps

1. **Agent Identity (`Agent ID` & Associated Keys):**
    * **Current Help:**
        * **Unique Identification:** Each agent instance gets a unique, cryptographically verifiable `Agent ID` (tied to an Ed25519 key pair).
        * **Proof of Origin for Credentials:** The agent uses its long-term private key to sign the ephemeral public key during credential issuance.
    * **How Developers Use It:** Establish local agent identity using `deepsecure vault issue`. Use `Agent ID` for tracking in frameworks like LangGraph.

2. **Authentication (Agent-to-Backend & Agent-to-Resource):**
    * **Current Help (Agent-to-Backend):** Static API key (`DEEPSECURE_CREDSERVICE_API_TOKEN`) authenticates the CLI to the `credservice` backend.
    * **Current Help (Agent-to-Resource - via Ephemeral Credentials):**
        * The issued credential (containing `Credential ID`, signed `Ephemeral Public Key`, `Agent ID`, `scope`, `expiry`) is presented to the target resource.
        * The resource verifies the credential by calling `credservice`'s `/verify` endpoint.
    * **How Developers Use It:** Replace static API keys in agent tools (AutoGen, CrewAI, LangChain) with a call to `deepsecure vault issue`, then use the resulting credential for the resource call.

3. **Authorization (Scoped Credentials):**
    * **Current Help:** The `--scope` parameter in `deepsecure vault issue` requests credentials with limited permissions. The backend stores and can verify this scope via the `/verify` endpoint.
    * **How Developers Use It:** Request specific scopes (e.g., `db:orders:read`). Target resources check the credential's scope before allowing operations, enforcing least privilege.

4. **Audit (Basic Logging):**
    * **Current Help:**
        * **CLI-Side:** Logs local events (issuance, revocation, rotation) including IDs, scope, TTL, and backend interaction status to `~/.deepsecure/logs/audit.log`.
        * **Backend-Side:** FastAPI logs request/response metadata and internal operations/errors.
    * **How Developers Use It (Indirectly):** Provides a basic trace for debugging and incident response by correlating `Agent ID` and `Credential ID` across local and backend logs.

5. **Risk (Implicit / Foundational):**
    * **Current Help:**
        * Short-lived credentials reduce the risk window.
        * Scoped access limits blast radius.
        * Revocation provides a mechanism to invalidate compromised credentials.
        * Agent Identity provides the basis for tracking and accountability.
    * **How Developers Use It:** Inherently reduces risk compared to static secrets by adopting the dynamic credential pattern.

### Functionality Not Yet Implemented (or Partially Placeholder) for Broader Security Goals

1. **Comprehensive Agent Identity Lifecycle Management (CLI & Backend):** Explicit CLI commands/APIs for agent registration, listing, decommissioning; more secure local key storage (`keyring`).
2. **Advanced Authentication & Authorization:** User-specific CLI login/tokens; Backend RBAC; dynamic JWTs for CLI-backend communication.
3. **Comprehensive Audit Trail & Analysis:** Centralized, immutable backend audit logs; richer log context; CLI/API for querying audit trails.
4. **Risk Management & Scoring:** Defined risk metrics; backend risk scoring engine; CLI/API for viewing risk scores; future automated responses based on risk.
5. **Policy Enforcement:** Runtime policy decision capabilities beyond simple scope checks.
6. **Developer Experience (Beyond Core Functionality):** Robust Python library interface (replacing `subprocess` calls); framework-specific SDKs/wrappers; simplified configuration (`deepsecure configure`); secure token handling (`keyring`); pre-built cloud artifacts (Docker image, Lambda Layer).

---

## Demonstrating Current Functionality & Integration with Agent Frameworks

**Core Concept for Testing & Demonstration:**

The primary goal is to show how `deepsecure-cli` replaces static, long-lived secrets (API keys, DB passwords used directly by the agent/tool) with dynamic, short-lived, scoped credentials. The "test" involves integrating the `deepsecure vault issue` command (or its future library equivalent) into the agent's workflow right before it accesses a protected resource.

**Designing Demonstrations per Framework:**

The key is to identify *where* the agent framework makes external calls (to tools, APIs, databases) and inject the `deepsecure vault issue` call immediately before that point.

1. **AutoGen:**
    * **Integration Point:** Custom functions registered as tools for an agent (e.g., `UserProxyAgent.register_function`, or methods within custom Agent classes).
    * **Demonstration:**
        * Create a sample AutoGen script with a `Planner` and an `Executor` agent.
        * Define a Python function, say `call_secure_internal_api(query: str) -> str`, that the `Executor` can call.
        * **Inside `call_secure_internal_api`:**
            * Use Python's `subprocess` to run `deepsecure vault issue --scope "api:internal_service:query" --ttl "60s" [--local | --output json]`. *(This assumes the CLI is installed and configured)*.
            * Parse the output (especially the `credential_id` and `ephemeral_private_key` if needed for a subsequent secure channel, though the demo might just focus on getting the credential ID).
            * Log: "Obtained DeepSecure credential `<credential_id>` for API call."
            * *(Simulated Call)* Log: "Making API call to internal service with query: `<query>` using credential `<credential_id>`." (No actual API call needed for the demo).
            * Return a dummy success message.
        * The AutoGen script tasks the Planner/Executor to use this secure function.
        * **Value Shown:** Demonstrates replacing a potentially hardcoded API key within the tool function with a dynamically fetched credential ID.

2. **CrewAI:**
    * **Integration Point:** Custom `Tool` classes. The logic goes inside the `_run` method of the tool.
    * **Demonstration:**
        * Define a custom CrewAI `Tool`, e.g., `SecureDatabaseQueryTool`.
        * **Inside the `_run` method:**
            * Use `subprocess` to run `deepsecure vault issue --scope "db:orders:read" --ttl "120s" [--local | --output json]`.
            * Parse the output.
            * Log: "Obtained DeepSecure credential `<credential_id>` for DB query."
            * *(Simulated Call)* Log: "Connecting to DB and running query using credential `<credential_id>`."
            * Return dummy query results.
        * Create a simple Crew with an Agent assigned this `SecureDatabaseQueryTool`.
        * Define a Task that requires the agent to use the tool.
        * Run the Crew `kickoff()`.
        * **Value Shown:** Shows credential fetching integrated within a reusable CrewAI tool.

3. **LangChain / LangGraph:**
    * **Integration Point (LangChain):** Custom `Tool` classes (similar to CrewAI) or within custom LCEL chains (`RunnableLambda`).
    * **Integration Point (LangGraph):** A dedicated node within the graph's state machine.
    * **Demonstration (LangGraph):**
        * Define a LangGraph state graph.
        * Create a node function `get_deepsecure_credential(state)`:
            * Uses `subprocess` to run `deepsecure vault issue --scope "..." --ttl "..." [--local | --output json]`.
            * Parses output and updates the graph's shared `state` dictionary with credential details (e.g., `state['deepsecure_credential_id'] = ...`).
        * Create another node function `call_external_tool(state)`:
            * Reads the `state['deepsecure_credential_id']`.
            * Logs: "Calling external tool using credential `<credential_id>`."
            * Returns dummy results, updating the state.
        * Define edges connecting these nodes appropriately (e.g., fetch credential -> call tool).
        * Compile and run the graph.
        * **Value Shown:** Explicitly shows credential issuance as a distinct, auditable step within a complex agent workflow.

4. **Amazon Bedrock Agents:**
    * **Integration Point:** The Lambda function code backing an Action Group.
    * **Demonstration:**
        * **Prerequisite:** The Lambda execution environment needs access to `deepsecure-cli` (install it in the deployment package or a Lambda Layer) and the necessary environment variables (`DEEPSECURE_CREDSERVICE_URL`, `DEEPSECURE_CREDSERVICE_API_TOKEN`). The agent's identity file must also be accessible (e.g., mounted via EFS or fetched securely).
        * Modify the Lambda handler function (e.g., `lambda_handler(event, context)`).
        * **Inside the Lambda function:**
            * Before the code makes its call to the *actual* target API/service defined by the Action Group:
                * Use `subprocess` to run `deepsecure vault issue --scope "..." --ttl "..." [--local | --output json]`. *Note: Using `--local` might be complex depending on where the identity file is; calling the backend might be more feasible if the Lambda can reach it.*
                * Parse the output.
                * Log: "Lambda obtained DeepSecure credential `<credential_id>`."
                * *(Hypothetical Use)* Pass the credential ID or a derived token in the call to the target API/service.
            * Return the result to Bedrock as per the Action Group schema.
        * Invoke the Bedrock Agent in a way that triggers this Action Group.
        * **Value Shown:** Demonstrates securing the "last mile" call from the Bedrock infrastructure to internal APIs/databases.

---

## Making it Easy for Developers to Start Using

The current implementation relies heavily on `subprocess` calls from Python and manual environment variable setup, which isn't ideal for ease of use. Key improvements needed:

1. **Python Client Library (`deepsecure` Package):**
    * **Crucial:** Expose the core `VaultClient` functionality directly through the installed `deepsecure` package. Developers should be able to do `from deepsecure.core import vault_client` (or a simplified facade) and call methods like `vault_client.client.issue_credential(...)` directly from their agent code/tools. This avoids `subprocess` entirely.
    * Ensure this library handles configuration loading (environment variables, config files) smoothly.

2. **Clear Documentation & Examples:**
    * Provide a dedicated "Integrating with Agent Frameworks" section in the documentation.
    * Include concise, runnable code snippets for each framework (AutoGen tool, CrewAI tool, LangGraph node, Bedrock Lambda function) demonstrating the *library* usage (not `subprocess`).
    * Clearly explain the concepts: Agent ID vs Credential ID, Local vs Backend mode, required configuration.

3. **Simplified Configuration:**
    * Implement the planned file-based configuration (`deepsecure/config.py`, `~/.deepsecure/config.toml`).
    * Add a `deepsecure configure` command to help users set the backend URL and API token easily.

4. **Secure API Token Handling:**
    * Integrate the `keyring` library into `deepsecure/auth.py` and `BaseClient`.
    * Provide a command like `deepsecure configure set-token` or `deepsecure login` (even if it just stores a static token for now) that securely saves the `DEEPSECURE_CREDSERVICE_API_TOKEN` to the system keyring, rather than relying only on environment variables.

5. **Pre-built Artifacts (for Cloud):**
    * Offer a Docker container image with `deepsecure-cli` pre-installed.
    * Offer an AWS Lambda Layer containing the `deepsecure` library and its dependencies.

By providing a direct Python library interface, clear examples, and easier configuration/token management, developers can integrate DeepSecure's credential management into their agent workflows much more smoothly.
