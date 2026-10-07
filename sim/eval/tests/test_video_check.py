# -*- coding: utf-8 -*-
"""찍힌 영상 관문을 못 박는다. `sim/eval/video_check.py`.

    python -m unittest discover -s sim/eval/tests -v

## 막는 사고 `확인됨`

2026-09-20. `gap_vx0.5_H` 600 프레임이 **전부 검정**인데

- 종료 코드 0
- mp4 도 trace 도 만들어짐
- 물리는 정상 (전진 2.24 m · MAE 0.181)
- HUD 패스도 성공 (검은 화면에 계기를 곱게 그렸다)

그래서 「실패 0」으로 보고됐고 **배포본에 실려 팀장이 찾았다.**

신호는 있었다 · **33 KB · 55 바이트/프레임** (정상은 1600 ~ 2600) 이고
`record.log` 에 `hydra ... failed` 가 있었다. 둘 다 아무도 안 봤다.

여기서는 **검은 영상을 실제로 만들어 넣고 관문이 잡는지** 본다.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import video_check as vc  # noqa: E402

try:
    import imageio.v2 as imageio
    import numpy as np
    HAVE_IMAGEIO = True
except ImportError:  # pragma: no cover
    HAVE_IMAGEIO = False


def _write_video(path, luma, frames=30, size=(240, 320)):
    """밝기가 `luma` 로 균일한 mp4. 0 이면 완전한 검정이다."""
    data = np.full((size[0], size[1], 3), luma, dtype=np.uint8)

    with imageio.get_writer(path, fps=15, macro_block_size=None) as writer:
        for _ in range(frames):
            # 완전 균일하면 압축이 과하게 먹으므로 아주 작은 잡음을 준다.
            # 검은 영상도 실제로는 이렇게 나온다.
            noise = np.random.randint(0, 2, data.shape, dtype=np.uint8)
            writer.append_data(np.clip(data.astype(int) + noise, 0, 255)
                               .astype(np.uint8))


def _write_alternating(path, bright, dark_parity, frames=300, size=(240, 320)):
    """**한 걸러 한 장** 이 검은 mp4.

    `dark_parity` 가 0 이면 짝수 프레임이, 1 이면 홀수 프레임이 검다.
    2026-09-23 에 실제로 난 모양이다 (300 장 중 짝수 150 장이 검었다).
    """
    with imageio.get_writer(path, fps=50, macro_block_size=None) as writer:
        for i in range(frames):
            level = 0 if i % 2 == dark_parity else bright
            data = np.full((size[0], size[1], 3), level, dtype=np.uint8)
            noise = np.random.randint(0, 2, data.shape, dtype=np.uint8)
            writer.append_data(np.clip(data.astype(int) + noise, 0, 255)
                               .astype(np.uint8))


class RendererLogTest(unittest.TestCase):
    """로그 검사는 **imageio 없이도** 돈다."""

    def test_it_finds_the_line_that_was_actually_in_our_log(self):
        text = (
            "2026-09-20T12:03:02Z [Warning] [omni.hydra.rtx] "
            "HydraEngine rtx failed creating scene renderer.\n"
            "2026-09-20T12:03:02Z [Warning] [omni.usd] "
            "failed to add hydra engine - uid: 1024, name: 'rtx'\n"
            "그 밖 평범한 줄\n"
        )
        hits = vc.renderer_failed(text)

        self.assertEqual(len(hits), 2, hits)

    def test_a_clean_log_gives_nothing(self):
        self.assertEqual(vc.renderer_failed("잘 돌았다\n[PASS] 프레임 300 장\n"), [])


@unittest.skipUnless(HAVE_IMAGEIO, "imageio · numpy 가 없습니다")
class VerifyRenderTest(unittest.TestCase):

    def test_a_bright_video_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "ok.mp4")
            _write_video(p, 180)

            got = vc.verify_render(p, min_bytes_per_frame=1)

            self.assertGreater(got["mean_luma"], vc.MIN_MEAN_LUMA)

    def test_a_black_video_is_caught(self):
        """**이 시험이 이 파일의 이유다.**"""
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "black.mp4")
            _write_video(p, 0)

            with self.assertRaises(RuntimeError) as caught:
                vc.verify_render(p, min_bytes_per_frame=1)

            self.assertIn("검", str(caught.exception))

    def test_half_black_is_caught_whichever_parity(self):
        """**옛 표본 자리가 놓쳤을 쪽까지 본다.**

        300 프레임에서 옛 자리는 `[50,100,150,200,250]` 로 전부 짝수였다.
        그래서 «짝수» 가 검으면 잡히고 «홀수» 가 검으면 통과했다.
        이제 이웃 한 장을 더 보므로 어느 쪽이든 잡혀야 한다.
        """
        for parity, label in ((0, "짝수가 검음"), (1, "홀수가 검음")):
            with self.subTest(parity=label):
                with tempfile.TemporaryDirectory() as tmp:
                    p = os.path.join(tmp, "half.mp4")
                    _write_alternating(p, 180, parity)

                    with self.assertRaises(RuntimeError) as caught:
                        vc.verify_render(p, min_bytes_per_frame=1)

                    self.assertIn("한 걸러", str(caught.exception))

    def test_samples_cover_both_parities(self):
        """표본 자리가 한쪽 홀짝으로 쏠리면 위 시험이 «운으로» 통과한다.

        옛 자리는 300 프레임에서 전부 짝수였다. 그것이 사각이었다.
        """
        for count in (300, 299, 301, 600, 150, 1000):
            with self.subTest(frames=count):
                picks = vc.sample_indices(count, samples=5)
                self.assertEqual({i % 2 for i in picks}, {0, 1}, (count, picks))
                self.assertTrue(all(0 <= i < count for i in picks), picks)

    def test_unmeasured_luma_is_not_reported_as_measured(self):
        """**못 쟀다를 통과로 적지 않는다.**

        `imageio` 가 없는 자리에서는 밝기를 못 잰다. 그때 보고서가
        「쟀다」로 보이면 부르는 쪽이 `[PASS]` 를 찍는다. 실제로 찍고 있었다.
        """
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "half.mp4")
            _write_alternating(p, 180, 0, frames=60)

            saved = vc.luma_samples
            try:
                vc.luma_samples = lambda *a, **k: None
                got = vc.verify_render(p, min_bytes_per_frame=1)
            finally:
                vc.luma_samples = saved

            self.assertFalse(got["luma_measured"])
            self.assertIsNone(got["mean_luma"])
            self.assertIsNone(got["dark_sample_ratio"])

    def test_measured_luma_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "ok.mp4")
            _write_video(p, 180)

            got = vc.verify_render(p, min_bytes_per_frame=1)

            self.assertTrue(got["luma_measured"])
            self.assertEqual(got["dark_sample_ratio"], 0.0)

    def test_frame_count_mismatch_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "ok.mp4")
            _write_video(p, 180, frames=30)

            with self.assertRaises(RuntimeError) as caught:
                vc.verify_render(p, expected_frames=999, min_bytes_per_frame=1)

            self.assertIn("999", str(caught.exception))

    def test_renderer_log_kills_it_even_when_the_picture_is_fine(self):
        """**로그만으로도 죽인다.** 나머지 셋이 통과해도 원인은 로그에 있다."""
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "ok.mp4")
            _write_video(p, 180)

            log = os.path.join(tmp, "record.log")

            with open(log, "w", encoding="utf-8") as handle:
                handle.write("[Warning] [omni.hydra.rtx] "
                             "HydraEngine rtx failed creating scene renderer.\n")

            with self.assertRaises(RuntimeError) as caught:
                vc.verify_render(p, log_path=log, min_bytes_per_frame=1)

            self.assertIn("렌더러", str(caught.exception))

    def test_bytes_per_frame_floor_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "ok.mp4")
            _write_video(p, 180)

            with self.assertRaises(RuntimeError) as caught:
                vc.verify_render(p, min_bytes_per_frame=10 ** 9)

            self.assertIn("바이트/프레임", str(caught.exception))

    def test_missing_file_is_caught(self):
        with self.assertRaises(RuntimeError):
            vc.verify_render(os.path.join(tempfile.gettempdir(), "없다.mp4"))


class SplitAttemptsTest(unittest.TestCase):
    """**한 컷에 여러 시도가 들어간다.** `imageio` 없이도 돈다."""

    @staticmethod
    def _rows(spec):
        """(t, fwd, z, roll) 목록을 행 사전으로."""
        return [{"t_s": t, "fwd_m": f, "base_z_m": z, "roll_deg": r}
                for t, f, z, r in spec]

    def test_one_clean_run_is_one_attempt(self):
        rows = self._rows([(i * 0.02, i * 0.01, 0.30, 2.0) for i in range(100)])

        self.assertEqual(len(vc.split_attempts(rows)), 1)

    def test_a_forward_drop_splits(self):
        """전진이 한 프레임에 크게 줄면 리셋이다."""
        rows = self._rows(
            [(i * 0.02, 0.80, 0.30, 5.0) for i in range(10)] +
            [(0.20 + i * 0.02, 0.10 + i * 0.01, 0.30, 5.0) for i in range(10)])

        got = vc.split_attempts(rows)

        self.assertEqual(len(got), 2, got)
        self.assertAlmostEqual(got[0]["reached_m"], 0.80)

    def test_an_upright_robot_can_be_reset_too(self):
        """**뒤집히지 않아도 리셋된다.** 이것이 앞선 판별식의 구멍이었다.

        `floating_ring_vx1.0_F` 가 고리 앞에서 **높이 0.286 m · 롤 16°** 로
        «서 있다» 리셋됐다. 앞선 판별식은 전진 낙차에 「직전 높이가 0.25 m
        아래」를 «그리고» 로 묶어서 이것을 놓쳤다 `확인됨`.

        실제 값 그대로 넣는다 (전진 0.74 -> 0.10 · 높이 0.286 -> 0.400).
        """
        rows = self._rows(
            [(i * 0.02, 0.74, 0.286, 16.2) for i in range(10)] +
            [(0.20 + i * 0.02, 0.10, 0.400, 0.0) for i in range(10)])

        got = vc.split_attempts(rows)

        self.assertEqual(len(got), 2, "서 있어도 갈라야 한다")
        self.assertAlmostEqual(got[0]["max_abs_roll_deg"], 16.2)

    def test_a_height_jump_alone_splits_when_forward_barely_moves(self):
        """전진이 거의 안 줄어도 **높이가 스폰으로 튀면** 리셋이다.

        스폰 근처에서 뒤집힌 판이 이렇게 된다. 전진 낙차만 보면 놓친다.
        """
        rows = self._rows(
            [(i * 0.02, 0.12, 0.070, 179.0) for i in range(10)] +
            [(0.20 + i * 0.02, 0.05, 0.400, 0.0) for i in range(10)])

        got = vc.split_attempts(rows)

        self.assertEqual(len(got), 2, "높이 도약만으로도 갈라야 한다")

    def test_it_reports_reach_and_roll_per_attempt(self):
        rows = self._rows(
            [(0.00, 0.50, 0.30, 180.0), (0.02, 0.86, 0.08, 179.0)] +
            [(0.04, 0.10, 0.40, 0.0), (0.06, 2.24, 0.30, 12.0)])

        got = vc.split_attempts(rows)

        self.assertEqual(len(got), 2)
        self.assertAlmostEqual(got[0]["max_abs_roll_deg"], 180.0)
        self.assertAlmostEqual(got[1]["reached_m"], 2.24)

    def test_empty_is_empty(self):
        self.assertEqual(vc.split_attempts([]), [])


if __name__ == "__main__":
    unittest.main()
