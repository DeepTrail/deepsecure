# API Gateway Integration Reference Example

This example provides a complete, runnable demonstration of integrating DeepSecure with the Kong API Gateway to provide fine-grained, dynamic authorization for a backend service.

## Overview

The example consists of four main components orchestrated by Docker Compose:

1.  **Mock API (`my-api-service`):** A simple Flask-based API with a single endpoint (`/invoices/{invoice_id}`) that we want to protect.
2.  **Kong (`kong`):** The API Gateway that acts as the Policy Enforcement Point (PEP). It is configured to proxy requests to the Mock API.
3.  **DeepSecure Control Plane (`deeptrail-control`):** The authorization service that acts as the Policy Decision Point (PDP).
4.  **Agent Simulation (`agent_simulation.py`):** A Python script that demonstrates the end-to-end flow:
    *   It acts as a client application to request a fine-grained credential from the DeepSecure Control Plane.
    *   It then acts as an AI agent, using that credential to access a specific resource on the Mock API via the Kong gateway.

## How to Run

### Prerequisites

*   Docker and Docker Compose
*   Python 3.6+ and the `requests` library (`pip install requests`)

### Steps

1.  **Start the Services:**
    From this directory (`examples/api-gateway-integration`), run:
    ```bash
    docker-compose up --build
    ```
    This will start the Mock API, Kong, and the DeepSecure Control Plane. It will also configure Kong with the necessary service and route.

2.  **Run the Agent Simulation:**
    In a separate terminal, run the simulation script:
    ```bash
    python agent_simulation.py
    ```

## Expected Output

The output of the `agent_simulation.py` script will demonstrate the following flow:

1.  **Successful Request:** The script will first request a credential that is authorized to access a *specific* invoice (`/invoices/123`). It will then use this credential to make a request to Kong, which will be approved by the PDP, and the request will succeed.

    ```
    --> Scenario 1: Agent requests access to a resource it IS authorized for (/invoices/123)
    Credential obtained successfully for resource: ds:api:invoices/123
    Making request to Kong with valid credential...
    SUCCESS! API call to http://localhost:8000/invoices/123 returned status 200
    Response: {"invoice_id": "123", "amount": "USD 1000", "status": "paid"}
    ```

2.  **Failed Request:** The script will then attempt to use the *same credential* to access a different invoice (`/invoices/456`) for which it is *not* authorized. Kong will forward the request to the PDP, which will deny it, and Kong will return a `403 Forbidden` error.

    ```
    --> Scenario 2: Agent attempts to access a resource it is NOT authorized for (/invoices/456)
    Using the SAME credential to access a different resource...
    Making request to Kong with credential for wrong resource...
    FAILURE! API call to http://localhost:8000/invoices/456 returned status 403
    Response: {"message":"Forbidden by DeepSecure Policy"}
    ```

This clearly demonstrates that the authorization is fine-grained and enforced on a per-resource basis.

## Tearing Down

To stop and remove the containers, press `Ctrl+C` in the terminal where `docker-compose` is running, and then run:

```bash
docker-compose down
```


