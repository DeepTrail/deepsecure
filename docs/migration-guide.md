# DeepSecure Gateway Migration Guide

This guide helps you migrate from the legacy single-service architecture to the new dual-service gateway architecture. The migration enables enhanced security, automatic secret injection, and complete audit trails for external API calls.

## Overview

### What's Changing

**Legacy Architecture (v0.1.x)**:
- Single `deeptrail-control` service
- Direct external API calls from agents
- Manual secret management in agent code
- Limited audit capabilities

**New Gateway Architecture (v0.2.x)**:
- Dual services: `deeptrail-control` + `deeptrail-gateway`
- All external API calls routed through gateway
- Automatic secret injection
- Complete audit trail and policy enforcement

### Migration Benefits

- 🔐 **Enhanced Security**: Zero API key exposure in agent code
- 📊 **Complete Audit Trail**: All external API calls logged with agent identity
- 🔄 **Automatic Secret Rotation**: No code changes needed for key updates
- 🎯 **Fine-Grained Access Control**: Per-agent, per-service policies
- 🛡️ **Zero-Trust Architecture**: Network-level security controls

## Migration Checklist

### Pre-Migration Assessment

- [ ] Current DeepSecure version: `deepsecure --version`
- [ ] Number of agents in use: `deepsecure agent list`
- [ ] External services currently used (OpenAI, AWS, etc.)
- [ ] Current secret management approach
- [ ] Deployment environment (Docker, Kubernetes, etc.)

### Migration Steps

## Step 1: Update Infrastructure

### 1.1 Update Docker Compose

**Old docker-compose.yml**:
```yaml
services:
  deeptrail-control:
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/deepsecure_db
```

**New docker-compose.yml**:
```yaml
services:
  deeptrail-control:
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/deepsecure_db
      - DEEPSECURE_GATEWAY_URL=http://deeptrail-gateway:8002
  
  deeptrail-gateway:
    ports:
      - "8002:8002"
    environment:
      - DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://deeptrail-control:8000
    depends_on:
      - deeptrail-control
```

### 1.2 Update Kubernetes Deployments

**Add Gateway Service**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: deeptrail-gateway
spec:
  replicas: 2
  selector:
    matchLabels:
      app: deeptrail-gateway
  template:
    metadata:
      labels:
        app: deeptrail-gateway
    spec:
      containers:
      - name: deeptrail-gateway
        image: deeptrail/gateway:latest
        ports:
        - containerPort: 8002
        env:
        - name: DEEPSECURE_DEEPTRAIL_CONTROL_URL
          value: "http://deeptrail-control:8000"
---
apiVersion: v1
kind: Service
metadata:
  name: deeptrail-gateway
spec:
  selector:
    app: deeptrail-gateway
  ports:
  - port: 8002
    targetPort: 8002
```

## Step 2: Update Configuration

### 2.1 Update Environment Variables

**Legacy Configuration**:
```bash
export DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000
export DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN=your-token
```

**New Configuration**:
```bash
export DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002
export DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN=your-token
```

### 2.2 Update CLI Configuration

```bash
# Update CLI configuration
deepsecure configure set-url http://localhost:8000
deepsecure configure set-gateway-url http://localhost:8002
deepsecure configure set-token  # Re-enter your token
```

### 2.3 Verify Configuration

```bash
# Check configuration
deepsecure configure show

# Test connectivity
curl http://localhost:8000/health  # Control plane
curl http://localhost:8002/health  # Gateway
```

## Step 3: Update Agent Code

### 3.1 Client Initialization (No Changes Required)

The DeepSecure client automatically detects the gateway configuration:

```python
# This works with both old and new architectures
import deepsecure
client = deepsecure.Client()
```

### 3.2 External API Calls Migration

**Legacy Approach** (Direct API calls):
```python
import requests
import deepsecure

client = deepsecure.Client()
agent_client = client.with_agent("my-agent", auto_create=True)

# Manual secret retrieval
api_key_secret = agent_client.get_secret("openai-api-key")
api_key = api_key_secret.value

# Direct API call (legacy)
response = requests.post(
    "https://api.openai.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello"}]}
)
```

**New Gateway Approach** (Automatic secret injection):
```python
import deepsecure

client = deepsecure.Client()
agent_client = client.with_agent("my-agent", auto_create=True)

# Gateway-proxied API call with automatic secret injection
response = agent_client.call_external_api(
    target_base_url="https://api.openai.com",
    path="/v1/chat/completions",
    method="POST",
    json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello"}]}
)
# Gateway automatically injects the OpenAI API key
```

### 3.3 Framework Integration Updates

**CrewAI Migration**:
```python
# Legacy approach
def create_openai_tool():
    @tool("OpenAI Tool")
    def openai_tool(prompt: str):
        api_key = get_secret_manually("openai-api-key")
        # Direct API call
        return call_openai_directly(prompt, api_key)

# New gateway approach
def create_openai_tool(agent_client):
    @tool("OpenAI Tool")
    def openai_tool(prompt: str):
        # Gateway handles authentication automatically
        return agent_client.call_external_api(
            target_base_url="https://api.openai.com",
            path="/v1/chat/completions",
            method="POST",
            json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}]}
        )
```

## Step 4: Update Secret Management

### 4.1 Review Current Secrets

```bash
# List all secrets
deepsecure vault list

# Review secret usage
deepsecure vault show SECRET_NAME
```

### 4.2 Update Secret Policies

With the gateway architecture, you can define fine-grained access policies:

```bash
# Create agent-specific policies
deepsecure policy create --name openai-access --agent my-agent --service openai.com
deepsecure policy create --name aws-access --agent my-agent --service aws.amazon.com
```

### 4.3 Secret Rotation

The gateway enables zero-downtime secret rotation:

```bash
# Rotate secrets without code changes
deepsecure vault rotate openai-api-key --new-value "new-api-key-value"
```

## Step 5: Update Tests

### 5.1 Mock Gateway Calls

**Legacy Test Approach**:
```python
@patch('requests.post')
def test_openai_call(mock_post):
    mock_post.return_value = Mock(status_code=200, json=lambda: {"response": "test"})
    # Test direct API call
```

**New Gateway Test Approach**:
```python
@patch('deepsecure.Client.call_external_api')
def test_openai_call(mock_call):
    mock_call.return_value = Mock(status_code=200, json=lambda: {"response": "test"})
    # Test gateway-proxied call
```

### 5.2 Integration Tests

Add gateway-specific integration tests:

```python
def test_gateway_connectivity():
    client = deepsecure.Client()
    assert client.gateway_url is not None
    
    # Test gateway health
    response = requests.get(f"{client.gateway_url}/health")
    assert response.status_code == 200

def test_secret_injection():
    client = deepsecure.Client()
    agent_client = client.with_agent("test-agent", auto_create=True)
    
    # Test that external API calls work through gateway
    response = agent_client.call_external_api(
        target_base_url="https://httpbin.org",
        path="/get",
        method="GET"
    )
    assert response.status_code == 200
```

## Step 6: Deployment Strategy

### 6.1 Blue-Green Deployment

1. **Deploy new services** alongside existing ones
2. **Update configuration** for new agents
3. **Gradually migrate** existing agents
4. **Monitor and validate** functionality
5. **Decommission** old services

### 6.2 Canary Deployment

1. **Deploy gateway** with 10% of traffic
2. **Monitor metrics** and error rates
3. **Gradually increase** traffic to gateway
4. **Full migration** once validated

### 6.3 Rollback Plan

If issues arise during migration:

```bash
# Rollback to legacy configuration
export DEEPSECURE_GATEWAY_URL=""
deepsecure configure set-gateway-url ""

# Restart agents with legacy configuration
# Gateway calls will automatically fall back to direct calls
```

## Step 7: Validation & Testing

### 7.1 Functional Testing

```bash
# Test agent creation
deepsecure agent create migration-test-agent

# Test secret storage
deepsecure vault store test-secret --value "test-value"

# Test secret retrieval
deepsecure vault get test-secret --agent migration-test-agent

# Test external API call through gateway
python -c "
import deepsecure
client = deepsecure.Client()
agent_client = client.with_agent('migration-test-agent', auto_create=True)
response = agent_client.call_external_api('https://httpbin.org', '/get')
print('Gateway test:', response.status_code == 200)
"
```

### 7.2 Performance Testing

```bash
# Test gateway response times
time curl http://localhost:8002/health

# Test end-to-end latency
time python examples/08_gateway_secret_injection_demo.py
```

### 7.3 Security Testing

```bash
# Test that direct API calls are blocked (if configured)
# Test that unauthorized agents can't access secrets
# Test that audit logs are generated
docker compose logs deeptrail-gateway | grep "audit"
```

## Step 8: Monitor & Optimize

### 8.1 Monitoring Setup

```bash
# Monitor gateway metrics
curl http://localhost:8002/metrics

# Monitor control plane metrics
curl http://localhost:8000/metrics

# Check audit logs
docker compose logs deeptrail-gateway | grep "external_api_call"
```

### 8.2 Performance Optimization

- **Connection pooling**: Configure HTTP client pools
- **Caching**: Enable policy and secret caching
- **Load balancing**: Deploy multiple gateway instances
- **Monitoring**: Set up alerts for error rates and latency

## Troubleshooting Migration Issues

### Common Issues

#### 1. Gateway Connection Failed

**Symptoms**:
- "Connection refused" errors
- External API calls failing
- Gateway not responding

**Solutions**:
```bash
# Check gateway service
docker compose ps deeptrail-gateway
docker compose logs deeptrail-gateway

# Verify network connectivity
docker network inspect deepsecure_default

# Check configuration
echo $DEEPSECURE_GATEWAY_URL
```

#### 2. Secret Injection Not Working

**Symptoms**:
- API calls return 401/403 errors
- "API key not found" messages
- External services rejecting requests

**Solutions**:
```bash
# Verify secrets are stored
deepsecure vault list

# Check agent policies
deepsecure policy list

# Test secret retrieval
deepsecure vault get SECRET_NAME --agent AGENT_NAME
```

#### 3. Authentication Errors

**Symptoms**:
- "Invalid JWT token" errors
- Gateway returning 401 errors
- Agent authentication failures

**Solutions**:
```bash
# Check agent status
deepsecure agent list

# Verify token configuration
deepsecure configure show-token

# Test authentication
deepsecure agent create test-auth-agent
```

#### 4. Policy Violations

**Symptoms**:
- "Access denied" messages
- Policy enforcement blocking requests
- Unexpected permission errors

**Solutions**:
```bash
# Review agent policies
deepsecure policy list --agent AGENT_NAME

# Check policy logs
docker compose logs deeptrail-gateway | grep "policy_violation"

# Update policies if needed
deepsecure policy update --name POLICY_NAME --permissions "read,write"
```

## Post-Migration Validation

### Checklist

- [ ] All agents can authenticate successfully
- [ ] External API calls work through gateway
- [ ] Secrets are injected automatically
- [ ] Audit logs are generated
- [ ] Performance meets requirements
- [ ] Security policies are enforced
- [ ] Monitoring and alerting are functional
- [ ] Rollback procedures are documented
- [ ] Team is trained on new architecture

### Success Metrics

- **Zero API key exposure**: No API keys in agent code or logs
- **Complete audit trail**: All external API calls logged
- **Performance**: Gateway adds <100ms latency
- **Reliability**: 99.9% uptime for gateway service
- **Security**: Zero policy violations or unauthorized access

## Getting Help

If you encounter issues during migration:

1. **Check documentation**:
   - [Configuration Guide](./configuration.md)
   - [Troubleshooting Guide](../README.md#troubleshooting)
   - [Examples](../examples/README.md)

2. **Community support**:
   - [GitHub Discussions](https://github.com/DeepTrail/deepsecure/discussions)
   - [GitHub Issues](https://github.com/DeepTrail/deepsecure/issues)

3. **Enable debug logging**:
   ```bash
   export DEEPSECURE_DEBUG=true
   export DEEPSECURE_LOG_LEVEL=DEBUG
   ```

4. **Gather diagnostic information**:
   ```bash
   # Save configuration
   deepsecure configure show > deepsecure-config.txt
   
   # Save service logs
   docker compose logs deeptrail-control > control-logs.txt
   docker compose logs deeptrail-gateway > gateway-logs.txt
   
   # Save system information
   docker compose ps > services-status.txt
   ```

## Migration Timeline

### Recommended Timeline

- **Week 1**: Infrastructure setup and testing
- **Week 2**: Agent code updates and testing
- **Week 3**: Staged deployment and validation
- **Week 4**: Full migration and optimization

### Critical Path

1. **Infrastructure deployment** (Days 1-3)
2. **Configuration updates** (Days 4-5)
3. **Agent code migration** (Days 6-10)
4. **Testing and validation** (Days 11-14)
5. **Production deployment** (Days 15-21)
6. **Monitoring and optimization** (Days 22-28)

## Conclusion

The gateway architecture migration provides significant security, operational, and compliance benefits. While the migration requires careful planning and execution, the new architecture positions your AI agents for secure, scalable, and auditable operation.

Key migration success factors:
- Thorough testing at each stage
- Gradual rollout with monitoring
- Team training on new patterns
- Comprehensive validation before full deployment

The investment in migration pays dividends through reduced security risk, operational overhead, and compliance complexity. 