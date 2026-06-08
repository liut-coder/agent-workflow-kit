# agent-workflow-kit

Reusable Codex agent workflow assets for project memory, long-task state, and cross-session recovery.

Use this kit when a project cannot be finished in one clean turn, has many moving parts, or needs reliable recovery after context compaction, a new Codex session, or multiple agent handoffs.

## Why Use This Skill

Long-running agent work often fails for predictable reasons:

- the latest objective gets mixed with stale plans;
- important decisions live only in chat history;
- work resumes without checking Git state first;
- large tasks drift instead of being split into bounded issues;
- later sessions cannot tell what was already verified, committed, or intentionally left untouched.

`codex-long-task-bootstrap` turns that into a repeatable recovery loop. It makes Codex verify the repository checkpoint, read the current project context, choose one bounded next issue, update durable docs/state after progress, and report the commit/push/verification status clearly.

## What This Contains

```text
skills/codex-long-task-bootstrap/
  Codex Skill for bootstrapping and resuming Memory + Long-task workflows.

scripts/bootstrap_project.py
  Standalone project initializer.

docs/agent-memory-long-task.md
  Generic workflow protocol.

docs/agent-state-schema.sql
  SQLite schema for local long-task state.
```

## When To Use It

Use the skill for:

- resuming an interrupted project with `续任务`, `恢复项目`, `继续项目`, `LT恢复`, or `long-task恢复`;
- starting a multi-session software task that needs durable memory;
- creating `docs/current-project-context.md`, `docs/project-next-actions.md`, and `data/state.sqlite`;
- preventing old plans, stale docs, or previous chat summaries from overriding current code and Git state;
- splitting a broad objective into small issues with explicit validation and closeout.

Do not use it for one-off questions, tiny edits that fit in a single turn, or tasks where no durable project state is needed.

## Short Triggers

After the Skill is installed, these should trigger project recovery:

```text
续任务
恢复项目
继续项目
LT恢复
```

## Install The Skill Locally

From the repository root, copy the skill folder into your Codex skills directory:

```powershell
$skills = Join-Path $env:USERPROFILE ".codex\skills"
$source = ".\skills\codex-long-task-bootstrap"
$dest = Join-Path $skills "codex-long-task-bootstrap"

New-Item -ItemType Directory -Force -Path $skills | Out-Null
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Recurse -Force (Join-Path $source "*") $dest
```

Restart or open a new Codex session so the skill metadata is discovered.

## Typical Usage

### Resume an existing project

From a project workspace, tell Codex:

```text
续任务
```

Expected Codex behavior:

```text
1. Read repository instructions such as AGENTS.md.
2. Retrieve project memory or use docs/data fallback.
3. Verify Git branch, recent commits, dirty files, and remote state.
4. Read docs/current-project-context.md and docs/project-next-actions.md.
5. Pick one bounded next issue.
6. Implement, verify, update docs/state, and report closeout.
```

### Bootstrap a new long task

From any project root:

```powershell
python <path-to-agent-workflow-kit>\scripts\bootstrap_project.py `
  --project-root . `
  --project-key my-project `
  --title "My long task" `
  --objective "Concrete objective" `
  --infer-git `
  --issue "First issue" `
  --issue "Second issue"
```

This creates:

```text
docs/agent-memory-long-task.md
docs/agent-state-schema.sql
docs/current-project-context.md
docs/project-next-actions.md
data/state.sqlite
```

`data/state.sqlite` is local runtime state and should not be committed.

### Ask Codex to improve recoverability

Use prompts like:

```text
用 codex-long-task-bootstrap 帮我把这个项目变成可恢复的长期任务。
```

```text
恢复项目，先检查 Git 状态和长期记忆，再继续下一个可验证 issue。
```

## Bootstrap A Project

The standalone script can also be used directly when the Codex skill is not available:

```powershell
python <path-to-agent-workflow-kit>\scripts\bootstrap_project.py `
  --project-root . `
  --project-key my-project `
  --title "My long task" `
  --objective "Concrete objective" `
  --issue "First issue" `
  --issue "Second issue"
```

Useful options:

```text
--infer-git       Record current branch, head, remote, recent commits, and dirty status.
--read-doc PATH   Include existing context docs; repeat for multiple files.
--issue TITLE     Seed an open issue; repeat for multiple issues.
--done TEXT       Seed a completed checkpoint.
--constraint TEXT Seed a project constraint.
--risk TEXT       Seed a known risk.
--success TEXT    Seed a success criterion.
--no-init-db      Generate docs/schema only.
--force           Overwrite generated docs.
```

## Existing Project Resume

Say:

```text
续任务
```

Expected flow:

```text
project-memory-loop retrieval
  -> codex-long-task resume/status/issue-next
  -> read project context docs
  -> continue current issue
```

If CLI or Skills are unavailable, use the generated docs and `data/state.sqlite` as the fallback.

## Maintenance Notes

Validate the skill after edits:

```powershell
python $env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py `
  .\skills\codex-long-task-bootstrap

python .\scripts\bootstrap_project.py --help
```

When updating the skill, keep `SKILL.md` concise and put detailed operational material in `docs/` or script help. The skill is designed to guide Codex behavior, not to be a long user manual.
