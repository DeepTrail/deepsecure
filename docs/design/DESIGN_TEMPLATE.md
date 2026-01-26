# [Feature/Component Name] Design Document

> **Status**: Draft | In Review | Approved | Implemented  
> **Author**: [Name]  
> **Created**: [Date]  
> **Last Updated**: [Date]

## Overview

[1-2 paragraph summary of what this design accomplishes]

## Goals

- [ ] Goal 1
- [ ] Goal 2
- [ ] Goal 3

## Non-Goals

- What this design explicitly does NOT address

## Background

[Context and motivation for this design]

## Technical Design

### Architecture

[Describe the architecture, include diagrams if helpful]

### Data Models

[Define new data structures, database schemas, API contracts]

### API Changes

[New or modified APIs]

### Security Considerations

[Authentication, authorization, encryption, key management]

---

## Implementation Workstreams

### Workstream A: [Name] (can run in parallel with B, C)

| Task ID | Description | Dependencies | Complexity | Acceptance Criteria |
|---------|-------------|--------------|------------|---------------------|
| WS-A1 | [Task description] | None | S/M/L | [How to verify] |
| WS-A2 | [Task description] | WS-A1 | S/M/L | [How to verify] |
| WS-A3 | [Task description] | WS-A1 | S/M/L | [How to verify] |

**Files to modify/create:**
- `path/to/file1.py`
- `path/to/file2.py`

### Workstream B: [Name] (can run in parallel with A, C)

| Task ID | Description | Dependencies | Complexity | Acceptance Criteria |
|---------|-------------|--------------|------------|---------------------|
| WS-B1 | [Task description] | None | S/M/L | [How to verify] |
| WS-B2 | [Task description] | WS-B1 | S/M/L | [How to verify] |

**Files to modify/create:**
- `path/to/file3.py`

### Workstream C: [Name] (blocked by Workstream A)

| Task ID | Description | Dependencies | Complexity | Acceptance Criteria |
|---------|-------------|--------------|------------|---------------------|
| WS-C1 | [Task description] | WS-A3, WS-B2 | S/M/L | [How to verify] |
| WS-C2 | [Task description] | WS-C1 | S/M/L | [How to verify] |

**Files to modify/create:**
- `path/to/file4.py`
- `tests/test_integration.py`

---

## Dependency Graph

```
Workstream A          Workstream B          Workstream C
-----------          ------------          ------------
   A1                     B1
   │                      │
   ├──► A2                │
   │                      │
   └──► A3 ───────────────┴──────────────► C1
                                            │
                                            ▼
                                           C2
```

## Critical Path

The critical path is: `A1 → A3 → C1 → C2`

Workstream B can run entirely in parallel with A.

---

## Testing Strategy

### Unit Tests
- [ ] Test for component X
- [ ] Test for component Y

### Integration Tests
- [ ] Test for workflow Z

### End-to-End Tests
- [ ] E2E test requiring live backend

---

## Rollout Plan

### Phase 1: [Description]
- Tasks: WS-A1, WS-A2, WS-B1

### Phase 2: [Description]  
- Tasks: WS-A3, WS-B2

### Phase 3: [Description]
- Tasks: WS-C1, WS-C2

---

## Open Questions

- [ ] Question 1?
- [ ] Question 2?

## References

- [Link to related design docs]
- [Link to external documentation]
