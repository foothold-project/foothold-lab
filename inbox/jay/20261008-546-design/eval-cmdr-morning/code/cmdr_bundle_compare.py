# Compare the first bundle of the CMD-R treatment arm with the control arm (VERIFY-astra-7 section 1: "처리군 시작 전
# bundle 대조에서 의도한 off/on 외 초기 hash 가 다르면 원인 확인 전 그 군의 진행을 보류").
# Allowed differences: meta.args.cmdr, meta.args.tag, meta.t_start. Everything else in bundle.json and every array in
# bundle.npz must be equal. Writes out/branch/cmdr_bundle_compare.json and prints SAME or DIFFERENT.
# Usage: python cmdr_bundle_compare.py [off_dir on_dir]
import hashlib
import json
import os
import sys

import numpy as np

B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "branch")
off_dir = sys.argv[1] if len(sys.argv) > 2 else os.path.join(B, "cmdr_s1042_off_u4000")
on_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(B, "cmdr_s1042_on_u4000")
ALLOWED = {"meta.args.cmdr", "meta.args.tag", "meta.t_start"}


def walk(a, b, path, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            walk(a.get(k, "<missing>"), b.get(k, "<missing>"), f"{path}.{k}" if path else k, out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append((path, a, b))


ja = json.load(open(os.path.join(off_dir, "bundle.json"), encoding="utf-8"))
jb = json.load(open(os.path.join(on_dir, "bundle.json"), encoding="utf-8"))
diffs = []
walk(ja, jb, "", diffs)
unexpected = [(p, str(a)[:200], str(b)[:200]) for p, a, b in diffs if p not in ALLOWED]
expected = [(p, str(a)[:200], str(b)[:200]) for p, a, b in diffs if p in ALLOWED]
na, nb = np.load(os.path.join(off_dir, "bundle.npz")), np.load(os.path.join(on_dir, "bundle.npz"))
arrays = {}
for k in sorted(set(na.files) | set(nb.files)):
    if k not in na.files or k not in nb.files:
        arrays[k] = "missing in one"
        continue
    ha = hashlib.sha256(np.ascontiguousarray(na[k]).tobytes()).hexdigest()
    hb = hashlib.sha256(np.ascontiguousarray(nb[k]).tobytes()).hexdigest()
    arrays[k] = "same" if (ha == hb and na[k].shape == nb[k].shape and na[k].dtype == nb[k].dtype) else f"DIFFERENT {ha[:12]} {hb[:12]}"
bad_arrays = {k: v for k, v in arrays.items() if v != "same"}
verdict = "SAME" if not unexpected and not bad_arrays and {p for p, _, _ in expected} == ALLOWED else "DIFFERENT"
res = {"verdict": verdict, "off": off_dir, "on": on_dir, "expected_diffs": expected, "unexpected_diffs": unexpected[:50],
       "n_unexpected": len(unexpected), "arrays": arrays}
json.dump(res, open(os.path.join(B, "cmdr_bundle_compare.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(verdict, "unexpected", len(unexpected), "arrays", bad_arrays or "all same", "expected", [p for p, _, _ in expected])
