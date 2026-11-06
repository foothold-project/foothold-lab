"""Curriculum lineage v2 (11/07): EX-41 as it actually ran (m6001~m12000) + EX-42 plan.

What changed from v1 (make_lineage.py, 11/03):
- EX-41 stage spans and DR come from the run's own boundary ledger
  (ex41_application.jsonl, 26 rows), not from the plan. The plan yaml is the one
  the relaunch actually loaded (ex41-launch-2b01df9a, D181: T0' up to 1500, 6000 cap).
- Result rows per stage end come from tool outputs saved in data-v2/
  (boundary_report.py text and the D179 push-ladder reader), never typed by hand.
- 06 is new: EX-42 plan. Numbers there are analyst v5 proposals unless marked decided.
v1 files are kept untouched.
"""
import hashlib
import json
import re
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_lineage as v1  # noqa: E402  (v1 helpers, EX-40 columns, WHY and STEPS text)

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

RUN = Path("C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522")
LEDGER = RUN / "main/EX-41-B-main_20261104_235522/ex41_application.jsonl"
YAML41 = Path("D:/mai-wt/foothold-lab/ex41-launch-2b01df9a/foothold_s2/curriculum/ex41-fixed5000.yaml")
YAML41_SHA = "75b55225ed01114b"
DATA = HERE / "data-v2"
SCORES_TXT = DATA / "ex41-stage-end-boundary-report.txt"
STAGE_END = {"S2a": 750, "S2b": 2750, "S2c": 3750, "S2d": 5000, "S2e": 5500, "T0′": 6000}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


assert sha(YAML41).startswith(YAML41_SHA), "EX-41 yaml is not the one the relaunch loaded"
ex41 = yaml.safe_load(YAML41.read_text(encoding="utf-8"))
ROWS41 = {("T0′" if s["id"] == "T0_prime" else s["id"]): s for s in ex41["stages"]}

# ---------------------------------------------------------------- actual ledger
LED = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
assert len(LED) == 26 and LED[-1]["iteration"] == 6001
PTS = [(r["iteration"] if r["iteration"] > 1 else 0, r["after"]["dr"]["scale"]) for r in LED if r["iteration"] != 1]
PTS.append((6000, LED[-1]["after"]["dr"]["scale"]))
STAGE_OF = [(r["iteration"], "T0′" if r["after"]["stage_id"] == "T0_prime" else r["after"]["stage_id"], r["reason"]) for r in LED]
for r in LED:  # what the plan held fixed must really have stayed fixed
    assert r["after"]["reward_weights"]["swing"] == -10.0 and r["after"]["critic_mirror"] is False


def dr_actual(t):
    for (a, x), (b, y) in zip(PTS, PTS[1:]):
        if t <= b:
            return x + (y - x) * (t - a) / (b - a) if b > a else y
    return PTS[-1][1]


spans = {}
for it, st, _ in STAGE_OF:
    lo = 0 if it <= 1 else it
    a, b = spans.get(st, (lo, lo))
    spans[st] = (min(a, lo), max(b, min(it + 249, 6000)))
assert [spans[k] for k in STAGE_END] == [(0, 750), (751, 2750), (2751, 3750), (3751, 5000), (5001, 5500), (5501, 6000)], spans

COLS = [c for c in v1.COLS if c["exp"] == "EX-40"]
for sid, (a, b) in spans.items():
    COLS.append(dict(id=sid, exp="EX-41", a=6000 + a + (1 if a == 0 else 0), b=6000 + b, la=a, lb=b,
                     row=ROWS41[sid], dr=(dr_actual(a), dr_actual(b))))
PUSH_VMAX = dict(zip(["S2a", "S2b", "S2c", "S2d", "S2e", "T0′"], ex41["fixed_schedule"]["push_vmax_mps"]))
HOLDS = [(it, why) for it, _, why in STAGE_OF if why.startswith("dr_")]

# ---------------------------------------------------------------- stage-end results (tool output, parsed)
txt = SCORES_TXT.read_text(encoding="utf-8")
RES = {}
for block in txt.split("== EX-41 ")[1:]:
    n = int(block.split()[0])
    sid = next(k for k, v in STAGE_END.items() if v == n)
    mm = {m: int(re.search(rf"^M {m}\s+판정선 넘은 명령 (\d+)", block, re.M).group(1)) for m in ("eval_gt", "eval_pred", "probe_prop_only")}
    cmds = sorted(set(c for c in re.findall(r"\('(?:eval_gt|eval_pred|probe_prop_only)', '([^']+)'\), 0\.\d+", block.split("\n2 ")[1].split("\n")[0])))
    surv = int(re.search(r"^1 생존 최저 \([^)]*\) (\d+) /64", block, re.M).group(1))
    s = re.search(r"^6 대칭 S eval_gt: 평균 ([\d.]+) 최저 ([\d.]+) <0.8 (\d+)", block, re.M)
    RES[sid] = dict(over=mm, cmds=cmds, surv=surv, s_mean=float(s.group(1)), s_low=int(s.group(3)))


def d179(n):
    root = next(RUN.glob(f"eval/score-watch/model_{n}_*/stage_end_auxiliary_eval/push_ladder/push_ladder"), None)
    if root is None:
        return None
    out = {}
    for t in ("flat", "random_rough", "pyramid_stairs"):
        worst = 1.0
        for m in ("eval_gt", "eval_pred", "probe_prop_only"):
            p = next(root.glob(f"*_{t}_{m}_walk_1.5/push_ladder.json"))
            cells = [c for c in json.loads(p.read_text(encoding="utf-8"))["cells"] if abs(c["magnitude_mps"] - 1.5) < 1e-6]
            worst = min(worst, min((c["pre_push_alive_envs"] - c["post_push_fallen_envs"]) / c["pre_push_alive_envs"] for c in cells))
        out[t] = worst
    return out


D179 = {sid: d179(n) for sid, n in STAGE_END.items()}
assert D179["S2d"] and abs(D179["S2d"]["pyramid_stairs"] - 62 / 64) < 1e-9  # m5000 logged 0.969 (cross-check)


def res_over(c):
    if c["exp"] == "EX-40":
        return "05 그림 참고"
    r = RES[c["id"]]
    o = r["over"]
    return f"{o['eval_gt']} · {o['eval_pred']} · {o['probe_prop_only']}" + (f" ({', '.join(r['cmds'])})" if r["cmds"] else "")


def res_surv(c):
    return "-" if c["exp"] == "EX-40" else f"{RES[c['id']]['surv']}/64"


def res_push(c):
    if c["exp"] == "EX-40":
        return "-"
    d = D179[c["id"]]
    if d is None:
        return "밀기 판정 대기 (748)"
    ok = all(v >= 0.9 for v in d.values())
    return f"{'통과' if ok else '미달'} · {d['flat']:.2f} · {d['random_rough']:.2f} · {d['pyramid_stairs']:.2f}"


def res_sym(c):
    if c["exp"] == "EX-40":
        return "-"
    r = RES[c["id"]]
    return f"{r['s_mean']:.2f} · 0.8 미만 {r['s_low']}"


def hold_actual(c):
    if c["exp"] == "EX-40":
        return "-"
    if c["id"] == "S2b":
        a = HOLDS[0][0]
        b = next(it for it, why in HOLDS if why == "dr_resume_same_slope")
        return f"증거 누락 유지 {a}~{b - 1} (+1000 회)"
    if c["id"] == "S2e":
        return "+500 연장 안 씀"
    if c["id"] == "T0′":
        return "500 회 (D181 최대 1500)"
    return "없음 (계획대로)"


ROWS = [r for r in v1.ROWS if r[0] != "DR 유지 · 연장"]
ROWS = [(n, f) for n, f in ROWS]
ROWS[0] = ("회차 (누적)", lambda c: f"m{c['a']}~m{c['b']}")
ROWS[2] = ("길이", lambda c: f"{c['b'] - c['a'] + 1} 회")
ROWS[[n for n, _ in ROWS].index("DR 배율")] = ("DR 배율 (실제 경계 기록)", v1.dr_txt)
ROWS[[n for n, _ in ROWS].index("밀기")] = ("밀기", lambda c: v1.push_txt(c) if c["exp"] == "EX-40"
                                         else f"원 표집 크기 U[0, {PUSH_VMAX[c['id']]:.2f}] m/s × 방향 360°")
ROWS[[n for n, _ in ROWS].index("자동 조정 (실행 중 켜진 것)")] = ("자동 조정 (실제로 켜진 것)",
    lambda c: "-" if c["exp"] == "EX-40" else ("DR 유지 (증거 누락)" if c["id"] == "S2b" else "없음"))
RESULT_ROWS = [("DR 유지 · 연장 (실제)", hold_actual),
               ("결과: 단계 끝 0.15 넘은 칸 (정답 · 복원 · 끔)", res_over),
               ("결과: 단계 끝 생존 최저", res_surv),
               ("결과: 밀기 1.5 m/s 최약 방향 (평지 · 거친 · 계단)", res_push),
               ("결과: 좌우 대칭 S 정답 평균 · 0.8 미만 칸", res_sym)]
ALL_ROWS = ROWS + RESULT_ROWS
GRID = [[fn(c) for c in COLS] for _, fn in ALL_ROWS]
STATE = []
for r, vals in enumerate(GRID):
    name = ALL_ROWS[r][0]
    st = []
    for i, v in enumerate(vals):
        if name.startswith("결과") or name.startswith("DR 유지") or name.startswith("자동 조정"):
            st.append(6 if COLS[i]["exp"] == "EX-41" else 4)
        elif i == 0 or name.startswith("회차") or name == "길이":
            st.append(0 if i == 0 else 4)
        else:
            prev = vals[i - 1]
            st.append(1 if v == prev else (3 if prev in ("-", "0", "없음", "0 (끔)") else 2))
    STATE.append(st)
COLORS = dict(v1.COLORS)
COLORS[6] = "#e8f5e9"


def result_color(name, txt):
    if "미달" in txt or (name.startswith("결과: 단계 끝 0.15") and not txt.startswith("0 · 0 · 0")):
        return "#ffcdd2" if "미달" in txt else "#fff3e0"
    return "#e8f5e9"


def table_png(path):
    W = [3.9] + [2.95] * len(COLS)
    H = 0.5
    fig_w = sum(W) + 0.6
    fig_h = H * (len(ALL_ROWS) + 3) + 2.6
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_w)
    ax.set_ylim(fig_h, 0)
    ax.axis("off")
    ax.text(0.3, 0.45, "커리큘럼 계보 표 v2 · EX-40 m0~m6000 → EX-41 실제 실행 로컬 0~6000 (누적 m6001~m12000)",
            fontsize=22, weight="bold", va="center")
    ax.text(0.3, 0.95, f"원자료: ex40.yaml sha {v1.EX40_SHA[:8]} · ex41-fixed5000.yaml sha {YAML41_SHA[:8]} (2b01df9a, 실제 기동판) · "
            f"단계 구간 · DR 은 경계 기록 ex41_application.jsonl 26 줄 · 결과 줄은 boundary_report.py · 밀기 사다리 원자료",
            fontsize=12, va="center", color="#37474f")
    lx = 0.3
    for st, label in [(1, "앞 단계에서 이어짐"), (2, "이 단계에서 바뀜"), (3, "이 단계에서 새로 생김"),
                      (5, "같은 규칙의 램프가 계속 오름"), (6, "실측 결과 (초록 통과 · 주황 0.15 넘은 칸 있음 · 빨강 미달)")]:
        ax.add_patch(Rectangle((lx, 1.25), 0.45, 0.32, facecolor=COLORS[st], edgecolor="#90a4ae"))
        ax.text(lx + 0.55, 1.41, label, fontsize=12, va="center")
        lx += 3.4 if st != 5 else 4.0
    y0 = 1.85
    x = 0.3
    ax.add_patch(Rectangle((x, y0), W[0], H * 1.6, facecolor="#263238"))
    ax.text(x + 0.1, y0 + H * 0.8, "항목", color="white", fontsize=13, weight="bold", va="center")
    x += W[0]
    for i, c in enumerate(COLS):
        col = "#37474f" if c["exp"] == "EX-40" else "#4a148c"
        ax.add_patch(Rectangle((x, y0), W[i + 1], H * 1.6, facecolor=col, edgecolor="white"))
        ax.text(x + W[i + 1] / 2, y0 + H * 0.55, f"{c['exp']} {c['id']}", color="white", fontsize=14, weight="bold", ha="center", va="center")
        ax.text(x + W[i + 1] / 2, y0 + H * 1.15, f"m{c['a']}~m{c['b']}", color="#e0e0e0", fontsize=11, ha="center", va="center")
        x += W[i + 1]
    y = y0 + H * 1.6
    for r, (name, _) in enumerate(ALL_ROWS):
        x = 0.3
        is_res = name.startswith("결과") or name.startswith("DR 유지")
        ax.add_patch(Rectangle((x, y), W[0], H, facecolor="#e8eaf6" if is_res else "#f5f5f5", edgecolor="#cfd8dc"))
        ax.text(x + 0.1, y + H / 2, name, fontsize=11 if len(name) < 24 else 10, va="center", weight="bold")
        x += W[0]
        for i, c in enumerate(COLS):
            t = GRID[r][i]
            fc = COLORS[STATE[r][i]]
            if STATE[r][i] == 6 and name.startswith("결과"):
                fc = result_color(name, t)
            ax.add_patch(Rectangle((x, y), W[i + 1], H, facecolor=fc, edgecolor="#cfd8dc"))
            fsz = 11 if len(t) <= 24 else 10
            if len(t) > 30:
                cut = t.rfind(" ", 0, len(t) // 2 + 6)
                t = t[:cut] + "\n" + t[cut + 1:] if cut > 0 else t
                fsz = 9.6
            ax.text(x + W[i + 1] / 2, y + H / 2, t, fontsize=fsz, ha="center", va="center", linespacing=1.0)
            x += W[i + 1]
        y += H
    xd = 0.3 + W[0] + sum(W[1:7])
    ax.plot([xd, xd], [y0, y], color="#d50000", lw=3)
    ax.text(xd + 0.05, y + 0.25, "← EX-40 (처음부터 m0)   |   EX-41 (m6000 이어 받기, 실제 실행) →", fontsize=12, color="#d50000", va="center")
    ax.text(0.3, y + 0.7, "계획(v1 표)과 다른 점: S2b 에서 DR 이 증거 누락으로 1251~2250 동안 0.575 에 머물러(자동 유지 장치) 뒤 단계가 1000 회씩 밀렸다. "
            "T0′ 는 6000 에서 끝(팀장 결정). 보상 가중 · 대칭은 끝까지 그대로.", fontsize=11.5, color="#37474f", va="center")
    ax.text(0.3, y + 1.1, "결과 줄 읽는 법: 0.15 는 경계 보고의 기록선(생존 판정과 다름) · 밀기는 걷는 중 1.5 m/s 로 8 방향 밀어 가장 나쁜 방향 생존(지도 셋 중 최저) · "
            "0.9 이상이면 통과(D179).", fontsize=11.5, color="#37474f", va="center")
    fig.savefig(path, dpi=100)
    plt.close(fig)


def timeline_png(path):
    fig = plt.figure(figsize=(28, 15), dpi=100)
    gs = fig.add_gridspec(5, 1, height_ratios=[0.5, 2.2, 1.6, 1.3, 1.5], hspace=0.12, left=0.06, right=0.94, top=0.93, bottom=0.05)
    fig.suptitle("EX-40 m0 → m6000 → EX-41 m12000 (실제 실행): 무엇이 언제 바뀌었나 · v2", fontsize=26, weight="bold", x=0.06, ha="left")
    X1 = 12600
    axes = [fig.add_subplot(gs[i]) for i in range(5)]
    for a in axes[1:]:
        a.sharex(axes[0])
    ax = axes[0]
    for c in COLS:
        col = "#546e7a" if c["exp"] == "EX-40" else "#6a1b9a"
        n = c["b"] - c["a"] + 1
        ax.add_patch(Rectangle((c["a"], 0), n, 1, facecolor=col, edgecolor="white", lw=2))
        ax.text(c["a"] + n / 2, 0.5, c["id"], color="white", ha="center", va="center", fontsize=15, weight="bold")
    ax.add_patch(Rectangle((12001, 0), 599, 1, facecolor="#e1bee7", edgecolor="white", hatch="//"))
    ax.text(12300, 0.5, "EX-42 →\n(06 그림)", ha="center", va="center", fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xlim(0, X1)
    ax.tick_params(labelbottom=False)
    ax = axes[1]
    xs = list(range(0, 6001, 10))
    ax.plot(xs, [v1.ex40_dr(u) for u in xs], color="#1565c0", lw=3, label="DR 배율 (EX-40 계획 직선 · EX-41 은 경계 기록)")
    ax.plot([6000 + u for u in xs], [dr_actual(u) for u in xs], color="#1565c0", lw=3)
    ax.plot([6000 + u for u in xs], [v1.ex41_dr(u) if u <= 5000 else 1.0 for u in xs], color="#90caf9", lw=2, ls=":",
            label="EX-41 계획 DR (v1 그림) · 실제와 비교용")
    ax.set_ylabel("DR 배율", fontsize=14, color="#1565c0")
    ax.set_ylim(-0.05, 1.15)
    a0 = 6000 + HOLDS[0][0]
    a1 = 6000 + next(it for it, why in HOLDS if why == "dr_resume_same_slope")
    ax.axvspan(a0, a1, color="#ffe082", alpha=0.45)
    ax.text((a0 + a1) / 2, 0.02, "DR 유지\n(증거 누락)\n로컬 1251~2250", ha="center", fontsize=11.5, color="#e65100")
    ax2 = ax.twinx()
    ax2.plot(xs, [v1.ex40_dr(u) for u in xs], color="#c62828", lw=2.5, ls="--", label="밀기 EX-40: 상자 표집 축마다 ±(1.0 × DR) m/s")
    px, py = [], []
    for c in COLS[6:]:
        px += [c["a"], c["b"]]
        py += [PUSH_VMAX[c["id"]]] * 2
    ax2.plot(px, py, color="#c62828", lw=3, label="밀기 EX-41: 원 표집 크기 최대 Vmax")
    ax2.set_ylim(-0.1, 2.3)
    ax2.set_ylabel("밀기 최대 m/s", fontsize=14, color="#c62828")
    for c in COLS[6:]:
        v = PUSH_VMAX[c["id"]]
        ax2.text((c["a"] + c["b"]) / 2, v + 0.08, f"{v:g}", color="#c62828", ha="center", fontsize=13, weight="bold")
        ax.text((c["a"] + c["b"]) / 2, (c["dr"][0] + c["dr"][1]) / 2 - 0.17, "DR " + v1.dr_txt(c), color="#1565c0", ha="center",
                fontsize=12, bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1))
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=12, framealpha=0.95)
    ax.grid(alpha=0.25)
    ax.tick_params(labelbottom=False)
    ax = axes[2]
    keys = [("reverse_vx", 0, "후진 vx 하한", "#6d4c41"), ("spin_wz_abs", 0, "회전 |wz| 하한", "#00838f"),
            ("spin_wz_abs", 1, "회전 |wz| 상한", "#00695c"), ("walk_wz_abs", 1, "걸으며 돌기 |wz| 상한", "#f9a825"),
            ("side_vy_abs", 1, "옆 |vy| 상한", "#7b1fa2"), ("forward_vx", 0, "전진 vx 하한", "#2e7d32")]
    for key, j, lab, col in keys:
        xx, yy = [], []
        for c in COLS:
            r = c["row"]["ranges"].get(key)
            if r is not None:
                xx += [c["a"], c["b"]]
                yy += [r[j]] * 2
        ax.plot(xx, yy, color=col, lw=3, label=lab)
    ax.axhline(0, color="#9e9e9e", lw=0.8)
    ax.set_ylabel("명령 범위 m/s · rad/s", fontsize=14)
    ax.legend(loc="lower right", fontsize=11, ncol=3, framealpha=0.95)
    ax.set_ylim(-1.5, 1.8)
    ax.grid(alpha=0.25)
    ax.tick_params(labelbottom=False)
    ax = axes[3]
    groups = [("전진", ["forward"], "#43a047"), ("제자리 회전", ["spin_left", "spin_right"], "#00acc1"),
              ("정지", ["stand"], "#9e9e9e"), ("걸으며 돌기", ["walk_left", "walk_right"], "#fdd835"),
              ("후진", ["reverse"], "#8d6e63"), ("옆", ["side_left", "side_right"], "#8e24aa"),
              ("대각 앞", ["diag_fwd_left", "diag_fwd_right"], "#f06292"), ("대각 뒤", ["diag_back_left", "diag_back_right"], "#c2185b")]
    for c in COLS:
        base = 0
        n = c["b"] - c["a"] + 1
        for name, ks, col in groups:
            v = sum(c["row"]["shares"].get(k, 0) for k in ks)
            if v:
                ax.add_patch(Rectangle((c["a"], base), n, v, facecolor=col, edgecolor="white", lw=0.6))
                if v >= 0.06:
                    ax.text(c["a"] + n / 2, base + v / 2, f"{v * 100:g}", ha="center", va="center", fontsize=10)
            base += v
    for name, ks, col in groups:
        ax.add_patch(Rectangle((0, 0), 0, 0, facecolor=col, label=name))
    ax.set_ylim(0, 1)
    ax.set_ylabel("명령 몫 (%)", fontsize=14)
    ax.legend(loc="upper left", bbox_to_anchor=(1.005, 1.0), fontsize=10, ncol=1, title="명령 몫 (%)")
    ax.tick_params(labelbottom=False)
    ax = axes[4]
    for name, yv in [("지형", 3), ("지도", 2), ("보상 · 대칭", 1), ("단계 끝 결과", 0)]:
        ax.text(-150, yv + 0.5, name, ha="right", va="center", fontsize=13, weight="bold")

    def bar(a, b, yv, t, col):
        ax.add_patch(Rectangle((a, yv + 0.1), b - a, 0.8, facecolor=col, edgecolor="white"))
        ax.text((a + b) / 2, yv + 0.5, t, ha="center", va="center", fontsize=11)
    s2d, t0 = COLS[9], COLS[11]
    bar(0, s2d["a"] - 1, 3, "L0~2 고정 (EX-40 · EX-41 S2a~S2c)", "#cfd8dc")
    bar(s2d["a"], 12000, 3, "성과 승급 상한 L5 (S2d~T0′)", "#ffcc80")
    bar(0, t0["a"] - 1, 2, "정답 지도 강제 force_gt · 지도 끔 10 %", "#cfd8dc")
    bar(t0["a"], 12000, 2, "T0′ 복원", "#90caf9")
    bar(0, 1500, 1, "B0 8 항 · lin_vel_z -2", "#eceff1")
    bar(1501, 3000, 1, "lin_vel_z -2 → 0", "#fff3e0")
    bar(3001, 6000, 1, "lin_vel_z 0 · 걸림 -1 · 대칭 끔", "#eceff1")
    bar(6001, 12000, 1, "걸림 -2 · 스윙 -10 · 회전0 L1 -0.5 (끝까지 그대로) · 대칭 끔 유지(감시기 켜짐 조건 안 옴)", "#ffcc80")
    bar(0, 6000, 0, "EX-40: 250 회 26 칸 그림자 판정 (05 그림)", "#eceff1")
    for c in COLS[6:]:
        p = res_push(c)
        col = "#ffcdd2" if "미달" in p else ("#fff9c4" if "대기" in p else "#c8e6c9")
        o = RES[c["id"]]["over"]
        word = "미달" if "미달" in p else ("대기" if "대기" in p else "통과")
        bar(c["a"], c["b"], 0, f"{word}\n{o['eval_gt']}·{o['eval_pred']}·{o['probe_prop_only']}", col)
    ax.set_ylim(0, 4)
    ax.set_yticks([])
    ax.set_xlim(0, X1)
    ticks = [0, 1500, 3000, 4500, 6000, 6750, 8750, 9750, 11000, 11500, 12000]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"m{t}" for t in ticks], fontsize=11)
    ax.set_xlabel("누적 회차 (EX-41 로컬 n = 누적 - 6000)  ·  단계 끝 결과 칸: 위 = 밀기 1.5 m/s 판정(D179) · 아래 = 0.15 넘은 칸 수 (정답 · 복원 · 끔) · T0′ 밀기 판정은 대기 중", fontsize=13)
    for a in axes:
        a.axvline(6000, color="#d50000", lw=2.5)
        a.axvline(12000, color="#ef6c00", lw=2)
    axes[0].text(6000, 1.12, "m6000 = EX-41 부모 (DR 0.5)", color="#d50000", fontsize=13, ha="center", weight="bold", transform=axes[0].get_xaxis_transform())
    axes[0].text(12000, 1.12, "m12000 = EX-41 끝 · EX-42 부모", color="#ef6c00", fontsize=13, ha="center", weight="bold", transform=axes[0].get_xaxis_transform())
    fig.savefig(path, dpi=100)
    plt.close(fig)


# ---------------------------------------------------------------- 06 EX-42 plan
# Source: D:/mai-tmp/analyst/PLAN-ex42-terrain-blocks-1106.md v5 §0.4 (E stage rows read from
# CURRICULUM-GATES.md 187~195, sha 0db658ef) and §8.1 (L level sizes, CPU generated mid-row values).
# DECIDED = lead's chat decisions recorded in decisions.tsv 11/06 19:5x ~ 11/07 00:2x.
PLAN42 = Path("D:/mai-tmp/analyst/PLAN-ex42-terrain-blocks-1106.md")
CANON_ROWS = Path("D:/mai-tmp/analyst/w38-v5-evidence/canonical-duration-rows.json")
E_V5 = [("E1", 1750, "익숙한 연속 지형 · 명령 과제 · 상한 L5→L9 경계마다 +1"), ("E1F", 750, "깃발 목표 추종 · 정지 · 재출발"),
        ("E2", 1500, "쉬운 새 발 놓기 하나(넓은 징검돌 · 평균대 · 작은 틈 L0 중 하나)"), ("E3", 2250, "종류별 치수 · 불규칙성 +1 · 다음 쉬운 종류"),
        ("E4", 2000, "고난도 종류(climb · gap · stones · beam …)"), ("E5", 1500, "혼합 · 방향 일반화"),
        ("M", 500, "지도 끔 보완(조건부 · 어디서나)"), ("E6a", 1000, "자세 명령 값(몸 높이 · roll) 열기"),
        ("E6b", 2000, "지형 2 판(high_ledge 0.3→0.6 · wall · crawl)")]
STAIR_MID = {5: 0.149, 6: 0.167, 7: 0.185, 8: 0.203, 9: 0.221}  # v5 §8.1 table (CPU 생성 중간값)
SLOPE_MID = {5: 12.41, 6: 14.57, 7: 16.70, 8: 18.78, 9: 20.81}


def plan42_png(path):
    rows = {r["stage"]: r for r in json.loads(CANON_ROWS.read_text(encoding="utf-8"))["rows"]}
    assert sum(r["base"] for r in rows.values()) == 13250 and sum(b for _, b, _ in E_V5) == 13250
    assert all(rows[k]["base"] == b for k, b, _ in E_V5 if k not in ("E1", "E3"))  # v5 moves 750 E3 -> E1
    assert rows["E1"]["base"] + rows["E3"]["base"] == 1750 + 2250
    plan = PLAN42.read_text(encoding="utf-8")
    for needle in ("| 합계 · 앞 지형 배치 | **20,000** |", "| 합계 · 미션 배치 | **20,000** |", "| 전체 | **40,000** |",
                   "| 0 | 0.059 |", "| 9 | 0.221 |"):
        assert needle in plan, needle
    fig = plt.figure(figsize=(28, 17), dpi=100)
    fig.suptitle("EX-42 커리큘럼 계획 · m12000 (EX-41 끝) 에서 지형 40,000 회 · v5 (11/07)", fontsize=26, weight="bold", x=0.04, ha="left")
    fig.text(0.04, 0.935, "실선 테두리 = 팀장 결정 · 점선 테두리 = analyst v5 제안(팀장 결정 대기) · 회차는 완료 PPO 갱신 · 시간 27.8 초/회 가정이면 40,000 회 약 309 시간(Linux · 두 GPU 미측)",
             fontsize=13, color="#37474f")
    # --- (a) whole budget band
    ax = fig.add_axes([0.04, 0.79, 0.92, 0.11])
    ax.set_xlim(-4400, 40000)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def box(a, w, y, h, t, fc, dashed=False, fs=12, tc="black"):
        ax.add_patch(Rectangle((a, y), w, h, facecolor=fc, edgecolor="#37474f", lw=1.6, ls="--" if dashed else "-"))
        ax.text(a + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, color=tc)
    box(-4300, 2600, 0.15, 0.7, "0 단계 T0′ 보완\n1,000 회\n(40,000 밖)", "#bbdefb", fs=11)
    box(-1600, 1400, 0.15, 0.7, "E0 250\n(밖)", "#e3f2fd", fs=11)
    ax.text(-2900, 0.03, "앞 두 칸 너비는 회차 비례 아님", fontsize=9.5, color="#546e7a", ha="center")
    for k in range(4):
        terrain = k < 2
        box(k * 10000, 10000, 0.15, 0.7, f"블록 B{k + 1} · {k * 10000 + 1:,}~{(k + 1) * 10000:,}\n"
            + ("지형 적응 (기본 순서)" if terrain else "어려운 미션 (기본 순서)") + "\n끝에서 분석 · 학습은 멈추지 않음",
            "#c8e6c9" if terrain else "#ffe0b2", fs=13)
    ax.text(20000, 0.98, "20,000 = 기본 순서의 경계일 뿐 · 결과가 좋으면 미션을 앞당기고 부족하면 늦춤 · 미션은 한 번에 하나 (팀장 11/06 22:1x)",
            ha="center", va="top", fontsize=12.5, color="#bf360c", weight="bold")
    # --- (b) first 20,000 reservation (v5 proposal)
    ax = fig.add_axes([0.04, 0.60, 0.92, 0.16])
    ax.set_xlim(-4400, 40000)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(-2500, 0.93, "지형 20,000 회 예약 (v5 제안)", fontsize=14, weight="bold", va="top")
    x = 0
    pal = ["#a5d6a7", "#81c784", "#66bb6a", "#4caf50", "#43a047", "#388e3c", "#90caf9", "#2e7d32", "#1b5e20"]
    for (sid, n, desc), col in zip(E_V5, pal):
        box(x, n, 0.38, 0.4, f"{sid}\n{n:,}", col, dashed=True, fs=11, tc="white" if col in ("#388e3c", "#2e7d32", "#1b5e20") else "black")
        x += n
    for n, t, col in [(3000, "연장 공용\n3,000", "#fff9c4"), (2000, "미달 재도전\n2,000", "#ffecb3"), (1750, "회복 · 전환\n1,750", "#ffe0b2")]:
        box(x, n, 0.38, 0.4, t, col, dashed=True, fs=11)
        x += n
    assert x == 20000
    ax.text(0, 0.30, "E 단계 첫 시도 13,250 = 정본 기본 합(E0 제외) · v5 는 E3 의 레벨 몫 750 을 E1 로 옮김\n단계마다 최소 · 최대 체류(시간 상자) · 미달이면 보류(deferred) 후 선행이 갖춰진 다른 과제로",
            fontsize=11.5, va="top")
    x = 20000
    for i, (n, t) in enumerate([(2000, "① 외다리 ·\n평행봉"), (2000, "② ㄹ 자\n좁은 길 회전"), (2000, "③ 작은 도약\n→ 넓은 틈"),
                                (2000, "④ 높은 턱"), (2000, "⑤ 큰 단차\n내려오기"), (2000, "⑥ 낮은 천장\n기어가기")]):
        box(x, n, 0.38, 0.4, t, "#ffcc80", dashed=True, fs=10.5)
        x += n
    for n, t in [(6000, "미션 재도전 6,000 (각 최대 1,000 · 한 번)"), (2000, "회복 2,000")]:
        box(x, n, 0.38, 0.4, t, "#ffe0b2", dashed=True, fs=11)
        x += n
    assert x == 40000
    ax.text(20000, 0.93, "미션 20,000 회 예약 (v5 제안 · 슬롯은 예시 · 준비 안 되면 비워 두고 선행 연습)", fontsize=14, weight="bold", va="top")
    ax.text(20300, 0.30, "몸통 · 배 · 머리 접촉 금지(결정) · 무릎은 실측 뒤 정함\n평행봉 · ㄹ 자 형상은 팀장 그림 필요(U06 · U07) · 큰 점프는 실기 위험이 커서 뒤로",
            fontsize=11.5, va="top")
    # --- (c) E1 ladder
    ax = fig.add_axes([0.06, 0.31, 0.38, 0.24])
    lv = list(STAIR_MID)
    ax.step([4.5] + lv, [STAIR_MID[5]] + [STAIR_MID[k] for k in lv], where="post", color="#2e7d32", lw=3, label="계단 단 높이 m (중간값)")
    ax.set_xticks(lv)
    ax.set_xticklabels([f"L{k}" for k in lv], fontsize=12)
    ax.set_ylabel("계단 단 높이 m", fontsize=13, color="#2e7d32")
    for k in lv:
        ax.text(k, STAIR_MID[k] + 0.004, f"{STAIR_MID[k]:.3f}", ha="center", fontsize=11, color="#2e7d32")
    ax2 = ax.twinx()
    ax2.plot(lv, [SLOPE_MID[k] for k in lv], color="#6a1b9a", marker="o", lw=2, label="경사 ° (중간값)")
    ax2.set_ylabel("경사 °", fontsize=13, color="#6a1b9a")
    ax.set_title("E1 첫 변경 (결정): 같은 지형 종류에서 상한 L5 → L9 · 경계마다 +1 · 성과 · 유지 통과 때만", fontsize=13.5)
    ax.text(5.0, 0.212, "+1 당 계단 1.8 cm · 최소 체류 250 회\nEX-41 끝 상한 = L5", fontsize=11.5)
    ax.grid(alpha=0.3)
    # --- (d) decided vs proposed
    ax = fig.add_axes([0.50, 0.05, 0.46, 0.50])
    ax.axis("off")
    dec = ["목표 지형 40,000 회 · 20,000 먼저 확보 · 10,000 블록마다 분석 (W31 · 11/06 19:5x)",
           "0 단계 T0′ 보완 1,000 · E0 250 은 40,000 밖 (11/06 21:2x)",
           "E1 첫 변경 = 상한 L5 → L9, 경계마다 +1 (11/06 22:3x · 23:1x)",
           "블록 끝에서 학습을 멈추지 않음 · 합의 규칙 안이면 팀장 없이 이어 감 (11/06 22:1x)",
           "미션 시작은 결과로 · 한 번에 하나 · 몸통 · 배 · 머리 접촉 금지 (11/06 22:1x)",
           "EX-41 식 회차 시계 뼈대 + 단계마다 최소 · 최대 체류 (11/07 00:1x)",
           "250 경계마다 빠르게 판단 · 유지 / 올림 / 보상 조정 (11/07 00:2x)",
           "Linux 두 GPU 묶음 실측 뒤 결정 (W43 · 11/06 22:2x)"]
    pro = ["미달 = 보류(deferred) · 다음 줄 무조건 아님 · 선행 갖춘 과제로",
           "40,000 공용 예약표(위 두 띠) · 미션 상자 2,000 + 재도전 1,000 · 회복 500 + 500",
           "보상 후보 셋(swing · stumble · zero_yaw) 한 번 +10 % · 누적 1.25 배 · +250 · +500 확인 뒤 채택 / 원복",
           "점수 나온 뒤 30 분 안 판단 · lead · analyst 각자 읽고 대조",
           "값이 없는 12 개(U01~U12)는 실측으로 · 기준은 결과 전 등록"]
    y = 0.98
    ax.text(0, y, "팀장 결정", fontsize=16, weight="bold", color="#1b5e20", va="top")
    y -= 0.06
    for t in dec:
        ax.text(0.01, y, "■ " + t, fontsize=12.3, va="top")
        y -= 0.052
    y -= 0.02
    ax.text(0, y, "analyst v5 제안 (팀장 결정 대기)", fontsize=16, weight="bold", color="#e65100", va="top")
    y -= 0.06
    for t in pro:
        ax.text(0.01, y, "□ " + t, fontsize=12.3, va="top")
        y -= 0.052
    ax.text(0, max(y - 0.02, 0.0), "근거: PLAN-ex42-terrain-blocks-1106.md v5 · CURRICULUM-GATES 187~195 · decisions.tsv", fontsize=10.5, color="#546e7a", va="top")
    # --- (e) mission families
    ax = fig.add_axes([0.06, 0.05, 0.38, 0.22])
    ax.axis("off")
    ax.text(0, 1.0, "미션을 능력 묶음으로 (목적: 사고 · 붕괴 현장 진입 · 팀장 11/06 22:1x)", fontsize=14, weight="bold", va="top")
    fam = [("A 정밀 발 놓기", "외다리 · 평행봉 · 징검돌 · 구멍 난 바닥 · 부서진 계단", "넓은 것은 지형 단계 안 · 좁은 것은 뒤"),
           ("D 불안정 지면", "미끄럼 · 흔들리는 판 · 움직이는 잔해 · 기울어진 슬래브", "지형 단계 안 후보"),
           ("C 몸 낮추기", "낮은 천장 기어가기 · 좁은 틈", "A 다음"),
           ("B 힘 · 도약", "틈 점프 · 높은 턱 · 경사 사이 틈 오르내리기", "실기 위험이 커서 뒤"),
           ("E 회복", "넘어진 뒤 일어나기 · 막다른 곳 후진", "별도 판단")]
    y = 0.84
    for a_, b_, c_ in fam:
        ax.text(0.0, y, a_, fontsize=12.5, weight="bold", va="top")
        ax.text(0.22, y, b_, fontsize=12, va="top")
        ax.text(0.78, y, c_, fontsize=11.5, va="top", color="#6a1b9a")
        y -= 0.16
    fig.savefig(path, dpi=100)
    plt.close(fig)


if __name__ == "__main__":
    plan42_png(HERE / "06-ex42-plan-v2.png")
    table_png(HERE / "02-stage-table-v2.png")
    timeline_png(HERE / "01-timeline-v2.png")
    print("ok", {k: (v["over"], v["surv"]) for k, v in RES.items()})
    print("d179", {k: (None if v is None else {t: round(x, 3) for t, x in v.items()}) for k, v in D179.items()})
