---
name: create-fixed-direction-action-sprites
description: Generate native pixel sprite animations through the PixelLab API from approved same-direction character references. Use for walking, running, attacks, tools, damage, emotes, or a complete directional action set, with bounded costs, resumable jobs, lossless packaging, and visual review. Static eight-direction character portraits belong to create-topdown-8dir-sprites.
---

# PixelLab Action Sprites

PixelLab owns all new action-frame generation. The retained invocation name
identifies the temporal workflow; its previous native-cel authoring, manual
pixel repair and ImageGen-per-phase implementations are retired. Do not choose
those routes when PixelLab fails. The separate `create-topdown-8dir-sprites`
Skill remains unchanged as the owner of static character reference views.

Match explanations and handoffs to the user's language. Preserve API fields,
model identifiers, filenames and raw error codes.

## Inputs and model

Use an approved reference matching each requested facing direction. Existing
same-view frames are usable; a neutral or contact pose can establish identity.
For a missing view, use the static eight-direction Skill first. Do not mirror a
view or rotate every action phase through ImageGen to fill an animation row.

Default to PixelLab V3 `/v2/animate-with-text-v3`, the tested native-animation
route. Read [the API and artifact contract](references/pixellab-contract.md)
before preparing a job. Verify current official schemas and pricing when
choosing another PixelLab model; do not imply it was tested here or purchase a
subscription to access it without authorization. Generation and repairs stay
inside PixelLab; scripts only transport, inspect and package its outputs.

## Contract and authorization

Before generation, record the character/reference authority, directions/order,
native dimensions, action/motion prompt, frame count, timing, loop or one-shot,
pivot/PPU, palette policy, destination, model/seed, budget and job-attempt cap.
Use 64x64 for the current player family; frame counts follow the action. V3
supports even counts from 4 to 16. Do not stretch frames to satisfy a canvas.

Read the user's credential file without copying its contents into a contract,
output, log or repository. Reuse authorized credentials and spending limits;
otherwise obtain missing cost authorization before POST. A previous completed
experiment's budget does not authorize new paid generations. Read-only balance
checks, offline replay and packaging do not generate new art.

The helper accepts a conservative per-job reservation and checks current balance
and observed debit before each sequential submission. Provider prices are
variable: this is a client guard, not a provider-enforced price ceiling. Report
actual credit debit, subscription/trial consumption and returned `cost_if_paid`
separately. Trial use does not establish a zero paid price.

## Generate and resume

Use `scripts/pixellab_actions.py` with an existing Python/Pillow environment or
the declared PEP 723 dependencies. Prepare a fresh task-owned output root,
then run the recorded jobs sequentially. The tested trial account permits one
active job. Keep immutable reference copies, requests, seeds, job IDs, raw
responses and all returned PNGs; resume accepted IDs instead of submitting again.

- Persist the attempt before POST. Timeouts or ambiguous 5xx/acceptance errors
  stop with `post-uncertain`; investigate the existing provider job before any
  new submission. Do not blindly retry.
- A definite validation/auth/credit/concurrency rejection or a completed failed
  job is recorded. Correct its cause, then use an explicit bounded retry if the
  current authorization covers it. Never switch to hand-authored frames.
- V3 currently returns a processed reference-like frame plus the requested
  generated frames. Keep every raw frame; explicitly select indices 1..N for
  N-frame packaging. The prefixed frame may differ from the upload. Record its
  differences rather than asserting exact preservation. Unexpected counts or
  sizes require inspection and an updated contract, not automatic trimming.

## Package and judge

Package exact RGBA at 1:1. Preserve the model's pixels, Alpha, placement and
colors. Do not silently recolor, crop limbs, recenter frames, freeze a pasted
head, erase pixels, or apply Perfect Pixel to already-native API outputs.
An exact palette limit is a contract gate only when explicitly required;
otherwise retain raw colors and record the union and observed color drift.

The helper produces individual magnifications of at least 1024px, exact normal
and slow APNGs, a direction-row sheet, manifest, diagnostics and receipt.
Check native size/count, requested transparency, binary Alpha, nonempty and
distinct visible frames, raw/packed RGBA equality, timing and current hashes.
File integrity alone remains `awaiting-visual-review`.

Inspect every magnified frame: silhouette/facing, head/face, torso/garment
identity, arm/leg connection, cuff/hand and boot details, occlusion and bounds.
Inspect the ordered action and normal/slow playback, including loop closure or
one-shot events/final hold. For several directions, also inspect facing
continuity and semantic gait/event correspondence. Equal frame indices do not
establish equal contact phases. State what was actually viewed; a static
contact sheet cannot stand in for full playback or human feel testing.

Record a hash-bound visual verdict and concrete findings. `pass`,
`candidate-with-warnings`, `visual-fail`, user preference and engine integration
are separate. A subjective decision cannot waive failed size/Alpha/palette or
other explicit hard gates. A rejected sequence is revised through PixelLab
with a better same-view reference, motion/keyframe prompt, seed or suitable
PixelLab model, in a new version or recorded attempt within the budget.

Deliver references, raw responses/frames, selected PNGs, exact loops, sheet,
metadata, checks, cost ledger and visual findings. Keep earlier approved art
unchanged. Importing into an engine and world-speed/foot-contact testing remain
separately scoped work; do not call packaged art integrated.
