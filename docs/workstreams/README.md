# Workstreams Directory

This directory contains workstreams, task tickets, and completion reports for feature implementations.

## Directory Structure

```
docs/workstreams/
├── README.md                           # This file
├── TASK_TICKET_TEMPLATE.md             # Template for task tickets
├── COMPLETION_REPORT_TEMPLATE.md       # Template for completion reports
├── WORKSTREAM_TEMPLATE.md              # Template for workstream overview
│
└── [feature-name]/                     # One folder per feature/project
    ├── WORKSTREAM.md                   # Workstream overview and tracking
    ├── tasks/                          # Task tickets
    │   ├── WS-A1-task-name.md
    │   ├── WS-A2-task-name.md
    │   └── ...
    └── reports/                        # Completion reports
        ├── WS-A1-completion.md
        ├── WS-A2-completion.md
        └── ...
```

## Workflow

```
┌─────────────────┐
│   Design Doc    │
│ (docs/design/)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Workstream    │  Create WORKSTREAM.md
│    Breakdown    │  Identify parallel/sequential tasks
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Task Tickets   │  Create individual task files
│    Created      │  in tasks/ folder
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Execute      │  Work on task using ticket as guide
│     Tasks       │  Update status as you go
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Completion    │  Create report in reports/ folder
│    Reports      │  Document outcomes, learnings
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Update         │  Add learnings to CLAUDE.md
│  CLAUDE.md      │  if applicable
└─────────────────┘
```

## Templates

### Creating a New Workstream

1. Create a folder: `docs/workstreams/[feature-name]/`
2. Copy `WORKSTREAM_TEMPLATE.md` to `[feature-name]/WORKSTREAM.md`
3. Create subfolders: `tasks/` and `reports/`
4. Fill in workstream details and task breakdown

### Creating a Task Ticket

1. Copy `TASK_TICKET_TEMPLATE.md` to `[feature-name]/tasks/[WS-ID]-[task-name].md`
2. Fill in all metadata and acceptance criteria
3. Update the workstream's task table with a link

### Creating a Completion Report

1. Copy `COMPLETION_REPORT_TEMPLATE.md` to `[feature-name]/reports/[WS-ID]-completion.md`
2. Fill in implementation details, test results, and learnings
3. Update the workstream's progress tracking

## Task States

| State | Description |
|-------|-------------|
| `draft` | Task ticket created but not fully specified |
| `ready` | Task is fully specified and ready to start |
| `in_progress` | Actively being worked on |
| `review` | Implementation complete, awaiting review |
| `completed` | Task done, completion report filed |
| `blocked` | Cannot proceed due to external dependency |
| `cancelled` | Task no longer needed |

## Naming Conventions

- **Workstream IDs**: `WS-A`, `WS-B`, `WS-C`, etc.
- **Task IDs**: `WS-A1`, `WS-A2`, `WS-B1`, etc.
- **File names**: lowercase with hyphens, e.g., `WS-A1-implement-token-service.md`

## Active Workstreams

<!-- Update this list as workstreams are created -->

| Feature | Status | Progress | Link |
|---------|--------|----------|------|
| _No active workstreams yet_ | - | - | - |

## Completed Workstreams

<!-- Move completed workstreams here for reference -->

| Feature | Completed | Tasks | Link |
|---------|-----------|-------|------|
| _None yet_ | - | - | - |
