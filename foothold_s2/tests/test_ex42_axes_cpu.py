"""EX-42 새 학습 축 표 (ex42_axes) CPU 시험: 합성 배열로 식을 확인한다 (Kit 없이)."""
import numpy as np
import pytest

from foothold_s2.eval import ex42_axes as ax
from foothold_s2.eval.ex42_axes_run import pick_kinds


def _flat(h=0.0):
    return np.full((1, 6, 6), h, dtype=np.float64)


def test_hole_mask_finds_a_pit_not_a_step_edge():
    g = _flat()
    g[0, 3, 3] = -0.3                        # 양옆이 0.3 높은 구멍
    m = ax.hole_mask(g)
    assert m[0, 3, 3] and m.sum() == 1
    step = _flat()
    step[0, :, 3:] = 0.3                     # 계단 모서리: 한쪽만 높다
    assert not ax.hole_mask(step).any()


def test_hole_stats_counts_missed_and_false():
    gt = _flat(); gt[0, 3, 3] = -0.3
    perfect = ax.hole_stats(gt.copy(), gt)
    assert perfect[0, 0] == 1 and perfect[0, 1] == 0
    filled = gt.copy(); filled[0, 3, 3] = 0.0   # 구멍을 메워 버린 복원: 놓침
    s = ax.hole_stats(filled, gt)
    assert s[0, 0] == 1 and s[0, 1] == 1
    ghost = gt.copy(); ghost[0, 1, 1] = -0.3     # 없는 구멍을 만든 복원
    s = ax.hole_stats(ghost, gt)
    assert s[0, 3] == 1


def test_hole_summary_none_without_holes_and_alive_mask():
    stats = np.zeros((2, 1, 6)); stats[:, 0, 0] = 1; stats[:, 0, 1] = 1; stats[:, 0, 2] = 10
    assert ax.hole_summary(stats, np.ones((2, 1), bool))["missed_hole_frac"] == 1.0
    assert ax.hole_summary(stats, np.zeros((2, 1), bool))["missed_hole_frac"] is None   # 살아 있는 step 이 없으면 값 없음
    with pytest.raises(ValueError):
        ax.hole_summary(stats, np.ones((3, 1), bool))


def test_keep_cell_ok_and_off():
    t = np.zeros((300, 4, 3)); t[:, :, 0] = 0.1; t[:, 3, 0] = 0.02   # env 3 은 못 간다
    c = ax.keep_cell(t, np.array([0.1, 0.0]))
    assert c["ok"] == 3 and c["axis"] == 0
    side = np.zeros((300, 2, 3)); side[:, :, 1] = -0.2
    assert ax.keep_cell(side, np.array([0.0, -0.2]))["ok"] == 2


def test_slope_fit_recovers_known_slope_and_offset():
    rng = np.random.default_rng(0)
    true = rng.uniform(0.0, 0.3, size=(300, 40)).mean(0) * 0 + np.linspace(0.02, 0.3, 40)
    t = np.tile(true, (300, 1)); e = 0.7 * t + 0.01
    fit = ax.slope_fit([t], [e])
    assert fit["slope"] == pytest.approx(0.7, abs=1e-6) and fit["intercept"] == pytest.approx(0.01, abs=1e-6)
    flat = np.tile(np.full(40, 0.1), (300, 1))
    assert ax.slope_fit([flat], [flat])["slope"] is None          # 실제 값이 안 퍼지면 값 없음


def test_kind_counts_separates_reached_survived_fell():
    S, N, dt = 100, 4, 0.1
    x = np.zeros((S, N)); x[:, 0] = np.linspace(0, 5, S); x[:, 1] = np.linspace(0, 1, S)
    x[:, 2] = np.linspace(0, 5, S); x[:, 3] = 0.0
    alive = np.ones((S, N), bool); alive[50:, 2] = False             # env 2 는 도달 뒤 중간에 넘어짐 (도달 5 m 는 끝에서)
    arr = {"alive": alive, "root_x_local_m": x, "root_y_local_m": np.zeros((S, N)), "dt": np.array(dt)}
    out = ax.kind_counts(arr, None, settle_s=1.0, envs=N)
    assert out["survived"] == 3 and out["fell"] == 1 and out["reached"] is None and out["completed"] is None
    assert out["stalled_frac"] == pytest.approx(1 / 3)               # 산 셋 (5 m · 1 m · 0 m) 가운데 0.25 m 미만은 하나
    anchor = {"forward_x_m": 4.0, "kind": "x", "level": 1, "family": "B", "method": "t"}
    out = ax.kind_counts(arr, anchor, settle_s=1.0, envs=N)
    assert out["reached"] is not None and out["reached"] >= out["completed"]


def test_continuous_counts_and_format_line_runs():
    S, N = 20, 3
    alive = np.ones((S, N), bool); alive[10:, 1] = False
    x = np.tile(np.linspace(0, 2, S)[:, None], (1, N))
    c = ax.continuous_counts({"alive": alive, "root_x_local_m": x, "root_y_local_m": np.zeros((S, N))}, envs=N)
    assert c["survived"] == 2 and c["mean_forward_m"] < 2.0
    row = {"continuous": {"kind": "A/random_rough", "level": 5, "gt": c, "pred": c}, "slope": {"gt": {"slope": 0.7, "intercept": 0.0}, "pred": {}}}
    line = ax.format_line(50, row)
    assert line.startswith("m50") and "\u2014" not in line and "0.70|-" in line


def test_pick_kinds_rotates_and_caps():
    opened = {"A/a": 1, "A/b": 1, "A/c": 1}
    assert list(pick_kinds(opened, 50, 2)) == ["A/a", "A/b"]
    assert list(pick_kinds(opened, 100, 2)) == ["A/c", "A/a"]
    assert pick_kinds({}, 50, 2) == {} and len(pick_kinds(opened, 50, 9)) == 3


def test_kind_counts_is_direction_free():
    """시작 방향이 무작위여도 뒤로 걸은 env 를 멈춘 것으로 세지 않는다 (m50 에서 +x 전진이 -3 ~ +3 m 로 퍼진 것을 본 뒤)."""
    S, N = 100, 2
    x = np.zeros((S, N)); x[:, 0] = np.linspace(0, -3, S)       # env 0 은 뒤로 3 m
    out = ax.kind_counts({"alive": np.ones((S, N), bool), "root_x_local_m": x, "root_y_local_m": np.zeros((S, N)), "dt": np.array(0.1)}, None, settle_s=1.0, envs=N)
    assert out["stalled_frac"] == pytest.approx(0.5) and out["mean_forward_speed"] == pytest.approx(0.15)
