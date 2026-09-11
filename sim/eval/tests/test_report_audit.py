"""발행 관문이 스스로 약해지는 것을 막는다.

    python -m pytest sim/eval/tests/test_report_audit.py

## 왜 이 파일이 있나

`audit.py` 의 검사를 하나씩 예전으로 되돌려 봤더니 **아홉 가지 모두 시험
313개가 다 통과했다** `확인됨` (2026-09-12 검증 6회차 5번). 관문은 있는데
그 관문을 지키는 것이 없었다. `make_report.py` 에서 관문 호출 한 줄을
지워도 마찬가지였다.

그래서 여기서는 **관문을 실제로 돌린다.**

| 넣는 오류 | 막아야 하는 검사 |
|---|---|
| 성적표 한 칸을 빈칸으로 | 1h |
| 성적표 한 칸의 수를 바꿈 | 1h |
| 집합 평균을 바꿈 | 1i |
| wave 캡션의 종합 성공을 바꿈 | 1j |
| rails 캡션의 성공·실패를 바꿈 | 1c |
| 속도추종 1,369 를 바꿈 | 1e |
| 표 머리칸 하나 삭제 | 4a |
| 옛 과장 문장 되넣기 | 6 |
| 한정 문장 삭제 | 6 |

## 왜 `--only numbers` 인가

영상 절은 84컷을 디코딩하고 122 MB 를 해시해 한 번에 20초가 넘는다.
여기서는 수치와 문구만 본다. 영상 절은 발행 때 도는 전체 실행이 맡는다.

`--only` 자체가 조용히 전부를 건너뛰지 않는지도 시험한다.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
AUDIT = os.path.join(LAB, "sim", "eval", "report", "audit.py")
REPORT = os.path.join(LAB, "sim", "eval", "results", "report-v1", "report-v1.html")
SITE = os.path.abspath(os.path.join(LAB, "..", "foothold-site"))


def have_inputs():
    return os.path.isfile(REPORT) and os.path.isfile(
        os.path.join(SITE, "gallery", "v1", "manifest.json"))


@unittest.skipUnless(have_inputs(), "보고서나 갤러리 색인이 아직 없다")
class AuditCatchesTampering(unittest.TestCase):
    """**관문을 실제로 돌린다.** 함수만 부르면 호출을 지워도 안 걸린다."""

    @classmethod
    def setUpClass(cls):
        cls.good = io.open(REPORT, encoding="utf-8").read()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(self.out)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def audit(self, html):
        io.open(os.path.join(self.out, "report-v1.html"), "w",
                encoding="utf-8").write(html)
        env = dict(os.environ, FOOTHOLD_REPO=LAB, FOOTHOLD_SITE=SITE,
                   FOOTHOLD_REPORT_OUT=self.out, PYTHONIOENCODING="utf-8")
        done = subprocess.run([sys.executable, AUDIT, "--only", "numbers"],
                              capture_output=True, text=True, errors="replace",
                              env=env)
        hit = [l.strip() for l in done.stdout.splitlines()
               if l.strip().startswith("[X]") and "5a." not in l]
        return done.returncode, hit, done.stdout

    def assert_blocked(self, html, why):
        code, hit, out = self.audit(html)
        self.assertNotEqual(code, 0, "%s 를 넣었는데 통과했다%s%s" % (why, chr(10), out))
        self.assertTrue(hit, "%s · 실패한 검사가 없다" % why)

    def swap(self, old, new, why):
        self.assertIn(old, self.good, "본문에 %r 이 없다. 시험을 고쳐야 한다" % old)
        self.assert_blocked(self.good.replace(old, new, 1), why)

    # ── 통과해야 하는 것 ────────────────────────────────────
    def test_clean_report_passes(self):
        code, _hit, out = self.audit(self.good)
        self.assertEqual(code, 0, out)

    def test_only_does_not_skip_everything(self):
        """`--only` 가 조용히 전부를 건너뛰면 관문이 없는 것과 같다."""
        _code, _hit, out = self.audit(self.good)
        self.assertGreaterEqual(out.count("OK "), 20, out)

    # ── 막아야 하는 것 ──────────────────────────────────────
    def test_blank_scorecard_cell(self):
        self.swap('<td class="num grp">76</td>', '<td class="num grp"></td>',
                  "성적표 빈칸")

    def test_wrong_scorecard_cell(self):
        self.swap('<td class="num grp">76</td>', '<td class="num grp">7</td>',
                  "성적표 수치 변조")

    def test_scorecard_row_removed(self):
        """줄을 통째로 지우면 키가 모자란다. 「틀린 칸이 없다」만 보면 통과한다."""
        m = re.search(r"<tr><td class=\"mono\">boxes</td>.*?</tr>", self.good, re.S)
        self.assertIsNotNone(m, "성적표의 boxes 줄을 못 찾았다")
        self.assert_blocked(self.good.replace(m.group(0), "", 1), "성적표 줄 삭제")

    def test_wrong_set_average(self):
        m = re.search(r"\b65\.8\b", self.good)
        self.assertIsNotNone(m, "집합 평균 65.8 이 본문에 없다")
        self.swap("65.8", "7.0", "집합 평균 변조")

    def test_wrong_wave_caption(self):
        self.swap("종합 성공 100/100", "종합 성공 9/100", "wave 캡션 변조")

    def test_wrong_rails_caption(self):
        self.swap("성공 48/100", "성공 99/100", "rails 캡션 변조")

    def test_wrong_tracking_count(self):
        self.swap("1,369 / 1,600", "1,599 / 1,600", "속도추종 변조")

    def test_table_header_removed(self):
        self.swap('<th class="num">중앙값</th>', "", "표 머리칸 삭제")

    def test_old_overclaim_comes_back(self):
        self.assert_blocked(self.good + "<p>명령 속도를 실제로 냅니다</p>",
                            "옛 과장 문장")

    def test_limit_sentence_removed(self):
        self.swap("명령 속도를 정확히 낸다는 뜻은 아닙니다", "", "한정 문장 삭제")

    def test_em_dash(self):
        self.assert_blocked(self.good + "<p>" + chr(8212) + "</p>", "em dash")


@unittest.skipUnless(have_inputs(), "보고서나 갤러리 색인이 아직 없다")
class MakeReportRunsTheGate(unittest.TestCase):
    """생성 명령이 관문을 **부르는지** 본다. 부르지 않으면 관문이 없는 것과 같다."""

    def test_make_report_invokes_audit(self):
        source = io.open(os.path.join(LAB, "sim", "eval", "report", "make_report.py"),
                         encoding="utf-8").read()
        self.assertIn('stage("audit.py"', source,
                      "생성 명령이 관문을 안 부른다")
        self.assertIn("--no_audit", source,
                      "관문을 건너뛰는 길이 명시돼 있지 않다")

    def test_stage_stops_on_failure(self):
        """어느 단계가 실패하면 뒤로 안 넘어가야 한다."""
        source = io.open(os.path.join(LAB, "sim", "eval", "report", "make_report.py"),
                         encoding="utf-8").read()
        self.assertIn("raise SystemExit", source)


if __name__ == "__main__":
    unittest.main()
