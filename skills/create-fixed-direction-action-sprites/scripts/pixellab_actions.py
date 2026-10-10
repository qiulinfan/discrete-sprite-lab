#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=11,<14"]
# ///
"""Generate native action sprites with PixelLab V3, then package exact RGBA.

Credentials stay outside contracts, artifacts and logs. Preparation, replay and
packaging are offline. Only run submits jobs; it resumes recorded jobs and never
retries an uncertain POST. MIT License; copyright (c) 2026 qiulinfan.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

API = "https://api.pixellab.ai/v2"
ENDPOINT = "/animate-with-text-v3"
DIRECTIONS = {"north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"}
ALLOWED_FIELDS = {"schema_version", "description", "action", "directions", "image_size", "frame_count", "frame_ms", "slow_multiplier", "loop", "model", "palette_max_colors", "pivot", "ppu", "budget", "reference_policy", "seed_base", "no_background", "enhance_prompt", "drift_threshold"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def now():
    return datetime.now(timezone.utc).isoformat()


def rgba(data):
    with Image.open(io.BytesIO(data)) as image:
        require(image.format == "PNG", "Input/result must be a PNG")
        return image.convert("RGBA")


def png(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def visible_digest(image):
    data = image.tobytes()
    # Comparison only; saved RGBA is never changed.
    return digest(b"".join(data[i:i+4] if data[i+3] else bytes(4) for i in range(0, len(data), 4)))


class APIError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class PixelLab:
    def __init__(self, credential_file=None):
        path = credential_file or os.environ.get("PIXELLAB_TOKEN_FILE") or Path.home() / "Desktop/pixellab_api.txt"
        value = Path(path).read_text().strip()
        value = re.sub(r"^(?:Authorization:\s*)?Bearer\s+", "", value, flags=re.I)
        require(bool(value) and not any(ch.isspace() for ch in value), "Use a file containing only the bearer token")
        self._token = value

    def call(self, method, endpoint, body=None):
        request = urllib.request.Request(API + endpoint, method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + self._token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace").replace(self._token, "[REDACTED]")
            raise APIError(f"HTTP {error.code}: {detail[:2000]}", error.code) from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise APIError(str(error).replace(self._token, "[REDACTED]")) from None


def validate_contract(contract):
    require(isinstance(contract, dict) and not (set(contract) - ALLOWED_FIELDS), "Unknown contract fields")
    require(contract.get("schema_version") == 1, "schema_version must be 1")
    require(contract.get("model", "v3") == "v3", "This helper implements tested PixelLab V3 only")
    require(isinstance(contract.get("description"), str) and bool(contract["description"].strip()), "description is required")
    action = contract.get("action")
    require(isinstance(action, str) and 1 <= len(action) <= 800, "action needs 1..800 characters; leave room for facing/camera instructions")
    size = contract.get("image_size", [64, 64])
    require(isinstance(size, list) and len(size) == 2 and all(type(n) is int and 16 <= n <= 256 for n in size), "image_size needs two native dimensions, 16..256")
    count = contract.get("frame_count")
    require(type(count) is int and 4 <= count <= 16 and count % 2 == 0, "V3 frame_count must be even, 4..16")
    require(size[0] * size[1] * count <= 524288, "V3 pixel budget exceeded")
    duration = contract.get("frame_ms")
    require(type(duration) is int and duration > 0, "frame_ms must be a positive integer for exact APNG timing")
    require(type(contract.get("loop")) is bool, "Declare loop true/false")
    require(type(contract.get("slow_multiplier", 3)) is int and contract.get("slow_multiplier", 3) >= 2, "slow_multiplier must be an integer >=2")
    pivot = contract.get("pivot")
    require(isinstance(pivot, list) and len(pivot) == 2 and all(type(n) is int for n in pivot) and 0 <= pivot[0] <= size[0] and 0 <= pivot[1] <= size[1], "Declare pivot in bottom-left native pixels")
    require(isinstance(contract.get("ppu"), (str, int, float)) and bool(contract["ppu"]), "Declare PPU or reference family")
    require(contract.get("reference_policy", "prefixed") in {"prefixed", "none"}, "reference_policy must be prefixed or none")
    limit = contract.get("palette_max_colors")
    require(limit is None or type(limit) is int and limit > 0, "palette_max_colors must be positive or null")
    require(type(contract.get("seed_base", 1)) is int and contract.get("seed_base", 1) >= 0, "seed_base must be nonnegative")
    require(type(contract.get("no_background", True)) is bool and type(contract.get("enhance_prompt", False)) is bool, "Background/enhancement switches must be boolean")
    threshold = contract.get("drift_threshold")
    require(threshold is None or type(threshold) in (int, float) and threshold >= 0, "drift_threshold must be nonnegative")
    directions = contract.get("directions")
    require(isinstance(directions, list) and 1 <= len(directions) <= 8, "Declare 1..8 directional references")
    seen = set()
    for item in directions:
        require(isinstance(item, dict) and not (set(item) - {"direction", "reference", "last_frame", "seed"}), "Unknown direction fields")
        direction = item.get("direction")
        require(direction in DIRECTIONS and direction not in seen, "Invalid or duplicate direction")
        require(isinstance(item.get("reference"), str) and bool(item["reference"]), "Each direction requires its own PNG reference")
        require(item.get("last_frame") is None or isinstance(item["last_frame"], str), "last_frame must be a PNG path")
        require(type(item.get("seed", 1)) is int and item.get("seed", 1) >= 0, "seed must be nonnegative")
        seen.add(direction)
    budget = contract.get("budget")
    require(isinstance(budget, dict) and not (set(budget) - {"usd", "max_jobs", "reserve_usd_per_job"}), "Declare a bounded budget")
    require(type(budget.get("usd")) in (int, float) and 0 < budget["usd"] <= 10000, "User-authorized positive USD budget required")
    require(type(budget.get("max_jobs")) is int and len(directions) <= budget["max_jobs"] <= 1000, "max_jobs must cover the initial directions")
    require(type(budget.get("reserve_usd_per_job")) in (int, float) and 0 < budget["reserve_usd_per_job"] <= budget["usd"], "Declare a conservative per-job USD reserve within budget")
    return contract


def prepare(contract_path, root):
    contract_path, root = Path(contract_path), Path(root)
    contract = validate_contract(load(contract_path))
    require(not root.exists() or not any(root.iterdir()), "Output root must be fresh; use run to resume")
    require(not root.resolve().is_relative_to(Path(__file__).resolve().parents[1]), "Keep outputs outside the installed Skill")
    captured = []
    for index, item in enumerate(contract["directions"]):
        normalized = {"direction": item["direction"], "seed": item.get("seed", contract.get("seed_base", 1) + index)}
        for field in ("reference", "last_frame"):
            if not item.get(field):
                continue
            source = (contract_path.parent / item[field]).resolve()
            data = source.read_bytes()
            image = rgba(data)
            require(list(image.size) == contract.get("image_size", [64, 64]), "Reference dimensions must match contract")
            require(255 in image.getchannel("A").tobytes(), "Reference is empty")
            require(set(image.getchannel("A").tobytes()) <= {0, 255}, "Reference must use binary Alpha")
            relative = f"source/references/{item['direction']}-{field}.png"
            normalized[field] = relative
            normalized[field + "_sha256"] = digest(data)
            captured.append((relative, data))
        contract["directions"][index] = normalized
    for relative, data in captured:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    contract["image_size"] = contract.get("image_size", [64, 64])
    contract["reference_policy"] = contract.get("reference_policy", "prefixed")
    save(root / "contract.json", contract)
    save(root / "state.json", {"created_at": now(), "jobs": [], "transport": "live-api", "authorization": "budget recorded in contract; scope applies only to this output root"})
    return root


def direction_record(contract, direction):
    return next(item for item in contract["directions"] if item["direction"] == direction)


def payload_for(root, item):
    contract = load(root / "contract.json")
    def encoded(field):
        path = root / item[field]
        data = path.read_bytes()
        require(digest(data) == item[field + "_sha256"], "Reference changed after preparation")
        return {"type": "base64", "base64": base64.b64encode(data).decode(), "format": "png"}
    facing = item["direction"].replace("northeast", "north-east").replace("northwest", "north-west").replace("southeast", "south-east").replace("southwest", "south-west")
    action = contract["action"] + f" Keep facing {facing} in the reference camera view; preserve character identity and native pixel style. No camera movement or zoom."
    body = {"first_frame": encoded("reference"), "action": action, "frame_count": contract["frame_count"], "seed": item["seed"], "no_background": contract.get("no_background", True), "enhance_prompt": contract.get("enhance_prompt", False)}
    if item.get("last_frame"):
        body["last_frame"] = encoded("last_frame")
    if contract.get("drift_threshold") is not None:
        body["drift_threshold"] = contract["drift_threshold"]
    return body


def attempt_path(root, job):
    return root / "api/jobs" / job["direction"] / f"attempt-{job['attempt']:02d}"


def update_job(root, state, job):
    save(attempt_path(root, job) / "state.json", job)
    save(root / "state.json", state)


def refresh_cost(root, api):
    current = api.call("GET", "/balance")
    save(root / "api/balance-latest.json", current)
    initial = load(root / "api/balance-initial.json")
    state = load(root / "state.json")
    equivalent = []
    for job in state["jobs"]:
        path = attempt_path(root, job) / "result.json"
        if path.exists():
            response = load(path)
            usage = (response.get("last_response") or {}).get("usage") or {}
            equivalent.append({"direction": job["direction"], "attempt": job["attempt"], "returned_usage": response.get("usage"), "provider_usage": usage})
    ledger = {"initial": initial, "latest": current, "actual_usd_balance_delta": initial["credits"]["usd"] - current["credits"]["usd"],
        "subscription_generations_delta": initial["subscription"]["generations"] - current["subscription"]["generations"],
        "cost_if_paid_usd_total": sum((j["provider_usage"].get("cost_if_paid") or 0) for j in equivalent),
        "cost_if_paid_is_actual_charge": False, "jobs": equivalent,
        "account_delta_scope": "Account-wide balance; concurrent external use may contribute. Returned job usage is recorded separately."}
    save(root / "api/cost-ledger.json", ledger)
    return current, ledger


def check_budget(contract, state, current, ledger):
    budget = contract["budget"]
    require(len(state["jobs"]) < budget["max_jobs"], "Authorized job-attempt cap reached")
    active = [j for j in state["jobs"] if j["status"] not in {"completed", "failed", "rejected", "artifact-failed"}]
    require(not active, "Resolve/resume the existing job before submitting another")
    reserve = budget["reserve_usd_per_job"]
    require(max(0, ledger["actual_usd_balance_delta"]) + reserve <= budget["usd"], "USD budget exhausted or insufficient unreserved budget")
    require(current["credits"]["usd"] >= reserve, "Insufficient credit reserve")


def submit(root, api, direction):
    root = Path(root)
    state, contract = load(root / "state.json"), load(root / "contract.json")
    require(state["transport"] == "live-api", "Replay outputs cannot submit jobs")
    body = payload_for(root, direction_record(contract, direction))
    current, ledger = refresh_cost(root, api)
    check_budget(contract, state, current, ledger)
    job = {"direction": direction, "attempt": 1 + sum(j["direction"] == direction for j in state["jobs"]), "status": "post-uncertain", "submitted_at": now()}
    state["jobs"].append(job)
    directory = attempt_path(root, job)
    save(directory / "request.json", {"endpoint": ENDPOINT, "payload": body})
    update_job(root, state, job)  # Persist before POST, including ambiguous transport failures.
    try:
        accepted = api.call("POST", ENDPOINT, body)
    except APIError as error:
        job["status"] = "rejected" if error.status in {400, 401, 402, 403, 404, 422, 429} else "post-uncertain"
        job["http_status"] = error.status
        save(directory / "error.json", {"http_status": error.status, "message": str(error)})
        update_job(root, state, job)
        raise
    save(directory / "accepted.json", accepted)
    require(isinstance(accepted.get("background_job_id"), str), "POST returned no job ID; do not resubmit")
    job.update({"job_id": accepted["background_job_id"], "status": "processing"})
    update_job(root, state, job)
    return job


def decode_result(root, job, result):
    root = Path(root)
    contract = load(root / "contract.json")
    items = (result.get("last_response") or {}).get("images") or []
    directory = attempt_path(root, job)
    raw = directory / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, item in enumerate(items):
        text = item["base64"]
        if text.startswith("data:"):
            text = text.split(",", 1)[1]
        data = base64.b64decode(text, validate=True)
        (raw / f"frame-{index:02d}.png").write_bytes(data)
        frames.append(rgba(data))
    first = 1 if contract["reference_policy"] == "prefixed" else 0
    require(len(frames) == contract["frame_count"] + first, "Unexpected frame count; all returned PNGs retained for inspection")
    require(all(list(f.size) == contract["image_size"] for f in frames), "Unexpected native dimensions; no resizing applied")
    observation = None
    if first:
        item = direction_record(contract, job["direction"])
        reference = rgba((root / item["reference"]).read_bytes())
        original, returned = reference.tobytes(), frames[0].tobytes()
        observation = {"exact_rgba_match": original == returned, "changed_visible_cells": sum(original[i:i+4] != returned[i:i+4] for i in range(0, len(original), 4) if original[i+3] or returned[i+3]), "changed_alpha_cells": sum(a != b for a,b in zip(reference.getchannel("A").tobytes(), frames[0].getchannel("A").tobytes()))}
    selected = directory / "frames"
    selected.mkdir(parents=True, exist_ok=True)
    for index, image in enumerate(frames[first:]):
        (selected / f"frame-{index:02d}.png").write_bytes(png(image))
    save(directory / "decode.json", {"raw_count": len(frames), "selected_raw_indices": list(range(first, len(frames))), "prefixed_reference_observation": observation, "raw_sha256": [digest(p.read_bytes()) for p in sorted(raw.glob("*.png"))], "pixel_changes": "none; RGBA decode/copy only"})


def poll_job(root, api, job, wait_seconds=10, deadline_seconds=900):
    root = Path(root)
    state = load(root / "state.json")
    job = next(j for j in state["jobs"] if j["direction"] == job["direction"] and j["attempt"] == job["attempt"])
    require(job.get("job_id"), "POST acceptance is uncertain; locate the existing provider job before another submission")
    deadline = time.monotonic() + deadline_seconds
    last_message = None
    while True:
        result = api.call("GET", "/background-jobs/" + job["job_id"])
        save(attempt_path(root, job) / "result.json", result)
        status = result.get("status")
        require(status in {"processing", "completed", "failed"}, "Unknown job status; preserve response and inspect")
        message = {"direction": job["direction"], "status": status, "progress": (result.get("last_response") or {}).get("progress")}
        if message != last_message:
            print(json.dumps(message), flush=True)
            last_message = message
        job["status"] = status
        if status == "completed":
            try:
                decode_result(root, job, result)
            except (ValueError, KeyError, OSError) as error:
                job["status"] = "artifact-failed"
                job["artifact_error"] = str(error)
                update_job(root, state, job)
                raise
            update_job(root, state, job)
            return
        update_job(root, state, job)
        if status == "failed":
            raise RuntimeError("Provider job failed; inspect saved response before a bounded retry")
        require(time.monotonic() < deadline, "Polling deadline reached; resume the job, do not submit another")
        time.sleep(wait_seconds)


def run(root, api, retry_direction=None):
    root = Path(root)
    state = load(root / "state.json")
    require(state["transport"] == "live-api", "Replay is offline-only")
    if not (root / "api/balance-initial.json").exists():
        save(root / "api/balance-initial.json", api.call("GET", "/balance"))
    # Drain accepted/uncertain jobs before attempting any new direction.
    for job in list(state["jobs"]):
        if job["status"] in {"processing", "post-uncertain"}:
            poll_job(root, api, job)
    if retry_direction:
        old = [j for j in load(root / "state.json")["jobs"] if j["direction"] == retry_direction]
        require(old and old[-1]["status"] in {"failed", "rejected", "artifact-failed"}, "Retry requires a known terminal failed/rejected attempt")
        poll_job(root, api, submit(root, api, retry_direction))
    else:
        for item in load(root / "contract.json")["directions"]:
            matching = [j for j in load(root / "state.json")["jobs"] if j["direction"] == item["direction"]]
            if matching:
                require(matching[-1]["status"] == "completed", "Direction has a failed attempt; use explicit --retry-direction within the existing budget")
                continue
            poll_job(root, api, submit(root, api, item["direction"]))
    refresh_cost(root, api)


def replay(contract_path, recordings, root):
    root = prepare(contract_path, root)
    state = load(root / "state.json")
    state["transport"] = "offline-replay"
    for item in load(root / "contract.json")["directions"]:
        source_dir = Path(recordings) / item["direction"]
        source = source_dir / "job-latest.json"
        request = load(source_dir / "request.json")
        recorded_body = request["payload"]
        encoded = recorded_body["first_frame"]["base64"]
        if encoded.startswith("data:"):
            encoded = encoded.split(",", 1)[1]
        require(digest(base64.b64decode(encoded, validate=True)) == item["reference_sha256"], "Replay reference does not match the recorded API input")
        require(recorded_body["frame_count"] == load(root / "contract.json")["frame_count"], "Replay frame count differs from recorded request")
        result = load(source)
        require(result.get("status") == "completed", "Replay needs completed recorded provider jobs")
        job = {"direction": item["direction"], "attempt": 1, "status": "completed", "job_id": result["id"], "replayed_at": now()}
        state["jobs"].append(job)
        save(attempt_path(root, job) / "request.json", request)
        save(attempt_path(root, job) / "result.json", result)
        decode_result(root, job, result)
        update_job(root, state, job)
    return root


def package(root, visual_review=None):
    root = Path(root)
    contract, state = load(root / "contract.json"), load(root / "state.json")
    count, size = contract["frame_count"], contract["image_size"]
    sheet = Image.new("RGBA", (size[0]*count, size[1]*len(contract["directions"])))
    records, checks, colors, frame_sets = [], [], set(), {}
    for row, item in enumerate(contract["directions"]):
        direction = item["direction"]
        jobs = [j for j in state["jobs"] if j["direction"] == direction and j["status"] == "completed"]
        require(bool(jobs), f"Missing completed direction: {direction}")
        job = jobs[-1]
        # If a newer failed retry exists, the previous completed version is retained,
        # but must not silently become the selected latest result.
        latest = [j for j in state["jobs"] if j["direction"] == direction][-1]
        require(latest == job, "Latest attempt is not complete; explicitly preserve/select an older version outside this root")
        directory = attempt_path(root, job)
        decoded = load(directory / "decode.json")
        frames = []
        hashes = []
        for index, raw_index in enumerate(decoded["selected_raw_indices"]):
            path = directory / "frames" / f"frame-{index:02d}.png"
            data = path.read_bytes()
            image = rgba(data)
            original_data = (directory / "raw" / f"frame-{raw_index:02d}.png").read_bytes()
            require(digest(original_data)==decoded["raw_sha256"][raw_index], "Preserved raw provider PNG changed after decoding")
            original = rgba(original_data)
            require(image.tobytes() == original.tobytes(), "Selected pixels differ from preserved raw provider PNG")
            frames.append(image)
            hashes.append(visible_digest(image))
            alpha = image.getchannel("A")
            checks.append({"direction": direction, "index": index, "size": list(image.size) == size, "binary_alpha": set(alpha.tobytes()) <= {0,255}, "nonempty": bool(alpha.getbbox()), "requested_transparency": not contract.get("no_background",True) or 0 in alpha.tobytes()})
            cells = image.tobytes()
            colors.update(tuple(cells[i:i+3]) for i in range(0, len(cells), 4) if cells[i+3])
            x,y = index*size[0], row*size[1]
            sheet.paste(image, (x,y))
            require(sheet.crop((x,y,x+size[0],y+size[1])).tobytes() == image.tobytes(), "Packing changed RGBA")
            scale = max(1, math.ceil(1024/max(size)))
            review_path = root / "evidence/review" / direction / f"frame-{index:02d}.png"
            review_path.parent.mkdir(parents=True, exist_ok=True)
            image.resize((size[0]*scale,size[1]*scale),Image.Resampling.NEAREST).save(review_path)
            records.append({"direction": direction, "index": index, "path": str(path.relative_to(root)), "file_sha256": digest(data), "rgba_sha256": digest(image.tobytes()), "raw_index": raw_index, "rect": [x,y,*size], "duration_ms": contract["frame_ms"], "pivot_px_from_bottom_left": contract["pivot"], "bbox": alpha.getbbox()})
        checks.append({"direction": direction, "distinct_visible_frames": len(set(hashes)) == count})
        frame_sets[direction] = frames
        for suffix,multiplier in (("normal",1),("slow",contract.get("slow_multiplier",3))):
            folder = root / "evidence/loops"
            folder.mkdir(parents=True, exist_ok=True)
            options = {"save_all":True,"append_images":frames[1:],"duration":contract["frame_ms"]*multiplier,"disposal":0,"blend":0}
            if contract["loop"]:
                options["loop"] = 0
            else:
                # APNG counts plays; one is a one-shot.
                options["loop"] = 1
            path = folder / f"{direction}-{suffix}.png"
            frames[0].save(path, **options)
            with Image.open(path) as animation:
                require(animation.n_frames == count, "APNG collapsed frames")
                for i,frame in enumerate(frames):
                    animation.seek(i)
                    require(animation.convert("RGBA").tobytes()==frame.tobytes(), "APNG changed RGBA")
                    require(animation.info["duration"] == contract["frame_ms"]*multiplier, "APNG timing changed")
    generated = root / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    sheet_path = generated / "sheet.png"
    sheet.save(sheet_path)
    manifest = {"model":"PixelLab V3", "endpoint":API+ENDPOINT, "transport":state["transport"], "frame_size":size,"frame_count":count,"direction_order":[i["direction"] for i in contract["directions"]],"frame_ms":contract["frame_ms"],"loop":contract["loop"],"ppu":contract["ppu"],"sheet_sha256":digest(sheet_path.read_bytes()),"frames":records,"palette_rgb":sorted(colors),"pixel_changes":"none; exact native RGBA copy and 1:1 placement","phase_alignment":"Not established by matching ordinal frame indices"}
    save(generated / "manifest.json", manifest)
    hard_pass = all(all(v for k,v in c.items() if k not in {"direction","index"}) for c in checks)
    limit = contract.get("palette_max_colors")
    palette_ok = limit is None or len(colors) <= limit
    hard_pass = hard_pass and palette_ok
    audit = {"checks":checks,"palette_rgb_count":len(colors),"palette_limit":limit,"palette_requirement_passed":palette_ok,"hard_pass":hard_pass,"visual_verdict":"awaiting-visual-review" if hard_pass else "technical-fail","user_approval":"pending","engine_import":"not performed","sheet_sha256":manifest["sheet_sha256"]}
    # Invalidate any old approval before validating a newly supplied review.
    save(generated / "audit.json", audit)
    if visual_review:
        review = load(visual_review)
        expected = {f"{f['direction']}/{f['index']}":f["rgba_sha256"] for f in records}
        require(review.get("sheet_sha256")==manifest["sheet_sha256"] and review.get("frame_hashes")==expected, "Visual review is stale or incomplete")
        require(review.get("frame_ms")==contract["frame_ms"] and review.get("slow_multiplier")==contract.get("slow_multiplier",3) and review.get("loop")==contract["loop"] and review.get("direction_order")==manifest["direction_order"], "Visual review timing, loop or direction order is stale")
        require(review.get("authority") and review.get("individual_frame_review") is True and review.get("normal_and_slow_review") is True, "Explicit individual-frame and normal/slow review required")
        require(review.get("verdict") in {"pass","candidate-with-warnings","visual-fail"} and isinstance(review.get("findings"),dict) and review["findings"], "Record visual verdict and concrete findings")
        require(all(review["findings"].get(direction) for direction in manifest["direction_order"]), "Concrete visual findings required for every direction")
        require(review["verdict"] != "candidate-with-warnings" or bool(review.get("warnings")), "Candidate verdict needs concrete warnings")
        if hard_pass:
            audit["visual_verdict"] = review["verdict"]
        else:
            audit["requested_visual_verdict"] = review["verdict"]
        save(root / "evidence/visual-review.json", review)
    save(generated / "audit.json", audit)
    save(generated / "receipt.json", {"contract_sha256":digest((root/"contract.json").read_bytes()),"manifest_sha256":digest((generated/"manifest.json").read_bytes()),"audit_sha256":digest((generated/"audit.json").read_bytes()),"provider":"PixelLab AI","docs":"https://api.pixellab.ai/v2/docs","terms":"https://www.pixellab.ai/termsofservice","cost_ledger":"api/cost-ledger.json" if (root/"api/cost-ledger.json").exists() else None,"visual_approval_separate_from_file_integrity":True})
    return manifest, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare","balance","run","package","replay"])
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--recordings", type=Path)
    parser.add_argument("--credential-file", type=Path)
    parser.add_argument("--retry-direction", choices=sorted(DIRECTIONS))
    parser.add_argument("--visual-review", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        require(args.contract and args.root, "prepare needs --contract and --root")
        prepare(args.contract, args.root)
    elif args.command == "balance":
        print(json.dumps(PixelLab(args.credential_file).call("GET", "/balance")))
    elif args.command == "run":
        require(args.root, "run needs --root")
        run(args.root, PixelLab(args.credential_file), args.retry_direction)
    elif args.command == "replay":
        require(args.contract and args.root and args.recordings, "replay needs --contract, --root, --recordings")
        replay(args.contract, args.recordings, args.root)
    else:
        require(args.root, "package needs --root")
        manifest,audit = package(args.root,args.visual_review)
        print(json.dumps({"sheet_sha256":manifest["sheet_sha256"],"frame_total":len(manifest["frames"]),"hard_pass":audit["hard_pass"],"visual_verdict":audit["visual_verdict"]}))
        return 0 if audit["hard_pass"] else 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError,RuntimeError,OSError,KeyError) as error:
        raise SystemExit(f"{type(error).__name__}: {error}") from None
