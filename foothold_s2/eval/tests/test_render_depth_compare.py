"""Known-input CPU tests for synchronized depth and height-map rendering."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from foothold_s2.eval.render_depth_compare import (
    HEIGHT_SHAPE,
    compose_frame,
    depth_input_to_meters,
    normalize_npz,
    probe_video,
    render,
    reshape_heightmap,
    selected_label,
    synchronize_frame,
)


class RenderDepthCompareTests(unittest.TestCase):
    def test_heightmap_flat_order_restores_32_by_16_grid(self):
        flat = np.arange(32 * 16, dtype=np.float32)
        grid = reshape_heightmap(flat)
        self.assertEqual(grid.shape, HEIGHT_SHAPE)
        self.assertEqual(grid[0, 0], 0)
        self.assertEqual(grid[0, 1], 1)
        self.assertEqual(grid[1, 0], 16)
        self.assertEqual(grid[31, 15], 511)

    def test_synchronization_selects_nearest_observation_and_reports_delta(self):
        sync = synchronize_frame(3, 25.0, np.array([0.0, 0.1, 0.2]))
        self.assertEqual(sync["map_index"], 1)
        self.assertAlmostEqual(sync["frame_t"], 0.12)
        self.assertAlmostEqual(sync["map_t"], 0.1)
        self.assertAlmostEqual(sync["delta_s"], 0.02)
        with self.assertRaises(ValueError):
            synchronize_frame(8, 25.0, np.array([0.0, 0.1, 0.2]))

    def test_depth_input_inverts_fixed_normalization_in_meters(self):
        meters = depth_input_to_meters(np.array([0.0, 0.5, 1.0], dtype=np.float32))
        np.testing.assert_allclose(meters, [0.2, 1.6, 3.0])
        with self.assertRaises(ValueError):
            depth_input_to_meters(np.array([np.nan]))

    def test_selected_policy_input_comes_from_boolean_use_gt(self):
        self.assertIn("GT", selected_label(True, "saved"))
        self.assertIn("PRED", selected_label(False, "pred"))

    def test_npz_contract_reshapes_each_map_sample_with_shared_timeline(self):
        class FakeNpz:
            files = ["t", "dt", "map_t", "depth", "gt_map", "rough_map",
                     "refined_map", "map_use_gt"]
            data = {
                "t": np.array([0.0, 0.02, 0.04]),
                "dt": np.array(0.02),
                "map_t": np.array([0.0, 0.04]),
                "depth": np.full((2, 60, 60), 0.5, dtype=np.float32),
                "gt_map": np.tile(np.arange(512, dtype=np.float32), (2, 1)),
                "rough_map": np.ones((2, 32, 16), dtype=np.float32),
                "refined_map": np.full((2, 512), 0.25, dtype=np.float32),
                "map_use_gt": np.array([True, False]),
            }
            def __getitem__(self, key):
                return self.data[key]

        sample = normalize_npz(FakeNpz())
        self.assertEqual(sample["maps"]["gt_map"].shape, (2, 32, 16))
        self.assertEqual(sample["maps"]["gt_map"][1, 0, 1], 1)
        self.assertAlmostEqual(float(sample["maps"]["depth"][0, 0, 0]), 1.6)
        self.assertTrue(sample["map_use_gt"][0])
        self.assertFalse(sample["map_use_gt"][1])

    def test_composed_frame_keeps_rgb_and_four_diagnostic_views(self):
        sample = {
            "maps": {
                "depth": np.full((1, 60, 60), 0.5, dtype=np.float32),
                "gt_map": np.zeros((1, 32, 16), dtype=np.float32),
                "rough_map": np.full((1, 32, 16), 0.2, dtype=np.float32),
                "refined_map": np.full((1, 32, 16), -0.2, dtype=np.float32),
            },
            "map_use_gt": np.array([False]),
        }
        frame = compose_frame(np.zeros((540, 960, 3), dtype=np.uint8), sample, 0,
                              {"frame_t": 0.0, "map_index": 0, "map_t": 0.0, "delta_s": 0.0},
                              "pred")
        self.assertEqual(frame.shape, (540, 1600, 3))
        self.assertEqual(frame.dtype, np.uint8)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg tools unavailable")
    def test_cpu_known_input_writes_synchronized_video(self):
        ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rgb_video = root / "rgb.mp4"
            pixels = np.zeros((5, 48, 64, 3), dtype=np.uint8)
            pixels[:, :, :, 0] = np.arange(5, dtype=np.uint8)[:, None, None] * 40
            encoded = subprocess.run(
                [ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s:v", "64x48", "-r", "25", "-i", "pipe:0", "-an", "-c:v", "libx264",
                 "-pix_fmt", "yuv420p", str(rgb_video)],
                input=pixels.tobytes(), capture_output=True, check=False)
            self.assertEqual(encoded.returncode, 0, encoded.stderr.decode(errors="replace"))
            npz = root / "capture_feet.npz"
            map_t = np.array([0.0, 0.1], dtype=np.float64)
            np.savez_compressed(npz, t=np.arange(10) * 0.02, dt=np.float64(0.02),
                                map_t=map_t, depth=np.full((2, 60, 60), 0.5, dtype=np.float32),
                                gt_map=np.tile(np.arange(512, dtype=np.float32), (2, 1)),
                                rough_map=np.full((2, 512), 0.1, dtype=np.float32),
                                refined_map=np.full((2, 32, 16), -0.1, dtype=np.float32),
                                map_use_gt=np.array([True, False], dtype=np.bool_))
            metadata = root / "capture.json"
            metadata.write_text(json.dumps({
                "format": "foothold-sol23f-capture/1",
                "map_modes": {"map_mode": {"requested": "saved"}},
            }), encoding="utf-8")
            output = root / "synchronized.mp4"
            receipt = render(rgb_video, npz, metadata, output, ffmpeg, ffprobe)
            self.assertEqual(receipt["frames"], 5)
            self.assertEqual(receipt["height_shape"], [32, 16])
            self.assertTrue(output.is_file())
            self.assertEqual(probe_video(output, ffprobe)["frames"], 5)


if __name__ == "__main__":
    unittest.main()
