# Task: [WS-ID] [Task Name]

> Copy this template to create a new task ticket.
> Save as: `docs/workstreams/[feature-name]/tasks/[WS-ID]-[task-name].md`

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `draft` / `ready` / `in_progress` / `review` / `completed` / `blocked` |
| **Design Doc** | [link to design doc] |
| **Workstream** | [Workstream name] |
| **Dependencies** | [List of task IDs that must complete first, or "None"] |
| **Blocked By** | [External blockers if any] |
| **Assigned** | [Agent/Person] |
| **Created** | [Date] |
| **Estimated Complexity** | `S` (< 1hr) / `M` (1-3hr) / `L` (3+ hr) |

---

## Pre-Conditions

Before starting this task, ensure:

- [ ] All dependency tasks are completed: [list task IDs]
- [ ] Required services are running: [list services if needed]
- [ ] [Any other prerequisites]

---

## Task Description

[Detailed description of what needs to be done. Include:]
- What problem this solves
- The approach to take
- Any constraints or considerations

### Context

[Link to relevant design sections, existing code, or documentation]

### Technical Notes

[Any implementation hints, gotchas, or technical context]

---

## Acceptance Criteria

- [ ] [Specific, measurable criterion 1]
- [ ] [Specific, measurable criterion 2]
- [ ] [Specific, measurable criterion 3]
- [ ] Unit tests added and passing
- [ ] Integration tests added (if applicable)
- [ ] No new linting errors introduced
- [ ] Documentation updated (if applicable)

---

## Files to Modify/Create

### Files to Create
- `path/to/new_file.py` - [purpose]

### Files to Modify
- `path/to/existing_file.py` - [what changes]

### Tests to Add
- `tests/path/to/test_file.py` - [what to test]

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `make test` or `pytest path/to/tests`
- [ ] Linting passes: `make lint`
- [ ] Type checking passes: `mypy deepsecure/`
- [ ] [Any downstream tasks can now start]

---

## References

- Design Doc: [link]
- Related Issues: [links]
- Related Code: [links to relevant existing code]
- External Docs: [links to API docs, specs, etc.]

---

## Notes

[Any additional context, open questions, or things to watch out for]

---

## Execution Log

<!-- Updated during task execution -->

### Progress Updates

| Date | Update |
|------|--------|
| [date] | Started task |
| [date] | [Progress note] |

### Blockers Encountered

| Date | Blocker | Resolution |
|------|---------|------------|
| [date] | [description] | [how resolved] |
