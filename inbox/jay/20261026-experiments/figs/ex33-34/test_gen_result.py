"""Known-answer and mutation checks for the CPU result generator."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import gen_result as g
import verify_repro as repro


class ResultTests(unittest.TestCase):
    def test_eight_bins_keep_equal_env_weight_and_alive_mask(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "arrays_indep_right.npz"
            # The third env is not kept. Env 2 has half the alive samples.
            alive = np.ones((3, 16), bool)
            alive[1, 1::2] = False
            kept = np.array([True, True, False])
            wz = np.array([[-1.0] * 16, [-0.5] * 16, [99.0] * 16])
            wz[1, 1::2] = 999.0
            np.savez(p, alive=alive, kept=kept, wz=wz)
            self.assertEqual(g.time_bins(p, "indep_right"), [.75] * 8)

    def test_empty_kept_bin_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "arrays_indep_left.npz"
            alive = np.ones((1, 16), bool)
            alive[0, 0:2] = False
            np.savez(p, alive=alive, kept=np.array([True]),
                     wz=np.ones((1, 16)))
            with self.assertRaises(AssertionError):
                g.time_bins(p, "indep_left")

    def test_map_terrain_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source = g.root_path("S-B50", "m1500/map64/map_modes.json")
            data = json.loads(source.read_text(encoding="utf-8"))
            data["fixed_terrain"]["assignment_sha256"] = "0" * 64
            p = Path(d) / "map_modes.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(AssertionError):
                g.map64(p)

    def test_card_threshold_exact_boundary(self):
        start = {"map64": {
            "B1500|eval_gt": {"fwd1.0": [10.0, 0, 64]},
            "G0-B|none": {"fwd1.0": [5.0, 0, 64]},
        }}
        stats = lambda q: {"Q": q}
        row = {
            "map": {"modes": {
                "eval_gt": {"fwd1.0": {"body_vx_integral_median_m": 9.0,
                                       "alive_envs_at_end": 64}},
                "probe_prop_only": {"fwd1.0": {"body_vx_integral_median_m": 4.0,
                                               "alive_envs_at_end": 63}},
            }},
            "turn": {
                "eval_gt": {c: stats(.4) for c in g.CASES},
                "probe_prop_only": {c: stats(.3) for c in g.CASES},
            },
        }
        verdict = g.result_verdict("S-B50", row, start)
        self.assertTrue(verdict["card_numeric_candidate"])
        self.assertEqual(verdict["turn_mode_similarity_counts"], {"같음": 6, "다름": 0})
        row["turn"]["probe_prop_only"][g.CASES[0]]["Q"] = .2793
        verdict = g.result_verdict("S-B50", row, start)
        self.assertEqual(verdict["turn_mode_similarity"][g.CASES[0]], "다름")
        self.assertEqual(verdict["turn_mode_similarity_counts"], {"같음": 5, "다름": 1})
        self.assertTrue(verdict["card_numeric_candidate"])
        row["map"]["modes"]["probe_prop_only"]["fwd1.0"]["body_vx_integral_median_m"] = 3.999
        self.assertFalse(g.result_verdict("S-B50", row, start)["card_numeric_candidate"])

    def test_lead_sections_are_required_and_verbatim(self):
        for ex in ("EX33", "EX34"):
            source = Path(g.__file__).resolve().parent / f"lead_sections_{ex}.md"
            self.assertEqual(g.read_lead_sections(ex), source.read_bytes().decode("utf-8-sig"))
        with self.assertRaisesRegex(AssertionError, "lead sections missing"):
            g.read_lead_sections("MISSING")

    def test_video_renames_match_new_sha_list_and_reject_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rows = [(f"old_{i}.mp4", f"EX33-new_{i}.mp4", f"{i:064x}")
                    for i in range(16)]
            csv_text = "old_name,new_name,sha256\n" + "".join(
                f"{old},{new},{digest}\n" for old, new, digest in rows)
            (root / "renames.csv").write_text(csv_text, encoding="utf-8")
            sha_text = "".join(f"{digest} *{new}\n" for _, new, digest in rows)
            sha_text += f"{'a' * 64} *unfinished_forward_0.25x.mp4\n"
            (root / "SHA256SUMS.txt").write_text(sha_text, encoding="utf-8")
            mapped = g.video_sources(root)
            self.assertEqual(len(mapped), 16)
            self.assertEqual(mapped[0]["new_name"], "EX33-new_0.mp4")
            (root / "renames.csv").write_text(csv_text.replace(
                rows[0][2], "b" * 64, 1), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "rename SHA mismatch"):
                g.video_sources(root)
            (root / "renames.csv").write_text(csv_text, encoding="utf-8")
            (root / "SHA256SUMS.txt").write_text(sha_text.replace(
                f"{rows[0][2]} *{rows[0][1]}\n", "", 1), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "rename SHA mismatch"):
                g.video_sources(root)

    def test_repro_receipt_seals_final_sha_without_masking_other_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            receipt = root / "reproducibility.json"
            other = root / "other.txt"
            receipt.write_text("before", encoding="utf-8")
            other.write_text("stable", encoding="utf-8")
            digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            (root / "SHA256SUMS.txt").write_text(
                f"{digest(other)}  other.txt\n{digest(receipt)}  reproducibility.json\n",
                encoding="utf-8")
            receipt.write_text("after", encoding="utf-8")
            self.assertEqual(repro.seal_sha_list(root), 2)
            self.assertIn(f"{digest(receipt)}  reproducibility.json",
                          (root / "SHA256SUMS.txt").read_text(encoding="utf-8"))
            other.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "SHA mismatch: other.txt"):
                repro.seal_sha_list(root)

    def test_card_denominators_are_raw_and_lead_table_mutation_caught(self):
        start = g.read_json(g.LEAD / "startline_table.json")
        raw = g.raw_reference(start)
        self.assertAlmostEqual(raw["map64"]["B1500|eval_gt"]["fwd1.0"][0],
                               5.662734508514404)
        self.assertAlmostEqual(raw["map64"]["G0-B|none"]["fwd1.0"][0],
                               5.739945411682129)
        start["map64"]["G0-B|none"]["fwd1.0"][0] += 1
        with self.assertRaises(AssertionError):
            g.raw_reference(start)


if __name__ == "__main__":
    unittest.main()
