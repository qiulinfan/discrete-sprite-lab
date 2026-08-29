#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy>=2,<3",
#   "pillow>=11,<13",
#   "perfect-pixel==0.1.4",
# ]
# ///
"""Build and audit one fixed-direction temporal pixel animation cycle."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps


TOOL = "create-fixed-direction-action-sprites.build"
VERSION = "3.4.0"


def local_file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def load_turnaround_primitives(skill_root: Path | None):
    root = skill_root.resolve() if skill_root else Path(__file__).resolve().parents[2] / "create-topdown-8dir-sprites"
    script = root / "scripts/build_topdown_8dir.py"
    if not script.is_file():
        raise FileNotFoundError(f"Missing referenced turnaround Skill script: {script}")
    spec = importlib.util.spec_from_file_location("turnaround_primitives", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load referenced turnaround Skill script: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    required = (
        "extract_background",
        "calibrate_grid",
        "place_one_to_one",
        "apply_canonical_palette",
        "alpha_bbox",
        "landmark_metrics",
        "file_sha256",
        "rgba_sha256",
        "checkerboard",
    )
    missing = [name for name in required if not hasattr(module, name)]
    if missing:
        raise RuntimeError(f"Referenced turnaround Skill lacks required primitives: {', '.join(missing)}")
    return module, root


def parse_int_list(raw: str, expected: int, label: str) -> list[int]:
    values = [int(value.strip()) for value in raw.split(",") if value.strip()]
    if len(values) != expected:
        raise ValueError(f"{label} requires exactly {expected} comma-separated values")
    return values


def parse_phase_ids(raw: str, frame_count: int) -> list[str]:
    if not raw:
        return [f"frame-{index:02}" for index in range(frame_count)]
    values = [value.strip() for value in raw.split(",") if value.strip()]
    if len(values) != frame_count:
        raise ValueError(f"--phase-ids requires exactly {frame_count} values")
    if len(set(values)) != len(values):
        raise ValueError("--phase-ids values must be unique")
    return values


def parse_grid_overrides(raw: str, frame_count: int) -> dict[int, int]:
    overrides: dict[int, int] = {}
    if not raw:
        return overrides
    for item in raw.split(","):
        key, separator, value = item.partition("=")
        if not separator:
            raise ValueError(f"Invalid --grid-overrides item: {item}")
        index = int(key)
        grid = int(value)
        if not 0 <= index < frame_count:
            raise ValueError(f"Frame override index out of bounds: {index}")
        if not 16 <= grid <= 256:
            raise ValueError(f"Grid override out of bounds for frame {index}: {grid}")
        overrides[index] = grid
    return overrides


def assess_recovery_grid_policy(
    refined_grids: list[tuple[int, int]], require_shared: bool
) -> dict:
    valid = bool(refined_grids) and all(width > 0 and height > 0 for width, height in refined_grids)
    shared = valid and len(set(refined_grids)) == 1
    mode = "shared-required" if require_shared else "recorded-per-frame"
    return {
        "mode": mode,
        "shared": shared,
        "valid": valid,
        "satisfied": valid and (shared or not require_shared),
    }


def parse_index_pairs(raw: str, frame_count: int, label: str) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    if not raw:
        return pairs
    seen: set[int] = set()
    for item in raw.split(","):
        left, separator, right = item.partition(":")
        if not separator:
            raise ValueError(f"Invalid {label} item: {item}")
        source, target = int(left), int(right)
        if not 0 <= source < frame_count or not 0 <= target < frame_count:
            raise ValueError(f"{label} index out of bounds: {item}")
        if source == target:
            raise ValueError(f"{label} cannot pair a frame with itself: {item}")
        if source in seen or target in seen:
            raise ValueError(f"{label} reuses a frame index: {item}")
        seen.update((source, target))
        pairs.append((source, target))
    return pairs


def parse_offsets(raw: str, frame_count: int) -> list[tuple[int, int]]:
    if not raw:
        return [(0, 0)] * frame_count
    values: list[tuple[int, int]] = []
    for item in raw.split(";"):
        left, separator, right = item.partition(":")
        if not separator:
            raise ValueError(f"Invalid --identity-offsets item: {item}")
        values.append((int(left), int(right)))
    if len(values) != frame_count:
        raise ValueError(f"--identity-offsets requires exactly {frame_count} x:y values")
    return values


def translate_rgba(image: Image.Image, offset: tuple[int, int]) -> Image.Image:
    dx, dy = offset
    source = image.convert("RGBA")
    output = Image.new("RGBA", source.size, (0, 0, 0, 0))
    source_x = max(0, -dx)
    source_y = max(0, -dy)
    destination_x = max(0, dx)
    destination_y = max(0, dy)
    width = min(source.width - source_x, source.width - destination_x)
    height = min(source.height - source_y, source.height - destination_y)
    if width > 0 and height > 0:
        crop = source.crop((source_x, source_y, source_x + width, source_y + height))
        output.alpha_composite(crop, (destination_x, destination_y))
    return output


def load_identity_mask(path: Path, frame_size: int) -> np.ndarray:
    image = Image.open(path)
    if image.size != (frame_size, frame_size):
        raise ValueError(f"Identity mask must be {frame_size}x{frame_size}, got {image.size}")
    if "A" in image.getbands() and image.getchannel("A").getextrema()[0] < 255:
        values = np.asarray(image.getchannel("A"), dtype=np.uint8)
    else:
        values = np.asarray(image.convert("L"), dtype=np.uint8)
    mask = values > 0
    if not mask.any():
        raise ValueError("Identity mask has no selected pixels")
    return mask


def apply_identity_lock(
    frame: Image.Image,
    gold: Image.Image,
    identity_mask: np.ndarray,
    offset: tuple[int, int],
) -> Image.Image:
    output = np.array(frame.convert("RGBA"), dtype=np.uint8)
    shifted_gold = np.asarray(translate_rgba(gold, offset), dtype=np.uint8)
    output[identity_mask] = shifted_gold[identity_mask]
    output[..., 3] = np.where(output[..., 3] > 0, 255, 0).astype(np.uint8)
    output[output[..., 3] == 0, :3] = 0
    return Image.fromarray(output, "RGBA")


def identity_lock_record(
    frame: Image.Image,
    gold: Image.Image,
    identity_mask: np.ndarray,
    offset: tuple[int, int],
    frame_index: int,
) -> dict:
    pixels = np.asarray(frame.convert("RGBA"), dtype=np.uint8)
    expected = np.asarray(translate_rgba(gold, offset), dtype=np.uint8)
    mismatch = np.any(pixels != expected, axis=2) & identity_mask
    selected = int(identity_mask.sum())
    return {
        "frame_index": frame_index,
        "offset": list(offset),
        "selected_pixels": selected,
        "mismatched_pixels": int(mismatch.sum()),
        "mismatch_rate": float(mismatch.sum() / max(1, selected)),
    }


def derive_paired_motion(
    frames: list[Image.Image],
    pairs: list[tuple[int, int]],
    gold: Image.Image,
    identity_mask: np.ndarray,
    offsets: list[tuple[int, int]],
) -> list[Image.Image]:
    output = [frame.copy() for frame in frames]
    for source, target in pairs:
        mirrored = ImageOps.mirror(output[source])
        output[target] = apply_identity_lock(mirrored, gold, identity_mask, offsets[target])
    return output


def pair_ratio(first: float, second: float) -> float:
    if first == 0 and second == 0:
        return 1.0
    if min(first, second) <= 0:
        return float("inf")
    return max(first, second) / min(first, second)


def place_action_one_to_one(
    image: Image.Image,
    frame_size: int,
    target_bottom: int,
    axis_mode: str,
    primitives,
) -> tuple[Image.Image, dict]:
    bbox = primitives.alpha_bbox(image)
    crop = image.crop(bbox).convert("RGBA")
    if crop.width > frame_size or crop.height > frame_size:
        raise ValueError(
            f"Recovered sprite {crop.size} does not fit {frame_size}x{frame_size} without scaling"
        )
    landmarks = primitives.landmark_metrics(crop)
    if axis_mode == "foot":
        source_axis = landmarks["feet"]["extent_mid_x"]
    else:
        source_axis = (
            landmarks["head"]["extent_mid_x"] + landmarks["torso"]["extent_mid_x"]
        ) / 2
    target_axis = (frame_size - 1) / 2
    x = round(target_axis - source_axis)
    y = target_bottom - crop.height
    if x < 0 or x + crop.width > frame_size or y < 0 or target_bottom > frame_size:
        raise ValueError(
            f"Recovered sprite {crop.size} cannot align {axis_mode} axis to {target_axis} "
            f"at bottom {target_bottom} without scaling or clipping"
        )
    canvas = Image.new("RGBA", (frame_size, frame_size), (0, 0, 0, 0))
    canvas.alpha_composite(crop, (x, y))
    pixels = np.array(canvas, dtype=np.uint8)
    pixels[..., 3] = np.where(pixels[..., 3] > 0, 255, 0).astype(np.uint8)
    pixels[pixels[..., 3] == 0, :3] = 0
    canvas = Image.fromarray(pixels, "RGBA")
    final_landmarks = primitives.landmark_metrics(canvas)
    if axis_mode == "foot":
        final_axis = final_landmarks["feet"]["extent_mid_x"]
    else:
        final_axis = (
            final_landmarks["head"]["extent_mid_x"]
            + final_landmarks["torso"]["extent_mid_x"]
        ) / 2
    return canvas, {
        "placement_mode": "one-to-one",
        "axis_mode": axis_mode,
        "recovered_crop_size": [crop.width, crop.height],
        "position": [x, y],
        "final_alpha_bbox": list(primitives.alpha_bbox(canvas)),
        "source_axis_x": source_axis,
        "target_axis_x": target_axis,
        "final_axis_x": final_axis,
        "source_landmarks": landmarks,
        "final_landmarks": final_landmarks,
        "resampled_after_recovery": False,
    }


def palette_histogram(frame: Image.Image, palette: list[list[int]]) -> np.ndarray:
    palette_index = {tuple(color): index for index, color in enumerate(palette)}
    pixels = np.asarray(frame.convert("RGBA"), dtype=np.uint8)
    mask = pixels[..., 3] > 0
    colors, counts = np.unique(pixels[..., :3][mask], axis=0, return_counts=True)
    histogram = np.zeros(len(palette), dtype=np.float64)
    for color, count in zip(colors, counts):
        histogram[palette_index[tuple(map(int, color))]] = count
    histogram /= histogram.sum()
    return histogram


def temporal_metrics(
    frames: list[Image.Image],
    phase_ids: list[str],
    palette: list[list[int]],
    primitives,
    identity_mask: np.ndarray | None = None,
) -> dict:
    frame_records = []
    histograms = []
    masks = []
    for phase_id, frame in zip(phase_ids, frames):
        metrics = primitives.landmark_metrics(frame)
        metrics["phase_id"] = phase_id
        pixels = np.asarray(frame.convert("RGBA"), dtype=np.uint8)
        mask = pixels[..., 3] > 0
        masks.append(mask)
        histogram = palette_histogram(frame, palette)
        histograms.append(histogram)
        metrics["unique_palette_colors"] = int((histogram > 0).sum())
        if identity_mask is not None:
            locked_y, locked_x = np.where(mask & identity_mask)
            if not len(locked_x):
                raise ValueError("Identity mask does not overlap visible pixels")
            metrics["identity_anchor_x"] = float(locked_x.mean())
        frame_records.append(metrics)

    transitions = []
    for index, phase_id in enumerate(phase_ids):
        next_index = (index + 1) % len(frames)
        current = frame_records[index]
        following = frame_records[next_index]
        union = masks[index] | masks[next_index]
        xor = masks[index] ^ masks[next_index]
        motion_region = ~identity_mask if identity_mask is not None else np.ones_like(union, dtype=bool)
        motion_union = union & motion_region
        motion_xor = xor & motion_region
        transitions.append(
            {
                "from": phase_id,
                "to": phase_ids[next_index],
                "cyclic_closure": next_index == 0,
                "silhouette_change": float(xor.sum() / max(1, union.sum())),
                "motion_silhouette_change": float(
                    motion_xor.sum() / max(1, motion_union.sum())
                ),
                "head_anchor_dx": abs(current["head"]["centroid_x"] - following["head"]["centroid_x"]),
                "torso_anchor_dx": abs(
                    current["torso"]["centroid_x"] - following["torso"]["centroid_x"]
                ),
                "identity_anchor_dx": abs(
                    current.get("identity_anchor_x", current["torso"]["centroid_x"])
                    - following.get("identity_anchor_x", following["torso"]["centroid_x"])
                ),
                "foot_axis_dx": abs(
                    current["feet"]["extent_mid_x"] - following["feet"]["extent_mid_x"]
                ),
                "visible_height_delta": abs(current["visible_height"] - following["visible_height"]),
                "palette_total_variation": float(
                    0.5 * np.abs(histograms[index] - histograms[next_index]).sum()
                ),
            }
        )
    return {
        "schema_version": 1,
        "phase_order": phase_ids,
        "frames": frame_records,
        "transitions": transitions,
        "summary": {
            "min_silhouette_change": min(item["silhouette_change"] for item in transitions),
            "max_silhouette_change": max(item["silhouette_change"] for item in transitions),
            "closure_silhouette_change": transitions[-1]["silhouette_change"],
            "max_head_anchor_dx": max(item["head_anchor_dx"] for item in transitions),
            "max_torso_anchor_dx": max(item["torso_anchor_dx"] for item in transitions),
            "max_identity_anchor_dx": max(item["identity_anchor_dx"] for item in transitions),
            "max_foot_axis_dx": max(item["foot_axis_dx"] for item in transitions),
            "max_visible_height_delta": max(item["visible_height_delta"] for item in transitions),
            "max_palette_total_variation": max(item["palette_total_variation"] for item in transitions),
            "min_motion_silhouette_change": min(
                item["motion_silhouette_change"] for item in transitions
            ),
            "max_motion_silhouette_change": max(
                item["motion_silhouette_change"] for item in transitions
            ),
        },
    }


def paired_transition_audit(
    transitions: list[dict],
    pairs: list[tuple[int, int]],
) -> dict:
    records = []
    for first, second in pairs:
        first_value = transitions[first]["motion_silhouette_change"]
        second_value = transitions[second]["motion_silhouette_change"]
        records.append(
            {
                "transition_indices": [first, second],
                "from_to": [
                    [transitions[first]["from"], transitions[first]["to"]],
                    [transitions[second]["from"], transitions[second]["to"]],
                ],
                "motion_silhouette_change": [first_value, second_value],
                "ratio": pair_ratio(first_value, second_value),
            }
        )
    return {
        "pairs": records,
        "max_ratio": max((record["ratio"] for record in records), default=1.0),
    }


def write_previews(
    root: Path,
    slug: str,
    frames: list[Image.Image],
    metrics: dict,
    frame_size: int,
    target_bottom: int,
    duration_ms: int,
    review_min_size: int,
    checkerboard,
) -> None:
    scale = max(4, 384 // frame_size)
    display = frame_size * scale
    columns = min(4, len(frames))
    rows = (len(frames) + columns - 1) // columns
    label_height = 24
    contact = Image.new("RGB", (display * columns, (display + label_height) * rows), (24, 27, 34))
    draw = ImageDraw.Draw(contact)
    guides = contact.copy()
    guide_draw = ImageDraw.Draw(guides)
    target_axis_x = (frame_size - 1) / 2
    gif_frames = []
    review_scale = max(1, math.ceil(review_min_size / frame_size))
    review_display = frame_size * review_scale
    review_dir = root / f"evidence/{slug}-magnified-frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_records = []

    for index, (frame, frame_metrics) in enumerate(zip(frames, metrics["frames"])):
        enlarged = frame.resize((display, display), Image.Resampling.NEAREST)
        background = checkerboard((display, display), max(8, scale * 2))
        background.alpha_composite(enlarged)
        cell_x = (index % columns) * display
        cell_y = (index // columns) * (display + label_height)
        contact.paste(background.convert("RGB"), (cell_x, cell_y))
        draw.text((cell_x + 6, cell_y + display + 4), frame_metrics["phase_id"], fill=(245, 246, 250))

        guide_background = background.convert("RGB")
        guides.paste(guide_background, (cell_x, cell_y))
        axis_x = cell_x + round((target_axis_x + 0.5) * scale)
        baseline_y = cell_y + target_bottom * scale
        guide_draw.line((axis_x, cell_y, axis_x, cell_y + display - 1), fill=(244, 88, 96), width=1)
        guide_draw.line((cell_x, baseline_y, cell_x + display - 1, baseline_y), fill=(82, 218, 132), width=1)
        for region_name, color in (
            ("head", (75, 214, 255)),
            ("torso", (255, 211, 77)),
            ("feet", (229, 104, 255)),
        ):
            region = frame_metrics[region_name]
            anchor = region["extent_mid_x"] if region_name == "feet" else region["centroid_x"]
            region_bbox = region["bbox"]
            anchor_x = cell_x + round((anchor + 0.5) * scale)
            anchor_y = cell_y + round(((region_bbox[1] + region_bbox[3] - 1) / 2 + 0.5) * scale)
            radius = max(2, scale // 2)
            guide_draw.ellipse(
                (anchor_x - radius, anchor_y - radius, anchor_x + radius, anchor_y + radius),
                fill=color,
            )
        guide_draw.text((cell_x + 6, cell_y + display + 4), frame_metrics["phase_id"], fill=(245, 246, 250))

        gif_size = frame_size * 8
        gif_frame = Image.new("RGBA", (gif_size, gif_size + 28), (27, 31, 38, 255))
        gif_frame.alpha_composite(frame.resize((gif_size, gif_size), Image.Resampling.NEAREST), (0, 28))
        ImageDraw.Draw(gif_frame).text((10, 8), frame_metrics["phase_id"], fill=(245, 246, 250, 255))
        gif_frames.append(gif_frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=256))

        review_enlarged = frame.resize((review_display, review_display), Image.Resampling.NEAREST)
        review_background = checkerboard(
            (review_display, review_display), max(8, review_scale * 2)
        )
        review_background.alpha_composite(review_enlarged)
        review_path = review_dir / f"frame-{index:02}-{frame_metrics['phase_id']}-{review_scale}x.png"
        review_background.convert("RGB").save(review_path)
        grid_image = review_background.convert("RGB")
        grid_draw = ImageDraw.Draw(grid_image)
        grid_color = (102, 109, 122)
        if review_scale >= 4:
            for coordinate in range(0, review_display + 1, review_scale):
                grid_draw.line(
                    (coordinate, 0, coordinate, review_display - 1), fill=grid_color, width=1
                )
                grid_draw.line(
                    (0, coordinate, review_display - 1, coordinate), fill=grid_color, width=1
                )
        grid_path = review_dir / f"frame-{index:02}-{frame_metrics['phase_id']}-{review_scale}x-grid.png"
        grid_image.save(grid_path)
        review_records.append(
            {
                "frame_index": index,
                "phase_id": frame_metrics["phase_id"],
                "scale": review_scale,
                "size_px": [review_display, review_display],
                "resample": "nearest",
                "review": str(review_path.relative_to(root)),
                "review_sha256": local_file_sha256(review_path),
                "grid_review": str(grid_path.relative_to(root)),
                "grid_review_sha256": local_file_sha256(grid_path),
            }
        )

    contact.save(root / f"evidence/{slug}-contact.png")
    guides.save(root / f"evidence/{slug}-temporal-guides.png")
    (root / f"evidence/{slug}-magnified-review.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "minimum_requested_size_px": review_min_size,
                "frames": review_records,
            },
            indent=2,
        )
        + "\n"
    )
    gif_frames[0].save(
        root / f"evidence/{slug}.gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=False,
        disposal=2,
    )
    gif_frames[0].save(
        root / f"evidence/{slug}-slow.gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=max(350, duration_ms),
        loop=0,
        optimize=False,
        disposal=2,
    )


def load_visual_review(
    path: Path | None,
    sheet_sha256: str,
    frame_count: int,
    failed_diagnostics: list[str] | None = None,
) -> dict:
    failed_diagnostics = failed_diagnostics or []
    if path is None:
        return {
            "status": "missing",
            "verdict": None,
            "required_stages": ["high_detail", "pseudo_pixel", "logical_frames", "loop"],
            "unacknowledged_diagnostics": failed_diagnostics,
        }
    review_path = path.resolve()
    payload = json.loads(review_path.read_text())
    if payload.get("schema_version") != 1:
        raise ValueError("Visual review requires schema_version 1")
    if payload.get("artifact_sheet_sha256") != sheet_sha256:
        raise ValueError(
            "Visual review is stale: artifact_sheet_sha256 does not match the generated sheet"
        )
    verdict = payload.get("verdict")
    if verdict not in ("pass", "fail"):
        raise ValueError("Visual review verdict must be pass or fail")
    required = ("high_detail", "pseudo_pixel", "logical_frames", "loop")
    stages = payload.get("stages", {})
    diagnostic_overrides = payload.get("diagnostic_overrides", [])
    if not isinstance(diagnostic_overrides, list):
        raise ValueError("diagnostic_overrides must be a list")
    if verdict == "pass":
        missing = [stage for stage in required if stages.get(stage, {}).get("verdict") != "pass"]
        if missing:
            raise ValueError(
                "Passing visual review lacks passing stages: " + ", ".join(missing)
            )
        reviewed_frames = stages["logical_frames"].get("reviewed_frame_count")
        if reviewed_frames != frame_count:
            raise ValueError(
                f"Passing visual review must cover {frame_count} logical frames, got {reviewed_frames}"
            )
        acknowledged: set[str] = set()
        for record in diagnostic_overrides:
            diagnostic_id = record.get("id")
            if diagnostic_id not in failed_diagnostics:
                raise ValueError(
                    f"Visual review overrides an unknown or passing diagnostic: {diagnostic_id}"
                )
            if record.get("decision") != "accept":
                raise ValueError(
                    f"Diagnostic override {diagnostic_id} requires decision=accept"
                )
            if record.get("authority") not in ("user", "agent_visual_review"):
                raise ValueError(
                    f"Diagnostic override {diagnostic_id} requires user or agent_visual_review authority"
                )
            if not str(record.get("reason", "")).strip():
                raise ValueError(f"Diagnostic override {diagnostic_id} requires a reason")
            evidence = record.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                raise ValueError(f"Diagnostic override {diagnostic_id} requires evidence")
            acknowledged.add(diagnostic_id)
        missing_diagnostics = sorted(set(failed_diagnostics) - acknowledged)
        if missing_diagnostics:
            raise ValueError(
                "Passing visual review does not acknowledge failed diagnostics: "
                + ", ".join(missing_diagnostics)
            )
    return {
        "status": "provided",
        "path": str(review_path),
        "sha256": local_file_sha256(review_path),
        "verdict": verdict,
        "stages": stages,
        "diagnostic_overrides": diagnostic_overrides,
        "failures": payload.get("failures", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pseudo-dir", required=True, type=Path)
    parser.add_argument("--gold-frame", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--artifact-slug", required=True)
    parser.add_argument("--frame-count", required=True, type=int)
    parser.add_argument("--phase-ids", default="")
    parser.add_argument("--duration-ms", type=int, default=120)
    parser.add_argument("--frame-size", type=int, default=64)
    parser.add_argument("--grid", type=int, default=64)
    parser.add_argument("--grid-overrides", default="")
    parser.add_argument("--height-profile", default="")
    parser.add_argument("--target-visible-height", type=int, default=52)
    parser.add_argument("--height-tolerance", type=int, default=1)
    parser.add_argument("--target-bottom", type=int, default=61)
    parser.add_argument(
        "--placement-axis",
        choices=("body", "foot"),
        default="body",
        help="Temporal actions default to a stable head/torso axis; foot is legacy/regression mode",
    )
    parser.add_argument("--colors", type=int, default=32)
    parser.add_argument("--contact-frames", default="")
    parser.add_argument("--axis-tolerance", type=float, default=0.5)
    parser.add_argument("--min-adjacent-silhouette-change", type=float, default=0.02)
    parser.add_argument("--max-adjacent-silhouette-change", type=float, default=0.50)
    parser.add_argument("--max-adjacent-head-shift", type=float, default=2.0)
    parser.add_argument("--max-adjacent-torso-shift", type=float, default=2.0)
    parser.add_argument("--max-adjacent-palette-tv", type=float, default=0.40)
    parser.add_argument(
        "--identity-mask",
        type=Path,
        help="Legacy/regression exact-mask input; production repair uses pixel_region_workbench.py",
    )
    parser.add_argument(
        "--identity-offsets",
        default="",
        help="Semicolon-separated x:y integer offsets, one per frame",
    )
    parser.add_argument(
        "--phase-pairs",
        default="",
        help="Comma-separated source:opposite frame pairs, for example 0:3,1:4,2:5",
    )
    parser.add_argument(
        "--transition-pairs",
        default="",
        help="Comma-separated transition-index pairs used for cadence comparison",
    )
    parser.add_argument(
        "--derive-paired-motion",
        action="store_true",
        help="Regression-only raster mirroring; forbidden by the production Skill workflow",
    )
    parser.add_argument(
        "--require-shared-refined-grid",
        action="store_true",
        help=(
            "Require one identical refined-grid shape for all frames. Omit to allow "
            "evidence-backed per-frame integer recovery without post-recovery resampling."
        ),
    )
    parser.add_argument("--max-paired-transition-ratio", type=float, default=1.15)
    parser.add_argument(
        "--require-paired-transition-cadence",
        action="store_true",
        help=(
            "Promote paired-transition cadence from a visual diagnostic to a hard "
            "technical gate for contracts that explicitly require it."
        ),
    )
    parser.add_argument("--max-paired-height-delta", type=int, default=0)
    parser.add_argument("--review-min-size", type=int, default=1024)
    parser.add_argument(
        "--visual-review",
        type=Path,
        help="Explicit agent-authored visual review JSON for the current sheet hash",
    )
    parser.add_argument(
        "--logical-overrides-dir",
        type=Path,
        help="Agent-approved 64x64 local patches with frame-XX.receipt.json stale-safety evidence",
    )
    parser.add_argument("--calibration-iterations", type=int, default=3)
    parser.add_argument("--turnaround-skill-root", type=Path)
    args = parser.parse_args()

    if args.frame_count < 2:
        raise ValueError("--frame-count must be at least 2")
    if args.duration_ms < 20:
        raise ValueError("--duration-ms must be at least 20")
    if args.review_min_size < args.frame_size:
        raise ValueError("--review-min-size cannot be smaller than --frame-size")
    phase_ids = parse_phase_ids(args.phase_ids, args.frame_count)
    height_profile = (
        parse_int_list(args.height_profile, args.frame_count, "--height-profile")
        if args.height_profile
        else [args.target_visible_height] * args.frame_count
    )
    contact_frames = (
        [int(value.strip()) for value in args.contact_frames.split(",") if value.strip()]
        if args.contact_frames
        else []
    )
    if any(not 0 <= index < args.frame_count for index in contact_frames):
        raise ValueError("--contact-frames contains an out-of-range index")
    grid_overrides = parse_grid_overrides(args.grid_overrides, args.frame_count)
    identity_offsets = parse_offsets(args.identity_offsets, args.frame_count)
    phase_pairs = parse_index_pairs(args.phase_pairs, args.frame_count, "--phase-pairs")
    transition_pairs = parse_index_pairs(
        args.transition_pairs, args.frame_count, "--transition-pairs"
    )
    if args.derive_paired_motion and not phase_pairs:
        raise ValueError("--derive-paired-motion requires --phase-pairs")
    if args.derive_paired_motion and not args.identity_mask:
        raise ValueError("--derive-paired-motion requires --identity-mask")
    if args.identity_offsets and not args.identity_mask:
        raise ValueError("--identity-offsets requires --identity-mask")
    primitives, turnaround_root = load_turnaround_primitives(args.turnaround_skill_root)

    pseudo_dir = args.pseudo_dir.resolve()
    gold_path = args.gold_frame.resolve()
    root = args.output_root.resolve()
    for directory in (
        "working/source-transparent",
        "working/perfect-pixel",
        "working/placed-1to1",
        "working/identity-locked",
        "working/pre-overrides",
        "working/final-frames",
        "generated",
        "evidence",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)

    background_records = []
    placed_frames = []
    recovery_records = []
    for index, phase_id in enumerate(phase_ids):
        source = pseudo_dir / f"frame-{index:02}.png"
        if not source.is_file():
            raise FileNotFoundError(f"Missing phase source: {source}")
        transparent = root / f"working/source-transparent/frame-{index:02}.png"
        background_record = primitives.extract_background(source, transparent)
        background_record.update({"frame_index": index, "phase_id": phase_id})
        background_records.append(background_record)
        array = np.asarray(Image.open(transparent).convert("RGBA"), dtype=np.uint8)
        recovered, selected, trials = primitives.calibrate_grid(
            array=array,
            base_grid=args.grid,
            target_height=height_profile[index],
            tolerance=args.height_tolerance,
            override=grid_overrides.get(index),
            max_iterations=args.calibration_iterations,
        )
        recovered_path = root / f"working/perfect-pixel/frame-{index:02}.png"
        recovered.save(recovered_path)
        placed, placement = place_action_one_to_one(
            recovered,
            args.frame_size,
            args.target_bottom,
            args.placement_axis,
            primitives,
        )
        placed_path = root / f"working/placed-1to1/frame-{index:02}.png"
        placed.save(placed_path)
        placed_frames.append(placed)
        recovery_records.append(
            {
                "frame_index": index,
                "phase_id": phase_id,
                "target_visible_height": height_profile[index],
                "selected": selected,
                "trials": trials,
                "placement": placement,
                "source_sha256": primitives.file_sha256(source),
                "recovered_sha256": primitives.file_sha256(recovered_path),
                "placed_sha256": primitives.file_sha256(placed_path),
            }
        )
    (root / "evidence/background-extraction.json").write_text(
        json.dumps({"schema_version": 1, "records": background_records}, indent=2) + "\n"
    )
    (root / "evidence/perfect-pixel-frame-metrics.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "referenced_skill": str(turnaround_root),
                "records": recovery_records,
            },
            indent=2,
        )
        + "\n"
    )

    gold = Image.open(gold_path).convert("RGBA")
    if gold.size != (args.frame_size, args.frame_size):
        raise ValueError(f"Gold frame must be {args.frame_size}x{args.frame_size}, got {gold.size}")
    palette_inputs = [gold, *placed_frames]
    palette_outputs, palette = primitives.apply_canonical_palette(palette_inputs, args.colors, "north")
    final_frames = palette_outputs[1:]
    identity_mask = None
    identity_records: list[dict] = []
    if args.identity_mask:
        identity_mask_path = args.identity_mask.resolve()
        identity_mask = load_identity_mask(identity_mask_path, args.frame_size)
        final_frames = [
            apply_identity_lock(frame, gold, identity_mask, identity_offsets[index])
            for index, frame in enumerate(final_frames)
        ]
        if args.derive_paired_motion:
            final_frames = derive_paired_motion(
                final_frames,
                phase_pairs,
                gold,
                identity_mask,
                identity_offsets,
            )
        final_frames = [
            apply_identity_lock(frame, gold, identity_mask, identity_offsets[index])
            for index, frame in enumerate(final_frames)
        ]
        for index, frame in enumerate(final_frames):
            identity_path = root / f"working/identity-locked/frame-{index:02}.png"
            frame.save(identity_path)
            record = identity_lock_record(
                frame,
                gold,
                identity_mask,
                identity_offsets[index],
                index,
            )
            record["sha256"] = primitives.file_sha256(identity_path)
            identity_records.append(record)
        (root / "evidence/identity-lock.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "mask": str(identity_mask_path),
                    "mask_sha256": primitives.file_sha256(identity_mask_path),
                    "records": identity_records,
                },
                indent=2,
            )
            + "\n"
        )
    logical_override_records = []
    if args.logical_overrides_dir:
        overrides_root = args.logical_overrides_dir.resolve()
        for index, frame in enumerate(final_frames):
            pre_path = root / f"working/pre-overrides/frame-{index:02}.png"
            frame.save(pre_path)
            override_path = overrides_root / f"frame-{index:02}.png"
            if not override_path.is_file():
                continue
            receipt_path = overrides_root / f"frame-{index:02}.receipt.json"
            if not receipt_path.is_file():
                raise FileNotFoundError(f"Missing logical override receipt: {receipt_path}")
            receipt = json.loads(receipt_path.read_text())
            current_rgba = primitives.rgba_sha256(frame)
            if receipt.get("target_rgba_sha256") != current_rgba:
                raise ValueError(
                    f"Stale logical override frame {index}: target RGBA hash does not match"
                )
            if receipt.get("unchanged_outside_writes") is not True or receipt.get("resampling") is not False:
                raise ValueError(f"Unsafe logical override receipt for frame {index}")
            override = Image.open(override_path).convert("RGBA")
            if override.size != (args.frame_size, args.frame_size):
                raise ValueError(f"Logical override frame {index} has size {override.size}")
            override_pixels = np.asarray(override, dtype=np.uint8)
            partial = (override_pixels[..., 3] > 0) & (override_pixels[..., 3] < 255)
            if partial.any():
                raise ValueError(f"Logical override frame {index} contains partial Alpha")
            if receipt.get("output_rgba_sha256") != primitives.rgba_sha256(override):
                raise ValueError(f"Logical override output hash mismatch for frame {index}")
            final_frames[index] = override
            logical_override_records.append(
                {
                    "frame_index": index,
                    "phase_id": phase_ids[index],
                    "path": str(override_path),
                    "sha256": primitives.file_sha256(override_path),
                    "rgba_sha256": primitives.rgba_sha256(override),
                    "receipt": str(receipt_path),
                    "receipt_sha256": primitives.file_sha256(receipt_path),
                }
            )
        (root / "evidence/logical-overrides.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "source": str(overrides_root),
                    "records": logical_override_records,
                },
                indent=2,
            )
            + "\n"
        )
    temporal = temporal_metrics(final_frames, phase_ids, palette, primitives, identity_mask)
    paired_transitions = paired_transition_audit(temporal["transitions"], transition_pairs)
    temporal["paired_transitions"] = paired_transitions
    (root / "evidence/temporal-continuity.json").write_text(json.dumps(temporal, indent=2) + "\n")

    sheet = Image.new("RGBA", (args.frame_size * args.frame_count, args.frame_size), (0, 0, 0, 0))
    frame_records = []
    for index, (phase_id, frame) in enumerate(zip(phase_ids, final_frames)):
        frame_path = root / f"working/final-frames/frame-{index:02}.png"
        frame.save(frame_path)
        sheet.alpha_composite(frame, (index * args.frame_size, 0))
        frame_records.append(
            {
                "index": index,
                "phase_id": phase_id,
                "duration_ms": args.duration_ms,
                "contact_event": index in contact_frames,
                "rect_px_top_left": {
                    "x": index * args.frame_size,
                    "y": 0,
                    "width": args.frame_size,
                    "height": args.frame_size,
                },
                "pivot_px_from_bottom_left": [args.frame_size // 2, args.frame_size - args.target_bottom],
                "path": frame_path.relative_to(root).as_posix(),
                "sha256": primitives.file_sha256(frame_path),
                "rgba_sha256": primitives.rgba_sha256(frame),
                "landmarks": temporal["frames"][index],
            }
        )

    sheet_path = root / f"generated/{args.artifact_slug}.png"
    sheet.save(sheet_path)
    manifest = {
        "schema_version": 1,
        "tool": TOOL,
        "tool_version": VERSION,
        "referenced_skill": {
            "name": "create-topdown-8dir-sprites",
            "root": str(turnaround_root),
            "script_version": getattr(primitives, "VERSION", "unknown"),
        },
        "phase_order": phase_ids,
        "sheet": {
            "path": sheet_path.relative_to(root).as_posix(),
            "size_px": list(sheet.size),
            "sha256": primitives.file_sha256(sheet_path),
            "rgba_sha256": primitives.rgba_sha256(sheet),
        },
        "processing": {
            "frame_count": args.frame_count,
            "duration_ms": args.duration_ms,
            "loop": True,
            "frame_size": args.frame_size,
            "height_profile": height_profile,
            "height_tolerance": args.height_tolerance,
            "target_bottom": args.target_bottom,
            "placement_axis": args.placement_axis,
            "contact_frames": contact_frames,
            "post_recovery_resampling": False,
            "palette_gold": str(gold_path),
            "palette_mode": "approved-gold-oklab-medoid",
            "colors": args.colors,
            "alpha": "binary",
            "identity_lock": str(args.identity_mask.resolve()) if args.identity_mask else None,
            "identity_offsets": [list(offset) for offset in identity_offsets],
            "phase_pairs": [list(pair) for pair in phase_pairs],
            "transition_pairs": [list(pair) for pair in transition_pairs],
            "require_paired_transition_cadence": args.require_paired_transition_cadence,
            "derive_paired_motion": args.derive_paired_motion,
            "require_shared_refined_grid": args.require_shared_refined_grid,
            "recovery_grid_policy": (
                "shared-required"
                if args.require_shared_refined_grid
                else "recorded-per-frame"
            ),
            "review_min_size": args.review_min_size,
            "visual_review_required": True,
            "logical_overrides": logical_override_records,
        },
        "palette_rgb": palette,
        "frames": frame_records,
    }
    manifest_path = root / f"generated/{args.artifact_slug}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    write_previews(
        root,
        args.artifact_slug,
        final_frames,
        temporal,
        args.frame_size,
        args.target_bottom,
        args.duration_ms,
        args.review_min_size,
        primitives.checkerboard,
    )

    sheet_pixels = np.asarray(sheet, dtype=np.uint8)
    alpha = sheet_pixels[..., 3]
    visible_heights = [metrics["visible_height"] for metrics in temporal["frames"]]
    contacts = [metrics["alpha_bbox"][3] for metrics in temporal["frames"]]
    foot_axes = [metrics["feet"]["extent_mid_x"] for metrics in temporal["frames"]]
    placement_axes = [record["placement"]["final_axis_x"] for record in recovery_records]
    rgba_hashes = [primitives.rgba_sha256(frame) for frame in final_frames]
    summary = temporal["summary"]
    target_axis = (args.frame_size - 1) / 2
    refined_grids = [tuple(record["selected"]["refined_grid_size"]) for record in recovery_records]
    recovery_grid_policy = assess_recovery_grid_policy(
        refined_grids, args.require_shared_refined_grid
    )
    shared_refined_grid = recovery_grid_policy["shared"]
    paired_height_deltas = [
        abs(visible_heights[first] - visible_heights[second]) for first, second in phase_pairs
    ]
    max_paired_height_delta = max(paired_height_deltas, default=0)
    max_identity_mismatch_pixels = max(
        (record["mismatched_pixels"] for record in identity_records), default=0
    )
    checks = {
        "frame_count": len(final_frames) == args.frame_count,
        "sheet_size": sheet.size == (args.frame_size * args.frame_count, args.frame_size),
        "all_frames_requested_size": all(frame.size == (args.frame_size, args.frame_size) for frame in final_frames),
        "all_frames_nonempty": all(frame.getchannel("A").getbbox() for frame in final_frames),
        "binary_alpha": int(((alpha > 0) & (alpha < 255)).sum()) == 0,
        "palette_within_limit": len(np.unique(sheet_pixels[..., :3][alpha > 0], axis=0)) <= args.colors,
        "all_contacts_match": all(contact == args.target_bottom for contact in contacts),
        "height_profile_within_tolerance": all(
            abs(actual - expected) <= args.height_tolerance
            for actual, expected in zip(visible_heights, height_profile)
        ),
        "placement_axes_aligned": all(
            abs(axis - target_axis) <= args.axis_tolerance for axis in placement_axes
        ),
        "no_post_recovery_resampling": all(
            record["placement"]["resampled_after_recovery"] is False for record in recovery_records
        ),
        "no_exact_duplicate_frames": len(set(rgba_hashes)) == len(rgba_hashes),
        "adjacent_phase_change_minimum": (
            summary["min_silhouette_change"] >= args.min_adjacent_silhouette_change
        ),
        "adjacent_phase_change_bounded": (
            summary["max_silhouette_change"] <= args.max_adjacent_silhouette_change
        ),
        "adjacent_head_shift_bounded": summary["max_head_anchor_dx"] <= args.max_adjacent_head_shift,
        "adjacent_stable_anchor_shift_bounded": (
            summary[
                "max_identity_anchor_dx" if identity_mask is not None else "max_torso_anchor_dx"
            ]
            <= args.max_adjacent_torso_shift
        ),
        "adjacent_palette_transition_bounded": (
            summary["max_palette_total_variation"] <= args.max_adjacent_palette_tv
        ),
        "contact_frames_declared": len(contact_frames) > 0,
        "recovery_grid_policy_satisfied": recovery_grid_policy["satisfied"],
        "identity_lock_exact": (
            identity_mask is None or max_identity_mismatch_pixels == 0
        ),
        "paired_phase_heights_match": (
            not phase_pairs or max_paired_height_delta <= args.max_paired_height_delta
        ),
    }
    paired_transition_cadence = (
        not transition_pairs
        or paired_transitions["max_ratio"] <= args.max_paired_transition_ratio
    )
    diagnostics = {
        "paired_transition_cadence": {
            "pass": paired_transition_cadence,
            "value": paired_transitions["max_ratio"],
            "limit": args.max_paired_transition_ratio,
            "hard_required": args.require_paired_transition_cadence,
        }
    }
    if args.require_paired_transition_cadence:
        checks["paired_transition_cadence_required"] = paired_transition_cadence
    technical_verdict = "pass" if all(checks.values()) else "fail"
    failed_diagnostics = [
        name for name, record in diagnostics.items() if record["pass"] is False
    ]
    diagnostic_verdict = "pass" if not failed_diagnostics else "warn"
    sheet_sha256 = primitives.file_sha256(sheet_path)
    visual_review = load_visual_review(
        args.visual_review,
        sheet_sha256,
        args.frame_count,
        failed_diagnostics if not args.require_paired_transition_cadence else [],
    )
    if technical_verdict == "fail":
        verdict = "fail"
    elif visual_review["status"] == "missing":
        verdict = "awaiting-visual-review"
    elif visual_review["verdict"] == "pass":
        verdict = "pass"
    else:
        verdict = "fail"
    audit = {
        "schema_version": 1,
        "tool": TOOL,
        "tool_version": VERSION,
        "verdict": verdict,
        "technical_verdict": technical_verdict,
        "diagnostic_verdict": diagnostic_verdict,
        "diagnostics": diagnostics,
        "visual_review": visual_review,
        "artifact": {
            "sheet_sha256": sheet_sha256,
            "manifest_sha256": primitives.file_sha256(manifest_path),
        },
        "checks": checks,
        "facts": {
            "phase_order": phase_ids,
            "visible_heights": visible_heights,
            "contacts": contacts,
            "foot_axes": foot_axes,
            "placement_axis_mode": args.placement_axis,
            "placement_axes": placement_axes,
            "unique_frame_hashes": len(set(rgba_hashes)),
            "visible_palette_colors": int(len(np.unique(sheet_pixels[..., :3][alpha > 0], axis=0))),
            "partially_transparent_pixels": int(((alpha > 0) & (alpha < 255)).sum()),
            "temporal": summary,
            "refined_grids": [list(grid) for grid in refined_grids],
            "shared_refined_grid": shared_refined_grid,
            "recovery_grid_policy": recovery_grid_policy,
            "identity_lock": {
                "enabled": identity_mask is not None,
                "max_mismatched_pixels": max_identity_mismatch_pixels,
            },
            "phase_pairs": {
                "pairs": [list(pair) for pair in phase_pairs],
                "height_deltas": paired_height_deltas,
                "max_height_delta": max_paired_height_delta,
            },
            "paired_transitions": paired_transitions,
            "thresholds": {
                "axis_tolerance": args.axis_tolerance,
                "min_adjacent_silhouette_change": args.min_adjacent_silhouette_change,
                "max_adjacent_silhouette_change": args.max_adjacent_silhouette_change,
                "max_adjacent_head_shift": args.max_adjacent_head_shift,
                "max_adjacent_torso_shift": args.max_adjacent_torso_shift,
                "max_adjacent_palette_tv": args.max_adjacent_palette_tv,
                "max_paired_transition_ratio": args.max_paired_transition_ratio,
                "require_paired_transition_cadence": args.require_paired_transition_cadence,
                "max_paired_height_delta": args.max_paired_height_delta,
            },
        },
    }
    audit_path = root / f"generated/{args.artifact_slug}-audit.json"
    audit_path.write_text(json.dumps(audit, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": audit["verdict"],
                "sheet": str(sheet_path),
                "manifest": str(manifest_path),
                "audit": str(audit_path),
                "visible_heights": visible_heights,
                "temporal": summary,
                "shared_refined_grid": shared_refined_grid,
                "max_paired_transition_ratio": paired_transitions["max_ratio"],
                "max_identity_mismatch_pixels": max_identity_mismatch_pixels,
            }
        )
    )
    return 0 if audit["verdict"] in ("pass", "awaiting-visual-review") else 1


if __name__ == "__main__":
    raise SystemExit(main())
