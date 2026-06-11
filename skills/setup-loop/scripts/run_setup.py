#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Darkmine Pty Ltd
"""Bootstrap a fresh darkmine-algorithm-skills checkout for Loop3D.

Creates a conda env (default name ``loop``) with ``map2loop`` +
``LoopStructural`` + ``loopstructuralvisualisation`` + ``pyvista`` from the
loop3d and conda-forge channels, and (optionally) symlinks every skill in
this repo into ``~/.claude/skills/`` or a project's ``.claude/skills/`` so
Claude Code discovers them.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _find_conda(explicit):
    if explicit:
        if not shutil.which(explicit) and not Path(explicit).exists():
            raise SystemExit(f"--conda {explicit!r} not found")
        return explicit
    for name in ("mamba", "conda"):
        if shutil.which(name):
            return name
    raise SystemExit(
        "No conda or mamba found on PATH. Install Miniforge "
        "(https://github.com/conda-forge/miniforge) and re-run. "
        "GDAL via pip is a known bug magnet so we don't fall back to pip."
    )


def _run(cmd, **kwargs):
    print(f"  $ {' '.join(str(c) for c in cmd)}", flush=True)
    return subprocess.run(cmd, check=True, **kwargs)


def _env_exists(conda, env_name):
    out = subprocess.run(
        [conda, "env", "list", "--json"], capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        return False
    import json
    envs = json.loads(out.stdout).get("envs", [])
    return any(Path(e).name == env_name for e in envs)


def _create_env(conda, env_name, map2loop_spec, loopstructural_spec):
    extra_specs = [
        map2loop_spec,
        loopstructural_spec,
        "loopstructuralvisualisation",
        "pyvista",
    ]
    channels = ["-c", "loop3d", "-c", "conda-forge"]
    if _env_exists(conda, env_name):
        print(f"[env] reusing existing env {env_name}")
        _run([conda, "install", "-n", env_name, "-y", *channels, *extra_specs])
    else:
        print(f"[env] creating conda env {env_name}")
        _run([conda, "create", "-n", env_name, "-y", *channels, "python=3.12", *extra_specs])


def _resolve_link_root(scope, project_dir):
    if scope == "user":
        return Path.home() / ".claude" / "skills"
    if scope == "project":
        if project_dir is None:
            raise SystemExit("--scope project requires --project-dir")
        return project_dir.resolve() / ".claude" / "skills"
    if scope == "none":
        return None
    raise SystemExit(f"Unknown --scope {scope!r}")


def _symlink_skills(repo_dir, link_root):
    link_root.mkdir(parents=True, exist_ok=True)
    skills_dir = repo_dir / "skills"
    if not skills_dir.exists():
        raise SystemExit(f"Expected skills directory at {skills_dir}")
    created, kept, conflicts = [], [], []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        if not (skill_dir / "SKILL.md").exists():
            continue
        target = link_root / skill_dir.name
        if target.is_symlink():
            current = os.readlink(target)
            if Path(current) == skill_dir.resolve() or current == str(skill_dir.resolve()):
                kept.append(skill_dir.name)
            else:
                conflicts.append((skill_dir.name, current))
            continue
        if target.exists():
            conflicts.append((skill_dir.name, "existing non-symlink path"))
            continue
        target.symlink_to(skill_dir.resolve(), target_is_directory=True)
        created.append(skill_dir.name)
    return created, kept, conflicts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("repo_dir", type=Path,
                   help="Path to the darkmine-algorithm-skills checkout.")
    p.add_argument("--scope", choices=("user", "project", "none"), default="user")
    p.add_argument("--project-dir", type=Path, default=None)
    p.add_argument("--env-name", default="loop",
                   help="Conda env name (default: 'loop')")
    p.add_argument("--conda", default=None,
                   help="Path to conda/mamba (default: prefer mamba, fall back to conda)")
    p.add_argument("--map2loop-spec", default="map2loop",
                   help="Conda spec for map2loop (default: 'map2loop'). "
                        "Override to pin, e.g. 'map2loop=3.3.1'.")
    p.add_argument("--loopstructural-spec", default="LoopStructural",
                   help="Conda spec for LoopStructural (default: 'LoopStructural').")
    p.add_argument("--skip-env", action="store_true")
    p.add_argument("--skip-link", action="store_true")
    args = p.parse_args(argv)

    repo_dir = args.repo_dir.resolve()
    if not (repo_dir / "skills").is_dir():
        p.error(f"REPO_DIR doesn't look like darkmine-algorithm-skills: {repo_dir}")

    conda = None
    if not args.skip_env:
        conda = _find_conda(args.conda)
        _create_env(conda, args.env_name, args.map2loop_spec, args.loopstructural_spec)

    created, kept, conflicts = [], [], []
    link_root = None
    if not args.skip_link:
        link_root = _resolve_link_root(args.scope, args.project_dir)
        if link_root is not None:
            print(f"[link] symlinking skills into {link_root}")
            created, kept, conflicts = _symlink_skills(repo_dir, link_root)

    print()
    print("=== Setup complete ===")
    if not args.skip_env:
        print(f"  conda:         {conda}")
        print(f"  env name:      {args.env_name}")
        print(f"  activate:      conda activate {args.env_name}")
    if not args.skip_link and args.scope != "none":
        print(f"  scope:         {args.scope}")
        print(f"  link root:     {link_root}")
        if created:
            print(f"  created:       {', '.join(created)}")
        if kept:
            print(f"  already there: {', '.join(kept)}")
        if conflicts:
            print(f"  conflicts:     {len(conflicts)} — left untouched:")
            for name, where in conflicts:
                print(f"    - {name}: {where}")

    if not args.skip_link and args.scope != "none":
        print()
        print("Next: restart Claude Code (or start a new session). "
              "Ask it 'which skills are available?' to confirm discovery.")
        print(f"      Then `conda activate {args.env_name}` before running map2loop-run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
