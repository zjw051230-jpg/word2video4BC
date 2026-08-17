from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from urllib.request import Request, urlopen


PROJECT = Path(__file__).resolve().parent
OUT_ROOT = PROJECT / r"6.生成结果\T20260812-144226\ol3d_minigame_ads_15versions"
VERSIONS = [f"V{i:03d}" for i in range(1, 16)]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_json(command):
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else None
    except json.JSONDecodeError:
        data = None
    return result.returncode, data, result.stderr[-2000:]


def ffprobe(path):
    return run_json(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)])


def download(url, destination):
    if destination.is_file() and destination.stat().st_size > 0:
        return {"status": "existing", "bytes": destination.stat().st_size, "sha256": sha256(destination)}
    temporary = destination.with_suffix(destination.suffix + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, method="GET", headers={"Accept": "video/mp4"})
    with urlopen(request, timeout=600) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output, 1024 * 1024)
    if not temporary.is_file() or temporary.stat().st_size == 0:
        raise RuntimeError("empty downloaded video")
    temporary.replace(destination)
    return {"status": "downloaded", "bytes": destination.stat().st_size, "sha256": sha256(destination)}


def extract_five_frames(video_path, frame_dir, duration):
    frame_dir.mkdir(parents=True, exist_ok=True)
    points = [("00", 0.0), ("25", 0.25), ("50", 0.5), ("75", 0.75), ("100", 1.0)]
    rows = []
    for label, fraction in points:
        # Keep the final seek safely inside the encoded timeline. A seek at
        # duration - 0.05 can miss the last decodable frame on short clips.
        timestamp = 0.0 if fraction == 0 else max(0.0, duration * fraction - (0.15 if fraction == 1.0 else 0.0))
        target = frame_dir / f"frame_{label}.png"
        result = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{timestamp:.3f}", "-i", str(video_path), "-frames:v", "1", str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        rows.append({"label": label, "timestamp_sec": timestamp, "path": str(target), "exists": target.is_file() and target.stat().st_size > 0, "stderr": result.stderr[-1000:]})
    return rows


def image_info(path):
    code, data, stderr = ffprobe(path)
    stream = next((item for item in (data or {}).get("streams", []) if item.get("codec_type") == "video"), None)
    return {"ffprobe_ok": code == 0 and isinstance(stream, dict), "width": stream.get("width") if stream else None, "height": stream.get("height") if stream else None, "stderr": stderr}


def task_by_id(plan):
    return {task["task_id"]: task for task in plan["tasks"]}


def asset_gate(version, shot_id, task, payload, remote_response):
    source_rows = task.get("source_asset_binding", [])
    source_checks = []
    for item in source_rows:
        path = Path(item["path"])
        actual = sha256(path) if path.is_file() else None
        source_checks.append({"local_path": str(path), "exists": path.is_file(), "expected_sha256": item.get("sha256"), "actual_sha256": actual, "sha256_match": bool(actual and item.get("sha256") and actual.lower() == item["sha256"].lower())})
    params = remote_response.get("params", {}) if isinstance(remote_response, dict) else {}
    if isinstance(params, dict) and not {"input_image_count", "input_video_count"}.issubset(params) and isinstance(params.get("generation_params"), dict):
        params = params["generation_params"]
    expected_refs = payload.get("input_reference", [])
    response_gate = params.get("input_video_count") == 0 and params.get("input_image_count") == len(expected_refs)
    payload_gate = payload.get("reference_video") is None and payload.get("size") == "720x1280" and payload.get("aspect_ratio") == "9:16" and payload.get("seconds") == "4" and payload.get("quality") == "720p" and payload.get("n") == 1 and payload.get("generate_audio") is True
    return {
        "shot_id": shot_id,
        "version_prompt_match": f"Variant {version}:" in str(payload.get("prompt", "")) and payload.get("prompt") == task.get("prompt"),
        "payload_gate": payload_gate,
        "response_input_gate": response_gate,
        "response_input_image_count": params.get("input_image_count"),
        "response_input_video_count": params.get("input_video_count"),
        "start_frame_path": task["start_frame"]["path"],
        "end_frame_path": task["end_frame"]["path"],
        "start_frame_exists": Path(task["start_frame"]["path"]).is_file(),
        "end_frame_exists": Path(task["end_frame"]["path"]).is_file(),
        "source_asset_checks": source_checks,
        "source_assets_pass": all(row["exists"] and row["sha256_match"] for row in source_checks),
    }


def process_job(version, state, task):
    shot_id = task["task_id"]
    job = next(row for row in state["jobs"] if row["shot_id"] == shot_id)
    version_dir = OUT_ROOT / version
    original = version_dir / "original" / f"{shot_id}.mp4"
    url = job.get("video_url")
    if not isinstance(url, str) or not url.startswith("http"):
        return {"shot_id": shot_id, "status": "blocked_missing_video_url", "remote_id": job.get("remote_id")}
    try:
        pull = download(url, original)
        code, probe, probe_stderr = ffprobe(original)
        streams = (probe or {}).get("streams", [])
        video_stream = next((item for item in streams if item.get("codec_type") == "video"), None)
        duration = float(((probe or {}).get("format") or {}).get("duration") or 0.0)
        technical = {
            "ffprobe_exit_code": code,
            "ffprobe": probe,
            "video_stream_present": isinstance(video_stream, dict),
            "width": video_stream.get("width") if video_stream else None,
            "height": video_stream.get("height") if video_stream else None,
            "duration_sec": duration,
            "duration_gate": 3.5 <= duration <= 4.5,
            "technical_pass": code == 0 and isinstance(video_stream, dict) and video_stream.get("width") == 720 and video_stream.get("height") == 1280 and 3.5 <= duration <= 4.5,
            "pull": pull,
            "stderr": probe_stderr,
        }
        write_json(version_dir / f"{shot_id}_ffprobe.json", technical)
        frames = extract_five_frames(original, version_dir / "five_frames" / shot_id, duration)
        frame_checks = []
        for row in frames:
            info = image_info(Path(row["path"])) if row["exists"] else {"ffprobe_ok": False, "width": None, "height": None}
            frame_checks.append({**row, **info, "dimension_gate": info.get("width") == 720 and info.get("height") == 1280})
        payload = read_json(version_dir / f"{shot_id}_payload_snapshot.json")
        remote_response = job.get("remote_response", {})
        # State files intentionally store a sanitized response and may omit
        # params. The immutable submit response retains the input-count echo
        # needed for the continuity gate.
        response_params = remote_response.get("params") if isinstance(remote_response, dict) else None
        has_input_counts = isinstance(response_params, dict) and (
            "input_image_count" in response_params
            or "input_video_count" in response_params
            or isinstance(response_params.get("generation_params"), dict)
        )
        if not has_input_counts:
            submit_response_path = version_dir / f"{shot_id}_submit_response.json"
            if submit_response_path.is_file():
                saved_response = read_json(submit_response_path)
                if isinstance(saved_response, dict) and isinstance(saved_response.get("response"), dict):
                    remote_response = saved_response["response"]
        continuity = asset_gate(version, shot_id, task, payload, remote_response)
        continuity.update({"five_frame_count": sum(row["exists"] for row in frame_checks), "five_frame_gate": len(frame_checks) == 5 and all(row["exists"] and row["dimension_gate"] for row in frame_checks), "five_frames": frame_checks})
        continuity["continuity_pass"] = technical["technical_pass"] and continuity["five_frame_gate"] and continuity["version_prompt_match"] and continuity["payload_gate"] and continuity["response_input_gate"] and continuity["start_frame_exists"] and continuity["end_frame_exists"] and continuity["source_assets_pass"]
        write_json(version_dir / f"{shot_id}_continuity.json", continuity)
        return {"shot_id": shot_id, "remote_id": job["remote_id"], "status": "success", "original_path": str(original), "technical_pass": technical["technical_pass"], "continuity_pass": continuity["continuity_pass"], "frame_count": continuity["five_frame_count"]}
    except Exception as exc:
        return {"shot_id": shot_id, "remote_id": job.get("remote_id"), "status": "blocked_pull_or_qc", "error": type(exc).__name__ + ": " + str(exc), "original_path": str(original)}


def main():
    all_results = []
    version_states = []
    for version in VERSIONS:
        state_path = OUT_ROOT / version / f"{version}_state.json"
        state = read_json(state_path)
        if not state.get("terminal") or any(job.get("status") not in {"success", "failed"} for job in state.get("jobs", [])):
            raise RuntimeError(f"{version}: terminal gate failed")
        plan_path = next((path for path in (OUT_ROOT / version / "video").glob("*.json") if "提交" in path.name), None)
        if plan_path is None:
            plan_path = next((path for path in (OUT_ROOT / version / "video").glob("*.json") if "plan" in path.name.lower()), None)
        if plan_path is None:
            raise RuntimeError(f"{version}: submission plan missing")
        plan = read_json(plan_path)
        version_states.append((version, state_path, state, task_by_id(plan)))

    with ThreadPoolExecutor(max_workers=32) as pool:
        futures = []
        for version, _, state, tasks in version_states:
            for task in tasks.values():
                if next(job for job in state["jobs"] if job["shot_id"] == task["task_id"]).get("status") == "success":
                    futures.append(pool.submit(process_job, version, state, task))
        for future in as_completed(futures):
            all_results.append(future.result())

    by_version = {version: [] for version in VERSIONS}
    for result in all_results:
        shot_id = result["shot_id"]
        by_version[shot_id.split("-", 1)[0]].append(result)
    batch_technical = batch_continuity = batch_pulled = 0
    version_summary = []
    for version, state_path, state, tasks in version_states:
        rows = sorted(by_version[version], key=lambda row: row["shot_id"])
        technical = sum(row.get("technical_pass") is True for row in rows)
        continuity = sum(row.get("continuity_pass") is True for row in rows)
        pulled = sum(row.get("status") == "success" and bool(row.get("original_path")) for row in rows)
        state["pulled_back"] = pulled
        state["pulled_back_total"] = len(state.get("jobs", []))
        state["technical_acceptance"] = technical
        state["technical_acceptance_total"] = len(state.get("jobs", []))
        state["continuity_acceptance"] = continuity
        state["continuity_acceptance_total"] = len(state.get("jobs", []))
        state["pullback_qc"] = {"status": "passed" if technical == len(rows) and continuity == len(rows) else "blocked", "jobs": rows, "completed_at": datetime.now(timezone.utc).isoformat()}
        state["next_poll_at"] = None
        write_json(state_path, state)
        write_json(OUT_ROOT / version / "technical_check.json", {"version": version, "technical_pass": technical == len(rows), "success_jobs": len(rows), "technical_acceptance": technical, "jobs": rows})
        write_json(OUT_ROOT / version / "continuity_acceptance.json", {"version": version, "continuity_pass": continuity == len(rows), "success_jobs": len(rows), "continuity_acceptance": continuity, "jobs": rows})
        batch_pulled += pulled
        batch_technical += technical
        batch_continuity += continuity
        version_summary.append({"version": version, "success": len(rows), "pulled_back": pulled, "technical_acceptance": technical, "continuity_acceptance": continuity, "blocked": [row for row in rows if row.get("status") != "success" or not row.get("technical_pass") or not row.get("continuity_pass")]})

    batch_path = OUT_ROOT / "batch_state.json"
    batch = read_json(batch_path)
    batch["phase"] = "pullback_qc_completed" if batch_pulled == 165 and batch_technical == 165 and batch_continuity == 165 else "blocked_pullback_qc"
    batch["terminal"] = 165
    batch["terminal_total"] = 165
    batch["pulled_back"] = batch_pulled
    batch["pulled_back_total"] = 165
    batch["technical_acceptance"] = batch_technical
    batch["technical_acceptance_total"] = 165
    batch["continuity_acceptance"] = batch_continuity
    batch["continuity_acceptance_total"] = 165
    batch["next_poll_at"] = None
    batch["next_step"] = "stop heartbeat; final structured report" if batch["phase"] == "pullback_qc_completed" else "structured pullback/QC blockage report"
    batch["versions"] = version_summary
    write_json(batch_path, batch)
    print(json.dumps({"phase": batch["phase"], "pulled_back": batch_pulled, "technical_acceptance": batch_technical, "continuity_acceptance": batch_continuity}, ensure_ascii=False))


if __name__ == "__main__":
    main()
