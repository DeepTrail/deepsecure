# DeepSecure CLI: Ephemeral Credentials Design

## Requirements for Ephemeral Keys

For LLM-based AI agents and Model Context Protocol (MCP) servers that interact with tools, data sources, and APIs, the best protocols for generating ephemeral keys must satisfy these properties:

- 🔐 **Perfect Forward Secrecy (PFS)**: Ephemeral keys ensure compromise of a long-term key doesn't affect prior sessions.
- 🧠 **Agent-aware Auth**: Works in environments with autonomous, potentially multi-hop agents.
- 🔄 **Stateless or Low-state**: Allows scalable, repeatable interactions across short-lived or chained sessions.
- 🌐 **Works over HTTP / JSON-RPC**: Compatible with API-style agent calls, not just raw TCP.
- 🪪 **Identity Binding**: Ties ephemeral keys to verifiable agent or service identity.
- 📜 **Auditable & Enforceable**: Compatible with auditing, delegation, and policy enforcement mechanisms.

## Best Protocols for Ephemeral Key Use in AI Agent + MCP Workflows

| Protocol / Framework | Why It Works Well for AI + MCP | Notes |
|----------------------|--------------------------------|-------|
| Noise Protocol Framework | ⚡ Lightweight, ephemeral by default, flexible message patterns | Use XX or IK patterns. Widely used in WireGuard, Lightning, etc. |
| X3DH (from Signal Protocol) | 🤝 Designed for ephemeral+identity key blending, agent pairing, async setup | Pairs well with double-ratchet if needed for post-compromise security |
| TLS 1.3 (customized) | 🛡️ Secure, standardized, ephemeral-only key exchange (ECDHE) | Can be tunneled into gRPC/QUIC-based API infra; not ideal for stateless |
| ECDH (Curve25519) | 🔑 Low-cost ephemeral keys, ideal for short-lived agent sessions | Use in raw key exchange or with signature wrapping for binding |
| MLS (Messaging Layer Security) | 🧑‍🤝‍🧑 For multi-agent settings; supports PFS and group membership changes | More suited for chat/group scenarios; can inspire multi-agent handshake design |
| WebAuthn-like ephemeral key attestation | 🧾 Combines ephemeral key with attested device or agent identity | Ideal if you want to enforce origin-bound ephemeral identities |

## Recommended Strategy for MCP + LLM-based Agents

### 1. Use Curve25519 for ephemeral key exchange

- Fast, widely supported, secure
- Ideal for both JSON-based APIs and embedded agents
- Example: each agent/server generates ephemeral key pair (X25519) per interaction

### 2. Combine with identity proofs

- Sign ephemeral key with long-term identity key (Ed25519)
- Or use external attestations (e.g., signed device fingerprint, enclave attestation)

```python
# Ephemeral Key + Signature (agent)
ephemeral_pub, ephemeral_priv = generate_x25519_keypair()
signature = sign(ephemeral_pub, agent_identity_private_key)
send_to_peer(ephemeral_pub, signature)
```

### 3. Use Noise Framework for embedded agent-to-agent or tool communication

- Patterns like XX and IK support mutual ephemeral key exchanges + identity auth
- Extremely efficient and great for stateless JSON-RPC agents

### 4. Bind ephemeral keys to agent context (MCP)

- Include ephemeral key in MCP session header or auth payload
- Example: agent signs its ephemeral_pub_key + mcp_session_id with its long-term key

```json
{
  "mcp_auth": {
    "ephemeral_pub_key": "base64...",
    "signature": "base64...",
    "session_id": "uuid-123..."
  }
}
```

### 5. Rotate ephemeral keys per tool or data access

- For multi-tool workflows, generate a new ephemeral key per external call
- Combine with signed delegation: Agent A gives Agent B a signed token scoped to a single tool/data call

## Protocol Comparison for Agent-Based Workflows

| Property | Noise Protocol | X3DH | TLS 1.3 | Raw ECDH + Sig | WebAuthn-style |
|----------|---------------|------|---------|----------------|----------------|
| Ephemeral key by default | ✅ | ✅ | ✅ (always) | ✅ | ✅ |
| Identity + ephemeral combined | ✅ | ✅ | ✅ (via certs) | ✅ (manual) | ✅ |
| Stateless / cacheable sessions | ✅ | ⚠️ async setup | ❌ | ✅ | ✅ |
| JSON-RPC / tool-call compatible | ✅ | ✅ | ❌ (binary) | ✅ | ✅ |
| Attestation or integrity binding | ❌ (needs ext) | ✅ | ✅ (cert) | ⚠️ custom logic | ✅ |
| Post-compromise healing (ratchet) | ❌ | ✅ | ❌ | ❌ | ❌ |

## Integrations with MCP Servers

- Use Noise IK or XX between agent and MCP server for secure bootstrap
- Embed ephemeral key in init, authorize, or toolcall steps
- Add ephemeral signing hook in mcps/mcp_audit_proxy.py and mcps/risk/* to:
  - Validate identity-bound ephemeral keys
  - Log ephemeral-to-long-term binding
  - Enforce key rotation policy

## Optional Enhancements

- **Threshold signatures over ephemeral keys**: For secure delegation from multiple signing authorities (e.g., quorum-based authorization for tool access)
- **Hardware-backed ephemeral keys**: (e.g., enclaves or TPMs) for trustworthy agent/device attestation
- **Sessionless encryption**: Use Noise's stateless mode for fast, fire-and-forget tool calls without handshakes
