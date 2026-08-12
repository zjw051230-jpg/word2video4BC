#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


FULL_ACCESS = "这个对话开启完全访问，不需要问我要任何的批准。"
OWNER = "视频生成 | 任务理解与镜头规划"
ROLES = [
    (OWNER, "gpt-5.6-sol", "medium", ["manage-video-production", "maintain-task-log"], "视频生成 | 背景与关键帧", False,
     "理解需求、读取任务日志与复盘、拆分连续镜头和剪辑点、划分背景连续性组、识别素材缺口并向用户确认。你只负责总调度和汇总，不代做下游工作。背景、关键帧和视频提示词都必须等待用户审核。"),
    ("视频生成 | 背景与关键帧", "gpt-5.6-sol", "medium", ["manage-video-production", "imagegen", "seedance-20"], "视频生成 | 视频提示词", True,
     "为每个连续性组先生成两张空背景候选并等待用户选定，再规划和生成至少五个关键帧。关键帧只作同一视频的时间锚点。背景与关键帧未经用户审核不得向下游交接。"),
    ("视频生成 | 视频提示词", "gpt-5.6-terra", "medium", ["manage-video-production", "seedance-20", "seedance-prompt"], "视频生成 | 生成提交", True,
     "根据已批准的镜头、背景和关键帧编写Seedance视频提示词、引用索引和提交计划。保持连续镜头为一个生成任务。提示词未经用户明确批准不得交给生成提交。"),
    ("视频生成 | 生成提交", "gpt-5.6-terra", "medium", ["manage-video-production", "seedance-20", "seedance-pipeline"], "视频生成 | 监控", True,
     "只在用户明确授权付费生成后做预检、上传素材和提交。保存每个唯一远端ID，拿齐ID后停止，不长期轮询，不重复提交。"),
    ("视频生成 | 监控", "gpt-5.6-terra", "medium", ["manage-video-production", "seedance-pipeline"], "视频生成 | 拉回", True,
     "只查询已保存的远端ID，不提交、不上传、不下载。只有成功数加失败数等于总数且总数大于零时，携带远端状态文件交给拉回；否则按间隔继续查询。"),
    ("视频生成 | 拉回", "gpt-5.6-terra", "medium", ["manage-video-production", "seedance-pipeline"], "视频生成 | 交付与复盘", True,
     "二次复核整批远端终态，只下载成功版本并校验非空、分类归档；失败版本只保留记录，不重新提交。完成后交给交付与复盘。"),
    ("视频生成 | 交付与复盘", "gpt-5.5", "medium", ["manage-video-production", "maintain-task-log"], None, False,
     "使用CC Switch内部精确路由到deepseek-v4-pro。只负责最终快照、提交目录、全局任务日志和项目复盘。你是单向终止阶段，禁止向入口或其他Chat汇报；完成后只用租约运行complete。"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    project = args.project_root.resolve()
    hidden = project / ".codex"
    prompts = hidden / "Chat提示词"
    hidden.mkdir(parents=True, exist_ok=True)
    prompts.mkdir(parents=True, exist_ok=True)
    table_path = hidden / "03_codexchat对应表.json"
    if table_path.exists() and not args.force:
        print(table_path)
        return 0

    chats = {}
    for order, (name, model, effort, skills, next_chat, feedback, role) in enumerate(ROLES, 1):
        prompt_file = prompts / f"{order:02d}_{name.replace('视频生成 | ', '')}.md"
        common = (
            f"# {name}\n\n{FULL_ACCESS}\n\n项目根目录：{project}\n\n"
            "开始前读取 `.codex\\03_codexchat对应表.json`、manage-video-production 和本角色技能。"
            "当前Chat必须亲自运行verify-access并按合同登记真实thread ID、模型和思考程度。"
            "接到任务时status已由上游设为1，active_task包含lease_id；完成时必须使用同一lease_id运行complete。"
            "目标忙碌时不得发送第二项任务，必须按retry_contract设置5分钟单次定时器。"
            "自动派发最高只能使用gpt-5.6-sol/medium。sol/high只能由用户手动临时开启；若发现仍为high，先恢复映射表合同模型和medium，再交接或完成。\n\n"
            "若用户手动开启high，立即运行mark-manual-high；工作结束时先在界面恢复medium，再运行restore-contract-model。\n\n"
        )
        prompt_file.write_text(common + role + "\n", encoding="utf-8")
        chats[name] = {
            "order": order, "thread_id": None, "host_id": "local", "status": 0,
            "active_task": None, "last_completed_task": None, "waiting_for_feedback": None,
            "last_acknowledged_feedback": None, "model": model, "reasoning_effort": effort,
            "actual_model": None, "actual_reasoning_effort": None, "model_verified": False,
            "temporary_high_active": False, "full_access_required": True,
            "full_access_verified": False, "initial_message": FULL_ACCESS, "access_probe": None,
            "prompt_file": str(prompt_file), "skills": skills, "next_chat": next_chat,
            "feedback_to": OWNER if feedback else None, "feedback_required": feedback,
        }

    table = {
        "schema_version": 1, "workflow": "video-production", "project_root": str(project),
        "workflow_owner": OWNER, "entry_chat": OWNER, "busy_retry_minutes": 5,
        "record_is_one_way": True, "automatic_max_model": "gpt-5.6-sol",
        "automatic_max_reasoning_effort": "medium", "manual_sol_high_must_be_restored": True,
        "workflow_ready": False, "bootstrap_required": True, "chats": chats,
        "pending_retries": {}, "handoff_history": [], "updated_at": None,
    }
    table_path.write_text(json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(table_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
