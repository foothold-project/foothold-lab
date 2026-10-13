"""v7 vs v8 on the frozen 14:00 bundle (lead 10/13, TASK-astra-16i). Read only.
Pass when: targets, target_verdict and holm are equal; every regression row and every contract cell is equal except the
cells of the runs v8 holds; v7 counts exactly len(held) more valid runs. Prints every other difference.
Usage: python compare_frozen.py <v7 cmdr_post.json> <v8 cmdr_post.json>"""
import json
import sys

a = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.load(open(sys.argv[2], encoding="utf-8"))
held_tags = [h["tag"] for h in b.get("held", [])]


def cellkey(tag):
    _, m, rest = tag.split("_", 2)
    rest, seed = rest.rsplit("_s", 1)
    rest, noise = rest.rsplit("_", 1)
    fam, cell = rest.rsplit("_", 1)
    return f"{fam}/{cell}/{noise}", m


held_cells = {cellkey(t)[0] for t in held_tags}
out = {"held": held_tags, "checks": {}, "other_differences": []}
for k in ("targets", "target_verdict", "holm"):
    out["checks"][k] = a.get(k) == b.get(k)
ra = {k: v for k, v in a["regression_24000"].items() if k not in held_cells}
rb = {k: v for k, v in b["regression_24000"].items() if k not in held_cells}
out["checks"]["regression rows except held cells"] = ra == rb
out["regression rows (v7, v8)"] = [len(a["regression_24000"]), len(b["regression_24000"])]
out["held cell rows (v7 has, v8 has)"] = {c: [c in a["regression_24000"], c in b["regression_24000"]] for c in sorted(held_cells)}
ok_contract = True
for m in sorted(set(a.get("contract_24000", {})) | set(b.get("contract_24000", {}))):
    ca = {k: v for k, v in a["contract_24000"].get(m, {}).get("cells", {}).items() if k not in held_cells}
    cb = {k: v for k, v in b["contract_24000"].get(m, {}).get("cells", {}).items() if k not in held_cells}
    ok_contract &= ca == cb
out["checks"]["contract cells except held cells"] = ok_contract
out["checks"]["valid runs differ by the held count"] = a["n_valid_runs"] - b["n_valid_runs"] == len(held_tags)
for k in sorted(set(a) | set(b)):
    if k in ("targets", "target_verdict", "holm", "regression_24000", "contract_24000", "schema", "as_of", "inputs_manifest",
             "origin_counts", "held", "hold_released", "n_valid_runs", "legacy_tags", "legacy_stamps"):
        continue
    if a.get(k) != b.get(k):
        out["other_differences"].append(k)
out["pass"] = all(out["checks"].values())
print(json.dumps(out, ensure_ascii=False, indent=1))
sys.exit(0 if out["pass"] else 1)
