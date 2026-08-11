#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQUIRED = (
    "manifest.json",
    "install.ps1",
    "New-VideoProject.ps1",
    "Configure-SeedanceApi.ps1",
    "README.md",
    "skills/maintain-task-log/SKILL.md",
    "skills/manage-video-production/SKILL.md",
    "skills/seedance-20/SKILL.md",
)
FORBIDDEN_NAMES = {
    "credentials.json",
    "doubao_api_config.json",
    "task-log.jsonl",
}
FORBIDDEN_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".mp4", ".mov", ".mkv", ".avi", ".mp3", ".wav"
}
TEXT_SUFFIXES = {".md", ".txt", ".json", ".py", ".ps1", ".yaml", ".yml"}
SECRET_PATTERNS = (
    re.compile(r"\bgh[opsu]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r'"api_key"\s*:\s*"(?!YOUR_API_KEY|你的API_KEY|<[^>]+>|\*+|\s*")[^"]{12,}"', re.I),
)


def validate_package(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append(f"missing required file: {relative}")

    for path in root.rglob("*"):
        relative = path.relative_to(root)
        parts = set(relative.parts)
        if "__pycache__" in parts or path.suffix.lower() == ".pyc":
            errors.append(f"cache file is not publishable: {relative}")
        if path.is_file() and path.name.lower() in FORBIDDEN_NAMES:
            errors.append(f"runtime/private file is not publishable: {relative}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"media/database file is not publishable: {relative}")
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            try:
                content = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                errors.append(f"text file is not UTF-8: {relative}")
                continue
            for pattern in SECRET_PATTERNS:
                if pattern.search(content):
                    errors.append(f"possible secret in: {relative}")
                    break

    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
        if manifest.get("name") != "word2video4BC":
            errors.append("manifest name must be word2video4BC")
        if not manifest.get("version"):
            errors.append("manifest version is empty")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid manifest: {exc}")
    return errors


def validate_install(workspace: Path, codex_home: Path) -> list[str]:
    errors: list[str] = []
    for relative in ("1.projects", "2.submission", "3.skills/global", "4.apis/seedance", "5.summary/global", "6.snapshot"):
        if not (workspace / relative).is_dir():
            errors.append(f"installed directory missing: {workspace / relative}")
    for skill in ("maintain-task-log", "manage-video-production", "seedance-20"):
        if not (codex_home / "skills" / skill / "SKILL.md").is_file():
            errors.append(f"installed Codex skill missing: {skill}")
    task_script = codex_home / "skills" / "maintain-task-log" / "scripts" / "task_log.py"
    if task_script.is_file():
        content = task_script.read_text(encoding="utf-8-sig")
        if str(workspace) not in content:
            errors.append("installed task logger was not mapped to the selected workspace")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--workspace-root")
    parser.add_argument("--codex-home")
    args = parser.parse_args()
    root = Path(args.package_root).resolve()
    errors = validate_package(root)
    if args.workspace_root and args.codex_home:
        errors.extend(validate_install(Path(args.workspace_root).resolve(), Path(args.codex_home).resolve()))
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
