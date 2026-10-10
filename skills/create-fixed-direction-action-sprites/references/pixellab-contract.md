# PixelLab V3 API and artifact contract

Verified against official V2 OpenAPI and the 2026-10-10 64px walking experiment.
Consult [current schemas](https://api.pixellab.ai/v2/docs) and
[estimated prices](https://www.pixellab.ai/pixellab-api) before changing models.
The official service is `https://api.pixellab.ai/v2`; bearer credentials are
loaded separately from a user file, never serialized in a contract or output.

## API facts

- `GET /balance`: `credits.usd`, `subscription.generations/status/plan`.
- `POST /animate-with-text-v3`: `first_frame`, `action`; optional `last_frame`,
  `frame_count`, `seed`, `no_background`, `enhance_prompt`, `drift_threshold`.
- PNG image objects: `{ "type": "base64", "base64": "<PNG data>", "format": "png" }`.
- Each side <=256px; even 4..16 frames; width × height × frames <=524288.
- POST returns `background_job_id`. Poll `GET /background-jobs/{id}` every
  5–10 seconds until the outer `status` is `completed` or `failed`. A progress
  value or completed inner event is insufficient. Images are in
  `last_response.images`.
- Tested V3 returns a processed input pose plus N generated frames. Contract
  `reference_policy: prefixed` preserves raw 0..N and selects raw 1..N. The
  input pose can differ in color or Alpha from the upload. `none` explicitly
  selects N frames when a verified provider response has no prefixed pose;
  unexpected counts stop rather than guessing.
- Actual credits and subscription/trial consumption are distinct from a
  response's `cost_if_paid`. Do not add both outer/inner usage as two charges.

## Contract

Reference paths resolve from the contract file. Preparation copies exact PNGs
and normalizes artifact paths. `--credential-file`, `PIXELLAB_TOKEN_FILE`, or
the user's existing desktop `pixellab_api.txt` selects the credential file.
Keep both contracts and outputs outside the installed Skill.

```json
{
  "schema_version": 1,
  "model": "v3",
  "description": "Approved protagonist reference family",
  "action": "Seamless relaxed walking in place. Alternate left/right contacts and passing legs, arms opposite to legs. Preserve costume details and lighting; stay on the same ground plane.",
  "image_size": [64, 64],
  "frame_count": 6,
  "frame_ms": 120,
  "slow_multiplier": 3,
  "loop": true,
  "pivot": [32, 3],
  "ppu": "match approved player family on integration",
  "palette_max_colors": null,
  "reference_policy": "prefixed",
  "seed_base": 20261010,
  "no_background": true,
  "enhance_prompt": false,
  "directions": [
    { "direction": "south", "reference": "references/south.png" },
    { "direction": "east", "reference": "references/east.png" }
  ],
  "budget": { "usd": 1.0, "max_jobs": 4, "reserve_usd_per_job": 0.25 }
}
```

The budget is illustrative, not standing permission. Use actual user authority;
`max_jobs` caps POST attempts, including rejected ones. The reservation is a
conservative client guard, not a provider-enforced price ceiling. Select it
from current pricing/response evidence; do not reuse the small 64px estimate
for every model or size. The helper currently requires an available USD
reserve even when the provider may use trial generations.

Directions: north, northeast, east, southeast, south, southwest, west,
northwest. List requested directions in output row order. Optional direction
`seed` overrides `seed_base + row`; optional same-size `last_frame` supplies
a target pose. Timings/counts depend on the action; a walk example does not
define all attacks, tools or one-shots. `palette_max_colors: null` preserves
model colors with no color-count cap; an integer is an exact whole-sheet gate.
Color drift still requires visual inspection. There is no local recoloring.

## Commands

From this Skill directory, using an existing Python/Pillow environment (or use
the script's full path):

```sh
python3 -B scripts/pixellab_actions.py prepare --contract request.json --root output-v1
python3 -B scripts/pixellab_actions.py balance --credential-file TOKEN_FILE
python3 -B scripts/pixellab_actions.py run --root output-v1 --credential-file TOKEN_FILE
python3 -B scripts/pixellab_actions.py package --root output-v1
```

`run` resumes IDs and skips completed directions. Ambiguous POST failures stay
`post-uncertain`; inspect the existing provider job before any new submission.
After resolving a definite rejection or a terminal failed job, an authorized
explicit retry uses the same budget/attempt cap:

```sh
python3 -B scripts/pixellab_actions.py run --root output-v1 --retry-direction east --credential-file TOKEN_FILE
```

Changing reference/action/seed for quality revision uses a fresh version.
`replay --contract request.json --root replay-v1 --recordings RECORDED_JOBS`
reads each `{direction}/request.json` and `{direction}/job-latest.json`, checks
the recorded reference hash/count, preserves the original request, and marks
the root `offline-replay`. It cannot later submit jobs. A replay contract
describes packaging; recorded prompts/seeds, not new text, produced that art.

## Output and review

Attempt folders retain requests, acceptance, job responses, every raw PNG,
selected PNGs and selection observations. Packaging checks exact RGBA against
the raw provider files and their recorded hashes. Magnification is integer
nearest-neighbor; the 1:1 sheet and normal/slow APNGs retain exact pixels and
timing. Loop APNGs repeat, one-shots play once. Engine import is separate.

After actually inspecting every magnified frame and normal/slow sequence,
`package --visual-review review.json` accepts this shape:

```json
{
  "sheet_sha256": "<current sheet hash>",
  "frame_hashes": { "south/0": "<current RGBA hash>" },
  "frame_ms": 120,
  "slow_multiplier": 3,
  "loop": true,
  "direction_order": ["south"],
  "authority": "named reviewer",
  "individual_frame_review": true,
  "normal_and_slow_review": true,
  "verdict": "candidate-with-warnings",
  "findings": { "south": "concrete identity, anatomy and motion observations" },
  "warnings": ["specific remaining limits"]
}
```

Include every frame hash and every direction's findings, not only the example.
`pass` and `visual-fail` are also valid. Hard failures remain `technical-fail`
despite a positive subjective verdict. Hashes, timing, loop mode and direction
order bind the review; changing any requires a fresh review. User preference,
human feel and engine tests remain separate evidence.
