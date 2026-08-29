#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=11,<13"]
# ///
"""Verify the curated Discrete Sprite Lab publication."""

from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
IDLE = ROOT / "art-pack/player/idle-8dir"
WALK = ROOT / "art-pack/player/walk-south-6f"
MAX_BYTES = 90 * 1024 * 1024


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_rgba_frame(path: Path) -> None:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        require(rgba.size == (64, 64), f"wrong frame size: {path} {rgba.size}")
        alpha = set(rgba.getchannel("A").get_flattened_data())
        require(alpha <= {0, 255}, f"partial Alpha: {path}")
        require(255 in alpha, f"empty frame: {path}")


def verify_gif(path: Path, expected_frames: int) -> None:
    with Image.open(path) as image:
        require(
            getattr(image, "n_frames", 1) == expected_frames,
            f"wrong GIF frame count: {path}",
        )


def main() -> int:
    required_root_files = (
        "README.md",
        "README.zh-CN.md",
        "ARTIFACTS.md",
        "LICENSE",
        "LICENSES/CC0-1.0.txt",
        "LICENSES/MIT.txt",
        "THIRD_PARTY.md",
        "docs/methodology.md",
        "docs/development-journal.md",
        "docs/failure-atlas.md",
    )
    for relative in required_root_files:
        require((ROOT / relative).is_file(), f"missing required file: {relative}")

    directions = {
        "south",
        "southeast",
        "east",
        "northeast",
        "north",
        "northwest",
        "west",
        "southwest",
    }
    idle_frames = {path.stem for path in (IDLE / "frames").glob("*.png")}
    require(idle_frames == directions, f"idle directions differ: {idle_frames}")
    for path in sorted((IDLE / "frames").glob("*.png")):
        verify_rgba_frame(path)

    walk_paths = sorted((WALK / "frames").glob("frame-*.png"))
    require(len(walk_paths) == 6, f"walk frame count is {len(walk_paths)}")
    for path in walk_paths:
        verify_rgba_frame(path)

    with Image.open(IDLE / "sheet.png") as sheet:
        require(sheet.size == (256, 128), f"wrong idle sheet size: {sheet.size}")
    with Image.open(WALK / "sheet.png") as sheet:
        require(sheet.size == (384, 64), f"wrong walk sheet size: {sheet.size}")

    verify_gif(IDLE / "previews/rotation.gif", 8)
    verify_gif(WALK / "previews/walk.gif", 6)

    json_count = 0
    for path in ROOT.rglob("*.json"):
        json.loads(path.read_text())
        json_count += 1

    unsafe_markers = (
        "/" + "Users/",
        "gh" + "o_",
        "api" + "_key",
        "api" + "-key",
        "pass" + "word",
    )
    text_suffixes = {".md", ".json", ".yaml", ".yml", ".py", ".toml", ".txt"}
    for path in ROOT.rglob("*"):
        if path.is_symlink():
            raise AssertionError(f"symlink is not allowed in publication: {path}")
        if not path.is_file():
            continue
        require(path.stat().st_size < MAX_BYTES, f"file exceeds 90 MiB: {path}")
        if path.suffix.lower() in text_suffixes:
            text = path.read_text(errors="replace")
            for marker in unsafe_markers:
                require(marker not in text, f"unsafe publication marker {marker!r}: {path}")

    local_link_count = 0
    for markdown in ROOT.rglob("*.md"):
        text = markdown.read_text()
        for target in re.findall(r"!?(?:\[[^\]]*\])\(([^)]+)\)", text):
            clean = target.split("#", 1)[0]
            if not clean or "://" in clean or clean.startswith("mailto:"):
                continue
            require((markdown.parent / clean).resolve().exists(), f"broken link: {markdown} -> {target}")
            local_link_count += 1

    print(
        "publication-ok "
        f"idle_frames={len(idle_frames)} walk_frames={len(walk_paths)} "
        f"json_files={json_count} local_links={local_link_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
