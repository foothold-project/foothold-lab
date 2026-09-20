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


if __name__ == "__main__":
    unittest.main()
