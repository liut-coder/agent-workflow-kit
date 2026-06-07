#!/usr/bin/env python3
"""Bootstrap project memory + long-task files for a repository.

The script uses only the Python standard library. It can generate durable
fallback docs, initialize local state.sqlite, and optionally infer a Git-backed
checkpoint so future resumes do not rely on stale conversation context.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from textwrap import dedent


SCHEMA = r"""
pragma foreign_keys = on;

create table if not exists agent_schema_migrations (
  version integer primary key,
  name text not null,
  applied_at text not null default (datetime('now'))
);

create table if not exists agent_memories (
  id text primary key,
  project_key text not null,
  scope text not null default 'project',
  memory_type text not null,
  title text not null,
  summary text not null default '',
  content text not null,
  tags_json text not null default '[]',
  source_ref text not null default '',
  confidence real not null default 1.0,
  status text not null default 'active',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  last_used_at text,
  closed_at text
);

create index if not exists idx_agent_memories_project_status
  on agent_memories(project_key, status, memory_type);

create table if not exists agent_long_tasks (
  id text primary key,
  project_key text not null,
  title text not null,
  objective text not null,
  status text not null default 'init',
  priority integer not null default 100,
  owner text not null default 'codex',
  current_phase text not null default 'Init',
  context_summary text not null default '',
  constraints_json text not null default '[]',
  success_criteria_json text not null default '[]',
  risk_json text not null default '[]',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  started_at text,
  resumed_at text,
  reviewed_at text,
  closed_at text
);

create index if not exists idx_agent_long_tasks_project_status
  on agent_long_tasks(project_key, status, priority);

create table if not exists agent_long_task_steps (
  id text primary key,
  task_id text not null references agent_long_tasks(id) on delete cascade,
  step_order integer not null default 0,
  phase text not null,
  title text not null,
  status text not null default 'pending',
  detail text not null default '',
  result_summary text not null default '',
  evidence_refs_json text not null default '[]',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  completed_at text
);

create index if not exists idx_agent_long_task_steps_task
  on agent_long_task_steps(task_id, status, step_order);

create table if not exists agent_issues (
  id text primary key,
  task_id text references agent_long_tasks(id) on delete cascade,
  project_key text not null,
  issue_type text not null,
  severity text not null default 'normal',
  title text not null,
  detail text not null default '',
  status text not null default 'open',
  blocker boolean not null default 0,
  evidence_refs_json text not null default '[]',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  resolved_at text
);

create table if not exists agent_sessions (
  id text primary key,
  project_key text not null,
  task_id text references agent_long_tasks(id) on delete set null,
  session_kind text not null default 'work',
  status text not null default 'active',
  started_at text not null default (datetime('now')),
  ended_at text,
  start_summary text not null default '',
  end_summary text not null default '',
  git_head_start text not null default '',
  git_head_end text not null default '',
  changed_files_json text not null default '[]'
);

create table if not exists agent_events (
  id text primary key,
  project_key text not null,
  task_id text references agent_long_tasks(id) on delete cascade,
  session_id text references agent_sessions(id) on delete set null,
  event_type text not null,
  phase text not null default '',
  summary text not null,
  payload_json text not null default '{}',
  created_at text not null default (datetime('now'))
);

create table if not exists agent_artifacts (
  id text primary key,
  task_id text references agent_long_tasks(id) on delete cascade,
  project_key text not null,
  artifact_type text not null,
  path text not null,
  description text not null default '',
  status text not null default 'active',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now'))
);

insert or ignore into agent_schema_migrations(version, name)
values (1, 'agent memory and long task base schema');
"""


@dataclass
class GitSnapshot:
    available: bool
    branch: str = ""
    head: str = ""
    upstream: str = ""
    remote_url: str = ""
    status_short: str = ""
    recent_log: str = ""


MEMORY_DOC = """# Agent 记忆、长任务与执行编排

更新时间：{today}

## 1. 恢复入口

短口令：

```text
恢复项目
继续项目
续任务
LT恢复
long-task恢复
```

恢复流程：

```text
1. 读取仓库指令，例如 AGENTS.md。
2. project-memory-loop 检索记忆，如果工具可用。
3. codex-long-task resume/status/issue-next，如果工具可用。
4. 工具不可用时，读取本文、当前上下文和下一步待办。
5. 先核对 Git checkpoint，再相信历史上下文。
6. 只执行当前 bounded issue。
```

## 2. Git-backed 进度优先

恢复时优先按已提交代码和远端状态推定进度，不要只按计划文档推断。

当前 bootstrap checkpoint：

```text
branch: {branch}
head: {head}
upstream: {upstream}
remote: {remote_url}
```

恢复时建议重新执行：

```text
git fetch origin main --prune
git status --short --branch
git log --oneline --decorate -n 10
```

未提交文件只作为现场痕迹，不自动视为已完成进度，也不要无关暂存。

## 3. 项目记忆

约束：

{constraints}

已完成 checkpoint：

{done}

风险 / 易错点：

{risks}

## 4. 工具与状态

```text
docs/agent-state-schema.sql
data/state.sqlite
```

`data/state.sqlite` 是本地运行态，不提交。

## 5. 写回规则

写回项目记忆：

```text
项目级约束。
重复踩坑。
稳定架构决策。
跨任务可复用模式。
用户纠正过的误导项。
```

不写回：

```text
一次性命令输出。
临时状态。
真实地址、短链、用户名、token、设备私有连接信息。
未验证猜测。
```
"""


CONTEXT_DOC = """# 当前项目上下文

更新时间：{today}

## 1. Long-task

```text
project_key: {project_key}
title: {title}
objective: {objective}
state: data/state.sqlite
```

## 2. 当前 Git Checkpoint

```text
branch: {branch}
head: {head}
upstream: {upstream}
remote: {remote_url}
```

最近提交：

```text
{recent_log}
```

当前工作树：

```text
{status_short}
```

## 3. 恢复方式

如果 `project-memory-loop` 和 `codex-long-task` 命令不可用，使用 file-based fallback：

```text
docs/agent-memory-long-task.md
docs/current-project-context.md
docs/project-next-actions.md
docs/agent-state-schema.sql
data/state.sqlite
```

## 4. 必读项目文档

{read_docs}

## 5. 当前完成范围

{done}

## 6. 当前约束与风险

约束：

{constraints}

风险：

{risks}

## 7. 成功标准

{success}
"""


NEXT_ACTIONS_DOC = """# 项目下一步待办

更新时间：{today}

## 1. 当前 Long-task

```text
{title}
```

目标：

```text
{objective}
```

## 2. Issue 队列

{issues}

## 3. 执行约定

每个 issue 必须明确：

```text
objective
file boundaries
verification commands
documentation updates
commit / push expectations
unrelated dirty files to leave untouched
```

任务结束：

```text
1. 运行相关验证。
2. 更新本文件和相关进度文档。
3. 更新 data/state.sqlite，如果存在。
4. 只暂存当前 issue 文件。
5. 按仓库规则 fetch / commit / push。
6. 汇报 commit、push、验证和未触碰 dirty 文件。
```

## 4. 暂缓事项

{risks}
"""


def slug(value: str) -> str:
    chars: list[str] = []
    for ch in value.lower():
        if ch.isalnum():
            chars.append(ch)
        elif ch in {"-", "_", " ", "."}:
            chars.append("-")
    collapsed = "-".join(part for part in "".join(chars).split("-") if part)
    return collapsed or "long-task"


def bullet_lines(values: list[str], empty: str = "- 暂无") -> str:
    if not values:
        return empty
    return "\n".join(f"- {value}" for value in values)


def numbered_lines(values: list[str]) -> str:
    if not values:
        return "1. Plan first issue\n2. Implement first issue\n3. Review and closeout"
    return "\n".join(f"{idx}. {value}" for idx, value in enumerate(values, start=1))


def run_git(project_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def infer_git(project_root: Path) -> GitSnapshot:
    inside = run_git(project_root, ["rev-parse", "--is-inside-work-tree"])
    if inside != "true":
        return GitSnapshot(available=False)
    return GitSnapshot(
        available=True,
        branch=run_git(project_root, ["branch", "--show-current"]),
        head=run_git(project_root, ["rev-parse", "--short", "HEAD"]),
        upstream=run_git(project_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]),
        remote_url=run_git(project_root, ["remote", "get-url", "origin"]),
        status_short=run_git(project_root, ["status", "--short", "--branch"]),
        recent_log=run_git(project_root, ["log", "--oneline", "--decorate", "-n", "10"]),
    )


def write_text(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        print(f"skip existing {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path}")


def ensure_gitignore(project_root: Path) -> None:
    gitignore = project_root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    lines = {line.strip() for line in existing.splitlines()}
    if "data/" in lines or "data/state.sqlite" in lines:
        return
    suffix = "" if not existing or existing.endswith("\n") else "\n"
    gitignore.write_text(existing + suffix + "data/\n", encoding="utf-8")
    print(f"updated {gitignore}")


def read_doc_list(project_root: Path, docs: list[str]) -> list[str]:
    result: list[str] = []
    for doc in docs:
        path = project_root / doc
        if path.exists():
            result.append(f"{doc} (exists)")
        else:
            result.append(f"{doc} (missing)")
    return result


def init_db(
    db_path: Path,
    project_key: str,
    title: str,
    objective: str,
    issues: list[str],
    done: list[str],
    constraints: list[str],
    risks: list[str],
    success: list[str],
    docs: list[str],
    git_snapshot: GitSnapshot,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    task_id = f"lt-{slug(title)}"
    session_id = f"session-bootstrap-{task_id}"
    head = git_snapshot.head if git_snapshot.available else ""
    context_summary = f"Bootstrap checkpoint head={head or 'unknown'}; {objective}"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            dedent(
                """
                insert into agent_long_tasks (
                  id, project_key, title, objective, status, priority, owner,
                  current_phase, context_summary, constraints_json,
                  success_criteria_json, risk_json, started_at, resumed_at
                ) values (?, ?, ?, ?, 'active', 10, 'codex', 'Issue Planning', ?, ?, ?, ?, datetime('now'), datetime('now'))
                on conflict(id) do update set
                  status='active',
                  current_phase=excluded.current_phase,
                  context_summary=excluded.context_summary,
                  constraints_json=excluded.constraints_json,
                  success_criteria_json=excluded.success_criteria_json,
                  risk_json=excluded.risk_json,
                  updated_at=datetime('now'),
                  resumed_at=datetime('now')
                """
            ),
            (
                task_id,
                project_key,
                title,
                objective,
                context_summary,
                json.dumps(constraints, ensure_ascii=False),
                json.dumps(success, ensure_ascii=False),
                json.dumps(risks, ensure_ascii=False),
            ),
        )

        for idx, issue in enumerate(issues, start=1):
            issue_id = f"{task_id}-issue-{idx:02d}-{slug(issue)[:40]}"
            evidence = json.dumps(["docs/project-next-actions.md"], ensure_ascii=False)
            conn.execute(
                dedent(
                    """
                    insert into agent_issues (
                      id, task_id, project_key, issue_type, severity, title,
                      detail, status, evidence_refs_json
                    ) values (?, ?, ?, 'implementation', 'normal', ?, '', 'open', ?)
                    on conflict(id) do update set
                      title=excluded.title,
                      status='open',
                      evidence_refs_json=excluded.evidence_refs_json,
                      updated_at=datetime('now')
                    """
                ),
                (issue_id, task_id, project_key, issue, evidence),
            )
            conn.execute(
                dedent(
                    """
                    insert into agent_long_task_steps (
                      id, task_id, step_order, phase, title, status, detail,
                      evidence_refs_json
                    ) values (?, ?, ?, 'Issue', ?, 'pending', '', ?)
                    on conflict(id) do update set
                      step_order=excluded.step_order,
                      title=excluded.title,
                      status='pending',
                      evidence_refs_json=excluded.evidence_refs_json,
                      updated_at=datetime('now')
                    """
                ),
                (f"{task_id}-step-{idx:02d}", task_id, idx, issue, evidence),
            )

        memories = [
            ("constraints", "constraint", "Project constraints", constraints),
            ("done", "checkpoint", "Completed checkpoints", done),
            ("risks", "pitfall", "Known risks and pitfalls", risks),
        ]
        for key, memory_type, memory_title, values in memories:
            if not values:
                continue
            content = "\n".join(f"- {value}" for value in values)
            conn.execute(
                dedent(
                    """
                    insert into agent_memories (
                      id, project_key, memory_type, title, summary, content,
                      tags_json, source_ref
                    ) values (?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(id) do update set
                      summary=excluded.summary,
                      content=excluded.content,
                      tags_json=excluded.tags_json,
                      source_ref=excluded.source_ref,
                      updated_at=datetime('now')
                    """
                ),
                (
                    f"{task_id}-memory-{key}",
                    project_key,
                    memory_type,
                    memory_title,
                    values[0],
                    content,
                    json.dumps(["long-task", "bootstrap"], ensure_ascii=False),
                    "docs/agent-memory-long-task.md",
                ),
            )

        artifact_paths = [
            "docs/agent-memory-long-task.md",
            "docs/agent-state-schema.sql",
            "docs/current-project-context.md",
            "docs/project-next-actions.md",
            *docs,
        ]
        for path in artifact_paths:
            conn.execute(
                dedent(
                    """
                    insert into agent_artifacts (
                      id, task_id, project_key, artifact_type, path,
                      description, status
                    ) values (?, ?, ?, 'doc', ?, 'Long-task context artifact', 'active')
                    on conflict(id) do update set
                      path=excluded.path,
                      status='active',
                      updated_at=datetime('now')
                    """
                ),
                (f"{task_id}-artifact-{slug(path)}", task_id, project_key, path),
            )

        conn.execute(
            dedent(
                """
                insert into agent_sessions (
                  id, project_key, task_id, session_kind, status, start_summary,
                  git_head_start, changed_files_json
                ) values (?, ?, ?, 'bootstrap', 'active', ?, ?, ?)
                on conflict(id) do update set
                  status='active',
                  start_summary=excluded.start_summary,
                  git_head_start=excluded.git_head_start,
                  changed_files_json=excluded.changed_files_json
                """
            ),
            (
                session_id,
                project_key,
                task_id,
                "Initialized long-task docs and local state.",
                head,
                json.dumps(artifact_paths, ensure_ascii=False),
            ),
        )
        conn.execute(
            dedent(
                """
                insert or ignore into agent_events (
                  id, project_key, task_id, session_id, event_type, phase,
                  summary, payload_json
                ) values (?, ?, ?, ?, 'init', 'Bootstrap', ?, ?)
                """
            ),
            (
                f"{task_id}-event-bootstrap",
                project_key,
                task_id,
                session_id,
                "Initialized project long-task fallback state.",
                json.dumps(
                    {
                        "source": "codex-long-task-bootstrap",
                        "git": git_snapshot.__dict__,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
    print(f"initialized {db_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap project memory + long-task files.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--project-key", required=True, help="Stable project key for state.sqlite.")
    parser.add_argument("--title", required=True, help="Initial long-task title.")
    parser.add_argument("--objective", required=True, help="Initial long-task objective.")
    parser.add_argument("--issue", action="append", default=[], help="Initial issue title. Can be repeated.")
    parser.add_argument("--done", action="append", default=[], help="Completed checkpoint. Can be repeated.")
    parser.add_argument("--constraint", action="append", default=[], help="Project constraint. Can be repeated.")
    parser.add_argument("--risk", action="append", default=[], help="Known risk or pitfall. Can be repeated.")
    parser.add_argument("--success", action="append", default=[], help="Success criterion. Can be repeated.")
    parser.add_argument("--read-doc", action="append", default=[], help="Existing context doc to list. Can be repeated.")
    parser.add_argument("--context-doc", default="docs/current-project-context.md")
    parser.add_argument("--next-actions-doc", default="docs/project-next-actions.md")
    parser.add_argument("--infer-git", action="store_true", help="Include Git branch/head/status/log context.")
    parser.add_argument("--no-gitignore", action="store_true", help="Do not add data/ to .gitignore.")
    parser.add_argument("--no-init-db", action="store_true", help="Generate docs/schema only.")
    parser.add_argument("--force", action="store_true", help="Overwrite generated docs if present.")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    if not args.no_gitignore:
        ensure_gitignore(project_root)

    issues = args.issue or ["Audit current checkpoint", "Plan next bounded issue", "Implement and verify next issue", "Review and closeout"]
    constraints = args.constraint or ["Prefer committed code and Git checkpoint over stale conversation context."]
    risks = args.risk or ["Plan documents can overstate implementation progress; verify with code and tests."]
    success = args.success or ["Next issue has clear file boundaries, verification commands, and progress docs."]
    done = args.done or ["Long-task bootstrap initialized."]
    git_snapshot = infer_git(project_root) if args.infer_git else GitSnapshot(available=False)
    doc_entries = read_doc_list(project_root, args.read_doc)
    today = date.today().isoformat()

    format_values = {
        "today": today,
        "project_key": args.project_key,
        "title": args.title,
        "objective": args.objective,
        "branch": git_snapshot.branch or "unknown",
        "head": git_snapshot.head or "unknown",
        "upstream": git_snapshot.upstream or "unknown",
        "remote_url": git_snapshot.remote_url or "unknown",
        "recent_log": git_snapshot.recent_log or "not captured",
        "status_short": git_snapshot.status_short or "not captured",
        "read_docs": bullet_lines(doc_entries),
        "constraints": bullet_lines(constraints),
        "done": bullet_lines(done),
        "risks": bullet_lines(risks),
        "success": bullet_lines(success),
        "issues": numbered_lines(issues),
    }

    write_text(project_root / "docs" / "agent-state-schema.sql", SCHEMA.strip() + "\n", args.force)
    write_text(project_root / "docs" / "agent-memory-long-task.md", MEMORY_DOC.format(**format_values), args.force)
    write_text(project_root / args.context_doc, CONTEXT_DOC.format(**format_values), args.force)
    write_text(project_root / args.next_actions_doc, NEXT_ACTIONS_DOC.format(**format_values), args.force)

    if not args.no_init_db:
        init_db(
            project_root / "data" / "state.sqlite",
            args.project_key,
            args.title,
            args.objective,
            issues,
            done,
            constraints,
            risks,
            success,
            args.read_doc,
            git_snapshot,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
