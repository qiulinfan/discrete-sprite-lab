"""Offline tests for the hosted pose generator: billing handshake, key handling and matte."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
GEMINI = SKILL / "scripts" / "gemini_image.py"


def ppm(path, pixels, size=8):
    path.write_bytes(f"P6 {size} {size} 255\n".encode() + bytes(c for p in pixels for c in p))


class GeminiImageTests(unittest.TestCase):
    def run_gemini(self, *arguments):
        uv = shutil.which("uv")
        self.assertIsNotNone(uv, "uv runs the script's declared NumPy/Pillow dependencies")
        env = dict(os.environ, UV_NO_PROGRESS="1")
        return subprocess.run([uv, "run", str(GEMINI), *arguments], capture_output=True, text=True, timeout=120, env=env)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_skill_asks_for_the_image_source(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for marker in ("scripts/gemini_image.py", "built-in image generation", "do not choose for them", "never", "matte"):
            self.assertIn(marker, text)

    def test_generate_refuses_billable_without_acknowledgement(self):
        result = self.run_gemini("generate", "--credentials", "unused.txt", "--prompt", "x", "--output-root", ".", "--name", "x")
        self.assertEqual(2, result.returncode)
        self.assertIn("BILLABLE_NOT_ACKNOWLEDGED", result.stderr)

    def test_key_travels_only_in_header(self):
        source = GEMINI.read_text(encoding="utf-8")
        self.assertIn("req.add_header(KEY_HEADER, key)", source)
        self.assertNotIn("?key=", source)

    def test_matte_keys_border_background_to_binary_alpha(self):
        # Magenta canvas, 4x4 blue subject with a magenta-tinted edge column and one enclosed magenta pixel.
        pixels = []
        for y in range(8):
            for x in range(8):
                if (x, y) == (4, 4):
                    pixels.append((255, 0, 255))
                elif 2 <= x <= 5 and 2 <= y <= 5:
                    pixels.append((200, 60, 200) if x == 2 else (30, 60, 160))
                else:
                    pixels.append((255, 0, 255))
        ppm(self.root / "source.ppm", pixels)
        result = self.run_gemini("matte", "--input", str(self.root / "source.ppm"), "--output", str(self.root / "keyed.png"))
        self.assertEqual(0, result.returncode, result.stderr)
        stats = json.loads(result.stdout)
        self.assertEqual(4, stats["fringe_pixels_removed"])
        self.assertEqual(1, stats["enclosed_key_pixels"])
        self.assertEqual(48 + 4, stats["transparent_pixels"])
        self.assertTrue(any("ENCLOSED_KEY_PIXELS" in w for w in stats["warnings"]))
        rekeyed = self.run_gemini("matte", "--input", str(self.root / "source.ppm"), "--output", str(self.root / "global.png"), "--key-mode", "global")
        self.assertEqual(0, json.loads(rekeyed.stdout)["enclosed_key_pixels"])
        # Output already carries real Alpha, so keying it again is refused.
        again = self.run_gemini("matte", "--input", str(self.root / "keyed.png"), "--output", str(self.root / "again.png"))
        self.assertEqual(2, again.returncode)
        self.assertIn("ALREADY_HAS_ALPHA", again.stderr)


if __name__ == "__main__":
    unittest.main()
