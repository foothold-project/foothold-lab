"""Linux pins (7): ex41/tg_send.py off Windows. CPU only, no network, no real send.

Ground: analyst REPORT-analyst-linux-windows-pins-1108 2 절 (O/ex41/tg_send.py:17,38).
Counterexample before the fix: send() wrote C:/ssd-cleanup-logs/tg-outbox.txt and ran ["powershell", ..., tg-send.ps1]
on every OS, so on Linux every lead report failed.
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tg_send  # noqa: E402

MSG = "[EX-42] 경계 보고 #555\n둘째 줄"


class Rec:
    def __init__(self, rc=0, out="sent ok=True\n"):
        self.rc, self.out, self.calls = rc, out, []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.rc, stdout=self.out, stderr="")


def test_counterexample_windows_path_is_powershell_and_c_drive():
    # still true on Windows, and it is what Linux used to get
    assert tg_send.OUTBOX == Path("C:/ssd-cleanup-logs/tg-outbox.txt")
    rec = Rec()
    with pytest.raises(OSError):        # no C:/ssd-cleanup-logs folder on a POSIX box or a clean temp
        tg_send.send(MSG, outbox=Path("/nonexistent-dir/x/tg-outbox.txt"), run=rec, platform="win32")


def test_linux_uses_python_sender_from_profile_env(tmp_path, monkeypatch):
    box, script = tmp_path / "tg" / "tg-outbox.txt", tmp_path / "tg_send.py"
    monkeypatch.setenv("TELEGRAM_OUTBOX", str(box))
    monkeypatch.setenv("TELEGRAM_SCRIPT", str(script))
    rec = Rec()
    first = tg_send.send(MSG, run=rec, platform="linux")
    assert first == "[EX-42] 경계 보고 https://github.com/foothold-project/foothold-lab/issues/555"
    assert rec.calls == [[sys.executable, str(script), "--outbox", str(box)]]
    assert "powershell" not in rec.calls[0]
    assert box.read_text(encoding="utf-8").endswith("둘째 줄\n")


def test_linux_without_profile_values_fails_before_writing(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_OUTBOX", raising=False)
    monkeypatch.delenv("TELEGRAM_SCRIPT", raising=False)
    rec = Rec()
    with pytest.raises(RuntimeError, match="TELEGRAM_OUTBOX"):
        tg_send.send(MSG, run=rec, platform="linux")
    assert rec.calls == []


def test_linux_refuses_ps1_sender(tmp_path):
    with pytest.raises(RuntimeError, match="Python"):
        tg_send.send(MSG, outbox=tmp_path / "o.txt", sender=Path("/x/tg-send.ps1"), run=Rec(), platform="linux")


def test_linux_failed_send_raises(tmp_path):
    kw = dict(outbox=tmp_path / "o.txt", sender=tmp_path / "s.py", platform="linux")
    with pytest.raises(RuntimeError, match="send failed"):
        tg_send.send(MSG, run=Rec(rc=1, out="FAIL: HTTP Error 400\n"), **kw)
    with pytest.raises(RuntimeError, match="send failed"):
        tg_send.send(MSG, run=Rec(rc=0, out="FAIL: x\n"), **kw)


def test_layout_checks_still_apply_on_linux(tmp_path):
    with pytest.raises(ValueError):
        tg_send.send("no prefix", outbox=tmp_path / "o.txt", sender=tmp_path / "s.py", run=Rec(), platform="linux")


def test_windows_call_unchanged(tmp_path):
    rec = Rec()
    tg_send.send(MSG, outbox=tmp_path / "o.txt", sender=Path("C:/x/tg-send.ps1"), run=rec, platform="win32")
    assert rec.calls == [["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(Path("C:/x/tg-send.ps1"))]]
