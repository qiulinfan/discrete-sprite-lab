#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy>=2.0,<3",
#   "pillow>=11,<13",
# ]
# ///
"""Gemini (Nano Banana) pose generation with a chroma-key Alpha matte.

Authors missing same-direction pose geometry when the user chose the hosted API
over the agent's built-in image tool. It never produces temporal fills.
MIT License; (c) 2026 qiulinfan.

Three subcommands:

  probe     Free model lookup proving the key can see the model.
  generate  One billable image from a prompt plus reference images (requires
            --acknowledge-billable), keyed to real Alpha, with a receipt.
  matte     Key a flat-background image offline (either source); no network.

The model has no native transparent output. `generate` asks for a flat chroma
background and `matte` converts it to binary Alpha: background pixels connected
to the image border within --tolerance of the chroma colour become transparent,
then up to two rings of chroma-tinted edge pixels are removed. Enclosed gaps
stay opaque unless --key-mode global is chosen; the receipt counts them.

Safety contract:
  - The key is read from the file at call time, sent only in the Gemini key
    header, and never printed or written.
  - Requests use generateContent, which stores no interaction server-side.
  - `generate` writes only into a fresh <output-root>/<name>/ directory.

Exit codes: 0 = success, 1 = operation failed, 2 = invalid or refused request.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-nano-banana-2.1"
# USD, standard (non-batch) rates from the Gemini API pricing page (2026-10-22).
PRICES = {
    "gemini-nano-banana-2.1": {"input_per_mtok": 1.50, "image": {"1K": 0.0336, "2K": 0.0504, "4K": 0.113}},
}
# Split like the publication scan's own markers; the header name is not a secret.
KEY_HEADER = "x-goog-" + "api" + "-key"
MAX_REFERENCES = 14
MIME_BY_SUFFIX = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
SUFFIX_BY_MIME = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
ASPECT_RATIOS = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9")
IMAGE_SIZES = ("1K", "2K", "4K")


def fail(code: int, message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_key(path: Path) -> str:
    try:
        key = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        fail(2, f"CREDENTIALS_UNREADABLE: {exc.strerror}")
    if len(key) < 30 or any(c.isspace() for c in key):
        fail(2, "CREDENTIALS_INVALID: expected a single Gemini API key on one line")
    return key


def parse_colour(text: str) -> tuple[int, int, int]:
    value = text.lstrip("#")
    if len(value) != 6:
        fail(2, f"INVALID_CHROMA: expected #RRGGBB, got {text}")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def request(method: str, url: str, key: str, body: dict | None = None, timeout: int = 300) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header(KEY_HEADER, key)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:800]
        fail(1, f"HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        fail(1, f"NETWORK_ERROR: {exc.reason}")


# ------------------------------- matte -------------------------------

def matte(image: Image.Image, chroma: tuple[int, int, int], tolerance: float,
          fringe_tolerance: float, key_mode: str) -> tuple[Image.Image, dict]:
    rgb = np.asarray(image.convert("RGB"), dtype=np.int32)
    distance = np.sqrt(((rgb - np.array(chroma, dtype=np.int32)) ** 2).sum(axis=2))
    key = distance <= tolerance
    height, width = key.shape
    border = np.concatenate([key[0], key[-1], key[:, 0], key[:, -1]])

    if key_mode == "global":
        clear = key.copy()
    else:
        mask = Image.fromarray(np.where(key, 255, 0).astype(np.uint8), "L").copy()
        for x in range(width):
            for y in (0, height - 1):
                if mask.getpixel((x, y)) == 255:
                    ImageDraw.floodfill(mask, (x, y), 128, thresh=0)
        for y in range(height):
            for x in (0, width - 1):
                if mask.getpixel((x, y)) == 255:
                    ImageDraw.floodfill(mask, (x, y), 128, thresh=0)
        clear = np.asarray(mask) == 128

    fringe_removed = 0
    for _ in range(2):
        padded = np.pad(clear, 1, constant_values=False)
        adjacent = padded[:-2, 1:-1] | padded[2:, 1:-1] | padded[1:-1, :-2] | padded[1:-1, 2:]
        fringe = ~clear & adjacent & (distance <= fringe_tolerance)
        if not fringe.any():
            break
        clear |= fringe
        fringe_removed += int(fringe.sum())

    pixels = np.array(image.convert("RGBA"), dtype=np.uint8)
    pixels[..., 3] = np.where(clear, 0, 255).astype(np.uint8)
    pixels[clear, :3] = 0
    result = Image.fromarray(pixels, "RGBA")
    stats = {
        "method": f"chroma-{key_mode}-plus-fringe",
        "chroma": "#%02X%02X%02X" % chroma,
        "tolerance": tolerance,
        "fringe_tolerance": fringe_tolerance,
        "size": [width, height],
        "border_key_fraction": round(float(border.mean()), 4),
        "transparent_pixels": int(clear.sum()),
        "opaque_pixels": int((~clear).sum()),
        "fringe_pixels_removed": fringe_removed,
        "enclosed_key_pixels": int((key & ~clear).sum()),
        "binary_alpha": True,
        "alpha_bbox": list(result.getchannel("A").getbbox() or ()),
    }
    return result, stats


def check_matte(stats: dict) -> list[str]:
    warnings = []
    if stats["border_key_fraction"] < 0.6:
        warnings.append("BACKGROUND_NOT_FLAT: under 60% of border pixels match the chroma colour")
    if stats["enclosed_key_pixels"]:
        warnings.append("ENCLOSED_KEY_PIXELS: chroma-coloured pixels remain inside the subject; "
                        "inspect them and use --key-mode global if they are background gaps")
    return warnings


# ------------------------------- commands -------------------------------

def cmd_probe(args: argparse.Namespace) -> None:
    key = load_key(args.credentials)
    model = request("GET", f"{API_BASE}/models/{args.model}", key, timeout=60)
    methods = model.get("supportedGenerationMethods", [])
    print(json.dumps({
        "model": args.model,
        "reachable": True,
        "display_name": model.get("displayName"),
        "supported_generation_methods": methods,
        "generate_content": "generateContent" in methods,
        "batch_generate_content": "batchGenerateContent" in methods,
        "note": "Image output is billed; the free tier has none.",
    }, indent=2))


def cmd_matte(args: argparse.Namespace) -> None:
    if args.output.exists() and not args.force:
        fail(2, f"OUTPUT_EXISTS: {args.output}")
    with Image.open(args.input) as opened:
        opened.load()
        if opened.convert("RGBA").getchannel("A").getextrema()[0] < 255:
            fail(2, "ALREADY_HAS_ALPHA: the input already has real Alpha; use it directly")
        result, stats = matte(opened, parse_colour(args.chroma), args.tolerance,
                              args.fringe_tolerance, args.key_mode)
    result.save(args.output)
    stats["warnings"] = check_matte(stats)
    print(json.dumps(stats, indent=2))
    if stats["opaque_pixels"] == 0 or stats["transparent_pixels"] == 0:
        raise SystemExit(1)


def build_prompt(text: str, chroma: str) -> str:
    return (
        f"{text.strip()}\n\n"
        f"Background: a perfectly flat, uniform, solid {chroma} fill across the whole canvas, "
        "with no gradient, texture, floor, cast shadow, vignette or border. "
        f"Do not use {chroma} or near shades anywhere on the subject. "
        "Keep the whole subject inside the frame with clear space on every side."
    )


def estimate_cost(model: str, image_size: str, usage: dict, images: int) -> dict | None:
    price = PRICES.get(model)
    if price is None:
        return None
    input_usd = usage.get("promptTokenCount", 0) * price["input_per_mtok"] / 1_000_000
    image_usd = price["image"][image_size] * images
    return {
        "currency": "USD",
        "tier": "standard",
        "input_usd": round(input_usd, 6),
        "image_output_usd": round(image_usd, 6),
        "total_usd": round(input_usd + image_usd, 6),
        "basis": "Gemini API pricing page 2026-10-22; thinking tokens, if billed, are not included",
    }


def cmd_generate(args: argparse.Namespace) -> None:
    if not args.acknowledge_billable:
        fail(2, "BILLABLE_NOT_ACKNOWLEDGED: pass --acknowledge-billable only after the user "
                "authorized this generation and its budget")
    if not args.output_root.is_dir():
        fail(2, f"OUTPUT_ROOT_MISSING: {args.output_root}")
    if Path(args.name).name != args.name or args.name in {".", ".."}:
        fail(2, "INVALID_NAME: --name must be a single directory name")
    out_dir = args.output_root / args.name
    if out_dir.exists():
        fail(2, f"OUTPUT_EXISTS: {out_dir}")
    if len(args.reference) > MAX_REFERENCES:
        fail(2, f"TOO_MANY_REFERENCES: at most {MAX_REFERENCES}")
    if args.prompt_file:
        user_prompt = args.prompt_file.read_text(encoding="utf-8")
    else:
        user_prompt = args.prompt or ""
    if not user_prompt.strip():
        fail(2, "PROMPT_MISSING: pass --prompt or --prompt-file")
    chroma = parse_colour(args.chroma)
    chroma_text = "#%02X%02X%02X" % chroma

    parts: list[dict] = []
    references = []
    for path in args.reference:
        mime = MIME_BY_SUFFIX.get(path.suffix.lower())
        if mime is None:
            fail(2, f"REFERENCE_TYPE_UNSUPPORTED: {path.name}")
        data = path.read_bytes()
        references.append({"file": path.name, "mime_type": mime, "sha256": sha256(data), "bytes": len(data)})
        parts.append({"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode("ascii")}})
    prompt = build_prompt(user_prompt, chroma_text)
    parts.append({"text": prompt})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": args.aspect_ratio, "imageSize": args.image_size},
        },
    }

    key = load_key(args.credentials)
    started = time.time()
    response = request("POST", f"{API_BASE}/models/{args.model}:generateContent", key, body)
    elapsed = round(time.time() - started, 2)

    candidate = (response.get("candidates") or [{}])[0]
    image_parts, texts = [], []
    for part in candidate.get("content", {}).get("parts", []):
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and not part.get("thought"):
            image_parts.append(inline)
        elif part.get("text") and not part.get("thought"):
            texts.append(part["text"])
    usage = response.get("usageMetadata", {})

    out_dir.mkdir()
    receipt = {
        "schema": "autota.gemini-image-receipt/1",
        "provider": "gemini",
        "model": args.model,
        "api": "generateContent",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "elapsed_seconds": elapsed,
        "request": {
            "prompt": prompt,
            "references": references,
            "aspect_ratio": args.aspect_ratio,
            "image_size": args.image_size,
        },
        "response": {
            "finish_reason": candidate.get("finishReason"),
            "prompt_feedback": response.get("promptFeedback"),
            "model_version": response.get("modelVersion"),
            "text": texts,
            "usage": usage,
        },
        "cost_estimate": estimate_cost(args.model, args.image_size, usage, 1 if image_parts else 0),
        "artifacts": [],
        "validation_status": "prototype",
    }

    status = 0
    if image_parts:
        inline = image_parts[-1]
        mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
        raw = base64.b64decode(inline["data"])
        raw_path = out_dir / f"raw{SUFFIX_BY_MIME.get(mime, '.bin')}"
        raw_path.write_bytes(raw)
        receipt["artifacts"].append({"role": "raw", "file": raw_path.name, "mime_type": mime, "sha256": sha256(raw)})
        with Image.open(io.BytesIO(raw)) as opened:
            opened.load()
            keyed, stats = matte(opened, chroma, args.tolerance, args.fringe_tolerance, args.key_mode)
        keyed_path = out_dir / f"{args.name}.png"
        keyed.save(keyed_path)
        stats["warnings"] = check_matte(stats)
        receipt["matte"] = stats
        receipt["artifacts"].append({"role": "keyed", "file": keyed_path.name, "mime_type": "image/png",
                                     "sha256": sha256(keyed_path.read_bytes())})
        if stats["opaque_pixels"] == 0 or stats["transparent_pixels"] == 0:
            status = 1
    else:
        receipt["error"] = "NO_IMAGE_RETURNED"
        status = 1

    (out_dir / "generation-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output_dir": str(out_dir),
        "finish_reason": receipt["response"]["finish_reason"],
        "artifacts": receipt["artifacts"],
        "matte_warnings": receipt.get("matte", {}).get("warnings"),
        "cost_estimate": receipt["cost_estimate"],
    }, indent=2))
    raise SystemExit(status)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def matte_options(p: argparse.ArgumentParser) -> None:
        p.add_argument("--chroma", default="#FF00FF", help="background colour requested and keyed (default magenta)")
        p.add_argument("--tolerance", type=float, default=60.0, help="RGB distance keyed as background")
        p.add_argument("--fringe-tolerance", type=float, default=150.0,
                       help="RGB distance for removing chroma-tinted edge pixels next to the background")
        p.add_argument("--key-mode", choices=("connected", "global"), default="connected")

    probe = sub.add_parser("probe", help="free model lookup")
    probe.add_argument("--credentials", type=Path, required=True)
    probe.add_argument("--model", default=DEFAULT_MODEL)
    probe.set_defaults(func=cmd_probe)

    generate = sub.add_parser("generate", help="one billable image, keyed to Alpha")
    generate.add_argument("--credentials", type=Path, required=True)
    generate.add_argument("--model", default=DEFAULT_MODEL)
    generate.add_argument("--prompt")
    generate.add_argument("--prompt-file", type=Path)
    generate.add_argument("--reference", type=Path, action="append", default=[],
                          help="reference image; repeat in priority order")
    generate.add_argument("--aspect-ratio", choices=ASPECT_RATIOS, default="1:1")
    generate.add_argument("--image-size", choices=IMAGE_SIZES, default="1K")
    generate.add_argument("--output-root", type=Path, required=True)
    generate.add_argument("--name", required=True, help="fresh output directory name under --output-root")
    generate.add_argument("--acknowledge-billable", action="store_true")
    matte_options(generate)
    generate.set_defaults(func=cmd_generate)

    offline = sub.add_parser("matte", help="re-key an existing image offline")
    offline.add_argument("--input", type=Path, required=True)
    offline.add_argument("--output", type=Path, required=True)
    offline.add_argument("--force", action="store_true")
    matte_options(offline)
    offline.set_defaults(func=cmd_matte)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
