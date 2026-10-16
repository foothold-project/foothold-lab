"""S2 case evaluator core. Kit caller supplies an adapter with pre-reset state capture.

Import is CPU-only. No AppLauncher or simulator is started here. A missing Kit
adapter hook fails closed, since post-step robot data may already be reset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import h5py  # noqa: F401  approved Windows DLL preload before isaaclab.app
import tensordict  # noqa: F401  approved native extension preload before isaaclab.app
import numpy as np
import torch

from s2_eval_cases import CaseError, verify as verify_cases, canonical
from s2_eval_cpu import strict_load, sha as file_sha
from s2_env_adapter_17v import training_map
from s2_packet_17v import AtomicPacket
import s2_1043_q_metrics as Q


class EvalHold(RuntimeError):
    pass


STATE_KEYS = ("pos", "yaw", "vb", "wb", "grav_z", "hag", "term")
OBS_KEYS = ("policy", "single_obs", "critic")
OBS_WIDTHS = {"policy": 450, "single_obs": 45, "critic": 275}
PARENT_E1_SHA256 = "c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8"
AGENT_YAML_SHA256 = "9b8149ddc6101f92966d2ffdef326f44fa0fb46553678d8f092bcf624dc3173b"


def read_json(path, expected_sha256):
    if file_sha(path) != expected_sha256:
        raise EvalHold("input_sha256")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_job(job, cases):
    if job.get("schema") != "s2-eval-job-v1" or job.get("inference") != "act_inference":
        raise EvalHold("deterministic_inference_required")
    if (job.get("update") not in (0, 2000) or
        (cases["phase"] == "smoke" and job.get("update") != 0) or
        job.get("phase") != cases["phase"] or
        job.get("cases_sha256") != cases["cases_sha256"]):
        raise EvalHold("case_or_update_identity")
    if set(job.get("arms", {})) != {"A", "B"}:
        raise EvalHold("both_arms_required")
    for mode in ("A", "B"):
        arm = job["arms"][mode]
        if (not isinstance(arm, dict) or not all(arm.get(k) for k in
                ("checkpoint", "checkpoint_sha256", "env_config_sha256"))
            or type(arm.get("map_init_seed")) is not int):
            raise EvalHold("checkpoint_manifest_fields")
    if (job["arms"]["A"]["env_config_sha256"] != job["arms"]["B"]["env_config_sha256"] or
        job["arms"]["A"]["map_init_seed"] != job["arms"]["B"]["map_init_seed"]):
        raise EvalHold("arm_environment_or_map_seed_diff")
    for name, mod in (("q_metrics.py", Q),):
        if file_sha(mod.__file__) != cases["source_sha256"][name]:
            raise EvalHold("1043_scoring_source_sha256")
    return True


def load_policies(job, *, parent_loader=None, checkpoint_loader=strict_load):
    """Verify all three file hashes before any parent or S2 torch.load."""
    for key in ("parent", "agent_yaml"):
        ref = job.get(key, {})
        pinned = PARENT_E1_SHA256 if key == "parent" else AGENT_YAML_SHA256
        if (not ref.get("path") or ref.get("sha256") != pinned or
            file_sha(ref["path"]) != pinned):
            raise EvalHold(key + "_sha256")
    for mode in ("A", "B"):
        arm = job["arms"][mode]
        if file_sha(arm["checkpoint"]) != arm["checkpoint_sha256"]:
            raise EvalHold(mode + "_checkpoint_sha256")
    if parent_loader is None:
        from s2_policy import load_parent_cpu
        parent_loader = load_parent_cpu
    parent, _ = parent_loader(job["parent"]["path"], job["agent_yaml"]["path"])
    loaded = {}
    for mode in ("A", "B"):
        arm = job["arms"][mode]
        policy, info = checkpoint_loader(
            arm["checkpoint"], expected_sha256=arm["checkpoint_sha256"],
            parent=parent, mode=mode, expected_env_config_sha256=arm["env_config_sha256"],
            map_init_seed=arm["map_init_seed"])
        policy.eval()
        loaded[mode] = (policy, info)
    return loaded


def _same_obs(left, right):
    return (set(left) == set(right) and all(isinstance(left[k], torch.Tensor) and
            torch.equal(left[k], right[k]) for k in left))


def _state(state):
    optional = {"contact_force_max_n", "contact_forces_sha256"}
    if not isinstance(state, dict) or not set(STATE_KEYS).issubset(state) or set(state) - set(STATE_KEYS) - optional:
        raise EvalHold("physical_state_before_reset_missing")
    out = {}
    for key in STATE_KEYS:
        x = np.asarray(state[key])
        shape = (3,) if key in ("pos", "vb", "wb") else ()
        if x.shape != shape or (key != "term" and not np.isfinite(x).all()):
            raise EvalHold("physical_state_shape_or_nonfinite:" + key)
        out[key] = bool(x) if key == "term" else x.astype(float).copy()
    if "contact_force_max_n" in state or "contact_forces_sha256" in state:
        force = state.get("contact_force_max_n")
        digest = state.get("contact_forces_sha256")
        if (type(force) not in (float, int) or not np.isfinite(force) or force < 0 or
            not isinstance(digest, str) or len(digest) != 64 or
            any(c not in "0123456789abcdef" for c in digest)):
            raise EvalHold("contact_physical_state")
        out["contact_force_max_n"] = float(force)
        out["contact_forces_sha256"] = digest
    return out


def _fingerprint(adapter, case):
    value = adapter.case_fingerprint()
    keys = ("mesh_sha256", "initial_state_sha256", "command_sha256", "friction",
            "terrain_seed", "eval_seed", "policy_dt", "physics_dt", "origin_x", "zone_end_x")
    if not isinstance(value, dict) or not all(k in value for k in keys):
        raise EvalHold("case_fingerprint_incomplete")
    if (value["terrain_seed"] != case["terrain_seed"] or value["eval_seed"] != case["eval_seed"] or
        value["friction"] != case["friction"] or value["policy_dt"] != case["policy_dt"] or
        value["physics_dt"] != case["physics_dt"] or
        value["command_sha256"] != hashlib.sha256(canonical(case["command"])).hexdigest() or
        not all(isinstance(value[k], str) and len(value[k]) == 64 for k in ("mesh_sha256", "initial_state_sha256"))):
        raise EvalHold("case_fingerprint_mismatch")
    if case["family"] in ("gap", "stepping_stones") and value["zone_end_x"] is None:
        raise EvalHold("obstacle_zone_missing")
    return value


def _frame(adapter, obs, previous, previous_done, mode, tolerance):
    packet = adapter.capture_packet_after_sensor_update()
    if not isinstance(packet, AtomicPacket) or not _same_obs(packet.obs, obs):
        raise EvalHold("atomic_packet_or_observation")
    if adapter.read_sensor_source_receipt() != packet.source_receipt:
        raise EvalHold("independent_sensor_receipt")
    yaw = packet.validate(previous=previous, previous_done=previous_done)
    mapped, faults = training_map(packet.sensor, mode=mode, yaw_w=yaw,
                                  geometry_tolerance_m=tolerance)
    if faults.total:
        raise EvalHold("map_fault")
    frame = {k: obs[k].detach().clone() for k in OBS_KEYS}
    frame["map"] = mapped.detach().clone()
    for key, width in (*OBS_WIDTHS.items(), ("map", 374)):
        if frame[key].shape != (1, width) or not bool(torch.isfinite(frame[key]).all()):
            raise EvalHold("observation_shape_or_nonfinite:" + key)
    return frame, packet


def _score(case, states, fp):
    arrays = {k: np.asarray([s[k] for s in states]) for k in STATE_KEYS}
    cmd = np.tile(np.asarray(case["command"]["cmd"], dtype=float), (len(states), 1))
    result = Q.episode_metrics(case["command"], **arrays, cmd=cmd,
                               dt=case["policy_dt"], time_def="span")
    last = len(states) - 1
    if not result["survived"]:
        last = max(0, min(last, int(round(result["fall_t"] / case["policy_dt"])) - 1))
    crossed = None
    if fp["zone_end_x"] is not None:
        crossed = bool(np.any(arrays["pos"][:last + 1, 0] - fp["origin_x"] >= fp["zone_end_x"]))
    q_pass = bool(result["q1_pass"])
    is_target = case["family"] in ("gap", "stepping_stones")
    return {"success": crossed if is_target else q_pass,
            "success_rule": "1043_unseen_crossed" if is_target else "1043_span_q1_pass",
            "crossed": crossed, "command_pass": q_pass,
            "fall": not bool(result["survived"]), "fall_reason": result["fall_reason"],
            "stuck_diagnostic": bool(result["survived"] and crossed is False) if crossed is not None else None,
            "progress_m": result["progress_m"], "last_valid_state_index": last,
            "last_physical_state_before_reset": {k: (v.tolist() if isinstance(v, np.ndarray) else v)
                                                   for k, v in states[-1].items()}}


def run_case(adapter, policy, case, mode, *, geometry_tolerance_m):
    obs = adapter.reset(case)
    if hasattr(policy, "to"):
        policy.to(obs["policy"].device)
    fp = _fingerprint(adapter, case)
    reset = adapter.reset_receipt()
    if (not isinstance(reset, dict) or reset.get("case_id") != case["case_id"] or
        reset.get("eval_seed") != case["eval_seed"] or
        reset.get("initial_state_sha256") != fp["initial_state_sha256"] or
        type(reset.get("episode_id")) is not int or
        type(reset.get("previous_sensor_generation")) is not int or
        reset.get("post_reset_sensor_refresh") is not True):
        raise EvalHold("reset_receipt_missing_or_mismatched")
    states = [_state(adapter.initial_physical_state())]
    previous = None
    previous_done = None
    limit = int(round(case["command"]["duration_s"] / case["policy_dt"]))
    for step in range(limit):
        frame, packet = _frame(adapter, obs, previous, previous_done, mode, geometry_tolerance_m)
        if step == 0 and (int(packet.episode_ids[0]) != reset["episode_id"] or
                          packet.sensor_generation <= reset["previous_sensor_generation"]):
            raise EvalHold("reset_packet_not_fresh")
        with torch.inference_mode():
            action = policy.act_inference(frame)
        if action.shape != (1, 12) or not bool(torch.isfinite(action).all()):
            raise EvalHold("action_shape_or_nonfinite")
        # step_recorded must capture the state before any automatic reset. Plain step is forbidden.
        obs, done, pre_reset_state = adapter.step_recorded(action)
        state = _state(pre_reset_state)
        states.append(state)
        previous, previous_done = packet, torch.as_tensor([bool(done)], dtype=torch.bool)
        if done:
            if not state["term"]:
                raise EvalHold("done_without_pre_reset_termination")
            break
        if state["term"]:
            raise EvalHold("termination_without_done")
    score = _score(case, states, fp)
    return {"case_id": case["case_id"], "family": case["family"], "arm": mode,
            "eval_seed": case["eval_seed"], "steps": len(states) - 1,
            "fingerprint": fp, "score": score, "missing_reason": None,
            "usd_robot_references": getattr(adapter, "usd_robot_references", [])}


def run(job, cases, adapter_factory, *, policies=None, parent_loader=None,
        checkpoint_loader=strict_load, geometry_tolerance_m=0.002):
    verify_cases(cases)
    validate_job(job, cases)
    if policies is None:
        policies = load_policies(job, parent_loader=parent_loader, checkpoint_loader=checkpoint_loader)
    records = []
    for case in cases["cases"]:
        for mode in ("A", "B"):
            adapter = None
            try:
                adapter = adapter_factory(case, mode)
                policy = policies[mode][0] if isinstance(policies[mode], tuple) else policies[mode]
                record = run_case(adapter, policy, case, mode,
                                  geometry_tolerance_m=geometry_tolerance_m)
            except Exception as ex:
                record = {"case_id": case["case_id"], "family": case["family"],
                          "arm": mode, "eval_seed": case["eval_seed"], "missing_reason":
                          type(ex).__name__ + ":" + str(ex)[:240]}
            finally:
                if adapter is not None:
                    adapter.close()
            records.append(record)
    return {"schema": "s2-eval-episodes-v1", "cases_sha256": cases["cases_sha256"],
            "job_sha256": hashlib.sha256(canonical(job)).hexdigest(),
            "inputs": {"parent": job["parent"], "agent_yaml": job["agent_yaml"],
                       "arms": job["arms"], "1043_sources": cases["source_sha256"]},
            "update": job["update"], "inference": "act_inference", "records": records,
            "comparison_ready": False, "performance_verified": False}


def run_from_files(*, job_path, job_sha256, cases_path, cases_file_sha256,
                   adapter_factory, output_path, parent_loader=None,
                   checkpoint_loader=strict_load, runtime_info=None):
    """Read exactly one sealed list and one sealed job, then write CPU/Kit episode JSON."""
    job = read_json(job_path, job_sha256)
    cases = read_json(cases_path, cases_file_sha256)
    verify_cases(cases)
    result = run(job, cases, adapter_factory, parent_loader=parent_loader,
                 checkpoint_loader=checkpoint_loader)
    result["cases_file_sha256"] = cases_file_sha256
    result["job_file_sha256"] = job_sha256
    if runtime_info is not None:
        result["runtime"] = runtime_info
    target = Path(output_path)
    if target.exists():
        raise EvalHold("output_already_exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical(result) + b"\n")
    return result


def kit_main(argv=None):
    """Supervised Kit child. The supervisor pins this exact argv and all inputs."""
    from isaaclab.app import AppLauncher
    p = argparse.ArgumentParser()
    for name in ("job", "job-sha256", "cases", "cases-file-sha256", "out",
                 "asset-path", "hook-source-path", "hook-source-sha256"):
        p.add_argument("--" + name, required=True)
    AppLauncher.add_app_launcher_args(p)
    a = p.parse_args(argv)
    if (not a.headless or a.device != "cuda:0" or
        os.environ.get("FOOTHOLD_S2_EVAL_PURPOSE") != "evaluation_information_only" or
        os.environ.get("FOOTHOLD_EXPECT_CONVERSIONS") != "any"):
        raise EvalHold("supervised_headless_evaluation_only")
    launcher = AppLauncher(a)
    try:
        from s2_eval_kit_adapter import factory
        from s2_step4a34.s2_device_binding_a2 import inspect_child_device
        expected_uuid = os.environ.get("FOOTHOLD_S2_EVAL_GPU_UUID")
        if not expected_uuid:
            raise EvalHold("expected_gpu_uuid_missing")
        binding_raw = {}
        try:
            binding = inspect_child_device(expected_uuid, launcher, evidence=binding_raw)
        finally:
            evidence_path = Path(os.environ["FOOTHOLD_USD_ROOT"]) / "device_binding.json"
            evidence_path.write_bytes(canonical(binding_raw) + b"\n")
        runtime = {name: {"path": str(getattr(sys.modules.get(name), "__file__", None)),
                          "version": str(getattr(sys.modules.get(name), "__version__", None))}
                   for name in ("torch", "isaaclab", "robot_lab", "gymnasium",
                                "s2_eval_driver", "s2_eval_kit_adapter")}
        result = run_from_files(job_path=a.job, job_sha256=a.job_sha256,
                cases_path=a.cases, cases_file_sha256=a.cases_file_sha256,
                adapter_factory=factory(hook_source_path=a.hook_source_path,
                                        hook_source_sha256=a.hook_source_sha256), output_path=a.out,
                runtime_info={"pid": os.getpid(), "imports": runtime,
                              "driver_path": str(Path(__file__).resolve()), "device_binding": binding})
    finally:
        launcher.app.close()
    print(json.dumps({"status": "HOLD" if any(r.get("missing_reason") for r in result["records"])
          else "INFORMATION_ONLY", "records": len(result["records"])}), flush=True)
    return 42 if any(r.get("missing_reason") for r in result["records"]) else 0


if __name__ == "__main__":
    raise SystemExit(kit_main())
