#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=11,<14"]
# ///
"""Preserve authored action keys and fill only their gaps with PixelLab.

Procedural controllers remain task-owned: supply their native PNG frames.
All actions in a task share one explicitly authorized budget ledger. Only
``run`` spends credits. MIT License; copyright (c) 2026 qiulinfan.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import io
import json
import math
import os
from pathlib import Path
import time

from PIL import Image

import pixellab_actions as P

DIRECTION_ORDER = ("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest")

def read_png(path, size, transparent=True):
    data = Path(path).read_bytes()
    image = P.rgba(data)
    P.require(list(image.size) == size, f"Native size differs: {path}")
    if transparent:
        P.require(set(image.getchannel("A").tobytes()) == {0, 255}, f"Transparent binary Alpha required: {path}")
    P.require(image.getbbox() is not None, f"Empty frame: {path}")
    return image


def segments(keys, count, loop):
    """Return time gaps; keys at the endpoints are never provider outputs."""
    indices = [k["frame"] for k in keys]
    P.require(indices == sorted(set(indices)) and indices[0] == 0, "Keys must start at0 and be unique/in order")
    P.require(all(type(i) is int and 0 <= i < count for i in indices), "Key index outside sequence")
    P.require(loop or indices[-1] == count - 1, "A one-shot needs an authored final key")
    pairs = list(zip(keys, keys[1:]))
    if loop:
        pairs.append((keys[-1], {**keys[0], "frame": count}))
    result = []
    for a, b in pairs:
        missing = b["frame"] - a["frame"] - 1
        if not missing:
            continue
        n = max(4, math.ceil((missing + 1) / 2) * 2)
        P.require(n <= 16, "Gap exceeds16 frames: add a meaningful action key")
        # raw0 is the provider's processed reference; raw1..N are returned motion.
        selected = [round(n * j / (missing + 1)) for j in range(1, missing + 1)]
        P.require(len(set(selected)) == missing and min(selected) >= 1 and max(selected) < n, "Invalid inbetween selection")
        result.append({"from": a["frame"], "to": b["frame"], "start": a["path"], "end": b["path"],
                       "start_phase": a["phase"], "end_phase": b["phase"], "generated_count": n,
                       "slots": list(range(a["frame"] + 1, b["frame"])), "raw_indices": selected})
    return result


def prepare(contract_path, root):
    contract_path, root = Path(contract_path).resolve(), Path(root).resolve()
    c = P.load(contract_path)
    P.require(c.get("schema_version") == 2, "Hybrid contract schema_version must be2")
    P.require(c.get("route") in {"procedural", "keyframed"}, "Declare procedural or keyframed route")
    P.require(isinstance(c.get("controller_or_pose_authority"), str) and c["controller_or_pose_authority"], "Name the controller or key-pose authority")
    size, count = c.get("image_size"), c.get("frame_count")
    P.require(isinstance(size, list) and len(size) == 2 and all(type(n) is int and 1 <= n <= 256 for n in size), "Declare native size <=256")
    P.require(type(count) is int and 2 <= count <= 128 and type(c.get("loop")) is bool, "Declare frame count and loop policy")
    durations = c.get("durations_ms", [c.get("frame_ms")] * count)
    P.require(len(durations) == count and all(type(n) is int and n > 0 for n in durations), "Positive per-frame timing required")
    P.require(len(c.get("pivot", [])) == 2 and c.get("ppu"), "Declare pivot and PPU/matching family")
    rows = c.get("directions", [])
    P.require(rows and len({r["direction"] for r in rows}) == len(rows), "Declare unique directions")
    P.require(all(r["direction"] in P.DIRECTIONS for r in rows), "Unknown direction")
    P.require(not root.exists(), "Use a fresh output root")
    # Validate every source before creating a partial workspace.
    for row in rows:
        items = row.get("frames", []) if c["route"] == "procedural" else row.get("keys", [])
        P.require(items, "Every direction needs frames or authored keys")
        if c["route"] == "procedural":
            P.require(len(items) == count, "Procedural controller must supply the complete sequence")
        else:
            segments(items, count, c["loop"])
            P.require(all(isinstance(k.get("phase"), str) and k["phase"] for k in items), "Name every deliberate key phase")
        for item in items:
            read_png(contract_path.parent / (item if isinstance(item, str) else item["path"]), size)
    root.mkdir(parents=True)
    c["durations_ms"] = durations
    if c.get("budget_file"):
        c["budget_file"] = os.path.relpath((contract_path.parent / c["budget_file"]).resolve(), root)
    inputs, jobs = {}, []
    for row in rows:
        direction = row["direction"]
        items = row.get("frames", []) if c["route"] == "procedural" else row["keys"]
        copied = []
        for i, item in enumerate(items):
            original = contract_path.parent / (item if isinstance(item, str) else item["path"])
            dest = root / "inputs" / direction / f"{i:02d}.png"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(original.read_bytes())
            rel = str(dest.relative_to(root))
            inputs[rel] = P.digest(dest.read_bytes())
            copied.append(rel if isinstance(item, str) else {**item, "path": rel})
        if c["route"] == "procedural":
            row["frames"] = copied
        else:
            row["keys"] = copied
            for segment in segments(copied, count, c["loop"]):
                P.require(size[0] * size[1] * segment["generated_count"] <= 524288, "V3 pixel budget exceeded")
                jobs.append({**segment, "id": f"{direction}-{segment['from']:03d}-{segment['to']:03d}", "direction": direction})
    P.save(root / "contract.json", c)
    P.save(root / "evidence/input-lock.json", inputs)
    P.save(root / "evidence/jobs.json", jobs)
    P.save(root / "evidence/state.json", {"status": "prepared", "jobs": {}})
    return {"directions": len(rows), "planned_jobs": len(jobs), "route": c["route"]}


def check_inputs(root):
    for path, expected in P.load(root / "evidence/input-lock.json").items():
        P.require(P.digest((root / path).read_bytes()) == expected, "Prepared input changed; use a fresh version")


@contextmanager
def budget_lock(path):
    """One process owns a shared account ledger; OS releases the lock on crash."""
    lock = Path(str(path) + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as f:
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0); f.write(b"0"); f.flush(); f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError("Another worker owns this task budget") from None
        try:
            yield
        finally:
            if os.name == "nt":
                f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


def fresh_balance(api, ledger, path):
    current = api.call("GET", "/balance")
    if ledger.get("initial_balance") is None:
        ledger["initial_balance"] = current
    ledger["latest_balance"] = current
    ledger["actual_debit_usd"] = ledger["initial_balance"]["credits"]["usd"] - current["credits"]["usd"]
    ledger["trial_generations_used"] = max(0, ledger["initial_balance"].get("subscription", {}).get("generations", 0) - current.get("subscription", {}).get("generations", 0))
    P.save(path, ledger)
    return current


def payload(root, segment):
    c = P.load(root / "contract.json")
    def encoded(path):
        return {"type": "base64", "format": "png", "base64": base64.b64encode((root / path).read_bytes()).decode()}
    direction = segment["direction"]
    facing = {"north":"North/back, back of head visible", "northeast":"Northeast/rear-right three-quarter, back of head visible",
              "east":"East/right profile", "southeast":"Southeast/front-right three-quarter", "south":"South/front",
              "southwest":"Southwest/front-left three-quarter", "west":"West/left profile",
              "northwest":"Northwest/rear-left three-quarter, back of head visible"}[direction]
    # Action/event names stay in metadata: weapon semantics can induce an
    # unrequested strike/effect instead of a short pose-to-pose transition.
    geometry = c.get("transition_description", "Slowly connect the supplied two poses along one short path. Existing objects keep their shape and size.")
    prompt = (f"Interpolate only between the supplied first and last poses. {geometry} "
              f"Fixed facing: {facing}; fixed camera, character scale and lighting. "
              "Preserve the same face, costume and connected limbs. Keep the image clean with no additional visual effects.")
    P.require(len(prompt) <= 1000, "Transition prompt exceeds provider limit")
    return {"first_frame": encoded(segment["start"]), "last_frame": encoded(segment["end"]),
            "action": prompt, "frame_count": segment["generated_count"],
            "seed": c.get("seed_base", 1) + segment["from"] + DIRECTION_ORDER.index(direction) * 1000,
            "no_background": True, "enhance_prompt": False}


def decode(root, segment, result):
    images = (result.get("last_response") or {}).get("images")
    P.require(isinstance(images, list) and len(images) == segment["generated_count"] + 1, "Unexpected prefixed-reference frame count; inspect raw response")
    size = P.load(root / "contract.json")["image_size"]
    folder = root / "evidence/api" / segment["id"] / "raw"
    folder.mkdir(parents=True, exist_ok=True)
    digests = []
    for i, item in enumerate(images):
        value = item.get("base64", "")
        value = value.split(",", 1)[1] if value.startswith("data:") else value
        raw = base64.b64decode(value)
        target = folder / f"frame-{i:02d}.png"
        target.write_bytes(raw)
        read_png(target, size, transparent=i in segment["raw_indices"])
        digests.append(P.digest(raw))
    P.save(folder.parent / "decode.json", {"raw_sha256": digests, "selected_indices": segment["raw_indices"], "processed_reference_preserved": True})


def poll(root, segment, entry, ledger, ledger_path, api, wait_seconds=8, deadline_seconds=900):
    deadline = time.monotonic() + deadline_seconds
    folder = root / "evidence/api" / segment["id"]
    last_message = None
    while True:
        result = None
        for attempt in range(3):
            try:
                result = api.call("GET", "/background-jobs/" + entry["job_id"])
                break
            except P.APIError as error:
                P.save(folder / "get-error.json", {"error": str(error), "time": P.now(), "job_id": entry["job_id"]})
                if error.status not in {None, 429, 500, 502, 503, 504} or attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        P.save(folder / "result.json", result)
        status = result.get("status")
        P.require(status in {"processing", "completed", "failed"}, "Unknown provider state; resume this job after inspection")
        entry["status"] = status
        entry["last_polled_at"] = P.now()
        P.save(ledger_path, ledger)
        message = {"segment": segment["id"], "status": status, "progress": (result.get("last_response") or {}).get("progress")}
        if message != last_message:
            print(json.dumps(message), flush=True)
            last_message = message
        if status == "completed":
            try:
                decode(root, segment, result)
            except (ValueError, KeyError, OSError) as error:
                entry["status"] = "artifact-failed"
                entry["error"] = str(error)
                P.save(ledger_path, ledger)
                raise
            fresh_balance(api, ledger, ledger_path)
            return
        if status == "failed":
            fresh_balance(api, ledger, ledger_path)
            raise ValueError("Provider failed this segment; inspect before a new authorized revision")
        P.require(time.monotonic() < deadline, "Polling deadline; job remains resumable, no new POST")
        time.sleep(wait_seconds)


def run(root, api, max_new_jobs=None):
    root = Path(root).resolve()
    c = P.load(root / "contract.json")
    P.require(c["route"] == "keyframed", "Procedural actions never submit API jobs")
    P.require(c.get("budget_file"), "Current task budget authorization required")
    path = (root / c["budget_file"]).resolve()
    with budget_lock(path):
        ledger = P.load(path)
        P.require(ledger.get("status") == "open" and ledger.get("authority"), "Budget is closed or not authorized")
        check_inputs(root)
        jobs = P.load(root / "evidence/jobs.json")
        new_count = 0
        # Never submit while another action has an accepted/uncertain job.
        for entry in ledger.get("jobs", []):
            if entry["status"] in {"processing", "post-uncertain"}:
                P.require(entry.get("job_id"), "Ambiguous POST: locate existing provider job before any resubmission")
                other = Path(entry["root"])
                check_inputs(other)
                segment = next(j for j in P.load(other / "evidence/jobs.json") if j["id"] == entry["segment"])
                poll(other, segment, entry, ledger, path, api)
        for segment in jobs:
            previous = [j for j in ledger.get("jobs", []) if j["root"] == str(root) and j["segment"] == segment["id"]]
            if previous:
                P.require(previous[-1]["status"] == "completed", "Segment has a terminal failed/rejected attempt; create a reviewed revision")
                continue
            if max_new_jobs is not None and new_count >= max_new_jobs:
                break
            P.require(not c.get("submission_closed"), "This action version is closed for new submissions; preserve results and use the reviewed revision")
            current = fresh_balance(api, ledger, path)
            reserve = max(ledger["reserve_usd_per_job"], c.get("reserve_usd_per_job", 0))
            P.require(len(ledger.get("jobs", [])) < ledger["max_jobs"], "Shared job-attempt cap reached")
            P.require(max(0, ledger["actual_debit_usd"]) + reserve <= ledger["usd"], "Shared USD budget exhausted")
            P.require(current["credits"]["usd"] >= reserve, "Insufficient credit reserve")
            body = payload(root, segment)
            folder = root / "evidence/api" / segment["id"]
            P.save(folder / "request.json", {"endpoint": P.ENDPOINT, "payload": body})
            entry = {"root": str(root), "segment": segment["id"], "status": "post-uncertain", "time": P.now()}
            ledger.setdefault("jobs", []).append(entry)
            P.save(path, ledger)  # persisted BEFORE POST; never blind retry
            try:
                response = api.call("POST", P.ENDPOINT, body)
                P.save(folder / "accepted.json", response)
                entry["job_id"] = response["background_job_id"]
                entry["status"] = "processing"
            except (P.APIError, KeyError) as error:
                if isinstance(error, P.APIError) and error.status in {400, 401, 402, 403, 404, 422, 429}:
                    entry["status"] = "rejected"
                entry["error"] = str(error)
                P.save(path, ledger)
                raise
            P.save(path, ledger)
            new_count += 1
            poll(root, segment, entry, ledger, path, api)
    return {"new_jobs": new_count}


def assemble(root, only_directions=None):
    root = Path(root).resolve()
    c = P.load(root / "contract.json")
    check_inputs(root)
    size, count = c["image_size"], c["frame_count"]
    requested = [r["direction"] for r in c["directions"]]
    P.require(not only_directions or set(only_directions) <= set(requested), "Unknown partial-output direction")
    rows = [r for r in c["directions"] if not only_directions or r["direction"] in only_directions]
    jobs = P.load(root / "evidence/jobs.json")
    locks, records, diagnostics = {}, [], []
    sheet = Image.new("RGBA", (size[0] * count, size[1] * len(rows)))
    for row_number, row in enumerate(rows):
        direction, slots = row["direction"], [None] * count
        if c["route"] == "procedural":
            for i, path in enumerate(row["frames"]):
                slots[i] = (path, "procedural", None)
        else:
            for k in row["keys"]:
                slots[k["frame"]] = (k["path"], "authored-key", k["phase"])
            for job in (j for j in jobs if j["direction"] == direction):
                decoded = root / "evidence/api" / job["id"] / "decode.json"
                P.require(decoded.exists(), f"Missing inbetweens: {job['id']}")
                proof = P.load(decoded)
                for index, expected in enumerate(proof["raw_sha256"]):
                    p = decoded.parent / "raw" / f"frame-{index:02d}.png"
                    P.require(P.digest(p.read_bytes()) == expected, "Provider output changed")
                for slot, raw_index in zip(job["slots"], job["raw_indices"]):
                    P.require(slots[slot % count] is None, "Inbetween would overwrite an authored key")
                    slots[slot % count] = (str((decoded.parent / "raw" / f"frame-{raw_index:02d}.png").relative_to(root)), "pixellab-inbetween", None)
        P.require(all(slots), "Sequence has missing frames")
        frames = []
        visible = []
        for i, (source, origin, phase) in enumerate(slots):
            image = read_png(root / source, size)
            target = root / "generated" / direction / f"frame-{i:02d}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            # Preserve even the source PNG bytes, not just RGBA.
            target.write_bytes((root / source).read_bytes())
            P.require(read_png(target, size).tobytes() == image.tobytes(), "RGBA changed during assembly")
            frames.append(image)
            visible.append(P.visible_digest(image))
            sheet.paste(image, (i * size[0], row_number * size[1]))
            rel = str(target.relative_to(root))
            locks[rel] = P.digest(target.read_bytes())
            records.append({"direction": direction, "index": i, "path": rel, "source": source, "origin": origin,
                            "phase": phase, "duration_ms": c["durations_ms"][i], "rect": [i * size[0], row_number * size[1], *size]})
            n = math.ceil(1024 / max(size))
            big = image.resize((size[0] * n, size[1] * n), Image.Resampling.NEAREST)
            review = Image.new("RGBA", big.size, (37, 46, 60, 255)); review.alpha_composite(big)
            out = root / "evidence/review" / direction / f"frame-{i:02d}.png"
            out.parent.mkdir(parents=True, exist_ok=True); review.save(out)
        repeats = [[i, j] for i in range(count) for j in range(i + 1, count) if visible[i] == visible[j]]
        allowed = c.get("allowed_repeated_frame_pairs", [])
        P.require(all(pair in allowed for pair in repeats), f"Unexpected repeated frames in {direction}: {repeats}")
        for label, multiplier in [("normal", 1), ("slow", c.get("slow_multiplier", 3))]:
            durations = list(c["durations_ms"])
            if not c["loop"]:
                durations[-1] += c.get("final_hold_ms", 700)
            durations = [n * multiplier for n in durations]
            apng = root / "generated" / f"{direction}-{label}.png"
            frames[0].save(apng, save_all=True, append_images=frames[1:], duration=durations, loop=0 if c["loop"] else 1, disposal=0, blend=0)
            with Image.open(apng) as anim:
                P.require(anim.n_frames == count, "APNG merged repeated adjacent frames")
                for i, expected in enumerate(frames):
                    anim.seek(i)
                    P.require(anim.convert("RGBA").tobytes() == expected.tobytes() and anim.info["duration"] == durations[i], "APNG pixels/timing differ")
        diagnostics.append({"direction": direction, "frames": count, "authored_keys": sum(x[1] == "authored-key" for x in slots),
                            "inbetweens": sum(x[1] == "pixellab-inbetween" for x in slots), "repeated_pairs": repeats})
    sheet.save(root / "generated/sheet.png")
    manifest = {"schema_version": 2, "action": c["action"], "route": c["route"], "native_size": size, "frame_count": count,
                "direction_order": [r["direction"] for r in rows], "requested_direction_order": requested,
                "complete": len(rows) == len(c["directions"]), "durations_ms": c["durations_ms"], "loop": c["loop"],
                "pivot": c["pivot"], "ppu": c["ppu"], "frames": records, "production_approved": False}
    P.save(root / "generated/manifest.json", manifest)  # functional metadata, no digest inventory
    P.save(root / "evidence/output-lock.json", locks)
    P.save(root / "evidence/audit.json", {"integrity_pass": True, "complete": manifest["complete"],
             "requested_directions": requested, "verified_directions": [r["direction"] for r in rows],
             "keys_exact": True, "provider_pixels_exact": True,
             "directions": diagnostics, "visual_verdict": "awaiting-visual-review", "production_approved": False})
    return {"frames": len(records), "directions": len(rows), "complete": manifest["complete"], "route": c["route"], "production_approved": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--contract", required=True); p.add_argument("--root", required=True)
    p = sub.add_parser("run"); p.add_argument("--root", required=True); p.add_argument("--credential-file"); p.add_argument("--max-new-jobs", type=int)
    p = sub.add_parser("assemble"); p.add_argument("--root", required=True); p.add_argument("--direction", action="append")
    args = ap.parse_args()
    if args.command == "prepare": result = prepare(args.contract, args.root)
    elif args.command == "run": result = run(args.root, P.PixelLab(args.credential_file), args.max_new_jobs)
    else: result = assemble(args.root, args.direction)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
