# Page table for the lead: E1 vs E2 Q pass per cell, Q main condition (noise off and on), models 19500 / 20000 /
# 20499, from out/E12-cells.csv (written by e12_md.py). A cell is marked when the two seeds differ by more than
# 10 pp or the MAE sum differs by more than 20 %. Writes out/E12-page.md and out/E12-page.csv.
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
R = list(csv.DictReader(open(os.path.join(OUT, "E12-cells.csv"), encoding="utf-8")))
GROUPS = [("능력 곡선 · noise 끔 · 19500", "19500", "끔"), ("Q 주 실행 · noise 끔 · 20000", "20000", "끔"), ("Q 주 실행 · noise 끔 · 20499", "20499", "끔"),
          ("능력 곡선 · noise 켬 · 19500", "19500", "켬"), ("Q 주 실행 · noise 켬 · 20000", "20000", "켬"), ("Q 주 실행 · noise 켬 · 20499", "20499", "켬")]
by = {(r["group"], r["unit"], r["cell"]): r for r in R}
units = []
for r in R:
    if (r["unit"], r["cell"]) not in units:
        units.append((r["unit"], r["cell"]))
rows = []
for nn in ("끔", "켬"):
    for unit, cell in units:
        rec = {"noise": nn, "terrain": unit, "cell": cell}
        for g, it, n2 in GROUPS:
            if n2 != nn:
                continue
            x = by.get((g, unit, cell))
            if x is None:
                rec[f"E1_{it}"] = rec[f"E2_{it}"] = rec[f"flag_{it}"] = ""
                continue
            e1, e2 = 100 * float(x["e1_pass"]), 100 * float(x["e2_pass"])
            fl = []
            if x["flag_pp"] == "True":
                fl.append("pp")
            if x["flag_mae"] == "True":
                # MAE sums of a few hundredths differ by > 20 % on noise alone (stand cells: 0.001 vs 0.0015)
                fl.append("MAE" if abs(float(x["e2_mae_sum"]) - float(x["e1_mae_sum"])) >= 0.02 else "(MAE)")
            rec[f"E1_{it}"], rec[f"E2_{it}"], rec[f"flag_{it}"] = round(e1), round(e2), "+".join(fl)
        rows.append(rec)
with open(os.path.join(OUT, "E12-page.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
with open(os.path.join(OUT, "E12-page.md"), "w", encoding="utf-8") as f:
    f.write("> 분류: A/정책학습 · 평가 · E1 대 E2 · 페이지용 표\n> 작성: 오흥재 (lead 세션 하위 작업 · Claude 실행) · 2026-10-12\n"
            "> 근거: `_eval/out/E12-cells.csv` (e12_md.py) · Q-E1 임시 조건 · 현행 정의 · 같은 평가 시드 · 배치 · DR · 메시 (짝 확인됨)\n"
            "> 요지: cell 마다 E1 (시드 42) 과 E2 (시드 43) 의 Q 통과 %. `pp` = 두 시드 차 > 10 pp, `MAE` = MAE 합 차 > 20 % 이고 절대 차 ≥ 0.02, `(MAE)` = 20 % 는 넘지만 절대 차 < 0.02 (ASTRA 기준 · 괄호는 잡음 수준 표시)\n"
            "> 상태: 자동 생성 (e12_page.py)\n\n")
    for nn in ("끔", "켬"):
        f.write(f"## 관측 noise {nn} · Q 통과 % (E1 / E2, 표시는 같은 체크포인트끼리)\n\n")
        f.write("| 지형 · 출발 | cell | 19500 | 20000 | 20499 |\n|---|---|---|---|---|\n")
        for r in rows:
            if r["noise"] != nn:
                continue
            cells = []
            for it in ("19500", "20000", "20499"):
                if r[f"E1_{it}"] == "":
                    cells.append("-")
                    continue
                mark = f" **{r[f'flag_{it}']}**" if r[f"flag_{it}"] else ""
                cells.append(f"{r[f'E1_{it}']} / {r[f'E2_{it}']}{mark}")
            f.write(f"| {r['terrain']} | {r['cell']} | " + " | ".join(cells) + " |\n")
        f.write("\n")
print(len(rows))
