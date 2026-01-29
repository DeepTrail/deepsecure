# Workstream: [Workstream Name]

> Copy this template to create a new workstream.
> Save as: `docs/workstreams/[feature-name]/WORKSTREAM.md`

---

## Overview

| Field | Value |
|-------|-------|
| **Design Doc** | [link to parent design doc] |
| **Workstream ID** | WS-[A/B/C/...] |
| **Status** | `planning` / `in_progress` / `blocked` / `completed` |
| **Owner** | [Person/Team] |
| **Created** | [Date] |
| **Target Completion** | [Date] |

---

## Description

[Brief description of what this workstream accomplishes and why it exists as a separate workstream]

---

## Parallelization

### Can Run In Parallel With
- Workstream B: [name] - [why parallel is safe]
- Workstream C: [name] - [why parallel is safe]

### Blocked By
- Workstream X: [name] - [why this dependency exists]

### Blocks
- Workstream Y: [name] - [what this workstream produces that Y needs]

---

## Tasks

| Task ID | Task Name | Status | Dependencies | Complexity | Assignee |
|---------|-----------|--------|--------------|------------|----------|
| WS-A1 | [Task name] | `ready` | None | S | - |
| WS-A2 | [Task name] | `draft` | WS-A1 | M | - |
| WS-A3 | [Task name] | `draft` | WS-A1 | M | - |
| WS-A4 | [Task name] | `draft` | WS-A2, WS-A3 | L | - |

### Task Dependency Graph

```
WS-A1
  │
  ├──► WS-A2 ──┐
  │            │
  └──► WS-A3 ──┴──► WS-A4
```

---

## Task Links

### Task Tickets
- [WS-A1: Task Name](./tasks/WS-A1-task-name.md)
- [WS-A2: Task Name](./tasks/WS-A2-task-name.md)
- [WS-A3: Task Name](./tasks/WS-A3-task-name.md)
- [WS-A4: Task Name](./tasks/WS-A4-task-name.md)

### Completion Reports
- [WS-A1 Completion](./reports/WS-A1-completion.md) - ✅ Completed
- [WS-A2 Completion](./reports/WS-A2-completion.md) - ⏳ In Progress
- WS-A3 - Not started
- WS-A4 - Not started

---

## Progress

### Overall Progress: **[X]%**

```
[████████░░░░░░░░░░░░] 40% complete
```

| Metric | Value |
|--------|-------|
| **Total Tasks** | [X] |
| **Completed** | [Y] |
| **In Progress** | [Z] |
| **Blocked** | [W] |

### Milestone Tracking

| Milestone | Target Date | Status | Notes |
|-----------|-------------|--------|-------|
| All task tickets created | [date] | ✅ / ⏳ / ❌ | |
| Core implementation complete | [date] | ✅ / ⏳ / ❌ | |
| Tests passing | [date] | ✅ / ⏳ / ❌ | |
| Ready for integration | [date] | ✅ / ⏳ / ❌ | |

---

## Files Affected

This workstream will create or modify:

### New Files
- `path/to/new/file1.py`
- `path/to/new/file2.py`

### Modified Files
- `path/to/existing/file.py`

### Test Files
- `tests/path/to/test_file.py`

---

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [Risk description] | High/Med/Low | High/Med/Low | [How to mitigate] |

---

## Notes

[Any additional context, decisions made, or things to remember]

---

## History

| Date | Event |
|------|-------|
| [date] | Workstream created |
| [date] | [Event/decision/milestone] |
