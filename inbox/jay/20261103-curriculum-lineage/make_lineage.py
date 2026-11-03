"""EX-40 m0~m6000 -> EX-41 local 0~5000 curriculum lineage figures.

Stage shares / ranges / force_gt / terrain come from the two curriculum yaml
files (read at run time, sha256 checked). DR, push and delay follow the code
formulas cited next to each function. Hand-written text cells carry their
source in the canon markdown (CURRICULUM-LINEAGE.md).
"""
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import yaml

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

OUT = Path(__file__).resolve().parent
EX40_YAML = Path("C:/mai/wt/foothold-lab/analyst-ex40-main-verified-1031/foothold_s2/curriculum/ex40.yaml")
EX40_SHA = "66a519b28f5597ff41cec09f286d4cdd66af5d3877ecb1580005ca5a13a70585"
EX41_ROOT = Path("D:/mai-wt/foothold-lab/ex41-launch-2ee5dc00/foothold_s2/curriculum")
EX41_YAML = EX41_ROOT / "ex41-fixed5000.yaml"
LADDER = Path("D:/mai-tmp/runner/ex41_push_ladder_m6000_20261103_161418/push_ladder_bundle.json")
SCORE6000 = Path("C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/scores-b/score_6000_d5e9ec400f33.json")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


assert sha(EX40_YAML) == EX40_SHA, "EX-40 curriculum yaml differs from the launched one"
ex40 = yaml.safe_load(EX40_YAML.read_text(encoding="utf-8"))
ex41 = yaml.safe_load(EX41_YAML.read_text(encoding="utf-8"))
EX41_SHA = sha(EX41_YAML)

# ---------------------------------------------------------------- formulas
def ex40_dr(u):
    # ex40_dr.py:32-40 (analyst-ex40-main-verified-1031, 2df419b0)
    if u <= 1500:
        return 0.0
    if u <= 6000:
        return 0.5 * (u - 1501) / (6000 - 1501)
    return 1.0


fs = ex41["fixed_schedule"]
EX41_DUR = [s["duration"]["maximum_updates"] for s in ex41["stages"]]
EX41_POINTS = [(0, ex41["domain_randomization"]["scale"])]
_t = 0
for d, x in zip(EX41_DUR, fs["dr_stage_end_scales"]):
    _t += d
    EX41_POINTS.append((_t, x))


def ex41_dr(t):
    # ex41_fixed.py:156-162 Clock.scale (no pause)
    for (a, x), (b, y) in zip(EX41_POINTS, EX41_POINTS[1:]):
        if t <= b:
            return x + (y - x) * max(0, min(1, (t - a) / (b - a)))
    return EX41_POINTS[-1][1]


def delay_ms(scale):
    # ex40_dr.py:71-80: 15 ms * scale, floored to physics 5 ms steps
    sec = scale * 0.015
    return sec * 1000, math.floor(sec / 0.005 + 1e-9) * 5


# ---------------------------------------------------------------- stages
E40 = [s for s in ex40["stages"] if s["id"] in ("B0", "B1", "B2", "B3a", "B3b", "B3c")]
E40_END = {"B0": 1500, "B1": 3000, "B2": 4500, "B3a": 5000, "B3b": 5500, "B3c": 6000}
COLS = []
for s in E40:
    a = s["start"]["fixed_update"]
    b = E40_END[s["id"]]
    COLS.append(dict(id=s["id"], exp="EX-40", a=a, b=b, la=a, lb=b, row=s,
                     dr=(ex40_dr(max(a, 0)), ex40_dr(b))))
names41 = {"T0_prime": "T0′"}
t = 0
for s, d in zip(ex41["stages"], EX41_DUR):
    COLS.append(dict(id=names41.get(s["id"], s["id"]), exp="EX-41", a=6000 + t + 1, b=6000 + t + d,
                     la=t + 1 if t else 0, lb=t + d, row=s, dr=(ex41_dr(t), ex41_dr(t + d))))
    t += d
assert t == fs["duration_updates"] == 5000
PUSH_VMAX = dict(zip([c["id"] for c in COLS[6:]], fs["push_vmax_mps"]))


def share(row, *keys):
    sh = row["shares"]
    v = sum(sh.get(k, 0) for k in keys)
    return "-" if v == 0 else f"{v * 100:g} %"


def rng(row, key, absd=False):
    r = row["ranges"].get(key)
    if r is None:
        return "-"
    if absd:
        return f"±[{r[0]:g}, {r[1]:g}]"
    return f"[{r[0]:g}, {r[1]:g}]"


def slots(row, exp):
    sh = row["shares"]
    groups = [("전진", ["forward"]), ("회전", ["spin_left"]), ("정지", ["stand"]),
              ("걸으며 돌기", ["walk_left"]), ("후진", ["reverse"]), ("옆", ["side_left"]),
              ("대각", ["diag_fwd_left"])]
    return " · ".join(n for n, k in groups if sh.get(k[0], 0) > 0)


def low_fwd(c):
    if c["exp"] == "EX-40":
        return f"{c['row'].get('low_forward_fraction', 0) * 100:g} %" if c["row"].get("low_forward_fraction") else "-"
    return "20 %"  # ex41.py:136 passes .20 for every EX-41 stage


def heading(c):
    return f"{(ex40 if c['exp'] == 'EX-40' else ex41)['heading']['forward_fraction'] * 100:g} %"


def dr_txt(c):
    a, b = c["dr"]
    if c["id"] == "B0":
        return "0 (끔)"
    return f"{a:.2f}" if abs(a - b) < 1e-9 else f"{a:.2f} → {b:.2f}"


def push_txt(c):
    if c["exp"] == "EX-40":
        a, b = c["dr"]
        if b == 0:
            return "없음"
        return f"상자 표집 축마다 ±{a:.2f} → ±{b:.2f} m/s"
    return f"원 표집 크기 U[0, {PUSH_VMAX[c['id']]:.2f}] m/s × 방향 360°"


def delay_txt(c):
    b = c["dr"][1]
    if b == 0:
        return "0"
    raw, q = delay_ms(b)
    return f"끝 {raw:.1f} ms → 실제 {q:g} ms"


def com_txt(c):
    b = c["dr"][1]
    if b == 0:
        return "0"
    return f"끝 COM ±{0.05 * b * 100:.1f} cm · 이득 · 모터 ±{0.1 * b * 100:.1f} %"


def terrain(c):
    if c["exp"] == "EX-40":
        return "L0~2 고정 (승급 끔)"
    tr = c["row"]["terrain"]
    return "L0~2 고정" if tr["policy"] == "fixed_l02" else f"성과 승급 · 상한 L{tr['level_cap']}"


def mapmode(c):
    if c["row"]["force_gt"]:
        return "정답 지도 강제 (force_gt) · 끔 10 %"
    return "복원 지도 소비 (force_gt 끔) · 끔 10 %"


def shift(c):
    if c["exp"] == "EX-40":
        return "회차 고정 · 성과는 그림자 기록"
    return "회차 고정 (일찍 넘김 없음)"


def rewards(c):
    if c["exp"] == "EX-40":
        if c["id"] == "B0":
            return "B0 8 항 · lin_vel_z -2 · 걸림 -1"
        if c["id"] == "B1":
            return "lin_vel_z -2 → 0 (1501~3000 직선)"
        return "lin_vel_z 0 · 걸림 -1"
    return "걸림 -2 · 스윙 -10 · 회전0 L1 -0.5 · lin_vel_z 0"


def prereg(c):
    return "-" if c["exp"] == "EX-40" else "무릎 · 관절 한계 · 체공 · 미끄럼 0 가중"


def pose(c):
    return "-" if c["exp"] == "EX-40" else "몸 높이 · roll 2 칸 (0 고정)"


def ppo(c):
    return "lr 1e-3 적응 · 엔트로피 0.01 · KL 0.01"


def mirror(c):
    if c["exp"] == "EX-40":
        return "끔 (symmetry_cfg null)"
    return "끔 · S 기록 · 승인 시 W72 로 켬"


def auto(c):
    if c["exp"] == "EX-40":
        return "-"
    return "서 있기 복원 · DR 유지 · +500 연장"


def gate(c):
    if c["exp"] == "EX-40":
        return "250 회 26 칸 그림자 (생존 ≥60/64 · 오차 ≤0.15)"
    if c["id"] == "T0′":
        return "250 회 39 숫자 · 단계 끝 축 전부 · 졸업 P7"
    return "250 회 39 숫자 + 좌우 S · 단계 끝 축 전부 · 밀기 1.5 ≥ 90 %"


def hold(c):
    if c["exp"] == "EX-40":
        return "-"
    if c["id"] in ("S2b", "S2c", "S2d"):
        return "DR 오를 때 26 칸 기준 -3/64 밑이면 유지 (총 +1000)"
    if c["id"] == "S2e":
        return "끝에서 +500 연장 한 번 판단"
    if c["id"] == "T0′":
        return "-"
    return "DR 그대로 (적응)"


ROWS = [
    ("회차 (누적)", lambda c: f"m{c['a']}~m{c['b']}"),
    ("회차 (그 실험 안)", lambda c: f"{c['la']}~{c['lb']}"),
    ("길이", lambda c: f"{c['b'] - c['a'] + (1 if c['a'] == 0 else 1)} 회" if c["a"] else "1501 회"),
    ("단계 넘김", shift),
    ("DR 배율", dr_txt),
    ("밀기", push_txt),
    ("밀기 간격", lambda c: "-" if c["dr"][1] == 0 else "10~15 s"),
    ("지연 상한", delay_txt),
    ("무게중심 · 이득 · 모터", com_txt),
    ("마찰 · 질량 (시작부터)", lambda c: "0.2~1.2 · -1~+3 kg"),
    ("관측 잡음", lambda c: "1 배 고정"),
    ("지형", terrain),
    ("지도 (정답 · 복원 · 끔)", mapmode),
    ("명령 종류", lambda c: slots(c["row"], c["exp"])),
    ("몫: 전진", lambda c: share(c["row"], "forward")),
    ("몫: 제자리 회전 좌+우", lambda c: share(c["row"], "spin_left", "spin_right")),
    ("몫: 정지", lambda c: share(c["row"], "stand")),
    ("몫: 걸으며 돌기 좌+우", lambda c: share(c["row"], "walk_left", "walk_right")),
    ("몫: 후진", lambda c: share(c["row"], "reverse")),
    ("몫: 옆 좌+우", lambda c: share(c["row"], "side_left", "side_right")),
    ("몫: 대각 앞 좌+우", lambda c: share(c["row"], "diag_fwd_left", "diag_fwd_right")),
    ("몫: 대각 뒤 좌+우", lambda c: share(c["row"], "diag_back_left", "diag_back_right")),
    ("범위: 전진 vx", lambda c: rng(c["row"], "forward_vx")),
    ("저속 전진 몫 (0.1~0.3)", low_fwd),
    ("범위: 후진 vx", lambda c: rng(c["row"], "reverse_vx")),
    ("범위: 옆 |vy|", lambda c: rng(c["row"], "side_vy_abs")),
    ("범위: 회전 |wz|", lambda c: rng(c["row"], "spin_wz_abs")),
    ("범위: 걸으며 돌기 vx", lambda c: rng(c["row"], "walk_vx")),
    ("범위: 걸으며 돌기 |wz|", lambda c: rng(c["row"], "walk_wz_abs")),
    ("범위: 대각 |vx| · |vy|", lambda c: "-" if "diag_vx_abs" not in c["row"]["ranges"] else
        f"{rng(c['row'], 'diag_vx_abs')} · {rng(c['row'], 'diag_vy_abs')}"),
    ("heading 직진 유지 몫", heading),
    ("보상 (바뀐 항)", rewards),
    ("미리 등록 보상 (0 가중)", prereg),
    ("자세 명령 입력", pose),
    ("PPO", ppo),
    ("좌우 대칭 (critic 거울)", mirror),
    ("자동 조정 (실행 중 켜진 것)", auto),
    ("평가 · 판정", gate),
    ("DR 유지 · 연장", hold),
]


def length(c):
    return c["b"] - c["a"] + 1


ROWS[2] = ("길이", lambda c: f"{length(c)} 회")

GRID = [[fn(c) for c in COLS] for _, fn in ROWS]

# change state: 0 start, 1 carried, 2 changed, 3 new
STATE = []
for r, vals in enumerate(GRID):
    st = []
    for i, v in enumerate(vals):
        if i == 0:
            st.append(0)
        elif ROWS[r][0].startswith("회차") or ROWS[r][0] == "길이":
            st.append(4)
        else:
            prev = vals[i - 1]
            if v == prev:
                st.append(1)
            elif prev in ("-", "0", "없음", "0 (끔)"):
                st.append(3)
            else:
                st.append(2)
    STATE.append(st)
# DR / push / delay / COM are continuous ramps; a ramp that keeps going is
# not a new decision. Mark "ramp continues" separately so the eye catches only
# real changes of rule.
RAMP_ROWS = {"DR 배율", "밀기", "지연 상한", "무게중심 · 이득 · 모터"}
RULE_CHANGE_AT = {"DR 배율": {"B1", "S2a"}, "밀기": {"B1", "S2a", "S2b", "S2c", "S2d"},
                  "지연 상한": {"B1"}, "무게중심 · 이득 · 모터": {"B1"}}
for r, (name, _) in enumerate(ROWS):
    if name in RAMP_ROWS:
        for i, c in enumerate(COLS):
            if i and STATE[r][i] in (2, 3) and c["id"] not in RULE_CHANGE_AT[name]:
                STATE[r][i] = 5

COLORS = {0: "#ffffff", 1: "#eceff1", 2: "#ffcc80", 3: "#90caf9", 4: "#ffffff", 5: "#fff3e0"}


def table_png(path):
    ncol = len(COLS) + 1
    W = [3.3] + [2.95] * len(COLS)
    H = 0.5
    fig_w = sum(W) + 0.6
    fig_h = H * (len(ROWS) + 3) + 2.4
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_w)
    ax.set_ylim(fig_h, 0)
    ax.axis("off")
    ax.text(0.3, 0.45, "커리큘럼 계보 표 · EX-40 m0~m6000 → EX-41 로컬 0~5000 (누적 m6001~m11000)",
            fontsize=22, weight="bold", va="center")
    ax.text(0.3, 0.95, f"원자료: ex40.yaml sha {EX40_SHA[:8]} · ex41-fixed5000.yaml sha {EX41_SHA[:8]} (2ee5dc00) · "
            "DR · 밀기 · 지연은 코드 공식(ex40_dr.py:32 · ex41_fixed.py:156 · ex41_fixed.py:236) · 값 등급: 표 안 숫자는 모두 「코드」(실행 설정)",
            fontsize=12, va="center", color="#37474f")
    # legend
    lx = 0.3
    for st, label in [(1, "앞 단계에서 이어짐"), (2, "이 단계에서 바뀜"), (3, "이 단계에서 새로 생김"),
                      (5, "같은 규칙의 램프가 계속 오름")]:
        ax.add_patch(Rectangle((lx, 1.25), 0.45, 0.32, facecolor=COLORS[st], edgecolor="#90a4ae"))
        ax.text(lx + 0.55, 1.41, label, fontsize=12, va="center")
        lx += 3.4
    y0 = 1.85
    # header
    x = 0.3
    ax.add_patch(Rectangle((x, y0), W[0], H * 1.6, facecolor="#263238"))
    ax.text(x + 0.1, y0 + H * 0.8, "항목", color="white", fontsize=13, weight="bold", va="center")
    x += W[0]
    for i, c in enumerate(COLS):
        col = "#37474f" if c["exp"] == "EX-40" else "#4a148c"
        ax.add_patch(Rectangle((x, y0), W[i + 1], H * 1.6, facecolor=col, edgecolor="white"))
        ax.text(x + W[i + 1] / 2, y0 + H * 0.55, f"{c['exp']} {c['id']}", color="white",
                fontsize=14, weight="bold", ha="center", va="center")
        ax.text(x + W[i + 1] / 2, y0 + H * 1.15, f"m{c['a']}~m{c['b']}", color="#e0e0e0",
                fontsize=11, ha="center", va="center")
        x += W[i + 1]
    y = y0 + H * 1.6
    for r, (name, _) in enumerate(ROWS):
        x = 0.3
        ax.add_patch(Rectangle((x, y), W[0], H, facecolor="#f5f5f5", edgecolor="#cfd8dc"))
        ax.text(x + 0.1, y + H / 2, name, fontsize=11.5, va="center", weight="bold")
        x += W[0]
        for i, c in enumerate(COLS):
            ax.add_patch(Rectangle((x, y), W[i + 1], H, facecolor=COLORS[STATE[r][i]], edgecolor="#cfd8dc"))
            txt = GRID[r][i]
            fsz = 11 if len(txt) <= 24 else 10
            if len(txt) > 30:
                # wrap once at the middle separator
                cut = txt.rfind(" ", 0, len(txt) // 2 + 6)
                txt = txt[:cut] + "\n" + txt[cut + 1:] if cut > 0 else txt
                fsz = 9.6
            ax.text(x + W[i + 1] / 2, y + H / 2, txt, fontsize=fsz, ha="center", va="center", linespacing=1.0)
            x += W[i + 1]
        y += H
    # divider between experiments
    xd = 0.3 + W[0] + sum(W[1:7])
    ax.plot([xd, xd], [y0, y], color="#d50000", lw=3)
    ax.text(xd + 0.05, y + 0.25, "← EX-40 (처음부터 m0)   |   EX-41 (m6000 이어 받기, 로컬 회차 0 부터) →",
            fontsize=12, color="#d50000", va="center")
    ax.text(0.3, y + 0.7, "EX-40 은 m6001~m7500 D(DR 1.0) · m7501~m8000 T0(복원 지도) 까지 갔지만, EX-41 부모는 m6000(DR 0.5 마지막 저장본, D124) 이다. "
            "그래서 이 표는 m6000 까지만 EX-40 을 싣는다.", fontsize=11.5, color="#37474f", va="center")
    fig.savefig(path, dpi=100)
    plt.close(fig)


# ---------------------------------------------------------------- timeline
def timeline_png(path):
    fig = plt.figure(figsize=(28, 15), dpi=100)
    gs = fig.add_gridspec(5, 1, height_ratios=[0.5, 2.2, 1.6, 1.3, 1.5], hspace=0.12,
                          left=0.06, right=0.94, top=0.93, bottom=0.05)
    fig.suptitle("EX-40 m0 → m6000 → EX-41 m11000 (로컬 5000): 무엇이 언제 바뀌었나", fontsize=26, weight="bold", x=0.06, ha="left")
    X1 = 12600
    axes = [fig.add_subplot(gs[i]) for i in range(5)]
    for a in axes[1:]:
        a.sharex(axes[0])
    # band row
    ax = axes[0]
    for c in COLS:
        col = "#546e7a" if c["exp"] == "EX-40" else "#6a1b9a"
        ax.add_patch(Rectangle((c["a"], 0), length(c), 1, facecolor=col, edgecolor="white", lw=2))
        ax.text(c["a"] + length(c) / 2, 0.5, c["id"], color="white", ha="center", va="center", fontsize=15, weight="bold")
    ax.add_patch(Rectangle((11001, 0), 1500, 1, facecolor="#e1bee7", edgecolor="white", hatch="//"))
    ax.text(11750, 0.5, "여유: DR 유지 최대 +1000\n+500 연장 한 번 (총 6500)", ha="center", va="center", fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xlim(0, X1)
    ax.tick_params(labelbottom=False)
    # DR + push
    ax = axes[1]
    xs = list(range(0, 6001, 10))
    ax.plot(xs, [ex40_dr(u) for u in xs], color="#1565c0", lw=3, label="DR 배율 (EX-40: B1 부터 0 → 0.5 직선)")
    xs2 = list(range(0, 5001, 10))
    ax.plot([6000 + u for u in xs2], [ex41_dr(u) for u in xs2], color="#1565c0", lw=3, ls="-")
    ax.set_ylabel("DR 배율", fontsize=14, color="#1565c0")
    ax.set_ylim(-0.05, 1.15)
    ax2 = ax.twinx()
    ax2.plot(xs, [ex40_dr(u) * 1.0 for u in xs], color="#c62828", lw=2.5, ls="--",
             label="밀기 EX-40: 상자 표집, 축마다 최대 ±(1.0 × DR) m/s")
    px, py = [], []
    for c in COLS[6:]:
        px += [c["a"], c["b"]]
        py += [PUSH_VMAX[c["id"]]] * 2
    ax2.plot(px, py, color="#c62828", lw=3, label="밀기 EX-41: 원 표집 크기 최대 Vmax (DR 과 뗌)")
    ax2.set_ylim(-0.1, 2.3)
    ax2.set_ylabel("밀기 최대 m/s", fontsize=14, color="#c62828")
    for c in COLS[6:]:
        v = PUSH_VMAX[c["id"]]
        ax2.text((c["a"] + c["b"]) / 2, v + 0.08, f"{v:.1f}" if v == int(v) else f"{v:g}", color="#c62828",
                 ha="center", fontsize=13, weight="bold")
    for c in COLS[6:]:
        ax.text((c["a"] + c["b"]) / 2, (c["dr"][0] + c["dr"][1]) / 2 - 0.16, "DR " + dr_txt(c), color="#1565c0", ha="center", fontsize=12,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1))
    ax.text(1600, 0.62, "EX-40: 밀기는 DR 배율에 묶여 m6000 에서 축마다 ±0.5 m/s (빨간 점선, 오른쪽 눈금)", fontsize=12, color="#c62828")
    ax.text(6100, 1.06, "EX-41 S2a: 부모 m6000 의 DR 0.5 를 그대로 750 회 적응 (D126)", fontsize=12, color="#1565c0")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=12, framealpha=0.95)
    ax.grid(alpha=0.25)
    ax.tick_params(labelbottom=False)
    # command ranges
    ax = axes[2]
    keys = [("reverse_vx", 0, "후진 vx 하한", "#6d4c41"), ("spin_wz_abs", 0, "회전 |wz| 하한", "#00838f"),
            ("spin_wz_abs", 1, "회전 |wz| 상한", "#00695c"), ("walk_wz_abs", 1, "걸으며 돌기 |wz| 상한", "#f9a825"),
            ("side_vy_abs", 1, "옆 |vy| 상한", "#7b1fa2"), ("forward_vx", 0, "전진 vx 하한", "#2e7d32")]
    for key, j, lab, col in keys:
        xx, yy = [], []
        for c in COLS:
            r = c["row"]["ranges"].get(key)
            if r is None:
                continue
            xx += [c["a"], c["b"]]
            yy += [r[j]] * 2
        ax.plot(xx, yy, color=col, lw=3, label=lab)
    ax.axhline(0, color="#9e9e9e", lw=0.8)
    ax.set_ylabel("명령 범위 m/s · rad/s", fontsize=14)
    ax.legend(loc="lower right", fontsize=11, ncol=3, framealpha=0.95)
    ax.text(6100, -1.2, "후진 -1.0 → -1.3 (D105)", fontsize=12, color="#6d4c41")
    ax.text(3050, 1.55, "B2: 회전 상한 1.2 → 1.5 · 후진 -1.0 · 옆 0.6 · 대각 생김", fontsize=11.5)
    ax.text(4520, 1.08, "B3a: 걸으며 돌기 |wz| 1.0", fontsize=11.5, color="#f9a825")
    ax.text(5020, 0.36, "B3b: 회전 하한 0.5→0.3", fontsize=11.5, color="#00838f")
    ax.text(4300, -0.28, "B3c: 전진 하한 0.3→0.1", fontsize=11.5, color="#2e7d32")
    ax.set_ylim(-1.5, 1.8)
    ax.grid(alpha=0.25)
    ax.tick_params(labelbottom=False)
    # shares stacked
    ax = axes[3]
    groups = [("전진", ["forward"], "#43a047"), ("제자리 회전", ["spin_left", "spin_right"], "#00acc1"),
              ("정지", ["stand"], "#9e9e9e"), ("걸으며 돌기", ["walk_left", "walk_right"], "#fdd835"),
              ("후진", ["reverse"], "#8d6e63"), ("옆", ["side_left", "side_right"], "#8e24aa"),
              ("대각 앞", ["diag_fwd_left", "diag_fwd_right"], "#f06292"),
              ("대각 뒤", ["diag_back_left", "diag_back_right"], "#c2185b")]
    for c in COLS:
        base = 0
        for name, ks, col in groups:
            v = sum(c["row"]["shares"].get(k, 0) for k in ks)
            if v:
                ax.add_patch(Rectangle((c["a"], base), length(c), v, facecolor=col, edgecolor="white", lw=0.6))
                if v >= 0.06:
                    ax.text(c["a"] + length(c) / 2, base + v / 2, f"{v * 100:g}", ha="center", va="center", fontsize=10)
            base += v
    for name, ks, col in groups:
        ax.add_patch(Rectangle((0, 0), 0, 0, facecolor=col, label=name))
    ax.set_ylim(0, 1)
    ax.set_ylabel("명령 몫 (%)", fontsize=14)
    ax.legend(loc="upper right", fontsize=10.5, ncol=2, title="명령 몫 (숫자 %)")
    ax.tick_params(labelbottom=False)
    # terrain / map / rules
    ax = axes[4]
    lanes = [("지형", 3), ("지도", 2), ("보상 · 대칭", 1), ("판정 · 자동", 0)]
    for name, yv in lanes:
        ax.text(-150, yv + 0.5, name, ha="right", va="center", fontsize=13, weight="bold")
    def bar(a, b, yv, txt, col):
        ax.add_patch(Rectangle((a, yv + 0.1), b - a, 0.8, facecolor=col, edgecolor="white"))
        ax.text((a + b) / 2, yv + 0.5, txt, ha="center", va="center", fontsize=11.5)
    bar(0, 8750, 3, "L0~2 고정 (EX-40 승급 끔 · EX-41 S2a~S2c 도 고정)", "#cfd8dc")
    bar(8751, 11000, 3, "성과 승급 상한 L5 (S2d~T0′)", "#ffcc80")
    bar(0, 10500, 2, "정답 지도 강제 force_gt · 지도 끔 10 % (p_map_off 0.1)", "#cfd8dc")
    bar(10501, 11000, 2, "T0′ 복원 지도", "#90caf9")
    bar(0, 1500, 1, "B0 8 항 · lin_vel_z -2", "#eceff1")
    bar(1501, 3000, 1, "lin_vel_z -2 → 0", "#fff3e0")
    bar(3001, 6000, 1, "lin_vel_z 0 · 걸림 -1 · 대칭 끔", "#eceff1")
    bar(6001, 11000, 1, "걸림 -2 · 스윙 -10 · 회전 0 명령 L1 -0.5 · 자세 명령 2 칸(0) · 대칭은 S 기록, 승인 시 켬", "#ffcc80")
    bar(0, 6000, 0, "250 회 26 칸 그림자 판정 (단계 넘김은 회차 고정)", "#eceff1")
    bar(6001, 11000, 0, "250 회 39 숫자 + 좌우 S · 단계 끝 축 전부 + 밀기 사다리 · DR 유지 안전장치 · 서 있기 복원 · +500 연장", "#ffcc80")
    ax.set_ylim(0, 4)
    ax.set_yticks([])
    ax.set_xlim(0, X1)
    ticks = [0, 1500, 3000, 4500, 5000, 5500, 6000, 6750, 7750, 8750, 10000, 10500, 11000, 12000, 12500]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"m{t}" for t in ticks], fontsize=11)
    ax.set_xlabel("누적 회차 (EX-41 로컬 n = 누적 - 6000)", fontsize=13)
    for a in axes:
        a.axvline(6000, color="#d50000", lw=2.5)
        a.axvline(12000, color="#ef6c00", lw=1.5, ls=":")
    axes[0].text(6000, 1.12, "m6000 = EX-41 부모 (DR 0.5)", color="#d50000", fontsize=13, ha="center", weight="bold",
                 transform=axes[0].get_xaxis_transform())
    axes[0].text(12000, 1.12, "팀장 희망 m12000 (로컬 6000) · 미정", color="#ef6c00", fontsize=12, ha="center",
                 transform=axes[0].get_xaxis_transform())
    fig.savefig(path, dpi=100)
    plt.close(fig)


# ---------------------------------------------------------------- why table
WHY = [
    # (항목, 이전 → 지금, 왜 (무엇을 극복), 근거 m6000 실측, 결정 · 출처, 등급)
    ("부모 · 시작", "EX-40 처음부터 m0 → EX-41 m6000 이어 받기",
     "B 단계 명령을 다 배운 DR 0.5 마지막 저장본에서 갈라 구간 2 를 붙인다. D96 의 m7500 안을 바꿈",
     "m6000 26 칸 모두 생존 ≥ 60/64 (오차 미달은 끔 back1.0 하나) · 정지 64/64", "D124 WORKLIST:152 · ex41-fixed5000.yaml:4-6", "코드 · 실측"),
    ("DR 배율", "m6000 에서 0.5 (전체 범위 못 감) → S2a 0.5 유지 · S2b~S2d 0.5→1.0",
     "EX-40 은 B 동안 0.5 까지만. 실기 편차(무게중심 · 모터 · 지연)를 1.0 까지 넓히되 갑자기 올리지 않음(적응 750 회 뒤 램프)",
     "m6000 DR 0.5 · 기울기는 B 단계의 1.35~1.44 배", "D124 · D126 WORKLIST:154 · ex41-fixed5000.yaml:445", "코드 · 가정"),
    ("DR 안전장치", "없음 → 26 칸이 m6000 기준 -3/64 밑이면 DR 유지, 2 경계 회복 뒤 같은 기울기 재개, 유지 총 1000",
     "DR 을 올리다 걷기가 무너지는 것을 막되 학습은 멈추지 않음",
     "기준 = m6000 점수 26 칸 (score_6000_d5e9ec40)", "D126 · D130 WORKLIST:158 · D133 · ex41_fixed.py:156-206", "코드 · 가정"),
    ("밀기", "DR 에 묶인 상자 표집 축마다 ±0.5 → 원 표집 크기 U[0, Vmax] · 1.5→1.65→1.8→2.0",
     "사람이 발로 차는 세기(1.5 m/s 이상으로 보임)를 m6000 이 못 버팀. 방향이 대각일 때만 세지는 상자 표집을 고르게",
     "걷는 중 1.0: 99~100 % · 1.5: 78~88 % · 2.0: 37~45 % · 서 있기 1.0: 89~92 %", "D168 WORKLIST:196 · D171 WORKLIST:198 · ex41-fixed5000.yaml:446", "실측 · 가정"),
    ("후진 범위 · 몫", "[-1.0, -0.2] 12 % · 대각 뒤 1.5 % → [-1.3, -0.2] 14 % · 대각 뒤 2.5 %",
     "후진 1.0 추종이 m6000 에서 유일한 미달 칸. 앱 후진 1.3 까지 쓰려면 학습 범위가 넓어야 함",
     "끔 back1.0 생존 60/64 · 오차 0.151 (> 0.15 FAIL) · 정답 0.149", "D94 WORKLIST:122 · D105 WORKLIST:133 · ex41-fixed5000.yaml:118-120,144-149", "실측 · 코드"),
    ("전진 · 회전 몫", "전진 25 % · 회전 10+10 % → 23 % · 9+9 %",
     "후진 · 대각 뒤를 늘린 만큼 이미 잘 되는 전진 · 회전에서 뗌",
     "m6000 전진 · 회전 칸 64/64 (정답 fwd0.5 63)", "D96 WORKLIST:124 · ex41-fixed5000.yaml:137-149", "코드"),
    ("옆 · 대각 앞 몫 (S2c 부터)", "옆 6+6 % · 대각 앞 1.5+1.5 % · 걸으며 돌기 7.5+7.5 % → 7+7 · 2+2 · 6+6",
     "좌우를 같은 양으로 늘려 옆걸음 좌우 차를 줄임(오른쪽만 늘린다는 옛 기록은 잘못, D161 정정)",
     "정답 옆 오차 side+0.5 0.083 · side-0.5 0.112 m/s (좌우 차)", "D91 WORKLIST:119 · D161 WORKLIST:189 · ex41-fixed5000.yaml:236-248", "실측 · 코드"),
    ("heading 직진 유지 몫", "50 % → 30 %", "구간 2 설계 추가 제안 여섯 중 하나(승인). 상세 근거 문장은 원장에 없음",
     "미확인", "D93 WORKLIST:121 · ex41-fixed5000.yaml:24", "코드"),
    ("걸림 · 스윙 벌점", "걸림 -1 · 스윙 없음 → 걸림 -2 · 스윙 -10",
     "후진 때 뒷다리 끌림, 옆걸음 때 반대쪽 뒷다리 끌림(팀장 영상 관찰). 스윙 -10 은 「두 발 8 cm 낮게 끌릴 때 추종 보상의 5~10 %」 로 계산",
     "m6000 영상 관찰 (숫자 지표 없음)", "D109 · D117 WORKLIST:145 · D123 WORKLIST:151 · ex41 env.yaml rewards", "가정 · 코드"),
    ("회전 0 명령 때 회전 L1", "없음 → -0.5",
     "전진 · 정지 · 후진 때 몸이 한쪽으로 도는 치우침(정지 뒤 후진이 왼쪽 엉덩이 쪽으로 감)",
     "axis250 yaw 표 · 팀장 관찰", "D86 · D89 WORKLIST:117 · D96 · D128 · ex41-fixed5000.yaml:98", "가정 · 코드"),
    ("lin_vel_z", "B1 1501~3000 에 -2 → 0 직선, m6000 은 0", "옮겨 받은 실제 가중 0 을 유지. env.yaml 의 -2 는 시작값일 뿐",
     "m6000 Loss/basic_reward/lin_vel_z_weight 0", "D141 WORKLIST:169 · ex41.py:381-384", "코드"),
    ("미리 등록 보상 4 항", "없음 → 무릎 토크 · 관절 한계 근접 · 체공 · 미끄럼 0 가중",
     "지형 단계에서 켤 칸을 입력 · 기록 경로부터 미리 확인. 실행 중 0 이 아니면 거절", "W86 기록만", "D106 · D116 · D117 · ex41.py:376-378", "코드"),
    ("자세 명령 2 칸", "없음 → 몸 높이 · roll 입력 2 칸, 값 0 고정",
     "HiPAN 식 기어가기 · 자세 명령을 다음 판에서 열기 위해 입력 차원만 먼저", "-", "D82 · D93 · start_runner.py:240-245", "코드"),
    ("지형", "L0~2 고정 → S2a~S2c 고정 · S2d 부터 성과 승급 상한 L5",
     "기본 명령 보행을 DR 아래에서 굳힌 뒤 지형 레벨을 성과로 올림. 많은 지형 미리 넣기는 EX-42", "-", "D96 · D114 · D126 · ex41-fixed5000.yaml:324-326", "코드"),
    ("지도", "m6000 까지 정답 강제 → S2a~S2e 정답 강제 · T0′ 복원 소비",
     "복원 지도로 바꾸는 것은 맨 끝에 그것만 따로 (EX-40 T0 와 같은 방식)",
     "EX-40 T0 use_gt_frac 평균 0.151", "D65 · D90 · D136 · D143 (P7-4 ≤ 0.3) · ex41-fixed5000.yaml:421", "코드 · 실측"),
    ("좌우 대칭", "끔 → 끔 유지 · 250 마다 S = min/max 기록 · 승인되면 W72 로 켬",
     "옆 · 대각 좌우 차. 자동 켬은 하지 않기로(D142 · D155). 실행 코드도 자동 켬 규칙을 부르지 않음",
     "m6000 좌우 오차 차 위 「옆」 행", "D91 · D99 · D101 · D142 WORKLIST:170 · D155 WORKLIST:183 · D166 · ex41_fixed.py:479-483", "코드"),
    ("자동 조정", "없음 → 서 있기 61/64 밑이면 스윙 -10→-5 한 번 · S2e 끝 +500 연장 한 번",
     "D96 의 「약한 칸 자동 가중」 · 보상 반감은 승인 범위에서 빠짐(D130 은 서 있기 복원 · 연장 · 보고만)",
     "m6000 정지 64/64", "D110 · D130 · ex41_fixed.py:496-514 · approvals.yaml automatic", "코드"),
    ("평가 주기", "250 회 26 칸 그림자 → 250 회 39 숫자 + 계단 옆걸음 좌우 S · 단계 끝 축 전부 + 밀기 사다리",
     "숫자만이 아니라 250 경계마다 해석 · 복원 13 칸도 늘 기록(M83 · D160)", "-", "D166 WORKLIST:194 · D133", "코드"),
    ("회차 · 끝", "EX-40 m0~m8000 계획 → EX-41 5000 회 고정(+유지 1000 · +연장 500 = 최대 6500)",
     "성과로 일찍 넘기지 않고 같은 길이로 비교. 팀장 희망: 로컬 6000(누적 12000) 으로 끝맺기는 미정",
     "-", "D126 · ex41_fixed.py:222 · 팀장 11/03 21:0x 희망", "코드 · 가정"),
]


def why_png(path):
    cols = [("항목", 2.7), ("이전 → 지금", 6.2), ("왜 (무엇을 극복하나)", 7.6), ("근거가 된 m6000 실측", 5.2),
            ("결정 · 출처 파일:줄", 5.6), ("등급", 1.3)]
    H = 0.78
    fig_w = sum(w for _, w in cols) + 0.6
    fig_h = H * (len(WHY) + 1) + 1.6
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_w)
    ax.set_ylim(fig_h, 0)
    ax.axis("off")
    ax.text(0.3, 0.45, "왜 바꿨나 · EX-40 m6000 의 무엇을 넘으려고", fontsize=22, weight="bold", va="center")
    ax.text(0.3, 0.95, "등급: 코드 = 실행 설정 · 실측 = 우리 평가 원자료 · 가정 = 정해 둔 값(결과 전 등록) · 결정 번호는 inbox/jay/20261028-plan/WORKLIST.md 줄",
            fontsize=12, color="#37474f", va="center")
    import textwrap
    y = 1.3
    x = 0.3
    for name, w in cols:
        ax.add_patch(Rectangle((x, y), w, H * 0.6, facecolor="#263238"))
        ax.text(x + 0.1, y + H * 0.3, name, color="white", fontsize=13, weight="bold", va="center")
        x += w
    y += H * 0.6
    for k, row in enumerate(WHY):
        x = 0.3
        for j, ((name, w), txt) in enumerate(zip(cols, row)):
            fc = "#fff8e1" if j == 1 else ("#f5f5f5" if j == 0 else "white")
            if j == 3 and txt == "미확인":
                fc = "#ffcdd2"
            ax.add_patch(Rectangle((x, y), w, H, facecolor=fc, edgecolor="#cfd8dc"))
            width = int(w * 7.6) if j else int(w * 7.0)
            wrapped = "\n".join(textwrap.wrap(txt, width=width)[:3])
            ax.text(x + 0.08, y + H / 2, wrapped, fontsize=10.6 if j else 11.5, va="center",
                    weight="bold" if j == 0 else "normal", linespacing=1.15)
            x += w
        y += H
    fig.savefig(path, dpi=100)
    plt.close(fig)


# ---------------------------------------------------------------- m6000 baseline
def baseline_png(path):
    lad = json.loads(LADDER.read_text(encoding="utf-8"))
    sc = json.loads(SCORE6000.read_text(encoding="utf-8-sig"))
    assert lad["checkpoint_sha256"] == sc["checkpoint_sha256"] == ex41["parent_sha256"]
    fig, axes = plt.subplots(1, 2, figsize=(28, 9), dpi=100, gridspec_kw=dict(width_ratios=[1.25, 1]))
    fig.suptitle("m6000 기준선 (EX-41 이 넘어야 할 출발점) · 실측", fontsize=24, weight="bold", x=0.04, ha="left")
    ax = axes[0]
    style = {"flat": "-", "random_rough": "--", "pyramid_stairs": ":"}
    color = {"eval_gt": "#1565c0", "eval_pred": "#2e7d32", "probe_prop_only": "#c62828"}
    tname = {"flat": "평지", "random_rough": "거친 땅", "pyramid_stairs": "계단"}
    mname = {"eval_gt": "정답", "eval_pred": "복원", "probe_prop_only": "끔"}
    for ch in lad["children"]:
        s = ch["summary"]
        mags = sorted(float(k) for k in s["magnitudes"])
        vals = [s["magnitudes"][f"{m:g}" if f"{m:g}" in s["magnitudes"] else str(m)]["survival_fraction"] for m in mags]
        if ch["command"] == "stand":
            ax.plot(mags, vals, color=color[s["map_mode"]], lw=1.6, ls="-.", marker="x", alpha=0.8,
                    label=f"서 있기 · 평지 · {mname[s['map_mode']]}")
        else:
            ax.plot(mags, vals, color=color[s["map_mode"]], lw=2.2, ls=style[s["terrain"]], marker="o",
                    label=f"걷는 중 0.5 · {tname[s['terrain']]} · {mname[s['map_mode']]}")
    ax.axhline(0.9, color="#000", lw=1.2)
    ax.text(2.05, 0.92, "판정선 90 % (D171: 걷는 중 1.5 m/s · 가장 나쁜 방향 기준,\n그림은 8 방향 모음이라 판정보다 후하게 보임)", fontsize=12, va="bottom")
    for v, lab in [(1.5, "EX-41 기본 1.5"), (2.0, "상한 2.0")]:
        ax.axvline(v, color="#6a1b9a", ls="--")
        ax.text(v + 0.03, 0.05, lab, color="#6a1b9a", fontsize=12, rotation=90, va="bottom")
    ax.set_xlabel("밀기 크기 m/s (방향 8 개 모음)", fontsize=13)
    ax.set_ylabel("생존 비율", fontsize=13)
    ax.set_title("밀기 사다리 (runner 11/03 16:14 · 512 env × 칸)", fontsize=15)
    ax.legend(fontsize=9.5, ncol=2, loc="lower left")
    ax.grid(alpha=0.3)
    ax = axes[1]
    ax.axis("off")
    c = sc["cells"]
    lines = [("판정 26 칸 (정답 · 끔) 생존", ""),
             ("  60/64 미만", "없음 (최저 끔 back1.0 60)"),
             ("  끔 back1.0 vx 오차", f"{c['probe_prop_only/back1.0']['tracking_medians']['vx_abs_error_mean_alive_mps']:.3f} m/s  (> 0.15 FAIL)"),
             ("  정답 back1.0 vx 오차", f"{c['eval_gt/back1.0']['tracking_medians']['vx_abs_error_mean_alive_mps']:.3f} m/s"),
             ("  정답 옆 +0.5 / -0.5 vy 오차", f"{c['eval_gt/side+0.5']['tracking_medians']['vy_abs_error_mean_alive_mps']:.3f} / "
                                         f"{c['eval_gt/side-0.5']['tracking_medians']['vy_abs_error_mean_alive_mps']:.3f} m/s"),
             ("  정답 회전 +1.2 / -1.2 wz 오차", f"{c['eval_gt/spin+1.2']['tracking_medians']['wz_abs_error_mean_alive_radps']:.3f} / "
                                          f"{c['eval_gt/spin-1.2']['tracking_medians']['wz_abs_error_mean_alive_radps']:.3f} rad/s"),
             ("  정지 (정답 · 끔)", f"{c['eval_gt/flat_stand']['passed_envs']}/64 · {c['probe_prop_only/flat_stand']['passed_envs']}/64"),
             ("복원 13 칸 (기록 전용)", "최저 62/64 (side-0.5 · diag-back+side+)"),
             ("그림자 판정", f"{sc['verdict']} (끔 back1.0 오차 · W78 증거 누락)"),
             ("DR · 밀기", "DR 0.5 · 밀기 축마다 ±0.5 m/s · 지연 상한 7.5 ms (실제 5 ms)"),
             ("영상 관찰 (팀장)", "후진 · 옆걸음 때 뒷다리 끌림 (D117)"),
             ("관찰 (팀장)", "정지 · 정지 뒤 후진 때 몸이 돎 (D128)")]
    y = 0.95
    for k, v in lines:
        ax.text(0.0, y, k, fontsize=14, weight="bold" if not k.startswith("  ") else "normal", transform=ax.transAxes)
        ax.text(0.47, y, v, fontsize=14, transform=ax.transAxes)
        y -= 0.075
    ax.text(0.0, y - 0.02, f"원자료: {SCORE6000.name} · push_ladder_bundle.json (sha 일치 확인)", fontsize=11,
            color="#546e7a", transform=ax.transAxes)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=100)
    plt.close(fig)


if __name__ == "__main__":
    timeline_png(OUT / "01-timeline.png")
    table_png(OUT / "02-stage-table.png")
    why_png(OUT / "03-why-changed.png")
    baseline_png(OUT / "04-m6000-baseline.png")
    print("ok", EX41_SHA[:8])
