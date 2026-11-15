"""Known-answer and counterexample checks for exp_sync_check."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import exp_sync_check as sync


NOW = datetime(2026, 10, 21, 16, 0, tzinfo=timezone(timedelta(hours=9)))


class SyncFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.chain = self.repo / "chain_state.json"
        self.write(sync.DECISION_REL, """# 결정
<!-- exp-sync:decision:v1 -->
| 체크 | 결정 | 반영 자리 |
|---|---|---|
| [x] | D1 | 반영 |
""")
        self.write(sync.MAP_REL, """# 지도
<!-- exp-sync:experiments:v1 -->
| 카드 | 역할 |
|---|---|
| [A](EXP-A.md) | 시험 |

<!-- exp-sync:chain:v1 -->
| 사슬 작업 | 카드 또는 분류 |
|---|---|
| `train_A` | A |
| `observer` | 운영 |
""")
        self.write(sync.MAP_REL.parent / "EXP-A.md", """# A
## 가설
가설 내용.
## 설정
seed 1.
## 결과
영상: 영상 없음 · 미확인.
## 다음
다음 측정.
""")
        self.write(sync.SCHEDULE_REL, "# 일정\n")
        self.chain.write_text(json.dumps({"train_A": {"state": "done"}, "observer": {"state": "running"}}), encoding="utf-8")

    def write(self, relative: Path, content: str) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def run_audit(self, updated: datetime = NOW) -> list[sync.Row]:
        return sync.audit(self.repo, self.chain, NOW, updated=updated)

    def test_complete_known_answer(self) -> None:
        rows = self.run_audit()
        self.assertEqual(5, len(rows))
        self.assertTrue(all(row.ok for row in rows), sync.render(rows))

    def test_unchecked_decision_is_named_and_fails(self) -> None:
        path = self.repo / sync.DECISION_REL
        path.write_text(path.read_text(encoding="utf-8").replace("[x]", "[ ]"), encoding="utf-8")
        rows = self.run_audit()
        self.assertEqual(["D1"], [row.item for row in rows if not row.ok])

    def test_missing_card_and_missing_result_video(self) -> None:
        card = self.repo / sync.MAP_REL.parent / "EXP-A.md"
        card.unlink()
        rows = self.run_audit()
        self.assertIn("파일 없음", next(row.detail for row in rows if row.area == "실험 카드"))
        self.write(sync.MAP_REL.parent / "EXP-A.md", "# A\n## 가설\n값\n## 설정\n값\n## 결과\n값\n## 다음\n값\n")
        rows = self.run_audit()
        self.assertIn("영상", next(row.detail for row in rows if row.area == "실험 카드"))

    def test_missing_section_and_real_video_path(self) -> None:
        self.write(sync.MAP_REL.parent / "EXP-A.md", "# A\n## 가설\n값\n## 결과\n영상: videos/a.mp4\n## 다음\n값\n")
        rows = self.run_audit()
        detail = next(row.detail for row in rows if row.area == "실험 카드")
        self.assertIn("설정", detail)
        self.assertNotIn("영상", detail)

    def test_only_running_and_done_need_chain_names(self) -> None:
        self.chain.write_text(json.dumps({"train_A": {"state": "done"}, "observer": {"state": "running"},
                                          "new_C": {"state": "running"}, "future": {"state": "pending"}}), encoding="utf-8")
        rows = self.run_audit()
        self.assertEqual(["new_C"], [row.item for row in rows if not row.ok])

    def test_schedule_older_than_24_hours_fails(self) -> None:
        rows = self.run_audit(NOW - timedelta(hours=24, seconds=1))
        self.assertEqual(["SCHEDULE-NOW"], [row.item for row in rows if not row.ok])
        self.assertTrue(all(row.ok for row in self.run_audit(NOW - timedelta(hours=24))))

    def test_cli_exit_codes_on_real_git_fixture(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "--", sync.SCHEDULE_REL.as_posix()],
                       check=True, capture_output=True)
        env = os.environ.copy()
        env.update({"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"})
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "fixture"],
                       check=True, capture_output=True, env=env)
        script = Path(sync.__file__).resolve()
        command = [sys.executable, str(script), "--repo-root", str(self.repo), "--chain-state", str(self.chain)]
        good = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, good.returncode, good.stdout + good.stderr)
        self.assertIn("종료 코드 0", good.stdout)
        path = self.repo / sync.DECISION_REL
        path.write_text(path.read_text(encoding="utf-8").replace("[x]", "[ ]"), encoding="utf-8")
        bad = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(1, bad.returncode, bad.stdout + bad.stderr)
        self.assertIn("| 결정 | D1 | 누락 |", bad.stdout)


if __name__ == "__main__":
    unittest.main()
