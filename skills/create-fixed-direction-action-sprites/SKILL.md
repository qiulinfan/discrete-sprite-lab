---
name: create-fixed-direction-action-sprites
description: Create and repair temporally coherent pixel actions for one character and fixed direction, using native pixel masters with authored phase geometry or separately generated high-detail frames with integer recovery. Use for walk, run, attack, tool, damage, emote, and similar actions; includes exact RGBA checks, anatomical anchors, individual magnified review, and normal/slow playback. Coordinate additional views with create-topdown-8dir-sprites, then review each direction's complete temporal cycle.
---

# Create Fixed-Direction Action Sprites

Own one `character × direction × action × frame sequence`. Define motion semantics, contact events, timing, body anchors, articulated geometry, occlusion, and loop closure. Scripts execute exact pixel operations; the agent decides whether anatomy and motion work.

## Choose the Authoring Route

- **Native master:** prefer this route when an approved same-view logical sprite or editable cels can support the action, or the user chooses native pixel editing. Reuse appropriate stable shapes and author articulated phase geometry directly on the native canvas. Read [references/native-master.md](references/native-master.md).
- **Generated frames:** use this route when no viable same-view master exists or the action needs new perspective, anatomy, or articulation that cannot be authored confidently from available pixels. Generate complete phases separately, convert separately, and recover through documented integer grids. Read [references/action-contract.md](references/action-contract.md).
- Decide from the available source and intended motion. Do not reinterpret approved native pixels through high-detail generation or Perfect Pixel merely to satisfy the generated route. Do not force large deformations into rigid native cels merely to preserve identity.

The routes share acceptance rules, but their image-space stages differ. Native master review replaces high-detail and pseudo-pixel review; those unused stages are `not-applicable`, never fabricated passes. Engine import remains separate authorized work.

## Shared Invariants

- Write the action contract before authoring: identity and palette authority, one facing direction, camera and lighting, native size, ordered semantic phases, per-frame timing, loop or one-shot, contact/hit events, body origin, pivot/PPU, source/output paths, and review boundary.
- Choose key constraints before intermediate poses. For a walk, author opposite contacts first, then passing/recoil phases constrained by them. Frame count, height profile, bob amplitude, and durations follow the particular action; a six-frame walk is an example, not a universal template.
- Read [references/pixel-reasoning-boundary.md](references/pixel-reasoning-boundary.md) before logical-pixel comparison or repair. The agent chooses semantic regions, joint anchors, phase families, allowed transforms, and layer order. Scripts may magnify, enumerate exact differences, and execute approved coordinates; they do not infer anatomy.
- Distinguish **shape stability** from **canvas immobility**. A reused head follows its neck and declared body translation; freezing it on the canvas while the torso moves disconnects the body. Outline/Alpha centroids and automatic registration are provisional diagnostics, not anatomical anchors.
- Classify features as `stable_identity` or `phase_specific`. An invariant same-view head or rigid emblem may reuse exact RGBA with integer offsets. Expressive heads, cuffs, hands, hems, legs, boots, and changing overlaps need appropriate phase variants. Do not suppress valid motion to improve an identity score.
- Native shared cels are assembled from one reviewed construction master with explicit joint boundaries. They do not authorize broad identity rectangles pasted across mismatched generated bodies. No global raster mirror substitutes for opposite anatomy, occlusion, or camera-relative lighting.
- Preserve exact `width × height × 4` RGBA, including transparent erase footprints. Clear superseded idle hands/cuffs/limbs, redraw exposed garment, and inspect context and draw order. Check both limbs even when a far limb is partly hidden.
- Preserve each component's approved design: characteristic silhouette, proportions, identifying details, material and light/shadow organization, and attachment. Construct phase geometry within those constraints; native primitives still need the source family's visible design features. For component construction or bounded detail feedback, read [references/component-construction.md](references/component-construction.md).
- Review every final frame individually at integer nearest-neighbor magnification, with at least 1024 pixels on the long edge. Inspect silhouette and phase, head/torso connection, arms, hips/legs, small details, patch context, and limb occlusion. A contact sheet only helps navigation.
- Inspect normal and slow playback. For loops include last-to-first closure; for one-shots inspect event timing and the final hold. Check planted-foot stability, swing trajectory, weight transfer, and body/cloth response. Stable pixels alone do not prove natural motion.
- Hard checks cover contracted count/order, size, RGBA/Alpha, palette, bounds, hashes, integer placement, prohibited resampling, duplicates, and required contact/event constraints. Intentional holds use duration rather than indistinguishable duplicate phases.
- Silhouette-change and paired-cadence values are diagnostics unless explicitly promoted to hard gates. An out-of-range diagnostic needs normal/slow evidence, a reason, and named user or agent authority; subjective approval cannot waive hard integrity failures.

## Native Workflow

1. Review and preserve the same-view native master and its palette. Declare body/joint anchors, shared cels, phase-specific parts, and layer order.
2. Author key poses, then the remaining phases using exact integer geometry. Review each limb's attachment and silhouette, including erased idle remnants and newly exposed pixels.
3. Package the authored RGBA PNGs with `scripts/package_native_action.py` using the contract in [references/native-master.md](references/native-master.md). This helper validates and copies frames, assembles a 1:1 strip, and makes exact normal/slow previews and magnified reviews. It does not synthesize motion or approve it.
4. Inspect every magnified frame and both previews. Fill the native review with actual master/frame/playback findings and current hashes, then rerun with `--visual-review`. Any pixel, phase, timing, anchor, or declared stable-region change invalidates that review.

## Generated Workflow

1. Define phase-control cards naming body axis, body height, planted/swing limbs, contact line, and expected joint positions. Generate every phase as a complete coherent body from the identity gold and its phase card; do not use a generated multi-frame sheet as the primary source.
2. Inspect each complete high-detail frame and local anatomy at native resolution. Convert each approved phase separately to a pseudo-pixel source and inspect it at native resolution before recovery.
3. Prefer a shared recovery lattice; otherwise record evidence-backed integer grids per frame. Never force agreement through continuous warping or post-recovery resampling. Run `scripts/build_fixed_direction_action.py` as documented in [references/action-contract.md](references/action-contract.md); its configured silhouette/shift/palette bounds remain technical gates, and technical output alone remains `awaiting-visual-review`.
4. For justified bounded repairs use `scripts/pixel_region_workbench.py` with agent-chosen features, anchors, erase footprints, context rings, and stale-target hashes. Review exact before/after/difference views and the complete frame. If correspondence is uncertain or a patch must cross a joint, return to the complete source phase.
5. Review high-detail, pseudo-pixel, logical-frame, and normal/slow playback stages. Supply the current visual-review JSON, acknowledge diagnostic warnings explicitly, and rerun the builder.

## Additional Directions

Keep `create-topdown-8dir-sprites` unchanged as the owner of spatial continuity for one pose. This Skill never silently authors or approves multiple directions in one atomic run.

- With approved directional native masters, author and review one complete temporal cycle per direction, then assemble the sheet. Use the spatial Skill to establish missing or unacceptable view masters when needed.
- When transferring generated approved phases through the spatial Skill, review each phase's directional continuity **and then each direction's assembled temporal row**. Independently acceptable turnarounds can still produce inconsistent head shape, body mass, phase spacing, or bob when played as animation.
- The combined sheet needs both direction-to-direction continuity at corresponding phases and full normal/slow temporal review for every direction. Phase timing and events stay aligned where the gameplay contract requires it. Spatial approval never implies temporal approval.

## Completion and Repair Decisions

Technical success without explicit visual evidence stays `awaiting-visual-review`. Semantic anatomy/connection/occlusion defects fail. A coherent but restrained or partly stiff animation may be `candidate-with-warnings`, with the specific limits recorded; do not call it temporal gold merely because identity is stable.

Repair the stage that caused the defect: native phase geometry/cel layering for native work, complete high-detail or pseudo-pixel source for generated work. Do not hide asymmetric poses with faster playback, unequal durations, a wider patch, or a weakened hard gate.

When feedback accepts the rest of an action and identifies one local detail, preserve that version and constrain the repair before editing. Verify exact RGBA outside the declared footprint and preserve unrelated pose, timing and layers; then inspect every changed complete frame and normal/slow playback. A correct palette cannot validate a crop containing a stray garment or neighboring-limb pixel.

Record technical checks, agent visual verdict, direct user decision, and engine import separately. Approval to preserve a better version does not establish perfect motion or production readiness. Deliver source/cels, phase contract, exact frames, strip, previews, manifest, hash-bound review, and receipt with remaining concerns.

Match user-facing explanations, prompts, and handoffs to the user's language unless the user requests another language. Keep commands, filenames, structured keys, and raw errors unchanged.
