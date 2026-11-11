"""CPU-only EX-42 render request planner for the pinned combined mesh.

This freezes which kind/level/map/selection slots are required. It does not
claim that the legacy record_c_layer renderer can consume an EX-42 checkpoint
or mesh; capture remains blocked until that Kit backend is integrated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh


SCHEMA = "foothold-ex42-render-plan/1"
MAP_MODES = ("eval_gt", "eval_pred")
SELECTION_ROLES = ("success", "failure", "overview")
MAX_LEVEL = 9


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mesh_kinds(folder: Path) -> tuple[dict, dict, str]:
    folder = Path(folder).resolve(strict=True)
    mesh_manifest_path = folder / "mesh_manifest.json"
    terrain_manifest_path = folder / "terrain_manifest.json"
    mesh_path = folder / "terrain_mesh.npz"
    mesh_manifest = json.loads(mesh_manifest_path.read_text(encoding="utf-8"))
    terrain_manifest = json.loads(terrain_manifest_path.read_text(encoding="utf-8"))
    if (mesh_manifest.get("format") != "foothold-ex42-combined-mesh/1"
            or mesh_manifest.get("families_present") != ["A", "B", "C", "D", "E"]
            or mesh_manifest.get("families_missing") != []
            or mesh_manifest.get("seed") != 42
            or mesh_manifest.get("training_started") is not False):
        raise ValueError("render planning requires the pinned seed-42 combined mesh, before training")
    if terrain_manifest.get("format") != "foothold-ex42-terrain-manifest/1":
        raise ValueError("combined terrain manifest format differs")
    if (terrain_manifest.get("status") not in ("ready", "passed", "measured")
            or terrain_manifest.get("blockers")):
        raise ValueError("terrain manifest is not ready for render planning")
    mesh_file_sha = _sha256(mesh_path)
    if (mesh_manifest.get("mesh_file_sha256") is not None
            and mesh_manifest.get("mesh_file_sha256") != mesh_file_sha):
        raise ValueError("combined mesh file SHA differs from mesh manifest")
    loaded = load_combined_mesh(mesh_path, mesh_manifest.get("mesh_sha256"))
    if list(loaded["origins"].shape) != mesh_manifest.get("origins_shape"):
        raise ValueError("combined mesh origin shape differs from mesh manifest")
    columns_by_family = mesh_manifest.get("columns_by_family")
    if not isinstance(columns_by_family, dict):
        raise ValueError("mesh manifest has no family column counts")
    expected_families = [family for family in ("A", "B", "C", "D", "E")
                         for _ in range(columns_by_family.get(family, 0))]
    if loaded["column_family"] != expected_families:
        raise ValueError("combined mesh family columns differ from mesh manifest")

    kinds: dict[str, dict] = {}
    for row in terrain_manifest.get("kinds", []):
        family, geometry_family, kind = row.get("family"), row.get("geometry_family"), row.get("kind")
        columns = (row.get("geometry_selection") or {}).get("columns")
        key = f"{geometry_family}/{kind}"
        if (family not in (geometry_family, "continuous") or geometry_family not in ("A", "B", "C", "D", "E")
                or not isinstance(kind, str) or not kind or not isinstance(columns, list) or not columns):
            raise ValueError("terrain kind declaration is incomplete")
        normalized = sorted(set(columns))
        if (len(normalized) != len(columns) or any(type(col) is not int or col < 0
                or col >= len(loaded["column_family"]) for col in normalized)
                or any(loaded["column_family"][col] != geometry_family for col in normalized)):
            raise ValueError(f"terrain kind columns do not match combined mesh family: {key}")
        if key in kinds:
            if kinds[key]["columns"] != normalized:
                raise ValueError(f"duplicate terrain declarations disagree on columns: {key}")
            kinds[key]["trained_declaration"] |= family == "continuous"
        else:
            kinds[key] = {"terrain_key": key, "family": geometry_family,
                          "kind": kind, "columns": normalized,
                          "trained_declaration": family == "continuous"}
    if not kinds:
        raise ValueError("terrain manifest has no kinds")
    return mesh_manifest, kinds, mesh_file_sha


def build_render_plan(mesh_dir: str | Path, checkpoint: str | Path, *,
                      trained_kinds: Iterable[str], current_cap: int) -> dict:
    """Freeze EX-42 capture slots without inventing evaluation outcomes.

    ``trained_kinds`` must come from the checkpoint's approved exposure record.
    ``current_cap`` is the cap read from that same checkpoint/runtime receipt.
    Each requested kind gets the decision's two map modes and one slot for each
    selected outcome/view. Env selection is intentionally deferred to evaluation
    receipts; no video is marked capture-ready here.
    """
    if type(current_cap) is not int or not 0 <= current_cap <= MAX_LEVEL:
        raise ValueError("current cap must be an integer from 0 through 9")
    checkpoint_path = Path(checkpoint).resolve(strict=True)
    mesh_manifest, kinds, mesh_file_sha = _mesh_kinds(Path(mesh_dir))
    trained = set(trained_kinds)
    unknown = trained - set(kinds)
    if unknown:
        raise ValueError("trained kind absent from terrain manifest: " + ", ".join(sorted(unknown)))
    if not trained:
        raise ValueError("trained kinds must be supplied from the approved exposure record")
    checkpoint_sha = _sha256(checkpoint_path)
    mesh_sha = mesh_manifest["mesh_sha256"]
    requests = []
    for key, kind in sorted(kinds.items()):
        levels = sorted({current_cap, MAX_LEVEL}) if key in trained else [0]
        for mode in MAP_MODES:
            for level in levels:
                for role in SELECTION_ROLES:
                    identity = {"mesh_sha256": mesh_sha, "checkpoint_sha256": checkpoint_sha,
                                "terrain_key": key, "terrain_level": level,
                                "map_mode": mode, "selection_role": role}
                    request_id = hashlib.sha256(json.dumps(
                        identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                    requests.append({"request_id": request_id, **identity,
                        "columns": kind["columns"], "selected_env_id": None,
                        "selection_source": "matching evaluation receipt required",
                        "capture_ready": False})
    return {"schema": SCHEMA, "state": "selection_pending",
            "mesh_dir": str(Path(mesh_dir).resolve(strict=True)),
            "mesh_sha256": mesh_sha, "mesh_file_sha256": mesh_file_sha,
            "checkpoint": str(checkpoint_path), "checkpoint_sha256": checkpoint_sha,
            "trained_kinds_source": "explicit approved exposure/runtime receipt required",
            "current_cap_source": "explicit checkpoint/runtime receipt required",
            "current_cap": current_cap, "map_modes": list(MAP_MODES),
            "selection_roles": list(SELECTION_ROLES),
            "renderer_backend": {"supported": False,
                "reason": "record_c_layer has no EX-42 profile or combined-mesh mount path"},
            "requests": requests}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CPU-only EX-42 combined-mesh render plan")
    parser.add_argument("--mesh-dir", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--trained-kind", action="append", required=True,
                        help="family/kind from the approved checkpoint exposure receipt")
    parser.add_argument("--current-cap", required=True, type=int)
    args = parser.parse_args(argv)
    result = build_render_plan(args.mesh_dir, args.checkpoint,
                               trained_kinds=args.trained_kind,
                               current_cap=args.current_cap)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
