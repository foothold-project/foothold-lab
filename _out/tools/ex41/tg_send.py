"""Send a lead Telegram report safely (incidents I01 · I02 · 11/05).

Usage: python tg_send.py <message.txt>
- Refuses a message whose first line does not start with "[EX-" (lead layout) or that is over 15 lines.
- Turns a bare issue number "#555" into its full URL so it opens on the phone.
- Writes the outbox, reads it back and compares the SHA-256 before sending; never sends what it did
  not just write (11/05 00:06 an earlier outbox was resent because the write had failed unseen).
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

OUTBOX = Path("C:/ssd-cleanup-logs/tg-outbox.txt")
SENDER = Path("C:/ssd-cleanup-logs/tg-send.ps1")
REPO_ISSUES = "https://github.com/foothold-project/foothold-lab/issues/"


def prepare(text: str) -> str:
    text = re.sub(r"(?<![\w/])#(\d{2,5})\b", lambda m: REPO_ISSUES + m.group(1), text.strip()) + "\n"
    lines = text.strip().splitlines()
    if not lines or not lines[0].startswith("[EX-"):
        raise ValueError("first line must start with [EX-")
    if len(lines) > 15:
        raise ValueError(f"{len(lines)} lines > 15")
    return text


def posix_paths(environ=os.environ) -> tuple[Path, Path]:
    """Linux pins (7): outbox and sender come from the machine profile, never from the C: constants above.

    The Linux profile (machines/AI-WS01-linux.yaml) fills telegram_outbox / telegram_script from TELEGRAM_OUTBOX /
    TELEGRAM_SCRIPT. This ops branch has no machine_profile module, so it reads the profile when it can import it and
    the same two variables otherwise. The sender is the Python one (mai-tools tools/tg-send/tg_send.py)."""
    try:
        from foothold_s2.machine_profile import machine_path
        return machine_path("telegram_outbox"), machine_path("telegram_script")
    except ImportError:
        pass
    out, script = environ.get("TELEGRAM_OUTBOX"), environ.get("TELEGRAM_SCRIPT")
    if not out or not script:
        raise RuntimeError("TELEGRAM_OUTBOX and TELEGRAM_SCRIPT must be set off Windows (machine profile)")
    return Path(out), Path(script)


def send(text: str, outbox: Path | None = None, sender: Path | None = None, run=subprocess.run,
         platform: str = sys.platform) -> str:
    if platform != "win32":
        return send_posix(text, outbox, sender, run)
    outbox = OUTBOX if outbox is None else outbox
    sender = SENDER if sender is None else sender
    body = prepare(text)
    outbox.write_text(body, encoding="utf-8", newline="\n")
    back = outbox.read_text(encoding="utf-8")
    if hashlib.sha256(back.encode()).hexdigest() != hashlib.sha256(body.encode()).hexdigest():
        raise RuntimeError("outbox read-back differs; not sending")
    r = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(sender)],
            capture_output=True, text=True)
    if "ok=True" not in (r.stdout or ""):
        raise RuntimeError(f"send failed: {r.stdout!r} {r.stderr!r}")
    return body.splitlines()[0]


def send_posix(text: str, outbox: Path | None, sender: Path | None, run=subprocess.run) -> str:
    """Same checks as the Windows path (layout, read-back SHA, "ok=True"), then the Python sender, no powershell."""
    if outbox is None or sender is None:
        p_out, p_sender = posix_paths()
        outbox, sender = outbox or p_out, sender or p_sender
    if Path(sender).suffix != ".py":
        raise RuntimeError(f"sender must be the Python tg_send.py off Windows, got {sender}")
    body = prepare(text)
    Path(outbox).parent.mkdir(parents=True, exist_ok=True)
    Path(outbox).write_text(body, encoding="utf-8", newline="\n")
    back = Path(outbox).read_text(encoding="utf-8")
    if hashlib.sha256(back.encode()).hexdigest() != hashlib.sha256(body.encode()).hexdigest():
        raise RuntimeError("outbox read-back differs; not sending")
    r = run([sys.executable, str(sender), "--outbox", str(outbox)], capture_output=True, text=True)
    if r.returncode != 0 or "ok=True" not in (r.stdout or ""):
        raise RuntimeError(f"send failed: {r.stdout!r} {r.stderr!r}")
    return body.splitlines()[0]


if __name__ == "__main__":
    print("sent:", send(Path(sys.argv[1]).read_text(encoding="utf-8")))
