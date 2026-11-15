"""CPU CLI contracts. Real files and Git objects, no GPU or mocked Git."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1]


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tools = self.root / '_out/tools'
        self.tools.mkdir(parents=True)
        for src in TOOLS.glob('*.py'):
            shutil.copy2(src, self.tools / src.name)
        self.plan = self.root / 'inbox/jay/20261028-plan'
        self.plan.mkdir(parents=True)
        self.wl = self.plan / 'WORKLIST.md'
        self.wl.write_text('## 확정\n- D57 졸업선 13 명령 생존 60/64 추종 오차 0.15\n', encoding='utf-8')
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'fixture')
        self.sha = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True, encoding='utf-8')

    def cli(self, script, *args):
        return subprocess.run([sys.executable, str(self.tools / script), *args], cwd=self.root,
                              env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                              text=True, encoding='utf-8', capture_output=True)

    def card(self, text):
        (self.plan / 'CARD.md').write_text(text, encoding='utf-8')

    def gate_rows(self, state):
        self.wl.write_text(f'| W1 | prerequisite | owner | - | {state} |\n'
                           '| W2 | next | owner | W1 | 대기 |\n', encoding='utf-8')

    def test_keywordless_d57_is_hit(self):
        r = self.cli('decision_check.py', '--text', '졸업선 13 명령 생존 60/64 추종 오차 0.15')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('HIT D57:', r.stdout)

    def test_closed_missing_proof_fails(self):
        self.card('- [x] R99-1 완료 · 증거 proof.json\n')
        r = self.cli('worklist_check.py')
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn('proof.json', r.stdout)

    def test_gate_done_with_missing_proof_fails(self):
        self.gate_rows('끝 · 증거 proof.json')
        r = self.cli('worklist_gate.py', 'W2')
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn('proof.json', r.stdout)

    def test_real_proof_and_commit_pass(self):
        (self.plan / 'proof.json').write_text('{}')
        self.card(f'- [x] R99-1 증거 `proof.json` · 커밋 {self.sha[:8]}\n')
        r = self.cli('worklist_check.py')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_missing_commit_fails_even_with_proof(self):
        (self.plan / 'proof.json').write_text('{}')
        self.card('- [x] R99-1 증거 proof.json · 커밋 deadbeef\n')
        r = self.cli('worklist_check.py')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('MISSING_COMMIT deadbeef', r.stdout)

    def test_missing_binary_path_not_hidden_by_valid_commit(self):
        self.card(f'- [x] R99-1 증거 proof.bin · 커밋 {self.sha}\n')
        r = self.cli('worklist_check.py')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('MISSING_PATH proof.bin', r.stdout)

    def test_missing_backup_not_confused_with_existing_json(self):
        (self.plan / 'proof.json').write_text('{}')
        self.card('- [x] R99-1 증거 proof.json.bak\n')
        r = self.cli('worklist_check.py')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('proof.json.bak', r.stdout)

    def test_remote_proof_is_unverified(self):
        self.card('- [x] R99-1 증거 [report](https://example.invalid/proof.json)\n')
        r = self.cli('worklist_check.py')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('UNVERIFIED_REMOTE', r.stdout)

    def test_missing_extensionless_path_not_hidden_by_commit(self):
        self.card(f'- [x] R99-1 증거 evidence/proof · 커밋 {self.sha}\n')
        r = self.cli('worklist_check.py')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('MISSING_PATH evidence/proof', r.stdout)

    def test_keywordless_d53_and_d54(self):
        self.wl.write_text('## 확정\n- D53 영상 머리줄 policy map eval_gt\n'
                           '- D54 정본 EX-38 m3001 기록부 계보\n', encoding='utf-8')
        for draft, did in [('영상 머리줄 policy map', 'D53'), ('정본 m3001 기록부', 'D54')]:
            with self.subTest(did=did):
                r = self.cli('decision_check.py', '--text', draft)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn('HIT ' + did + ':', r.stdout)

    def test_blob_sha_is_not_a_commit(self):
        blob = self.git('hash-object', '-w', str(self.wl)).strip()
        self.card(f'- [x] R99-1 커밋 {blob}\n')
        r = self.cli('worklist_check.py')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('MISSING_COMMIT', r.stdout)

    def test_all_refs_checked_not_just_first(self):
        (self.plan / 'proof.json').write_text('{}')
        self.card(f'- [x] R99-1 증거 proof.json · absent.json · {self.sha}\n')
        r = self.cli('worklist_check.py')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('absent.json', r.stdout)

    def test_no_evidence_is_not_completion(self):
        self.card('- [x] R99-1 끝 20261030\n')
        r = self.cli('worklist_check.py')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('NO_EVIDENCE', r.stdout)

    def test_open_stays_open_with_valid_proof(self):
        self.card(f'- [ ] R99-1 {self.sha}\n')
        self.assertEqual(self.cli('worklist_check.py').returncode, 1)

    def test_missing_plan_not_empty_success(self):
        r = self.cli('worklist_check.py', str(self.root / 'absent'))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_path_with_spaces_root_relative_and_line_suffix(self):
        (self.root / 'proof space.json').write_text('{}')
        self.card('- [x] R99-1 증거 [report](<proof space.json>) · `proof space.json:3`\n')
        r = self.cli('worklist_check.py')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_absolute_path(self):
        proof = self.root / 'proof.json'
        proof.write_text('{}')
        self.card(f'- [x] R99-1 증거 `{proof}`\n')
        self.assertEqual(self.cli('worklist_check.py').returncode, 0)

    def test_hash_in_missing_path_not_valid_commit(self):
        self.card(f'- [x] R99-1 증거 `logs/{self.sha}/proof.json`\n')
        r = self.cli('worklist_check.py')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('MISSING_PATH', r.stdout)

    def test_gate_real_evidence_passes(self):
        self.gate_rows(f'끝 · 커밋 {self.sha}')
        r = self.cli('worklist_gate.py', 'W2')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_gate_done_without_evidence_fails(self):
        self.gate_rows('끝')
        self.assertEqual(self.cli('worklist_gate.py', 'W2').returncode, 3)

    def test_gate_missing_commit_fails(self):
        self.gate_rows('끝 · 커밋 deadbeef')
        r = self.cli('worklist_gate.py', 'W2')
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn('MISSING_COMMIT', r.stdout)

    def test_gate_partial_and_negated_done_do_not_pass(self):
        for state in ['P1 끝 · P2 대기', '끝 아님', '끝나지 않음']:
            with self.subTest(state=state):
                self.gate_rows(state + ' · 커밋 ' + self.sha)
                r = self.cli('worklist_gate.py', 'W2')
                self.assertEqual(r.returncode, 3, r.stdout + r.stderr)

    def test_gate_unknown_prerequisite_fails(self):
        self.wl.write_text('| W2 | next | owner | W99 | 대기 |\n', encoding='utf-8')
        self.assertEqual(self.cli('worklist_gate.py', 'W2').returncode, 3)

    def test_gate_non_w_dependency_not_silently_satisfied(self):
        self.wl.write_text('| W2 | next | owner | EX-36 끝 | 대기 |\n', encoding='utf-8')
        self.assertEqual(self.cli('worklist_gate.py', 'W2').returncode, 3)

    def test_gate_no_prerequisite_passes(self):
        self.gate_rows('대기')
        self.assertEqual(self.cli('worklist_gate.py', 'W1').returncode, 0)

    def test_decision_explicit_keyword_and_id_still_hit(self):
        self.wl.write_text('## 확정\n- D21 시드 42 · 키워드: seed\n', encoding='utf-8')
        for draft in ['SEED 43', 'D21 다시 논의']:
            with self.subTest(draft=draft):
                r = self.cli('decision_check.py', '--text', draft)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn('HIT D21:', r.stdout)

    def test_fallback_does_not_match_numeric_only_or_one_word(self):
        for draft in ['13 60/64 0.15', '명령', '완전히 다른 이야기', '']:
            with self.subTest(draft=draft):
                r = self.cli('decision_check.py', '--text', draft)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn('hits 0', r.stdout)

    def test_empty_decision_registry_is_error(self):
        self.wl.write_text('## 확정\n', encoding='utf-8')
        self.assertEqual(self.cli('decision_check.py', '--text', '질문').returncode, 2)


if __name__ == '__main__':
    unittest.main()
