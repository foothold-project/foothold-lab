"""CPU-only 17s comparison, report-shape and isolated common-path probes."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys
import time

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from s1043_manifest import assert_isolated, sha256

if os.environ.get("S1043_MANIFEST_OVERRIDE"):
    spec = importlib.util.spec_from_file_location("s1043_manifest_mutant", os.environ["S1043_MANIFEST_OVERRIDE"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__file__ = str(HERE / "s1043_manifest.py")
    module.ROOT = ROOT
    assert_isolated = module.assert_isolated


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label, flush=True)
    if not condition:
        raise AssertionError(label)


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    driver = Path(os.environ.get("S1043_DRIVER_OVERRIDE", HERE / "cmdr_eval_driver_s1043.py"))
    old = sys.argv
    try:
        sys.argv = [str(driver), "--manifest", str(HERE / "manifest_s1043.json"),
                    "--expect_self_sha", sha256(driver), "--cpu_plan"]
        g = runpy.run_path(str(driver), run_name="diagnostic_17s_cpu_probe")["diagnostic_record"].__globals__
    finally:
        sys.argv = old
    fixture = ROOT / "fixture_17s_diagnostic" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    fixture.mkdir(parents=True, exist_ok=False)
    g["OUT"] = str(fixture)
    left, right = fixture / "left", fixture / "right"
    left.mkdir()
    right.mkdir()
    (left / "cells.json").write_text('{"a":1,"b":2}', encoding="utf-8")
    (right / "cells.json").write_text('{\n  "b": 2, "a": 1\n}', encoding="utf-8")
    for folder in (left, right):
        (folder / "traj.npz").write_bytes(b"identical fixture trajectory bytes")
    comparison = g["diagnostic_compare_pair"](left, right)
    check("byte-only JSON reason", comparison == {"semantic_equal": True,
          "json_sha_equal": False, "traj_sha_equal": True, "reason_code": "byte_only_json"})
    check("conservative strict hold", not all(comparison[k] for k in
          ("semantic_equal", "json_sha_equal", "traj_sha_equal")))
    (right / "cells.json").write_text('{"a":9,"b":2}', encoding="utf-8")
    check("semantic mismatch distinct", g["diagnostic_compare_pair"](left, right)["reason_code"] ==
          "semantic_mismatch")

    item = {"evaluator": "q_eval.py", "small": True}
    for tag in ("base", "orig_repeat"):
        d = fixture / tag
        d.mkdir()
        (d / "meta.json").write_text(json.dumps({"terrain_mesh": [["mesh"]],
             "terrain_origins_sha256": "fingerprint", "pairing_sha256": {"flat": "fingerprint"},
             "eval_changes": ["reset pinned"], "args": {"families": "flat", "cells": "stop03",
             "episodes": 100, "eval_seed": 1000, "spawn_offset": "", "physx_small_buffers": True}}), encoding="utf-8")
        (d / "cells.json").write_text("[]", encoding="utf-8")
        (d / "traj.npz").write_bytes(b"fixture")
        (fixture / f"{tag}.guard.json").write_text(json.dumps({"max_used_mib": 6000,
             "min_free_mib": 4000, "exit_code": 0, "stopped_by_guard": False}), encoding="utf-8")
        g["TRIES"][tag] = [{"s": 2, "gpu_preflight": {"free_mib": 8192}, "rc": 0}]
    g["fingerprint"] = lambda tag: {"pairing_sha256": "cpu fixture"}
    valid = g["diagnostic_record"]("base", item, "base", 0, 1, "")
    repeat = g["diagnostic_record"]("orig_repeat", item, "orig_repeat", 0, 1, "")
    check("repeat same report fields", set(valid) == set(repeat) and
          repeat["fingerprint"] and repeat["max_used_mib"] == 6000 and
          repeat["preflight"] and repeat["reset"] and repeat["inputs_sha256"] and
          repeat["try_records"])
    failed = g["diagnostic_record"]("failed", item, "missing", 124, 1, "exit 124")
    check("failed report same fields with null evidence", set(valid) == set(failed) and
          failed["status"] == "failed" and failed["max_used_mib"] is None and
          failed["fingerprint"] is None)
    held = g["diagnostic_record"]("held", item, "missing", 0, 1, "validation error")
    check("held distinct from failed", held["status"] == "held")
    check("peak scope labeled", all(x["guard_peak_scope"] == "whole_device_not_job_dedicated"
                                    for x in (valid, repeat, failed, held)))

    m = json.loads((HERE / "manifest_s1043.json").read_text(encoding="utf-8"))
    check("write_root default isolated", bool(assert_isolated(m)))
    source = m["contract"]["deployment"]["source_eval"]
    common = str(Path(source) / "slot" / "isaac_run.lock")
    trial = copy.deepcopy(m)
    trial["contract"]["paths"]["run_lease"] = common
    try:
        assert_isolated(trial)
    except ValueError:
        check("_eval slot without allowlist rejected", True)
    else:
        check("_eval slot without allowlist rejected", False)
    trial["contract"]["deployment"]["common_write_allowlist"] = [{"key": "run_lease", "path": common}]
    check("exact common allowlist accepted", bool(assert_isolated(trial)))
    unlisted = copy.deepcopy(trial)
    unlisted["contract"]["paths"]["run_lease"] = str(Path(source) / "slot" / "other.lock")
    try:
        assert_isolated(unlisted)
    except ValueError:
        check("unlisted common path rejected", True)
    else:
        check("unlisted common path rejected", False)
    partial = copy.deepcopy(trial)
    partial["contract"]["paths"]["run_lease"] = common + ".copy"
    try:
        assert_isolated(partial)
    except ValueError:
        check("substring alias rejected", True)
    else:
        check("substring alias rejected", False)
    alias = copy.deepcopy(trial)
    alias["contract"]["paths"]["run_lease"] = common.upper()
    try:
        assert_isolated(alias)
    except ValueError:
        check("case alias rejected", True)
    else:
        check("case alias rejected", False)
    alias["contract"]["deployment"]["common_write_allowlist"] = [{"key": "run_lease", "path": common.upper()}]
    try:
        assert_isolated(alias)
    except ValueError:
        check("case alias in allowlist rejected", True)
    else:
        check("case alias in allowlist rejected", False)


if __name__ == "__main__":
    main()
