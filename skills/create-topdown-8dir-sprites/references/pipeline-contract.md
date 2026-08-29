# Pipeline Contract and Operating Reference

Read this reference when preparing a new eight-direction asset, prompting the raster generator, running the processor, or reviewing a delivery.

## Asset Contract

Record these facts before generation:

- character identity, age range, body proportions, hair, costume, equipment, and protected asymmetric details;
- gameplay role and pose or animation state;
- camera projection and elevation, with top-down rather than isometric explicitly stated;
- direction order: `N, NE, E, SE, S, SW, W, NW`;
- final canvas dimensions, intended visible-height target and tolerance, bottom contact, pivot, and PPU assumption;
- canonical palette authority, normally `south.png`, and whether painted lighting is camera-relative or world-relative;
- normalized turnaround landmarks: foot baseline, rotation-axis X, head top, eye or ear line, shoulder line, waist or belt line, and protected costume breaks;
- high-detail and pseudo-pixel source locations;
- palette limit or approved palette family;
- alpha policy, filenames, intended engine destination, and approval boundary;
- generator provenance, source hashes, processing versions, and license facts when applicable.

## Direction Semantics

| File | Character faces | Expected face visibility |
| --- | --- | --- |
| `north.png` | away/up | back of head; no frontal face |
| `northeast.png` | away-right/up-right | rear three-quarter; little or no frontal face |
| `east.png` | right | true profile; one visible eye when unobscured |
| `southeast.png` | toward-right/down-right | front three-quarter; readable eyes and nose direction |
| `south.png` | toward camera/down | frontal face |
| `southwest.png` | toward-left/down-left | front three-quarter; readable eyes and nose direction |
| `west.png` | left | true profile; one visible eye when unobscured |
| `northwest.png` | away-left/up-left | rear three-quarter; little or no frontal face |

Treat direction semantics as visual requirements, not instructions to erase facial features. If a diagonal source reads frontal, regenerate that source.

## Two-Pass Generation Pattern

Do not generate the directions as eight unrelated jobs or as one low-precision sheet. Use this reference graph:

1. Approve `S` as the identity, proportion, palette, lighting, and landmark master.
2. Generate `N`, `E`, and `W` separately from `S` plus the same landmark card.
3. Generate `SE` from `S + E`, `SW` from `S + W`, `NE` from `N + E`, and `NW` from `N + W`; include the `S` identity master when the tool supports a third reference.

This graph gives each diagonal two neighboring structural constraints without accumulating sequential drift around the circle.

For every high-detail pass, request one isolated full-body character, one exact direction, a fixed top-down camera, identical neutral pose, consistent proportions, one lighting model, and a transparent background. Overlay or provide the same landmark card. Before pseudo-pixel conversion, compare every source against the master landmarks. Uniform scaling and translation are permitted at high resolution when they preserve anatomy; regenerate when eye or ear line, shoulder, waist, head-to-foot axis, or costume breaks remain inconsistent. Never solve internal proportion errors with a piecewise warp.

For the pseudo-pixel pass, transform only that approved direction. Supply `S` or an extracted palette card as the color authority. Require large coherent square pixel clusters aligned to one repeated grid, hard nearest-neighbor-like edges, no antialiasing, no painterly texture, unchanged anatomy and costume, and transparent background. Do not ask the model to redesign or relight the character.

Measure alpha-bbox occupancy again after this pass. A generator can preserve identity yet change character scale relative to the canvas. When that drift prevents a common recovered height, normalize every transparent pseudo-pixel source to one shared high-resolution visible height with nearest-neighbor sampling before Perfect Pixel. This is a source-conditioning step: record it, keep the original pseudo-pixel files, and never use it to hide internal proportion errors. Recovered logical frames remain strictly 1:1 and must not be rescaled.

Image generators may return RGB images with a baked checkerboard despite a transparency request. Keep the raw file, record the mode, and let the processor recover only corner-connected neutral matte pixels. Visually inspect pale costume edges after recovery.

## Processor

The script has PEP 723 dependencies and is intended to run with `uv`:

```sh
uv run scripts/build_topdown_8dir.py \
  --pseudo-dir /absolute/path/to/pseudo-pixel-directions \
  --output-root /absolute/path/to/output \
  --artifact-slug character-idle-8dir-64 \
  --frame-size 64 \
  --normalize-source-visible-height 0 \
  --target-visible-height 52 \
  --height-tolerance 1 \
  --target-bottom 61 \
  --colors 32 \
  --palette-reference south \
  --rotation-ms 120 \
  --axis-tolerance 0.5 \
  --max-head-foot-offset-spread 2
```

The automatic calibration begins with `--grid 64`, measures each recovered visible height, and makes an integer grid correction with refinement fixed at zero. To reproduce an approved calibration exactly, pass overrides:

`--normalize-source-visible-height 0` preserves source occupancy. Set it to a measured high-resolution alpha-bbox height only when the pseudo-pixel generator reintroduced uniform scale drift. The processor writes normalized copies under `working/source-normalized/`; originals remain untouched. This step uses nearest-neighbor sampling before majority recovery and is distinct from forbidden post-recovery resampling.

Calibration candidates that recover no visible pixels are recorded as invalid and skipped; they do not abort the remaining directions when another bounded integer candidate is valid.

```sh
--grid-overrides north=64,northeast=67,east=61,southeast=68,south=64,southwest=64,west=69,northwest=67
```

The processor must fail rather than rescale when a recovered sprite cannot fit the requested canvas or bottom contact.

The final placement aligns the extent midpoint of the bottommost 4% grounded support region to the frame pivot. This stabilizes the gameplay rotation axis without allowing suspended bows, blades, scabbards, capes, or effects to drag the root sideways. Because a single translation cannot also repair an inconsistent head-to-foot axis, the script records head, torso, and foot landmarks and gates the head-to-foot offset spread. A failure at that gate returns to high-detail generation or high-resolution normalization.

`--palette-reference south` derives the canonical OKLab medoid palette only from the approved master and maps all views into it. Use `shared` only when the user explicitly approves all views as equal palette authorities.

## Expected Output

- `working/source-transparent/`: alpha-preserved or audited matte-recovered sources;
- `working/source-normalized/`: optional shared-occupancy high-resolution sources before recovery;
- `working/perfect-pixel/`: selected logical-pixel recovery for each direction;
- `working/final-frames/`: shared-palette, binary-alpha frames placed 1:1;
- `generated/<slug>.png`: 4x2 sheet in canonical direction order;
- `generated/<slug>.json`: frame rectangles, pivots, palette, hashes, and processing facts;
- `generated/<slug>-audit.json`: machine checks and measurements;
- `evidence/background-extraction.json`: raw-mode and matte-recovery evidence;
- `evidence/source-occupancy-normalization.json`: optional pre-recovery scale factors and hashes;
- `evidence/perfect-pixel-grid-metrics.json`: every calibration trial and selected grid;
- `evidence/turnaround-continuity.json`: per-view head, torso, foot, and palette facts plus all eight circular transitions;
- contact sheet, head crops, `120ms` rotation GIF, slow rotation GIF, and color-coded continuity guide under `evidence/`.

## Acceptance

Automated acceptance requires eight nonempty frames of the requested size, canonical direction order, binary alpha, palette within the requested limit, common bottom contact, foot axes within tolerance, every visible height within tolerance, bounded head-to-foot offset spread, bounded adjacent head and torso shifts, bounded adjacent palette-distribution distance, zero post-recovery resampling, bounded recovery grids, and deterministic hashes on repetition.

Human acceptance checks identity, angle readability, face integrity, costume continuity, silhouette mass, painted-light continuity, native-size readability, and motion continuity in both rotation speeds. Review the circular `NW → N` transition explicitly. Record source-level limitations separately from processing defects.

For an animation, first approve one eight-direction identity and idle baseline. Then repeat the same contract per animation frame or key pose; keep direction ordering, pivot, palette, and no-resampling rules unchanged.
