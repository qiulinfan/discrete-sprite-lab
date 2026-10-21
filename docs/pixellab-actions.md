# Current character and action routing

`create-topdown-8dir-sprites` remains frozen for character reference views.
`create-fixed-direction-action-sprites` is the hybrid temporal workflow:

- Small motions use a task-owned procedural controller and same-view source parts.
- Large silhouette, articulation or occlusion changes use deliberate action keys.
- PixelLab fills the gaps between two specified keys. It does not design a whole
  action from one standing image. Original keys remain exact in the final output.

Plan phases/events before choosing frame counts. Preserve identity, handedness,
body scale and camera through all directions. A larger transparent canvas can
accommodate tools without enlarging logical character pixels. Compare a formula
portrait entry against a tool-ready entry when the distinction affects motion.

The production entrypoint is
[`hybrid_actions.py`](../skills/create-fixed-direction-action-sprites/scripts/hybrid_actions.py).
See the [Skill](../skills/create-fixed-direction-action-sprites/SKILL.md) and
[hybrid contract](../skills/create-fixed-direction-action-sprites/references/hybrid-contract.md).
All actions and A/B samples in a task share one user-authorized budget ledger.
Accepted IDs resume; ambiguous POSTs never retry blindly. Close finished budgets.

The V3 transport supplies first/last guides; provider pixels need not equal the
keys. Preserve all raw responses, then select only interior frames. The final
assembler copies authored keys byte-for-byte at their indices and packages
selected provider PNGs unchanged. No pasted heads, recoloring, grid recovery or
recentering is performed on native API results. High-detail/pseudo-pixel/grid
recovery applies to newly authored keys, not their returned inbetweens.

Historical published packs and failure studies retain their original provenance.
The low-level `pixellab_actions.py` can replay those recordings offline; live
submission requires both endpoints. Replaying an old first-only request does not
claim that the new hybrid route generated that art.

Checks use an existing Python/Pillow environment:

```sh
python3 -B skills/create-fixed-direction-action-sprites/tests/test_hybrid_actions.py
python3 -B skills/create-fixed-direction-action-sprites/tests/test_pixellab_actions.py
python3 -B scripts/verify_pack.py
```

Maintenance tests use synthetic transport/PNG fixtures and do not spend credits.
Integrity, per-frame/normal/slow visual review, user feel and engine integration
remain separate. Never present unviewed frames or failed API jobs as approved.
