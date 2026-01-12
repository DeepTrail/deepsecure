# Writer AWS Single-Tenant Deployment Architecture

## DeepSecure Integration for Writer's MCP Platform

```mermaid
flowchart TB
    subgraph WriterAWS["Writer AWS Account - Single Tenant"]
        subgraph VPC["VPC (10.0.0.0/16)"]
            subgraph PublicSubnet["Public Subnets"]
                ALB[Application Load Balancer]
                WAF[AWS WAF]
            end
            
            subgraph PrivateSubnet["Private App Subnets"]
                subgraph EKS["EKS Cluster"]
                    ControlPlane[DeepTrail Control Plane<br/>- Policy Management<br/>- Agent Identity<br/>- Audit Logging]
                    Gateway[DeepTrail Gateway<br/>- Policy Enforcement<br/>- Secret Injection<br/>- Request Proxying]
                    AdminUI[Admin UI<br/>- MCP Registry<br/>- Agent Management<br/>- Policy Editor]
                    MCPRegistry[MCP Server Registry<br/>- Whitelisted MCPs<br/>- Version Control]
                end
                
                subgraph DataStores["Data Layer"]
                    RDS[(RDS PostgreSQL<br/>Policies & Audit)]
                    Redis[(ElastiCache Redis<br/>Gateway Cache)]
                    OpenSearch[(OpenSearch<br/>Audit Analytics)]
                end
                
                subgraph Security["Security Services"]
                    KMS[AWS KMS<br/>Key Management]
                    SM[Secrets Manager<br/>API Keys]
                    VPCEndpoints[VPC Endpoints<br/>STS, S3, ECR]
                end
            end
            
            subgraph DMZ["Private Egress Subnet"]
                NAT[NAT Gateway]
                Egress[Egress Controller<br/>Prefix List]
            end
        end
    end
    
    subgraph External["External Services"]
        OIDC[Okta/IdP<br/>Admin SSO]
        OAuth[OAuth Providers<br/>Google, Slack]
        APIs[SaaS APIs<br/>OpenAI, GitHub]
        MCPs[Writer MCP Servers<br/>Approved Registry]
    end
    
    subgraph Users["Users"]
        Devs[Developers/<br/>AI Agents]
        Admins[Writer Admins]
    end
    
    %% User Flows
    Devs -->|SDK Operations| ALB
    Admins -->|Admin Access| WAF
    WAF --> ALB
    
    %% Internal Flows
    ALB --> ControlPlane
    ALB --> Gateway
    ALB --> AdminUI
    
    ControlPlane --> RDS
    Gateway --> Redis
    Gateway --> ControlPlane
    AdminUI --> ControlPlane
    MCPRegistry --> ControlPlane
    
    %% Data Store Connections
    ControlPlane --> KMS
    ControlPlane --> SM
    Gateway --> SM
    ControlPlane --> OpenSearch
    
    %% External Connections
    Gateway -->|Proxied API Calls| NAT
    NAT --> Egress
    Egress --> APIs
    Egress --> MCPs
    
    AdminUI -.->|OIDC Auth| OIDC
    Gateway -.->|OAuth Flow| OAuth
    
    %% Styling
    classDef app fill:#e8f2ff,stroke:#3986e1
    classDef data fill:#fff7e6,stroke:#d9a441
    classDef security fill:#eefcf0,stroke:#2f855a
    classDef external fill:#f6f6f7,stroke:#8a8f98
    classDef user fill:#ffffff,stroke:#666
    
    class ControlPlane,Gateway,AdminUI,MCPRegistry app
    class RDS,Redis,OpenSearch data
    class KMS,SM,VPCEndpoints,WAF security
    class OIDC,OAuth,APIs,MCPs external
    class Devs,Admins user
```

## Key Architectural Features for Writer

### 1. **MCP Registry & Management**
- **Centralized MCP allowlist** - Only Writer-approved MCP servers
- **Version control** for MCP server deployments
- **Security scanning** before MCP approval

### 2. **Multi-Level Security**
- **WAF** for web protection
- **Network isolation** with private subnets
- **Egress control** with prefix lists for approved destinations
- **KMS encryption** for all secrets

### 3. **Admin UI Features**
- **MCP Server Management**
  - Add/remove MCP servers
  - Configure MCP permissions
  - Monitor MCP usage
- **Agent Management**
  - Create agent identities
  - View agent sessions
  - Manage agent lifecycle
- **Policy Editor**
  - Visual policy creation
  - Test policy effects
  - Apply policies to agents/MCPs
- **Delegation Trail**
  - Real-time delegation visualization
  - Complete audit trail
  - Session replay capability

### 4. **Deployment Considerations**

#### Trade-offs to Consider:

1. **OpenSearch vs S3+Athena for Audit**
   - **OpenSearch**: Real-time search, higher cost
   - **S3+Athena**: Cost-effective, slight query delay
   - **Recommendation**: Start with S3+Athena, migrate if needed

2. **Redis Deployment**
   - **ElastiCache**: Managed, automatic failover
   - **Self-managed**: More control, higher operational burden
   - **Recommendation**: Use ElastiCache for production

3. **MCP Communication Pattern**
   - **Direct Gateway-to-MCP**: Lower latency
   - **Via Control Plane**: Better policy control
   - **Recommendation**: Direct with policy caching

#### Key Assumptions:

1. **Single-tenant per AWS account** for isolation
2. **EKS for container orchestration** (vs ECS)
3. **PostgreSQL for policy/audit** (vs DynamoDB)
4. **Okta for admin SSO** (configurable)
5. **Writer manages the MCP allowlist**

### 5. **Security & Compliance**

- **Zero-trust architecture** - Every request authenticated
- **Ephemeral credentials** - No long-lived API keys
- **Complete audit trail** - Every action logged
- **Policy enforcement** - Granular control over agent capabilities
- **Secure MCP integration** - Only approved servers, encrypted communication

### 6. **Scalability Patterns**

- **Horizontal scaling** of gateway pods
- **Read replicas** for policy database
- **CDN integration** for static assets
- **Auto-scaling groups** for compute resources

This architecture provides Writer with:
- ✅ Complete control over MCP ecosystem
- ✅ Enterprise-grade security
- ✅ Full visibility and auditability
- ✅ Scalable to thousands of agents
- ✅ Integration with existing Writer infrastructure
