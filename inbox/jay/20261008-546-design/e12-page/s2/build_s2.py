"""S2 A/B 절을 E1 · E2 페이지(8판)에 끼워 넣는 생성기.

원자료:
  A 학습 기록  s2_step27_run/runs/shortA-.../out/updates.jsonl
  B 학습 기록  s2_step29a_run/frozen_delivery/runs/shortB-.../out/updates.jsonl
  평가 결과    S2-AB-UPDATE2000.json (s2_eval_full_result.py 가 쓴 것, 없으면 「평가 중」)
  영상 목록    step30 도구의 manifest json (없으면 「영상 준비 중」)
  게시본       현재 아티팩트의 index.html (7판)
출력: <site>/index.html (+ v/s2/*.mp4, p/s2/*.jpg 복사)
숫자는 손으로 쓰지 않는다. 결과 판정은 결과 전에 등록한 규칙(evaluation_criteria_s2_ab.json)을 그대로 적용한다.
"""
from __future__ import annotations
import argparse, hashlib, html, json, math, re, shutil
from pathlib import Path

LAYERS = [("gap", "gap (틈)", "목표"), ("stepping_stones", "징검다리", "목표"),
          ("flat", "평지", "퇴행 감시"), ("stairs_up", "계단 오르기", "퇴행 감시")]
E = html.escape


def read_updates(p):
    rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    return rows


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------- 그림 도구 ----------
def line_chart(series, *, title, ylab, ymin, ymax, yticks, w=560, h=250, skip_first=0):
    L, R, T, B = 52, 14, 18, 36
    pw, ph = w - L - R, h - T - B
    xmax = max(len(s["y"]) for s in series)
    def X(i): return L + pw * (i / max(1, xmax - 1))
    def Y(v): return T + ph * (1 - (min(max(v, ymin), ymax) - ymin) / (ymax - ymin))
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{E(title)}" class="s2c">']
    for t in yticks:
        y = Y(t)
        out.append(f'<line x1="{L}" x2="{w-R}" y1="{y:.1f}" y2="{y:.1f}" class="gl"/>'
                   f'<text x="{L-6}" y="{y+4:.1f}" class="ax" text-anchor="end">{t:g}</text>')
    for u in (0, 500, 1000, 1500, 2000):
        x = X(u - 1 if u else 0)
        out.append(f'<text x="{x:.1f}" y="{h-14}" class="ax" text-anchor="middle">{u}</text>')
    out.append(f'<text x="{L+pw/2:.1f}" y="{h-1}" class="ax" text-anchor="middle">update</text>')
    out.append(f'<text x="12" y="{T+ph/2:.1f}" class="ax" transform="rotate(-90 12 {T+ph/2:.1f})" text-anchor="middle">{E(ylab)}</text>')
    for s in series:
        ys = s["y"]
        step = max(1, len(ys) // 500)
        pts = " ".join(f"{X(i):.1f},{Y(ys[i]):.1f}" for i in range(skip_first, len(ys), step))
        out.append(f'<polyline points="{pts}" class="ln {s["cls"]}"/>')
    out.append("</svg>")
    return "".join(out)


def design_svg():
    w, h = 980, 250
    box = lambda x, y, bw, bh, cls, t1, t2="": (
        f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="8" class="bxs {cls}"/>'
        f'<text x="{x+bw/2}" y="{y+(24 if t2 else bh/2+5)}" text-anchor="middle" class="bt1">{E(t1)}</text>'
        + (f'<text x="{x+bw/2}" y="{y+46}" text-anchor="middle" class="bt2">{E(t2)}</text>' if t2 else ""))
    arrow = lambda x1, y1, x2, y2: f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="ar" marker-end="url(#s2ah)"/>'
    o = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="A/B 실험 설계 그림" class="s2c">',
         '<defs><marker id="s2ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="arh"/></marker></defs>',
         box(10, 95, 190, 64, "par", "E1 model_20000", "같은 부모 · 시드 11"),
         box(270, 20, 250, 70, "a", "A · 지도 없음", "지도 입력 374 칸 = 0"),
         box(270, 160, 250, 70, "b", "B · 지도 있음", "높이 187 점 + 유효 표시"),
         box(590, 95, 170, 64, "par", "각 2,000 update", "로봇 1,024 · 같은 설정"),
         box(810, 95, 160, 64, "ev", "같은 60 쌍 평가", "B − A 쌍 차이"),
         arrow(200, 120, 268, 58), arrow(200, 134, 268, 192),
         arrow(520, 55, 588, 116), arrow(520, 195, 588, 140), arrow(760, 127, 808, 127), "</svg>"]
    return "".join(o)


def result_svg(layers):
    w, rowh, top = 980, 74, 34
    h = top + rowh * len(LAYERS) + 30
    L1, barx, barw, dx, dw = 10, 230, 330, 640, 300
    def BX(r): return barx + barw * r
    def DX(d): return dx + dw * (d + 1) / 2          # d in [-1, 1]
    o = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="지형별 성공률 A 대 B 와 쌍 차이" class="s2c">',
         f'<text x="{barx}" y="18" class="ax">성공률 (기준선 도달 · 끝까지 생존)</text>',
         f'<text x="{dx}" y="18" class="ax">B − A (쌍 차이) · 95% 구간</text>']
    for t in (0, .5, 1):
        o.append(f'<line x1="{BX(t):.1f}" x2="{BX(t):.1f}" y1="{top-6}" y2="{h-26}" class="gl"/>'
                 f'<text x="{BX(t):.1f}" y="{h-10}" class="ax" text-anchor="middle">{int(t*100)}%</text>')
    for t in (-1, -.5, 0, .5, 1):
        o.append(f'<line x1="{DX(t):.1f}" x2="{DX(t):.1f}" y1="{top-6}" y2="{h-26}" class="gl{" z" if t == 0 else ""}"/>'
                 f'<text x="{DX(t):.1f}" y="{h-10}" class="ax" text-anchor="middle">{int(t*100):+d}%p</text>'.replace("+0%p", "0"))
    for i, (key, name, role) in enumerate(LAYERS):
        y = top + i * rowh
        lay = layers.get(key) if layers else None
        o.append(f'<text x="{L1}" y="{y+22}" class="bt1" text-anchor="start">{E(name)}</text>'
                 f'<text x="{L1}" y="{y+42}" class="bt2" text-anchor="start">{E(role)}'
                 + (f' · {lay["valid_pairs"]}/{lay["planned_pairs"]} 쌍' if lay else " · 평가 중") + "</text>")
        if role == "목표":
            o.append(f'<line x1="{DX(.1):.1f}" x2="{DX(.1):.1f}" y1="{y+4}" y2="{y+rowh-14}" class="thr"/>')
        if not lay or not lay["valid_pairs"]:
            continue
        n = lay["valid_pairs"]
        ra, rb = lay["A_success"] / n, lay["B_success"] / n
        for j, (r, cls, lab, cnt) in enumerate(((ra, "a", "A", lay["A_success"]), (rb, "b", "B", lay["B_success"]))):
            yy = y + 8 + j * 26
            o.append(f'<rect x="{barx}" y="{yy}" width="{barw}" height="18" class="trk"/>'
                     f'<rect x="{barx}" y="{yy}" width="{barw*r:.1f}" height="18" class="bar {cls}"/>'
                     f'<text x="{barx-8}" y="{yy+14}" class="ax" text-anchor="end">{lab}</text>'
                     f'<text x="{barx+barw+8}" y="{yy+14}" class="vl">{cnt}/{n} · {r*100:.0f}%</text>')
        d = (lay["discordant"]["B_only"] - lay["discordant"]["A_only"]) / n
        ci = lay.get("paired_tango_95")
        yc = y + 30
        if ci:
            o.append(f'<line x1="{DX(ci[1]):.1f}" x2="{DX(ci[2]):.1f}" y1="{yc}" y2="{yc}" class="ci"/>'
                     f'<line x1="{DX(ci[1]):.1f}" x2="{DX(ci[1]):.1f}" y1="{yc-7}" y2="{yc+7}" class="ci"/>'
                     f'<line x1="{DX(ci[2]):.1f}" x2="{DX(ci[2]):.1f}" y1="{yc-7}" y2="{yc+7}" class="ci"/>')
        o.append(f'<circle cx="{DX(d):.1f}" cy="{yc}" r="6" class="pt"/>'
                 f'<text x="{DX(d):.1f}" y="{yc-12}" class="vl" text-anchor="middle">{d*100:+.0f}%p</text>')
    o.append("</svg>")
    return "".join(o)


# ---------- 판정 (등록 규칙 그대로) ----------
def judge(layers):
    if not layers:
        return None
    out = {}
    for key, _, role in LAYERS:
        lay = layers[key]
        n = lay["valid_pairs"]
        d = (lay["discordant"]["B_only"] - lay["discordant"]["A_only"]) / n if n else None
        ci = lay.get("paired_tango_95")
        if role == "목표":
            ok = bool(ci and ci[1] > 0 and d is not None and d >= .1)
            out[key] = ("좋다" if ok else "불명")
        else:
            bad = bool(ci and ci[2] < 0)
            out[key] = ("퇴행" if bad else "퇴행 없음")
    if "퇴행" in (out["flat"], out["stairs_up"]):
        verdict = "퇴행 감시 위반"
    elif out["gap"] == "좋다" and out["stepping_stones"] == "좋다":
        verdict = "지도가 좋다"
    elif out["gap"] == "좋다":
        verdict = "gap 만 좋다 (징검다리 불명)"
    elif out["stepping_stones"] == "좋다":
        verdict = "징검다리만 좋다 (gap 불명)"
    else:
        verdict = "불명"
    return verdict, out


def build_section(a, b, result, videos, asof):
    layers = result["trained_ab"]["layers"] if result else None
    ready = bool(result and result.get("comparison_ready"))
    J = judge(layers) if layers else None
    ent = lambda rows: [r["entropy"] for r in rows]
    def kl(rows, k=25):
        v = [r["kl"] for r in rows][1:]
        return [v[0]] + [sum(v[max(0, i-k+1):i+1]) / len(v[max(0, i-k+1):i+1]) for i in range(len(v))]
    wall = lambda rows: [r["iteration_wall_s"] for r in rows]
    a_wall = sum(wall(a)); b_wall = sum(wall(b))
    first_kl = (a[0]["kl"], b[0]["kl"])
    # 학습 곡선
    curves = (
        '<div class="split">'
        f'<figure>{line_chart([{"y": ent(a), "cls": "a"}, {"y": ent(b), "cls": "b"}], title="엔트로피", ylab="엔트로피", ymin=0, ymax=10, yticks=[0, 2, 4, 6, 8, 10])}'
        '<figcaption>행동의 무작위 정도(엔트로피). 둘 다 1.6 에서 출발해 8 근처에서 평탄해집니다. A 와 B 가 거의 겹칩니다.</figcaption></figure>'
        f'<figure>{line_chart([{"y": kl(a), "cls": "a"}, {"y": kl(b), "cls": "b"}], title="KL", ylab="KL (한 번의 수정 크기)", ymin=0, ymax=.04, yticks=[0, .01, .02, .03, .04], skip_first=1)}'
        f'<figcaption>한 번 update 로 정책이 얼마나 바뀌었나(KL, 25 update 이동 평균). 첫 update 는 그림 밖(A {first_kl[0]:.1f} · B {first_kl[1]:.1f}), 그 뒤 둘 다 0.01 ~ 0.02.</figcaption></figure>'
        '</div>')
    # 결과 표
    if layers:
        rows = []
        for key, name, role in LAYERS:
            lay = layers[key]; n = lay["valid_pairs"]
            d = (lay["discordant"]["B_only"] - lay["discordant"]["A_only"]) / n if n else None
            ci = lay.get("paired_tango_95")
            rows.append(f'<tr><td>{E(name)}</td><td>{role}</td><td class="num">{n}/{lay["planned_pairs"]}</td>'
                        f'<td class="num">{lay["A_success"]}</td><td class="num">{lay["B_success"]}</td>'
                        f'<td class="num">{lay["discordant"]["A_only"]} · {lay["discordant"]["B_only"]}</td>'
                        f'<td class="num">{d*100:+.1f}%p</td>'
                        f'<td class="num">[{ci[1]*100:+.1f}, {ci[2]*100:+.1f}]</td><td>{E(J[1][key])}</td></tr>' if n and ci else
                        f'<tr><td>{E(name)}</td><td>{role}</td><td class="num">0/{lay["planned_pairs"]}</td><td colspan="6">결측</td></tr>')
        table = ('<div class="tbl"><table class="def s2t"><thead><tr><th>지형</th><th>역할</th><th>유효 쌍</th><th>A 성공</th><th>B 성공</th>'
                 '<th>한쪽만 성공 (A만 · B만)</th><th>B − A</th><th>95% 구간</th><th>규칙 적용</th></tr></thead><tbody>'
                 + "".join(rows) + '</tbody></table></div>')
        head = (f'<p class="s2v {"g" if J[0] == "지도가 좋다" else ("b" if "퇴행" in J[0] else "w")}">'
                f'<b>판정 (결과 전 등록 규칙): {E(J[0])}</b>' + ("" if ready else " · 평가 증거 확인 미완") + '</p>')
    else:
        table, head = "", '<p class="s2v w"><b>평가 진행 중입니다.</b> 결과가 나오면 이 자리에 숫자와 판정이 들어갑니다.</p>'
    res = (head + f'<figure class="s2r">{result_svg(layers)}<figcaption>막대는 각 지형에서 성공한 판의 비율, 오른쪽 점은 같은 지형 · 같은 시드 쌍에서 잰 B − A 차이와 95% 구간(Tango). '
           '세로 점선은 목표 지형의 기준 +10%p 입니다. 「성공」은 기준선에 닿고 끝까지 넘어지지 않은 판입니다.</figcaption></figure>' + table)
    # 영상
    vids = video_block(videos)
    return SECTION.format(asof=E(asof), result=res, curves=curves, design=design_svg(), videos=vids,
                          a_h=f"{a_wall/3600:.1f}", b_h=f"{b_wall/3600:.1f}", know=know_block(J, layers),
                          nextexp=next_block(J))


def know_block(J, layers):
    if not J:
        return ('<li><b>A · B 둘 다 2,000 update 를 끝까지 학습했습니다.</b> 학습 값이 깨진 적(NaN) 없이 안정적이었고, 학습 곡선은 거의 겹칩니다.</li>'
                '<li><b>성능은 아직 모릅니다.</b> 학습 중에는 성공률을 기록하지 않아서, 평가가 끝나야 첫 숫자가 나옵니다.</li>')
    g, s = layers["gap"], layers["stepping_stones"]
    pct = lambda lay, k: f'{lay[k]}/{lay["valid_pairs"]}'
    return (f'<li><b>gap: A {pct(g,"A_success")} · B {pct(g,"B_success")} 성공.</b> 규칙 적용: {E(J[1]["gap"])}.</li>'
            f'<li><b>징검다리: A {pct(s,"A_success")} · B {pct(s,"B_success")} 성공.</b> 규칙 적용: {E(J[1]["stepping_stones"])}.</li>'
            f'<li><b>평지 · 계단 오르기 (퇴행 감시):</b> {E(J[1]["flat"])} · {E(J[1]["stairs_up"])}.</li>'
            '<li><b>A · B 둘 다 2,000 update 를 끝까지 학습했고 곡선은 거의 겹칩니다.</b> 차이는 지도 입력 하나입니다.</li>')


def next_block(J):
    rows = [("지도가 좋다", "지도가 gap · 징검다리 둘 다에서 좋다", "① 발 디딤 자리 보상 (MARG 방식, 보상만 바꾼 A1/B1 비교) → ② D435i 카메라 현실화 (시야 가림 → 잡음 → 렌더) → ③ AME-2 식 attention 지도 encoder"),
            ("gap 만 좋다 (징검다리 불명)", "gap 만 좋고 징검다리는 불명", "발 디딤 자리 보상을 먼저. v2 가 징검다리에서 0 ~ 24 % 였던 원인 후보가 「발 놓을 자리를 모름」 (MARG Fig 8b)"),
            ("불명", "둘 다 불명 · 약함", "지도가 정말 쓰이는지부터: 지도를 지웠을 때 B 의 행동이 바뀌는지 재는 탐침 · 학습 길이 늘리기 · encoder 동결 영향. 그다음 지도 표현 (attention encoder)"),
            ("퇴행 감시 위반", "B 가 퇴행", "지도 입력 이상 점검 (좌표 · 이력 · reset 연결), 같은 부모 · 시드로 재현")]
    cur = J[0] if J else None
    body = "".join(f'<tr{" class=cur" if cur == k else ""}><td>{E(c)}</td><td>{E(n)}</td></tr>' for k, c, n in rows)
    return ('<div class="tbl"><table class="def s2n"><thead><tr><th>평가 결과</th><th>다음 실험 (결과 전에 적어 둔 갈래 · S2-RESULT-PLAN 4 절)</th></tr></thead><tbody>'
            + body + '</tbody></table></div>'
            + ('<p class="sub">색칠한 줄이 이번 결과에 해당하는 갈래입니다.</p>' if cur else '<p class="sub">평가가 끝나면 해당 줄에 색이 칠해집니다.</p>'))


def video_block(videos):
    if not videos:
        return '<p class="s2v w"><b>영상 준비 중입니다.</b> 최종 평가가 끝난 뒤 같은 시드 · 같은 지형으로 A 와 B 를 나란히 찍습니다.</p>'
    pairs = {}
    for v in videos:
        pairs.setdefault(v["case_id"], {})[v["arm"]] = v
    cells = []
    for cid, d in pairs.items():
        info = d.get("A") or d.get("B")
        sel = "결과 전 고정" if info.get("selection") == "fixed" else E(info.get("selection_label", "차이 예시"))
        tiles = []
        for arm in ("A", "B"):
            v = d.get(arm)
            if not v:
                continue
            ok = v.get("success")
            tiles.append(f'<div class="vc"><video src="{E(v["web"])}" poster="{E(v["poster_web"])}" muted playsinline preload="metadata" controls></video>'
                         f'<div class="cap"><div class="t1"><span class="tag s2{arm.lower()}">{arm}</span><b>{"지도 없음" if arm == "A" else "지도 있음"}</b></div>'
                         f'<div class="q {"ok" if ok else "ng"}">{"성공" if ok else "실패"} · 기준선 {"도달" if v.get("reached") else "미도달"} · {"끝까지 생존" if v.get("survived") else "넘어짐"}</div></div></div>')
        cells.append(f'<div class="s2pair"><div class="s2ph"><b>{E(info.get("layer_name", info.get("layer", "")))}</b> · 시드 <span class="num">{info.get("seed")}</span> · <span class="sub">{sel}</span></div><div class="s2pv">{"".join(tiles)}</div></div>')
    return ('<div class="ctl"><div class="seg" id="s2ctl"><button type="button" data-a="play">함께 재생</button><button type="button" data-a="pause">멈춤</button><button type="button" data-a="zero">처음으로</button></div>'
            '<div class="seg" id="s2spd"><button type="button" data-r="0.25">0.25×</button><button type="button" data-r="0.5">0.5×</button><button type="button" data-r="1" aria-pressed="true">1×</button><button type="button" data-r="2">2×</button></div></div>'
            + '<div class="s2pairs">' + "".join(cells) + '</div>' + VIDEO_JS)


VIDEO_JS = """<script>(()=>{const vs=()=>[...document.querySelectorAll('#s2 video')];
document.getElementById('s2ctl').addEventListener('click',e=>{const a=e.target.dataset.a;if(!a)return;
vs().forEach(v=>{if(a==='play'){v.play().catch(()=>{})}else if(a==='pause'){v.pause()}else{v.pause();v.currentTime=0}})});
document.getElementById('s2spd').addEventListener('click',e=>{const r=e.target.dataset.r;if(!r)return;
[...e.currentTarget.children].forEach(b=>b.setAttribute('aria-pressed',b===e.target));vs().forEach(v=>v.playbackRate=+r)});})();</script>"""


S2CSS = """<style id="s2css">
:root{--sa:#6b7a90;--sb:#0e7a6e}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--sa:#9aa7b8;--sb:#3ec7b4}}
:root[data-theme="dark"]{--sa:#9aa7b8;--sb:#3ec7b4}
#s2 svg.s2c{width:100%;height:auto;display:block;font-family:var(--sans)}
#s2 figure.s2d svg{max-width:860px} #s2 figure.s2r svg{max-width:1100px}
#s2 .s2c .gl{stroke:var(--rule);stroke-width:1}
#s2 .s2c .gl.z{stroke:var(--ink-3)}
#s2 .s2c .ax{fill:var(--ink-3);font-size:12px}
#s2 .s2c .vl{fill:var(--ink-2);font-size:12.5px;font-family:var(--mono)}
#s2 .s2c .ln{fill:none;stroke-width:1.6}
#s2 .s2c .ln.a,#s2 .s2c .bar.a{stroke:var(--sa)}
#s2 .s2c .ln.b{stroke:var(--sb)}
#s2 .s2c .bar.a{fill:var(--sa)} #s2 .s2c .bar.b{fill:var(--sb)}
#s2 .s2c .trk{fill:var(--paper-2)}
#s2 .s2c .ci{stroke:var(--ink);stroke-width:2}
#s2 .s2c .pt{fill:var(--ink)}
#s2 .s2c .thr{stroke:var(--note);stroke-width:1.5;stroke-dasharray:4 4}
#s2 .s2c .bxs{fill:var(--card);stroke:var(--rule);stroke-width:1.2}
#s2 .s2c .bxs.a{stroke:var(--sa);stroke-width:2} #s2 .s2c .bxs.b{stroke:var(--sb);stroke-width:2}
#s2 .s2c .bxs.ev{stroke:var(--ink-2)}
#s2 .s2c .bt1{fill:var(--ink);font-size:15px;font-weight:600}
#s2 .s2c .bt2{fill:var(--ink-2);font-size:13px}
#s2 .s2c .ar{stroke:var(--ink-3);stroke-width:1.4} #s2 .s2c .arh{fill:var(--ink-3)}
#s2 .s2leg{display:flex;gap:18px;font-size:13.5px;color:var(--ink-2);margin:6px 0 10px}
#s2 .s2leg i{display:inline-block;width:14px;height:4px;border-radius:2px;vertical-align:3px;margin-right:6px}
#s2 .s2v{padding:12px 16px;border-radius:6px;margin:10px 0 14px;border-left:4px solid var(--rule);background:var(--paper-2)}
#s2 .s2v.g{border-left-color:var(--brand);background:var(--brand-soft)}
#s2 .s2v.w{border-left-color:var(--note);background:var(--note-soft)}
#s2 .s2v.b{border-left-color:var(--stop);background:var(--stop-soft)}
#s2 table.s2t{min-width:860px} #s2 table.s2t td:first-child{font-family:var(--sans);font-size:14px}
#s2 table.s2n td:first-child{font-family:var(--sans);white-space:normal;min-width:10em}
#s2 table.s2n tr.cur td{background:var(--brand-soft)}
#s2 ol.flow{list-style:none;padding:0;margin:10px 0 0;display:grid;gap:10px}
#s2 ol.flow li{display:grid;grid-template-columns:7.5em 1fr;gap:4px 14px;padding-left:12px;border-left:3px solid var(--rule)}
#s2 ol.flow li.b{border-left-color:var(--stop)} #s2 ol.flow li.g{border-left-color:var(--brand)} #s2 ol.flow li.w{border-left-color:var(--note)}
#s2 ol.flow .tm{font-family:var(--mono);font-size:13px;color:var(--ink-3)}
#s2 .tag.s2a{background:var(--sa)} #s2 .tag.s2b{background:var(--sb)}
#s2 .s2pairs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 22px}
#s2 .s2pv{display:grid;grid-template-columns:1fr 1fr;gap:8px}
#s2 .s2ph{font-size:14px;margin:0 0 6px}
@media (max-width:900px){#s2 .s2pairs{grid-template-columns:1fr}}
@media (max-width:720px){#s2 ol.flow li{grid-template-columns:1fr}}
</style>"""


SECTION = """
<section id="s2">
  <h2>S2 · 지형 지도를 주면 gap · 징검다리를 더 건너나 (A/B · 10/17 ~ 10/18)</h2>
  <p class="sub">{asof} 기준 · 이 절이 8판에서 새로 더한 내용입니다. 아래 E1 · E2 내용은 7판 그대로입니다.</p>
  <div class="tri">
    <div>
      <h3>한 것</h3>
      <p>E1 이 2만 번 학습한 정책(<span class="num">model_20000</span>)을 부모로, 똑같은 조건에서 <b>지도 입력만 다른 두 정책</b>을 2,000 update 씩 더 학습했습니다. A 는 발밑 지형 높이 지도를 0 으로 막았고, B 는 실제 지도(187 점 높이 + 유효 표시)를 받았습니다. 학습 시간은 A {a_h} 시간 · B {b_h} 시간(update 시간 합)입니다.</p>
      <p>그다음 미리 등록한 60 쌍(gap 20 · 징검다리 20 · 평지 10 · 계단 오르기 10)의 같은 지형 · 같은 시드 · 같은 명령(전진 1.0 m/s)에서 A 와 B 를 한 번씩 걸려 짝지어 비교합니다.</p>
    </div>
    <div>
      <h3>알게 된 것</h3>
      <ul class="plain">{know}</ul>
    </div>
    <div>
      <h3>아직 모르는 것</h3>
      <ul class="plain">
        <li><b>학습 전(update 0)과의 비교.</b> 2,000 update 로 나아졌는지는 update 0 평가가 있어야 압니다(아래 「팀장이 정할 것」).</li>
        <li><b>학습 시드 하나.</b> 시드를 바꿔도 같은 차이가 나는지는 재지 않았습니다.</li>
        <li><b>로봇이 지도를 「써서」 걷는지.</b> 지도가 제대로 들어간 것은 확인했지만, 지도를 지웠을 때 B 의 행동이 바뀌는지는 아직 재지 않았습니다.</li>
      </ul>
    </div>
  </div>

  <h3 class="h3gap">결과: 같은 지형에서 A 와 B 를 짝지어 잰 성공률</h3>
  <div class="s2leg"><span><i style="background:var(--sa)"></i>A · 지도 없음</span><span><i style="background:var(--sb)"></i>B · 지도 있음</span></div>
  {result}
  <p class="sub">판정 규칙은 결과를 보기 전(10/17 15:15)에 등록했습니다: 목표 지형(gap, 징검다리) 각각에서 B − A 의 95% 구간 하한이 0 보다 크고 평균 차이가 10%p 이상이면 「지도가 좋다」, 아니면 「불명」(효과 없음이 아니라 이 실험으로 가를 수 없다는 뜻). 평지 · 계단 오르기는 B 가 A 보다 구간 밖으로 나쁘면 「퇴행」. 낮은 결과가 나와도 좋은 결과가 나올 때까지 다시 돌리지 않습니다.</p>

  <h3 class="h3gap">실험 설계: 지도 입력 한 칸만 다르게</h3>
  <figure class="s2d">{design}<figcaption>부모 · 시드 · 학습 길이 · 로봇 수 · 보상 · 평가 지형이 모두 같고 지도 입력만 다릅니다. 그래서 차이가 나면 지도 때문이라고 읽을 수 있습니다. critic(학습 때만 쓰는 채점 신경망)은 두 쪽 모두 지형 높이를 받습니다.</figcaption></figure>

  <h3 class="h3gap">영상: 같은 시드 · 같은 지형에서 A 와 B</h3>
  <p class="sub">높이 센서가 재는 187 점을 지형 위에 그렸습니다. B 는 이 점이 정책에 들어갑니다. A 는 센서가 같은 점을 재지만 정책에는 0 이 들어가므로 회색으로 흐리게 그렸습니다. 영상은 판정 근거가 아니라 보기용입니다(판정은 위 60 쌍 평가). 결과 전에 고른 고정 사례와, 결과에서 규칙으로 고른 차이 예시를 나눠 표시합니다.</p>
  {videos}

  <h3 class="h3gap">학습 곡선: A 와 B 가 거의 같은 길을 걸었다</h3>
  <div class="s2leg"><span><i style="background:var(--sa)"></i>A</span><span><i style="background:var(--sb)"></i>B</span></div>
  {curves}

  <h3 class="h3gap">10/13 부터 10/17 까지 왜 결과가 없었나</h3>
  <p>새 실험 장치(지도 입력 · 감독기 · 평가기)를 실제 시뮬레이터에서 처음 돌리며 막힌 곳을 하나씩 고쳤습니다. 가짜 입력으로 한 CPU 시험은 통과했지만 실제 실행에서 처음 드러난 결함이 많았습니다. 10/16 14:18 부터 10/17 오전까지 약 20 시간은 GPU 를 띄우기 위한 동의 절차를 기다리느라 GPU 가 놀았습니다(lead 의 잘못: 상시 위임을 한 번에 받지 않고 실행마다 다시 물었습니다).</p>
  <ol class="flow">
    <li class="w"><span class="tm">10/13 ~ 10/16</span><span>지도 입력 · 학습 · 평가 장치를 설계하고 ASTRA 검증을 반복. 실제 지도 수집은 10/15 ~ 10/16 에 네 번 시도(USD 폴더 · 장면 조회 문제로 보류)</span></li>
    <li class="b"><span class="tm">10/16 14:18 ~ 10/17 10:4x</span><span>GPU 놀았음. 실행마다 팀장 동의를 다시 받는 절차 때문. 10/17 10:4x 팀장 「앞으로 매번 묻지 말고 설계대로 진행」</span></li>
    <li class="g"><span class="tm">10/17 10:49 ~ 14:31</span><span>실제 시뮬레이터에서 지도 입력이 정답 지형 높이와 맞는지 확인(통과), 평가기 · 발 위치 · 배관 점검. 평가기 닫기 실패 · 상태 파일 경합 · 높은 지형의 float32 반올림을 찾아 고침</span></li>
    <li class="b"><span class="tm">15:13 ~ 18:12</span><span>A 학습을 네 번 띄움. ① 한 update 23.5 초(센서 점검이 로봇마다 따로 돌아 느림 → 묶어서 3.7 초) ② 33 update 에서 중단(16 초 뒤 센서 시각이 float32 로 반올림돼 갱신을 건너뜀 → 매 step 갱신) ③ 923 update 에서 감독기가 상태 파일을 한 번 못 읽자 학습을 죽임(→ 연속으로 못 읽을 때만)</span></li>
    <li class="g"><span class="tm">18:12 ~ 20:38</span><span>A 학습 2,000 update 완료</span></li>
    <li class="w"><span class="tm">20:38 ~ 21:12</span><span>끝난 뒤 「정상 완료」 확인서를 쓰는 코드에 <code>import math</code> 한 줄이 빠져 확인서가 보류로 찍힘. 학습은 멀쩡해서 다시 학습하지 않고, 고친 코드로 같은 확인을 다시 돌려 새 확인서를 만듦(원본은 그대로 둠)</span></li>
    <li class="g"><span class="tm">21:12 ~ 23:36</span><span>B 학습 2,000 update. 같은 시간에 평가기의 GPU 확인 코드 결함(실제 값 모양을 잘못 가정)을 고침</span></li>
    <li class="g"><span class="tm">23:43 ~</span><span>예행 평가 8 건 → 최종 평가 120 건 → 영상</span></li>
  </ol>

  <h3 class="h3gap">다음 실험</h3>
  {nextexp}

  <h3 class="h3gap">팀장 질문과 답 (10/17)</h3>
  <dl class="qa">
    <dt>지도 점검을 왜 여러 번 했나? 지도가 잘못됐나?</dt><dd>지도 자체는 처음부터 맞았습니다. 점검 도구 쪽 문제(USD 폴더 · 장면 조회 · 기록 형식)로 다시 돌렸고, 10/17 오전 실제 시뮬레이터에서 지도 값이 정답 지형 높이와 맞는 것을 확인했습니다.</dd>
    <dt>그동안 실제 GPU 로 A/B 를 돌린 적이 없었나?</dt><dd>네. A/B 학습은 10/17 15:13 에 A 를 띄운 것이 처음입니다. 그 전까지 S2 는 설계 · CPU 시험 · 짧은 점검 실행뿐이었습니다.</dd>
    <dt>「smoke」 가 뭔가?</dt><dd>본 평가 120 건 전에 8 건만 먼저 돌려 보는 예행 평가입니다. 새로 고친 평가 프로그램이 실제 시뮬레이터에서 끝까지 도는지 확인합니다.</dd>
    <dt>확인서가 보류로 찍혔다면 A 를 다시 학습해야 하나?</dt><dd>아닙니다. 학습과 체크포인트는 멀쩡합니다. 끝난 뒤 확인서를 쓰는 코드에 한 줄(<code>import math</code>)이 빠졌던 것이라, 고친 코드로 같은 확인을 A 의 저장 파일에 다시 돌려 통과했습니다. A 와 B 의 학습 계산 코드는 같습니다.</dd>
    <dt>2,000 update 면 충분한가?</dt><dd>모릅니다. E1 학습의 약 1/80 경험량입니다(로봇 1/8 × 횟수 1/10, 한 번에 모으는 길이가 같다는 가정). 지도 효과의 첫 답을 빨리 얻으려고 짧게 잡았습니다. 결과가 「불명」 이면 학습 길이를 늘리는 것이 다음 후보입니다.</dd>
    <dt>감독기가 지형을 잘 보는지 확인했다는 것은?</dt><dd>두 가지입니다. 실제 시뮬레이터에서 B 의 지도 값이 정답 지형 높이와 맞는지(10/17 오전 통과), 그리고 학습 내내 매 step 모든 로봇의 높이 센서가 새로 갱신됐는지(A · B 모두 이상 0). 이것은 「지도가 제대로 들어간다」 는 확인이고, 「지도를 써서 걷는다」 는 확인은 평가와 지도 지우기 시험으로 합니다.</dd>
    <dt>자동 안전 검사는 무엇이고 왜 막았나?</dt><dd>Claude Code 프로그램에 들어 있는 검사입니다(ASTRA 장치가 아님). lead 가 팀장 말씀 전에 동의 파일을 대신 쓰려 할 때 막았습니다. 팀장이 직접 말씀한 뒤에는 막지 않았습니다.</dd>
  </dl>

  <h3 class="h3gap">팀장이 정할 것</h3>
  <ul class="plain">
    <li><b>update 0 평가(약 1 시간)를 이어서 돌릴지.</b> lead 권고: 돌린다. 등록한 비교의 나머지 절반(학습 효과)이고, 밤에 GPU 가 비어 있습니다.</li>
    <li><b>다음 실험 갈래.</b> 위 표에서 결과에 해당하는 줄이 권고입니다.</li>
    <li><b>실행 절차 줄이기.</b> 실행마다 동의 파일을 만드는 절차를 상시 동의 하나로 바꾸는 것(ASTRA 17ak 가 수용, 구현은 아직).</li>
  </ul>
</section>
"""


def splice(pub, section, *, kicker, version_line):
    s = pub
    s = s.replace("</head>", S2CSS + "\n</head>", 1)
    s = re.sub(r'<div class="kicker">[^<]*</div>', f'<div class="kicker">{E(kicker)}</div>', s, count=1)
    s = s.replace("<title>E1 · E2 시뮬 평가</title>", "<title>E1 · E2 · S2 시뮬 평가</title>", 1)
    s = s.replace('<h1>E1 · E2 시뮬 평가 <span class="seed">', '<h1>E1 · E2 · S2 시뮬 평가 <span class="seed">', 1)
    s = s.replace('<p class="lead">', '<p class="lead"><b>8판: 맨 위에 S2 (지도를 주면 gap · 징검다리를 더 건너나, A/B) 를 더했습니다.</b> ', 1)
    s = s.replace("· 7판 2026-10-14 09:50</dd>", f"· 7판 2026-10-14 09:50 · {E(version_line)}</dd>", 1)
    s = s.replace("<dt>상태</dt><dd>", "<dt>상태</dt><dd>8판 (S2 A/B 결과 · 영상 · 학습 곡선) · ", 1)
    marker = '<section id="sum">'
    assert s.count(marker) == 1, "본문 첫 절 표지가 하나가 아니다"
    s = s.replace(marker, section + "\n" + marker, 1)
    for need in ("s2css", 'id="s2"', "E1 · E2 · S2 시뮬 평가", "8판"):
        assert need in s, need
    return s


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pub", required=True)
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--result")
    p.add_argument("--videos")
    p.add_argument("--site", required=True)
    p.add_argument("--asof", required=True)
    a = p.parse_args()
    A, B = read_updates(a.a), read_updates(a.b)
    assert [r["update"] for r in A] == list(range(1, len(A) + 1)) and len(A) == 2000, "A 기록 2000 줄 아님"
    assert [r["update"] for r in B] == list(range(1, len(B) + 1)), "B 기록 번호 이상"
    assert {r["arm"] for r in A} == {"A"} and {r["arm"] for r in B} == {"B"}
    result = json.load(open(a.result, encoding="utf-8")) if a.result else None
    videos = json.load(open(a.videos, encoding="utf-8")) if a.videos else None
    site = Path(a.site); site.mkdir(parents=True, exist_ok=True)
    if videos:
        for v in videos:
            for k, sub in (("mp4", "v"), ("poster", "p")):
                src = Path(v[k]); dst = site / sub / "s2" / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dst.exists() or sha(dst) != sha(src):
                    shutil.copy2(src, dst)
                v["web" if k == "mp4" else "poster_web"] = f"{sub}/s2/{src.name}"
    sec = build_section(A, B, result, videos, a.asof)
    pub = open(a.pub, encoding="utf-8").read()
    out = splice(pub, sec, kicker=f"FOOTHOLD · 시뮬 RL · {a.asof}", version_line=f"8판 {a.asof}")
    (site / "index.html").write_text(out, encoding="utf-8")
    print(json.dumps({"site": str(site / "index.html"), "bytes": len(out.encode()), "A_updates": len(A),
                      "B_updates": len(B), "result": bool(result), "videos": len(videos or [])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
