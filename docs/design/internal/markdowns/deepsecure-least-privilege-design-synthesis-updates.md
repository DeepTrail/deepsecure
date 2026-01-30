# Synthesis: Updates to Least-Privilege Design for AI Agents

## Overview

This document synthesizes the concepts from four key research documents with the existing `least-privilege-design-for-ai-agents.md` architecture. It identifies **gaps**, **enhancements**, and **new components** that should be incorporated into the design.

### Source Documents Analyzed:
1. **Agent_Permission.pdf** (MiniScope Paper) - Academic framework for tool-calling agent authorization
2. **Building_a_permission_tree_and_hierarchy.pdf** - Design patterns for hierarchical permissions
3. **Implementing_Least-Privilege_Access_in_Tool-Calling_AI_Agents.pdf** - Implementation strategies by agent category
4. **Techniques_+_system_design_for_per-task_least_privilege.pdf** - Technical design stack

---

## Table of Contents

1. [Executive Summary of Required Updates](#1-executive-summary-of-required-updates)
2. [MiniScope Framework Integration](#2-miniscope-framework-integration)
3. [Permission Hierarchy Reconstruction Algorithm](#3-permission-hierarchy-reconstruction-algorithm)
4. [Execution Graph and Intent Analysis](#4-execution-graph-and-intent-analysis)
5. [Minimal Permission Computation (ILP Solver)](#5-minimal-permission-computation-ilp-solver)
6. [Session-Based Permission Model Enhancement](#6-session-based-permission-model-enhancement)
7. [Tooling Integration Layer](#7-tooling-integration-layer)
8. [Agent Category Implementation Analysis](#8-agent-category-implementation-analysis)
9. [Formal Security Properties](#9-formal-security-properties)
10. [Updated Architecture Diagrams](#10-updated-architecture-diagrams)
11. [Implementation Priority Matrix](#11-implementation-priority-matrix)

---

## 1. Executive Summary of Required Updates

### Existing Design Strengths
The current `least-privilege-design-for-ai-agents.md` provides:
- ✅ Solid four-party agent classification model
- ✅ Comprehensive permission tree structure
- ✅ Per-task dynamic permission scoping concept
- ✅ Party-specific security controls
- ✅ Integration with existing DeepSecure architecture

### Critical Gaps to Address

| Gap | Source Document | Priority | Complexity |
|-----|-----------------|----------|------------|
| **MiniScope Framework** - Formal least-privilege computation | Agent_Permission.pdf | Critical | High |
| **Execution Graph Extraction** - Dynamic permission derivation | Techniques PDF | Critical | High |
| **ILP/Solver for Minimal Permissions** - Automated optimization | Agent_Permission.pdf | High | Medium |
| **Permission Hierarchy Reconstruction** - From OAuth scopes | Techniques PDF | High | Medium |
| **Session-Based Permission Modes** - Allow once/session/always | Agent_Permission.pdf | Medium | Low |
| **Tooling Integration Layer** - Tool-to-permission mapping | Techniques PDF | High | Medium |
| **Formal Security Proofs** - Guarantees and properties | Agent_Permission.pdf | Medium | Low |
| **Implementation Difficulty Analysis** - Per agent category | Implementing PDF | Medium | Low |

---

## 2. MiniScope Framework Integration

### 2.1 What is MiniScope?

MiniScope (from Agent_Permission.pdf) is a **formal framework** for authorizing tool-calling AI agents with rigorous least-privilege guarantees. It provides:

1. **Hierarchical Permission Model** - Permissions form a DAG (Directed Acyclic Graph) where parent permissions subsume children
2. **Automated Permission Computation** - Uses Integer Linear Programming (ILP) to find minimal permission sets
3. **Session-Based Authorization** - Four modes: Always allow, Allow this session, Allow once, Don't allow
4. **Execution Graph Analysis** - Derives required permissions from agent's planned tool calls

### 2.2 Required Updates to Existing Design

#### Update 1: Add MiniScope Core Components

```yaml
# NEW SECTION: Add to least-privilege-design-for-ai-agents.md
## MiniScope Framework Integration

### Core Components

miniscope_framework:
  # Component 1: Permission Hierarchy
  permission_hierarchy:
    description: "DAG structure where permissions have parent-child relationships"
    properties:
      - "Granting parent automatically grants all descendants"
      - "Multiple paths to same permission allowed (DAG not tree)"
      - "Leaf permissions are most specific"
      - "Root permissions are most general"
    
  # Component 2: Execution Graph
  execution_graph:
    description: "Graph representing agent's planned or observed tool calls"
    nodes:
      - type: "tool_call"
        attributes: ["function_name", "parameters", "dependencies"]
      - type: "permission_requirement"
        attributes: ["required_permissions", "constraints"]
    edges:
      - type: "depends_on"
        description: "Tool call depends on output of another"
      - type: "requires"
        description: "Tool call requires specific permission"
  
  # Component 3: Permission Solver
  permission_solver:
    description: "Computes minimal permission set for execution graph"
    algorithms:
      primary: "integer_linear_programming"
      fallback: "greedy_set_cover"
    output: "minimal_permission_set"
  
  # Component 4: Session Controller
  session_controller:
    description: "Manages permission grants across session lifecycle"
    modes:
      - "always_allow"      # Persist across all sessions
      - "allow_this_session" # Valid until session ends
      - "allow_once"        # Single use, immediately revoked
      - "dont_allow"        # Explicit denial
```

#### Update 2: Integrate with Existing Task Model

The existing design has a Task Definition Schema. This should be **enhanced** to include MiniScope's execution graph:

```yaml
# ENHANCED: Task Definition Schema
task:
  id: "task-20250108-summary-q3-sales"
  name: "Summarize Q3 Sales Performance"
  agent_id: "agent-analytics-001"
  
  # ... existing fields ...
  
  # NEW: Execution Graph
  execution_graph:
    nodes:
      - id: "node-1"
        type: "tool_call"
        function: "openai.chat.completions.create"
        parameters:
          model: "gpt-4"
          messages: "{{input}}"
        requires_permissions:
          - "urn:deepsecure:service:openai:chat_completions"
      
      - id: "node-2"
        type: "tool_call"
        function: "database.query"
        parameters:
          query: "SELECT * FROM sales WHERE quarter='Q3'"
        requires_permissions:
          - "urn:deepsecure:data:sales:read"
        depends_on: []
      
      - id: "node-3"
        type: "tool_call"
        function: "storage.write"
        parameters:
          path: "/reports/q3-summary.md"
        requires_permissions:
          - "urn:deepsecure:storage:reports:write"
        depends_on: ["node-1", "node-2"]
    
    edges:
      - from: "node-2"
        to: "node-1"
        type: "data_flow"
      - from: "node-1"
        to: "node-3"
        type: "data_flow"
  
  # NEW: Computed Minimal Permissions (from solver)
  computed_permissions:
    solver: "ilp"
    minimal_set:
      - permission: "urn:deepsecure:service:openai:chat_completions"
        constraints: {model: "gpt-4", max_tokens: 4000}
      - permission: "urn:deepsecure:data:sales:read"
        constraints: {quarter: "Q3", columns: ["amount", "region"]}
      - permission: "urn:deepsecure:storage:reports:write"
        constraints: {path_pattern: "/reports/q3-*.md"}
    solver_stats:
      computation_time_ms: 45
      permissions_requested: 3
      permissions_optimized: 3
      reduction_ratio: 1.0
```

---

## 3. Permission Hierarchy Reconstruction Algorithm

### 3.1 Gap in Existing Design

The existing design defines a static permission tree. The research documents describe **dynamic hierarchy reconstruction** from OAuth scopes and API documentation.

### 3.2 Algorithm from Research

From `Techniques_+_system_design_for_per-task_least_privilege.pdf`:

```
ALGORITHM: Reconstruct Permission Hierarchy from OAuth Scopes

Input: Set of OAuth scopes S, API method definitions M
Output: Permission hierarchy H (DAG)

1. For each scope s in S:
   a. Identify all API methods m ∈ M authorized by s
   b. Create scope node: H.add_node(s, methods=m)

2. For each pair of scopes (s1, s2):
   a. If methods(s1) ⊃ methods(s2):  # s1 authorizes strict superset
      b. Add edge: H.add_edge(s1 → s2)  # s1 is parent of s2

3. Optimize hierarchy:
   a. Remove transitive edges (keep only direct parent-child)
   b. For multiple potential parents, choose minimal strict superset

4. Return H
```

### 3.3 New Component to Add

```yaml
# NEW SECTION: Permission Hierarchy Reconstruction
permission_hierarchy_reconstruction:
  
  # Source: OAuth/API definitions
  sources:
    - type: "oauth_scopes"
      provider: "openai"
      scopes:
        - name: "models.read"
          methods: ["GET /models", "GET /models/{id}"]
        - name: "completions.create"
          methods: ["POST /chat/completions", "POST /completions"]
        - name: "all"
          methods: ["*"]  # Authorizes everything
    
    - type: "api_documentation"
      provider: "stripe"
      openapi_spec: "https://api.stripe.com/openapi.yaml"
  
  # Reconstruction process
  process:
    - step: "extract_scopes"
      description: "Parse OAuth scope definitions"
    
    - step: "map_methods"
      description: "Map each scope to authorized API methods"
    
    - step: "compute_subsumption"
      description: "Determine parent-child relationships via set containment"
    
    - step: "build_dag"
      description: "Construct DAG with minimal edges"
    
    - step: "validate"
      description: "Ensure no cycles, complete coverage"
  
  # Output format
  output:
    format: "permission_dag"
    storage: "control_plane_database"
    cache: "gateway_memory"
    refresh_interval: "daily"
```

### 3.4 Implementation Pseudocode

```python
# NEW: Add to SDK/Control Plane
class PermissionHierarchyBuilder:
    """
    Reconstructs permission hierarchy from OAuth scopes and API definitions.
    Based on MiniScope research methodology.
    """
    
    def __init__(self, api_definitions: List[APIDefinition]):
        self.api_definitions = api_definitions
        self.hierarchy = DAG()
    
    def build_from_oauth_scopes(self, scopes: List[OAuthScope]) -> DAG:
        """
        Build permission hierarchy from OAuth scope definitions.
        
        Algorithm:
        1. Map each scope to its authorized methods
        2. Compute subsumption relationships
        3. Build minimal DAG
        """
        # Step 1: Map scopes to methods
        scope_methods = {}
        for scope in scopes:
            scope_methods[scope.name] = set(scope.authorized_methods)
        
        # Step 2: Compute parent-child relationships
        for s1, methods1 in scope_methods.items():
            for s2, methods2 in scope_methods.items():
                if s1 != s2 and methods1.issuperset(methods2):
                    # s1 is potential parent of s2
                    self._add_parent_child(s1, s2, methods1, methods2)
        
        # Step 3: Remove transitive edges
        self._minimize_edges()
        
        return self.hierarchy
    
    def _add_parent_child(self, parent: str, child: str, 
                          parent_methods: Set, child_methods: Set):
        """Add parent-child edge if it's the minimal superset."""
        # Check if there's a closer parent
        existing_parents = self.hierarchy.get_parents(child)
        for existing in existing_parents:
            existing_methods = self.hierarchy.get_methods(existing)
            if parent_methods.issuperset(existing_methods):
                # Existing parent is closer, skip
                return
            if existing_methods.issuperset(parent_methods):
                # New parent is closer, remove existing
                self.hierarchy.remove_edge(existing, child)
        
        self.hierarchy.add_edge(parent, child)
    
    def _minimize_edges(self):
        """Remove transitive edges to keep hierarchy minimal."""
        # Use transitive reduction algorithm
        self.hierarchy = transitive_reduction(self.hierarchy)
```

---

## 4. Execution Graph and Intent Analysis

### 4.1 Gap in Existing Design

The existing design mentions "declared intent" but lacks a formal model for extracting and analyzing agent execution plans.

### 4.2 Execution Graph Model from Research

```yaml
# NEW SECTION: Execution Graph Model
execution_graph_model:
  
  description: |
    An Execution Graph represents the planned or observed sequence of tool
    calls an agent will make. It enables:
    1. Pre-flight permission validation
    2. Minimal permission computation
    3. Runtime permission enforcement
    4. Audit trail generation
  
  # Graph structure
  structure:
    nodes:
      tool_call_node:
        id: "string (unique)"
        function_name: "string (tool function name)"
        function_signature: "string (parameter types)"
        parameters: "object (actual parameter values)"
        required_permissions: "list (permission URNs)"
        estimated_cost: "number (optional, for cost constraints)"
        estimated_tokens: "number (optional, for token constraints)"
      
      decision_node:
        id: "string"
        condition: "string (branching condition)"
        branches: "list (node IDs for each branch)"
      
      aggregation_node:
        id: "string"
        aggregation_type: "enum (all, any, first)"
        inputs: "list (node IDs to aggregate)"
    
    edges:
      data_dependency:
        from_node: "string"
        to_node: "string"
        data_type: "string (type of data passed)"
      
      control_dependency:
        from_node: "string"
        to_node: "string"
        condition: "string (optional condition)"
  
  # Extraction methods
  extraction:
    static_analysis:
      description: "Parse agent code to extract tool call graph"
      applicable_to: ["first_party", "second_party_integrated"]
      accuracy: "high"
      limitations: ["dynamic tool selection", "conditional branches"]
    
    plan_declaration:
      description: "Agent declares execution plan before running"
      applicable_to: ["all"]
      accuracy: "depends on agent honesty"
      enforcement: "runtime validation against declared plan"
    
    runtime_observation:
      description: "Build graph by observing actual tool calls"
      applicable_to: ["all"]
      accuracy: "perfect (after fact)"
      use_case: "audit, anomaly detection, learning"
    
    llm_plan_extraction:
      description: "Use LLM to generate execution plan from task description"
      applicable_to: ["all"]
      accuracy: "medium"
      use_case: "pre-approval workflow"
```

### 4.3 Integration with Task Model

```python
# NEW: ExecutionGraphExtractor class
class ExecutionGraphExtractor:
    """
    Extracts execution graphs from various sources.
    """
    
    async def extract_from_agent_code(
        self, 
        agent_code: str,
        entry_point: str
    ) -> ExecutionGraph:
        """
        Static analysis of agent code to extract potential tool calls.
        Uses AST parsing and data flow analysis.
        """
        pass
    
    async def extract_from_plan_declaration(
        self,
        plan: TaskPlan
    ) -> ExecutionGraph:
        """
        Convert declared task plan to execution graph.
        Agent explicitly declares what tools it will call.
        """
        pass
    
    async def extract_from_task_description(
        self,
        task_description: str,
        available_tools: List[ToolDefinition]
    ) -> ExecutionGraph:
        """
        Use LLM to infer execution graph from natural language task.
        Useful for pre-approval workflows.
        """
        pass
    
    async def build_from_runtime(
        self,
        task_id: str,
        tool_calls: List[ToolCallRecord]
    ) -> ExecutionGraph:
        """
        Build graph from observed runtime tool calls.
        Used for audit and learning.
        """
        pass
```

---

## 5. Minimal Permission Computation (ILP Solver)

### 5.1 Gap in Existing Design

The existing design specifies permission requirements but lacks automated **optimization** to find the minimal permission set.

### 5.2 ILP Formulation from MiniScope

From `Agent_Permission.pdf`:

```
FORMULATION: Minimal Permission Set as Integer Linear Program

Given:
- Permission hierarchy H = (P, E) where P = permissions, E = parent-child edges
- Required API methods M = {m1, m2, ..., mn}
- Permission-method mapping: methods(p) = set of methods authorized by p

Variables:
- x_p ∈ {0, 1} for each p ∈ P (1 if permission is granted)

Objective:
- Minimize: Σ_p w_p * x_p
  where w_p = weight of permission (e.g., scope breadth, risk level)

Constraints:
- Coverage: For each required method m ∈ M:
  Σ_{p: m ∈ methods(p)} x_p ≥ 1
  (At least one permission must cover each method)

- Hierarchy: For each parent-child pair (p, c) ∈ E:
  x_c ≤ x_p
  (If child is granted, parent must also be granted... OR...)
  
  Actually in MiniScope: If parent is granted, children are implicit.
  So constraint is: Don't double-count parent and children.

Optional Constraints:
- Maximum permissions: Σ_p x_p ≤ k
- Risk budget: Σ_p risk(p) * x_p ≤ R
- Cost budget: Σ_p cost(p) * x_p ≤ C
```

### 5.3 New Component: Permission Solver

```yaml
# NEW SECTION: Permission Solver
permission_solver:
  
  description: |
    The Permission Solver computes the minimal set of permissions needed
    to authorize a given execution graph. It uses Integer Linear Programming
    (ILP) as the primary algorithm with fallback alternatives.
  
  # Primary algorithm
  primary_algorithm:
    name: "integer_linear_programming"
    implementation: "ortools.linear_solver"
    
    inputs:
      - permission_hierarchy: "DAG of permissions"
      - required_methods: "Set of API methods from execution graph"
      - permission_weights: "Risk/cost weights per permission"
      - constraints: "Budget constraints (risk, cost, count)"
    
    output:
      minimal_permissions: "List of permission URNs to grant"
      solver_stats:
        computation_time_ms: "number"
        explored_nodes: "number"
        optimal: "boolean"
  
  # Fallback algorithms (when ILP is too slow or infeasible)
  fallback_algorithms:
    
    - name: "greedy_set_cover"
      description: "Greedy approximation: pick permission covering most uncovered methods"
      complexity: "O(n * m)"
      approximation_ratio: "ln(m) where m = number of methods"
      when_to_use: "Large permission spaces, real-time requirements"
    
    - name: "branch_and_bound"
      description: "Exact algorithm with pruning"
      complexity: "O(2^n) worst case, often faster in practice"
      when_to_use: "Small permission spaces, need exact solution"
    
    - name: "precomputed_minimal_sets"
      description: "Cache minimal permission sets for common method combinations"
      complexity: "O(1) lookup"
      when_to_use: "Repeated similar requests, batch processing"
    
    - name: "two_stage_solver"
      description: "Quick heuristic + ILP refinement"
      complexity: "O(n*m) + ILP on reduced set"
      when_to_use: "Balance between speed and optimality"
  
  # Configuration
  configuration:
    timeout_ms: 1000
    fallback_on_timeout: "greedy_set_cover"
    cache_results: true
    cache_ttl_seconds: 3600
```

### 5.4 Implementation

```python
# NEW: PermissionSolver class
from ortools.linear_solver import pywraplp

class PermissionSolver:
    """
    Computes minimal permission set using ILP.
    Based on MiniScope framework.
    """
    
    def __init__(
        self,
        hierarchy: PermissionHierarchy,
        timeout_ms: int = 1000
    ):
        self.hierarchy = hierarchy
        self.timeout_ms = timeout_ms
    
    def solve(
        self,
        required_methods: Set[str],
        weights: Optional[Dict[str, float]] = None,
        constraints: Optional[SolverConstraints] = None
    ) -> SolverResult:
        """
        Find minimal permission set covering all required methods.
        
        Args:
            required_methods: Set of API method identifiers
            weights: Optional weights per permission (default: all 1.0)
            constraints: Optional budget constraints
        
        Returns:
            SolverResult with minimal permissions and stats
        """
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            return self._fallback_greedy(required_methods)
        
        solver.SetTimeLimit(self.timeout_ms)
        
        # Create binary variable for each permission
        perm_vars = {}
        for perm in self.hierarchy.all_permissions():
            perm_vars[perm] = solver.IntVar(0, 1, perm)
        
        # Objective: minimize weighted sum
        objective = solver.Objective()
        for perm, var in perm_vars.items():
            weight = weights.get(perm, 1.0) if weights else 1.0
            objective.SetCoefficient(var, weight)
        objective.SetMinimization()
        
        # Constraint: each method must be covered
        for method in required_methods:
            covering_perms = self.hierarchy.permissions_covering(method)
            constraint = solver.Constraint(1, solver.infinity())
            for perm in covering_perms:
                constraint.SetCoefficient(perm_vars[perm], 1)
        
        # Optional constraints
        if constraints:
            self._add_constraints(solver, perm_vars, constraints)
        
        # Solve
        status = solver.Solve()
        
        if status == pywraplp.Solver.OPTIMAL:
            return SolverResult(
                permissions=[p for p, v in perm_vars.items() if v.solution_value() > 0.5],
                optimal=True,
                computation_time_ms=solver.wall_time(),
                algorithm="ilp"
            )
        elif status == pywraplp.Solver.FEASIBLE:
            return SolverResult(
                permissions=[p for p, v in perm_vars.items() if v.solution_value() > 0.5],
                optimal=False,
                computation_time_ms=solver.wall_time(),
                algorithm="ilp"
            )
        else:
            return self._fallback_greedy(required_methods)
    
    def _fallback_greedy(self, required_methods: Set[str]) -> SolverResult:
        """Greedy set cover fallback."""
        uncovered = set(required_methods)
        selected = []
        
        while uncovered:
            # Find permission covering most uncovered methods
            best_perm = None
            best_coverage = 0
            for perm in self.hierarchy.all_permissions():
                coverage = len(uncovered & self.hierarchy.methods_of(perm))
                if coverage > best_coverage:
                    best_coverage = coverage
                    best_perm = perm
            
            if best_perm is None:
                break
            
            selected.append(best_perm)
            uncovered -= self.hierarchy.methods_of(best_perm)
        
        return SolverResult(
            permissions=selected,
            optimal=False,
            algorithm="greedy"
        )
```

---

## 6. Session-Based Permission Model Enhancement

### 6.1 Gap in Existing Design

The existing design has temporal constraints but lacks the **four-mode session model** from MiniScope.

### 6.2 Session Permission Modes

From `Agent_Permission.pdf`:

```yaml
# NEW/ENHANCED SECTION: Session Permission Modes
session_permission_model:
  
  description: |
    Permissions can be granted with different persistence levels,
    allowing fine-grained control over how long permissions remain active.
  
  modes:
    always_allow:
      description: "Permission persists indefinitely across all sessions"
      persistence: "permanent"
      storage: "agent_policy_table"
      revocation: "explicit_only"
      use_cases:
        - "Core capabilities the agent always needs"
        - "Well-established trust relationships"
      risk_level: "highest"
      audit_frequency: "periodic_review"
    
    allow_this_session:
      description: "Permission valid until session ends"
      persistence: "session"
      storage: "session_cache (Redis)"
      revocation: "automatic_on_session_end"
      session_definition:
        - "Task completion"
        - "Explicit session termination"
        - "Timeout (configurable)"
        - "Agent restart"
      use_cases:
        - "Task-specific permissions"
        - "Interactive agent sessions"
      risk_level: "medium"
    
    allow_once:
      description: "Single use, immediately revoked after use"
      persistence: "single_use"
      storage: "ephemeral (in-memory)"
      revocation: "automatic_after_single_use"
      use_cases:
        - "High-risk operations"
        - "Explicit user approval workflows"
        - "Sensitive data access"
      risk_level: "lowest"
      implementation_note: "Must track usage count, revoke after 1"
    
    dont_allow:
      description: "Explicit denial, blocks permission even if parent grants"
      persistence: "permanent"
      storage: "agent_policy_table"
      override: "deny_takes_precedence"
      use_cases:
        - "Compliance requirements"
        - "Explicit restrictions"
        - "Temporary suspensions"
      risk_level: "n/a"
  
  # API for managing session permissions
  api:
    grant_permission:
      endpoint: "POST /api/v1/permissions/grant"
      body:
        agent_id: "string"
        permission_urn: "string"
        mode: "enum (always_allow, allow_this_session, allow_once)"
        constraints: "object (optional)"
        session_id: "string (required for session/once modes)"
    
    check_permission:
      endpoint: "POST /api/v1/permissions/check"
      body:
        agent_id: "string"
        permission_urn: "string"
        session_id: "string (optional)"
      response:
        allowed: "boolean"
        mode: "string"
        remaining_uses: "number (for allow_once)"
        expires_at: "timestamp (for session)"
    
    revoke_permission:
      endpoint: "DELETE /api/v1/permissions/grant/{grant_id}"
```

### 6.3 Integration with Existing Temporal Constraints

```yaml
# ENHANCED: Constraint Types (merge with existing)
constraint_types:
  temporal:
    # ... existing constraints ...
    
    # NEW: Session-based constraints
    - type: "session_bound"
      description: "Permission valid only within session"
      mode: "allow_this_session"
      example:
        session_id: "session-abc123"
        session_timeout_minutes: 60
    
    - type: "single_use"
      description: "Permission valid for exactly one use"
      mode: "allow_once"
      example:
        use_count: 1
        revoke_on_use: true
```

---

## 7. Tooling Integration Layer

### 7.1 Gap in Existing Design

The existing design assumes permissions map directly to resources but lacks a formal **tool-to-permission mapping** layer.

### 7.2 Tooling Integration from Research

From `Techniques_+_system_design_for_per-task_least_privilege.pdf`:

```yaml
# NEW SECTION: Tooling Integration Layer
tooling_integration:
  
  description: |
    Maps agent tool functions to underlying API methods and permissions.
    Essential for computing required permissions from execution graphs.
  
  # Tool Definition Schema
  tool_definition:
    name: "string (function name as seen by agent)"
    description: "string (human-readable description)"
    provider: "string (API provider: openai, stripe, etc.)"
    
    # Mapping to API methods
    api_mapping:
      method: "string (HTTP method)"
      endpoint: "string (API endpoint pattern)"
      parameters:
        - name: "string"
          type: "string"
          source: "enum (function_arg, config, secret)"
          required: "boolean"
    
    # Required permissions
    required_permissions:
      - urn: "string (permission URN)"
        constraints_from_params:
          # Map function parameters to permission constraints
          param_name: "constraint_field"
    
    # Cost estimation
    cost_model:
      type: "enum (per_call, per_token, per_byte)"
      rate: "number"
      unit: "string"
  
  # Example: OpenAI Chat Completions Tool
  examples:
    - name: "openai_chat_completion"
      description: "Generate chat completions using OpenAI"
      provider: "openai"
      
      api_mapping:
        method: "POST"
        endpoint: "/v1/chat/completions"
        parameters:
          - name: "model"
            type: "string"
            source: "function_arg"
            required: true
          - name: "messages"
            type: "array"
            source: "function_arg"
            required: true
          - name: "api_key"
            type: "string"
            source: "secret"
            required: true
      
      required_permissions:
        - urn: "urn:deepsecure:service:openai:chat_completions"
          constraints_from_params:
            model: "model"  # model param -> model constraint
            max_tokens: "max_tokens"
      
      cost_model:
        type: "per_token"
        rate:
          gpt-4: 0.00003  # per input token
          gpt-3.5-turbo: 0.000001
    
    - name: "stripe_create_payment"
      description: "Create a Stripe payment intent"
      provider: "stripe"
      
      api_mapping:
        method: "POST"
        endpoint: "/v1/payment_intents"
        parameters:
          - name: "amount"
            type: "integer"
            source: "function_arg"
            required: true
          - name: "currency"
            type: "string"
            source: "function_arg"
            required: true
      
      required_permissions:
        - urn: "urn:deepsecure:service:stripe:payment_intents:create"
          constraints_from_params:
            max_amount: "amount"
      
      cost_model:
        type: "per_call"
        rate: 0.029  # 2.9% + $0.30
  
  # Tool Registry API
  registry_api:
    register_tool:
      endpoint: "POST /api/v1/tools"
      body: "ToolDefinition"
    
    get_tool:
      endpoint: "GET /api/v1/tools/{tool_name}"
    
    get_permissions_for_tool:
      endpoint: "GET /api/v1/tools/{tool_name}/permissions"
      response:
        required_permissions: "list"
        constraints_template: "object"
```

### 7.3 Tool Wrapper Implementation

```python
# NEW: Tool wrapper that enforces permission validation
class PermissionValidatedTool:
    """
    Wraps agent tools with permission validation.
    """
    
    def __init__(
        self,
        tool_definition: ToolDefinition,
        permission_checker: PermissionChecker
    ):
        self.tool_definition = tool_definition
        self.permission_checker = permission_checker
    
    async def __call__(self, *args, **kwargs):
        """
        Execute tool after validating permissions.
        """
        # Extract permission constraints from arguments
        constraints = self._extract_constraints(kwargs)
        
        # Check permissions
        for perm in self.tool_definition.required_permissions:
            merged_constraints = {**perm.constraints, **constraints}
            
            result = await self.permission_checker.check(
                permission_urn=perm.urn,
                constraints=merged_constraints
            )
            
            if not result.allowed:
                raise PermissionDeniedError(
                    f"Permission {perm.urn} denied: {result.reason}"
                )
        
        # Execute actual tool
        return await self._execute_tool(*args, **kwargs)
    
    def _extract_constraints(self, kwargs: Dict) -> Dict:
        """Extract permission constraints from function arguments."""
        constraints = {}
        for param, constraint_field in self.tool_definition.constraints_from_params.items():
            if param in kwargs:
                constraints[constraint_field] = kwargs[param]
        return constraints
```

---

## 8. Agent Category Implementation Analysis

### 8.1 Gap in Existing Design

The existing design has the four-party model but lacks **implementation difficulty analysis** and **risk assessment** from the research.

### 8.2 Implementation Analysis from Research

From `Implementing_Least-Privilege_Access_in_Tool-Calling_AI_Agents.pdf`:

```yaml
# ENHANCED SECTION: Agent Category Implementation Analysis
agent_category_implementation:
  
  first_party:
    implementation_ease: "EASIEST"
    reasoning: |
      - Full control over agent code
      - Can instrument tool calls at source
      - Can enforce arbitrary constraints
      - Direct integration with permission system
    
    architectural_hooks:
      code_level:
        - "Function decorators for permission checks"
        - "Tool wrapper classes"
        - "AST instrumentation for static analysis"
      runtime_level:
        - "SDK integration with automatic validation"
        - "Execution graph extraction from code"
    
    recommended_approach:
      primary: "Pre-flight permission computation via execution graph"
      secondary: "Runtime validation at tool invocation"
      audit: "Complete logging of all tool calls"
    
    risks:
      - risk: "Developer bypasses permission checks"
        mitigation: "Mandatory code review, linting rules"
      - risk: "Permissions too broad"
        mitigation: "ILP solver for minimal permissions"
    
    implementation_effort: "2-4 weeks"
  
  second_party_vendor_managed:
    implementation_ease: "HARDEST"
    reasoning: |
      - No access to agent runtime
      - Cannot instrument tool calls
      - Must rely on vendor's enforcement
      - Limited visibility into agent behavior
    
    architectural_hooks:
      api_level:
        - "Capability tokens for each request"
        - "Gateway-enforced constraints"
        - "Request/response filtering"
      contract_level:
        - "Contractual permission limits"
        - "Audit log requirements in SLA"
    
    recommended_approach:
      primary: "Capability tokens with cryptographic binding"
      secondary: "Gateway-level enforcement (all traffic proxied)"
      audit: "Reconciliation with vendor logs"
    
    risks:
      - risk: "Vendor doesn't enforce permissions internally"
        mitigation: "Regular audits, breach clauses in contract"
      - risk: "Data exposure to vendor"
        mitigation: "Never expose raw secrets, use token exchange"
      - risk: "Audit log gaps"
        mitigation: "Automated reconciliation, anomaly detection"
    
    implementation_effort: "8-12 weeks"
    vendor_dependencies:
      - "Vendor must support capability tokens"
      - "Vendor must provide audit logs"
      - "Vendor must respect gateway-issued constraints"
  
  second_party_vendor_integrated:
    implementation_ease: "MODERATE"
    reasoning: |
      - Full runtime control (runs in our infra)
      - Limited code visibility (vendor library)
      - Can sandbox and monitor
      - Can instrument at network/syscall level
    
    architectural_hooks:
      sandbox_level:
        - "Container isolation"
        - "Network policy (egress through gateway only)"
        - "Filesystem restrictions"
        - "Syscall filtering"
      network_level:
        - "All API calls through gateway"
        - "Request/response validation"
        - "Traffic analysis"
    
    recommended_approach:
      primary: "Sandboxed execution with gateway enforcement"
      secondary: "Runtime behavior monitoring"
      audit: "Complete (we control infra)"
    
    risks:
      - risk: "Sandbox escape"
        mitigation: "Defense in depth, regular security testing"
      - risk: "Supply chain attack in vendor library"
        mitigation: "Version pinning, vulnerability scanning"
      - risk: "Unexpected behavior from black-box code"
        mitigation: "Behavioral anomaly detection"
    
    implementation_effort: "4-8 weeks"
  
  third_party:
    implementation_ease: "MODERATE-HARD"
    reasoning: |
      - No control over agent
      - Assume malicious intent
      - Must enforce everything at edge
      - Zero trust architecture required
    
    architectural_hooks:
      edge_level:
        - "WAF and rate limiting"
        - "Capability token validation"
        - "Response filtering"
      isolation_level:
        - "Separate infrastructure"
        - "No internal network access"
    
    recommended_approach:
      primary: "Zero-trust capability tokens"
      secondary: "Aggressive rate limiting and anomaly detection"
      audit: "Complete (they only see our edge)"
    
    risks:
      - risk: "Capability token theft"
        mitigation: "Short TTL, cryptographic binding to source"
      - risk: "Enumeration attacks"
        mitigation: "Rate limiting, honeypots"
      - risk: "Data scraping"
        mitigation: "Response filtering, quotas"
    
    implementation_effort: "4-6 weeks"
```

### 8.3 Decision Matrix for Implementation Priority

```
IMPLEMENTATION PRIORITY MATRIX
═══════════════════════════════════════════════════════════════════

              │ Impact │ Effort │ Risk    │ Priority │ Phase
──────────────┼────────┼────────┼─────────┼──────────┼────────
1st Party     │ HIGH   │ LOW    │ LOW     │ P0       │ Phase 1
2nd-Integrated│ HIGH   │ MEDIUM │ MEDIUM  │ P1       │ Phase 2
3rd Party     │ MEDIUM │ MEDIUM │ HIGH    │ P1       │ Phase 2
2nd-Managed   │ LOW    │ HIGH   │ HIGH    │ P2       │ Phase 3

RECOMMENDATION: 
Start with 1st party agents (most control, lowest risk, highest ROI)
Then 2nd-party integrated (sandbox approach reusable)
Then 3rd party (similar to integrated but edge-focused)
Finally vendor-managed (requires vendor cooperation)
```

---

## 9. Formal Security Properties

### 9.1 Gap in Existing Design

The existing design lacks **formal security guarantees** from the MiniScope paper.

### 9.2 Security Properties from Research

From `Agent_Permission.pdf`:

```yaml
# NEW SECTION: Formal Security Properties
security_properties:
  
  # Property 1: Minimal Authorization
  minimal_authorization:
    definition: |
      The set of permissions granted to an agent for a task T is 
      minimal if no proper subset of those permissions is sufficient 
      to complete T.
    
    formal: |
      ∀ T, P: granted(T) = P ⟹ ∄ P' ⊂ P : sufficient(P', T)
    
    enforcement:
      - "ILP solver computes minimal set"
      - "No additional permissions granted beyond solver output"
    
    verification:
      - "Permission audit: compare granted vs. used"
      - "Unused permissions indicate non-minimality"
  
  # Property 2: Monotonic Attenuation
  monotonic_attenuation:
    definition: |
      When an agent delegates permissions to another agent, the 
      delegated permissions are always a (non-strict) subset of 
      the delegating agent's permissions.
    
    formal: |
      ∀ A1, A2: delegates(A1, A2, P) ⟹ P ⊆ permissions(A1)
    
    enforcement:
      - "Delegation validation at control plane"
      - "Macaroon caveats for cryptographic enforcement"
    
    verification:
      - "Delegation chain audit"
      - "Compare each level's permissions"
  
  # Property 3: Temporal Boundedness
  temporal_boundedness:
    definition: |
      All task-scoped permissions have a finite validity period
      that is bounded by the task's deadline plus a grace period.
    
    formal: |
      ∀ T, P: task_permission(T, P) ⟹ 
        expires(P) ≤ deadline(T) + grace_period
    
    enforcement:
      - "TTL on all scoped permission records"
      - "Automatic revocation on task completion"
      - "Periodic sweep for expired permissions"
    
    verification:
      - "Audit for permissions used after expiration"
      - "Alert on long-lived task permissions"
  
  # Property 4: Non-Circumvention
  non_circumvention:
    definition: |
      There exists no path for an agent to access a resource without 
      passing through the permission enforcement point.
    
    formal: |
      ∀ A, R: accesses(A, R) ⟹ ∃ check : enforced(check, A, R)
    
    enforcement:
      - "All traffic through gateway (network policy)"
      - "Secret injection only at gateway"
      - "No direct API access from agent"
    
    verification:
      - "Network audit: detect direct API calls"
      - "Penetration testing"
  
  # Property 5: Complete Auditability
  complete_auditability:
    definition: |
      Every permission grant, use, and revocation is logged with 
      sufficient detail to reconstruct the authorization state at 
      any point in time.
    
    formal: |
      ∀ t, A, P: state(A, P, t) = 
        reconstruct(audit_log(A, P, t0 → t))
    
    enforcement:
      - "Immutable audit logs"
      - "Correlation IDs across systems"
    
    verification:
      - "State reconstruction tests"
      - "Log completeness audits"
```

---

## 10. Updated Architecture Diagrams

### 10.1 Enhanced Permission Flow with MiniScope

```
ENHANCED PERMISSION FLOW (with MiniScope Integration)
═══════════════════════════════════════════════════════════════════

  ┌─────────────┐
  │   AGENT     │
  │  (Any Type) │
  └──────┬──────┘
         │ 1. Submit Task with Intent
         ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                    TASK MANAGER                               │
  │  ┌─────────────────────────────────────────────────────────┐ │
  │  │              EXECUTION GRAPH EXTRACTOR                  │ │
  │  │  • Parse task description                               │ │
  │  │  • Identify required tool calls                         │ │
  │  │  • Build dependency graph                               │ │
  │  └─────────────────────────────────────────────────────────┘ │
  └────────────────────────┬─────────────────────────────────────┘
                           │ 2. Execution Graph
                           ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                   PERMISSION SOLVER                           │
  │  ┌─────────────────┐  ┌────────────────┐  ┌───────────────┐ │
  │  │ Permission      │  │ ILP Solver     │  │ Constraint    │ │
  │  │ Hierarchy       │→ │ (MiniScope)    │→ │ Application   │ │
  │  │ (DAG)           │  │                │  │               │ │
  │  └─────────────────┘  └────────────────┘  └───────────────┘ │
  │         ↑                     │                              │
  │         │                     │ 3. Minimal Permission Set    │
  │  ┌──────┴──────────┐          │                              │
  │  │ Tool Registry   │          │                              │
  │  │ (Tool→Perm Map) │          │                              │
  │  └─────────────────┘          │                              │
  └───────────────────────────────┼──────────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                   POLICY ENGINE (PDP)                         │
  │  ┌─────────────────────────────────────────────────────────┐ │
  │  │ • Validate minimal set against agent's base policy      │ │
  │  │ • Apply party-type-specific rules                       │ │
  │  │ • Check delegation chain (if applicable)                │ │
  │  │ • Determine session mode (always/session/once)          │ │
  │  └─────────────────────────────────────────────────────────┘ │
  └────────────────────────┬─────────────────────────────────────┘
                           │ 4. Scoped Permissions
                           ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                  PERMISSION STORE                             │
  │  ┌─────────────────────────────────────────────────────────┐ │
  │  │ • Store scoped permissions with TTL                     │ │
  │  │ • Track usage counts (for allow_once)                   │ │
  │  │ • Link to task ID                                       │ │
  │  └─────────────────────────────────────────────────────────┘ │
  └────────────────────────┬─────────────────────────────────────┘
                           │ 5. Task Token
                           ▼
  ┌─────────────┐
  │   AGENT     │←────── Task Token includes:
  └──────┬──────┘        • task_id
         │               • scoped_permission_ids
         │               • expiration
         │
         │ 6. Execute Task (API calls with Task Token)
         ▼
  ┌──────────────────────────────────────────────────────────────┐
  │               DEEPTRAIL GATEWAY (PEP)                         │
  │  ┌─────────────────────────────────────────────────────────┐ │
  │  │ • Validate Task Token                                   │ │
  │  │ • Check permissions from store                          │ │
  │  │ • Enforce constraints                                   │ │
  │  │ • Inject secrets (JIT)                                  │ │
  │  │ • Forward to external API                               │ │
  │  │ • Log everything                                        │ │
  │  └─────────────────────────────────────────────────────────┘ │
  └────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ External    │
                    │ APIs        │
                    └─────────────┘
```

### 10.2 Party-Type Specific Flows

```
PARTY-TYPE SPECIFIC PERMISSION FLOWS
═══════════════════════════════════════════════════════════════════

1ST PARTY AGENT:
────────────────
Agent → [Static Analysis] → Execution Graph → ILP Solver →
     → Policy Engine (full access) → Direct JWT → Gateway → API

2ND PARTY VENDOR-MANAGED:
─────────────────────────
Vendor Agent → Vendor IdP → SAML Assertion →
     → Control Plane (assertion validation) →
     → Capability Token (scoped, short TTL) →
     → Gateway (token validation) → API
     
     Note: No execution graph analysis (can't see agent code)
           Permissions limited to contracted capabilities

2ND PARTY VENDOR-INTEGRATED:
────────────────────────────
Agent (in Sandbox) → [Runtime Observation] → Execution Graph →
     → ILP Solver → Policy Engine (sandbox-enforced) →
     → JWT + Sandbox Attestation → Gateway → API
     
     Note: Can't do static analysis (black box)
           Can observe runtime and build graph dynamically

3RD PARTY AGENT:
────────────────
External Agent → API Key → Rate Limiter →
     → Edge Gateway (capability validation) →
     → Minimal capability token → Internal Gateway → API
     
     Note: No execution graph (don't trust declarations)
           Permissions based on registered capabilities only
           Maximum constraints applied
```

---

## 11. Implementation Priority Matrix

### 11.1 Components to Add/Update

| Component | Current State | Required Update | Priority | Effort |
|-----------|--------------|-----------------|----------|--------|
| **Execution Graph Model** | Not present | Add new | P0 | Medium |
| **Permission Solver (ILP)** | Not present | Add new | P0 | High |
| **Tool Registry** | Not present | Add new | P0 | Medium |
| **Session Permission Modes** | Basic TTL only | Enhance | P1 | Low |
| **Hierarchy Reconstruction** | Static tree | Add algorithm | P1 | Medium |
| **Formal Security Properties** | Not present | Add documentation | P2 | Low |
| **Agent Category Analysis** | Basic | Enhance with risk | P2 | Low |

### 11.2 Updated Implementation Roadmap

```yaml
updated_roadmap:
  
  phase_0_research:
    name: "MiniScope Research Integration"
    duration: "2 weeks"
    deliverables:
      - "Finalize permission hierarchy schema with DAG support"
      - "Design execution graph data model"
      - "Select and prototype ILP solver"
      - "Define tool registry schema"
  
  phase_1_foundation:
    name: "Foundation + MiniScope Core"
    duration: "6-8 weeks"
    deliverables:
      - "Permission DAG implementation"
      - "Execution Graph extractor (for 1st party)"
      - "ILP solver integration (ortools)"
      - "Tool registry with OpenAI/Stripe mappings"
      - "Session permission modes"
    success_criteria:
      - "Can compute minimal permissions for simple execution graphs"
      - "Four session modes working"
  
  phase_2_per_task:
    name: "Per-Task Least Privilege"
    duration: "6-8 weeks"
    deliverables:
      - "Full task workflow with execution graph"
      - "Constraint enforcement from solver output"
      - "SDK task context with automatic permission management"
      - "Runtime permission validation"
    success_criteria:
      - "End-to-end task with minimal permissions"
      - "Automatic revocation on task completion"
  
  phase_3_multi_party:
    name: "Multi-Party with MiniScope"
    duration: "8-10 weeks"
    deliverables:
      - "Vendor-integrated sandbox with runtime graph observation"
      - "Vendor-managed capability token system"
      - "Third-party edge enforcement"
      - "Party-specific solver constraints"
    success_criteria:
      - "All four party types supported"
      - "Least privilege verified per party type"
  
  phase_4_advanced:
    name: "Advanced Features"
    duration: "4-6 weeks"
    deliverables:
      - "Permission hierarchy auto-reconstruction from OAuth"
      - "Delegation chain with MiniScope validation"
      - "Formal security property verification"
      - "Performance optimization (caching, precomputation)"
```

---

## Summary of Required Changes

### Changes to `least-privilege-design-for-ai-agents.md`:

1. **Add Section 2.4**: MiniScope Framework Integration
2. **Add Section 3.5**: Permission Hierarchy Reconstruction Algorithm  
3. **Add Section 4.5**: Execution Graph Model
4. **Add Section 4.6**: Minimal Permission Computation (ILP Solver)
5. **Enhance Section 4.4**: Session-Based Permission Modes (four modes)
6. **Add Section 4.7**: Tooling Integration Layer
7. **Enhance Sections 6-9**: Add implementation difficulty analysis per party
8. **Add Section 12.3**: Formal Security Properties
9. **Update Section 11**: Enhanced implementation roadmap with MiniScope phases

### New Components to Implement:

1. `PermissionHierarchyBuilder` - DAG construction from OAuth scopes
2. `ExecutionGraphExtractor` - Multiple extraction methods
3. `PermissionSolver` - ILP-based minimal permission computation
4. `ToolRegistry` - Tool-to-permission mapping service
5. `SessionPermissionController` - Four-mode session management
6. Enhanced `PartyAwarePolicyEnforcement` middleware

---

## Next Steps

**Pending approval:**

1. Merge these updates into the main design document
2. Begin Phase 0 research tasks
3. Prototype ILP solver with simple permission hierarchies
4. Design execution graph schema for database

Please review this synthesis and indicate which components should be prioritized for implementation.

