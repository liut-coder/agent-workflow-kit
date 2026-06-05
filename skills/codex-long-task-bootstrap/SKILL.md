---
name: codex-long-task-bootstrap
description: Bootstrap or resume vague, long-running, or multi-session software tasks into a durable project-memory and long-task workflow. Use when the user says short trigger phrases like "恢复项目", "继续项目", "续任务", "LT恢复", "long-task恢复", or asks to preserve agent memory, resume a project, initialize state.sqlite, structure work with project-memory-loop and codex-long-task, or make the Memory + Long-task workflow reusable across projects.
---

# Codex Long Task Bootstrap

## Purpose

Turn a vague project goal into a recoverable long-task loop:

```text
project-memory-loop
  -> task-start memory retrieval
codex-long-task
  -> lifecycle state in data/state.sqlite
implementation plan
  -> issue-based execution
project-memory-loop
  -> closeout memory writeback
```

Use this skill before implementing large, fuzzy, multi-file, multi-session, or cross-project work.

## Short Triggers

Treat these as equivalent:

```text
恢复项目
继续项目
续任务
LT恢复
long-task恢复
```

For an existing project, interpret them as:

```text
project-memory-loop retrieval
  -> codex-long-task resume/status/issue-next
  -> read project context docs
  -> continue the next issue
```

## Tool Roles

- `project-memory-loop`: retrieve project memory before work; decide whether to write memory after work.
- `codex-long-task-bootstrap`: this skill; convert vague goals into a long-task lifecycle.
- `codex-long-task`: CLI for `doctor`, `init`, `validate`, `status`, `timeline`, `resume`, `issue-next`, `issue-start`, `issue-close`, `check-add`, `review-add`, and `closeout`.
- `subagent-driven-development`: execute bounded issues only after a written implementation plan exists.
- `ccglm-delegate`: delegate plan writing, frontend shell work, review/audit, and final reporting when available.
- `writing-skills`: create, refactor, or audit Skills themselves.

If a named tool or Skill is unavailable in the current session, state that briefly and use the file-based fallback described below.

## Standard Lifecycle

1. **Init**
   - Run or simulate `project-memory-loop` retrieval.
   - Run `codex-long-task doctor`.
   - Run `codex-long-task init`.
   - Run `codex-long-task validate`.
   - Record objective, constraints, success criteria, and initial issues.

2. **Plan**
   - Run `codex-long-task status`.
   - Run `codex-long-task timeline`.
   - Run `codex-long-task issue-next`.
   - Write a concrete implementation plan before code changes.
   - Use `ccglm-delegate plan` if available and useful.

3. **Issue**
   - Run `codex-long-task issue-start`.
   - Execute only the current issue scope.
   - Use `subagent-driven-development` only for bounded sub-work with explicit files and checks.
   - Run `codex-long-task check-add`.
   - Run `codex-long-task issue-close`.

4. **Resume**
   - Run `project-memory-loop` retrieval.
   - Run `codex-long-task resume`.
   - Run `codex-long-task status`.
   - Run `codex-long-task issue-next`.
   - Read project context docs before modifying files.

5. **Review**
   - Run `codex-long-task review-add`.
   - Use `ccglm-delegate review` or `ccglm-delegate audit` for independent review when available.
   - Confirm constraints, tests/checks, changed files, and unresolved risks.

6. **Closeout**
   - Run `codex-long-task closeout`.
   - Run or simulate `project-memory-loop` writeback decision.
   - Write project-level lessons only when they are reusable and non-sensitive.

## Project Bootstrap

For a project without memory/long-task files, use the bundled script:

```powershell
python scripts\bootstrap_project.py `
  --project-root . `
  --project-key my-project `
  --title "My long task" `
  --objective "Concrete objective for the long task"
```

The script creates:

```text
docs/agent-memory-long-task.md
docs/agent-state-schema.sql
docs/current-project-context.md
docs/project-next-actions.md
data/state.sqlite
```

`data/state.sqlite` is local runtime state. Do not commit it. Commit the docs and schema.

Use `--context-doc` and `--next-actions-doc` to choose project-specific filenames.
Use `--no-init-db` when the project should only receive docs/schema.
Use `--force` only when intentionally overwriting existing generated docs.

## File-Based Fallback

When `project-memory-loop` or `codex-long-task` is not available:

1. Read `docs/agent-memory-long-task.md`.
2. Read the project context doc.
3. Read the project next-actions doc.
4. Inspect `data/state.sqlite` if present.
5. Update docs and local state manually after each issue.

Use the schema in `docs/agent-state-schema.sql`; initialize manually with:

```powershell
python scripts\bootstrap_project.py `
  --project-root . `
  --project-key my-project `
  --title "My long task" `
  --objective "Concrete objective for the long task" `
  --force
```

## Memory Writeback Rules

Write memory for:

- Project-level constraints.
- Repeated pitfalls.
- Stable architecture decisions.
- Cross-task implementation patterns.
- User corrections that prevent future wrong turns.

Do not write memory for:

- One-off command output.
- Temporary execution details.
- Secrets, usernames, private URLs, short links, tokens, or device-specific private connection info.
- Unverified guesses.

## Delegation Rules

Use `subagent-driven-development` only when:

- A written implementation plan exists.
- The subtask has file boundaries.
- The expected output and checks are explicit.
- The subtask does not require live user judgment.

Use `ccglm-delegate` for:

- Plan drafting.
- Frontend shell/scaffold work.
- Review/audit.
- Final report preparation.

Use `writing-skills` when:

- This skill or related Skills need changes.
- A project workflow should be extracted into a reusable Skill.
- Skill prompts, checks, or tool contracts need audit.

## Validation

Before closeout:

- Confirm `git status`.
- Confirm docs/schema are committed if they are project artifacts.
- Confirm local `data/state.sqlite` is not committed.
- Add checks/reviews to long-task state.
- Run memory writeback decision.
