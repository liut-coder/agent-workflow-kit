# agent-workflow-kit

Reusable Agent workflow assets for project memory, long-task state, and cross-session recovery.

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

## Short Triggers

After the Skill is installed, these should trigger project recovery:

```text
续任务
恢复项目
继续项目
LT恢复
```

## Install The Skill

Copy the skill folder into your Codex skills directory:

```powershell
$skills = Join-Path $env:USERPROFILE ".codex\skills"
New-Item -ItemType Directory -Force -Path $skills | Out-Null
Copy-Item -Recurse -Force `
  .\skills\codex-long-task-bootstrap `
  (Join-Path $skills "codex-long-task-bootstrap")
```

Restart or open a new Codex session so the skill metadata is discovered.

## Bootstrap A Project

From any project root:

```powershell
python <path-to-agent-workflow-kit>\scripts\bootstrap_project.py `
  --project-root . `
  --project-key my-project `
  --title "My long task" `
  --objective "Concrete objective" `
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
