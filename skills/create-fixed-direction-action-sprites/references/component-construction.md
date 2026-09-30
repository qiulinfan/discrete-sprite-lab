# Preserve Component Design and Connections

Use this reference for native component construction and bounded detail repairs. Apply it to heads, hair, hands, cuffs, clothing, footwear, ornaments, tools and weapons. Treat a crop or glyph as the representation of a named component with a design, a pose and connections to the rest of the character.

## Carry Design Through Pose Changes

1. Use one approved design family and the corresponding view master. Identify the component's characteristic silhouette, proportions, distinguishing features and surface treatment; preserve the approved style's level of detail. A pose can be connected and palette-correct while a simplified component loses the original design.
2. Separate design constraints from pose variables. Keep the item's defining shape/material language while changing the view-dependent visible faces, articulation, deformation and overlap required by the phase. Use native strokes, glyphs or polygons to construct geometry, then refine the visible features against the approved family.
3. Assign palette colors by their material and light/shadow roles. Preserve meaningful edges, folds, creases and highlights where visible. Being a far component determines depth and occlusion; it does not alone justify collapsing every material tone into one dark block. Review camera-relative illumination when drawing opposite views.
4. Select reuse from the actual state. Reuse exact native cells only while visible orientation, topology, load, lighting and overlap remain compatible with the approved cel. Author phase variants when these change. Preserve design across variants without freezing valid articulation or forcing identical pixels in different views.

Use these distinctions when choosing geometry:

| Component | Design to retain where visible | Phase/view change to author |
| --- | --- | --- |
| Head or hair | Recognizable silhouette, face and hair clusters | Expression, tilt, hair response, occlusion and neck attachment |
| Hand or cuff | Hand volume, cuff shape and trim | Wrist orientation, grip, finger/contact silhouette and sleeve connection |
| Hem or ornament | Garment cut, edging, emblem or ornament form | Folds, sway, visible surface and attachment to cloth/body |
| Boot or shoe | Cuff, shaft, toe, heel, sole and material treatment | Foreshortening, contact/load, foot rotation and ankle connection |
| Tool or weapon | Blade/head, handle and identifying fittings | Visible faces, swing trajectory, hand contact and layer order |

## Build and Connect Exact Native Cells

1. Declare each component's role, source cells, phase family, attachment anchor, allowed integer transforms and layer order. Anchor to its actual body, joint or contact parent. A head follows the neck; a planted foot can stay fixed while the hips move. The native packager's body-offset `stable_regions` assertion cannot represent independently anchored parts; verify their placement separately.
2. Isolate source cells with an agent-chosen crop or mask. Inspect every border and transparent gap for neighboring clothing, limbs or objects. One included cell can create a detached detail even when its color is in the palette. Record exact erasures, including zero RGB/Alpha; scripts do not select anatomy from colors or components.
3. Clear superseded outlines, idle remnants and primitive line caps within the relevant construction layer before compositing. Write the complete transparent footprint. An erase operation on the already combined character can remove a neighboring component or far limb. Repaint exposed garment/skin with the current phase's geometry.
4. Assemble with 1:1 RGBA and integer placement. Inspect the connection and its context: neck/head, sleeve/wrist, hip/leg, ankle/shoe, hand/tool, or cloth/ornament. Confirm joint position, contour width, part count, negative space and near/far overlap throughout the action. If correspondence crosses an uncertain joint, return to coherent phase construction instead of expanding a pasted rectangle.

## Revise Locally and Review at Three Scales

- Preserve an otherwise accepted parent version and declare the smallest coherent repair footprint before editing. Include old cells that must become transparent and enough context to judge attachment. Repair the identified design or connection defect; expand the scope only when actual anatomy requires it.
- Verify exact RGBA outside the footprint for every frame. For a detail-only revision, preserve unrelated pose anchors, phase timing/events and layers. Keep the original master and prior version available; do not change motion merely to conceal a local defect.
- Inspect **the component** against its approved design: silhouette/proportions, identifying details, material roles, source-border residue and transparent footprint. Use local before/after/difference views; isolate the relevant layer when available so clipped neighboring effects are not mistaken for component pixels.
- Inspect **the complete pose** at integer nearest-neighbor magnification with at least 1024 pixels on the long edge: attachment, silhouette, consistent design/detail treatment across parts, both limbs, draw order and weapon/effect overlaps. A good isolated crop can still be misplaced, disconnected or stylistically inconsistent with the whole character.
- Inspect **the sequence** at normal and slow speeds: phase semantics, parent/contact motion, expected deformation, detail flicker, occlusion and return/loop closure. Review corresponding phases across requested views. Refresh pixel/timing-bound review after changes and record the user's decision against the reviewed version, separately from engine integration.

## Transfer the Method, Not a Particular Patch

A planted slash with acceptable body and weapon motion but block-like boots illustrates loss of component design: restore view-specific native silhouettes and material detail, clear old ankle caps per leg, remove neighboring crop cells and keep the rest exact. The same method applies to a cuff reduced to a generic band, a hand pasted onto a rotated wrist, a flattened garment edge, or a weapon fitting whose grip no longer connects.

Keep the source feature inventory, coordinates, palette, frame count and cel-reuse decisions local to the actual character and phase. For independently generated bodies with uncertain joint correspondence, repair the complete source phase; native shared-cel construction does not authorize broad overlays on mismatched generated anatomy.
