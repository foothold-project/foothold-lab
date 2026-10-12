# Pairing check across the condition processes of one D1-B main run (CPU only).
# Every condition must start from the same settled state, the same restored PhysX state and the same
# first observation outside the critic height block. Exit 1 if any of these differ.
# Usage: python d1b_pair_check.py out/<tag>
import glob
import json
import os
import sys

d = sys.argv[1]
fs = sorted(f for f in glob.glob(os.path.join(d, "main_*.json")) if not os.path.basename(f).startswith("main_rows_"))
M = {os.path.basename(f)[5:-5]: json.load(open(f)) for f in fs}
if len(M) < 2:
    print("need at least two condition files", list(M))
    sys.exit(2)
ref_name = sorted(M)[0]
ref = M[ref_name]
bad = []
for c, m in M.items():
    for k in ("settled_sha256", "restore1_sha256", "restore1_first_critic_without_height_sha256"):
        if m.get(k) != ref.get(k):
            bad.append((c, k))
    for g in ("policy", "single_obs"):
        if m["restore1_first_obs_sha256"][g] != ref["restore1_first_obs_sha256"][g]:
            bad.append((c, "first_obs_" + g))
    if m.get("halted"):
        bad.append((c, "halted"))
out = {"dir": d, "conditions": sorted(M), "reference": ref_name, "mismatches": bad, "paired": not bad}
json.dump(out, open(os.path.join(d, "pair_check.json"), "w"), indent=1)
print(json.dumps(out))
sys.exit(1 if bad else 0)
