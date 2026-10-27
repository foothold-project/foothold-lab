"""Known-input and mutation checks for EX-35 status entries."""

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).with_name("lab_ex35_results.py")
SPEC = importlib.util.spec_from_file_location("lab_ex35_results", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_real_sources_make_newest_first_entries_and_eight_decisions():
    data, agenda, result, a11 = MODULE.load_sources()
    cards = MODULE.render_cards(data, agenda, result, a11)
    decisions = MODULE.render_decisions(data, agenda)
    assert cards.count('class="card ex35-recent"') == 11
    assert cards.index("복원 지도 셋 진행 상태") < cards.index("지형 레벨 평가 결정") < cards.index("영상 제작 상태")
    assert "L0~2 · L3 · L6 · L9" in cards and "L3 미측" in cards
    assert "7b1ad9fe" in cards and "해석 미완" in cards
    assert "753f9b08, GPU 미실행" in cards and "복원 지도 모드 영상 미착수" in cards
    assert cards.index("05:5x") < cards.index("05:19") < cards.index("05:1x")
    assert cards.index("05:1x") < cards.index("05:0x") < cards.index("04시대") < cards.index("02:48:13")
    for phrase in ("m1950", "m2000", "MAINTAIN_FAIL", "STOP 4행", "STOP 6행", "27개", 'href="videos/'):
        assert phrase in cards
    assert decisions.count('class="row"') == 8
    assert "촬영 GPU 규칙 확대" not in decisions
    for phrase in (
        "GATE-v2 일곱", "S-B10 m1500 되돌림 판 기동 여부", "다음 판 방향",
        "듬성 지형 깃발 평가 진행 여부", "실험 순서 v2", "PID 147032 재시작 승인",
        "주기마다 모듈을 다시 읽게 고칠지", "77388 종료 소급 승인",
    ):
        assert phrase in decisions
    assert decisions.count("AGENDA-LEAD.md 10/27 12:1x") == 8


def test_repeat_render_replaces_cards_and_decisions_without_duplication():
    data, agenda, result, a11 = MODULE.load_sources()
    cards = MODULE.render_cards(data, agenda, result, a11)
    decisions = MODULE.render_decisions(data, agenda)
    page = (
        '<section class="decide"><h2>팀장이 정할 것 · OLD</h2><p>판정 요약</p>'
        + '<div class="row">old1</div>' * 3
        + '</section><section><h2>새 결과 (최신이 위)</h2><div class="card">old history</div></section>'
    )
    once = MODULE.render_page(page, cards, decisions)
    twice = MODULE.render_page(once, cards, decisions)
    assert once == twice
    assert twice.count(MODULE.START) == 1 and twice.count(MODULE.END) == 1
    assert twice.count('class="card ex35-recent"') == 11
    assert "old history" in twice and "old1" not in twice


def test_wrong_result_or_a11_fails_closed():
    data, agenda, result, a11 = MODULE.load_sources()
    try:
        MODULE.render_cards(data, agenda, result.replace("> 판: v1.5", "> 판: v1.4"), a11)
    except ValueError as exc:
        assert "seal" in str(exc)
    else:
        raise AssertionError("wrong result version accepted")
    changed = dict(a11)
    changed["items"] = dict(a11["items"], **{"1": "있음"})
    try:
        MODULE.render_cards(data, agenda, result, changed)
    except ValueError as exc:
        assert "A11" in str(exc)
    else:
        raise AssertionError("A11 mutation accepted")
    try:
        MODULE.render_decisions(data, agenda.replace("  - (7) 갱신기가 주기마다", "  - (9) 갱신기가 주기마다"))
    except ValueError as exc:
        assert "eight decisions incomplete" in str(exc)
    else:
        raise AssertionError("missing seventh decision accepted")


def test_each_item_has_its_own_evidence_and_registered_axes():
    data, agenda, result, a11 = MODULE.load_sources()
    cards = MODULE.render_cards(data, agenda, result, a11)
    import re

    parts = re.findall(r'<div class="card ex35-recent">(.*?)</div>', cards, flags=re.S)
    assert len(parts) == 11
    assert "reconstruction_loss_s-b10_ex35.png" in parts[0]
    assert "RULES-HUB.md" in parts[0] and "RULES-HUB.md" in parts[1]
    assert "jobs_remaining.json" in parts[2] and "compose_jobs.json" in parts[2]
    assert re.search(r"10/27 \d\d:\d\d KST · 영상 제작 상태", parts[2])
    assert "sparse18 4편은 제작됐으나 납품 보류" in parts[2]
    assert "3.78초부터 몸통 z&lt;0.25 m" in parts[2]
    assert "4.86초 네 발 z&lt;0 m" in parts[2]
    assert "review_feet.npz" in parts[2] and "frame_check.csv" in parts[2]
    assert "듬성 성공 · 실패 촬영 0건 미완" not in parts[2]
    assert 'href="file:///' not in cards
    assert all(name in parts[2] for name in (
        "CMP_S-B10-m1500_vs_EX-35-m2000", "EX-35-m2000_rough", "S-B10-m1500_rough"
    ))
    assert "같은 조건 지형별 부모 대조" in parts[3] and "env_arrays_probe_prop_only_fwd1.0.npz" in parts[3]
    assert "ex35_repro_turn16\\compare.md" in parts[4] and "ex35_turn16_repeat.png" in parts[4]
    assert "a11_m2000.json" in parts[5] and "ex35-a1-m2000" in parts[5]
    assert "ex35_repro_x27k\\compare.md" in parts[6]
    assert "window_m2000_default.json" in parts[7]
    assert "GATE-v2-performance-promotion.md" in parts[8]
    assert "VERIFY-verifier-GATE-v2-statistics.md" in parts[8]
    assert "VERIFY-analyst-GATE-v2.md" in parts[8]
    assert "EXP-EX35-SB10-cmd-S2a.md" in parts[10]
    assert all(f"A{i} " in parts[10] for i in range(1, 13))
    assert "75%" in parts[10] and "2.5% + 2.5%" in parts[10] and "500회" in parts[10]
    assert "ex35_turn16_repeat.png" not in "".join(parts[5:])


def test_design_distribution_or_media_completion_change_needs_review(monkeypatch, tmp_path):
    import lab_ex35_additions as additions

    original = additions.CARD
    class ChangedCard:
        def read_text(self, **kwargs):
            return original.read_text(**kwargs).replace("**75 %**", "**74 %**", 1)
    monkeypatch.setattr(additions, "CARD", ChangedCard())
    try:
        additions.design_card()
    except ValueError as exc:
        assert "distribution" in str(exc)
    else:
        raise AssertionError("changed distribution accepted")
    monkeypatch.setattr(additions, "CARD", original)
    changed_state = tmp_path / "state.json"
    changed_state.write_text('{"completed": ["capture-02"]}', encoding="utf-8")
    monkeypatch.setattr(additions, "STATE", changed_state)
    assert "대기열 상태와 영수증 수가 달라 확인 필요" in additions.video_card()


def test_sparse_physical_receipt_known_input_and_mutation(tmp_path):
    import numpy as np
    import pytest
    import lab_ex35_additions as additions

    path = tmp_path / "review_feet.npz"
    t = np.array([0.0, 3.78, 4.86])
    root = np.zeros((3, 3), dtype=np.float32)
    root[:, 2] = [0.40, 0.24, -0.01]
    feet = np.zeros((3, 4, 3), dtype=np.float32)
    feet[-1, :, 2] = [-0.27, -0.26, -0.25, -0.15]
    np.savez(path, t=t, root_pos_w=root, foot_pos_w=feet)
    assert additions.sparse_crossed_record(path) == (3.78, 4.86)
    feet[-1, -1, 2] = 0.01
    np.savez(path, t=t, root_pos_w=root, foot_pos_w=feet)
    with pytest.raises(ValueError, match="four-feet"):
        additions.sparse_crossed_record(path)
