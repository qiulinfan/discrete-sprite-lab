# Discrete Sprite Lab agent guidance

- Current production workflows: `skills/create-topdown-8dir-sprites` for static
  character views, `skills/create-fixed-direction-action-sprites` for PixelLab
  API animation. The latter retains its public invocation name while its
  native-cel/ImageGen temporal implementation is retired.
- The owner froze the spatial Skill. Do not change its files, scripts, tests
  or behavior as action-work maintenance.
- Action generation and quality revisions use PixelLab. Preserve raw results;
  local scripts package/review exact native pixels and do not author anatomy,
  paste heads, recolor or provide an old authoring fallback.
- Keep credentials and machine-specific artifacts outside this public repo.
  Use task-local contracts/output roots; no embedded bearer tokens.
- Historical published art, source evidence and failure studies remain intact.
  README examples describe that publication; active development commands and
  current routing are here and in `docs/pixellab-actions.md`.
- Preserve existing user work and licenses. No commit/push without the owner's
  explicit request. Personal environment files stay ignored.
- Verify changes with a Python/Pillow environment: Skill metadata validator,
  `skills/create-fixed-direction-action-sprites/tests/test_pixellab_actions.py`,
  and `scripts/verify_pack.py`. Do not spend credits to test maintenance when
  recorded-response replay and synthetic transport fixtures suffice.
- Match handoffs to the user's language; keep identifiers/API fields unchanged.
