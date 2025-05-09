# DeepSecure CLI Implementation To-Do and Discussion

This file captures the status and decisions made during the backend implementation.

## Implementation Status (as of last summary)

> **Assistant:**
> Okay, let's break down the "Reconciled Backend Integration Plan" and map it against the work completed so far in the `credservice` backend.
>
> **Fully Implemented Steps So Far:**
>
> Based on the plan provided:
>
> * **Phase 1, Step 1: Project Setup:**
>   * Initialize FastAPI project: Done.
>   * Choose and configure database (PostgreSQL/SQLite): Done.
>   * Set up ORM (SQLAlchemy): Done.
>   * Configure database migrations (Alembic): Done.
> * **Phase 1, Step 2: Define Data Models (Partial):**
>   * Agents Table: Done.
>   * Define corresponding Pydantic models for Agents: Done.
> * **Phase 1, Step 5: Testing (Partial):**
>   * Create unit and integration tests for the backend API endpoints for basic Agent registration and retrieval: Done.
>
> *(Note: While implementing the basic Agent endpoints wasn't explicitly listed under Step 4 of *this specific plan*, they were a necessary foundational step completed during our recent work, covering parts of Step 2 and Step 5 for Agents).*
>
> ---
>
> **Remaining Steps (Based on the Plan):**
>
> * **Phase 1, Step 2: Define Data Models (Remaining):**
>   * Finalize and implement Credentials Table model.
>   * Define corresponding Pydantic models for Credentials.
> * **Phase 1, Step 3: Implement Authentication/Authorization:**
>   * Implement middleware/dependency for API token verification.
>   * Define authorization logic.
>   * (Self-Correction): The plan implies a simple bearer token, whereas deps.py currently sets up OAuth2PasswordBearer pointing to a non-existent login endpoint. This needs clarification and implementation alignment.
> * **Phase 1, Step 4: Implement API Endpoints:**
>   * Implement POST /v1/vault/credentials (Issue) - including signature verification logic.
>   * Implement POST /v1/vault/credentials/{credential_id}/revoke (Revoke).
>   * Implement POST /v1/vault/agents/{agent_id}/rotate-identity (Rotate Long-Term Key).
>   * Implement GET /v1/vault/credentials/{credential_id}/verify (Verification).
>   * (Align API prefixes: Plan uses /v1/vault/, current code uses /api/v1/ - decide and make consistent).
> * **Phase 1, Step 5: Testing (Remaining):**
>   * Write tests for all implemented Vault API endpoints (Issue, Revoke, Rotate, Verify).
>   * Write tests for authentication/authorization flows.
> * **Phase 2: CLI Client Integration (All Steps):**
>   * Update VaultClient methods to interact with the backend API.
>   * Update BaseClient (_request) to handle backend API token authentication.
>   * Write/update CLI tests to mock backend interactions.

## Authentication Decision Discussion

**User:**
> Ok. Let's go to the step 3: Authentication & Authorization:
> Implement the chosen API token verification mechanism (middleware or dependency).
> Decision Needed: Clarify if using simple bearer token or OAuth2 flow (current deps.py implies OAuth2).
> Implement token generation/login endpoint if required by the chosen mechanism.
> Secure the vault API endpoints.

> **Assistant:**
> Okay, let's tackle **Step 3: Authentication & Authorization**.
>
> **1. Decision on Mechanism:**
>
> You're right, the plan mentions a simple "API token" verification, while `deps.py` had boilerplate for OAuth2/JWT. For integrating the CLI client initially, a simple, static API key sent as a Bearer token is the most straightforward approach.
>
> * **Decision:** We will implement a simple API Key authentication using the `Authorization: Bearer <YOUR_STATIC_TOKEN>` header. We will defer the OAuth2/JWT flow for now. This means we **do not** need to implement a `/login` endpoint at this stage.
>
> *(Implementation steps followed: Added BACKEND_API_TOKEN setting, implemented verify_api_key dependency, secured endpoints)*

**User:**
> It seems we removed the OAuth2/JWT from deps.py and not implementing a /login endpoint at this stage? Why and what does this mean for a developer using deepsecure-cli

> **Assistant:**
> You are correct. We opted to remove the specific OAuth2/JWT code from `deps.py` for now and did not implement a `/login` endpoint **for this initial phase** of backend integration.
>
> **Why?**
>
> 1. **Simplicity for CLI-to-Backend Communication:** ... a pre-configured, static API key (sent as a Bearer token) is a significantly simpler and faster mechanism...
> 2. **Focus on Core Vault Logic:** ... focus on implementing and testing the core vault functionality ... without getting bogged down in the complexities of a full identity provider setup.
> 3. **Deferral, Not Permanent Removal:** ... doesn't mean OAuth2/JWT can't be added later...
>
> **What does this mean for a developer using `deepsecure-cli`?**
>
> 1. **Configuration:** ... CLI needs to be configured with the static `BACKEND_API_TOKEN`...
> 2. **Client-Side Logic:** ... `BaseClient._request` method ... needs to be updated to read this configured token and include it in the `Authorization` header...
> 3. **No Session Management (via token):** Authentication is based purely on presenting the correct static token with each request...
> 4. **Security:** The security relies on keeping the static `BACKEND_API_TOKEN` confidential...
