# DeepSecure CLI: AI Agent Testing Plan and Functionality Roadmap

## Original User Query

Based on the markdown document - Secure AI Agent Frameworks: Comparison and Architecture, Secretless Identity & Authentication for AI Agents: Architecture & Design Guidance, Comprehensive Agent Security and Governance Platform Vision, and Current Implementation and Integration Testing Plan -- Let's create a plan to 1. With current implemented deepsecure-cli functionality - read the code base and not just the README.md- start testing the AI agents built with 1. Crew AI 2. Google ADK 3. AutoGen (Microsoft) 4. LangGraph (LangChain) 2. What additional deepsecure-cli functionality needs to be added that is not yet implemented - read the code base and not just the README.md

## Response

Here's a plan to address your request:

**Part 1: Plan for Testing AI Agents with Current `deepsecure-cli` Functionality**

This plan focuses on leveraging the *currently implemented* features of `deepsecure-cli` and `credservice` as described in "Current Implementation and Integration Testing Plan.md" and "Comprehensive Agent Security and Governance Platform Vision.md" (specifically the "How Current Functionality Helps" and "Demonstrating Current Functionality..." sections).

**A. General Setup and Assumptions for Testing:**

1.  **Backend Service (`credservice`):**
    *   The `credservice` FastAPI application must be running and accessible to the environment where the AI agents will execute.
    *   It should be configured with its database (e.g., a clean SQLite `test.db` for testing).
2.  **CLI Configuration:**
    *   The `deepsecure-cli` must be installed and executable in the agent's environment.
    *   The following environment variables must be set in the agent's execution environment:
        *   `DEEPSECURE_CREDSERVICE_URL`: Pointing to the running `credservice`.
        *   `DEEPSECURE_CREDSERVICE_API_TOKEN`: The static API token matching the backend's configuration.
3.  **Clean State (Recommended for each major test run):**
    *   Start with an empty `~/.deepsecure/` directory on the machine running the agent/CLI.
    *   Start with a clean `credservice` database.
4.  **Integration Method:** All integrations will use Python's `subprocess` module to call the `deepsecure-cli` commands from within the agent's tool/function code. The output will be JSON (`--output json`) for easier parsing.

**B. General Integration and Testing Pattern for each AI Framework:**

This pattern will be adapted for each specific framework:

1.  **Identify Integration Point:** Determine where the AI agent framework makes an external call (to a tool, API, database) that would typically use a static, long-lived secret.
2.  **Agent Identity Creation (Implicit on First Use):**
    *   The first time `deepsecure vault issue` is called for a new agent, the CLI will generate a local Ed25519 key pair, store it in `~/.deepsecure/identities/<agent_id>.json`, and the `credservice` will register the agent's public key. Subsequent calls will use this existing identity.
3.  **Dynamic Credential Issuance:**
    *   **Action:** Within the agent's custom tool/function, execute:
        `deepsecure vault issue --scope "framework:resource:action" --ttl "5m" --output json`
        (Replace `framework:resource:action` with a relevant scope, e.g., `crewai:database:read_order`).
    *   **Process:** The agent code will parse the JSON output to retrieve `credential_id`, `agent_id`, `ephemeral_public_key`, `ephemeral_private_key`, `scope`, and `expires_at`.
    *   **Verification (CLI/Backend Interaction):**
        *   Confirm a local identity file `~/.deepsecure/identities/<agent_id>.json` is created/present.
        *   Confirm the `credservice` registered the agent (e.g., by trying to fetch agent details via a (currently non-existent) direct API or checking DB if accessible). This step might be implicit.
4.  **Simulate Resource Interaction:**
    *   **Action:** The agent's tool uses the obtained `credential_id` (and potentially the `ephemeral_private_key` to sign something or establish a mock secure channel) to "call" the target resource.
    *   **Logging:** Log the `credential_id`, `agent_id`, and `scope` being used for the simulated call.
5.  **Simulate Resource-Side Credential Verification:**
    *   **Action:** A separate script or a simulated part of the "resource" calls the `credservice`'s verification endpoint:
        `curl -X GET $DEEPSECURE_CREDSERVICE_URL/api/v1/vault/credentials/<credential_id>/verify`
    *   **Verification:** Check that the response shows `is_valid: true`, `status: "valid"`, and matches the issued `scope`, `agent_id`, and `ephemeral_public_key`.
6.  **Test Credential Revocation:**
    *   **Action:** After the simulated resource interaction, the agent's tool (or a cleanup step) executes:
        `deepsecure vault revoke --id <credential_id>`
    *   **Verification:**
        *   Confirm the CLI command succeeds.
        *   Call the `credservice` verification endpoint again for the `<credential_id>`.
        *   Check that the response now shows `is_valid: false`, `status: "revoked"`.
        *   Verify `~/.deepsecure/revoked_creds.json` contains the `credential_id`.
7.  **Test Agent Identity Rotation:**
    *   **Action:** For a given `agent_id` (obtained from a previous issuance), execute:
        `deepsecure vault rotate --agent-id <agent_id>`
    *   **Verification:**
        *   Confirm the CLI command indicates backend notification was successful.
        *   Inspect `~/.deepsecure/identities/<agent_id>.json` to confirm `public_key` and `private_key` have changed and `rotated_at` is updated.
        *   (If possible) Verify `credservice` has the new agent public key (e.g., by calling `GET /api/v1/agents/<agent_id>` if you implement such an endpoint, or checking DB).
        *   **Crucially:** Attempt a new `deepsecure vault issue --agent-id <agent_id> --scope "..."` and verify it succeeds, demonstrating the agent can still get credentials after rotation (using its new long-term key to sign the new ephemeral key).

**C. Specific Testing Plans for AI Frameworks:**

1.  **CrewAI:**
    *   **Integration Point:** Inside the `_run` method of a custom CrewAI `Tool`.
    *   **Test Scenario:**
        1.  Create a custom tool (e.g., `SecureInternalAPITool`).
        2.  In `_run`, use `subprocess` to call `deepsecure vault issue --scope "crewai:internal_api:user_query" --ttl "2m" --output json`.
        3.  Parse the credential. Log its details.
        4.  Simulate calling an internal API using the `credential_id`.
        5.  (Optional) Implement a mock internal API that calls `credservice` to verify the credential.
        6.  After simulation, use `subprocess` to call `deepsecure vault revoke`.
        7.  Define a CrewAI Agent and Task that utilize this tool. Kick off the crew.
        8.  Separately, test `deepsecure vault rotate` for the `agent_id` used by the tool.

2.  **Google ADK:**
    *   **Integration Point:** Within the code that implements a "Tool" that the ADK agent can invoke, or within the "Handler" that processes an agent's request.
    *   **Test Scenario:**
        1.  Define an ADK tool (e.g., for accessing a protected data source).
        2.  In the tool's execution logic, before accessing the data source, use `subprocess` to call `deepsecure vault issue --scope "adk:datasource:read_record" --ttl "3m" --output json`.
        3.  Parse and log the credential.
        4.  Simulate accessing the data source.
        5.  (Optional) Mock data source verifies with `credservice`.
        6.  Revoke the credential via `subprocess`.
        7.  Test agent identity rotation for the involved `agent_id`.

3.  **AutoGen (Microsoft):**
    *   **Integration Point:** Inside a Python function registered as a tool for an agent (e.g., `UserProxyAgent.register_function`) or within a method of a custom Agent class.
    *   **Test Scenario:**
        1.  Create an AutoGen script with, for example, an `ExecutorAgent`.
        2.  Define a Python function `call_protected_service(details: str)` and register it.
        3.  Inside `call_protected_service`, use `subprocess` for `deepsecure vault issue --scope "autogen:protected_svc:action" --ttl "1m" --output json`.
        4.  Parse, log, simulate service call, (optional) mock verification, and revoke.
        5.  Task the AutoGen agent to use this function.
        6.  Test agent identity rotation.

4.  **LangGraph (LangChain):**
    *   **Integration Point:** As a dedicated node within the LangGraph state machine.
    *   **Test Scenario:**
        1.  Define a LangGraph graph.
        2.  Create a node function `fetch_dynamic_credential(state)`:
            *   Uses `subprocess` to call `deepsecure vault issue --scope "langgraph:external_tool:execute" --ttl "5m" --output json`.
            *   Parses the output and updates the graph's shared `state` with `credential_id`, `agent_id`, `ephemeral_private_key`, etc.
        3.  Create another node `execute_external_tool_securely(state)`:
            *   Reads credential details from `state`.
            *   Logs simulation of tool call using the credential.
        4.  (Optional) A node simulating the tool could verify via `credservice`.
        5.  Add a node `revoke_credential_node(state)` that uses `subprocess` to revoke.
        6.  Define edges to connect these nodes logically. Compile and run the graph.
        7.  Test agent identity rotation for the `agent_id` captured in the state.

**Part 2: Additional `deepsecure-cli` Functionality Needed**

Based on a comparison of the "Current Implementation" document against the vision outlined in "Comprehensive Agent Security and Governance Platform Vision" and the feature list in "deepsecure-cli-features.md", the following functionality is needed:

**A. Core Developer Experience & Integration:**

1.  **Python Client Library (`deepsecure` Package):**
    *   **Need:** This is the **most critical missing piece** for smoother and more secure integration. Directly calling CLI commands via `subprocess` is cumbersome, error-prone, and less secure than a dedicated library.
    *   **Functionality:** Expose `VaultClient` methods (issue, revoke, rotate, verify) directly. Handle configuration, backend communication, and parsing of responses.
2.  **Simplified Configuration (`deepsecure configure`):**
    *   **Need:** Easier setup of `DEEPSECURE_CREDSERVICE_URL` and `DEEPSECURE_CREDSERVICE_API_TOKEN` than manual environment variables.
    *   **Functionality:** A command to guide users through setting these, potentially storing them in a local config file (`~/.deepsecure/config.toml`) or system keyring.
3.  **Secure API Token Handling (CLI to Backend):**
    *   **Need:** Storing the `DEEPSECURE_CREDSERVICE_API_TOKEN` in an environment variable is not ideal for production.
    *   **Functionality:** Integrate with `keyring` to securely store and retrieve this token. Implement a `deepsecure login` (even if it's for a static token initially) or `deepsecure configure set-token` command.

**B. Agent Identity and Lifecycle Management:**

1.  **Explicit Agent Management Commands:**
    *   **Need:** Currently, agent registration is implicit on the first credential issuance. More control is needed.
    *   **Functionality:**
        *   `deepsecure agent register [--public-key <key_path>]`: Explicitly register a new agent with `credservice`.
        *   `deepsecure agent list`: List agents known to `credservice` (or locally).
        *   `deepsecure agent describe <agent_id>`: Get details of a specific agent.
        *   `deepsecure agent delete <agent_id>`: Decommission/deregister an agent.
2.  **More Secure Local Key Storage:**
    *   **Need:** Storing agent private keys in plaintext JSON files in `~/.deepsecure/identities/` is a risk.
    *   **Functionality:** Option to use the system `keyring` or other encrypted storage for local agent private keys.

**C. Enhanced Authentication and Authorization:**

1.  **User-Specific CLI Authentication:**
    *   **Need:** The static shared `DEEPSECURE_CREDSERVICE_API_TOKEN` is a single point of failure and doesn't allow for user-specific CLI access control to the backend.
    *   **Functionality:** Implement user logins for the CLI (e.g., OAuth2, JWTs) that `credservice` can authenticate, allowing for different CLI users to have different permissions against the backend.
2.  **Backend RBAC/Policy for CLI Actions:**
    *   **Need:** `credservice` currently only checks the static API token.
    *   **Functionality:** Implement Role-Based Access Control in `credservice` so that different authenticated CLI users/tokens can only perform certain actions (e.g., only admins can list all agents).

**D. Comprehensive Audit and Risk Management (largely unimplemented):**

1.  **Centralized & Richer Backend Audit Logs:**
    *   **Need:** Current backend logging is basic. A dedicated, immutable audit trail is required.
    *   **Functionality:** `credservice` should log all significant events (agent registration, credential issuance/revocation/verification, rotation, auth attempts) with rich context to a secure, queryable store.
2.  **CLI for Audit Access:**
    *   **Need:** Way to retrieve and view audit logs.
    *   **Functionality:** `deepsecure audit tail`, `deepsecure audit query --agent-id <id> --event-type <type>`.
3.  **Risk Scoring Engine & CLI Commands:**
    *   **Need:** Proactive risk assessment is a core vision.
    *   **Functionality:**
        *   Backend components for defining risk metrics and calculating scores.
        *   `deepsecure risk score <agent_id>`, `deepsecure risk list`.

**E. Policy Enforcement (beyond passive scope checking):**

1.  **Runtime Policy Engine:**
    *   **Need:** The current `scope` is a passive string. Active policy enforcement is a key goal.
    *   **Functionality:**
        *   A policy definition language/format.
        *   `credservice` (or a new policy service) endpoint that can make decisions based on agent identity, scope, resource, and other attributes.
        *   CLI commands: `deepsecure policy init`, `deepsecure policy apply`, `deepsecure policy get <agent_id>`.
2.  **Sandboxing (`deepsecure sandbox run`):**
    *   **Need:** To securely execute agent code.
    *   **Functionality:** CLI command to run agent code within a containerized/restricted environment, potentially integrated with the policy engine.

**F. Credential Scanning & Server Hardening (entirely unimplemented):**

*   **Functionality:** `deepsecure scan`, `deepsecure scan live`, `deepsecure harden server`, `deepsecure deploy secure`. These are significant new capabilities.

**G. Visibility & IDE Integration (entirely unimplemented):**

*   **Functionality:** `deepsecure scorecard`, `deepsecure inventory list`, `deepsecure ide init`, `deepsecure ide suggest`. 
