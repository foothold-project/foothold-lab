# Lists the web copies (out/web/...) with their size, the HUD source, and the Q verdict line of the episode.
# Usage: python web_list.py [--batch1]  -> out/web_list[_batch1].csv and .md (sizes in MB = 10^6 bytes)
import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import label_runner  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--batch1", action="store_true")
a = ap.parse_args()
items = json.load(open(os.path.join(HERE, "out", "hud_sel.json"), encoding="utf-8"))
if a.batch1:
    items = [x for x in items if label_runner.batch1(x)]
rep = {}
p = os.path.join(HERE, "out", "hud_report.json")
if os.path.exists(p):
    rep = {r["key"]: r for r in json.load(open(p, encoding="utf-8"))}
rows = []
for x in items:
    have = os.path.exists(x["web"])
    vj = x["video"][:-4] + ".json"
    q = json.load(open(vj, encoding="utf-8")).get("q_line", "") if os.path.exists(vj) else ""
    r = rep.get(x["key"], {})
    rows.append({"run": x["title"].split()[0], "model": x["title"].split()[1], "tag": x["tag"], "file": x["file"], "pick": x["pick"],
                 "title": x["title"], "web": os.path.relpath(x["web"], HERE).replace("\\", "/") if have else "",
                 "web_bytes": os.path.getsize(x["web"]) if have else "", "web_crf": r.get("web_crf", ""), "web_height": r.get("web_height", ""),
                 "hud": os.path.relpath(x["hud"], HERE).replace("\\", "/") if os.path.exists(x["hud"]) else "",
                 "hud_bytes": os.path.getsize(x["hud"]) if os.path.exists(x["hud"]) else "", "q_line": q})
suf = "_batch1" if a.batch1 else ""
with open(os.path.join(HERE, "out", f"web_list{suf}.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
made = [r for r in rows if r["web"]]
tot = sum(r["web_bytes"] for r in made)
over = [r for r in made if r["web_bytes"] >= 2_000_000]
with open(os.path.join(HERE, "out", f"web_list{suf}.md"), "w", encoding="utf-8") as f:
    f.write(f"웹 사본 {len(made)} / {len(rows)} 편 · 합계 {tot / 1e6:.1f} MB · 2 MB 넘는 것 {len(over)} 편 · 최대 {max([r['web_bytes'] for r in made] or [0]):,} B\n\n")
    f.write("| 실행 | model | 장면 · cell · episode (HUD 제목) | 고른 이유 | Q 판정 (episodes.csv) | 웹 사본 | MB |\n|---|---|---|---|---|---|---|\n")
    for r in rows:
        pick = {"first_success": "첫 성공", "first_failure": "첫 실패"}[r["pick"]]
        size = f"{r['web_bytes'] / 1e6:.2f}" if r["web"] else "-"
        f.write(f"| {r['run']} | {r['model']} | {r['title']} | {pick} | {r['q_line'].replace('Q 판정: ', '').replace(' (Q-E1 임시 조건 · 현행 정의)', '')} | `{r['web'] or '아직 없음'}` | {size} |\n")
print(json.dumps({"rows": len(rows), "made": len(made), "MB": round(tot / 1e6, 1), "over_2MB": len(over)}))
