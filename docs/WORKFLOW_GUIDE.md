# Complete Design-to-Execution Workflow Guide

This guide documents the end-to-end workflow for taking a feature from design to implementation, including all commands, templates, and the learning loop.

---

## Quick Start: Agentic Mode

For automated execution of the entire workflow:

```
/orchestrate-feature @docs/design/internal/markdowns/my-feature-design.md
```

This command automates all phases with checkpoints for human approval. See `.cursor/commands/orchestrate-feature.md` for details.

---

## Related Guides

| Guide | Purpose |
|-------|---------|
| **This Guide** | What to do (phases, steps, templates) |
| `PARALLEL_EXECUTION_GUIDE.md` | How to parallelize (worktrees, instances) |
| `TASK_BREAKDOWN.md` | Methodology reference (prompts, patterns) |

---

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FULL WORKFLOW                                   │
└─────────────────────────────────────────────────────────────────────────────┘

    PHASE 1                PHASE 2                PHASE 3              PHASE 4
    ────────              ────────               ────────             ────────
    DESIGN                PLANNING               EXECUTION            LEARNING
    
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Design Doc   │───►│  Workstream  │───►│    Task      │───►│  Completion  │
│  Created     │    │   Breakdown  │    │  Execution   │    │   Reports    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  DESIGN_TEMPLATE    /breakdown-design   /create-task-ticket  /complete-task
                     TASK_BREAKDOWN.md   Task Tickets          │
                     /create-workstream                        ▼
                                                          /update-claude-md
                                                          CLAUDE.md updated
```

---

## Phase 1: Design Document Creation

### When to Use
- Starting a new feature
- Planning architectural changes
- Documenting technical decisions

### Template Used
**`docs/design/DESIGN_TEMPLATE.md`**

### Why This Template?
The design template provides a structured format that:
1. Captures goals and non-goals upfront
2. Documents technical architecture
3. **Prepares for task extraction** with the "Implementation Workstreams" section
4. Includes dependency graphs for parallelization analysis

### Process

```bash
# 1. Copy the template
cp docs/design/DESIGN_TEMPLATE.md docs/design/internal/markdowns/my-feature-design.md

# 2. Fill in all sections:
#    - Overview, Goals, Non-Goals
#    - Technical Design
#    - Leave "Implementation Workstreams" section for Phase 2
```

### Output
A complete design document at `docs/design/internal/markdowns/[feature-name]-design.md`

---

## Phase 2: Workstream Breakdown

### When to Use
- After design document is approved/finalized
- Before starting any implementation work

### Reference Document
**`docs/TASK_BREAKDOWN.md`**

### Why This Document?
The task breakdown framework provides:
1. **Prompts** for analyzing dependencies
2. **Heuristics** for identifying parallel vs sequential work
3. **Patterns** specific to DeepSecure's architecture
4. **Visualization templates** for dependency graphs

### Commands Used

#### Step 2a: Analyze Design and Create Breakdown
```
/breakdown-design @docs/design/internal/markdowns/my-feature-design.md
```

**What this command does:**
1. Reads and analyzes the design document
2. Identifies architectural boundaries
3. Maps dependencies between components
4. Creates workstreams (parallel groupings)
5. Breaks each workstream into sequential tasks
6. Identifies critical path
7. Outputs structured task breakdown

**Output:** Workstream breakdown with tasks, dependencies, and parallelization notes

#### Step 2b: Create Workstream Folder
```
/create-workstream my-feature
```

**What this command does:**
1. Creates directory structure:
   ```
   docs/workstreams/my-feature/
   ├── WORKSTREAM.md
   ├── tasks/
   └── reports/
   ```
2. Populates WORKSTREAM.md with task tracking table
3. Updates `docs/workstreams/README.md` with new entry

**Output:** Workstream folder ready for task tickets

### Templates Used
- `docs/workstreams/WORKSTREAM_TEMPLATE.md` - For workstream overview

---

## Phase 3: Task Execution

### When to Use
- After workstreams are defined
- For each individual task

### Process

#### Step 3a: Create Task Ticket
```
/create-task-ticket WS-A1 "Define token data models" for my-feature
```

**What this command does:**
1. Creates task ticket at `docs/workstreams/my-feature/tasks/WS-A1-define-token-data-models.md`
2. Fills in:
   - Metadata (status, dependencies, complexity)
   - Pre-conditions
   - Detailed task description
   - Acceptance criteria
   - Files to modify
   - Post-conditions
3. Updates WORKSTREAM.md task table

**Output:** Complete task ticket ready for execution

### Template Used
- `docs/workstreams/TASK_TICKET_TEMPLATE.md`

#### Step 3b: Execute Task
Use the task ticket as your execution guide:

```markdown
# Read the task ticket
Read: docs/workstreams/my-feature/tasks/WS-A1-define-token-data-models.md

# Work through:
1. Verify pre-conditions ✓
2. Implement changes
3. Update execution log in ticket
4. Verify acceptance criteria
5. Run tests
```

#### Step 3c: Run Quality Checks
```
/run-checks
```

**What this command does:**
1. Runs `make format` (black, isort)
2. Runs `make lint` (ruff)
3. Runs `mypy deepsecure/`
4. Runs relevant tests
5. Reports pass/fail status

**Output:** Quality validation report

---

## Phase 4: Completion and Learning Loop

### When to Use
- After each task is completed
- To document outcomes and learnings

### Commands Used

#### Step 4a: Generate Completion Report
```
/complete-task WS-A1 my-feature
```

**What this command does:**
1. Reads original task ticket
2. Gathers implementation details (git diff, test results)
3. Creates completion report at `docs/workstreams/my-feature/reports/WS-A1-completion.md`
4. Includes:
   - **Accuracy %**: How well implementation matched spec
   - **Test results**: Pass/fail summary
   - **Failures documented**: Root cause for any issues
   - **Lessons learned**: What to improve
   - **CLAUDE.md recommendations**: Rules to add
5. Updates task status to `completed`
6. Updates workstream progress

**Output:** Detailed completion report

### Template Used
- `docs/workstreams/COMPLETION_REPORT_TEMPLATE.md`

#### Step 4b: Update CLAUDE.md (Learning Loop)
```
/update-claude-md "Always validate JWT expiry with timezone-aware datetimes"
```

**What this command does:**
1. Reads current CLAUDE.md
2. Identifies appropriate section
3. Adds the learning/rule
4. Optionally commits the change

**Output:** CLAUDE.md updated with new learning

### Why the Learning Loop Matters
From Boris Cherny's workflow:
> "Anytime we see Claude do something incorrectly we add it to the CLAUDE.md, so Claude knows not to do it next time"

This creates **compounding knowledge** - every mistake becomes a rule that prevents future mistakes.

---

## Command Reference

| Command | Phase | Purpose |
|---------|-------|---------|
| `/breakdown-design` | 2 | Analyze design → workstreams + tasks |
| `/create-workstream` | 2 | Create workstream folder structure |
| `/create-task-ticket` | 3 | Generate individual task spec |
| `/run-checks` | 3 | Validate code quality |
| `/complete-task` | 4 | Generate completion report |
| `/update-claude-md` | 4 | Add learning to CLAUDE.md |
| `/commit-push-pr` | 4 | Ship changes |

---

## Template Reference

| Template | Location | Used In Phase | Purpose |
|----------|----------|---------------|---------|
| Design Template | `docs/design/DESIGN_TEMPLATE.md` | 1 | Structure feature designs |
| Task Breakdown | `docs/TASK_BREAKDOWN.md` | 2 | Framework & prompts for breakdown |
| Workstream Template | `docs/workstreams/WORKSTREAM_TEMPLATE.md` | 2 | Track workstream progress |
| Task Ticket | `docs/workstreams/TASK_TICKET_TEMPLATE.md` | 3 | Individual task specification |
| Completion Report | `docs/workstreams/COMPLETION_REPORT_TEMPLATE.md` | 4 | Post-task documentation |

---

## Document Purposes Explained

### `docs/design/DESIGN_TEMPLATE.md`

**When:** Phase 1 - Starting a new feature

**Why:**
- Ensures all aspects of design are captured
- Provides structure for architectural decisions
- **Critical:** Contains "Implementation Workstreams" section that directly feeds into Phase 2
- Makes designs consistent and reviewable
- Documents trade-offs and alternatives considered

**Key Sections for Workflow:**
```markdown
## Implementation Workstreams    ← Populated in Phase 2
## Dependency Graph              ← Visualizes parallelization
## Testing Strategy              ← Feeds into task acceptance criteria
```

### `docs/TASK_BREAKDOWN.md`

**When:** Phase 2 - Breaking down design into tasks

**Why:**
- Provides **prompts** for consistent breakdown
- Contains **DeepSecure-specific patterns** for common scenarios
- Documents **parallelization heuristics** for identifying parallel work
- Shows **dependency visualization** patterns
- Includes **checklist** before implementation
- Links to all templates in the workflow

**Key Sections:**
```markdown
## Phase 1-3 Workflow            ← Step-by-step process
## Quick Reference Prompts       ← Copy-paste prompts for Cursor
## DeepSecure-Specific Patterns  ← SDK, Backend, Cross-service patterns
## Task Execution Workflow       ← Links to ticket/report templates
```

---

## Complete Example Walkthrough

### Scenario: Adding MCP Token Validation Feature

#### Phase 1: Create Design Doc
```bash
cp docs/design/DESIGN_TEMPLATE.md docs/design/internal/markdowns/mcp-token-validation-design.md
# Edit and fill in design details
```

#### Phase 2: Break Down into Workstreams
```
/breakdown-design @docs/design/internal/markdowns/mcp-token-validation-design.md
```

Output:
```markdown
## Workstream A: Token Models (PARALLEL)
- WS-A1: Define token data models [None] [S]
- WS-A2: Implement token generation [WS-A1] [M]

## Workstream B: Validation Logic (PARALLEL with A)
- WS-B1: Implement JWT validation [None] [M]
- WS-B2: Add expiry handling [WS-B1] [S]

## Workstream C: Integration (SEQUENTIAL after A, B)
- WS-C1: Integrate with gateway [WS-A2, WS-B2] [L]
- WS-C2: E2E tests [WS-C1] [M]
```

Create workstream:
```
/create-workstream mcp-token-validation
```

#### Phase 3: Execute Tasks

Create first task tickets (can create WS-A1 and WS-B1 in parallel since they have no dependencies):
```
/create-task-ticket WS-A1 "Define token data models" for mcp-token-validation
/create-task-ticket WS-B1 "Implement JWT validation" for mcp-token-validation
```

Execute WS-A1:
1. Read task ticket
2. Implement changes
3. Run checks: `/run-checks`
4. Complete: `/complete-task WS-A1 mcp-token-validation`

Continue with dependent tasks...

#### Phase 4: Learning Loop

After completing WS-B2, discovered timezone issue:
```
/update-claude-md "Always use timezone-aware datetimes when validating JWT expiry - use datetime.now(timezone.utc) not datetime.utcnow()"
```

Ship when ready:
```
/commit-push-pr
```

---

## Parallel Execution Strategy

Based on Boris Cherny's workflow, run multiple tasks in parallel:

```
Terminal 1: WS-A1 (Token Models)     ──► WS-A2 ──► 
Terminal 2: WS-B1 (Validation)       ──► WS-B2 ──►  ──► WS-C1 (Integration)
Terminal 3: WS-D1 (Documentation)    ──────────────►
```

### Parallel Execution Rules
1. **No dependency** = Can run in parallel
2. **Same files** = Must be sequential
3. **Shared database table** = Must be sequential
4. **API producer/consumer** = Producer first
5. **Tests** = Can parallel after implementation

---

## Files Created in This Workflow

After completing a feature, you'll have:

```
docs/
├── design/
│   └── internal/markdowns/
│       └── mcp-token-validation-design.md     # Phase 1
├── workstreams/
│   └── mcp-token-validation/
│       ├── WORKSTREAM.md                       # Phase 2
│       ├── tasks/
│       │   ├── WS-A1-define-token-models.md   # Phase 3
│       │   ├── WS-A2-implement-generation.md
│       │   ├── WS-B1-implement-validation.md
│       │   ├── WS-B2-add-expiry-handling.md
│       │   ├── WS-C1-integrate-gateway.md
│       │   └── WS-C2-e2e-tests.md
│       └── reports/
│           ├── WS-A1-completion.md            # Phase 4
│           ├── WS-A2-completion.md
│           └── ...
└── TASK_BREAKDOWN.md                          # Reference (Phase 2)

CLAUDE.md                                       # Updated with learnings (Phase 4)
```

---

## Summary

| What | When | Why |
|------|------|-----|
| `DESIGN_TEMPLATE.md` | Creating new features | Structured design with workstream-ready format |
| `TASK_BREAKDOWN.md` | Breaking down designs | Prompts, patterns, and heuristics reference |
| `/breakdown-design` | After design approval | Automated analysis → workstreams + tasks |
| `/create-workstream` | Starting implementation | Folder structure for tracking |
| `/create-task-ticket` | Before each task | Detailed spec for execution |
| `/complete-task` | After each task | Accuracy tracking and learning capture |
| `/update-claude-md` | When learning occurs | Compound knowledge for future work |

This workflow creates a complete audit trail from design to implementation while building institutional knowledge through the learning loop.

---

## Integration with Parallel Execution

See `docs/PARALLEL_EXECUTION_GUIDE.md` for detailed setup.

### When Parallel Execution Applies

```
Phase 1 (Design)     → Single author
Phase 2 (Planning)   → Single breakdown, creates parallel plan
Phase 3 (Execution)  → PARALLEL EXECUTION HERE
Phase 4 (Learning)   → Merge learnings back
```

### Phase 3 Parallel Setup

After `/breakdown-design` identifies parallel workstreams:

```bash
# Create worktrees for parallel workstreams
git worktree add ../feature-ws-a -b feature/ws-a main
git worktree add ../feature-ws-b -b feature/ws-b main

# Open Claude instances
cd ../feature-ws-a && cursor .  # Terminal 1: WS-A tasks
cd ../feature-ws-b && cursor .  # Terminal 2: WS-B tasks
```

### Workflow with Worktrees

```
Main Repo                     Worktree A                Worktree B
─────────                     ──────────                ──────────
Phase 1: Design
    │
    ▼
Phase 2: /breakdown-design
         /create-workstream
         /create-task-ticket (all)
    │
    ├─────────────────────────────┬─────────────────────────────┐
    │                             │                             │
    ▼                             ▼                             ▼
git worktree add          cd ../worktree-a            cd ../worktree-b
                          cursor .                    cursor .
                               │                             │
                               ▼                             ▼
                          Execute WS-A               Execute WS-B
                          /complete-task             /complete-task
                               │                             │
                               └──────────┬──────────────────┘
                                          │
                                          ▼
                                    Merge to main
                                          │
                                          ▼
                                    Phase 4: Learning
                                    /update-claude-md
```

---

## Agentic Automation

### Fully Automated Mode

```
/orchestrate-feature @design-doc.md --mode=auto
```

Flow:
1. **CHECKPOINT 1**: Confirm feature name
2. Auto-executes Phase 2 (Planning)
3. **CHECKPOINT 2**: Approve workstream breakdown
4. Auto-executes Phase 3 (Execution) batch by batch
5. **CHECKPOINT 3**: After each batch, confirm continue
6. Auto-executes Phase 4 (Learning)
7. **CHECKPOINT 4**: Approve CLAUDE.md updates

### Phase-by-Phase Mode

```bash
# Execute one phase at a time
/orchestrate-feature @design-doc.md --phase=planning
/orchestrate-feature @design-doc.md --phase=execution
/orchestrate-feature @design-doc.md --phase=learning
```

### Single Task Mode

```bash
# Focus on specific task
/orchestrate-feature @design-doc.md --task=WS-A1
```

---

## Automation Decision Tree

```
                    ┌─────────────────┐
                    │ Design Doc Ready │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌─────────┐   ┌─────────┐    ┌─────────┐
        │  Manual │   │  Agentic│    │ Hybrid  │
        │  Mode   │   │   Mode  │    │  Mode   │
        └────┬────┘   └────┬────┘    └────┬────┘
             │              │              │
             ▼              ▼              ▼
        Run commands   /orchestrate   Manual planning
        one by one     -feature       Agentic execution
             │              │              │
             │              │              │
             ▼              ▼              ▼
        Full control   4 checkpoints   Best of both
        More effort    Less effort     Balanced
```

### When to Use Each Mode

| Mode | Use When |
|------|----------|
| **Manual** | Learning the workflow, complex decisions needed |
| **Agentic** | Well-understood features, trust the breakdown |
| **Hybrid** | Want control over planning, automate execution |
