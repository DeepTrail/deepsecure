# Integrating DeepSecure with Google Apigee

This guide outlines how to integrate DeepSecure with Google Apigee to enable fine-grained, dynamic authorization for your APIs. In this pattern, Apigee acts as the Policy Enforcement Point (PEP), intercepting API requests and validating them against the DeepSecure Control Plane, which serves as the Policy Decision Point (PDP).

This allows you to protect your backend services with AI-ready security, including secure delegation and just-in-time credentials, without altering the services themselves.

## Prerequisites

*   An Apigee Edge or Apigee X environment.
*   A running DeepSecure Control Plane instance accessible from your Apigee environment.
*   An existing API Proxy in Apigee that you wish to protect.

## Integration Architecture

The flow is conceptually similar to other API gateway integrations:

1.  A client (e.g., an AI agent) sends a request to an Apigee API Proxy endpoint. The request includes a credential from DeepSecure.
2.  The API Proxy flow is triggered.
3.  A **Service Callout** policy is executed, which makes a request to the DeepSecure Control Plane's authorization endpoint (`/v1/authorize`).
4.  The Service Callout policy sends the original request's headers (including the `Authorization` header containing the DeepSecure credential) and other context to DeepSecure.
5.  DeepSecure evaluates the policy and returns an `HTTP 200 OK` for an approved request or `HTTP 403 Forbidden` for a denied one.
6.  The Apigee flow continues, checking the response from the Service Callout.
7.  A **Raise Fault** policy is used to halt execution and return a `403 Forbidden` error to the client if the DeepSecure response was not `200 OK`.
8.  If the response was `200 OK`, the request is forwarded to the backend target service.

## Configuration Steps

### Step 1: Create a Service Callout Policy

In your Apigee API Proxy editor, navigate to the **Develop** tab. In the **PreFlow** of the Proxy Endpoint, add a new **Service Callout** policy.

This policy will be responsible for calling the DeepSecure PDP.

Configure the policy XML. Name the policy `SC-Authorize-With-DeepSecure`.

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ServiceCallout async="false" continueOnError="false" enabled="true" name="SC-Authorize-With-DeepSecure">
    <DisplayName>SC Authorize With DeepSecure</DisplayName>
    <Request clearPayload="true" variable="deepsecureRequest">
        <Set>
            <Headers>
                <!-- Forward the original Authorization header to DeepSecure -->
                <Header name="Authorization">{request.header.Authorization}</Header>
                <Header name="Content-Type">application/json</Header>
            </Headers>
            <Verb>POST</Verb>
            <!-- Add any other relevant context to the payload -->
            <Payload contentType="application/json">
            {
                "method": "{request.verb}",
                "path": "{proxy.pathsuffix}",
                "user_agent": "{request.header.User-Agent}"
            }
            </Payload>
        </Set>
        <IgnoreUnresolvedVariables>false</IgnoreUnresolvedVariables>
    </Request>
    <Response>deepsecureResponse</Response>
    <HTTPTargetConnection>
        <Properties/>
        <!-- URL of your DeepSecure Control Plane PDP endpoint -->
        <URL>https://your-deepsecure-pdp.example.com/v1/authorize</URL>
    </HTTPTargetConnection>
</ServiceCallout>
```

**Key elements of this policy:**
*   `continueOnError="false"`: Ensures that if the callout fails, the entire flow stops.
*   `<Request>`: We create a new request variable named `deepsecureRequest`. We copy the `Authorization` header from the original client request. We also construct a JSON payload with contextual information from the original request for the PDP.
*   `<Response>`: The response from DeepSecure will be stored in the `deepsecureResponse` variable.
*   `<URL>`: This must be the full URL to your DeepSecure Control Plane's authorization endpoint.

### Step 2: Add a Conditional Fault Rule

After the Service Callout policy, you need to check the response from DeepSecure and block the request if it was not successful.

Add a **Raise Fault** policy to your proxy. Name it `RF-Forbidden-By-Policy`.

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<RaiseFault async="false" continueOnError="false" enabled="true" name="RF-Forbidden-By-Policy">
    <DisplayName>RF Forbidden By Policy</DisplayName>
    <Properties/>
    <FaultResponse>
        <Set>
            <Headers/>
            <Payload contentType="application/json" variablePrefix="@" variableSuffix="#">
            {
                "error": "Access denied.",
                "message": "The request was blocked by a DeepSecure security policy."
            }
            </Payload>
            <StatusCode>403</StatusCode>
            <ReasonPhrase>Forbidden</ReasonPhrase>
        </Set>
    </FaultResponse>
    <IgnoreUnresolvedVariables>true</IgnoreUnresolvedVariables>
</RaiseFault>
```

Now, attach this `RF-Forbidden-By-Policy` to a conditional step in your PreFlow, immediately after the Service Callout policy.

In the Proxy Endpoint PreFlow view, add a new **Fault Rule**. Configure it with the following condition:

```
(deepsecureResponse.status.code != "200")
```

And attach the `RF-Forbidden-By-Policy` to this rule.

Your PreFlow should now look like this:
1.  `SC-Authorize-With-DeepSecure` policy executes.
2.  A conditional step that triggers the `RF-Forbidden-By-Policy` if the status code from the previous step is not 200.

### Step 3: Deploy and Test

Save and deploy the new revision of your API Proxy.

1.  **Make a request without a valid credential (or with none):**
    ```bash
    curl -i -X GET https://your-apigee-org-env.apigee.net/your-proxy-basepath/some-resource
    ```
    The `SC-Authorize-With-DeepSecure` policy will execute, but since no valid `Authorization` header is present, the DeepSecure PDP will return a `403`. The conditional fault rule will trigger, and you will receive a `403 Forbidden` response.

2.  **Make a request with a valid DeepSecure credential:**
    Obtain a valid credential from DeepSecure for the desired action.
    ```bash
    curl -i -X GET \
      -H "Authorization: Bearer <your-deepsecure-credential>" \
      https://your-apigee-org-env.apigee.net/your-proxy-basepath/some-resource
    ```
    The Service Callout will forward the credential. DeepSecure will validate it and return `200 OK`. The fault rule condition will not be met, and the request will proceed to your backend target.

## Conclusion

By using Apigee's Service Callout and Raise Fault policies, you can effectively integrate DeepSecure as an externalized authorization engine. This setup enhances your API security with the fine-grained, dynamic controls necessary for a modern, AI-driven application landscape, all without modifying your backend services.


