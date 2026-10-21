---
name: create-fixed-direction-action-sprites
description: Create fixed-direction pixel character actions with procedural motion for small movements, deliberately authored action keyframes for large pose changes, and PixelLab endpoint-guided inbetweens. Use for locomotion, attacks, tools, damage or full directional action packs with preserved keys, shared cost limits and visual review. Static eight-direction portraits belong to create-topdown-8dir-sprites.
---

# Fixed-Direction Hybrid Action Sprites

Choose the motion route by articulation, silhouette change and occlusion. Small
motions can reuse the existing art procedurally; larger motions need deliberate
same-direction key poses. PixelLab connects authored poses. Do not ask a single
standing reference plus an action name to define the complete animation.

Match explanations and handoffs to the user's language. Keep API fields,
identifiers, filenames and raw errors unchanged.

## Establish identity and motion

Use an approved same-direction portrait as the identity authority for every
requested view. Keep `create-topdown-8dir-sprites` unchanged: it owns spatial
reference continuity, not this action controller. Never fill an opposite view
by mirroring the entire raster or accumulate facing drift around the circle.

Before generating anything, record canvas/body scale, direction order,
reference family, Alpha/palette policy, pivot/PPU, action phases and event times,
loop or one-shot, output destination, review scope and any API budget. Preserve
native logical pixels; a larger transparent action canvas may accommodate tools
without enlarging the character. Existing art stays intact in a separate version.

Choose a route per action, not per character:

- **Procedural:** breathing, light sway, small steps and brief recoil when the
  existing same-view parts expose enough anatomy. Use explicit parts, anchors,
  trajectories and occlusion order; keep rigid identity blocks intact. A
  controller may render new discrete limb poses when its source/geometry is
  recorded. Check contacts, closure and texture stability. If articulation
  exposes missing surfaces or tears a joint, author the missing pose/part.
- **Keyframed:** running with flight, wide strikes, overhead tools, casting,
  throwing, fishing, falls and other substantial pose/occlusion changes.
  Plan anticipation, extreme/impact and recovery before producing images. Use
  ImageGen or suitable existing authored poses with the same-view identity
  reference. Generate actual bent limbs, torso changes and grounded final
  poses; rotating a standing cutout does not establish a fall.

When a retained high-detail same-view mother exists, make it the primary identity
and camera reference for new key geometry; use other action art only to explain
phases. A small native reference alone can lose to a differently facing action
study. Verify every cel, rather than inferring the whole row from its first pose.

Key count follows the motion, not a fixed four-frame formula. Author enough
phases that interpolation has no major action decision left to invent. For
several directions, keep event semantics, handedness and gait half-cycles
corresponding. Jointly approve the key poses before spending on their gaps.

## Produce and review keys

For newly generated pixel keys, preserve high-detail sources, approved
pseudo-pixel conversion and recorded Perfect Pixel recovery where that is the
established family workflow. Recover each cel separately; never rescale its
logical pixels afterwards. Use deliberate body/contact landmarks rather than a
weapon's total bounding box. One carefully aligned key study can contain a
small pose set only if each cel's identity, scale, complete silhouette and
separation are reviewable; otherwise generate individual keys. Eight unrelated
facings on one generation sheet are not a substitute for directional references.

Using the exact directional formula portrait at frame0 can establish an idle
entry. Holding a tool or entering an attack can instead require a preparatory
pose. When uncertain, compare these starts with the other keys and timing held
constant; judge identity and entry motion. Do not silently add a tool into an
empty hand or label a different pose the unchanged formula portrait.
For a cyclic action, plan its first motion phase and wrap. A standing-formula
entry can be a separate transition clip while preserving the cycle's contact
phases. The formula remains the identity reference in both clips.

## Fill gaps and assemble

Read [the hybrid contract](references/hybrid-contract.md) for preparation,
shared budgeting and commands. `scripts/hybrid_actions.py` consumes native
procedural frames or authored keys, computes only the missing time slots and
submits PixelLab V3 jobs with **both** endpoint frames. Keep action/event names
as metadata; describe only the local geometric transition in API prompts when
action semantics cause unrequested turns or effects. This is endpoint-guided
V3 generation, not a claim that the provider preserves either endpoint exactly.
The final sequence always uses the original authored key PNGs at their planned
indices, including loop closure; the provider's processed reference and all
motion frames remain separately preserved.

Name the actual endpoint/model in the handoff. Pilot a cardinal and an oblique
transition, checking subject count, tool count, facing and unrequested effects.
Very similar endpoint poses can behave differently from a recovery with a
changed silhouette or tool side; key count alone is insufficient. A failed
pilot blocks ordinary production batching. An explicitly requested full test
may retain failed rows as negative results, clearly separated from approval.
If an interpolation-specific endpoint is inaccessible, report that access
result and keep conclusions about a V3 trial limited to V3.

Use a current user-authorized task budget shared by every action and comparison.
The ledger checks actual balance/debit and a conservative reservation before
POST, caps attempts, persists before submission and resumes accepted IDs. A
completed experiment's budget is closed. Ambiguous POSTs never retry blindly;
transient GET failures leave the same job resumable. Do not buy a subscription
or change providers to bypass access restrictions.

PixelLab output is already native pixel art. Preserve its RGBA, Alpha, colors,
placement and size. Do not recover a grid, paste a head, recolor, recenter or
locally repaint the returned inbetweens. Revise the input keys/transition/model
in a bounded new attempt when interpolation fails; add an authored major phase
when the action itself is underspecified. Preserve prior failed results.

The older `pixellab_actions.py` is a low-level transport/replay utility; live
submission now also requires both endpoints. Its historical first-only recorded
responses can be read offline but do not authorize new direct-action requests.
Current model/access facts remain in
[the API reference](references/pixellab-contract.md); consult the official
schema before changing the backend.

## Verify and deliver

Check native dimensions/count, binary transparent Alpha, nonempty/bounded
silhouettes, declared palette gates, exact authored-key and selected-provider
PNG/RGBA equality, complete slot coverage, and normal/slow APNG timing/loop/final
hold. Declared repeated holds/return poses are legitimate; unexpected duplicates
stop for review. File integrity yields `awaiting-visual-review`, not approval.

View every final frame at native scale and a nearest-neighbor enlargement of
at least1024px. Inspect face, facing, costume, connected joints, props, contacts
and silhouette changes, then the ordered normal/slow sequence, wrap or one-shot
ending. Compare direction/event correspondence and check large actions really
change pose. Record what was actually seen. A single sheet or metrics cannot
stand in for playback or user feel acceptance.

Deliver source/part/controller data, approved keys, preserved API results,
selected frames, sheets, normal/slow previews, functional metadata, local cost
and integrity evidence, and explicit visual findings. Keep hash inventories,
run logs and receipts in Git-ignored evidence. Engine integration and playtest
are separately authorized work.
