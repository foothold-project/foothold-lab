# -*- coding: utf-8 -*-
"""미경험 지형 영상 페이지 2판 (lead · 10/13 저녁).
팀장 10/13: 「이전 '미경험 지형' 영상에 대해서는 내가 원하는 규칙으로 아티팩트 만들지는 않았더라고, 재생 속도랑 이런 것도」
1판 (unseen_gallery.py) 과 다른 점
  - 본 페이지 · 사이트 갤러리의 묶음 재생기 (함께 재생 · 처음으로 · 배속 0.25 ~ 2) 로 바꿈
  - 판정 기준을 위에 모으고 예시 단추로 영상을 엶 (칸마다 긴 문장을 없앰)
  - 결과 색은 lead 가 원자료로 다시 잰 결과 (건넘 · 생존 · 넘어짐) 가 주인공 · Q 판정은 작은 글씨
  - 전체 목록 (판정 거르기 · 누르면 재생기로)
원자료와 영상은 1판과 같다 (같은 경로 · sha256 대조). 숫자는 손으로 쓰지 않는다.
사용: python unseen_gallery_v2.py site=<폴더> [main=<본 페이지 주소>] [design=<설계 문서 주소>]"""
import csv
import hashlib
import html
import io
import json
import os
import sys

import facts5_unseen as F
import unseen_gallery_facts as G

HERE = os.path.dirname(os.path.abspath(__file__))
OPT = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
SITE = OPT["site"]
MAIN = OPT.get("main", "https://claude.ai/artifact/BYuAVDuVJuRWVkAs5mGJSN")
OUT = F.OUT
SPEED = {"fwd03": "0.3 m/s", "fwd05": "0.5 m/s", "fwd10": "1.0 m/s"}
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()

rows = list(csv.DictReader(open(os.path.join(OUT, "unseen_web_list.csv"), encoding="utf-8")))
assert len(rows) == 144, len(rows)
V = []
for r in rows:
    src = os.path.join(OUT, r["web"].replace("out/", "", 1))
    tag, fn = r["web"].split("/")[-2], r["web"].split("/")[-1]
    ep = int(fn.split("_ep")[1][:3])
    f = G.ep_facts(tag, ep)
    v = f"v/{tag}/{fn}"
    p = f"p/{tag}/{fn[:-4]}.jpg"
    dst = os.path.join(SITE, v)
    assert os.path.exists(dst) and sha(dst) == sha(src), ("사이트 사본이 원본과 다름", dst)
    assert os.path.exists(os.path.join(SITE, p)), p
    if f["surv"] and f["cross"]:
        out, txt = "ok", "건넘 · 끝까지 생존"
    elif f["surv"]:
        out, txt = "ng", f"못 닿음 · 생존 · {f['x_max']:.2f} / {f['zone']:.2f} m"
    elif f["cross"]:
        out, txt = "fall2", f"건넌 뒤 넘어짐 · {f['fall_t']:.1f} 초 · {f['x_max']:.2f} / {f['zone']:.2f} m"
    else:
        out, txt = "fall", f"넘어짐 · {f['fall_t']:.1f} 초 · {f['x_max']:.2f} / {f['zone']:.2f} m"
    q = r["q_line"].replace(" (Q-E1 임시 조건 · 현행 정의)", "").replace("Q 판정: ", "")
    V.append({"ter": r["terrain"], "cell": r["cell"], "ck": int(r["model"]), "run": r["run"], "pick": r["pick"], "ep": ep,
              "out": out, "txt": txt, "q": q, "qpass": q.startswith("통과"), "v": v, "p": p,
              "mb": round(os.path.getsize(dst) / 1e6, 2), "zone": round(f["zone"], 2), "reason": f["fall_reason"] or ""})

# 표 숫자: 칸마다 100 판 (F.cell = 하위 작업 집계와 같은 정의 · F.build 가 0.5 · 1.0 칸을 하위 작업 원표와 대조)
_, data = F.build()
T = {}
for t in F.TERR:
    for c in ("fwd03", "fwd05", "fwd10"):
        for m in ("e1_m20000", "e2_m20000", "e1_m20499", "e2_m20499"):
            k = f"un_{m}_{t}_{c}"
            if not os.path.exists(os.path.join(OUT, k, "cells.json")):
                continue
            x = data.get(k) or F.cell(k)
            assert x["n"] == 100, (k, x["n"])
            T[k] = {"cross": x["cross"], "alive": x["alive_cross"], "surv": x["surv"], "zone": round(x["zone_end"], 2)}

# 머리말 숫자 (손으로 쓰지 않음)
seven = [t for t in F.TERR if t not in ("gap", "stepping_stones", "floating_ring")]
v7 = [T[f"un_{m}_{t}_{c}"]["cross"] for t in seven for m, c in F.COLS]
fr = [T[f"un_{m}_floating_ring_{c}"]["cross"] for m, c in F.COLS]
g05 = [T[f"un_{m}_gap_fwd05"]["cross"] for m in ("e1_m20000", "e2_m20000", "e1_m20499", "e2_m20499")]
g10 = [T[f"un_{m}_gap_fwd10"]["cross"] for m in ("e1_m20499", "e2_m20499")]
st = [T[k]["cross"] for k in T if "_stepping_stones_" in k]
TOK = {
    "N_VID": str(len(V)), "MB": f"{sum(x['mb'] for x in V):.0f}",
    "SEVEN": f"{min(v7)} ~ {max(v7)} %", "FR": f"{min(fr)} ~ {max(fr)} %",
    "G05": f"{min(g05)} ~ {max(g05)} %", "G10": f"{min(g10)} ~ {max(g10)} %",
    "ST": f"{max(st)} %", "MAIN": MAIN,
}
assert max(st) == 0, st


def ex(out=None, ter=None, cell=None, qpass=None, run=None, ck=None):
    for x in V:
        if (out is None or x["out"] == out) and (ter is None or x["ter"] == ter) and (cell is None or x["cell"] == cell) \
                and (qpass is None or x["qpass"] == qpass) and (run is None or x["run"] == run) and (ck is None or x["ck"] == ck):
            return x
    raise SystemExit(f"예시 없음 {out} {ter} {cell} {qpass}")


def btn(x, label):
    return (f'<button class="ex" type="button" data-open="{x["ter"]}|{x["cell"]}|{x["ck"]}">{html.escape(label)} · '
            f'{F.KO[x["ter"]]} {SPEED[x["cell"]]} · {x["run"]} {x["ck"]:,} · ep {x["ep"]}</button>')


E_OK = ex(out="ok", ter="wave", cell="fwd05")
E_QNG = ex(out="ng", qpass=True)
E_FALL2 = ex(out="fall2")
E_GAPF = ex(out="fall", ter="gap", cell="fwd10")
E_GAPN = ex(ter="gap", cell="fwd05")
E_GAPOK = ex(out="ok", ter="gap")
E_ST = ex(ter="stepping_stones", cell="fwd05")
E_SLOW = ex(out="ng", cell="fwd03", qpass=False)

KO = F.KO
TRAINED = {t: F.TRAINED.get(t, "처음 봄") for t in F.TERR}
DATA = {"V": V, "T": T, "TERR": F.TERR, "KO": KO, "TR": TRAINED, "SPEED": SPEED}

css = io.open(os.path.join(HERE, "page.html"), encoding="utf-8").read()
root = css[css.index(":root{"): css.index("</style>")]
root = root[: root.index("/* 결론 */")] if "/* 결론 */" in root else root

STYLE = r"""
.sub{color:var(--ink-3);font-size:13.5px}
.sub2{color:var(--ink-3);font-size:13px;font-weight:400}
.read{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 28px;background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:16px 18px;margin:14px 0 4px}
@media (max-width:900px){.read{grid-template-columns:1fr}}
.read h3{font-size:15px;margin:0 0 4px}
.read p{margin:0 0 6px;font-size:14.5px;color:var(--ink-2)}
.read .exs{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
.ex{font:inherit;font-size:13px;text-align:left;border:1px solid var(--rule);background:var(--paper-2);color:var(--brand-ink);border-radius:6px;padding:5px 8px;cursor:pointer}
.ex:hover{border-color:var(--brand)}
.legend{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:13.5px;color:var(--ink-2);margin:8px 0 0}
.vd{display:inline-block;font-size:12px;font-weight:600;padding:1px 7px;border-radius:4px;margin-right:4px;white-space:nowrap}
.vd.ok{background:var(--brand-soft);color:var(--brand-ink)}
.vd.ng{background:var(--note-soft);color:var(--note-ink)}
.vd.fall2{background:var(--stop-soft);color:var(--stop-ink)}
.vd.fall{background:var(--stop);color:var(--card)}
.vd.q{background:var(--paper-2);color:var(--ink-3);font-weight:500}
.why{border-left:3px solid var(--brand);padding:2px 0 2px 14px;margin:14px 0}
.why p{margin:0 0 6px}
.frow{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:4px 0}
.frow .lab{font-size:12.5px;color:var(--ink-3);width:72px;flex:none}
.chip{font:inherit;font-size:13.5px;border:1px solid var(--rule);background:var(--card);color:var(--ink-2);border-radius:999px;padding:5px 11px;cursor:pointer;min-height:32px}
.chip[aria-pressed="true"]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.chip:focus-visible,.ex:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
.chip .n{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);margin-left:5px}
.chip[aria-pressed="true"] .n{color:inherit;opacity:.8}
.chip:disabled{opacity:.4;cursor:default}
.player{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:14px 16px 16px;margin:12px 0}
.quadhead{font-size:14.5px;margin:10px 0 8px;color:var(--ink-2)}
.trow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0 12px}
.trow .clock{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:13.5px;min-width:9.5em;color:var(--ink)}
.trow .flabel{font-size:12.5px;color:var(--ink-3);margin-left:6px}
.trow .tnote{font-size:12.5px;color:var(--stop-ink)}
.quad{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
@media (max-width:1100px){.quad{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:600px){.quad{grid-template-columns:1fr}.frow .lab{width:100%}}
.tile{background:var(--paper);border:1px solid var(--rule);border-radius:8px;overflow:hidden;display:flex;flex-direction:column}
.tile .th{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;padding:7px 10px;border-bottom:1px solid var(--rule);font-size:13.5px}
.tile video{display:block;width:100%;height:auto;aspect-ratio:16/9;background:#0d1117}
.tile .cap{padding:8px 10px 10px;display:grid;gap:4px;font-size:13px}
.tile .none{padding:14px 10px;color:var(--ink-3);font-size:13.5px;aspect-ratio:16/9;display:flex;align-items:center}
.tag{flex:none;font-family:var(--mono);font-size:12px;font-weight:600;padding:1px 6px;border-radius:4px;color:#fff}
.tag.e1{background:var(--e1)} .tag.e2{background:var(--e2)}
:root[data-theme="dark"] .tag{color:#12161d}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .tag{color:#12161d}}
.tbl{overflow-x:auto;border:1px solid var(--rule);border-radius:8px;background:var(--card);margin:8px 0 6px}
table.mx{border-collapse:collapse;width:100%;min-width:640px;font-size:13.5px}
.mx th,.mx td{padding:7px 10px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:middle}
.mx thead th{font-weight:500;color:var(--ink-3);font-size:12.5px}
.mx tbody tr{cursor:pointer}
.mx tbody tr:hover td,.mx tbody tr:hover th,.mx tbody tr:focus td,.mx tbody tr:focus th{background:var(--paper-2)}
.mx tbody tr:focus{outline:2px solid var(--brand);outline-offset:-2px}
.mx .tr{display:block;font-size:12px;color:var(--ink-3);font-weight:400}
.cellv{display:grid;grid-template-columns:3.2em 1fr;gap:2px 8px;align-items:center;font-family:var(--mono);font-variant-numeric:tabular-nums}
.bar{height:6px;border-radius:3px;background:var(--paper-2);overflow:hidden}
.bar i{display:block;height:100%;background:var(--brand)}
.cellv .s{grid-column:1/3;font-size:11.5px;color:var(--ink-3)}
.na{color:var(--ink-3)}
table.vlist{border-collapse:collapse;font-size:13.5px;width:100%;min-width:900px}
.vlist th{position:sticky;top:0;background:var(--card);text-align:left;font-weight:500;color:var(--ink-3);font-size:12.5px;padding:8px 10px;border-bottom:1px solid var(--rule)}
.vlist td{padding:7px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
.vlist tr[data-i]{cursor:pointer}
.vlist tr[data-i]:hover td,.vlist tr[data-i]:focus td{background:var(--paper-2)}
.vlist tr:focus{outline:2px solid var(--brand);outline-offset:-2px}
.lwrap{max-height:520px;overflow:auto;border:1px solid var(--rule);border-radius:8px;background:var(--card)}
nav.toc{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:14px;margin:12px 0 0}
nav.toc a{color:var(--brand-ink)}
footer{padding:36px 0 56px;color:var(--ink-3);font-size:13px}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
"""

BODY = """
<div class="wrap">
<header class="top">
  <div class="kicker">FOOTHOLD · 시뮬 RL · 미경험 지형 · 2판 (10/13 저녁)</div>
  <h1>미경험 지형 영상 <span class="sub2">E1 · E2 student · %%N_VID%% 편</span></h1>
  <p class="lead">E1 · E2 를 v2 의 미경험 지형 10 종에서 1 만 판 잰 결과와, 그중 %%N_VID%% 편의 영상입니다. 지형 · 속도 · 체크포인트를 고르면 네 편이 함께 재생됩니다. 배속을 낮추면 발이 닿는 순간을 볼 수 있습니다. 실험 배경과 해석은 <a href="%%MAIN%%#unseen" target="_blank" rel="noopener">본 페이지</a> 에 있습니다.</p>
  <nav class="toc"><a href="#read">먼저 읽을 것</a> <a href="#why">gap · 징검다리</a> <a href="#table">지형별 숫자</a> <a href="#play">함께 보기</a> <a href="#list">전체 목록</a></nav>
</header>

<section id="read">
  <h2>먼저 읽을 것</h2>
  <div class="read">
    <div>
      <h3>건넘</h3>
      <p>넘어지기 전에 몸 중심이 장애물 구간 끝 (기준선) 을 한 번이라도 넘은 판입니다. 네 발이 안정되게 디뎠다는 뜻은 아닙니다.</p>
      <div class="exs">%%EX_OK%%</div>
    </div>
    <div>
      <h3>끝까지 생존 · 넘어짐</h3>
      <p>20 초 동안 넘어지지 않으면 생존입니다. 몸통이 땅에 닿거나 60 도 넘게 0.2 초 기울면 넘어짐입니다. 기준선을 넘은 뒤에 넘어진 판은 따로 표시합니다.</p>
      <div class="exs">%%EX_FALL2%%</div>
    </div>
    <div>
      <h3>영상을 고른 규칙</h3>
      <p>칸마다 「속도 추종 판정 (Q) 」 으로 처음 통과한 판과 처음 미달한 판을 골랐습니다. Q 는 명령한 속도를 얼마나 잘 따랐는지를 보는 다른 잣대입니다. 그래서 Q 는 통과인데 기준선에 못 닿은 판이 있습니다. 영상 화면 안의 판정 글자도 Q 입니다.</p>
      <div class="exs">%%EX_QNG%%</div>
    </div>
    <div>
      <h3>0.3 m/s 는 따로 읽기</h3>
      <p>0.3 m/s 로 20 초를 걸으면 6 m 입니다. 조금 느리게 따라가거나 옆으로 새면 기준선에 못 닿습니다. 그래서 0.3 m/s 의 「못 닿음」 에는 지형 탓과 느림이 섞여 있습니다.</p>
      <div class="exs">%%EX_SLOW%%</div>
    </div>
  </div>
  <p class="sub">결과 글자의 「a / b m」 는 타일 가운데에서 앞으로 잰 가장 먼 위치 a 와 기준선 b 입니다. 출발 위치는 가운데에서 앞뒤 · 좌우 0.5 m 안에서 무작위라 a 가 음수일 수 있습니다 (출발점에서 앞으로 가지 못하고 넘어진 판).</p>
  <div class="legend"><span><span class="vd ok">건넘 · 끝까지 생존</span></span><span><span class="vd ng">못 닿음 · 생존</span></span><span><span class="vd fall2">건넌 뒤 넘어짐</span></span><span><span class="vd fall">넘어짐</span></span><span><span class="vd q">Q 판정</span> 속도 추종 (작은 글씨)</span></div>
  <p class="sub">영상은 저장된 궤적을 다시 그린 기록 재생입니다 (물리를 다시 계산하지 않음). %%N_VID%% 편 (%%MB%% MB) 모두 모든 프레임을 검사했고 검은 · 단색 · 푸른 화면 프레임은 0 장입니다. 멈춘 화면이나 로봇이 빠진 화면은 이 검사로 못 잡습니다.</p>
</section>

<section id="why">
  <h2>gap · 징검다리에서 깨지는 까닭</h2>
  <div class="why">
    <p>흩어진 장애물 · 물결 · 구덩이 · 레일 · 별 모양 다리 · 상자 반복 · 기둥 반복 일곱 종은 0.5 · 1.0 m/s 에서 <b>%%SEVEN%%</b> 건넜습니다. 떠 있는 고리는 %%FR%% 입니다. gap 은 0.5 m/s 에서 <b>%%G05%%</b>, 1.0 m/s 에서 %%G10%% 이고, 징검다리는 <b>%%ST%%</b> 입니다.</p>
    <p>까닭은 둘이 겹칩니다. 배포하는 student 는 지형 높이를 보지 않고 몸 감각 (관절 · 자세 · 지난 행동) 만 봅니다. 그래서 발이 빠진 뒤에야 구멍을 압니다. 또 E1 · E2 는 학습 때 gap · 징검다리를 한 번도 연습하지 않았습니다 (학습 지형 비율 0). 둘 중 어느 쪽이 더 큰지는 아직 가르지 못했습니다. 지도를 주는 판과 안 주는 판을 같은 연습으로 비교하는 다음 실험이 그것을 가릅니다.</p>
    <div class="exs">%%EX_GAPN%% %%EX_GAPF%% %%EX_GAPOK%% %%EX_ST%%</div>
  </div>
</section>

<section id="table">
  <h2>지형별 숫자 <span class="sub2">칸마다 100 판 · 막대와 큰 숫자 = 건넘 % · 아래 작은 글씨 = 그중 끝까지 생존 · 20 초 생존</span></h2>
  <div class="frow" id="tspd"></div>
  <div class="tbl"><table class="mx" id="mx"></table></div>
  <p class="sub">줄을 누르면 아래 재생기가 그 지형으로 바뀝니다. 「같은 종류 학습」 은 매개변수가 다른 같은 생성기를 학습했다는 뜻이고, 「정의만」 은 학습 설정에 이름은 있으나 비율이 0 이라 한 번도 나오지 않았다는 뜻입니다.</p>
</section>

<section id="play">
  <h2>함께 보기</h2>
  <div class="player">
    <div id="pick"></div>
    <div class="quadhead" id="quadhead"></div>
    <div id="tp"></div>
    <div class="quad" id="quad"></div>
  </div>
</section>

<section id="list">
  <h2>전체 목록 <span class="sub2" id="lcount"></span></h2>
  <div id="lfilt"></div>
  <div class="lwrap"><table class="vlist" id="vlist"></table></div>
</section>

<footer>원자료 C:/isaac/ext/go2_rl_robotlab/_eval/out/un_* (episodes.csv · traj.npz · env_origins.npy · meta.json) · 영상 고른 목록 unseen_web_list.csv · 생성 unseen_gallery_v2.py (lead) · 1판과 같은 영상 (sha256 대조) · 재생기는 사이트 갤러리 (web/gallery/gallery.js) 의 묶음 재생을 옮겨 씀</footer>
</div>
"""

JS = r"""
const D = JSON.parse(document.getElementById('data').textContent);
const $ = s => document.querySelector(s);
const GP = {};
GP.el = function (tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'text') node.textContent = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k === 'class') node.className = v;
    else node.setAttribute(k, v === true ? '' : String(v));
  }
  for (const child of (children || [])) { if (child) node.appendChild(child); }
  return node;
};
GP.video = function (attrs) {
  const v = GP.el('video', Object.assign({ preload: 'metadata', playsinline: true, muted: true }, attrs || {}));
  v.muted = true; v.defaultMuted = true;
  return v;
};
GP.attach = function (video, src) {
  if (video.getAttribute('src') === src) return video;
  const rate = video.playbackRate;
  video.setAttribute('src', src);
  video.load();
  if (rate && rate !== 1) {
    video.playbackRate = rate;
    video.addEventListener('loadedmetadata', () => { video.playbackRate = rate; }, { once: true });
  }
  return video;
};
GP.play = function (video) {
  const p = video.play();
  return p && p.catch ? p.catch(err => ({ error: err })) : Promise.resolve();
};
GP.fmt = function (s) {
  if (!Number.isFinite(s)) return '--:--';
  const m = Math.floor(s / 60);
  return m + ':' + String(Math.floor(s % 60)).padStart(2, '0') + '.' + String(Math.floor((s % 1) * 10));
};
GP.syncGroup = function (o) {
  const players = {}; let order = []; let running = false, raf = 0, base = 0;
  const live = () => order.map(k => players[k]).filter(p => p && p.video.getAttribute('src'));
  const longest = () => Math.max(0, ...live().map(p => p.duration || 0));
  const clock = () => { if (o.onClock) o.onClock(GP.fmt(base) + ' / ' + GP.fmt(longest())); };
  function tick() {
    if (!running) return;
    base = Math.max(0, ...live().map(p => p.video.currentTime));
    clock();
    if (base >= longest() - 0.04) { stop(); return; }
    raf = requestAnimationFrame(tick);
  }
  async function play() {
    running = true;
    const res = await Promise.all(live().map(async p => {
      if (p.duration && p.video.currentTime >= p.duration - 0.04) return null;
      const r = await GP.play(p.video);
      return r && r.error ? p.key : null;
    }));
    const failed = res.filter(Boolean);
    if (o.onNote) o.onNote(failed.length ? failed.join(' · ') + ' 이 재생을 시작하지 못했습니다' : '');
    if (o.onButton) o.onButton('멈춤');
    raf = requestAnimationFrame(tick);
  }
  function stop() {
    running = false; cancelAnimationFrame(raf);
    live().forEach(p => p.video.pause());
    if (o.onButton) o.onButton('함께 재생');
  }
  return {
    clear() { stop(); order = []; Object.keys(players).forEach(k => delete players[k]); base = 0; clock(); },
    add(key, video, duration) {
      players[key] = { key, video, duration: duration || 0 };
      if (order.indexOf(key) < 0) order.push(key);
      video.addEventListener('loadedmetadata', () => { if (players[key]) { players[key].duration = video.duration || duration || 0; clock(); } });
      video.addEventListener('pause', () => { if (running && live().every(p => p.video.paused)) stop(); });
    },
    toggle() { if (running) stop(); else play(); },
    stop,
    seek(t) { base = t; live().forEach(p => { p.video.currentTime = Math.min(t, Math.max(0, (p.duration || t) - 0.01)); }); clock(); },
    rate(x) { live().forEach(p => { p.video.playbackRate = x; }); },
    clock
  };
};
GP.transport = function (group, rates) {
  const btn = GP.el('button', { class: 'chip', type: 'button', text: '함께 재생' });
  const rew = GP.el('button', { class: 'chip', type: 'button', text: '처음으로' });
  const clock = GP.el('span', { class: 'clock', text: '0:00.0 / 0:00.0' });
  const note = GP.el('span', { class: 'tnote' });
  const row = GP.el('div', { class: 'trow' }, [btn, rew, clock, GP.el('span', { class: 'flabel', text: '배속' })]);
  let cur = 1;
  (rates || [0.25, 0.5, 1, 2]).forEach(x => {
    const b = GP.el('button', { class: 'chip', type: 'button', 'aria-pressed': x === 1 ? 'true' : 'false', text: x + '×' });
    b.addEventListener('click', () => {
      row.querySelectorAll('.chip[aria-pressed]').forEach(o => o.setAttribute('aria-pressed', 'false'));
      b.setAttribute('aria-pressed', 'true'); cur = x; group.rate(x);
    });
    row.appendChild(b);
  });
  row.appendChild(note);
  btn.addEventListener('click', () => group.toggle());
  rew.addEventListener('click', () => { group.stop(); group.seek(0); });
  return { row, button: btn, clock, note, rate: () => cur };
};

const PICK = { first_success: 'Q 첫 통과 판', first_failure: 'Q 첫 미달 판' };
const MODELS = [['E1', 20000], ['E2', 20000], ['E1', 20499], ['E2', 20499]];
const key = (run, ck, ter, cell) => `un_${run.toLowerCase()}_m${ck}_${ter}_${cell}`;
const fmtN = n => n.toLocaleString('en-US');
const badge = v => `<span class="vd ${v.out}">${v.txt}</span>`;

/* ---------- 지형별 숫자 ---------- */
const TS = { cell: 'fwd05' };
function chipRow(host, label, vals, cur, onPick, opts) {
  const row = GP.el('div', { class: 'frow' }, [GP.el('span', { class: 'lab', text: label })]);
  vals.forEach(x => {
    const lab = opts && opts.label ? opts.label(x) : String(x);
    const b = GP.el('button', { class: 'chip', type: 'button', 'aria-pressed': x === cur ? 'true' : 'false', text: lab });
    if (opts && opts.count) b.appendChild(GP.el('span', { class: 'n', text: String(opts.count(x)) }));
    if (opts && opts.disabled && opts.disabled(x)) b.disabled = true;
    b.addEventListener('click', () => onPick(x));
    row.appendChild(b);
  });
  host.appendChild(row);
}
function renderTable() {
  const host = $('#tspd'); host.innerHTML = '';
  chipRow(host, '속도', ['fwd03', 'fwd05', 'fwd10'], TS.cell, x => { TS.cell = x; renderTable(); }, { label: x => D.SPEED[x] });
  const cols = MODELS.filter(([r, ck]) => D.T[key(r, ck, D.TERR[0], TS.cell)]);
  let h = '<thead><tr><th>지형</th>' + cols.map(([r, ck]) => `<th><span class="tag ${r.toLowerCase()}">${r}</span> ${fmtN(ck)}</th>`).join('') + '</tr></thead><tbody>';
  D.TERR.forEach(t => {
    h += `<tr data-t="${t}" tabindex="0"><th scope="row">${D.KO[t]}<span class="tr">${D.TR[t]}</span></th>`;
    cols.forEach(([r, ck]) => {
      const x = D.T[key(r, ck, t, TS.cell)];
      h += x ? `<td><div class="cellv"><b>${x.cross}</b><span class="bar"><i style="width:${x.cross}%"></i></span><span class="s">끝까지 ${x.alive} · 생존 ${x.surv}</span></div></td>` : '<td class="na">-</td>';
    });
    h += '</tr>';
  });
  $('#mx').innerHTML = h + '</tbody>';
}
$('#mx').addEventListener('click', e => {
  const tr = e.target.closest('tr[data-t]'); if (!tr) return;
  openAt(tr.dataset.t, TS.cell, S.ck === 20000 && TS.cell === 'fwd10' ? 20499 : S.ck);
});
$('#mx').addEventListener('keydown', e => { if (e.key === 'Enter') { const tr = e.target.closest('tr[data-t]'); if (tr) tr.click(); } });

/* ---------- 함께 보기 ---------- */
const S = { ter: 'gap', cell: 'fwd10', ck: 20499 };
let ui = null;
const group = GP.syncGroup({
  onClock: t => { if (ui) ui.clock.textContent = t; },
  onButton: t => { if (ui) ui.button.textContent = t; },
  onNote: t => { if (ui) ui.note.textContent = t; }
});
ui = GP.transport(group);
$('#tp').appendChild(ui.row);
const has = (ter, cell, ck) => D.V.some(v => v.ter === ter && v.cell === cell && v.ck === ck);
function fixSel() {
  if (has(S.ter, S.cell, S.ck)) return;
  for (const c of ['fwd05', 'fwd10', 'fwd03']) for (const k of [S.ck, 20000, 20499]) if (has(S.ter, c, k)) { S.cell = c; S.ck = k; return; }
}
function renderPick() {
  const host = $('#pick'); host.innerHTML = '';
  chipRow(host, '지형', D.TERR, S.ter, x => { S.ter = x; fixSel(); renderPick(); renderQuad(); },
    { label: x => D.KO[x], count: x => D.V.filter(v => v.ter === x).length });
  chipRow(host, '속도', ['fwd03', 'fwd05', 'fwd10'], S.cell, x => { S.cell = x; fixSel(); renderPick(); renderQuad(); },
    { label: x => D.SPEED[x], disabled: x => ![20000, 20499].some(k => has(S.ter, x, k)) });
  chipRow(host, '체크포인트', [20000, 20499], S.ck, x => { S.ck = x; fixSel(); renderPick(); renderQuad(); },
    { label: x => 'model_' + x, disabled: x => !has(S.ter, S.cell, x) });
}
function renderQuad() {
  group.clear();
  const q = $('#quad'); q.innerHTML = '';
  const set = D.V.filter(v => v.ter === S.ter && v.cell === S.cell && v.ck === S.ck);
  const a = D.T[key('E1', S.ck, S.ter, S.cell)], b = D.T[key('E2', S.ck, S.ter, S.cell)];
  $('#quadhead').innerHTML = `<b>${D.KO[S.ter]}</b> · ${D.SPEED[S.cell]} · model_${S.ck} · 100 판 건넘 E1 ${a ? a.cross : '-'} % · E2 ${b ? b.cross : '-'} % · 장애물 구간 끝 ${a ? a.zone.toFixed(2) : '-'} m`;
  ['first_success', 'first_failure'].forEach(pk => ['E1', 'E2'].forEach(run => {
    const v = set.find(x => x.pick === pk && x.run === run);
    const tile = GP.el('article', { class: 'tile' });
    tile.appendChild(GP.el('div', { class: 'th', html: `<span class="tag ${run.toLowerCase()}">${run}</span><b>${PICK[pk]}</b>` + (v ? `<span class="sub">ep ${v.ep}</span>` : '') }));
    if (!v) {
      tile.appendChild(GP.el('div', { class: 'none', text: pk === 'first_failure' ? 'Q 미달 판 없음 · 이 칸은 100 판 모두 Q 통과' : 'Q 통과 판 없음 · 이 칸은 100 판 모두 Q 미달' }));
    } else {
      const vid = GP.video({ poster: v.p, controls: true, 'aria-label': `${run} ${D.KO[S.ter]} ${D.SPEED[S.cell]} ep ${v.ep}` });
      GP.attach(vid, v.v);
      vid.playbackRate = ui.rate();
      group.add(run + ' ' + PICK[pk], vid, 0);
      tile.appendChild(vid);
      tile.appendChild(GP.el('div', { class: 'cap', html: `<div>${badge(v)}</div><div><span class="vd q">Q ${v.q}</span></div>` }));
    }
    q.appendChild(tile);
  }));
  group.clock();
}
function openAt(ter, cell, ck) {
  S.ter = ter; S.cell = cell; S.ck = ck; fixSel(); renderPick(); renderQuad();
  $('#play').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
}
document.querySelectorAll('button.ex').forEach(b => b.addEventListener('click', () => {
  const [t, c, k] = b.dataset.open.split('|'); openAt(t, c, +k);
}));

/* ---------- 전체 목록 ---------- */
const OUTS = { ok: '건넘 · 끝까지 생존', ng: '못 닿음 · 생존', fall2: '건넌 뒤 넘어짐', fall: '넘어짐' };
const LF = { out: '모두' };
function renderListFilter() {
  const host = $('#lfilt'); host.innerHTML = '';
  const opts = ['모두', 'ok', 'ng', 'fall2', 'fall'];
  chipRow(host, '결과', opts, LF.out, x => { LF.out = x; renderListFilter(); renderList(); },
    { label: x => x === '모두' ? '모두' : OUTS[x], count: x => x === '모두' ? D.V.length : D.V.filter(v => v.out === x).length });
}
function renderList() {
  const rows = D.V.map((v, i) => [v, i]).filter(([v]) => LF.out === '모두' || v.out === LF.out)
    .sort((x, y) => D.TERR.indexOf(x[0].ter) - D.TERR.indexOf(y[0].ter) || x[0].cell.localeCompare(y[0].cell) || x[0].ck - y[0].ck || x[0].run.localeCompare(y[0].run));
  let h = '<thead><tr><th>지형</th><th>속도</th><th>체크포인트</th><th>정책</th><th>고른 판</th><th>결과</th><th>Q 판정 (속도 추종)</th></tr></thead><tbody>';
  rows.forEach(([v, i]) => {
    h += `<tr data-i="${i}" tabindex="0"><td>${D.KO[v.ter]}</td><td>${D.SPEED[v.cell]}</td><td>${fmtN(v.ck)}</td><td><span class="tag ${v.run.toLowerCase()}">${v.run}</span></td><td>${PICK[v.pick]} · ep ${v.ep}</td><td>${badge(v)}</td><td class="sub">${v.q}</td></tr>`;
  });
  $('#vlist').innerHTML = h + '</tbody>';
  $('#lcount').textContent = rows.length + ' 편';
}
$('#vlist').addEventListener('click', e => {
  const tr = e.target.closest('tr[data-i]'); if (!tr) return;
  const v = D.V[+tr.dataset.i]; openAt(v.ter, v.cell, v.ck);
});
$('#vlist').addEventListener('keydown', e => { if (e.key === 'Enter') { const tr = e.target.closest('tr[data-i]'); if (tr) tr.click(); } });

renderTable(); fixSel(); renderPick(); renderQuad(); renderListFilter(); renderList();
"""

body = BODY
for k, v in TOK.items():
    body = body.replace(f"%%{k}%%", v)
body = (body.replace("%%EX_OK%%", btn(E_OK, "건넘 예"))
        .replace("%%EX_FALL2%%", btn(E_FALL2, "건넌 뒤 넘어짐 예"))
        .replace("%%EX_QNG%%", btn(E_QNG, "Q 통과 · 못 닿음 예"))
        .replace("%%EX_SLOW%%", btn(E_SLOW, "느려서 못 닿음 예"))
        .replace("%%EX_GAPN%%", btn(E_GAPN, "넘어짐"))
        .replace("%%EX_GAPF%%", btn(E_GAPF, "넘어짐"))
        .replace("%%EX_GAPOK%%", btn(E_GAPOK, "건넌 판"))
        .replace("%%EX_ST%%", btn(E_ST, "넘어짐")))
assert "%%" not in body, body[body.index("%%") - 40: body.index("%%") + 40]

page = ("<!doctype html>\n<html lang=\"ko\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>미경험 지형 영상</title>\n"
        "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">\n<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>\n"
        "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap\">\n"
        "<style>\n" + root + STYLE + "</style>\n</head>\n<body>\n" + body +
        "<script type=\"application/json\" id=\"data\">" + json.dumps(DATA, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
        "<script>\n" + JS + "</script>\n</body>\n</html>\n")
for bad in ("\u2014", "\u2013"):
    assert bad not in page, "dash"
io.open(os.path.join(SITE, "index.html"), "w", encoding="utf-8", newline="\n").write(page)
print(json.dumps({"videos": len(V), "MB": TOK["MB"], "seven": TOK["SEVEN"], "fr": TOK["FR"], "g05": TOK["G05"], "g10": TOK["G10"],
                  "examples": {k: f"{x['ter']} {x['cell']} {x['run']} {x['ck']} ep{x['ep']} {x['out']}" for k, x in
                               (("ok", E_OK), ("qng", E_QNG), ("fall2", E_FALL2), ("gapf", E_GAPF), ("gapn", E_GAPN), ("gapok", E_GAPOK), ("st", E_ST), ("slow", E_SLOW))},
                  "bytes": len(page.encode())}, ensure_ascii=False))
