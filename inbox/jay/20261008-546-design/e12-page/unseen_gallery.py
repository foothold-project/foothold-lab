# -*- coding: utf-8 -*-
"""처음 보는 지형 영상 144 편 페이지 (lead · 10/13 아침).
원자료: _eval/out/unseen_web_list.csv (하위 작업이 고른 영상 · 칸마다 첫 Q 통과 · 첫 Q 미달) · 실행마다 episodes.csv · traj.npz ·
env_origins.npy · meta.json. 숫자는 손으로 쓰지 않는다. 영상은 web 사본을 그대로 복사하고 sha256 으로 대조한다.
출력: <site>/index.html · v/<tag>/<file>.mp4 · p/<tag>/<file>.jpg
사용: python unseen_gallery.py site=<폴더>"""
import csv
import hashlib
import html
import io
import json
import os
import shutil
import subprocess
import sys

import numpy as np

OUT = "C:/isaac/ext/go2_rl_robotlab/_eval/out"
HERE = os.path.dirname(os.path.abspath(__file__))
OPT = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
SITE = OPT["site"]
MAIN = OPT.get("main", "https://claude.ai/artifact/BYuAVDuVJuRWVkAs5mGJSN")
import facts5_unseen as F

TERR = F.TERR
KO = F.KO
TRAINED = F.TRAINED
SPEED = {"fwd03": "0.3 m/s", "fwd05": "0.5 m/s", "fwd10": "1.0 m/s"}
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()

rows = list(csv.DictReader(open(os.path.join(OUT, "unseen_web_list.csv"), encoding="utf-8")))
cache = {}


def ep_facts(tag, ep):
    if tag not in cache:
        d = os.path.join(OUT, tag)
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        fam = meta["args"]["families"]
        cache[tag] = (meta["obstacle_zone_m"][fam][1], np.load(os.path.join(d, "traj.npz"))["traj"],
                      np.load(os.path.join(d, "env_origins.npy")),
                      {int(r["episode"]): r for r in csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8"))})
    ze, tr, org, eps = cache[tag]
    r = eps[ep]
    e = int(r["env"])
    s = r["survived"] == "True"
    j = tr.shape[0] - 1 if s else max(0, int(round(float(r["fall_t"]) / 0.02)) - 1)
    x = tr[: j + 1, e, 0] - org[e, 0]
    return {"surv": s, "fall_t": None if s else float(r["fall_t"]), "fall_reason": r["fall_reason"],
            "cross": bool(np.nanmax(x) >= ze), "x_end": float(x[-1]), "x_max": float(np.nanmax(x)), "zone": ze}


cards = {t: [] for t in TERR}
copied = 0
for r in rows:
    src = os.path.join(OUT, r["web"].replace("out/", "", 1))
    tag, fn = r["web"].split("/")[-2], r["web"].split("/")[-1]
    ep = int(fn.split("_ep")[1][:3])
    f = ep_facts(tag, ep)
    v = f"v/{tag}/{fn}"
    p = f"p/{tag}/{fn[:-4]}.jpg"
    dst = os.path.join(SITE, v)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.exists(dst) or sha(dst) != sha(src):
        shutil.copy2(src, dst)
        copied += 1
    assert sha(dst) == sha(src), dst
    pst = os.path.join(SITE, p)
    if not os.path.exists(pst):
        os.makedirs(os.path.dirname(pst), exist_ok=True)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                                   capture_output=True, text=True, check=True).stdout.strip())
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(round(min(4.0, dur * 0.6), 2)), "-i", src, "-frames:v", "1",
                        "-vf", "scale=640:-2,format=yuvj420p", "-q:v", "5", pst], check=True)
    if f["surv"] and f["cross"]:
        vd, cls = "기준선 닿고 끝까지 생존", "ok"
    elif f["surv"]:
        vd, cls = f"못 닿음 · 생존 (가장 멀리 {f['x_max']:.2f} m)", "ng"
    elif f["cross"]:
        vd, cls = f"닿은 뒤 넘어짐 {f['fall_t']:.1f} s ({f['x_end']:.2f} m)", "fall"
    else:
        vd, cls = f"넘어짐 {f['fall_t']:.1f} s ({f['x_end']:.2f} m)", "fall"
    m = r["model"]
    cards[r["terrain"]].append((r["run"], int(m), r["cell"], ep, f"""    <article class="tile"><div class="th"><span class="tag {r['run'].lower()}">{r['run']}</span><b>{int(m):,} · {SPEED[r['cell']]} · ep {ep}</b></div>
      <video controls preload="none" playsinline muted poster="{p}"><source src="{v}" type="video/mp4"></video>
      <div class="cap"><div><span class="vd {cls}">{html.escape(vd)}</span></div><span class="look">{html.escape(r['q_line'])} · 고른 규칙: {'그 칸의 첫 Q 통과 판' if r['pick'] == 'first_success' else '그 칸의 첫 Q 미달 판'}</span></div></article>"""))

T, data = F.build()
secs = []
for t in TERR:
    cs = sorted(cards[t], key=lambda c: (c[2], c[1], c[0], c[3]))
    tab = []
    for c in ("fwd03", "fwd05", "fwd10"):
        tds = []
        for mdl in ("e1_m20000", "e2_m20000", "e1_m20499", "e2_m20499"):
            k = f"un_{mdl}_{t}_{c}"
            if not os.path.exists(os.path.join(OUT, k, "cells.json")):
                tds.append("<td class=\"na\">-</td>")
                continue
            x = data.get(k) or F.cell(k)
            tds.append(f"<td><b>{x['cross']}</b> ({x['alive_cross']}) · {x['surv']}</td>")
        tab.append(f"<tr><th scope=\"row\">{SPEED[c]}</th>{''.join(tds)}</tr>")
    secs.append(f"""<section id="{t}">
  <h2>{KO[t]} <span class="sub2">{TRAINED.get(t, '처음 봄')} · 장애물 구간 끝 {data.get(f'un_e1_m20000_{t}_fwd05', F.cell(f'un_e1_m20000_{t}_fwd05'))['zone_end']:.2f} m · 영상 {len(cs)} 편</span></h2>
  <div class="tbl"><table class="def"><thead><tr><th></th><th>E1 20,000</th><th>E2 20,000</th><th>E1 20,499</th><th>E2 20,499</th></tr></thead><tbody>{''.join(tab)}</tbody></table></div>
  <p class="sub">칸: <b>기준선 도달</b> (그중 20 초 끝까지 생존) · 20 초 생존 (% · 100 판). 0.3 m/s 는 느리게 따라가거나 옆으로 새면 20 초 안에 기준선에 닿지 못해, 도달이 지형 난이도와 섞입니다.</p>
  <div class="urow">
{chr(10).join(c[4] for c in cs)}
  </div>
</section>""")

css = io.open(os.path.join(HERE, "page.html"), encoding="utf-8").read()
root = css[css.index(":root{"): css.index("</style>")]
root = root[: root.index("/* 결론 */")] if "/* 결론 */" in root else root
page = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>미경험 지형 영상</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap">
<style>
{root}
.sub{{color:var(--ink-3);font-size:13.5px}}
.sub2{{color:var(--ink-3);font-size:13px;font-weight:400}}
.tbl{{overflow-x:auto;border:1px solid var(--rule);border-radius:8px;background:var(--card);margin:8px 0 6px}}
table.def{{border-collapse:collapse;font-size:14px;width:100%;min-width:560px}}
.def th,.def td{{text-align:left;padding:6px 10px;border-bottom:1px solid var(--rule);font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:13px}}
.def th{{font-weight:500;color:var(--ink-3);font-family:var(--sans);font-size:12.5px}}
.na{{color:var(--ink-3)}}
.urow{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:12px 0 4px}}
@media (max-width:1100px){{.urow{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media (max-width:600px){{.urow{{grid-template-columns:1fr}}}}
.tile{{background:var(--card);border:1px solid var(--rule);border-radius:8px;overflow:hidden;display:flex;flex-direction:column}}
.tile .th{{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;padding:8px 12px;border-bottom:1px solid var(--rule);font-size:14px}}
.tile video{{display:block;width:100%;height:auto;aspect-ratio:16/9;background:#0d1117}}
.tile .cap{{padding:9px 12px 12px;display:grid;gap:5px;font-size:13.5px}}
.tile .look{{color:var(--ink-3);font-size:12.5px}}
.tag{{flex:none;font-family:var(--mono);font-size:12px;font-weight:600;padding:1px 6px;border-radius:4px;color:#fff}}
.tag.e1{{background:var(--e1)}} .tag.e2{{background:var(--e2)}}
:root[data-theme="dark"] .tag{{color:#12161d}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]) .tag{{color:#12161d}}}}
.vd{{display:inline-block;font-size:12px;font-weight:600;padding:1px 7px;border-radius:4px}}
.vd.ok{{background:var(--brand-soft);color:var(--brand-ink)}} .vd.ng{{background:var(--note-soft);color:var(--note-ink)}}
.vd.fall{{background:var(--stop-soft);color:var(--stop-ink)}}
nav.toc{{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:14px;margin:12px 0 0}}
nav.toc a{{color:var(--brand-ink)}}
section{{padding-top:30px}}
footer{{padding:36px 0 56px;color:var(--ink-3);font-size:13px}}
</style>
</head>
<body>
<div class="wrap">
<header class="top">
  <div class="kicker">FOOTHOLD · 시뮬 RL · 2026-10-13</div>
  <h1>미경험 지형 영상 <span class="sub2">E1 · E2 student · 144 편</span></h1>
  <p class="lead">E1 · E2 를 v2 의 「미경험 지형」 10 종 (난이도 0.5 · 그중 물결 · 흩어진 장애물은 비슷한 종류를 학습함) 에 올린 판 가운데, 칸마다 하위 작업이 미리 정한 규칙 (첫 Q 통과 판 · 첫 Q 미달 판) 으로 고른 영상입니다. 영상은 기록을 다시 그린 것이고 물리를 다시 계산하지 않았습니다. 해석과 표는 <a href="{MAIN}#unseen">본 페이지의 미경험 지형 절</a> 에 있습니다.</p>
  <p class="sub">영상 아래 색 띠는 lead 가 원자료에서 다시 잰 그 판의 결과입니다 (기준선 도달 = 넘어지기 전 몸 중심이 장애물 너머 기준선을 한 번 넘음 · 네 발의 안정된 착지는 뜻하지 않음 · 괄호 안은 타일 가운데에서 앞으로 잰 m). 「Q 판정」 은 영상에 박힌 속도 추종 판정이라 기준선 도달과 다를 수 있습니다. 144 편 모두 어둠 · 단색 · 푸른 화면 기준으로 모든 프레임을 검사해 위반 0 입니다 (멈춘 화면 · 로봇 누락은 이 검사로 못 잡습니다).</p>
  <nav class="toc">{' '.join(f'<a href="#{t}">{KO[t]}</a>' for t in TERR)}</nav>
</header>
{chr(10).join(secs)}
<footer>원자료 C:/isaac/ext/go2_rl_robotlab/_eval/out/un_* · 생성 unseen_gallery.py (lead) · ASTRA 14 검증 (원표 재현 · 해석 고침)</footer>
</div>
</body>
</html>
"""
os.makedirs(SITE, exist_ok=True)
io.open(os.path.join(SITE, "index.html"), "w", encoding="utf-8", newline="\n").write(page)
print(json.dumps({"videos": sum(len(v) for v in cards.values()), "copied": copied,
                  "MB": round(sum(os.path.getsize(os.path.join(SITE, "v", d, f)) for d in os.listdir(os.path.join(SITE, "v")) for f in os.listdir(os.path.join(SITE, "v", d))) / 1e6, 1)}))
