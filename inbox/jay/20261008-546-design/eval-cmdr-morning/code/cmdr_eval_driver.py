# CMD-R morning evaluation driver v2 (lead, 2026-10-13 00:10; plan VERIFY-astra-7 section 2, fixes VERIFY-astra-8).
# GPU 1 only, no training.
#   evaluator : q_eval_cmdr.py = q_eval.py @717325a7 + --train_yaml for branch checkpoints (exact parent params/env.yaml,
#               bundle hashes recorded) + loaded-iter check.
#   pins      : sha256 of the evaluator, metrics, post, guard and the six robot_lab / rsl_rl source files the branch
#               bundle records. Taken at start, re-checked before every run (a change stops the driver, exit 4), written
#               into every run folder (driver_stamp.json). A run counts as done only if its stamp has the current pins
#               and it passes validate(): exit 0 and guard not stopped, cells/meta/episodes/traj parse with the expected
#               shape, args, checkpoint sha256 and loaded iter, GPU 1 UUID, checks_pre / checks_run within limits, finite.
#   models    : parent E1 model_20000, off/on model_22000 and model_24000. A checkpoint is ready when its size and mtime
#               stayed the same over two looks at least 120 s apart; its sha256 is pinned then and re-checked before
#               every run. The on arm also needs a SAME bundle comparison for this pair (cmdr_bundle_compare.py v2).
#   runs      : one family x one cell x 100 episodes (100 envs), student, difficulty 0.5, heading hold 0, centre start.
#               Tag cq_<model>_<family>_<cell>_<noise>_s<seed>.
#   order     : (A) flat 11 cells, noise on, seed 1000  (B) flat stop03 fwd01 fwd02, noise on, seeds 1001-1004
#               (ASTRA 8 3: seed list fixed before results)  (C) other 7 training families, noise on, seed 1000
#               (D) flat 11 cells noise off, seed 1000. The first ready job in this order runs next.
#   pairing   : per (family, cell, noise, seed) group every run is compared with the group's first valid run on the
#               recorded initial state / DR / terrain / layout / device fingerprints and traj[0]. A mismatch marks the
#               run pair_fail (kept on disk, excluded from tables).
#   waits     : starts after the UNSEEN driver (a python process whose argv has unseen_driver.py) has exited.
# Every run is under gpu_guard.py --gpu 1 --min_free_mib 4096. Deadline is checked before every run.
# v3 (00:25, VERIFY-astra-8b): expected cell order follows the evaluator's own order (q_eval ALL_CELLS), episode IDs /
# family / cell per CSV row, T from the cell durations, finite traj (hag may be NaN) and cmd_hist, non-empty fingerprint
# dicts, both bundle hashes + contract + comparator version for the on arm, pins and deadline before every try and
# again before stamping, positive-reaction diagnostics recorded as warnings (not invalid). Every run uses
# --physx_small_buffers (GPU 1 headroom; same for all five models); test 2b checks it is bitwise equal to the default
# buffers on the flat training terrain. q_eval.py is pinned only for the known-answer tests.
# v3.1 (04:30): Isaac Kit exited 0 after the AssertionError in test 3 (wrong train_yaml refused, exit 0). A Python
# traceback in the run log now counts as error 1 in guarded() and as invalid in validate(); test 3 also requires that
# no cells.json / traj.npz was written.
# Usage: python cmdr_eval_driver.py [--until "2026-10-13 14:00"]
import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
OUT = os.path.join(HERE, "out")
B = os.path.join(OUT, "branch")
E1 = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192"
E2 = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-11_12-39-32_e2_seed43_n8192"
E1_YAML = f"{E1}/params/env.yaml"
GPU1_UUID = "315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f"
MODELS = {"p20000": (f"{E1}/model_20000.pt", 20000),
          "off22000": (f"{B}/cmdr_s1042_off_u4000/model_22000.pt", 22000),
          "off24000": (f"{B}/cmdr_s1042_off_u4000/model_24000.pt", 24000),
          "on22000": (f"{B}/cmdr_s1042_on_u4000/model_22000.pt", 22000),
          "on24000": (f"{B}/cmdr_s1042_on_u4000/model_24000.pt", 24000)}
CELLS = ["stop03", "fwd01", "fwd02", "stand", "fwd03", "fwd05", "back03", "left03", "right03", "yawL05", "yawR05"]
TARGETS = ["stop03", "fwd01", "fwd02"]
FAMILIES = ["flat", "obstacles", "rough_slope", "slope_up", "slope_down", "stairs_up", "stairs_down", "wave"]
EXT_SEEDS = [1001, 1002, 1003, 1004]
CKPT_BYTES = 26367183
PIN_FILES = ["q_eval_cmdr.py", "q_metrics.py", "q_post.py", "gpu_guard.py", "cmdr_bundle_compare.py"]
# the evaluator keeps its own ALL_CELLS order whatever order --cells gives (q_eval_cmdr.py ALL_CELLS)
EVAL_ORDER = ["stand", "stop03", "fwd01", "fwd02", "fwd03", "fwd05", "fwd10", "back03", "left03", "right03", "yawL05", "yawR05"]
DUR_S = {"stand": 10.0, "stop03": 10.0}  # every other cell 20 s (q_eval_cmdr.py ALL_CELLS)
P0, DEADLINE = None, None


def in_eval_order(cells):
    return [c for c in EVAL_ORDER if c in cells]
ENV = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES="1", OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1")
LOGF = os.path.join(OUT, "cmdr_eval_driver.json")
LOG = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "pins": {}, "tests": {}, "runs": [], "skipped": [], "pair_fail": [],
       "ckpt": {}, "matrix": {}}


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


def pins():
    p = {f: sha(os.path.join(HERE, f)) for f in PIN_FILES}
    code = json.load(open(os.path.join(B, "cmdr_s1042_off_u4000", "bundle.json"), encoding="utf-8"))["meta"]["code"]["files_sha256"]
    for rel, recorded in code.items():
        now = sha(os.path.join(ROOT, rel))
        assert now == recorded, f"source {rel} differs from the branch bundle record"
        p[rel] = now
    return p


def unseen_running():
    for pr in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            c = pr.info["cmdline"] or []
            if (pr.info["name"] or "").lower().startswith("python") and any(os.path.basename(x) == "unseen_driver.py" for x in c):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


SEEN = {}


def ready(m):
    p, _ = MODELS[m]
    if not os.path.exists(p):
        return False
    st = os.stat(p)
    key = (st.st_size, st.st_mtime_ns)
    first = SEEN.setdefault(m, (key, time.time()))
    if first[0] != key:
        SEEN[m] = (key, time.time())
        return False
    if st.st_size != CKPT_BYTES or time.time() - first[1] < 120:
        return False
    if m.startswith("on"):
        rep = os.path.join(B, "cmdr_bundle_compare__cmdr_s1042_off_u4000__cmdr_s1042_on_u4000.json")
        if not os.path.exists(rep):
            return False
        r = json.load(open(rep, encoding="utf-8"))
        d = os.path.join(B, "cmdr_s1042_on_u4000")
        do = os.path.join(B, "cmdr_s1042_off_u4000")
        now = {"off_json": sha(os.path.join(do, "bundle.json")), "off_npz": sha(os.path.join(do, "bundle.npz")),
               "on_json": sha(os.path.join(d, "bundle.json")), "on_npz": sha(os.path.join(d, "bundle.npz"))}
        con = r.get("contract", {})
        if r.get("verdict") != "SAME" or r.get("bundle_sha256") != now or con.get("envs") != 8192 or con.get("updates") != 4000 \
                or con.get("gate") is not False or r.get("tool_sha256") != P0["cmdr_bundle_compare.py"]:
            LOG["ckpt"].setdefault(m, {})["blocked"] = "bundle comparison not SAME for the current on bundle"
            save()
            return False
    if "sha256" not in LOG["ckpt"].get(m, {}):
        LOG["ckpt"][m] = {"path": p, "sha256": sha(p), "pinned_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        save()
    return True


def py_traceback(name):
    """True if out/<name>.log holds a Python traceback. Isaac Kit can exit 0 after an uncaught exception (04:21 test 3:
    AssertionError in the log, exit 0), so the exit code alone does not tell a refused or crashed run from a good one.
    Checked on the 586 logs in out/ at 04:30: the 5 with a traceback are all failed runs, none of the others has one."""
    try:
        with open(os.path.join(OUT, f"{name}.log"), encoding="utf-8", errors="replace") as f:
            return "Traceback (most recent call last)" in f.read()
    except FileNotFoundError:
        return False


def guarded(name, cmd, tries=4, wait_s=300):
    rc = None
    for k in range(1, tries + 1):
        if time.time() > DEADLINE:
            say(f"DEADLINE before {name}")
            LOG["stopped"] = "deadline"
            save()
            sys.exit(2)
        if pins() != P0:
            LOG["stopped"] = f"pins changed before {name}"
            save()
            say("PINS CHANGED: stop")
            sys.exit(4)
        t0 = time.time()
        rc = subprocess.run([PY, "gpu_guard.py", "--gpu", "1", "--min_free_mib", "4096", "--log", f"out/{name}.log",
                             "--summary", f"out/{name}.guard.json", "--"] + cmd, cwd=HERE, env=ENV).returncode
        say(f"RUN {name} try {k} EXIT {rc} {time.time() - t0:.0f}s")
        if rc == 0 and py_traceback(name):
            say(f"  {name}: exit 0 but a Python Traceback is in the log; counted as error 1 (Isaac Kit exits 0 after an uncaught exception)")
            rc = 1
        if rc == 0:
            return 0, k
        if rc == 99:
            say(f"GUARD STOP {name}: free < 4096 MiB on GPU 1, waiting {wait_s}s")
            time.sleep(wait_s)
        else:
            return rc, k  # a real error is not retried
    return rc, tries


def q(script, tag, model_path, fam, cells, episodes, noise, seed, train_yaml=None, small=True):
    cmd = [PY, script, "--headless", "--tag", tag, "--policy", "student", "--checkpoint", model_path,
           "--families", fam, "--cells", cells, "--episodes", str(episodes), "--eval_seed", str(seed)]
    if small:
        cmd.append("--physx_small_buffers")
    if noise:
        cmd.append("--obs_noise")
    if not model_path.startswith(E1):
        cmd += ["--train_yaml", train_yaml or E1_YAML]
    return cmd


PRE_ZERO = ["teacher_input_randomized_max_abs_action_change", "manual_student_path_vs_act_inference_max_abs",
            "height_block_vs_raycaster_recomputed_max_abs", "non_height_critic_unchanged_max_abs",
            "student_height_permuted_max_abs_action_change", "teacher_manual_vs_module_act_mean_max_abs",
            "teacher_identity_perm_vs_normal_max_abs"]
PRE_TRUE = ["critic_dims_sum_equals_width", "height_block_values_same_multiset"]
PRE_POS = ["policy_history_perturbed_max_abs_action_change", "single_obs_perturbed_max_abs_action_change",
           "teacher_height_permuted_max_abs_action_change"]


def validate(tag, ckpt_sha, it, fam, cells, episodes, noise, seed, branch, need_iter=True, small=True):
    """Return '' if the run folder is a complete, correct result for exactly this input, else the reason."""
    d = os.path.join(OUT, tag)
    try:
        g = json.load(open(os.path.join(OUT, f"{tag}.guard.json"), encoding="utf-8"))
        if g.get("exit_code") != 0 or g.get("stopped_by_guard"):
            return f"guard exit {g.get('exit_code')} stopped {g.get('stopped_by_guard')}"
        if py_traceback(tag):
            return "Python Traceback in log"
        m = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        c = json.load(open(os.path.join(d, "cells.json"), encoding="utf-8"))
        rows = list(csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")))
        z = np.load(os.path.join(d, "traj.npz"))
        a = m["args"]
        n = len(cells) * episodes
        want = {"families": fam, "cells": ",".join(cells), "episodes": episodes, "eval_seed": seed, "obs_noise": noise,
                "difficulty": 0.5, "terrain_set": "train", "heading_hold": 0.0, "spawn_offset": "", "policy": "student"}
        for k, v in want.items():
            if a.get(k) != v:
                return f"arg {k}={a.get(k)!r} want {v!r}"
        if m.get("checkpoint_sha256") != ckpt_sha:
            return "checkpoint sha256"
        if need_iter and m.get("loaded_iter") != it:
            return f"loaded_iter {m.get('loaded_iter')}"
        if m.get("N") != n or [x["name"] for x in m["cells"]] != cells:
            return "N or cells"
        if m["devices"].get("torch_cuda0_uuid") != GPU1_UUID:
            return "gpu uuid"
        pre, run = m["checks_pre"], m["checks_run"]
        for k in PRE_ZERO:
            if not abs(float(pre[k])) <= 1e-6:
                return f"checks_pre {k}={pre[k]}"
        for k in PRE_TRUE:
            if pre[k] is not True:
                return f"checks_pre {k}"
        if run["obs_single_cmd_vs_target_max_abs"] > 1e-6 or run["obs_history_latest_cmd_vs_target_max_abs"] > 1e-6 \
                or run["nonfinite_action_or_obs_count"] != 0:
            return f"checks_run {run}"
        if branch:
            s = m.get("train_yaml_source", {})
            if os.path.normcase(os.path.abspath(s.get("train_yaml", ""))) != os.path.normcase(os.path.abspath(E1_YAML)) \
                    or "bundle_json_sha256" not in s:
                return "train_yaml_source"
        if len(c) != len(cells) or any(x["n"] != episodes for x in c):
            return "cells.json n"
        if len(rows) != n:
            return f"episodes.csv rows {len(rows)}"
        for cl in cells:
            ids = sorted(int(r["episode"]) for r in rows if r["cell"] == cl and r["family"] == fam)
            if ids != list(range(episodes)):
                return f"episode ids for {cl}"
        if any(r["family"] != fam or r["cell"] not in cells for r in rows):
            return "episodes.csv family / cell"
        T = m["T_steps"]
        if T != int(round(max(DUR_S.get(c, 20.0) for c in cells) / 0.02)):
            return f"T_steps {T}"
        if z["traj"].shape != (T + 1, n, 12) or z["term"].shape != (T + 1, n):
            return f"traj shape {z['traj'].shape}"
        if not np.isfinite(z["traj"][..., :11]).all():  # channel 11 (height above ground) may be NaN on a ray miss
            return "traj non-finite"
        if z["cmd_hist"].shape != (T + 1, n, 3) or not np.isfinite(z["cmd_hist"]).all():
            return "cmd_hist"
        if "physx buffers reduced" not in " ".join(m.get("eval_changes", [])) and small:
            return "physx small buffers not applied"
        if isinstance(m.get("terrain_mesh"), str) or not m.get("terrain_mesh"):
            return "terrain mesh"
        for k in ("pairing_sha256", "pairing_sha256_ext"):
            v = m.get(k)
            if not isinstance(v, dict) or not v or not all(v.values()):
                return f"{k} empty"
    except Exception as ex:  # noqa: BLE001
        return f"unreadable: {type(ex).__name__}: {ex}"
    return ""


def diag_warns(tag):
    m = json.load(open(os.path.join(OUT, tag, "meta.json"), encoding="utf-8"))
    return [k for k in PRE_POS if not float(m["checks_pre"][k]) > 0]


def fingerprint(tag):
    d = os.path.join(OUT, tag)
    m = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    z = np.load(os.path.join(d, "traj.npz"))
    return {"pairing_sha256": m["pairing_sha256"], "pairing_sha256_ext": m["pairing_sha256_ext"], "terrain_mesh": m["terrain_mesh"],
            "terrain_origins_sha256": m["terrain_origins_sha256"], "env_origins": sha(os.path.join(d, "env_origins.npy")),
            "N": m["N"], "T": m["T_steps"], "cells": m["cells"], "obs_shapes": m["obs_shapes"], "eval_changes": m.get("eval_changes"),
            "uuid": m["devices"]["torch_cuda0_uuid"], "layout": {k: hashlib.sha256(np.ascontiguousarray(z[k]).tobytes()).hexdigest()
                                                                   for k in ("fam", "cel", "epi", "cmd_a", "cmd_b", "sw")},
            "traj0": hashlib.sha256(np.ascontiguousarray(z["traj"][0]).tobytes()).hexdigest()}


def stamp_ok(tag, P):
    p = os.path.join(OUT, tag, "driver_stamp.json")
    return os.path.exists(p) and json.load(open(p, encoding="utf-8")).get("pins") == P


def write_stamp(tag, P, extra):
    json.dump({"pins": P, "t": time.strftime("%Y-%m-%d %H:%M:%S"), **extra},
              open(os.path.join(OUT, tag, "driver_stamp.json"), "w", encoding="utf-8"), indent=1)


def tests(P):
    pin8 = hashlib.sha256(json.dumps(P, sort_keys=True).encode()).hexdigest()[:8]
    psha = LOG["ckpt"]["p20000"]["sha256"]
    # 1. smoke: parent, flat, 11 cells x 10 = 110 envs, validated like a real run
    t = f"cq_test_{pin8}_smoke"
    sc = in_eval_order(CELLS)
    rc, _ = guarded(t, q("q_eval_cmdr.py", t, MODELS["p20000"][0], "flat", ",".join(sc), 10, True, 1000))
    why = validate(t, psha, 20000, "flat", sc, 10, True, 1000, False) if rc == 0 else f"exit {rc}"
    LOG["tests"]["smoke"] = why or "ok"
    save()
    if why:
        return False
    # 2. known answer: q_eval.py vs q_eval_cmdr.py, same input; if different, q_eval.py vs q_eval.py tells
    #    non-determinism from a copy fault (ASTRA 8 2)
    LOG["tests"]["q_eval_py_sha256"] = sha(os.path.join(HERE, "q_eval.py"))
    a, b = f"cq_test_{pin8}_ka_orig", f"cq_test_{pin8}_ka_copy"
    for tag, script in ((a, "q_eval.py"), (b, "q_eval_cmdr.py")):
        rc, _ = guarded(tag, q(script, tag, MODELS["p20000"][0], "flat", "stop03", 100, True, 1000))
        if rc != 0:
            LOG["tests"]["known_answer"] = f"{tag} exit {rc}"
            save()
            return False
    same = lambda x, y: (json.load(open(os.path.join(OUT, x, "cells.json"))) == json.load(open(os.path.join(OUT, y, "cells.json")))
                         and sha(os.path.join(OUT, x, "traj.npz")) == sha(os.path.join(OUT, y, "traj.npz")))
    ok = same(a, b)
    LOG["tests"]["known_answer"] = {"orig_vs_copy_same": ok}
    if not ok:
        a2 = f"cq_test_{pin8}_ka_orig2"
        guarded(a2, q("q_eval.py", a2, MODELS["p20000"][0], "flat", "stop03", 100, True, 1000))
        LOG["tests"]["known_answer"]["orig_vs_orig_same"] = same(a, a2)
        save()
        return False
    save()
    # 2b. small PhysX buffers must not change the physics on the flat training terrain (copy, default buffers vs small)
    c2 = f"cq_test_{pin8}_ka_copy_default_buffers"
    rc, _ = guarded(c2, q("q_eval_cmdr.py", c2, MODELS["p20000"][0], "flat", "stop03", 100, True, 1000, small=False))
    ok2 = rc == 0 and same(b, c2)
    LOG["tests"]["small_buffers_vs_default_same"] = ok2
    save()
    if not ok2:
        return False
    # 3. branch path must refuse a wrong train_yaml: another run's env.yaml, and a sibling file of the right folder
    g = f"{B}/gate_c1/model_20002.pt"
    gsha = sha(g)
    for name, bad in (("other_run", f"{E2}/params/env.yaml"), ("sibling", f"{E1}/params/agent.yaml")):
        t = f"cq_test_{pin8}_wrong_yaml_{name}"
        rc, _ = guarded(t, q("q_eval_cmdr.py", t, g, "flat", "stop03", 10, True, 1000, train_yaml=bad), tries=1)
        log = open(os.path.join(OUT, f"{t}.log"), encoding="utf-8", errors="replace").read()
        wrote = os.path.exists(os.path.join(OUT, t, "cells.json")) or os.path.exists(os.path.join(OUT, t, "traj.npz"))
        refused = rc != 0 and "AssertionError: train_yaml is not the parent run's" in log and not wrote
        LOG["tests"][f"wrong_yaml_{name}"] = {"exit": rc, "refused": refused, "wrote_result": wrote}
        save()
        if not refused:
            return False
    # 4. branch checkpoint passes and is read as iteration 20002 with the exact parent yaml and bundle hashes
    t = f"cq_test_{pin8}_branch_20002"
    rc, _ = guarded(t, q("q_eval_cmdr.py", t, g, "flat", "stop03", 10, True, 1000))
    why = validate(t, gsha, 20002, "flat", ["stop03"], 10, True, 1000, True) if rc == 0 else f"exit {rc}"
    LOG["tests"]["branch_pass"] = why or "ok"
    save()
    return not why


def jobs():
    out = []
    for m in MODELS:  # (A)
        for cell in CELLS:
            out.append((m, "flat", cell, True, 1000))
    for m in MODELS:  # (B)
        for s in EXT_SEEDS:
            for cell in TARGETS:
                out.append((m, "flat", cell, True, s))
    for fam in FAMILIES[1:]:  # (C)
        for m in MODELS:
            for cell in CELLS:
                out.append((m, fam, cell, True, 1000))
    for m in MODELS:  # (D)
        for cell in CELLS:
            out.append((m, "flat", cell, False, 1000))
    return out


def tagof(m, fam, cell, noise, seed):
    return f"cq_{m}_{fam}_{cell}_{'on' if noise else 'off'}_s{seed}"


ap = argparse.ArgumentParser()
ap.add_argument("--until", default="2026-10-13 14:00")
args = ap.parse_args()
deadline = DEADLINE = time.mktime(time.strptime(args.until, "%Y-%m-%d %H:%M"))
P0 = pins()
LOG["pins"] = P0
save()
say(f"pins {len(P0)} files · q_eval_cmdr {P0['q_eval_cmdr.py'][:16]}")
while unseen_running():
    if time.time() > deadline:
        say("deadline while waiting for the unseen driver")
        sys.exit(2)
    time.sleep(60)
say("unseen driver not running: GPU 1 is ours")
LOG["gpu1_from"] = time.strftime("%Y-%m-%d %H:%M:%S")
while not ready("p20000"):
    if time.time() > deadline:
        sys.exit(2)
    time.sleep(30)
if not tests(P0):
    say(f"TESTS FAILED {LOG['tests']}")
    save()
    sys.exit(3)
say(f"tests passed {LOG['tests']}")
groups = {}
pending = jobs()
while pending and time.time() < deadline:
    pick = next((j for j in pending if ready(j[0])), None)
    if pick is None:
        time.sleep(60)
        continue
    pending.remove(pick)
    m, fam, cell, noise, seed = pick
    tag = tagof(m, fam, cell, noise, seed)
    path, it = MODELS[m]
    if pins() != P0:
        LOG["stopped"] = "pins changed"
        save()
        say("PINS CHANGED: stop")
        sys.exit(4)
    if sha(path) != LOG["ckpt"][m]["sha256"]:
        LOG["stopped"] = f"checkpoint {m} changed after pinning"
        save()
        say(f"CHECKPOINT CHANGED {m}: stop")
        sys.exit(5)
    branch = not path.startswith(E1)
    if stamp_ok(tag, P0) and not validate(tag, LOG["ckpt"][m]["sha256"], it, fam, [cell], 100, noise, seed, branch):
        why, reused = "", True
    else:
        rc, k = guarded(tag, q("q_eval_cmdr.py", tag, path, fam, cell, 100, noise, seed))
        why = validate(tag, LOG["ckpt"][m]["sha256"], it, fam, [cell], 100, noise, seed, branch) if rc == 0 else f"exit {rc}"
        reused = False
    if pins() != P0:
        LOG["stopped"] = f"pins changed during {tag}"
        save()
        say("PINS CHANGED: stop")
        sys.exit(4)
    rec = {"tag": tag, "valid": not why, "why": why, "reused": reused, "t": time.strftime("%H:%M:%S")}
    if not why:
        rec["diag_warns"] = diag_warns(tag)
        fp = fingerprint(tag)
        gk = (fam, cell, noise, seed)
        if gk not in groups:
            groups[gk] = (tag, fp)
        elif fp != groups[gk][1]:
            bad = sorted(k for k in fp if fp[k] != groups[gk][1].get(k))
            rec["pair_fail"] = {"against": groups[gk][0], "fields": bad}
            LOG["pair_fail"].append(tag)
        write_stamp(tag, P0, {"ckpt_sha256": LOG["ckpt"][m]["sha256"], "pair_ref": groups[gk][0]})
    else:
        LOG["skipped"].append(tag)
    LOG["runs"].append(rec)
    LOG["matrix"][tag] = "valid" if not why and "pair_fail" not in rec else ("pair_fail" if not why else "invalid")
    save()
LOG["ended"] = time.strftime("%Y-%m-%d %H:%M:%S")
LOG["pending_at_end"] = [tagof(*j) for j in pending]
save()
say(f"END runs={len(LOG['runs'])} invalid={len(LOG['skipped'])} pair_fail={len(LOG['pair_fail'])} pending={len(pending)}")
