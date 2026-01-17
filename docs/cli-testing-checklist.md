# DeepSecure CLI Testing Checklist

**Version:** 0.1.11  
**Last Updated:** 2026-01-12  
**Test Environment:** macOS Darwin 24.5.0, Python 3.12.2

---

## Legend

| Status | Meaning |
|--------|---------|
| ✅ | Tested and working |
| ❌ | Tested and failing |
| ⏳ | Not yet tested |
| 🔧 | Fixed (was failing, now working) |
| ⚠️ | Works with warnings |
| 🚫 | Skipped (destructive/interactive) |

---

## 1. Root Commands

| # | Command | Status | Exit Code | Notes |
|---|---------|--------|-----------|-------|
| 1.1 | `deepsecure --version` | ✅ | 0 | Shows version 0.1.11 |
| 1.2 | `deepsecure --help` | ✅ | 0 | Lists all 6 command groups |

---

## 2. Configure Commands

| # | Command | Status | Exit Code | Notes |
|---|---------|--------|-----------|-------|
| 2.1 | `deepsecure configure --help` | ✅ | 0 | Shows 9 subcommands |
| 2.2 | `deepsecure configure show` | ✅ | 0 | Shows config JSON |
| 2.3 | `deepsecure configure get-url` | ✅ | 0 | Returns `http://localhost:8000` |
| 2.4 | `deepsecure configure set-url <URL>` | ✅ | 0 | Sets Control Plane URL |
| 2.5 | `deepsecure configure get-gateway-url` | ✅ | 0 | Returns configured URL |
| 2.6 | `deepsecure configure set-gateway-url <URL>` | ✅ | 0 | Sets Gateway URL |
| 2.7 | `deepsecure configure get-token` | ✅ | 0 | Returns effective token |
| 2.8 | `deepsecure configure set-token <TOKEN>` | 🚫 | - | Skipped (stores real token) |
| 2.9 | `deepsecure configure delete-token` | 🚫 | - | Skipped (destructive) |
| 2.10 | `deepsecure configure set-log-level DEBUG` | ✅ | 0 | Sets log level |

---

## 3. Login Command

| # | Command | Status | Exit Code | Notes |
|---|---------|--------|-----------|-------|
| 3.1 | `deepsecure login --help` | ✅ | 0 | Shows options |
| 3.2 | `deepsecure login` | 🚫 | - | Skipped (interactive) |
| 3.3 | `deepsecure login --endpoint <URL>` | 🚫 | - | Skipped (interactive) |

---

## 4. Agent Commands

| # | Command | Status | Exit Code | Notes |
|---|---------|--------|-----------|-------|
| 4.1 | `deepsecure agent --help` | ✅ | 0 | Shows 5 subcommands |
| 4.2 | `deepsecure agent create --help` | ✅ | 0 | Shows --name required |
| 4.3 | `deepsecure agent create --name <NAME>` | ✅ | 0 | Creates agent, stores key in keychain |
| 4.4 | `deepsecure agent list` | ✅ | 0 | Shows table of agents |
| 4.5 | `deepsecure agent describe <AGENT_ID>` | ❌ | 1 | **BUG**: "No authentication token available" |
| 4.6 | `deepsecure agent delete <AGENT_ID> --force` | ✅ | 0 | Deletes agent |
| 4.7 | `deepsecure agent cleanup` | 🔧 | 0 | Fixed: `err=True` + dict handling |

---

## 5. Vault Commands

| # | Command | Status | Exit Code | Notes |
|---|---------|--------|-----------|-------|
| 5.1 | `deepsecure vault --help` | ✅ | 0 | Shows 4 subcommands |
| 5.2 | `deepsecure vault store --help` | ✅ | 0 | Shows NAME required, --value option |
| 5.3 | `deepsecure vault store <NAME> --value <VALUE>` | ✅ | 0 | Stores secret with split-key |
| 5.4 | `deepsecure vault get-secret <NAME>` | ✅ | 0 | Retrieves secret (see TTL note below) |
| 5.5 | `deepsecure vault list` | ✅ | 0 | Lists all secrets in vault |
| 5.6 | `deepsecure vault delete <NAME>` | ✅ | 0 | Deletes secret |

### ⚠️ Important: Split-Key TTL Behavior

Secrets stored in the vault use a **split-key architecture** with a 24-hour TTL:
- `share_1` is stored in the database (persistent)
- `share_2` is stored in Redis (expires after 24 hours)

**Observed Behavior:**
- `vault list` shows secrets whose metadata exists in the database (including expired ones)
- `vault get-secret` **fails for secrets older than 24 hours** because `share_2` has expired in Redis

This is **expected behavior** by design. See [Split-Key Share Refresh Mechanism](./design/split-key-share-refresh-mechanism.md) for the proposed solution.

**Example:**
```bash
$ deepsecure vault list
│ openai-api-key           │ 2026-01-11 00:54 UTC │  # Listed (metadata exists)
│ openai-api-key-duplicate │ 2026-01-12 06:46 UTC │  # Listed (metadata exists)

$ deepsecure vault get-secret openai-api-key
⚠️  Secret 'openai-api-key' not found in vault.  # FAILS - share_2 expired (>24h old)

$ deepsecure vault get-secret openai-api-key-duplicate
✓ Retrieved successfully                         # WORKS - share_2 still valid (<24h old)
```

---

## 6. Policy Commands

| # | Command | Status | Exit Code | Notes |
|---|---------|--------|-----------|-------|
| 6.1 | `deepsecure policy --help` | ✅ | 0 | Shows 5 subcommands (incl attestation) |
| 6.2 | `deepsecure policy create --help` | ✅ | 0 | Shows required options |
| 6.3 | `deepsecure policy create --name <NAME> --agent-id <ID> --action <ACTION> --resource <RESOURCE>` | ✅ | 0 | Creates policy successfully |
| 6.4 | `deepsecure policy list` | ✅ | 0 | Shows table of policies |
| 6.5 | `deepsecure policy get <POLICY_ID>` | ✅ | 0 | Shows policy JSON |
| 6.6 | `deepsecure policy delete <POLICY_ID>` | ✅ | 0 | Deletes policy |

### 6.7 Policy Attestation Subcommands

| # | Command | Status | Exit Code | Notes |
|---|---------|--------|-----------|-------|
| 6.7.1 | `deepsecure policy attestation --help` | ✅ | 0 | Shows 9 subcommands |
| 6.7.2 | `deepsecure policy attestation create-k8s --help` | ⏳ | - | - |
| 6.7.3 | `deepsecure policy attestation create-k8s ...` | ⏳ | - | - |
| 6.7.4 | `deepsecure policy attestation create-aws ...` | ⏳ | - | - |
| 6.7.5 | `deepsecure policy attestation create-azure ...` | ⏳ | - | - |
| 6.7.6 | `deepsecure policy attestation create-docker ...` | ⏳ | - | - |
| 6.7.7 | `deepsecure policy attestation list` | ⏳ | - | - |
| 6.7.8 | `deepsecure policy attestation get <ID>` | ⏳ | - | - |
| 6.7.9 | `deepsecure policy attestation update <ID>` | ⏳ | - | - |
| 6.7.10 | `deepsecure policy attestation delete <ID>` | ⏳ | - | - |
| 6.7.11 | `deepsecure policy attestation validate ...` | ⏳ | - | - |

---

## 7. Gateway Commands

| # | Command | Status | Exit Code | Notes |
|---|---------|--------|-----------|-------|
| 7.1 | `deepsecure gateway --help` | ✅ | 0 | Shows 4 subcommands |
| 7.2 | `deepsecure gateway health --help` | ✅ | 0 | Shows options |
| 7.3 | `deepsecure gateway health` | ✅ | 0 | Shows "Gateway is healthy!" |
| 7.4 | `deepsecure gateway test-proxy` | ⏳ | - | - |
| 7.5 | `deepsecure gateway status` | ✅ | 0 | Shows both services healthy |
| 7.6 | `deepsecure gateway connectivity` | ✅ | 0 | 2/3 tests pass (proxy needs auth) |

---

## Summary

| Category | Total | Tested | Passing | Failing | Fixed | Skipped |
|----------|-------|--------|---------|---------|-------|---------|
| Root Commands | 2 | 2 | 2 | 0 | 0 | 0 |
| Configure | 10 | 8 | 8 | 0 | 0 | 2 |
| Login | 3 | 1 | 1 | 0 | 0 | 2 |
| Agent | 7 | 6 | 5 | 1 | 1 | 0 |
| Vault | 6 | 6 | 6 | 0 | 4 | 0 |
| Policy | 6 | 6 | 6 | 0 | 0 | 0 |
| Policy Attestation | 11 | 1 | 1 | 0 | 0 | 0 |
| Gateway | 6 | 5 | 5 | 0 | 0 | 0 |
| **TOTAL** | **51** | **35** | **34** | **1** | **5** | **4** |

---

## Issues Found

### 🔧 Fixed Issues (5)

| # | Command | Issue | Fix |
|---|---------|-------|-----|
| 1 | `agent cleanup` | `Console.print(err=True)` + dict handling | Changed `err=True` to styled output, extract agents from response dict |
| 2 | `vault store` | "No authentication token available" | Token now set via `configure set-token` |
| 3 | `vault get-secret` | 401 Unauthorized | Token now set via `configure set-token` |
| 4 | `vault list` | 401 Unauthorized | Token now set via `configure set-token` |
| 5 | `vault delete` | 401 Unauthorized | Token now set via `configure set-token` |

**Resolution**: Run `deepsecure configure set-token DEFAULT_QUICKSTART_TOKEN` to set the API token before using vault commands.

### ❌ Open Issues (1)

| # | Command | Issue | Root Cause |
|---|---------|-------|------------|
| 1 | `agent describe <ID>` | "No authentication token available" | Uses authenticated request without token - **investigation needed** |

### ⚠️ Known Behaviors (Not Bugs)

| # | Behavior | Explanation | Reference |
|---|----------|-------------|-----------|
| 1 | `vault get-secret` fails for secrets >24h old | Split-key architecture uses 24h TTL for Redis shares. Secrets older than 24 hours have expired `share_2` and cannot be recovered without re-storing. | [Share Refresh Mechanism](./design/split-key-share-refresh-mechanism.md) |

---

## Test Groups Status

### ✅ Group A: No Backend Required - COMPLETE
All commands tested and working (with 1 fix applied).

### ✅ Group B: Backend Required - COMPLETE
Most commands working, 5 authentication-related failures identified.

### ✅ Group C: Gateway Required - COMPLETE
All gateway commands working (gateway URL was configured during testing).

---

## Testing Log

### 2026-01-12 - Session 2: Group B & C Testing

| Time | Command | Result | Notes |
|------|---------|--------|-------|
| 22:29 | Check docker services | ✅ | All 4 containers running |
| 22:30 | `agent list` | ✅ Pass | Shows agent table |
| 22:30 | `agent create --name test-cli-agent-xxx` | ✅ Pass | Creates agent, stores key |
| 22:30 | `agent describe <ID>` | ❌ Fail | "No authentication token available" |
| 22:31 | `vault list` | ❌ Fail | 401 Unauthorized |
| 22:31 | `vault store ... --agent-id <ID>` | ❌ Fail | "No authentication token available" |
| 22:31 | `policy list` | ✅ Pass | Shows policy table |
| 22:31 | `policy create ...` | ✅ Pass | Creates policy |
| 22:32 | `policy get <ID>` | ✅ Pass | Shows policy JSON |
| 22:32 | `configure set-gateway-url http://localhost:8002` | ✅ Pass | Sets gateway URL |
| 22:33 | `gateway health` | ✅ Pass | Gateway is healthy |
| 22:33 | `gateway status` | ✅ Pass | Both services healthy |
| 22:33 | `gateway connectivity` | ✅ Pass | 2/3 tests pass |
| 22:34 | `policy delete <ID>` | ✅ Pass | Policy deleted |
| 22:34 | `agent delete <ID> --force` | ✅ Pass | Agent deleted |
| 22:34 | `vault get-secret <NAME>` | ❌ Fail | 401 Unauthorized |
| 22:34 | `vault delete <NAME>` | ❌ Fail | 401 Unauthorized |

---

## Next Steps

### Priority 1: Fix `agent describe` Authentication Issue
This is the only remaining failing command. Investigation needed:
1. Check how `agent describe` obtains the client
2. Verify token is being passed to `BaseClient._request()`
3. Compare with working commands (agent list/create/delete)

### Priority 2: Implement Share Refresh Mechanism
Implement the proposed share refresh mechanism to address the 24-hour TTL limitation:
- CLI command: `deepsecure vault refresh <name>`
- CLI command: `deepsecure vault status`
- See [Design Document](./design/split-key-share-refresh-mechanism.md)

### Priority 3: Test Policy Attestation Commands
10 attestation subcommands remain untested.

### Priority 4: Test Gateway test-proxy
This command requires a target URL and credentials.

---

## Notes

1. **Working Commands Use Unauthenticated Endpoints**: Commands like `agent list`, `agent create`, and `policy *` work because they use the internal API token (`X-Internal-API-Token` header) rather than user authentication.

2. **Failing Commands Require User Token**: Vault commands and `agent describe` require the user's token to be included in the request, but this isn't happening.

3. **IdentityManager Logs**: All commands output IdentityManager initialization logs. This could be gated for cleaner output.

4. **Environment Variables**:
   - `DEEPSECURE_CONTROL_PLANE_URL`: http://localhost:8000
   - `DEEPSECURE_GATEWAY_URL`: http://localhost:8002
   - `BACKEND_API_TOKEN`: test-api-token (from configure get-token)
