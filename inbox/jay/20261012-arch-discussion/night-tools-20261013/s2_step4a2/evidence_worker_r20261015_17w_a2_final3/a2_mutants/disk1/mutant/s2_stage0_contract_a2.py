"""Exact one-shot information-only contract and closed import-source list."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from s2_known_scene_a2 import answer_sha256
from s2_stage0_resources_a2 import normalize_bus


class ContractHold(RuntimeError):pass


REQUIRED_BUNDLE=(
    "s2_connect_diag_17v.py","s2_connect_check_17v.py","s2_env_config_17v.py",
    "s2_known_scene_a2.py","s2_scene_answer_a2.json","s2_capture_journal_a2.py",
    "s2_sensor_tracker_17v.py","s2_packet_17v.py","s2_env_adapter_17v.py",
    "s2_map_obs.py","s2_terrain_overlay_17v.py","s2_runner_17v.py",
    "s2_ppo_17v.py","s2_policy.py","s2_job_owner.py","s2_resource_lease.py",
    "s2_zero_supervisor.py","s2_stage_gate_17v.py","s2_stage0_contract_a2.py",
    "s2_stage0_resources_a2.py","s2_stage0_prelaunch.py","s2_device_binding_a2.py",
    "s2_mesh_probe_a2.py")


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required_args(manifest):
    options=manifest["diag_options"]
    keys=("seed","num_envs","steps","gap_proportion","stones_proportion",
          "step_height_m","step_width_m","geometry_tolerance_m")
    return ["--parent",manifest["parent_path"],"--out_root",manifest["out_root"],
            "--criteria",manifest["criteria_path"],"--attempt",manifest["attempt"],
            "--gpu_uuid",manifest["gpu_uuid"],"--gpu_bus_id",manifest["gpu_bus_id"],
            "--asset_path",manifest["asset_path"],
            "--hook_source_path",manifest["hook_source_path"],
            "--hook_source_sha256",manifest["hook_source_sha256"],
            "--scene_answer_sha256",manifest["scene_answer_sha256"],
            *[item for key in keys for item in ("--"+key,str(options[key]))],
            "--headless","--device","cuda:0"]


def validate_a2(manifest,bundle:Path):
    needed=("purpose","max_launches","retry_count","gpu_bus_id","min_free_vram_bytes",
            "running_floor_vram_bytes","min_free_disk_bytes","max_disk_bytes",
            "usd_lock_path","usd_root","log_path","asset_path","asset_ref_sha256",
            "hook_source_path","hook_source_sha256","scene_answer_sha256","code_hashes",
            "observer_mode","reservation_confirmed","diag_options","prelaunch_report_path")
    if any(k not in manifest or manifest[k] in (None,"","UNDECIDED") for k in needed):
        raise ContractHold("a2_contract_missing")
    if (manifest["purpose"]!="stage0_information_only" or manifest["max_launches"]!=1 or
        manifest["retry_count"]!=0 or manifest["observer_mode"]!="attended" or
        manifest["reservation_confirmed"] is not True):
        raise ContractHold("information_only_attended_claim")
    if manifest["gpu_index"]!=0 or normalize_bus(manifest["gpu_bus_id"])!=manifest["gpu_bus_id"].lower():
        raise ContractHold("gpu0_bus_contract")
    if any(type(manifest[k]) is not int or manifest[k]<=0 for k in
           ("min_free_vram_bytes","running_floor_vram_bytes","min_free_disk_bytes","max_disk_bytes")):
        raise ContractHold("resource_limits_invalid")
    if False:
        raise ContractHold("output_budget_below_raw_minimum")
    if manifest["scene_answer_sha256"]!=answer_sha256():raise ContractHold("scene_answer_hash")
    if hashlib.sha256(manifest["asset_path"].encode()).hexdigest()!=manifest["asset_ref_sha256"]:
        raise ContractHold("asset_reference_hash")
    if Path(manifest["usd_lock_path"]).resolve()!=Path(
        "C:/isaac/ext/go2_rl_robotlab/_eval/slot/isaac_convert.lock").resolve():
        raise ContractHold("usd_lock_path")
    if not Path(manifest["usd_lock_path"]).is_file():raise ContractHold("usd_lock_missing")
    hp=Path(manifest["hook_source_path"])
    if not hp.is_file() or sha(hp)!=manifest["hook_source_sha256"]:
        raise ContractHold("sensor_hook_source_hash")
    hashes=manifest["code_hashes"]
    if not isinstance(hashes,dict) or set(hashes)!=set(REQUIRED_BUNDLE):
        raise ContractHold("bundle_dependency_closure")
    for name in REQUIRED_BUNDLE:
        path=bundle/name
        if not path.is_file() or sha(path)!=hashes[name]:raise ContractHold("bundle_hash_"+name)
    options=manifest["diag_options"]
    if not isinstance(options,dict):raise ContractHold("diag_options")
    try:
        if type(options["seed"]) is not int or options["num_envs"]!=8 or options["steps"]!=256:
            raise ContractHold("diag_size_seed")
        for k in ("gap_proportion","stones_proportion","step_height_m","step_width_m",
                  "geometry_tolerance_m"):
            value=options[k]
            if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
                raise ContractHold("diag_option_"+k)
    except KeyError as ex:raise ContractHold("diag_required_option") from ex
    if manifest["diag_args"]!=required_args(manifest):
        raise ContractHold("diag_argv_exact_contract")
    if Path(manifest["out_root"]).exists() or Path(manifest["stop_path"]).exists():
        raise ContractHold("output_or_STOP_exists")
    for key in ("out_root","usd_root","log_path","prelaunch_report_path"):
        path=Path(manifest[key]).resolve()
        if bundle.parent not in path.parents:
            raise ContractHold("write_outside_codexE_"+key)
    if Path(manifest["usd_root"]).exists() or Path(manifest["log_path"]).exists():
        raise ContractHold("usd_or_log_reused")
    return True
