# DeepTrail MCP & Monetization Architecture

## 1. MCP Policy Enforcement Architecture

To enable Model Context Protocol (MCP) policy enforcement at the DeepTrail Gateway, we must move beyond simple HTTP Method/Path matching and inspect the JSON-RPC payload typical of MCP.

### 1.1 Components

1.  **MCP Protocol Inspector (Gateway Middleware)**
    *   **Function**: Intercepts requests identified as MCP traffic (via Content-Type `application/json` or specific headers/paths).
    *   **Logic**: Parses the JSON-RPC body.
    *   **Extraction**: Extracts `method` (e.g., `tools/call`, `resources/read`) and `params` (e.g., tool name, resource URI).

2.  **MCP Policy Engine (Extension)**
    *   **Current State**: Matches `domain`, `method`, `path`.
    *   **New State**: Adds `mcp_tool`, `mcp_resource`, `mcp_prompt`.
    *   **Rule Example**:
        ```json
        {
          "effect": "allow",
          "mcp_tool": "weather_lookup",
          "mcp_resource": "file://data/*"
        }
        ```

3.  **MCP Registry (Control Plane)**
    *   **Function**: specific registry to resolve "remote" MCP servers.
    *   **Data Model**: Maps `server_name` -> `base_url`, `public_key`.

### 1.2 Flow
1.  **Agent** sends MCP JSON-RPC request to Gateway.
2.  **Gateway** authenticates Agent (mTLS/JWT).
3.  **MCP Inspector** parses payload: `method="tools/call", params.name="calculator"`.
4.  **Policy Engine** checks: Does Agent have "allow" for `mcp_tool:calculator`?
5.  **Enforcement**:
    *   *Allowed*: Request proxies to the registered MCP Server.
    *   *Denied*: Gateway returns JSON-RPC Error `-32601` (Method not found/allowed).

---

## 2. Edge Monetization Services & ERP Integration

This architecture enables the "Integrated with any backend sales, accounting and ERP system" feature.

### 2.1 Core Design Principles
*   **Asynchronous Decoupling**: The Gateway must not block request processing to talk to an ERP. It emits events.
*   **Adapter Pattern**: Support "any" backend via a plugin system.
*   **Event Sourcing**: The "Billable Event" is the source of truth.

### 2.2 Architecture Diagram

```mermaid
graph LR
    A[Agent] -->|API Call| G[DeepTrail Gateway]
    G -->|Proxy| S[Upstream Service]
    
    subgraph "Monetization Pipeline"
        G -- Async Emit --> Q[(Redis Stream\n'billing.events')]
        W[Billing Worker\n(DeepTrail Control)] -- Consume --> Q
        W -->|Aggregates| db[(Usage DB)]
        W -->|Sync| ERP[ERP Adapter]
    end
    
    subgraph "External Systems"
        ERP -->|API| SF[Salesforce/NetSuite]
        ERP -->|API| SAP[SAP/Oracle]
    end
```

### 2.3 Data Models

1.  **BillableEvent** (Emitted by Gateway)
    *   `event_id`: UUID
    *   `agent_id`: String
    *   `timestamp`: ISO8601
    *   `transaction_type`: "api_call" | "mcp_tool_call"
    *   `metric_name`: "requests" | "tokens" | "compute_ms"
    *   `quantity`: Integer
    *   `metadata`: JSON (Customer ID, Region, etc.)

2.  **BillingAdapter** (Interface)
    *   `sync_customer(customer_data)`: Create/Update customer in ERP.
    *   `record_usage(subscription_id, metric, quantity)`: Push usage to ERP.
    *   `generate_invoice(period)`: Trigger invoice generation.

### 2.4 Integration Workflow (Sales/ERP)

1.  **Onboarding**: When a new Organization/Agent is created in DeepTrail, the `BillingWorker` calls `ERP.sync_customer()`.
2.  **Runtime**:
    *   Gateway calculates usage (e.g., counts 1 request, measures 50ms duration).
    *   Pushes `BillableEvent` to Redis.
3.  **Processing**:
    *   `BillingWorker` reads batch of events.
    *   Aggregates by `agent_id` + `metric`.
    *   Calls `ERP.record_usage()`.
4.  **Sync**:
    *   If the ERP is offline, `BillingWorker` retries (Reliability).
    *   Status is reported back to the User Dashboard (Self-Service).

### 2.5 Implementation Phases
1.  **Phase 1: Data Capture & Transport**: Implement `UsageCollector` middleware and Redis transport.
2.  **Phase 2: Billing Worker & Adapter Interface**: Create the worker and the `ERPAdapter` abstract class.
3.  **Phase 3: ERP Implementation**: Implement a specific adapter (e.g., Mock/File first, then Stripe/Salesforce).

