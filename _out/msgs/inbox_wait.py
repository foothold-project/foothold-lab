"""Wait for new orchestration messages after the coordinator moved to the mailbox shell (lead, 10/28 04:1x).

The lead pane is no longer the run consumer (check --run is fenced), so read the inbox without acking:
poll `orca orchestration inbox --json` every 20 s and exit, printing the new rows, once a sequence number
above the last seen one appears. The last seen sequence lives in _out/msgs/.inbox_seq.
Usage: python _out/msgs/inbox_wait.py [timeout_s]
"""
import json
import os
import pathlib
import subprocess
import sys
import time

STATE = pathlib.Path(__file__).with_name(os.environ.get("INBOX_STATE", ".inbox_seq"))
timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 3600.0


def rows():
    t = subprocess.run(["orca", "orchestration", "inbox", "--limit", "30", "--json"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace").stdout
    try:
        d = json.loads(t[t.find("{"):])
    except ValueError:
        return []
    return (d.get("result") or {}).get("messages") or []


seen = int(STATE.read_text()) if STATE.exists() else max((int(m["sequence"]) for m in rows()), default=0)
STATE.write_text(str(seen))
end = time.time() + timeout
while time.time() < end:
    new = sorted((m for m in rows() if int(m["sequence"]) > seen), key=lambda m: int(m["sequence"]))
    if new:
        for m in new:
            print(m["type"], m["from_handle"][5:13], m.get("subject", ""), "|",
                  (m.get("body") or "")[:1200].replace("\n", " / "))
        STATE.write_text(str(max(int(m["sequence"]) for m in new)))
        sys.exit(0)
    time.sleep(20)
print("timeout, no new message after sequence", seen)
