# Reproducibility and provenance

Current actions use authored poses and procedural animation; see
[the current workflow and validation](action-workflow.md). Historical model
experiments correspond to product commit `ad3249b42aa874350362dcf9c6204215ef50f0c2`.
Their recorded images remain preserved; retired transport code is not part of
the current Skill. The operations below describe the historical art pack.

## What is reproducible

The repository includes the deterministic stages after image generation:

- checkerboard or matte extraction;
- Perfect Pixel majority recovery;
- per-source integer grid records;
- `1:1` logical placement;
- canonical palette and binary Alpha;
- exact local RGBA extraction, comparison, and stale-safe writes;
- magnified previews, temporal/spatial metrics, manifests, and audits.

The two Codex Skills under `skills/` contain PEP 723 dependency declarations and can be executed with `uv run`.

## What is not deterministic

Image generation itself is stochastic. Accepted high-detail and pseudo-pixel outputs are preserved so the deterministic half of the pipeline can be studied and rerun without pretending that a text prompt guarantees identical art.

## Publication sanitization

Source receipts and audit JSON originally contained workstation-absolute paths. `scripts/sanitize_metadata.py` replaces only those path strings with `source-project://` or `source-workspace://` identifiers before publication. Binary art is unchanged. Because the JSON text changes, any hash that referred to the original metadata file is provenance-only; hashes of image artifacts remain meaningful.

## Validation

Run:

```sh
uv run scripts/verify_pack.py
```

The verification script intentionally checks publication facts rather than regenerating ImageGen outputs.
