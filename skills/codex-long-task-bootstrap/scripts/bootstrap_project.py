#!/usr/bin/env python3
"""Bootstrap project memory + long-task files for a repository.

This script intentionally uses only the Python standard library so it can run
inside most Codex workspaces without extra setup.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
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


MEMORY_DOC = """# Agent 记忆、长任务与执行编排

更新时间：{date}

## 1. 短口令

恢复项目时可以直接说：

```text
恢复项目
继续项目
续任务
LT恢复
```

等价流程：

```text
project-memory-loop 检索项目记忆
  -> codex-long-task resume/status/issue-next
  -> 阅读项目上下文
  -> 继续当前 issue
```

## 2. 工具分工

```text
project-memory-loop:
  任务前检索已有记忆，任务后判断是否写回。

codex-long-task-bootstrap:
  把模糊大任务整理成 long-task 闭环。

codex-long-task:
  doctor / init / validate / status / timeline / resume /
  issue-next / issue-start / issue-close / check-add / review-add / closeout。

subagent-driven-development:
  按书面 implementation plan 派发 bounded subagent。

ccglm-delegate:
  方案成文、前端壳层、review / audit、最终汇报。

writing-skills:
  创建、重构、审计 Skill 本身。
```

## 3. 本地状态

```text
data/state.sqlite
docs/agent-state-schema.sql
```

`data/state.sqlite` 是本地运行态，不提交。

## 4. 写回原则

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

更新时间：{date}

## 1. 当前目标

```text
{objective}
```

## 2. 当前 Long-task

```text
project_key: {project_key}
title: {title}
state: data/state.sqlite
```

## 3. 恢复方式

短口令：

```text
续任务
恢复项目
LT恢复
```

恢复流程：

```text
project-memory-loop 检索项目记忆。
codex-long-task resume。
codex-long-task status。
codex-long-task issue-next。
阅读本文件和 docs/project-next-actions.md。
```

如果工具不可用，直接读取：

```text
docs/agent-memory-long-task.md
docs/project-next-actions.md
data/state.sqlite
```
"""


NEXT_ACTIONS_DOC = """# 项目下一步待办

更新时间：{date}

## 1. 当前 Long-task

```text
{title}
```

目标：

```text
{objective}
```

## 2. 初始 Issue

{issues}

## 3. 执行约定

```text
任务开始:
  project-memory-loop 检索记忆。
  codex-long-task issue-start。

任务中:
  按当前 issue 边界执行。
  有书面 plan 后才能用 subagent-driven-development。

任务结束:
  codex-long-task check-add。
  codex-long-task review-add。
  codex-long-task issue-close 或 closeout。
  project-memory-loop 判断是否写回项目经验。
```
"""


def slug(value: str) -> str:
    chars = []
    for ch in value.lower():
        if ch.isalnum():
            chars.append(ch)
        elif ch in {"-", "_", " ", "."}:
            chars.append("-")
    collapsed = "-".join(part for part in "".join(chars).split("-") if part)
    return collapsed or "long-task"


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


def init_db(db_path: Path, project_key: str, title: str, objective: str, issues: list[str]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    task_id = f"lt-{slug(title)}"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            dedent(
                """
                insert or replace into agent_long_tasks (
                  id, project_key, title, objective, status, priority, owner,
                  current_phase, context_summary, constraints_json,
                  success_criteria_json, risk_json, started_at, updated_at
                ) values (?, ?, ?, ?, 'active', 10, 'codex', 'Plan', ?, '[]', '[]', '[]', datetime('now'), datetime('now'))
                """
            ),
            (task_id, project_key, title, objective, objective),
        )
        for idx, issue in enumerate(issues, start=1):
            conn.execute(
                dedent(
                    """
                    insert or replace into agent_long_task_steps (
                      id, task_id, step_order, phase, title, status, detail, updated_at
                    ) values (?, ?, ?, 'Issue', ?, 'pending', '', datetime('now'))
                    """
                ),
                (f"{task_id}-issue-{idx:02d}", task_id, idx, issue),
            )
        conn.execute(
            dedent(
                """
                insert or replace into agent_events (
                  id, project_key, task_id, event_type, phase, summary, payload_json
                ) values (?, ?, ?, 'init', 'Init', ?, ?)
                """
            ),
            (
                f"evt-init-{task_id}",
                project_key,
                task_id,
                "Initialized project long-task state.",
                json.dumps({"source": "codex-long-task-bootstrap"}, ensure_ascii=False),
            ),
        )
    print(f"initialized {db_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap project memory + long-task files.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--project-key", required=True, help="Stable project key for state.sqlite.")
    parser.add_argument("--title", required=True, help="Initial long-task title.")
    parser.add_argument("--objective", required=True, help="Initial long-task objective.")
    parser.add_argument(
        "--issue",
        action="append",
        default=[],
        help="Initial issue title. Can be repeated.",
    )
    parser.add_argument("--context-doc", default="docs/current-project-context.md")
    parser.add_argument("--next-actions-doc", default="docs/project-next-actions.md")
    parser.add_argument("--no-init-db", action="store_true")
    parser.add_argument("--force", action="store_true", help="Overwrite generated docs if present.")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    issues = args.issue or ["Plan first issue", "Implement first issue", "Review and closeout"]

    project_root.mkdir(parents=True, exist_ok=True)
    ensure_gitignore(project_root)

    today = date.today().isoformat()
    issue_lines = "\n".join(f"{idx}. {issue}" for idx, issue in enumerate(issues, start=1))

    write_text(project_root / "docs" / "agent-state-schema.sql", SCHEMA.strip() + "\n", args.force)
    write_text(
        project_root / "docs" / "agent-memory-long-task.md",
        MEMORY_DOC.format(date=today),
        args.force,
    )
    write_text(
        project_root / args.context_doc,
        CONTEXT_DOC.format(
            date=today,
            project_key=args.project_key,
            title=args.title,
            objective=args.objective,
        ),
        args.force,
    )
    write_text(
        project_root / args.next_actions_doc,
        NEXT_ACTIONS_DOC.format(
            date=today,
            title=args.title,
            objective=args.objective,
            issues=issue_lines,
        ),
        args.force,
    )

    if not args.no_init_db:
        init_db(project_root / "data" / "state.sqlite", args.project_key, args.title, args.objective, issues)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
