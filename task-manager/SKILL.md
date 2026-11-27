---
name: task-manager
description: Manage, index, and update all task markdown files stored inside task-manager/tasks/.
---

# Task Manager Workflow

## Storage Layout
- `task-manager/SKILL.md` — Read-only workflow instructions (do not modify unless asked to update rules).
- `task-manager/INDEX.md` — Master task table (single source of truth).
- `task-manager/tasks/` — Individual task markdown files.

## Formatting Rules for `INDEX.md`
1. **Single-Line Table Format:** Every task in `task-manager/INDEX.md` MUST be one single row:
   `| Status | Created Date | Description | Location |`
2. **Allowed Status Values:** Use ONLY these exact uppercase tags:
   - `TODO` — Not started
   - `IN_PROGRESS` — Actively being worked on
   - `BLOCKED` — Waiting on another task or input
   - `DONE` — Completed
3. **Date Format:** Always use `YYYY-MM-DD`.
4. **Description:** Max 10–12 words, single line, no `|` pipe characters.
5. **Location:** Relative link to the file inside `tasks/` (e.g., `[001-fix-login.md](tasks/001-fix-login.md)`).

## Operating Procedures

### 1. Create a Task
1. Check `task-manager/tasks/` for the highest 3-digit prefix (e.g., `001`) and increment by 1.
2. Create `task-manager/tasks/<NNN>-<kebab-case-name>.md` using the Task File Template below.
3. Append a new `TODO` row with today's date to `task-manager/INDEX.md`.

### 2. Update a Task
1. Edit the target file inside `task-manager/tasks/`.
2. Update the matching row's `Status` (and `Description` if needed) in `task-manager/INDEX.md`. Keep `Created Date` and `Location` unchanged.

### 3. Audit, Sync & List (`INDEX.md` vs `tasks/`)
1. **Audit:** Run `python3 task-manager/scripts/sync.py` to get a compact status summary and check for drift.
2. **Sync Untracked Files:** **If** the summary reports files in `tasks/` missing from `INDEX.md`, run `python3 task-manager/scripts/sync.py --sync` to add them automatically.
3. **Clean Deleted Files:** **If** the summary reports rows in `INDEX.md` missing on disk, show those details to the user and ask for confirmation before running `python3 task-manager/scripts/sync.py --clean`.
4. **Filter & List:** When asked to view specific tasks (e.g., active or pending tasks), run `python3 task-manager/scripts/sync.py --list <STATUS>` (`TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, or `ALL`) instead of reading the entire `INDEX.md` manually.

## Task File Template (`tasks/<NNN>-<name>.md`)
```markdown
# Task: <Short Title>
- **Status:** TODO
- **Created:** YYYY-MM-DD

## Objective
<1–2 sentences describing the goal>

## Steps / Checklist
- [ ] Step 1
- [ ] Step 2
```
