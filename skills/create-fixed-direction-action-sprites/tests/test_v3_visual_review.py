#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy>=2,<3",
#   "pillow>=11,<13",
# ]
# ///

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_fixed_direction_action.py"
SPEC = importlib.util.spec_from_file_location("fixed_direction_action", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class V3VisualReviewTests(unittest.TestCase):
    def test_missing_review_never_means_pass(self) -> None:
        record = MODULE.load_visual_review(None, "a" * 64, 6)
        self.assertEqual(record["status"], "missing")
        self.assertIsNone(record["verdict"])

    def test_passing_review_must_cover_every_stage_and_frame(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "review.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "artifact_sheet_sha256": "a" * 64,
                        "verdict": "pass",
                        "stages": {
                            "high_detail": {"verdict": "pass"},
                            "pseudo_pixel": {"verdict": "pass"},
                            "logical_frames": {
                                "verdict": "pass",
                                "reviewed_frame_count": 6,
                            },
                            "loop": {"verdict": "pass"},
                        },
                    }
                )
            )
            record = MODULE.load_visual_review(path, "a" * 64, 6)
            self.assertEqual(record["verdict"], "pass")

    def test_stale_review_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "review.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "artifact_sheet_sha256": "b" * 64,
                        "verdict": "fail",
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "stale"):
                MODULE.load_visual_review(path, "a" * 64, 6)

    def test_passing_review_must_acknowledge_failed_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "review.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "artifact_sheet_sha256": "a" * 64,
                        "verdict": "pass",
                        "stages": {
                            "high_detail": {"verdict": "pass"},
                            "pseudo_pixel": {"verdict": "pass"},
                            "logical_frames": {
                                "verdict": "pass",
                                "reviewed_frame_count": 6,
                            },
                            "loop": {"verdict": "pass"},
                        },
                    }
                )
            )

            with self.assertRaisesRegex(ValueError, "does not acknowledge"):
                MODULE.load_visual_review(
                    path, "a" * 64, 6, ["paired_transition_cadence"]
                )

    def test_user_visual_approval_can_accept_diagnostic_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "review.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "artifact_sheet_sha256": "a" * 64,
                        "verdict": "pass",
                        "stages": {
                            "high_detail": {"verdict": "pass"},
                            "pseudo_pixel": {"verdict": "pass"},
                            "logical_frames": {
                                "verdict": "pass",
                                "reviewed_frame_count": 6,
                            },
                            "loop": {"verdict": "pass"},
                        },
                        "diagnostic_overrides": [
                            {
                                "id": "paired_transition_cadence",
                                "decision": "accept",
                                "authority": "user",
                                "reason": "Normal and slow loops were explicitly approved.",
                                "evidence": ["normal.gif", "slow.gif"],
                            }
                        ],
                    }
                )
            )

            record = MODULE.load_visual_review(
                path, "a" * 64, 6, ["paired_transition_cadence"]
            )
            self.assertEqual(record["verdict"], "pass")
            self.assertEqual(
                record["diagnostic_overrides"][0]["authority"], "user"
            )


if __name__ == "__main__":
    unittest.main()
