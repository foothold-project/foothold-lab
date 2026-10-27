"""Known-input and mutation checks for EX-35 status entries."""

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).with_name("lab_ex35_results.py")
SPEC = importlib.util.spec_from_file_location("lab_ex35_results", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_real_sources_make_six_newest_first_entries_and_three_decisions():
    data, agenda, result, a11 = MODULE.load_sources()
    cards = MODULE.render_cards(data, agenda, result, a11)
    decisions = MODULE.render_decisions(data, agenda)
    assert cards.count('class="card ex35-recent"') == 8
    assert cards.index("05:5x") < cards.index("05:19") < cards.index("05:1x")
    assert cards.index("05:1x") < cards.index("05:0x") < cards.index("04시대") < cards.index("02:48:13")
    for phrase in ("m1950", "m2000", "MAINTAIN_FAIL", "STOP 4행", "STOP 6행", "27개", 'href="file:///'):
        assert phrase in cards
    assert decisions.count('class="row"') == 3
    assert "촬영 GPU 규칙 확대" not in decisions
    assert "GATE-v2" in decisions and "되돌림 판" in decisions and "다음 판 방향" in decisions


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
    assert twice.count('class="card ex35-recent"') == 8
    assert "old history" in twice and "old1" not in twice


def test_wrong_result_or_a11_fails_closed():
    data, agenda, result, a11 = MODULE.load_sources()
    try:
        MODULE.render_cards(data, agenda, result.replace("> 판: v1.4", "> 판: v1.3"), a11)
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


def test_each_item_has_its_own_evidence_and_registered_axes():
    data, agenda, result, a11 = MODULE.load_sources()
    cards = MODULE.render_cards(data, agenda, result, a11)
    import re

    parts = re.findall(r'<div class="card ex35-recent">(.*?)</div>', cards, flags=re.S)
    assert len(parts) == 8
    assert "jobs_remaining.json" in parts[0] and "compose_jobs.json" in parts[0]
    assert all(name in parts[0] for name in (
        "CMP_S-B10-m1500_vs_EX-35-m2000", "EX-35-m2000_rough", "S-B10-m1500_rough"
    ))
    assert "ex35_repro_turn16\\compare.md" in parts[1] and "ex35_turn16_repeat.png" in parts[1]
    assert "a11_m2000.json" in parts[2] and "ex35-a1-m2000" in parts[2]
    assert "ex35_repro_x27k\\compare.md" in parts[3]
    assert "window_m2000_default.json" in parts[4]
    assert "GATE-v2-performance-promotion.md" in parts[5]
    assert "VERIFY-verifier-GATE-v2-statistics.md" in parts[5]
    assert "VERIFY-analyst-GATE-v2.md" in parts[5]
    assert "EXP-EX35-SB10-cmd-S2a.md" in parts[7]
    assert all(f"A{i} " in parts[7] for i in range(1, 13))
    assert "75%" in parts[7] and "2.5% + 2.5%" in parts[7] and "500회" in parts[7]
    assert "ex35_turn16_repeat.png" not in parts[2] + parts[3] + parts[4] + parts[5] + parts[6] + parts[7]


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
