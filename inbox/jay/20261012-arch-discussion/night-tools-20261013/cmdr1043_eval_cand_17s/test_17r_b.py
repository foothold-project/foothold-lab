"""CPU-only 17r execution gate probes. All generated evidence stays in codexE."""
import copy
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from s1043_manifest import (CANDIDATE_FILES, ROOT, approval_binding, canonical_hash,
                            check_inputs, launch_errors, sha256)
from frozen_exec_s1043 import command_errors


def make(gpu):
    m = json.loads((ROOT / "cand/manifest_s1043.json").read_text(encoding="utf-8"))
    folder = ROOT / "fixture_17r_b" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}" / str(gpu)
    folder.mkdir(parents=True, exist_ok=True)
    c = m["contract"]
    c["paths"]["compare_report"] = str(folder / "comparison.json")
    c["device"].update(gpu_index=gpu, gpu_uuid=f"GPU-FIXTURE-{gpu}", CUDA_VISIBLE_DEVICES=str(gpu))
    c["runtime"].update(torch="fixture", isaac="fixture")
    m["contract_sha256"] = canonical_hash(c)
    (folder / "comparison.json").write_text(json.dumps({"verdict": "SAME", "contract_sha256": m["contract_sha256"]}), encoding="utf-8")
    e = m["execution"]
    e.update(contract_sha256=m["contract_sha256"], stage="diagnostic", gpu_index=gpu,
             gpu_uuid=f"GPU-FIXTURE-{gpu}", CUDA_VISIBLE_DEVICES=str(gpu),
             diagnostic_repeat_original=False,
             deadline_epoch=time.time() + 7200, risk_limit={"max_child_launches": 12,
             "max_retries_per_run": 2, "max_wall_s": 3600}, attempt=f"fixture-{gpu}",
             approval_id=f"fixture-approval-{gpu}", log_name=f"fixture-log-{gpu}",
             restart_scope="single_start_no_reuse",
             termination_policy={"terminate_grace_s": 0.5, "partial_result": "held"},
             comparison_report_sha256=sha256(folder / "comparison.json"),
             candidate_hashes={name: sha256(ROOT / "cand" / name) for name in CANDIDATE_FILES},
             run_lease_participants_confirmed=True, convert_lock_shared_confirmed=True,
             approval_path=str(folder / "approval.json"))
    approval = {"approved": True, "by": "CPU_FIXTURE_ONLY", "approved_at": "fixture",
                "reviewed": approval_binding(m)}
    (folder / "approval.json").write_text(json.dumps(approval, sort_keys=True), encoding="utf-8")
    e["approval_sha256"] = sha256(folder / "approval.json")
    return m, e["approval_sha256"]


def expect(label, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), label, got)
    if not ok:
        raise AssertionError(label)


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    for gpu in (0, 1):
        m, external = make(gpu)
        expect(f"gpu{gpu} valid", launch_errors(m, approved_digest=external, require_files=False), [])
        bad = copy.deepcopy(m)
        bad["execution"]["gpu_index"] = str(gpu)
        expect(f"gpu{gpu} string", any("gpu_index" in x for x in launch_errors(bad, approved_digest=external, require_files=False)), True)
        bad = copy.deepcopy(m)
        bad["execution"]["candidate_hashes"] = "yes"
        expect("hashes scalar", "execution candidate_hashes invalid" in launch_errors(bad, approved_digest=external, require_files=False), True)
        bad = copy.deepcopy(m)
        bad["execution"]["run_lease_participants_confirmed"] = "no"
        expect("confirmation scalar", any("not confirmed" in x for x in launch_errors(bad, approved_digest=external, require_files=False)), True)
        bad = copy.deepcopy(m)
        bad["execution"]["risk_limit"]["max_child_launches"] += 1
        expect("risk approval binding", "approval contract mismatch" in launch_errors(bad, approved_digest=external, require_files=False), True)
        bad = copy.deepcopy(m)
        bad["execution"]["candidate_hashes"]["frozen_exec_s1043.py"] = "0" * 64
        expect("code hash and approval", any("candidate hash" in x for x in launch_errors(bad, approved_digest=external, require_files=False)), True)
        expect("external digest", "approval hash mismatch" in launch_errors(m, approved_digest="0" * 64, require_files=False), True)
        bad = copy.deepcopy(m)
        bad["execution"]["CUDA_VISIBLE_DEVICES"] = str(1 - gpu)
        expect("execution CUDA mismatch", any("CUDA_VISIBLE_DEVICES" in x for x in launch_errors(bad, approved_digest=external, require_files=False)), True)
        bad = copy.deepcopy(m)
        bad["contract"]["paths"]["run_lease"] = bad["contract"]["paths"]["convert_lock"].upper()
        expect("lock alias", "conversion lock or run lease contract" in check_inputs(bad, require_files=False), True)
        if gpu == 0:
            c = m["contract"]
            source = Path("C:/isaac/ext/go2_rl_robotlab/_eval")
            model, fam, cell, noise, seed = c["plan"]["A"][0]
            tag = f"cq_{model}_{fam}_{cell}_{noise}_s{seed}"
            q = [c["runtime"]["python"], c["inputs"]["source_usd_isolate_run_v3.py"]["path"], c["inputs"]["source_q_eval_cmdr.py"]["path"],
                 "--headless", "--tag", tag, "--policy", "student", "--checkpoint", c["parent"]["path"],
                 "--outdir", c["paths"]["data"], "--families", fam, "--cells", cell,
                 "--episodes", "100", "--eval_seed", str(seed), "--difficulty", "0.5",
                 "--terrain_set", "train", "--heading_hold", "0", "--spawn_offset", "",
                 "--physx_small_buffers", "--obs_noise"]
            cmd = [c["runtime"]["python"], c["inputs"]["source_gpu_guard.py"]["path"], "--gpu", "0",
                   "--min_free_mib", "4096", "--log", str(Path(c["paths"]["data"]) / f"{tag}.log"),
                   "--summary", str(Path(c["paths"]["data"]) / f"{tag}.guard.json"), "--"] + q
            command_manifest = copy.deepcopy(m)
            command_manifest["execution"]["stage"] = "A"
            expect("normal command", command_errors(command_manifest, model, cmd), [])
            expect("duplicate outdir", bool(command_errors(command_manifest, model, cmd + ["--outdir", str(source / "out")])), True)
    driver = ROOT / "cand/cmdr_eval_driver_s1043.py"
    saved = sys.argv
    try:
        sys.argv = [str(driver), "--manifest", str(ROOT / "cand/manifest_s1043.json"),
                    "--expect_self_sha", sha256(driver), "--cpu_plan"]
        namespace = runpy.run_path(str(driver), run_name="lease_probe")
    finally:
        sys.argv = saved
    wrapper = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(3)']); time.sleep(.75)"
    started = time.monotonic()
    p = subprocess.Popen([sys.executable, "-B", "-c", wrapper])
    def observe(known, live):
        if time.monotonic() - started > 8:
            import psutil
            detail = {}
            for pid in live:
                try:
                    x = psutil.Process(pid)
                    detail[pid] = (x.name(), x.status(), x.cmdline())
                except psutil.Error as exc:
                    detail[pid] = str(exc)
            raise AssertionError(f"tree did not exit: known={known} live={detail} parent_rc={p.poll()}")
    rc = namespace["wait_child_tree"](p, observer=observe)
    expect("orphan descendant exit", rc == 0 and time.monotonic() - started >= 2.5, True)


if __name__ == "__main__":
    main()
