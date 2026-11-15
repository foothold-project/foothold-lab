"""Build the immutable candidate contract from read-only source bytes."""
import json
import platform
import sys
from pathlib import Path

import numpy as np

from s1043_manifest import ROOT, UNDECIDED, canonical_hash, sha256

EVAL = Path("C:/isaac/ext/go2_rl_robotlab/_eval")
BRANCH = EVAL / "out_branch"
PARENT_DIR = Path("C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192")
PROJECT = EVAL.parent
CELLS = ["stop03", "fwd01", "fwd02", "stand", "fwd03", "fwd05", "back03", "left03", "right03", "yawL05", "yawR05"]
TARGETS = ["stop03", "fwd01", "fwd02"]
FAMILIES = ["flat", "obstacles", "rough_slope", "slope_up", "slope_down", "stairs_up", "stairs_down", "wave"]
MODELS = ["p20000", "off22000", "on22000", "off24000", "on24000"]


def record(path):
    return {"path": path.as_posix(), "sha256": sha256(path)}


def base_jobs():
    jobs = []
    for m in MODELS:
        for cell in CELLS:
            jobs.append([m, "flat", cell, "on", 1000])
    for m in MODELS:
        for seed in (1001, 1002, 1003, 1004):
            for cell in TARGETS:
                jobs.append([m, "flat", cell, "on", seed])
    for fam in FAMILIES[1:]:
        for m in MODELS:
            for cell in CELLS:
                jobs.append([m, fam, cell, "on", 1000])
    for m in MODELS:
        for cell in CELLS:
            jobs.append([m, "flat", cell, "off", 1000])
    return jobs


def build():
    parent = PARENT_DIR / "model_20000.pt"
    inputs = {"parent_model": record(parent), "parent_env_yaml": record(PARENT_DIR / "params/env.yaml"),
              "parent_agent_yaml": record(PARENT_DIR / "params/agent.yaml")}
    branches = {}
    for arm in ("off", "on"):
        directory = BRANCH / f"cmdr_s1043_{arm}_u4000"
        names = {"model_22000": "model_22000.pt", "model_24000": "model_24000.pt",
                 "result": "result.json", "bundle_json": "bundle.json", "bundle_npz": "bundle.npz",
                 "stamp": "validate_stamp.json"}
        branches[arm] = {}
        for kind, filename in names.items():
            key = f"{arm}_{kind}"
            inputs[key] = record(directory / filename)
            branches[arm][kind] = key
        for kind, suffix in (("run_log", ".log"), ("guard", ".guard.json"), ("slot", ".slot.json")):
            key = f"{arm}_{kind}"
            inputs[key] = record(BRANCH / f"cmdr_s1043_{arm}_u4000{suffix}")
            branches[arm][kind] = key
    code = ["q_eval_cmdr.py", "q_eval.py", "q_metrics.py", "q_post.py", "paired_ci.py", "gpu_guard.py",
            "isaac_slot_v3.py", "usd_isolate_run_v3.py", "cmdr_eval_driver_v37.py", "cmdr_post_v10.py",
            "cmdr_bundle_compare.py"]
    for name in code:
        inputs[f"source_{name}"] = record(EVAL / name)
    for relative in ("source/robot_lab/robot_lab/tasks/go2/mdp/commands.py",
                     "source/robot_lab/robot_lab/tasks/go2/mdp/curriculums.py",
                     "source/robot_lab/robot_lab/tasks/go2/mdp/utils.py",
                     "source/robot_lab/robot_lab/tasks/go2/env_cfg.py",
                     "source/rsl_rl/rsl_rl/runners/on_policy_runner_cts.py",
                     "source/rsl_rl/rsl_rl/algorithms/moe_cts.py"):
        inputs[f"config_{relative}"] = record(PROJECT / relative)
    jobs = base_jobs()
    a = [j for j in jobs if j[0] in ("p20000", "off24000", "on24000") and j[1] == "flat" and j[2] in TARGETS and j[3] == "on"]
    screen = sorted({(fam, cell, noise) for _, fam, cell, noise, seed in jobs if seed == 1000
                     and not (fam == "flat" and noise == "on" and cell in TARGETS)})
    extra = [[m, fam, cell, noise, seed] for fam, cell, noise in screen for m in ("off24000", "on24000")
             for seed in (1001, 1002, 1003, 1004)]
    assert (len(jobs), len(a), len(screen), len(extra)) == (555, 45, 96, 768)
    startup = {
        "smoke": {"evaluator": "q_eval_cmdr.py", "checkpoint": "p20000", "cells": "all_11", "episodes": 10, "small": True, "yaml": "none"},
        "ka_orig": {"evaluator": "q_eval.py", "checkpoint": "p20000", "cells": "stop03", "episodes": 100, "small": True, "yaml": "none"},
        "ka_copy": {"evaluator": "q_eval_cmdr.py", "checkpoint": "p20000", "cells": "stop03", "episodes": 100, "small": True, "yaml": "none"},
        "ka_orig2": {"evaluator": "q_eval.py", "checkpoint": "p20000", "cells": "stop03", "episodes": 100, "small": True, "yaml": "none"},
        "ka_copy_default_buffers": {"evaluator": "q_eval_cmdr.py", "checkpoint": "p20000", "cells": "stop03", "episodes": 100, "small": False, "yaml": "none"},
        "wrong_yaml_other_run": {"evaluator": "q_eval_cmdr.py", "checkpoint": "off24000", "cells": "stop03", "episodes": 10, "small": True, "yaml": "other_run"},
        "wrong_yaml_sibling": {"evaluator": "q_eval_cmdr.py", "checkpoint": "off24000", "cells": "stop03", "episodes": 10, "small": True, "yaml": "sibling"},
        "branch_off24000": {"evaluator": "q_eval_cmdr.py", "checkpoint": "off24000", "cells": "stop03", "episodes": 10, "small": True, "yaml": "parent"},
        "branch_on24000": {"evaluator": "q_eval_cmdr.py", "checkpoint": "on24000", "cells": "stop03", "episodes": 10, "small": True, "yaml": "parent"},
    }
    paths = {"data": ROOT / "cand/data", "reports": ROOT / "cand/reports", "work": ROOT / "cand/work",
             "attempts": ROOT / "cand/attempts", "registry": ROOT / "cand/registry/isaac_usd_registry_v3.json",
             "convert_lock": ROOT / "cand/locks/isaac_convert.lock", "run_lease": ROOT / "cand/locks/isaac_run.lock",
             "slot_records": ROOT / "cand/slot_records", "stop": ROOT / "cand/STOP",
             "logs": ROOT / "cand/logs", "compare_report": ROOT / "cand/reports/bundle_compare.json"}
    contract = {
        "experiment": "cmdr_s1043_pair_eval", "train_seed": 1043,
        "parent": inputs["parent_model"], "branches": branches, "inputs": inputs,
        "input_note": "env.yaml은 현재 Go2EnvCfg와 비교하는 용도이며 설정 전체를 복원하지 않는다",
        "evaluation": {"difficulty": 0.5, "terrain_set": "train", "heading_hold": 0.0,
                       "policy": "student", "run_envs": 100, "episodes": 100,
                       "seeds": [1000, 1001, 1002, 1003, 1004],
                       "target_noise": "on", "flat_control_noise": "off",
                       "noise_meaning": "obs_noise preserves Go2EnvCfg policy and single_obs corruption; false disables both",
                       "history": "Go2EnvCfg source hash and q_eval_cmdr output fingerprints required",
                       "commands": {"stop03": {"vector": [0.3, 0, 0], "duration_s": 10, "switch_s": 5},
                                    "fwd01": {"vector": [0.1, 0, 0], "duration_s": 20, "switch_s": None},
                                    "fwd02": {"vector": [0.2, 0, 0], "duration_s": 20, "switch_s": None}},
                       "all_cell_names": CELLS,
                       "timing": {"physics_dt": 0.005, "policy_dt": 0.02,
                                  "episode_id_layout": "e_idx % E; family=floor(e_idx/(C*E)); cell=floor((e_idx%(C*E))/E)"},
                       "reset": {"origin_xy_m": [-0.5, 0.5], "origin_z_m": [0, 0.2],
                                 "joints": "default pose scale 1.0", "body_velocity": [0, 0, 0, 0, 0, 0],
                                 "yaw": "fixed per command; linear commands point toward world +x",
                                 "spawn_offset": "", "spawn_offset_meaning": "no separate forward offset",
                                 "rng": "u.reset(seed=eval_seed); original q_eval_cmdr.py controls consumption",
                                 "physics_randomization": "push events off; other changes pinned by q evaluator and Go2EnvCfg"},
                       "terrain": "mesh/origins/initial state pinned by q evaluator and configuration source hashes; verify output fingerprints",
                       "ordering": "action/joint order and observation history from q evaluator meta and output fingerprint",
                       "metrics": ["span_q2", "span_q1a", "span_q1"],
                       "missing_nonfinite": "invalid, never zero or dropped from denominator",
                        "mae_missing_policy": "invalidate_entire_run",
                       "mae_parent_zero": "retain original absolute threshold, no division by zero",
                       "selection_boundary": "on-off point estimate <= -5 percentage points",
                       "ci_boundary": "Tango 95% bounds, three lower bounds > 0 and equal-cell mean >= 10 percentage points"},
        "plan": {"order": ["A", "B", "selective_remeasure"], "A": a, "base": jobs,
                 "B_remaining": [j for j in jobs if j not in a], "screen_cells": screen,
                 "extra_possible": extra, "first_release": "A_only", "B_enabled": False,
                 "remeasure_enabled": False, "A_reuse": "same base log next attempt, revalidate all 45",
                 "budget_runs": {"A": 45, "base": 555, "B_remaining": 510, "extra_max": 768},
                 "partial_report": "record complete, invalid, missing and STOP/deadline reason; no adoption verdict"},
        "paths": {k: str(v) for k, v in paths.items()},
        "deployment": {"candidate_dir": str(ROOT / "cand"), "source_eval": str(EVAL),
                       "layout": "single-directory", "write_root": str(ROOT)},
        "startup_tests": {"tag_prefix": "cq_test_", "suffixes": startup,
                          "smoke_cells": ["stand", "stop03", "fwd01", "fwd02", "fwd03", "fwd05", "back03", "left03", "right03", "yawL05", "yawR05"],
                          "common": {"family": "flat", "eval_seed": 1000, "obs_noise": True,
                                     "policy": "student", "difficulty": 0.5, "terrain_set": "train",
                                     "heading_hold": 0, "spawn_offset": ""},
                          "other_run_yaml": str(PROJECT / "logs/rsl_rl/go2_moe_cts/2026-10-11_12-39-32_e2_seed43_n8192/params/env.yaml")},
        "diagnostic": {"tag_prefix": "cq_diag_", "checkpoint": "p20000", "family": "flat",
                       "cell": "stop03", "eval_seed": 1000, "episodes": 100,
                       "runs": {"orig": {"evaluator": "q_eval.py", "small": True},
                                "small": {"evaluator": "q_eval_cmdr.py", "small": True},
                                "default": {"evaluator": "q_eval_cmdr.py", "small": False},
                                "orig_repeat": {"evaluator": "q_eval.py", "small": True, "optional": True}}},
        "tag": {"prefix": "cq", "grammar": "cq_<model>_<family>_<cell>_<noise>_s<seed>",
                "owner": "one base log per attempt; no duplicate tags in post inputs"},
        "device": {"gpu_index": UNDECIDED, "gpu_uuid": UNDECIDED,
                   "min_free_mib": 4096, "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
                   "CUDA_VISIBLE_DEVICES": UNDECIDED, "child_logical_cuda": 0,
                   "expect_conversions": "1", "slot": "v3", "registry": "v3 dedicated",
                   "convert_lock": "shared with participating v3 tools", "run_lease": "separate from conversion lock, held through child tree exit",
                   "nonparticipant_isaac": "refuse launch"},
        "runtime": {"python": sys.executable, "python_version": platform.python_version(),
                    "numpy": np.__version__, "numpy_file": np.__file__,
                    "torch": UNDECIDED, "isaac": UNDECIDED},
        "reporting": {"claim": "학습 seed 1043의 평지 목표 세 칸, 24,000 on−off 결합 판정. 부모 대비 별도 표시. 회귀 범위 3/99 칸 측정, 나머지 96 칸 및 22,000 미평가",
                      "no_seed_pooling": True, "no_1000_independent_episodes_claim": True}
    }
    manifest = {"schema": "s1043-candidate-1", "contract": contract,
                "contract_sha256": canonical_hash(contract),
                 "execution": {"contract_sha256": canonical_hash(contract), "attempt": UNDECIDED,
                               "stage": UNDECIDED, "CUDA_VISIBLE_DEVICES": UNDECIDED,
                               "diagnostic_repeat_original": UNDECIDED,
                              "gpu_index": UNDECIDED, "gpu_uuid": UNDECIDED,
                              "deadline_epoch": UNDECIDED, "approval_path": UNDECIDED,
                              "approval_sha256": UNDECIDED, "risk_limit": UNDECIDED,
                              "run_lease_participants_confirmed": UNDECIDED,
                              "convert_lock_shared_confirmed": UNDECIDED,
                              "candidate_hashes": UNDECIDED,
                              "comparison_report_sha256": UNDECIDED}}
    out = ROOT / "cand/manifest_s1043.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("manifest", out, "contract_sha256", manifest["contract_sha256"])


if __name__ == "__main__":
    build()
