# Pixel Reasoning Boundary

Read this reference when reviewing, comparing, or repairing logical pixel frames. The boundary is semantic: scripts execute exact pixel algebra, while the agent owns every interpretation of what the pixels mean.

## Core Split

### Agent-owned semantic work

- choose a local region and name its role, such as face, eyebrow, cross, skirt hem, contact boot, or passing boot;
- classify it as `stable_identity` or `phase_specific` before extraction;
- choose the approved reference and phase-specific variant;
- assign integer anchors, occlusion order, and allowed transforms;
- inspect the high-detail source at native resolution, the pseudo-pixel source at native resolution, and every recovered logical frame at a nearest-neighbor display size of at least 1024 pixels on the long edge;
- reason about local topology: silhouette, connected anatomy, negative space, occlusion, part count, and whether a patch boundary remains coherent;
- author or approve the exact pixel patch and reject it when the local match or surrounding context is ambiguous.

The agent should not reason over the whole `64x64` frame as one undifferentiated image. Use a hierarchy:

1. whole silhouette and pose;
2. head, torso, left arm, right arm, skirt, left leg, right leg;
3. face, eyes, eyebrows, hair breaks, emblem, cuffs, shoes, and phase-specific contour details.

Each level must pass before the next. Local windows should normally contain 8-24 logical pixels per side and be displayed at 16x-32x nearest-neighbor scale.

### Script-owned exact work

- lossless RGBA loading and saving;
- exact rectangle or agent-authored mask extraction;
- nearest-neighbor magnification for inspection;
- exact coordinate-set, color, Alpha, and hash comparisons;
- integer translation or an explicitly authorized discrete mirror of a local feature;
- clearing and writing agent-approved pixel coordinates;
- binary-Alpha, palette-membership, bounds, conflict, and stale-source checks;
- receipts and before/after/difference artifacts.

These operations must not infer semantics. A script may enumerate connected components, exact contours, integer-offset overlap scores, or IoU candidates, but the agent selects and approves the correspondence.

For temporal character placement, the agent declares the stable body axis. The script may integer-translate the recovered frame to that axis. It must not infer the pivot from whichever foot happens to be planted in the current phase.

## Forbidden Repair Operations

- bilinear, bicubic, Lanczos, antialiased, or fractional resampling in logical pixel space;
- blur, sharpen, denoise, contour smoothing, morphology, optical flow, or continuous warping as an automatic repair;
- fuzzy color thresholds or perceptual nearest-color matching used to decide feature identity;
- global raster mirroring used as a substitute for drawing or reviewing anatomy, occlusion, and lighting;
- a broad patch that crosses the neck, shoulder, elbow, wrist, waist, hip, knee, or ankle boundary;
- automatic acceptance from silhouette metrics, cadence ratios, palette counts, or feature-match scores.

Perfect Pixel majority recovery is a bounded conversion from an already approved high-resolution pseudo-pixel lattice. It is not a repair tool. If recovery removes or merges a semantic feature, return to the pseudo-pixel source.

The logical canvas is exact `width × height × 4` RGBA, not RGB alone: transparent cells are part of a silhouette patch. A canonical patch must write its transparent erase footprint as well as its opaque colors, or remnants of the old outline survive around the new feature.

## Feature Classes

- `stable_identity`: fixed within one view and action family except for declared integer bob or translation. Typical examples are the complete head silhouette with face, a chest emblem, or a rigid hair ornament. One canonical exact cell set may be reused after whole-frame generation.
- `phase_specific`: changes topology, bend, overlap, or lighting with the action. Skirt hems, sleeves, cuffs, hands, legs, and boots use separate contact, recoil, passing, or other phase-family variants. Mirroring one local variant is allowed only when its record explicitly permits `mirror_x` and the agent approves the surrounding anatomy afterward.

Do not promote a feature to `stable_identity` merely because copying it improves a metric. If its patch would cross a joint or suppress real motion, keep it phase-specific or regenerate the source.

## Local Feature Record

A reusable feature is an exact local record rather than a generic image crop:

```json
{
  "id": "cross-south",
  "semantic_class": "stable_identity",
  "phase_family": "all",
  "anchor": [31, 33],
  "rect": [28, 29, 35, 38],
  "allowed_transforms": ["identity"],
  "context_ring": 1
}
```

Use phase-specific families for articulated or deforming features, for example `shoe-left-contact`, `shoe-left-recoil`, `shoe-left-passing`, and corresponding right-side variants. Face details and small emblems may be rigid; shoes, hands, sleeves, skirt contours, and limb silhouettes are not globally rigid.

## Review and Patch Loop

1. Generate each complete high-detail frame separately.
2. Inspect each full frame and local anatomy at native high resolution. Reject malformed anatomy before pixelization.
3. Convert approved frames separately to pseudo-pixel sources and inspect those sources at native resolution.
4. Recover through the declared integer-grid policy. Prefer a shared lattice; otherwise record each frame's selected refined grid. Do not resample after recovery.
5. Run `scripts/pixel_region_workbench.py review` to produce individual magnified local windows and exact differences against the approved reference.
6. The agent selects the feature class, canonical or phase-family reference, target anchor, transparent erase footprint, context ring, and allowed discrete transform.
7. Run `extract` and `apply` for exact, stale-safe RGBA replacement. The script never chooses the feature or placement.
8. Inspect the magnified before, after, and difference views. Confirm the local patch and its one-pixel context ring do not break anatomy or silhouette.
9. Inspect the full magnified frame and cyclic animation again. Technical checks remain subordinate to this visual decision.

## Completion Semantics

- `technical-pass`: hard file, lattice, palette, Alpha, anchor, hash, bounds, resampling, and deterministic checks passed.
- `diagnostic-warn`: a visual measurement such as paired cadence lies outside its reference range; it requires explicit normal/slow loop review but does not itself prove a defect.
- `awaiting-visual-review`: magnified artifacts exist, but the agent has not completed all high-detail, pseudo-pixel, logical-frame, and loop reviews.
- `visual-fail`: any semantic anatomy, feature, connection, occlusion, or pixel-cluster defect remains.
- `pass`: hard technical checks and explicit magnified visual review passed for every frame and the loop, with every diagnostic warning explicitly acknowledged.

Never report `technical-pass` or `diagnostic-warn` alone as an approved animation. Direct user approval governs subjective motion feel, but cannot waive a hard integrity failure.
