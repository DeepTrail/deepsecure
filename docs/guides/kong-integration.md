# Integrating DeepSecure with Kong API Gateway

This guide provides a step-by-step walkthrough for integrating DeepSecure with the Kong API Gateway. By following these instructions, you can use Kong as a Policy Enforcement Point (PEP) to protect your upstream APIs, while delegating authorization decisions to a DeepSecure Control Plane (PDP).

This allows you to add fine-grained, dynamic, and context-aware authorization to your APIs for AI agents and other services without modifying your existing application code.

## Prerequisites

*   A running Kong Gateway instance.
*   A running DeepSecure Control Plane instance.
*   An upstream API service that you want to protect.

For a complete, runnable example of this integration, see the [API Gateway Integration Reference Example](../examples/api-gateway-integration/README.md).

## Integration Architecture

The integration follows a standard external authorization pattern:

1.  A client (e.g., an AI agent) makes a request to a route on Kong that is configured to protect an upstream API.
2.  Kong intercepts the request.
3.  Using a plugin, Kong makes a request to the DeepSecure Control Plane's authorization endpoint, forwarding relevant information from the original request.
4.  DeepSecure evaluates the request based on its policies and returns an `HTTP 200 OK` response if the request is allowed, or an `HTTP 403 Forbidden` response if it is denied.
5.  Kong enforces the decision:
    *   If the decision is `allow`, Kong forwards the original request to the upstream API.
    *   If the decision is `deny`, Kong immediately returns the `403 Forbidden` error to the client.

## Configuration Steps

### Step 1: Configure the Upstream Service in Kong

First, you need to tell Kong about your upstream API.

```bash
curl -i -X POST \
  --url http://localhost:8001/services/ \
  --data 'name=my-api' \
  --data 'url=http://my-api-service:5000' # Replace with the URL of your service
```

### Step 2: Configure a Route for the Service

Next, create a route that maps incoming requests to your service. For this example, any request to `/invoices` will be routed to `my-api`.

```bash
curl -i -X POST \
  --url http://localhost:8001/services/my-api/routes \
  --data 'paths[]=/invoices' \
  --data 'name=invoices-route'
```

At this point, your API is proxied by Kong, but it is not yet protected.

### Step 3: Configure Kong's External Authorization Plugin

Kong has a variety of plugins for handling authentication and authorization. For this integration, we can use the `pre-function` serverless plugin to call out to the DeepSecure PDP.

This example uses a `pre-function` that calls out to a DeepSecure Control Plane running at `http://deeptrail-control:8000/v1/authorize`.

Create the plugin and associate it with the `my-api` service:

```bash
curl -i -X POST \
  --url http://localhost:8001/services/my-api/plugins \
  --header 'Content-Type: application/json' \
  --data '
{
  "name": "pre-function",
  "config": {
    "access": [
      "
      local http = require 'resty.http'

      -- The address of your DeepSecure Control Plane PDP endpoint
      local deepsecure_pdp_url = 'http://deeptrail-control:8000/v1/authorize'

      -- Create a new HTTP client
      local httpc = http.new()

      -- Forward relevant headers from the original request to the PDP
      local headers = {
        ['Authorization'] = kong.request.get_header('Authorization'),
        ['Content-Type'] = 'application/json'
      }

      -- Send the authorization request to DeepSecure
      local res, err = httpc:request_uri(deepsecure_pdp_url, {
        method = 'POST',
        headers = headers,
        body = kong.request.get_raw_body() -- Or construct a specific body
      })

      -- If DeepSecure denies the request, terminate the execution with 403
      if not res or res.status == 403 then
        return kong.response.exit(403, { message = 'Forbidden by DeepSecure Policy' })
      end

      -- If the request is allowed (200 OK), continue execution
      "
    ]
  }
}
'
```

**Note on the Lua script:** This script is a simplified example. In a production scenario, you would likely want to construct a more specific JSON body to send to the DeepSecure PDP, including details like the HTTP method, path, and other contextual information from the original request. The PDP would then use this rich context to make a more informed decision.

### Step 4: Test the Integration

Now, any request to the `/invoices` route on Kong will first be sent to DeepSecure for an authorization decision.

1.  **Request without a valid credential:**

    ```bash
    curl -i -X GET http://localhost:8000/invoices/123
    ```

    This request will be sent to the DeepSecure PDP without an `Authorization` header. Assuming your policy requires a valid credential, DeepSecure will return a `403`, and Kong will block the request.

2.  **Request with a valid DeepSecure credential:**

    First, obtain a valid, fine-grained credential from DeepSecure for a specific action (e.g., `GET /invoices/123`).

    Then, make the request to Kong with the credential in the `Authorization` header:

    ```bash
    curl -i -X GET \
      --header "Authorization: Bearer <your-deepsecure-credential>" \
      http://localhost:8000/invoices/123
    ```

    Kong will forward this to the PDP. DeepSecure will validate the credential and, if it authorizes `GET` access to `/invoices/123`, it will return a `200 OK`. Kong will then proceed to proxy the request to your upstream API.

## Conclusion

You have now successfully configured Kong to act as a PEP, enforcing the dynamic, fine-grained authorization decisions made by DeepSecure. This powerful pattern allows you to secure your APIs for agentic and other modern workflows without embedding complex authorization logic into your core services.


