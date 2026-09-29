# Native Master Action Authoring

Use this route for already approved logical pixels that can support the intended same-view action. It owns one direction and one action. Missing view design, major perspective changes, and anatomy that cannot be authored confidently require source work before this route can continue.

## Construction and Motion

1. Preserve the original same-view PNG and its palette authority. If a palette remap is needed, make and review it as a separate explicit preparation step; the native packager never recolors inputs.
2. Declare the body origin, neck/shoulder/hip anchors, gameplay pivot, contact line, and expected phase offsets. Anatomical landmarks come from inspection. An Alpha bbox midpoint is not a shoulder or hip.
3. Separate shared construction cels from articulated parts. A same-view head, torso core, or emblem may remain stable when the action permits it. Stable shape still follows the appropriate parent/body transform. Expressions, torso twists, hair response, and garment deformation may need phase variants.
4. Clear superseded idle arms, cuffs, hands, legs, and boots with exact erase masks. Repaint newly exposed garment/skin. Leaving the old hand behind while drawing a swinging arm creates extra anatomy even if palette and bounds pass.
5. For walks, draw opposite contact poses first, then passing/recoil phases; define planted and swing legs and opposing arm motion. For attacks, tools, damage, and emotes, use the actual anticipation/event/recovery or expression phases. Do not carry one walk's frame count, bob, or boot glyphs into every action.
6. Draw integer joint geometry and phase-specific silhouettes. Declare far/near ordering from the view; review overlaps rather than assuming one universal layer stack. A torso can accidentally hide a far arm, and a near contact leg can hide the swing boot. Check visibility throughout the sequence.
7. Inspect every completed frame and normal/slow playback. Shared head/torso shape improves identity consistency but can still produce stiff weight transfer, limited cloth response, or weak action readability. Record these as specific warnings or repair them.

A shared cel is part of a reviewed construction from a common master. It is not permission to splice a broad rectangle across the neck, shoulder, waist, or hip of an independently generated body. Native articulation requires drawing the connecting geometry, not inferring it automatically from image components.

## Packaging Contract

`scripts/package_native_action.py` packages already authored PNGs. Paths resolve relative to the contract; output paths are separate. Keep the full asset contract (camera, lighting, pivot, PPU, contacts/events, pose cards, and source provenance) beside this minimal packaging contract.

```json
{
  "schema_version": 1,
  "artifact_slug": "character-walk-east",
  "direction": "east",
  "action": "walk",
  "frame_size": [64, 64],
  "body_origin_px": [32, 44],
  "master": "source/prepared-native-master.png",
  "loop": true,
  "slow_factor": 3,
  "padding_px": 1,
  "max_colors": 32,
  "review_min_px": 1024,
  "stable_regions": [
    {"id": "head", "rect": [20, 7, 44, 28]}
  ],
  "frames": [
    {"phase_id": "left-contact", "path": "authored/contact-left.png", "duration_ms": 120, "body_offset": [0, 0]},
    {"phase_id": "passing-right", "path": "authored/passing-right.png", "duration_ms": 120, "body_offset": [0, -1]},
    {"phase_id": "right-contact", "path": "authored/contact-right.png", "duration_ms": 120, "body_offset": [0, 0]},
    {"phase_id": "passing-left", "path": "authored/passing-left.png", "duration_ms": 120, "body_offset": [0, -1]}
  ]
}
```

This is a schema example, not an accepted gait. Use the action's actual semantic phases and coordinates. Add `palette_rgb` as an array of RGB triplets when exact palette membership is contracted. An optional frame `direction` must equal the root direction. `loop: false` produces a one-shot preview without an infinite-loop extension.

- Inputs must be nonempty, same-size RGBA PNGs with binary Alpha. At least two distinct visible frames are required. Intentional holds belong in durations.
- `stable_regions` are half-open rectangles `[x0, y0, x1, y1]` chosen by the agent. Each is compared exactly, including transparent cells, to the master after that phase's integer `body_offset`. Declare only genuinely invariant, unoccluded regions that follow this body transform; this helper does not validate arbitrary cel hierarchies or expressive variants. An empty list means no stable-region assertion, not proof of stable identity.
- Body origin is an anatomical construction anchor, not a gameplay pivot inferred from moving feet. `body_offset` moves stable shape with the body; contact/swing limbs are independently authored around the declared joints.
- No native resampling, automatic registration, recovery lattice, palette mapping, or motion synthesis occurs. Frame PNG bytes are copied unchanged; the sheet preserves exact RGBA at 1:1.
- GIF evidence uses a fixed exact palette with at most 254 art colors plus two checker colors. Durations must be positive multiples of 10 ms; normal and slow decoded pixels, durations, and loop flags are checked. Preserve other production timing through an appropriate exporter rather than silently rounding it. `slow_factor` must be at least 2.
- Invalid inputs or stale visual reviews are rejected before output writes. Use a task-owned output directory and retain the source provenance and cel/pose authoring records separately.

```sh
uv run scripts/package_native_action.py \
  --contract /absolute/path/to/native-contract.json \
  --output-root /absolute/path/to/native-package
```

Outputs include copied master/frames, `generated/<slug>.png`, manifest/audit JSON, exact normal/slow GIFs, individual integer magnifications, and `evidence/visual-review-template.json`. Exit zero means packaging succeeded; without review the verdict remains `awaiting-visual-review`.

## Native Visual Review

Inspect the master, every magnified frame, and both playback speeds before editing a copy of the template. Record concrete findings in stage notes or per-frame notes; populated hashes and a frame count are coverage bookkeeping, not evidence that inspection happened.

The required stages are `native_master`, `logical_frames`, and `loop` (playback, also used for one-shots). A passing review includes every current frame hash, the sheet hash, animation hash, full reviewed-frame count, and `normal_and_slow: true`. The animation hash covers pixel identity, phase IDs, durations, loop behavior, body origin/offsets, and declared stable regions, so a timing or anchor change also invalidates old review. Unused generated image stages are `not-applicable` in the broader receipt.

Use `pass`, `fail`, or `candidate-with-warnings`. The warning verdict requires explicit remaining concerns while the required stages pass their checks. For example, record restricted torso motion or weak far-foot visibility rather than declaring the animation perfect. An explicit visual failure dominates a successful technical package.

```sh
uv run scripts/package_native_action.py \
  --contract /absolute/path/to/native-contract.json \
  --output-root /absolute/path/to/native-package \
  --visual-review /absolute/path/to/native-visual-review.json
```

The supplied review is preserved unchanged at `evidence/visual-review.json`. Keep direct user approval in the handoff receipt. The packager always leaves `user_approval: pending` and never authorizes engine import. A preservation decision should remain scoped to preservation and the reviewed artifact hashes.

## Several Directions

Repeat this single-direction process for each approved view master. Assemble only after each full temporal row passes; separately inspect corresponding phases around the direction ring. Static turnaround consistency cannot validate time continuity, and a successful south row cannot approve another direction.

The transferable result is the construction principle (common same-view identity plus authored phase geometry) and the two-axis review requirement. Character-specific joints, erase masks, amplitudes, palette values, frame count, and layer choices stay in that character's source contract.
