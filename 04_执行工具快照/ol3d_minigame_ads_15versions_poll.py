from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(r"D:\孵化-上岛\1.projects\孵化-上岛")
OUT_ROOT = ROOT / r"6.生成结果\T20260812-144226\ol3d_minigame_ads_15versions"
CFG_PATH = Path(r"D:\孵化-上岛\4.apis\seedance\api_config2.json")
VERSIONS = [f"V{i:03d}" for i in range(1, 16)]
SUCCESS = {"completed", "succeeded", "success", "done"}
FAILED = {"failed", "error", "cancelled", "canceled", "submit_failed"}
TERMINAL = SUCCESS | FAILED


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def poll(remote_id, cfg):
    request = Request(
        cfg["base_url"].rstrip("/") + "/videos/" + remote_id,
        method="GET",
        headers={"Authorization": "Bearer " + cfg["api_key"], "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status_code = response.status
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return None, exc.code, "http_error: " + raw[:1000]
    except (URLError, TimeoutError, OSError) as exc:
        return None, None, type(exc).__name__ + ": " + str(exc)
    try:
        return json.loads(raw), status_code, None
    except json.JSONDecodeError:
        return None, status_code, "non_json_response: " + raw[:1000]


def sanitize_response(data):
    allowed = {"id", "object", "model", "status", "progress", "completed_at", "expires_at", "error", "video_url", "vendor_task_id", "vendor_provider", "vendor_account_id", "params"}
    result = {key: data[key] for key in allowed if key in data}
    params = data.get("params")
    if isinstance(params, dict):
        param_keys = {"quality", "duration", "generate_audio", "size", "resolution", "aspect_ratio", "video_mode", "generation_mode", "input_image_count", "input_video_count", "input_audio_count", "count"}
        result["params"] = {key: params[key] for key in param_keys if key in params}
    return result


def main():
    cfg = read_json(CFG_PATH)
    batch_path = OUT_ROOT / "batch_state.json"
    batch = read_json(batch_path)
    if batch.get("model_contract") != "gpt-5.6-luna/high":
        raise RuntimeError("Chat model contract mismatch")
    if not cfg.get("model") or not cfg.get("base_url") or not cfg.get("api_key"):
        raise RuntimeError("Seedance API configuration is incomplete")
    loaded = []
    jobs = []
    for version in VERSIONS:
        path = OUT_ROOT / version / f"{version}_state.json"
        state = read_json(path)
        loaded.append((version, path, state))
        for index, job in enumerate(state.get("jobs", [])):
            remote_id = job.get("remote_id")
            if isinstance(remote_id, str) and remote_id:
                jobs.append((version, index, remote_id))
    ids = [remote_id for _, _, remote_id in jobs]
    if len(ids) != 165 or len(set(ids)) != 165:
        raise RuntimeError(f"saved remote_id gate failed: {len(ids)} IDs, {len(set(ids))} unique")

    with ThreadPoolExecutor(max_workers=165) as pool:
        results = list(pool.map(lambda item: (*item[:2], *poll(item[2], cfg)), jobs))
    by_job = {(version, index): (data, status_code, error) for version, index, data, status_code, error in results}
    now = datetime.now().astimezone()
    next_poll = (now + timedelta(seconds=120)).isoformat(timespec="seconds")
    batch_success = batch_failed = batch_terminal = 0
    version_summary = []
    for version, path, state in loaded:
        state_jobs = state.get("jobs", [])
        for index, job in enumerate(state_jobs):
            data, status_code, error = by_job[(version, index)]
            if error:
                job["poll_error"] = error
                job["poll_http_status"] = status_code
                continue
            remote_status = str(data.get("status", "unknown")).lower()
            job["status"] = "success" if remote_status in SUCCESS else "failed" if remote_status in FAILED else remote_status
            job["remote_status"] = remote_status
            job["poll_http_status"] = status_code
            job["remote_response"] = sanitize_response(data)
            if isinstance(data.get("video_url"), str) and data["video_url"]:
                job["video_url"] = data["video_url"]
            if data.get("error") is not None:
                job["error"] = data["error"]
        success = sum(job.get("status") == "success" for job in state_jobs)
        failed = sum(job.get("status") == "failed" for job in state_jobs)
        terminal = success + failed
        state["success"] = success
        state["failed"] = failed
        state["terminal"] = terminal == state.get("total", len(state_jobs))
        state["last_polled_at"] = now.isoformat(timespec="seconds")
        state["next_poll_at"] = None if state["terminal"] else next_poll
        write_json(path, state)
        batch_success += success
        batch_failed += failed
        batch_terminal += terminal
        version_summary.append({"version": version, "success": success, "failed": failed, "terminal": terminal, "total": len(state_jobs)})

    batch["phase"] = "all_terminal_waiting_pullback" if batch_terminal == 165 else "monitoring"
    batch["terminal"] = batch_terminal
    batch["terminal_total"] = 165
    batch["success"] = batch_success
    batch["failed"] = batch_failed
    batch["next_poll_at"] = None if batch_terminal == 165 else next_poll
    batch["versions"] = version_summary
    write_json(batch_path, batch)
    print(json.dumps({"terminal": batch_terminal, "success": batch_success, "failed": batch_failed, "next_poll_at": batch["next_poll_at"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
