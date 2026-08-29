# Methodology: reasoning on a discrete sprite

## 1. The representation matters

A logical sprite is not a low-resolution photograph. It is an exact `width × height × 4` RGBA field. Two neighboring cells may have identical colors or an abrupt discontinuity, and a transparent cell can be just as important as an opaque one because it erases the previous silhouette.

This changes the division of labor:

- **The agent owns semantics:** identity, anatomy, phase, occlusion, feature class, anchors, context, and visual approval.
- **Scripts own exact algebra:** lossless RGBA I/O, integer coordinates, nearest-neighbor display, exact diffs, bounded writes, hashes, and receipts.

Scripts must not decide that a component is an eye, hand, boot, or valid action phase.

## 2. End-to-end pipeline

```mermaid
flowchart LR
    Contract[Asset and phase contract] --> Detail[Separate complete high-detail images]
    Detail --> DetailReview[Native high-detail review]
    DetailReview --> Pseudo[Separate high-resolution pseudo-pixel images]
    Pseudo --> PseudoReview[Native pseudo-pixel review]
    PseudoReview --> Recover[Perfect Pixel majority recovery]
    Recover --> Place[1:1 integer placement on logical canvas]
    Place --> Palette[Shared palette and binary Alpha]
    Palette --> Local[Agent-selected exact local RGBA patches]
    Local --> Magnify[16x-32x nearest-neighbor review]
    Magnify --> Loop[Normal and slow cyclic review]
    Loop --> Audit[Hard checks, diagnostics, hashes, receipt]
```

## 3. Generate complete frames separately

Multi-frame image-generation sheets reduced detail and frequently produced duplicate phases, perspective drift, baked backgrounds, and inconsistent character scale. Every accepted direction or action phase is therefore generated as a complete high-detail image.

For a six-frame walk, define semantic phases before generation: opposite contacts, opposite recoil poses, and opposite passing poses. Frame numbers alone are not pose specifications.

## 4. Recover, do not resize

Perfect Pixel majority sampling recovers the logical cells from a reviewed pseudo-pixel lattice. After recovery:

- no bilinear, bicubic, Lanczos, antialiasing, or fractional resampling;
- no blur, denoise, morphology, optical flow, or continuous warping;
- only exact cropping, integer translation, transparent padding, palette mapping, and binary Alpha.

A shared refined grid is preferred. Independently generated sources may use different recorded integer grids if every source and final loop passes review. Continuous scaling is never used merely to manufacture shared-grid evidence.

## 5. Stable identity versus phase-specific geometry

Every local feature is classified before repair:

- `stable_identity`: a complete same-view head and face, rigid emblem, or fixed ornament. It may reuse one canonical exact RGBA set with declared integer bob offsets.
- `phase_specific`: skirt hems, sleeves, cuffs, hands, legs, and boots. These change topology and occlusion, so contact, recoil, and passing families stay separate.

An exact patch includes its transparent erase footprint and a reviewed one-pixel context ring. It must not cross an articulating neck, shoulder, elbow, wrist, waist, hip, knee, or ankle boundary.

## 6. Review at a scale the reviewer can read

Every logical `64×64` frame is enlarged to at least `1024×1024` with nearest-neighbor sampling. Review proceeds hierarchically:

1. whole silhouette and action phase;
2. head, torso, arms, skirt, and legs;
3. eyes, brows, hair breaks, emblem, cuffs, and shoes;
4. the one-pixel context ring around any exact patch;
5. the cyclic animation, including last-to-first closure.

## 7. Hard checks and visual diagnostics

Hard integrity failures cannot be waived:

- wrong count or dimensions;
- empty or duplicate frames;
- partial Alpha or palette violation;
- out-of-bounds writes or stale hashes;
- prohibited post-recovery resampling;
- failed required contacts, grid policy, or an explicitly promoted contract gate.

Silhouette-change distance and paired-cadence ratios are diagnostics by default. A diagnostic outside its reference range must remain visible and requires normal-speed and slow-loop evidence, a reason, and named user or agent visual authority. It cannot approve or reject subjective motion automatically.

## 8. Spatial and temporal axes stay separate

`create-topdown-8dir-sprites` owns spatial rotation continuity for one approved pose. `create-fixed-direction-action-sprites` owns temporal continuity for one direction and action. A complete `directions × phases` sheet is assembled only after both axes pass independently.
