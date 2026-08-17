import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import threading

import ol3d_minigame_ads_15versions_media as media


MODEL_CONTRACT = "gpt-5.6-luna/high"
SUBMIT_STOP = threading.Event()


def load_submission_contract(version):
    folder, plan, state, manifest, local_paths = media.version_data(version)
    if state.get("video_stage_submitted") is True:
        raise RuntimeError(f"{version}: state already submitted")
    if version == "V010":
        repair_dir = folder / "upload_repair_v003"
        audit_path = repair_dir / "V010_upload_repair_v003_audit.json"
        bindings_path = repair_dir / "V010_upload_repair_v003_asset_bindings.json"
        receipts_path = repair_dir / "V010_upload_repair_v003_upload_receipts.json"
        audit = media.read_json(audit_path) if audit_path.is_file() else {}
        if audit.get("status") != "passed" or audit.get("audited_assets") != 23 or audit.get("cross_version_asset_mix") is not False or audit.get("sha256_matching") is not True:
            raise RuntimeError(f"{version}: upload_repair_v003 audit is not passed")
        if state.get("upload_repair_v003", {}).get("status") != "passed":
            raise RuntimeError(f"{version}: upload_repair_v003 state is not passed")
    else:
        audit_path = folder / "upload_audit.json"
        bindings_path = folder / "asset_bindings.json"
        receipts_path = folder / "upload_receipts_repaired.json" if (folder / "upload_receipts_repaired.json").exists() else folder / "upload_receipts.json"
        audit = media.read_json(audit_path) if audit_path.is_file() else {}
        if not audit.get("passed"):
            raise RuntimeError(f"{version}: upload audit is not passed")
    if not bindings_path.is_file() or not receipts_path.is_file():
        raise RuntimeError(f"{version}: binding or receipt file missing")
    binding_doc = media.read_json(bindings_path)
    bindings = binding_doc.get("bindings")
    if not isinstance(bindings, list) or len(bindings) != 11 or binding_doc.get("cross_version_asset_mix") is not False:
        raise RuntimeError(f"{version}: binding completeness/isolation failed")
    binding_map = {row.get("shot_id"): row for row in bindings}
    receipts = media.read_json(receipts_path)
    if version == "V010":
        returned = {row.get("local_path"): row.get("asset_id") for row in receipts if isinstance(row.get("asset_id"), str)}
        if len(returned) != 23 or any(row.get("asset_id_is_real_returned_url") is not True or row.get("sha256_match") is not True for row in receipts):
            raise RuntimeError(f"{version}: v003 audited receipt rows are invalid")
    else:
        returned = {row.get("local_path"): row.get("filename") for row in receipts if row.get("status") == "success"}
    if len(returned) != len(receipts) or any(not isinstance(asset_id, str) or not asset_id.startswith("http") for asset_id in returned.values()):
        raise RuntimeError(f"{version}: receipt mapping is invalid")

    items = []
    expected_ids = [f"{version}-R{i:02d}" for i in range(1, 12)]
    if set(binding_map) != set(expected_ids):
        raise RuntimeError(f"{version}: shot_id set is not exactly R01-R11")
    for task in plan["tasks"]:
        sid = task["task_id"]
        response_path = folder / f"{sid}_submit_response.json"
        if response_path.exists():
            raise RuntimeError(f"{version}/{sid}: existing submit response; refusing duplicate")
        binding = binding_map[sid]
        binding_items = [binding["start_frame"], binding["end_frame"]] + binding.get("source_asset_binding", [])
        for item in binding_items:
            asset_id = item.get("asset_id")
            if not isinstance(asset_id, str) or not asset_id.startswith("http"):
                raise RuntimeError(f"{version}/{sid}: binding contains non-URL asset_id")
            local_path = item.get("local_path")
            if local_path not in returned or returned[local_path] != asset_id:
                raise RuntimeError(f"{version}/{sid}: binding does not match its own upload receipt")
        start = binding["start_frame"]["asset_id"]
        end = binding["end_frame"]["asset_id"]
        refs = [start] if start == end else [start, end]
        payload = {
            "model": media.read_json(media.CFG_PATH)["model"],
            "prompt": task["prompt"],
            "n": 1,
            "size": "720x1280",
            "seconds": "4",
            "aspect_ratio": "9:16",
            "quality": "720p",
            "generate_audio": True,
            "external_tts_blocked": True,
            "input_reference": refs,
            "first_frame": start,
            "last_frame": end,
            "reference_video": None,
        }
        serialized = json.dumps(payload, ensure_ascii=False)
        if any(str(Path(local_path)) in serialized for local_path in local_paths):
            raise RuntimeError(f"{version}/{sid}: local path entered payload")
        if payload["size"] != "720x1280" or payload["aspect_ratio"] != "9:16" or payload["seconds"] != "4" or payload["quality"] != "720p" or payload["n"] != 1 or payload["generate_audio"] is not True or payload["reference_video"] is not None:
            raise RuntimeError(f"{version}/{sid}: payload gate failed")
        snapshot_path = folder / f"{sid}_payload_snapshot.json"
        if snapshot_path.exists():
            if media.read_json(snapshot_path) != payload:
                raise RuntimeError(f"{version}/{sid}: existing payload snapshot differs")
        else:
            media.write_json(snapshot_path, payload)
        items.append((version, folder, task, payload, media.read_json(media.CFG_PATH)))
    return {"version": version, "folder": folder, "state": state, "items": items, "audit": audit}


def submit_one(item):
    version, folder, task, payload, cfg = item
    sid = task["task_id"]
    result, status_code, error = media.json_request("POST", cfg["base_url"].rstrip("/") + "/videos", cfg, payload)
    if result is None:
        result = {"error": error}
    media.write_json(folder / f"{sid}_submit_response.json", {"http_status": status_code, "response": result})
    remote_id = result.get("id") if isinstance(result, dict) else None
    remote_id = remote_id if isinstance(remote_id, str) and remote_id else None
    response_status = result.get("status", "submit_failed") if isinstance(result, dict) else "submit_failed"
    failed_status = str(response_status).lower() in {"failed", "error", "submit_failed"}
    submission_error = error or ("missing_remote_id" if not remote_id else None) or ("remote_response_failed" if failed_status else None)
    if submission_error:
        SUBMIT_STOP.set()
    return {
        "shot_id": sid,
        "remote_id": None if submission_error else remote_id,
        "status": response_status,
        "http_status": status_code,
        "error": submission_error,
        "reference_video": None,
        "input_reference_count": len(payload["input_reference"]),
    }


def submit_contract(contract):
    version = contract["version"]
    folder = contract["folder"]
    state = contract["state"]
    plan_tasks = [item[2] for item in contract["items"]]
    results = []
    with ThreadPoolExecutor(max_workers=11) as pool:
        futures = [pool.submit(submit_one, item) for item in contract["items"]]
        for future in as_completed(futures):
            results.append(future.result())
    ordered = [next(row for row in results if row["shot_id"] == task["task_id"]) for task in plan_tasks]
    submitted = sum(bool(row.get("remote_id")) for row in ordered)
    merged = dict(state)
    merged["video_stage_submitted"] = submitted == 11
    merged["media_version"] = "ol3d_minigame_ads_15versions"
    merged["total"] = 11
    merged["submitted"] = submitted
    merged["submission_errors"] = [row for row in ordered if row.get("error") or not row.get("remote_id")]
    merged["jobs"] = ordered
    merged["next_poll_at"] = None
    media.write_json(folder / f"{version}_state.json", merged)
    return {"version": version, "submitted": submitted, "total": 11, "jobs": ordered, "errors": merged["submission_errors"]}


def main():
    cfg = media.read_json(media.CFG_PATH)
    if not cfg.get("api_key") or not cfg.get("base_url") or not cfg.get("model"):
        raise RuntimeError("API configuration is incomplete")
    root = media.OUT_ROOT
    preflight_path = root / "submission_preflight.json"
    if preflight_path.exists():
        raise RuntimeError("submission_preflight.json already exists; refusing duplicate submission")
    contracts = [load_submission_contract(version) for version in media.VERSIONS]
    preflight = {
        "batch": "ol3d_minigame_ads_15versions",
        "task_id": "T20260812-144226",
        "model_contract": MODEL_CONTRACT,
        "versions": [{"version": c["version"], "tasks": len(c["items"]), "upload_audit_passed": True} for c in contracts],
        "tasks": sum(len(c["items"]) for c in contracts),
        "submission_authorized": True,
        "remote_ids_before_submit": 0,
    }
    if preflight["tasks"] != 165:
        raise RuntimeError(f"expected 165 tasks, got {preflight['tasks']}")
    media.write_json(preflight_path, preflight)

    results = []
    for contract in contracts:
        result = submit_contract(contract)
        results.append(result)
        if result["errors"]:
            batch = media.read_json(root / "batch_state.json") if (root / "batch_state.json").exists() else {}
            batch.update({"phase": "blocked_submit", "submitted": sum(row["submitted"] for row in results), "submitted_total": 165, "heartbeat": None, "next_step": "stop; structured error returned; no heartbeat"})
            batch["submission_errors"] = [error for row in results for error in row["errors"]]
            media.write_json(root / "batch_state.json", batch)
            print(json.dumps({"status": "blocked_submit", "submitted": batch["submitted"], "total": 165, "errors": batch["submission_errors"]}, ensure_ascii=False))
            return 2
    remote_ids = [job["remote_id"] for result in results for job in result["jobs"] if job.get("remote_id")]
    if len(remote_ids) != 165 or len(set(remote_ids)) != 165:
        raise RuntimeError(f"remote_id gate failed: {len(remote_ids)} IDs, {len(set(remote_ids))} unique")
    batch = media.read_json(root / "batch_state.json") if (root / "batch_state.json").exists() else {}
    batch.update({"phase": "submitted_waiting_heartbeat", "submitted": 165, "submitted_total": 165, "remote_ids": remote_ids, "heartbeat": None, "next_step": "create unique 120-second heartbeat; query only saved IDs"})
    batch["versions"] = [{"version": result["version"], "submitted": result["submitted"], "total": result["total"]} for result in results]
    media.write_json(root / "batch_state.json", batch)
    print(json.dumps({"status": "submitted", "submitted": 165, "unique_remote_ids": 165, "state_root": str(root), "heartbeat_required": True}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
