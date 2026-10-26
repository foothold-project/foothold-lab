"""Known-input checks for the narrow EX-35 record and status sync."""

import unittest
from datetime import datetime, timezone

from sync_result_v13 import render_exp_map, render_lab


DATA = {
    "training": {"completed_iteration": 2000, "exit_code": 0, "parent_sha256": "a" * 64},
    "window_decision": "STOP",
    "window_default_row": 4,
    "window_row": 6,
    "canonical": "S-B10 m1500",
    "window_evidence": {
        "a11": {"state": "clear"},
        "map64_numeric_changed": 28,
        "map64_numeric_comparable": 74,
        "repro_a1_a2_changed": 27,
        "repro_numeric_count": 56,
    },
}


class SyncTest(unittest.TestCase):
    def test_exp_map_preserves_other_record(self):
        source = (
            "> 상태: old\n"
            "- **EX-35 최종 판정**: old\n"
            "| [EX-35 S-B10 명령 S2a](old) | old |\n"
            "- 다른 기록: 보존\n"
        )
        output = render_exp_map(source, DATA)
        self.assertIn("STOP` 6행", output)
        self.assertIn("27/56", output)
        self.assertIn("- 다른 기록: 보존", output)
        self.assertEqual(output, render_exp_map(output, DATA))

    def test_lab_timestamp_comes_from_given_date(self):
        source = (
            '<header><p>마지막 원자료 대조 <b>old</b></p></header>\n'
            '<section class="decide">\n<h2>팀장이 정할 것 · old</h2>\n<p>old</p>\n'
            '<div class="row">팀장 결정 보존</div>\n</section>\n'
            '<div class="row"><div class="k">GPU1</div><div>old</div></div>\n'
        )
        instant = datetime(2026, 10, 26, 20, 30, tzinfo=timezone.utc)
        output = render_lab(source, DATA, instant)
        self.assertIn("2026-10-27 05:30 KST", output)
        self.assertIn("10/27 05:30 KST", output)
        self.assertIn("팀장 결정 보존", output)
        self.assertIn("STOP 6행", output)
        self.assertEqual(output, render_lab(output, DATA, instant))

    def test_wrong_window_row_is_rejected(self):
        wrong = {**DATA, "window_row": 4}
        with self.assertRaises(AssertionError):
            render_exp_map("> 상태: old", wrong)


if __name__ == "__main__":
    unittest.main()
