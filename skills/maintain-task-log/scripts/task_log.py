#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(r"D:\视频生成")
CANONICAL_LOG_PATH = WORKSPACE_ROOT / "视频本体" / "03_运行日志" / "task-log.jsonl"
LEGACY_LOG_PATH = WORKSPACE_ROOT / "task-log.jsonl"
# v2.2.0 installs the canonical body path. The fallback keeps this skill usable
# while an older workspace is awaiting its one-time layout migration.
LOG_PATH = CANONICAL_LOG_PATH if CANONICAL_LOG_PATH.parent.exists() else LEGACY_LOG_PATH
TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
PHASES = ("开始", "进展", "结束")


def load_records():
    if not LOG_PATH.exists():
        return []
    records = []
    with LOG_PATH.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSONL at line {line_number}: {exc}")
    return records


def command_read(args):
    records = load_records()
    if args.task_id:
        records = [r for r in records if r.get("任务ID") == args.task_id]
    if args.project:
        records = [r for r in records if r.get("项目") == args.project]
    records = records[-args.limit :]
    print(json.dumps(records, ensure_ascii=False, indent=2))


def clean_paths(values):
    result = []
    for value in values or []:
        expanded = os.path.abspath(os.path.expandvars(value))
        if expanded not in result:
            result.append(expanded)
    return result


def command_append(args):
    existing = load_records()
    if args.phase == "开始":
        prior = [r for r in existing if r.get("任务ID") == args.task_id]
        if prior:
            print(f"continuation: {args.task_id} has {len(prior)} prior record(s)", file=sys.stderr)
    record = {
        "时间": datetime.now(TZ).isoformat(timespec="seconds"),
        "任务ID": args.task_id,
        "阶段": args.phase,
        "项目": args.project or "全局",
        "摘要": args.summary,
        "干了什么": args.did,
        "文件位置": clean_paths(args.file),
        "评价": args.evaluation or "",
        "复盘位置": clean_paths(args.review),
        "备注标注": args.note or "",
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps(record, ensure_ascii=False, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(description="Read or append the global video-workspace task log.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    read_parser = subparsers.add_parser("read")
    read_parser.add_argument("--task-id")
    read_parser.add_argument("--project")
    read_parser.add_argument("--limit", type=int, default=50)
    read_parser.set_defaults(func=command_read)

    append_parser = subparsers.add_parser("append")
    append_parser.add_argument("--task-id", required=True)
    append_parser.add_argument("--phase", required=True, choices=PHASES)
    append_parser.add_argument("--project")
    append_parser.add_argument("--summary", required=True)
    append_parser.add_argument("--did", required=True)
    append_parser.add_argument("--file", action="append", default=[])
    append_parser.add_argument("--evaluation")
    append_parser.add_argument("--review", action="append", default=[])
    append_parser.add_argument("--note")
    append_parser.set_defaults(func=command_append)
    return parser


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
