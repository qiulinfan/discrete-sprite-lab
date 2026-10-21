# Offline action contract

The entrypoint is `scripts/action_sprites.py`, using Python3.11+ and Pillow.
It packages complete native PNG sequences. The task's controller renders
procedural poses before preparation; authored key poses can also play directly
with deliberate timings. Two flat images do not define an articulated rig.

```json
{
  "schema_version": 3,
  "action": "walk",
  "route": "procedural",
  "controller_or_pose_authority": "Recorded same-view gait controller and contact poses",
  "reference_family": "Approved directional character portraits",
  "image_size": [64, 64],
  "frame_count": 4,
  "durations_ms": [100, 80, 100, 80],
  "loop": true,
  "pivot": [32, 3],
  "ppu": "match the retained character family on integration",
  "palette_max_colors": null,
  "directions": [{
    "direction": "south",
    "frames": [
      {"path": "keys/left-contact.png", "phase": "left-contact", "origin": "authored-key"},
      {"path": "rendered/left-pass.png", "phase": "left-pass", "origin": "procedural"},
      {"path": "keys/right-contact.png", "phase": "right-contact", "origin": "authored-key"},
      {"path": "rendered/right-pass.png", "phase": "right-pass", "origin": "procedural"}
    ]
  }]
}
```

`route` is `procedural` or `authored`. Every direction supplies all final frame
paths and meaningful phases. `origin` defaults to `procedural` or `authored-key`
respectively; a mixed controller/key sequence names the origin of each frame.
An authored four-pose sequence is valid at four frames: do not manufacture extra
frames to reach a target count. The helper does not invent missing poses.

The native canvas is1..256px per side; sequences have2..128 frames per direction.
Sources must be single-frame PNGs at the exact native size, with transparent
binary Alpha and visible pixels. No rescaling or recoloring is performed.
`frame_ms` may replace `durations_ms` for uniform timing. PPU is a positive
number or the name of the matching family; pivot is in pixel space from the
lower-left. Add transparent motion/tool room without scaling the character.

Use frame duration for a held pose. A deliberately repeated nonadjacent return
pose needs `allowed_repeated_frame_pairs`, for example `[[0,3]]`; adjacent
duplicate frames are rejected because APNG may merge them. One-shots set
`loop:false`; their last frame receives `final_hold_ms` (default700ms) in normal
playback, multiplied by `slow_multiplier` (default3) in slow playback.

```sh
python3 -B scripts/action_sprites.py prepare --contract action-plan.json --root output-v1
python3 -B scripts/action_sprites.py assemble --root output-v1
```

The only commands are offline `prepare` and `assemble`. Contracts from the
retired model route are not accepted. There is no credential, budget or online
submission interface.

- `inputs/`: exact copies of the supplied rendered frames and authored keys.
- `contract.json`: functional frame/timing/identity plan.
- `generated/`: exact source PNGs, a1:1 sprite sheet, normal/slow APNGs and a
  functional manifest with phase, origin, timing, pivot and source paths.
- `evidence/`: input/output locks, nearest-neighbor reviews of at least1024px
  per frame and a local integrity result. Keep verification JSON ignored.

Preparation locks its contract and inputs; changed poses, timing or source
pixels require a fresh output version. Packaging verifies exact PNG/RGBA and
APNG timing, with an optional explicit palette cap. The result remains
`production_approved:false` until the separate visual/feel review.
