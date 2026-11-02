"""Build a SHA-pinned one-cell C76 diagnostic from the untouched 5027e4ad recorder."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


FROZEN_RECORDER_SHA256 = "94647fd6150f138aaaccedd1e5ea34858e482186bfa9fc857aa8b284d60798cb"
OLD = """                    mask_row = robot_pixel_evidence(
                        instance_annotator.get_data(), selected_env=capture_env_id,
                        env_count=n_envs(spec), height=full_args.height, width=full_args.width)
                    require_single_visible_robot(mask_row)
                    instance_evidence.append(mask_row)
"""
NEW = """                    if hashlib.sha256(Path(__file__).resolve().with_name("c_layer_seg_probe.py").read_bytes()).hexdigest() != "__C_LAYER_PROBE_SHA__":
                        raise RuntimeError("C76 segmentation probe source SHA differs")
                    from c_layer_seg_probe import recognize_after_render, write_failure
                    from pxr import UsdGeom
                    selected_path = render_visibility_record["visible_robot_root"]
                    selected_prim = omni.usd.get_context().get_stage().GetPrimAtPath(selected_path)
                    selected_visibility = (str(UsdGeom.Imageable(selected_prim).ComputeVisibility())
                                           if selected_prim.IsValid() else "prim_missing")
                    mask_row, frame, seg_checks, failed_packet, seg_reason = recognize_after_render(
                        instance_annotator.get_data,
                        lambda packet: robot_pixel_evidence(
                            packet, selected_env=capture_env_id, env_count=n_envs(spec),
                            height=full_args.height, width=full_args.width),
                        lambda: (raw.sim.render(), np.ascontiguousarray(raw.render(recompute=True))[..., :3])[1],
                        lambda: _render_state(raw, robot, command_term, sensor, capture_env_id),
                        frame)
                    if mask_row is None:
                        diagnostic = write_failure(
                            output.parent, packet=failed_packet, frame=frame,
                            selected_env=capture_env_id, selected_root=selected_path,
                            root_visibility=selected_visibility,
                            camera=camera_screen_projection[-1], checks=seg_checks,
                            reason=seg_reason)
                        raise ValueError("C76 selected robot instance IDs missing; diagnostic=" + str(diagnostic))
                    require_single_visible_robot(mask_row)
                    instance_evidence.append(mask_row)
                    render_retry_checks.extend({"physics_tick": k, "segmentation": True, **check}
                                               for check in seg_checks)
"""
VISIBILITY_OLD = """            if c_layer_ref(spec) and len(render_visibility_record["hidden_robot_roots"]) != n_envs(spec) - 1:
                raise RuntimeError("C76 expected all other robot roots to be invisible")
"""
VISIBILITY_NEW = VISIBILITY_OLD + """            if c_layer_ref(spec):
                if hashlib.sha256(Path(__file__).resolve().with_name("c_layer_visibility.py").read_bytes()).hexdigest() != "__C_LAYER_VISIBILITY_SHA__":
                    raise RuntimeError("C76 visibility helper source SHA differs")
                from c_layer_visibility import ensure_only_selected_visible
                from pxr import UsdGeom
                render_visibility_record["visibility_check"] = ensure_only_selected_visible(
                    omni.usd.get_context().get_stage(),
                    render_visibility_record["visible_robot_root"],
                    render_visibility_record["hidden_robot_roots"], UsdGeom.Imageable)
"""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(frozen: Path, base_plan: Path, output_root: Path, diagnostic_out: Path,
          cell: str, runner: Path | None = None) -> dict:
    source = frozen / "foothold_s2/eval/video25/record_c_layer.py"
    if digest(source) != FROZEN_RECORDER_SHA256:
        raise ValueError("frozen C76 recorder SHA differs")
    recorder_dir = output_root / "foothold_s2/eval/video25"
    recorder_dir.mkdir(parents=True, exist_ok=True)
    recorder = recorder_dir / "record_c_layer.py"
    text = source.read_text(encoding="utf-8")
    if text.count(OLD) != 1 or text.count(VISIBILITY_OLD) != 1:
        raise ValueError("C76 instance-mask insertion point differs")
    tools = Path(__file__).resolve().parent
    patched = text.replace(OLD, NEW).replace(VISIBILITY_OLD, VISIBILITY_NEW)
    patched = patched.replace("__C_LAYER_PROBE_SHA__", digest(tools / "c_layer_seg_probe.py"))
    patched = patched.replace("__C_LAYER_VISIBILITY_SHA__", digest(tools / "c_layer_visibility.py"))
    recorder.write_text(patched, encoding="utf-8")
    shutil.copyfile(tools / "c_layer_seg_probe.py", recorder_dir / "c_layer_seg_probe.py")
    shutil.copyfile(tools / "c_layer_visibility.py", recorder_dir / "c_layer_visibility.py")
    for relative in ("foothold_s2/eval/video25/overlay_25e.py", "foothold_s2/eval/video_style.py"):
        destination = output_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(frozen / relative, destination)
    plan = json.loads(base_plan.read_text(encoding="utf-8-sig"))
    if len(plan["jobs"]) != 216 or cell not in {
            f"{row['kind']}_L{row['level']}_{row['map_mode']}" for row in plan["jobs"]}:
        raise ValueError("diagnostic cell is not in the canonical full plan")
    plan["recorder"] = str(recorder.resolve())
    plan["recorder_sha256"] = digest(recorder)
    old_overlay = next(key for key in plan["runtime_sources_sha256"] if key.endswith("overlay_25e.py"))
    del plan["runtime_sources_sha256"][old_overlay]
    overlay = recorder_dir / "overlay_25e.py"
    plan["runtime_sources_sha256"][str(overlay.resolve())] = digest(overlay)
    for row in plan["jobs"]:
        row["recorder_argv"][1] = str(recorder.resolve())
    # This is a diagnostic run, not a canonical success receipt. Use a fresh out.
    plan["execution_shard"]["output"] = str(diagnostic_out.resolve())
    if runner is not None:
        plan["execution_shard"]["runner"] = str(runner.resolve())
        plan["execution_shard"]["runner_sha256"] = digest(runner)
    target = output_root / "diagnostic_plan.json"
    target.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"cell": cell, "plan": str(target), "plan_sha256": digest(target),
            "recorder": str(recorder), "recorder_sha256": digest(recorder),
            "probe_sha256": digest(recorder_dir / "c_layer_seg_probe.py"),
            "visibility_sha256": digest(recorder_dir / "c_layer_visibility.py"),
            "diagnostic_out": str(diagnostic_out.resolve())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--base-plan", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--diagnostic-out", type=Path, required=True)
    parser.add_argument("--cell", required=True)
    parser.add_argument("--runner", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.frozen, args.base_plan, args.output_root,
                           args.diagnostic_out, args.cell, args.runner), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
