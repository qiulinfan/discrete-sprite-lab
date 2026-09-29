#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=11,<13"]
# ///
"""Observable packaging, identity, review-invalidation, and playback regressions."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/package_native_action.py"
SPEC = importlib.util.spec_from_file_location("native_action", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NativeActionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "output"
        self.contract_path = self.root / "contract.json"
        master = Image.new("RGBA", (16, 16))
        draw = ImageDraw.Draw(master)
        draw.rectangle((6, 3, 8, 5), fill=(180, 100, 220, 255))
        draw.rectangle((6, 8, 8, 10), fill=(20, 30, 40, 255))
        master.save(self.root / "master.png")
        items = []
        for index, offset in enumerate([0, 1, -1]):
            frame = Image.new("RGBA", (16, 16))
            frame.paste(master, (0, offset))
            frame.putpixel((4+index, 12), (20, 30, 40, 255))
            frame.putpixel((0, 0), (31, 32, 33, 0))
            frame.save(self.root / f"phase-{index}.png")
            items.append({"phase_id": f"pose-{index}", "path": f"phase-{index}.png",
                          "duration_ms": [120, 180, 240][index], "body_offset": [0, offset]})
        self.contract = {"schema_version": 1, "artifact_slug": "fixture-walk-east",
                         "direction": "east", "action": "walk", "frame_size": [16, 16],
                         "body_origin_px": [7, 9], "master": "master.png", "loop": True,
                         "slow_factor": 3, "padding_px": 1, "max_colors": 2,
                         "palette_rgb": [[180, 100, 220], [20, 30, 40]],
                         "stable_regions": [{"id": "head", "rect": [4, 2, 10, 7]}],
                         "frames": items}

    def package(self, review=None):
        self.contract_path.write_text(json.dumps(self.contract))
        return MODULE.package(self.contract_path, self.output, review)

    def edit_frame(self, index, edit):
        path = self.root / f"phase-{index}.png"
        with Image.open(path) as source:
            frame = source.copy()
        edit(frame)
        frame.save(path)

    def review(self, verdict="pass"):
        self.package()
        path = self.root / "review.json"
        payload = json.loads((self.output / "evidence/visual-review-template.json").read_text())
        payload["verdict"] = verdict
        for stage in payload["stages"].values():
            stage["verdict"] = "pass"
        payload["stages"]["loop"]["normal_and_slow"] = True
        if verdict == "candidate-with-warnings":
            payload["warnings"] = ["Synthetic review fixture: restrained torso motion"]
        path.write_text(json.dumps(payload))
        return path, payload

    def snapshot(self):
        return {path.relative_to(self.output): path.read_bytes()
                for path in self.output.rglob("*") if path.is_file()}

    def test_packaging_preserves_png_bytes_and_all_sheet_rgba_cells(self):
        manifest, audit = self.package()
        self.assertEqual(audit["technical_verdict"], "pass")
        self.assertEqual((self.output / "source/master.png").read_bytes(),
                         (self.root / "master.png").read_bytes())
        with Image.open(self.output / manifest["sheet_path"]) as sheet:
            self.assertEqual(sheet.size, (48, 16))
            for index, record in enumerate(manifest["frames"]):
                source = self.root / f"phase-{index}.png"
                self.assertEqual((self.output / record["path"]).read_bytes(), source.read_bytes())
                with Image.open(source) as original:
                    self.assertEqual(sheet.crop((index*16, 0, (index+1)*16, 16)).tobytes(),
                                     original.tobytes())
                with Image.open(self.output / f"evidence/review/frame-{index:02d}.png") as review:
                    self.assertEqual(review.size, (1024, 1024))

    def test_gif_pixels_varying_durations_and_loop_are_exact(self):
        self.package()
        for name, factor in [("normal", 1), ("slow", 3)]:
            with Image.open(self.output / f"evidence/fixture-walk-east-{name}.gif") as gif:
                self.assertEqual(gif.n_frames, 3)
                self.assertEqual(gif.info["loop"], 0)
                for index, item in enumerate(self.contract["frames"]):
                    gif.seek(index)
                    self.assertEqual(gif.info["duration"], item["duration_ms"] * factor)
                    with Image.open(self.root / item["path"]) as source:
                        expected = MODULE.rendered(source, 4)
                    self.assertEqual(gif.convert("RGB").tobytes(), expected.tobytes())

    def test_one_shot_has_no_infinite_loop_extension(self):
        self.contract["loop"] = False
        self.package()
        for name in ["normal", "slow"]:
            with Image.open(self.output / f"evidence/fixture-walk-east-{name}.gif") as gif:
                self.assertNotIn("loop", gif.info)
                self.assertEqual(gif.n_frames, 3)

    def test_missing_review_stays_awaiting_even_after_technical_pass(self):
        _, audit = self.package()
        self.assertEqual(audit["verdict"], "awaiting-visual-review")
        self.assertEqual(audit["user_approval"], "pending")

    def test_stable_shape_follows_declared_body_translation(self):
        _, audit = self.package()
        self.assertEqual(len(audit["identity_regions"]), 3)
        self.assertTrue(all(item["mismatched_cells"] == 0 for item in audit["identity_regions"]))

    def test_head_fixed_on_canvas_while_body_moves_is_rejected(self):
        def freeze_head(frame):
            frame.paste((0, 0, 0, 0), (4, 2, 10, 8))
            with Image.open(self.root / "master.png") as master:
                frame.paste(master.crop((4, 2, 10, 7)), (4, 2))
        self.edit_frame(1, freeze_head)
        with self.assertRaisesRegex(ValueError, "Stable identity mismatch"):
            self.package()
        self.assertFalse(self.output.exists())

    def test_changed_identity_pixel_and_old_outline_remnant_are_rejected(self):
        original = (self.root / "phase-0.png").read_bytes()
        for coordinate in [(6, 3), (4, 2)]:
            with self.subTest(coordinate=coordinate):
                (self.root / "phase-0.png").write_bytes(original)
                self.edit_frame(0, lambda frame: frame.putpixel(coordinate, (20, 30, 40, 255)))
                with self.assertRaisesRegex(ValueError, "Stable identity mismatch"):
                    self.package()

    def test_invalid_alpha_empty_mode_or_size_is_rejected(self):
        original = (self.root / "phase-0.png").read_bytes()
        invalid = [Image.new("RGBA", (16, 16)), Image.new("RGB", (16, 16), "white"),
                   Image.new("RGBA", (8, 8), "white"), Image.new("RGBA", (16, 16), (1, 2, 3, 128))]
        for image in invalid:
            with self.subTest(mode=image.mode, size=image.size):
                image.save(self.root / "phase-0.png")
                with self.assertRaises(ValueError):
                    self.package()
                self.assertFalse(self.output.exists())
        (self.root / "phase-0.png").write_bytes(original)

    def test_mixed_directions_and_duplicate_phase_ids_are_rejected(self):
        self.contract["frames"][1]["direction"] = "west"
        with self.assertRaisesRegex(ValueError, "Mixed directions"):
            self.package()
        del self.contract["frames"][1]["direction"]
        self.contract["frames"][1]["phase_id"] = "pose-0"
        with self.assertRaisesRegex(ValueError, "Duplicate phase ids"):
            self.package()

    def test_transparent_rgb_difference_does_not_disguise_duplicate_pose(self):
        self.contract["stable_regions"] = []
        with Image.open(self.root / "phase-0.png") as source:
            duplicate = source.copy()
        duplicate.putpixel((0, 0), (41, 42, 43, 0))
        duplicate.save(self.root / "phase-1.png")
        with self.assertRaisesRegex(ValueError, "Duplicate visible frames"):
            self.package()

    def test_palette_and_padding_are_enforced_without_recoloring(self):
        self.edit_frame(0, lambda frame: frame.putpixel((11, 11), (123, 124, 125, 255)))
        with self.assertRaisesRegex(ValueError, "palette violation"):
            self.package()
        self.edit_frame(0, lambda frame: frame.putpixel((0, 12), (20, 30, 40, 255)))
        with self.assertRaisesRegex(ValueError, "padding"):
            self.package()

    def test_unrepresentable_gif_timing_is_rejected_without_rounding(self):
        self.contract["frames"][0]["duration_ms"] = 125
        with self.assertRaisesRegex(ValueError, "multiples of 10ms"):
            self.package()
        self.assertFalse(self.output.exists())

    def test_current_complete_review_passes_without_transferring_user_approval(self):
        path, payload = self.review()
        payload["user_approval"] = "approved"
        path.write_text(json.dumps(payload))
        _, audit = self.package(path)
        self.assertEqual(audit["verdict"], "pass")
        self.assertEqual(audit["user_approval"], "pending")
        self.assertEqual(audit["visual_review"]["user_approval"], "pending")
        self.assertEqual((self.output / "evidence/visual-review.json").read_bytes(), path.read_bytes())

    def test_candidate_requires_specific_warnings(self):
        path, payload = self.review("candidate-with-warnings")
        _, audit = self.package(path)
        self.assertEqual(audit["verdict"], "candidate-with-warnings")
        payload["warnings"] = []
        path.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, "explicit remaining concerns"):
            self.package(path)

    def test_incomplete_stages_frame_hashes_or_playback_review_are_rejected(self):
        path, payload = self.review()
        changes = []
        missing_stage = copy.deepcopy(payload)
        del missing_stage["stages"]["native_master"]
        changes.append(missing_stage)
        missing_hash = copy.deepcopy(payload)
        missing_hash["reviewed_frames"].pop()
        changes.append(missing_hash)
        incorrect_hash = copy.deepcopy(payload)
        incorrect_hash["reviewed_frames"][0]["rgba_sha256"] = "0" * 64
        changes.append(incorrect_hash)
        no_slow = copy.deepcopy(payload)
        no_slow["stages"]["loop"]["normal_and_slow"] = False
        changes.append(no_slow)
        before = self.snapshot()
        for candidate in changes:
            with self.subTest(candidate=candidate):
                path.write_text(json.dumps(candidate))
                with self.assertRaises(ValueError):
                    self.package(path)
                self.assertEqual(before, self.snapshot())

    def test_stale_pixels_timing_anchors_or_phase_names_preserve_prior_output(self):
        path, _ = self.review()
        before = self.snapshot()
        original = copy.deepcopy(self.contract)
        mutations = [lambda: self.contract["frames"][0].update(duration_ms=130),
                     lambda: self.contract.update(body_origin_px=[8, 9]),
                     lambda: self.contract["frames"][0].update(phase_id="different-contact")]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.contract = copy.deepcopy(original)
                mutation()
                with self.assertRaisesRegex(ValueError, "stale"):
                    self.package(path)
                self.assertEqual(before, self.snapshot())
        self.contract = original
        self.edit_frame(0, lambda frame: frame.putpixel((11, 11), (20, 30, 40, 255)))
        with self.assertRaisesRegex(ValueError, "stale"):
            self.package(path)
        self.assertEqual(before, self.snapshot())

    def test_explicit_visual_failure_overrides_technical_success(self):
        path, _ = self.review("fail")
        _, audit = self.package(path)
        self.assertEqual(audit["technical_verdict"], "pass")
        self.assertEqual(audit["verdict"], "fail")


if __name__ == "__main__":
    unittest.main()
