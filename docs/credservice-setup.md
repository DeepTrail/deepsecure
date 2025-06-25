# Credservice Backend Setup Guide

Welcome! This guide explains how to set up the `credservice` backend locally. The `credservice` is the heart of DeepSecure, acting as the centralized access orchestrator and policy engine. Running it is essential for local development and for using the `deepsecure` CLI and SDK.

## Quickstart: Running the Service

Follow these steps from the root of the repository to get the backend service running quickly.

1.  **Start the Backend Services**
    This command will build the Docker images and start the `credservice` and `db` containers in the background. The first time you run this, the database will be created and all migrations will be applied automatically.

    ```bash
    docker compose -f credservice/docker-compose.yml up -d --build
    ```

2.  **Verify the Service is Running**
    You can check that the service is active by sending a request to its health check endpoint. It might take a few moments to become available as the database initializes.
    ```bash
    curl http://127.0.0.1:8001/health
    ```

    You should see a JSON response like this:

    ```json
    {
      "service": "DeepSecure CredService",
      "version": "0.1.7",
      "status": "ok",
      "dependencies": {
        "database": "connected"
      }
    }
    ```

    If you see `curl: (7) Failed to connect...`, wait a few seconds and try again. If it persists, check the container logs with `docker compose -f credservice/docker-compose.yml logs credservice`.

3.  **Verify the Database Tables (Optional)**
    To confirm that the database schema was created automatically, you can connect to the database inside the Docker container.

    First, connect to the database shell:
    ```bash
    docker compose -f credservice/docker-compose.yml exec db psql -U deepsecure_user -d credservicedb
    ```

    Then, at the `credservicedb=#` prompt, list the tables using the `\dt` command. You should see a list that includes `agents`, `credentials`, and `secrets`. To exit the `psql` shell, type `\q` and press Enter.

Your local `credservice` is now running! You can now proceed with the main project **[Quick Start Guide](../README.md#quick-start)**.

<details>
<summary><b>► Troubleshooting</b></summary>

If the service fails to start, the first place to look is the Docker container logs.

```bash
# View the logs for the credservice application
docker compose -f credservice/docker-compose.yml logs credservice

# View the logs for the database
docker compose -f credservice/docker-compose.yml logs db
```
</details>