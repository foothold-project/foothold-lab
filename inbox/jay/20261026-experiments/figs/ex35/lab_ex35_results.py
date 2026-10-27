"""Render the six dated EX-35 lab updates from sealed result evidence."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path, PureWindowsPath


ROOT = Path(__file__).resolve().parents[5]
DATA = Path(__file__).with_name("result_data.json")
RESULT = ROOT / "inbox/jay/20261026-experiments/RESULT-EX35-1027.md"
AGENDA = ROOT / "inbox/jay/20261019-design/AGENDA-LEAD.md"
RULES = ROOT / "inbox/jay/20261019-design/RULES-HUB.md"
RECON_FIGURE = Path(__file__).with_name("reconstruction_loss_s-b10_ex35.png")
FIGURE = Path("C:/Users/AI-WS01/s2_lab/lab_status/ex35_turn16_repeat.png")
RESULT_URL = (
    "https://github.com/foothold-project/foothold-lab/blob/"
    "feature/verify-v2-mvp-jay/inbox/jay/20261026-experiments/RESULT-EX35-1027.md"
)
START = "<!-- EX35_RECENT_START -->"
END = "<!-- EX35_RECENT_END -->"


def winpath(value: str | Path) -> str:
    return str(PureWindowsPath(str(value).replace("\\\\", "\\")))


def source_path(data: dict, key: str) -> str:
    value = data["source_paths"][key]
    if not Path(winpath(value)).is_file():
        raise FileNotFoundError(value)
    return winpath(value)


def proof_link(data: dict, table_key: str) -> str:
    video = source_path(data, "cmp_video")
    table = source_path(data, table_key)
    return (
        f'<p class="t"><a href="{RESULT_URL}">RESULT-EX35 v1.5</a> · '
        f'그림 {html.escape(winpath(FIGURE))} · '
        f'영상 {html.escape(video)} · 표 {html.escape(table)}</p>'
    )


def card(title: str, body: str, data: dict, table_key: str) -> str:
    return (
        f'<div class="card ex35-recent"><p><b>{html.escape(title)}</b>: '
        f'{html.escape(body)}</p>{proof_link(data, table_key)}</div>'
    )


def agenda_gate(agenda: str) -> tuple[int, int, float, float, str]:
    section = agenda.split("## 10/27 04시대 · GATE-v2", 1)[1].split("\n## ", 1)[0]
    blockers = re.search(r"verifier.*?막음 (\d+).*?analyst.*?막음 (\d+)", section)
    right = re.search(r"right_then_left m1500 Q ([\d.]+), 부모 7 저장본 μ−σ ([\d.]+)", section)
    forward = re.search(r"fwd_then_left ([\d.]+) → ([\d.]+)", section)
    planner = re.search(r"planner `([^`]+)` v0\.2", section)
    if not (blockers and right and forward and planner and "결정 일곱" in section):
        raise ValueError("AGENDA-LEAD GATE-v2 evidence incomplete")
    gate_path = ROOT.parent / planner[1]
    if not gate_path.is_file():
        raise FileNotFoundError(gate_path)
    right_drop = 100 * (1 - float(right[2]) / float(right[1]))
    forward_drop = 100 * (1 - float(forward[2]) / float(forward[1]))
    return int(blockers[1]), int(blockers[2]), right_drop, forward_drop, winpath(gate_path)


def render_cards(data: dict, agenda: str, result: str, a11: dict) -> str:
    if "> 판: v1.5" not in result or data["window_decision"] != "STOP" or data["window_row"] != 6:
        raise ValueError("RESULT-EX35 v1.5 seal mismatch")
    if data["windows"]["m1950"]["state"] != "MAINTAIN_FAIL" or data["windows"]["m2000"]["state"] != "MAINTAIN_FAIL":
        raise ValueError("two saved-window verdicts missing")
    if data["window_evidence"]["a11"]["state"] != "clear" or list(a11["items"].values()) != ["없음"] * 5:
        raise ValueError("A11 reading mismatch")
    if a11["cmp_video"]["sha256"] != data["source_sha256"]["cmp_video"]:
        raise ValueError("CMP video SHA mismatch")
    blockers_v, blockers_a, right_drop, forward_drop, gate_path = agenda_gate(agenda)
    t, x, turn = data["training"], data["window_evidence"], data["turn16"]
    samples = turn["cases"]
    right_q = [samples["right_then_left"]["repeats"][f"R{i}"]["Q"] for i in range(1, 4)]
    kept_forward = [samples["fwd_then_left"]["repeats"][f"R{i}"]["kept"] for i in range(1, 4)]
    kept_left_right = [samples["left_then_right"]["repeats"][f"R{i}"]["kept"] for i in range(1, 4)]
    if not all(v < turn["right_then_left_q_limit"] for v in right_q):
        raise ValueError("repeat Q no longer below limit")
    count_figures = sum(int(n) for n in re.findall(r"(\d+) 장", a11["basis"]["a1"]))
    if count_figures != 8 or "300 프레임" not in a11["basis"]["frames"]:
        raise ValueError("A11 frame or figure count mismatch")
    duration = re.search(r"(\d+) s", a11["basis"]["item1"])
    remeasure_line = re.search(r"^- \*\*재평가\*\*: (.+)$", agenda, flags=re.M)
    if not duration or not remeasure_line:
        raise ValueError("A11 duration or remeasurement stages missing")
    stage_count = len(set(re.findall(r"m\d{4}", remeasure_line[1].split("×", 1)[0])))
    if stage_count * 4 != x["remeasure_stages"]:
        raise ValueError("remeasurement stage count mismatch")
    end_match = re.search(r"GPU0 학습 작업은 (\d\d:\d\d:\d\d)부터 종료", agenda)
    if not end_match:
        raise ValueError("training completion time missing in AGENDA-LEAD")
    cards = [
        card(
            "05:5x · 16 env 회전 세 번 반복",
            f"전진→좌 kept {kept_forward[0]} · {kept_forward[1]} · {kept_forward[2]}, "
            f"우→좌 Q {right_q[0]:.3f} · {right_q[1]:.3f} · {right_q[2]:.3f} "
            f"< {turn['right_then_left_q_limit']:.3f}으로 실패 사유 둘이 반복됐다. "
            f"좌→우 kept는 사슬 {samples['left_then_right']['chain']['kept']} → "
            f"{kept_left_right[0]} · {kept_left_right[1]} · {kept_left_right[2]}로 흔들렸다.",
            data,
            "turn16_compare",
        ),
        card(
            "05:19 · A11 영상 판독과 창 판정",
            f"CMP {a11['basis']['frames'].split(' 프레임')[0].removeprefix('CMP ')} 프레임과 A1 그림 {count_figures}장 판독에서 "
            f"A11 {len(a11['items'])}항목 모두 없음. {duration[1]}초 영상과 축소 해상도의 한계가 있다. "
            f"기본 STOP {data['window_default_row']}행에서 판독 반영 뒤 STOP {data['window_row']}행 "
            f"(되돌림 갈래), 정본 {data['canonical']} 유지. 직진 명령에서 부모는 왼쪽, "
            "m2000은 오른쪽으로 휘는 발자국 메모는 수치 미측이다.",
            data,
            "a11",
        ),
        card(
            "05:1x · 같은 GPU 재평가 비결정성",
            f"같은 GPU0 · 저장본 · 시드 반복에서도 map64 비교 가능 {x['repro_numeric_count']} 수치 중 "
            f"{x['repro_a1_a2_changed']}개가 달랐다. 코드 변경 영향과 반복 잡음을 분리하지 못했다.",
            data,
            "repro_compare",
        ),
        card(
            "05:0x · m1800~m2000 재평가",
            f"{stage_count}개 저장본의 네 칸씩 {x['remeasure_stages']}단계 재평가. A11 파일 없이 돌린 "
            f"기본 창 판정은 STOP {data['window_default_row']}행이었다. "
            "16 env 회전 사슬과 64 env 재평가의 합본이며 원인 미확인 차이가 있다.",
            data,
            "remeasure_log",
        ),
        card(
            "04시대 · GATE-v2 v0.2 검토",
            f"verifier 막음 {blockers_v}, analyst 막음 {blockers_a}. 부모 7 저장본 평균−표준편차 "
            f"기준선을 쓰면 {data['canonical']} 대비 우→좌 {right_drop:.0f}%, "
            f"전진→좌 {forward_drop:.0f}% 하락까지 허용한다는 검토 수치다. "
            f"팀장 결정 일곱은 아직 대기 중이다. GATE 검토 문서 {gate_path}.",
            data,
            "baseline",
        ),
        card(
            f"{end_match[1]} · EX-35 학습 완료",
            f"완료 iteration {t['completed_iteration']}, model_{t['completed_iteration']} 저장 기록과 "
            f"종료 rc {t['exit_code']}. m1950 · m2000 저장본은 모두 MAINTAIN_FAIL. "
            "이는 독립 평가의 최종 해석이 아니다.",
            data,
            "receipt",
        ),
    ]
    from lab_ex35_additions import decorate_existing, design_card, video_card

    terrain = data["terrain_compare"]
    measured = [row for row in terrain["rows"] if row["measured"] and row["mode"] == "켬" and row["command"] == "fwd1.0"]
    gains = [row["child_median_m"] - row["parent_median_m"] for row in measured]
    if len(measured) != 21 or not all(gain > 0 for gain in gains) or len(terrain["missing"]) != 4:
        raise ValueError("terrain comparison evidence incomplete")
    repeat = terrain["repeat"]
    terrain_card = (
        '<div class="card ex35-recent"><p><b>10/27 · 같은 조건 지형별 부모 대조</b>: '
        f'켬 fwd1.0 {len(measured)}칸의 m2000 거리 중앙값 차이 {min(gains):.2f}~{max(gains):.2f} m. '
        f'L9 상자 가림 생존 재측정 {repeat["earlier_alive"]}/{repeat["n"]} → '
        f'{repeat["current_alive"]}/{repeat["n"]}. 두 재측정의 코드 해시는 달라 원인 분리 불가. '
        '복원 L6·L9는 미측정.</p>'
        f'<p class="t"><a href="{RESULT_URL}">RESULT-EX35 v1.5 지형 표</a> · '
        f'원자료 {html.escape(source_path(data, "terrain_child_L9_probe_prop_only_fwd1.0"))}</p></div>'
    )
    cards = [*new_decision_cards(), video_card(), terrain_card, *decorate_existing(cards, data), design_card()]
    return START + "\n" + "\n".join(cards) + "\n" + END


def new_decision_cards() -> list[str]:
    rules = RULES.read_text(encoding="utf-8")
    level_row = next((line for line in rules.splitlines() if line.startswith("| 10/27 11:2x |")), "")
    restart_row = next((line for line in rules.splitlines() if line.startswith("| 10/27 11:3x |")), "")
    if not all(token in level_row for token in ("L0~2 · L3 · L6 · L9", "L3 은 미측", "이미 고정된 EX-35 카드")):
        raise ValueError("RULES-HUB level decision incomplete")
    if "77388 종료는 승인 없이" not in restart_row:
        raise ValueError("RULES-HUB process decision incomplete")
    if not RECON_FIGURE.is_file():
        raise FileNotFoundError(RECON_FIGURE)
    proof = html.escape(winpath(RULES))
    figure = html.escape(winpath(RECON_FIGURE))
    return [
        '<div class="card ex35-recent"><p><b>10/27 12:02 · 복원 지도 셋 진행 상태</b>: '
        '복원 손실 학습 곡선 완료 (7b1ad9fe, 해석 미완). '
        '복원 오차 축 코드 검토 중 (sonnet-code 753f9b08, GPU 미실행). '
        '복원 지도 모드 영상 미착수.</p>'
        f'<p class="t">근거 그림 {figure} · 팀장 결정 원장 {proof} 10/27 11:2x</p></div>',
        '<div class="card ex35-recent"><p><b>10/27 11:2x · 지형 레벨 평가 결정</b>: '
        '앞으로 부모 비교와 지형 레벨 평가는 L0~2 · L3 · L6 · L9. '
        'L3 미측. 기존 EX-35 카드 v0.9의 판정 칸은 소급 변경하지 않음.</p>'
        f'<p class="t">근거 팀장 결정 원장 {proof} 10/27 11:2x</p></div>',
    ]


def render_decisions(data: dict, agenda: str) -> str:
    if "결정 일곱" not in agenda or "되돌림 판" not in agenda or data["window_row"] != 6:
        raise ValueError("decision sources incomplete")
    intro = (
        f'<p>EX-35 m1950 · m2000 저장본은 MAINTAIN_FAIL. 기본 창 STOP '
        f'{data["window_default_row"]}행은 A11 파일이 없었기 때문이며, 판독을 반영한 창 판정은 '
        f'STOP {data["window_row"]}행 (되돌림 갈래)이다. 연장 없음, '
        f'정본 {data["canonical"]} 유지. 새 학습은 팀장 결정 전 대기.</p>'
    )
    return intro + "\n" + "\n".join(
        [
            '<div class="row"><div class="k">1 · 깃발 평가 진행 여부</div><div>'
            '추가 평가를 진행할지 팀장이 결정. 현재 새 GPU 실행 지시 아님.</div></div>',
            '<div class="row"><div class="k">2 · 실험 순서 v2 규칙화</div><div>'
            '실험 순서 v2를 규칙으로 확정할지 팀장이 결정. 현재 초안 단계.</div></div>',
            '<div class="row"><div class="k">3 · 77388 종료 소급 승인</div><div>'
            f'갱신기 PID 77388 종료는 승인 없이 이뤄졌다. 소급 승인 여부는 팀장 대기. '
            f'근거 {html.escape(winpath(RULES))} 10/27 11:3x.</div></div>',
        ]
    )


def render_page(source: str, cards: str, decisions: str) -> str:
    if START in source or END in source:
        if source.count(START) != 1 or source.count(END) != 1:
            raise ValueError("duplicate EX-35 recent markers")
        source = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: cards, source, count=1, flags=re.S)
    else:
        heading = "<h2>새 결과 (최신이 위)</h2>"
        if source.count(heading) != 1:
            raise ValueError("new results section missing")
        source = source.replace(heading, heading + "\n" + cards, 1)
    pattern = r'(<section class="decide">\s*<h2>[^<]+</h2>)(.*?)(</section>)'
    match = re.search(pattern, source, flags=re.S)
    if not match or match[2].count('class="row"') != 3:
        raise ValueError("three decision rows missing")
    return source[: match.start()] + match[1] + "\n  " + decisions + "\n" + match[3] + source[match.end() :]


def load_sources() -> tuple[dict, str, str, dict]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    agenda = AGENDA.read_text(encoding="utf-8")
    result = RESULT.read_text(encoding="utf-8")
    a11 = json.loads(Path(source_path(data, "a11")).read_text(encoding="utf-8"))
    return data, agenda, result, a11


def ensure_figure(data: dict) -> None:
    if FIGURE.exists() and FIGURE.stat().st_mtime >= DATA.stat().st_mtime:
        return
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    cases = data["turn16"]["cases"]
    q = [cases["right_then_left"]["repeats"][f"R{i}"]["Q"] for i in range(1, 4)]
    kept = [cases["fwd_then_left"]["repeats"][f"R{i}"]["kept"] for i in range(1, 4)]
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2), constrained_layout=True)
    axes[0].plot([1, 2, 3], q, marker="o", color="#1f6f5c")
    axes[0].axhline(data["turn16"]["right_then_left_q_limit"], color="#a3302a", linestyle="--")
    axes[0].set(title="Right then left Q", xlabel="Repeat", ylabel="Q", xticks=[1, 2, 3])
    axes[1].plot([1, 2, 3], kept, marker="o", color="#1f6f5c")
    axes[1].axhline(data["turn16"]["kept_limit"], color="#a3302a", linestyle="--")
    axes[1].set(title="Forward then left kept", xlabel="Repeat", ylabel="Kept / 16", xticks=[1, 2, 3])
    for axis in axes:
        axis.grid(alpha=0.25)
    temporary = FIGURE.with_name(FIGURE.stem + ".refresh.png")
    fig.savefig(temporary, dpi=140)
    plt.close(fig)
    temporary.replace(FIGURE)
