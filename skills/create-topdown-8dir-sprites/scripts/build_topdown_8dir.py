#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy>=2,<3",
#   "pillow>=11,<13",
#   "perfect-pixel==0.1.4",
# ]
# ///
"""Recover, align, palette, and audit a top-down eight-direction pixel set."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from perfect_pixel.perfect_pixel_noCV2 import get_perfect_pixel


DIRECTIONS = (
    "north",
    "northeast",
    "east",
    "southeast",
    "south",
    "southwest",
    "west",
    "northwest",
)
LABELS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
TOOL = "create-topdown-8dir-sprites.build"
VERSION = "2.2.0"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rgba_sha256(image: Image.Image) -> str:
    return hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()


def parse_grid_overrides(raw: str) -> dict[str, int]:
    overrides: dict[str, int] = {}
    if not raw:
        return overrides
    for item in raw.split(","):
        direction, separator, value = item.partition("=")
        direction = direction.strip()
        if not separator or direction not in DIRECTIONS:
            raise ValueError(f"Invalid --grid-overrides item: {item}")
        grid = int(value)
        if not 16 <= grid <= 256:
            raise ValueError(f"Grid override out of bounds for {direction}: {grid}")
        overrides[direction] = grid
    return overrides


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.convert("RGBA").getchannel("A").getbbox()
    if not bbox:
        raise ValueError("Image has no visible pixels")
    return tuple(map(int, bbox))


def extract_background(source: Path, output: Path) -> dict:
    image = Image.open(source)
    original_mode = image.mode
    existing_alpha = image.convert("RGBA").getchannel("A")
    has_useful_alpha = existing_alpha.getextrema()[0] < 255
    defringe_pixels = 0

    if has_useful_alpha:
        rgba = image.convert("RGBA")
        method = "preserve-source-alpha"
    else:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
        high = rgb.max(axis=2).astype(np.int16)
        low = rgb.min(axis=2).astype(np.int16)
        saturation = high - low
        corner_values = np.array([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]])
        dark_background = float(corner_values.mean()) < 64
        eligible = (saturation <= 10) & ((high <= 32) if dark_background else (low >= 225))
        flood_mask = Image.fromarray(np.where(eligible, 255, 0).astype(np.uint8), "L").copy()
        for point in (
            (0, 0),
            (flood_mask.width - 1, 0),
            (0, flood_mask.height - 1),
            (flood_mask.width - 1, flood_mask.height - 1),
        ):
            ImageDraw.floodfill(flood_mask, point, 128, thresh=0)
        opaque = np.asarray(flood_mask) != 128

        for _ in range(3):
            adjacent_clear = (
                np.roll(~opaque, 1, axis=0)
                | np.roll(~opaque, -1, axis=0)
                | np.roll(~opaque, 1, axis=1)
                | np.roll(~opaque, -1, axis=1)
            )
            neutral_edge = (high <= 80) if dark_background else (low >= 80)
            matte = opaque & adjacent_clear & (saturation <= 20) & neutral_edge
            matte[[0, -1], :] = False
            matte[:, [0, -1]] = False
            removed = int(matte.sum())
            if not removed:
                break
            opaque[matte] = False
            defringe_pixels += removed

        pixels = np.array(image.convert("RGBA"), dtype=np.uint8)
        pixels[..., 3] = np.where(opaque, 255, 0).astype(np.uint8)
        pixels[~opaque, :3] = 0
        rgba = Image.fromarray(pixels, "RGBA")
        method = (
            "corner-connected-dark-matte-plus-neutral-defringe"
            if dark_background
            else "corner-connected-light-matte-plus-neutral-defringe"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    rgba.save(output)
    alpha = np.asarray(rgba)[..., 3]
    return {
        "source": str(source.resolve()),
        "output": str(output.resolve()),
        "original_mode": original_mode,
        "method": method,
        "defringe_pixels": defringe_pixels,
        "source_size_px": list(image.size),
        "alpha_bbox": list(alpha_bbox(rgba)),
        "transparent_pixels": int((alpha == 0).sum()),
        "partially_transparent_pixels": int(((alpha > 0) & (alpha < 255)).sum()),
        "source_sha256": file_sha256(source),
        "output_sha256": file_sha256(output),
    }


def normalize_source_visible_height(source: Path, output: Path, target_height: int) -> dict:
    """Normalize pseudo-pixel occupancy before Perfect Pixel recovery.

    Image generation can change character occupancy even when its high-detail
    input was anchored. Scaling the recovered logical sprite would violate the
    1:1 handoff, so occupancy correction belongs before majority sampling.
    Nearest-neighbor resampling keeps the pseudo-pixel source crisp; Perfect
    Pixel then restores a regular logical grid.
    """
    image = Image.open(source).convert("RGBA")
    bbox = alpha_bbox(image)
    crop = image.crop(bbox)
    source_height = crop.height
    scale = target_height / source_height
    width = max(1, round(crop.width * scale))
    if target_height > image.height or width > image.width:
        raise ValueError(
            "Normalized pseudo-pixel source would not fit its original canvas: "
            f"target={width}x{target_height}, canvas={image.width}x{image.height}"
        )
    resized = crop.resize((width, target_height), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
    x = (image.width - width) // 2
    y = (image.height - target_height) // 2
    canvas.alpha_composite(resized, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return {
        "source": str(source.resolve()),
        "output": str(output.resolve()),
        "source_alpha_bbox": list(bbox),
        "source_visible_height": source_height,
        "target_visible_height": target_height,
        "scale": scale,
        "resample": "nearest",
        "output_alpha_bbox": list(alpha_bbox(canvas)),
        "source_sha256": file_sha256(source),
        "output_sha256": file_sha256(output),
    }


def recover_candidate(array: np.ndarray, requested_grid: int) -> tuple[Image.Image, dict]:
    width, height, recovered = get_perfect_pixel(
        array,
        sample_method="majority",
        grid_size=(requested_grid, requested_grid),
        refine_intensity=0.0,
        fix_square=False,
    )
    image = Image.fromarray(recovered.astype(np.uint8), "RGBA")
    bbox = alpha_bbox(image)
    crop_size = [bbox[2] - bbox[0], bbox[3] - bbox[1]]
    return image, {
        "requested_grid_size": [requested_grid, requested_grid],
        "refined_grid_size": [int(width), int(height)],
        "alpha_bbox": list(bbox),
        "recovered_crop_size": crop_size,
        "visible_height": crop_size[1],
        "sample_method": "majority",
        "refine_intensity": 0.0,
    }


def calibrate_grid(
    array: np.ndarray,
    base_grid: int,
    target_height: int,
    tolerance: int,
    override: int | None,
    max_iterations: int,
) -> tuple[Image.Image, dict, list[dict]]:
    if override is not None:
        image, record = recover_candidate(array, override)
        return image, record, [record]

    trials: list[dict] = []
    valid_trials: list[dict] = []
    images: list[Image.Image] = []
    seen: set[int] = set()
    current = base_grid
    for _ in range(max_iterations):
        current = max(16, min(256, int(current)))
        if current in seen:
            break
        seen.add(current)
        try:
            image, record = recover_candidate(array, current)
        except ValueError as error:
            trials.append({
                "requested_grid_size": [current, current],
                "valid": False,
                "error": str(error),
            })
            remaining = [candidate for candidate in (current - 1, current + 1) if candidate not in seen]
            if not remaining:
                break
            current = min(remaining, key=lambda candidate: abs(candidate - base_grid))
            continue
        record["valid"] = True
        images.append(image)
        trials.append(record)
        valid_trials.append(record)
        error = abs(record["visible_height"] - target_height)
        if error <= tolerance:
            break
        proposed = round(current * target_height / record["visible_height"])
        if proposed in seen:
            remaining = [candidate for candidate in (proposed - 1, proposed + 1) if candidate not in seen]
            if not remaining:
                break
            proposed = min(remaining, key=lambda candidate: abs(candidate - base_grid))
        current = proposed

    if not valid_trials:
        raise ValueError("Perfect Pixel calibration produced no visible candidate")
    selected_index = min(
        range(len(valid_trials)),
        key=lambda index: (
            abs(valid_trials[index]["visible_height"] - target_height),
            abs(valid_trials[index]["requested_grid_size"][0] - base_grid),
            valid_trials[index]["requested_grid_size"][0],
        ),
    )
    return images[selected_index], valid_trials[selected_index], trials


def landmark_metrics(image: Image.Image) -> dict:
    pixels = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    mask = pixels[..., 3] > 0
    ys, xs = np.where(mask)
    if not len(xs):
        raise ValueError("Image has no visible pixels")
    x0, y0, x1, y1 = alpha_bbox(image)
    height = y1 - y0
    grid_y, _ = np.indices(mask.shape)
    head = mask & (grid_y < y0 + max(1, round(height * 0.38)))
    torso = (
        mask
        & (grid_y >= y0 + round(height * 0.35))
        & (grid_y < y0 + round(height * 0.72))
    )
    feet = mask & (grid_y >= y1 - max(2, round(height * 0.04)))

    def region(region_mask: np.ndarray) -> dict:
        region_y, region_x = np.where(region_mask)
        if not len(region_x):
            raise ValueError("Landmark region has no visible pixels")
        return {
            "centroid_x": float(region_x.mean()),
            "extent_mid_x": float((region_x.min() + region_x.max()) / 2),
            "bbox": [
                int(region_x.min()),
                int(region_y.min()),
                int(region_x.max() + 1),
                int(region_y.max() + 1),
            ],
            "visible_pixels": int(len(region_x)),
        }

    head_metrics = region(head)
    torso_metrics = region(torso)
    feet_metrics = region(feet)
    return {
        "alpha_bbox": [x0, y0, x1, y1],
        "visible_width": x1 - x0,
        "visible_height": y1 - y0,
        "alpha_centroid_x": float(xs.mean()),
        "head": head_metrics,
        "torso": torso_metrics,
        "feet": feet_metrics,
        "body_axis_x": float((head_metrics["centroid_x"] + torso_metrics["centroid_x"]) / 2),
    }


def place_one_to_one(
    image: Image.Image,
    frame_size: int,
    target_bottom: int,
    placement_axis: str = "foot",
) -> tuple[Image.Image, dict]:
    bbox = alpha_bbox(image)
    crop = image.crop(bbox).convert("RGBA")
    if crop.width > frame_size or crop.height > frame_size:
        raise ValueError(f"Recovered sprite {crop.size} does not fit {frame_size}x{frame_size} without scaling")
    crop_landmarks = landmark_metrics(crop)
    target_axis_x = (frame_size - 1) / 2
    if placement_axis == "foot":
        source_axis_x = crop_landmarks["feet"]["extent_mid_x"]
    elif placement_axis == "body":
        source_axis_x = crop_landmarks["body_axis_x"]
    else:
        raise ValueError(f"Unsupported placement axis: {placement_axis}")
    x = round(target_axis_x - source_axis_x)
    y = target_bottom - crop.height
    if x < 0 or x + crop.width > frame_size:
        raise ValueError(
            f"Recovered sprite {crop.size} cannot align its {placement_axis} axis to {target_axis_x} "
            f"on {frame_size}x{frame_size} without scaling or clipping"
        )
    if y < 0 or target_bottom > frame_size:
        raise ValueError(
            f"Recovered sprite {crop.size} cannot be placed at bottom {target_bottom} "
            f"on {frame_size}x{frame_size} without scaling"
        )
    canvas = Image.new("RGBA", (frame_size, frame_size), (0, 0, 0, 0))
    canvas.alpha_composite(crop, (x, y))
    pixels = np.array(canvas, dtype=np.uint8)
    pixels[..., 3] = np.where(pixels[..., 3] > 0, 255, 0).astype(np.uint8)
    pixels[pixels[..., 3] == 0, :3] = 0
    canvas = Image.fromarray(pixels, "RGBA")
    final_landmarks = landmark_metrics(canvas)
    return canvas, {
        "placement_mode": "one-to-one",
        "placement_axis": placement_axis,
        "recovered_crop_size": [crop.width, crop.height],
        "position": [x, y],
        "final_alpha_bbox": list(alpha_bbox(canvas)),
        "target_placement_axis_x": target_axis_x,
        "source_landmarks": crop_landmarks,
        "final_landmarks": final_landmarks,
        "resampled_after_recovery": False,
    }


def srgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    value = rgb.astype(np.float64) / 255.0
    linear = np.where(value <= 0.04045, value / 12.92, ((value + 0.055) / 1.055) ** 2.4)
    red, green, blue = linear[:, 0], linear[:, 1], linear[:, 2]
    light = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
    medium = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
    short = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue
    light_root, medium_root, short_root = np.cbrt(light), np.cbrt(medium), np.cbrt(short)
    return np.stack(
        (
            0.2104542553 * light_root + 0.7936177850 * medium_root - 0.0040720468 * short_root,
            1.9779984951 * light_root - 2.4285922050 * medium_root + 0.4505937099 * short_root,
            0.0259040371 * light_root + 0.7827717662 * medium_root - 0.8086757660 * short_root,
        ),
        axis=1,
    )


def apply_canonical_palette(
    frames: list[Image.Image],
    color_limit: int,
    palette_reference: str,
) -> tuple[list[Image.Image], list[list[int]]]:
    visible_pixels = []
    palette_frames = frames if palette_reference == "shared" else [frames[DIRECTIONS.index(palette_reference)]]
    for frame in palette_frames:
        pixels = np.asarray(frame.convert("RGBA"), dtype=np.uint8)
        visible_pixels.append(pixels[..., :3][pixels[..., 3] > 0])
    all_pixels = np.concatenate(visible_pixels, axis=0)
    unique, counts = np.unique(all_pixels, axis=0, return_counts=True)
    labs = srgb_to_oklab(unique)
    count = min(color_limit, len(unique))
    selected = [int(np.argmax(counts))]
    minimum = np.sum((labs - labs[selected[0]]) ** 2, axis=1)
    for _ in range(1, count):
        candidate = int(np.argmax(minimum * counts))
        selected.append(candidate)
        minimum = np.minimum(minimum, np.sum((labs - labs[candidate]) ** 2, axis=1))

    medoids = np.array(selected, dtype=np.int32)
    for _ in range(20):
        distances = np.sum((labs[:, None, :] - labs[medoids][None, :, :]) ** 2, axis=2)
        labels = np.argmin(distances, axis=1)
        updated = medoids.copy()
        for index in range(count):
            members = np.where(labels == index)[0]
            if not len(members):
                continue
            centroid = np.average(labs[members], axis=0, weights=counts[members])
            updated[index] = members[np.argmin(np.sum((labs[members] - centroid) ** 2, axis=1))]
        if np.array_equal(updated, medoids):
            break
        medoids = updated

    palette = unique[medoids]
    palette_labs = srgb_to_oklab(palette)
    outputs: list[Image.Image] = []
    for frame in frames:
        pixels = np.array(frame.convert("RGBA"), dtype=np.uint8)
        mask = pixels[..., 3] > 0
        source_unique, inverse = np.unique(pixels[..., :3][mask], axis=0, return_inverse=True)
        source_labs = srgb_to_oklab(source_unique)
        labels = np.argmin(
            np.sum((source_labs[:, None, :] - palette_labs[None, :, :]) ** 2, axis=2),
            axis=1,
        )
        pixels[..., :3][mask] = palette[labels][inverse]
        pixels[~mask, :3] = 0
        pixels[..., 3] = np.where(mask, 255, 0).astype(np.uint8)
        outputs.append(Image.fromarray(pixels, "RGBA"))
    return outputs, [list(map(int, color)) for color in palette]


def turnaround_continuity(frames: list[Image.Image], palette: list[list[int]]) -> dict:
    frame_metrics = []
    palette_index = {tuple(color): index for index, color in enumerate(palette)}
    histograms = []
    for direction, frame in zip(DIRECTIONS, frames):
        metrics = landmark_metrics(frame)
        metrics["head_foot_axis_offset"] = (
            metrics["head"]["extent_mid_x"] - metrics["feet"]["extent_mid_x"]
        )
        pixels = np.asarray(frame.convert("RGBA"), dtype=np.uint8)
        mask = pixels[..., 3] > 0
        colors, counts = np.unique(pixels[..., :3][mask], axis=0, return_counts=True)
        histogram = np.zeros(len(palette), dtype=np.float64)
        for color, count in zip(colors, counts):
            histogram[palette_index[tuple(map(int, color))]] = count
        histogram /= histogram.sum()
        histograms.append(histogram)
        metrics["direction"] = direction
        metrics["unique_palette_colors"] = int(len(colors))
        frame_metrics.append(metrics)

    transitions = []
    for index, direction in enumerate(DIRECTIONS):
        next_index = (index + 1) % len(DIRECTIONS)
        next_direction = DIRECTIONS[next_index]
        current = frame_metrics[index]
        following = frame_metrics[next_index]
        transitions.append(
            {
                "from": direction,
                "to": next_direction,
                "head_anchor_dx": abs(current["head"]["centroid_x"] - following["head"]["centroid_x"]),
                "torso_anchor_dx": abs(
                    current["torso"]["centroid_x"] - following["torso"]["centroid_x"]
                ),
                "foot_axis_dx": abs(
                    current["feet"]["extent_mid_x"] - following["feet"]["extent_mid_x"]
                ),
                "head_foot_axis_offset_delta": abs(
                    current["head_foot_axis_offset"] - following["head_foot_axis_offset"]
                ),
                "visible_width_delta": abs(current["visible_width"] - following["visible_width"]),
                "visible_height_delta": abs(current["visible_height"] - following["visible_height"]),
                "palette_total_variation": float(
                    0.5 * np.abs(histograms[index] - histograms[next_index]).sum()
                ),
            }
        )

    head_foot_offsets = [item["head_foot_axis_offset"] for item in frame_metrics]
    return {
        "schema_version": 1,
        "direction_order": list(DIRECTIONS),
        "frame_metrics": frame_metrics,
        "transitions": transitions,
        "summary": {
            "max_head_anchor_dx": max(item["head_anchor_dx"] for item in transitions),
            "max_torso_anchor_dx": max(item["torso_anchor_dx"] for item in transitions),
            "max_foot_axis_dx": max(item["foot_axis_dx"] for item in transitions),
            "max_head_foot_axis_offset_delta": max(
                item["head_foot_axis_offset_delta"] for item in transitions
            ),
            "head_foot_axis_offset_spread": max(head_foot_offsets) - min(head_foot_offsets),
            "max_visible_width_delta": max(item["visible_width_delta"] for item in transitions),
            "max_visible_height_delta": max(item["visible_height_delta"] for item in transitions),
            "max_palette_total_variation": max(item["palette_total_variation"] for item in transitions),
        },
    }


def checkerboard(size: tuple[int, int], tile: int) -> Image.Image:
    image = Image.new("RGBA", size, (48, 53, 64, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], tile):
        for x in range(0, size[0], tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill=(63, 69, 82, 255))
    return image


def write_previews(
    root: Path,
    slug: str,
    frames: list[Image.Image],
    frame_size: int,
    target_bottom: int,
    rotation_ms: int,
) -> None:
    scale = max(4, 384 // frame_size)
    display = frame_size * scale
    label_height = 24
    contact = Image.new("RGB", (display * 4, (display + label_height) * 2), (24, 27, 34))
    contact_draw = ImageDraw.Draw(contact)
    head_height = min(frame_size, frame_size // 2 + 4)
    head_display_height = head_height * scale
    heads = Image.new("RGB", (display * 4, (head_display_height + label_height) * 2), (24, 27, 34))
    heads_draw = ImageDraw.Draw(heads)
    rotation = []
    frame_landmarks = [landmark_metrics(frame) for frame in frames]

    for index, (label, frame) in enumerate(zip(LABELS, frames)):
        enlarged = frame.resize((display, display), Image.Resampling.NEAREST)
        background = checkerboard((display, display), max(8, scale * 2))
        background.alpha_composite(enlarged)
        x = (index % 4) * display
        y = (index // 4) * (display + label_height)
        contact.paste(background.convert("RGB"), (x, y))
        contact_draw.text((x + 6, y + display + 4), label, fill=(245, 246, 250))

        head = frame.crop((0, 0, frame_size, head_height)).resize(
            (display, head_display_height), Image.Resampling.NEAREST
        )
        head_background = checkerboard((display, head_display_height), max(8, scale * 2))
        head_background.alpha_composite(head)
        head_y = (index // 4) * (head_display_height + label_height)
        heads.paste(head_background.convert("RGB"), (x, head_y))
        heads_draw.text((x + 6, head_y + head_display_height + 4), label, fill=(245, 246, 250))

        gif_size = frame_size * 8
        gif_frame = Image.new("RGBA", (gif_size, gif_size + 28), (27, 31, 38, 255))
        gif_frame.alpha_composite(frame.resize((gif_size, gif_size), Image.Resampling.NEAREST), (0, 28))
        ImageDraw.Draw(gif_frame).text((10, 8), label, fill=(245, 246, 250, 255))
        rotation.append(gif_frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=256))

    contact.save(root / f"evidence/{slug}-contact.png")
    heads.save(root / f"evidence/{slug}-head-crops.png")
    guides = contact.copy()
    guide_draw = ImageDraw.Draw(guides)
    target_axis_x = (frame_size - 1) / 2
    for index, metrics in enumerate(frame_landmarks):
        x = (index % 4) * display
        y = (index // 4) * (display + label_height)
        axis_x = x + round((target_axis_x + 0.5) * scale)
        baseline_y = y + target_bottom * scale
        guide_draw.line((axis_x, y, axis_x, y + display - 1), fill=(244, 88, 96), width=1)
        guide_draw.line((x, baseline_y, x + display - 1, baseline_y), fill=(82, 218, 132), width=1)
        for region_name, color in (
            ("head", (75, 214, 255)),
            ("torso", (255, 211, 77)),
            ("feet", (229, 104, 255)),
        ):
            region = metrics[region_name]
            anchor = region["extent_mid_x"] if region_name == "feet" else region["centroid_x"]
            region_bbox = region["bbox"]
            anchor_x = x + round((anchor + 0.5) * scale)
            anchor_y = y + round(((region_bbox[1] + region_bbox[3] - 1) / 2 + 0.5) * scale)
            radius = max(2, scale // 2)
            guide_draw.ellipse(
                (anchor_x - radius, anchor_y - radius, anchor_x + radius, anchor_y + radius),
                fill=color,
            )
    guides.save(root / f"evidence/{slug}-continuity-guides.png")
    rotation[0].save(
        root / f"evidence/{slug}-rotation.gif",
        save_all=True,
        append_images=rotation[1:],
        duration=rotation_ms,
        loop=0,
        optimize=False,
        disposal=2,
    )
    rotation[0].save(
        root / f"evidence/{slug}-rotation-slow.gif",
        save_all=True,
        append_images=rotation[1:],
        duration=350,
        loop=0,
        optimize=False,
        disposal=2,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pseudo-dir", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--artifact-slug", required=True)
    parser.add_argument("--frame-size", type=int, default=64)
    parser.add_argument("--grid", type=int, default=64)
    parser.add_argument(
        "--normalize-source-visible-height",
        type=int,
        default=0,
        help=(
            "Optional shared alpha-bbox height on the high-resolution pseudo-pixel canvas "
            "before Perfect Pixel recovery; 0 preserves source occupancy"
        ),
    )
    parser.add_argument("--grid-overrides", default="")
    parser.add_argument("--target-visible-height", type=int, default=52)
    parser.add_argument("--height-tolerance", type=int, default=1)
    parser.add_argument("--target-bottom", type=int, default=61)
    parser.add_argument(
        "--placement-axis",
        choices=("foot", "body"),
        default="foot",
        help=(
            "Horizontal root used for 1:1 placement after recovery: foot for static turnarounds, "
            "body for one propagated animation phase whose feet move around a stable gameplay root"
        ),
    )
    parser.add_argument("--colors", type=int, default=32)
    parser.add_argument("--palette-reference", choices=(*DIRECTIONS, "shared"), default="south")
    parser.add_argument("--rotation-ms", type=int, default=120)
    parser.add_argument("--axis-tolerance", type=float, default=0.5)
    parser.add_argument("--max-adjacent-head-shift", type=float, default=2.5)
    parser.add_argument("--max-adjacent-torso-shift", type=float, default=2.0)
    parser.add_argument("--max-adjacent-palette-tv", type=float, default=0.45)
    parser.add_argument("--max-head-foot-offset-spread", type=float, default=2.0)
    parser.add_argument("--calibration-iterations", type=int, default=3)
    args = parser.parse_args()

    if args.frame_size < 16:
        raise ValueError("--frame-size must be at least 16")
    if not 1 <= args.target_visible_height <= args.frame_size:
        raise ValueError("--target-visible-height must fit the frame")
    if not 1 <= args.target_bottom <= args.frame_size:
        raise ValueError("--target-bottom must fit the frame")
    if args.colors < 2:
        raise ValueError("--colors must be at least 2")
    if args.rotation_ms < 20:
        raise ValueError("--rotation-ms must be at least 20")
    if args.normalize_source_visible_height < 0:
        raise ValueError("--normalize-source-visible-height must be 0 or greater")

    pseudo_dir = args.pseudo_dir.resolve()
    root = args.output_root.resolve()
    overrides = parse_grid_overrides(args.grid_overrides)
    for directory in (
        "working/source-transparent",
        "working/source-normalized",
        "working/perfect-pixel",
        "working/placed-1to1",
        "working/final-frames",
        "generated",
        "evidence",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)

    background_records = []
    for direction in DIRECTIONS:
        source = pseudo_dir / f"{direction}.png"
        if not source.is_file():
            raise FileNotFoundError(f"Missing direction source: {source}")
        destination = root / f"working/source-transparent/{direction}.png"
        record = extract_background(source, destination)
        record["direction"] = direction
        background_records.append(record)
    (root / "evidence/background-extraction.json").write_text(
        json.dumps({"schema_version": 1, "records": background_records}, indent=2) + "\n"
    )

    normalization_records = []
    if args.normalize_source_visible_height:
        for direction in DIRECTIONS:
            source = root / f"working/source-transparent/{direction}.png"
            destination = root / f"working/source-normalized/{direction}.png"
            record = normalize_source_visible_height(
                source,
                destination,
                args.normalize_source_visible_height,
            )
            record["direction"] = direction
            normalization_records.append(record)
        (root / "evidence/source-occupancy-normalization.json").write_text(
            json.dumps({"schema_version": 1, "records": normalization_records}, indent=2) + "\n"
        )

    placed_frames: list[Image.Image] = []
    grid_records = []
    for direction in DIRECTIONS:
        source_stage = "source-normalized" if args.normalize_source_visible_height else "source-transparent"
        source = root / f"working/{source_stage}/{direction}.png"
        array = np.asarray(Image.open(source).convert("RGBA"), dtype=np.uint8)
        recovered, selected, trials = calibrate_grid(
            array=array,
            base_grid=args.grid,
            target_height=args.target_visible_height,
            tolerance=args.height_tolerance,
            override=overrides.get(direction),
            max_iterations=args.calibration_iterations,
        )
        recovered_path = root / f"working/perfect-pixel/{direction}.png"
        recovered.save(recovered_path)
        placed, placement = place_one_to_one(
            recovered,
            args.frame_size,
            args.target_bottom,
            args.placement_axis,
        )
        placed_path = root / f"working/placed-1to1/{direction}.png"
        placed.save(placed_path)
        placed_frames.append(placed)
        grid_records.append(
            {
                "direction": direction,
                "selected": selected,
                "trials": trials,
                "placement": placement,
                "source_sha256": file_sha256(source),
                "recovered_sha256": file_sha256(recovered_path),
                "placed_sha256": file_sha256(placed_path),
            }
        )
    (root / "evidence/perfect-pixel-grid-metrics.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tool": "perfect-pixel",
                "version": "0.1.4",
                "backend": "perfect_pixel_noCV2",
                "sample_method": "majority",
                "refine_intensity": 0.0,
                "records": grid_records,
            },
            indent=2,
        )
        + "\n"
    )

    final_frames, palette = apply_canonical_palette(
        placed_frames,
        args.colors,
        args.palette_reference,
    )
    continuity = turnaround_continuity(final_frames, palette)
    (root / "evidence/turnaround-continuity.json").write_text(json.dumps(continuity, indent=2) + "\n")
    sheet = Image.new("RGBA", (args.frame_size * 4, args.frame_size * 2), (0, 0, 0, 0))
    frame_records = []
    for index, (direction, frame) in enumerate(zip(DIRECTIONS, final_frames)):
        x = (index % 4) * args.frame_size
        y = (index // 4) * args.frame_size
        frame_path = root / f"working/final-frames/{direction}.png"
        frame.save(frame_path)
        sheet.alpha_composite(frame, (x, y))
        frame_records.append(
            {
                "id": direction,
                "direction": direction,
                "rect_px_top_left": {
                    "x": x,
                    "y": y,
                    "width": args.frame_size,
                    "height": args.frame_size,
                },
                "pivot_px_from_bottom_left": [args.frame_size // 2, args.frame_size - args.target_bottom],
                "landmarks": continuity["frame_metrics"][index],
                "path": frame_path.relative_to(root).as_posix(),
                "sha256": file_sha256(frame_path),
                "rgba_sha256": rgba_sha256(frame),
            }
        )

    sheet_path = root / f"generated/{args.artifact_slug}.png"
    sheet.save(sheet_path)
    manifest = {
        "schema_version": 1,
        "tool": TOOL,
        "tool_version": VERSION,
        "direction_order": list(DIRECTIONS),
        "sheet": {
            "path": sheet_path.relative_to(root).as_posix(),
            "size_px": list(sheet.size),
            "sha256": file_sha256(sheet_path),
            "rgba_sha256": rgba_sha256(sheet),
        },
        "processing": {
            "perfect_pixel_version": "0.1.4",
            "backend": "perfect_pixel_noCV2",
            "sample_method": "majority",
            "refine_intensity": 0.0,
            "default_grid": args.grid,
            "grid_overrides": overrides,
            "automatic_integer_calibration": True,
            "source_occupancy_normalization": {
                "enabled": bool(args.normalize_source_visible_height),
                "target_visible_height": args.normalize_source_visible_height or None,
                "resample": "nearest" if args.normalize_source_visible_height else None,
                "stage": "before-perfect-pixel",
            },
            "frame_size": args.frame_size,
            "target_visible_height": args.target_visible_height,
            "height_tolerance": args.height_tolerance,
            "target_bottom": args.target_bottom,
            "post_recovery_resampling": False,
            "placement": "one-to-one",
            "placement_axis": args.placement_axis,
            "palette_mode": "canonical-reference-oklab-medoid",
            "palette_reference": args.palette_reference,
            "colors": args.colors,
            "alpha": "binary",
            "rotation_preview_ms": args.rotation_ms,
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
        args.frame_size,
        args.target_bottom,
        args.rotation_ms,
    )

    sheet_pixels = np.asarray(sheet, dtype=np.uint8)
    alpha = sheet_pixels[..., 3]
    visible_heights = []
    contacts = []
    for frame in final_frames:
        bbox = alpha_bbox(frame)
        visible_heights.append(bbox[3] - bbox[1])
        contacts.append(bbox[3])
    selected_refined_grids = [record["selected"]["refined_grid_size"] for record in grid_records]
    target_axis_x = (args.frame_size - 1) / 2
    continuity_summary = continuity["summary"]
    checks = {
        "frame_count_8": len(final_frames) == 8,
        "canonical_direction_order": list(DIRECTIONS) == [record["direction"] for record in grid_records],
        "sheet_size": sheet.size == (args.frame_size * 4, args.frame_size * 2),
        "all_frames_requested_size": all(frame.size == (args.frame_size, args.frame_size) for frame in final_frames),
        "all_frames_nonempty": all(frame.getchannel("A").getbbox() for frame in final_frames),
        "binary_alpha": int(((alpha > 0) & (alpha < 255)).sum()) == 0,
        "palette_within_limit": len(np.unique(sheet_pixels[..., :3][alpha > 0], axis=0)) <= args.colors,
        "all_contacts_match": all(contact == args.target_bottom for contact in contacts),
        "all_heights_within_tolerance": all(
            abs(height - args.target_visible_height) <= args.height_tolerance for height in visible_heights
        ),
        "no_post_recovery_resampling": all(
            record["placement"]["resampled_after_recovery"] is False for record in grid_records
        ),
        "adjacent_head_anchor_shift_bounded": (
            continuity_summary["max_head_anchor_dx"] <= args.max_adjacent_head_shift
        ),
        "adjacent_torso_anchor_shift_bounded": (
            continuity_summary["max_torso_anchor_dx"] <= args.max_adjacent_torso_shift
        ),
        "adjacent_palette_transition_bounded": (
            continuity_summary["max_palette_total_variation"] <= args.max_adjacent_palette_tv
        ),
        "recovery_grids_bounded": all(
            args.frame_size // 2 <= dimension <= args.frame_size * 2
            for grid in selected_refined_grids
            for dimension in grid
        ),
    }
    if args.placement_axis == "foot":
        checks["foot_axes_aligned"] = all(
            abs(metrics["feet"]["extent_mid_x"] - target_axis_x) <= args.axis_tolerance
            for metrics in continuity["frame_metrics"]
        )
        checks["head_foot_axis_offset_spread_bounded"] = (
            continuity_summary["head_foot_axis_offset_spread"] <= args.max_head_foot_offset_spread
        )
    else:
        checks["body_axes_aligned"] = all(
            abs(metrics["body_axis_x"] - target_axis_x) <= args.axis_tolerance
            for metrics in continuity["frame_metrics"]
        )
    audit = {
        "schema_version": 1,
        "tool": TOOL,
        "tool_version": VERSION,
        "verdict": "pass" if all(checks.values()) else "fail",
        "artifact": {
            "sheet_sha256": file_sha256(sheet_path),
            "manifest_sha256": file_sha256(manifest_path),
        },
        "checks": checks,
        "facts": {
            "visible_heights": visible_heights,
            "visible_height_spread": max(visible_heights) - min(visible_heights),
            "contacts": contacts,
            "selected_requested_grids": [
                record["selected"]["requested_grid_size"] for record in grid_records
            ],
            "selected_refined_grids": selected_refined_grids,
            "palette_reference": args.palette_reference,
            "target_axis_x": target_axis_x,
            "placement_axis": args.placement_axis,
            "continuity": continuity_summary,
            "continuity_thresholds": {
                "axis_tolerance": args.axis_tolerance,
                "max_adjacent_head_shift": args.max_adjacent_head_shift,
                "max_adjacent_torso_shift": args.max_adjacent_torso_shift,
                "max_adjacent_palette_tv": args.max_adjacent_palette_tv,
                "max_head_foot_offset_spread": args.max_head_foot_offset_spread,
            },
            "visible_palette_colors": int(len(np.unique(sheet_pixels[..., :3][alpha > 0], axis=0))),
            "fully_transparent_pixels": int((alpha == 0).sum()),
            "fully_opaque_pixels": int((alpha == 255).sum()),
            "partially_transparent_pixels": int(((alpha > 0) & (alpha < 255)).sum()),
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
                "selected_requested_grids": audit["facts"]["selected_requested_grids"],
                "visible_palette_colors": audit["facts"]["visible_palette_colors"],
                "palette_reference": args.palette_reference,
                "continuity": continuity_summary,
            }
        )
    )
    return 0 if audit["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
