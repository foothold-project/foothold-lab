"""CPU-only diagnostic registration and three-run routing probes."""
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
from frozen_exec_s1043 import command_errors
from test_17r_b import make


def check(label, ok):
    print(("PASS" if ok else "FAIL"), label, flush=True)
    if not ok:
        raise AssertionError(label)


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    m, _ = make(0)
    c = m["contract"]
    driver = HERE / "cmdr_eval_driver_s1043.py"
    old = sys.argv
    try:
        sys.argv = [str(driver), "--manifest", str(HERE / "manifest_s1043.json"),
                    "--expect_self_sha", sha256(driver), "--cpu_plan"]
        ns = runpy.run_path(str(driver), run_name="diagnostic_cpu_probe")
    finally:
        sys.argv = old
    for key, item in c["diagnostic"]["runs"].items():
        tag = f"cq_diag_deadbeef_g0t123456p123_{key}"
        q = ns["q"](item["evaluator"], tag, c["parent"]["path"], "flat", "stop03", 100, True, 1000,
                    small=item["small"])
        out = Path(c["paths"]["data"])
        cmd = [c["runtime"]["python"], c["inputs"]["source_gpu_guard.py"]["path"], "--gpu", "0",
               "--min_free_mib", "4096", "--log", str(out / f"{tag}.log"),
               "--summary", str(out / f"{tag}.guard.json"), "--",
               c["runtime"]["python"], c["inputs"]["source_usd_isolate_run_v3.py"]["path"]] + q[1:]
        check("diagnostic " + key, (command_errors(m, "p20000", cmd) == []) == (key != "orig_repeat"))
        if key == "orig_repeat":
            repeat = copy.deepcopy(m)
            repeat["execution"]["diagnostic_repeat_original"] = True
            check("diagnostic repeat prebudget", command_errors(repeat, "p20000", cmd) == [])
    a_tag = "cq_p20000_flat_stop03_on_s1000"
    q = ns["q"]("q_eval_cmdr.py", a_tag, c["parent"]["path"], "flat", "stop03", 100, True, 1000)
    out = Path(c["paths"]["data"])
    cmd = [c["runtime"]["python"], c["inputs"]["source_gpu_guard.py"]["path"], "--gpu", "0",
           "--min_free_mib", "4096", "--log", str(out / f"{a_tag}.log"),
           "--summary", str(out / f"{a_tag}.guard.json"), "--",
           c["runtime"]["python"], c["inputs"]["source_usd_isolate_run_v3.py"]["path"]] + q[1:]
    check("diagnostic refuses A tag", bool(command_errors(m, "p20000", cmd)))
    g = ns["main_diagnostic"].__globals__
    fixture = ROOT / "fixture_17r_d" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    data = fixture / "data"
    reports = fixture / "reports"
    data.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    c = copy.deepcopy(c)
    c["paths"]["data"] = str(data)
    c["paths"]["reports"] = str(reports)
    g["CONTRACT"] = c
    g["MANIFEST"] = m
    g["OUT"] = str(data)
    g["LOGF"] = str(data / "diag_fake.json")
    g["ATTF"] = str(data / "diag_fake.attempt.json")
    g["P0"] = {"q_eval.py": "0" * 64}
    g["LOG"]["ckpt"]["p20000"] = {"sha256": c["parent"]["sha256"]}
    g["ATTEMPT"] = "cpu-diagnostic-probe"
    g["PUBLISH"][0] = False
    seen = []
    mismatch = {"on": False}
    def guarded(tag, cmd, ck=None):
        seen.append(tag)
        d = data / tag
        d.mkdir(parents=True, exist_ok=True)
        (d / "cells.json").write_text('{"pass":false}' if mismatch["on"] and tag.endswith("_small") else '{"pass":true}', encoding="utf-8")
        (d / "traj.npz").write_bytes(b"same synthetic trajectory")
        (d / "meta.json").write_text(json.dumps({"terrain_mesh": {"flat": "mesh"},
            "terrain_origins_sha256": "fake", "pairing_sha256": {"flat": "fake"},
            "eval_changes": ["reset pinned"], "args": {"families": "flat", "cells": "stop03",
            "episodes": 100, "eval_seed": 1000, "spawn_offset": "", "physx_small_buffers": "--physx_small_buffers" in cmd}}), encoding="utf-8")
        (data / f"{tag}.guard.json").write_text(json.dumps({"max_used_mib": 100, "min_free_mib": 5000,
            "exit_code": 0, "stopped_by_guard": False}), encoding="utf-8")
        g["TRIES"][tag] = [{"s": 1, "gpu_preflight": {"gpu_index": "0", "free_mib": 5000}}]
        return 0, 1
    g["guarded"] = guarded
    g["validate"] = lambda *args, **kwargs: ""
    g["main_diagnostic"]()
    path = reports / "diagnostic_cpu-diagnostic-probe.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    check("three distinct q runs", len(seen) == 3 and len(set(seen)) == 3)
    check("diagnostic completed before A", report["status"] == "completed" and report["A_started"] is False)
    check("semantic and byte comparisons", all(v["semantic_equal"] and v["json_sha_equal"] and v["traj_sha_equal"]
                                               for v in report["comparisons"].values()))
    seen.clear()
    mismatch["on"] = True
    g["ATTEMPT"] = "cpu-diagnostic-mismatch"
    g["P0"] = {"q_eval.py": "1" * 64}
    m["execution"]["diagnostic_repeat_original"] = True
    g["MANIFEST"] = m
    try:
        g["main_diagnostic"]()
    except SystemExit as exc:
        check("diagnostic mismatch held", exc.code == 3)
    else:
        check("diagnostic mismatch held", False)
    report = json.loads((reports / "diagnostic_cpu-diagnostic-mismatch.json").read_text(encoding="utf-8"))
    check("repeat uses approved budget", len(seen) == 4 and "orig_repeat" in report["runs"])
    check("mismatch never auto A", report["status"] == "held_mismatch" and report["A_started"] is False)
    # Exercise the real main dispatch with launch and start replaced by CPU test doubles.
    called = []
    g["args"].cpu_plan = False
    g["args"].log = "diag_cpu_route"
    g["launch_errors"] = lambda *args, **kwargs: []
    g["start"] = lambda: called.append("start")
    g["main_diagnostic"] = lambda: called.append("diagnostic")
    g["main_base"] = lambda: called.append("A")
    g["main"]()
    check("main dispatch diagnostic only", called == ["start", "diagnostic"])


if __name__ == "__main__":
    main()
