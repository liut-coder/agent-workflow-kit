---
name: codex-long-task-bootstrap
description: Bootstrap or resume vague, long-running, or multi-session software tasks into a durable project-memory and long-task workflow. Use when the user says "恢复项目", "继续项目", "续任务", "LT恢复", "long-task恢复", asks to preserve project memory, initialize or improve state.sqlite, structure work with project-memory-loop and codex-long-task, or make a project recoverable across sessions; also use when updating this long-task workflow itself.
---

# Codex Long Task Bootstrap

## Purpose

Turn a fuzzy or multi-session project into a recoverable loop:

```text
retrieve memory
  -> verify Git/code checkpoint
  -> inspect project context docs
  -> choose one bounded issue
  -> execute, verify, commit/push when required
  -> update docs/state
```

Use this skill before changing large, cross-cutting, or easy-to-lose-context work.

Use this skill because long tasks need durable state outside the chat context: current objective, Git checkpoint, next bounded issue, verification status, and stale-context safeguards. Prefer it when losing context would cause duplicated work, unsafe edits, or old plans overriding current repository state.

## Resume Rules

For short triggers such as `恢复项目`, `继续项目`, `续任务`, `LT恢复`, or `long-task恢复`:

```text
1. Read repository instructions such as AGENTS.md.
2. Run project-memory-loop retrieval if available.
3. Run codex-long-task resume/status/issue-next if available.
4. If either tool is unavailable, use the file-based fallback.
5. Verify Git state before trusting old context.
6. Read the project context and next-actions docs before editing files.
```

When Git is available, always prefer GitHub-backed committed code over stale plan text:

```text
git fetch origin main --prune
git status --short --branch
git log --oneline --decorate -n 10
```

Treat dirty files as user or prior-agent work. Do not revert or stage them unless the current issue explicitly requires it.

## Tool Fallback

If `project-memory-loop` or `codex-long-task` is missing, say so briefly and continue with:

```text
docs/agent-memory-long-task.md
docs/current-project-context.md
docs/project-next-actions.md
docs/agent-state-schema.sql
data/state.sqlite
```

If these files do not exist, bootstrap them with the bundled script.

## Bootstrap Script

Prefer `python3`; use `python` only if `python3` is unavailable:

```bash
python3 /path/to/codex-long-task-bootstrap/scripts/bootstrap_project.py \
  --project-root . \
  --project-key my-project \
  --title "My long task" \
  --objective "Concrete objective" \
  --infer-git \
  --read-doc docs/documentation-status.md \
  --issue "Calibrate the first production slice" \
  --issue "Add tests and closeout"
```

The script creates:

```text
docs/agent-memory-long-task.md
docs/agent-state-schema.sql
docs/current-project-context.md
docs/project-next-actions.md
data/state.sqlite
```

Commit the docs/schema when they are project artifacts. Do not commit `data/state.sqlite`; the script adds `data/` to `.gitignore` unless disabled.

Useful script options:

```text
--infer-git       Include current head, branch, remote, recent commits, and dirty status.
--read-doc PATH   Record important existing context docs; can be repeated.
--issue TITLE     Seed an open issue; can be repeated.
--done TEXT       Seed a completed checkpoint.
--constraint TEXT Seed project constraints.
--risk TEXT       Seed known pitfalls or risks.
--success TEXT    Seed success criteria.
--no-init-db      Generate docs/schema only.
--force           Overwrite generated docs.
```

## Plan Before Edits

Before implementing code, write or update a concrete issue plan:

```text
issue title
objective
file boundaries
checks / tests
documentation updates
commit/push expectations
unrelated dirty files to leave untouched
```

Use subagents only after a written plan exists and the subtask has clear files and checks.

## Progress And Closeout

After each independently verifiable issue:

```text
1. Run relevant verification.
2. Update docs/project-next-actions.md and any project progress doc.
3. Update data/state.sqlite when present.
4. Commit only related files.
5. Fetch before push when repository rules require it.
6. Push if the project requires pushed task slices.
7. Report commit hash, push status, verification, and untouched dirty files.
```

## Memory Writeback

Write memory for:

```text
project-level constraints
stable architecture decisions
repeated pitfalls
cross-task implementation patterns
user corrections that prevent wrong turns
```

Do not write memory for:

```text
one-off command output
temporary state
secrets, usernames, short links, private device/server connection details, tokens
unverified guesses
```

## Validation

For skill maintenance, validate with:

```bash
python3 /root/.codex/skills/.system/skill-creator/scripts/quick_validate.py /path/to/codex-long-task-bootstrap
python3 /path/to/codex-long-task-bootstrap/scripts/bootstrap_project.py --help
```

For script changes, run the script in a temporary directory and verify:

```text
docs are generated
data/state.sqlite is initialized unless --no-init-db is set
data/ or data/state.sqlite is ignored
seeded issues/memories appear in SQLite
```
