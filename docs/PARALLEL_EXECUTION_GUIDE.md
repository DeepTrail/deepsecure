# Parallel Execution Guide

How to run multiple Claude Code instances in parallel for maximum productivity.

---

## Strategy Overview

| Scenario | Recommended Approach |
|----------|---------------------|
| Parallel tasks within same feature | **Git Worktrees** |
| Independent features | **Git Worktrees** or **Multiple Clones** |
| Need complete isolation (risky changes) | **Multiple Clones** |
| Long-running background tasks | **Kick to claude.ai/code** |

---

## Option 1: Git Worktrees (Recommended for Task Parallelization)

### Setup

```bash
# From your main repo
cd /Users/imaxxs/repositories/deepsecure-cli

# Create worktrees for parallel workstreams
git worktree add ../deepsecure-ws-a feature/ws-a-token-models
git worktree add ../deepsecure-ws-b feature/ws-b-validation
git worktree add ../deepsecure-ws-c feature/ws-c-integration

# List all worktrees
git worktree list
```

### Directory Structure
```
/Users/imaxxs/repositories/
├── deepsecure-cli/              # Main (main branch)
│   ├── .git/                    # Shared git database
│   ├── docs/workstreams/        # Task tickets (shared via git)
│   └── ...
│
├── deepsecure-ws-a/             # Worktree (feature/ws-a-*)
│   └── (Claude instance 1)
│
├── deepsecure-ws-b/             # Worktree (feature/ws-b-*)
│   └── (Claude instance 2)
│
└── deepsecure-ws-c/             # Worktree (feature/ws-c-*)
    └── (Claude instance 3)
```

### Advantages
- **Disk efficient**: Shares .git directory (~500MB+ savings)
- **Branch safety**: Can't accidentally checkout same branch in two places
- **Easy merging**: All worktrees share refs, easy to merge/rebase
- **Shared config**: .cursorrules, CLAUDE.md available in all worktrees

### Disadvantages
- **Git operations can conflict**: Avoid `git gc`, `git prune` while working
- **Stash is shared**: Be careful with `git stash`
- **Some git operations lock**: Large rebases may block other worktrees

### Worktree Workflow

```bash
# Terminal 1: Working on WS-A (Token Models)
cd ../deepsecure-ws-a
cursor .
# Claude works on WS-A1, WS-A2

# Terminal 2: Working on WS-B (Validation) - PARALLEL
cd ../deepsecure-ws-b  
cursor .
# Claude works on WS-B1, WS-B2

# Terminal 3: Main repo for coordination
cd deepsecure-cli
# Review PRs, merge completed work, update task statuses
```

### Cleanup
```bash
# When done with a worktree
git worktree remove ../deepsecure-ws-a

# Or force remove if unclean
git worktree remove --force ../deepsecure-ws-a

# Prune stale worktree references
git worktree prune
```

---

## Option 2: Multiple Clones (For Complete Isolation)

### Setup

```bash
# Clone multiple copies
git clone git@github.com:your-org/deepsecure-cli.git deepsecure-cli-1
git clone git@github.com:your-org/deepsecure-cli.git deepsecure-cli-2
git clone git@github.com:your-org/deepsecure-cli.git deepsecure-cli-3
```

### When to Use Multiple Clones
- **Risky experimental changes** that might corrupt git state
- **Different remote targets** (e.g., fork vs upstream)
- **Long-running operations** that lock git
- **Complete isolation needed** (different configs, env vars)

### Disadvantages
- **Disk heavy**: Full .git copy each (~500MB+ per clone)
- **Sync overhead**: Must pull/push to share changes
- **Branch conflicts**: Can checkout same branch in multiple clones (dangerous)
- **Config divergence**: CLAUDE.md changes don't auto-sync

---

## Option 3: Hybrid Approach (Recommended)

Combine worktrees with claude.ai/code for optimal workflow:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     LOCAL MACHINE (Interactive)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Terminal 1          Terminal 2          Terminal 3                 │
│  (Worktree A)        (Worktree B)        (Main Repo)               │
│  ┌─────────┐        ┌─────────┐         ┌─────────┐               │
│  │ Claude  │        │ Claude  │         │  Review │               │
│  │ WS-A    │        │ WS-B    │         │  & Merge│               │
│  └─────────┘        └─────────┘         └─────────┘               │
│       │                  │                   │                      │
│       └──────────────────┼───────────────────┘                      │
│                          │                                          │
│  When task is long-running or needs less interaction:               │
│                          │                                          │
│                          ▼                                          │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           │ Hand off with &
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     CLAUDE.AI/CODE (Background)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Session 1           Session 2           Session 3                  │
│  ┌─────────┐        ┌─────────┐         ┌─────────┐               │
│  │ WS-C    │        │ WS-D    │         │  Docs   │               │
│  │ (long)  │        │ (tests) │         │  Update │               │
│  └─────────┘        └─────────┘         └─────────┘               │
│                                                                     │
│  • Runs in background                                               │
│  • Frees local terminals for interactive work                       │
│  • Can "teleport" session back to local when needed                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Integration with Task Workflow

### Mapping Workstreams to Worktrees

```bash
# After /breakdown-design identifies parallel workstreams:

# Workstream A: Token Models (PARALLEL)
git worktree add ../ds-ws-a feature/ws-a-token-models

# Workstream B: Validation (PARALLEL with A)
git worktree add ../ds-ws-b feature/ws-b-validation

# Workstream C: Integration (SEQUENTIAL - after A, B)
# Don't create yet - wait for A, B to merge
```

### Task Ticket Access

Task tickets are in `docs/workstreams/` which is tracked by git. To access in worktrees:

```bash
# Option 1: Commit task tickets to main, pull in worktrees
# In main repo:
git add docs/workstreams/my-feature/
git commit -m "Add task tickets for my-feature"
git push

# In worktrees:
git fetch origin
git merge origin/main  # or rebase

# Option 2: Create task tickets in each worktree branch
# Task tickets travel with the feature branch
```

### Recommended Workflow

```bash
# 1. Create task tickets in main branch first
cd deepsecure-cli
/create-workstream my-feature
/create-task-ticket WS-A1 "..." for my-feature
/create-task-ticket WS-B1 "..." for my-feature
git add . && git commit -m "Add workstream and task tickets"

# 2. Create worktrees branching from main (includes tickets)
git worktree add ../ds-ws-a -b feature/ws-a main
git worktree add ../ds-ws-b -b feature/ws-b main

# 3. Work in parallel
# Terminal 1:
cd ../ds-ws-a && cursor .
# Execute WS-A tasks, commit completion reports

# Terminal 2:
cd ../ds-ws-b && cursor .
# Execute WS-B tasks, commit completion reports

# 4. Merge back to main
cd deepsecure-cli
git merge feature/ws-a
git merge feature/ws-b

# 5. Create integration worktree
git worktree add ../ds-ws-c -b feature/ws-c main
# Execute WS-C tasks
```

---

## Shared Resources Considerations

### Docker Services
Both worktrees and clones share the same Docker containers if using same ports:

```bash
# Problem: Both worktrees try to use localhost:8000
# Solution: Use different ports per worktree

# In worktree A (.env or environment):
DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000

# In worktree B:
DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8010
```

Or use a single shared backend:
```bash
# Run backend in main repo only
cd deepsecure-cli
docker compose up -d

# All worktrees use same backend
# (Fine for read operations, careful with writes)
```

### Database State
If tasks modify database:
- **Safe**: Use separate database containers per worktree
- **Risky**: Share database (may have conflicts)

```yaml
# docker-compose.override.yml per worktree
services:
  db:
    ports:
      - "${DB_PORT:-5434}:5432"  # Override port per worktree
```

---

## Quick Reference: Worktree Commands

```bash
# Create worktree with new branch
git worktree add <path> -b <branch-name> <start-point>
git worktree add ../ds-ws-a -b feature/ws-a main

# Create worktree with existing branch
git worktree add <path> <existing-branch>
git worktree add ../ds-ws-a feature/ws-a

# List worktrees
git worktree list

# Remove worktree (clean)
git worktree remove <path>

# Remove worktree (force)
git worktree remove --force <path>

# Prune stale references
git worktree prune

# Move worktree
git worktree move <old-path> <new-path>
```

---

## Summary: When to Use What

| Situation | Use |
|-----------|-----|
| Parallel tasks, same feature | Git Worktrees |
| Need to share CLAUDE.md learnings instantly | Git Worktrees |
| Risky/experimental work | Multiple Clones |
| Long-running, low-interaction tasks | claude.ai/code |
| Testing different configurations | Multiple Clones |
| Working on unrelated features | Either works |

### For Your Workflow Specifically

Given your design → workstream → task workflow:

1. **Create task tickets in main** (shared reference)
2. **Create worktrees per parallel workstream** (WS-A, WS-B)
3. **Run Claude in each worktree** (parallel execution)
4. **Merge completed work back to main**
5. **Create next worktrees for sequential tasks** (WS-C after A,B merge)
6. **Kick long tasks to claude.ai/code** (free up local terminals)

This approach maximizes parallelization while keeping your task tracking centralized.
