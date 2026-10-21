#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=11,<14"]
# ///
"""Package complete procedural or authored pixel-action frames offline.

Controllers remain task-owned. This helper does not infer motion from flat
images, call a model, or fill missing geometry. MIT License; (c) 2026 qiulinfan.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image

DIRECTIONS = ("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_png(path, size):
    with Image.open(io.BytesIO(Path(path).read_bytes())) as opened:
        require(opened.format == "PNG" and opened.n_frames == 1, f"One native PNG per frame required: {path}")
        image = opened.convert("RGBA")
    require(list(image.size) == size, f"Native size differs: {path}")
    alpha = image.getchannel("A")
    require(set(alpha.tobytes()) == {0, 255}, f"Transparent binary Alpha required: {path}")
    require(alpha.getbbox() is not None, f"Empty frame: {path}")
    return image


def prepare(contract_path, root):
    contract_path, root = Path(contract_path).resolve(), Path(root).resolve()
    c = load(contract_path)
    require(c.get("schema_version") == 3, "Offline action contract schema_version must be3")
    require(c.get("route") in {"procedural", "authored"}, "Declare procedural or authored route")
    for key in ("action", "controller_or_pose_authority", "reference_family"):
        require(isinstance(c.get(key), str) and c[key].strip(), f"Declare {key}")
    require(not any(k in c for k in ("budget", "budget_file", "model", "credential_file")), "Model/budget contracts are not part of this offline workflow")
    size, count = c.get("image_size"), c.get("frame_count")
    require(isinstance(size, list) and len(size) == 2 and all(type(n) is int and 1 <= n <= 256 for n in size), "Declare native size <=256")
    require(type(count) is int and 2 <= count <= 128 and type(c.get("loop")) is bool, "Declare frame count and loop policy")
    durations = c.get("durations_ms", [c.get("frame_ms")] * count)
    require(isinstance(durations, list) and len(durations) == count and all(type(n) is int and n > 0 for n in durations), "Positive per-frame timing required")
    pivot = c.get("pivot", [])
    require(isinstance(pivot, list) and len(pivot) == 2 and all(type(n) in (int, float) and math.isfinite(n) and 0 <= n <= side for n, side in zip(pivot, size)), "Declare a finite pixel-space pivot inside the canvas")
    ppu = c.get("ppu")
    require(isinstance(ppu, str) and ppu.strip() or type(ppu) in (int, float) and math.isfinite(ppu) and ppu > 0, "Declare PPU or a matching asset family")
    require(type(c.get("slow_multiplier", 3)) is int and c.get("slow_multiplier", 3) > 0, "Positive slow multiplier required")
    require(type(c.get("final_hold_ms", 700)) is int and c.get("final_hold_ms", 700) >= 0, "Final hold cannot be negative")
    cap = c.get("palette_max_colors")
    require(cap is None or type(cap) is int and cap > 0, "Palette cap must be null or a positive integer")
    rows = c.get("directions", [])
    require(isinstance(rows, list) and rows and all(isinstance(r, dict) and r.get("direction") in DIRECTIONS for r in rows), "Declare known directions")
    require(len({r["direction"] for r in rows}) == len(rows), "Directions must be unique")
    pairs = c.get("allowed_repeated_frame_pairs", [])
    require(isinstance(pairs, list) and all(isinstance(p, list) and len(p) == 2 and all(type(i) is int for i in p) and 0 <= p[0] < p[1] < count for p in pairs), "Declare valid repeated-frame index pairs")
    require(not root.exists(), "Use a fresh output root")
    # Complete native frames must exist before a workspace is created.
    for row in rows:
        frames = row.get("frames", [])
        require(isinstance(frames, list) and len(frames) == count, "Supply every final frame; render missing poses with the controller or author them first")
        for f in frames:
            require(isinstance(f, dict) and isinstance(f.get("path"), str) and f["path"] and isinstance(f.get("phase"), str) and f["phase"].strip(), "Every frame needs its path and planned phase")
            f.setdefault("origin", "procedural" if c["route"] == "procedural" else "authored-key")
            require(f["origin"] in {"procedural", "authored-key"}, "Unknown frame origin")
            read_png(contract_path.parent / f["path"], size)
    root.mkdir(parents=True)
    c["durations_ms"] = durations
    locks = {}
    for row in rows:
        for i, f in enumerate(row["frames"]):
            target = root / "inputs" / row["direction"] / f"{i:02d}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((contract_path.parent / f["path"]).read_bytes())
            f["path"] = str(target.relative_to(root))
            locks[f["path"]] = digest(target.read_bytes())
    save(root / "contract.json", c)
    save(root / "evidence/input-lock.json", {"contract_sha256": digest((root / "contract.json").read_bytes()), "inputs": locks})
    return {"directions": len(rows), "frames": count * len(rows), "route": c["route"]}


def check_inputs(root):
    root = Path(root)
    lock = load(root / "evidence/input-lock.json")
    require(digest((root / "contract.json").read_bytes()) == lock["contract_sha256"], "Prepared contract changed; use a fresh version")
    for path, expected in lock["inputs"].items():
        require(digest((root / path).read_bytes()) == expected, "Prepared input changed; use a fresh version")


def assemble(root):
    root = Path(root).resolve()
    check_inputs(root)
    c = load(root / "contract.json")
    size, count = c["image_size"], c["frame_count"]
    sheet = Image.new("RGBA", (size[0] * count, size[1] * len(c["directions"])))
    records, locks, colors = [], {}, set()
    for row_number, row in enumerate(c["directions"]):
        direction = row["direction"]
        frames = [read_png(root / f["path"], size) for f in row["frames"]]
        visible = [digest(Image.alpha_composite(Image.new("RGBA", image.size), image).tobytes()) for image in frames]
        repeats = [[i, j] for i in range(count) for j in range(i + 1, count) if visible[i] == visible[j]]
        require(all(j > i + 1 for i, j in repeats), "Use frame duration for adjacent held poses instead of duplicate PNG frames")
        require(all(pair in c.get("allowed_repeated_frame_pairs", []) for pair in repeats), f"Unexpected repeated frames in {direction}: {repeats}")
        for i, (f, image) in enumerate(zip(row["frames"], frames)):
            target = root / "generated" / direction / f"frame-{i:02d}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((root / f["path"]).read_bytes())
            require(target.read_bytes() == (root / f["path"]).read_bytes(), "Source PNG changed")
            sheet.paste(image, (i * size[0], row_number * size[1]))
            colors.update(pixel[:3] for _, pixel in image.getcolors(maxcolors=size[0] * size[1]) if pixel[3])
            rel = str(target.relative_to(root))
            locks[rel] = digest(target.read_bytes())
            records.append({"direction": direction, "index": i, "path": rel, "source": f["path"], "origin": f["origin"], "phase": f["phase"], "duration_ms": c["durations_ms"][i], "rect": [i * size[0], row_number * size[1], *size]})
            scale = math.ceil(1024 / max(size))
            enlarged = image.resize((size[0] * scale, size[1] * scale), Image.Resampling.NEAREST)
            review = Image.new("RGBA", enlarged.size, (37, 46, 60, 255))
            review.alpha_composite(enlarged)
            path = root / "evidence/review" / direction / f"frame-{i:02d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            review.save(path)
        for label, multiplier in (("normal", 1), ("slow", c.get("slow_multiplier", 3))):
            durations = list(c["durations_ms"])
            if not c["loop"]:
                durations[-1] += c.get("final_hold_ms", 700)
            durations = [d * multiplier for d in durations]
            path = root / "generated" / f"{direction}-{label}.png"
            frames[0].save(path, save_all=True, append_images=frames[1:], duration=durations, loop=0 if c["loop"] else 1, disposal=0, blend=0)
            with Image.open(path) as anim:
                require(anim.n_frames == count and anim.info["loop"] == (0 if c["loop"] else 1), "APNG frame count or loop differs")
                for i, expected in enumerate(frames):
                    anim.seek(i)
                    require(anim.convert("RGBA").tobytes() == expected.tobytes() and anim.info["duration"] == durations[i], "APNG pixels/timing differ")
    cap = c.get("palette_max_colors")
    require(cap is None or len(colors) <= cap, "Declared palette cap exceeded")
    sheet.save(root / "generated/sheet.png")
    manifest = {"schema_version": 3, "action": c["action"], "route": c["route"], "native_size": size, "frame_count": count, "direction_order": [r["direction"] for r in c["directions"]], "complete": True, "durations_ms": c["durations_ms"], "loop": c["loop"], "final_hold_ms": 0 if c["loop"] else c.get("final_hold_ms", 700), "pivot": c["pivot"], "ppu": c["ppu"], "reference_family": c["reference_family"], "controller_or_pose_authority": c["controller_or_pose_authority"], "frames": records, "production_approved": False}
    save(root / "generated/manifest.json", manifest)
    save(root / "evidence/output-lock.json", locks)
    save(root / "evidence/audit.json", {"integrity_pass": True, "source_pngs_exact": True, "complete": True, "visual_verdict": "awaiting-visual-review", "production_approved": False})
    return {"frames": len(records), "directions": len(c["directions"]), "route": c["route"], "production_approved": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--contract", required=True)
    p.add_argument("--root", required=True)
    p = commands.add_parser("assemble")
    p.add_argument("--root", required=True)
    args = parser.parse_args()
    result = prepare(args.contract, args.root) if args.command == "prepare" else assemble(args.root)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
