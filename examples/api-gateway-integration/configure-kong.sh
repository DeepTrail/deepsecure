#!/bin/sh

# This script configures the Kong gateway.
# It waits for Kong to be available and then creates the necessary
# Service, Route, and Plugin.

KONG_ADMIN_URL="http://kong:8001"

echo "Waiting for Kong to be ready at $KONG_ADMIN_URL..."

# Wait for Kong admin API to be available
until curl -s -f -o /dev/null "$KONG_ADMIN_URL"; do
  echo "Kong not ready, sleeping for 5 seconds..."
  sleep 5
done

echo "Kong is up. Proceeding with configuration."

# 1. Configure the upstream 'my-api-service'
curl -s -X POST \
  --url $KONG_ADMIN_URL/services/ \
  --data 'name=my-api' \
  --data 'url=http://my-api-service:5000'

# 2. Configure the route for the service
curl -s -X POST \
  --url $KONG_ADMIN_URL/services/my-api/routes \
  --data 'paths[]=/invoices' \
  --data 'name=invoices-route'

# 3. Apply the pre-function plugin to call DeepSecure PDP
curl -s -X POST \
  --url $KONG_ADMIN_URL/services/my-api/plugins \
  --header 'Content-Type: application/json' \
  --data @- <<'EOF'
{
  "name": "pre-function",
  "config": {
    "access": [
      "
      local http = require 'resty.http'
      local deepsecure_pdp_url = 'http://deeptrail-control:8001/v1/authorize'
      local httpc = http.new()
      local headers = {
        ['Authorization'] = kong.request.get_header('Authorization'),
        ['Content-Type'] = 'application/json'
      }
      -- Construct a body with context for the PDP
      local body_str = '{\"method\":\"' .. kong.request.get_method() .. '\",\"path\":\"' .. kong.request.get_path() .. '\"}'

      local res, err = httpc:request_uri(deepsecure_pdp_url, {
        method = 'POST',
        headers = headers,
        body = body_str
      })

      if not res or res.status ~= 200 then
        return kong.response.exit(403, { message = 'Forbidden by DeepSecure Policy' })
      end
      "
    ]
  }
}
EOF

echo "Kong configuration complete."


