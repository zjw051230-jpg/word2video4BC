---
name: maintain-task-log
description: Maintain the append-only global task log at D:\视频生成\视频本体\03_运行日志\task-log.jsonl. Use for every task performed anywhere under D:\视频生成, regardless of task type, to read prior history before work, identify whether the request continues an existing task or starts a new one, record task start/progress/end, and preserve what was done, artifact locations, user evaluation, review/复盘 locations, and notes or annotations.
---

# Maintain Task Log

Use `scripts/task_log.py` as the only writer for `D:\视频生成\视频本体\03_运行日志\task-log.jsonl`. Keep the log append-only; never rewrite or delete old records. The hidden root `task-log.jsonl` is only a compatibility hard link, never a second log.

## At task start

1. Run `read --limit 50` before changing files or performing task actions.
2. Compare the request with recent records using project, summary, task ID, artifact paths, and notes.
3. Reuse the recorded task ID when the user is continuing, revising, reviewing, or asking about the same deliverable. Create a new `TyyyyMMdd-HHmmss` ID in Asia/Shanghai only when no prior task matches.
4. Append a `开始` record before substantive work. State whether it is a new task or a continuation in `备注标注`.

Do not treat a new chat as a new task by itself. Treat continuity of objective or deliverable as the deciding signal.

## During work

Append a `进展` record when one of these occurs:

- a meaningful artifact is created, moved, generated, submitted, or reviewed;
- the user gives an evaluation, correction, approval, rejection, or annotation;
- a blocker, failed attempt, changed decision, or important path is worth preserving;
- work spans multiple distinct stages.

Record paths as absolute paths. Record only locations and non-secret context; never place credentials, tokens, private keys, or secret values in the log.

## Before task end

1. Run `read --task-id <id>` again before the final response.
2. Check that the history identifies what was done and where every important input/output is located.
3. Append an `结束` record containing the final result, artifact paths, any user evaluation, review/复盘 locations, and concrete notes or annotations.
4. If unfinished, use `进展` rather than falsely marking the task ended, and state the remaining work in `备注标注`.

## Commands

Read recent history:

```powershell
python scripts/task_log.py read --limit 50
```

Read one task:

```powershell
python scripts/task_log.py read --task-id T20260723-164111
```

Append an event:

```powershell
python scripts/task_log.py append `
  --task-id T20260723-164111 --phase 开始 --project 王国大作战 `
  --summary 创建全局任务日志 `
  --did "读取历史并初始化日志技能" `
  --file "D:\视频生成\视频本体\01_程序与工具\3.skills\global\maintain-task-log" `
  --review "D:\视频生成\视频本体\03_运行日志\全局复盘\lessons.md" `
  --note "新任务"
```

Repeat `--file` and `--review` for multiple paths. Omit `--evaluation`, `--review`, or `--note` when they do not apply; the script records empty values consistently.

## Record contract

Every JSONL line contains:

- `时间`, `任务ID`, `阶段`, `项目`, `摘要`
- `干了什么`
- `文件位置` as an array
- `评价`
- `复盘位置` as an array
- `备注标注`

Use concise factual wording. Preserve user evaluation verbatim when practical and clearly distinguish it from Codex's own assessment.
