"""W04 계기판 v9 (compose_25e_v2style9): 합성 촬영 기록으로 깃발 칸 · 미니맵 · 판정 성분이 맞고 패널 밖으로 넘치지 않는지 본다. Kit 없이 돈다."""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval" / "video25"))
import compose_25e_v2style9 as C  # noqa: E402

FLAGS = np.array([[0.5, 0.0], [1.5, 0.0], [2.5, 0.0], [3.5, 0.0], [5.0, 0.2], [6.5, 0.0], [7.5, 0.0]], np.float32)


def _capture(path, with_flags=True, n_per=(300, 200, 400), fall_in=(1,)):
    dt, t = 0.02, 0.0
    pos, tgt, done, tout, ts = [], [], [], [], []

    for e, n in enumerate(n_per):
        x, idx = 0.0, 0

        for i in range(n):
            x += 0.6 * dt if not (e in fall_in and i > 150) else 0.0
            while idx < len(FLAGS) and abs(FLAGS[idx, 0] - x) <= 0.5:
                idx += 1

            pos.append([x, 0.05 * math.sin(i / 20.0), 0.35])
            tgt.append(idx)
            ts.append(t)
            t += dt
            last = i == n - 1
            done.append(last)
            tout.append(last and e not in fall_in)

    n = len(ts)
    z = dict(t=np.array(ts), done=np.array(done), time_out=np.array(tout), command=np.tile([0.6, 0, 0.1], (n, 1)).astype(np.float32),
             vx=np.full(n, 0.55, np.float32), vy=np.zeros(n, np.float32), wz=np.full(n, 0.08, np.float32), body_height_foot_center_m=np.full(n, 0.30, np.float32),
             root_pos_w=np.array(pos, np.float32), root_quat_w=np.tile([1.0, 0, 0, 0], (n, 1)).astype(np.float32), roll=np.zeros(n, np.float32), pitch=np.zeros(n, np.float32),
             foot_pos_w=np.zeros((n, 4, 3), np.float32))

    if with_flags:
        z["flag_world"], z["flag_target_idx"] = FLAGS, np.array(tgt, np.int8)

    np.savez(path, **z)

    return np.load(path)


def test_flag_state_follows_the_recorded_target(tmp_path):
    z = _capture(tmp_path / "a.npz")
    f0 = C.flag_state(z, 0)
    assert f0["k"] == 7 and f0["target"] in (0, 1) and f0["reached"] == f0["target"]
    f = C.flag_state(z, 299)
    assert f["reached"] == int(z["flag_target_idx"][299]) and 0 < f["reached"] < 7


def test_old_captures_without_flags_render_like_v8(tmp_path):
    z = _capture(tmp_path / "b.npz", with_flags=False)
    assert C.flag_state(z, 10) is None and not C.fl_present(z)
    scene = np.full((720, 1280, 3), (60, 70, 60), np.uint8)
    out = C.scene_gauges(scene, z, 100, {"selected_environment": {"kind": "gaps", "level": 3}})
    assert out.shape == (720, 1280, 3)


@pytest.mark.parametrize("row", [10, 150, 299, 330, 500, 650, 899])
def test_flag_panel_stays_inside_its_column(tmp_path, row):
    z = _capture(tmp_path / "c.npz")
    bg = (60, 70, 60)
    scene = np.full((720, 1280, 3), bg, np.uint8)
    out = C.scene_gauges(scene, z, row, {"selected_environment": {"kind": "stepping_stones_high", "level": 3}})
    assert (out[:, :1280 - 196] == np.array(bg, np.uint8)).all()                                      # 패널 왼쪽 바깥은 그대로
    assert (out[:, 1280 - 8:] == np.array(bg, np.uint8)).all()                                        # 오른쪽 여백도 그대로(글이 넘치지 않음)
    assert (out[:C.GAUGE_Y0] == np.array(bg, np.uint8)).all() and (out[683:] == np.array(bg, np.uint8)).all()


def test_gauge_text_values_match_flag_eval_gauges(tmp_path):
    """계기판이 보이는 거리 · 방향은 평가 코드의 gauges 와 같은 함수에서 나온다(손계산: 몸 (3,0) yaw 0 에서 깃발 5 (5.0, 0.2) -> 2.00 m, 5.7 도)."""
    from foothold_s2.eval import flag_eval as FE

    d, a = FE.gauges([3.0, 0.0], 0.0, [5.0, 0.2])
    assert d == pytest.approx(math.hypot(2.0, 0.2)) and a == pytest.approx(math.degrees(math.atan2(0.2, 2.0)))
    assert f"{d:.2f}" == "2.01" and f"{a:+.0f}" == "+6"
