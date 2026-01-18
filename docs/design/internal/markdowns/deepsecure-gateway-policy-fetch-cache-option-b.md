## Implementation Plan: Gateway fetch-and-cache per-agent policies (Option B)

### Goal
- Enforce control-plane path-level policies in the gateway by fetching an agent’s policies on-demand and caching them briefly.
- Deny requests that violate domain/method/path constraints defined in the control plane.

### High-level design
- On each proxied request, the middleware has `agent_id`, `request.method`, `X-Target-Base-URL` (domain) and the composed path.
- The gateway maintains an in-memory cache: `agent_id → compiled policy set with expiry (TTL)`.
- If cache miss or expired, gateway calls control plane to fetch policies for that agent:
  - `GET /api/v1/policies?agent_id=agent-<uuid>` (add if not present; otherwise fetch all and filter client-side).
- Compile fetched policies into a fast-evaluable structure:
  - Allowed domains
  - Allowed methods
  - Allowed resources (patterns for URLs/paths; e.g., prefix/glob)
- Enforce on each request:
  - Domain check: `target_domain ∈ allowed_domains`
  - Method check: `method ∈ allowed_methods` (optionally per-resource rules)
  - Path check: composed URL/path matches at least one resource rule
  - Decision: allow or return 403 with reason.

### Detailed steps
1) Control Plane API support
   - Add optional filter to list policies by `agent_id`:
     - `GET /api/v1/policies?agent_id=agent-<uuid>`
     - Response: array of policy objects
   - If not adding the filter, gateway can fetch all policies and filter client-side, but server-side filtering is cleaner.

2) Gateway policy client
   - Add a small async client in gateway (e.g., `app/core/policy_client.py`) to call control-plane:
     - Requires control-plane base URL (existing: `http://deeptrail-control:8001`)
     - Auth: No admin token if endpoint is protected by an internal role; otherwise use an internal token header
     - Method: `async def fetch_policies_for_agent(agent_id: str) -> List[Policy]`
     - Include retry/backoff logic on transient errors.

3) Cache layer
   - In-memory dict with TTL:
     - `Dict[str, CachedEntry]`, where `CachedEntry = { compiled: CompiledPolicy, expires_at: float }`
     - TTL default: 60s (configurable in gateway config)
   - Functions:
     - `get_cached(agent_id)` → `CompiledPolicy | None`
     - `set_cached(agent_id, compiled)`
     - `invalidate(agent_id)` (for future push invalidation)

4) Compiled policy structure
```python
class CompiledPolicy:
    allowed_domains: set[str]
    allowed_methods: set[str]  # global or per-domain
    resource_rules: list[ResourceRule]

class ResourceRule:
    method: str | None        # None → any
    domain: str | None        # None → any
    pattern: str              # normalized path or URL pattern
    match_type: Literal['prefix','glob','regex']  # start with 'prefix'
```
- Compiler: translate control-plane resources (full URLs or wildcards) into normalized rules:
  - If resource starts with `http(s)://domain/path` → `domain = parsed`, `pattern = path`
  - If resource is only path → `domain=None`, `pattern = path`
  - If resource ends with `/*` or `*` → `match_type='prefix'` with trimmed pattern
  - Else exact match via prefix on full path (or exact if preferred)

5) Middleware integration
- In `PolicyEnforcementMiddleware.dispatch()`:
  - Extract `agent_id`, `target_url` (domain), HTTP method, and path (already available)
  - `policy = cache.get(agent_id)`
  - If `None` or expired:
    - `policies = await policy_client.fetch_policies_for_agent(agent_id)`
    - `compiled = compile(policies)`  // also derive allowed_domains/methods from policies or keep JWT/config logic as defaults
    - `cache.set(agent_id, compiled)`
  - Evaluate:
    - Check domain against `compiled.allowed_domains` (or derive from resource rules)
    - Check method against `compiled.allowed_methods` (or derive from resource rules)
    - Compose request URL/path and match against `compiled.resource_rules`
  - If any check fails → return 403 with reason; else call next.

6) Configuration
- Add to `proxy_config.py`:
  - `policy_cache_ttl_seconds: int` (default 60)
  - `policy_enforcement_mode: "strict" | "permissive" | "disabled"` (reuse existing)
  - `policy_match_strategy: "prefix" | "glob" | "regex"` (default `"prefix"`)
- Add to `/config` response for observability.

7) Observability and errors
- Log cache hits/misses and TTL (debug)
- Log deny decisions with reason (domain/method/path mismatch)
- Return consistent error bodies: `{ "detail": "Access denied: <reason>" }`

8) Testing plan
- Unit tests for compiler:
  - Parse full URL resources, path-only resources, and wildcard patterns
  - Method-specific vs method-agnostic rules
- Unit tests for cache TTL logic
- Middleware tests:
  - Given a compiled policy, verify allow/deny for various domain/method/path combos
  - Cache miss triggers fetch; cache hit avoids fetch
- Integration tests:
  - Simulate control-plane policies for agent; gateway requests hit allow or deny correctly
  - TTL expiry refreshes policy

9) Security considerations
- Validate `agent_id` format (`agent-<uuid>`) before calling control plane
- Timeouts and retries for control-plane fetch
- Consider rate limiting policy fetches per agent to avoid thundering herds

10) Future enhancements
- Push-based invalidation: control-plane POSTs to gateway `/internal/policy-invalidate?agent_id=...`
- Per-resource method binding: enforce method if `rule.method` is set
- Fine-grained effects (allow/deny rules ordering)
- Negative rules support (explicit denies)

### Deliverables
- Gateway:
  - `app/core/policy_client.py`
  - Cache in `app/middleware/policy_enforcement.py` or a shared `app/core/policy_cache.py`
  - Compiler in `app/core/policy_compiler.py`
  - Config additions in `app/core/proxy_config.py`
- Control Plane:
  - Optional: add `GET /policies?agent_id=` filter
- Docs:
  - Update `docs/openapi.yaml` for control-plane filter (if added)
  - Add a paragraph in gateway docs about policy fetch & cache with TTL and evaluation strategy

