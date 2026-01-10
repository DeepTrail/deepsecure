# DeepSecure Web Bot Authentication: Implementation Plan

This document outlines the phased implementation plan for integrating Web Bot Authentication via HTTP Message Signatures (RFC 9421) into the DeepSecure platform.

**Related Document:** [Architecture Proposal](web-bot-authentication-architecture.md)

---

## Phase 1: Control Plane Foundation

**Goal:** Establish the public key infrastructure required for decentralized, third-party verification of agent identities.

### Task 1.1: Create New Endpoint in `deeptrail-control`
*   **Objective:** Create the public-facing `.well-known` endpoint for public key discovery.
*   **Files to Modify:**
    *   `deeptrail-control/app/main.py`: To register the new router for root-level endpoints.
    *   `deeptrail-control/app/api/v1/api.py`: To include the new router.
    *   Create `deeptrail-control/app/api/well_known.py`: To house the logic for the new endpoint.
*   **Details:**
    *   The endpoint will be `GET /.well-known/http-signatures/{agent_id}.json`.
    *   It must be publicly accessible without authentication.

### Task 1.2: Implement Public Key Retrieval Logic
*   **Objective:** Connect the new endpoint to the data layer to serve the correct public key.
*   **Files to Modify:**
    *   `deeptrail-control/app/crud/crud_agent.py`: Add a new method to retrieve an agent by its ID and select its public key.
    *   `deeptrail-control/app/api/well_known.py`: Implement the endpoint logic to call the new CRUD method and format the response.
*   **Details:**
    *   The response must conform to the `draft-meunier-http-message-signatures-directory` JSON structure.

### Task 1.3: Phase 1 Testing
*   **Objective:** Ensure the new endpoint is reliable and correct.
*   **File to Create:** `deeptrail-control/tests/api/test_well_known.py`
*   **Details:**
    *   Write unit tests for the new `crud_agent` method.
    *   Write integration tests for the endpoint, covering success cases (valid agent ID), failure cases (invalid agent ID), and validating the response schema.

---

## Phase 2: SDK and CLI Integration

**Goal:** Empower developers to have their agents sign requests and provide them with the tools to manage and debug this functionality.

### Task 2.1: Add SDK Dependency
*   **Objective:** Incorporate a standard library for handling HTTP Message Signatures.
*   **File to Modify:** `pyproject.toml` (and subsequently `requirements/base.txt`).
*   **Details:** Add the `http-message-signatures` Python library as a core dependency.

### Task 2.2: Implement SDK Signing Middleware
*   **Objective:** Automatically sign outgoing requests from the agent.
*   **Files to Modify:**
    *   `deepsecure/_core/client.py`: To integrate the new signing transport.
    *   Create `deepsecure/_core/signing.py`: To contain the `HttpxAuth` transport logic.
*   **Details:**
    *   Create a custom `httpx.Auth` class that uses the agent's private key (from `IdentityManager`) to generate `Signature` and `Signature-Input` headers.
    *   The `DeepSecureClient` will be updated to use this signing mechanism, controlled by a new `sign_external_requests=True` flag during initialization.

### Task 2.3: Implement CLI Command
*   **Objective:** Provide a simple way for developers to inspect an agent's public key in the correct format.
*   **File to Modify:** `deepsecure/commands/agent.py`.
*   **Details:**
    *   Add a new command: `deepsecure agent get-key --agent-id <id> --format web-bot-auth`.
    *   This command will fetch the agent's details and format the public key into the standard Web Bot Auth JSON structure.

### Task 2.4: Phase 2 Testing
*   **Objective:** Verify that the signing logic is correct and the CLI command works as expected.
*   **Files to Create/Modify:**
    *   `tests/_core/test_signing.py`: To test the request signing middleware.
    *   `tests/commands/test_agent.py`: To add tests for the new CLI command.
*   **Details:**
    *   Unit tests should ensure signatures are generated correctly for different HTTP methods and headers.
    *   CLI tests will verify the command's output format and accuracy.

---

## Phase 3: End-to-End Validation and Documentation

**Goal:** Ensure the feature is robust, easy to understand, and ready for adoption by developers.

### Task 3.1: Create End-to-End Demo
*   **Objective:** Demonstrate the complete signing and verification flow in a practical example.
*   **File to Create:** `examples/13_web_bot_authentication_demo.py`.
*   **Details:**
    *   The script will feature a mock web server that receives signed requests.
    *   The mock server will perform the verification step by fetching the public key from the live `deeptrail-control` endpoint.
    *   The demo will show the full lifecycle: Agent signs -> Server receives -> Server fetches key -> Server verifies.

### Task 3.2: Write Comprehensive Documentation
*   **Objective:** Create clear, user-friendly documentation for the new feature.
*   **File to Create:** `docs/guides/web-bot-authentication.md`.
*   **Details:**
    *   Explain the purpose and benefits of Web Bot Authentication.
    *   Provide a step-by-step guide on how to enable request signing in the DeepSecure SDK.
    *   Include code snippets (e.g., Python, JavaScript) showing how an external service can implement the verification logic.

### Task 3.3: Update CLI Reference
*   **Objective:** Keep the CLI documentation current.
*   **File to Modify:** `docs/cli_reference.md`.
*   **Details:** Add the new `deepsecure agent get-key` command, its arguments, and an example of its output to the official CLI reference guide.
