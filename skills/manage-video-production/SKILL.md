---
name: manage-video-production
description: Manage the D:\视频生成 production workspace, including project creation and in-place edits, task execution, immutable version snapshots, delivery packaging, review/复盘 updates, Seedance prompting, API preparation, and video generation. Use whenever Codex creates, modifies, generates, exports, submits, or reviews files for a project in this workspace, including requests mentioning 项目, task, 视频生成, Seedance, 提交, snapshot, version, or 复盘.
---

# Manage Video Production

## Handle toolkit update requests

When the user says `更新视频工具`, `视频工具需要更新`, or an equivalent request, use the registered Git checkout only—not a downloaded archive. Read `<WorkspaceRoot>\.word2video4BC\update-source.json`; verify `repository` is exactly `https://github.com/zjw051230-jpg/word2video4BC`, `main_branch` is `main`, and `checkout_root` is an existing clean Git checkout whose `origin` is that repository. Then run `git -C <checkout_root> pull --ff-only origin main` and run that checkout's `install.ps1 -UpdateOnly -Force` (or the recorded local `Update-Toolkit.ps1`, which performs those same steps). The updater may modify only the declared tool scope. It must never scan, sync, move, rename, overwrite, or delete projects, materials, submissions, API configuration, summaries, snapshots, or task logs. Ask for the official repository link only when the hidden update record does not exist; after the first verified installation the link must not be needed again.

## Honor the workspace contract

Use these paths exactly:

- `D:\视频生成\1.projects\<project>`: canonical working copy and latest state; keep that project's tasks and source materials inside it.
- `D:\视频生成\2.submission\<project>\<task-folder>`: completed deliverables, grouped by project first and task second.
- `D:\视频生成\3.skills\global\<skill>`: skills shared by every project.
- `D:\视频生成\3.skills\<project>\<skill>`: skills dedicated to one project.
- `D:\视频生成\4.apis`: local Seedance API configuration and credentials.
- `D:\视频生成\5.summary\global\lessons.md`: cross-project lessons.
- `D:\视频生成\5.summary\<project>\lessons.md`: lessons dedicated to one project.
- `D:\视频生成\6.snapshot\<project>\<task-folder>\vNNN-<label>`: immutable history.

Never edit a snapshot. Modify the canonical project in place only after preserving its current state.

## Resolve the task identity

Determine these values before writing project files:

1. `project`: use the user-specified project. If only one existing project fits the request, use it. Ask only when choosing incorrectly would risk another project.
2. `task-id`: preserve a supplied ID. Otherwise assign `TyyyyMMdd-HHmmss` in Asia/Shanghai time.
3. `task-date`: record `yyyy-MM-dd` when the task starts and keep it unchanged if work crosses midnight.
4. `summary`: write a stable, filesystem-safe description of at most 10 visible characters; prefer exactly 10 Chinese characters when natural.
5. `task-folder`: combine them as `yyyy-MM-dd_<task-id>_<summary>`.

Keep the same task identity through all revisions of one task.

## Run every task in this order

### -1. Bootstrap the video Chat workflow

For every project, read `references/chat-workflow.md` and run `scripts/manage_chat_workflow.py --project-root <project> bootstrap-status` before business work. The entry Chat must be named `视频生成 | 任务理解与镜头规划`; it must create and register the other six fixed video-production Chats with the exact model and reasoning contracts returned by the script. Do not execute the whole pipeline in one Chat.

Use the same atomic status, unique thread ID, lease, feedback, and five-minute busy retry contracts defined in that reference. Automatic contracts must never exceed `gpt-5.6-sol / medium`. `sol/high` is user-only and temporary; restore the contract model and `medium` before handoff or completion. The final `视频生成 | 交付与复盘` Chat uses `gpt-5.5 / medium`, routed by CC Switch to `deepseek-v4-pro`, and is one-way.

### 0. Read and maintain the global task log

Invoke `$maintain-task-log` for every task under `D:\视频生成`, regardless of task type. Before task actions, read `D:\视频生成\task-log.jsonl`, determine whether the request continues an existing task or starts a new one, and append a start record. Before the final response, read that task's records again and append an end record with work performed, artifact locations, evaluation if any, review/复盘 locations, and notes or annotations. Append progress records for meaningful intermediate artifacts, feedback, failures, or decisions.

### 1. Read lessons first

Before changing or generating anything, read these files when present:

- `D:\视频生成\5.summary\global\lessons.md`
- `D:\视频生成\5.summary\<project>\lessons.md`

Convert applicable lessons into a short preflight checklist. Do not silently ignore a conflicting lesson; explain the conflict and follow the user's latest explicit instruction.

### 2. Snapshot before overwrite

Before the first modification in a task or feedback cycle, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File 'D:\视频生成\3.skills\global\manage-video-production\scripts\snapshot-project.ps1' `
  -Project '<project>' -TaskId '<task-id>' -TaskDate '<yyyy-MM-dd>' `
  -Summary '<summary>' -Label 'before'
```

For a new project, create its directory and capture the empty baseline before adding content. Stop if the snapshot fails; do not overwrite without history.

### 3. Work only in the project

Perform the requested operations inside `1.projects\<project>`. Keep the working project as the latest version. Preserve unrelated user files and never use `2.submission` or `6.snapshot` as a working directory.

### 4. Close every revision cycle

After each meaningful revision or user-requested modification:

1. Capture the resulting state with the snapshot script and label it `after`, `review-1`, `review-2`, or another short stage name.
2. Append at least one concise requirement learned or reconfirmed in this cycle to `5.summary\<project>\lessons.md`.
3. Format each lesson as `- [yyyy-MM-dd][task-id] requirement`.
4. Keep only actionable constraints, avoid narrative, and do not duplicate an existing rule.

Use `5.summary\global\lessons.md` only for requirements that genuinely apply to every project.

### 5. Generate Seedance work safely

Before each video generation, re-read global and project lessons and check the prompt against them.

- Invoke `$seedance-20` for every Seedance request. Follow its root operating loop and load its relative sub-skills only when routed by that loop.
- For API, provider, pricing, model-ID, or platform-limit claims, follow `$seedance-20`'s source gate and pipeline references, then read the relevant local client or credentials under `4.apis`.
- Never invent endpoints, model IDs, authentication fields, or provider capabilities.
- Keep credentials in `4.apis`; never echo, commit, copy into submissions, snapshots, prompts, logs, or final messages.
- Record generated artifacts and the exact non-secret parameters in the canonical project.

### 5a. Lock shared backgrounds before character keyframes

Partition generated shots into background-continuity groups according to story and character needs. Different groups may and should use different locations when that improves characterization. For each group that must share one location, use this two-pass image workflow:

1. Generate exactly two empty background candidates for that group before generating any character keyframe.
2. Stop for explicit user selection of one candidate. Treat the selected image as the immutable master for that character, scene, or continuity group only; do not force unrelated characters or scenes to reuse it.
3. On every later GPT Image character-keyframe request, pass the selected background as a dedicated input image and label it as the sole authority for environment geometry, fixed props, materials, time of day, palette, and light direction.
4. Label the character turnaround separately as the sole identity and design authority; label action frames as pose and motion only.
5. Require at least five planned and generated keyframes for every video: setup, preparation, action peak, visible consequence, and changed end state. Give every keyframe its own detailed image prompt, camera, composition, motion phase, and continuity endpoint.
6. Do not generate character keyframes until the background is selected. Do not silently substitute or redesign the selected background in later passes.
7. After selection, archive both candidates under `1.projects\<project>\0.背景参考\<character-or-group>` as `背景1` (selected) and `背景2` (alternate), unless the project has a stricter naming convention. Use `背景1` as the environment-authority input for every keyframe and final video in that group, while retaining batch-local originals as task history.

### 5b. Preserve continuous shots in one generation

Do not split one continuous action across separate Seedance generations when the scene, camera setup, camera movement, time, and motion vector remain continuous. Generate that shot as one task; use intermediate reference images only as temporal anchors inside the same generation.

Split generation only at an intentional editorial cut to a genuinely different camera shot, such as a new camera position, angle, lens, framing, or separately motivated shot contract. Record the cut point and the purpose of both shots in the plan. A timing boundary, action peak, or desire for easier generation is not sufficient reason to split a continuous shot.

For avoidance of doubt, five planned keyframes are temporal anchors within one Seedance task when the action and camera remain continuous; they must never be submitted as five generation jobs. Split only at an intentional editorial cut to a truly different camera shot.

### 6. Package the result

After approval or completion:

1. Capture a `final` snapshot.
2. Create `2.submission\<project>\yyyy-MM-dd_<task-id>_<summary>`.
3. Copy only final deliverables into it; leave editable sources in the project.
4. Preserve existing submissions. Do not overwrite a same-named folder without explicit user approval.

Apply only this folder convention for now. Leave detailed submission renaming and inspection to the separate skill planned for that purpose.

## Guardrails

- Keep `3.skills` as the single source of truth. Put shared skills under `3.skills\global`, project-only skills under `3.skills\<project>`, and never place a skill directly in `3.skills`.
- Expose global and applicable project skills to Codex with directory junctions instead of maintaining copies.
- Keep summaries under `5.summary\global` or `5.summary\<project>`; never place a summary file directly in `5.summary`.
- Keep all versions under `6.snapshot`; never prune them unless the user explicitly requests deletion.
- Never place secrets or large generated media inside a skill folder.
- Report the project path, created snapshot versions, submission path, and appended lessons at handoff.
