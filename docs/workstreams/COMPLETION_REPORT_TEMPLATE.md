# Completion Report: [WS-ID] [Task Name]

> Copy this template to create a completion report.
> Save as: `docs/workstreams/[feature-name]/reports/[WS-ID]-completion.md`

---

## Summary

| Field | Value |
|-------|-------|
| **Final Status** | `completed` / `partial` / `failed` / `cancelled` |
| **Task Ticket** | [link to task ticket] |
| **Design Doc** | [link to design doc] |
| **Started** | [Date/Time] |
| **Completed** | [Date/Time] |
| **Estimated Complexity** | [S/M/L] |
| **Actual Time** | [hours] |

---

## Accuracy Assessment

### Completion Percentage: **[0-100]%**

| Criterion | Status | Notes |
|-----------|--------|-------|
| [Acceptance criterion 1] | ✅ / ❌ / ⚠️ | [notes] |
| [Acceptance criterion 2] | ✅ / ❌ / ⚠️ | [notes] |
| [Acceptance criterion 3] | ✅ / ❌ / ⚠️ | [notes] |

### Scope Match

- **Did implementation match original spec?** Yes / Partially / No
- **Deviation Notes:** [Explain any changes from the original plan]

### Quality Assessment

- **Code Quality:** [High / Medium / Low]
- **Test Coverage:** [Adequate / Needs improvement]
- **Documentation:** [Complete / Partial / Missing]

---

## Implementation Details

### Approach Taken

[Detailed description of the implementation approach. Include:]
- Architecture decisions made
- Patterns used
- Trade-offs considered

### Key Changes

[Summarize the most important changes]

1. **[Change 1]**: [Description]
2. **[Change 2]**: [Description]
3. **[Change 3]**: [Description]

---

## Files Changed

| File | Change Type | Lines +/- | Description |
|------|-------------|-----------|-------------|
| `path/to/file1.py` | Created | +100 | [what it does] |
| `path/to/file2.py` | Modified | +50 / -10 | [what changed] |
| `tests/test_file.py` | Created | +75 | [what it tests] |

### Total Changes
- **Files Changed:** [X]
- **Lines Added:** [+X]
- **Lines Removed:** [-X]

---

## Commits and PRs

### Commits

| Hash | Message |
|------|---------|
| `abc1234` | [commit message] |
| `def5678` | [commit message] |

### Pull Requests

| PR | Title | Status |
|----|-------|--------|
| #[number] | [title] | Merged / Open / Draft |

---

## Testing

### Tests Added

| Test File | Test Name | Type |
|-----------|-----------|------|
| `tests/test_x.py` | `test_feature_works` | Unit |
| `tests/test_x.py` | `test_edge_case` | Unit |
| `tests/test_integration.py` | `test_e2e_flow` | Integration |

### Test Results

```
======================== test session summary ========================
[X] passed, [Y] failed, [Z] skipped in [time]s
```

| Metric | Value |
|--------|-------|
| **Passed** | [X] |
| **Failed** | [Y] |
| **Skipped** | [Z] |
| **Coverage** | [X]% |

### Test Failures (if any)

| Test | Error | Root Cause | Resolution |
|------|-------|------------|------------|
| `test_name` | `ErrorType: message` | [why it failed] | [how fixed or TODO] |

---

## Blockers Encountered

| Blocker | Duration | Impact | Resolution |
|---------|----------|--------|------------|
| [Description] | [time blocked] | [High/Med/Low] | [how resolved] |

---

## Lessons Learned

### What Went Well
- [Thing that worked well]
- [Another positive]

### What Could Be Improved
- [Challenge or inefficiency]
- [Suggestion for next time]

### Unexpected Discoveries
- [Something learned that wasn't anticipated]

---

## CLAUDE.md Updates

Should any learnings be added to CLAUDE.md?

- [ ] **Yes** - Add: "[rule or pattern to add]"
- [ ] **No** - No generalizable learnings

---

## Follow-Up Tasks

New tasks identified during implementation:

| Task | Priority | Description |
|------|----------|-------------|
| [Task name] | High/Med/Low | [Brief description] |

---

## Sign-Off

- [ ] All acceptance criteria verified
- [ ] Tests passing in CI
- [ ] Code reviewed (if applicable)
- [ ] Documentation updated
- [ ] Ready for downstream tasks to proceed
