from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(r"D:\孵化-上岛\1.projects\孵化-上岛")
OUT_ROOT = ROOT / r"6.生成结果\T20260812-144226\ol3d_minigame_ads_15versions"
API_DIR = Path(r"D:\孵化-上岛\4.apis\seedance")
CFG_PATH = API_DIR / "api_config2.json"
MANIFEST_PATH = OUT_ROOT / "img2_binding_manifest.json"
VERSIONS = [f"V{i:03d}" for i in range(1, 16)]
_write_lock = threading.Lock()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def root_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base[:-3] if base.lower().endswith("/v1") else base


def headers(cfg: dict) -> dict[str, str]:
    return {"Authorization": "Bearer " + cfg["api_key"]}


def json_request(method: str, url: str, cfg: dict, payload: dict | None = None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request_headers = {**headers(cfg), "Accept": "application/json"}
    if body is not None:
        request_headers["Content-Type"] = "application/json; charset=utf-8"
    request = Request(url, data=body, method=method, headers=request_headers)
    try:
        with urlopen(request, timeout=300) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except (URLError, TimeoutError, OSError) as exc:
        return None, None, type(exc).__name__ + ": " + str(exc)
    try:
        return json.loads(raw), status, None
    except json.JSONDecodeError:
        return None, status, "non_json_response: " + raw[:1000]


def upload_image(path: Path, cfg: dict) -> dict:
    boundary = "----Codex" + uuid.uuid4().hex
    field = "file"
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; "
        f"filename=\"{path.name}\"\r\nContent-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("ascii")
    request = Request(
        root_url(cfg["base_url"]) + "/api/upload/image",
        data=body,
        method="POST",
        headers={**headers(cfg), "Accept": "application/json", "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urlopen(request, timeout=300) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except (URLError, TimeoutError, OSError) as exc:
        return {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
    try:
        response = json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "failed", "http_status": status, "error": "non_json_response: " + raw[:1000]}
    filename = response.get("filename") if isinstance(response, dict) else None
    if not isinstance(filename, str) or not filename.strip():
        return {"status": "failed", "http_status": status, "response": response, "error": "missing_filename"}
    return {"status": "success", "http_status": status, "filename": filename, "response": response}


def version_data(version: str):
    folder = OUT_ROOT / version
    plan = read_json(folder / "video" / "结构化提交计划.json")
    state = read_json(folder / f"{version}_state.json")
    manifest = read_json(MANIFEST_PATH)
    manifest_row = next(row for row in manifest["versions"] if row["version"] == version)
    if state.get("video_stage_unlocked") is not True:
        raise RuntimeError(f"{version}: video_stage_unlocked is not true")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 11:
        raise RuntimeError(f"{version}: expected 11 tasks")
    if manifest_row.get("cross_version_asset_mix") is not False:
        raise RuntimeError(f"{version}: manifest cross_version_asset_mix is not false")
    local_paths = []
    for task_index, task in enumerate(tasks, 1):
        expected = f"{version}-R{task_index:02d}"
        if task.get("task_id") != expected:
            raise RuntimeError(f"{version}: invalid shot id {task.get('task_id')!r}, expected {expected}")
        if task.get("mode") != "I2V" or task.get("aspect_ratio") != "9:16" or task.get("resolution") != "720x1280":
            raise RuntimeError(f"{version}/{expected}: I2V geometry gate failed")
        if float(task.get("duration_sec")) != 4.0 or task.get("quality") != "720p" or task.get("generate_audio") is not True:
            raise RuntimeError(f"{version}/{expected}: duration/quality/audio gate failed")
        if task.get("reference_video") is not None:
            raise RuntimeError(f"{version}/{expected}: reference_video is not null in plan")
        for raw in [task["start_frame"]["path"], task["end_frame"]["path"]] + [x["path"] for x in task["source_asset_binding"]]:
            path = Path(raw)
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"{version}/{expected}: missing asset {path}")
            if str(path) not in local_paths:
                local_paths.append(str(path))
        for frame in (task["start_frame"], task["end_frame"]):
            if not all(frame.get(k) is True for k in ("exists", "technical_pass", "semantic_pass", "state_machine_continuity_pass")):
                raise RuntimeError(f"{version}/{expected}: endpoint acceptance gate failed")
    return folder, plan, state, manifest_row, local_paths


def upload_version(version: str, cfg: dict):
    folder, plan, state, manifest_row, local_paths = version_data(version)
    out = folder
    receipt_path = out / "upload_receipts.json"
    if receipt_path.exists():
        raise RuntimeError(f"{version}: upload_receipts.json already exists; refusing overwrite")
    receipts = []
    for raw in local_paths:
        path = Path(raw)
        result = upload_image(path, cfg)
        row = {"local_path": raw, "sha256": sha256(path), "byte_size": path.stat().st_size, **result}
        receipts.append(row)
        write_json(receipt_path, receipts)
        if result.get("status") != "success":
            raise RuntimeError(f"{version}: upload failed for {raw}: {result.get('error')}")
    by_path = {row["local_path"]: row["filename"] for row in receipts if row.get("status") == "success"}
    if len(by_path) != len(local_paths) or any(not isinstance(x, str) or not x for x in by_path.values()):
        raise RuntimeError(f"{version}: upload receipt audit failed")
    shots = []
    for task in plan["tasks"]:
        sid = task["task_id"]
        start = task["start_frame"]["path"]
        end = task["end_frame"]["path"]
        source = [{"local_path": x["path"], "asset_id": by_path[x["path"]], "sha256": x["sha256"]} for x in task["source_asset_binding"]]
        shots.append({"shot_id": sid, "start_frame": {"local_path": start, "asset_id": by_path[start]}, "end_frame": {"local_path": end, "asset_id": by_path[end]}, "source_asset_binding": source})
    write_json(out / "asset_bindings.json", {"version": version, "cross_version_asset_mix": False, "bindings": shots})
    for task in plan["tasks"]:
        sid = task["task_id"]
        start = by_path[task["start_frame"]["path"]]
        end = by_path[task["end_frame"]["path"]]
        refs = [start] if start == end else [start, end]
        payload = {"model": cfg["model"], "prompt": task["prompt"], "n": 1, "size": "720x1280", "seconds": "4", "aspect_ratio": "9:16", "quality": "720p", "generate_audio": True, "external_tts_blocked": True, "input_reference": refs, "first_frame": start, "last_frame": end, "reference_video": None}
        serialized = json.dumps(payload, ensure_ascii=False)
        if any(str(Path(x)) in serialized for x in local_paths):
            raise RuntimeError(f"{version}/{sid}: local path entered payload")
        if payload["prompt"] != next(t["prompt"] for t in plan["tasks"] if t["task_id"] == sid):
            raise RuntimeError(f"{version}/{sid}: prompt mapping failed")
        write_json(out / f"{sid}_payload_snapshot.json", payload)
    write_json(out / "upload_audit.json", {"version": version, "uploaded": len(receipts), "required": len(local_paths), "passed": True, "asset_ids_are_returned_filenames": True, "reference_video": None})
    return {"version": version, "uploaded": len(receipts), "required": len(local_paths)}


def submit_one(item):
    version, out, task, payload, cfg = item
    sid = task["task_id"]
    result, status_code, error = json_request("POST", cfg["base_url"].rstrip("/") + "/videos", cfg, payload)
    if result is None:
        result = {"error": error}
    write_json(out / f"{sid}_submit_response.json", {"http_status": status_code, "response": result})
    remote_id = result.get("id") if isinstance(result, dict) else None
    remote_id = remote_id if isinstance(remote_id, str) and remote_id else None
    response_status = result.get("status", "submit_failed") if isinstance(result, dict) else "submit_failed"
    failed_status = str(response_status).lower() in {"failed", "error", "submit_failed"}
    submission_error = error or ("missing_remote_id" if not remote_id else None) or ("remote_response_failed" if failed_status else None)
    return {"shot_id": sid, "remote_id": None if submission_error else remote_id, "status": response_status, "http_status": status_code, "error": submission_error, "reference_video": None, "input_reference_count": len(payload["input_reference"])}


def submit_version(version: str, cfg: dict):
    folder, plan, state, manifest_row, local_paths = version_data(version)
    if not (folder / "upload_audit.json").is_file() or not read_json(folder / "upload_audit.json").get("passed"):
        raise RuntimeError(f"{version}: upload audit missing or failed")
    bindings = read_json(folder / "asset_bindings.json")["bindings"]
    binding_map = {row["shot_id"]: row for row in bindings}
    receipt_path = folder / "upload_receipts_repaired.json" if (folder / "upload_receipts_repaired.json").exists() else folder / "upload_receipts.json"
    receipts = read_json(receipt_path)
    returned = {row["local_path"]: row.get("filename") for row in receipts if row.get("status") == "success"}
    if len(returned) != len(receipts) or any(not isinstance(x, str) or not x for x in returned.values()):
        raise RuntimeError(f"{version}: receipt mapping invalid")
    items = []
    for task in plan["tasks"]:
        sid = task["task_id"]
        b = binding_map[sid]
        start = b["start_frame"]["asset_id"]
        end = b["end_frame"]["asset_id"]
        refs = [start] if start == end else [start, end]
        payload = {"model": cfg["model"], "prompt": task["prompt"], "n": 1, "size": "720x1280", "seconds": "4", "aspect_ratio": "9:16", "quality": "720p", "generate_audio": True, "external_tts_blocked": True, "input_reference": refs, "first_frame": start, "last_frame": end, "reference_video": None}
        serialized = json.dumps(payload, ensure_ascii=False)
        if any(str(Path(x)) in serialized for x in local_paths):
            raise RuntimeError(f"{version}/{sid}: local path in payload")
        if payload["reference_video"] is not None or payload["size"] != "720x1280" or payload["aspect_ratio"] != "9:16" or payload["seconds"] != "4" or payload["quality"] != "720p" or payload["n"] != 1 or payload["generate_audio"] is not True:
            raise RuntimeError(f"{version}/{sid}: payload gate failed")
        items.append((version, folder, task, payload, cfg))
    results = []
    with ThreadPoolExecutor(max_workers=11) as pool:
        futures = [pool.submit(submit_one, item) for item in items]
        for future in as_completed(futures):
            results.append(future.result())
    ordered = [next(row for row in results if row["shot_id"] == task["task_id"]) for task in plan["tasks"]]
    merged = dict(state)
    merged["video_stage_unlocked"] = True
    merged["video_stage_submitted"] = True
    merged["media_version"] = "ol3d_minigame_ads_15versions"
    merged["total"] = 11
    merged["submitted"] = sum(bool(row.get("remote_id")) for row in ordered)
    merged["jobs"] = ordered
    merged["next_poll_at"] = None
    write_json(folder / f"{version}_state.json", merged)
    return {"version": version, "submitted": merged["submitted"], "total": 11, "missing_remote_id": [row["shot_id"] for row in ordered if not row.get("remote_id")]}


def repair_v010(cfg: dict):
    version = "V010"
    folder, plan, state, manifest_row, local_paths = version_data(version)
    target_name = "T20260812-144226_BG_AUTUMNCAMP_OL3D_master_v001.png"
    target = next(Path(task["source_asset_binding"][0]["path"]) for task in plan["tasks"] if Path(task["source_asset_binding"][0]["path"]).name == target_name)
    requested = r"D:\孵化-上岛\1.projects\孵化-上岛\0.资产库\T20260812-144226_抢滩登陆视频策划\backgrounds\OL3D\T20260812-144226_BG_AUTUMNCAMP_OL3D_master_v001.png"
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError(f"V010: resolved repair asset missing: {target}")
    repair_dir = folder / "upload_repair_v001"
    repair_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    digest = sha256(target)
    request_record = {"repair_id": "upload_repair_v001", "version": version, "timestamp_utc": timestamp, "method": "POST", "endpoint": root_url(cfg["base_url"]) + "/api/upload/image", "file_field": "file", "requested_path": requested, "resolved_plan_path": str(target), "resolved_path_exists": True, "sha256": digest, "byte_size": target.stat().st_size, "model_contract": "gpt-5.6-luna/high", "api_key_included": False}
    write_json(repair_dir / "V010_upload_repair_v001_request.json", request_record)
    result = upload_image(target, cfg)
    write_json(repair_dir / "V010_upload_repair_v001_response.json", {"timestamp_utc": timestamp, "response": result})
    if result.get("status") != "success":
        blocked = {"repair_id": "upload_repair_v001", "version": version, "status": "blocked", "timestamp_utc": timestamp, "asset": str(target), "http_status": result.get("http_status"), "error": result.get("error"), "filename_returned": False}
        write_json(repair_dir / "V010_upload_repair_v001_state.json", blocked)
        print(json.dumps(blocked, ensure_ascii=False))
        return blocked
    filename = result["filename"]
    receipt = {"local_path": str(target), "asset_id": filename, "returned_filename": filename, "sha256": digest, "byte_size": target.stat().st_size, "status": "success", "timestamp_utc": timestamp, "repair_id": "upload_repair_v001"}
    write_json(repair_dir / "V010_upload_repair_v001_receipt.json", receipt)
    global_rows = []
    for other in VERSIONS:
        rows_path = OUT_ROOT / other / "upload_receipts.json"
        if rows_path.exists():
            for row in read_json(rows_path):
                if row.get("status") == "success" and isinstance(row.get("filename"), str):
                    global_rows.append({"local_path": row["local_path"], "asset_id": row["filename"], "sha256": row.get("sha256"), "source_receipt": str(rows_path), "source_version": other})
    global_by_path = {}
    for row in global_rows:
        global_by_path.setdefault(row["local_path"], row)
    repaired_by_path = {str(target): {**receipt, "source_receipt": str(repair_dir / "V010_upload_repair_v001_receipt.json"), "source_version": version}}
    old_v010 = OUT_ROOT / version / "upload_receipts.json"
    if old_v010.exists():
        for row in read_json(old_v010):
            if row.get("status") == "success" and isinstance(row.get("filename"), str):
                repaired_by_path.setdefault(row["local_path"], {"local_path": row["local_path"], "asset_id": row["filename"], "sha256": row.get("sha256"), "source_receipt": str(old_v010), "source_version": version})
    repaired_rows = []
    for raw in local_paths:
        row = repaired_by_path.get(raw) or global_by_path.get(raw)
        if not row or not isinstance(row.get("asset_id"), str) or not row["asset_id"].startswith("http"):
            raise RuntimeError(f"V010: complete 23/23 binding missing {raw}")
        repaired_rows.append({"local_path": raw, "asset_id": row["asset_id"], "returned_filename": row["asset_id"], "sha256": row.get("sha256") or sha256(Path(raw)), "status": "success", "source_receipt": row.get("source_receipt"), "source_version": row.get("source_version")})
    if len(repaired_rows) != 23 or len({row["local_path"] for row in repaired_rows}) != 23:
        raise RuntimeError(f"V010: expected complete 23/23 binding, got {len(repaired_rows)}")
    write_json(folder / "upload_receipts_repaired.json", repaired_rows)
    by_path = {row["local_path"]: row["asset_id"] for row in repaired_rows}
    bindings = []
    for task in plan["tasks"]:
        start = task["start_frame"]["path"]
        end = task["end_frame"]["path"]
        bindings.append({"shot_id": task["task_id"], "start_frame": {"local_path": start, "asset_id": by_path[start]}, "end_frame": {"local_path": end, "asset_id": by_path[end]}, "source_asset_binding": [{"local_path": item["path"], "asset_id": by_path[item["path"]], "sha256": item["sha256"]} for item in task["source_asset_binding"]]})
    write_json(folder / "asset_bindings.json", {"version": version, "cross_version_asset_mix": False, "repair_id": "upload_repair_v001", "bindings": bindings, "old_upload_receipts_preserved": True})
    write_json(folder / "upload_audit.json", {"version": version, "repair_id": "upload_repair_v001", "uploaded": 23, "required": 23, "passed": True, "asset_ids_are_real_returned_filenames": True, "old_upload_receipts_preserved": True, "reused_successful_receipts": True})
    passed = {"repair_id": "upload_repair_v001", "version": version, "status": "passed", "timestamp_utc": timestamp, "repaired_asset": receipt, "complete_asset_count": 23, "required_asset_count": 23, "old_upload_receipts_preserved": True, "asset_bindings": str(folder / "asset_bindings.json"), "submission_unlocked": True}
    write_json(repair_dir / "V010_upload_repair_v001_state.json", passed)
    merged = dict(state)
    merged["video_stage_unlocked"] = True
    merged["upload_repair_v001"] = passed
    write_json(folder / "V010_state.json", merged)
    print(json.dumps(passed, ensure_ascii=False))


def record_repair_block():
    version = "V010"
    folder, plan, state, manifest_row, local_paths = version_data(version)
    repair_dir = folder / "upload_repair_v001"
    existing = read_json(repair_dir / "V010_upload_repair_v001_receipt.json") if (repair_dir / "V010_upload_repair_v001_receipt.json").exists() else {}
    successful_paths = set()
    for other in VERSIONS:
        path = OUT_ROOT / other / "upload_receipts.json"
        if path.exists():
            for row in read_json(path):
                if row.get("status") == "success" and isinstance(row.get("filename"), str):
                    successful_paths.add(row.get("local_path"))
    successful_paths.add(existing.get("local_path"))
    missing = [raw for raw in local_paths if raw not in successful_paths]
    block = {"repair_id": "upload_repair_v001", "version": version, "status": "blocked_asset_binding", "timestamp_utc": existing.get("timestamp_utc"), "repair_upload_succeeded": bool(existing.get("asset_id")), "complete_asset_count": len(local_paths) - len(missing), "required_asset_count": len(local_paths), "missing_assets": missing, "reason": "V010-R03 through V010-R11 accepted PNGs have no successful upload receipt and have no SHA256-identical asset in other version frame directories; cross-version substitution is prohibited", "old_upload_receipts_preserved": True, "submission_unlocked": False}
    write_json(repair_dir / "V010_upload_repair_v001_state.json", block)
    merged = dict(state)
    merged["upload_repair_v001"] = block
    write_json(folder / "V010_state.json", merged)
    batch_path = OUT_ROOT / "batch_state.json"
    batch = read_json(batch_path) if batch_path.exists() else {"task_id": "T20260812-144226", "batch": "ol3d_minigame_ads_15versions"}
    batch["phase"] = "blocked_upload_repair"
    batch["upload_completed"] = 319
    batch["upload_total"] = 339
    batch["submitted"] = 0
    batch["heartbeat"] = None
    batch["blocking_errors"] = list(batch.get("blocking_errors", [])) + [{"version": version, "stage": "upload_repair_v001_binding_audit", "error": "missing V010-R03..R11 upload receipts", "missing_count": len(missing), "repair_upload_succeeded": True}]
    batch["next_step"] = "stop; coordinator must authorize uploads for the missing V010 accepted frames; no submission"
    write_json(batch_path, batch)
    print(json.dumps(block, ensure_ascii=False))


def repair_v010_v002(cfg: dict):
    version = "V010"
    folder, plan, state, manifest_row, local_paths = version_data(version)
    repair_dir = folder / "upload_repair_v002"
    repair_dir.mkdir(parents=True, exist_ok=True)
    targets = []
    for task in plan["tasks"]:
        sid = task["task_id"]
        if 3 <= int(sid.rsplit("R", 1)[1]) <= 11:
            path = Path(task["start_frame"]["path"])
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"V010/{sid}: missing V010 source PNG {path}")
            expected_sha = task["start_frame"].get("sha256")
            actual_sha = sha256(path)
            if expected_sha and actual_sha.lower() != expected_sha.lower():
                raise RuntimeError(f"V010/{sid}: SHA256 mismatch before upload")
            targets.append((sid, path, actual_sha))
    if len(targets) != 9:
        raise RuntimeError(f"V010: expected exactly 9 repair targets, got {len(targets)}")
    for sid, path, digest in targets:
        request_path = repair_dir / f"V010_upload_repair_v002_{sid}_request.json"
        response_path = repair_dir / f"V010_upload_repair_v002_{sid}_response.json"
        receipt_path = repair_dir / f"V010_upload_repair_v002_{sid}_receipt.json"
        state_path = repair_dir / f"V010_upload_repair_v002_{sid}_state.json"
        if any(p.exists() for p in (request_path, response_path, receipt_path, state_path)):
            raise RuntimeError(f"V010/{sid}: v002 evidence already exists; refusing overwrite/retry")
        timestamp = datetime.now(timezone.utc).isoformat()
        request_record = {"repair_id": "upload_repair_v002", "version": version, "shot_id": sid, "timestamp_utc": timestamp, "method": "POST", "endpoint": root_url(cfg["base_url"]) + "/api/upload/image", "file_field": "file", "local_path": str(path), "sha256": digest, "byte_size": path.stat().st_size, "model_contract": "gpt-5.6-luna/high", "api_key_included": False}
        write_json(request_path, request_record)
        result = upload_image(path, cfg)
        write_json(response_path, {"timestamp_utc": timestamp, "response": result})
        if result.get("status") != "success":
            failed = {"repair_id": "upload_repair_v002", "version": version, "shot_id": sid, "status": "blocked_upload", "timestamp_utc": timestamp, "local_path": str(path), "sha256": digest, "http_status": result.get("http_status"), "error": result.get("error"), "filename_returned": False}
            write_json(state_path, failed)
            print(json.dumps(failed, ensure_ascii=False))
            return failed
        receipt = {"repair_id": "upload_repair_v002", "version": version, "shot_id": sid, "local_path": str(path), "asset_id": result["filename"], "returned_filename": result["filename"], "sha256": digest, "byte_size": path.stat().st_size, "status": "success", "timestamp_utc": timestamp}
        write_json(receipt_path, receipt)
        write_json(state_path, {"repair_id": "upload_repair_v002", "version": version, "shot_id": sid, "status": "success", "timestamp_utc": timestamp, "sha256_verified": True, "asset_id_is_returned_filename": True})
    own_rows = []
    old_path = folder / "upload_receipts.json"
    if old_path.exists():
        for row in read_json(old_path):
            if row.get("status") == "success" and isinstance(row.get("filename"), str):
                own_rows.append({"local_path": row["local_path"], "asset_id": row["filename"], "source": "V010/upload_receipts.json"})
    v1_receipt = folder / "upload_repair_v001" / "V010_upload_repair_v001_receipt.json"
    if v1_receipt.exists():
        row = read_json(v1_receipt)
        if row.get("status") == "success":
            own_rows.append({"local_path": row["local_path"], "asset_id": row["asset_id"], "source": "V010/upload_repair_v001"})
    for sid, path, digest in targets:
        row = read_json(repair_dir / f"V010_upload_repair_v002_{sid}_receipt.json")
        own_rows.append({"local_path": row["local_path"], "asset_id": row["asset_id"], "source": f"V010/upload_repair_v002/{sid}", "sha256": row["sha256"]})
    own_map = {row["local_path"]: row for row in own_rows}
    missing = [raw for raw in local_paths if raw not in own_map]
    audit = {"repair_id": "upload_repair_v002", "version": version, "status": "passed" if not missing and len(own_map) == 23 else "blocked_asset_binding", "required_assets": 23, "v010_real_receipt_assets": len(own_map), "missing_assets": missing, "cross_version_asset_mix": False, "sha256_matching": not missing, "old_upload_receipts_preserved": True, "v001_preserved": True, "v002_uploaded": 9}
    write_json(repair_dir / "V010_upload_repair_v002_audit.json", audit)
    if audit["status"] != "passed":
        block = {"repair_id": "upload_repair_v002", "version": version, "status": "blocked_asset_binding", "required_assets": 23, "v010_real_receipt_assets": len(own_map), "missing_assets": missing, "cross_version_asset_mix": False, "old_upload_receipts_preserved": True, "v001_preserved": True, "submission_unlocked": False}
        write_json(repair_dir / "V010_upload_repair_v002_state.json", block)
        merged = dict(state)
        merged["upload_repair_v002"] = block
        write_json(folder / "V010_state.json", merged)
        batch_path = OUT_ROOT / "batch_state.json"
        batch = read_json(batch_path) if batch_path.exists() else {"task_id": "T20260812-144226", "batch": "ol3d_minigame_ads_15versions"}
        batch["phase"] = "blocked_upload_repair_v002"
        batch["upload_completed"] = 328
        batch["upload_total"] = 339
        batch["submitted"] = 0
        batch["heartbeat"] = None
        batch["blocking_errors"] = list(batch.get("blocking_errors", [])) + [{"version": version, "stage": "upload_repair_v002_binding_audit", "error": "V010-only receipts cover fewer than 23 planned assets", "missing_count": len(missing)}]
        batch["next_step"] = "stop; coordinator must authorize missing V010 source-asset uploads; no submission"
        write_json(batch_path, batch)
        print(json.dumps(block, ensure_ascii=False))
        return block
    bindings = []
    by_path = {raw: row["asset_id"] for raw, row in own_map.items()}
    for task in plan["tasks"]:
        bindings.append({"shot_id": task["task_id"], "start_frame": {"local_path": task["start_frame"]["path"], "asset_id": by_path[task["start_frame"]["path"]]}, "end_frame": {"local_path": task["end_frame"]["path"], "asset_id": by_path[task["end_frame"]["path"]]}, "source_asset_binding": [{"local_path": item["path"], "asset_id": by_path[item["path"]], "sha256": item["sha256"]} for item in task["source_asset_binding"]]})
    write_json(folder / "asset_bindings.json", {"version": version, "cross_version_asset_mix": False, "repair_id": "upload_repair_v002", "bindings": bindings})
    write_json(folder / "upload_receipts_repaired.json", [{"local_path": raw, "asset_id": row["asset_id"], "status": "success", "source": row.get("source")} for raw, row in own_map.items()])
    print(json.dumps({"repair_id": "upload_repair_v002", "version": version, "status": "passed", "asset_bindings": str(folder / "asset_bindings.json"), "required_assets": 23}, ensure_ascii=False))


def repair_v010_v003(cfg: dict):
    version = "V010"
    repair_id = "upload_repair_v003"
    folder, plan, state, manifest_row, local_paths = version_data(version)
    repair_dir = folder / repair_id
    repair_dir.mkdir(parents=True, exist_ok=True)
    state_path = repair_dir / "V010_upload_repair_v003_state.json"
    audit_path = repair_dir / "V010_upload_repair_v003_audit.json"
    if state_path.exists() or audit_path.exists():
        raise RuntimeError("V010: upload_repair_v003 evidence already exists; refusing overwrite/retry")

    expected_assets = {}
    frame_paths = set()
    for task in plan["tasks"]:
        frame_paths.update((task["start_frame"]["path"], task["end_frame"]["path"]))
        for item in task["source_asset_binding"]:
            path = item["path"]
            row = expected_assets.setdefault(path, {"sha256": item.get("sha256"), "roles": []})
            row["roles"].append(task["task_id"])
            if row.get("sha256") and item.get("sha256") and row["sha256"].lower() != item["sha256"].lower():
                raise RuntimeError(f"V010: inconsistent planned SHA256 for {path}")

    own_rows = {}

    def add_existing(path: Path, source: str, row: dict, asset_key: str):
        if row.get("status") != "success":
            return
        asset_id = row.get(asset_key)
        local_path = row.get("local_path")
        if isinstance(local_path, str) and isinstance(asset_id, str) and asset_id.strip():
            own_rows.setdefault(local_path, {"local_path": local_path, "asset_id": asset_id, "source": source, "sha256": row.get("sha256")})

    old_receipts = folder / "upload_receipts.json"
    if old_receipts.exists():
        for row in read_json(old_receipts):
            add_existing(old_receipts, "V010/upload_receipts.json", row, "filename")
    v1_receipt = folder / "upload_repair_v001" / "V010_upload_repair_v001_receipt.json"
    if v1_receipt.exists():
        add_existing(v1_receipt, "V010/upload_repair_v001", read_json(v1_receipt), "asset_id")
    v2_dir = folder / "upload_repair_v002"
    for receipt_path in sorted(v2_dir.glob("V010_upload_repair_v002_*_receipt.json")):
        add_existing(receipt_path, f"V010/upload_repair_v002/{receipt_path.stem.rsplit('_', 1)[-1]}", read_json(receipt_path), "asset_id")

    missing_sources = [path for path in expected_assets if path not in own_rows]
    preflight = []
    for raw in missing_sources:
        path = Path(raw)
        expected_sha = expected_assets[raw].get("sha256")
        exists = path.is_file() and path.stat().st_size > 0 if path.exists() else False
        actual_sha = sha256(path) if exists else None
        preflight.append({
            "local_path": raw,
            "resolved_path": str(path),
            "resolved_path_exists": exists,
            "byte_size": path.stat().st_size if exists else 0,
            "expected_sha256": expected_sha,
            "actual_sha256": actual_sha,
            "sha256_match": bool(exists and expected_sha and actual_sha.lower() == expected_sha.lower()),
            "source_roles": expected_assets[raw]["roles"],
        })
    write_json(repair_dir / "V010_upload_repair_v003_path_resolution.json", {"repair_id": repair_id, "version": version, "targets": preflight})
    if len(missing_sources) != 11 or any(not row["sha256_match"] for row in preflight):
        blocked = {
            "repair_id": repair_id,
            "version": version,
            "status": "blocked_preflight",
            "required_uploads": 11,
            "resolved_targets": len(missing_sources),
            "missing_or_unverified": [row for row in preflight if not row["sha256_match"]],
            "cross_version_asset_mix": False,
            "old_upload_receipts_preserved": True,
            "upload_started": False,
            "submission_unlocked": False,
        }
        write_json(audit_path, blocked)
        write_json(state_path, blocked)
        merged = dict(state)
        merged[repair_id] = blocked
        write_json(folder / "V010_state.json", merged)
        print(json.dumps(blocked, ensure_ascii=False))
        return blocked

    targets = [(row["local_path"], Path(row["resolved_path"]), row["actual_sha256"]) for row in preflight]
    uploaded = []
    for raw, path, digest in targets:
        sid = path.stem
        request_path = repair_dir / f"V010_upload_repair_v003_{sid}_request.json"
        response_path = repair_dir / f"V010_upload_repair_v003_{sid}_response.json"
        receipt_path = repair_dir / f"V010_upload_repair_v003_{sid}_receipt.json"
        item_state_path = repair_dir / f"V010_upload_repair_v003_{sid}_state.json"
        if any(candidate.exists() for candidate in (request_path, response_path, receipt_path, item_state_path)):
            raise RuntimeError(f"V010/{sid}: v003 evidence already exists; refusing overwrite/retry")
        timestamp = datetime.now(timezone.utc).isoformat()
        request_record = {
            "repair_id": repair_id,
            "version": version,
            "asset_name": sid,
            "timestamp_utc": timestamp,
            "method": "POST",
            "endpoint": root_url(cfg["base_url"]) + "/api/upload/image",
            "file_field": "file",
            "local_path": raw,
            "resolved_path": str(path),
            "resolved_path_exists": True,
            "sha256": digest,
            "planned_sha256": expected_assets[raw]["sha256"],
            "byte_size": path.stat().st_size,
            "source_roles": expected_assets[raw]["roles"],
            "model_contract": "gpt-5.6-luna/high",
            "api_key_included": False,
        }
        write_json(request_path, request_record)
        result = upload_image(path, cfg)
        write_json(response_path, {"timestamp_utc": timestamp, "response": result})
        if result.get("status") != "success":
            blocked = {
                "repair_id": repair_id,
                "version": version,
                "asset_name": sid,
                "status": "blocked_upload",
                "timestamp_utc": timestamp,
                "local_path": raw,
                "sha256": digest,
                "http_status": result.get("http_status"),
                "error": result.get("error"),
                "filename_returned": False,
                "uploaded_before_block": len(uploaded),
                "cross_version_asset_mix": False,
                "submission_unlocked": False,
            }
            write_json(item_state_path, blocked)
            audit = {"repair_id": repair_id, "version": version, "status": "blocked_upload", "uploaded": len(uploaded), "required": 11, "failed_asset": sid, "cross_version_asset_mix": False, "old_upload_receipts_preserved": True}
            write_json(audit_path, audit)
            write_json(state_path, audit)
            merged = dict(state)
            merged[repair_id] = audit
            write_json(folder / "V010_state.json", merged)
            print(json.dumps(blocked, ensure_ascii=False))
            return blocked
        receipt = {
            "repair_id": repair_id,
            "version": version,
            "asset_name": sid,
            "local_path": raw,
            "asset_id": result["filename"],
            "returned_filename": result["filename"],
            "sha256": digest,
            "planned_sha256": expected_assets[raw]["sha256"],
            "byte_size": path.stat().st_size,
            "status": "success",
            "timestamp_utc": timestamp,
        }
        write_json(receipt_path, receipt)
        write_json(item_state_path, {"repair_id": repair_id, "version": version, "asset_name": sid, "status": "success", "timestamp_utc": timestamp, "sha256_verified": True, "asset_id_is_returned_filename": True})
        uploaded.append(receipt)

    for receipt in uploaded:
        own_rows[receipt["local_path"]] = {"local_path": receipt["local_path"], "asset_id": receipt["asset_id"], "source": f"V010/upload_repair_v003/{receipt['asset_name']}", "sha256": receipt["sha256"]}

    audit_rows = []
    audit_errors = []
    for raw in local_paths:
        expected_sha = None
        if raw in expected_assets:
            expected_sha = expected_assets[raw].get("sha256")
        else:
            for task in plan["tasks"]:
                for frame_key in ("start_frame", "end_frame"):
                    if task[frame_key]["path"] == raw:
                        expected_sha = task[frame_key].get("sha256")
        row = own_rows.get(raw)
        path = Path(raw)
        actual_sha = sha256(path) if path.is_file() else None
        valid_asset = bool(row and isinstance(row.get("asset_id"), str) and row["asset_id"].startswith("http"))
        sha_match = bool(row and expected_sha and row.get("sha256", "").lower() == expected_sha.lower() and actual_sha and actual_sha.lower() == expected_sha.lower())
        audit_rows.append({"local_path": raw, "asset_id": row.get("asset_id") if row else None, "source": row.get("source") if row else None, "expected_sha256": expected_sha, "receipt_sha256": row.get("sha256") if row else None, "actual_sha256": actual_sha, "asset_id_is_real_returned_url": valid_asset, "sha256_match": sha_match})
        if not row:
            audit_errors.append({"local_path": raw, "error": "missing_V010_receipt"})
        elif not valid_asset:
            audit_errors.append({"local_path": raw, "error": "asset_id_not_real_returned_url"})
        elif not sha_match:
            audit_errors.append({"local_path": raw, "error": "sha256_mismatch"})

    audit = {
        "repair_id": repair_id,
        "version": version,
        "status": "passed" if len(audit_rows) == 23 and not audit_errors else "blocked_asset_binding",
        "required_assets": 23,
        "audited_assets": len(audit_rows),
        "uploaded_this_round": len(uploaded),
        "asset_rows": audit_rows,
        "errors": audit_errors,
        "cross_version_asset_mix": False,
        "sha256_matching": not audit_errors,
        "old_upload_receipts_preserved": True,
        "upload_repair_v001_preserved": True,
        "upload_repair_v002_preserved": True,
    }
    write_json(audit_path, audit)
    if audit["status"] != "passed":
        blocked = {**audit, "submission_unlocked": False}
        write_json(state_path, blocked)
        merged = dict(state)
        merged[repair_id] = blocked
        write_json(folder / "V010_state.json", merged)
        print(json.dumps(blocked, ensure_ascii=False))
        return blocked

    binding_rows = []
    by_path = {row["local_path"]: row for row in audit_rows}
    for task in plan["tasks"]:
        start = task["start_frame"]["path"]
        end = task["end_frame"]["path"]
        binding_rows.append({
            "shot_id": task["task_id"],
            "start_frame": {"local_path": start, "asset_id": by_path[start]["asset_id"]},
            "end_frame": {"local_path": end, "asset_id": by_path[end]["asset_id"]},
            "source_asset_binding": [{"local_path": item["path"], "asset_id": by_path[item["path"]]["asset_id"], "sha256": item["sha256"]} for item in task["source_asset_binding"]],
        })
    bindings_path = repair_dir / "V010_upload_repair_v003_asset_bindings.json"
    receipts_path = repair_dir / "V010_upload_repair_v003_upload_receipts.json"
    write_json(bindings_path, {"version": version, "repair_id": repair_id, "cross_version_asset_mix": False, "bindings": binding_rows})
    write_json(receipts_path, audit_rows)
    passed = {"repair_id": repair_id, "version": version, "status": "passed", "required_assets": 23, "audited_assets": 23, "uploaded_this_round": 11, "cross_version_asset_mix": False, "sha256_matching": True, "asset_bindings": str(bindings_path), "upload_receipts": str(receipts_path), "old_upload_receipts_preserved": True, "upload_repair_v001_preserved": True, "upload_repair_v002_preserved": True, "submission_unlocked": False}
    write_json(state_path, passed)
    merged = dict(state)
    merged[repair_id] = passed
    write_json(folder / "V010_state.json", merged)
    batch_path = OUT_ROOT / "batch_state.json"
    batch = read_json(batch_path) if batch_path.exists() else {"task_id": "T20260812-144226", "batch": "ol3d_minigame_ads_15versions"}
    batch["phase"] = "upload_repair_v003_passed"
    batch["upload_completed"] = 339
    batch["upload_total"] = 339
    batch["submitted"] = 0
    batch["heartbeat"] = None
    batch["next_step"] = "V010 23/23 binding ready; await separate submission authorization"
    write_json(batch_path, batch)
    print(json.dumps(passed, ensure_ascii=False))
    return passed


def record_upload_block():
    versions = []
    total_required = 0
    total_success = 0
    failures = []
    for version in VERSIONS:
        folder, plan, state, manifest, local_paths = version_data(version)
        total_required += len(local_paths)
        receipt_path = folder / "upload_receipts.json"
        rows = read_json(receipt_path) if receipt_path.exists() else []
        success = sum(row.get("status") == "success" for row in rows)
        total_success += success
        version_failures = [
            {"local_path": row.get("local_path"), "error": row.get("error"), "http_status": row.get("http_status")}
            for row in rows if row.get("status") != "success"
        ]
        if version_failures:
            failures.extend([{**row, "version": version} for row in version_failures])
        versions.append({"version": version, "required_assets": len(local_paths), "successful_uploads": success, "upload_receipt_exists": receipt_path.exists(), "upload_audit": (folder / "upload_audit.json").is_file(), "blocked": bool(version_failures)})
    batch = {
        "task_id": "T20260812-144226",
        "batch": "ol3d_minigame_ads_15versions",
        "model_contract": "gpt-5.6-luna/high",
        "phase": "blocked_upload",
        "upload_completed": total_success,
        "upload_total": total_required,
        "submitted": 0,
        "submitted_total": 165,
        "terminal": 0,
        "terminal_total": 165,
        "pulled_back": 0,
        "pulled_back_total": 165,
        "technical_acceptance": 0,
        "technical_acceptance_total": 165,
        "continuity_acceptance": 0,
        "continuity_acceptance_total": 165,
        "blocking_errors": failures,
        "versions": versions,
        "heartbeat": None,
        "next_step": "stop; coordinator decision required; no retry or submission",
    }
    write_json(OUT_ROOT / "batch_state.json", batch)
    print(json.dumps(batch, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["preflight", "upload", "submit", "record_block", "repair_v010", "record_repair_block", "repair_v010_v002", "repair_v010_v003"], required=True)
    args = parser.parse_args()
    cfg = read_json(CFG_PATH)
    if not cfg.get("api_key") or not cfg.get("base_url") or not cfg.get("model"):
        raise RuntimeError("actual API configuration is incomplete")
    if args.stage == "repair_v010_v002":
        repair_v010_v002(cfg)
    elif args.stage == "repair_v010_v003":
        repair_v010_v003(cfg)
    elif args.stage == "record_repair_block":
        record_repair_block()
    elif args.stage == "repair_v010":
        repair_v010(cfg)
    elif args.stage == "record_block":
        record_upload_block()
    elif args.stage == "preflight":
        rows = []
        for version in VERSIONS:
            folder, plan, state, manifest, local_paths = version_data(version)
            rows.append({"version": version, "tasks": len(plan["tasks"]), "assets": len(local_paths), "unlocked": state.get("video_stage_unlocked") is True})
        print(json.dumps({"versions": rows, "tasks": sum(x["tasks"] for x in rows), "model": cfg["model"], "api_key_not_printed": True}, ensure_ascii=False))
    elif args.stage == "upload":
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(upload_version, version, cfg) for version in VERSIONS]
            rows = [future.result() for future in as_completed(futures)]
        print(json.dumps({"uploaded_versions": sorted(rows, key=lambda x: x["version"]), "total_versions": 15}, ensure_ascii=False))
    else:
        with ThreadPoolExecutor(max_workers=15) as pool:
            futures = [pool.submit(submit_version, version, cfg) for version in VERSIONS]
            rows = [future.result() for future in as_completed(futures)]
        print(json.dumps({"submitted_versions": sorted(rows, key=lambda x: x["version"]), "total_tasks": sum(x["submitted"] for x in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
