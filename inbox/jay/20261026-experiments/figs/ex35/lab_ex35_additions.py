"""Source-specific evidence and pending-media cards for the EX-35 lab page."""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[5]
CARD = ROOT / "inbox/jay/20261021-experiments/EXP-EX35-SB10-cmd-S2a.md"
GATE = Path("C:/mai/wt/foothold-lab/fable-25a/inbox/jay/20261027-design/GATE-v2-performance-promotion.md")
VERIFIER = Path("C:/mai/wt/foothold-lab/verifier-27c-window/inbox/jay/20261027-experiments/VERIFY-verifier-GATE-v2-statistics.md")
ANALYST = Path("C:/mai/wt/foothold-lab/astra-25b/inbox/jay/20261027-design/VERIFY-analyst-GATE-v2.md")
A1_FIGURES = Path("C:/mai/wt/foothold-lab/astra-25b/inbox/jay/20261027-design/figs/ex35-a1-m2000")
TURN_FIGURE = Path("C:/Users/AI-WS01/s2_lab/lab_status/ex35_turn16_repeat.png")
MEDIA = Path("C:/Users/AI-WS01/s2_lab/video_25e/final/runner-26m")
SERVED = Path("C:/Users/AI-WS01/s2_lab/lab_status")
JOBS = MEDIA / "queue/jobs_remaining.json"
STATE = MEDIA / "queue/state_remaining.json"
FIRST_RECEIPT = MEDIA / "cap/b1500_rough_normalized/review.done"
COMPOSE = MEDIA / "queue/compose_jobs.json"
SEQS = (
    MEDIA / "p2/rendered/CMP_S-B10-m1500_vs_EX-35-m2000_rough_eval_gt_seq_1x.mp4",
    MEDIA / "p2/rendered/EX-35-m2000_rough_eval_gt_seq_1x.mp4",
    MEDIA / "p2/rendered/S-B10-m1500_rough_eval_gt_seq_1x.mp4",
)

AXES = {
    "A1": ("보행 위상", "대각 발 접촉 위상과 주기"),
    "A2": ("지형별 전진", "레벨별 전진 거리와 생존"),
    "A3": ("회전 16 env", "방향별 Q, C, 생존"),
    "A4": ("회전 64 env", "좌우 제자리 회전 중앙값과 생존"),
    "A5": ("걸으며 돌기", "좌우 추종, 반대 부호, 전진 적분"),
    "A6": ("생존", "종료와 넘어짐 수"),
    "A7": ("몸 기울기", "몸 기울기 분포"),
    "A8": ("접촉 링크 평면 속도", "접촉한 발 링크의 평면 속도"),
    "A9": ("학습 곡선", "손실, KL, 보상과 비유한값"),
    "A10": ("지도 소비 모드", "정답, 가림, 예측 지도 비교"),
    "A11": ("영상 1x 판독", "CMP와 단독 영상의 시각 판독"),
    "A12": ("재현", "판정 수치 독립 재계산"),
}


def checked(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return str(path).replace("/", "\\")


def evidence(*items: tuple[str, Path]) -> str:
    links = []
    for label, path in items:
        display = html.escape(checked(path))
        if path in SEQS:
            served = SERVED / "videos" / path.name
            url = f"videos/{quote(path.name)}" if served.is_file() and os.path.samefile(served, path) else None
        elif path == TURN_FIGURE and (SERVED / path.name).is_file():
            url = quote(path.name)
        else:
            url = None
        if url:
            links.append(f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a> {display}')
        else:
            links.append(f"{html.escape(label)} {display}")
    return f'<p class="t">근거 {" · ".join(links)}</p>'


def decorate_existing(cards: list[str], data: dict) -> list[str]:
    from lab_ex35_results import source_path

    if len(cards) != 6:
        raise ValueError("six source result cards expected")
    specs = (
        (("반복표", Path(source_path(data, "turn16_compare"))), ("반복 그림", TURN_FIGURE)),
        (("A11 판독", Path(source_path(data, "a11"))), ("CMP 영상", Path(source_path(data, "cmp_video"))), ("A1 그림", A1_FIGURES)),
        (("재현성 비교", Path(source_path(data, "repro_compare"))),),
        (("기본 창 판정", Path(source_path(data, "window_default"))), ("재평가 로그", Path(source_path(data, "remeasure_log")))),
        (("GATE-v2", GATE), ("verifier 검토", VERIFIER), ("analyst 검토", ANALYST)),
        (("학습 영수증", Path(source_path(data, "receipt"))), ("학습 로그", Path(source_path(data, "run_log")))),
    )
    result = []
    for card, spec in zip(cards, specs, strict=True):
        replaced, count = re.subn(r'<p class="t">.*?</p>', lambda _: evidence(*spec), card, count=1, flags=re.S)
        if count != 1:
            raise ValueError("result card evidence slot missing")
        result.append(replaced)
    return result


def design_card() -> str:
    source = CARD.read_text(encoding="utf-8")
    row = next((line for line in source.splitlines() if line.startswith("| 바꾸는 것(한 축) |")), None)
    if row is None:
        raise ValueError("EX-35 one-axis preregistration missing")
    weights = re.findall(r"([\d.]+) %", row.split("|")[2])
    if weights != ["75", "2.5", "2.5", "10", "10"] or sum(map(float, weights)) != 100:
        raise ValueError("EX-35 command distribution changed")
    for token in ("**500 회**", "**3072**", "**cuda:0**", "물리 · 보상 · PPO", "p_map_off **0.1**"):
        if token not in source:
            raise ValueError(f"EX-35 contract missing: {token}")
    for key, (name, _) in AXES.items():
        if f"**{key} {name}**" not in source:
            raise ValueError(f"EX-35 axis missing: {key}")
    axis_text = " · ".join(f"{key} {name}: {meaning}" for key, (name, meaning) in AXES.items())
    body = (
        "결과 전 등록 v0.9. 바꾼 축은 명령 배분 하나: "
        f"전진 {weights[0]}%, 걸으며 돌기 좌우 {weights[1]}% + {weights[2]}%, "
        f"제자리 회전 좌우 {weights[3]}% + {weights[4]}%. "
        "지도 끔 허용 지형 10%, 보정 켬, 지형과 물리 · 보상 · PPO 유지. "
        "S-B10 m1500에서 추가 500회, 3072 env, cuda:0. "
        f"판정 축: {axis_text}."
    )
    return (
        '<div class="card ex35-recent"><p><b>10/26 23:24 · EX-35 설계와 판정 축</b>: '
        + html.escape(body)
        + "</p>"
        + evidence(("결과 전 카드", CARD))
        + "</div>"
    )


def video_card() -> str:
    jobs = json.loads(JOBS.read_text(encoding="utf-8"))["jobs"]
    state = json.loads(STATE.read_text(encoding="utf-8"))
    compose = json.loads(COMPOSE.read_text(encoding="utf-8"))["jobs"]
    if len(jobs) != 9 or len(compose) != 32 or len({job["id"] for job in jobs}) != len(jobs):
        raise ValueError("media queue size or IDs changed")
    sparse = [job for job in jobs if "sparse18" in job["id"]]
    if len(sparse) != 4:
        raise ValueError("four sparse media jobs expected")
    receipt = json.loads(FIRST_RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("child_returncode") != 0 or len(receipt.get("files", {})) != 3:
        raise ValueError("prior capture receipt incomplete")
    completed = []
    for job in jobs:
        output = Path(job["output"])
        if not output.exists():
            continue
        done = json.loads(output.read_text(encoding="utf-8"))
        if done.get("child_returncode") == 0 and len(done.get("files", {})) == 3:
            completed.append(job["id"])
    composed = sum(Path(job["output"]).is_file() for job in compose)
    state_completed = {entry["id"] if isinstance(entry, dict) else entry for entry in state["completed"]}
    state_note = "" if state_completed == set(completed) else " 대기열 상태와 영수증 수가 달라 확인 필요."
    seq_paths = [Path(checked(path)) for path in SEQS]
    body = (
        "EX-35 CMP · EX-35 단독 · 부모 S-B10 단독 seq 1x 세 편 완료. "
        f"L4 재구성 {composed}/{len(compose)}편 완료. 첫 촬영 영수증 1건 확인, "
        f"남은 촬영 {len(completed)}/{len(jobs)}건 완료, "
        f"듬성 성공 · 실패 촬영 {len(sparse) - sum(job['id'] in completed for job in sparse)}건 미완. "
        "EX-35 구간 영상과 m1750 영상은 이 대기열에 완료 영수증 없음." + state_note
    )
    proof = evidence(
        ("CMP", seq_paths[0]), ("EX-35 단독", seq_paths[1]), ("부모 단독", seq_paths[2]),
        ("첫 촬영 영수증", FIRST_RECEIPT), ("남은 촬영", JOBS),
        ("대기 상태", STATE), ("재구성 목록", COMPOSE),
    )
    stamp = datetime.now(timezone(timedelta(hours=9))).strftime("%m/%d %H:%M KST")
    return f'<div class="card ex35-recent"><p><b>{stamp} · 영상 제작 상태</b>: ' + html.escape(body) + "</p>" + proof + "</div>"
