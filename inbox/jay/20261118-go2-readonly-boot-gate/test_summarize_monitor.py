#!/usr/bin/env python3
import unittest

from summarize_monitor import JOINTS, summarize


def row(sample, temp_fr, temp_fl, reserve_fr, kp):
    value = {
        "sample": str(sample),
        "t_s": str(sample * 0.02),
        "state_callbacks": str(10 + sample),
        "cmd_callbacks": str(20 + sample),
        "sport_callbacks": str(30 + sample),
        "error_callbacks": "0",
        "state_age_ms": "2.0",
        "cmd_age_ms": "3.0",
        "sport_age_ms": "4.0",
        "soc_pct": "81",
        "sport_error_code": "1001",
    }
    for joint in JOINTS:
        value[f"temp_{joint}"] = str(
            temp_fr if joint == "FR_hip" else temp_fl if joint == "FL_hip" else 35
        )
        value[f"reserve0_{joint}"] = str(reserve_fr if joint == "FR_hip" else 0)
        value[f"lost_{joint}"] = "0"
        value[f"kp_{joint}"] = str(kp)
        value[f"kd_{joint}"] = "5"
    return value


class SummarizeMonitorTest(unittest.TestCase):
    def test_preserves_temperature_reserve_and_gain_evidence(self):
        summary = summarize([
            row(0, 40, 41, 0, 1),
            row(1, 78, 81, 4, 100),
            row(2, 65, 68, 4, 100),
        ])
        self.assertEqual(summary["samples"], 3)
        self.assertEqual(summary["global_max_temp_c"], 81)
        self.assertEqual(summary["global_max_temp_joint"], "FL_hip")
        self.assertEqual(summary["motors"]["FR_hip"]["reserve0_values"], [0, 4])
        self.assertEqual(summary["motors"]["FR_hip"]["reserve0_nonzero_samples"], 2)
        self.assertEqual(summary["motors"]["FR_hip"]["kp_max"], 100)
        self.assertEqual(summary["sport_marker_counts"], {"1001": 3})
        self.assertEqual(summary["message_age_ms_max"]["state_age_ms"], 2.0)

    def test_rejects_empty_input(self):
        with self.assertRaisesRegex(ValueError, "no data rows"):
            summarize([])


if __name__ == "__main__":
    unittest.main()
