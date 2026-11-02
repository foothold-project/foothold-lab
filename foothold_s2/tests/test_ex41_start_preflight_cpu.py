from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from foothold_s2.ex41_start_preflight import (
    audit_train_source,
    inspect_train_argv,
    inspect_fixed_worktree,
    verify_parent_checkpoint,
)
from foothold_s2.scripts.make_ex41_playlists import create_playlists


REPO = Path(__file__).resolve().parents[2]


def git(path: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(path), *args], text=True,
                            encoding="utf-8", capture_output=True, check=True)
    return result.stdout.strip()


def make_git_repo(path: Path) -> None:
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.name", "CPU test")
    git(path, "config", "user.email", "cpu-test@example.invalid")
    (path / "seed.txt").write_text("fixture\n", encoding="utf-8")
    git(path, "add", "seed.txt")
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "fixture"], check=True)
    git(path, "checkout", "--detach", "HEAD")


class Ex41PreflightTests(unittest.TestCase):
    def test_detached_clean_worktree_accepts_exact_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            make_git_repo(repo)
            head = git(repo, "rev-parse", "HEAD")
            row = inspect_fixed_worktree(repo, expected_head=head)
            self.assertTrue(row["detached"])
            self.assertTrue(row["clean"])
            self.assertEqual(row["head"], head)

    def test_attached_or_dirty_worktree_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "attached"
            repo.mkdir()
            git(repo, "init", "-q")
            git(repo, "config", "user.name", "CPU test")
            git(repo, "config", "user.email", "cpu-test@example.invalid")
            (repo / "seed.txt").write_text("fixture\n", encoding="utf-8")
            git(repo, "add", "seed.txt")
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
            with self.assertRaisesRegex(ValueError, "detached"):
                inspect_fixed_worktree(repo)
            git(repo, "checkout", "--detach", "HEAD")
            (repo / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not clean"):
                inspect_fixed_worktree(repo)

    def test_manifest_parent_sha_and_progress_are_all_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            run.mkdir()
            checkpoint = run / "model_6000.pt"
            checkpoint.write_bytes(b"known parent bytes")
            digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            manifest = {"checkpoints": {checkpoint.name: digest},
                        "progress": {"completed_updates": 6001}}
            (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            row = verify_parent_checkpoint(checkpoint, digest)
            self.assertTrue(row["verified"])
            self.assertEqual(row["completed_updates"], 6001)
            old_parent = run / "model_7500.pt"
            old_parent.write_bytes(b"old parent bytes")
            with self.assertRaisesRegex(ValueError, "model_6000.pt"):
                verify_parent_checkpoint(old_parent, hashlib.sha256(old_parent.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                verify_parent_checkpoint(checkpoint, "0" * 64)
            manifest["progress"]["completed_updates"] = 499
            (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "progress"):
                verify_parent_checkpoint(checkpoint, digest)

    def test_source_audit_is_static_and_does_not_claim_runtime(self):
        row = audit_train_source(REPO)
        self.assertEqual(row["parser_execution"], "source_ast_and_safe_rsl_args_only")
        self.assertEqual(row["environment_import"], "not_run")
        self.assertEqual(row["kit_launch"], "not_run")
        self.assertIn("--resume_from", row["required_flags_source_checked"])

    def test_actual_train_start_and_installed_rsl_args_parse_candidate(self):
        argv = ["--task", "FootholdS2-Go2-S2-SB-v0", "--num_envs", "3072",
                "--max_iterations", "6500", "--resume_from", "model_6000.pt",
                "--distributed", "--run_name", "EX-41-B-cpu-dry",
                "--headless", "--device", "cuda:1"]
        row = inspect_train_argv(REPO, argv)
        self.assertEqual(row["max_iterations"], 6500)
        self.assertEqual(row["device"], "cuda:1")
        self.assertFalse(row["applauncher_imported"])
        self.assertFalse(row["training_started"])

    def test_candidate_parser_rejects_implicit_device_or_low_update_target(self):
        base = ["--task", "FootholdS2-Go2-S2-SB-v0", "--num_envs", "3072",
                "--max_iterations", "6000", "--resume_from", "model_6000.pt",
                "--distributed", "--run_name", "EX-41-B-cpu-dry", "--headless"]
        with self.assertRaisesRegex(ValueError, "above m6000"):
            inspect_train_argv(REPO, base + ["--device", "cuda:1"])
        base[base.index("--max_iterations") + 1] = "6500"
        with self.assertRaisesRegex(ValueError, "exactly one --headless and --device"):
            inspect_train_argv(REPO, base)

    def test_playlist_paths_are_explicit_and_fail_list_is_a_subset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "videos"
            run = root / "EX-41-m07500"
            run.mkdir(parents=True)
            (run / "case-ok.mp4").write_bytes(b"ok")
            (run / "case-fail.mp4").write_bytes(b"fail")
            (root / "not-an-ex41-run").mkdir()
            out = Path(tmp) / "playlists"
            paths = create_playlists(root, out)
            self.assertEqual({p.name for p in paths}, {
                "EX-41-m07500-all.m3u8", "EX-41-m07500-fail.m3u8"})
            all_rows = paths[0].read_text(encoding="utf-8")
            fail_rows = (out / "EX-41-m07500-fail.m3u8").read_text(encoding="utf-8")
            self.assertIn("case-ok.mp4", all_rows)
            self.assertIn("case-fail.mp4", all_rows)
            self.assertIn("case-fail.mp4", fail_rows)
            self.assertNotIn("case-ok.mp4", fail_rows)


if __name__ == "__main__":
    unittest.main()
