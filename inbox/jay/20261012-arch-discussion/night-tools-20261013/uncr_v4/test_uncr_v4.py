"""CPU tests for uncr_revalidate.py and unseen_driver_cmdr_v4.py (lead sub task 10/13 night · ASTRA 17c counterexamples kept).

UNCR_REVAL_SCRIPT / UNCR_V4_SCRIPT may point at mutated copies (mutate_uncr_v4.py). UNCR_TEST_SKIP_REAL=1 skips the read-only pass
over the real _eval/out_uncr. Expected values are written by hand, not computed by the code under test. Fixture runs get their
episodes.csv / cells.json from the evaluator's own q_post (as q_eval_cmdr.py:648~650 does). No Isaac, no GPU. Fixture roots live in
the system temp folder and are removed at the end. Exit 1 when any check fails.
"""
import csv
import hashlib
import importlib.util
import io
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
RV_SCRIPT = os.path.abspath(os.environ.get("UNCR_REVAL_SCRIPT", os.path.join(HERE, "uncr_revalidate.py")))
V4_SCRIPT = os.path.abspath(os.environ.get("UNCR_V4_SCRIPT", os.path.join(HERE, "unseen_driver_cmdr_v4.py")))
SKIP_REAL = os.environ.get("UNCR_TEST_SKIP_REAL") == "1"
REAL_ROOT = os.path.join(HERE, "out_uncr")
fails = []

# --- the collection contract, written out by hand (unseen_driver_cmdr.py v3 lines 36~48) ---------------------------------
E1 = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192"
YAML = E1 + "/params/env.yaml"
BRD = os.path.join(HERE, "out", "branch")
CK = {"par": (E1 + "/model_20000.pt", 20000, ""),
      "off": (os.path.join(BRD, "cmdr_s1042_off_u4000", "model_24000.pt").replace("\\", "/"), 24000, YAML),
      "on": (os.path.join(BRD, "cmdr_s1042_on_u4000", "model_24000.pt").replace("\\", "/"), 24000, YAML)}
DIAG = [("gap", "fwd05"), ("stepping_stones", "fwd05"), ("floating_ring", "fwd05"), ("rails", "fwd05"), ("wave", "fwd05"),
        ("gap", "back03"), ("discrete_obstacles", "back03")]
DIAG_KEYS = ["gap/fwd05", "stepping_stones/fwd05", "floating_ring/fwd05", "rails/fwd05", "wave/fwd05", "gap/back03", "discrete_obstacles/back03"]
CMD = {"fwd05": [0.5, 0.0, 0.0], "back03": [-0.3, 0.0, 0.0], "fwd03": [0.3, 0.0, 0.0], "fwd10": [1.0, 0.0, 0.0]}
V3_CODE = ("q_eval_cmdr.py", "q_metrics.py", "isaac_slot.py", "usd_isolate_run.py", "gpu_guard.py", "unseen_driver_cmdr.py")
USD_KEY = "20261013_190023_7028"
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
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


QP = load(os.path.join(HERE, "q_post.py"), "q_post_fixture")
RV = load(RV_SCRIPT, "rv_under_test")
_BASE = {}


def base_arrays(cell):
    """100 envs x 1001 states. Each env walks +x at 0.01 m per state from 0.2 m past its origin; env 50 hits the ground with the base
    at state 78 (1.56 s, base_contact) and is reset there, as Isaac does."""
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


def write_stamp(root, tag, code=None):
    d = os.path.join(root, tag)
    with open(os.path.join(root, f"{tag}.slot.json"), encoding="utf-8") as f:
        att = json.load(f)["attempt"]
    out = {f: bsha(os.path.join(d, f)) for f in ("meta.json", "cells.json", "episodes.csv", "traj.npz", "env_origins.npy")}
    out.update({e: bsha(os.path.join(root, f"{tag}{e}")) for e in (".log", ".guard.json", ".slot.json")})
    cs = {f: fsha(os.path.join(HERE, f)) for f in V3_CODE}
    cs.update(code or {})
    with open(os.path.join(d, "driver_stamp.json"), "w", encoding="utf-8") as f:
        json.dump({"attempt": att, "out_sha256": out, "code_sha256": cs, "t": "2026-10-13 19:01:32"}, f, indent=1)


def make_run(root, m, fam, cell, edit=None, post_edit=None, after_stamp=None, code=None, att=None, stamp=True):
    tag = f"uncr_{m}_{fam}_{cell}"
    d = os.path.join(root, tag)
    os.makedirs(d, exist_ok=True)
    ck, it, yaml = CK[m]
    att = att or f"gT-1-1013000000-{tag}-try1"
    usd_root = norm(os.path.join(root, "usd", f"{tag}-{att}"))
    os.makedirs(f"{usd_root}/IsaacLab/usd_{USD_KEY}", exist_ok=True)
    with open(f"{usd_root}/assigned.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"t": "2026-10-13 19:00:23", "pid": 1, "usd_dir": f"{usd_root}/IsaacLab/usd_{USD_KEY}", "asset_path": "go2.urdf",
                            "cfg_class": "UnitreeUrdfFileCfg", "patched_by": "loader"}) + "\n")
    with open(f"{usd_root}/isolate_state.json", "w", encoding="utf-8") as f:
        json.dump({"patched_by": "loader"}, f)
    arr, org = base_arrays(cell)
    if (m, fam, cell) == ("on", "gap", "fwd05"):
        arr["traj"][808:, 50, 11] = np.nan  # as the real uncr_on_gap_fwd05: ground ray miss long after env 50's fall (ASTRA 17c §1)
    meta = {"args": {"checkpoint": ck, "policy": "student", "families": fam, "cells": cell, "episodes": 100, "difficulty": 0.5,
                     "terrain_set": "unseen10", "eval_seed": 1000, "obs_noise": False, "tag": tag, "outdir": root, "full_record": False,
                     "train_yaml": yaml},
            "cells": [{"name": cell, "kind": "lin", "cmd": CMD[cell], "duration_s": 20.0, "switch_s": None, "src": "LEAD_TEMP"}],
            "families": [fam], "N": 100, "T_steps": 1000, "checkpoint_sha256": fsha(ck), "loaded_iter": it,
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
                f"Warning: In </go2/Head_upper/visuals>: Unresolved reference prim path @{usd_root}/IsaacLab/usd_{USD_KEY}/configuration/"
                "go2_physics.usd@</visuals/Head_upper>\n[INFO]: Time taken for scene creation : 4.4 seconds\n"
                f"[Q-EVAL] done {tag} N 100 rollout_s 1.0\n")
    with open(os.path.join(root, f"{tag}.guard.json"), "w", encoding="utf-8") as f:
        json.dump({"exit_code": 0, "stopped_by_guard": False}, f)
    with open(os.path.join(root, f"{tag}.slot.json"), "w", encoding="utf-8") as f:
        json.dump({"attempt": att, "cmd": [PY, "gpu_guard.py", "--gpu", "1", "--", PY, "usd_isolate_run.py", "q_eval_cmdr.py", "--headless",
                                           "--tag", tag, "--checkpoint", ck], "usd_root": usd_root, "state_at_release": "scene_built",
                   "usd_at_release": [USD_KEY], "child_rc": 0, "usd_final": [USD_KEY], "usd_outside_root": [], "conflicts": {}, "slot_rc": 0}, f)
    if post_edit:
        post_edit(root, tag, d)
    if stamp:
        write_stamp(root, tag, code)
    if after_stamp:
        after_stamp(root, tag, d)
    return tag


def make_cell(root, fam="gap", cell="fwd05", edits=None):
    for m in ("par", "off", "on"):
        make_run(root, m, fam, cell, **(edits or {}).get(m, {}))


def make_diag(root, edits=None):
    for fam, cell in DIAG:
        make_cell(root, fam, cell, {m: e for (m, f, c), e in (edits or {}).items() if (f, c) == (fam, cell)})


# --- edits ------------------------------------------------------------------------------------------------------------------
def nan_x_env0(meta, arr, org):
    arr["traj"][:, 0, 0] = np.nan


def fp_empty(meta, arr, org):
    meta.update(terrain_mesh={}, pairing_sha256={}, pairing_sha256_ext={}, terrain_origins_sha256="")


def origins_empty(meta, arr, org):
    meta["terrain_origins_sha256"] = ""


def origins_hash_of_nothing(meta, arr, org):
    meta["terrain_origins_sha256"] = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def mesh_failed(meta, arr, org):
    meta["terrain_mesh"] = "failed: No module named 'pxr'"


def ground_nan_before_fall(meta, arr, org):
    arr["traj"][10:21, 50, 11] = np.nan


def dr_other(meta, arr, org):
    meta["pairing_sha256_ext"]["com"] = hx("other com")


def ckpt_wrong(meta, arr, org):
    meta["checkpoint_sha256"] = "0" * 64


def nonfinite10(meta, arr, org):
    meta["checks_run"]["nonfinite_action_or_obs_count"] = 10


def _npz_edit(d, fn):
    p = os.path.join(d, "traj.npz")
    with np.load(p) as z:
        arr = {k: z[k].copy() for k in z.files}
    fn(arr)
    np.savez_compressed(p, **arr)


def three_channels(root, tag, d):
    _npz_edit(d, lambda a: a.update(traj=a["traj"][:, :, :3].copy()))


def survived_but_term(root, tag, d):
    _npz_edit(d, lambda a: a["term"].__setitem__((500, 3), True))


def term_before_fall(root, tag, d):
    def f(a):
        a["term"][78, 50] = False
        a["term"][60, 50] = True
    _npz_edit(d, f)


def fam_index_one(root, tag, d):
    _npz_edit(d, lambda a: a["fam"].__setitem__(slice(None), 1))


def _csv_edit(d, fn):
    p = os.path.join(d, "episodes.csv")
    with open(p, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    fn(rows)
    with open(p, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)


def env_negative(root, tag, d):
    def f(rows):
        i = rows[0].index("env")
        rows[6][i] = "-1"
    _csv_edit(d, f)


def csv_value_edit(root, tag, d):
    def f(rows):
        i = rows[0].index("act_abs_mean")
        rows[8][i] = "0.2"
    _csv_edit(d, f)


def origins_shift(root, tag, d):
    p = os.path.join(d, "env_origins.npy")
    o = np.load(p)
    o[:, 0] += 3.0
    np.save(p, o)


def slot_outside(root, tag, d):
    p = os.path.join(root, f"{tag}.slot.json")
    with open(p, encoding="utf-8") as f:
        s = json.load(f)
    s["usd_outside_root"] = [USD_KEY]
    with open(p, "w", encoding="utf-8") as f:
        json.dump(s, f)


def log_other_path(root, tag, d):
    with open(os.path.join(root, f"{tag}.log"), "a", encoding="utf-8") as f:
        f.write(f"Warning: In </go2/Head_lower/visuals>: Unresolved reference prim path @C:/other/IsaacLab/usd_{USD_KEY}/go2.usd@</visuals>\n")


def assigned_outside(root, tag, d):
    with open(os.path.join(root, f"{tag}.slot.json"), encoding="utf-8") as f:
        ur = json.load(f)["usd_root"]
    with open(f"{ur}/assigned.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"usd_dir": f"C:/Users/x/AppData/Local/Temp/IsaacLab/usd_{USD_KEY}", "patched_by": "loader"}) + "\n")


def append_csv_line(root, tag, d):
    with open(os.path.join(d, "episodes.csv"), "a", encoding="utf-8", newline="") as f:
        f.write("\r\n")


# --- helpers ----------------------------------------------------------------------------------------------------------------
TMPS = []


def case_dir(case):
    t = tempfile.mkdtemp(prefix=f"uncr_v4_{case}_")
    TMPS.append(t)
    return os.path.join(t, "out_uncr"), os.path.join(t, "reval")


def cell_root(case, edits=None):
    root, reval = case_dir(case)
    make_cell(root, "gap", "fwd05", edits)
    return root, reval


def has(reasons, code):
    return any(r.startswith(code) for r in reasons)


def snapshot(root):
    out = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            st = os.stat(os.path.join(dp, f))
            out.append((os.path.relpath(os.path.join(dp, f), root), st.st_size, st.st_mtime_ns))
    return sorted(out)


def load_v4(root, reval):
    os.environ.update(UNCR_ROOT=root, UNCR_REVAL_ROOT=reval, UNCR_REVAL_SCRIPT=RV_SCRIPT)
    return load(V4_SCRIPT, f"v4_{len(TMPS)}_{abs(hash(root))}")


def run_main(U, argv):
    sys.argv = ["unseen_driver_cmdr_v4.py"] + argv
    try:
        U.main()
    except SystemExit as e:
        return e.code
    return None


def stub_run_set(U):
    calls = []
    U.run_set = lambda stage, cells: calls.append((stage, len(cells)))
    return calls


def cli(root, reval, argv):
    env = dict(os.environ, UNCR_ROOT=root, UNCR_REVAL_ROOT=reval, UNCR_REVAL_SCRIPT=RV_SCRIPT, CUDA_VISIBLE_DEVICES="-1",
               PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    r = subprocess.run([PY, "-B", V4_SCRIPT] + argv, cwd=HERE, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    return r.returncode


def post_json(root):
    with open(os.path.join(root, "post_v4.json"), encoding="utf-8") as f:
        return json.load(f)


def fake_launcher(root, launched):
    """stands in for isaac_slot + Isaac: writes a synthetic run (no stamp) with the slot attempt the driver asked for."""
    def run_one(tag, cmd, att, tries=3):
        _, m, rest = tag.split("_", 2)
        fam, cell = rest.rsplit("_", 1)
        make_run(root, m, fam, cell, att=f"{att}-try1", stamp=False)
        launched.append(tag)
        return 0, 1
    return run_one


def code_moves_after(U, n_real):
    real = U.code_sha
    n = [0]

    def moving():
        n[0] += 1
        c_ = real()
        if n[0] > n_real:
            c_["q_eval_cmdr.py"] = "0" * 64
        return c_
    U.code_sha = moving


try:
    # ===== revalidator, one cell (gap / fwd05) ===================================================================================
    root, reval = cell_root("r01")
    R01_ROOT, R01_REVAL = root, reval
    rep = RV.revalidate(root)
    c, on = rep["cells"]["gap/fwd05"], rep["runs"]["uncr_on_gap_fwd05"]
    check("R01 (17c §1) on env 50 channel 11 NaN at states 808~1000, after its base contact at 1.56 s: three runs valid, cell valid, "
          "193 NaN counted apart, none inside the window",
          (c["runs"], c["verdict"], on["nan"]["ground_ch11_after_window"], on["nan"]["ground_ch11_after_window_envs"], on["nan"]["ground_ch11_in_window"]),
          (ALL_VALID, "valid", 193, [50], 0))
    check("R01b counts by hand: 99 of 100 survive, 99 pass the zone end 4.0 m (0.2 + 0.01 j reaches it at j 380; env 50 reaches 0.97 m before its fall)",
          on["stats"], {"n": 100, "surv": 99, "cross": 99, "alive_cross": 99, "zone_end": 4.0})
    check("R01c (17c §5) v3 stamp: q_post provenance 「출처 미확인」, q_post on disk gives the same bytes, collection code recorded as it was",
          (on["q_post"]["in_stamp"], on["q_post"]["provenance"][:6], on["q_post"]["recompute_equal"],
           on["code_at_collection"]["q_eval_cmdr.py"] == fsha(os.path.join(HERE, "q_eval_cmdr.py"))),
          (False, "출처 미확인", {"episodes.csv": True, "cells.json": True}, True))

    root, _ = cell_root("r02", {"on": {"edit": nan_x_env0}})
    rep = RV.revalidate(root)
    c = rep["cells"]["gap/fwd05"]
    check("R02 (17c P1) on env 0 x NaN at every state, checks_run 0, stamp made after: on invalid (required channel in the window), cell invalid",
          (c["runs"], c["verdict"], has(rep["runs"]["uncr_on_gap_fwd05"]["invalid"], "[window-required]")),
          ({"par": "valid", "off": "valid", "on": "invalid"}, "invalid", True))

    for case, ed, what in (("r03", fp_empty, "(17c P1) mesh / initial state / DR fingerprints {} and origins '' in all three"),
                           ("r04", origins_empty, "(17c) origins fingerprint '' in all three"),
                           ("r05", origins_hash_of_nothing, "origins fingerprint = sha256 of zero bytes (hash of an empty array) in all three"),
                           ("r06", mesh_failed, "terrain_mesh 'failed: ...' string in all three")):
        root, _ = cell_root(case, {m: {"edit": ed} for m in ("par", "off", "on")})
        rep = RV.revalidate(root)
        c = rep["cells"]["gap/fwd05"]
        check(f"{case.upper()} {what}: equal across the three but not the evaluator's form: all invalid, cell invalid",
              (c["runs"], c["verdict"], all(has(r["invalid"], "[fp-form]") for r in rep["runs"].values())),
              ({"par": "invalid", "off": "invalid", "on": "invalid"}, "invalid", True))

    single = [("R07", "(17c) traj saved with 3 channels [1001, 100, 3]", {"post_edit": three_channels}, "invalid", "[traj-shape]"),
              ("R08", "(17c) episodes.csv env -1 in one row", {"post_edit": env_negative}, "invalid", "[env-negative]"),
              ("R09", "channel 11 NaN at states 10~20 of env 50, before its fall at 78", {"edit": ground_nan_before_fall}, "hold", "[ground-in-window]"),
              ("R10", "(17c) env 3 survived in episodes.csv but term set at state 500", {"post_edit": survived_but_term}, "invalid", "[term-episode]"),
              ("R10b", "env 50 base contact at 1.56 s in episodes.csv but term first set at state 60", {"post_edit": term_before_fall}, "invalid",
               "[term-episode]"),
              ("R11", "episodes.csv changed after the stamp", {"after_stamp": append_csv_line}, "invalid", "[stamp-out]"),
              ("R12", "stamp says q_eval_cmdr.py had another hash", {"code": {"q_eval_cmdr.py": "0" * 64}}, "hold", "[stamp-code]"),
              ("R14", "episodes.csv value edited (stamp made after): q_post on disk gives other bytes", {"post_edit": csv_value_edit}, "hold",
               "[post-recompute]"),
              ("R16", "meta checkpoint_sha256 is not the checkpoint file's", {"edit": ckpt_wrong}, "invalid", "[ckpt]"),
              ("R17", "(17b) checks_run nonfinite count 10", {"edit": nonfinite10}, "invalid", "[checks]"),
              ("R18", "slot record lists a USD folder outside the root", {"post_edit": slot_outside}, "invalid", "[slot]"),
              ("R19", "(17c 2.2) log also names C:/other/IsaacLab/usd_<same key>", {"post_edit": log_other_path}, "invalid", "[usd-path]"),
              ("R22", "env origins moved 3 m in x (traj start 2.8 m from its origin)", {"post_edit": origins_shift}, "invalid", "[env-map]"),
              ("R23", "traj.npz fam index 1 for every env", {"post_edit": fam_index_one}, "invalid", "[env-map]"),
              ("R24", "assigned.jsonl USD folder in the shared temp folder", {"post_edit": assigned_outside}, "invalid", "[usd-path]")]
    R12_ROOT = None
    for tid, what, ed, want, code in single:
        root, _ = cell_root(tid.lower(), {"on": ed})
        if tid == "R12":
            R12_ROOT = root
        rep = RV.revalidate(root)
        r = rep["runs"]["uncr_on_gap_fwd05"]
        cv = rep["cells"]["gap/fwd05"]["verdict"]
        check(f"{tid} {what}: on {want} with {code}, cell {want}", (r["verdict"], has(r[want], code), cv), (want, True, want))
        if tid == "R12":
            check("R13 (17c §5) the stamp's collection hash is kept as it was, the file hash now next to it; the pair notes the code difference",
                  (r["code_at_collection"]["q_eval_cmdr.py"], r["code_now"]["q_eval_cmdr.py"] == fsha(os.path.join(HERE, "q_eval_cmdr.py")),
                   "collection code q_eval_cmdr.py" in rep["cells"]["gap/fwd05"]["pair_diff"]),
                  ("0" * 64, True, True))

    root, _ = cell_root("r15", {"on": {"edit": dr_other}})
    rep = RV.revalidate(root)
    c = rep["cells"]["gap/fwd05"]
    check("R15 (17b 2.4) on's DR fingerprint com differs: runs valid, cell hold, pair_ok False with the key named",
          (c["runs"], c["verdict"], c["pair_ok"], "pairing_sha256_ext.com" in c["pair_diff"]), (ALL_VALID, "hold", False, True))

    before = snapshot(R01_ROOT)
    rep = RV.revalidate(R01_ROOT)
    p = RV.write_report(rep, R01_REVAL)
    with open(p, encoding="utf-8") as f:
        js = json.load(f)
    try:
        RV.write_report(rep, os.path.join(R01_ROOT, "sub"))
        refused = False
    except ValueError:
        refused = True
    check("R20 the input root is only read; the report goes to <reval>/<time>/revalidate.json with 33 input hashes (3 runs x 11 files) + 4 "
          "external, a 64-hex bundle hash; a report path inside the root is refused",
          (snapshot(R01_ROOT) == before, norm(p).startswith(norm(R01_REVAL) + "/"), os.path.basename(p), len(js["inputs_sha256"]),
           len(js["external_sha256"]), len(js["bundle_sha256"]), refused),
          (True, True, "revalidate.json", 33, 4, 64, True))

    root, _ = cell_root("r21")
    orig_read = RV.Reader.read

    def evil(self, path):
        b = orig_read(self, path)
        if norm(path).endswith("uncr_par_gap_fwd05/traj.npz"):
            with open(path, "ab") as f:
                f.write(b"x")
        return b
    RV.Reader.read = evil
    try:
        rep = RV.revalidate(root)
    finally:
        RV.Reader.read = orig_read
    check("R21 an input changes while it is checked: frozen_ok False, that run invalid, its cell invalid",
          (rep["frozen_ok"], has(rep["runs"]["uncr_par_gap_fwd05"]["invalid"], "[frozen]"), rep["cells"]["gap/fwd05"]["verdict"]),
          (False, True, "invalid"))

    # ===== driver v4 ===========================================================================================================
    root, reval = case_dir("v01")
    os.makedirs(root)
    rc = cli(root, reval, ["--stages", "post"])
    pj = post_json(root)
    check("V01 (17c P1) public CLI --stages post on an empty root: exit 1, the 7 diag cells listed missing, 0 complete",
          (rc, pj["requested_missing"], pj["complete"]), (1, DIAG_KEYS, 0))

    V02_ROOT, V02_REVAL = case_dir("v02")
    make_diag(V02_ROOT)
    rc = cli(V02_ROOT, V02_REVAL, ["--stages", "post"])
    pj = post_json(V02_ROOT)
    check("V02 CLI --stages post on 21 valid runs (v3 stamps, incl. the post-fall NaN): exit 0, 7 complete, nothing requested is missing, "
          "v3 records (driver.json, diag_gate.json, UNCR-cells.csv) not written, one revalidate.json under the reval folder",
          (rc, pj["complete"], [pj[f"requested_{k}"] for k in ("missing", "incomplete", "invalid", "hold", "unpaired")],
           [os.path.exists(os.path.join(V02_ROOT, f)) for f in ("driver.json", "diag_gate.json", "UNCR-cells.csv")],
           sum(f == "revalidate.json" for _, _, fs in os.walk(V02_REVAL) for f in fs)),
          (0, 7, [[], [], [], [], []], [False, False, False], 1))

    rc = cli(V02_ROOT, V02_REVAL, ["--stages", "post", "--manifest", "full"])
    pj = post_json(V02_ROOT)
    check("V03 --stages post --manifest full on the same root: exit 1, 25 of the 30 full cells missing (5 fwd05 cells are diag cells)",
          (rc, len(pj["requested_missing"]), pj["requested_invalid"]), (1, 25, []))

    root, reval = case_dir("v04")
    make_diag(root, {("on", "gap", "fwd05"): {"edit": nan_x_env0}})
    V04_ROOT = root
    U = load_v4(root, reval)
    rc = run_main(U, ["--stages", "post"])
    pj = post_json(root)
    check("V04 (17c P1) post with on/gap/fwd05 env 0 x NaN: exit 1, that cell requested_invalid, not a performance failure",
          (rc, pj["requested_invalid"], pj["complete"]), (1, ["gap/fwd05"], 6))

    root, reval = case_dir("v05")
    make_diag(root, {("on", "gap", "fwd05"): {"edit": dr_other}})
    U = load_v4(root, reval)
    rc = run_main(U, ["--stages", "post"])
    pj = post_json(root)
    check("V05 post with on's DR fingerprint different in gap/fwd05: exit 1, listed as unpaired (not hold, not complete)",
          (rc, pj["requested_unpaired"], pj["requested_hold"]), (1, ["gap/fwd05"], []))

    root, reval = case_dir("v06")
    os.makedirs(root)
    with open(os.path.join(root, "diag_gate.json"), "w", encoding="utf-8") as f:
        json.dump({"diag_runs_valid": True, "diag_pair_ok": True, "t": "2000-01-01 00:00:00", "attempt": "g1-1-0101000000"}, f)
    with open(os.path.join(root, "full_gate_v4.json"), "w", encoding="utf-8") as f:
        json.dump({"attempt": "g1-1-0101000000", "t": "2000-01-01 00:00:00", "bundle_sha256": "0" * 64}, f)
    U = load_v4(root, reval)
    calls = stub_run_set(U)
    rc = run_main(U, ["--stages", "full"])
    check("V06 (17c P1) empty root with a 2000-01-01 gate of an unrelated attempt (v3 booleans true, old full_gate_v4.json): full not started, exit 1",
          (rc, calls, any(x["stage"] == "full" for x in U.LOG["failures"])), (1, [], True))

    forged = os.path.join(reval, "forged", "revalidate.json")
    os.makedirs(os.path.dirname(forged))
    with open(forged, "w", encoding="utf-8") as f:
        json.dump({"kind": "uncr_revalidate", "version": "uncr-reval-1", "t": "2000-01-01 00:00:00", "root": norm(root), "frozen_ok": True,
                   "revalidator": {"sha256": bsha(RV_SCRIPT)}, "bundle_sha256": "0" * 64, "attempt": "g1-1-0101000000",
                   "cells": {k: {"verdict": "valid"} for k in DIAG_KEYS}}, f)
    U = load_v4(root, reval)
    calls = stub_run_set(U)
    rc = run_main(U, ["--stages", "full", "--reval", forged])
    check("V07 (17c P1) the same empty root with a forged 2000-01-01 revalidate.json claiming 7 valid cells: full not started, exit 1",
          (rc, calls), (1, []))

    rep = RV.revalidate(V02_ROOT)
    p = RV.write_report(rep, V02_REVAL)
    U = load_v4(V02_ROOT, V02_REVAL)
    calls = stub_run_set(U)
    rc = run_main(U, ["--stages", "full", "--reval", p])
    with open(os.path.join(V02_ROOT, "full_gate_v4.json"), encoding="utf-8") as f:
        gate = json.load(f)
    check("V08 valid 21 runs and a revalidation of exactly them: full starts once with 30 cells, the gate is written for this attempt and bundle",
          (rc, calls, gate["attempt"] == U.ATTEMPT, gate["bundle_sha256"] == rep["bundle_sha256"]), (0, [("full", 30)], True, True))

    bad_rv = os.path.join(V02_REVAL, "other_code", "revalidate.json")
    os.makedirs(os.path.dirname(bad_rv))
    with open(p, encoding="utf-8") as f:
        js = json.load(f)
    js["revalidator"]["sha256"] = "0" * 64
    with open(bad_rv, "w", encoding="utf-8") as f:
        json.dump(js, f)
    U = load_v4(V02_ROOT, V02_REVAL)
    calls = stub_run_set(U)
    rc = run_main(U, ["--stages", "full", "--reval", bad_rv])
    check("V14 the same revalidation but recorded as made by other revalidator code: full not started, exit 1", (rc, calls), (1, []))

    U = load_v4(V02_ROOT, V02_REVAL)
    U.freeze()
    r_ok = U.reusable("par", "gap", "fwd05", "uncr_par_gap_fwd05")
    U = load_v4(V04_ROOT, V02_REVAL)
    U.freeze()
    r_nan = U.reusable("on", "gap", "fwd05", "uncr_on_gap_fwd05")
    U = load_v4(R12_ROOT, V02_REVAL)
    U.freeze()
    r_code = U.reusable("on", "gap", "fwd05", "uncr_on_gap_fwd05")
    check("V13 reuse: a valid run with a v3 stamp yes; the env 0 x NaN run no (stamp hashes match but revalidation invalid); a stamp with "
          "other q_eval_cmdr.py code no", (r_ok, r_nan, r_code), (True, False, False))

    U = load_v4(V02_ROOT, V02_REVAL)
    real_code_sha = U.code_sha
    n_calls = [0]

    def moving_code():
        n_calls[0] += 1
        c_ = real_code_sha()
        if n_calls[0] > 1:
            c_["q_post.py"] = "0" * 64
        return c_
    U.code_sha = moving_code
    rc = run_main(U, ["--stages", "post"])
    check("V12 (17c §5) code that changes after the driver start (q_post.py hash at the end differs): exit 1 with an end failure",
          (rc, any(x["stage"] == "end" for x in U.LOG["failures"])), (1, True))

    U = load_v4(V02_ROOT, V02_REVAL)
    seen = []
    U.subprocess = types.SimpleNamespace(run=lambda argv, **kw: (seen.append(argv), types.SimpleNamespace(returncode=0))[1])
    rc = U.run_one("uncr_par_pit_fwd03", ["q_eval_cmdr.py"], "A", tries=1)  # a tag with no files: keep_attempt has nothing to move
    sd = [norm(x) for x in seen[0][seen[0].index("--scan_dirs") + 1].split(",")] if seen else []
    check("V11 (17c §4 · §5) CODE holds q_post.py and uncr_revalidate.py; isaac_slot --scan_dirs includes _eval/out_branch",
          ("q_post.py" in U.CODE, "uncr_revalidate.py" in U.CODE, norm(os.path.join(HERE, "out_branch")) in sd, rc), (True, True, True, (0, 1)))

    with open(os.path.join(V02_ROOT, "uncr_par_wave_fwd05.log"), "a", encoding="utf-8") as f:
        f.write("one more line after the revalidation\n")
    write_stamp(V02_ROOT, "uncr_par_wave_fwd05")
    U = load_v4(V02_ROOT, V02_REVAL)
    calls = stub_run_set(U)
    rc = run_main(U, ["--stages", "full", "--reval", p])
    check("V09 one diag run re-recorded after the revalidation (still valid on its own): bundle differs, full not started, exit 1", (rc, calls), (1, []))

    root, reval = case_dir("v10")
    make_diag(root, {("par", "gap", "fwd05"): {"edit": ground_nan_before_fall}})
    rep = RV.revalidate(root)
    p = RV.write_report(rep, reval)
    U = load_v4(root, reval)
    calls = stub_run_set(U)
    rc = run_main(U, ["--stages", "full", "--reval", p])
    check("V10 a revalidation of exactly these runs in which gap/fwd05 is hold: full not started, exit 1",
          (rep["cells"]["gap/fwd05"]["verdict"], rc, calls), ("hold", 1, []))

    root, reval = case_dir("v15")
    os.makedirs(root)
    U = load_v4(root, reval)
    U.freeze()
    launched = []
    U.run_one = fake_launcher(root, launched)
    U.run_set("diag", [("gap", "fwd05")])
    with open(os.path.join(root, "uncr_on_gap_fwd05", "driver_stamp.json"), encoding="utf-8") as f:
        st = json.load(f)
    rep = RV.revalidate(root)
    U.run_set("diag", [("gap", "fwd05")])
    check("V15 fresh runs (launcher stubbed): each checked, stamped as cmdr-4 with q_post.py in code_sha256, revalidated valid with q_post in "
          "the stamp; a second pass reuses all three without launching",
          (launched, [r.get("verdict") for r in U.LOG["runs"][:3]], [r.get("reused") for r in U.LOG["runs"][3:]], st["driver_version"],
           st["code_sha256"]["q_post.py"] == fsha(os.path.join(HERE, "q_post.py")), rep["cells"]["gap/fwd05"]["verdict"],
           rep["runs"]["uncr_on_gap_fwd05"]["q_post"]["in_stamp"], U.LOG["failures"]),
          (["uncr_par_gap_fwd05", "uncr_off_gap_fwd05", "uncr_on_gap_fwd05"], ["valid"] * 3, [True] * 3, "cmdr-4", True, "valid", True, []))

    root, reval = case_dir("v16")
    os.makedirs(root)
    U = load_v4(root, reval)
    U.freeze()
    launched = []
    U.run_one = fake_launcher(root, launched)
    code_moves_after(U, 1)
    U.run_set("diag", [("gap", "fwd05")])
    check("V16 (17c §5) collection code changes while a run is out: that run is not stamped, the failure is recorded, nothing more is launched",
          (launched, os.path.exists(os.path.join(root, "uncr_par_gap_fwd05", "driver_stamp.json")),
           any("changed during the run" in x["what"] for x in U.LOG["failures"])), (["uncr_par_gap_fwd05"], False, True))

    root, reval = case_dir("v16b")
    os.makedirs(root)
    U = load_v4(root, reval)
    U.freeze()
    launched = []
    U.run_one = fake_launcher(root, launched)
    code_moves_after(U, 0)
    U.run_set("diag", [("gap", "fwd05")])
    check("V16b collection code changed after the driver start, before the first launch: nothing launched, failure recorded",
          (launched, any("since the driver start" in x["what"] for x in U.LOG["failures"])), ([], True))

    # ===== the real out_uncr, read only =======================================================================================
    if not SKIP_REAL:
        snap0 = snapshot(REAL_ROOT)
        rep = RV.revalidate(REAL_ROOT)
        snap1 = snapshot(REAL_ROOT)
        check("X01 real _eval/out_uncr is only read: every file name, size and mtime unchanged", (snap1 == snap0, len(snap0) > 0), (True, True))
        print("REAL counts", json.dumps(rep["counts"]), "bundle", rep["bundle_sha256"], "frozen_ok", rep["frozen_ok"])
        for k in DIAG_KEYS + sorted(set(rep["cells"]) - set(DIAG_KEYS)):
            cc = rep["cells"].get(k)
            if not cc:
                print("REAL", k, "missing")
                continue
            print("REAL", "DIAG" if cc["in_diag"] else "full", k, cc["verdict"], cc["runs"],
                  {m: (s["surv"], s["cross"]) for m, s in cc["stats"].items() if s}, " | ".join(cc["reasons"])[:300])
        for tg, r in rep["runs"].items():
            if r.get("hold") or r.get("invalid") or (r.get("nan") or {}).get("ground_ch11_after_window"):
                print("REAL run", tg, r["verdict"], r.get("invalid"), r.get("hold"), r.get("nan"))
        check("X02 real: 21 diag runs present (7 cells x par / off / on)", sum(rep["counts"]["diag_runs"].values()), 21)
finally:
    for t in TMPS:
        shutil.rmtree(t, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
