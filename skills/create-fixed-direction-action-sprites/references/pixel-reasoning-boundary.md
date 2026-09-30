# Pixel Reasoning Boundary

Read this reference when reviewing, comparing, or repairing logical pixel frames. The boundary is semantic: scripts execute exact pixel algebra, while the agent owns every interpretation of what the pixels mean.

## Core Split

### Agent-owned semantic work

- choose a local region and name its role, such as face, eyebrow, cross, skirt hem, contact boot, or passing boot;
- classify it as `stable_identity` or `phase_specific` before extraction;
- choose the approved reference and phase-specific variant;
- assign integer anchors, occlusion order, and allowed transforms;
- inspect each applicable source stage (native master, or high-detail and pseudo-pixel sources) at native resolution and every final logical frame at a nearest-neighbor display size of at least 1024 pixels on the long edge;
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

For temporal character placement, the agent declares the body origin, neck/shoulder/hip landmarks, and phase offsets. The script may execute those integer transforms; outline/Alpha-centroid registration is only a provisional estimate. It must not infer the pivot from whichever foot happens to be planted in the current phase. A shared head follows its neck/body offset; fixed canvas coordinates are not stable anatomy when the torso bobs.

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

- `stable_identity`: fixed within one view and action family except for declared integer bob or translation. Typical examples are an invariant head silhouette with face, a chest emblem, or a rigid hair ornament. One canonical exact cell set may be reused in native construction or as a bounded generated-frame patch. Expressive or rotating heads need phase variants instead.
- `phase_specific`: changes topology, bend, overlap, or lighting with the action. Skirt hems, sleeves, cuffs, hands, legs, and boots use separate contact, recoil, passing, or other phase-family variants. Mirroring one local variant is allowed only when its record explicitly permits `mirror_x` and the agent approves the surrounding anatomy afterward.

Classify the actual feature state, not merely its name. Reuse a component cel within a reviewed view/phase family only while its visible orientation, topology, material lighting and overlap remain compatible. Move it with its declared body, joint or contact anchor; a head can follow the neck while planted boots stay fixed during a lunge. Require variants when rotation, load or deformation changes the visible part. Preserve the component's design constraints across those variants; see [component-construction.md](component-construction.md).

Do not promote a feature to `stable_identity` merely because copying it improves a metric. If its patch would cross a joint or suppress real motion, keep it phase-specific or regenerate the source.

In native construction, shared cels originate from one reviewed master and connect through explicitly authored joints. Clear old idle hands/cuffs/limbs with full erase footprints and repaint exposed garment. Inspect far/near limb visibility and layer order at every phase; unchanged pixels can still hide a limb or preserve an extra idle hand. This construction does not authorize broad overlays on independently generated anatomy.

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

1. For generated work, generate each complete high-detail frame separately and inspect full/local anatomy before pixelization.
2. Convert approved generated frames separately to pseudo-pixel sources and inspect them at native resolution.
3. Recover generated sources through the declared integer-grid policy. Prefer a shared lattice; otherwise record each frame's selected refined grid. Do not resample after recovery.
4. For native work instead, review the same-view master, then author shared cels and phase-specific geometry with declared joints, erase masks, body offsets, and layers. Generation and recovery stages are not applicable.
5. Run `scripts/pixel_region_workbench.py review` to produce individual magnified local windows and exact differences against the approved reference.
6. The agent selects the feature class, canonical or phase-family reference, target anchor, transparent erase footprint, context ring, and allowed discrete transform.
7. Run `extract` and `apply` for exact, stale-safe RGBA replacement. The script never chooses the feature or placement.
8. Inspect the magnified before, after, and difference views. Confirm the local patch and its one-pixel context ring do not break anatomy or silhouette.
9. Inspect the full magnified frame and cyclic animation again. Technical checks remain subordinate to this visual decision.

## Completion Semantics

- `technical-pass`: hard file, lattice, palette, Alpha, anchor, hash, bounds, resampling, and deterministic checks passed.
- `diagnostic-warn`: a visual measurement such as paired cadence lies outside its reference range; it requires explicit normal/slow loop review but does not itself prove a defect.
- `awaiting-visual-review`: magnified artifacts exist, but the agent has not completed all applicable source, logical-frame, and normal/slow playback reviews.
- `visual-fail`: any semantic anatomy, feature, connection, occlusion, or pixel-cluster defect remains.
- `pass`: hard technical checks and explicit magnified visual review passed for every frame and the loop, with every diagnostic warning explicitly acknowledged.
- `candidate-with-warnings`: explicit visual review permits a coherent candidate while recording specific remaining motion or articulation limits; stable identity alone does not imply natural motion.

Never report `technical-pass` or `diagnostic-warn` alone as an approved animation. Direct user approval governs subjective motion feel, but cannot waive a hard integrity failure. Record the scope of the user decision: approval to preserve a better version does not grant perfect-motion or engine-integration approval.
