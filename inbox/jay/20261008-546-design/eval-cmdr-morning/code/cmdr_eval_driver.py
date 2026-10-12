# CMD-R morning evaluation driver (lead, 2026-10-12 night; plan from VERIFY-astra-7 section 2). GPU 1 only, no training.
#   evaluator : q_eval_cmdr.py = q_eval.py @717325a7 (the version ASTRA 7 read) + --train_yaml for branch checkpoints
#               + loaded-iter check. Frozen for all five checkpoints; its sha256 is written in the driver log.
#   models    : parent E1 model_20000, off/on model_22000 and model_24000 (saved by branch_run.py in out/branch/<tag>/)
#   runs      : one family x one cell x 100 episodes (100 envs), student, difficulty 0.5, eval seed 1000, heading hold 0,
#               centre start. Main analysis: observation noise ON (as in training). Noise OFF afterwards (diagnosis).
#   order     : tests first (smoke 110 env, known answer against q_eval.py, branch path break/pass), then
#               flat (stop03 fwd01 fwd02 stand fwd03 fwd05 back03 left03 right03 yawL05 yawR05) for every model as it
#               becomes ready, then the other seven training families, then flat noise off.
#   waits     : starts after the UNSEEN driver (unseen_driver.py) has exited, so two Isaac processes never share GPU 1.
#               A checkpoint is ready when it exists, is 26,367,183 B and unchanged for 120 s.
# Every run is under gpu_guard.py --gpu 1 --min_free_mib 4096 (ASTRA 7: not the night training's 256).
# Usage: python cmdr_eval_driver.py [--until "2026-10-13 14:00"]
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
OUT = os.path.join(HERE, "out")
B = os.path.join(OUT, "branch")
E1 = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192"
E2 = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-11_12-39-32_e2_seed43_n8192"
E1_YAML = f"{E1}/params/env.yaml"
MODELS = {"p20000": f"{E1}/model_20000.pt",
          "off22000": f"{B}/cmdr_s1042_off_u4000/model_22000.pt",
          "off24000": f"{B}/cmdr_s1042_off_u4000/model_24000.pt",
          "on22000": f"{B}/cmdr_s1042_on_u4000/model_22000.pt",
          "on24000": f"{B}/cmdr_s1042_on_u4000/model_24000.pt"}
CELLS = ["stop03", "fwd01", "fwd02", "stand", "fwd03", "fwd05", "back03", "left03", "right03", "yawL05", "yawR05"]
FAMILIES = ["flat", "obstacles", "rough_slope", "slope_up", "slope_down", "stairs_up", "stairs_down", "wave"]
CKPT_BYTES = 26367183
ENV = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES="1", OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1")
LOGF = os.path.join(OUT, "cmdr_eval_driver.json")
LOG = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "evaluator": {}, "tests": {}, "runs": [], "skipped": [], "ckpt": {}}


def save():
    json.dump(LOG, open(LOGF, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def say(s):
    print(f"{time.strftime('%H:%M:%S')} {s}", flush=True)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def unseen_running():
    me = os.getpid()
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            if p.info["pid"] != me and p.info["cmdline"] and any("unseen_driver.py" in c for c in p.info["cmdline"]):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def ready(m):
    p = MODELS[m]
    if not os.path.exists(p):
        return False
    st = os.stat(p)
    if st.st_size != CKPT_BYTES or time.time() - st.st_mtime < 120:
        return False
    if m not in LOG["ckpt"]:
        LOG["ckpt"][m] = {"path": p, "sha256": sha(p), "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))}
        save()
    return True


def guarded(name, cmd, tries=4, wait_s=300):
    for k in range(1, tries + 1):
        t0 = time.time()
        rc = subprocess.run([PY, "gpu_guard.py", "--gpu", "1", "--min_free_mib", "4096", "--log", f"out/{name}.log",
                             "--summary", f"out/{name}.guard.json", "--"] + cmd, cwd=HERE, env=ENV).returncode
        say(f"RUN {name} try {k} EXIT {rc} {time.time() - t0:.0f}s")
        if rc == 0:
            return 0, k
        if rc == 99:
            say(f"GUARD STOP {name}: free < 4096 MiB on GPU 1, waiting {wait_s}s")
            time.sleep(wait_s)
        else:
            return rc, k  # a real error is not retried (tests rely on the exit code)
    return rc, tries


def q(script, tag, model_path, fam, cells, episodes, noise, extra=()):
    cmd = [PY, script, "--headless", "--tag", tag, "--policy", "student", "--checkpoint", model_path,
           "--families", fam, "--cells", cells, "--episodes", str(episodes)]
    if noise:
        cmd.append("--obs_noise")
    if not model_path.startswith(E1):
        cmd += ["--train_yaml", E1_YAML]
    return cmd + list(extra)


def done(tag):
    return os.path.exists(os.path.join(OUT, tag, "cells.json"))


def tests():
    # 1. smoke: parent, flat, all 11 cells x 10 episodes = 110 envs (config path, device, noise, loading, recording)
    t = "cq_test_smoke_p20000"
    if not done(t):
        rc, _ = guarded(t, q("q_eval_cmdr.py", t, MODELS["p20000"], "flat", ",".join(CELLS), 10, True))
        LOG["tests"]["smoke"] = rc
        save()
        if rc != 0:
            return False
    # 2. known answer: q_eval.py and q_eval_cmdr.py on the same input must give the same cells.json
    a, b = "cq_test_ka_qeval_p20000_flat_stop03_on", "cq_p20000_flat_stop03_on"
    for tag, script in ((a, "q_eval.py"), (b, "q_eval_cmdr.py")):
        if not done(tag):
            rc, _ = guarded(tag, q(script, tag, MODELS["p20000"], "flat", "stop03", 100, True))
            if rc != 0:
                LOG["tests"]["known_answer"] = f"{tag} exit {rc}"
                save()
                return False
    ca = json.load(open(os.path.join(OUT, a, "cells.json"), encoding="utf-8"))
    cb = json.load(open(os.path.join(OUT, b, "cells.json"), encoding="utf-8"))
    ta, tb = sha(os.path.join(OUT, a, "traj.npz")), sha(os.path.join(OUT, b, "traj.npz"))
    LOG["tests"]["known_answer"] = {"cells_json_same": ca == cb, "traj_npz_same": ta == tb, "traj_sha": [ta[:16], tb[:16]]}
    save()
    if ca != cb or ta != tb:  # QC-E1.md: q_eval re-runs were bitwise identical, so any difference is the copy's
        return False
    # 3. branch path, break then pass: gate_c1/model_20002.pt (parent E1 model_20000)
    g = f"{B}/gate_c1/model_20002.pt"
    t = "cq_test_branch_wrong_yaml"
    cmd = q("q_eval_cmdr.py", t, g, "flat", "stop03", 10, True)
    cmd[cmd.index("--train_yaml") + 1] = f"{E2}/params/env.yaml"
    rc, _ = guarded(t, cmd, tries=1)
    log = open(os.path.join(OUT, f"{t}.log"), encoding="utf-8", errors="replace").read()
    LOG["tests"]["branch_wrong_yaml"] = {"exit": rc, "refused": "train_yaml is not the parent run's" in log}
    save()
    if rc == 0 or "train_yaml is not the parent run's" not in log:
        return False
    t = "cq_test_branch_gate_c1_20002"
    if not done(t):
        rc, _ = guarded(t, q("q_eval_cmdr.py", t, g, "flat", "stop03", 10, True))
        LOG["tests"]["branch_pass"] = rc
        save()
        if rc != 0:
            return False
    m = json.load(open(os.path.join(OUT, t, "meta.json"), encoding="utf-8"))
    LOG["tests"]["branch_pass_meta"] = {"loaded_iter": m.get("loaded_iter"), "has_train_yaml_source": "train_yaml_source" in m}
    save()
    return m.get("loaded_iter") == 20002 and "train_yaml_source" in m


def jobs():
    out = []
    for fam in FAMILIES:
        for m in MODELS:
            for cell in CELLS:
                out.append((m, fam, cell, True))
    for m in MODELS:
        for cell in CELLS:
            out.append((m, "flat", cell, False))
    return out


ap = argparse.ArgumentParser()
ap.add_argument("--until", default="2026-10-13 14:00")
args = ap.parse_args()
deadline = time.mktime(time.strptime(args.until, "%Y-%m-%d %H:%M"))
LOG["evaluator"] = {"q_eval_cmdr.py": sha(os.path.join(HERE, "q_eval_cmdr.py")), "q_eval.py": sha(os.path.join(HERE, "q_eval.py")),
                    "q_metrics.py": sha(os.path.join(HERE, "q_metrics.py")), "gpu_guard.py": sha(os.path.join(HERE, "gpu_guard.py"))}
save()
say(f"evaluator q_eval_cmdr.py {LOG['evaluator']['q_eval_cmdr.py'][:16]}")
while unseen_running():
    if time.time() > deadline:
        say("deadline while waiting for the unseen driver")
        sys.exit(2)
    time.sleep(60)
say("unseen driver not running: GPU 1 is ours")
LOG["gpu1_from"] = time.strftime("%Y-%m-%d %H:%M:%S")
if not tests():
    say(f"TESTS FAILED {LOG['tests']}")
    save()
    sys.exit(3)
say(f"tests passed {LOG['tests']}")
pending = jobs()
while pending and time.time() < deadline:
    pick = next((j for j in pending if ready(j[0])), None)
    if pick is None:
        time.sleep(60)
        continue
    pending.remove(pick)
    m, fam, cell, noise = pick
    tag = f"cq_{m}_{fam}_{cell}_{'on' if noise else 'off'}"
    if done(tag):
        continue
    rc, k = guarded(tag, q("q_eval_cmdr.py", tag, MODELS[m], fam, cell, 100, noise))
    LOG["runs"].append({"tag": tag, "rc": rc, "tries": k, "t": time.strftime("%H:%M:%S")})
    if rc != 0:
        LOG["skipped"].append(tag)
    save()
LOG["ended"] = time.strftime("%Y-%m-%d %H:%M:%S")
LOG["pending_at_end"] = [f"{m}_{f}_{c}_{'on' if n else 'off'}" for m, f, c, n in pending]
save()
say(f"END runs={len(LOG['runs'])} skipped={len(LOG['skipped'])} pending={len(pending)}")
