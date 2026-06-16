# darkmine-algorithm-skills

Reusable skills for AI agents (and humans on the CLI) that **wrap third-party scientific algorithms** in the geosciences. The goal: make powerful algorithms (3D geomodelling, geostats, inversion) accessible to people who shouldn't have to wrangle Python args, env setup, or data parsing.

Sibling repo to [`darkmine-data-skills`](https://github.com/darkmine-oss/darkmine-data-skills). The two repos split along these lines:

| Repo | Theme | Install model |
|---|---|---|
| [`darkmine-data-skills`](https://github.com/darkmine-oss/darkmine-data-skills) | Manipulating data the user already has (Baselode drillhole, generic data prep) | venv + pip |
| **this repo** (`darkmine-algorithm-skills`) | Running third-party algorithms | conda (most algos need GDAL or other native libs) |

Most algorithm skills here will depend on data-prep skills from `darkmine-data-skills` — install both side-by-side.

Each skill is a self-contained subdirectory under `skills/` with:

- `SKILL.md` — frontmatter (`name`, `description`, `version`) + when to use + invocation
- `scripts/` — the Python entry point(s)
- `agents/` (optional) — additional agent prompts

## Setup

Algorithm wrappers often need native libraries (GDAL, VTK, etc), so this repo uses conda rather than plain venv. Each algorithm family has its own `setup-*` skill — there isn't one global setup, because the toolchains rarely co-exist cleanly in a single env.

### Loop3D (map2loop + LoopStructural)

The [`setup-loop`](skills/setup-loop/SKILL.md) skill creates a conda env named `loop` and installs `map2loop` + `LoopStructural` + `loopstructuralvisualisation` + `pyvista` from the `loop3d` and `conda-forge` channels.

```bash
git clone git@github.com:darkmine-oss/darkmine-algorithm-skills.git
cd darkmine-algorithm-skills
python3 skills/setup-loop/scripts/run_setup.py "$PWD" --scope user
```

`--scope user` symlinks every skill into `~/.claude/skills/`; `--scope project --project-dir /path/to/project` scopes them to a single project.

Requires `conda` or `mamba` on PATH. If neither is available the setup will fail loud — there's no pip fallback because GDAL via pip is a known bug magnet on macOS.

## Available skills

### Bootstrap

- [`setup-loop`](skills/setup-loop/SKILL.md) — Create a conda env named `loop`, install `map2loop` + `LoopStructural` + `loopstructuralvisualisation` + `pyvista` from the `loop3d` and `conda-forge` channels, and symlink every sibling skill into `~/.claude/skills/` (or a project's `.claude/skills/`).

### Loop3D (3D geomodelling from 2D maps)

- [`map2loop-run`](skills/map2loop-run/SKILL.md) — Wrap [map2loop](https://github.com/Loop3D/map2loop)'s `Project.run_all` pipeline as a single CLI. Three input modes (`bundled` Hamersley demo / `wfs` Loop server / `local` GeoJSONs), all six sorters, optional Stage-6 build via LoopStructural with VTK + interactive HTML export. Dumps intermediate CSVs/GMLs so geologists can poke past the black box.

## Reconstructing the GMD 2021 paper

The default invocation of `map2loop-run` reconstructs the case study from [Jessell et al. 2021 (GMD)](https://gmd.copernicus.org/articles/14/5063/2021/) — the Rocklea Dome / Hamersley region in Western Australia. map2loop ships the geodata (`map2loop/_datasets/geodata_files/hamersley/`), so no external data download is needed for the demo.

```bash
# After running setup-loop, from any directory:
conda activate loop
python <repo>/skills/map2loop-run/scripts/run_map2loop.py out/
```

Outputs in `out/`:
- `output.loop3d` — the headline `.loop3d` artifact
- `stratigraphy.csv`, `contacts.csv`, `orientations.csv`, `topology.gml` — intermediates
- `model.vtk`, `model.html` — when `--build-3d` is set (default for the demo)
- `run_summary.json` — provenance (bbox, projection, sorter, library versions, git rev)

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
