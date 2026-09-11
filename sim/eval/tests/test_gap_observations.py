"""평가 규격 2 의 핵심 한 줄을 못 박는다. `sim/eval/gap_observations.py`.

    python -m unittest discover -s sim/eval/tests -v

## 왜 이 파일이 있나

우리 평가 결과 전체가 **한 값**에 걸려 있습니다. 바닥 없는 지형에서 광선이
아무것도 못 맞혔을 때 관측에 무엇을 넣느냐입니다.

| 넣는 값 | 로봇이 읽는 뜻 | 규격 |
|---|---|---|
| `+1` | 바닥이 아래로 멀다 = **구멍** | 2 (학습과 같다 · 기본값) |
| `-1` | 내 몸통보다 높이 솟았다 = **벽** | 1 (결함) |

이것 하나로 `gap` 성공률이 6 % 에서 100 % 로 바뀝니다. 그런데
2026-09-11 까지 이 함수에는 **시험이 하나도 없었습니다.** Isaac 을 띄워야만
불러지는 구조라 시험 모음에 넣을 수가 없었기 때문입니다.

`gap_observations.py` 의 `isaaclab` 임포트를 이름표 전용으로 바꿔서 이제
여기서 돕니다. 계산은 torch 뿐입니다.

## 여기서 지키는 것

| 시험 | 막는 사고 |
|---|---|
| 기본값이 +1.0 | 아무도 모르게 기본이 규격 1 로 되돌아가는 것 |
| 빗나간 광선 | 못 맞힌 자리에 -inf 나 0 이 들어가는 것 |
| 맞힌 광선 | 규격을 고치면서 멀쩡하던 계산까지 바꾸는 것 |
| NaN | 이상한 값이 조용히 통과하는 것 |
"""

import os
import sys
import unittest

# torch 와 Isaac 이 각자 OpenMP 를 들고 와서 부딪힌다. torch 를 부르기 «전»에
# 둬야 한다. 이 줄이 없으면 시험이 아니라 인터프리터가 죽는다.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(HERE)

if EVAL_DIR not in sys.path:
    sys.path.insert(0, EVAL_DIR)

try:
    import torch

    import gap_observations
except ImportError:  # pragma: no cover
    torch = None
    gap_observations = None


class _Box(object):
    """아무 속성이나 담는 그릇."""


def fake_env(ray_z, base_z=0.8):
    """광선이 닿은 높이 목록으로 가짜 환경 하나.

    `ray_z` 에 `inf` 를 넣으면 「아무것도 못 맞혔다」입니다. RayCaster 가
    못 맞힌 자리를 그렇게 남깁니다.
    """
    sensor = _Box()
    sensor.data = _Box()
    sensor.data.ray_hits_w = torch.tensor([[[0.0, 0.0, z] for z in ray_z]])
    sensor.data.pos_w = torch.tensor([[0.0, 0.0, base_z]])

    env = _Box()
    env.scene = _Box()
    env.scene.sensors = {"height_scanner": sensor}

    return env


class _Cfg(object):
    name = "height_scanner"


@unittest.skipIf(gap_observations is None, "torch 가 없습니다")
class MissValueTest(unittest.TestCase):
    """빗나간 광선에 무엇이 들어가는가."""

    def scan(self, ray_z, base_z=0.8, **kwargs):
        out = gap_observations.height_scan_with_gap(
            fake_env(ray_z, base_z), _Cfg(), **kwargs)
        return [round(float(v), 6) for v in out[0]]

    def test_기본값은_규격_2_다(self):
        """**부르는 쪽이 아무 말 안 해도 +1.0 이어야 한다.**

        `git pull origin main` 만 받은 사람이 그냥 돌렸을 때 나오는 값입니다.
        여기가 뒤집히면 우리 성적표 전체가 다른 규격이 됩니다.
        """
        import inspect

        default = inspect.signature(
            gap_observations.height_scan_with_gap).parameters["miss_value"].default

        self.assertEqual(default, 1.0)

    def test_못_맞힌_광선은_구멍이다(self):
        # 몸통 0.8 · offset 0.5. 가운데 광선만 빗나갔다.
        self.assertEqual(self.scan([0.0, float("inf"), -0.2]), [0.3, 1.0, 0.5])

    def test_맞힌_광선은_기본_함수와_같은_식이다(self):
        """규격을 고치면서 멀쩡하던 계산까지 바꾸지 않았는가.

        `몸통높이 - 닿은높이 - offset` 입니다.
        """
        self.assertEqual(self.scan([0.0, 0.3, -0.2]), [0.3, 0.0, 0.5])
        self.assertEqual(self.scan([0.0], base_z=1.0), [0.5])

    def test_offset_을_따른다(self):
        self.assertEqual(self.scan([0.0], offset=0.0), [0.8])

    def test_NaN_도_빗나간_것으로_본다(self):
        """이상한 값을 조용히 통과시키지 않는다."""
        self.assertEqual(self.scan([float("nan"), 0.0]), [1.0, 0.3])

    def test_음의_무한도_잡는다(self):
        self.assertEqual(self.scan([float("-inf"), 0.0]), [1.0, 0.3])

    def test_규격_1_로도_부를_수_있다(self):
        """옛 결과를 재현할 때 쓴다. 그때만 쓴다."""
        self.assertEqual(self.scan([0.0, float("inf"), -0.2], miss_value=-1.0),
                         [0.3, -1.0, 0.5])

    def test_두_규격은_빗나간_자리에서만_다르다(self):
        """**이것이 「gap 만 영향받는다」의 근거다.**

        바닥이 있는 지형은 빗나가는 광선이 0개라 두 규격의 값이 글자 그대로
        같습니다. 빗나간 광선이 하나라도 있어야 달라집니다.
        """
        바닥이_다_있다 = [0.0, 0.3, -0.2, 0.1]

        self.assertEqual(self.scan(바닥이_다_있다),
                         self.scan(바닥이_다_있다, miss_value=-1.0))

        구멍이_있다 = [0.0, float("inf"), -0.2, 0.1]

        self.assertNotEqual(self.scan(구멍이_있다),
                            self.scan(구멍이_있다, miss_value=-1.0))

    def test_광선_수와_환경_수를_지킨다(self):
        out = gap_observations.height_scan_with_gap(
            fake_env([0.0, float("inf"), -0.2]), _Cfg())

        self.assertEqual(tuple(out.shape), (1, 3))


if __name__ == "__main__":
    unittest.main()
