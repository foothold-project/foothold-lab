"""Known-input and mutation checks for the six EX-35 status entries."""

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
    assert cards.count('class="card ex35-recent"') == 6
    assert cards.index("05:5x") < cards.index("05:19") < cards.index("05:1x")
    assert cards.index("05:1x") < cards.index("05:0x") < cards.index("04시대") < cards.index("02:48:13")
    for phrase in ("m1950", "m2000", "MAINTAIN_FAIL", "STOP 4행", "STOP 6행", "27개", "그림 C:", "영상 C:", "표 C:"):
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
    assert twice.count('class="card ex35-recent"') == 6
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
