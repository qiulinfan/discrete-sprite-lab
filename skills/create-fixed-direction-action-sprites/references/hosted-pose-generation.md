# Hosted pose generation (Nano Banana 2.1)

Read this only after the user chose the hosted API over the current agent's
built-in image generation tool for a missing key pose. The script authors pose
geometry; it never produces inbetweens or animation.

`scripts/gemini_image.py` calls `gemini-nano-banana-2.1` through stateless
`generateContent`, one image per call. It declares NumPy/Pillow inline with an
adjacent lock file, so run it with `uv run` from the linked Skill directory.

## Credentials and authorization

The user names a key file holding one Gemini API key on one line, from a paid
Google AI Studio project (the free tier has no image output). Read it only at
call time; never print, copy or commit it. The script sends it only in the
Gemini key request header, never in a URL. `generate` refuses to run without
`--acknowledge-billable`, which may be passed only after the user authorized
that batch and its budget in the conversation.

```sh
uv run "$skill_dir/scripts/gemini_image.py" probe --credentials /path/to/gemini.txt
uv run "$skill_dir/scripts/gemini_image.py" generate \
  --credentials /path/to/gemini.txt --prompt-file prompt.txt \
  --reference approved-portrait.png --reference landmark-card.png \
  --aspect-ratio 1:1 --image-size 1K \
  --output-root /abs/output --name south-swing-key --acknowledge-billable
uv run "$skill_dir/scripts/gemini_image.py" matte \
  --input raw.png --output keyed.png --chroma '#00FF00' --key-mode global
```

- `probe` is a free model lookup. It proves the key reaches the model; it does
  not prove the project is on a paid tier. An HTTP 429 naming a
  `free_tier` metric with `limit: 0` means the key's project has no usable paid
  billing (unlinked, closed, or an unfinished prepay setup).
- `generate` passes references in priority order (identity master first), at
  most 14 per request. It appends a flat chroma background request (default
  `#FF00FF`; choose a colour absent from the costume), writes `raw.*`,
  `<name>.png` and `generation-receipt.json` (model, full prompt, reference
  names and hashes, usage, finish reason, cost estimate, matte statistics) into
  a fresh `<output-root>/<name>/`.
- `matte` keys a flat-background image offline, from either source. It keeps
  border-connected pixels within `--tolerance` of the chroma colour as
  background and removes up to two rings of chroma-tinted edge pixels. It
  refuses input that already has real Alpha. Check `matte.warnings`:
  `BACKGROUND_NOT_FLAT` means regenerate; `ENCLOSED_KEY_PIXELS` means chroma
  pixels remain inside the silhouette, so use `--key-mode global` only after
  confirming they are background gaps, not costume colour.

## Facts and limits (checked 2026-10-22)

- Standard price per image: 1K US$0.0336, 2K US$0.0504, 4K US$0.113, plus
  input at US$1.50 per million tokens; thinking tokens are extra. The Batch API
  halves these but is not wrapped by the script.
- Output may come back as JPEG even when the reference is PNG; the receipt
  records the actual MIME type. Expect compression noise at edges and a few
  chroma-tinted outline pixels until the canonical-palette step.
- A real 1K run with the approved south portrait kept costume and palette but
  drifted the face and recovered 54 px tall where the family is 52. Treat every
  generated pose as unreviewed source: lock same-view identity blocks, normalize
  height before Perfect Pixel, and map to the family palette before packaging.
