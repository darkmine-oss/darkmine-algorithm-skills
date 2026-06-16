---
name: setup-loop
description: Bootstrap a freshly cloned darkmine-algorithm-skills checkout for the Loop3D toolchain — create a conda env named `loop`, install `map2loop` + `LoopStructural` + `loopstructuralvisualisation` + `pyvista` from the loop3d/conda-forge channels, and symlink every sibling skill into `~/.claude/skills/` or a project's `.claude/skills/` so Claude Code discovers them. Use when a user says "set up map2loop", "set up LoopStructural", "get Loop3D installed", or is staring at a fresh clone of darkmine-algorithm-skills wondering what to do next.
version: v0.1.0
---

# Setup Loop

One-shot bootstrap for `darkmine-algorithm-skills` targeted at the Loop3D toolchain (map2loop + LoopStructural). Does three things:

1. Verifies that `conda` (or `mamba`) is on PATH — fails loud if neither is available.
2. Creates a conda env (default name `loop`) and installs the Loop3D stack from `-c loop3d -c conda-forge`:
   - `map2loop` — map deconstruction → `.loop3d` files
   - `LoopStructural` — implicit 3D surface modelling from `.loop3d`
   - `loopstructuralvisualisation` — `Loop3DView` for VTK/HTML export
   - `pyvista` — VTK glue
3. Symlinks every sibling skill (including itself) into either:
   - a target project's `.claude/skills/` (per-project scope), or
   - the user-level `~/.claude/skills/` (every project sees them).

Idempotent — re-running upgrades pip + dependencies and leaves existing symlinks in place.

## Why conda (and not pip)?

map2loop pulls in GDAL via `geopandas` / `rasterio`. Installing GDAL via pip on macOS is a [well-known](https://hackernoon.com/hn-images/1*m4cnTYJWM7Rmpsju8dSHmQ.jpeg) bug magnet. Conda installs a pre-built GDAL and the rest of the stack on top of it cleanly. If you don't have conda, install [Miniforge](https://github.com/conda-forge/miniforge) first.

This is also why `darkmine-algorithm-skills` is a separate repo from `darkmine-data-skills`: that sibling repo uses a plain venv + pip because Baselode doesn't pull in native libs.

## Inputs

Just the path to a `darkmine-algorithm-skills` checkout, plus the scope for Claude Code discovery.

## Command

```bash
python skills/setup-loop/scripts/run_setup.py REPO_DIR \
    [--scope user|project|none] \
    [--project-dir PATH] \
    [--env-name NAME] \
    [--conda PATH] \
    [--map2loop-spec SPEC] \
    [--loopstructural-spec SPEC] \
    [--skip-env] \
    [--skip-link]
```

- `REPO_DIR` — path to the `darkmine-algorithm-skills` checkout itself.
- `--scope` — where to expose the skills to Claude Code. Default `user`.
  - `user` → `~/.claude/skills/<skill>/`
  - `project` → `<project-dir>/.claude/skills/<skill>/` (requires `--project-dir`)
  - `none` → only create the env, no symlinks
- `--project-dir` — required when `--scope project`.
- `--env-name` — conda env name (default `loop`). Pass a different name if you have multiple Loop3D installs.
- `--conda` — explicit path to `conda` or `mamba`. Default: prefer `mamba`, fall back to `conda`.
- `--map2loop-spec` — conda spec for map2loop (default `map2loop`). Override to pin a version, e.g. `map2loop=3.3.1`.
- `--loopstructural-spec` — conda spec for LoopStructural (default `LoopStructural`).
- `--skip-env` — only do the symlinks (env must already exist).
- `--skip-link` — only do the env.

## Outputs

- A conda env (default name `loop`) with the Loop3D stack installed.
- Symlinks named after each skill in the chosen scope directory.
- A short summary printed to stdout (env name, package list, symlinks created).

## Notes For Agents

- **This skill bootstraps the others.** Until it has run once, `~/.claude/skills/` may not contain the `map2loop-run` skill and Claude Code won't auto-discover it. Tell the user: clone the repo, then either run this skill's script directly or symlink just this one skill in by hand to get the discovery loop started.
- **Conda env activation.** Skills in this repo don't auto-activate the env. The user should `conda activate loop` (or pass `--python /path/to/loop-env/bin/python` to skill scripts when supported) before running other skills here.
- **Pinned versions.** Once a working version combination is verified, this skill should pin `map2loop` and `LoopStructural` to known-good versions to avoid breakage from API churn between releases.
- **Existing symlinks** are kept untouched. If a symlink points somewhere unexpected, the script warns but doesn't overwrite — let the user investigate.
- **Cross-reference:** the sibling repo `darkmine-data-skills` has its own `setup` skill — that one uses a plain venv because Baselode doesn't pull in native libs. The two repos can co-exist in `~/.claude/skills/`.
