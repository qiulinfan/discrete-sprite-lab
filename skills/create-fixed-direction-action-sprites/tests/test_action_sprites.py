"""Offline frame preservation, timing and complete-sequence regression tests."""
import io
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import action_sprites as A


class ActionSpritesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "out"
        self.plan = self.base / "plan.json"
        for i in range(4):
            image = Image.new("RGBA", (64, 64))
            ImageDraw.Draw(image).rectangle((20 + i, 15, 32 + i, 48), fill=(100 + i, 80, 40, 255))
            info = PngImagePlugin.PngInfo()
            info.add_text("source", f"authored-pose-{i}")
            image.save(self.base / f"{i}.png", pnginfo=info)
        self.c = {"schema_version": 3, "action": "walk", "route": "procedural", "controller_or_pose_authority": "fixture controller and authored contact", "reference_family": "fixture same-view source", "image_size": [64, 64], "frame_count": 4, "durations_ms": [80, 140, 90, 110], "loop": True, "pivot": [32, 3], "ppu": "fixture family", "directions": [{"direction": d, "frames": [{"path": f"{i}.png", "phase": f"planned-phase-{i}", "origin": "authored-key" if i == 0 else "procedural"} for i in range(4)]} for d in ("south", "east")]}

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self):
        A.save(self.plan, self.c)
        return A.prepare(self.plan, self.root)

    def test_exact_key_and_controller_pngs_preserve_metadata_and_pixels(self):
        self.prepare()
        result = A.assemble(self.root)
        self.assertEqual(result["frames"], 8)
        m = A.load(self.root / "generated/manifest.json")
        self.assertNotIn("sha256", str(m))
        self.assertFalse(m["production_approved"])
        self.assertEqual(m["frames"][0]["origin"], "authored-key")
        self.assertEqual(m["frames"][4]["rect"], [0, 64, 64, 64])
        with Image.open(self.root / "generated/sheet.png") as sheet:
            self.assertEqual(sheet.size, (256, 128))
            for row, d in enumerate(("south", "east")):
                for i in range(4):
                    p = self.root / f"generated/{d}/frame-{i:02d}.png"
                    self.assertEqual(p.read_bytes(), (self.base / f"{i}.png").read_bytes())
                    self.assertEqual(sheet.crop((i * 64, row * 64, (i + 1) * 64, (row + 1) * 64)).tobytes(), Image.open(p).convert("RGBA").tobytes())
        with Image.open(self.root / "evidence/review/south/frame-00.png") as review:
            self.assertEqual(review.size, (1024, 1024))

    def test_loop_normal_and_slow_playback_preserves_per_frame_timing(self):
        self.prepare(); A.assemble(self.root)
        for label, multiplier in (("normal", 1), ("slow", 3)):
            with Image.open(self.root / f"generated/south-{label}.png") as anim:
                self.assertEqual(anim.info["loop"], 0)
                self.assertEqual(anim.n_frames, 4)
                for i, duration in enumerate(self.c["durations_ms"]):
                    anim.seek(i)
                    self.assertEqual(anim.info["duration"], duration * multiplier)
                    self.assertEqual(anim.convert("RGBA").tobytes(), Image.open(self.base / f"{i}.png").convert("RGBA").tobytes())

    def test_authored_keys_are_a_valid_sequence_without_invented_inbetweens(self):
        self.c["route"] = "authored"
        for row in self.c["directions"]:
            for f in row["frames"]: f.pop("origin")
        self.prepare(); A.assemble(self.root)
        self.assertEqual({f["origin"] for f in A.load(self.root / "generated/manifest.json")["frames"]}, {"authored-key"})

    def test_incomplete_flat_pose_list_is_rejected_before_workspace_creation(self):
        self.c["directions"][0]["frames"] = self.c["directions"][0]["frames"][:2]
        with self.assertRaisesRegex(ValueError, "Supply every final frame"):
            self.prepare()
        self.assertFalse(self.root.exists())

    def test_old_model_contract_and_new_model_fields_are_rejected(self):
        self.c["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "schema_version"):
            self.prepare()
        self.c["schema_version"] = 3
        self.c["budget_file"] = "old-task-budget.json"
        with self.assertRaisesRegex(ValueError, "offline workflow"):
            self.prepare()
        self.assertFalse(self.root.exists())

    def test_prepared_input_tampering_stops_packaging(self):
        self.prepare()
        (self.root / "inputs/south/00.png").write_bytes((self.base / "1.png").read_bytes())
        with self.assertRaisesRegex(ValueError, "input changed"):
            A.assemble(self.root)

    def test_prepared_contract_tampering_requires_a_new_version(self):
        self.prepare()
        c = A.load(self.root / "contract.json"); c["durations_ms"][0] = 900
        A.save(self.root / "contract.json", c)
        with self.assertRaisesRegex(ValueError, "contract changed"):
            A.assemble(self.root)

    def test_wrong_size_empty_and_matte_inputs_are_rejected(self):
        images = [Image.new("RGBA", (32, 32)), Image.new("RGBA", (64, 64)), Image.new("RGBA", (64, 64), (20, 20, 20, 255))]
        for image in images:
            with self.subTest(size=image.size, box=image.getbbox()):
                image.save(self.base / "0.png")
                with self.assertRaises(ValueError): self.prepare()
                self.assertFalse(self.root.exists())

    def test_one_shot_ending_hold_is_recorded_and_preserved(self):
        self.c.update(loop=False, final_hold_ms=350)
        self.prepare(); A.assemble(self.root)
        self.assertEqual(A.load(self.root / "generated/manifest.json")["final_hold_ms"], 350)
        for label, multiplier in (("normal", 1), ("slow", 3)):
            with Image.open(self.root / f"generated/south-{label}.png") as anim:
                self.assertEqual(anim.info["loop"], 1)
                anim.seek(3)
                self.assertEqual(anim.info["duration"], (110 + 350) * multiplier)

    def test_palette_cap_is_a_gate_without_recoloring(self):
        self.c["palette_max_colors"] = 1
        self.prepare()
        with self.assertRaisesRegex(ValueError, "palette cap"):
            A.assemble(self.root)
        self.assertFalse((self.root / "generated/manifest.json").exists())
        self.assertEqual((self.root / "inputs/south/00.png").read_bytes(), (self.base / "0.png").read_bytes())

    def test_repeated_return_pose_requires_an_explicit_pair(self):
        self.c["directions"][0]["frames"][3]["path"] = "0.png"
        self.prepare()
        with self.assertRaisesRegex(ValueError, "Unexpected repeated"):
            A.assemble(self.root)
        self.root = self.base / "return-pose"
        self.c["allowed_repeated_frame_pairs"] = [[0, 3]]
        self.prepare(); A.assemble(self.root)

    def test_adjacent_held_pose_uses_duration_instead_of_duplicate_frames(self):
        self.c["directions"][0]["frames"][1]["path"] = "0.png"
        self.c["allowed_repeated_frame_pairs"] = [[0, 1]]
        self.prepare()
        with self.assertRaisesRegex(ValueError, "frame duration"):
            A.assemble(self.root)

    def test_complete_workflow_needs_no_socket_or_credential(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            self.prepare(); A.assemble(self.root)

    def test_no_online_run_command_is_exposed(self):
        with patch.object(sys, "argv", ["action_sprites.py", "run", "--root", str(self.root)]), patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as error: A.main()
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
