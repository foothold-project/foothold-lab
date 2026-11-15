"""CPU-only common fingerprint, whole-cost and repeat-state report probes."""
import copy
import json
import os
from pathlib import Path
import runpy
import sys
import time

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from s1043_manifest import sha256
from test_17r_b import make


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label, flush=True)
    if not condition:
        raise AssertionError(label)


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    driver = HERE / "cmdr_eval_driver_s1043.py"
    old = sys.argv
    try:
        sys.argv = [str(driver), "--manifest", str(HERE / "manifest_s1043.json"),
                    "--expect_self_sha", sha256(driver), "--cpu_plan"]
        g = runpy.run_path(str(driver), run_name="diagnostic_contract_17t_probe")["main_diagnostic"].__globals__
    finally:
        sys.argv = old
    m, _ = make(0)
    fixture = ROOT / "fixture_17t_diagnostic" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    fixture.mkdir(parents=True, exist_ok=False)
    base_fp = {k: "same physical evidence" for k in g["COMMON_FINGERPRINT_KEYS"]}
    base_fp["eval_changes"] = ["small buffer"]
    same = {"orig": {"status": "valid", "fingerprint": base_fp},
            "small": {"status": "valid", "fingerprint": dict(base_fp, eval_changes=["cmdr source"])},
            "default": {"status": "valid", "fingerprint": dict(base_fp, eval_changes=["default buffer"])}}
    check("intended source and buffer differences excluded",
          g["diagnostic_common_fingerprint"](same)["equal"] is True)
    changed = copy.deepcopy(same)
    changed["small"]["fingerprint"]["env_origins"] = "changed initial layout"
    result = g["diagnostic_common_fingerprint"](changed)
    check("common fingerprint mismatch names key", result["equal"] is False and
          result["mismatches"]["orig_vs_small"] == ["env_origins"])

    def scenario(name, *, mismatch=False, repeat=False, missing_fp=False, failed=False):
        folder = fixture / name
        data, reports = folder / "data", folder / "reports"
        data.mkdir(parents=True)
        reports.mkdir()
        local = copy.deepcopy(m)
        c = local["contract"]
        c["paths"]["data"] = str(data)
        c["paths"]["reports"] = str(reports)
        local["execution"]["diagnostic_repeat_original"] = repeat
        g["CONTRACT"] = c
        g["MANIFEST"] = local
        g["OUT"] = str(data)
        g["LOGF"] = str(data / "diagnostic.json")
        g["ATTEMPT"] = name
        g["ATTEMPT_START"] = time.time() - 2
        g["P0"] = {"q_eval.py": name}
        g["LOG"]["ckpt"]["p20000"] = {"sha256": c["parent"]["sha256"]}
        g["PUBLISH"][0] = False
        def guarded(tag, cmd, ck=None):
            d = data / tag
            d.mkdir()
            (d / "cells.json").write_text('[{"name":"stop03"}]', encoding="utf-8")
            (d / "traj.npz").write_bytes(b"same trajectory")
            (d / "meta.json").write_text(json.dumps({"terrain_mesh": [["flat"]],
                 "terrain_origins_sha256": "same", "pairing_sha256": {"same": "same"},
                 "eval_changes": ["small buffer"], "args": {"families": "flat", "cells": "stop03",
                 "episodes": 100, "eval_seed": 1000, "spawn_offset": "", "physx_small_buffers": "--physx_small_buffers" in cmd}}), encoding="utf-8")
            (data / f"{tag}.guard.json").write_text(json.dumps({"max_used_mib": 6000,
                "min_free_mib": 4000, "exit_code": 0, "stopped_by_guard": False}), encoding="utf-8")
            g["TRIES"][tag] = [{"try": 1, "s": 0, "elapsed_s": 0.01,
                                 "gpu_preflight": {"free_mib": 8192}}]
            time.sleep(.02)
            return (1 if failed and tag.endswith("_orig") else 0), 1
        g["guarded"] = guarded
        g["validate"] = lambda *a, **kw: ""
        def fingerprint(tag):
            if missing_fp and tag.endswith("_orig"):
                raise FileNotFoundError("env_origins.npy")
            fp = copy.deepcopy(base_fp)
            if mismatch and tag.endswith("_small"):
                fp["env_origins"] = "changed initial layout"
            return fp
        g["fingerprint"] = fingerprint
        try:
            g["main_diagnostic"]()
        except SystemExit as ex:
            check(name + " expected hold rc", ex.code == 3)
        return json.loads((reports / f"diagnostic_{name}.json").read_text(encoding="utf-8"))

    normal = scenario("normal")
    check("normal complete and no repeat needed", normal["status"] == "completed" and
          normal["repeat_status"] == "repeat_not_needed" and normal["common_fingerprint"]["equal"] is True)
    check("total wall includes startup and all try costs", normal["runs"]["orig"]["total_wall_s"] >= 2 and
          normal["runs"]["orig"]["try_wall_s_sum"] > 0 and
          normal["runs"]["orig"]["wall_s_scope"] == "last_try_only" and
          normal["runs"]["orig"]["last_try_wall_s"] == normal["runs"]["orig"]["wall_s"] and
          normal["runs"]["orig"]["startup_allocated_s"] >= 2)
    mismatch = scenario("mismatch", mismatch=True)
    check("common mismatch held with item", mismatch["status"] == "held_common_fingerprint" and
          mismatch["common_fingerprint"]["mismatches"]["orig_vs_small"] == ["env_origins"] and
          mismatch["repeat_status"] == "repeat_not_approved")
    repeated = scenario("repeated", mismatch=True, repeat=True)
    check("approved repeat ran but common mismatch held", repeated["status"] == "held_common_fingerprint" and
          repeated["repeat_status"] == "repeat_ran" and
          repeated["runs"]["orig_repeat"]["status"] == "valid" and
          repeated["runs"]["orig_repeat"]["total_wall_s"] is not None)
    incomplete = scenario("incomplete", missing_fp=True)
    check("missing fingerprint blocks final completion", incomplete["status"] == "held_incomplete" and
          incomplete["runs"]["orig"]["status"] == "held" and
          incomplete["not_run"] == ["small", "default"] and
          incomplete["repeat_status"] == "repeat_not_needed" and
          incomplete["repeat_reason"] == "base_incomplete")
    failure = scenario("failure", failed=True)
    check("failed run distinct from held and not-run", failure["status"] == "held_incomplete" and
          failure["failed_runs"] == ["orig"] and failure["not_run"] == ["small", "default"])


if __name__ == "__main__":
    main()
