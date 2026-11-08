"""Linux pins (7): chain/runner.py Telegram sender on POSIX. CPU only, no network, no real send.

Ground: analyst REPORT-analyst-linux-windows-pins-1108 2 절 (S/chain/runner.py:178,186).
Counterexample before the fix: off Windows, default_tg_sender still ran ["powershell", ..., "C:/ssd-cleanup-logs/tg-send.ps1"]
and wrote the outbox to C:/ssd-cleanup-logs, so every alert was lost on Linux.
"""
import subprocess
import sys

import pytest

from foothold_s2.chain import runner


class Recorder:
    def __init__(self, rc=0, stdout="sent ok=True\n"):
        self.rc, self.stdout, self.calls = rc, stdout, []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, self.rc, stdout=self.stdout, stderr="")


@pytest.fixture
def posix(monkeypatch):
    monkeypatch.setattr(runner, "IS_WIN", False)


def test_posix_never_calls_powershell(posix, tmp_path, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(runner.subprocess, "run", rec)
    box = tmp_path / "tg" / "tg-outbox.txt"
    sender = tmp_path / "tg_send.py"
    ok = runner.default_tg_sender({"outbox": str(box), "script": str(sender)}, "[EX-42] 한글 &amp; 줄")
    assert ok is True
    cmd = rec.calls[0][0]
    assert "powershell" not in cmd
    assert cmd == [sys.executable, str(sender), "--outbox", str(box)]
    assert box.read_text(encoding="utf-8") == "[EX-42] 한글 &amp; 줄"


def test_posix_refuses_ps1_without_running_anything(posix, tmp_path, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(runner.subprocess, "run", rec)
    ok = runner.default_tg_sender({"outbox": str(tmp_path / "o.txt"), "script": "C:/ssd-cleanup-logs/tg-send.ps1"}, "x")
    assert ok is False and rec.calls == []


def test_posix_success_needs_ok_true_not_only_rc0(posix, tmp_path):
    # the ps1 prints "FAIL: ..." and still exits 0; the exit code alone took that for a sent message
    cfg = {"outbox": str(tmp_path / "o.txt"), "script": str(tmp_path / "s.py")}
    assert runner.posix_tg_sender(cfg, "x", run=Recorder(rc=0, stdout="FAIL: HTTP Error 400\n")) is False
    assert runner.posix_tg_sender(cfg, "x", run=Recorder(rc=1, stdout="sent ok=True\n")) is False
    assert runner.posix_tg_sender(cfg, "x", run=Recorder()) is True


def test_posix_reads_profile_when_config_has_no_paths(posix, tmp_path, monkeypatch):
    box, script = tmp_path / "box" / "tg-outbox.txt", tmp_path / "tg_send.py"
    req = "".join("  %s: %s\n" % (k, (tmp_path / k).as_posix()) for k in (
        "isaaclab_root", "isaac_sim_root", "conda_python", "rsl_rl_module",
        "s2_lab_root", "mai_tmp_root", "mai_worktree_root"))
    prof = tmp_path / "linux.yaml"
    prof.write_text("format: foothold-machine-profile/1\nmachine_id: test-linux\npaths:\n" + req
                        + "  telegram_outbox: ${TELEGRAM_OUTBOX}\n  telegram_script: ${TELEGRAM_SCRIPT}\n"
                        + "devices:\n  training: {cuda_index: 0, uuid: GPU-test0}\n"
                        + "  p1_evaluation: {cuda_index: 0, uuid: GPU-test0}\n"
                        + "  screen: {cuda_index: 1, uuid: GPU-test1}\n", encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_OUTBOX", str(box))
    monkeypatch.setenv("TELEGRAM_SCRIPT", str(script))
    rec = Recorder()
    assert runner.posix_tg_sender({}, "hello", run=rec, profile_path=prof) is True
    assert rec.calls[0][0][1:] == [str(script), "--outbox", str(box)]


def test_posix_missing_profile_value_fails_closed(posix, tmp_path, monkeypatch):
    monkeypatch.delenv("FOOTHOLD_MACHINE_PROFILE", raising=False)
    rec = Recorder()
    assert runner.posix_tg_sender({}, "x", run=rec, profile_path=tmp_path / "absent.yaml") is False
    assert rec.calls == []


def test_windows_call_is_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "IS_WIN", True)
    rec = Recorder(rc=0, stdout="")
    monkeypatch.setattr(runner.subprocess, "run", rec)
    box = tmp_path / "o.txt"
    assert runner.default_tg_sender({"outbox": str(box), "script": "C:/x/tg-send.ps1"}, "y") is True
    cmd, kw = rec.calls[0]
    assert cmd == ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "C:/x/tg-send.ps1"]
    assert kw["creationflags"] == 0x08000000 and kw["timeout"] == 90
