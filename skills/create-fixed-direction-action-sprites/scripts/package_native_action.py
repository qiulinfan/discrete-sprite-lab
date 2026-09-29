#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=11,<13"]
# ///
"""Package already-authored native RGBA frames for one fixed-view action.

No anatomy inference, recoloring, resampling, registration, or motion synthesis.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

TOOL = "create-fixed-direction-action-sprites.native-package"
VERSION = "1.0.0"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def integers(value, count, label):
    require(isinstance(value, list) and len(value) == count, f"{label} needs {count} integers")
    require(all(type(x) is int for x in value), f"{label} requires integer coordinates")
    return tuple(value)


def source_path(root, value):
    require(isinstance(value, str) and value.strip(), "Image path must be a nonempty string")
    return (root / value).resolve()


def read_rgba(path, size):
    with Image.open(path) as image:
        require(image.format == "PNG", f"Native input must be PNG: {path.name}")
        require(image.mode == "RGBA", f"Native input must be RGBA: {path.name}")
        require(image.size == size, f"Wrong native frame size: {path.name}")
        result = image.copy()
    require(set(result.getchannel("A").tobytes()) <= {0, 255}, f"Partial Alpha: {path.name}")
    require(result.getbbox() is not None, f"Empty native input: {path.name}")
    return result


def colors(image):
    data = image.tobytes()
    return {tuple(data[i:i+3]) for i in range(0, len(data), 4) if data[i+3]}


def visible_digest(image):
    data = image.tobytes()
    # Comparison only: keep stored RGBA intact, including transparent-cell colors.
    visible = b"".join(data[i:i+4] if data[i+3] else bytes(4) for i in range(0, len(data), 4))
    return digest(visible)


def png_data(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def checker(size):
    result = Image.new("RGB", size, (55, 61, 72))
    draw = ImageDraw.Draw(result)
    for y in range(0, size[1], 8):
        for x in range(0, size[0], 8):
            if (x // 8 + y // 8) % 2:
                draw.rectangle((x, y, x+7, y+7), fill=(70, 76, 87))
    return result


def rendered(frame, scale):
    size = (frame.width * scale, frame.height * scale)
    enlarged = frame.resize(size, Image.Resampling.NEAREST)
    result = checker(size)
    result.paste(enlarged, (0, 0), enlarged)
    return result


def gif_data(frames, durations, loop):
    combined = Image.new("RGB", (frames[0].width, frames[0].height * len(frames)))
    for index, frame in enumerate(frames):
        combined.paste(frame, (0, index * frame.height))
    carrier = Image.new("P", (1, 1))
    carrier.putpalette(combined.quantize(colors=256).getpalette())
    encoded = [frame.quantize(palette=carrier, dither=Image.Dither.NONE) for frame in frames]
    buffer = io.BytesIO()
    options = {"loop": 0} if loop else {}
    encoded[0].save(buffer, format="GIF", save_all=True, append_images=encoded[1:],
                    duration=durations, disposal=2, optimize=False, **options)
    data = buffer.getvalue()
    with Image.open(io.BytesIO(data)) as decoded:
        require(decoded.n_frames == len(frames), "GIF collapsed distinct declared frames")
        require(decoded.info.get("loop") == (0 if loop else None), "GIF loop mismatch")
        for index, frame in enumerate(frames):
            decoded.seek(index)
            require(decoded.info.get("duration") == durations[index], "GIF timing mismatch")
            require(decoded.convert("RGB").tobytes() == frame.tobytes(), "GIF changed native colors")
    return data


def load_review(path, sheet_hash, animation_hash, records):
    if path is None:
        return {"status": "missing", "verdict": None, "user_approval": "pending"}
    review = json.loads(path.read_text())
    require(isinstance(review, dict), "Review must be an object")
    require(review.get("schema_version") == 1, "Review requires schema_version 1")
    require(review.get("artifact_sheet_sha256") == sheet_hash, "Visual review is stale: sheet changed")
    require(review.get("animation_sha256") == animation_hash, "Visual review is stale: timing or contract changed")
    verdict = review.get("verdict")
    require(verdict in {"pass", "fail", "candidate-with-warnings"}, "Invalid visual review verdict")
    if verdict != "fail":
        stages = review.get("stages", {})
        require(isinstance(stages, dict), "Review stages must be an object")
        require(all(isinstance(stages.get(name), dict) and stages[name].get("verdict") == "pass" for name in
                    ["native_master", "logical_frames", "loop"]), "Review lacks native/master/frame/loop stages")
        require(stages["logical_frames"].get("reviewed_frame_count") == len(records), "Review has incomplete frame coverage")
        expected = {record["phase_id"]: record["rgba_sha256"] for record in records}
        reviewed = review.get("reviewed_frames", [])
        require(isinstance(reviewed, list) and all(isinstance(item, dict) for item in reviewed),
                "reviewed_frames must be a list of records")
        require(len(reviewed) == len(records) and
                {item.get("phase_id"): item.get("rgba_sha256") for item in reviewed} == expected,
                "Review lacks current individual frame hashes")
        require(stages["loop"].get("normal_and_slow") is True, "Review must cover normal and slow playback")
        if verdict == "candidate-with-warnings":
            require(isinstance(review.get("warnings"), list) and
                    all(isinstance(value, str) and value.strip() for value in review["warnings"]) and
                    bool(review["warnings"]), "A warning verdict needs explicit remaining concerns")
    # A subjective review never grants engine integration or changes source pixels.
    return {"status": "provided", "verdict": verdict, "warnings": review.get("warnings", []),
            "review_sha256": digest(path.read_bytes()), "user_approval": "pending"}


def package(contract_path, output_root, review_path=None):
    contract_path = Path(contract_path).resolve()
    root = contract_path.parent
    contract = json.loads(contract_path.read_text())
    require(isinstance(contract, dict), "Contract must be an object")
    require(contract.get("schema_version") == 1, "Contract requires schema_version 1")
    slug = contract.get("artifact_slug", "")
    require(isinstance(slug, str) and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug), "Invalid artifact_slug")
    direction = contract.get("direction")
    require(isinstance(direction, str) and direction.strip() and "," not in direction, "Declare one fixed direction")
    action = contract.get("action")
    require(isinstance(action, str) and action.strip(), "Declare one action")
    size = integers(contract.get("frame_size"), 2, "frame_size")
    require(min(size) > 0, "Frame dimensions must be positive")
    origin = integers(contract.get("body_origin_px"), 2, "body_origin_px")
    require(0 <= origin[0] < size[0] and 0 <= origin[1] < size[1], "Body origin is outside canvas")
    loop = contract.get("loop", True)
    require(type(loop) is bool, "loop must be boolean")
    slow = contract.get("slow_factor", 3)
    require(type(slow) is int and slow >= 2, "slow_factor must be an integer of at least 2")
    review_min = contract.get("review_min_px", 1024)
    require(type(review_min) is int and review_min >= 1024, "review_min_px must be an integer of at least 1024")
    limit = contract.get("max_colors", 32)
    require(type(limit) is int and 1 <= limit <= 254, "GIF previews require at most 254 art colors")
    palette = contract.get("palette_rgb")
    if palette is not None:
        require(isinstance(palette, list), "palette_rgb must be a list")
        palette = {integers(value, 3, "palette_rgb") for value in palette}
        require(all(0 <= value <= 255 for rgb in palette for value in rgb), "Invalid palette channel")
        require(len(palette) <= limit, "Palette exceeds max_colors")
    master_path = source_path(root, contract.get("master"))
    master = read_rgba(master_path, size)
    regions = contract.get("stable_regions", [])
    require(isinstance(regions, list), "stable_regions must be a list")
    require(all(isinstance(region, dict) and isinstance(region.get("id"), str) and
                region["id"].strip() for region in regions), "Stable regions need named records")
    require(len({region["id"] for region in regions}) == len(regions), "Duplicate stable region ids")
    for region in regions:
        x0, y0, x1, y1 = integers(region.get("rect"), 4, "stable region rect")
        require(0 <= x0 < x1 <= size[0] and 0 <= y0 < y1 <= size[1], "Stable region outside master")
    items = contract.get("frames", [])
    require(isinstance(items, list) and len(items) >= 2, "An action needs at least two frames")
    frames, records, inputs, identity = [], [], [], []
    union = set()
    padding = contract.get("padding_px", 0)
    require(type(padding) is int and padding >= 0, "padding_px must be nonnegative")
    for index, item in enumerate(items):
        require(isinstance(item, dict), "Each frame must be a record")
        require(item.get("direction", direction) == direction, "Mixed directions in one native action")
        phase = item.get("phase_id")
        require(isinstance(phase, str) and phase.strip(), "Each frame needs a semantic phase_id")
        duration = item.get("duration_ms")
        require(type(duration) is int and duration > 0 and duration % 10 == 0,
                "Exact GIF review timings need positive multiples of 10ms; preserve other timing with another exporter")
        offset = integers(item.get("body_offset"), 2, "body_offset")
        require(0 <= origin[0]+offset[0] < size[0] and 0 <= origin[1]+offset[1] < size[1],
                f"Body origin is outside frame: {phase}")
        path = source_path(root, item.get("path"))
        frame = read_rgba(path, size)
        box = frame.getbbox()
        require(box[0] >= padding and box[1] >= padding and box[2] <= size[0]-padding and
                box[3] <= size[1]-padding, f"Frame violates declared padding: {phase}")
        union.update(colors(frame))
        for region in regions:
            x0, y0, x1, y1 = region["rect"]
            dx, dy = offset
            target = (x0+dx, y0+dy, x1+dx, y1+dy)
            require(0 <= target[0] < target[2] <= size[0] and 0 <= target[1] < target[3] <= size[1],
                    f"Shifted identity region outside canvas: {phase}")
            require(master.crop(region["rect"]).tobytes() == frame.crop(target).tobytes(),
                    f"Stable identity mismatch, including transparent footprint: {phase}/{region['id']}")
            identity.append({"phase_id": phase, "region": region["id"], "mismatched_cells": 0})
        frames.append(frame)
        inputs.append(path)
        records.append({"phase_id": phase, "direction": direction, "duration_ms": duration,
                        "body_offset": list(offset), "path": f"frames/frame-{index:02d}.png",
                        "source_sha256": digest(path.read_bytes()), "rgba_sha256": digest(frame.tobytes())})
    require(len({item["phase_id"] for item in records}) == len(records), "Duplicate phase ids")
    require(len({visible_digest(frame) for frame in frames}) == len(frames), "Duplicate visible frames; use a duration for intentional holds")
    require(len(union) <= limit and (palette is None or union <= palette), "Frame palette violation")
    sheet = Image.new("RGBA", (size[0]*len(frames), size[1]))
    for index, frame in enumerate(frames):
        sheet.paste(frame, (index*size[0], 0))
    sheet_bytes = png_data(sheet)
    signature = {"direction": direction, "action": contract.get("action"), "frame_size": size,
                 "body_origin_px": origin, "master_rgba_sha256": digest(master.tobytes()),
                 "stable_regions": regions, "loop": loop, "slow_factor": slow,
                 "frames": [{key: value for key, value in item.items() if key not in {"path", "source_sha256"}}
                            for item in records]}
    animation_hash = digest(json.dumps(signature, sort_keys=True, separators=(",", ":")).encode())
    review_path = Path(review_path).resolve() if review_path else None
    review = load_review(review_path,
                         digest(sheet_bytes), animation_hash, records)
    review_bytes = review_path.read_bytes() if review_path else None
    previews = [rendered(frame, 4) for frame in frames]
    durations = [item["duration_ms"] for item in records]
    normal = gif_data(previews, durations, loop)
    slow_gif = gif_data(previews, [ms*slow for ms in durations], loop)
    scale = math.ceil(review_min / max(size))
    output_root = Path(output_root).resolve()
    for name in ["source", "frames", "generated", "evidence/review"]:
        (output_root/name).mkdir(parents=True, exist_ok=True)
    destination = output_root/"source/master.png"
    if master_path != destination:
        shutil.copyfile(master_path, destination)
    for index, (path, frame) in enumerate(zip(inputs, frames)):
        destination = output_root/records[index]["path"]
        if path != destination:
            shutil.copyfile(path, destination)
        rendered(frame, scale).save(output_root/f"evidence/review/frame-{index:02d}.png")
    (output_root/f"generated/{slug}.png").write_bytes(sheet_bytes)
    (output_root/f"evidence/{slug}-normal.gif").write_bytes(normal)
    (output_root/f"evidence/{slug}-slow.gif").write_bytes(slow_gif)
    verdict = review["verdict"] or "awaiting-visual-review"
    manifest = {"schema_version": 1, "tool": TOOL, "tool_version": VERSION, "mode": "native",
                "direction": direction, "action": contract.get("action"), "frame_size": list(size),
                "body_origin_px": list(origin), "sheet_path": f"generated/{slug}.png",
                "sheet_sha256": digest(sheet_bytes), "animation_sha256": animation_hash,
                "palette_rgb": sorted(union), "frames": records,
                "processing": {"native_resampling": False, "automatic_registration": False,
                               "palette_remapping": False, "recovery_grid_policy": "not-applicable"}}
    audit = {"schema_version": 1, "technical_verdict": "pass", "visual_review": review,
             "verdict": verdict, "identity_regions": identity, "frame_count": len(frames),
             "normal_preview_sha256": digest(normal), "slow_preview_sha256": digest(slow_gif),
             "exact_gif_pixels_timing_loop": True, "user_approval": "pending", "engine_import": "separate-authorized-work"}
    template = {"schema_version": 1, "artifact_sheet_sha256": digest(sheet_bytes),
                "animation_sha256": animation_hash, "verdict": "pending", "warnings": [],
                "reviewed_frames": [{"phase_id": item["phase_id"], "rgba_sha256": item["rgba_sha256"]} for item in records],
                "stages": {"native_master": {"verdict": "pending"},
                           "logical_frames": {"verdict": "pending", "reviewed_frame_count": len(frames)},
                           "loop": {"verdict": "pending", "normal_and_slow": False}},
                "user_approval": "pending"}
    for path, payload in [(f"generated/{slug}.json", manifest),
                          (f"generated/{slug}-audit.json", audit),
                          ("evidence/visual-review-template.json", template)]:
        (output_root/path).write_text(json.dumps(payload, indent=2) + "\n")
    if review_bytes is not None:
        (output_root/"evidence/visual-review.json").write_bytes(review_bytes)
    return manifest, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--visual-review", type=Path)
    args = parser.parse_args()
    try:
        manifest, audit = package(args.contract, args.output_root, args.visual_review)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Native packaging failed: {error}\n")
    print(json.dumps({"sheet": manifest["sheet_path"], "technical_verdict": audit["technical_verdict"],
                      "verdict": audit["verdict"]}))
    return int(audit["verdict"] == "fail")


if __name__ == "__main__":
    raise SystemExit(main())
