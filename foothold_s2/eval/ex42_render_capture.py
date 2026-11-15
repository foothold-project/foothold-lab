"""One-cell EX-42 capture selection and fixed assignment helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import argparse
import subprocess
import sys

import numpy as np


PROFILE = "EX42_RENDER"
SUCCESS_FWD_M = 3.0
ENV_COUNT = 64


def ex42_render_ref(spec: dict) -> bool:
    return spec.get("ex42_render_reference") is True


def audit_capture_video(path: str | Path, *, expected: int, width: int, height: int,
                        screen_evidence: list[dict], robot_instance_evidence: list[dict]) -> dict:
    """Decode every raw capture frame and require scene, projection and robot evidence."""
    from foothold_s2.eval.c_layer_frame_audit import audit_video

    result = audit_video(Path(path), expected=expected, width=width, height=height,
                         screen_evidence=screen_evidence,
                         robot_instance_evidence=robot_instance_evidence)
    return result


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def capture_spec_from_evaluation(plan: dict, request_id: str, evaluation_json: str | Path, *,
                                 command_name: str, role: str, source_root: str | Path,
                                 source_head: str, recorder_sha256: str,
                                 overview_env_id: int | None = None) -> dict:
    """Bind one plan slot to a matching EX-42 map-mode result and env array.

    Success/failure use the existing record_c_layer forward selection rule.
    Overview is deliberately an explicit env selection because the team rule
    does not define an automatic overview rank.
    """
    from foothold_s2.eval.ex42_render_plan import SCHEMA

    if plan.get("schema") != SCHEMA:
        raise ValueError("EX-42 render plan schema differs")
    request = next((row for row in plan.get("requests", [])
                    if row.get("request_id") == request_id), None)
    if request is None:
        raise ValueError("request id absent from EX-42 render plan")
    if request.get("map_mode") not in ("eval_gt", "eval_pred"):
        raise ValueError("EX-42 renderer supports eval_gt/eval_pred only")
    if role not in ("success", "failure", "overview") or role != request.get("selection_role"):
        raise ValueError("selection role differs from planned slot")
    if (type(request.get("terrain_level")) is not int or not 0 <= request["terrain_level"] <= 9
            or not isinstance(request.get("terrain_key"), str)
            or not isinstance(request.get("columns"), list) or not request["columns"]):
        raise ValueError("planned EX-42 cell is incomplete")
    if (not re.fullmatch(r"[0-9a-f]{40}", source_head)
            or not re.fullmatch(r"[0-9a-f]{64}", recorder_sha256)):
        raise ValueError("recorder source identity must be pinned")
    root = Path(source_root).resolve(strict=True)
    evaluation_path = Path(evaluation_json).resolve(strict=True)
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8-sig"))
    checkpoint_path = Path(plan["checkpoint"]).resolve(strict=True)
    if sha256(checkpoint_path) != plan.get("checkpoint_sha256"):
        raise ValueError("plan checkpoint SHA differs from its file")
    mesh_dir = Path(plan["mesh_dir"]).resolve(strict=True)
    from foothold_s2.eval.ex42_mesh_eval import preflight
    mesh_record = preflight(mesh_dir)
    command = [1.0, 0.0, 0.0]
    if (evaluation.get("checkpoint_sha256") != plan.get("checkpoint_sha256")
            or (evaluation.get("ex42_mesh") or {}).get("mesh_sha256") != plan.get("mesh_sha256")
            or (evaluation.get("ex42_mesh") or {}).get("columns") != mesh_record["columns"]
            or evaluation.get("eval_seed") != 42 or evaluation.get("envs") != ENV_COUNT
            or (evaluation.get("commands") or {}).get(command_name) != command
            or not isinstance(evaluation.get("steps"), int) or evaluation["steps"] <= 0
            or evaluation.get("policy_dt_s") != 0.02):
        raise ValueError("evaluation checkpoint SHA, mesh SHA, or seed differs from plan")
    array_name = (evaluation.get("env_arrays") or {}).get(
        f"{request['map_mode']}/{command_name}")
    if not isinstance(array_name, str) or Path(array_name).name != array_name:
        raise ValueError("evaluation result has no safe env-array path for the requested cell")
    arrays_path = evaluation_path.parent / array_name
    if not arrays_path.is_file():
        raise ValueError("evaluation env-array file is missing")
    with np.load(arrays_path, allow_pickle=False) as arrays:
        per_env = {"kind", "terrain_col", "terrain_level", "alive_end", "body_vx_integral_m"}
        needed = per_env | {"assignment_sha256"}
        if not needed.issubset(arrays.files):
            raise ValueError("evaluation env-array fields are incomplete")
        values = {key: np.asarray(arrays[key]) for key in needed}
    n = len(values["kind"])
    if n != ENV_COUNT or any(values[key].shape != (n,) for key in per_env):
        raise ValueError("EX-42 render selection requires the matching 64-env evaluation arrays")
    levels_all = values["terrain_level"].astype(np.int64)
    columns_all = values["terrain_col"].astype(np.int64)
    if (columns_all.min() < 0 or columns_all.max() >= len(mesh_record["columns"])
            or not np.array_equal(values["kind"].astype(str),
                                  np.asarray(mesh_record["columns"])[columns_all])):
        raise ValueError("evaluation env kind/column mapping differs from the combined mesh reset table")
    from foothold_s2.eval.fixed_terrain import assignment_sha256
    array_assignment_sha = str(np.asarray(values["assignment_sha256"]).item())
    terrain_hash = (evaluation.get("terrain_hash") or {}).get(f"{request['map_mode']}/{command_name}")
    if (array_assignment_sha != assignment_sha256(levels_all, columns_all)
            or terrain_hash != array_assignment_sha
            or array_assignment_sha != (evaluation.get("fixed_terrain") or {}).get("assignment_sha256")):
        raise ValueError("evaluation array assignment SHA differs from its map-mode receipt")
    kind_name = request["terrain_key"].split("/", 1)[-1]
    columns = set(request["columns"])
    cell = ((values["kind"].astype(str) == kind_name)
            & np.isin(values["terrain_col"].astype(np.int64), list(columns))
            & (values["terrain_level"].astype(np.int64) == request["terrain_level"]))
    if not cell.any():
        raise ValueError("evaluation has no env in the planned terrain cell")
    if role == "success":
        eligible = cell & values["alive_end"].astype(bool)
        eligible &= values["body_vx_integral_m"].astype(np.float64) >= SUCCESS_FWD_M
        candidates = np.flatnonzero(eligible)
        if not len(candidates):
            raise ValueError("evaluation has no successful env for this render slot")
        selected = int(candidates[0])
    elif role == "failure":
        candidates = np.flatnonzero(cell & ~values["alive_end"].astype(bool))
        if not len(candidates):
            raise ValueError("evaluation has no failed env for this render slot")
        selected = int(candidates[0])
    else:
        if type(overview_env_id) is not int or not 0 <= overview_env_id < n or not cell[overview_env_id]:
            raise ValueError("overview requires a selected env in the planned terrain cell")
        selected = overview_env_id

    selected_col = int(values["terrain_col"][selected])
    selected_level = int(values["terrain_level"][selected])
    if selected_col not in columns or selected_level != request["terrain_level"]:
        raise ValueError("selected env terrain assignment differs from plan")
    return {
        "experiment": "SB", "source_profile": PROFILE,
        "ex42_render_reference": True, "terrain_set": "ex42_mesh",
        "source_root": str(root), "source_head": source_head,
        "source_recorder_sha256": recorder_sha256,
        "checkpoint": plan["checkpoint"], "checkpoint_sha256": plan["checkpoint_sha256"],
        "mesh_dir": str(mesh_dir), "mesh_sha256": plan["mesh_sha256"],
        "evaluation_json": str(evaluation_path), "evaluation_json_sha256": sha256(evaluation_path),
        "evaluation_arrays": str(arrays_path), "evaluation_arrays_sha256": sha256(arrays_path),
        "command_name": command_name, "command": command, "duration_s": 18.0,
        "seed": 42, "envs": ENV_COUNT, "env_id": selected,
        "terrain_key": request["terrain_key"], "kind": kind_name,
        "col": selected_col, "fixed_level": selected_level,
        "map_mode": request["map_mode"], "selection_role": role,
        "request_id": request_id, "z_mode": "mean", "act_mode": "mean",
        "render_request": request,
        "overview_env_id": selected if role == "overview" else None,
        "hide_others": True, "frame_audit_required": True,
    }


def recorder_command(spec_path: str | Path, spec: dict, *, output: str | Path,
                     label: str) -> list[str]:
    """Return the exact one-clip command; this function never starts Kit."""
    spec_path = Path(spec_path).resolve()
    output = Path(output).resolve()
    if not label or any(char in label for char in "\r\n"):
        raise ValueError("capture label must be a non-empty single line")
    return [sys.executable, "-m", "foothold_s2.eval.video25.record_c_layer",
            "--policy", "@" + str(spec_path), "--checkpoint", str(spec["checkpoint"]),
            "--label", label, "--scene", "sparse", "--mp4", str(output)]


def prepare_capture_command(plan_path: str | Path, request_id: str,
                            evaluation_json: str | Path, *, command_name: str,
                            role: str, source_root: str | Path, spec_path: str | Path,
                            output: str | Path, label: str,
                            overview_env_id: int | None = None) -> dict:
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8-sig"))
    root = Path(source_root).resolve(strict=True)
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    recorder = root / "foothold_s2/eval/video25/record_c_layer.py"
    spec = capture_spec_from_evaluation(
        plan, request_id, evaluation_json, command_name=command_name, role=role,
        source_root=root, source_head=head, recorder_sha256=sha256(recorder),
        overview_env_id=overview_env_id)
    spec_path = Path(spec_path).resolve()
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    with spec_path.open("x", encoding="utf-8") as handle:
        json.dump(spec, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
    return {"state": "prepared", "spec_path": str(spec_path),
            "request_id": spec["request_id"], "selected_env_id": spec["env_id"],
            "checkpoint_sha256": spec["checkpoint_sha256"], "mesh_sha256": spec["mesh_sha256"],
            "evaluation_arrays_sha256": spec["evaluation_arrays_sha256"],
            "command": recorder_command(spec_path, spec, output=output, label=label)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare one EX-42 combined-mesh video command; no Kit is started")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--evaluation-json", required=True)
    parser.add_argument("--command-name", required=True)
    parser.add_argument("--role", choices=("success", "failure", "overview"), required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--spec-out", required=True)
    parser.add_argument("--mp4", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--overview-env-id", type=int)
    args = parser.parse_args(argv)
    result = prepare_capture_command(
        args.plan, args.request_id, args.evaluation_json,
        command_name=args.command_name, role=args.role, source_root=args.source_root,
        spec_path=args.spec_out, output=args.mp4, label=args.label,
        overview_env_id=args.overview_env_id)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


def validate_capture_spec(spec: dict) -> dict:
    """Re-read all plan/evaluation identities before the Kit recorder starts."""
    from foothold_s2.eval.ex42_render_plan import MAP_MODES, SELECTION_ROLES

    request = spec.get("render_request")
    if not isinstance(request, dict):
        raise ValueError("EX-42 capture lacks its frozen render request")
    identity = {key: request.get(key) for key in
                ("mesh_sha256", "checkpoint_sha256", "terrain_key", "terrain_level",
                 "map_mode", "selection_role")}
    request_digest = hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if (request_digest != spec.get("request_id")
            or request.get("request_id") != spec.get("request_id")
            or identity["checkpoint_sha256"] != spec.get("checkpoint_sha256")
            or identity["mesh_sha256"] != spec.get("mesh_sha256")
            or identity["map_mode"] not in MAP_MODES
            or identity["selection_role"] not in SELECTION_ROLES
            or identity["terrain_level"] != spec.get("fixed_level")
            or identity["terrain_key"] != spec.get("terrain_key")):
        raise ValueError("EX-42 capture request identity differs")
    checkpoint = Path(spec["checkpoint"]).resolve(strict=True)
    evaluation_path = Path(spec["evaluation_json"]).resolve(strict=True)
    arrays_path = Path(spec["evaluation_arrays"]).resolve(strict=True)
    mesh_path = Path(spec["mesh_dir"]).resolve(strict=True)
    if (sha256(checkpoint) != spec["checkpoint_sha256"]
            or sha256(evaluation_path) != spec["evaluation_json_sha256"]
            or sha256(arrays_path) != spec["evaluation_arrays_sha256"]):
        raise ValueError("EX-42 capture checkpoint/evaluation artifact SHA differs")
    from foothold_s2.eval.ex42_mesh_eval import preflight
    mesh = preflight(mesh_path)
    if mesh["mesh_sha256"] != spec["mesh_sha256"]:
        raise ValueError("EX-42 capture mesh SHA differs")
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8-sig"))
    mesh_record = preflight(mesh_path)
    if (evaluation.get("checkpoint_sha256") != spec["checkpoint_sha256"]
            or (evaluation.get("ex42_mesh") or {}).get("mesh_sha256") != spec["mesh_sha256"]
            or (evaluation.get("ex42_mesh") or {}).get("columns") != mesh_record["columns"]
            or evaluation.get("eval_seed") != spec["seed"]
            or evaluation.get("envs") != ENV_COUNT
            or (evaluation.get("commands") or {}).get(spec["command_name"]) != [1.0, 0.0, 0.0]
            or not isinstance(evaluation.get("steps"), int) or evaluation["steps"] <= 0
            or evaluation.get("policy_dt_s") != 0.02):
        raise ValueError("EX-42 capture evaluation identity differs")
    named_array = (evaluation.get("env_arrays") or {}).get(
        f"{spec['map_mode']}/{spec['command_name']}")
    if named_array != arrays_path.name or arrays_path.parent != evaluation_path.parent:
        raise ValueError("EX-42 capture array is not the named evaluation artifact")
    with np.load(arrays_path, allow_pickle=False) as data:
        kinds, levels, cols = (np.asarray(data[key]) for key in
                               ("kind", "terrain_level", "terrain_col"))
        alive, distance = (np.asarray(data[key]) for key in
                           ("alive_end", "body_vx_integral_m"))
        array_assignment_sha = str(np.asarray(data["assignment_sha256"]).item())
    from foothold_s2.eval.fixed_terrain import assignment_sha256
    expected_assignment_sha = assignment_sha256(levels, cols)
    terrain_hash = (evaluation.get("terrain_hash") or {}).get(
        f"{spec['map_mode']}/{spec['command_name']}")
    if (array_assignment_sha != expected_assignment_sha
            or terrain_hash != expected_assignment_sha
            or array_assignment_sha != (evaluation.get("fixed_terrain") or {}).get("assignment_sha256")
            or not np.array_equal(kinds.astype(str), np.asarray(mesh_record["columns"])[cols.astype(np.int64)])):
        raise ValueError("EX-42 capture assignment or kind/column receipt differs")
    env_id = spec.get("env_id")
    if type(env_id) is not int or not 0 <= env_id < ENV_COUNT or len(kinds) != ENV_COUNT:
        raise ValueError("EX-42 selected env or evaluation env count differs")
    request_kind = identity["terrain_key"].split("/", 1)[-1]
    cell = ((kinds.astype(str) == request_kind)
            & (levels.astype(np.int64) == spec["fixed_level"])
            & np.isin(cols.astype(np.int64), request["columns"]))
    if not cell[env_id]:
        raise ValueError("EX-42 selected evaluation env does not match its planned cell")
    role = spec["selection_role"]
    if role == "success":
        eligible = cell & alive.astype(bool) & (distance.astype(np.float64) >= SUCCESS_FWD_M)
        expected = int(np.flatnonzero(eligible)[0]) if eligible.any() else None
        if expected != env_id:
            raise ValueError("EX-42 success env is not the first env under the success rule")
    elif role == "failure":
        eligible = cell & ~alive.astype(bool)
        expected = int(np.flatnonzero(eligible)[0]) if eligible.any() else None
        if expected != env_id:
            raise ValueError("EX-42 failure env is not the first failed env")
    elif spec.get("overview_env_id") != env_id:
        raise ValueError("EX-42 overview env lacks explicit selection provenance")
    return {"request_id": spec["request_id"], "checkpoint_sha256": spec["checkpoint_sha256"],
            "mesh_sha256": spec["mesh_sha256"], "evaluation_arrays_sha256": spec["evaluation_arrays_sha256"],
            "selected_env_id": env_id, "terrain_key": identity["terrain_key"],
            "terrain_level": int(levels[env_id]), "terrain_col": int(cols[env_id]),
            "selection_role": role, "state": "verified"}


def apply_evaluation_assignment(raw, spec: dict) -> dict:
    """Apply the exact 64-env assignment recorded by the matching evaluation."""
    import torch
    from foothold_s2.eval.ex42_mesh_eval import preflight
    from foothold_s2.eval.fixed_terrain import apply_assignment, assignment_sha256

    arrays_path = Path(spec["evaluation_arrays"]).resolve(strict=True)
    if sha256(arrays_path) != spec["evaluation_arrays_sha256"]:
        raise ValueError("evaluation env-array SHA changed before capture")
    mesh = preflight(spec["mesh_dir"])
    if mesh["mesh_sha256"] != spec["mesh_sha256"]:
        raise ValueError("EX-42 render mesh SHA changed before capture")
    with np.load(arrays_path, allow_pickle=False) as data:
        levels = np.asarray(data["terrain_level"], dtype=np.int64)
        columns = np.asarray(data["terrain_col"], dtype=np.int64)
        kinds = np.asarray(data["kind"]).astype(str)
    terrain = raw.scene.terrain
    rows, cols = map(int, terrain.terrain_origins.shape[:2])
    if (int(raw.num_envs) != ENV_COUNT or levels.shape != (ENV_COUNT,) or columns.shape != (ENV_COUNT,)
            or kinds.shape != (ENV_COUNT,) or (levels < 0).any() or (levels >= rows).any()
            or (columns < 0).any() or (columns >= cols).any()):
        raise ValueError("EX-42 evaluation terrain assignment shape or bounds differ")
    if cols != len(mesh["columns"]):
        raise ValueError("EX-42 mounted mesh column count differs from evaluation")
    env_id = int(spec["env_id"])
    if (not 0 <= env_id < ENV_COUNT or levels[env_id] != spec["fixed_level"]
            or columns[env_id] != spec["col"] or kinds[env_id] != spec["kind"]
            or mesh["columns"][spec["col"]] != spec["kind"]):
        raise ValueError("selected EX-42 env is not the planned cell")
    if not np.isin(levels, np.arange(rows)).all():
        raise ValueError("evaluation assignment contains an invalid terrain level")
    receipt = apply_assignment(raw, levels, columns, rows, cols,
                               levels_used=rows, fixed_level=None)
    if not torch.equal(raw.scene.terrain.terrain_levels.cpu(), torch.as_tensor(levels)):
        raise RuntimeError("EX-42 fixed levels did not stick")
    if not torch.equal(raw.scene.terrain.terrain_types.cpu(), torch.as_tensor(columns)):
        raise RuntimeError("EX-42 fixed columns did not stick")
    return {**receipt, "selected_env_id": env_id, "selected_kind": kinds[env_id],
            "selected_level": int(levels[env_id]), "selected_col": int(columns[env_id]),
            "assignment_sha256": assignment_sha256(levels, columns),
            "evaluation_arrays_sha256": spec["evaluation_arrays_sha256"]}


if __name__ == "__main__":
    raise SystemExit(main())
