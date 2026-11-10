"""EX-42 terrain manifest: per-family Kit measurement runner (queued, non-training).

Scope kept narrow on purpose:
  * Only families whose generator code exists in this repository are buildable:
    continuous (rough_go2_cfg), E (terrains/ex42.py), A (columns.FULL = continuous 7 + START sparse 6), C (terrains/jeplo_preset.py). Families B (AME-2) and D
    have no generator code here; this tool never creates one and reports them as missing.
  * Dimensions, paper references and physical flags are never filled in by this tool.
    They come from a declarations JSON written by whoever owns the kind. A kind with a
    null or missing field is reported as undeclared and is NOT measured.
  * The three aggregate measurements of the plan (peak_memory_gib, generation_seconds,
    ray_count_per_second) are not produced here, so assemble_manifest keeps the manifest
    partial with an `aggregate_measurements_missing` blocker.

Modes:
  plan      CPU only. Coverage of the 39-kind inventory and declaration gaps. Exit 0.
  template  CPU only. Write a declarations skeleton with null fields for buildable kinds.
  measure   Kit (device cuda:0 or cuda:1, the real device is recorded; lead starts it). Writes one family
            receipt per family, ready for scripts/ex42_manifest_build.py.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DECLARATION_FIELDS = (
    "preset_id", "original_dimensions_m", "training_dimensions_m",
    "evaluation_dimensions_m", "evaluation_axis_directions",
    "paper_reference", "physical_flag",
)
DEFAULT_TABLE = REPO / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
DEFAULT_SEED = 42


def buildable_kinds() -> dict[str, list[str]]:
    """Kind names whose generator code exists here (no Isaac import)."""
    from foothold_s2.terrains import columns
    from foothold_s2.terrains import jeplo_preset
    from foothold_s2.terrains.ex42 import PAPER_EXT_SPECS

    return {
        "continuous": list(columns.CONTINUOUS),
        "E": [spec.kind for spec in PAPER_EXT_SPECS],
        "A": list(columns.FULL),
        "C": list(jeplo_preset.KINDS),
    }


def coverage(expected_counts: dict[str, int], buildable: dict[str, list[str]],
             declarations: dict[str, Any]) -> dict[str, Any]:
    """Per family: expected count, buildable kinds, declared-complete kinds, gaps."""
    report: dict[str, Any] = {}
    for family, expected in expected_counts.items():
        kinds = buildable.get(family, [])
        declared: list[str] = []
        gaps: dict[str, list[str]] = {}
        for kind in kinds:
            missing = declaration_gaps((declarations.get(family) or {}).get(kind))
            if missing:
                gaps[kind] = missing
            else:
                declared.append(kind)
        report[family] = {
            "expected_kinds": expected,
            "generator_in_repo": len(kinds),
            "generator_missing": max(0, expected - len(kinds)),
            "buildable_kinds": kinds,
            "declared_complete": declared,
            "undeclared_fields": gaps,
        }
    return report


def declaration_gaps(row: Any) -> list[str]:
    """Fields that are absent or null in one kind declaration."""
    if not isinstance(row, dict):
        return list(DECLARATION_FIELDS)
    return [name for name in DECLARATION_FIELDS if row.get(name) is None]


def load_declarations(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("declarations must be a JSON object {family: {kind: {...}}}")
    return value


def declarations_template(buildable: dict[str, list[str]]) -> dict[str, Any]:
    return {family: {kind: {name: None for name in DECLARATION_FIELDS} for kind in kinds}
            for family, kinds in buildable.items()}


def _generator_for(family: str, kind: str, seed: int = DEFAULT_SEED):
    """Return (TerrainGeneratorCfg, subterrain cfg) for one buildable kind (Kit python)."""
    if family == "C":
        from foothold_s2.terrains.jeplo_preset import measurement_generator

        return measurement_generator(kind, seed=seed)
    from foothold_s2.terrains.rough_go2_cfg import build_generator, continuous_subterrains

    if family == "continuous":
        subs = continuous_subterrains()
    elif family == "E":
        from foothold_s2.terrains.ex42 import PAPER_EXT_SPECS, paper_ext_subterrains

        # measure_kind_with_kit forces proportion 1.0 for the single tile.
        subs = paper_ext_subterrains({spec.kind: 1.0 for spec in PAPER_EXT_SPECS})
    elif family == "A":
        from foothold_s2.terrains import columns
        from foothold_s2.terrains.sparse_terrains import sparse_subterrains

        # A = columns.FULL: the continuous 7 plus the START sparse 6 (50 columns)
        subs = {**continuous_subterrains(), **sparse_subterrains(dict(columns.SPARSE))}
    else:
        raise ValueError(f"no generator code for terrain family {family!r} in this repository")
    if kind not in subs:
        raise ValueError(f"no generator for {family}/{kind}")
    return build_generator(subs, 1, seed), subs[kind]


def source_head() -> str:
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    if len(head) != 40:
        raise RuntimeError("cannot read source head")
    return head


def measure_family(family: str, declarations: dict[str, Any], *, seed: int,
                   device: str, receipt_id: str) -> dict[str, Any]:
    """Kit side: measure every fully declared buildable kind of one family."""
    from foothold_s2.curriculum.ex42_manifest import (
        build_family_receipt, measure_kind_with_kit)

    head = source_head()
    rows = []
    for kind in buildable_kinds().get(family, []):
        declaration = (declarations.get(family) or {}).get(kind)
        if declaration_gaps(declaration):
            continue
        generator_cfg, subterrain_cfg = _generator_for(family, kind, seed)
        row, _elapsed = measure_kind_with_kit(
            family=family, kind=kind, preset_id=declaration["preset_id"],
            generator_cfg=generator_cfg, subterrain_cfg=subterrain_cfg,
            original_dimensions_m=declaration["original_dimensions_m"],
            training_dimensions_m=declaration["training_dimensions_m"],
            evaluation_dimensions_m=declaration["evaluation_dimensions_m"],
            evaluation_axis_directions=declaration["evaluation_axis_directions"],
            paper_reference=declaration["paper_reference"],
            physical_flag=declaration["physical_flag"],
            source_head=head, seed=seed, device=device)
        rows.append(row)
    if not rows:
        raise ValueError(f"no fully declared buildable kind for family {family}")
    return build_family_receipt(family, rows, receipt_id=receipt_id,
                                source_head=head, seed=seed, device=device)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def build_parser(app_launcher: Any | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("plan", "template", "measure"))
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--declarations", type=Path)
    parser.add_argument("--out", type=Path, help="template: file; measure: output folder")
    parser.add_argument("--family", action="append", help="measure: family (repeatable)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    if app_launcher is None:
        parser.add_argument("--device", default="cuda:1")
        parser.add_argument("--headless", action="store_true", default=True)
    else:
        app_launcher.add_app_launcher_args(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args, _ = build_parser().parse_known_args(argv)
    sys.path.insert(0, str(REPO))
    if args.mode in ("plan", "template"):
        buildable = buildable_kinds()
        if args.mode == "template":
            if args.out is None:
                raise SystemExit("template needs --out")
            _write_json(args.out, declarations_template(buildable))
            print(json.dumps({"state": "template_written", "out": str(args.out)}))
            return 0
        from foothold_s2.curriculum.ex42_prep import EX42Plan

        plan = EX42Plan.load(args.table)
        expected = plan.document["terrain_manifest_contract"]["kind_count_by_family"]
        report = coverage(expected, buildable, load_declarations(args.declarations))
        print(json.dumps({"state": "plan", "coverage": report}, ensure_ascii=False,
                         indent=2, sort_keys=True))
        return 0
    # measure: Kit
    from foothold_s2.curriculum.ex42_manifest import MEASURE_DEVICES

    if args.device not in MEASURE_DEVICES:
        raise SystemExit(f"EX-42 terrain measurement device must be one of {MEASURE_DEVICES}")
    if not args.family or args.out is None or args.declarations is None:
        raise SystemExit("measure needs --family, --out and --declarations")
    from isaaclab.app import AppLauncher

    args, _ = build_parser(AppLauncher).parse_known_args(argv)
    app = AppLauncher(args).app
    declarations = load_declarations(args.declarations)
    exit_code = 0
    try:
        for family in args.family:
            receipt = measure_family(family, declarations, seed=args.seed, device=args.device,
                                     receipt_id=f"ex42-kit-measure-{family}-seed{args.seed}")
            _write_json(args.out / f"family_{family}.json", receipt)
            print(json.dumps({"state": "family_receipt", "family": family,
                              "kinds": [row["kind"] for row in receipt["kinds"]]}), flush=True)
    except Exception as exc:  # fail closed, no receipt for the family that failed
        print(json.dumps({"state": "failed", "error_type": type(exc).__name__,
                          "error": str(exc)}), flush=True)
        exit_code = 1
    app.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
