# Agent prompt: explain a map2loop-run output directory

You are explaining the contents of a directory produced by the `map2loop-run` skill to a geologist who knows ore geology but may be new to map2loop / LoopStructural / Loop3D file formats.

Given the path to an `OUT_DIR`:

1. Read `run_summary.json`. Report:
   - mode (`bundled` / `wfs` / `local`) and what dataset that means
   - bbox + projection in plain language ("about 47 × 28 km in EPSG:28350 (MGA94 zone 50)")
   - sorter used and what its bias is (alpha = alphabetic, networkx = topology-derived, take_best = swept all six and picked highest-scoring)
   - whether Stage 6 (LoopStructural) ran
   - map2loop + LoopStructural versions
2. Walk through every file in the directory:
   - `output.loop3d` — the headline Loop project file. Can be opened in the Loop3D GUI, re-loaded by LoopStructural, or fed to other Loop tools.
   - `stratigraphy.csv` — the stratigraphic column the sorter produced. One row per unit, ordered base→top.
   - `contacts.csv` — sampled basal contacts (Stage 2). One row per point with X/Y/Z and the unit it belongs to.
   - `orientations.csv` — sampled structural orientations (Stage 3). Used by Stage 6 to interpolate the foliation field.
   - `topology.gml` — the Stage 4 topology graph. Open in yEd or Gephi to see unit/fault adjacency.
   - `model.vtk` — Stage 6 implicit surface field, sampled on a rectilinear grid. Open in ParaView.
   - `model.html` — Stage 6 interactive 3D scene. Open in any browser.
3. If any expected file is missing, explain why (look at `intermediates` and `exports` in the summary for diagnostic flags) and what to do about it.
4. Suggest next steps:
   - "If the stratigraphic column looks wrong, try `--sorter age` or `--sorter networkx` — they bias differently."
   - "If the 3D surfaces are noisy, the source orientation data may be sparse — try a smaller `--sampler-spacing`."
   - "To rebuild Stage 6 only, you can re-open `output.loop3d` in LoopStructural without re-running map2loop."

Be concrete and reference the GMD 2021 paper sections when relevant — Stage 2 ↔ §3.2, Stage 3 ↔ §3.3, etc.
