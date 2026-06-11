#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Darkmine Pty Ltd
"""Run map2loop end-to-end and optionally build a 3D model via LoopStructural.

Three input modes:

* ``bundled`` — use the Hamersley geodata packaged inside map2loop
  (reconstructs the case study from Jessell et al. 2021, GMD 14, 5063).
* ``wfs`` — pull data from Loop's Web Feature Service for an Australian state.
* ``local`` — point at a directory of user-supplied GeoJSONs + DTM.

Always dumps a ``.loop3d`` file plus inspectable intermediate CSVs and a
topology GML. With ``--build-3d`` (default for ``--mode bundled``) it also
builds implicit surfaces via LoopStructural and exports VTK + interactive HTML.
"""

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import time
from typing import Optional


# ---------- bundled-Hamersley defaults (matches map2loop's plot_hamersley.py) ----------

HAMERSLEY_BBOX = {
    "minx": 515687.31005864,
    "miny": 7493446.76593407,
    "maxx": 562666.860106543,
    "maxy": 7521273.57407786,
    "base": -3200.0,
    "top": 3000.0,
}
HAMERSLEY_PROJECTION = "EPSG:28350"
HAMERSLEY_CONFIG = {
    "structure": {"dipdir_column": "azimuth2", "dip_column": "dip"},
    "geology": {"unitname_column": "unitname", "alt_unitname_column": "code"},
    "fault": {"structtype_column": "feature", "fault_text": "Fault"},
}

# ---------- sorter registry ----------

def _build_sorter(name: str, proj):
    """Return a map2loop Sorter instance, or None for ``take_best``.

    Some sorters (SorterAlpha, SorterMaximiseContacts, SorterObservationProjections)
    require data that doesn't exist until after Project.run_all begins. For
    ``take_best`` we skip set_sorter entirely — ``run_all(take_best=True)``
    constructs its own sorter list internally. For the others we instantiate
    with no args and let map2loop's deferred-attribute mechanism populate the
    rest once contacts/relationships are ready.
    """
    if name == "take_best":
        return None
    from map2loop.sorter import (
        SorterAgeBased,
        SorterUseHint,
        SorterUseNetworkX,
        SorterMaximiseContacts,
        SorterObservationProjections,
    )
    no_arg_mapping = {
        "age":        SorterAgeBased,
        "hint":       SorterUseHint,
        "networkx":   SorterUseNetworkX,
        "maximise":   SorterMaximiseContacts,
        "projection": SorterObservationProjections,
    }
    if name == "alpha":
        # SorterAlpha needs contacts at construct time, which don't exist until
        # run_all extracts them. Pre-run the contact extractor to satisfy it.
        from map2loop.sorter import SorterAlpha
        from map2loop.contact_extractor import ContactExtractor
        from map2loop.m2l_enums import Datatype
        proj.contact_extractor = ContactExtractor(
            proj.map_data.get_map_data(Datatype.GEOLOGY),
            proj.map_data.get_map_data(Datatype.FAULT),
        )
        proj.contact_extractor.extract_all_contacts()
        return SorterAlpha(contacts=proj.contact_extractor.contacts)
    if name in no_arg_mapping:
        return no_arg_mapping[name]()
    raise SystemExit(
        f"Unknown sorter {name!r}. Valid: alpha, age, hint, networkx, "
        "maximise, projection, take_best."
    )


# ---------- I/O helpers ----------

def _parse_bbox(arg: Optional[str]):
    if arg is None:
        return None
    parts = [float(x) for x in arg.split(",")]
    if len(parts) != 6:
        raise SystemExit(
            "--bbox must be MINX,MINY,MAXX,MAXY,BASE,TOP (6 floats)."
        )
    keys = ("minx", "miny", "maxx", "maxy", "base", "top")
    return dict(zip(keys, parts))


def _hamersley_data_dir() -> pathlib.Path:
    import map2loop
    root = pathlib.Path(map2loop.__file__).parent / "_datasets" / "geodata_files" / "hamersley"
    if not root.exists():
        raise SystemExit(
            f"map2loop's bundled Hamersley data not found at {root}. "
            "Reinstall map2loop or use --mode wfs / --mode local."
        )
    return root


def _git_rev(start: pathlib.Path) -> Optional[str]:
    if not shutil.which("git"):
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _safe_versions():
    import map2loop
    versions = {"map2loop": getattr(map2loop, "__version__", "unknown")}
    try:
        import LoopStructural
        versions["LoopStructural"] = getattr(LoopStructural, "__version__", "unknown")
    except Exception:
        versions["LoopStructural"] = None
    try:
        import LoopProjectFile
        versions["LoopProjectFile"] = getattr(LoopProjectFile, "__version__", "unknown")
    except Exception:
        versions["LoopProjectFile"] = None
    return versions


# ---------- Stage 1-5: run map2loop ----------

def _make_project(mode, source_dir, state, bbox, projection, config_path, loop_filename, verbose_level):
    from map2loop.project import Project
    common = dict(
        working_projection=projection,
        bounding_box=bbox,
        verbose_level=verbose_level,
        loop_project_filename=str(loop_filename),
        overwrite_loopprojectfile=True,
    )
    if mode == "bundled":
        data = _hamersley_data_dir()
        return Project(
            geology_filename=str(data / "geology.geojson"),
            fault_filename=str(data / "faults.geojson"),
            structure_filename=str(data / "structures.geojson"),
            dtm_filename=str(data / "dtm_rp.tif"),
            config_dictionary=HAMERSLEY_CONFIG,
            **common,
        )
    if mode == "wfs":
        return Project(use_australian_state_data=state, **common)
    if mode == "local":
        if source_dir is None:
            raise SystemExit("--mode local requires --source-dir")
        sd = pathlib.Path(source_dir).resolve()
        if not sd.is_dir():
            raise SystemExit(f"--source-dir not found: {sd}")
        def first(*names):
            for n in names:
                p = sd / n
                if p.exists():
                    return str(p)
            return ""
        config_kwargs = {}
        if config_path:
            config_kwargs["config_filename"] = str(pathlib.Path(config_path).resolve())
        return Project(
            geology_filename=first("geology.geojson", "geology.shp"),
            fault_filename=first("faults.geojson", "faults.shp"),
            structure_filename=first("structures.geojson", "structure.geojson", "structures.shp"),
            dtm_filename=first("dtm.tif", "dtm_rp.tif"),
            **config_kwargs,
            **common,
        )
    raise SystemExit(f"Unknown mode {mode!r}")


def _run_pipeline(proj, sorter_name, spacing):
    from map2loop.m2l_enums import Datatype
    from map2loop.sampler import SamplerSpacing
    proj.set_sampler(Datatype.GEOLOGY, SamplerSpacing(spacing))
    proj.set_sampler(Datatype.FAULT, SamplerSpacing(spacing))
    take_best = sorter_name == "take_best"
    sorter = _build_sorter(sorter_name, proj)
    if sorter is not None:
        proj.set_sorter(sorter)
    t0 = time.monotonic()
    proj.run_all(take_best=take_best)
    return time.monotonic() - t0


# ---------- intermediate-artifact dumps ----------

def _to_csv(df, out_path: pathlib.Path):
    """Best-effort CSV dump; tolerate None / empty / non-DataFrame."""
    if df is None:
        return False
    try:
        if hasattr(df, "to_csv"):
            df.to_csv(out_path, index=False)
            return True
    except Exception as exc:
        print(f"  ! could not write {out_path.name}: {exc}")
    return False


def _dump_intermediates(proj, out_dir: pathlib.Path):
    dumps = {}
    sc = getattr(proj, "stratigraphic_column", None)
    if sc is not None and hasattr(sc, "stratigraphicUnits"):
        dumps["stratigraphy.csv"] = _to_csv(sc.stratigraphicUnits, out_dir / "stratigraphy.csv")
    md = getattr(proj, "map_data", None)
    if md is not None:
        dumps["contacts.csv"] = _to_csv(getattr(md, "sampled_contacts", None), out_dir / "contacts.csv")
        # Orientations: map_data.STRUCTURE is the raw GeoDataFrame of bedding
        # measurements (X, Y, dip, dipdir, ...). map2loop doesn't "sample"
        # structures because they're already point data.
        dumps["orientations.csv"] = _to_csv(getattr(md, "STRUCTURE", None), out_dir / "orientations.csv")
    topo = getattr(proj, "topology", None)
    if topo is not None:
        # map2loop stores topology as three pandas DataFrames (not a graph).
        # Dump each as CSV — they're directly visualisable in Excel/QGIS and
        # can be loaded into NetworkX or yEd by the user if a graph is wanted.
        for attr, fname in (
            ("unit_unit_relationships",   "topology_unit_unit.csv"),
            ("unit_fault_relationships",  "topology_unit_fault.csv"),
            ("fault_fault_relationships", "topology_fault_fault.csv"),
        ):
            dumps[fname] = _to_csv(getattr(topo, attr, None), out_dir / fname)
    return dumps


# ---------- Stage 6: LoopStructural ----------

def _build_3d(loop_filename: pathlib.Path, out_dir: pathlib.Path, export_formats):
    """Load the .loop3d, build implicit surfaces, dump VTK + HTML."""
    try:
        from LoopProjectFile import ProjectFile
        from LoopStructural.modelling.input.project_file import LoopProjectfileProcessor
        from LoopStructural import GeologicalModel
    except ImportError as exc:
        print(f"  ! LoopStructural import failed ({exc}); skipping --build-3d")
        return {}
    pf = ProjectFile(str(loop_filename))
    processor = LoopProjectfileProcessor(pf)
    model = GeologicalModel.from_processor(processor)
    model.update()
    exported = {}
    if "vtk" in export_formats:
        try:
            import pyvista as pv  # noqa: F401
            grid = model.bounding_box.vtk()
            scalar_field = model.evaluate_model(grid.points, scale=False)
            grid["stratigraphy"] = scalar_field
            grid.save(str(out_dir / "model.vtk"))
            exported["model.vtk"] = True
        except Exception as exc:
            print(f"  ! VTK export failed: {exc}")
            exported["model.vtk"] = False
    if "html" in export_formats:
        try:
            from loopstructuralvisualisation import Loop3DView
            view = Loop3DView(model, off_screen=True)
            # cmap is passed explicitly to bypass a known integration drift
            # between LoopStructural's StratigraphicColumn object and
            # loopstructuralvisualisation._build_stratigraphic_cmap, which
            # assumes the column is a dict-of-dicts.
            view.plot_model_surfaces(cmap="tab20")
            view.export_html(str(out_dir / "model.html"))
            exported["model.html"] = True
        except Exception as exc:
            print(f"  ! HTML export failed: {exc}")
            exported["model.html"] = False
    return exported


# ---------- main ----------

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("out_dir", type=pathlib.Path,
                   help="Output directory (created if absent).")
    p.add_argument("--mode", choices=("bundled", "wfs", "local"), default="bundled")
    p.add_argument("--source-dir", type=pathlib.Path, default=None,
                   help="For --mode local: directory of geology/faults/structures GeoJSON + DTM.")
    p.add_argument("--state", default="WA",
                   help="For --mode wfs: Australian state code "
                        "(WA, SA, NSW, VIC, QLD, TAS, NT).")
    p.add_argument("--bbox", default=None,
                   help="MINX,MINY,MAXX,MAXY,BASE,TOP. Required for wfs/local; "
                        "defaults to bundled-Hamersley bbox for --mode bundled.")
    p.add_argument("--projection", default=None,
                   help="Working projection (e.g. EPSG:28350). "
                        "Required for wfs/local; defaults to EPSG:28350 for bundled.")
    p.add_argument("--config-json", type=pathlib.Path, default=None,
                   help="For --mode local: JSON config mapping shapefile columns "
                        "to map2loop field names.")
    p.add_argument("--sampler-spacing", type=float, default=200.0,
                   help="SamplerSpacing distance in metres (default: 200.0).")
    p.add_argument("--sorter", default="take_best",
                   choices=("alpha", "age", "hint", "networkx",
                            "maximise", "projection", "take_best"),
                   help="Stratigraphic sorter (default: take_best — sweeps all six "
                        "and picks the highest-scoring).")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--build-3d", action="store_true", default=None,
                   help="Build 3D surfaces via LoopStructural after map2loop runs.")
    g.add_argument("--no-build-3d", action="store_true",
                   help="Skip the LoopStructural step (default for wfs/local).")
    p.add_argument("--export", default="vtk,html",
                   help="Comma-separated 3D export formats (default: vtk,html).")
    p.add_argument("--loop-filename", default="output.loop3d",
                   help="Filename for the .loop3d output (default: output.loop3d).")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress map2loop progress lines.")
    args = p.parse_args(argv)

    # Resolve bbox/projection defaults for bundled mode.
    if args.mode == "bundled":
        bbox = _parse_bbox(args.bbox) if args.bbox else dict(HAMERSLEY_BBOX)
        projection = args.projection or HAMERSLEY_PROJECTION
    else:
        bbox = _parse_bbox(args.bbox)
        projection = args.projection
        if bbox is None or projection is None:
            p.error(f"--mode {args.mode} requires --bbox and --projection.")

    # Build-3d default: on for bundled, off otherwise (unless --build-3d).
    if args.no_build_3d:
        build_3d = False
    elif args.build_3d is None:
        build_3d = (args.mode == "bundled")
    else:
        build_3d = bool(args.build_3d)

    export_formats = [s.strip() for s in args.export.split(",") if s.strip()]

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    loop_filename = out_dir / args.loop_filename

    from map2loop.m2l_enums import VerboseLevel
    verbose_level = VerboseLevel.NONE if args.quiet else VerboseLevel.TEXTONLY

    started = time.time()
    print(f"[map2loop-run] mode={args.mode} sorter={args.sorter} build_3d={build_3d}")
    print(f"               out={out_dir}")
    print(f"               bbox={bbox}")
    print(f"               projection={projection}")

    print("[stage 1-5] running map2loop pipeline …")
    proj = _make_project(
        mode=args.mode,
        source_dir=args.source_dir,
        state=args.state,
        bbox=bbox,
        projection=projection,
        config_path=args.config_json,
        loop_filename=loop_filename,
        verbose_level=verbose_level,
    )
    map2loop_elapsed = _run_pipeline(proj, args.sorter, args.sampler_spacing)
    print(f"               done in {map2loop_elapsed:.1f}s → {loop_filename.name}")

    print("[intermediates] dumping CSVs + topology GML …")
    dumps = _dump_intermediates(proj, out_dir)
    for name, ok in dumps.items():
        print(f"               {name}: {'wrote' if ok else 'skipped'}")

    exports = {}
    build_elapsed = None
    if build_3d:
        print(f"[stage 6] building 3D model via LoopStructural ({','.join(export_formats)}) …")
        t0 = time.monotonic()
        exports = _build_3d(loop_filename, out_dir, export_formats)
        build_elapsed = time.monotonic() - t0
        for name, ok in exports.items():
            print(f"               {name}: {'wrote' if ok else 'failed'}")

    summary = {
        "started_at": started,
        "mode": args.mode,
        "state": args.state if args.mode == "wfs" else None,
        "source_dir": str(args.source_dir.resolve()) if args.source_dir else None,
        "bbox": bbox,
        "projection": projection,
        "sampler_spacing_m": args.sampler_spacing,
        "sorter": args.sorter,
        "build_3d": build_3d,
        "export_formats": export_formats if build_3d else [],
        "loop_filename": str(loop_filename),
        "intermediates": dumps,
        "exports": exports,
        "map2loop_elapsed_s": map2loop_elapsed,
        "stage6_elapsed_s": build_elapsed,
        "versions": _safe_versions(),
        "skill_git_rev": _git_rev(pathlib.Path(__file__).resolve().parent),
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print()
    print("=== map2loop-run complete ===")
    print(f"  loop project file: {loop_filename}")
    print(f"  summary:           {out_dir / 'run_summary.json'}")
    if build_3d and exports:
        for name in exports:
            print(f"  3D export:         {out_dir / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
