# Compare the first bundle of the CMD-R treatment arm with the control arm (VERIFY-astra-7 section 1: "처리군 시작 전
# bundle 대조에서 의도한 off/on 외 초기 hash 가 다르면 원인 확인 전 그 군의 진행을 보류").
# v2 after VERIFY-astra-8 section 4:
#   - required difference: meta.args.cmdr is exactly "off" (left) and "on" (right); meta.args.tag differs.
#   - allowed (may or may not differ): meta.t_start. Any other JSON difference, any npz key/dtype/shape/bytes difference
#     -> DIFFERENT.
#   - both sides must meet the run contract (parent path + sha256, seed, num_envs, updates, gate False) and carry the
#     required meta/state keys; a field missing on both sides is reported, not passed.
#   - writes out/branch/cmdr_bundle_compare__<off_tag>__<on_tag>.json with the sha256 of both bundle files, and exits
#     0 = SAME, 1 = DIFFERENT, 2 = input missing.
# Usage: python cmdr_bundle_compare.py [off_dir on_dir] [--envs 8192 --updates 4000 --gate false]
import argparse
import hashlib
import json
import os
import sys

import numpy as np

B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "branch")
PARENT = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192/model_20000.pt"
PARENT_SHA = "c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8"
META_KEYS = ["args", "gate_decision", "t_start", "env_vars", "parent_sha256", "code", "clock"]
STATE_KEYS = ["where", "label_next", "common_step_counter", "iter_from_counter", "command_ranges", "env_ranges_unique",
              "remaining_stages", "zero_command_prob", "reward_weights", "terrain_level_hist", "terrain_level_per_column_ok",
              "origins_vs_terrain_origins_max_abs", "scene_env_origins_vs_terrain_max_abs", "root_xy_minus_origin_max_abs",
              "episode_length_buf", "alg_learning_rate", "optimizer", "optimizer_stu_enc", "model_sha", "rng", "sha", "obs_sha",
              "obs_cmd_vs_commands_max_abs", "synced_reward_terms", "first_commands"]
NPZ_KEYS = ["commands", "episode_length_buf", "joint_pos", "levels", "origins", "root_pose", "torch_cpu_rng", "torch_cuda_rng"]
# required sub-keys whose values must be present and non-empty on both sides (VERIFY-astra-8b 1)
SUB_KEYS = {"rng": ["torch_cpu", "torch_cuda", "numpy", "python"],
            "sha": ["levels", "origins", "root_pose", "joint_pos", "masses", "coms", "materials", "gains"],
            "obs_sha": ["policy", "critic", "single_obs"],
            "optimizer": ["lr_groups", "steps", "n", "sha"], "optimizer_stu_enc": ["lr_groups", "steps", "n", "sha"]}

ap = argparse.ArgumentParser()
ap.add_argument("dirs", nargs="*")
ap.add_argument("--envs", type=int, default=8192)
ap.add_argument("--updates", type=int, default=4000)
ap.add_argument("--gate", default="false")
ap.add_argument("--out", default="", help="report path (default out/branch/cmdr_bundle_compare__<off>__<on>.json)")
a = ap.parse_args()
off_dir = a.dirs[0] if len(a.dirs) == 2 else os.path.join(B, "cmdr_s1042_off_u4000")
on_dir = a.dirs[1] if len(a.dirs) == 2 else os.path.join(B, "cmdr_s1042_on_u4000")
for d in (off_dir, on_dir):
    for f in ("bundle.json", "bundle.npz"):
        if not os.path.exists(os.path.join(d, f)):
            print("MISSING", os.path.join(d, f))
            sys.exit(2)


def fsha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def walk(x, y, path, out):
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            walk(x.get(k, "<missing>"), y.get(k, "<missing>"), f"{path}.{k}" if path else k, out)
    elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
        for i, (p, q) in enumerate(zip(x, y)):
            walk(p, q, f"{path}[{i}]", out)
    elif x != y:
        out.append((path, x, y))


ja = json.load(open(os.path.join(off_dir, "bundle.json"), encoding="utf-8"))
jb = json.load(open(os.path.join(on_dir, "bundle.json"), encoding="utf-8"))
problems = []
# schema
for side, j in (("off", ja), ("on", jb)):
    for k in META_KEYS:
        if k not in j.get("meta", {}):
            problems.append(f"{side}: meta.{k} missing")
    for k in STATE_KEYS:
        if k not in j.get("state", {}):
            problems.append(f"{side}: state.{k} missing")
    for k, subs in SUB_KEYS.items():
        v = j.get("state", {}).get(k)
        for sk in subs:
            x = v.get(sk) if isinstance(v, dict) else None
            if x is None or x == "" or x == {} or x == []:
                problems.append(f"{side}: state.{k}.{sk} missing or empty")
# run contract, both sides
gate = a.gate.lower() == "true"
for side, j, arm in (("off", ja, "off"), ("on", jb, "on")):
    m = j.get("meta", {})
    g = m.get("args", {})
    exp = {"cmdr": arm, "parent": PARENT, "seed": 1042, "num_envs": a.envs, "updates": a.updates, "gate": gate}
    for k, v in exp.items():
        if g.get(k) != v:
            problems.append(f"{side}: args.{k} = {g.get(k)!r}, expected {v!r}")
    if m.get("parent_sha256") != PARENT_SHA:
        problems.append(f"{side}: parent_sha256 {str(m.get('parent_sha256'))[:16]} != {PARENT_SHA[:16]}")
# differences
diffs = []
walk(ja, jb, "", diffs)
REQUIRED, ALLOWED = {"meta.args.cmdr", "meta.args.tag"}, {"meta.t_start"}
paths = {p for p, _, _ in diffs}
for r in sorted(REQUIRED - paths):
    problems.append(f"required difference absent: {r}")
unexpected = [(p, str(x)[:200], str(y)[:200]) for p, x, y in diffs if p not in REQUIRED | ALLOWED]
problems += [f"unexpected difference: {p}" for p, _, _ in unexpected[:50]]
na, nb = np.load(os.path.join(off_dir, "bundle.npz")), np.load(os.path.join(on_dir, "bundle.npz"))
arrays = {}
for k in sorted(set(na.files) | set(nb.files) | set(NPZ_KEYS)):
    if k not in na.files or k not in nb.files:
        arrays[k] = "missing"
        continue
    x, y = na[k], nb[k]
    same = x.shape == y.shape and x.dtype == y.dtype and x.size > 0 and \
        hashlib.sha256(np.ascontiguousarray(x).tobytes()).digest() == hashlib.sha256(np.ascontiguousarray(y).tobytes()).digest()
    arrays[k] = "same" if same else f"DIFFERENT shape {x.shape}/{y.shape} dtype {x.dtype}/{y.dtype}"
problems += [f"npz {k}: {v}" for k, v in arrays.items() if v != "same"]
verdict = "SAME" if not problems else "DIFFERENT"
res = {"verdict": verdict, "problems": problems, "off": off_dir, "on": on_dir,
       "bundle_sha256": {"off_json": fsha(os.path.join(off_dir, "bundle.json")), "off_npz": fsha(os.path.join(off_dir, "bundle.npz")),
                         "on_json": fsha(os.path.join(on_dir, "bundle.json")), "on_npz": fsha(os.path.join(on_dir, "bundle.npz"))},
       "contract": {"envs": a.envs, "updates": a.updates, "gate": gate, "parent": PARENT, "parent_sha256": PARENT_SHA},
       "diff_paths": sorted(paths), "arrays": arrays, "tool_sha256": fsha(os.path.abspath(__file__))}
out = a.out or os.path.join(B, f"cmdr_bundle_compare__{os.path.basename(os.path.normpath(off_dir))}__{os.path.basename(os.path.normpath(on_dir))}.json")
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(verdict, "problems", len(problems), problems[:6], "->", out)
sys.exit(0 if verdict == "SAME" else 1)
