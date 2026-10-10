# Current character and action routing

On 2026-10-10 the owner chose PixelLab API for the complete animation workflow.
`create-topdown-8dir-sprites` stays unchanged for static reference views.
`create-fixed-direction-action-sprites` keeps its public invocation name, with
new PixelLab instructions/client, lossless packaging, budget/async handling and
visual review. Its previous native-cel and separately generated ImageGen action
routes, scripts, repair tools and tests are retired from the active Skill.

Flow: approved directional references → contract/budget → PixelLab native
animation per direction → preserve raw responses/frames → exact packaging →
individual magnified frames and normal/slow sequences → hash-bound review →
separately scoped engine integration. Requested views share a canvas/timer;
semantic gait/event alignment must be reviewed rather than inferred by index.

Instructions and contract:
[PixelLab action Skill](../skills/create-fixed-direction-action-sprites/SKILL.md),
[API/artifact contract](../skills/create-fixed-direction-action-sprites/references/pixellab-contract.md).
The old public art and failure studies describe how earlier assets were made;
their native pixels and historical evidence are unchanged. That provenance
does not authorize invoking retired production code.

The retained entry name avoids breaking public Skill references and the frozen
spatial Skill's links. No legacy code or provider fallback remains behind it.
The archived implementation is recoverable in the owner's private archive,
with source commit and per-file hashes; Git also retains published history.

Current checks (existing Python/Pillow environment):

```sh
python3 -B skills/create-fixed-direction-action-sprites/tests/test_pixellab_actions.py
python3 -B scripts/verify_pack.py
```

The helper's offline `replay` accepts preserved API requests/results and checks
their reference hashes. Replay labels are explicit; it cannot issue live jobs
or claim that a new prompt generated old frames. Maintenance validation does
not consume credits. Optional `balance` is read-only.

V3 is the default tested API model. Other PixelLab models require current
schema/cost/access checks and remain PixelLab-only. Avoid automatic upgrades,
new subscriptions or reusing completed-task budgets. Actual USD debit, trial
generations and returned paid-equivalent estimates are separate quantities.
