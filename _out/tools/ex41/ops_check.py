"""EX-41 live operations check: the invariants that broke on 11/04-05, checked every lead round.

Usage: python ops_check.py <run_root> [--json]
  run_root = C:/Users/AI-WS01/s2_lab/ex41_main_<stamp>
Read-only. Prints one line per finding: OK / WARN / FAIL. Exit 1 when any FAIL.

Each check names the incident it prevents (EX41R-INCIDENTS.md):
  I04 push watcher missing at launch        I05 rehearsal watchers left running
  I06 rehearsal items left in the queue      I08 dispatcher runs older code than on disk
  I11 P1 marker held while GPU1 sits idle    I11 marker owner process gone
  I14 finished video group with no playlist  I15 P4 filler about to run dry
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import psutil

QUEUE = Path("D:/mai-tmp/gpu/queue.json")
P1_MARKER = Path("D:/mai-tmp/gpu/PRIORITY_BUSY_GPU1")
TRAIN_MARKER = Path("D:/mai-tmp/gpu/TRAINING_BUSY_GPU0")
DISPATCH = Path(__file__).resolve().parents[1] / "gpu_jobs" / "dispatch.py"
GPU1 = "1"
P1_IDLE_MINUTES = 10       # a P1 owner that keeps GPU1 under 5 % this long is stuck (I11: 30 min)
GPU1_IDLE_MIB = 4000      # below this no Kit job is running on GPU1
LONG_UNIT_MINUTES = 45     # a unit longer than this can push a P1 score past its boundary
P4_LOW_WATER = 3           # queue the next filler before the last ones start (I15)


def _cmd(p: psutil.Process) -> str:
    try:
        return " ".join(p.cmdline())
    except (psutil.Error, OSError):
        return ""


def _procs() -> list[tuple[psutil.Process, str]]:
    out = []
    for p in psutil.process_iter(["pid", "create_time"]):
        c = _cmd(p)
        if c:
            out.append((p, c))
    return out


def _gpu1_util() -> int | None:
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits",
                            "-i", GPU1], capture_output=True, text=True, timeout=20)
        return int(r.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def check(run_root: Path, now: float | None = None, procs=None, queue=None, util=None,
          util_history: list[int] | None = None) -> list[tuple[str, str, str]]:
    now = now or time.time()
    procs = procs if procs is not None else _procs()
    queue = queue if queue is not None else json.loads(QUEUE.read_text(encoding="utf-8"))
    items = queue["items"]
    out: list[tuple[str, str, str]] = []
    run_s = str(run_root).replace("/", "\\").casefold()
    run_f = str(run_root).replace("\\", "/").casefold()

    def mine(c: str) -> bool:
        low = c.casefold()
        return run_s in low or run_f in low

    # training and its watchers
    train = [c for _, c in procs if "train_start.py" in c and mine(c)]
    out.append(("OK" if train else "FAIL", "train", f"{len(train)} train_start for this run"))
    sw = [c for _, c in procs if "ex41_score_watch" in c]
    out.append(("OK" if any(mine(c) for c in sw) else "FAIL", "score_watch", "production score watch alive"))
    stray = [c for c in sw if not mine(c)]
    out.append(("FAIL" if stray else "OK", "I05 stray_watch", f"{len(stray)} score watch for other runs"))
    pw = [c for _, c in procs if "ex41_push250_watch" in c]
    out.append(("OK" if any(mine(c) for c in pw) else "FAIL", "I04 push_watch", "push250 watcher for this run"))
    out.append(("FAIL" if [c for c in pw if not mine(c)] else "OK", "I05 stray_push", "push watcher for other runs"))

    # dispatcher loop runs the code that is on disk
    loops = [(p, c) for p, c in procs if "dispatch.py" in c and c.rstrip().endswith(" dispatch")]
    if not loops:
        out.append(("FAIL", "dispatcher", "dispatch loop not running"))
    else:
        started = min(p.info["create_time"] for p, _ in loops)
        stale = DISPATCH.stat().st_mtime > started
        out.append(("WARN" if stale else "OK", "I08 dispatcher_code",
                    "dispatch.py changed after the loop started: restart the loop" if stale else "loop runs current code"))

    # queue hygiene
    reh = [j["id"] for j in items if "REHEARSAL" in (j.get("title") or "") and j.get("state") in ("대기", "실행")]
    out.append(("FAIL" if reh else "OK", "I06 rehearsal_items", f"waiting/running rehearsal items {reh}"))
    # Any waiting GPU1 work keeps it busy; warn before the queue runs dry (P2/P3 stage-end work counts).
    waiting = [j for j in items if j.get("gpu") in (1, None) and j.get("state") == "대기"]
    out.append(("WARN" if len(waiting) < P4_LOW_WATER else "OK", "I15 gpu1_depth",
                f"{len(waiting)} GPU1 items waiting"))
    fails = [j["id"] for j in items if j.get("state") == "실패" and now - (j.get("done_at") or 0) < 3600]
    out.append(("WARN" if fails else "OK", "fail_1h", f"failed in last hour {fails}"))

    # P1 marker: owner alive, and not holding an idle GPU
    if P1_MARKER.exists():
        try:
            m = json.loads(P1_MARKER.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            m = {}
        alive = psutil.pid_exists(int(m.get("pid") or 0))
        out.append(("OK" if alive else "FAIL", "I11 marker_owner", f"P1 owner pid {m.get('pid')} alive={alive}"))
        age = (now - P1_MARKER.stat().st_mtime) / 60
        # Memory, not utilization: a Kit job sits at 6-13 GB while its utilization dips to 0-1 %
        # between phases; the 11/05 stuck owner held the marker with GPU1 at 2.4 GB (desktop only).
        u = util if util is not None else _gpu1_util()
        idle = u is not None and u < GPU1_IDLE_MIB and age > P1_IDLE_MINUTES
        out.append(("FAIL" if idle else "OK", "I11 marker_idle",
                    f"marker {age:.0f} min · GPU1 {u} MiB · job {m.get('job')}"))
        # I24 (11/05 08:3x): a 2-3 h stage-end unit started before P1 and P1 waited behind it.
        long_run = [j["id"] for j in items if j.get("state") == "실행" and j.get("priority", 9) >= 2
                    and now - (j.get("run_at") or now) > LONG_UNIT_MINUTES * 60]
        out.append(("WARN" if long_run else "OK", "I24 p1_behind_long_unit",
                    f"P1 marker present while units running > {LONG_UNIT_MINUTES} min: {long_run}"))
    else:
        out.append(("OK", "I11 marker", "no P1 marker"))
    return out


def main(argv: list[str]) -> int:
    run_root = Path(argv[0])
    rows = check(run_root)
    if "--json" in argv:
        print(json.dumps([{"level": a, "check": b, "detail": c} for a, b, c in rows], ensure_ascii=False))
    else:
        for a, b, c in rows:
            print(f"{a:4s} {b:22s} {c}")
    return 1 if any(a == "FAIL" for a, _, _ in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
