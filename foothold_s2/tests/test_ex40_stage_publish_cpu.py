"""Known-input checks for EX-40 stage document delivery, without Kit or network."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from foothold_s2.ex40_stage_publish import BRANCH, FEET, MODES, STAGE_DIR, _draw_charts, publish


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def report(stage: str, update: int) -> dict:
    w15 = {f"{mode}/cmd{i:02d}": {"alive_envs_at_end": 60 - i,
            "tracking_medians": {"vx_abs_error_mean_alive_mps": i / 100,
                                 "vy_abs_error_mean_alive_mps": i / 200,
                                 "wz_abs_error_mean_alive_radps": i / 300}}
            for mode in MODES for i in range(13)}
    stand = {mode: {"contact_left_right_gap_median": .1,
             "feet": {foot: {"sole_gap_p95_m": .005, "mean_fz_over_mg": .25,
                              "contact_fraction_gt1n": .9} for foot in FEET}}
             for mode in MODES}
    return {"stage": stage, "checkpoint_iteration": update, "checkpoint_sha256": "a" * 64,
            "previous_stage": None, "previous_checkpoint_iteration": None,
            "current": {"w15": w15, "w57": {}, "stand": stand,
                        "source_sha256": {"map64": "b" * 64}},
            "previous": None, "dr_previous": None,
            "dr_current": {"state": "측정", "scale": .4, "actual_samples": {
                "mass": {"min": .8, "max": 1.2, "mean": 1., "count": 10}}},
            "gains": [], "losses": [], "unchanged": [], "caution": "repeat band ±3/64"}


def fake_repo(tmp_path: Path) -> tuple[Path, Path]:
    bare, repo = tmp_path / "remote.git", tmp_path / "docs"
    bare.mkdir()
    git(bare, "init", "--bare", "-q")
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "CPU Test")
    git(repo, "config", "user.email", "cpu@example.invalid")
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "checkout", "-b", BRANCH)
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-qm", "baseline")
    git(repo, "push", "-q", "origin", f"HEAD:{BRANCH}")
    return bare, repo


def test_chart_five_raw_value_pngs(tmp_path):
    charts = _draw_charts([report("B0", 1500), report("B1", 3000)], tmp_path, "RESULT-test")
    assert len(charts) == 5
    assert all(path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" for path in charts)
    assert {path.stem.rsplit("_", 2)[-1] for path in charts}


def test_fake_git_scoped_commit_and_push_then_no_duplicate(tmp_path):
    bare, repo = fake_repo(tmp_path)
    out = tmp_path / "out"
    report_root = out / "stage_reports"
    report_root.mkdir(parents=True)
    row = report("B0", 1500)
    (report_root / "stage_B0_m1500.json").write_text(json.dumps(row), encoding="utf-8")
    sent = []
    result = publish(row, report_root, out, repo, tmp_path / "sender.py", available_update=1500,
                     sender=lambda script, path: sent.append(path.read_text(encoding="utf-8")) or True)
    assert result["state"] == "sent" and len(sent) == 1
    assert "GitHub 보고서:" in sent[0] and result["commit"] in sent[0]
    changed = git(repo, "show", "--pretty=format:", "--name-only", "HEAD").splitlines()
    assert len(changed) == 6 and all(name.startswith(STAGE_DIR.as_posix() + "/") for name in changed)
    assert git(bare, "rev-parse", f"refs/heads/{BRANCH}") == result["commit"]
    again = publish(row, report_root, out, repo, tmp_path / "sender.py", available_update=3000,
                    sender=lambda *_: pytest.fail("duplicate Telegram"))
    assert again == result
    assert not git(repo, "status", "--porcelain")


def test_dirty_unowned_file_and_wrong_branch_rejected(tmp_path):
    _, repo = fake_repo(tmp_path)
    out = tmp_path / "out"
    (out / "stage_reports").mkdir(parents=True)
    row = report("B0", 1500)
    (repo / "someone.txt").write_text("unowned", encoding="utf-8")
    with pytest.raises(ValueError, match="dirty"):
        publish(row, out / "stage_reports", out, repo, tmp_path / "sender.py",
                available_update=1500, sender=lambda *_: True)
    assert not (repo / STAGE_DIR).exists()
    (repo / "someone.txt").unlink()
    with pytest.raises(ValueError, match="unapproved"):
        publish(row, out / "stage_reports", out, repo, tmp_path / "sender.py",
                available_update=1500, sender=lambda *_: True, branch="main")


def test_push_failure_notifies_and_waits_until_next_stage(tmp_path, monkeypatch):
    bare, repo = fake_repo(tmp_path)
    out = tmp_path / "out"
    report_root = out / "stage_reports"
    report_root.mkdir(parents=True)
    row = report("B0", 1500)
    (report_root / "stage_B0_m1500.json").write_text(json.dumps(row), encoding="utf-8")
    from foothold_s2 import ex40_stage_publish as publishing
    real_run = publishing._run

    def reject_push(path, *args):
        if args[0] == "push":
            raise RuntimeError("git push failed: simulated remote rejection")
        return real_run(path, *args)

    monkeypatch.setattr(publishing, "_run", reject_push)
    sent = []
    failed = publish(row, report_root, out, repo, tmp_path / "sender.py", available_update=1500,
                     sender=lambda script, path: sent.append(path.read_text(encoding="utf-8")) or True)
    assert failed["state"] == "push_failed" and failed["link"] is None
    assert "push 실패" in sent[0] and "GitHub 보고서:" not in sent[0]
    held = publish(row, report_root, out, repo, tmp_path / "sender.py", available_update=1500,
                   sender=lambda *_: pytest.fail("same-stage retry"))
    assert held == failed
    monkeypatch.setattr(publishing, "_run", real_run)
    retried = publish(row, report_root, out, repo, tmp_path / "sender.py", available_update=3000,
                      sender=lambda script, path: sent.append(path.read_text(encoding="utf-8")) or True)
    assert retried["state"] == "sent" and len(sent) == 2
    assert git(bare, "rev-parse", f"refs/heads/{BRANCH}") == retried["commit"]
