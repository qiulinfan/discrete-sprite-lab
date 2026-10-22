# Current character and action workflow

Static eight-direction portraits use the frozen `create-topdown-8dir-sprites`.
Character actions use authored poses and procedural animation through
`create-fixed-direction-action-sprites`. Generative animation and model-based
inbetweens are retired from this workflow.

Choose the method by available geometry and occlusion. With usable same-view
parts, interpolate joint positions, angles, body motion and tool trajectories,
then render discrete pixel poses. Missing surfaces, large silhouette changes
and new overlaps need authored poses or part variants. Large movements can
also be procedural when their source geometry is sufficient.

Start by playing the key poses directly with deliberate timing. Add a
procedural transition only when it improves a visible gap. Preserve impact,
contact, anticipation and held poses; frame counts follow the motion. An image
generator can author missing pose geometry, but does not supply temporal fills.
The user chooses that generator: the agent's built-in image tool, or
[`gemini_image.py`](../skills/create-fixed-direction-action-sprites/scripts/gemini_image.py)
for the Nano Banana 2.1 API, whose offline `matte` also keys either source to
binary Alpha.

The offline helper
[`action_sprites.py`](../skills/create-fixed-direction-action-sprites/scripts/action_sprites.py)
packages complete source sequences with exact PNG preservation. It does not
infer joints, blend flat images or expose a model API. Read the
[Skill](../skills/create-fixed-direction-action-sprites/SKILL.md) and
[frame contract](../skills/create-fixed-direction-action-sprites/references/action-contract.md)
for controller inputs, timings, rendering and review requirements.

Local research images and intermediate outputs belong in the sibling
`../discrete-sprite-lab-experiments/` workspace. Existing experimental frames
remain preserved. Earlier model experiments correspond to product commit
`ad3249b42aa874350362dcf9c6204215ef50f0c2`; their old transport implementation is
historical source in the owner's archive, not an active Skill command.

Validation, using an existing Python/Pillow environment:

```sh
python3 -B skills/create-fixed-direction-action-sprites/tests/test_action_sprites.py
python3 -B skills/create-fixed-direction-action-sprites/tests/test_gemini_image.py
python3 -B scripts/verify_pack.py
```

Technical integrity, frame/sequence inspection, human feel and engine
integration remain separate decisions. Preserve the static Skill and published
art; game adoption is a separately scoped task.
