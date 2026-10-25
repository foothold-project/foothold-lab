"""16 env turn probe -> case table: mean yaw (rad/s, alive steps) / all-four-feet contact ratio. Feet = links with contact (force>1 N)."""
import sys, numpy as np
from pathlib import Path
FEET = [4, 8, 14, 18]
CASES = ["indep_left", "indep_right", "left_then_right", "right_then_left", "fwd_then_left", "fwd_then_right"]
def one(p, thr):
    z = np.load(p); a = z["alive"]; c = (z["force"][..., FEET] > thr).all(-1)
    return float(z["wz"][a].mean()), float(c[a].mean()), int(z["kept"].sum()) if "kept" in z.files else -1, int(a[:, -1].sum())
if __name__ == "__main__":
    thr = 1.0
    for d in sys.argv[1:]:
        row = []
        for k in CASES:
            p = Path(d) / f"arrays_{k}.npz"
            row.append("%+.2f / %.2f (%d)" % one(p, thr)[::1][:2] + "" if False else ("%+.2f / %.2f alive%d" % (one(p, thr)[0], one(p, thr)[1], one(p, thr)[3]) if p.exists() else "-"))
        print(Path(d).name, " | ".join(row))
