"""CPU-only known-input tests. Uses temporary fixtures, with no simulator or GPU."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("capture_audit.py")
spec = importlib.util.spec_from_file_location("capture_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class InventoryTests(unittest.TestCase):
    def test_missing_candidate_is_not_claimed_available(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = audit.inventory(root / "missing-models", root / "missing-videos", "B", [500, 1000, 1500])
            self.assertEqual(len(result["rows"]), 6)
            self.assertTrue(all(row["status"] == "missing" for row in result["rows"]))
            self.assertTrue(all(row["reason"] == "missing_or_empty:model,mp4,json,npz" for row in result["rows"]))

    def test_resets_are_science_not_file_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            model = root / "model_500.pt"
            model.write_bytes(b"known model")
            folder = root / "ex23r_500"
            folder.mkdir()
            with patch.object(audit, "probe_video", return_value=(300, 12.0)), \
                 patch.object(audit, "validate_npz", return_value=None), \
                 patch.object(audit, "decode_video", return_value=None), \
                 patch.object(audit, "sha256", return_value="a" * 64):
                for suffix in (".mp4", ".json", "_feet.npz"):
                    (folder / ("run_flat" + suffix)).write_bytes(b"fixture")
                (folder / "run_flat.done").write_text("done\n", encoding="utf-8")
                (folder / "run_flat.json").write_text(json.dumps({
                    "checkpoint": str(model), "label": "ex23r 500", "scene": "flat",
                    "frames": 300, "min_mean_brightness": 56.0, "resets": 2,
                }), encoding="utf-8")
                result = audit.inspect_one(model, folder, "run_flat", "ex23r 500", "flat")
            self.assertEqual(result["status"], "available_files")
            self.assertEqual(result["resets"], 2)
            self.assertEqual(result["receipt"], "legacy_or_invalid")

    def test_checkpoint_mismatch_is_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            model = root / "model_500.pt"
            model.write_bytes(b"model")
            folder = root / "ex23r_500"
            folder.mkdir()
            (folder / "run_flat.mp4").write_bytes(b"x")
            (folder / "run_flat_feet.npz").write_bytes(b"x")
            (folder / "run_flat.json").write_text(
                json.dumps({"checkpoint": str(root / "other.pt")}), encoding="utf-8")
            result = audit.inspect_one(model, folder, "run_flat", "ex23r 500", "flat")
            self.assertEqual(result["status"], "broken_excluded")
            self.assertEqual(result["reason"], "checkpoint_mismatch")


if __name__ == "__main__":
    unittest.main()
