# Hybrid action contract

The entry script is `scripts/hybrid_actions.py`. It uses Python3.11+ and Pillow;
prepare and assemble are offline. A task may have several action roots sharing
one cost ledger. Contracts and art stay outside the installed Skill.

## One action

```json
{
  "schema_version": 2,
  "action": "pickaxe",
  "route": "keyframed",
  "controller_or_pose_authority": "Reviewed same-direction protagonist keys",
  "image_size": [96,96],
  "frame_count": 12,
  "frame_ms": 80,
  "loop": false,
  "pivot": [48,19],
  "ppu": "match retained character family on integration",
  "budget_file": "evidence/task-budget.json",
  "transition_description": "Slowly connect these two poses, keeping one rigid handheld object and both hands connected.",
  "seed_base": 101,
  "directions": [{
    "direction": "south",
    "keys": [
      {"frame":0,"path":"keys/ready.png","phase":"tool-ready"},
      {"frame":3,"path":"keys/windup.png","phase":"overhead windup"},
      {"frame":5,"path":"keys/impact.png","phase":"ground impact"},
      {"frame":11,"path":"keys/recover.png","phase":"recovery"}
    ]
  }]
}
```

Frame count and timing are action-specific. `durations_ms` optionally supplies
one positive duration per frame. One-shots require authored frame0 and the final
frame. Loops connect the last key back to the original frame0 without duplicating
that endpoint in storage. Each key has a meaningful phase label. No gap can need
more than15 interior frames: author another phase instead. The V3 per-job pixel
limit still applies. Native size is1..256 per side; source keys and procedural
frames must match it exactly, without stretching.

For `route: procedural`, replace each direction's keys with `frames`, a complete
ordered list of native PNG paths. Name the actual controller in
`controller_or_pose_authority`, and preserve its source/parts/parameters alongside
the plan. The script packages its exact output and never submits API jobs.

Optional `allowed_repeated_frame_pairs: [[0,11]]` explicitly allows a returned
ready pose or designed hold. All other visible duplicates stop assembly.
`final_hold_ms` defaults to700 for one-shots; `slow_multiplier` defaults to3.

## Shared task budget

Create this ledger only from current user authorization, not by copying a past
example. Store it in ignored evidence; never put credentials in it.

```json
{
  "schema_version":1,
  "status":"open",
  "authority":"Current user-authorized task and spending scope",
  "usd":5,
  "max_jobs":180,
  "reserve_usd_per_job":0.05,
  "jobs":[]
}
```

Numbers above illustrate the format, not standing permission or a price quote.
Reservations are client guards, not provider-enforced price ceilings. Use current
size/model pricing and balance evidence. All action roots and A/B comparisons in
the same task reference this exact ledger; they do not each receive a new budget.
An OS file lock prevents concurrent workers from spending against one ledger.
The ledger retains initial/latest balances, actual USD delta, trial consumption
and every attempted job. Close its status when the task's submissions finish.

## Commands

```sh
python3 -B scripts/hybrid_actions.py prepare --contract action-plan.json --root output-v1
python3 -B scripts/hybrid_actions.py run --root output-v1 --credential-file TOKEN_FILE
python3 -B scripts/hybrid_actions.py assemble --root output-v1
```

`run --max-new-jobs 1` submits a bounded first sample. Run again to resume the
existing ID and continue. A transient GET failure never authorizes a new POST.
A known failed/rejected/artifact-invalid segment stops for inspection; a reviewed
revision uses a fresh action root and the same task ledger. An ambiguous POST
stays `post-uncertain`; locate the existing provider job before any resubmission.
No automatic subscription/model upgrade is implemented.

V3 has a minimum of4 generated frames. Each gap requests the smallest sufficient
even count; the exact raw indices selected for its interior time slots are saved
in `evidence/jobs.json`. Raw0 is the returned processed reference; every raw PNG
is retained. The proportional index selection is a documented sampling policy,
not proof of constant velocity or semantic event alignment. Authored keys always
win at their indices. Never paste identity patches over API inbetweens.

## Artifacts and evidence

- `inputs/`: exact copied native keys/controller PNGs.
- `contract.json`: functional action plan with copied input paths.
- `generated/manifest.json`: source/origin, direction, index, duration and rect;
  no hash inventory. `generated/sheet.png`, native PNGs and normal/slow APNGs.
- `evidence/`: input/output digest locks, immutable API payloads/responses/raw
  PNGs, slot selection,1024px reviews and integrity audit. Ignore this directory.

Assembly proves original keys and chosen API pixels are exact, all time slots
exist, Alpha/dimensions are valid and APNGs match pixels/timing. It records
`production_approved:false` until a separate visual/feel decision. An API error,
missing sequence or unviewed frame cannot be converted into an approval label.

`assemble --direction north` exports only an actually completed pilot row and marks
`complete:false` plus the full requested direction order. It does not waive missing
rows: run/assemble without that filter to finish the complete contracted set.
