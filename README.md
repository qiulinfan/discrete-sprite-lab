# Discrete Sprite Lab

**AI-native pixel art, rebuilt on a discrete grid.**

[中文说明](README.zh-CN.md)

Discrete Sprite Lab is a public research-and-art repository about producing readable, temporally coherent pixel characters with generative image models. It contains an art pack, reproducible Codex Skills, production methodology, development history, and failures that changed the pipeline.

This project is intentionally permissive: art and documentation are released under **CC0 1.0**, while code and Agent Skills use the **MIT License**. Commercial use, modification, redistribution, and derivative works are welcome. See [LICENSE](LICENSE).

## Current art pack

| Asset | Native format | Preview |
| --- | --- | --- |
| Black-haired girl, idle turnaround | 8 directions × `64×64` RGBA | ![Eight-direction idle rotation](art-pack/player/idle-8dir/previews/rotation.gif) |
| Black-haired girl, south walk | 6 phases × `64×64` RGBA, 120 ms/frame | ![Six-frame south walk](art-pack/player/walk-south-6f/previews/walk.gif) |

The pack includes final logical frames, sprite sheets, normal and slow previews, accepted high-detail sources, pseudo-pixel sources, phase cards, audits, review evidence, and provenance receipts.

## The breakthrough

The pipeline treats pixel art as a discrete symbolic image instead of a small photograph:

1. Generate every view or action phase as a complete high-detail image.
2. Review anatomy and identity in high-detail image space.
3. Convert each accepted image into a high-resolution pseudo-pixel source.
4. Recover the underlying lattice with Perfect Pixel majority sampling.
5. Place recovered pixels `1:1` on a shared logical canvas; never resize after recovery.
6. Reason locally over exact `width × height × 4` RGBA cells.
7. Reuse stable identity blocks such as a same-view head or rigid emblem, including their transparent erase footprints.
8. Keep articulated skirt, hand, leg, and boot geometry phase-specific.
9. Separate hard integrity failures from visual diagnostics. Metrics inform review; they do not replace it.

Read [Methodology](docs/methodology.md) for the full contract.

## Why failures are included

The failed versions expose errors that a polished result hides:

- a second resize erased eyes and facial topology;
- incompatible temporal lattices and weak phase control created uneven motion;
- a broad identity mask produced perfect numerical symmetry while detaching arms and cutting joints;
- a cadence ratio outside a reference range still looked correct after normal-speed and slow-loop human review.

See the illustrated [Failure Atlas](docs/failure-atlas.md) and the chronological [Development Journal](docs/development-journal.md).

## Repository map

```text
art-pack/       Approved frames, sheets, sources, previews, and evidence
case-studies/   Selected failed artifacts and their audits
docs/           Methodology, journal, failure analysis, and reproducibility
skills/         Codex Skills and deterministic pixel-processing scripts
scripts/        Repository publication and verification helpers
```

Full local experiments and intermediate outputs live in the sibling workspace
`../discrete-sprite-lab-experiments/`. The directories above contain the selected
publication; experimental materials are maintained separately from Village_Rim's
game assets.

## Verify the publication

Install [uv](https://docs.astral.sh/uv/) and run:

```sh
uv run scripts/verify_pack.py
uv run skills/create-fixed-direction-action-sprites/tests/test_action_sprites.py
```

The verifier checks frame counts, `64×64` dimensions, binary Alpha, sheet dimensions, GIF phase counts, JSON parsing, publication-path hygiene, file size limits, local links, and symlink safety.

## Third-party boundary

Perfect Pixel is an external MIT-licensed dependency and is not vendored here. Image generation was performed with OpenAI ImageGen. See [THIRD_PARTY.md](THIRD_PARTY.md) and [Reproducibility](docs/reproducibility.md).

## License

- Art, examples, failure evidence, and documentation: [CC0 1.0 Universal](LICENSES/CC0-1.0.txt)
- Software and Agent Skills: [MIT](LICENSES/MIT.txt)

Attribution is appreciated but not required for CC0 material.

## Status

This is the first public snapshot. The south walk is temporal gold; the remaining seven walk directions have not yet been produced. Unity import data and the Village_Rim game project are intentionally outside this repository.
