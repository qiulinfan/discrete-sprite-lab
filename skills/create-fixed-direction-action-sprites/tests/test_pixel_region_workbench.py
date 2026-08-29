#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pillow>=11,<13",
# ]
# ///

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pixel_region_workbench.py"
SPEC = importlib.util.spec_from_file_location("pixel_region_workbench", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PixelRegionWorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.regions = self.root / "regions.json"
        self.regions.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "canvas_size": [4, 4],
                    "regions": [
                        {
                            "id": "feature",
                            "rect": [1, 1, 3, 3],
                            "anchor": [2, 2],
                            "semantic_class": "stable_identity",
                            "phase_family": "all",
                            "allowed_transforms": ["identity"],
                            "context_ring": 1,
                        }
                    ],
                }
            )
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def image(self, path: Path, feature_color: tuple[int, int, int, int]) -> None:
        image = Image.new("RGBA", (4, 4), (10, 20, 30, 255))
        for y in range(1, 3):
            for x in range(1, 3):
                image.putpixel((x, y), feature_color)
        image.save(path)

    def test_review_uses_exact_nearest_neighbor_blocks(self) -> None:
        subject = self.root / "subject.png"
        reference = self.root / "reference.png"
        output = self.root / "review"
        self.image(subject, (200, 40, 50, 255))
        self.image(reference, (50, 80, 220, 255))

        MODULE.command_review(
            argparse.Namespace(
                image=subject,
                reference=reference,
                regions=self.regions,
                output_dir=output,
                scale=4,
                grid=False,
            )
        )

        rendered = Image.open(output / "feature-subject-4x.png").convert("RGB")
        self.assertEqual(rendered.size, (8, 8))
        self.assertEqual(len(rendered.getcolors(maxcolors=rendered.width * rendered.height)), 1)
        self.assertEqual(rendered.getpixel((0, 0)), (200, 40, 50))
        review = json.loads((output / "review.json").read_text())
        self.assertEqual(review["regions"][0]["exact_diff"]["changed_pixels"], 4)
        with Image.open(output / "feature-context-subject-4x.png") as context_review:
            self.assertEqual(context_review.size, (16, 16))
        self.assertEqual(
            review["regions"][0]["context_exact_diff"]["changed_pixels"], 4
        )

    def test_extract_and_apply_replace_only_agent_selected_cells(self) -> None:
        reference = self.root / "reference.png"
        target = self.root / "target.png"
        atlas = self.root / "atlas.json"
        placements = self.root / "placements.json"
        output = self.root / "output.png"
        receipt = self.root / "receipt.json"
        self.image(reference, (220, 180, 90, 255))
        self.image(target, (80, 60, 40, 255))

        MODULE.command_extract(
            argparse.Namespace(image=reference, regions=self.regions, output=atlas)
        )
        placements.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "target_sha256": MODULE.digest(target),
                    "placements": [{"feature_id": "feature", "anchor": [2, 2]}],
                }
            )
        )
        MODULE.command_apply(
            argparse.Namespace(
                image=target,
                atlas=atlas,
                placements=placements,
                output=output,
                receipt=receipt,
            )
        )

        result = Image.open(output).convert("RGBA")
        self.assertEqual(result.getpixel((1, 1)), (220, 180, 90, 255))
        self.assertEqual(result.getpixel((0, 0)), (10, 20, 30, 255))
        record = json.loads(receipt.read_text())
        self.assertTrue(record["unchanged_outside_writes"])
        self.assertFalse(record["resampling"])
        self.assertEqual(record["written_coordinates"], 4)

    def test_apply_rejects_stale_target(self) -> None:
        target = self.root / "target.png"
        atlas = self.root / "atlas.json"
        placements = self.root / "placements.json"
        self.image(target, (80, 60, 40, 255))
        MODULE.command_extract(
            argparse.Namespace(image=target, regions=self.regions, output=atlas)
        )
        placements.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "target_sha256": "0" * 64,
                    "placements": [{"feature_id": "feature", "anchor": [2, 2]}],
                }
            )
        )

        with self.assertRaisesRegex(ValueError, "Stale target"):
            MODULE.command_apply(
                argparse.Namespace(
                    image=target,
                    atlas=atlas,
                    placements=placements,
                    output=self.root / "output.png",
                    receipt=None,
                )
            )

    def test_transparent_feature_cells_clear_the_old_silhouette(self) -> None:
        reference = self.root / "reference.png"
        target = self.root / "target.png"
        atlas = self.root / "atlas.json"
        placements = self.root / "placements.json"
        output = self.root / "output.png"
        receipt = self.root / "receipt.json"
        canonical = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        canonical.putpixel((1, 1), (220, 180, 90, 255))
        canonical.save(reference)
        old = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        for y in range(1, 3):
            for x in range(1, 3):
                old.putpixel((x, y), (80, 60, 40, 255))
        old.save(target)

        MODULE.command_extract(
            argparse.Namespace(image=reference, regions=self.regions, output=atlas)
        )
        placements.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "target_sha256": MODULE.digest(target),
                    "placements": [{"feature_id": "feature", "anchor": [2, 2]}],
                }
            )
        )
        MODULE.command_apply(
            argparse.Namespace(
                image=target,
                atlas=atlas,
                placements=placements,
                output=output,
                receipt=receipt,
            )
        )

        result = Image.open(output).convert("RGBA")
        self.assertEqual(result.getpixel((1, 1)), (220, 180, 90, 255))
        self.assertEqual(result.getpixel((2, 1)), (0, 0, 0, 0))
        record = json.loads(receipt.read_text())
        self.assertEqual(record["transparent_written_coordinates"], 3)
        self.assertEqual(record["cleared_coordinates"], 3)
        self.assertTrue(record["unchanged_outside_writes"])

    def test_local_mirror_is_exact_and_bounded(self) -> None:
        reference = self.root / "reference.png"
        target = self.root / "target.png"
        atlas = self.root / "atlas.json"
        placements = self.root / "placements.json"
        output = self.root / "mirrored.png"
        image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        image.putpixel((1, 1), (255, 0, 0, 255))
        image.putpixel((2, 1), (0, 0, 255, 255))
        image.save(reference)
        Image.new("RGBA", (4, 4), (0, 0, 0, 0)).save(target)
        self.regions.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "canvas_size": [4, 4],
                    "regions": [
                        {
                            "id": "feature",
                            "rect": [1, 1, 3, 3],
                            "anchor": [2, 2],
                            "semantic_class": "phase_specific",
                            "phase_family": "paired-passing",
                            "allowed_transforms": ["identity", "mirror_x"],
                        }
                    ],
                }
            )
        )
        MODULE.command_extract(
            argparse.Namespace(image=reference, regions=self.regions, output=atlas)
        )
        placements.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "target_sha256": MODULE.digest(target),
                    "placements": [
                        {
                            "feature_id": "feature",
                            "anchor": [2, 2],
                            "transform": "mirror_x",
                        }
                    ],
                }
            )
        )
        MODULE.command_apply(
            argparse.Namespace(
                image=target,
                atlas=atlas,
                placements=placements,
                output=output,
                receipt=None,
            )
        )
        result = Image.open(output).convert("RGBA")
        self.assertEqual(result.getpixel((3, 1)), (255, 0, 0, 255))
        self.assertEqual(result.getpixel((2, 1)), (0, 0, 255, 255))


if __name__ == "__main__":
    unittest.main()
