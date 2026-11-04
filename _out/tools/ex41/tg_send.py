"""Send a lead Telegram report safely (incidents I01 · I02 · 11/05).

Usage: python tg_send.py <message.txt>
- Refuses a message whose first line does not start with "[EX-" (lead layout) or that is over 15 lines.
- Turns a bare issue number "#555" into its full URL so it opens on the phone.
- Writes the outbox, reads it back and compares the SHA-256 before sending; never sends what it did
  not just write (11/05 00:06 an earlier outbox was resent because the write had failed unseen).
"""
from __future__ import annotations

import hashlib
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


def send(text: str, outbox: Path = OUTBOX, sender: Path = SENDER, run=subprocess.run) -> str:
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


if __name__ == "__main__":
    print("sent:", send(Path(sys.argv[1]).read_text(encoding="utf-8")))
