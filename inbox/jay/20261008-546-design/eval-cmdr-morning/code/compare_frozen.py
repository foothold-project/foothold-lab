"""v7 vs v8 on a frozen bundle (lead 10/13, TASK-astra-16i, fixed for VERIFY-astra-16j 6). Read only.
Pass only when every difference between the two outputs is explained by the runs v8 holds:
  - targets, target_verdict, holm: equal
  - regression rows: equal except the rows of held (family/cell/noise) cells, which v8 may lack
  - basic contract: equal for every arm; only the held model's held cells may be missing in v8 (the other arm's same cell
    is compared as usual)
  - cells: per family/cell/noise entry equal; in a held cell only the held model's sub-entry may differ / be missing
  - completion: equal except completion[held model][family], which v8 may count lower by exactly the held runs there
  - regression_coverage: measured and done lower by exactly the held rows, unmeasured gains exactly them, rest equal
  - driver_logs: equal except the "attempt" field v8 adds
  - every other key not in the bookkeeping list (schema, times, manifests, origin and hold lists, valid-run count) equal
  - valid runs: v7 counts exactly len(held) more
Usage: python compare_frozen.py <v7 cmdr_post.json> <v8 cmdr_post.json>"""
import json
import sys

a = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.load(open(sys.argv[2], encoding="utf-8"))


def split(tag):
    _, m, rest = tag.split("_", 2)
    rest, seed = rest.rsplit("_s", 1)
    rest, noise = rest.rsplit("_", 1)
    fam, cell = rest.rsplit("_", 1)
    return m, fam, cell, noise


held = [split(h["tag"]) for h in b.get("held", [])]
held_keys = {f"{f}/{c}/{n}" for _, f, c, n in held}
held_mk = {(m, f"{f}/{c}/{n}") for m, f, c, n in held}
out = {"held": [h["tag"] for h in b.get("held", [])], "checks": {}, "unexplained": []}
for k in ("targets", "target_verdict", "holm"):
    out["checks"][k] = a.get(k) == b.get(k)
ra = {k: v for k, v in a["regression_24000"].items() if k not in held_keys}
rb = {k: v for k, v in b["regression_24000"].items() if k not in held_keys}
out["checks"]["regression rows except held cells"] = ra == rb
ok = True
for m in sorted(set(a.get("contract_24000", {})) | set(b.get("contract_24000", {}))):
    ca, cb = a["contract_24000"].get(m, {}), b["contract_24000"].get(m, {})
    cells_a = {k: v for k, v in ca.get("cells", {}).items() if (m, k) not in held_mk}
    cells_b = {k: v for k, v in cb.get("cells", {}).items() if (m, k) not in held_mk}
    ok &= cells_a == cells_b
    extra_b = [k for k in cb.get("cells", {}) if (m, k) in held_mk]
    ok &= not extra_b  # a held run must not appear in v8's contract
out["checks"]["contract: every arm equal, only the held model's held cells missing"] = ok


def cells_map(x):
    return {f"{e['family']}/{e['cell']}/{e['noise']}": e for e in x.get("cells", [])}
ok = True
ma, mb = cells_map(a), cells_map(b)
for k in sorted(set(ma) | set(mb)):
    if k not in held_keys:
        if ma.get(k) != mb.get(k):
            ok = False
            out["unexplained"].append(f"cells/{k}")
        continue
    ea, eb = dict(ma.get(k, {})), dict(mb.get(k, {}))
    for m, kk in held_mk:
        if kk == k:
            for key in (m, f"on_minus_off_{m[-5:]}" if m[:2] in ("on", "of") else None):  # the held arm and its derived on - off
                ea.pop(key, None)
                eb.pop(key, None)
    if eb and ea != eb:
        ok = False
        out["unexplained"].append(f"cells/{k} (other models)")
out["checks"]["cells: only the held model in held cells differs"] = ok
ok = True
want_drop = {}
for m, f, c, n in held:
    want_drop[(m, f)] = want_drop.get((m, f), 0) + 1
for key in sorted(set(a.get("completion", {})) | set(b.get("completion", {}))):  # "model/family": count
    m, f = key.split("/", 1)
    va, vb = a["completion"].get(key), b["completion"].get(key)
    if va != vb and not (isinstance(va, int) and isinstance(vb, int) and va - vb == want_drop.get((m, f), 0)):
        ok = False
        out["unexplained"].append(f"completion/{key}: {va} -> {vb}")
out["checks"]["completion: lower only by the held runs"] = ok
ca, cb = a.get("regression_coverage", {}), b.get("regression_coverage", {})
nh = len({k for k in held_keys if k in a["regression_24000"]})
ok = (ca.get("measured", 0) - cb.get("measured", 0) == nh and ca.get("done", 0) - cb.get("done", 0) == nh
      and sorted(set(cb.get("unmeasured", [])) - set(ca.get("unmeasured", []))) == sorted(k for k in held_keys if k in a["regression_24000"])
      and {k: v for k, v in ca.items() if k not in ("measured", "done", "unmeasured")} == {k: v for k, v in cb.items() if k not in ("measured", "done", "unmeasured")})
out["checks"]["regression_coverage: lower only by the held rows"] = ok
dla = {n: {k: v for k, v in d.items() if k != "attempt"} for n, d in a.get("driver_logs", {}).items()}
dlb = {n: {k: v for k, v in d.items() if k != "attempt"} for n, d in b.get("driver_logs", {}).items()}
out["checks"]["driver_logs: equal but v8's attempt field"] = dla == dlb
BOOK = {"schema", "as_of", "inputs", "inputs_manifest", "origin_counts", "held", "hold_released", "hold_candidates", "legacy_tags",
        "legacy_stamps", "n_valid_runs", "targets", "target_verdict", "holm", "regression_24000", "contract_24000", "cells",
        "completion", "regression_coverage", "driver_logs"}
for k in sorted(set(a) | set(b)):
    if k not in BOOK and a.get(k) != b.get(k):
        out["unexplained"].append(k)
out["checks"]["no other key differs"] = not [u for u in out["unexplained"] if "/" not in u]
out["checks"]["valid runs differ by the held count"] = a["n_valid_runs"] - b["n_valid_runs"] == len(held)
out["pass"] = all(out["checks"].values())
print(json.dumps(out, ensure_ascii=False, indent=1))
sys.exit(0 if out["pass"] else 1)
