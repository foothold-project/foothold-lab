"""Place the generated EX-35 outcome in the record chain, idempotently."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DATA = Path(__file__).with_name("result_data.json")
REPORT = ROOT / "inbox/jay/20261026-experiments/RESULT-EX35-1027.md"
CARD = ROOT / "inbox/jay/20261021-experiments/EXP-EX35-SB10-cmd-S2a.md"
DOCS = (
    ROOT / "inbox/jay/20261021-experiments/EXP-MAP.md",
    ROOT / "inbox/jay/20261019-design/SCHEDULE-NOW.md",
    ROOT / "inbox/jay/20261019-design/DECISION-SYNC.md",
    ROOT / "inbox/jay/20261019-design/AGENDA-LEAD.md",
)
LAB = Path("C:/Users/AI-WS01/s2_lab/lab_status/index.html")


def put(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def update() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    t, w = data["training"], data["windows"]
    assert w["m1950"]["state"] == w["m2000"]["state"] == "MAINTAIN_FAIL"
    assert data["window_decision"] == "HOLD" and data["checkpoint_pair_row6"] == "REVERT" and REPORT.is_file()
    status = (
        f"10/27 최종 기록 · EX-35 m{t['completed_iteration']} 학습 rc {t['exit_code']} · "
        f"m1950/m2000 {w['m2000']['state']} · 창 {data['window_decision']} · "
        f"{data['canonical']} 유지 · 해석 대기"
    )
    line = (
        "**EX-35 최종 판정**: [RESULT-EX35](../20261026-experiments/RESULT-EX35-1027.md)는 "
        f"학습 m{t['completed_iteration']} 종료(rc {t['exit_code']})와 "
        f"m1950·m2000의 `{w['m2000']['state']}` 두 건을 원자료에서 생성했다. "
        f"카드 §4b.6 선행 1·4행의 필수 칸·A11 판독이 미완이라 창은 `{data['window_decision']}`. "
        f"6행 `{data['checkpoint_pair_row6']}`는 조건부다. 정본 `{data['canonical']}` 유지, EX-35 연장 없음. "
        "독립 좌회전 Q는 부모보다 높아 전환 좌회전과 구별한다. 영상·보행 위상·저장본 추세 해석은 analyst·runner 분석 대기. "
        "GPU0 학습 작업은 02:48:13부터 종료, 다음 학습은 팀장 승인 대기. "
        "GPU1 평가 사슬의 복원 지도 경로는 별도 진행 중."
    )
    for path in DOCS:
        s = path.read_text(encoding="utf-8")
        s, count = re.subn(r"(?m)^> 상태:.*$", f"> 상태: {status}", s, count=1)
        assert count == 1
        s, count = re.subn(
            r"## 10/27 최종 · EX-35 결과 기록\n.*?(?=## 10/27 01시대)",
            f"## 10/27 최종 · EX-35 결과 기록\n\n- {line}\n\n",
            s,
            count=1,
            flags=re.S,
        )
        if count == 0:
            s = s.replace("## 10/27 01시대", f"## 10/27 최종 · EX-35 결과 기록\n\n- {line}\n\n## 10/27 01시대", 1)
        if path.name == "EXP-MAP.md":
            s, count = re.subn(
                r"(?m)^\| \[EX-35 S-B10 명령 S2a\].*$",
                f"| [EX-35 S-B10 명령 S2a](EXP-EX35-SB10-cmd-S2a.md) | S-B10 m{t['parent_iter']} 명령 S2a 첫 축 | 부모 sha256 `{t['parent_sha256']}` | 학습 m{t['completed_iteration']} rc {t['exit_code']}; m1950·m2000 `{w['m2000']['state']}`. 필수 칸·A11 미완으로 창 `{data['window_decision']}`, 연장 없음. 정본 {data['canonical']} | [RESULT-EX35](../20261026-experiments/RESULT-EX35-1027.md) · 카드 §4b.6 선행 행 · 해석 대기 |",
                s,
                count=1,
            )
            assert count == 1
        if path.name == "DECISION-SYNC.md":
            marker = "| [x] | 결정 8 ·"
            row = (
                f"| [x] | EX-35 저장본 판정과 창 보류 | 결과 전 카드 §4b.6 | "
                f"m1950·m2000 `{w['m2000']['state']}`. 선행 1·4행 미완으로 창 `{data['window_decision']}`, {data['canonical']} 유지. "
                "RESULT-EX35 생성기 원자료 해시 | 10/27 최종 절 | 10/27 최종 절 | "
                "문턱 불변 · EX-35 연장 없음 · 6행 REVERT는 조건부 | 원자료와 [RESULT-EX35](../20261026-experiments/RESULT-EX35-1027.md) |\n"
            )
            s = re.sub(r"(?m)^\| \[x\] \| EX-35 최종 두 저장본 판정과 되돌림 \|.*\n", "", s, count=1)
            if row not in s:
                assert marker in s
                s = s.replace(marker, row + marker, 1)
        put(path, s)

    s = CARD.read_text(encoding="utf-8")
    s, count = re.subn(r"(?m)^> 상태:.*$", f"> 상태: {status}", s, count=1)
    assert count == 1
    note = (
        f"10/27 최종 운영 기록: [RESULT-EX35](../20261026-experiments/RESULT-EX35-1027.md)의 "
        f"m1950·m2000 정답 지도 판정은 둘 다 `{w['m2000']['state']}`. "
        f"§4b.6 선행 1·4행의 필수 칸·A11 미완으로 창 판정은 `{data['window_decision']}`다. "
        f"6행 `{data['checkpoint_pair_row6']}`는 조건부이며 정본 `{data['canonical']}` 유지, 연장 없음. "
        "독립 좌회전은 부모 대비 상승했고 전환 좌회전과 구별한다. 영상·보행 위상·저장본 추세 해석은 미완이다. 결과 전 문턱은 수정하지 않았다."
    )
    s, note_count = re.subn(r"(?m)^10/27 최종 운영 기록:.*$", note, s)
    if note_count == 0:
        s = s.replace("## 7. 결과\n", f"## 7. 결과\n\n{note}\n\n", 1)
        s = s.replace("## 결과\n", f"## 결과\n\n{note}\n\n", 1)
    s = s.replace("현재 선택은 결과 전 카드의 REVERT 갈래다. 아래 조건부 계획은 이 실행에서 승인되지 않았다.", "현재 창 판정은 HOLD이고 연장하지 않는다. 아래 조건부 계획은 이 실행에서 승인되지 않았다.")
    if "현재 창 판정은 HOLD이고" not in s:
        s = s.replace("## 8. 다음\n", "## 8. 다음\n\n현재 창 판정은 HOLD이고 연장하지 않는다. 아래 조건부 계획은 이 실행에서 승인되지 않았다.\n\n", 1)
    if "이전 01시대 기록: 당시 m2001 최종 결과 미완료." not in s:
        s = s.replace("m2001 최종 결과 미완료.", "이전 01시대 기록: 당시 m2001 최종 결과 미완료.", 1)
    if "이전 01시대 기록: 당시 m2001 결과와 최종 판정은 미완료." not in s:
        s = s.replace("m2001 결과와 최종 판정은 미완료.", "이전 01시대 기록: 당시 m2001 결과와 최종 판정은 미완료.", 1)
    put(CARD, s)

    lab = LAB.read_text(encoding="utf-8")
    lab = lab.replace("마지막 직접 대조 <b>10/27 01:52 KST</b>", "마지막 원자료 대조 <b>10/27 03:14 KST</b>")
    lab = lab.replace("마지막 원자료 대조 <b>10/27 03:14 KST</b>", "마지막 원자료 대조 <b>10/27 03:27 KST</b>")
    decision_section = (
        '<section class="decide">\n'
        '  <h2>팀장이 정할 것 · 10/27 03:27 KST</h2>\n'
        '  <p>EX-35 저장본 판정 m1950 · m2000 MAINTAIN_FAIL. 창 판정은 필수 칸 결측과 A11 영상 미판독으로 보류, 연장 없음. mai-os PR #61은 02:10:59 병합 확인.</p>\n'
        '  <div class="row"><div class="k">1 · 촬영 GPU 규칙</div><div>촬영 GPU 규칙 확대 여부를 팀장이 결정.</div></div>\n'
        '  <div class="row"><div class="k">2 · 단계 길이</div><div>최소 500 · 예산 1500 · 성과 조기 넘김의 관계를 팀장이 결정.</div></div>\n'
        '  <div class="row"><div class="k">3 · 다음 판 방향</div><div>분석과 영상 판독 뒤 다음 판 방향을 팀장이 결정.</div></div>\n'
        '</section>'
    )
    lab, count = re.subn(r'<section class="decide">.*?</section>', decision_section, lab, count=1, flags=re.S)
    assert count == 1
    lab, count = re.subn(
        r'<div class="row"><div class="k">GPU0</div><div>.*?</div></div>',
        '<div class="row"><div class="k">GPU0</div><div><span class="pill done">학습 종료</span>EX-35 m2000 rc 0. 02:48:13부터 학습 작업 없음. 새 학습은 팀장 승인 대기.</div></div>',
        lab,
        count=1,
    )
    assert count == 1
    lab, count = re.subn(
        r'<div class="row"><div class="k">GPU1</div><div>.*?</div></div>',
        '<div class="row"><div class="k">GPU1</div><div><span class="pill wait">평가</span>EX-35 평가 사슬 진행 중. m2000 정답 지도 판정 MAINTAIN_FAIL은 확인, 복원 지도 경로와 영상은 별도 진행·미확인.</div></div>',
        lab,
        count=1,
    )
    assert count == 1
    put(LAB, lab)


if __name__ == "__main__":
    update()
