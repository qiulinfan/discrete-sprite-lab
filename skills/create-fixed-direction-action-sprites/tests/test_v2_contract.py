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
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_fixed_direction_action.py"
SPEC = importlib.util.spec_from_file_location("fixed_direction_action", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def blank() -> Image.Image:
    return Image.new("RGBA", (8, 8), (0, 0, 0, 0))


class V2ContractTests(unittest.TestCase):
    def test_recorded_per_frame_grid_policy_accepts_distinct_integer_grids(self) -> None:
        record = MODULE.assess_recovery_grid_policy(
            [(63, 63), (62, 63), (66, 66)], require_shared=False
        )

        self.assertEqual(record["mode"], "recorded-per-frame")
        self.assertFalse(record["shared"])
        self.assertTrue(record["satisfied"])

    def test_shared_grid_policy_rejects_distinct_grid_shapes(self) -> None:
        record = MODULE.assess_recovery_grid_policy(
            [(63, 63), (62, 63), (66, 66)], require_shared=True
        )

        self.assertEqual(record["mode"], "shared-required")
        self.assertFalse(record["satisfied"])

    def test_body_axis_placement_does_not_center_the_current_foot(self) -> None:
        primitives, _ = MODULE.load_turnaround_primitives(None)
        frame = blank()
        for y in range(0, 6):
            for x in range(3, 6):
                frame.putpixel((x, y), (200, 100, 50, 255))
        for y in range(6, 8):
            for x in range(0, 3):
                frame.putpixel((x, y), (80, 40, 20, 255))

        placed, record = MODULE.place_action_one_to_one(
            frame, 16, 15, "body", primitives
        )
        landmarks = primitives.landmark_metrics(placed)

        self.assertLessEqual(abs(record["final_axis_x"] - 7.5), 0.5)
        self.assertGreater(abs(landmarks["feet"]["extent_mid_x"] - 7.5), 1.0)

    def test_identity_lock_restores_exact_gold_pixels(self) -> None:
        gold = blank()
        gold.putpixel((3, 2), (20, 30, 40, 255))
        frame = Image.new("RGBA", (8, 8), (200, 100, 50, 255))
        mask = np.zeros((8, 8), dtype=bool)
        mask[1:4, 2:5] = True

        locked = MODULE.apply_identity_lock(frame, gold, mask, (0, 1))
        record = MODULE.identity_lock_record(locked, gold, mask, (0, 1), 0)

        self.assertEqual(record["mismatched_pixels"], 0)
        self.assertEqual(locked.getpixel((3, 3)), (20, 30, 40, 255))
        self.assertEqual(locked.getpixel((2, 1)), (0, 0, 0, 0))

    def test_paired_motion_mirrors_only_then_restores_identity(self) -> None:
        gold = blank()
        gold.putpixel((3, 2), (240, 200, 120, 255))
        source = blank()
        source.putpixel((1, 6), (10, 200, 20, 255))
        source.putpixel((3, 2), (1, 1, 1, 255))
        target = blank()
        mask = np.zeros((8, 8), dtype=bool)
        mask[1:4, 2:5] = True

        paired = MODULE.derive_paired_motion(
            [source, target], [(0, 1)], gold, mask, [(0, 0), (0, 0)]
        )

        self.assertEqual(paired[1].getpixel((6, 6)), (10, 200, 20, 255))
        self.assertEqual(paired[1].getpixel((3, 2)), (240, 200, 120, 255))

    def test_paired_transition_ratio_exposes_lopsided_cycle(self) -> None:
        transitions = [
            {"from": "a", "to": "b", "motion_silhouette_change": 0.30},
            {"from": "b", "to": "c", "motion_silhouette_change": 0.20},
            {"from": "c", "to": "d", "motion_silhouette_change": 0.10},
            {"from": "d", "to": "e", "motion_silhouette_change": 0.10},
            {"from": "e", "to": "f", "motion_silhouette_change": 0.20},
            {"from": "f", "to": "a", "motion_silhouette_change": 0.10},
        ]

        audit = MODULE.paired_transition_audit(transitions, [(0, 3), (1, 4), (2, 5)])

        self.assertAlmostEqual(audit["max_ratio"], 3.0)
        self.assertGreater(audit["max_ratio"], 1.10)


if __name__ == "__main__":
    unittest.main()
