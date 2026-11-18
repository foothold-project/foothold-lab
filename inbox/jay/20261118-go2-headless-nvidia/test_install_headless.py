import tempfile
import unittest
from pathlib import Path

from install_headless import apply_config, rollback_config, validate_edid


class HeadlessInstallerTest(unittest.TestCase):
    def test_rejects_missing_or_invalid_edid(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaisesRegex(ValueError, "does not exist"):
                validate_edid(root / "missing.edid")

            invalid = root / "invalid.edid"
            invalid.write_bytes(b"not-an-edid")
            with self.assertRaisesRegex(ValueError, "128-byte blocks"):
                validate_edid(invalid)

    def test_apply_preserves_first_backup_and_rollback_restores_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            x11 = root / "X11"
            x11.mkdir()
            active = x11 / "xorg.conf"
            active.write_text("original\n")
            candidate = root / "candidate.conf"
            candidate.write_text("headless-v1\n")
            edid = root / "monitor.edid"
            edid.write_bytes(bytes(range(128)))

            result = apply_config(edid, candidate, x11)
            self.assertEqual(active.read_text(), "headless-v1\n")
            self.assertEqual(
                (x11 / "xorg.conf.pre-go2-headless").read_text(), "original\n"
            )
            self.assertEqual(
                (x11 / "go2-headless-1920x1080.edid").read_bytes(),
                bytes(range(128)),
            )
            self.assertTrue(result["backup_created"])

            candidate.write_text("headless-v2\n")
            result = apply_config(edid, candidate, x11)
            self.assertEqual(active.read_text(), "headless-v2\n")
            self.assertEqual(
                (x11 / "xorg.conf.pre-go2-headless").read_text(), "original\n"
            )
            self.assertFalse(result["backup_created"])

            rollback_config(x11)
            self.assertEqual(active.read_text(), "original\n")


if __name__ == "__main__":
    unittest.main()
