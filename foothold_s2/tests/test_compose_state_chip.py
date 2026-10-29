"""D51 (lead 17:5x): 상태 칩은 0.3 s 창 평균 + 문턱 둘(시작 0.20 · 멈춤 0.10)로 깜빡이지 않고, 명령 불이행은 따로 보이며, 머리줄 지도 표기는 한 형식."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

COMPOSER = Path(__file__).resolve().parents[1] / "eval/video25/compose_25e_v2style10.py"
FIRST = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/d51_capture/ex36a_m3000/EX36A-basic-pyramid_stairs_L1_env23-m3000-fwd_back_eval_pred-1x/review_feet.npz")


def _c():
    spec = importlib.util.spec_from_file_location("compose_v10_chip_test", COMPOSER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _flips(seq):
    return sum(1 for a, b in zip(seq, seq[1:]) if a != b)


def test_speed_wobbling_around_the_old_threshold_does_not_flicker():
    c = _c()
    n = 200
    rng = np.random.default_rng(0)
    vx = 0.15 + 0.04 * np.sin(np.arange(n) * 0.9) + rng.normal(0, 0.01, n)   # 0.11~0.19 근처에서 흔들림
    old = ["move" if v > 0.15 else "stand" for v in vx]
    new = c.motion_states(vx, np.zeros(n), np.zeros(n), np.zeros((n, 3)), 0.02)
    assert _flips(old) >= 8 and _flips(new) <= 2


def test_commanded_but_stopped_is_stalled_not_standing():
    c = _c()
    n = 60
    zero = np.zeros(n)
    asked = np.tile([1.0, 0.0, 0.0], (n, 1))
    idle = np.zeros((n, 3))
    assert set(c.motion_states(zero, zero, zero, asked, 0.02)) == {"stalled"}
    assert set(c.motion_states(zero, zero, zero, idle, 0.02)) == {"stand"}
    spin = np.full(n, 1.0)
    assert set(c.motion_states(zero, zero, spin, np.tile([0, 0, 1.2], (n, 1)), 0.02)[20:]) == {"spin"}


@pytest.mark.skipif(not FIRST.is_file(), reason="첫 편 촬영 산출이 없다")
def test_first_clip_back10_segment_no_longer_blinks():
    c = _c()
    z = np.load(FIRST)
    t = z["t"]
    m = (t >= 12.0)   # back1.0 구간(구간 3.0 s x 5 중 마지막)
    vx, wz = z["vx"], z["wz"]
    vy = z["vy"] if "vy" in z.files else np.zeros_like(vx)
    old = ["move" if np.hypot(a, b) > 0.15 else "other" for a, b in zip(vx[m], vy[m])]
    new = c.motion_states(vx, vy, wz, z["command"], float(z["dt"]))
    assert _flips(old) >= 5
    assert _flips(new[int(np.argmax(m)):]) <= 2


@pytest.mark.parametrize("mode,want", [("eval_pred", "복원 지도 (eval_pred)"), ("eval_gt", "정답 지도 (eval_gt)"), ("none", "지도 없음 (none)")])
def test_header_map_label_is_one_format(mode, want):
    assert _c().policy_map_header({"map_modes": {"map_mode": {"requested": mode}}}) == want
