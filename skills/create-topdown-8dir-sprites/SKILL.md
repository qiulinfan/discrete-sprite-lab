---
name: create-topdown-8dir-sprites
description: Create rotation-continuous top-down eight-direction pixel character sets from generated or supplied raster art, including anchored view generation, canonical palette, Perfect Pixel recovery, 1:1 placement, circular transition checks, previews, metadata, and audit evidence. Use for eight-view top-down character poses or animation baselines; do not use for four-direction-only, isometric, 3D, or skeletal-rig work.
---

# Create Top-Down 8-Direction Sprites

Produce an auditable eight-view character set ordered `N, NE, E, SE, S, SW, W, NW`. Treat it as a circular rotation animation, not eight independent illustrations.

## Non-Negotiable Invariants

- Treat the final dimensions as a canvas contract, not a command to shrink the character to an arbitrary height.
- Generate each direction separately for detail, but condition them as one turnaround: approve `S` as the master; generate `N/E/W` from the master and one fixed landmark card; generate each diagonal from the master plus its two adjacent cardinal views.
- Use one landmark card across all views for foot baseline, rotation axis, head top, eye or ear line, shoulders, waist or belt, and major costume breaks. A final translation cannot repair inconsistent internal head-to-foot geometry.
- Use the same identity, costume, proportions, camera elevation, camera-relative lighting model, and neutral pose across all views.
- Convert each approved high-detail direction separately into a high-resolution pseudo-pixel source.
- Audit alpha-bbox occupancy again after pseudo-pixel conversion. If the generator changed character scale, normalize the transparent high-resolution sources to one shared visible height before Perfect Pixel; never rescale recovered logical pixels.
- Let Perfect Pixel recovery define the final logical pixels. Use `majority` sampling, disable automatic refinement, and calibrate an integer grid per direction when necessary.
- After recovery, forbid all non-integer resampling. Only crop transparent bounds, center, integer-translate, and pad with transparency.
- Select one approved palette authority, normally `S`, and map every direction to that canonical palette. Do not build the style authority by allowing all eight generated views to vote equally.
- For static and idle turnarounds, align the final foot rotation axis from the bottommost grounded support region, excluding suspended bows, blades, scabbards, capes, and effects. For one already-approved animation phase propagated across directions, use the stable head/torso body axis instead because the feet move around the gameplay root. Audit the applicable root across the full circle; repair excessive drift before pseudo-pixel recovery, not by deforming recovered pixels.
- Preserve raw generated sources. A checkerboard-looking or black background is not evidence of real transparency; inspect image mode and alpha values, then remove only corner-connected light or dark matte regions.

## Workflow

1. Write an asset and turnaround-continuity contract. Read [references/pipeline-contract.md](references/pipeline-contract.md) for the landmark card, generation graph, direction semantics, palette authority, CLI, and acceptance evidence.
2. Approve the `S` master, then create `N/E/W`, then the diagonals using both neighboring cardinals. Reject a source that violates internal landmarks. Uniform scale and integer or high-resolution translation are allowed only before pseudo-pixel conversion; do not piecewise-warp anatomy.
3. Convert each approved direction separately to a high-resolution pseudo-pixel image using the master view or palette card as the color reference. Require a coherent repeated lattice. Recheck source occupancy because generation can reintroduce scale drift; when needed, use the processor's pre-recovery source normalization rather than post-recovery resizing.
4. Name the sources exactly `north.png`, `northeast.png`, `east.png`, `southeast.png`, `south.png`, `southwest.png`, `west.png`, `northwest.png`.
5. Run `scripts/build_topdown_8dir.py`. Automatic integer-grid calibration, optional high-resolution source-occupancy normalization, `S` palette authority, fast circular preview, and continuity gates are defaults. Keep the default `--placement-axis foot` for static poses; pass `--placement-axis body` only when processing one approved action phase from `create-fixed-direction-action-sprites`.
6. Inspect the recovered 1:1 frames, continuity guide, `120ms` rotation GIF, slow GIF, transition metrics, and audit. If the foot axis aligns but head-to-foot offset still varies excessively, return to the high-detail sources.
7. Regenerate only a direction whose source pose, landmarks, lighting, or identity are wrong. Never repair source errors by stretching or shrinking recovered pixels.

## Review Priorities

- `N` and `NW/NE` must not accidentally read as frontal.
- `E/W` must read as real profiles with the expected single visible eye.
- `SE/S/SW` must retain the intended eyes and face landmarks; never delete eyes merely to signal direction.
- Opposite views should agree on height, body mass, hair volume, costume landmarks, and handed asymmetries.
- Adjacent views must transition smoothly around the complete loop, including `NW → N`; do not review only the 4x2 sheet.
- The selected placement axis is the hard gameplay pivot: `foot` for static turnarounds and `body` for one propagated action phase. Head and torso anchors remain continuity gates, not independent post-processing translation targets.
- Palette membership alone is insufficient. Review adjacent palette-distribution distance and painted highlight or shadow placement.
- A one-pixel visible-height spread is a useful default for a static pose. Change the tolerance only when perspective or animation genuinely requires it.
- Judge the sprites at native size and nearest-neighbor magnification. Smooth display scaling is not valid pixel-art evidence.

## Delivery Boundary

Keep prototypes outside engine production directories until the user approves the visual set. Engine import, pivots, PPU, slicing, animation clips, and prefab wiring are separate authorized work.

Match user-facing explanations, prompts, and handoffs to the user's language unless the user requests another language. Keep commands, filenames, structured keys, and raw errors unchanged.
