"""5판 미경험 지형 절의 %%토큰%% 을 원자료에서 만든다 (lead · 10/13 아침).
원자료: _eval/out/un_<e1|e2>_m<20000|20499>_<지형>_<fwd03|fwd05|fwd10>/ (episodes.csv · traj.npz · env_origins.npy · meta.json)
        _eval/out/UNSEEN-cells.csv (하위 작업 unseen_post.py 집계 · 생존 · 건넘 대조용).
건넘 = 넘어지기 전 (q_post fall_t 로 자름) 몸통이 장애물 구간 끝을 넘음 (unseen_post 와 같은 정의).
살아서 건넘 = 건넘 이면서 20 s 끝까지 살아 있음 (lead 추가 · ASTRA 14 검증 대상)."""
import csv
import json
import os

import numpy as np

OUT = "C:/isaac/ext/go2_rl_robotlab/_eval/out"
TERR = ["discrete_obstacles", "wave", "pit", "rails", "star", "repeated_boxes", "repeated_cylinders", "floating_ring", "gap", "stepping_stones"]
KO = {"discrete_obstacles": "흩어진 장애물", "wave": "물결", "pit": "구덩이", "rails": "레일", "star": "별 모양 다리",
      "repeated_boxes": "상자 반복", "repeated_cylinders": "기둥 반복", "floating_ring": "떠 있는 고리", "gap": "틈 (gap)",
      "stepping_stones": "징검다리"}
TRAINED = {"discrete_obstacles": "같은 종류 학습", "wave": "같은 종류 학습", "gap": "정의만 (비율 0)", "stepping_stones": "정의만 (비율 0)"}
COLS = [("e1_m20000", "fwd05"), ("e2_m20000", "fwd05"), ("e1_m20499", "fwd05"), ("e2_m20499", "fwd05"),
        ("e1_m20499", "fwd10"), ("e2_m20499", "fwd10")]


def cell(tag):
    d = os.path.join(OUT, tag)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    fam = meta["args"]["families"]
    ze = meta["obstacle_zone_m"][fam][1]
    tr = np.load(os.path.join(d, "traj.npz"))["traj"]
    org = np.load(os.path.join(d, "env_origins.npy"))
    n = surv = cross = alive_cross = 0
    for r in csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")):
        e = int(r["env"])
        s = r["survived"] == "True"
        j = tr.shape[0] - 1 if s else max(0, int(round(float(r["fall_t"]) / 0.02)) - 1)
        c = bool(np.nanmax(tr[: j + 1, e, 0] - org[e, 0]) >= ze)
        n += 1
        surv += s
        cross += c
        alive_cross += c and s
    return {"n": n, "surv": surv, "cross": cross, "alive_cross": alive_cross, "zone_end": ze}


def _gallery_link():
    """144 편 영상 페이지 주소 (게시 뒤 gallery_url.txt 에 적는다). 없으면 문장을 넣지 않는다."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gallery_url.txt")
    if not os.path.exists(p):
        return ""
    u = open(p, encoding="utf-8").read().strip()
    return f'144 편 전부는 <a href="{u}" target="_blank" rel="noopener">미경험 지형 영상</a> 페이지에 있습니다.'


def build():
    ref = {(r["tag"]): r for r in csv.DictReader(open(os.path.join(OUT, "UNSEEN-cells.csv"), encoding="utf-8"))}
    data, rows, mism = {}, [], []
    for t in TERR:
        tds = []
        for m, c in COLS:
            tag = f"un_{m}_{t}_{c}"
            x = cell(tag)
            data[tag] = x
            r = ref[tag]
            # 하위 작업 집계와 같은 정의로 다시 셌으니 생존 · 건넘이 같아야 한다
            if round(100 * float(r["survival"])) != x["surv"] or round(100 * float(r["crossed"])) != x["cross"]:
                mism.append(tag)
            lost = x["cross"] - x["alive_cross"]
            tip = f"기준선 도달 {x['cross']} · 그중 20 초 끝까지 생존 {x['alive_cross']} · 도달 뒤 넘어짐 {lost} · 20 초 생존 {x['surv']} (100 판)"
            tds.append(f'<td title="{tip}"><b>{x["cross"]}</b><span class="sub2"> ({x["alive_cross"]})</span> · <span class="sub2">{x["surv"]}</span></td>')
        rows.append(f'<tr><th scope="row">{KO[t]}<span class="sub2"> {TRAINED.get(t, "처음 봄")}</span></th>' + "".join(tds) + "</tr>")
    assert not mism, ("하위 작업 집계와 다름", mism)
    g = {k: data[f"un_{k}_gap_fwd10"] for k in ("e1_m20499", "e2_m20499")}
    t = {"un_rows": "\n".join(rows),
         "un_gap10_cross": f"E1 {g['e1_m20499']['cross']} % · E2 {g['e2_m20499']['cross']} %",
         "un_gap10_alive": f"E1 {g['e1_m20499']['alive_cross']} % · E2 {g['e2_m20499']['alive_cross']} %",
         "un_runs": str(len(data)),
         "un_gallery_link": _gallery_link()}
    return t, data


if __name__ == "__main__":
    t, data = build()
    print(json.dumps({k: v for k, v in t.items() if k != "un_rows"}, ensure_ascii=False))
    print(t["un_rows"][:600])
