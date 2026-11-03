"""Known-input checks for twenty-step state feedback and trace guards."""
from __future__ import annotations

import unittest

import numpy as np

from foothold_s2.deploy.package_ex40_real20 import compare_trace


class FakeSession:
    def run(self, output_names, feed):
        assert output_names == ["action", "h_prop_next", "h_terr_next", "recon_map"]
        hp, ht = feed["h_prop"], feed["h_terr"]
        return [hp[:, :12] + feed["obs45"][:, :12], hp + 1.0, ht + 2.0,
                np.zeros((1, 32, 16), dtype=np.float32)]


def known_rows():
    rows = []
    for k in range(20):
        obs = np.full((1, 45), 0.25, dtype=np.float32)
        hp = np.zeros((1, 128), dtype=np.float32)
        ht = np.zeros((1, 128), dtype=np.float32)
        rows.append({"obs45": obs, "hist": np.zeros((1, 10, 45), np.float32),
                     "depth2": np.zeros((1, 2, 60, 60), np.float32),
                     "h_prop": hp.copy(), "h_terr": ht.copy(),
                     "depth_tick": np.array([True]), "first_after_reset": np.array([k == 0]),
                     "use_gt": np.array([False]), "gt_map": np.zeros((1, 32, 16), np.float32),
                     "action": np.full((1, 12), k + 0.25, np.float32),
                     "h_prop_next": np.full((1, 128), k + 1, np.float32),
                     "h_terr_next": np.full((1, 128), (k + 1) * 2, np.float32),
                     "recon_map": np.zeros((1, 32, 16), np.float32)})
    return rows


class TestReal20(unittest.TestCase):
    def test_feedback_replaces_recorded_hidden(self):
        result = compare_trace(FakeSession(), known_rows())
        self.assertEqual(result["action"], 0.0)
        self.assertEqual(result["h_prop_next"], 0.0)

    def test_wrong_action_fails_at_step_seven(self):
        rows = known_rows()
        rows[7]["action"] = rows[7]["action"] + 0.01
        with self.assertRaisesRegex(AssertionError, "step7 action"):
            compare_trace(FakeSession(), rows)

    def test_nonfinite_output_fails(self):
        rows = known_rows()
        rows[1]["recon_map"][0, 0, 0] = np.nan
        with self.assertRaisesRegex(AssertionError, "step1 recon_map"):
            compare_trace(FakeSession(), rows)


if __name__ == "__main__":
    unittest.main()
