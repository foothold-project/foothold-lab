"""CPU tests for uncr_revalidate_v3.py and unseen_driver_cmdr_v6.py (lead sub task 10/14 · ASTRA 17e counterexamples kept).

UNCR_REVAL3_SCRIPT / UNCR_V6_SCRIPT may point at mutated copies (mutate_uncr_v5.py). UNCR_TEST_SKIP_REAL=1 skips the read-only pass over
the real _eval/out_uncr. Expected values are written by hand. Fixture runs get episodes.csv / cells.json from the evaluator's own q_post
(as q_eval_cmdr.py:648~650). Launches are stubbed (no Isaac, no GPU). Every root, registry, lock and slot folder lives in the system temp
folder under codexA and remains for inspection; the real _eval/slot is not touched. Exit 1 when any check fails.
"""
import copy
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import warnings

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
SAFE_BASE = os.path.realpath("C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexA")
RV_SCRIPT = os.path.abspath(os.environ.get("UNCR_REVAL3_SCRIPT", os.path.join(HERE, "uncr_revalidate_v3.py")))
V5_SCRIPT = os.path.abspath(os.environ.get("UNCR_V6_SCRIPT", os.path.join(HERE, "unseen_driver_cmdr_v6.py")))
FZ_SCRIPT = os.path.abspath(os.environ.get("UNCR_FROZEN_SCRIPT", os.path.join(HERE, "frozen_exec.py")))
SKIP_REAL = os.environ.get("UNCR_TEST_SKIP_REAL") == "1"
REAL_ROOT = os.path.join(HERE, "out_uncr")
fails = []

# --- by hand: the collection contract (unseen_driver_cmdr.py v3 lines 36~48, q_eval_cmdr.py:92~105) -------------------------------
E1 = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192"
YAML = E1 + "/params/env.yaml"
BRD = "C:/isaac/ext/go2_rl_robotlab/_eval/out/branch"
CK = {"par": (E1 + "/model_20000.pt", 20000, ""), "off": (BRD + "/cmdr_s1042_off_u4000/model_24000.pt", 24000, YAML),
      "on": (BRD + "/cmdr_s1042_on_u4000/model_24000.pt", 24000, YAML)}
DIAG = [("gap", "fwd05"), ("stepping_stones", "fwd05"), ("floating_ring", "fwd05"), ("rails", "fwd05"), ("wave", "fwd05"),
        ("gap", "back03"), ("discrete_obstacles", "back03")]
DIAG_KEYS = ["gap/fwd05", "stepping_stones/fwd05", "floating_ring/fwd05", "rails/fwd05", "wave/fwd05", "gap/back03", "discrete_obstacles/back03"]
CMD = {"fwd05": [0.5, 0.0, 0.0], "back03": [-0.3, 0.0, 0.0], "fwd03": [0.3, 0.0, 0.0], "fwd10": [1.0, 0.0, 0.0]}
SRC = {"fwd05": "LEAD_TEMP", "back03": "Q", "fwd03": "Q", "fwd10": "LEAD_TEMP_UNSEEN"}
TERRAIN_SRC = "0009e1e11850191bb875e316038a08ae85308226e27d6a748fe474aa1301eed4"
REAL_BUNDLE = "e55975172405901a0178a8e2bd3541ce7e13b118d0a9ab723fb6028d69ef2b58"  # ASTRA 17e §4
V2_CODE = ("q_eval_cmdr.py", "q_metrics.py", "isaac_slot.py", "usd_isolate_run.py", "gpu_guard.py", "unseen_driver_cmdr.py")
V3_CODE = ("q_eval_cmdr.py", "q_metrics.py", "q_post.py", "isaac_slot_v3.py", "usd_isolate_run_v3.py", "gpu_guard.py")
USD_KEY = "20261013_190023_7028"
ROOT_FAIL = "</World/envs/env_0/Robot>: Unresolved reference"
ALL_VALID = {"par": "valid", "off": "valid", "on": "valid"}


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:260], "want", repr(want)[:160], flush=True)
    if not ok:
        fails.append(name.split()[0])


def norm(p):
    return os.path.normcase(os.path.abspath(p)).replace("\\", "/")


def bsha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


_SHA = {}


def fsha(p):
    if p not in _SHA:
        _SHA[p] = bsha(p)
    return _SHA[p]


def hx(s):
    return hashlib.sha256(s.encode()).hexdigest()


def load(path, name):
    original = os.environ.get("UNCR_MUT_ORIGINAL")
    if original and path in (RV_SCRIPT, V5_SCRIPT) and os.path.commonpath((SAFE_BASE, os.path.realpath(path))) == SAFE_BASE:
        module = types.ModuleType(name)
        module.__file__ = original
        with open(path, encoding="utf-8") as source:
            exec(compile(source.read(), original, "exec"), module.__dict__)
        return module
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def assert_safe_paths(U, allow_real_old=False):
    for name in ("ROOT", "SLOT", "OLD_ROOT", "REVAL_BASE"):
        resolved = os.path.realpath(getattr(U, name))
        inside = os.path.commonpath((SAFE_BASE, resolved)) == SAFE_BASE
        real_old = name == "OLD_ROOT" and allow_real_old and resolved == os.path.realpath(REAL_ROOT)
        assert inside or real_old, f"unsafe {name}: {resolved}"


os.environ.update({
    "UNCR_V6_ROOT": os.path.join(SAFE_BASE, "preflight", "root"),
    "UNCR_V6_OLD_ROOT": os.path.join(SAFE_BASE, "preflight", "old"),
    "UNCR_V6_SLOT": os.path.join(SAFE_BASE, "preflight", "slot"),
    "UNCR_V6_REVAL_ROOT": os.path.join(SAFE_BASE, "preflight", "reval"),
    "UNCR_V6_WORK": os.path.join(SAFE_BASE, "recompute"),
    "UNCR_REVAL3_SCRIPT": os.path.join(HERE, "uncr_revalidate_v3.py"),
})
PREFLIGHT = load(V5_SCRIPT, "v6_preflight")
assert_safe_paths(PREFLIGHT)
print("PREFLIGHT ROOT", PREFLIGHT.ROOT, "SLOT", PREFLIGHT.SLOT,
      "OLD_ROOT", PREFLIGHT.OLD_ROOT, "REVAL_BASE", PREFLIGHT.REVAL_BASE, flush=True)


QP = load(os.path.join(HERE, "q_post.py"), "q_post_fixture5")
RV = load(RV_SCRIPT, "rv2_under_test")
assert os.path.commonpath((SAFE_BASE, os.path.realpath(RV.RECOMPUTE_BASE))) == SAFE_BASE
FZ = load(FZ_SCRIPT, "frozen_exec_under_test")
_BASE = {}


def base_arrays(cell):
    """100 envs x 1001 states walking +x at 0.01 m per state from 0.2 m past the origin; env 50 has base contact at state 78 (1.56 s)."""
    if "a" not in _BASE:
        N, T = 100, 1000
        jj = np.arange(T + 1, dtype=np.float32)
        org = np.array([[-36.0 + 8.0 * (e % 8), 0.0, 0.0] for e in range(N)], np.float32)
        tr = np.zeros((T + 1, N, 12), np.float32)
        tr[:, :, 0] = org[None, :, 0] + 0.2 + 0.01 * jj[:, None]
        tr[:, :, 1] = 0.1
        tr[:, :, 2] = 0.35
        tr[:, :, 4] = 0.5
        tr[:, :, 10] = -1.0
        tr[:, :, 11] = 0.3
        term = np.zeros((T + 1, N), bool)
        term[78, 50] = True
        tr[78:, 50, 0] = org[50, 0] + 0.2 + 0.01 * (jj[78:] - 78)
        _BASE["a"] = ({"traj": tr, "term": term, "cel": np.zeros(N, np.int64), "fam": np.zeros(N, np.int64), "epi": np.arange(N, dtype=np.int64),
                       "sw": np.full(N, 10 ** 9, np.int64), "act_abs_mean": np.full(N, 0.1, np.float32)}, org)
    a, org = _BASE["a"]
    out = {k: v.copy() for k, v in a.items()}
    c = np.tile(np.array(CMD[cell], np.float32), (100, 1))
    out.update(cmd_a=c, cmd_b=c.copy(), cmd_hist=np.broadcast_to(c, (1001, 100, 3)).copy())
    return out, org.copy()


def write_stamp(root, tag, wrappers="v2", code=None):
    d = os.path.join(root, tag)
    with open(os.path.join(root, f"{tag}.slot.json"), encoding="utf-8") as f:
        att = json.load(f)["attempt"]
    out = {f: bsha(os.path.join(d, f)) for f in ("meta.json", "cells.json", "episodes.csv", "traj.npz", "env_origins.npy")}
    out.update({e: bsha(os.path.join(root, f"{tag}{e}")) for e in (".log", ".guard.json", ".slot.json")})
    cs = {f: fsha(os.path.join(HERE, f)) for f in (V2_CODE if wrappers == "v2" else V3_CODE)}
    cs.update(code or {})
    with open(os.path.join(d, "driver_stamp.json"), "w", encoding="utf-8") as f:
        json.dump({"attempt": att, "out_sha256": out, "code_sha256": cs, "t": "2026-10-14 01:00:00"}, f, indent=1)


def make_run(root, m, fam, cell, edit=None, post_edit=None, after_stamp=None, code=None, att=None, stamp=True, wrappers="v2", registry=None,
             slot_edit=None):
    tag = f"uncr_{m}_{fam}_{cell}"
    d = os.path.join(root, tag)
    os.makedirs(d, exist_ok=True)
    ck, it, yaml = CK[m]
    att = att or f"gT-1-1014000000-{tag}-try1"
    usd_root = norm(os.path.join(root, "usd", f"{tag}-{att}"))
    folder = f"{usd_root}/IsaacLab/usd_{USD_KEY}"
    os.makedirs(folder, exist_ok=True)
    line = {"t": "2026-10-14 01:00:00", "pid": 1, "usd_dir": folder, "asset_path": "go2.urdf", "cfg_class": "UnitreeUrdfFileCfg", "patched_by": "loader"}
    if wrappers == "v3":
        line.update(kind="assigned", original=None, version="v3")
    with open(f"{usd_root}/assigned.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    with open(f"{usd_root}/isolate_state.json", "w", encoding="utf-8") as f:
        json.dump({"patched_by": "loader", "version": wrappers, "blocked": [], "warnings": [], "conversions": 1}, f)
    arr, org = base_arrays(cell)
    if (m, fam, cell) == ("on", "gap", "fwd05"):
        arr["traj"][808:, 50, 11] = np.nan  # as the real uncr_on_gap_fwd05: ground ray miss long after env 50's fall
    meta = {"args": {"checkpoint": ck, "policy": "student", "height_perm_seed": -1, "families": fam, "cells": cell, "episodes": 100,
                     "difficulty": 0.5, "terrain_set": "unseen10", "eval_seed": 1000, "obs_noise": False, "tag": tag, "outdir": root,
                     "heading_hold": 0.0, "heading_clip": 0.5, "fingerprint_only": False, "full_record": False, "train_yaml": yaml, "spawn_offset": ""},
            "cells": [{"name": cell, "kind": "lin", "cmd": CMD[cell], "duration_s": 20.0, "switch_s": None, "src": SRC[cell]}],
            "families": [fam], "N": 100, "T_steps": 1000, "checkpoint_sha256": fsha(ck), "loaded_iter": it,
            "heading_hold": {"K": 0.0, "clip": 0.5, "envs": 0}, "terrain_set": {"name": "unseen10", "source_sha256": TERRAIN_SRC},
            "checks_run": {"obs_single_cmd_vs_target_max_abs": 0.0, "obs_history_latest_cmd_vs_target_max_abs": 0.0, "nonfinite_action_or_obs_count": 0},
            "checks_pre": {"manual_student_path_vs_act_inference_max_abs": 0.0, "teacher_input_randomized_max_abs_action_change": 0.0},
            "obstacle_zone_m": {fam: [0.75, 4.0, "x"]},
            "terrain_mesh": [["/World/ground/terrain/mesh", 432, hx("mesh-" + fam)]], "terrain_origins_sha256": hx("orig-" + fam),
            "pairing_sha256": {k: hx(k) for k in ("init_root_pose", "init_joint_pos", "body_masses", "joint_stiffness")},
            "pairing_sha256_ext": {k: hx(k) for k in ("com", "material_static_dynamic_restitution", "actuator_GO2HV_stiffness",
                                                      "actuator_GO2HV_damping", "actuator_GO2HV_delay_lags", "motor_zero_offset")}}
    if yaml:
        meta["train_yaml_source"] = {"train_yaml": yaml, "train_yaml_sha256": fsha(yaml)}
    if edit:
        edit(meta, arr, org)
    np.savez_compressed(os.path.join(d, "traj.npz"), **arr)
    np.save(os.path.join(d, "env_origins.npy"), org)
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        QP.postprocess(d)
    with open(os.path.join(root, f"{tag}.log"), "w", encoding="utf-8") as f:
        f.write(f"[USD-ISOLATE] root {usd_root}\n"
                f"Warning: In </go2/Head_upper/visuals>: Unresolved reference prim path @{folder}/configuration/go2_physics.usd@</visuals/Head_upper>\n"
                "[INFO]: Time taken for scene creation : 4.4 seconds\n"
                f"[Q-EVAL] done {tag} N 100 rollout_s 1.0\n")
    with open(os.path.join(root, f"{tag}.guard.json"), "w", encoding="utf-8") as f:
        json.dump({"exit_code": 0, "stopped_by_guard": False}, f)
    runner = "usd_isolate_run_v3.py" if wrappers == "v3" else "usd_isolate_run.py"
    rec = {"attempt": att, "cmd": [PY, "gpu_guard.py", "--gpu", "1", "--", PY, runner, "q_eval_cmdr.py", "--headless", "--tag", tag, "--checkpoint", ck],
           "usd_root": usd_root, "state_at_release": "scene_built", "child_rc": 0, "conflicts": {}, "slot_rc": 0}
    if wrappers == "v3":
        rec.update(slot_version="v3", registry=registry or "C:/x/slot/isaac_usd_registry_v3.json", expect_conversions="1",
                   usd_final=[norm(folder)], usd_final_keys=[USD_KEY], usd_at_release=[norm(folder)], usd_outside_root=[], usd_unassigned=[],
                   assigned=[norm(folder)], assigned_outside_root=[], registry_error="", expect_violation=False, hint_without_assigned=False,
                   launcher_blocked=[], unexpected_refused=[])
    else:
        rec.update(usd_final=[USD_KEY], usd_at_release=[USD_KEY], usd_outside_root=[])
    if slot_edit:
        slot_edit(rec)
    with open(os.path.join(root, f"{tag}.slot.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f)
    if post_edit:
        post_edit(root, tag, d)
    if stamp:
        write_stamp(root, tag, wrappers, code)
    if after_stamp:
        after_stamp(root, tag, d)
    return tag


def make_cell(root, fam="gap", cell="fwd05", edits=None, wrappers=None):
    for m in ("par", "off", "on"):
        e = dict((edits or {}).get(m, {}))
        e.setdefault("wrappers", (wrappers or {}).get(m, "v2"))
        make_run(root, m, fam, cell, **e)


def make_old(root, edits=None, with_partial=True):
    """the old bundle shape: 21 diag runs and the par / off of discrete_obstacles/fwd05, all v2 wrappers."""
    for fam, cell in DIAG:
        make_cell(root, fam, cell, {m: e for (m, f, c), e in (edits or {}).items() if (f, c) == (fam, cell)})
    if with_partial:
        for m in ("par", "off"):
            make_run(root, m, "discrete_obstacles", "fwd05", **(edits or {}).get((m, "discrete_obstacles", "fwd05"), {}))


# --- edits ------------------------------------------------------------------------------------------------------------------
def cmds_zero(meta, arr, org):
    arr["cmd_a"][:] = 0.0
    arr["cmd_b"][:] = 0.0
    arr["cmd_hist"][:] = 0.0


def cmd_hist_nan(meta, arr, org):
    arr["cmd_hist"][10, 0, 0] = np.nan


def meta_cmd_99(meta, arr, org):
    meta["cells"][0]["cmd"] = [99.0, 99.0, 99.0]


def spawn_offset_on(meta, arr, org):
    meta["args"]["spawn_offset"] = "stand=2.5"


def heading_hold_on(meta, arr, org):
    meta["heading_hold"] = {"K": 0.5, "clip": 0.5, "envs": 100}


def cmd_hist_state0(meta, arr, org):
    arr["cmd_hist"][0] = 0.0


def action_zero(meta, arr, org):
    arr["act_abs_mean"][:] = 0.0


def terrain_src_other(meta, arr, org):
    meta["terrain_set"]["source_sha256"] = hx("other generator")


def sw_250(meta, arr, org):
    arr["sw"][:] = 250


def dr_other(meta, arr, org):
    meta["pairing_sha256_ext"]["com"] = hx("other com")


def nan_x_env0(meta, arr, org):
    arr["traj"][:, 0, 0] = np.nan


def drop_cmd_hist(root, tag, d):
    p = os.path.join(d, "traj.npz")
    with np.load(p) as z:
        arr = {k: z[k].copy() for k in z.files if k != "cmd_hist"}
    np.savez_compressed(p, **arr)


def assigned_outside(root, tag, d):
    with open(os.path.join(root, f"{tag}.slot.json"), encoding="utf-8") as f:
        ur = json.load(f)["usd_root"]
    with open(f"{ur}/assigned.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"usd_dir": f"C:/Users/x/AppData/Local/Temp/IsaacLab/usd_{USD_KEY}", "patched_by": "loader", "kind": "assigned"}) + "\n")


def append_log(root, tag, d):
    with open(os.path.join(root, f"{tag}.log"), "a", encoding="utf-8") as f:
        f.write("one more line after the review\n")


# --- helpers ----------------------------------------------------------------------------------------------------------------
TMPS = []


def tmpdir(case):
    work = "C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexA/test-fixtures"
    os.makedirs(work, exist_ok=True)
    t = tempfile.mkdtemp(prefix=f"uncr_v6_{case}_", dir=work)
    TMPS.append(t)
    return t


def cell_root(case, edits=None, wrappers=None):
    root = os.path.join(tmpdir(case), "root")
    make_cell(root, "gap", "fwd05", edits, wrappers)
    return root


def has(reasons, code):
    return any(r.startswith(code) for r in reasons)


def snapshot(root):
    out = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            st = os.stat(os.path.join(dp, f))
            out.append((os.path.relpath(os.path.join(dp, f), root), st.st_size, st.st_mtime_ns))
    return sorted(out)


def env_for(t, old=None):
    return {"UNCR_V6_ROOT": os.path.join(t, "new"), "UNCR_V6_OLD_ROOT": old or os.path.join(t, "old"),
            "UNCR_V6_REVAL_ROOT": os.path.join(t, "reval"), "UNCR_V6_SLOT": os.path.join(t, "slot"),
            "UNCR_REVAL3_SCRIPT": os.path.join(HERE, "uncr_revalidate_v3.py") if os.environ.get("UNCR_MUT_ORIGINAL") else RV_SCRIPT}


def load_v5(t, old=None, approved=None):
    os.environ.update(env_for(t, old))
    U = load(V5_SCRIPT, f"v5_{len(TMPS)}_{abs(hash(t))}")
    if os.environ.get("UNCR_MUT_ORIGINAL") and RV_SCRIPT != os.path.join(HERE, "uncr_revalidate_v3.py"):
        U.RV = RV
    assert_safe_paths(U)
    assert os.path.commonpath((SAFE_BASE, os.path.realpath(U.RV.RECOMPUTE_BASE))) == SAFE_BASE
    if approved:
        U.OLD_APPROVED = approved
    U._sleep = lambda s: None
    U.gpu_free_mib = lambda: 20000
    return U


def run_main(U, argv):
    assert_safe_paths(U)
    sys.argv = ["unseen_driver_cmdr_v6.py"] + argv
    try:
        U.main()
    except SystemExit as e:
        return e.code
    return None


def approve(old, reval_dir):
    """the reviewed old bundle for a synthetic old root: its v2 report written and pinned as OLD_APPROVED."""
    rep = RV.revalidate(old)
    p = RV.write_report(rep, reval_dir)
    return {"report": p, "report_sha256": bsha(p), "bundle_sha256": rep["bundle_sha256"], "review": "test"}, p, rep


def write_approval(U, path, reval_path, reuse="no", new_runs=75, decision="approve", by="tester", old_bundle=None):
    U.freeze()
    ap = {"kind": "uncr_v6_full_approval", "decision": decision, "by": by, "t": "2026-10-14 01:00:00", "reval_sha256": bsha(reval_path),
          "old_bundle_sha256": old_bundle or U.OLD_APPROVED["bundle_sha256"], "code_manifest_sha256": U.manifest_sha(), "reuse_partial": reuse,
          "new_runs": new_runs}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ap, f)
    return path


def stub_run_set(U):
    calls = []
    U.run_set = lambda plan: calls.append(len(plan))
    return calls


def stub_launcher(U, actions, on_sleep=None):
    """stands in for isaac_slot_v3 + Isaac. actions per launch: '94' (v3 record, rc 94), '1' (v3 record, child exit 1), '99' (guard stopped),
    'ok' (a clean v3 synthetic run), 'rootfail' (clean run whose log has the robot root reference failure), 'outside' (assigned outside)."""
    launches = []

    def run(argv, **kw):
        tag = os.path.basename(argv[argv.index("--watch_log") + 1])[:-4]
        att = argv[argv.index("--attempt") + 1]
        act = actions[min(len(launches), len(actions) - 1)]
        launches.append(act)
        _, m, rest = tag.split("_", 2)
        fam, cell = rest.rsplit("_", 1)
        if act in ("94", "1", "99", "92"):
            with open(os.path.join(U.ROOT, f"{tag}.slot.json"), "w", encoding="utf-8") as f:
                json.dump({"slot_version": "v3", "attempt": att, "slot_rc": int(act), "child_rc": int(act) if act != "94" else 0}, f)
            with open(os.path.join(U.ROOT, f"{tag}.guard.json"), "w", encoding="utf-8") as f:
                json.dump({"exit_code": int(act), "stopped_by_guard": act == "99"}, f)
            return types.SimpleNamespace(returncode=int(act))
        make_run(U.ROOT, m, fam, cell, att=att, stamp=False, wrappers="v3", registry=U.REG_V3,
                 post_edit=assigned_outside if act == "outside" else None)
        if act == "rootfail":
            with open(os.path.join(U.ROOT, f"{tag}.log"), "a", encoding="utf-8") as f:
                f.write(f"[Warning] In {ROOT_FAIL} prim path @x@\n")
        return types.SimpleNamespace(returncode=0)
    U.subprocess = types.SimpleNamespace(run=run)
    if on_sleep:
        U._sleep = on_sleep
    return launches


def code_moves_after(U, n_real):
    real = U.code_sha
    n = [0]

    def moving():
        n[0] += 1
        c_ = real()
        if n[0] > n_real:
            c_["q_post.py"] = "0" * 64
        return c_
    U.code_sha = moving


GF = [("gap", "fwd05", "par"), ("gap", "fwd05", "off"), ("gap", "fwd05", "on")]

try:
    # ===== §3.1 command contract (revalidator v2, one cell) ===================================================================
    rep = RV.revalidate(cell_root("c00"))
    c, on = rep["cells"]["gap/fwd05"], rep["runs"]["uncr_on_gap_fwd05"]
    check("C00 baseline cell (fwd05 commands as the contract, on env 50 channel 11 NaN after its fall): valid, counts by hand 99 / 99",
          (c["runs"], c["verdict"], on["stats"]["surv"], on["stats"]["cross"], on["nan"]["ground_ch11_after_window"]), (ALL_VALID, "valid", 99, 99, 193))
    cases = [("C01", "(17e) cmd_a, cmd_b and cmd_hist all 0 in the three runs while meta says fwd05", cmds_zero, "[cmd-array]"),
             ("C02", "(17e) cmd_hist[10, 0, 0] NaN in the three runs", cmd_hist_nan, "[cmd-array]"),
             ("C03", "(17e) meta cell cmd [99, 99, 99] in the three runs, arrays as the contract", meta_cmd_99, "[cmd-contract]")]
    for tid, what, ed, code in cases:
        rep = RV.revalidate(cell_root(tid.lower(), {m: {"edit": ed} for m in ("par", "off", "on")}))
        c = rep["cells"]["gap/fwd05"]
        check(f"{tid} {what}: all three invalid with {code}, cell invalid (checks_run 0 does not stand in)",
              (c["runs"], c["verdict"], all(has(r["invalid"], code) for r in rep["runs"].values())),
              ({"par": "invalid", "off": "invalid", "on": "invalid"}, "invalid", True))
    single = [("C05", "args spawn_offset 'stand=2.5' (must be off here)", {"edit": spawn_offset_on}, "[eval-args]"),
              ("C05b", "meta heading_hold K 0.5 on 100 envs (must be off here)", {"edit": heading_hold_on}, "[eval-args]"),
              ("C06", "cmd_hist at state 0 is 0 (the time rule says cmd_a)", {"edit": cmd_hist_state0}, "[cmd-time]"),
              ("C07", "act_abs_mean 0 for every env", {"edit": action_zero}, "[action]"),
              ("C08", "unseen10 generator source hash is not the reviewed one", {"edit": terrain_src_other}, "[terrain-src]"),
              ("C09", "traj.npz without cmd_hist", {"post_edit": drop_cmd_hist}, "[traj-shape]"),
              ("C10", "sw 250 in a lin cell (no switch in the contract)", {"edit": sw_250}, "[cmd-array]")]
    for tid, what, ed, code in single:
        rep = RV.revalidate(cell_root(tid.lower(), {"on": ed}))
        r = rep["runs"]["uncr_on_gap_fwd05"]
        check(f"{tid} {what}: on invalid with {code}, cell invalid", (r["verdict"], has(r["invalid"], code), rep["cells"]["gap/fwd05"]["verdict"]),
              ("invalid", True, "invalid"))

    # ===== §3.4 judgement code frozen (copies of the revalidator, q_post and q_metrics in a temp folder) ==========================
    cd = tmpdir("code")
    for f in ("uncr_revalidate_v3.py", "q_post.py", "q_metrics.py"):
        shutil.copy(RV_SCRIPT if f == "uncr_revalidate_v3.py" else os.path.join(HERE, f), os.path.join(cd, f))
    froot = cell_root("f01")

    def during(rv, fname):
        orig = rv.Reader.read

        def evil(self, path):
            b = orig(self, path)
            if norm(path).endswith("uncr_par_gap_fwd05/traj.npz"):
                with open(os.path.join(cd, fname), "a", encoding="utf-8") as f:
                    f.write("\n# a comment added while the check ran\n")
            return b
        rv.Reader.read = evil
        try:
            return rv.revalidate(froot, check_environment=False)
        finally:
            rv.Reader.read = orig
    RVC = load(os.path.join(cd, "uncr_revalidate_v3.py"), "rv2_copy_a")
    rep = during(RVC, "q_post.py")
    check("F01 (17e 3.4) q_post gains a comment line while the check runs: frozen_ok False, code:q_post.py listed, cell invalid",
          (rep["frozen_ok"], "code:q_post.py" in rep["changed_during_check"], rep["cells"]["gap/fwd05"]["verdict"]), (False, True, "invalid"))
    with open(os.path.join(cd, "q_post.py"), "a", encoding="utf-8") as f:
        f.write("# changed between two checks\n")
    rep = RVC.revalidate(froot, check_environment=False)
    check("F02 (17e 3.4) q_post changed between two checks: the cached module is loaded again, the report names the bytes now on disk",
          (rep["judge_code"]["q_post.py"]["sha256_loaded"] == bsha(os.path.join(cd, "q_post.py")), rep["judge_code"]["q_post.py"]["reloaded_for_this_check"],
           rep["frozen_ok"]), (True, True, True))
    RVD = load(os.path.join(cd, "uncr_revalidate_v3.py"), "rv2_copy_b")
    rep = during(RVD, "uncr_revalidate_v3.py")
    check("F03 (17e 3.4) the revalidator file itself changes while it checks: frozen_ok False, code:uncr_revalidate_v3.py listed",
          (rep["frozen_ok"], "code:uncr_revalidate_v3.py" in rep["changed_during_check"]), (False, True))

    # ===== §5.3 wrapper provenance by role ======================================================================================
    rep = RV.revalidate(cell_root("w01", wrappers={"on": "v3"}))
    c = rep["cells"]["gap/fwd05"]
    check("W01 (17e 5.3) par / off collected with v2 wrappers, on with v3 (q_post in its stamp): cell valid, the wrapper replacement and the "
          "unknown q_post provenance of par / off noted",
          (c["runs"], c["verdict"], any("slot wrapper differs" in x for x in c["notes"]), any("q_post provenance unknown for ['par', 'off']" in x for x in c["notes"])),
          (ALL_VALID, "valid", True, True))
    runs = copy.deepcopy({m: rep["runs"][f"uncr_{m}_gap_fwd05"] for m in ("par", "off", "on")})
    runs["on"]["roles"]["eval"] = ["q_eval_cmdr.py", "0" * 64]
    c2 = RV.cell_verdict("gap", "fwd05", runs)
    check("W02 (17e 5.3) the on run's evaluator hash differs (wrapper change is the only exemption): cell hold, collection code eval named",
          (c2["verdict"], any("collection code eval" in x for x in c2["pair_diff"])), ("hold", True))
    runs = copy.deepcopy({m: rep["runs"][f"uncr_{m}_gap_fwd05"] for m in ("par", "off", "on")})
    runs["on"]["roles"]["slot"] = ["isaac_slot_v3.py", "1" * 64]
    c3 = RV.cell_verdict("gap", "fwd05", runs)
    check("W03 (17e 5.3) an isaac_slot_v3.py hash that is not the registered one: cell hold, unregistered slot wrapper named",
          (c3["verdict"], any("unregistered slot wrapper" in x for x in c3["pair_diff"])), ("hold", True))
    wcases = [("W04", "(17e 5.4) a v3 slot record that used the v2 registry file", {"wrappers": "v3", "registry": "C:/x/slot/isaac_usd_registry.json"}, "[slot]"),
              ("W05", "a v3 slot record whose child ran the v2 runner usd_isolate_run.py",
               {"wrappers": "v3", "slot_edit": lambda r: r.update(cmd=[x.replace("usd_isolate_run_v3.py", "usd_isolate_run.py") for x in r["cmd"]])}, "[slot]"),
              ("W06", "a v3 slot record with a stamp that names the v2 wrappers", {"wrappers": "v3",
               "code": {"isaac_slot.py": fsha(os.path.join(HERE, "isaac_slot.py")), "usd_isolate_run.py": fsha(os.path.join(HERE, "usd_isolate_run.py"))},
               "after_stamp": None}, "[stamp-code]")]
    for tid, what, ed, code in wcases:
        if tid == "W06":
            root = os.path.join(tmpdir("w06"), "root")
            for m in ("par", "off"):
                make_run(root, m, "gap", "fwd05")
            make_run(root, "on", "gap", "fwd05", wrappers="v3", stamp=False)
            st_code = {f: fsha(os.path.join(HERE, f)) for f in ("q_eval_cmdr.py", "q_metrics.py", "gpu_guard.py", "q_post.py", "isaac_slot.py", "usd_isolate_run.py")}
            write_stamp(root, "uncr_on_gap_fwd05", "v2", st_code)
        else:
            root = cell_root(tid.lower(), {"on": ed})
        rep = RV.revalidate(root)
        r = rep["runs"]["uncr_on_gap_fwd05"]
        check(f"{tid} {what}: on invalid with {code}", (r["verdict"], has(r["invalid"], code)), ("invalid", True))

    # ===== §3.2 · §3.3 launches (stubbed launcher, temp roots and slot folder) ====================================================
    def d_case(case, actions, on_sleep=None, moves=None, gpu=None):
        t = tmpdir(case)
        U = load_v5(t)
        U.freeze()
        launches = stub_launcher(U, actions, on_sleep)
        if gpu:
            U.gpu_free_mib = gpu
        if moves is not None:
            code_moves_after(U, moves)
        ok = U.run_set(GF)
        return U, launches, ok

    U, launches, ok = d_case("d01", ["94"])
    first = (launches, os.path.exists(U.HALTF), [r.get("cls") for r in U.LOG["runs"]], ok)
    n_before = len(launches)
    U.run_set(GF)
    check("D01 (17e 3.2) slot 94 once: one launch, no retry, off / on not launched, HALT_v6.json written; a second pass launches nothing",
          (first, len(launches) - n_before), ((["94"], True, ["protection"], False), 0))
    U, launches, ok = d_case("d02", ["1", "ok"])
    check("D02 a plain child exit 1: no retry, stage stopped, no HALT (not a protection failure)",
          (launches, os.path.exists(U.HALTF), U.LOG["runs"][-1]["cls"], ok), (["1"], False, "child", False))
    U, launches, ok = d_case("d03", ["99", "ok"])
    with open(os.path.join(U.ROOT, "uncr_par_gap_fwd05", "driver_stamp.json"), encoding="utf-8") as f:
        st = json.load(f)
    check("D03 gpu_guard stop (99) then a clean run: retried once under the GPU precondition, stamped as cmdr-6 with the v3 wrappers, all three valid",
          (launches[:2], U.LOG["runs"][0]["cls"], U.LOG["runs"][0]["tries"], st["driver_version"], "isaac_slot_v3.py" in st["code_sha256"],
           [r.get("verdict") for r in U.LOG["runs"]], ok),
          (["99", "ok"], "ok", 2, "cmdr-6", True, ["valid", "valid", "valid"], True))
    U, launches, ok = d_case("d04", ["99"])
    check("D04 gpu_guard stops every time: GPU_RETRIES 2 means 3 launches, then the stage stops without HALT",
          (launches, U.LOG["runs"][-1]["cls"], os.path.exists(U.HALTF), ok), (["99", "99", "99"], "gpu", False, False))
    U, launches, ok = d_case("d05", ["99", "ok"], moves=3)
    check("D05 (17e 3.3) q_post hash changes after the first launch, before its retry: the retry is not launched",
          (launches, U.LOG["runs"][-1]["cls"], ok), (["99"], "frozen", False))
    U = load_v5(tmpdir("d05_pre"))
    U.freeze()
    original_code_sha = U.code_sha
    U.code_sha = lambda: dict(original_code_sha(), **{"q_post.py": "0" * 64})
    gpu_calls = []
    U.gpu_ready = lambda: (gpu_calls.append(1) or True, "")
    result = U.run_one("uncr_par_gap_fwd05", ["q_eval_cmdr.py"], "d05_pre")
    check("D05_PRE frozen before GPU wait does not query GPU or launch", (result["cls"], len(gpu_calls)), ("frozen", 0))
    U, launches, ok = d_case("d05b", ["ok"], moves=3)
    check("D05b (17e 3.3) q_post hash changes while the first launch runs (exit 0): classified frozen, not stamped, nothing more launched",
          (launches, U.LOG["runs"][-1]["cls"], os.path.exists(os.path.join(U.ROOT, "uncr_par_gap_fwd05", "driver_stamp.json")), ok),
          (["ok"], "frozen", False, False))
    for changed, expected in ((False, (1, "ok")), (True, (0, "frozen"))):
        U = load_v5(tmpdir("d11_changed" if changed else "d11_control"))
        U.freeze()
        launches = stub_launcher(U, ["ok"])
        original_code_sha = U.code_sha
        switched = [False]

        def code_during_gpu():
            result = original_code_sha()
            if switched[0]:
                result["q_post.py"] = "0" * 64
            return result

        U.code_sha = code_during_gpu

        def gpu_wait():
            switched[0] = changed
            return True, ""

        U.gpu_ready = gpu_wait
        result = U.run_one("uncr_par_gap_fwd05", ["q_eval_cmdr.py"], "d11")
        check("D11_CHANGED GPU wait changes q_post before the child" if changed else "D11_CONTROL unchanged code after GPU wait",
              (len(launches), result["cls"]), expected)
    t = tmpdir("frozen_exec")
    fixture = os.path.join(t, "registered_input.bin")
    sentinel = os.path.join(t, "child_ran.txt")
    with open(fixture, "wb") as f:
        f.write(b"known input")
    code_hashes = {"frozen_exec.py": bsha(os.path.join(HERE, "frozen_exec.py"))}
    input_hashes = {"fixture": bsha(fixture)}
    digest = FZ.manifest_digest(code_hashes, input_hashes)
    manifest = {"code_sha256": code_hashes, "inputs_sha256": input_hashes,
                "code_paths": {"frozen_exec.py": os.path.join(HERE, "frozen_exec.py")},
                "input_paths": {"fixture": fixture}, "registered_ok": True, "code_manifest_sha256": digest}
    mfpath = os.path.join(t, "manifest.json")
    with open(mfpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    child = [PY, "-B", "-c", f"import sys;open({sentinel!r},'a').write('ran');sys.exit(7)"]
    rc = FZ.main(["--manifest", mfpath, "--expected-sha", digest, "--"] + child)
    check("A2_CONTROL frozen_exec starts the child and propagates exit 7", (rc, os.path.exists(sentinel)), (7, True))
    with open(fixture, "ab") as f:
        f.write(b" changed")
    rc = FZ.main(["--manifest", mfpath, "--expected-sha", digest, "--"] + child)
    with open(sentinel, encoding="utf-8") as f:
        sentinel_text = f.read()
    check("A2_CHANGED frozen_exec rejects input change before child", (rc, sentinel_text), (92, "ran"))
    U, launches, ok = d_case("a2_92", ["92"])
    check("A2_92 slot return 92 causes protection HALT without retry", (launches, os.path.exists(U.HALTF), ok), (["92"], True, False))
    argv = U.slot_argv("uncr_par_gap_fwd05", ["q_eval_cmdr.py"], "a2", 1)
    after_sep = argv[argv.index("--") + 1:]
    check("A2_ARG frozen_exec is the first slot child and gets the manifest", after_sep[:4],
          [PY, "frozen_exec.py", "--manifest", os.path.join(U.ROOT, "manifest_v6.json")])
    observed = RV.environment_fingerprint()
    check("A3_CONTROL supported environment has no differing fields", RV.environment_differences(observed), [])
    for field in RV.EXPECTED_ENV:
        changed = dict(observed)
        changed[field] = "intentionally different"
        check("A3_FIELD_" + field + " one changed fingerprint field is rejected", RV.environment_differences(changed), [field])
    original_fingerprint = RV.environment_fingerprint
    RV.environment_fingerprint = lambda: dict(observed, OPENBLAS_CORETYPE="Nehalem")
    try:
        try:
            RV.revalidate(os.path.join(SAFE_BASE, "missing_for_env_gate"))
            rejected = False
        except RV.UnsupportedEnvironment as ex:
            rejected = str(ex).startswith("[post-env] 다른 칸: OPENBLAS_CORETYPE")
    finally:
        RV.environment_fingerprint = original_fingerprint
    check("A3_GATE unsupported environment stops before data reading", rejected, True)
    sleeps = []

    def stop_on_sleep(s):
        sleeps.append(s)
        os.makedirs(os.path.dirname(U5_STOP[0]), exist_ok=True)
        open(U5_STOP[0], "w").close()
    t = tmpdir("d06")
    U = load_v5(t)
    U5_STOP = [U.STOPF]
    U.freeze()
    launches = stub_launcher(U, ["99", "ok"], stop_on_sleep)
    ok = U.run_set(GF)
    check("D06 (17e 3.3) STOP appears during the wait before a retry: the wait ends at the next step (1 sleep, not 120), no second launch",
          (launches, len(sleeps), U.LOG["runs"][-1]["cls"], ok), (["99"], 1, "stop", False))
    U, launches, ok = d_case("d07", ["rootfail"])
    check("D07 (17e 3.2) exit 0 but the log has the robot root reference failure: protection, HALT, nothing more launched",
          (launches, os.path.exists(U.HALTF), U.LOG["runs"][-1]["cls"]), (["rootfail"], True, "protection"))
    frees = iter([20000] + [100] * 1000)
    U, launches, ok = d_case("d08", ["99", "ok"], gpu=lambda: next(frees))
    check("D08 GPU 1 free memory stays low before the retry: no second launch, stopped as gpu_precondition, no HALT",
          (launches, U.LOG["runs"][-1]["cls"], os.path.exists(U.HALTF)), (["99"], "gpu_precondition", False))
    U, launches, ok = d_case("d09", ["outside"])
    check("D09 exit 0 but the new run's assigned USD folder is outside its root: protection from the revalidation, HALT, no stamp",
          (launches, os.path.exists(U.HALTF), os.path.exists(os.path.join(U.ROOT, "uncr_par_gap_fwd05", "driver_stamp.json"))), (["outside"], True, False))

    # ===== §5.3 · §5.4 launch arguments and registries ===========================================================================
    t = tmpdir("l01")
    U = load_v5(t)
    other = os.path.join(t, "elsewhere", "logs")
    os.makedirs(other)
    os.makedirs(U.SLOT, exist_ok=True)
    with open(U.REG_V2, "w", encoding="utf-8") as f:
        json.dump({"20261013_185709_9514": os.path.join(other, "cmdr_s1043_on_u4000.log").replace("\\", "/")}, f)
    v2_before = bsha(U.REG_V2)
    argv = U.slot_argv("uncr_par_pit_fwd03", ["q_eval_cmdr.py"], "A", 1)

    def arg(name):
        return argv[argv.index(name) + 1] if name in argv else None
    sd = [norm(x) for x in (arg("--scan_dirs") or "").split(",")]
    check("L01 (17e 5.3 · 5.4) v5 calls isaac_slot_v3.py --expect_conversions 1 with usd_isolate_run_v3.py, the separate v3 registry, and scans "
          "out_branch, the old and new roots and the folder of a log named in the v2 registry; the v2 registry file is only read",
          (os.path.basename(argv[1]), arg("--expect_conversions"), "usd_isolate_run_v3.py" in argv,
           norm(arg("--registry") or "") == norm(os.path.join(t, "slot", "isaac_usd_registry_v3.json")),
           norm(os.path.join(HERE, "out_branch")) in sd, norm(os.path.join(t, "old")) in sd, norm(os.path.join(t, "new")) in sd, norm(other) in sd,
           bsha(U.REG_V2) == v2_before),
          ("isaac_slot_v3.py", "1", True, True, True, True, True, True, True))

    S2 = load(os.path.join(HERE, "isaac_slot.py"), "slot_v2_read_only")
    S3 = load(os.path.join(HERE, "isaac_slot_v3.py"), "slot_v3_read_only")
    rt = tmpdir("l02")
    r2, r3, shared = os.path.join(rt, "reg_v2.json"), os.path.join(rt, "reg_v3.json"), os.path.join(rt, "shared.json")
    log_a, log_b = norm(os.path.join(rt, "a.log")), norm(os.path.join(rt, "b.log"))
    folder_b = norm(os.path.join(rt, "b_root", "IsaacLab", "usd_20261014_000000_1"))

    def v2_then_v3_then_v2(v2_path, v3_path):
        stale = {}  # v2 participant A reads its registry (empty) before B's update
        S3.registry_update(v3_path, {folder_b: "20261014_000000_1"}, log_b)  # v3 participant B, under its lock
        S2.write_reg(types.SimpleNamespace(registry=v2_path), stale, ["20261014_000001_2"], log_a)  # A's final write, outside any lock
        with open(v3_path, encoding="utf-8") as f:
            return json.load(f)
    sep = v2_then_v3_then_v2(r2, r3)
    same = v2_then_v3_then_v2(shared, shared)
    with open(r2, encoding="utf-8") as f:
        v2_after = json.load(f)
    check("L02 (17e 5.4) v2's unlocked final write after a v3 update: with separate files the v3 record stays (and v2's file holds only v2's entry); "
          "with one shared file the v3 record is lost (the hazard the separation removes)",
          (sep, v2_after, folder_b in same), ({folder_b: log_b}, {"20261014_000001_2": log_a}, False))

    t = tmpdir("l03")
    U = load_v5(t)
    fake_branch = os.path.join(t, "out_branch")
    os.makedirs(fake_branch)
    U.BR_NEW = fake_branch
    mine = norm(os.path.join(U.ROOT, "usd", "uncr_par_pit_fwd03-A-try1", "IsaacLab", "usd_20261014_000002_3"))
    with open(os.path.join(fake_branch, "cmdr_s1043_on_u4000.log"), "w", encoding="utf-8") as f:
        f.write(f"[Warning] reference @{mine}/go2.usd@\n")
    me = norm(os.path.join(U.ROOT, "uncr_par_pit_fwd03.log"))
    conf, unreadable, _ = S3.scan_logs(types.SimpleNamespace(scan_dirs=",".join(U.scan_dirs())), me, {mine: "20261014_000002_3"}, [])
    check("L03 (17e 5.4) a GPU 0 v2 log in out_branch naming the same absolute USD folder is found by the v3 slot's log scan over v5's scan dirs",
          conf, {mine: [norm(os.path.join(fake_branch, "cmdr_s1043_on_u4000.log"))]})

    # ===== §5.3 · §5.6 · §6 the gate, the approval, the plan and post ===========================================================
    t = tmpdir("m01")
    U = load_v5(t)
    check("M01 (17e 6) new runs to launch: 75 by default (reuse no), 73 when the old par / off of discrete_obstacles/fwd05 are reused",
          (len(U.plan_full(False)), len(U.plan_full(True)), ("discrete_obstacles", "fwd05", "par") in U.plan_full(True),
           ("discrete_obstacles", "fwd05", "par") in U.plan_full(False)), (75, 73, False, True))
    rc = run_main(U, ["--stages", "manifest"])
    with open(os.path.join(U.ROOT, "manifest_v6.json"), encoding="utf-8") as f:
        mf = json.load(f)
    check("M03 --stages manifest without --reuse_partial: registered manifest ok, new runs 75, an approval template that is pending",
          (rc, mf["registered_ok"], mf["new_runs"], mf["approval_template"]["decision"]), (0, True, 75, "pending"))

    TO = tmpdir("old")
    OLD = os.path.join(TO, "out_uncr")
    make_old(OLD)
    appr, p_old, rep_old = approve(OLD, os.path.join(TO, "reval"))
    old_snap = snapshot(OLD)

    t = tmpdir("p03")
    U = load_v5(t, OLD, appr)
    rc = run_main(U, ["--stages", "post"])
    with open(os.path.join(U.ROOT, "post_v6.json"), encoding="utf-8") as f:
        pj = json.load(f)
    check("P03 post (manifest diag) with the approved old bundle: exit 0, 7 valid, old bundle ok, and nothing written into the old root",
          (rc, pj["complete"], pj["old_bundle_ok"], snapshot(OLD) == old_snap,
           os.path.basename(pj["reval"]["old"]), os.path.basename(pj["reval"]["new"])),
          (0, 7, True, True, "revalidate_v6_old.json", "revalidate_v6_new.json"))

    rows = {}
    for reuse in ("no", "yes"):
        t = tmpdir(f"p02{reuse}")
        U = load_v5(t, OLD, appr)
        rc = run_main(U, ["--stages", "post", "--manifest", "full", "--reuse_partial", reuse])
        with open(os.path.join(U.ROOT, "UNCR-cells-v6.csv"), encoding="utf-8") as f:
            rows[reuse] = (rc, {(r["terrain"], r["cell"]): r for r in csv.DictReader(f)})
    do_no, do_yes, gap = rows["no"][1][("discrete_obstacles", "fwd05")], rows["yes"][1][("discrete_obstacles", "fwd05")], rows["no"][1][("gap", "fwd05")]
    check("P02 (17e 6) post --manifest full: discrete_obstacles/fwd05 is missing without reuse and incomplete with reuse, never with numbers "
          "(also not in the revalidator's cell); gap/fwd05 valid with its numbers (par surv 99); exit 1 both",
          (rows["no"][0], rows["yes"][0], do_no["state"], do_yes["state"], do_no.get("par_surv", ""), do_yes.get("par_surv", ""), gap["state"], gap["par_surv"],
           rep_old["cells"]["discrete_obstacles/fwd05"]["verdict"], rep_old["cells"]["discrete_obstacles/fwd05"]["stats"]),
          (1, 1, "missing", "incomplete", "", "", "valid", "99", "incomplete", {}))

    def gate_case(case, reuse="no", new_runs=75, decision="approve", argv_reuse=None, mutate=None, approved=None, reval=None, old=OLD,
                  approve_bundle=None):
        t = tmpdir(case)
        U = load_v5(t, old, approved or appr)
        calls = stub_run_set(U)
        rv_path = reval or p_old
        ap = write_approval(U, os.path.join(t, "approval.json"), rv_path, reuse, new_runs, decision, old_bundle=approve_bundle)
        if mutate:
            mutate(U, t)
        rc = run_main(U, ["--stages", "full", "--reval", rv_path, "--approval", ap, "--reuse_partial", argv_reuse or reuse])
        return U, rc, calls

    U, rc, calls = gate_case("g01")
    with open(os.path.join(U.ROOT, "full_gate_v6.json"), encoding="utf-8") as f:
        gate = json.load(f)
    check("G01 approved old bundle, its v2 revalidation, an approval bound to it: full starts with 75 new runs, gate written for this attempt",
          (rc, calls, gate["attempt"] == U.ATTEMPT, gate["approved_by"], len(gate["planned"])), (0, [75], True, "tester", 75))
    U, rc, calls = gate_case("g01y", reuse="yes", new_runs=73)
    check("G01b the same with --reuse_partial yes and an approval for 73: full starts with 73", (rc, calls), (0, [73]))
    U, rc, calls = gate_case("g02", decision="pending")
    check("G02 (17e 5.6) approval file still pending: full not started", (rc, calls), (1, []))
    U, rc, calls = gate_case("g03", argv_reuse="yes")
    check("G03 approval for reuse no / 75 runs, launched with --reuse_partial yes: full not started", (rc, calls), (1, []))
    bad_rv = os.path.join(tmpdir("g06b"), "revalidate.json")
    with open(p_old, encoding="utf-8") as f:
        js = json.load(f)
    js["judge_code"]["q_post.py"]["sha256_loaded"] = "0" * 64
    with open(bad_rv, "w", encoding="utf-8") as f:
        json.dump(js, f)
    U, rc, calls = gate_case("g06", reval=bad_rv)
    check("G06 (17e 3.4) a revalidation recorded as made with other q_post bytes: full not started", (rc, calls), (1, []))

    def halt_file(U, t):
        os.makedirs(U.ROOT, exist_ok=True)
        with open(U.HALTF, "w", encoding="utf-8") as f:
            json.dump({"tag": "uncr_par_pit_fwd05", "rc": 94}, f)
    U, rc, calls = gate_case("d10", mutate=halt_file)
    check("D10 (17e 3.2) HALT_v6.json from an earlier protection failure: full not started", (rc, calls), (1, []))

    def reg_off(U, t):
        U.REGISTERED_CODE = dict(U.REGISTERED_CODE, **{"q_eval_cmdr.py": "0" * 64})
    U, rc, calls = gate_case("m02", mutate=reg_off)
    check("M02 (17e 5.3) the evaluator differs from the registered (old approved) value: full not started (no exemption beyond the wrappers)",
          (rc, calls, any("registered" in x["what"] for x in U.LOG["failures"])), (1, [], True))

    TZ = tmpdir("g05")
    OZ = os.path.join(TZ, "out_uncr")
    make_old(OZ, {(m, f, c): {"edit": cmds_zero} for f, c in DIAG for m in ("par", "off", "on")}, with_partial=False)
    apz, pz, repz = approve(OZ, os.path.join(TZ, "reval"))
    U, rc, calls = gate_case("g05", approved=apz, reval=pz, old=OZ)
    check("G05 (17e 3.1 fourth counterexample) every diag run's stored commands 0, a fresh revalidation and an approval of it: diag invalid, "
          "full not started", (repz["counts"]["diag_cells"]["invalid"], rc, calls), (7, 1, []))

    TP = tmpdir("g05b")
    OP = os.path.join(TP, "out_uncr")
    make_old(OP, {("on", "gap", "fwd05"): {"edit": dr_other}})
    app_p, pp, rep_p = approve(OP, os.path.join(TP, "reval"))
    U, rc, calls = gate_case("g05b", approved=app_p, reval=pp, old=OP)
    check("G05b all 23 runs valid but gap/fwd05 is not a recorded pair (DR fingerprint): full not started",
          (rep_p["counts"]["runs"]["valid"], rep_p["cells"]["gap/fwd05"]["verdict"], rc, calls), (23, "hold", 1, []))

    TQ = tmpdir("g07")
    OQ = os.path.join(TQ, "out_uncr")
    make_old(OQ, {("par", "discrete_obstacles", "fwd05"): {"edit": nan_x_env0}})
    app_q, pq, rep_q = approve(OQ, os.path.join(TQ, "reval"))
    U, rc, calls = gate_case("g07", reuse="yes", new_runs=73, approved=app_q, reval=pq, old=OQ)
    check("G07 --reuse_partial yes while the old discrete_obstacles/fwd05 par is invalid (diag cells all valid): full not started",
          (rep_q["counts"]["diag_cells"]["valid"], rc, calls), (7, 1, []))

    append_log(OLD, "uncr_par_wave_fwd05", None)  # one run re-recorded after the review: other log bytes, a new stamp
    write_stamp(OLD, "uncr_par_wave_fwd05")
    rep_new = RV.revalidate(OLD)
    p_new = RV.write_report(rep_new, os.path.join(TO, "reval2"))
    U, rc, calls = gate_case("g04", reval=p_new, approve_bundle=rep_new["bundle_sha256"])
    check("G04 (17e 5.3) the old root changed after the review (one run re-recorded, still valid), with a fresh revalidation and approval of the "
          "changed root: not the approved bundle, full not started",
          (rep_new["cells"]["wave/fwd05"]["verdict"], rep_new["bundle_sha256"] != appr["bundle_sha256"], rc, calls), ("valid", True, 1, []))
    t = tmpdir("p04")
    U = load_v5(t, OLD, appr)
    rc = run_main(U, ["--stages", "post"])
    with open(os.path.join(U.ROOT, "UNCR-cells-v6.csv"), encoding="utf-8") as f:
        prow = {(r["terrain"], r["cell"]): r for r in csv.DictReader(f)}
    check("P04 (17e 5.3) post on an old root that is no longer the approved bundle: the diag cells are not used (invalid, reason named), exit 1",
          (rc, prow[("gap", "fwd05")]["state"], "old bundle not the approved one" in prow[("gap", "fwd05")]["why"], prow[("gap", "fwd05")].get("par_surv", "")),
          (1, "invalid", True, ""))

    t = tmpdir("e01")
    os.makedirs(os.path.join(t, "old"))
    env = dict(os.environ, **env_for(t), CUDA_VISIBLE_DEVICES="-1", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    r = subprocess.run([PY, "-B", V5_SCRIPT, "--stages", "post"], cwd=HERE, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=900)
    with open(os.path.join(t, "new", "post_v6.json"), encoding="utf-8") as f:
        pj = json.load(f)
    check("E01 (17c P1 kept) public CLI --stages post on empty old and new roots: exit 1, the 7 diag cells missing",
          (r.returncode, pj["requested_missing"]), (1, DIAG_KEYS))

    # ===== the real out_uncr, read only ===========================================================================================
    if not SKIP_REAL:
        snap0 = snapshot(REAL_ROOT)
        rep = RV.revalidate(REAL_ROOT)
        check("X01 real out_uncr under revalidator v2 (command contract included): 23 runs valid, 21 diag, 7 diag cells valid, the reviewed bundle "
              "hash, frozen, and every file unchanged",
              (rep["counts"]["runs"], rep["counts"]["diag_runs"]["valid"], rep["counts"]["diag_cells"]["valid"], rep["bundle_sha256"], rep["frozen_ok"],
               snapshot(REAL_ROOT) == snap0),
              ({"valid": 23, "hold": 0, "invalid": 0}, 21, 7, REAL_BUNDLE, True, True))
        for k in DIAG_KEYS + ["discrete_obstacles/fwd05"]:
            cc = rep["cells"].get(k) or {}
            print("REAL", k, cc.get("verdict"), cc.get("runs"), {m: (s["surv"], s["cross"]) for m, s in (cc.get("stats") or {}).items()},
                  " | ".join(cc.get("reasons") or [])[:200])
finally:
    pass  # Work-folder fixtures remain for inspection.
print("FAILS", fails)
sys.exit(1 if fails else 0)
