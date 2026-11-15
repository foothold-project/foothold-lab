# Run after the video chains: rename the world base height column base_z_m -> base_z_w_m in every written
# full-record CSV (header only, values unchanged) and in SCHEMA.md. Atomic replace with retry.
import glob, json, os, time
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(H, "out", "full")
old_s = "- base: `base_{x,y,z}_m` world position of the base link;"
new_s = ("- base: `base_x_m`, `base_y_m`, `base_z_w_m` world position of the base link (lab names; `base_z_m` in the lab\n"
         "  timeseries means height above the floor, so the world height is `base_z_w_m`; files written before 2026-10-12 17:00\n"
         "  named it `base_z_m`, the header was renamed, values unchanged);")
n = 0; fails = []; ns = 0
for d in sorted(glob.glob(os.path.join(FD, "*"))):
    for fn in glob.glob(os.path.join(d, "*.csv")):
        if fn.endswith("episodes_summary.csv"):
            continue
        with open(fn, encoding="utf-8") as f:
            head = f.readline()
            cols = head.rstrip("\n").split(",")
            if "base_z_m" not in cols:
                continue
            rest = f.read()
        cols[cols.index("base_z_m")] = "base_z_w_m"
        tmp = fn + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as g:
            g.write(",".join(cols) + "\n")
            g.write(rest)
        for k in range(20):
            try:
                os.replace(tmp, fn); n += 1; break
            except PermissionError:
                time.sleep(0.5)
        else:
            fails.append(fn)
    sp = os.path.join(d, "SCHEMA.md")
    if os.path.exists(sp):
        s = open(sp, encoding="utf-8").read()
        if old_s in s:
            open(sp, "w", encoding="utf-8").write(s.replace(old_s, new_s)); ns += 1
print(json.dumps({"csv_renamed": n, "schema_rewritten": ns, "fails": fails}))
