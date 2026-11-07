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
FINAL_ITER = 6000  # lead decision 11/06: EX-41 ends at 6000
P1_MARKER = Path("D:/mai-tmp/gpu/PRIORITY_BUSY_GPU1")
TRAIN_MARKER = Path("D:/mai-tmp/gpu/TRAINING_BUSY_GPU0")
DISPATCH = Path(__file__).resolve().parents[1] / "gpu_jobs" / "dispatch.py"
GPU1 = "1"
P1_IDLE_MINUTES = 10       # a P1 owner that keeps GPU1 under 5 % this long is stuck (I11: 30 min)
GPU1_IDLE_MIB = 4000      # below this no Kit job is running on GPU1
LONG_UNIT_MINUTES = 45     # a unit longer than this can push a P1 score past its boundary
P4_LOW_WATER = 3           # queue the next filler before the last ones start (I15)
# I36: no evaluation output for 30 min and <=0.10 CPU seconds across a 2 s
# sample means a score attempt is waiting, not evaluating. Sample only stale jobs.
I36_STALE_SECONDS = 30 * 60
I36_CPU_SAMPLE_SECONDS = 2.0
I36_CPU_DELTA_MAX = 0.10


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


def _owner_recent_child(pid: int, minutes: float) -> bool:
    """True when the P1 owner has a descendant process started within `minutes` (I11 progress)."""
    import time
    try:
        kids = psutil.Process(pid).children(recursive=True)
    except (psutil.Error, ValueError):
        return False
    t = time.time()
    return any(t - k.create_time() < minutes * 60 for k in kids if k.is_running())


def _cpu_tree_seconds(pid: int) -> tuple[float, float] | None:
    try:
        owner = psutil.Process(pid)
        created = owner.create_time()
        processes = [owner, *owner.children(recursive=True)]
        total = 0.0
        for process in processes:
            try:
                times = process.cpu_times()
                total += times.user + times.system
            except psutil.Error:
                continue
        return created, total
    except (psutil.Error, ValueError):
        return None


def _cpu_tree_delta(pid: int) -> float | None:
    before = _cpu_tree_seconds(pid)
    if before is None:
        return None
    time.sleep(I36_CPU_SAMPLE_SECONDS)
    after = _cpu_tree_seconds(pid)
    if after is None or before[0] != after[0]:
        return None
    return max(0.0, after[1] - before[1])


def _latest_output_file(path: Path) -> float | None:
    try:
        return max((entry.stat().st_mtime for entry in path.rglob('*') if entry.is_file()),
                   default=None)
    except OSError:
        return None


def score_attempt_wait(run_root: Path, now: float, procs, items,
                       cpu_delta=None) -> tuple[str, str, str]:
    """I36: check active score-watch attempts and its running evaluation queue jobs."""
    cpu_delta = cpu_delta or _cpu_tree_delta
    run_norm = str(run_root).replace('\\', '/').casefold()
    owners = [(p, c) for p, c in procs
              if 'ex41_score_watch' in c and run_norm in c.replace('\\', '/').casefold()]
    owner_pid = getattr(owners[0][0], 'pid', None) if owners else None
    candidates = []
    for job in items:
        if (job.get('state') not in ('실행', 'running')
                or job.get('kind') not in ('eval', 'evaluation')
                or job.get('owner') != 'ex41_score_watch'):
            continue
        args = job.get('argv') or []
        if '--out' not in args:
            continue
        output = Path(args[args.index('--out') + 1])
        if run_norm not in str(output).replace('\\', '/').casefold():
            continue
        candidates.append((f"queue {job.get('id')}", job.get('run_at'), output, job.get('pid')))
    for receipt in (run_root / 'eval' / 'score-watch').glob('model_*/attempt.json'):
        try:
            row = json.loads(receipt.read_text(encoding='utf-8'))
            if row.get('state') == 'running' and row.get('source'):
                candidates.append((f"attempt m{row.get('iteration')}", receipt.stat().st_mtime,
                                   Path(row['source']), owner_pid))
        except (OSError, ValueError):
            continue
    stalled = []
    for label, started, output, pid in candidates:
        if not isinstance(started, (int, float)) or now - started <= I36_STALE_SECONDS:
            continue
        newest = _latest_output_file(output)
        if newest is not None and now - newest <= I36_STALE_SECONDS:
            continue
        delta = cpu_delta(pid) if isinstance(pid, int) else None
        if delta is None or delta <= I36_CPU_DELTA_MAX:
            stalled.append(f"{label}: age={(now - started)/60:.0f}m "
                           f"output_age={('missing' if newest is None else f'{(now-newest)/60:.0f}m')} "
                           f"cpu_delta={delta}")
    return ('FAIL' if stalled else 'OK', 'I36 score_wait',
            '; '.join(stalled) if stalled else f'{len(candidates)} active score attempts progressing or fresh')


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
    final = sorted(Path(run_root).glob(f"main/*/model_{FINAL_ITER}.pt"))
    if train:
        out.append(("OK", "train", f"{len(train)} train_start for this run"))
    elif final:
        out.append(("OK", "train", f"finished: {final[0].name} present (planned end {FINAL_ITER})"))
    else:
        out.append(("FAIL", "train", f"0 train_start for this run"))
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
    # Items parked with a future start (e.g. 11/05 13:3x broken stage videos) cannot fill GPU1 now.
    waiting = [j for j in items if j.get("gpu") in (1, None) and j.get("state") == "대기"
               and (j.get("start") is None or j["start"] <= now)]
    out.append(("WARN" if len(waiting) < P4_LOW_WATER else "OK", "I15 gpu1_depth",
                f"{len(waiting)} GPU1 items waiting"))
    # I35: GPU0 work waiting but nothing running on GPU0 (fail-streak block stopped it 22:41~22:52).
    g0_wait = [j["id"] for j in items if j.get("gpu") == 0 and j.get("state") == "대기"
               and (j.get("start") is None or j["start"] <= now)]
    g0_run = [j["id"] for j in items if j.get("gpu") == 0 and j.get("state") == "실행"]
    out.append(("FAIL" if g0_wait and not g0_run and not train else "OK", "I35 gpu0_idle",
                f"GPU0 waiting {len(g0_wait)} · running {g0_run}"))
    out.append(score_attempt_wait(run_root, now, procs, items))
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
        # 11/06 06:31: a stage-end push ladder starts one Kit child per cell; between cells GPU1
        # drops to desktop-only memory. A child spawned recently under the owner means progress.
        idle = (u is not None and u < GPU1_IDLE_MIB and age > P1_IDLE_MINUTES
                and not _owner_recent_child(int(m.get("pid") or 0), P1_IDLE_MINUTES))
        out.append(("FAIL" if idle else "OK", "I11 marker_idle",
                    f"marker {age:.0f} min · GPU1 {u} MiB · job {m.get('job')}"))
        # I24 (11/05 08:3x): a 2-3 h stage-end unit started before P1 and P1 waited behind it.
        long_run = [j["id"] for j in items if j.get("state") == "실행" and j.get("priority", 9) >= 2
                    and now - (j.get("run_at") or now) > LONG_UNIT_MINUTES * 60]
        out.append(("WARN" if long_run else "OK", "I24 p1_behind_long_unit",
                    f"P1 marker present while units running > {LONG_UNIT_MINUTES} min: {long_run}"))
    else:
        out.append(("OK", "I11 marker", "no P1 marker"))
    out.append(next_boundary_score(run_root, now))
    return out


SECONDS_PER_UPDATE = 28.0   # 11/05 measured 27-29 s
SCORE_MARGIN_MINUTES = 20   # after 2251 the pause budget is spent: one late score freezes DR (I29)


def next_boundary_score(run_root: Path, now: float, it: int | None = None,
                        scores: list[str] | None = None) -> tuple[str, str, str]:
    """The score that boundary b+1 needs is m(b-250); warn when it is missing close to b+1."""
    if it is None:
        try:
            main = next((run_root / "main").iterdir())
            last = (main / "train_extra.jsonl").read_bytes().rstrip().rsplit(b"\n", 1)[-1]
            it = int(json.loads(last)["it"])
        except (OSError, StopIteration, ValueError, KeyError):
            return ("WARN", "I29 next_score", "training iteration unreadable")
    boundary = (it // 250) * 250 + 251 if it % 250 else it + 1
    need = boundary - 251
    if scores is None:
        scores = [p.name for p in (run_root / "eval" / "scores").glob("score_*.json")]
    have = any(n.startswith(f"score_{need}_") for n in scores)
    minutes = (boundary - it) * SECONDS_PER_UPDATE / 60
    level = "OK" if have or need < 250 or minutes > SCORE_MARGIN_MINUTES else "WARN"
    return (level, "I29 next_score",
            f"boundary {boundary} in ~{minutes:.0f} min needs m{need}: {'present' if have else 'missing'}")


WORKLIST = Path("D:/mai-wt/foothold-lab/lead-worklist-1103/inbox/jay/20261104-ex41-restart/WORKLIST.tsv")
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def _evidence_present(spec: str) -> bool:
    """`path` exists, or `path::text` exists and contains text. '-' never counts as evidence."""
    if not spec or spec == "-":
        return False
    path, _, needle = spec.partition("::")
    p = Path(path)
    if not p.exists():
        return False
    if not needle:
        return True
    try:
        return needle in p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _decided_at_iso(value: str) -> bool:
    from datetime import datetime
    if not value or "T" not in value:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def worklist(path: Path, now: float, it: int | None) -> list[tuple[str, str, str]]:
    """W (팀장 11/06 17:2x): planned work is read by the check, not remembered.

    An open item whose due (`at:YYYY-MM-DDTHH:MM` or `iter:N`) has passed without its evidence
    file is FAIL; due within 30 min (or 50 updates) is WARN. The top three open items are listed.
    """
    import csv
    from datetime import datetime
    try:
        rows = list(csv.DictReader(path.open(encoding="utf-8"), delimiter="\t"))
    except OSError:
        return [("FAIL", "W worklist", f"worklist unreadable: {path}")]
    out, todo = [], []
    for r in rows:
        if r.get("status") == "done":
            if not _evidence_present(r.get("evidence", "")) or not _decided_at_iso(r.get("decided_at", "")):
                out.append(("FAIL", f"W {r['id']}", "done without evidence or ISO decided_at"))
            continue
        if r.get("status") != "open":
            continue
        if _evidence_present(r.get("evidence", "")):
            out.append(("WARN", f"W {r['id']}", "evidence present but status still open · mark done"))
            continue
        due, level = r.get("due", "-"), "OK"
        if due.startswith("at:"):
            t = datetime.strptime(due[3:], "%Y-%m-%dT%H:%M").timestamp()
            level = "FAIL" if now >= t else ("WARN" if t - now < 1800 else "OK")
        elif due.startswith("iter:") and it is not None:
            n = int(due[5:])
            level = "FAIL" if it >= n else ("WARN" if n - it <= 50 else "OK")
        if level != "OK":
            out.append((level, f"W {r['id']}", f"{r['priority']} {r['owner']} due {due} · {r['what'][:70]}"))
        todo.append(r)
    todo.sort(key=lambda r: (PRIORITY_ORDER.get(r.get("priority"), 9), r.get("due", "")))
    top = " | ".join(f"{r['id']} {r['priority']} {r['what'][:40]}" for r in todo[:3])
    out.append(("OK", "W next", f"{len(todo)} open · next: {top}"))
    return out


def _train_iter(run_root: Path) -> int | None:
    try:
        main_dir = next((run_root / "main").iterdir())
        last = (main_dir / "train_extra.jsonl").read_bytes().rstrip().rsplit(b"\n", 1)[-1]
        return int(json.loads(last)["it"])
    except (OSError, StopIteration, ValueError, KeyError):
        return None


def main(argv: list[str]) -> int:
    run_root = Path(argv[0])
    rows = check(run_root)
    rows += worklist(WORKLIST, time.time(), _train_iter(run_root))
    if "--json" in argv:
        print(json.dumps([{"level": a, "check": b, "detail": c} for a, b, c in rows], ensure_ascii=False))
    else:
        for a, b, c in rows:
            print(f"{a:4s} {b:22s} {c}")
    return 1 if any(a == "FAIL" for a, _, _ in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
