---
name: create-fixed-direction-action-sprites
description: Create fixed-direction pixel character actions from authored poses and procedural animation, with controlled inbetweens, exact source preservation and visual review. Use for locomotion, attacks, tools, damage or directional action packs. Static eight-direction portraits belong to create-topdown-8dir-sprites.
---

# Procedural and Authored Action Sprites

Use authored poses and task-owned procedural controllers for character actions.
Generative animation and model-based inbetweens, including PixelLab, are outside
this workflow. An image generator may author missing pose geometry, never
temporal fills.

Match explanations and handoffs to the user's language. Keep commands,
identifiers, filenames and raw errors unchanged.

## Plan identity, poses and timing

Use the approved same-direction portrait as the identity authority. Keep
`create-topdown-8dir-sprites` frozen. Maintain camera, handedness, costume and
logical body scale across directions; do not obtain opposite views by mirroring
the entire character raster. Check paired facings and left/right gait phases.

Record native canvas, palette/reference family, Alpha, pivot/PPU, action phases,
contacts or impacts, loop/one-shot, timing and destination. Choose frame counts
from the motion. Play the deliberate keys first with useful holds and timing;
extra frames must improve the action rather than meet an arbitrary count.

A literal formula portrait may establish an idle entry. A loop begins at its
planned contact phase, and a tool action may need a ready pose. Plan entry and
loop separately while keeping the directional portrait as the identity source.

## Choose geometry before interpolation

- With sufficient same-view parts, use a procedural controller. Record part
  masks, joint anchors, parent relations, trajectories, contact constraints and
  occlusion order. Interpolate positions/angles and render discrete pixel poses.
  Large movements can also use this route when the geometry is available.
- Missing surfaces, changed silhouettes or new overlaps require authored key
  poses or part variants. Use approved existing art or generate the missing
  same-direction geometry. Before generating, ask the user which source to use
  and do not choose for them: the current agent's built-in image generation tool
  when it has one (for example Codex ImageGen), or the billable Nano Banana 2.1
  API through this Skill's `scripts/gemini_image.py` (the user authorizes each
  batch; see [hosted pose generation](references/hosted-pose-generation.md)).
  Record the chosen source with the pose. Pass the approved portrait first as
  the identity reference, then any landmark card or neighbouring key, and
  request a flat chroma background; key it to binary Alpha with
  `scripts/gemini_image.py matte` (offline) unless the source already has real
  Alpha. Review the pose before converting it to the retained family's
  high-detail, pseudo-pixel and Perfect Pixel workflow where applicable.
- For a flat key-pose sequence without a usable rig, use deliberate frame
  timings and holds or author the missing poses. Do not crossfade PNGs, warp
  the whole image, or claim that two endpoint images define an articulated rig.

Keep stable same-view identity blocks intact. Render limb geometry or select
reviewed part variants at native pixel scale; avoid arbitrary texture stretching
or resampling. A controller can evaluate continuous motion parameters, then
quantize placement on the pixel grid. Preserve foot contacts, controlled body
motion and the tool path. Add transparent canvas room without scaling the body.

For authored contact/extreme frames, place the exact source PNGs at their planned
indices. Preserve source parts, controller code, parameters, poses and phase map.
If interpolation reveals missing geometry or tears a joint, improve the sources
or controller rather than invoking an animation model.

## Package and review

Read [the offline action contract](references/action-contract.md).
`scripts/action_sprites.py` prepares and packages a complete native sequence,
including mixed procedural frames and exact authored keys. Its only commands
are offline `prepare` and `assemble`; it does not generate poses itself.

Validate dimensions, transparent binary Alpha, source PNG equality, explicit
palette gates, phase/order/timing, sprite-sheet placement and normal/slow APNGs.
Use durations for held poses; declare intentional nonadjacent repeated poses.
Keep digest locks and verification records in ignored evidence.

Inspect every final frame at native scale and a nearest-neighbor enlargement of
at least1024px. Then inspect normal/slow playback, face/costume stability, joints,
occlusion, foot planting, tool trajectory and wrap/one-shot ending. Corresponding
directions need matching event semantics; equal frame indices alone do not prove
alignment. Technical integrity is not visual approval or player feel acceptance.

Deliver original keys/parts, controller and parameters, complete source frames,
phase/timing metadata, sheets, previews and explicit visual findings. Research
outputs belong in the lab's separate experimental workspace; engine integration
is a separately scoped task. Preserve historical experimental images unchanged.
