# Discrete Sprite Lab agent guidance

- Current workflows: `skills/create-topdown-8dir-sprites` for static character
  views and `skills/create-fixed-direction-action-sprites` for authored poses
  and procedural actions. Keep both public invocation names.
- The owner froze the spatial Skill. Do not change its files, scripts, tests
  or behavior as action-work maintenance.
- Choose procedural motion by available part geometry and occlusion, not only
  movement size. Author missing poses/surfaces/part variants. Controllers own
  interpolation, joint/contact constraints and discrete pixel rendering.
- PixelLab action generation and generative inbetweens are retired. Do not
  invoke them or keep an API fallback in the current Skill.
- Current packaging entrypoint: `scripts/action_sprites.py` inside the action
  Skill. It accepts complete native sequences and preserves source PNG bytes.
  Controllers are task-owned; the packer does not infer a rig from flat images.
- Preserve exact authored keys, body scale, phase semantics and intentional
  timing. Review every enlarged frame plus normal/slow playback; integrity,
  visual judgment, user feel and engine integration are separate decisions.
- Full research images, intermediate outputs and reports belong in the sibling
  `../discrete-sprite-lab-experiments/` workspace, not Village_Rim's game assets.
  Keep selected published examples in `art-pack/` and `case-studies/`.
- Historical published art and source evidence remain intact. Current routing
  is in `docs/action-workflow.md`. Retired transport source is archived with its
  exact source commit; it is not an active command or compatibility wrapper.
- Preserve existing user work and licenses. No commit/push without the owner's
  explicit request. Keep credentials and personal runtime configuration out of
  Git; verification inventories and run logs stay in ignored local evidence.
- Verify with a Python/Pillow environment: Skill metadata validator,
  `skills/create-fixed-direction-action-sprites/tests/test_action_sprites.py`
  and `scripts/verify_pack.py`. Maintenance uses offline fixtures, not paid jobs.
- Match handoffs to the user's language; keep identifiers and raw errors unchanged.
