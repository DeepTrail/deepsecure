# Enterprise Key Custody Design for DeepSecure Agents (1Password / HashiCorp Vault)

This document describes an enterprise-ready design for managing DeepSecure agent keys using 1Password or HashiCorp Vault. It aligns to DeepSecure’s model (public key in the Control Plane; private key never leaves enterprise custody) and emphasizes remote signing, strong RBAC, auditability, rotation, and recovery.

## Goals
- Keep private keys off endpoints when possible; prefer remote signing.
- Enforce least-privilege access, comprehensive audit, and reliable rotation.
- Maintain compatibility with existing challenge–response authentication and agent workflows.

## Control Plane Data Model
- **Public key**: Stored in the Control Plane DB per agent (as today).
- **Key metadata**: Add fields for `key_origin` (e.g., `vault_transit` | `onepassword_remote_sign` | `kv` | `os_keyring` | `split_key`), `key_id`/`version`, and rotation state (`current`/`next`).

## Patterns

### 1) Remote-sign (preferred) with HashiCorp Vault Transit (optionally HSM-backed)
- **Where**: Vault Transit engine (can be backed by HSM/KMS).
- **How**:
  - Create asymmetric key in Transit (prefer Ed25519; use supported plugins where needed).
  - Store only the key handle; private material never leaves Vault.
  - Agent authenticates to Vault (K8s/JWT, AWS IAM, OIDC) and calls `transit/sign` to sign the server nonce.
  - Control Plane verifies the signature using the agent’s registered public key.
- **Benefits**: No private key on host; strong policy + audit; easy rotation via key versions.
- **Considerations**: Network latency, token caching, strict Vault policies per agent path, TLS pinning, HA Vault cluster.

### 2) 1Password Secrets Automation (KV or remote signing service)
- **Where**: 1Password Secrets Automation/Service Account with restricted scopes.
- **Options**:
  - **Remote-sign (recommended)**: A thin internal service (or 1Password integration) performs signing so the agent never materializes the key.
  - **KV-backed**: Private key stored in an item; agent retrieves into memory only for signing (avoid persisting to disk).
- **Benefits**: Enterprise RBAC and audit; mature rotation workflows.
- **Considerations**: Prefer remote-sign; if KV-backed, enforce ephemeral usage and strong per-item ACLs.

### 3) Split-key (DeepSecure-native) for high assurance
- **Where**: Split the private key into shares (e.g., Gateway share + Vault share).
- **How**:
  - During bootstrap, generate a key and store shares separately (e.g., Vault Transit share + Gateway JIT share).
  - For a signature, Gateway obtains its share locally and requests a signature fragment from Vault; perform threshold sign or JIT reassembly; return the signature.
- **Benefits**: Compromise of any single store is insufficient; JIT reassembly reduces dwell time of full key.
- **Considerations**: Operational complexity; align with Gateway JIT pipeline; validate performance.

### 4) Agent-held private key in enterprise store (fallback)
- **Where**: KV in Vault (KV v2) or 1Password item.
- **How**:
  - Agent fetches the key at runtime into OS keyring/memory; perform local signing.
  - Strict read-only access per agent; audit every fetch; prefer ephemeral use.
- **Benefits**: Simple adoption path.
- **Considerations**: Higher endpoint risk; use short TTL tokens and robust audit.

## Bootstrap & Identity
- **Kubernetes**: Authenticate to Vault via Kubernetes auth; bind SA→Vault policy; no static credentials.
- **AWS/Azure**: Use IAM/IMDS auth for short-lived Vault tokens.
- **Enrollment**: Upon registration, Control Plane stores public key + metadata (origin, key_id).
- **Origin binding (optional)**: Include `origin_context` in issued credentials for forensics.

## Rotation
- **Vault Transit**:
  - Rotate key (new version); publish new public key to Control Plane; support an overlap window where both pubkeys verify; revoke old version after grace period.
- **1Password**:
  - Create new item; update Control Plane pubkey; provide dual-pubkey grace period.
- **CLI**:
  - `deepsecure agent rotate-identity` orchestrates upload and cutover.

## Access Control & Audit
- **Per-agent policies**:
  - Vault namespaces/paths: `transit/keys/agents/<agent-id>` and `transit/sign/agents/<agent-id>`.
  - 1Password per-agent vaults or per-item ACLs.
- **Least privilege**: Issuing agent can only sign its own nonces; disallow raw key export in remote-sign models.
- **Audit**:
  - Control Plane: audit trail for auth and policy ops.
  - Vault/1Password: forward access logs to SIEM; include correlation IDs on challenges.

## Resilience & Recovery
- **HA**: Vault cluster with auto-unseal; 1Password HA/regions.
- **Backup**: Snapshot Vault metadata (private keys remain sealed/HSM-backed); enterprise DR for 1Password.
- **Break-glass**: Tightly scoped emergency group; MFA + short-lifetime approvals; mandatory post-incident rotation.

## Performance & Latency
- Use keep-alives and token caching for remote-sign requests.
- Co-locate Vault/remote-sign service with Control Plane; configure timeouts, retries, backoff.
- Include `key_id` in challenge/response to route to the correct signer/version.

## Security Posture
- Prefer **remote-sign** (Vault Transit or a 1Password-backed signer) so private keys never materialize on endpoints.
- mTLS to Vault/service; CA pinning; least-privilege network egress; endpoint hardening.
- Regular key rotation; enforce key lifetime SLAs.

## DeepSecure Integration Hooks
- **Pluggable identity providers**:
  - `vault_transit`: `sign(agent_id, data) -> signature`; `publish_public_key()` updates Control Plane.
  - `onepassword_remote_sign`: call enterprise signer; KV variant for fallback.
  - `split_key`: orchestrate threshold/JIT signing.
- **Configuration**:
  ```yaml
  identity:
    private_key_provider: vault_transit | onepassword_remote_sign | onepassword_kv | os_keyring | split_key
    vault:
      addr: https://vault.example.com
      role: agents
      mount: transit
      key_name_template: agents/{{agent_id}}
      tls:
        ca_file: /etc/ssl/certs/ca-bundle.crt
    onepassword:
      service_url: https://1p-signer.example.com
      token: ${OP_SERVICE_TOKEN}
      vault: agents
      item_template: agents/{{agent_id}}
  ```
- **CLI/SDK**:
  - `deepsecure agent create` supports provider selection/metadata.
  - `deepsecure login` consults provider for remote signing of nonce.

## Summary
- **Best default**: Vault Transit (or HSM-backed) remote signing.
- **1Password**: Prefer a remote-sign microservice; KV-only as a fallback with strict ephemeral usage.
- **Control Plane**: Stores public key + metadata; all private key operations are delegated to the enterprise custodian with strong RBAC, audit, and rotation.