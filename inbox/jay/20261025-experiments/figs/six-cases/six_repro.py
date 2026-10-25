import sys; sys.path.insert(0, r"C:/Users/AI-WS01/AppData/Local/Temp/claude/C--Users-AI-WS01-Desktop-jay----------foothold-lab/09bbf294-fda0-4c7b-81c5-e23f793f2be2/figs/six-cases")
from six_table import one, CASES
from pathlib import Path
NEW = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/six_cases")
OLD = {"b1500": "C:/mai/wt/foothold-lab/impl-t5/logs/w3p1_b1500_20261025_063715", "b50_m1510": "C:/mai/wt/foothold-lab/impl-t5/logs/onset_sweep/probe_b50_m1510", "b50_m1550": "C:/mai/wt/foothold-lab/impl-t5/logs/onset_sweep/probe_b50_m1550",
       "a50_m1550": "C:/mai/wt/foothold-lab/impl-t5/logs/onset_sweep/probe_a50_m1550"}
SOLO = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/fwd_then_left")
dy, dc = [], []
for t in ["b1500", "b50_m1510", "b50_m1550", "a50_m1550"]:
    pairs = [(Path(OLD[t]) / f"arrays_{k}.npz", NEW / t / f"arrays_{k}.npz", k) for k in CASES if t in OLD and (Path(OLD[t]) / f"arrays_{k}.npz").exists()]
    pairs.append((SOLO / t / "arrays_fwd_then_left.npz", NEW / t / "arrays_fwd_then_left.npz", "fwd_then_left(solo)"))
    for a, b, k in pairs:
        ya, ca, *_ = one(a, 1.0); yb, cb, *_ = one(b, 1.0)
        dy.append(abs(ya - yb)); dc.append(abs(ca - cb))
        print(f"{t:10s} {k:22s} yaw {ya:+.2f} -> {yb:+.2f} (d {yb-ya:+.2f})  four {ca:.2f} -> {cb:.2f} (d {cb-ca:+.2f})")
print(f"n={len(dy)} |d yaw| min {min(dy):.3f} max {max(dy):.3f} mean {sum(dy)/len(dy):.3f} ; |d four| min {min(dc):.3f} max {max(dc):.3f} mean {sum(dc)/len(dc):.3f}")
