"""v7 vs v8/v9 on a frozen bundle (lead 10/13, TASK-astra-16i; rewritten for VERIFY-astra-16k 3). Read only.
16k 3 showed that "explaining" differences by the held runs let wrong contract summaries, a whole missing row and a held
row that came back pass. So this compares EXACTLY:
  - reference = the v7 output on the same input. When the newer output holds runs, the reference must be a v7 output
    computed on that input with exactly those runs removed (third argument); without it the result is "not comparable"
    (exit 2), never a pass. Its valid-run count must be the plain v7 count minus the held runs.
  - every key except the bookkeeping ones (schema, as_of, inputs, inputs_manifest, origin_counts, held, hold_released,
    hold_candidates, legacy_tags, legacy_stamps, release_auth_fail, release_deps_sha256, hold_list) must be equal to the reference, value for value;
    driver_logs are compared without the "attempt" field the newer aggregate adds.
  - no held run may appear in the newer output's inputs_manifest; every released run must.
Exit 0 pass · 1 a difference (listed) · 2 not comparable (held runs and no filtered reference).
Usage: python compare_frozen.py <v7 cmdr_post.json> <v8/v9 cmdr_post.json> [<v7 cmdr_post.json without the held runs>]"""
import json
import sys

a = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.load(open(sys.argv[2], encoding="utf-8"))
ref = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else None
BOOK = {"schema", "as_of", "inputs", "inputs_manifest", "origin_counts", "held", "hold_released", "hold_candidates",
        "legacy_tags", "legacy_stamps", "release_auth_fail", "release_deps_sha256", "hold_list"}
held = [h["tag"] for h in b.get("held", [])]
out = {"held": held, "released": [r["tag"] for r in b.get("hold_released", [])], "differences": []}
if held and ref is None:
    out["result"] = "not comparable: the newer output holds runs; give a v7 output computed without exactly those runs"
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(2)
if held:
    if ref.get("n_valid_runs") != a.get("n_valid_runs", 0) - len(held):
        out["differences"].append(f"filtered reference counts {ref.get('n_valid_runs')} valid runs, want {a.get('n_valid_runs', 0) - len(held)}")
else:
    ref = a


def strip(dl):
    return {n: {k: v for k, v in d.items() if k != "attempt"} for n, d in (dl or {}).items()}


def diff(x, y, path, acc, limit=40):
    """every path where x and y differ (dicts walked key by key, anything else compared whole)"""
    if len(acc) >= limit:
        return
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y), key=str):
            if k not in x or k not in y:
                acc.append(f"{path}/{k}: only in {'newer' if k not in x else 'reference'}")
            else:
                diff(x[k], y[k], f"{path}/{k}", acc, limit)
    elif x != y:
        acc.append(f"{path}: {str(x)[:60]} -> {str(y)[:60]}")


for k in sorted(set(ref) | set(b)):
    if k in BOOK:
        continue
    x, y = ref.get(k, "<missing>"), b.get(k, "<missing>")
    if k == "driver_logs":
        x, y = strip(x if isinstance(x, dict) else {}), strip(y if isinstance(y, dict) else {})
    diff(x, y, k, out["differences"])
man = b.get("inputs_manifest", {})
out["differences"] += [f"held run used: {t}" for t in held if t in man]
out["differences"] += [f"released run not used: {t}" for t in out["released"] if t not in man]
out["pass"] = not out["differences"]
out["result"] = "equal to the reference on every non-bookkeeping key" if out["pass"] else f"{len(out['differences'])} difference(s)"
print(json.dumps(out, ensure_ascii=False, indent=1))
sys.exit(0 if out["pass"] else 1)
