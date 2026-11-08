"""Known-input check of the EXP-MAP summary insertion."""

from sync_result_v15 import MARKER, sync


def test_sync_is_repeatable_and_uses_measured_values():
    data = {"terrain_compare": {"rows": [
        {"mode": "켬", "command": "fwd1.0", "parent_median_m": 1.0,
        "child_median_m": 1.2, "measured": True} for _ in range(21)
    ] + [{"mode": "가림", "command": "fwd0.5", "measured": True} for _ in range(77)]
      + [{"mode": "복원", "command": "fwd0.5", "measured": False} for _ in range(28)],
        "repeat": {"earlier_alive": 8, "current_alive": 12, "n": 12}}}
    source = "## 10/27 최종 · EX-35 결과 기록\n\n- [RESULT-EX35 v1.4](x)\n"
    one = sync(source, data)
    assert sync(one, data) == one
    assert one.count(MARKER) == 1 and "126행 중 98행" in one and "0.20~0.20 m" in one
    assert "RESULT-EX35 v1.4" not in one
