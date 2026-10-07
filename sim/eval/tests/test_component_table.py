# -*- coding: utf-8 -*-
"""성분 조합 집계를 못 박는다. `sim/eval/component_table.py`.

    python -m unittest discover -s sim/eval/tests -v

## 막는 사고

**열 이름을 틀리면 조용히 0 이 나온다.** `survival_success` 를 `survived` 로
찾은 적이 있는데 예외가 아니라 **「생존 미달 0 판」**이 나왔다. `rails` 1.5 는
실제로 8 판이 넘어졌다. 두 사람이 각자 같은 실수를 했고 둘 다 요약 CSV 의
`survival_rate` 와 안 맞는 것을 보고서야 잡았다.

그래서 `failure_combinations()` 가 **셀 때마다 요약과 대조하고 안 맞으면
죽게** 해 두었다. 여기서는 **그 대조가 실제로 죽이는지**를 본다.
"""

import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import component_table as ct  # noqa: E402


def _write(folder, raw_rows, summary_row):
    os.makedirs(folder, exist_ok=True)

    with open(os.path.join(folder, "generalization_raw.csv"),
              "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(raw_rows[0]))
        writer.writeheader()
        writer.writerows(raw_rows)

    with open(os.path.join(folder, "generalization_summary.csv"),
              "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_row))
        writer.writeheader()
        writer.writerow(summary_row)


def _rows(n_fail_survival):
    """판 넷. 앞의 `n_fail_survival` 판만 생존 미달."""
    out = []

    for i in range(4):
        fell = i < n_fail_survival
        out.append({
            "terrain": "rails",
            "overall_success": str(not fell),
            "survival_success": str(not fell),
            "progress_success": "True",
            "tracking_success": "True",
            "direction_success": "True",
        })

    return out


class FailureCombinationTest(unittest.TestCase):

    def test_real_raw_csv_has_every_component_column(self):
        """**실제 원시 CSV 에 네 열이 다 있는가.** 이름이 바뀌면 여기서 걸린다."""
        path = os.path.join(
            ct.REPO_ROOT, "sim", "eval", "results", "20260920-H-axis1",
            "unseen10", "d0.5", "v1.5", "generalization_raw.csv")

        if not os.path.isfile(path):
            self.skipTest("H 축 1 결과가 없습니다")

        with open(path, encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle))

        for column, label, _rate in ct.RAW_COMPONENTS:
            self.assertIn(column, header, "{} 열이 없습니다".format(label))

    def test_counts_match_the_summary_on_real_data(self):
        """실제 칸 하나를 세어 요약과 맞는지. 안 맞으면 함수가 죽는다."""
        root = ct.RUNS["H"]
        folder = os.path.join(ct.REPO_ROOT, root, "unseen10", "d0.5", "v1.5")

        if not os.path.isfile(os.path.join(folder, "generalization_raw.csv")):
            self.skipTest("H 축 1 결과가 없습니다")

        got = ct.failure_combinations(root, "unseen10", "v1.5", "rails")

        self.assertEqual(got["episodes"], 100)
        self.assertEqual(sum(got["combinations"].values()), 100)
        self.assertEqual(got["combinations"]["실패 없음"], got["overall_pass"])

    def test_it_dies_when_summary_disagrees_with_raw(self):
        """**이것이 이 파일의 이유다.** 요약과 원시가 어긋나면 죽어야 한다."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "unseen10", "d0.5", "v1.5")

            # 원시에는 2 판이 넘어졌는데 요약은 «안 넘어졌다» 고 말한다.
            _write(folder, _rows(2), {
                "terrain": "rails", "episodes": "4",
                "overall_success_rate": "0.5",
                "survival_rate": "1.0",
                "progress_success_rate": "1.0",
                "tracking_success_rate": "1.0",
                "direction_success_rate": "1.0",
            })

            with self.assertRaises(SystemExit) as caught:
                ct.failure_combinations(tmp, "unseen10", "v1.5", "rails")

            self.assertIn("생존", str(caught.exception))

    def test_it_dies_when_a_component_column_is_missing(self):
        """열 이름이 틀리면 **0 을 돌려주지 말고 죽어야 한다.**"""
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "unseen10", "d0.5", "v1.5")
            rows = _rows(0)

            for row in rows:
                row["survived"] = row.pop("survival_success")

            _write(folder, rows, {
                "terrain": "rails", "episodes": "4",
                "overall_success_rate": "1.0", "survival_rate": "1.0",
                "progress_success_rate": "1.0", "tracking_success_rate": "1.0",
                "direction_success_rate": "1.0",
            })

            with self.assertRaises(SystemExit) as caught:
                ct.failure_combinations(tmp, "unseen10", "v1.5", "rails")

            self.assertIn("survival_success", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
