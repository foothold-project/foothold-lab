"""Compare registered 1043 CMD-R bundles without writing outside codexE."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

from s1043_manifest import ROOT, assert_isolated, inside, load, sha256

META_KEYS = ["args", "gate_decision", "t_start", "env_vars", "parent_sha256", "code", "clock"]
STATE_KEYS = ["where", "label_next", "common_step_counter", "iter_from_counter", "command_ranges",
              "env_ranges_unique", "remaining_stages", "zero_command_prob", "reward_weights", "terrain_level_hist",
              "terrain_level_per_column_ok", "origins_vs_terrain_origins_max_abs", "scene_env_origins_vs_terrain_max_abs",
              "root_xy_minus_origin_max_abs", "episode_length_buf", "alg_learning_rate", "optimizer",
              "optimizer_stu_enc", "model_sha", "rng", "sha", "obs_sha", "obs_cmd_vs_commands_max_abs",
              "synced_reward_terms", "first_commands"]
NPZ_KEYS = ["commands", "episode_length_buf", "joint_pos", "levels", "origins", "root_pose", "torch_cpu_rng", "torch_cuda_rng"]
SUB_KEYS = {"rng": ["torch_cpu", "torch_cuda", "numpy", "python"],
            "sha": ["levels", "origins", "root_pose", "joint_pos", "masses", "coms", "materials", "gains"],
            "obs_sha": ["policy", "critic", "single_obs"],
            "optimizer": ["lr_groups", "steps", "n", "sha"],
            "optimizer_stu_enc": ["lr_groups", "steps", "n", "sha"]}


def walk(x, y, path, out):
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            walk(x.get(k, "<missing>"), y.get(k, "<missing>"), f"{path}.{k}" if path else k, out)
    elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
        for i, (p, q) in enumerate(zip(x, y)):
            walk(p, q, f"{path}[{i}]", out)
    elif x != y:
        out.append((path, x, y))


def compare(manifest, off_dir, on_dir):
    c = manifest["contract"]
    problems = []
    data = []
    for arm, directory in (("off", off_dir), ("on", on_dir)):
        if not inside(directory):
            raise ValueError(f"comparison input must be copied under codexE: {directory}")
        try:
            bj = directory / "bundle.json"
            bn = directory / "bundle.npz"
            j = json.loads(bj.read_text(encoding="utf-8"))
            npz = np.load(bn, allow_pickle=False)
            data.append((j, npz))
            if sha256(bj) != c["inputs"][c["branches"][arm]["bundle_json"]]["sha256"]:
                problems.append(f"{arm}: bundle.json differs from registered bytes")
            if sha256(bn) != c["inputs"][c["branches"][arm]["bundle_npz"]]["sha256"]:
                problems.append(f"{arm}: bundle.npz differs from registered bytes")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            problems.append(f"{arm}: input unreadable: {type(exc).__name__}")
            data.append(({}, None))
    for arm, (j, _) in zip(("off", "on"), data):
        meta, state = j.get("meta", {}), j.get("state", {})
        for k in META_KEYS:
            if k not in meta:
                problems.append(f"{arm}: meta.{k} missing")
        for k in STATE_KEYS:
            if k not in state:
                problems.append(f"{arm}: state.{k} missing")
        for k, subs in SUB_KEYS.items():
            v = state.get(k)
            for sub in subs:
                x = v.get(sub) if isinstance(v, dict) else None
                if x is None or x == "" or x == {} or x == []:
                    problems.append(f"{arm}: state.{k}.{sub} missing or empty")
        args = meta.get("args") or {}
        expected = {"cmdr": arm, "parent": c["parent"]["path"], "seed": c["train_seed"],
                    "num_envs": 8192, "updates": 4000, "gate": False}
        for k, value in expected.items():
            if args.get(k) != value:
                problems.append(f"{arm}: args.{k} = {args.get(k)!r}, expected {value!r}")
        if meta.get("parent_sha256") != c["parent"]["sha256"]:
            problems.append(f"{arm}: parent hash mismatch")
    diffs = []
    walk(data[0][0], data[1][0], "", diffs)
    required = {"meta.args.cmdr", "meta.args.tag"}
    allowed = {"meta.t_start"}
    paths = {p for p, _, _ in diffs}
    for p in sorted(required - paths):
        problems.append(f"required difference absent: {p}")
    for p, _, _ in diffs:
        if p not in required | allowed:
            problems.append(f"unexpected difference: {p}")
    arrays = {}
    left, right = data[0][1], data[1][1]
    if left is not None and right is not None:
        import hashlib
        for key in sorted(set(left.files) | set(right.files) | set(NPZ_KEYS)):
            if key not in left.files or key not in right.files:
                arrays[key] = "missing"
            else:
                x, y = left[key], right[key]
                same = (x.shape == y.shape and x.dtype == y.dtype and x.size > 0 and
                        hashlib.sha256(np.ascontiguousarray(x).tobytes()).digest() ==
                        hashlib.sha256(np.ascontiguousarray(y).tobytes()).digest())
                arrays[key] = "same" if same else "DIFFERENT"
            if arrays[key] != "same":
                problems.append(f"npz {key}: {arrays[key]}")
    else:
        problems.append("npz unavailable")
    for _, npz in data:
        if npz is not None:
            npz.close()
    return {"verdict": "SAME" if not problems else "DIFFERENT", "problems": problems,
            "contract_sha256": manifest["contract_sha256"], "diff_paths": sorted(paths), "arrays": arrays,
            "bundle_sha256": {arm + "_" + f: sha256(directory / f) if (directory / f).is_file() else None
                              for arm, directory in (("off", off_dir), ("on", on_dir))
                              for f in ("bundle.json", "bundle.npz")}}


def main(argv=None):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--off", required=True)
    parser.add_argument("--on", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--expect_self_sha", required=True)
    args = parser.parse_args(argv)
    print("sys.executable", sys.executable)
    print("candidate.__file__", __file__)
    actual_sha = sha256(__file__)
    print("candidate.sha256", actual_sha)
    m = load(args.manifest)
    if (actual_sha != args.expect_self_sha or
            Path(__file__).resolve() != (Path(m["contract"]["deployment"]["candidate_dir"]) / "cmdr_bundle_compare_s1043.py").resolve()):
        print("환경 불일치", file=sys.stderr)
        return 3
    print("ISOLATION", assert_isolated(m))
    if Path(sys.executable).resolve() != Path(m["contract"]["runtime"]["python"]).resolve() or np.__version__ != m["contract"]["runtime"]["numpy"]:
        print("환경 불일치", file=sys.stderr)
        return 3
    out = Path(args.out).resolve(strict=False)
    if not inside(out) or out != Path(m["contract"]["paths"]["compare_report"]).resolve(strict=False):
        print("output outside registered codexE report", file=sys.stderr)
        return 3
    result = compare(m, Path(args.off), Path(args.on))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    print(result["verdict"], "problems", len(result["problems"]), result["problems"][:6], "->", out)
    return 0 if result["verdict"] == "SAME" else 1


if __name__ == "__main__":
    raise SystemExit(main())
