"""Named 17r input mutations. CAUGHT is printed only for a matching guard result."""
import copy
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from s1043_manifest import check_inputs, launch_errors
from frozen_exec_s1043 import command_errors
from test_17r_b import make


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    m, digest = make(0)
    normal = launch_errors(m, approved_digest=digest, require_files=False)
    if normal:
        raise AssertionError(f"normal launch contract failed before mutations: {normal}")
    c = m["contract"]
    a = copy.deepcopy(m)
    a["execution"]["stage"] = "A"
    model, fam, cell, noise, seed = c["plan"]["A"][0]
    tag = f"cq_{model}_{fam}_{cell}_{noise}_s{seed}"
    py = c["runtime"]["python"]
    path = c["inputs"]
    q = [py, path["source_q_eval_cmdr.py"]["path"], "--headless", "--tag", tag,
         "--policy", "student", "--checkpoint", c["parent"]["path"], "--outdir", c["paths"]["data"],
         "--families", fam, "--cells", cell, "--episodes", "100", "--eval_seed", str(seed),
         "--difficulty", "0.5", "--terrain_set", "train", "--heading_hold", "0", "--spawn_offset", "",
         "--physx_small_buffers", "--obs_noise"]
    base = [py, path["source_gpu_guard.py"]["path"], "--gpu", "0", "--min_free_mib", "4096",
            "--log", str(Path(c["paths"]["data"]) / f"{tag}.log"),
            "--summary", str(Path(c["paths"]["data"]) / f"{tag}.guard.json"), "--",
            py, path["source_usd_isolate_run_v3.py"]["path"]] + q[1:]
    if command_errors(a, model, base):
        raise AssertionError("normal complete argv rejected")
    print("NORMAL PASS launch and complete argv", flush=True)
    results = []
    def caught(name, want, got):
        exact = any(want in item for item in got)
        results.append({"name": name, "want": want, "got": got, "caught": exact})
        print(("CAUGHT" if exact else "FAILED"), name, "want", want, "got", got, flush=True)
        if not exact:
            raise AssertionError(name)
    bad = copy.deepcopy(m)
    bad["execution"]["gpu_index"] = "0"
    caught("GPU index string", "execution gpu_index invalid", launch_errors(bad, approved_digest=digest, require_files=False))
    bad = copy.deepcopy(m)
    bad["execution"]["candidate_hashes"] = "yes"
    caught("candidate hashes scalar", "execution candidate_hashes invalid", launch_errors(bad, approved_digest=digest, require_files=False))
    bad = copy.deepcopy(m)
    bad["execution"]["run_lease_participants_confirmed"] = "no"
    caught("confirmation scalar", "execution run_lease_participants_confirmed not confirmed", launch_errors(bad, approved_digest=digest, require_files=False))
    bad = copy.deepcopy(m)
    bad["execution"]["risk_limit"]["max_child_launches"] += 1
    caught("approval risk binding", "approval contract mismatch", launch_errors(bad, approved_digest=digest, require_files=False))
    bad = copy.deepcopy(m)
    bad["execution"]["candidate_hashes"]["frozen_exec_s1043.py"] = "0" * 64
    caught("candidate code digest", "candidate hash frozen_exec_s1043.py", launch_errors(bad, approved_digest=digest, require_files=False))
    bad = copy.deepcopy(m)
    bad["execution"]["CUDA_VISIBLE_DEVICES"] = "1"
    caught("execution CUDA selection", "device CUDA_VISIBLE_DEVICES undecided or inconsistent", launch_errors(bad, approved_digest=digest, require_files=False))
    bad = copy.deepcopy(m)
    bad["contract"]["paths"]["run_lease"] = bad["contract"]["paths"]["convert_lock"].upper()
    caught("conversion and run same file", "conversion lock or run lease contract", check_inputs(bad, require_files=False))
    bad = copy.deepcopy(m)
    bad["contract"]["evaluation"]["reset"]["origin_xy_m"] = [-9, 9]
    caught("reset XY nine metres", "reset contract differs from pinned q", check_inputs(bad, require_files=False))
    bad = copy.deepcopy(m)
    bad["contract"]["deployment"]["candidate_dir"] = str(ROOT / "wrong")
    caught("candidate layout", "deployment layout or source root", check_inputs(bad, require_files=False))
    caught("duplicate outdir", "complete child argv differs", command_errors(a, model, base + ["--outdir", "C:/isaac/ext/go2_rl_robotlab/_eval/out"]))
    wrong_tag = "cq_test_deadbeef_g0t123456p123_unregistered"
    wrong = [wrong_tag if x == tag else x for x in base]
    caught("startup tag not registered", "tag outside registered startup tests", command_errors(a, model, wrong))
    caught("diagnostic forbids A", "A job outside A stage", command_errors(m, model, base))
    out = ROOT / "fixture_17r_mutants" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps({"normal": True, "cases": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MUTANTS", len(results), "independent named inputs", flush=True)


if __name__ == "__main__":
    main()
