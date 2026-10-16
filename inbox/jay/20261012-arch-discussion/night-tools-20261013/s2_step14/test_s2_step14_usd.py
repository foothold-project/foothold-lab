"""CPU synthetic multi-conversion USD evidence, no Isaac import."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from s2_eval_usd_provenance import evidence, UsdEvalHold


class TestUsdEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "usd_root"
        self.root.mkdir()
        self.asset = Path(self.temp.name) / "go2.urdf"
        self.asset.write_text("fixture")
        self.rows = []
        for i in range(2):
            folder = self.root / f"conv{i}"
            folder.mkdir()
            (folder / "robot.usd").write_text(f"robot{i}")
            self.rows.append({"kind": "assigned", "asset_path": str(self.asset),
                              "usd_dir": str(folder)})
        self.refs = [str(self.root / "conv0" / "robot.usd")]
        self.state = {"version": "v3", "expect_conversions": "any", "conversions": 2,
                      "blocked": [], "warnings": [], "root": str(self.root)}
        self.save()

    def save(self):
        (self.root / "isolate_state.json").write_text(json.dumps(self.state))
        (self.root / "assigned.jsonl").write_text("".join(json.dumps(x) + "\n" for x in self.rows))

    def test_two_conversions_within_cap(self):
        actual = evidence(self.root, self.asset, self.refs, max_entries=8)
        self.assertEqual(actual["converter_entries"], 2)
        self.assertEqual(len(actual["robot_references"]), 1)

    def test_ninth_entry_and_outside_assignment_hold(self):
        self.state["conversions"] = 9
        self.rows = self.rows * 4 + self.rows[:1]
        self.save()
        with self.assertRaisesRegex(UsdEvalHold, "usd_isolation_state_or_count"):
            evidence(self.root, self.asset, self.refs, max_entries=8)
        self.state["conversions"] = 2
        self.rows = self.rows[:2]
        self.rows[1]["usd_dir"] = str(Path(self.temp.name) / "outside")
        self.save()
        with self.assertRaisesRegex(UsdEvalHold, "usd_assignment_asset_or_root"):
            evidence(self.root, self.asset, self.refs, max_entries=8)


if __name__ == "__main__":
    unittest.main()
