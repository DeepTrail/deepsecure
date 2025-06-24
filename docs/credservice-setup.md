# Credservice Backend Setup Guide

Welcome! This guide explains how to set up the `credservice` backend locally. The `credservice` is the heart of DeepSecure, acting as the centralized access orchestrator and policy engine. Running it is essential for local development and for using the `deepsecure` CLI and SDK.

## Quickstart: Running the Service

Follow these steps from the root of the repository to get the backend service running quickly.

1.  **Create the Database (One-Time Setup)**
    Before starting the service for the first time, you need to create the PostgreSQL database.
    ```bash
    # This command creates the 'deepsecure-db' database. You only need to run this once.
    createdb deepsecure-db
    ```

2.  **Set Up Local Environment Variables**
    Ensure you have `direnv` installed and enabled for this directory. This will automatically configure your client.
    ```bash
    # Run this once if you haven't already
    direnv allow .
    ```

3.  **Start the Backend Services**
    This command will build the Docker images and start the `credservice` and `db` containers in the background.
    ```bash
    docker compose -f credservice/docker-compose.yml up -d --build
    ```

4.  **Verify the Service is Running**
    You can check that the service is active by sending a request to its root endpoint.
    ```bash
    # You should see a JSON response like {"message": "Welcome to DeepSecure CredService"}
    curl http://127.0.0.1:8000
    ```

Your local `credservice` is now running, and your `deepsecure` client is configured to communicate with it. You're ready to develop! For a deeper understanding of how this setup works, please read the guide below.

---

## Developer Guide: Understanding the Setup

This section provides a detailed explanation of the components and configuration involved in the local development environment.

### The Local Environment: `.envrc` vs. `crederservice/.env`

When you look at the repository, you'll find two key environment files. It's crucial to understand their different roles:

1.  **`/.envrc` (in the root directory)**
    *   **Purpose:** Configures your **local shell** (the client).
    *   **How it works:** This file is designed for tools like `direnv`. When you `cd` into the project root, `direnv` automatically exports these variables into your shell. This is how the `deepsecure` CLI and SDK know how to contact the backend service.
    *   **What it contains:** The URL of the `credservice` and the low-privilege token for the client.

2.  **`crederservice/.env`**
    *   **Purpose:** Configures the **Docker container** (the server).
    *   **How it works:** This file is read exclusively by `docker compose`. When you run `docker compose up`, it injects these variables into the running `credservice` container. Your local shell never sees these variables directly.
    *   **What it contains:** The high-privilege administrative token for the service and the connection string for the database.

This separation is standard practice and ensures that server-side configuration, which may be more sensitive, does not leak into the client environment.

### Configuring the Database Connection

The most critical variable in `crederservice/.env` is the `DATABASE_URL`. You will very likely need to edit the default value to match your local PostgreSQL setup.

Here is the default value:
`DATABASE_URL=postgresql://imaxxs@localhost:5432/deepsecure-db`

Let's break down this connection string so you can adapt it for your system:
`postgresql://<user>:<password>@<host>:<port>/<database_name>`

*   **`<user>`**: Replace `imaxxs` with your local PostgreSQL username.
*   **`<password>`**: The provided example does not include a password, which assumes your local database is configured for password-less `trust` authentication. If your setup requires a password, add it between the user and the `@` symbol (e.g., `...://myuser:mypassword@...`).
*   **`<host>`**: `localhost` is correct for almost all local development setups.
*   **`<port>`**: `5432` is the standard default port for PostgreSQL.
*   **`<database_name>`**: Before starting the service, you must ensure a database with this name (e.g., `deepsecure-db`) has been created in your PostgreSQL instance.

By correctly configuring this URL, you enable the `credservice` running inside Docker to connect to the PostgreSQL database running on your host machine.

### The Two-Token Security Model: Admin vs. User

You've noticed two different tokens: `BACKEND_API_TOKEN` and `DEEPSECURE_CREDSERVICE_API_TOKEN`. This is not a mistake; it's a deliberate security design that separates administrative access from user access.

*   **`BACKEND_API_TOKEN` (The Server's "Master Key")**
    *   **Role:** Administrator.
    *   **Usage:** This is a high-privilege token used by the `credservice` to protect its own administrative endpoints. It's defined in `crederservice/.env` and is only known to the backend itself. Think of it as the key to the entire building.

*   **`DEEPSECURE_CREDSERVICE_API_TOKEN` (The Client's "User Key")**
    *   **Role:** User / Agent.
    *   **Usage:** This is a low-privilege token used by the `deepsecure` CLI and SDK to authenticate as a regular client. It's defined in `/.envrc`. It can't be used for administrative tasks. Think of it as a keycard that only opens specific rooms you're allowed into.

This two-token system is a robust security practice that enforces the **Principle of Least Privilege**. By separating roles, we limit the potential damage if a client-side token is compromised. For more information on this concept, see these [Role-Based Access Control Best Practices](https://www.cerbos.dev/blog/role-based-access-control-best-practices).

### The Role of `alembic.ini`

Alembic is a database migration tool for SQLAlchemy. You might wonder why its configuration file, `alembic.ini`, is committed to the repository.

The `alembic.ini` file in this project is a **template**. It does *not* contain sensitive information like the database password. Instead, it's configured to read the `DATABASE_URL` from the environment variables that Docker Compose provides. This is a secure pattern that avoids hardcoding secrets in version-controlled files.

### The Complete Workflow (How It All Fits Together)

Here's how the pieces connect when you run a command locally:

1.  You open a terminal and `cd` into the `deepsecure` root directory.
2.  `direnv` (via `.envrc`) automatically exports `DEEPSECURE_CREDSERVICE_URL` and `DEEPSECURE_CREDSERVICE_API_TOKEN` into your shell environment.
3.  You run `docker compose -f credservice/docker-compose.yml up -d`.
4.  Docker Compose reads `crederservice/.env` and starts the `credservice` and `db` containers. It injects `BACKEND_API_TOKEN` and `DATABASE_URL` into the `credservice` container's environment.
5.  The `credservice` application starts inside Docker, connects to the database using the `DATABASE_URL`, and protects its endpoints using the `BACKEND_API_TOKEN`.
6.  You run a CLI command, like `deepsecure agent list`.
7.  The CLI, configured by your shell's environment variables, sends a request to `http://127.0.0.1:8000/api/v1/agents` with the header `Authorization: Bearer DEFAULT_QUICKSTART_TOKEN`.
8.  The `credservice` receives the request, validates the token, and returns the list of agents. 