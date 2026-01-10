# DeepSecure Configuration Guide

This document provides comprehensive information about configuring DeepSecure for different environments and use cases.

## Environment Variables

### Core Service Configuration

#### `DEEPSECURE_DEEPTRAIL_CONTROL_URL`
- **Description**: URL of the DeepSecure control plane service
- **Default**: `http://localhost:8000`
- **Example**: `http://localhost:8000`
- **Usage**: Controls where the SDK and CLI connect for agent management, authentication, and policy operations

#### `DEEPSECURE_GATEWAY_URL`
- **Description**: URL of the DeepSecure gateway service for external API calls
- **Default**: `http://localhost:8002`
- **Example**: `http://localhost:8002`
- **Usage**: Routes external API calls through the gateway for secret injection and policy enforcement

#### `DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN`
- **Description**: Authentication token for the control plane service
- **Default**: None (must be set)
- **Example**: `DEFAULT_QUICKSTART_TOKEN` (for local development)
- **Usage**: Authenticates CLI and SDK operations with the control plane

### Optional Configuration

#### `DEEPSECURE_API_TOKEN`
- **Description**: Legacy authentication token (deprecated)
- **Default**: None
- **Usage**: Backwards compatibility for older authentication flows

#### `DEEPSECURE_SECRET_VALUE`
- **Description**: Secret value for CLI vault operations
- **Default**: None
- **Usage**: Allows non-interactive secret storage in CLI commands

#### `DEEPSECURE_AGENT_ID`
- **Description**: Agent ID for bootstrapping scenarios
- **Default**: None
- **Usage**: Used in Kubernetes and AWS bootstrapping for identity verification

#### `DEEPSECURE_VERSION`
- **Description**: Version override for the control plane service
- **Default**: Package version
- **Usage**: Development and testing environments

### Database Configuration (Control Plane)

#### `DATABASE_URL`
- **Description**: PostgreSQL database connection string
- **Default**: `postgresql://user:password@localhost/deepsecure_db`
- **Example**: `postgresql://user:password@localhost/deepsecure_db`
- **Usage**: Database connection for the control plane service

## Configuration Methods

### 1. Environment Variables

Set environment variables in your shell or process environment:

```bash
export DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002
export DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN=your-api-token
```

### 2. CLI Configuration

Use the CLI to set persistent configuration:

```bash
# Set control plane URL
deepsecure configure set-url http://localhost:8000

# Set gateway URL
deepsecure configure set-gateway-url http://localhost:8002

# Set API token (prompts for secure input)
deepsecure configure set-token
```

### 3. Docker Environment

In `docker-compose.yml`:

```yaml
environment:
  - DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://deeptrail-control:8000
  - DEEPSECURE_GATEWAY_URL=http://deeptrail-gateway:8002
  - DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN=DEFAULT_QUICKSTART_TOKEN
```

### 4. Kubernetes Configuration

Using ConfigMaps and Secrets:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: deepsecure-config
data:
  DEEPSECURE_DEEPTRAIL_CONTROL_URL: "http://deeptrail-control:8000"
  DEEPSECURE_GATEWAY_URL: "http://deeptrail-gateway:8002"
---
apiVersion: v1
kind: Secret
metadata:
  name: deepsecure-secrets
type: Opaque
stringData:
  DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN: "your-api-token"
```

## Configuration Precedence

Configuration values are resolved in the following order (highest to lowest priority):

1. **Command-line arguments** (when available)
2. **Environment variables**
3. **CLI configuration files** (`~/.deepsecure/config.json`)
4. **Default values**

## Local Development Setup

### Quick Start Configuration

For local development, use these settings:

```bash
# Set environment variables
export DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002
export DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN=DEFAULT_QUICKSTART_TOKEN

# Or use CLI configuration
deepsecure configure set-url http://localhost:8000
deepsecure configure set-gateway-url http://localhost:8002
deepsecure configure set-token  # Enter: DEFAULT_QUICKSTART_TOKEN
```

### Docker Compose Setup

Ensure your `docker-compose.yml` includes both services:

```yaml
services:
  deeptrail-control:
    # ... control plane configuration
    ports:
      - "8000:8000"
  
  deeptrail-gateway:
    # ... gateway configuration
    ports:
      - "8002:8002"
    depends_on:
      - deeptrail-control
```

## Production Configuration

### Security Considerations

1. **Use strong API tokens**: Never use default tokens in production
2. **Secure database connections**: Use SSL/TLS for database connections
3. **Network security**: Ensure services are properly isolated
4. **Environment variable security**: Use secure secret management

### Recommended Production Settings

```bash
# Use HTTPS in production
export DEEPSECURE_DEEPTRAIL_CONTROL_URL=https://control.your-domain.com
export DEEPSECURE_GATEWAY_URL=https://gateway.your-domain.com

# Use secure database connections
export DATABASE_URL=postgresql://user:password@db.your-domain.com:5432/deepsecure_db?sslmode=require
```

## Troubleshooting

### Common Configuration Issues

#### Gateway Connection Failed
- **Problem**: External API calls fail
- **Solution**: Verify `DEEPSECURE_GATEWAY_URL` is correct and service is running
- **Check**: `curl http://localhost:8002/health`

#### Authentication Failed
- **Problem**: CLI commands return authentication errors
- **Solution**: Verify `DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN` is set correctly
- **Check**: `deepsecure configure show-token`

#### Service Not Found
- **Problem**: Cannot connect to control plane
- **Solution**: Verify `DEEPSECURE_DEEPTRAIL_CONTROL_URL` and service is running
- **Check**: `curl http://localhost:8000/health`

### Validation Commands

```bash
# Check current configuration
deepsecure configure show

# Test control plane connectivity
curl http://localhost:8000/health

# Test gateway connectivity
curl http://localhost:8002/health

# Validate environment variables
env | grep DEEPSECURE
```

## Security Architecture Benefits

### Gateway-Based Security Model

The DeepSecure gateway architecture provides multiple layers of security:

#### 1. **Zero-Trust Network Architecture**
- All external API calls are routed through the gateway
- No direct internet access from agent environments
- Each request is authenticated and authorized individually
- Network segmentation and traffic control

#### 2. **Secret Management & Injection**
- **No hardcoded secrets**: Agents never store or see API keys
- **Automatic injection**: Gateway injects secrets based on agent identity
- **Centralized rotation**: Secret rotation without code changes
- **Ephemeral credentials**: Short-lived tokens for external services

#### 3. **Policy Enforcement**
- **Fine-grained access control**: Per-agent, per-service policies
- **Dynamic policy updates**: Real-time policy changes without restarts
- **Conditional access**: Context-aware authorization decisions
- **Rate limiting**: Per-agent quotas and throttling

#### 4. **Audit & Compliance**
- **Immutable logs**: All external API calls logged with agent identity
- **Request/response logging**: Complete audit trail for compliance
- **Policy violations**: Automatic logging of access denials
- **Compliance reporting**: Ready-to-use reports for auditors

#### 5. **Threat Detection & Prevention**
- **Request sanitization**: Automatic filtering of malicious requests
- **Anomaly detection**: Unusual patterns in API usage
- **Incident response**: Automatic blocking of compromised agents
- **Forensic analysis**: Complete request history for investigation

### Security Benefits vs Traditional Approaches

| Traditional Approach | DeepSecure Gateway | Benefit |
|---------------------|-------------------|---------|
| Hardcoded API keys | Automatic secret injection | Zero key exposure |
| Manual key rotation | Centralized rotation | Reduced operational risk |
| Direct API calls | Gateway-proxied calls | Complete audit trail |
| Shared credentials | Agent-specific identity | Fine-grained access control |
| No access control | Policy-based authorization | Least privilege access |
| No monitoring | Real-time logging | Incident detection |

### Compliance & Regulatory Benefits

The gateway architecture helps meet various compliance requirements:

- **SOC 2 Type II**: Comprehensive audit trails and access controls
- **GDPR**: Data processing logs and access controls
- **HIPAA**: Audit logs and access controls for healthcare data
- **PCI DSS**: Secure handling of payment-related API calls
- **ISO 27001**: Information security management system controls

## Configuration Examples

### Example 1: Local Development

```bash
# Environment setup
export DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002
export DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN=DEFAULT_QUICKSTART_TOKEN

# Start services
docker compose up deeptrail-control deeptrail-gateway -d
```

### Example 2: Production Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-agent
spec:
  template:
    spec:
      containers:
      - name: agent
        image: your-agent:latest
        env:
        - name: DEEPSECURE_DEEPTRAIL_CONTROL_URL
          value: "http://deeptrail-control:8000"
        - name: DEEPSECURE_GATEWAY_URL
          value: "http://deeptrail-gateway:8002"
        - name: DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN
          valueFrom:
            secretKeyRef:
              name: deepsecure-secrets
              key: api-token
```

### Example 3: AWS ECS

```json
{
  "environment": [
    {
      "name": "DEEPSECURE_DEEPTRAIL_CONTROL_URL",
      "value": "https://control.your-domain.com"
    },
    {
      "name": "DEEPSECURE_GATEWAY_URL",
      "value": "https://gateway.your-domain.com"
    }
  ],
  "secrets": [
    {
      "name": "DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN",
      "valueFrom": "arn:aws:secretsmanager:region:account:secret:deepsecure-token"
    }
  ]
}
```

## Configuration File Locations

### CLI Configuration Files

- **Location**: `~/.deepsecure/config.json`
- **Purpose**: Persistent CLI configuration
- **Format**: JSON

### Agent Identity Storage

- **Location**: `~/.deepsecure/identities/`
- **Purpose**: Agent private key storage
- **Format**: Encrypted files

### Revocation List

- **Location**: `~/.deepsecure/revoked_creds.json`
- **Purpose**: Locally cached credential revocation list
- **Format**: JSON

## Migration from Legacy Configuration

If you're upgrading from an older version of DeepSecure, update your configuration:

### Legacy → Current

```bash
# OLD: Single service configuration
export DEEPSECURE_CREDSERVICE_URL=http://localhost:8000
export DEEPSECURE_CREDSERVICE_API_TOKEN=your-token

# NEW: Dual service configuration
export DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002
export DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN=your-token
```

### Configuration Validation

After migration, validate your configuration:

```bash
# Check configuration
deepsecure configure show

# Test connectivity
deepsecure agent list

# Verify gateway routing
deepsecure gateway health  # (if available)
``` 