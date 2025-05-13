# DeepSecure CLI End-to-End Sequence Flows

This document outlines common sequence flows demonstrating how AI agents use credentials issued by the DeepSecure CLI.

## Scenario 1: AI Agent Accessing Internal Business Application/Database (Local Credential Issuance)

This flow describes how an AI agent uses credentials issued locally (`--local` flag) to authenticate and establish a secure channel with an internal target system.

**Actors:**

* **AI Agent:** The process needing access.
* **DeepSecure CLI/VaultClient (Local):** The helper tool/library running alongside the Agent.
* **Target Application/Database:** The internal resource (e.g., API, database).
* **Verification Component:** Logic at the Target responsible for verifying DeepSecure credentials.

**Sequence Flow:**

1. **Need Arises:** AI Agent logic determines the need to access the Target Application/Database.
2. **Request Ephemeral Credential:**
    * AI Agent invokes `deepsecure vault issue --scope="<relevant_scope>" --ttl="<short_ttl>" --local` (or equivalent library function).
    * The request implicitly uses the Agent's long-term `Agent ID` and associated local private key.
3. **Local Credential Issuance:**
    * `VaultClient` generates a unique `Cred ID`.
    * `VaultClient` generates a new X25519 `Ephemeral Public Key` and `Ephemeral Private Key`.
    * `VaultClient` signs the `Ephemeral Public Key` using the Agent's long-term private key.
    * `VaultClient` packages `Cred ID`, `Agent ID`, `Ephemeral Public Key`, signature, `scope`, `expires_at` into a credential structure.
    * `VaultClient` returns the credential structure and the sensitive `Ephemeral Private Key` to the AI Agent process.
4. **Agent Prepares Request:**
    * AI Agent receives credential details, holding the `Ephemeral Private Key` securely in memory.
    * AI Agent constructs the request for the Target (e.g., HTTPS API call, DB connection request).
5. **Agent Sends Request with Credential:**
    * AI Agent sends the request to the Target.
    * The **credential structure** (containing `Cred ID`, `Agent ID`, `Ephemeral Public Key`, signature, etc.) is included (e.g., in an `Authorization` header).
    * **The `Ephemeral Private Key` is NOT sent.**
6. **Target Verification:**
    * The Target's Verification Component intercepts the request.
    * Extracts the credential structure.
    * Performs checks:
        * Expiry (`expires_at`).
        * Revocation status (checks `Cred ID` against local revocation list, if applicable).
        * Signature verification:
            * Looks up Agent's long-term public key using `Agent ID` (requires a trusted way to know this key).
            * Verifies the signature on the `Ephemeral Public Key`.
        * Authorization (checks `scope` against the intended operation).
7. **Secure Channel Establishment (If Verification OK):**
    * Verification Component generates its *own* ephemeral X25519 key pair.
    * Computes a shared secret using its *new ephemeral private key* and the Agent's received `Ephemeral Public Key`.
    * Sends its *new ephemeral public key* back to the AI Agent (e.g., in a response header).
8. **Agent Completes Secure Channel:**
    * AI Agent receives the Target's ephemeral public key.
    * Computes the *same* shared secret using *its* in-memory `Ephemeral Private Key` and the Target's public key.
9. **Perform Action Securely:**
    * AI Agent and Target Application use the shared secret to encrypt/decrypt the actual application payload (e.g., API request/response body, database query/results) using symmetric encryption (e.g., AES-GCM).
    * Target Application processes the authenticated and authorized request.
10. **Session Teardown:**
    * Upon completion, both Agent and Target discard their ephemeral keys and the shared secret.
    * The `Cred ID` expires naturally or can be revoked.

## Scenario 1.2: AI Agent Accessing Internal Business Application/Database (With Backend Integration)

This flow describes how an AI agent uses credentials obtained via the DeepSecure backend to authenticate and establish a secure channel with an internal target system.

**Actors:**

* **AI Agent:** The process needing access.
* **DeepSecure CLI/VaultClient (Local):** Helper tool/library running alongside the Agent.
* **DeepSecure Backend:** The central service responsible for issuance and verification.
* **Target Application/Database:** The internal resource (e.g., API, database).
* **Verification Component:** Logic at the Target, now interacts with the DeepSecure Backend.

**Sequence Flow:**

1. **Need Arises:** AI Agent logic determines the need to access the Target Application/Database.
2. **Request Ephemeral Credential:**
    * AI Agent invokes `deepsecure vault issue --scope="<relevant_scope>" --ttl="<short_ttl>"` (***no `--local` flag***) (or equivalent library function).
    * The request still implicitly uses the Agent's long-term `Agent ID` and associated local private key.
3. **Credential Issuance (Involves Backend):**
    * `VaultClient` (local) generates a new X25519 `Ephemeral Public Key (Agent)` and `Ephemeral Private Key (Agent)`.
    * `VaultClient` signs the `Ephemeral Public Key (Agent)` using the Agent's long-term **local private key**.
    * `VaultClient` calls the **DeepSecure Backend API** (`POST /v1/vault/credentials`) sending the `Agent ID`, `Ephemeral Public Key (Agent)`, the **signature**, requested `scope`, and `ttl`.
    * **Backend Verification:**
        * Backend authenticates the CLI's API token.
        * Backend retrieves the Agent's long-term public key associated with the `Agent ID` from its database.
        * Backend **verifies the signature** on the `Ephemeral Public Key (Agent)`.
    * **Backend Issuance:**
        * If signature is valid, Backend generates a unique `Cred ID`.
        * Backend calculates `expires_at`.
        * Backend stores the credential record (Cred ID, Agent ID, Ephemeral Pub Key (Agent), scope, expiry, signature etc.) in its database.
    * **Backend Response:** Backend returns the official credential structure (containing `Cred ID`, `Agent ID`, `Ephemeral Public Key (Agent)`, `scope`, `expires_at`) to the `VaultClient`.
    * `VaultClient` returns the credential structure *and* the locally generated sensitive `Ephemeral Private Key (Agent)` to the AI Agent process. (Agent still gets its private key; backend never saw it).
4. **Agent Prepares Request:**
    * AI Agent receives credential details, holding `Ephemeral Private Key (Agent)` securely in memory.
    * AI Agent constructs the request for the Target.
5. **Agent Sends Request with Credential:**
    * AI Agent sends the request to the Target.
    * The **credential structure** received from the backend (containing `Cred ID`, `Agent ID`, `Ephemeral Public Key (Agent)`, etc.) is included (e.g., in an `Authorization` header).
    * **`Ephemeral Private Key (Agent)` is NOT sent.**
6. **Target Verification (Via Backend):**
    * The Target's Verification Component intercepts the request.
    * Extracts the `Cred ID` (and potentially other parts of the credential structure).
    * **Calls the DeepSecure Backend API** (e.g., `GET /v1/vault/credentials/{cred_id}/verify` or similar) to validate the `Cred ID`.
    * **Backend performs checks:** Is the `Cred ID` valid? Is it expired? Is it revoked? Does the associated `scope` permit the intended action by the Target?
    * Backend responds to the Target (Valid/Invalid/Unauthorized Scope).
7. **Secure Channel Establishment (If Verification OK):**
    * Verification Component generates its *own* ephemeral X25519 key pair.
    * Computes a shared secret using its *new ephemeral private key* and the Agent's received `Ephemeral Public Key (Agent)` (from the credential structure originally sent by the Agent).
    * Sends its *new ephemeral public key* back to the AI Agent.
8. **Agent Completes Secure Channel:**
    * AI Agent receives the Target's ephemeral public key.
    * Computes the *same* shared secret using *its* in-memory `Ephemeral Private Key (Agent)` and the Target's public key.
9. **Perform Action Securely:**
    * AI Agent and Target Application use the shared secret for encrypted communication of the payload.
    * Target Application processes the authenticated and authorized request.
10. **Session Teardown:**
    * Upon completion, both Agent and Target discard their ephemeral keys and the shared secret.
    * The `Cred ID` expires naturally or can be revoked via a backend API call (`deepsecure vault revoke cred-xyz...` which would call the backend).

## Scenario 1.3: Modified AI Agent Accessing Internal Business Application/Database (With CredService Backend Integration & Explicit Agent Management)

This flow describes how an AI agent uses credentials obtained via the DeepSecure backend (`credservice`) to authenticate and establish a secure channel with an internal target system, after the agent has been explicitly registered using the `deepsecure agent register` command.

**Actors:**

*   **AI Agent:** The process needing access.
*   **DeepSecure CLI/Client Libraries:** Helper tools/libraries, including `deepsecure agent` and `deepsecure vault` functionality.
*   **DeepSecure Backend (`credservice`):** The central service responsible for agent registration, credential issuance, and verification.
*   **Target Application/Database:** The internal resource (e.g., API, database).
*   **Verification Component:** Logic at the Target, interacts with the DeepSecure Backend.

**Sequence Flow:**

**Phase 1: Agent Onboarding/Registration (One-time or infrequent, explicit step)**

1.  **Decision to Onboard Agent:** An administrator or an automated provisioning process decides a new AI Agent needs to be managed by DeepSecure.
2.  **Explicit Agent Registration:**
    *   An administrator (or provisioning script) uses the `deepsecure-cli` (or a client library calling the equivalent backend API).
    *   **Option A (CLI generates keys):**
        `deepsecure agent register --name "ReportingAgent" --description "Generates daily sales reports"`
        *   The CLI (via `IdentityManager`) generates a new Ed25519 key pair locally.
        *   The CLI (via `AgentClient`) calls the **DeepSecure Backend API** (`POST /api/v1/agents/`) sending the *newly generated public key*, name, and description.
        *   The Backend creates the agent record, generates a canonical `agent_id`, and stores the public key and metadata.
        *   The Backend returns the new `agent_id` and other details.
        *   The CLI (via `IdentityManager`) saves the local key pair (private and public) associated with the `agent_id` received from the backend (e.g., in `~/.deepsecure/identities/<backend_agent_id>.json`).
    *   **Option B (User provides public key):**
        `deepsecure agent register --name "DataProcessor" --public-key /path/to/agent_pub.key`
        *   The user/script provides an existing public key. The corresponding private key is managed externally by the user/agent.
        *   The CLI (via `AgentClient`) calls the **DeepSecure Backend API** (`POST /api/v1/agents/`) sending the *provided public key*, name, etc.
        *   The Backend creates the agent record, generates/assigns an `agent_id`.
        *   The Backend returns the `agent_id`.
        *   No local private key is stored by the CLI in this case.
        *   **Result:** The AI Agent is now officially registered in `credservice`, and its long-term public key is known to the backend. If keys were generated by the CLI, the agent's execution environment has access to its corresponding private key and knows its `<registered_agent_id>`.

---

**Phase 2: Ephemeral Credential Issuance and Resource Access (Operational, happens repeatedly)**

3.  **Need Arises:** AI Agent logic determines the need to access the Target Application/Database.
4.  **Request Ephemeral Credential (Agent knows its `agent_id`):**
    *   AI Agent invokes `deepsecure vault issue --agent-id "<registered_agent_id>" --scope="<relevant_scope>" --ttl="<short_ttl>"` (or equivalent library function, now explicitly providing its `agent_id`).
    *   The local `VaultClient` needs access to the agent's long-term private key associated with `<registered_agent_id>` (stored locally or provisioned).
5.  **Credential Issuance (Involves Backend):**
    *   `VaultClient` (local) generates a new X25519 `Ephemeral Public Key (Agent)` and `Ephemeral Private Key (Agent)`.
    *   `VaultClient` signs the `Ephemeral Public Key (Agent)` using the Agent's long-term **local private key**.
    *   `VaultClient` calls the **DeepSecure Backend API** (`POST /v1/vault/credentials`) sending the `<registered_agent_id>`, `Ephemeral Public Key (Agent)`, the **signature**, requested `scope`, and `ttl`.
    *   **Backend Verification:**
        *   Backend authenticates the CLI's API token.
        *   Backend retrieves the Agent's long-term public key using the provided `<registered_agent_id>` (agent *must* exist and be active).
        *   Backend **verifies the signature** on the `Ephemeral Public Key (Agent)`.
    *   **Backend Issuance:**
        *   If signature is valid, Backend generates a unique `Cred ID`, calculates `expires_at`, and stores the credential record.
    *   **Backend Response:** Backend returns the official credential structure to the `VaultClient`.
    *   `VaultClient` returns the credential structure and the locally generated `Ephemeral Private Key (Agent)` to the AI Agent process.
6.  **Agent Prepares Request:**
    *   AI Agent receives credential details, holding `Ephemeral Private Key (Agent)` securely in memory.
    *   AI Agent constructs the request for the Target.
7.  **Agent Sends Request with Credential:**
    *   AI Agent sends the request to the Target with the **credential structure**.
    *   **`Ephemeral Private Key (Agent)` is NOT sent.**
8.  **Target Verification (Via Backend):**
    *   Target's Verification Component extracts `Cred ID`.
    *   Calls the **DeepSecure Backend API** (e.g., `GET /v1/vault/credentials/{cred_id}/verify`) to validate.
    *   Backend performs checks and responds to the Target.
9.  **Secure Channel Establishment (If Verification OK):**
    *   Verification Component (Target) generates its own ephemeral X25519 key pair.
    *   Computes shared secret using its new ephemeral private key and Agent's `Ephemeral Public Key (Agent)`.
    *   Sends its new ephemeral public key back to the AI Agent.
10. **Agent Completes Secure Channel:**
    *   AI Agent computes the same shared secret using its `Ephemeral Private Key (Agent)` and Target's public key.
11. **Perform Action Securely:**
    *   Encrypted communication using the shared secret.
12. **Session Teardown:**
    *   Ephemeral keys and shared secret are discarded.
    *   `Cred ID` expires or can be revoked via backend.

## Scenario 2: AI Agent Communication (Multi-Agent Orchestration)

This flow describes how an AI agent (Agent A) uses credentials issued locally (`--local` flag) to authenticate and establish a secure communication channel with another AI agent (Agent B) within an orchestration framework (e.g., CrewAI, LangGraph).

**Assumptions:**

* Agents can communicate directly or via the orchestration framework (which acts as a message passer).
* Each agent has access to a trusted source for the long-term public keys of other agents it needs to interact with (e.g., a shared directory, a configuration service, or fetched from a potential DeepSecure backend).
* The scope assigned to the credential defines the permissions Agent A has when interacting with Agent B for this specific task.

**Actors:**

* **Agent A:** The initiating agent needing a task performed.
* **Agent B:** The target agent performing the task.
* **DeepSecure CLI/VaultClient (Local):** The helper tool/library running alongside *each* Agent.
* **(Optional) Orchestration Framework:** May route messages between agents.

**Sequence Flow (Agent A -> Agent B):**

1. **Need Arises:** Agent A's logic determines it needs Agent B to perform a specific task (e.g., summarize a document, execute a specific tool).
2. **Request Ephemeral Credential (Agent A):**
    * Agent A invokes `deepsecure vault issue --scope="agent:AgentB:task:summarize" --ttl="120s" --local` (or equivalent library function), requesting a scope relevant to the interaction with Agent B.
    * The request implicitly uses Agent A's long-term `Agent ID (A)` and associated local private key.
3. **Local Credential Issuance (Agent A):**
    * `VaultClient` generates a unique `Cred ID`.
    * `VaultClient` generates Agent A's new X25519 `Ephemeral Public Key (A)` and `Ephemeral Private Key (A)`.
    * `VaultClient` signs `Ephemeral Public Key (A)` using Agent A's long-term private key.
    * `VaultClient` packages `Cred ID`, `Agent ID (A)`, `Ephemeral Public Key (A)`, signature, `scope`, `expires_at` into Agent A's credential structure.
    * `VaultClient` returns the credential structure and the sensitive `Ephemeral Private Key (A)` to the Agent A process.
4. **Agent A Prepares Request:**
    * Agent A receives its credential details, holding `Ephemeral Private Key (A)` securely in memory.
    * Agent A constructs the task request message for Agent B (e.g., "Summarize this text: ...").
5. **Agent A Sends Request with Credential:**
    * Agent A sends the task request message *and* its **credential structure** (containing `Cred ID`, `Agent ID (A)`, `Ephemeral Public Key (A)`, signature, etc.) to Agent B (potentially routed via the orchestration framework).
    * **`Ephemeral Private Key (A)` is NOT sent.**
6. **Agent B Verification:**
    * Agent B receives the message and Agent A's credential structure.
    * Agent B performs checks:
        * Expiry (`expires_at`).
        * Revocation status (checks `Cred ID` against its revocation information source).
        * Signature verification:
            * Looks up Agent A's long-term public key using `Agent ID (A)` from its trusted source.
            * Verifies the signature on `Ephemeral Public Key (A)`.
        * Authorization (checks `scope` against the requested task).
7. **Secure Channel Establishment (Agent B Side - If Verification OK):**
    * Agent B generates its *own* ephemeral X25519 key pair: `Ephemeral Public Key (B)` and `Ephemeral Private Key (B)`.
    * Agent B computes a shared secret using *its* `Ephemeral Private Key (B)` and Agent A's received `Ephemeral Public Key (A)`.
    * Agent B sends its `Ephemeral Public Key (B)` back to Agent A (e.g., in an acknowledgment message, potentially via the framework).
8. **Secure Channel Establishment (Agent A Side):**
    * Agent A receives Agent B's `Ephemeral Public Key (B)`.
    * Agent A computes the *same* shared secret using *its* in-memory `Ephemeral Private Key (A)` and Agent B's `Ephemeral Public Key (B)`.
9. **Perform Task Securely:**
    * Agent A and Agent B now use the shared secret to encrypt/decrypt the detailed task instructions, any sensitive data involved in the task, and the final results using symmetric encryption (e.g., AES-GCM).
    * Agent B performs the requested task using the decrypted instructions/data.
    * Agent B encrypts the results and sends them back to Agent A.
10. **Agent A Receives Results:**
    * Agent A decrypts the results received from Agent B.
11. **Session Teardown:**
    * Upon completion of the interaction, both Agent A and Agent B discard their respective ephemeral key pairs (`Ephemeral Private Key (A)`, `Ephemeral Private Key (B)`) and the shared secret.
    * The `Cred ID` expires naturally or can be revoked.

## Scenario 2.2: AI Agent Communication (Multi-Agent Orchestration) (With Backend Integration)

This flow describes how an AI agent (Agent A) uses credentials obtained via the DeepSecure backend to authenticate and establish a secure communication channel with another AI agent (Agent B) within an orchestration framework.

**Assumptions:**

* Agents can communicate directly or via the orchestration framework.
* The DeepSecure backend serves as the trusted source for agents' long-term public keys.
* The scope assigned by the backend credential defines the permissions Agent A has when interacting with Agent B.

**Actors:**

* **Agent A:** The initiating agent needing a task performed.
* **Agent B:** The target agent performing the task.
* **DeepSecure CLI/VaultClient (Local):** Helper tool/library running alongside *each* Agent.
* **DeepSecure Backend:** The central service responsible for issuance and verification.
* **(Optional) Orchestration Framework:** May route messages between agents.

**Sequence Flow (Agent A -> Agent B with Backend):**

1. **Need Arises:** Agent A's logic determines it needs Agent B to perform a specific task.
2. **Request Ephemeral Credential (Agent A):**
    * Agent A invokes `deepsecure vault issue --scope=\"<relevant_scope_for_B>\" --ttl=\"<short_ttl>\"` (***no `--local` flag***) (or equivalent library function).
    * The request implicitly uses Agent A's long-term `Agent ID (A)` and associated local private key.
3. **Credential Issuance (Involves Backend):**
    * `VaultClient` (local to Agent A) generates a new X25519 `Ephemeral Public Key (A)` and `Ephemeral Private Key (A)`.
    * `VaultClient` signs `Ephemeral Public Key (A)` using Agent A's long-term **local private key**.
    * `VaultClient` calls the **DeepSecure Backend API** (`POST /v1/vault/credentials`) sending `Agent ID (A)`, `Ephemeral Public Key (A)`, the **signature**, requested `scope`, and `ttl`.
    * **Backend Verification:**
        * Backend authenticates the CLI's API token.
        * Backend retrieves Agent A's long-term public key using `Agent ID (A)`.
        * Backend **verifies the signature** on `Ephemeral Public Key (A)`.
    * **Backend Issuance:**
        * If signature is valid, Backend generates a unique `Cred ID`.
        * Backend calculates `expires_at`.
        * Backend stores the credential record in its database.
    * **Backend Response:** Backend returns the official credential structure (containing `Cred ID`, `Agent ID (A)`, `Ephemeral Public Key (A)`, `scope`, `expires_at`) to Agent A's `VaultClient`.
    * `VaultClient` returns the credential structure *and* the locally generated sensitive `Ephemeral Private Key (A)` to the Agent A process.
4. **Agent A Prepares Request:**
    * Agent A receives its credential details, holding `Ephemeral Private Key (A)` securely in memory.
    * Agent A constructs the task request message for Agent B.
5. **Agent A Sends Request with Credential:**
    * Agent A sends the task request message *and* its **credential structure** received from the backend to Agent B (potentially via the framework).
    * **`Ephemeral Private Key (A)` is NOT sent.**
6. **Agent B Verification (Via Backend):**
    * Agent B receives the message and Agent A's credential structure.
    * Agent B extracts the `Cred ID`.
    * **Agent B calls the DeepSecure Backend API** (e.g., `GET /v1/vault/credentials/{cred_id}/verify`) to validate the `Cred ID`.
    * **Backend performs checks:** Is the `Cred ID` valid? Is it expired? Is it revoked? Does the associated `scope` permit the interaction requested by Agent A?
    * Backend responds to Agent B (Valid/Invalid/Unauthorized Scope).
7. **Secure Channel Establishment (Agent B Side - If Verification OK):**
    * Agent B generates its *own* ephemeral X25519 key pair: `Ephemeral Public Key (B)` and `Ephemeral Private Key (B)`.
    * Agent B computes a shared secret using *its* `Ephemeral Private Key (B)` and Agent A's `Ephemeral Public Key (A)` (from the credential structure).
    * Agent B sends its `Ephemeral Public Key (B)` back to Agent A.
8. **Secure Channel Establishment (Agent A Side):**
    * Agent A receives Agent B's `Ephemeral Public Key (B)`.
    * Agent A computes the *same* shared secret using *its* in-memory `Ephemeral Private Key (A)` and Agent B's `Ephemeral Public Key (B)`.
9. **Perform Task Securely:**
    * Agent A and Agent B use the shared secret for encrypted communication of task details and results.
    * Agent B performs the task.
    * Agent B encrypts results and sends them to Agent A.
10. **Agent A Receives Results:**
    * Agent A decrypts the results.
11. **Session Teardown:**
    * Both agents discard their ephemeral keys and the shared secret.
    * The `Cred ID` expires naturally or can be revoked via a backend API call.
