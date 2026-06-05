# Agent 记忆、长任务与执行编排

更新时间：2026-06-05

## 1. 目标

这套工作流解决两个问题：

```text
Memory:
  项目经验沉淀。
  任务开始前检索已有记忆。
  任务结束后判断是否写回经验。

Long-task:
  长任务拆解。
  状态持久化。
  跨会话恢复。
  生命周期管理。
```

短口令：

```text
恢复项目
继续项目
续任务
LT恢复
```

等价流程：

```text
project-memory-loop
  -> codex-long-task resume/status/issue-next
  -> 读取项目上下文
  -> 执行当前 issue
  -> check/review/closeout
  -> project-memory-loop 写回判断
```

## 2. 工具分工

### project-memory-loop

项目记忆工作流 Skill。

任务开始前：

```text
检索相关历史经验。
提取本轮必须遵守的约束。
识别可复用实现模式。
```

任务结束后：

```text
判断是否写回项目经验。
只写可复用、已验证、非敏感的内容。
```

### codex-long-task-bootstrap

把模糊的大任务整理成 long-task 闭环。

负责把用户目标转成：

```text
objective
constraints
success criteria
issues
checks
reviews
closeout
```

### codex-long-task

long-task CLI 生命周期：

```text
doctor
init
validate
status
timeline
resume
issue-next
issue-start
issue-close
check-add
review-add
closeout
```

默认本地状态：

```text
data/state.sqlite
```

schema：

```text
docs/agent-state-schema.sql
```

### subagent-driven-development

按书面 implementation plan 派发 subagent 执行。

只能在这些条件满足时使用：

```text
有明确 implementation plan。
有当前 issue 边界。
有允许修改的文件范围。
有验收标准。
不需要实时用户判断。
```

### ccglm-delegate

适合委托：

```text
方案成文。
前端壳层。
review / audit。
最终汇报。
```

不作为主实现执行器。

### writing-skills

负责创建、重构、审计 Skill 本身。

适合：

```text
把项目工作流抽成 Skill。
审计 Skill 触发条件。
调整 Skill 提示词和资源结构。
维护 Skill 工程化质量。
```

## 3. 生命周期

### Init

```text
project-memory-loop 检索项目记忆。
codex-long-task doctor。
codex-long-task init。
codex-long-task validate。
```

产物：

```text
long-task objective。
约束。
成功标准。
初始 issue。
恢复说明。
```

### Plan

```text
codex-long-task status。
codex-long-task timeline。
codex-long-task issue-next。
必要时 ccglm-delegate plan。
```

产物：

```text
implementation plan。
issue 顺序。
每个 issue 的边界、文件范围、验收标准。
```

### Issue

```text
codex-long-task issue-start。
按 issue 范围实现。
必要时 subagent-driven-development 派发子任务。
codex-long-task check-add。
codex-long-task issue-close。
```

### Resume

```text
project-memory-loop 检索项目记忆。
codex-long-task resume。
codex-long-task status。
codex-long-task issue-next。
读取项目上下文文档。
```

如果 CLI / Skill 不可用，降级为：

```text
读取 docs/agent-memory-long-task.md。
读取项目上下文文档。
读取项目 next-actions 文档。
查看 data/state.sqlite。
```

### Review

```text
codex-long-task review-add。
必要时 ccglm-delegate review / audit。
必要时 subagent-driven-development 做局部审计。
```

检查：

```text
是否遵守项目约束。
是否完成当前 issue。
是否有验证记录。
是否有未解决风险。
是否需要写回项目记忆。
```

### Closeout

```text
codex-long-task closeout。
project-memory-loop 判断是否写回经验。
必要时 ccglm-delegate 最终汇报。
```

## 4. 记忆写回规则

写回：

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

## 5. 提交规则

提交：

```text
docs/agent-memory-long-task.md
docs/agent-state-schema.sql
项目 context / next-actions 文档
```

不提交：

```text
data/state.sqlite
任何包含真实地址、短链、用户名、token、设备私有连接信息的状态导出
```
