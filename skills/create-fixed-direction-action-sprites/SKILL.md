---
name: create-fixed-direction-action-sprites
description: Create temporally coherent fixed-direction pixel animation cycles from separately generated high-detail frames using magnified semantic review, evidence-backed integer recovery lattices, agent-approved local pixel patches, paired cadence diagnostics, cyclic audits, and handoff evidence. Use for one direction of walk, run, attack, tool, damage, emote, or similar actions; use create-topdown-8dir-sprites separately to propagate approved phases across directions.
---

# Create Fixed-Direction Action Sprites

Create one action for one fixed facing direction. The output is a temporal gold strip and loop, not a turnaround.

## Atomic Boundary

- Own exactly one `character × direction × action × frame sequence`.
- Own action phases, contact events, pose-control cards, frame timing, planted and swing limbs, body-bob curve, temporal continuity, and loop closure.
- Own the boundary between agent semantic reasoning over magnified local pixel regions and scripts that execute exact pixel algebra.
- Do not generate or audit multiple directions inside this Skill.
- Do not modify, mirror, or expand `create-topdown-8dir-sprites`. After the temporal gold passes, reference that Skill once per approved phase when multi-direction propagation is requested.
- Engine import and animation-controller wiring remain separate authorized work.

## Non-Negotiable Invariants

- Define every frame's semantic phase before image generation. A frame number alone is not a pose specification.
- Use one pose-control card per frame. Do not use a generated multi-frame sheet as the primary source; prior trials showed perspective drift, duplicate phases, baked backgrounds, and scale changes.
- Generate paired key poses before interpolating phases. For a symmetric six-frame walk, author opposite contacts first, then opposite passing poses, then recoil poses constrained by their neighboring key poses.
- Generate every phase as a complete high-detail frame. Do not create an opposite half-cycle by globally mirroring recovered raster art, and do not splice anatomy with a broad rectangular identity mask.
- Review each high-detail frame individually at native resolution before pseudo-pixel conversion. Review each pseudo-pixel source individually at native resolution before recovery. Review every recovered logical frame individually at nearest-neighbor scale large enough for semantic inspection, with 1024 pixels on the long edge as the default minimum.
- Read [references/pixel-reasoning-boundary.md](references/pixel-reasoning-boundary.md) before logical-pixel comparison or repair. Scripts may crop, magnify, enumerate exact differences, apply integer transforms, and write approved coordinates; the agent chooses semantic regions, correspondences, phase variants, and whether the result is anatomically coherent.
- Classify every local patch as `stable_identity` or `phase_specific`. A same-view head silhouette, face, or emblem may reuse one canonical exact patch with integer bob offsets. Skirt hems, cuffs, hands, legs, and boots require phase-family variants because their topology and occlusion change with motion.
- Preserve stable identity details through agent-approved local feature patches with explicit anchors, transparent erase footprints, and context rings. Never let a patch cross an articulating neck, shoulder, elbow, wrist, waist, hip, knee, or ankle boundary.
- Prefer one pseudo-pixel recovery lattice when all frames recover cleanly from it. If independently generated sources need different integer refined-grid shapes, record the selected grid per frame and continue only when each native pseudo source, recovered frame, body-axis placement, and magnified loop passes. Never force a shared grid by continuous scaling, warping, or post-recovery resampling.
- For physically symmetric cycles, define phase pairs and corresponding transition pairs, but author both sides as complete frames. Use symmetry metrics as evidence, not as a substitute for anatomy, occlusion, or lighting review.
- Separate hard integrity checks from visual diagnostics. Dimensions, Alpha, hashes, bounds, exact writes, prohibited resampling, required contacts, duplicate frames, and an explicitly required diagnostic are hard gates. Silhouette-change and paired-cadence measurements are diagnostic by default; they cannot automatically approve or reject animation feel.
- A passing review with an out-of-range diagnostic must name the diagnostic, record normal-speed and slow-loop evidence, state a reason, and identify `user` or `agent_visual_review` authority. Direct user approval is authoritative for subjective motion feel but never overrides a hard integrity failure.
- Each frame keeps the approved identity, fixed facing direction, camera, costume, body mass, camera-relative lighting, canvas, and anchor system.
- Align a temporal action to its stable head/torso body axis. Feet move around the fixed gameplay pivot during a walk; centering each frame on its current feet creates artificial lateral body jumps. Foot-axis placement is a turnaround rule, not the default action rule.
- Uniform scale and translation are allowed only at high resolution before pseudo-pixel conversion. Do not piecewise-warp anatomy to force a phase.
- Convert every approved high-detail phase separately to a pseudo-pixel source using the approved character palette authority.
- Perfect Pixel defines the logical pixels. Post-recovery non-integer resampling is forbidden.
- A loop must be evaluated cyclically, including the last-to-first transition.

## Workflow

1. Read [references/action-contract.md](references/action-contract.md) and write the action, phase, timing, contact, anchor, palette, and completion contract.
2. Produce one code-native or user-approved pose-control card per phase. The card names planted foot, swing foot, arm counter-swing, body height, body axis, and expected contact line.
3. Generate complete high-detail frames individually from the character gold and exact phase card. Inspect the full anatomy and local head, shoulders, arms, waist, hips, legs, and feet at native high resolution. Reject malformed sources before pixelization.
4. Convert each approved frame to a high-resolution pseudo-pixel source. First try a shared recovery lattice; otherwise retain evidence-backed per-frame integer recovery grids. Inspect the full source and local identity or articulation regions at native resolution. Reject missing, fused, detached, or incoherent features before recovery.
5. Run `scripts/build_fixed_direction_action.py`. It produces technical evidence and individual nearest-neighbor magnified logical-frame reviews. Without an explicit review file matching the sheet hash, its strongest status is `awaiting-visual-review`, never `pass`.
6. Use `scripts/pixel_region_workbench.py review` to compare agent-chosen local windows and their context rings against approved or phase-specific references. If a local repair is justified, use `extract` and `apply`; these commands operate on exact `64 × 64 × 4` RGBA cells, including transparent cells that erase an old silhouette, with integer anchors and stale-target hashes. They never perform semantic matching or continuous image processing.
7. Inspect every magnified before, after, and exact difference view, then inspect the full magnified frame and cyclic loop at normal and slow speed. Author a visual-review JSON covering high-detail, pseudo-pixel, logical-frame, and loop stages. Explicitly acknowledge any failed diagnostic with evidence and authority. Rerun the builder with `--visual-review`; semantic defects fail, while reviewed diagnostic warnings may be accepted without weakening hard checks.
8. When one direction becomes temporal gold and the user requests more directions, hand each approved phase to `create-topdown-8dir-sprites`. That Skill owns the spatial direction axis; this Skill retains ownership of temporal semantics.

## Stopping Conditions

- Stop before propagation when the temporal master fails.
- Regenerate a source phase rather than weakening a hard integrity gate solely to make an audit pass.
- Do not use shorter timing or unequal frame durations to conceal asymmetric pose spacing.
- Do not accept a same-view humanoid loop whose declared recovery-grid policy, hard checks, magnified local reviews, or full anatomy reviews fail. An out-of-range paired-cadence diagnostic requires explicit review evidence and acknowledgement; absence of acknowledgement stops approval.
- Stop when a local feature cannot be matched confidently inside a bounded window. Regenerate the complete high-detail phase instead of widening the patch across a joint.
- Treat global raster mirroring and broad identity overlays as regression techniques only, never production repair.
- If one global translation cannot align the declared anchors, repair or regenerate the high-resolution source; never deform recovered pixels.
- Do not claim an animation is complete from a contact sheet, GIF, or technical audit alone. Individual magnified review at every image-space stage is required evidence.

Match user-facing explanations, prompts, and handoffs to the user's language unless the user requests another language. Keep commands, filenames, structured keys, and raw errors unchanged.
