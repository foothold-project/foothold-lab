"""CPU known-input checks for receipt-gated EX23/B model_500 comparison."""

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from foothold_s2.eval.compare_ex23_b500 import (
    EXPECTED_SEGMENTS,
    ComparisonError,
    inspect_clip,
    render_grid,
    validate_comparison,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_clip(root: Path, role: str, experiment: str, scene: str,
              checkpoint: Path, color: str) -> dict:
    mp4 = root / f"{role}.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-f", "lavfi", "-i", f"color=c={color}:s=320x180:r=25:d=12",
        "-frames:v", "300", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4),
    ], check=True, capture_output=True)
    npz = root / f"{role}_feet.npz"
    np.savez_compressed(npz, t=np.arange(600) * 0.02, seg=np.repeat(np.arange(4), 150),
                        dt=np.float64(0.02), seg_s=np.float64(3.0))
    physical = {
        "mode": "fixed",
        "applied_config": {"events": {
            "physics_material": {"params": {"static_friction_range": [0.8, 0.8],
                                                "dynamic_friction_range": [0.6, 0.6]}},
            "add_base_mass": None, "base_com": None, "actuator_gains": None,
            "motor_strength": None, "push_robot": None, "base_external_force_torque": None,
        }},
        "actual_readback": {"mass": [12.0], "material": [[0.8, 0.6]]},
    }
    data = {
        "format": "foothold-sol23f-capture/1", "experiment": experiment, "scene": scene,
        "label": f"{experiment} {scene} model_500", "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha(checkpoint), "seed": 42,
        "physics": physical,
        "policy_modes": {"latent": "mean", "action": "mean"},
        "map_modes": {"map_mode": {"requested": "saved", "effective_use_gt": False}},
        "step_contract": {"duration_s": 12.0, "video_frames": 300, "video_fps": 25,
                          "physics_dt_s": 0.02},
        "segments": EXPECTED_SEGMENTS, "frames": 300, "fps": 25, "duration_s": 12.0,
    }
    mp4.with_suffix(".json").write_text(json.dumps(data), encoding="utf-8")
    done = mp4.with_suffix(".done")
    receipt = {
        "format": "foothold-seq-video/1", "name": mp4.stem, "attempt": 1,
        "child_returncode": 0, "observed": {"frames": 300, "duration_s": 12.0,
                                               "brightness": 50.0, "resets": 0},
        "files": {mp4.name: sha(mp4), mp4.with_suffix(".json").name: sha(mp4.with_suffix(".json")),
                  npz.name: sha(npz)},
        "checkpoint": str(checkpoint), "checkpoint_sha256": sha(checkpoint),
    }
    done.write_text(json.dumps(receipt), encoding="utf-8")
    return inspect_clip(mp4, experiment, scene)


class CompareEX23B500Tests(unittest.TestCase):
    def test_four_verified_cpu_clips_render_synchronized_2x2(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "EX23").mkdir()
            (root / "B").mkdir()
            ex23_ck = root / "EX23" / "model_500.pt"
            b_ck = root / "B" / "model_500.pt"
            ex23_ck.write_bytes(b"fixture checkpoint EX23 500")
            b_ck.write_bytes(b"fixture checkpoint B 500")
            clips = {
                "flat_ex23": make_clip(root, "ex23-flat", "EX23", "flat", ex23_ck, "red"),
                "flat_b": make_clip(root, "b-flat", "B", "flat", b_ck, "blue"),
                "rough_ex23": make_clip(root, "ex23-rough", "EX23", "rough", ex23_ck, "green"),
                "rough_b": make_clip(root, "b-rough", "B", "rough", b_ck, "yellow"),
            }
            contract = validate_comparison(clips)
            self.assertEqual(contract["layout"], "top=flat, bottom=rough; left=EX23, right=B")
            out = root / "grid.mp4"
            payload = render_grid(clips, out)
            self.assertTrue(out.is_file())
            self.assertTrue(out.with_suffix(".json").is_file())
            self.assertEqual(payload["output_sha256"], sha(out))
            probe = subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                "-show_entries", "stream=nb_read_frames,r_frame_rate:format=duration",
                "-of", "json", str(out),
            ], check=True, capture_output=True, text=True)
            stream = json.loads(probe.stdout)["streams"][0]
            self.assertEqual(stream["nb_read_frames"], "300")
            self.assertEqual(stream["r_frame_rate"], "25/1")

    def test_plain_text_done_marker_is_not_a_success_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mp4 = root / "legacy.mp4"
            mp4.write_bytes(b"placeholder")
            mp4.with_suffix(".done").write_text("done\n", encoding="utf-8")
            with self.assertRaisesRegex(ComparisonError, "receipt_invalid"):
                inspect_clip(mp4, "EX23", "flat")

    def test_seed_mismatch_is_rejected_before_render(self):
        metadata = {
            "experiment": "EX23", "scene": "flat", "seed": 42,
            "physics": {"mode": "fixed"}, "policy_modes": {"latent": "mean", "action": "mean"},
            "map_mode": "saved", "physics_dt_s": 0.02,
            "checkpoint": "ex23/model_500.pt", "checkpoint_sha256": "a" * 64,
        }
        clips = {key: {"metadata": dict(metadata)} for key in
                 ("flat_ex23", "flat_b", "rough_ex23", "rough_b")}
        for key, experiment, scene in (("flat_b", "B", "flat"), ("rough_ex23", "EX23", "rough"),
                                       ("rough_b", "B", "rough")):
            clips[key]["metadata"].update(experiment=experiment, scene=scene)
        clips["rough_ex23"]["metadata"]["checkpoint"] = "ex23/model_500.pt"
        clips["rough_b"]["metadata"]["checkpoint"] = "b/model_500.pt"
        clips["rough_b"]["metadata"]["seed"] = 43
        with self.assertRaisesRegex(ComparisonError, "condition_mismatch:seed"):
            validate_comparison(clips)


if __name__ == "__main__":
    unittest.main()
