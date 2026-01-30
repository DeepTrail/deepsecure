# Split-Key Share Refresh Mechanism

## Design Document

**Status**: Proposed  
**Author**: DeepSecure Team  
**Created**: 2026-01-12  
**Last Updated**: 2026-01-12

---

## 1. Problem Statement

### Current Behavior

The DeepSecure split-key architecture stores secrets using Shamir's Secret Sharing:

- **`share_1`**: Stored in the Control Plane database (PostgreSQL) - **persistent**
- **`share_2`**: Stored in the Gateway cache (Redis) - **ephemeral with 24-hour TTL**

This design provides strong security guarantees but creates an operational issue:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Timeline: Secret Lifecycle with Current TTL                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  T+0 hours        T+24 hours        T+30 hours                              │
│  ─────────────────────────────────────────────────────────────────────►     │
│  │                │                 │                                       │
│  ▼                ▼                 ▼                                       │
│  [Secret Stored]  [Redis TTL       [Secret Listed in DB                     │
│   ├─ share_1 → DB  Expires]         but UNRECOVERABLE]                      │
│   └─ share_2 → Redis               │                                       │
│                   │                 └─ "Secret not found" error             │
│                   └─ share_2 deleted                                        │
│                      from Redis                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Observed Issue

```bash
# Secret stored 30 hours ago - metadata exists
$ deepsecure vault list
┌──────────────────┬─────────────────────────────────┐
│ Name             │ Created At                      │
├──────────────────┼─────────────────────────────────┤
│ openai-api-key   │ 2026-01-11 00:54 UTC (30h ago) │  ← Listed ✓
│ new-api-key      │ 2026-01-12 06:46 UTC (4h ago)  │  ← Listed ✓
└──────────────────┴─────────────────────────────────┘

# But retrieval fails for the older secret
$ deepsecure vault get-secret openai-api-key
⚠️  Secret 'openai-api-key' not found in vault.  ← share_2 expired!

$ deepsecure vault get-secret new-api-key
✓ Retrieved successfully                         ← share_2 still valid
```

### Impact

1. **Operational Disruption**: Long-running agents lose access to secrets after 24 hours
2. **Confusing UX**: Secrets appear in `vault list` but fail on `get-secret`
3. **Manual Re-entry**: Administrators must re-store secrets with original values
4. **Credential Availability**: Production workloads may fail unexpectedly

---

## 2. Use Cases

### Use Case 1: Long-Running Production Services

**Scenario**: A production AI agent runs continuously, accessing OpenAI API credentials stored in the vault.

**Current Problem**:
- Agent starts Monday morning with fresh credentials
- Tuesday morning (>24h later), API calls fail silently
- Agent cannot retrieve its credentials from the vault
- Production outage until manual re-storage

**With Share Refresh**:
```bash
# Option A: Automatic refresh on access
$ deepsecure vault get-secret openai-api-key
✓ Retrieved (TTL auto-extended to 24h from now)

# Option B: Explicit refresh command
$ deepsecure vault refresh openai-api-key
✓ Share TTL extended by 24 hours (expires: 2026-01-13 07:00 UTC)

# Option C: Set custom TTL at storage time
$ deepsecure vault store openai-api-key --ttl 7d
✓ Secret stored with 7-day TTL
```

### Use Case 2: Enterprise Secret Rotation

**Scenario**: An organization rotates API keys weekly but wants secrets to remain available between rotations.

**Current Problem**:
- Security team stores new API key on Monday
- Key expires from Redis on Tuesday
- Remaining 5 days of the rotation cycle, agents can't access the key

**With Share Refresh**:
```bash
# Set TTL to match rotation schedule
$ deepsecure vault store stripe-api-key --ttl 7d --labels rotation=weekly

# Or use background refresh job
$ deepsecure vault set-refresh-policy stripe-api-key --auto-refresh --interval 12h
```

### Use Case 3: Development/Testing Environments

**Scenario**: Developers store test credentials that should persist throughout a development sprint.

**Current Problem**:
- Developer stores test API key Monday morning
- By Wednesday, the key is inaccessible
- Sprint workflow is disrupted

**With Share Refresh**:
```bash
# Development secrets with extended TTL
$ deepsecure vault store test-api-key --ttl 14d --labels env=dev

# Bulk refresh for all dev secrets
$ deepsecure vault refresh --filter env=dev
✓ Refreshed 12 secrets with label 'env=dev'
```

### Use Case 4: Disaster Recovery

**Scenario**: After a Redis restart or failover, all share_2 values are lost.

**Current Problem**:
- All secrets become unrecoverable
- Manual re-entry of every secret required
- Significant downtime and security risk (exposing secrets for re-entry)

**With Share Refresh**:
```bash
# Regenerate share_2 from share_1 (requires master key or HSM)
$ deepsecure vault recover --all
⚠️  This operation requires administrative privileges and HSM access.
    Recovering 47 secrets...
✓ Recovered 47/47 secrets with new share_2 values
```

---

## 3. Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Share Refresh Architecture                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐      ┌──────────────────┐      ┌─────────────────────┐    │
│  │   CLI       │      │  Control Plane   │      │      Gateway        │    │
│  │             │      │                  │      │                     │    │
│  │ vault       │─────►│ /vault/refresh   │─────►│ POST /internal/     │    │
│  │ refresh     │      │                  │      │   shares/{name}/    │    │
│  │ <name>      │      │ 1. Validate auth │      │   extend            │    │
│  │             │      │ 2. Check policy  │      │                     │    │
│  │             │      │ 3. Call gateway  │      │ 1. Validate token   │    │
│  │             │◄─────│ 4. Return status │◄─────│ 2. Extend TTL       │    │
│  │             │      │ 5. Audit log     │      │ 3. Return new TTL   │    │
│  └─────────────┘      └──────────────────┘      └─────────────────────┘    │
│                                                                             │
│  ┌─────────────┐      ┌──────────────────┐      ┌─────────────────────┐    │
│  │ Background  │      │  Scheduler       │      │      Redis          │    │
│  │ Refresh     │      │                  │      │                     │    │
│  │ Worker      │─────►│ Every 12h:       │─────►│ EXPIRE share_2:*    │    │
│  │             │      │ - Query secrets  │      │   <new_ttl>         │    │
│  │             │      │ - Check TTL      │      │                     │    │
│  │             │      │ - Refresh if <6h │      │                     │    │
│  └─────────────┘      └──────────────────┘      └─────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 CLI Commands

#### `vault refresh` - Manual Share Refresh

```bash
# Refresh a single secret
$ deepsecure vault refresh <secret-name> [OPTIONS]

Options:
  --ttl <duration>      New TTL (e.g., 24h, 7d, 30d). Default: 24h
  --force               Refresh even if current TTL > 6h
  --output, -o          Output format (text, json)

Examples:
  $ deepsecure vault refresh openai-api-key
  ✓ Secret 'openai-api-key' refreshed
    Previous TTL: 2h 34m remaining
    New TTL: 24h (expires 2026-01-13 07:30 UTC)

  $ deepsecure vault refresh stripe-key --ttl 7d
  ✓ Secret 'stripe-key' refreshed with 7-day TTL
```

#### `vault refresh --all` - Bulk Refresh

```bash
# Refresh all secrets
$ deepsecure vault refresh --all [OPTIONS]

Options:
  --filter <labels>     Only refresh secrets matching labels
  --min-ttl <duration>  Only refresh if TTL < threshold (default: 6h)
  --dry-run             Show what would be refreshed without doing it

Examples:
  $ deepsecure vault refresh --all --min-ttl 12h
  Scanning 47 secrets...
  ├── 12 secrets with TTL < 12h
  ├── 35 secrets with TTL >= 12h (skipped)
  └── 0 secrets with expired shares

  Refreshing 12 secrets...
  ✓ All 12 secrets refreshed successfully

  $ deepsecure vault refresh --all --filter env=production
  ✓ Refreshed 8 production secrets
```

#### `vault status` - View Share Health

```bash
# View TTL status for secrets
$ deepsecure vault status [OPTIONS]

Options:
  --expiring            Only show secrets expiring within 6h
  --expired             Only show secrets with expired shares
  --output, -o          Output format (table, json)

Examples:
  $ deepsecure vault status
  ┌──────────────────────┬────────────────┬──────────────────┬────────────┐
  │ Name                 │ Share Status   │ TTL Remaining    │ Health     │
  ├──────────────────────┼────────────────┼──────────────────┼────────────┤
  │ openai-api-key       │ ⚠️  EXPIRED    │ -6h 24m          │ 🔴 DEAD    │
  │ stripe-key           │ ✓ ACTIVE       │ 4h 12m           │ 🟡 WARNING │
  │ db-password          │ ✓ ACTIVE       │ 22h 45m          │ 🟢 HEALTHY │
  │ new-api-key          │ ✓ ACTIVE       │ 23h 58m          │ 🟢 HEALTHY │
  └──────────────────────┴────────────────┴──────────────────┴────────────┘
  
  Summary: 4 secrets (1 expired, 1 warning, 2 healthy)
  
  💡 Run 'deepsecure vault refresh openai-api-key' to recover expired secrets
     (requires re-storing the secret value)
```

### 3.2 Automatic Refresh Options

#### Option A: Access-Based Refresh (Touch to Extend)

Every successful `get-secret` operation automatically extends the TTL:

```python
# In deeptrail-gateway share_storage.py
async def get_share(self, secret_name: str, auto_extend: bool = True) -> Optional[ShareData]:
    """Retrieve share and optionally extend TTL."""
    share = await self._get_share_internal(secret_name)
    
    if share and auto_extend:
        # Extend TTL on every access (sliding window)
        current_ttl = await self.redis_client.ttl(f"share_2:{secret_name}")
        if current_ttl > 0 and current_ttl < 86400:  # Less than 24h
            await self.redis_client.expire(f"share_2:{secret_name}", 86400)
            logger.info(f"Auto-extended TTL for '{secret_name}'")
    
    return share
```

**Pros**: 
- Zero operational overhead for active secrets
- Frequently used secrets never expire

**Cons**:
- Unused secrets still expire (may be desirable)
- Harder to predict expiration times

#### Option B: Background Refresh Worker

A periodic job refreshes secrets approaching expiration:

```python
# In deeptrail-control - background_tasks.py
from celery import Celery
from datetime import timedelta

app = Celery('share_refresh')

@app.task
def refresh_expiring_shares():
    """Refresh shares with TTL < threshold."""
    threshold_seconds = 6 * 3600  # 6 hours
    
    # Query gateway for shares approaching expiration
    expiring_secrets = gateway_client.get_expiring_shares(threshold_seconds)
    
    for secret in expiring_secrets:
        if secret.auto_refresh_enabled:
            gateway_client.extend_share_ttl(secret.name, ttl=86400)
            audit_log.info(f"Auto-refreshed share for '{secret.name}'")

# Schedule: Run every 2 hours
app.conf.beat_schedule = {
    'refresh-shares': {
        'task': 'refresh_expiring_shares',
        'schedule': timedelta(hours=2),
    },
}
```

**Pros**:
- Predictable refresh behavior
- Works for all secrets, even unused ones
- Can be configured per-secret

**Cons**:
- Requires additional infrastructure (Celery, Redis, scheduler)
- Keeping stale secrets alive may not be desirable

### 3.3 Storage-Time TTL Configuration

Allow custom TTL when storing secrets:

```bash
# Store with custom TTL
$ deepsecure vault store api-key --ttl 7d --labels env=prod

# Update TTL for existing secret (requires re-fetch and re-store internally)
$ deepsecure vault set-ttl api-key 30d
```

```python
# API endpoint update
@router.post("/store")
def store_secret(
    secret_in: SecretStoreRequest,
    ttl_seconds: int = Query(default=86400, ge=3600, le=2592000),  # 1h to 30d
    db: Session = Depends(get_db),
):
    """Store secret with configurable TTL."""
    # Split secret into shares
    share_1, share_2 = split_secret(secret_in.value)
    
    # Store share_1 in database
    crud.secret.create(db, share_1=share_1, metadata=secret_in.metadata)
    
    # Store share_2 in gateway with custom TTL
    gateway_client.store_share(secret_in.name, share_2, ttl_seconds=ttl_seconds)
```

### 3.4 Secret Recovery (Expired Shares)

For secrets where share_2 has already expired:

```bash
$ deepsecure vault recover <secret-name>
⚠️  Secret 'openai-api-key' has an expired gateway share.

To recover this secret, you must provide the original value:
Secret Value: ********

✓ Secret 'openai-api-key' recovered with new shares
  New TTL: 24h (expires 2026-01-13 07:30 UTC)
```

This operation:
1. Accepts the original secret value from the user
2. Regenerates both shares using Shamir's algorithm
3. Updates share_1 in the database
4. Stores new share_2 in Redis with fresh TTL

---

## 4. API Endpoints

### Control Plane Endpoints

```yaml
# POST /api/v1/vault/secrets/{name}/refresh
# Refresh the TTL for a secret's gateway share
Request:
  ttl_seconds: 86400  # Optional, default 24h
Response:
  name: "openai-api-key"
  previous_ttl_seconds: 7200
  new_ttl_seconds: 86400
  expires_at: "2026-01-13T07:30:00Z"
  
# GET /api/v1/vault/secrets/status
# Get health status of all secrets
Response:
  secrets:
    - name: "openai-api-key"
      share_status: "expired"
      ttl_remaining_seconds: -23040
      health: "dead"
    - name: "stripe-key"
      share_status: "active"
      ttl_remaining_seconds: 14520
      health: "warning"
  summary:
    total: 4
    healthy: 2
    warning: 1
    expired: 1
```

### Gateway Internal Endpoints

```yaml
# POST /internal/shares/{name}/extend
# Extend TTL for a share (internal use only)
Headers:
  X-Internal-API-Token: <gateway_token>
Request:
  additional_seconds: 86400
Response:
  secret_name: "openai-api-key"
  new_ttl_seconds: 86400
  expires_at: "2026-01-13T07:30:00Z"

# GET /internal/shares/expiring?threshold=21600
# List shares expiring within threshold
Response:
  shares:
    - name: "stripe-key"
      ttl_remaining_seconds: 14520
    - name: "db-password"
      ttl_remaining_seconds: 3600
```

---

## 5. Security Considerations

### 5.1 TTL Trade-offs

| TTL Duration | Security | Availability | Use Case |
|--------------|----------|--------------|----------|
| 1 hour | 🟢 High | 🔴 Low | High-security, short-lived tokens |
| 24 hours | 🟡 Medium | 🟡 Medium | Default, balanced security |
| 7 days | 🔴 Lower | 🟢 High | Stable production secrets |
| 30 days | 🔴 Lowest | 🟢 Highest | Development, testing |

### 5.2 Audit Requirements

All refresh operations must be logged:

```json
{
  "event_type": "secret.share.refreshed",
  "timestamp": "2026-01-12T07:30:00Z",
  "actor": {
    "type": "user",
    "id": "user-123",
    "ip": "10.0.0.1"
  },
  "secret_name": "openai-api-key",
  "previous_ttl_seconds": 7200,
  "new_ttl_seconds": 86400,
  "refresh_method": "manual"  // or "auto", "access-based"
}
```

### 5.3 Rate Limiting

Prevent abuse of refresh endpoints:

```python
@router.post("/secrets/{name}/refresh")
@ratelimit(limit="10/minute", key="user_id")
def refresh_secret(name: str, ...):
    ...
```

### 5.4 Policy-Based Refresh Control

Enterprise environments may want to control who can refresh secrets:

```yaml
# policy.yml
policies:
  - name: "secret-refresh-policy"
    rules:
      - action: "vault:refresh"
        conditions:
          - role: ["admin", "secret-manager"]
          - mfa_verified: true
        constraints:
          - max_ttl_days: 7  # Cannot set TTL > 7 days
```

---

## 6. Implementation Phases

### Phase 1: Manual Refresh (MVP)

**Scope**: CLI command to manually refresh individual secrets

```bash
$ deepsecure vault refresh <name> [--ttl <duration>]
$ deepsecure vault status [--expiring]
```

**Effort**: 2-3 days

### Phase 2: Bulk Operations

**Scope**: Refresh multiple secrets at once with filtering

```bash
$ deepsecure vault refresh --all [--filter <labels>] [--min-ttl <duration>]
```

**Effort**: 1-2 days

### Phase 3: Custom Storage TTL

**Scope**: Allow TTL configuration at storage time

```bash
$ deepsecure vault store <name> --ttl <duration>
$ deepsecure vault set-ttl <name> <duration>
```

**Effort**: 2-3 days

### Phase 4: Automatic Refresh

**Scope**: Background worker for proactive refresh

**Effort**: 3-5 days (includes infrastructure setup)

### Phase 5: Access-Based Extension

**Scope**: Auto-extend TTL on every successful access

**Effort**: 1 day

---

## 7. Configuration Options

```yaml
# config.yml - Share refresh configuration
vault:
  shares:
    # Default TTL for new secrets (in seconds)
    default_ttl: 86400  # 24 hours
    
    # Maximum allowed TTL
    max_ttl: 2592000  # 30 days
    
    # Minimum TTL (security floor)
    min_ttl: 3600  # 1 hour
    
    # Auto-refresh settings
    auto_refresh:
      enabled: true
      threshold_seconds: 21600  # Refresh when TTL < 6h
      check_interval_seconds: 7200  # Check every 2h
      
    # Access-based extension
    extend_on_access:
      enabled: true
      extension_seconds: 86400  # Extend by 24h on each access
```

---

## 8. Metrics and Alerting

### Prometheus Metrics

```python
# Metrics for monitoring share health
share_ttl_seconds = Gauge(
    'deepsecure_share_ttl_seconds',
    'Remaining TTL for secret shares',
    ['secret_name', 'environment']
)

share_refresh_total = Counter(
    'deepsecure_share_refresh_total',
    'Total share refresh operations',
    ['method', 'status']  # method: manual, auto, access
)

shares_expired_total = Counter(
    'deepsecure_shares_expired_total',
    'Total expired shares',
    ['environment']
)
```

### Alert Rules

```yaml
# alerting-rules.yml
groups:
  - name: deepsecure-shares
    rules:
      - alert: SecretShareExpiringSoon
        expr: deepsecure_share_ttl_seconds < 3600
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Secret share expiring soon: {{ $labels.secret_name }}"
          
      - alert: SecretShareExpired
        expr: deepsecure_share_ttl_seconds <= 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Secret share EXPIRED: {{ $labels.secret_name }}"
```

---

## 9. Example Workflow

### Daily Operations

```bash
# Morning check: View secret health
$ deepsecure vault status
┌──────────────────────┬────────────────┬──────────────────┬────────────┐
│ Name                 │ Share Status   │ TTL Remaining    │ Health     │
├──────────────────────┼────────────────┼──────────────────┼────────────┤
│ openai-key           │ ✓ ACTIVE       │ 4h 30m           │ 🟡 WARNING │
│ stripe-key           │ ✓ ACTIVE       │ 18h 15m          │ 🟢 HEALTHY │
│ db-password          │ ⚠️ EXPIRED     │ -2h 10m          │ 🔴 DEAD    │
└──────────────────────┴────────────────┴──────────────────┴────────────┘

# Refresh the warning secret
$ deepsecure vault refresh openai-key
✓ Secret 'openai-key' refreshed (new TTL: 24h)

# Recover the expired secret (requires original value)
$ deepsecure vault recover db-password
Secret Value: ********
Confirm Value: ********
✓ Secret 'db-password' recovered (new TTL: 24h)

# Verify all healthy now
$ deepsecure vault status
✓ All 3 secrets healthy
```

### Automated Pipeline Integration

```yaml
# .github/workflows/refresh-secrets.yml
name: Refresh DeepSecure Secrets

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - name: Refresh production secrets
        env:
          DEEPSECURE_API_TOKEN: ${{ secrets.DEEPSECURE_TOKEN }}
        run: |
          pip install deepsecure
          deepsecure vault refresh --all --filter env=production --min-ttl 12h
```

---

## 10. Appendix: Error Messages

| Error | Cause | Resolution |
|-------|-------|------------|
| `Share not found in gateway` | share_2 has expired | Use `vault recover` with original value |
| `Secret not found` | Secret doesn't exist in database | Use `vault store` to create |
| `TTL exceeds maximum` | Requested TTL > max_ttl config | Reduce TTL or update config |
| `Refresh rate limited` | Too many refresh requests | Wait and retry |
| `Unauthorized for refresh` | Missing permission | Contact admin for access |

---

## 11. References

- [Split-Key Credential Architecture](./deepsecure-technical-overview.md#64-split-key-credential-architecture)
- [Shamir's Secret Sharing](https://en.wikipedia.org/wiki/Shamir%27s_secret_sharing)
- [Redis EXPIRE Command](https://redis.io/commands/expire/)
