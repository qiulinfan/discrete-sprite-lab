# Fixed-Direction Action Contract

Read this reference when defining phases, generating frames, running the processor, reviewing a temporal loop, or handing approved phases to the turnaround Skill.

## Required Contract

- character and approved identity/palette gold;
- high-detail, pseudo-pixel, and logical-frame magnified review roots;
- local semantic feature records with agent-approved rectangles or masks, anchors, phase families, context rings, and allowed integer transforms;
- one fixed facing direction;
- action name and gameplay meaning;
- frame count, ordered phase IDs, duration per frame, loop or one-shot behavior;
- planted limb, swing limb, contact events, hit or tool event frames when applicable;
- per-frame body-height profile, rotation or body-axis expectation, and foot baseline;
- recovery-grid policy: either one shared refined-grid shape or an evidence-backed integer grid record per frame, with no post-recovery resampling;
- phase pairs and paired transition indices for physically symmetric cycles;
- which metrics are diagnostics and whether any diagnostic is explicitly promoted to a hard contract gate;
- camera, lighting, canvas size, final frame size, pivot, and PPU assumption;
- high-detail, pseudo-pixel, final, preview, manifest, audit, and engine destination paths;
- authorization boundary for turnaround propagation and engine import.

## Six-Frame Walk Example

Generate the key poses in constraint order rather than chronological order:

1. `frame-00-left-contact`: left foot plants forward; right foot trails; opposite arm counter-swing.
2. `frame-01-left-recoil`: left foot bears weight while right foot lifts.
3. `frame-02-passing-right`: right leg passes forward close beneath the body; body reaches its high point.
4. Independently generate `frame-03-right-contact` as the paired opposite of frame 0.
5. Independently generate `frame-04-right-recoil` as the paired opposite of frame 1.
6. Independently generate `frame-05-passing-left` as the paired opposite of frame 2 and verify closure into frame 0.

Example height profile for a 52-pixel visible character: `52,51,53,52,51,53`. Treat it as a configurable starting point, not a universal walk law.

Each phase card should show the body axis, head top, belt or torso landmark, contact line, planted foot, swing foot, limb direction, and body-height target. Do not rely on prose alone for limb-specific action.

## Source Generation Rules

- One ImageGen call per phase or one edit that changes only the intended phase.
- Generate a complete coherent body for every phase. Identity references constrain generation but do not authorize late broad-mask compositing across anatomy.
- The identity gold stays in every call. Neighboring or paired phase references supplement it; they never replace it.
- Multi-frame sheets may be generated as brainstorming evidence, but not accepted as production frame sources without independent per-cell phase and anchor verification.
- Ask for actual transparency, preserve raw outputs, and audit baked checkerboards or stray Alpha.
- Reject perspective enlargement in orthographic in-place actions.
- Prefer a shared recovery lattice, but do not continuously scale or warp a valid source merely to force one. Reject a pseudo source when it cannot recover through a documented integer grid without semantic loss. Palette agreement and matching outer bounds do not prove a clean recovery.
- Inspect every generated stage at a size where local semantic topology is readable. A compact contact sheet is navigation evidence, not visual approval.

## Processor

Inputs are `frame-00.png`, `frame-01.png`, and so on under one pseudo-pixel source directory. The gold frame is an approved final logical-pixel PNG for the same direction and supplies the canonical palette.

```sh
uv run scripts/build_fixed_direction_action.py \
  --pseudo-dir /absolute/path/to/pseudo-frames \
  --gold-frame /absolute/path/to/approved-idle-direction.png \
  --output-root /absolute/path/to/output \
  --artifact-slug character-walk-south-6f-64 \
  --frame-count 6 \
  --duration-ms 200 \
  --frame-size 64 \
  --height-profile 52,51,53,52,51,53 \
  --height-tolerance 1 \
  --target-bottom 61 \
  --placement-axis body \
  --colors 32 \
  --contact-frames 0,3 \
  --phase-pairs 0:3,1:4,2:5 \
  --transition-pairs 0:3,1:4,2:5 \
  --max-paired-transition-ratio 1.10 \
  --max-paired-height-delta 0 \
  --review-min-size 1024
```

This technical run produces magnified reviews and normally returns `awaiting-visual-review`. After the agent reviews every stage and authors a review JSON matching the generated sheet hash, rerun the same command with `--visual-review /absolute/path/to/visual-review.json`.

`paired_transition_cadence` is a diagnostic by default because silhouette-change distance is not perceived motion quality. If a contract truly requires it as a hard mechanical gate, add `--require-paired-transition-cadence`. Otherwise a passing review may accept an out-of-range value only through an explicit `diagnostic_overrides` record with decision, authority, reason, and normal/slow loop evidence.

```json
{
  "diagnostic_overrides": [
    {
      "id": "paired_transition_cadence",
      "decision": "accept",
      "authority": "user",
      "reason": "The normal and slow loops were explicitly approved as coherent.",
      "evidence": ["evidence/action.gif", "evidence/action-slow.gif"]
    }
  ]
}
```

For same-view temporal animation, first test one evidence-backed grid across all frames. When independently generated sources require different integer refined-grid shapes, omit `--require-shared-refined-grid`, record every selected grid, and rely on the common final canvas, body axis, 1:1 placement, exact local feature patches, and magnified loop review. Use `--require-shared-refined-grid` only when the contract explicitly requires it. `--derive-paired-motion` and broad identity masks remain available only to reproduce rejected experiments; they are not production authoring routes.

For local logical-pixel reasoning and repair, read [pixel-reasoning-boundary.md](pixel-reasoning-boundary.md) and use `pixel_region_workbench.py`. The agent defines the region and placement; the script only executes exact operations.

## Hard Integrity Acceptance

- correct frame count, order, size, palette, binary Alpha, pivot, and duration;
- zero post-recovery resampling;
- all requested height-profile values within tolerance;
- the declared recovery-grid policy passes: either one identical refined-grid shape or complete per-frame integer-grid evidence;
- paired phase heights within the declared tolerance;
- foot axes and bottom contacts remain within tolerance;
- the declared head/torso body placement axis remains fixed while feet are allowed to move around the pivot;
- no exact duplicate frames;
- each adjacent silhouette change is large enough to be a distinct phase but bounded against identity drift;
- head and torso lateral shifts remain bounded;
- palette-distribution changes remain bounded;
- last-to-first closure is explicitly included;
- each complete high-detail frame passes native-resolution anatomy review;
- each pseudo-pixel source passes native-resolution feature and lattice review;
- every logical frame passes an individual nearest-neighbor magnified review of at least 1024 pixels on the long edge;
- agent-reviewed stable-identity patches include transparent erase footprints, preserve their context rings, and do not cross articulating boundaries;
- articulated details use phase-specific feature families rather than a universal identity patch;
- human or agent visual review confirms phase semantics, planted-foot stability, swing trajectory, body bob, camera-relative lighting, anatomy, and action readability;
- technical evidence alone yields `awaiting-visual-review`, not `pass`.

## Visual Diagnostics

- corresponding left/right transition motion ratios and silhouette-change distances are reported with their reference limits;
- a passing in-range diagnostic needs no override;
- an out-of-range diagnostic cannot decide the result alone and requires explicit normal-speed and slow-loop review;
- the review records the accepting authority and reason; direct user approval outranks an agent's subjective rejection;
- `--require-paired-transition-cadence` promotes that diagnostic to a hard gate that visual approval cannot override.

## Handoff to `create-topdown-8dir-sprites`

Handoff occurs only after temporal approval. For every approved phase:

1. provide its high-detail and pseudo-pixel temporal-master source, phase card, palette authority, anchor facts, and hash;
2. invoke `create-topdown-8dir-sprites` for that single phase;
3. keep direction order and per-phase pivot fixed;
4. reject a directional set before assembling the action if that phase fails turnaround continuity;
5. assemble `directions × phases` only after every phase passes both Skill contracts.

The action Skill remains authoritative for phase meaning and cyclic timing. The turnaround Skill remains authoritative for identity and spatial direction continuity. Neither Skill silently takes over the other's axis.
