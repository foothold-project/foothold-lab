"""codex 8회차가 뚫은 네 가지를 다시 먹인다.

    python sim/eval/tests/test_audit_counts.py

## 무엇을 막는가

발행 관문이 **요약(`counts`)을 믿었고, 숨긴 글자를 본문으로 셌다.** 그래서
아래 넷이 통과했다 `확인됨` (2026-09-12 codex 검수 8회차).

| 주입 | 왜 통과했나 |
|---|---|
| 본문과 `counts` 를 «함께» 84·60 으로 | 둘을 서로 대조했을 뿐 배열은 안 셌다 |
| 보이는 글은 84, 숨긴 요소에 112 | 태그를 벗기면 숨긴 글자도 본문이 된다 |
| 대조컷 64를 36으로, 총합 유지 | 구성 수를 아무도 안 셌다 |

관문은 이제 **배열을 직접 센다.** 그러니 조작하려면 clips 배열까지 손대야 하고,
그때는 4a1 이 counts 와 배열의 어긋남을 잡는다.
"""
from __future__ import annotations

import io
import json
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
BOOK = os.path.join(SITE, "gallery", "v1", "manifest.json")


def have():
    return os.path.isfile(REPORT) and os.path.isfile(BOOK)


@unittest.skipUnless(have(), "보고서나 색인이 아직 없다")
class CountsCannotBeFaked(unittest.TestCase):
    """**관문을 실제로 돌린다.** 함수만 부르면 호출을 지워도 안 걸린다."""

    @classmethod
    def setUpClass(cls):
        cls.html = io.open(REPORT, encoding="utf-8").read()
        cls.book = json.load(io.open(BOOK, encoding="utf-8"))

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "out")
        self.site = os.path.join(self.tmp, "site")
        os.makedirs(self.out)
        shutil.copytree(SITE, self.site,
                        ignore=shutil.ignore_patterns("*.mp4", "*.jpg", "*.png",
                                                      ".git"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_audit(self, html=None, book=None):
        io.open(os.path.join(self.out, "report-v1.html"), "w",
                encoding="utf-8").write(html if html is not None else self.html)

        if book is not None:
            io.open(os.path.join(self.site, "gallery", "v1", "manifest.json"),
                    "w", encoding="utf-8").write(
                        json.dumps(book, ensure_ascii=False, indent=2))

        env = dict(os.environ, FOOTHOLD_REPO=LAB, FOOTHOLD_SITE=self.site,
                   FOOTHOLD_REPORT_OUT=self.out, PYTHONIOENCODING="utf-8")
        got = subprocess.run([sys.executable, AUDIT, "--only", "numbers"],
                             capture_output=True, text=True, errors="replace",
                             env=env)
        return got.returncode, got.stdout + got.stderr

    def assert_blocked(self, why, html=None, book=None):
        code, out = self.run_audit(html, book)
        hit = [l.strip() for l in out.splitlines()
               if l.strip().startswith("[X]") and "5a." not in l]
        self.assertNotEqual(code, 0, "%s 를 넣었는데 통과했다%s%s" % (why, chr(10), out))
        self.assertTrue(hit, "%s · 실패한 검사가 없다%s%s" % (why, chr(10), out))

    # ── 통과해야 하는 것 ────────────────────────────────────
    def test_clean_passes(self):
        code, out = self.run_audit()
        keep = [l for l in out.splitlines()
                if l.strip().startswith("[X]") and "5a." not in l]
        self.assertFalse(keep, out)

    # ── 막아야 하는 것 ──────────────────────────────────────
    def test_text_and_counts_changed_together(self):
        """본문과 요약을 «함께» 바꿔도 배열이 남는다."""
        book = json.loads(json.dumps(self.book))
        book["counts"]["clips"] = 84
        book["counts"]["evaluations_without_clip"] = 60
        html = self.html.replace("모두 144컷", "모두 84컷", 1)
        self.assert_blocked("본문과 counts 동시 변조", html, book)

    def test_hidden_element_carries_right_number(self):
        """보이는 자리에 틀린 수, 숨긴 자리에 맞는 수."""
        html = self.html.replace(
            "모두 144컷", "모두 84컷", 1).replace(
            "</body>", '<span hidden>모두 144컷</span></body>', 1)
        self.assert_blocked("숨긴 요소로 위장", html)

    def test_comparison_count_changed(self):
        """대조컷 수만 바꾸고 총합은 유지."""
        got = re.search(r"모델 대조 (\d+)컷", self.html)
        self.assertIsNotNone(got, "본문에 「모델 대조 N컷」 이 없다")
        html = self.html.replace(got.group(0), "모델 대조 36컷", 1)
        self.assert_blocked("대조컷 수 변조", html)

    def test_counts_alone_changed(self):
        """요약만 바꿔도 배열과 어긋난다."""
        book = json.loads(json.dumps(self.book))
        book["counts"]["comparison_clips"] = 36
        self.assert_blocked("counts 만 변조", None, book)


if __name__ == "__main__":
    unittest.main(verbosity=2)
