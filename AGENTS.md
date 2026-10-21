# Discrete Sprite Lab agent guidance

- Current production workflows: `skills/create-topdown-8dir-sprites` for static
  character views, `skills/create-fixed-direction-action-sprites` for PixelLab
  hybrid action animation. The latter routes small motions to procedural
  controllers, large pose changes to deliberate same-view keys, and only
  inbetweens to PixelLab. Keep its public invocation name.
- The owner froze the spatial Skill. Do not change its files, scripts, tests
  or behavior as action-work maintenance.
- Current action entrypoint: `scripts/hybrid_actions.py` inside the action
  Skill. Preserve original authored keys at their planned indices. PixelLab
  live requests require both endpoints; never generate a full action from a
  single standing reference. Preserve provider output without head patches,
  recoloring, recentering or grid recovery. Procedural controllers and authored
  keys have their own source/geometry records; API failures are not locally
  repainted.
- Keep credentials and machine-specific artifacts outside this public repo.
  Use task-local contracts/output roots; no embedded bearer tokens.
- The sibling `../discrete-sprite-lab-experiments/` is the local workspace for
  full experimental images, intermediates, reports and API evidence. These are
  Discrete Sprite Lab research materials, not Village_Rim production assets.
  Keep selected published examples in `art-pack/` and `case-studies/`; new local
  experiments belong in that external workspace, not the game's ArtSource.
- Historical published art, source evidence and failure studies remain intact.
  README examples describe that publication; active development commands and
  current routing are here and in `docs/pixellab-actions.md`.
- Preserve existing user work and licenses. No commit/push without the owner's
  explicit request. Personal environment files stay ignored.
- Verify changes with a Python/Pillow environment: Skill metadata validator,
  `skills/create-fixed-direction-action-sprites/tests/test_pixellab_actions.py`,
  `skills/create-fixed-direction-action-sprites/tests/test_hybrid_actions.py`,
  and `scripts/verify_pack.py`. Do not spend credits to test maintenance when
  recorded-response replay and synthetic transport fixtures suffice.
- Match handoffs to the user's language; keep identifiers/API fields unchanged.
