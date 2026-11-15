"""Known-input CPU checks for the post-render anomaly screen."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent))
import video_finish_w28 as video


class VideoTests(unittest.TestCase):
    def test_title_verdict_frame_and_dark_counterexamples(self):
        receipt = {"label": "EX35 · m2000", "frames": 300, "expected": 300}
        verdict = {"decision": "STOP"}
        self.assertEqual(video.assess(receipt, "EX35 · m2000", verdict, 300, []), [])
        flags = video.assess(receipt, "wrong", {}, 299, [9])
        self.assertIn("title_receipt_mismatch", flags)
        self.assertIn("verdict_missing", flags)
        self.assertIn("frame_count_mismatch", flags)
        self.assertIn("dark_samples:9", flags)

    def test_real_cpu_video_and_receipt(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("cv2/numpy not installed in this interpreter")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp4 = root / "sample.mp4"
            writer = cv2.VideoWriter(str(mp4), cv2.VideoWriter_fourcc(*"mp4v"), 5, (32, 32))
            for index in range(5):
                writer.write(np.full((32, 32, 3), 100 + index, dtype=np.uint8))
            writer.release()
            self.assertTrue(mp4.is_file())
            receipt = root / "sample.json"
            receipt.write_text(json.dumps({"label": "known title", "frames": 5, "expected": 5,
                                           "output": str(mp4), "sha256": video.sha(mp4)}))
            verdict = root / "verdict.json"
            verdict.write_text('{"decision":"PASS"}')
            result = video.inspect(mp4, receipt, verdict, "known title", root / "check")
            self.assertEqual(result["flags"], [])
            self.assertTrue((root / "check" / "screen_samples.jpg").is_file())
            self.assertEqual(json.loads((root / "check" / "screen_check.json").read_text())["frame_count"], 5)

            bad_mp4 = root / "dark.mp4"
            writer = cv2.VideoWriter(str(bad_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 5, (32, 32))
            for index in range(12):
                writer.write(np.full((32, 32, 3), 0 if index == 9 else 110, dtype=np.uint8))
            writer.release()
            receipt.write_text(json.dumps({"label": "known title", "frames": 12, "expected": 12,
                                           "output": str(bad_mp4), "sha256": video.sha(bad_mp4)}))
            bad = video.inspect(bad_mp4, receipt, verdict, "known title", root / "bad-check")
            self.assertIn("dark_samples:9", bad["flags"])


if __name__ == "__main__":
    unittest.main()
