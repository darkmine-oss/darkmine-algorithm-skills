---
name: map2loop-run
description: Run the map2loop 3D geomodel input pipeline (Loop3D/map2loop) end-to-end over a chosen region, optionally building 3D surfaces via LoopStructural. Three input modes — `bundled` (Hamersley demo dataset that reconstructs the GMD 2021 paper case study), `wfs` (Loop's Web Feature Service for any Australian state), or `local` (user-supplied GeoJSON layers + DTM). Outputs a `.loop3d` project file plus inspectable intermediate CSVs/GMLs and an optional VTK + interactive HTML 3D model. Use when a user says "run map2loop", "build a 3D geological model from a map", "reconstruct the GMD paper", "deconstruct a geology map into Loop inputs", or "generate a loop3d file for region X".
version: v0.1.0
---

# map2loop Run

Wrap the [map2loop](https://github.com/Loop3D/map2loop) `Project.run_all` pipeline as a single CLI. Optionally hand the resulting `.loop3d` to [LoopStructural](https://github.com/Loop3D/LoopStructural) for implicit 3D surface modelling and export VTK + interactive HTML.

The default invocation reconstructs the case study from [Jessell et al. 2021 (GMD)](https://gmd.copernicus.org/articles/14/5063/2021/) — the Rocklea Dome / Hamersley region in Western Australia. map2loop ships the geodata under `map2loop/_datasets/geodata_files/hamersley/`, so the demo path needs no network access.

## Dependencies

Requires the `loop` conda env created by the [`setup-loop`](../setup-loop/SKILL.md) skill. Activate it first:

```bash
conda activate loop
```

`map2loop`, `LoopStructural`, `loopstructuralvisualisation`, and `pyvista` must all be importable.

## Three input modes

| `--mode`   | What it loads | When to use |
|------------|---------------|-------------|
| `bundled`  | The Hamersley GeoJSONs + DTM packaged inside `map2loop._datasets.geodata_files.hamersley` | Demo / GMD reconstruction. Default. |
| `wfs`      | Loop's WFS server for the chosen Australian state (`--state`) | Any Australian region; bbox-driven. Requires network. |
| `local`    | User-supplied `geology.geojson`, `faults.geojson`, `structures.geojson`, `dtm.tif` in `--source-dir` | Bring-your-own-data. Requires `--bbox`, `--projection`, and an optional `--config-json`. |

## Command

```bash
python skills/map2loop-run/scripts/run_map2loop.py OUT_DIR \
    [--mode bundled|wfs|local]                          # default: bundled
    [--source-dir PATH]                                 # for --mode local
    [--state WA|SA|NSW|VIC|QLD|TAS|NT]                  # for --mode wfs
    [--bbox MINX,MINY,MAXX,MAXY,BASE,TOP]               # required for wfs/local
    [--projection EPSG:28350]                           # required for wfs/local
    [--config-json PATH]                                # field-mapping config for --mode local
    [--sampler-spacing 200.0]                           # SamplerSpacing distance (m) for geology + fault
    [--sorter alpha|age|hint|networkx|maximise|projection|take_best]
    [--build-3d]                                        # invoke LoopStructural to build implicit surfaces
    [--no-build-3d]                                     # opt out (default for --mode wfs/local; opt-in via --build-3d)
    [--export vtk,html]                                 # 3D export formats (default: vtk,html)
    [--loop-filename NAME]                              # default: output.loop3d
```

Default invocation (`python run_map2loop.py out/`) = bundled Hamersley dataset → `take_best` sorter → build 3D → VTK + interactive HTML.

## Examples

### Default — reconstruct the GMD 2021 case study

```bash
conda activate loop
python skills/map2loop-run/scripts/run_map2loop.py out/
```

### South Australia from Loop's WFS, no 3D build

```bash
python skills/map2loop-run/scripts/run_map2loop.py out-sa/ \
    --mode wfs --state SA \
    --bbox 250805,6405084,336682,6458336,-3200,1200 \
    --projection EPSG:28354 \
    --sorter alpha
```

### Bring-your-own-data

```bash
python skills/map2loop-run/scripts/run_map2loop.py out-myproject/ \
    --mode local --source-dir ~/maps/my-region/ \
    --bbox 500000,7400000,600000,7500000,-3000,1500 \
    --projection EPSG:28350 \
    --config-json ~/maps/my-region/config.json \
    --build-3d
```

The `--config-json` file must map your shapefile columns to map2loop's expected fields, e.g.:

```json
{
  "structure": {"dipdir_column": "azimuth2", "dip_column": "dip"},
  "geology":   {"unitname_column": "unitname", "alt_unitname_column": "code"},
  "fault":     {"structtype_column": "feature", "fault_text": "Fault"}
}
```

## Outputs (in `OUT_DIR`)

| File | Source | Stage |
|------|--------|-------|
| `output.loop3d` | `Project.save_into_projectfile()` | the headline artifact |
| `stratigraphy.csv` | `proj.stratigraphic_column.stratigraphicUnits` | Stage 5 |
| `contacts.csv` | `proj.map_data.sampled_contacts` | Stage 2 |
| `orientations.csv` | `proj.map_data.STRUCTURE` | Stage 3 |
| `topology_unit_unit.csv` | `proj.topology.unit_unit_relationships` | Stage 4 |
| `topology_unit_fault.csv` | `proj.topology.unit_fault_relationships` | Stage 4 |
| `topology_fault_fault.csv` | `proj.topology.fault_fault_relationships` | Stage 4 |
| `model.vtm` | LoopStructural stratigraphic + fault surfaces as a pyvista MultiBlock | Stage 6 (opt) |
| `model.html` | `Loop3DView` interactive scene | Stage 6 (opt) |
| `run_summary.json` | inputs + library versions + git rev + timing | provenance |

The intermediate CSVs/GML are dumped specifically so geologists can poke past the black box — see the GMD paper §4 for what each represents.

## Notes For Agents

- **map2loop's `Project.__init__` is strict.** When using local files (modes `bundled` and `local`), a `config_dictionary` or `config_filename` is required. The script supplies a default config dictionary for `bundled` that matches the column names in map2loop's bundled Hamersley GeoJSONs.
- **The WFS path requires network.** If `--mode wfs` times out, the script reports the timeout and exits non-zero rather than silently producing an empty file.
- **`--build-3d` is automatic for `--mode bundled`** because the bundled Hamersley demo is meant to be a complete reproduction of the GMD 2021 paper figures. Pass `--no-build-3d` to skip Stage 6 there.
- **Sorter shortcuts:** `take_best` runs `proj.run_all(take_best=True)` which sweeps all six sorters and picks the highest-scoring stratigraphic column. Costs more time but is the most defensible default.
- **Verbose level:** the script forces `VerboseLevel.TEXTONLY` so map2loop's progress lines land in stdout where users can see them. Pass `--quiet` to suppress.
- **Reproducibility:** `run_summary.json` records the bbox, projection, sorter, map2loop + LoopStructural versions, and the git rev of this skill repo. Treat it as the audit trail.
