#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy>=2,<3",
#   "pillow>=11,<13",
#   "perfect-pixel==0.1.4",
# ]
# ///

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
from PIL import Image


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_topdown_8dir.py"
SPEC = importlib.util.spec_from_file_location("build_topdown_8dir", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def synthetic_walker() -> Image.Image:
    pixels = np.zeros((24, 20, 4), dtype=np.uint8)
    color = np.array([220, 90, 40, 255], dtype=np.uint8)
    pixels[1:8, 7:14] = color
    pixels[8:17, 6:15] = color
    pixels[17:21, 2:6] = color
    pixels[18:24, 13:18] = color
    return Image.fromarray(pixels, "RGBA")


def visible_rgba_multiset(image: Image.Image) -> list[tuple[int, int, int, int]]:
    pixels = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    return sorted(map(tuple, pixels[pixels[..., 3] > 0].tolist()))


def main() -> None:
    source = synthetic_walker()
    foot_frame, foot_record = MODULE.place_one_to_one(source, 32, 30, "foot")
    body_frame, body_record = MODULE.place_one_to_one(source, 32, 30, "body")

    foot_metrics = MODULE.landmark_metrics(foot_frame)
    body_metrics = MODULE.landmark_metrics(body_frame)
    assert abs(foot_metrics["feet"]["extent_mid_x"] - 15.5) <= 0.5
    assert abs(body_metrics["body_axis_x"] - 15.5) <= 0.5
    assert foot_record["placement_axis"] == "foot"
    assert body_record["placement_axis"] == "body"
    assert foot_record["position"][0] != body_record["position"][0], (foot_record, body_record)
    assert foot_record["resampled_after_recovery"] is False
    assert body_record["resampled_after_recovery"] is False
    assert visible_rgba_multiset(source) == visible_rgba_multiset(foot_frame)
    assert visible_rgba_multiset(source) == visible_rgba_multiset(body_frame)

    try:
        MODULE.place_one_to_one(source, 32, 30, "unsupported")
    except ValueError as error:
        assert "Unsupported placement axis" in str(error)
    else:
        raise AssertionError("Unsupported placement axis did not fail")

    print("placement-axis tests passed")


if __name__ == "__main__":
    main()
