## DeepSecure Python SDK - API Overview

This document lists the primary functions exposed by the Python SDK, grouped by category. These reflect the current surface area of `deepsecure.Client` and its namespaces.

### Core
- properties: `control_url`, `gateway_url`, `version`

### Identity and Authentication
- `authenticate(agent_id) -> str`
- `login(agent_id) -> str` (alias of `authenticate`)
- `get_access_token(agent_id) -> str`
- `bootstrap_kubernetes(k8s_token, agent_id=None) -> httpx.Response`
- `bootstrap_aws(iam_token, agent_id=None) -> httpx.Response`
- `bootstrap_azure(imds_token, agent_id=None) -> httpx.Response`
- `bootstrap_docker(runtime_token, agent_id=None) -> httpx.Response`

### Agents
- `get_agent(name, auto_create=True) -> Agent`
- `list_agents() -> List[Dict]`
- Namespace `client.agents` (alias: `client.agent`)
  - `create(name, description=None) -> Agent`
  - `create_agent_unauthenticated(public_key, name, description) -> Dict`
  - `register_agent(public_key, name, description, agent_id=None) -> Dict`
  - `list_agents(skip=0, limit=100) -> Dict`
  - `describe_agent(agent_id) -> Optional[Dict]`
  - `update_agent(agent_id, update_data) -> Dict`
  - `delete_agent(agent_id) -> Dict`
  - `get_by_name(name, auto_create=False) -> Agent`

### Policies
- `policy.create(name, agent_id, actions, resources, effect='allow') -> PolicyResponse`
- `policy.list() -> List[PolicyResponse]`
- `policy.get(policy_id) -> PolicyResponse`
- `policy.delete(policy_id) -> Dict`
- `policy.create_attestation_policy(policy_data) -> Dict`
- `policy.list_attestation_policies() -> List[Dict]`
- `policy.get_attestation_policy(policy_id) -> Dict`
- `policy.update_attestation_policy(policy_id, update_data) -> Dict`
- `policy.delete_attestation_policy(policy_id) -> Dict`

### Vault (programmatic + admin)
- `vault.issue(scope, agent_id, ttl, origin_binding=True, passed_origin_context=None)`
- `vault.verify(credential_id)`
- `vault.revoke(credential_id)`
- `vault.store_secret(name, value, target_base_url, labels=None, metadata=None) -> Dict`
- `vault.get_secret_admin(name) -> Dict`
- `vault.list_secrets_admin() -> Dict`

### Credentials (thin wrappers)
- `credentials.issue(agent_id, scope, ttl_seconds=300, origin_binding=True, origin_context=None)`
- `credentials.verify(credential_id)`
- `credentials.revoke(credential_id)`

### Gateway
- `gateway.request(agent_id, target_base_url, path, method='GET', headers=None, params=None, json=None, data=None, content=None, stream=False, timeout=30.0) -> httpx.Response | stream`

### Service wrappers
- `openai.list_models(agent_id) -> httpx.Response`
- `openai.chat_completions(agent_id, body, stream=False) -> httpx.Response | stream`
- Admin/legacy helpers under `openai`:
  - `openai.store_secret_direct(name, value, target_base_url, metadata=None) -> Dict`
  - `openai.delete_secret(agent_id, name, delegation_token=None) -> None`
  - `openai.list_secrets(agent_id, delegation_token=None) -> List[Dict]`
  - [Deprecated] Use `vault.get_secret_admin(name)` instead of `openai.get_secret_direct(name)`.

### Delegation
- `delegate_access(delegator_agent_id, target_agent_id, resource, permissions, ttl_seconds=300, additional_restrictions=None) -> str`
- `create_delegation_chain(chain_spec) -> Dict[str, str]`
- `verify_delegation(delegation_token, request_context) -> (bool, str, Dict)`

### Agent resource sugar
- `Agent.issue_credential(scope, ttl=300) -> Credential`
- `Agent.get_secret(secret_name, path='/') -> SecretResourceType`
- `Agent.gateway_request(target_base_url, path, method='GET', headers=None, params=None, json=None, data=None, content=None, stream=False, timeout=30.0) -> httpx.Response | stream`
- `Agent.openai_list_models() -> httpx.Response`

