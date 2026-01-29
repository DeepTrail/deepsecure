# Task Breakdown Framework

This document provides a systematic approach for breaking down design documents into actionable, parallelizable tasks.

---

## Phase 1: Dependency Analysis

**Prompt to use:**

> "Analyze @docs/design/internal/markdowns/[design-doc].md and identify:
> 1. External service dependencies (APIs, databases, third-party services)
> 2. Database/schema changes required
> 3. Shared state or resources between components
> 4. API contracts between components"

**Expected output:**
- List of external dependencies with their interfaces
- Schema changes with migration requirements
- Shared state map (what's shared, who owns it)
- API contract definitions

---

## Phase 2: Workstream Identification

**Prompt to use:**

> "Group the identified tasks into workstreams where:
> - Tasks within a workstream are sequential (have dependencies)
> - Workstreams themselves can run in parallel
> - Identify the critical path (longest sequential chain)"

**Expected output:**
```
Workstream A: [Name] - can parallel with B, C
Workstream B: [Name] - can parallel with A, C  
Workstream C: [Name] - blocked by A completion
```

---

## Phase 3: Task Specification

**Prompt to use:**

> "For each task in the workstreams, provide:
> - Clear input/output definition
> - Test criteria (unit, integration, e2e)
> - Estimated complexity (S/M/L)
> - Dependencies listed explicitly
> - Files expected to be created/modified"

**Task Template:**

| Field | Description |
|-------|-------------|
| **ID** | WS[workstream]-[number] (e.g., WS-A1) |
| **Description** | One sentence describing the task |
| **Dependencies** | List task IDs or "None" |
| **Complexity** | S (< 1hr), M (1-3hr), L (3+ hr) |
| **Acceptance** | How to verify completion |
| **Files** | Expected files to create/modify |
| **Tests** | Required test coverage |

---

## Quick Reference Prompts

### Initial Breakdown
```
Read @docs/design/internal/markdowns/[design-doc].md and create a task breakdown with:
1. Parallel workstreams clearly separated
2. Sequential dependencies marked with arrows
3. Each task sized to ~1-2 hours of work
4. Test requirements for each task
```

### Dependency Analysis
```
Analyze the proposed changes and identify which tasks share state or have 
data dependencies. Output a dependency graph showing parallel vs sequential execution.
```

### Implementation Planning
```
Given these tasks, create a phased implementation plan where:
- Phase 1: All independent/parallel tasks
- Phase 2: Tasks that depend on Phase 1
- Phase 3: Integration and testing tasks
- Flag any blocking dependencies
```

### Parallel Opportunity Check
```
Review the task list and identify any tasks currently marked as sequential 
that could actually run in parallel. Consider:
- Do they modify the same files?
- Do they share database tables?
- Is there a data dependency?
```

### Critical Path Analysis
```
Identify the critical path through these tasks:
1. What is the minimum time to completion?
2. Which tasks, if delayed, would delay the entire project?
3. Where are the parallelization opportunities?
```

---

## DeepSecure-Specific Patterns

### Common Workstream Patterns

**SDK Feature Addition:**
```
WS-A: Core Implementation (deepsecure/_core/)
WS-B: Public API (deepsecure/client.py) - depends on A
WS-C: CLI Commands (deepsecure/commands/) - parallel with B
WS-D: Tests - parallel with B and C
WS-E: Examples & Docs - after B and C
```

**Backend Service Change:**
```
WS-A: Database Schema & Migrations
WS-B: Control Plane API (deeptrail-control/) - after A
WS-C: Gateway Changes (deeptrail-gateway/) - parallel with B if no shared state
WS-D: SDK Updates - after B's API is stable
WS-E: Integration Tests - after all above
```

**Cross-Service Feature:**
```
WS-A: Shared Contracts (API specs, data models)
WS-B: Control Plane Implementation - after A
WS-C: Gateway Implementation - after A, parallel with B
WS-D: SDK Client Updates - after B and C
WS-E: E2E Testing - after D
```

---

## Dependency Visualization

Use ASCII diagrams for dependency graphs:

```
Independent tasks (parallel):
A1 ─────────────────────►
B1 ─────────────────────►
C1 ─────────────────────►

Sequential chain:
A1 ──► A2 ──► A3 ──► A4

Diamond dependency:
      ┌──► B1 ──┐
A1 ───┤         ├──► D1
      └──► C1 ──┘

Complex graph:
A1 ──► A2 ──► A3
              │
B1 ──► B2 ────┼──► Integration
              │
C1 ──────────►┘
```

---

## Checklist Before Implementation

- [ ] All external dependencies identified
- [ ] Database changes have migration plan
- [ ] API contracts defined before implementation
- [ ] Parallel workstreams have no hidden dependencies
- [ ] Each task has acceptance criteria
- [ ] Test requirements specified per task
- [ ] Critical path identified
- [ ] Blocking dependencies flagged

---

## Task Execution Workflow

Once tasks are broken down, follow this execution workflow:

### Step 1: Create Workstream Folder
```
docs/workstreams/[feature-name]/
├── WORKSTREAM.md      # Copy from WORKSTREAM_TEMPLATE.md
├── tasks/             # Task tickets go here
└── reports/           # Completion reports go here
```

### Step 2: Create Task Tickets
For each task, create a ticket using the template:
```
docs/workstreams/[feature-name]/tasks/[WS-ID]-[task-name].md
```
Copy from: `docs/workstreams/TASK_TICKET_TEMPLATE.md`

### Step 3: Execute Tasks
Use the task ticket as your guide:
- Check pre-conditions
- Follow the acceptance criteria
- Update the execution log as you work

### Step 4: Create Completion Report
After completing a task:
```
docs/workstreams/[feature-name]/reports/[WS-ID]-completion.md
```
Copy from: `docs/workstreams/COMPLETION_REPORT_TEMPLATE.md`

Include:
- **Accuracy %**: How well did implementation match the spec?
- **Test results**: Pass/fail summary
- **Failures**: Document any test failures for review
- **Lessons learned**: What to add to CLAUDE.md?

### Step 5: Update CLAUDE.md
If the completion report identifies generalizable learnings, add them to CLAUDE.md.

---

## Templates Reference

| Template | Location | Purpose |
|----------|----------|---------|
| Design Doc | `docs/design/DESIGN_TEMPLATE.md` | High-level feature design |
| Workstream | `docs/workstreams/WORKSTREAM_TEMPLATE.md` | Workstream overview and tracking |
| Task Ticket | `docs/workstreams/TASK_TICKET_TEMPLATE.md` | Individual task specification |
| Completion Report | `docs/workstreams/COMPLETION_REPORT_TEMPLATE.md` | Post-task documentation |

---

## Full Workflow Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         DESIGN PHASE                                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │ Design Doc  │───►│ Workstream  │───►│   Task      │              │
│  │  Created    │    │  Breakdown  │    │  Tickets    │              │
│  └─────────────┘    └─────────────┘    └─────────────┘              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       EXECUTION PHASE                                 │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │   Execute   │───►│   Create    │───►│   Update    │              │
│  │    Task     │    │   Report    │    │  CLAUDE.md  │              │
│  └─────────────┘    └─────────────┘    └─────────────┘              │
│         │                  │                                         │
│         ▼                  ▼                                         │
│  ┌─────────────┐    ┌─────────────┐                                 │
│  │  Accuracy   │    │  Failures   │                                 │
│  │  Assessment │    │   Logged    │                                 │
│  └─────────────┘    └─────────────┘                                 │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        LEARNING LOOP                                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Completion Reports ──► Identify Patterns ──► Update CLAUDE.md      │
│                                                                      │
│  • Accuracy tracking improves estimates                              │
│  • Failure patterns prevent repeat mistakes                          │
│  • Lessons learned compound over time                                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```
