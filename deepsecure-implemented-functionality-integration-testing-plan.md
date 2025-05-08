# Current Implementation and Integration Testing Plan

## Summary of Implemented Functionality

The `deepsecure-cli` project now includes a functional backend service (`credservice`) built with FastAPI, integrated with the core CLI logic for vault operations.

### Backend (`credservice`)

* **Core Structure:** FastAPI application with organized modules for models, schemas, CRUD operations, API endpoints, configuration, and database interactions.
* **Database:** Configured to use SQLAlchemy with Alembic for migrations. Currently uses SQLite for testing.
* **Agent Management:**
  * `Agent` model storing `agent_id`, `current_public_key` (Ed25519 bytes), `created_at`.
  * `Agent` schemas for API validation and response.
  * CRUD operations for agents, including SSH public key parsing.
  * API endpoints (`/api/v1/agents/`) for agent registration and retrieval.
* **Credential Management:**
  * `Credential` model storing `credential_id`, `agent_id`, `ephemeral_public_key` (X25519 bytes), `signature` (Ed25519 bytes), `scope`, `origin_context`, `issued_at`, `expires_at`, `revoked_at`.
  * `Credential` schemas for API validation and response (issue, revoke, verify).
  * CRUD operations for creating, retrieving, and revoking credentials.
* **Vault API Endpoints (`/api/v1/vault/`):**
  * `POST /credentials`: Issues a new credential after verifying the signature of the ephemeral public key against the registered agent's long-term key.
  * `POST /credentials/{credential_id}/revoke`: Revokes a credential by setting the `revoked_at` timestamp.
  * `POST /agents/{agent_id}/rotate-identity`: Updates the agent's `current_public_key`.
  * `GET /credentials/{credential_id}/verify`: Checks and returns the validity status (valid, expired, revoked, not_found) of a credential.
* **Authentication:** Implemented simple static API Key authentication (`Authorization: Bearer <token>`) for the issue, revoke, and rotate endpoints via a FastAPI dependency.
* **Testing:** Includes unit/integration tests (`pytest`) for backend models, CRUD operations, and API endpoints (including authentication checks and vault logic).
* **Logging:** Basic request/response logging middleware and application-level logging are in place.

### CLI Client (`deepsecure-cli`)

* **`BaseClient`:** Updated to handle actual HTTP requests (`requests` library), load backend URL/token from environment variables (`DEEPSECURE_CREDSERVICE_URL`, `DEEPSECURE_CREDSERVICE_API_TOKEN`), and conditionally add the `Authorization` header for backend requests.
* **`VaultClient`:**
  * `issue_credential`: Modified to call the backend `POST /api/v1/vault/credentials` endpoint when `local_only=False`. Handles preparing the payload (including signature) and processing the response. Falls back to local-only mode if the backend is unavailable or `local_only=True`. Returns the credential including the ephemeral private key.
  * `revoke_credential`: Modified to call the backend `POST /api/v1/vault/credentials/{cred_id}/revoke` endpoint when `local_only=False`. Updates the local revocation list *only if* the backend confirms revocation or if `local_only=True`.
  * `rotate_credential`: Modified to perform the local identity file update *first*, then calls the backend `POST /api/v1/vault/agents/{agent_id}/rotate-identity` endpoint to notify it of the new key if `local_only=False`.
* **CLI Commands (`commands/vault.py`):** Updated `issue`, `revoke`, and `rotate` commands to call the corresponding `VaultClient` methods, handle potential `ApiError` or `VaultError` exceptions, and display appropriate output based on local vs. backend operations.
* **CLI Testing (`tests/commands/test_vault_local.py`):** Updated existing local tests and added new tests using `unittest.mock.patch` to simulate backend API calls and verify the correct requests are made and responses are handled when the `--local` flag is *not* used.

---

## Detailed Integration Testing Plan

This plan outlines steps to test the full integration between the CLI and the running backend service.

### Prerequisites

1. **Build/Install CLI:** Ensure the latest `deepsecure-cli` code is built and installed/available in the testing environment's PATH.
2. **Run Backend Service:** Start the `credservice` FastAPI application (e.g., using `uvicorn credservice.app.main:app --reload --port 8001`). Ensure it's using a known database (e.g., a clean `test.db` SQLite file).
3. **Configure Environment Variables:** Set the following environment variables for the shell where `deepsecure` CLI commands will be run:
    * `DEEPSECURE_CREDSERVICE_URL=http://localhost:8001` (or the correct host/port where the backend is running)
    * `DEEPSECURE_CREDSERVICE_API_TOKEN=your_chosen_static_token` (This value must be the **same value** as the `BACKEND_API_TOKEN` configured in the `credservice` backend's `.env` file or its environment).
4. **Clean State:** Start with an empty `~/.deepsecure/` directory (or ensure no conflicting identities/revocation lists exist) and a clean backend database.

### Test Cases

#### A. `vault issue` Command

1. **Scenario: Backend Issuance (Success)**
    * **Action:** Run `deepsecure vault issue --scope "int-test:backend-issue" --ttl 10m --output json`
    * **Verify CLI:**
        * Exit code is 0.
        * Output is valid JSON containing `credential_id`, `agent_id`, `scope`, `ephemeral_public_key`, `expires_at`, and crucially, `ephemeral_private_key`.
    * **Verify Local State:**
        * An identity file (`~/.deepsecure/identities/<agent_id>.json`) should be created for the new `agent_id`.
    * **Verify Backend State:**
        * Use `curl` or `requests` to call the backend's `GET /api/v1/vault/credentials/<credential_id>/verify` endpoint. Verify the response shows `is_valid: true`, `status: "valid"`, and matches the issued `scope` and `agent_id`.
        * (Optional) Query the backend database directly to confirm the record exists with correct details.

2. **Scenario: Local Issuance (`--local` flag)**
    * **Action:** Run `deepsecure vault issue --scope "int-test:local-issue" --ttl 1m --output json --local`
    * **Verify CLI:**
        * Exit code is 0.
        * Output is valid JSON containing all expected fields, including `ephemeral_private_key`. Let the generated ID be `local_cred_id`.
    * **Verify Local State:**
        * An identity file should be created.
    * **Verify Backend State:**
        * Call the backend's `GET /api/v1/vault/credentials/local_cred_id/verify` endpoint. Verify the response shows `status: "not_found"`.

3. **Scenario: Backend Issuance (Invalid Signature - Requires manual key manipulation)**
    * (Difficult to automate via CLI alone) This scenario was covered by backend unit tests.

4. **Scenario: Backend Issuance (Auth Failure)**
    * **Action:** Unset `DEEPSECURE_CREDSERVICE_API_TOKEN` env var. Run `deepsecure vault issue --scope "int-test:auth-fail" --ttl 1m`.
    * **Verify CLI:**
        * Exit code is non-zero.
        * Error message indicates an Authentication Error / Invalid API token (likely 401 from the backend).
    * **Verify Backend State:** No credential should be created.

#### B. `vault revoke` Command

1. **Scenario: Backend Revocation (Success)**
    * **Setup:** Issue a credential via the backend (like Step A.1). Get the `credential_id`.
    * **Action:** Run `deepsecure vault revoke --id <credential_id>`
    * **Verify CLI:**
        * Exit code is 0.
        * Success message indicates revocation processed.
    * **Verify Local State:**
        * The `credential_id` should be present in `~/.deepsecure/revoked_creds.json`.
    * **Verify Backend State:**
        * Call backend `GET /api/v1/vault/credentials/<credential_id>/verify`. Verify response shows `is_valid: false`, `status: "revoked"`.

2. **Scenario: Local Revocation (`--local` flag)**
    * **Setup:** Issue a credential via the backend (like Step A.1) OR locally (`--local`). Get the `credential_id`.
    * **Action:** Run `deepsecure vault revoke --id <credential_id> --local`
    * **Verify CLI:**
        * Exit code is 0.
        * Success message indicates local revocation.
    * **Verify Local State:**
        * The `credential_id` should be present in `~/.deepsecure/revoked_creds.json`.
    * **Verify Backend State (if issued via backend):**
        * Call backend `GET /api/v1/vault/credentials/<credential_id>/verify`. Verify response *still* shows `is_valid: true`, `status: "valid"` (backend was not contacted).

3. **Scenario: Backend Revocation (Not Found)**
    * **Action:** Run `deepsecure vault revoke --id "non-existent-cred"`
    * **Verify CLI:**
        * Exit code is non-zero.
        * Error message indicates credential not found (likely 404 from backend).
    * **Verify Local State:** Revocation list should not contain `"non-existent-cred"`.

4. **Scenario: Backend Revocation (Auth Failure)**
    * **Setup:** Issue a credential via the backend. Get `credential_id`. Unset `DEEPSECURE_CREDSERVICE_API_TOKEN`.
    * **Action:** Run `deepsecure vault revoke --id <credential_id>`
    * **Verify CLI:**
        * Exit code is non-zero.
        * Error message indicates an Authentication Error.
    * **Verify Backend State:** Credential should still be valid (`GET .../verify`).
    * **Verify Local State:** Revocation list should *not* contain the `credential_id`.

#### C. `vault rotate` Command

1. **Scenario: Backend Rotation Notification (Success)**
    * **Setup:** Issue a credential locally to ensure an identity file exists (`deepsecure vault issue --local --output json --scope setup --ttl 1m`). Extract `agent_id`. Get the initial public key from the identity file.
    * **Action:** Run `deepsecure vault rotate --agent-id <agent_id>`
    * **Verify CLI:**
        * Exit code is 0.
        * Success message indicates "Local rotation complete" and "Backend Notified: True".
    * **Verify Local State:**
        * Read the identity file for `<agent_id>`. Verify the `public_key`, `private_key`, and `rotated_at` fields have been updated/added. The public key should differ from the initial one.
    * **Verify Backend State:**
        * Call backend `GET /api/v1/agents/<agent_id>`. Verify the `current_public_key` in the response matches the *new* public key from the updated local identity file (note: backend returns SSH format, local file stores base64 - need to compare the underlying key).

2. **Scenario: Local Rotation (`--local` flag)**
    * **Setup:** Issue a credential locally. Extract `agent_id`. Get the initial public key.
    * **Action:** Run `deepsecure vault rotate --agent-id <agent_id> --local`
    * **Verify CLI:**
        * Exit code is 0.
        * Success message indicates "Local rotation complete" and "Backend Notified: False".
    * **Verify Local State:**
        * Identity file is updated (new keys, `rotated_at` timestamp).
    * **Verify Backend State:**
        * Call backend `GET /api/v1/agents/<agent_id>`. Verify the `current_public_key` still matches the *initial* public key.

3. **Scenario: Backend Rotation Notification (Auth Failure)**
    * **Setup:** Issue locally. Extract `agent_id`. Unset `DEEPSECURE_CREDSERVICE_API_TOKEN`.
    * **Action:** Run `deepsecure vault rotate --agent-id <agent_id>`
    * **Verify CLI:**
        * Exit code is non-zero.
        * Error message indicates Backend API error (likely 401).
    * **Verify Local State:** Identity file *should still be updated* because local rotation happens first.
    * **Verify Backend State:** Agent's key on backend should *not* have changed.

4. **Scenario: Backend Rotation Notification (Agent Not Found on Backend)**
    * **Setup:** Create an identity file *manually* in `~/.deepsecure/identities/` for an `agent_id` that does *not* exist in the backend DB.
    * **Action:** Run `deepsecure vault rotate --agent-id <manual_agent_id>`
    * **Verify CLI:**
        * Exit code is non-zero.
        * Error message indicates Backend API error (likely 404).
    * **Verify Local State:** The manual identity file should have been updated locally.

### Cleanup

* Stop the backend service.
* Remove the `~/.deepsecure` directory.
* Remove the test database file (`test.db`).
* Unset environment variables.
