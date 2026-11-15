# lead independent recheck of UNSEEN-cells.csv: survival and crossing from traj.npz 'term' (not episodes.csv fall_t)
import os, re, json, csv, glob
import numpy as np
OUT = r"C:/isaac/ext/go2_rl_robotlab/_eval/out"
ref = {}
for r in csv.DictReader(open(os.path.join(OUT, "UNSEEN-cells.csv"), encoding="utf-8")):
    ref[(r["run"], r["model"], r["terrain"], r["cell"])] = r
rows, bad, nrun = [], [], 0
for d in sorted(glob.glob(os.path.join(OUT, "un_e*_m*_*_fwd*"))):
    tag = os.path.basename(d)
    m = re.match(r"un_(e[12])_m(\d+)_(.+)_(fwd\d\d)$", tag)
    if not m or not os.path.isdir(d):
        continue
    run, it, fam, cell = m.group(1).upper(), m.group(2), m.group(3), m.group(4)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    z = np.load(os.path.join(d, "traj.npz"))
    org = np.load(os.path.join(d, "env_origins.npy"))
    tr, term = z["traj"], z["term"]
    T, N = term.shape
    zone = meta["obstacle_zone_m"][fam][1]
    log = open(os.path.join(OUT, tag + ".log"), encoding="utf-8", errors="replace").read()
    tb = "Traceback (most recent call last)" in log
    surv, cross = 0, 0
    for e in range(N):
        hit = np.flatnonzero(term[:, e])
        alive_to = hit[0] if hit.size else T   # rows before the first terminated row
        if not hit.size:
            surv += 1
        x = tr[:alive_to, e, 0] - org[e, 0]
        if x.size and np.nanmax(x) >= zone:
            cross += 1
    nrun += 1
    k = (run, it, fam, cell)
    r = ref.get(k)
    rs, rc = (float(r["survival"]) * 100, float(r["crossed"]) * 100) if r else (None, None)
    rows.append((tag, N, surv, cross, rs, rc, tb))
    if r is None or abs(rs - surv) > 0.5 or abs(rc - cross) > 0.5 or tb or N != 100:
        bad.append((tag, N, surv, cross, rs, rc, tb))
print("runs", nrun, "ref rows", len(ref))
print("mismatch or traceback or N!=100:", len(bad))
for b in bad[:40]:
    print(" ", b)
# 2) do the survival gaps equal the falls that the env does not terminate on (tilt60 / below support)?
print("--- falls by reason vs env term")
ok = 0
for tag, N, surv, cross, rs, rc, tb in rows:
    d = os.path.join(OUT, tag)
    eps = list(csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")))
    term = np.load(os.path.join(d, "traj.npz"))["term"]
    nonterm = sum(1 for r in eps if r["survived"] == "False" and r["fall_reason"] != "base_contact")
    bc = [r for r in eps if r["survived"] == "False" and r["fall_reason"] == "base_contact"]
    # base_contact episodes: fall_t should sit at the env's first terminated row (dt 0.02)
    dt_err = []
    for r in bc:
        hit = np.flatnonzero(term[:, int(r["env"])])
        dt_err.append(abs(hit[0] * 0.02 - float(r["fall_t"])) if hit.size else 99)
    # env-terminated episodes that q_post calls survived (should be 0)
    surv_but_term = sum(1 for r in eps if r["survived"] == "True" and term[:, int(r["env"])].any())
    good = (N - surv) == len(bc) or (N - surv) <= len(bc)
    match = (surv - (100 - len(bc))) == 0 and (rs is None or abs((surv - nonterm) - rs) < 0.5) and surv_but_term == 0
    ok += match
    if not match or (dt_err and max(dt_err) > 0.021):
        print(" ", tag, "termsurv", surv, "ref", rs, "nonterm falls", nonterm, "bc", len(bc), "surv_but_term", surv_but_term, "max|dt|", max(dt_err) if dt_err else None)
print("runs where termsurv - nonterm == ref survival and term falls == base_contact:", ok, "/", len(rows))
# 3) correct accounting: ref survival = env-survived minus q_post falls the env never terminated (tilt60 / below support)
print("--- 3")
ok3, tot_nt = 0, 0
for tag, N, surv, cross, rs, rc, tb in rows:
    d = os.path.join(OUT, tag)
    eps = list(csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")))
    term = np.load(os.path.join(d, "traj.npz"))["term"]
    nt = sum(1 for r in eps if r["survived"] == "False" and not term[:, int(r["env"])].any())
    sbt = sum(1 for r in eps if r["survived"] == "True" and term[:, int(r["env"])].any())
    tot_nt += nt
    if surv - nt == round(rs) and sbt == 0:
        ok3 += 1
    else:
        print("  X", tag, surv, nt, rs, sbt)
print("ok", ok3, "/", len(rows), "· q_post falls the env did not terminate, all runs:", tot_nt)
