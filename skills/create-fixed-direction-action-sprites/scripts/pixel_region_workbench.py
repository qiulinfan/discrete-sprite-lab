#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pillow>=11,<13",
# ]
# ///
"""Exact local pixel review, extraction, and stale-safe patch application."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw


VERSION = "1.1.0"

SEMANTIC_CLASSES = {"stable_identity", "phase_specific"}
DISCRETE_TRANSFORMS = {"identity", "mirror_x"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def rgba_digest(image: Image.Image) -> str:
    source = image.convert("RGBA")
    return hashlib.sha256(source.tobytes()).hexdigest()


def rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def safe_id(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
    if not result:
        raise ValueError("Region id has no filename-safe characters")
    return result


def load_regions(path: Path, image_size: tuple[int, int]) -> list[dict]:
    payload = json.loads(path.read_text())
    if payload.get("schema_version") != 1:
        raise ValueError("Region file requires schema_version 1")
    declared = tuple(payload.get("canvas_size", []))
    if declared and declared != image_size:
        raise ValueError(f"Region canvas {declared} does not match image {image_size}")
    regions = payload.get("regions")
    if not isinstance(regions, list) or not regions:
        raise ValueError("Region file requires a non-empty regions list")
    seen: set[str] = set()
    output = []
    for raw in regions:
        region_id = str(raw.get("id", ""))
        if not region_id or region_id in seen:
            raise ValueError(f"Region id is missing or duplicated: {region_id!r}")
        seen.add(region_id)
        rect = raw.get("rect")
        anchor = raw.get("anchor")
        if not isinstance(rect, list) or len(rect) != 4:
            raise ValueError(f"Region {region_id} requires rect [x0,y0,x1,y1]")
        if not isinstance(anchor, list) or len(anchor) != 2:
            raise ValueError(f"Region {region_id} requires anchor [x,y]")
        x0, y0, x1, y1 = map(int, rect)
        ax, ay = map(int, anchor)
        if not (0 <= x0 < x1 <= image_size[0] and 0 <= y0 < y1 <= image_size[1]):
            raise ValueError(f"Region {region_id} rect is outside the image: {rect}")
        if not (x0 <= ax < x1 and y0 <= ay < y1):
            raise ValueError(f"Region {region_id} anchor is outside its rect: {anchor}")
        reference_rect = raw.get("reference_rect", rect)
        if not isinstance(reference_rect, list) or len(reference_rect) != 4:
            raise ValueError(f"Region {region_id} reference_rect must be [x0,y0,x1,y1]")
        rx0, ry0, rx1, ry1 = map(int, reference_rect)
        if not (0 <= rx0 < rx1 <= image_size[0] and 0 <= ry0 < ry1 <= image_size[1]):
            raise ValueError(f"Region {region_id} reference_rect is outside the image")
        if (rx1 - rx0, ry1 - ry0) != (x1 - x0, y1 - y0):
            raise ValueError(f"Region {region_id} rect and reference_rect sizes differ")
        semantic_class = str(raw.get("semantic_class", "phase_specific"))
        if semantic_class not in SEMANTIC_CLASSES:
            raise ValueError(
                f"Region {region_id} semantic_class must be one of {sorted(SEMANTIC_CLASSES)}"
            )
        phase_family = str(raw.get("phase_family", "unspecified"))
        if not phase_family:
            raise ValueError(f"Region {region_id} phase_family cannot be empty")
        allowed_transforms = raw.get("allowed_transforms", ["identity"])
        if not isinstance(allowed_transforms, list) or not allowed_transforms:
            raise ValueError(f"Region {region_id} allowed_transforms must be a non-empty list")
        if any(transform not in DISCRETE_TRANSFORMS for transform in allowed_transforms):
            raise ValueError(
                f"Region {region_id} has unsupported allowed_transforms: {allowed_transforms}"
            )
        context_ring = int(raw.get("context_ring", 1))
        if not 0 <= context_ring <= 8:
            raise ValueError(f"Region {region_id} context_ring must be between 0 and 8")
        output.append(
            {
                "id": region_id,
                "rect": [x0, y0, x1, y1],
                "reference_rect": [rx0, ry0, rx1, ry1],
                "anchor": [ax, ay],
                "semantic_class": semantic_class,
                "phase_family": phase_family,
                "allowed_transforms": allowed_transforms,
                "context_ring": context_ring,
            }
        )
    return output


def context_rects(
    subject_rect: list[int],
    reference_rect: list[int],
    ring: int,
    image_size: tuple[int, int],
) -> tuple[list[int], list[int]]:
    x0, y0, x1, y1 = subject_rect
    rx0, ry0, rx1, ry1 = reference_rect
    width, height = image_size
    left = min(ring, x0, rx0)
    top = min(ring, y0, ry0)
    right = min(ring, width - x1, width - rx1)
    bottom = min(ring, height - y1, height - ry1)
    return (
        [x0 - left, y0 - top, x1 + right, y1 + bottom],
        [rx0 - left, ry0 - top, rx1 + right, ry1 + bottom],
    )


def exact_diff(
    subject: Image.Image,
    reference: Image.Image,
    subject_rect: list[int],
    reference_rect: list[int],
) -> dict:
    x0, y0, x1, y1 = subject_rect
    rx0, ry0, _, _ = reference_rect
    records = []
    counts = {"subject_only": 0, "reference_only": 0, "recolored": 0}
    for y in range(y0, y1):
        for x in range(x0, x1):
            first = subject.getpixel((x, y))
            reference_xy = (rx0 + x - x0, ry0 + y - y0)
            second = reference.getpixel(reference_xy)
            if first == second:
                continue
            if first[3] > 0 and second[3] == 0:
                kind = "subject_only"
            elif first[3] == 0 and second[3] > 0:
                kind = "reference_only"
            else:
                kind = "recolored"
            counts[kind] += 1
            records.append(
                {
                    "subject_xy": [x, y],
                    "reference_xy": list(reference_xy),
                    "kind": kind,
                    "subject_rgba": list(first),
                    "reference_rgba": list(second),
                }
            )
    return {"counts": counts, "changed_pixels": len(records), "pixels": records}


def composite_on_dark(image: Image.Image) -> Image.Image:
    background = Image.new("RGBA", image.size, (37, 42, 51, 255))
    background.alpha_composite(image.convert("RGBA"))
    return background.convert("RGB")


def render_diff(
    subject: Image.Image,
    reference: Image.Image,
    subject_rect: list[int],
    reference_rect: list[int],
) -> Image.Image:
    x0, y0, x1, y1 = subject_rect
    rx0, ry0, _, _ = reference_rect
    output = Image.new("RGB", (x1 - x0, y1 - y0), (48, 52, 60))
    colors = {
        "subject_only": (255, 82, 82),
        "reference_only": (82, 164, 255),
        "recolored": (255, 214, 82),
    }
    for y in range(y0, y1):
        for x in range(x0, x1):
            first = subject.getpixel((x, y))
            second = reference.getpixel((rx0 + x - x0, ry0 + y - y0))
            if first == second:
                if first[3] > 0:
                    output.putpixel((x - x0, y - y0), (116, 122, 132))
                continue
            if first[3] > 0 and second[3] == 0:
                kind = "subject_only"
            elif first[3] == 0 and second[3] > 0:
                kind = "reference_only"
            else:
                kind = "recolored"
            output.putpixel((x - x0, y - y0), colors[kind])
    return output


def save_magnified(image: Image.Image, output: Path, scale: int, grid: bool) -> None:
    if scale < 1:
        raise ValueError("Scale must be positive")
    enlarged = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    rendered = composite_on_dark(enlarged)
    if grid and scale >= 4:
        draw = ImageDraw.Draw(rendered)
        color = (67, 74, 86)
        for x in range(0, rendered.width + 1, scale):
            draw.line((x, 0, x, rendered.height - 1), fill=color, width=1)
        for y in range(0, rendered.height + 1, scale):
            draw.line((0, y, rendered.width - 1, y), fill=color, width=1)
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered.save(output)


def command_review(args: argparse.Namespace) -> int:
    image_path = args.image.resolve()
    subject = rgba(image_path)
    reference_path = args.reference.resolve() if args.reference else None
    reference = rgba(reference_path) if reference_path else None
    if reference is not None and reference.size != subject.size:
        raise ValueError(f"Reference size {reference.size} does not match subject {subject.size}")
    regions = load_regions(args.regions.resolve(), subject.size)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for region in regions:
        x0, y0, x1, y1 = region["rect"]
        slug = safe_id(region["id"])
        subject_crop = subject.crop((x0, y0, x1, y1))
        subject_output = output_dir / f"{slug}-subject-{args.scale}x.png"
        save_magnified(subject_crop, subject_output, args.scale, args.grid)
        record = {
            **region,
            "subject_review": str(subject_output),
            "subject_review_sha256": digest(subject_output),
        }
        if reference is not None:
            reference_crop = reference.crop(tuple(region["reference_rect"]))
            reference_output = output_dir / f"{slug}-reference-{args.scale}x.png"
            diff_output = output_dir / f"{slug}-diff-{args.scale}x.png"
            save_magnified(reference_crop, reference_output, args.scale, args.grid)
            save_magnified(
                render_diff(subject, reference, region["rect"], region["reference_rect"]),
                diff_output,
                args.scale,
                args.grid,
            )
            record.update(
                {
                    "reference_review": str(reference_output),
                    "reference_review_sha256": digest(reference_output),
                    "diff_review": str(diff_output),
                    "diff_review_sha256": digest(diff_output),
                    "exact_diff": exact_diff(
                        subject, reference, region["rect"], region["reference_rect"]
                    ),
                }
            )
            if region["context_ring"] > 0:
                subject_context_rect, reference_context_rect = context_rects(
                    region["rect"],
                    region["reference_rect"],
                    region["context_ring"],
                    subject.size,
                )
                context_subject = subject.crop(tuple(subject_context_rect))
                context_reference = reference.crop(tuple(reference_context_rect))
                context_subject_output = (
                    output_dir / f"{slug}-context-subject-{args.scale}x.png"
                )
                context_reference_output = (
                    output_dir / f"{slug}-context-reference-{args.scale}x.png"
                )
                context_diff_output = output_dir / f"{slug}-context-diff-{args.scale}x.png"
                save_magnified(
                    context_subject, context_subject_output, args.scale, args.grid
                )
                save_magnified(
                    context_reference, context_reference_output, args.scale, args.grid
                )
                save_magnified(
                    render_diff(
                        subject,
                        reference,
                        subject_context_rect,
                        reference_context_rect,
                    ),
                    context_diff_output,
                    args.scale,
                    args.grid,
                )
                record.update(
                    {
                        "context_subject_rect": subject_context_rect,
                        "context_reference_rect": reference_context_rect,
                        "context_subject_review": str(context_subject_output),
                        "context_subject_review_sha256": digest(context_subject_output),
                        "context_reference_review": str(context_reference_output),
                        "context_reference_review_sha256": digest(
                            context_reference_output
                        ),
                        "context_diff_review": str(context_diff_output),
                        "context_diff_review_sha256": digest(context_diff_output),
                        "context_exact_diff": exact_diff(
                            subject,
                            reference,
                            subject_context_rect,
                            reference_context_rect,
                        ),
                    }
                )
        records.append(record)
    manifest = {
        "schema_version": 1,
        "tool": "pixel-region-workbench.review",
        "tool_version": VERSION,
        "subject": str(image_path),
        "subject_sha256": digest(image_path),
        "reference": str(reference_path) if reference_path else None,
        "reference_sha256": digest(reference_path) if reference_path else None,
        "resample": "nearest",
        "scale": args.scale,
        "regions": records,
    }
    write_json(output_dir / "review.json", manifest)
    print(json.dumps({"status": "ok", "output": str(output_dir), "regions": len(records)}))
    return 0


def command_extract(args: argparse.Namespace) -> int:
    image_path = args.image.resolve()
    image = rgba(image_path)
    regions = load_regions(args.regions.resolve(), image.size)
    features = []
    for region in regions:
        x0, y0, x1, y1 = region["rect"]
        ax, ay = region["anchor"]
        cells = []
        for y in range(y0, y1):
            for x in range(x0, x1):
                color = image.getpixel((x, y))
                if color[3] not in (0, 255):
                    raise ValueError(f"Feature {region['id']} contains partial Alpha at {(x, y)}")
                cells.append({"offset": [x - ax, y - ay], "rgba": list(color)})
        features.append({**region, "cells": cells})
    atlas = {
        "schema_version": 1,
        "tool": "pixel-region-workbench.extract",
        "tool_version": VERSION,
        "source": str(image_path),
        "source_sha256": digest(image_path),
        "canvas_size": list(image.size),
        "features": features,
    }
    output = args.output.resolve()
    write_json(output, atlas)
    print(json.dumps({"status": "ok", "output": str(output), "features": len(features)}))
    return 0


def command_apply(args: argparse.Namespace) -> int:
    image_path = args.image.resolve()
    atlas_path = args.atlas.resolve()
    placements_path = args.placements.resolve()
    image = rgba(image_path)
    atlas = json.loads(atlas_path.read_text())
    placements = json.loads(placements_path.read_text())
    if atlas.get("schema_version") != 1 or placements.get("schema_version") != 1:
        raise ValueError("Atlas and placement files require schema_version 1")
    expected_hash = placements.get("target_sha256")
    actual_hash = digest(image_path)
    if expected_hash != actual_hash:
        raise ValueError(f"Stale target: expected {expected_hash}, got {actual_hash}")
    declared = tuple(atlas.get("canvas_size", []))
    if declared != image.size:
        raise ValueError(f"Atlas canvas {declared} does not match target {image.size}")
    features = {feature["id"]: feature for feature in atlas.get("features", [])}
    output = image.copy()
    writes: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    operations = []
    for placement in placements.get("placements", []):
        feature_id = placement.get("feature_id")
        if feature_id not in features:
            raise ValueError(f"Unknown feature_id: {feature_id}")
        target_anchor = placement.get("anchor")
        if not isinstance(target_anchor, list) or len(target_anchor) != 2:
            raise ValueError(f"Placement {feature_id} requires anchor [x,y]")
        ax, ay = map(int, target_anchor)
        transform = placement.get("transform", "identity")
        if transform not in DISCRETE_TRANSFORMS:
            raise ValueError(f"Unsupported discrete transform for {feature_id}: {transform}")
        feature = features[feature_id]
        if transform not in feature.get("allowed_transforms", ["identity"]):
            raise ValueError(f"Transform {transform} is not allowed for feature {feature_id}")
        count = 0
        for cell in feature["cells"]:
            dx, dy = map(int, cell["offset"])
            if transform == "mirror_x":
                dx = -dx
            color = tuple(map(int, cell["rgba"]))
            if len(color) != 4 or color[3] not in (0, 255) or any(not 0 <= value <= 255 for value in color):
                raise ValueError(f"Feature {feature_id} contains invalid RGBA: {color}")
            xy = (ax + dx, ay + dy)
            if not (0 <= xy[0] < image.width and 0 <= xy[1] < image.height):
                raise ValueError(f"Feature {feature_id} writes outside target at {xy}")
            if xy in writes and writes[xy] != color:
                raise ValueError(f"Conflicting feature writes at {xy}")
            writes[xy] = color
            count += 1
        operations.append(
            {
                "feature_id": feature_id,
                "anchor": [ax, ay],
                "transform": transform,
                "cells": count,
                "semantic_class": feature.get("semantic_class", "phase_specific"),
                "phase_family": feature.get("phase_family", "unspecified"),
            }
        )
    before = {xy: output.getpixel(xy) for xy in writes}
    for xy, color in writes.items():
        output.putpixel(xy, color)
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_path)
    unchanged_outside = True
    for y in range(image.height):
        for x in range(image.width):
            if (x, y) not in writes and image.getpixel((x, y)) != output.getpixel((x, y)):
                unchanged_outside = False
                break
    changed = sum(before[xy] != output.getpixel(xy) for xy in writes)
    transparent_writes = sum(color[3] == 0 for color in writes.values())
    cleared = sum(
        before[xy][3] > 0 and output.getpixel(xy)[3] == 0 for xy in writes
    )
    introduced = sum(
        before[xy][3] == 0 and output.getpixel(xy)[3] > 0 for xy in writes
    )
    receipt = {
        "schema_version": 1,
        "tool": "pixel-region-workbench.apply",
        "tool_version": VERSION,
        "target": str(image_path),
        "target_sha256": actual_hash,
        "target_rgba_sha256": rgba_digest(image),
        "atlas": str(atlas_path),
        "atlas_sha256": digest(atlas_path),
        "placements": str(placements_path),
        "placements_sha256": digest(placements_path),
        "output": str(output_path),
        "output_sha256": digest(output_path),
        "output_rgba_sha256": rgba_digest(output),
        "operations": operations,
        "written_coordinates": len(writes),
        "changed_coordinates": changed,
        "transparent_written_coordinates": transparent_writes,
        "cleared_coordinates": cleared,
        "introduced_coordinates": introduced,
        "unchanged_outside_writes": unchanged_outside,
        "resampling": False,
    }
    receipt_path = args.receipt.resolve() if args.receipt else output_path.with_suffix(".receipt.json")
    write_json(receipt_path, receipt)
    print(json.dumps({"status": "ok", "output": str(output_path), "receipt": str(receipt_path)}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser("review", help="Render exact local crops and differences")
    review.add_argument("--image", required=True, type=Path)
    review.add_argument("--reference", type=Path)
    review.add_argument("--regions", required=True, type=Path)
    review.add_argument("--output-dir", required=True, type=Path)
    review.add_argument("--scale", type=int, default=24)
    review.add_argument("--grid", action="store_true")
    review.set_defaults(handler=command_review)

    extract = subparsers.add_parser("extract", help="Extract agent-chosen regions as exact RGBA cells")
    extract.add_argument("--image", required=True, type=Path)
    extract.add_argument("--regions", required=True, type=Path)
    extract.add_argument("--output", required=True, type=Path)
    extract.set_defaults(handler=command_extract)

    apply = subparsers.add_parser("apply", help="Apply an exact feature atlas with stale-target protection")
    apply.add_argument("--image", required=True, type=Path)
    apply.add_argument("--atlas", required=True, type=Path)
    apply.add_argument("--placements", required=True, type=Path)
    apply.add_argument("--output", required=True, type=Path)
    apply.add_argument("--receipt", type=Path)
    apply.set_defaults(handler=command_apply)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
