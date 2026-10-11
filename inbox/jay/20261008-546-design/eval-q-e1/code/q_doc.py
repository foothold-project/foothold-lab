# Assemble Q-E1.md from Q-E1.src.md + out/Q-E1-tables.md.
# Tokens {{T1}} .. {{T9}} in the source are replaced by the generated "### 표 N" sections,
# so no table number is copied by hand. Also checks for em dash / en dash characters.

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "Q-E1.src.md"), encoding="utf-8").read()
tab = open(os.path.join(HERE, "out", "Q-E1-tables.md"), encoding="utf-8").read()
parts = re.split(r"(?m)^(?=### 표 \d+ )", tab)
sec = {}
for p in parts:
    m = re.match(r"### 표 (\d+) ", p)
    if m:
        sec[m.group(1)] = p.rstrip() + "\n"
missing = []


def sub(m):
    k = m.group(1)
    if k not in sec:
        missing.append(k)
        return f"(표 {k} 미생성)"
    return sec[k]


doc = re.sub(r"\{\{T(\d+)\}\}", sub, src)

# computed tokens from raw files
import glob  # noqa: E402
import json  # noqa: E402

pol, sgl, add, free, nlog = [], [], [], [], 0
for m in sorted(glob.glob(os.path.join(HERE, "out", "*", "meta.json"))):
    tag = os.path.basename(os.path.dirname(m))
    if tag.startswith("_pre") or tag == "smoke_zero":
        continue
    d = json.load(open(m, encoding="utf-8"))
    nlog += 1
    pol.append(d["checks_pre"]["policy_history_perturbed_max_abs_action_change"])
    sgl.append(d["checks_pre"]["single_obs_perturbed_max_abs_action_change"])

    def g(lst, i):
        return int(lst[i].split(",")[2].strip().split()[0])
    s0 = g(d["smi_start"], 1)
    peak = max(g(d[k], 1) for k in ("smi_after_env", "smi_mid", "smi_end") if d.get(k))
    add.append((d["N"], peak - s0))
    free.append(16303 - peak)
by_n = {}
for n, a in add:
    by_n.setdefault(n, []).append(a)
allv = [a for _, a in add]
mem_add = (f"실행별 {min(allv) / 1024:.1f}~{max(allv) / 1024:.1f} GB (env {min(by_n):,}~{max(by_n):,} 개. "
           f"env {min(by_n):,} 개에서 {max(by_n[min(by_n)]) / 1024:.1f} GB, {max(by_n):,} 개에서 {max(by_n[max(by_n)]) / 1024:.1f} GB 라 "
           f"고정 부담이 대부분)")
t3 = sec.get("3", "")
n_worse = sum(1 for line in t3.splitlines() if line.startswith("| ") and not line.startswith("| 지형") and "---" not in line)
fill = {"PERT_POL": f"{min(pol):.2f}~{max(pol):.2f}", "PERT_SGL": f"{min(sgl):.2f}~{max(sgl):.2f}",
        "N_LOGS": str(nlog), "MEM_ADD": mem_add, "MEM_FREE": f"{min(free) / 1024:.1f} GB", "N_WORSE": str(n_worse)}
fp = os.path.join(HERE, "Q-E1.fill.json")
if os.path.exists(fp):
    fill.update(json.load(open(fp, encoding="utf-8")))
left = []


def sub2(m):
    k = m.group(1)
    if k in fill:
        return fill[k]
    left.append(k)
    return m.group(0)


doc = re.sub(r"\{\{([A-Z_0-9]+)\}\}", sub2, doc)
print("unfilled tokens:", left)
bad = [c for c in (chr(0x2014), chr(0x2013)) if c in doc]  # em dash, en dash
open(os.path.join(HERE, "Q-E1.md"), "w", encoding="utf-8", newline="\n").write(doc)
print("missing tables:", missing, "| dash chars found:", bad)
sys.exit(1 if bad else 0)
