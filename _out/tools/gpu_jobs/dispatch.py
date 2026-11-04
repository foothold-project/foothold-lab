"""Read-only GPU job board and unit-boundary admission checks.

This tool never starts, signals, or kills a process. A lower-priority owner
must call ``gate`` before each new unit and yield after its current unit when
the answer is WAIT. Existing EX-35 and render owners retain their own gates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from datetime import datetime, timezone

try:
    import psutil
except ImportError:  # Unknown liveness must not grant GPU access.
    psutil = None


PRIORITIES = {0: "승인된 학습", 1: "판정용 평가", 2: "진단·평가", 3: "시드 반복", 4: "영상 렌더"}
STATES = {"대기", "실행", "끝", "실패", "취소"}
WAIT_TOKENS = ("waiting_for_checkpoint", "checkpoint_wait", "waiting for checkpoint",
               "waiting for new checkpoint", "waiting for next checkpoint",
               "new checkpoint pending", "새 저장본 대기", "다음 저장본 대기",
               "저장본 대기", "새 체크포인트 대기", "다음 체크포인트 대기", "체크포인트 대기")


def read_shared_bytes(path) -> bytes:
    """Read a whole file without ever blocking the writer's os.replace / rename.

    EX-41 died 11/04 01:13: training's os.replace(train_start_status.json) got PermissionError
    while some reader had the file open. On Windows this opens with FILE_SHARE_READ | WRITE |
    DELETE, reads and closes at once. Measured: replace is still denied while any handle is open,
    share-delete or not, so the only reader-side protection is a tiny open window and reading
    training files no more than every 10 s (the 1 s board refresh reads nvidia-smi only). The
    writer should retry os.replace on PermissionError.
    """
    import os
    if os.name != "nt":
        with open(path, "rb") as fh:
            return fh.read()
    with open_shared(path) as fh:  # closes the handle too
        return fh.read()


def open_shared(path):
    """Windows: binary read file object whose handle allows the writer to rename / replace."""
    import ctypes
    import msvcrt
    import os
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateFileW.restype = wintypes.HANDLE
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                              wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    GENERIC_READ, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL = 0x80000000, 3, 0x80
    share = 0x1 | 0x2 | 0x4  # FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
    h = k.CreateFileW(str(path), GENERIC_READ, share, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    if h is None or h == ctypes.c_void_p(-1).value:
        err = ctypes.get_last_error()
        if err in (2, 3):
            raise FileNotFoundError(2, "No such file", str(path))
        raise OSError(err, ctypes.FormatError(err), str(path))
    return os.fdopen(msvcrt.open_osfhandle(h, os.O_RDONLY | os.O_BINARY), "rb")


def read_shared_text(path, encoding="utf-8", errors="strict") -> str:
    return read_shared_bytes(path).decode(encoding, errors=errors)


def read_json(path: Path) -> dict:
    value = json.loads(read_shared_text(path, "utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def validate(config: dict) -> list[dict]:
    jobs = config.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("jobs must be a list")
    seen = set()
    required = {"id", "priority", "gpu", "owner_session", "preemptible", "state",
                "started_at", "ended_at", "output_path"}
    for job in jobs:
        if not isinstance(job, dict) or not required.issubset(job):
            raise ValueError("job has missing required fields")
        if job["id"] in seen or not isinstance(job["id"], str):
            raise ValueError("duplicate or invalid job id")
        seen.add(job["id"])
        if type(job["priority"]) is not int or job["priority"] not in PRIORITIES:
            raise ValueError(f"invalid priority: {job['id']}")
        if type(job["gpu"]) is not int or job["gpu"] not in (0, 1):
            raise ValueError(f"invalid GPU: {job['id']}")
        if job["state"] not in STATES:
            raise ValueError(f"invalid state: {job['id']}")
        if not job.get("command") and not job.get("pid"):
            raise ValueError(f"command or pid required: {job['id']}")
        if type(job["preemptible"]) is not bool:
            raise ValueError(f"preemptible must be bool: {job['id']}")
    return jobs


def pid_state(job: dict) -> str:
    pid = job.get("pid")
    if not pid:
        return "no_pid"
    if psutil is None:
        return "unknown"
    try:
        process = psutil.Process(int(pid))
        expected = job.get("pid_create_time")
        if expected is not None and abs(process.create_time() - float(expected)) > 0.1:
            return "pid_reused"
        return "live" if process.is_running() else "gone"
    except psutil.NoSuchProcess:
        return "gone"
    except (psutil.AccessDenied, OSError, ValueError):
        return "unknown"


def marker_state(path: Path) -> dict:
    try:
        marker = read_json(path)
    except FileNotFoundError:
        return {"present": False, "reason": "absent"}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"present": True, "reason": f"unreadable:{type(exc).__name__}"}
    pids = []
    for key, value in marker.items():
        if key == "pid" or key.endswith("_pid") or key.endswith("_pids"):
            pids.extend(value if isinstance(value, list) else [value])
    pids = [p for p in pids if type(p) is int and p > 0]
    if not pids or psutil is None:
        return {"present": True, "reason": "unknown_owner", "pids": pids}
    states = [pid_state({"pid": p}) for p in pids]
    present = any(s != "gone" for s in states)
    return {"present": present, "reason": "live_or_unknown_pid" if present else "stale_pids",
            "pids": pids}


def chain_wait(path: Path) -> dict:
    try:
        last = next((line.strip() for line in reversed(read_shared_text(path, "utf-8", "replace").splitlines())
                     if line.strip()), "")
    except OSError as exc:
        return {"waiting": False, "last": "", "error": type(exc).__name__}
    low = last.casefold()
    waiting = any(token in low for token in WAIT_TOKENS) or bool(
        re.search(r"대기.*(저장본|체크포인트)|(?:저장본|체크포인트).*대기", low))
    return {"waiting": waiting, "last": last}


def live_sources(config: dict) -> dict:
    sources = config.get("sources", {})
    marker = marker_state(Path(sources["priority_busy"]))
    chain = chain_wait(Path(sources["chain_log"]))
    try:
        render = read_json(Path(sources["render_state"]))
    except (OSError, ValueError, json.JSONDecodeError):
        render = {"state": "unknown", "pending": [], "current_job": None}
    return {"marker": marker, "chain": chain, "render": render}


def admission(config: dict, job_id: str, live: dict) -> tuple[bool, str]:
    jobs = validate(config)
    job = next((j for j in jobs if j["id"] == job_id), None)
    if job is None:
        raise ValueError(f"unknown job: {job_id}")
    if job["state"] != "대기":
        return False, f"not_waiting:{job['state']}"
    if not job.get("executable", True):
        return False, "unarmed_command"
    gpu, priority = job["gpu"], job["priority"]
    for higher in jobs:
        if higher["id"] == job_id or higher["gpu"] != gpu or higher["priority"] >= priority:
            continue
        if higher["state"] in ("끝", "실패"):
            continue
        if higher["state"] == "대기" and higher.get("executable", True):
            return False, f"higher_waiting:{higher['id']}"
        if higher["state"] == "실행":
            if higher["priority"] == 1 and not live["marker"]["present"] and live["chain"]["waiting"]:
                continue  # P1 waits for a checkpoint; lower work may fill the gap.
            return False, f"higher_active:{higher['id']}"
    if gpu == 1:
        if live["marker"]["present"] or not live["chain"]["waiting"]:
            return False, "p1_marker_or_chain_busy"
        render = live["render"]
        if priority < 4 and render.get("state") == "running":
            return False, "finish_current_render_item_then_yield"
    return True, "eligible_next_unit"


def status(config: dict, live: dict) -> str:
    jobs = validate(config)
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines = [f"GPU 작업 관리판 · {stamp}", "우선순위 P0 학습 > P1 판정 평가 > P2 진단 > P3 시드 반복 > P4 렌더"]
    for gpu in (0, 1):
        lines.append(f"GPU{gpu}")
        ordered = sorted((j for j in jobs if j["gpu"] == gpu), key=lambda j: (j["priority"], j["id"]))
        for job in ordered:
            pid = pid_state(job)
            label = f"P{job['priority']} {job['id']} · {job['state']}"
            if job.get("pid"):
                label += f" · PID {job['pid']} {pid}"
            if job["priority"] == 1:
                label += f" · marker={live['marker']['reason']} · chain_wait={live['chain']['waiting']}"
            if job["priority"] == 4:
                render = live["render"]
                label += f" · queue={render.get('state')} · current={render.get('current_job')}"
            if job["state"] == "대기":
                allowed, reason = admission(config, job["id"], live)
                label += f" · next={'GO' if allowed else 'WAIT'}:{reason}"
            lines.append("  " + label)
    lines.append("표는 관찰·다음 단위 진입 판단이다. 기존 프로세스를 선점하거나 새 작업을 기동하지 않는다.")
    return "\n".join(lines)


# Live view (11/03 lead): built from the machine, not from the hand-kept list.
LIVE = {
    "markers": ["D:/mai-tmp/gpu", "C:/Users/AI-WS01/s2_lab/c_layer_m6000/priority"],
    "ledgers": ["D:/mai-tmp/c_layer_m6000_gpu1_remainder_v34/gpu1_remainder_loop.jsonl"],
    # Training is found from the marker train_start writes (pid · run dir), not a fixed path.
    "train_marker": "D:/mai-tmp/gpu/TRAINING_BUSY_GPU0",
    "boundary": 250,
    "idle_state": "D:/mai-tmp/gpu/idle_since.json",
    "idle_util": 10,
    # board (팀장 11/03 22:1x)
    "queue": "D:/mai-tmp/gpu/queue.json",
    "stage_table": "D:/mai-wt/foothold-lab/ex41-launch-2ee5dc00/foothold_s2/curriculum/ex41-fixed5000.yaml",
    "parent_iter": 6000,
    "stage_end": [750, 1750, 2750, 4000, 4500, 5000],
    "eval_root": "C:/Users/AI-WS01/s2_lab/ex41_main_20261103_195435/eval/score-watch",
    "eval_minutes_assumed": 40,
    "stage_end_minutes_assumed": 120,
    "c_layer_total_cells": 81,
    "c_layer_manifest": "D:/mai-tmp/c_layer_m6000_gpu1_remainder_v34/cap2/remaining.json",
}
KINDS = (("guard", ("score_watch", "mirror_guard", "auto_guard", "inbox_wait")),
         ("training", ("train_start.py", "train.py")),
         ("render", ("c_layer", "c76_vis", "vis_loop", "remainder", "render", "play.py")),
         ("eval", ("eval", "terrain_skill", "axis_v2", "push_ladder", "map_modes", "probe")))


def classify(cmdline: str) -> str | None:
    low = cmdline.replace("\\", "/").casefold()
    for kind, words in KINDS:
        if any(w in low for w in words):
            return kind
    return None


def nvidia_smi() -> dict:
    """GPU index -> util/MiB and pid -> GPU set. Empty on failure (grants nothing)."""
    import subprocess

    def q(args):
        return subprocess.run(["nvidia-smi", *args, "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=20).stdout
    try:
        gpus, uuid = {}, {}
        for line in q(["--query-gpu=index,uuid,utilization.gpu,memory.used,memory.total,name"]).splitlines():
            i, u, util, mem, total, name = [x.strip() for x in line.split(",", 5)]
            gpus[int(i)] = {"util": int(util), "mib": int(mem), "total_mib": int(total),
                            "name": name.replace("NVIDIA GeForce ", "")}
            uuid[u] = int(i)
        apps = {}
        for line in q(["--query-compute-apps=pid,gpu_uuid"]).splitlines():
            pid, u = [x.strip() for x in line.split(",")[:2]]
            if u in uuid:
                apps.setdefault(int(pid), set()).add(uuid[u])
        return {"gpus": gpus, "apps": apps}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"gpus": {}, "apps": {}}


def processes() -> list[dict]:
    if psutil is None:
        return []
    out = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            if not (p.info["name"] or "").casefold().startswith("python"):
                continue
            out.append({"pid": p.info["pid"], "cmdline": " ".join(p.cmdline() or []),
                        "started": p.create_time()})
        except (psutil.Error, OSError):
            continue
    return out


def device_hint(cmdline: str) -> int | None:
    m = re.search(r"cuda:(\d)", cmdline)
    return int(m.group(1)) if m else None


def live_jobs(smi: dict, procs: list[dict]) -> list[dict]:
    jobs = []
    for p in procs:
        kind = classify(p["cmdline"])
        if kind is None:
            continue
        tokens = p["cmdline"].replace("\\", "/").split()
        module = tokens[tokens.index("-m") + 1] if "-m" in tokens[:-1] else None
        script = next((t for t in tokens if t.endswith(".py")), module or "?")
        jobs.append({"pid": p["pid"], "kind": kind, "gpus": sorted(smi["apps"].get(p["pid"], ())),
                     "device": device_hint(p["cmdline"]), "script": script.rsplit("/", 1)[-1],
                     "started": p["started"]})
    return jobs


def on_gpu(job: dict, gpu: int) -> bool:
    # A Kit process also holds a graphics context on the display GPU; trust cuda:N first.
    return job["kind"] != "guard" and (job["device"] == gpu or (job["device"] is None and gpu in job["gpus"]))


def marker_files(dirs: list[str], now: float) -> list[str]:
    lines = []
    for d in map(Path, dirs):
        for f in sorted(d.glob("*")) if d.is_dir() else []:
            if f.is_file() and re.fullmatch(r"[A-Z0-9_]+", f.stem):
                lines.append(f"{f} · {int((now - f.stat().st_mtime) // 60)} 분 전")
    return lines


def ledger_tail(path: str) -> str:
    name = Path(path).parent.name
    try:
        last = next((l for l in reversed(read_shared_text(path, "utf-8", "replace").splitlines())
                     if l.strip()), "")
        row = json.loads(last)
        ev = row.get("queue_event", {})
        stamp = datetime.fromtimestamp(row["at"]).strftime("%H:%M") if isinstance(row.get("at"), (int, float)) else "?"
        return f"{name}: {stamp} {row.get('cell')} {ev.get('state')} 시도 {ev.get('attempts')}"
    except (OSError, ValueError):
        return f"{name}: 읽지 못함"


def training_progress(path: str, boundary: int, now: float) -> str | None:
    try:
        d = read_json(Path(path))
    except (OSError, ValueError):
        return None
    it, s = d.get("iter"), d.get("iter_s")
    if type(it) is not int or not isinstance(s, (int, float)):
        return f"학습 {d.get('state')} · 회차 미확인"
    nxt = (it // boundary + 1) * boundary
    eta = datetime.fromtimestamp(now + (nxt - it) * s).strftime("%H:%M")
    return f"학습 {d.get('state')} · {it}/{d.get('tot_iter')} 회 · 회당 {s:.1f} 초 · 다음 {boundary} 경계 {nxt} 회 약 {eta} (추정)"


def idle_update(smi: dict, jobs: list[dict], state_path: str, util_floor: int, now: float) -> dict:
    """GPU -> idle-since epoch, None when busy (a non-guard job on it, or util >= floor)."""
    try:
        state = json.loads(Path(state_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    out = {}
    for i, g in smi["gpus"].items():
        busy = g["util"] >= util_floor or any(on_gpu(j, i) for j in jobs)
        out[str(i)] = None if busy else (state.get(str(i)) or now)
    try:
        Path(state_path).write_text(json.dumps(out), encoding="utf-8")
    except OSError:
        pass  # Only the since-when is lost; the current state is still printed.
    return out


def live_status(smi=None, procs=None, cfg=LIVE, now=None) -> str:
    now = now if now is not None else datetime.now().timestamp()
    smi = smi if smi is not None else nvidia_smi()
    procs = procs if procs is not None else processes()
    jobs = live_jobs(smi, procs)
    idle = idle_update(smi, jobs, cfg["idle_state"], cfg["idle_util"], now)
    lines = ["실측 · nvidia-smi · 프로세스 명령줄 · 표식 · 대기열 (등록부 아님)"]
    if not smi["gpus"]:
        lines.append("nvidia-smi 읽기 실패 · GPU 상태 미확인")
    for i, g in sorted(smi["gpus"].items()):
        since = idle.get(str(i))
        state = f"쉼 · {datetime.fromtimestamp(since).strftime('%m-%d %H:%M')} 부터 관측" if since else "사용 중"
        lines.append(f"GPU{i} · 사용률 {g['util']} % · {g['mib']} MiB · {state}")
        for j in sorted((j for j in jobs if on_gpu(j, i)), key=lambda j: j["kind"]):
            lines.append(f"  {j['kind']} · PID {j['pid']} · {j['script']} · "
                         f"{datetime.fromtimestamp(j['started']).strftime('%m-%d %H:%M')} 시작")
    guards = [j for j in jobs if j["kind"] == "guard"]
    lines.append("감시 (GPU 안 씀) " + (" · ".join(f"PID {j['pid']} {j['script']}" for j in guards) or "없음"))
    prog = training_progress(train_status_path(cfg), cfg["boundary"], now)
    lines.append(prog or "학습 상태 파일 없음")
    lines += ["대기열 " + ledger_tail(p) for p in cfg["ledgers"]]
    lines += ["표식 " + m for m in marker_files(cfg["markers"], now)] or ["표식 없음"]
    return "\n".join(lines)


# ---- board: one screen of now + planned GPU work (팀장 11/03 22:1x) ----
QUEUE_FORMAT = "foothold-gpu-queue/1"
QSTATES = ("대기", "실행", "끝", "취소")


def hm(ts: float | None) -> str:
    return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M") if ts else "?"


def read_queue(path: str) -> dict:
    try:
        q = json.loads(read_shared_text(path))
    except FileNotFoundError:
        return {"format": QUEUE_FORMAT, "items": []}
    if not isinstance(q, dict) or q.get("format") != QUEUE_FORMAT or not isinstance(q.get("items"), list):
        raise ValueError(f"queue format differs: {path}")
    return q


def write_queue(path: str, q: dict) -> None:
    tmp = Path(path).with_suffix(".tmp")
    tmp.write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def parse_when(text: str | None, now: float) -> float | None:
    """'HH:MM' (today) or 'MM-DD HH:MM'. None/'' -> None. Never shifts a day silently."""
    if not text:
        return None
    base = datetime.fromtimestamp(now)
    for fmt, value in (("%Y-%m-%d %H:%M", f"{base.year}-{text}"),
                       ("%Y-%m-%d %H:%M", f"{base:%Y-%m-%d} {text}")):
        try:
            return datetime.strptime(value, fmt).timestamp()
        except ValueError:
            continue
    raise ValueError(f"time must be HH:MM or MM-DD HH:MM: {text}")


def queue_cmd(args, cfg=LIVE, now=None) -> str:
    now = now if now is not None else datetime.now().timestamp()
    q = read_queue(cfg["queue"])
    items = q["items"]
    if args.qaction == "add":
        if not 0 <= args.priority <= 4 or args.gpu not in (0, 1):
            raise ValueError("priority 0..4, gpu 0|1")
        new_id = max((i["id"] for i in items), default=0) + 1
        items.append({"id": new_id, "title": args.title, "priority": args.priority, "gpu": args.gpu,
                      "start": parse_when(args.start, now), "end": parse_when(args.end, now),
                      "owner": args.owner, "condition": args.cond or "", "state": "대기", "added_at": now,
                      "needs_approval": bool(getattr(args, "needs_approval", False))})
        extra = {"kind": getattr(args, "kind", None), "cwd": getattr(args, "cwd", None),
                 "wait_absent": getattr(args, "wait_absent", None) or [],
                 "wait_pids": getattr(args, "wait_pid", None) or [],
                 "done_files": getattr(args, "done_file", None) or []}
        if getattr(args, "argv_json", None):
            argv = json.loads(args.argv_json)
            if not (isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv)):
                raise ValueError("--argv-json must be a non-empty JSON list of strings")
            if extra["kind"] not in ALLOWED_KINDS:
                raise ValueError("a command needs --kind eval|probe|render (training is never dispatched)")
            extra["argv"] = argv
        items[-1].update({k: v for k, v in extra.items() if v not in (None, [])})
        msg = f"added {new_id}"
    else:
        item = next((i for i in items if i["id"] == args.id), None)
        if item is None:
            raise ValueError(f"no queue item {args.id}")
        if args.qaction == "done":
            item["state"], item["done_at"] = "끝", now
        elif args.qaction == "cancel":
            if item.get("state") == "실행":
                raise ValueError(f"item {args.id} is running; cancel only waiting items")
            item["state"], item["cancelled_at"], item["cancel_reason"] = "취소", now, args.reason
        elif args.qaction == "run":
            item["state"], item["run_at"] = "실행", now
        else:  # move
            for key in ("priority", "gpu"):
                if getattr(args, key) is not None:
                    item[key] = getattr(args, key)
            for key in ("start", "end"):
                if getattr(args, key) is not None:
                    item[key] = parse_when(getattr(args, key), now)
        msg = f"{args.qaction} {args.id}"
    write_queue(cfg["queue"], q)
    return msg


def stage_rows(cfg: dict) -> list[tuple[str, int, int]]:
    """[(id, first local update, last local update)] from the EX-41 table."""
    try:
        import yaml
        stages = yaml.safe_load(Path(cfg["stage_table"]).read_text(encoding="utf-8"))["stages"]
        starts = [(s["id"], int(s["start"]["fixed_update"])) for s in stages]
    except Exception:  # unreadable table: no stage names, never invented ones
        return []
    ends = [s for _, s in starts[1:]]
    last = cfg["stage_end"][-1]
    return [(sid, max(st, 1), (ends[k] - 1 if k < len(ends) else last)) for k, (sid, st) in enumerate(starts)]


def stage_of(it: int, rows) -> tuple[str, int, int] | None:
    return next((r for r in rows if r[1] <= max(it, 1) <= r[2]), None)


def eval_attempts(root: str) -> list[dict]:
    """Per 250-boundary score attempt: iteration, start, end (if finished), state."""
    out = []
    for d in sorted(Path(root).glob("model_*_*")) if Path(root).is_dir() else []:
        try:
            a = json.loads(read_shared_text(d / "attempt.json"))
        except (OSError, ValueError):
            continue
        # attempt.json is rewritten when the attempt ends, so the start is the folder's birth
        # (st_birthtime on Windows / 3.12+, else the oldest file in it).
        st = d.stat()
        start = getattr(st, "st_birthtime", None) or min(
            (f.stat().st_mtime for f in d.rglob("*") if f.is_file()), default=st.st_mtime)
        latest = max((f.stat().st_mtime for f in d.rglob("*") if f.is_file()), default=start)
        done = a.get("state") not in ("running", None)
        out.append({"iteration": a.get("iteration"), "start": start, "end": latest if done else None,
                    "state": a.get("state")})
    return out


def c_layer_rows(path: str) -> list[dict]:
    try:
        return [json.loads(l) for l in read_shared_text(path).splitlines() if l.strip()]
    except (OSError, ValueError):
        return []


def c_layer_cell_seconds(rows: list[dict], last_n: int = 10) -> float | None:
    """Mean run time per closed C층 cell over the last `last_n` closed cells.

    One ledger row is one attempt: it runs from its `before.time` snapshot to `at`, so hold
    gaps (ex41_slowdown_hold until resume, P1 marker waits) between rows are never counted.
    A cell's time is the sum of all its attempts (an exhausted cell counts every try).
    Rows that are only status checks (only_cell_closed) are not attempts.
    """
    per_cell, order = {}, []
    for r in rows:
        ev = r.get("queue_event", {})
        if ev.get("state") not in ("pending", "complete", "exhausted"):
            continue
        try:
            start = datetime.fromisoformat(r["before"]["time"]).timestamp()
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 < r["at"] - start < 6 * 3600:
            continue
        per_cell[r["cell"]] = per_cell.get(r["cell"], 0.0) + (r["at"] - start)
        if ev["state"] in ("complete", "exhausted") and r["cell"] not in order:
            order.append(r["cell"])
    recent = order[-last_n:]
    return sum(per_cell[c] for c in recent) / len(recent) if recent else None


SAVE_EVERY = 50  # checkpoint + manifest rewrite interval (updates)


def watcher_pending(root: str) -> int | None:
    """Iteration score_watch is holding with `pending manifest_not_committed`, from its last log line."""
    try:
        tail = read_shared_bytes(Path(root) / "watcher.stdout.log")[-4096:].decode(
            "utf-8", errors="replace").splitlines()
        row = json.loads(next(l for l in reversed(tail) if l.strip().startswith("{")))
    except (OSError, ValueError, StopIteration):
        return None
    if row.get("state") == "pending" and row.get("reason") == "manifest_not_committed":
        return row.get("iteration")
    return None


def c_layer_files(cfg: dict) -> tuple[list[dict], list[str]]:
    """Ledger rows and manifest cell order (read in the 10 s slow pass, never per frame)."""
    rows = [r for p in cfg["ledgers"] for r in c_layer_rows(p)]
    try:
        order = json.loads(read_shared_text(cfg["c_layer_manifest"]))["remaining_cells"]
    except (OSError, ValueError, KeyError, TypeError):
        order = []
    return rows, order


def auto_items(cfg: dict, train: dict | None, now: float, jobs: list[dict], attempts=None,
               pending=None, c_files=None) -> list[dict]:
    """Planned work computed from live files. Each item says where its ETA came from."""
    items = []
    attempts = eval_attempts(cfg["eval_root"]) if attempts is None else attempts
    finished = [a for a in attempts if a["end"]]
    eval_min = (sum(a["end"] - a["start"] for a in finished) / len(finished) / 60) if finished else None
    eval_src = f"지난 {len(finished)} 회 실측 평균" if finished else f"가정 {cfg['eval_minutes_assumed']} 분"
    eval_min = eval_min or cfg["eval_minutes_assumed"]
    for a in attempts:
        if a["state"] == "running":
            items.append({"title": f"EX-41 {a['iteration']} 경계 평가 39 칸 + W78", "priority": 1, "gpu": 1,
                          "start": a["start"], "end": a["start"] + eval_min * 60, "state": "실행",
                          "owner": "score_watch", "source": eval_src, "kind": "eval"})
    if train and type(train.get("iter")) is int and isinstance(train.get("iter_s"), (int, float)):
        it, s, b = train["iter"], train["iter_s"], cfg["boundary"]
        done_iters = {a["iteration"] for a in attempts}
        # score_watch starts model_N only when the manifest shows >= N+1 updates, and the manifest
        # is rewritten at checkpoint saves, so the N evaluation starts at the N+50 save.
        for k in range(0, 5):
            nxt = (it // b + k) * b
            if nxt < b or nxt > cfg["stage_end"][-1] or nxt in done_iters:
                continue
            start = now + max(0, nxt + SAVE_EVERY - it) * s
            stage_end = nxt in cfg["stage_end"]
            dur = cfg["stage_end_minutes_assumed"] if stage_end else eval_min
            state = (f"대기 · 다음 저장 {datetime.fromtimestamp(start):%H:%M}" if pending == nxt else "대기")
            items.append({"title": (f"EX-41 {nxt} 단계 끝 사슬(축 전부 + 밀기)" if stage_end
                                    else f"EX-41 {nxt} 경계 평가 39 칸 + W78"),
                          "priority": 1, "gpu": 1, "start": start, "end": start + dur * 60, "state": state,
                          "owner": "score_watch", "kind": "eval",
                          "source": (f"시작 {nxt + SAVE_EVERY} 회 · manifest 는 다음 저장({nxt + SAVE_EVERY}) 때 갱신"
                                     f" · 회당 {s:.1f} 초 · " + (f"가정 {dur} 분" if stage_end else eval_src)),
                          "condition": f"model_{nxt}.pt"})
    rows, order = c_files if c_files is not None else c_layer_files(cfg)
    if rows:
        closed = {r["cell"] for r in rows if r.get("queue_event", {}).get("state") in ("complete", "exhausted")}
        left = cfg["c_layer_total_cells"] - len(closed)
        per = c_layer_cell_seconds(rows)
        last = rows[-1]
        held = "hold" in str(last.get("state"))
        render_live = any(j["kind"] == "render" and on_gpu(j, 1) for j in jobs)
        current = last["cell"] if render_live else None
        nxt_cell = next((c for c in order if c not in closed and c != (current or last["cell"])), None)
        items.append({"title": f"C층 남은 {left}/{cfg['c_layer_total_cells']} 칸", "priority": 4, "gpu": 1,
                      "group": "c_layer", "left": left, "total": cfg["c_layer_total_cells"],
                      "current_cell": current, "next_cell": nxt_cell, "per_cell_s": per,
                      "start": None, "end": (now + left * per) if per and render_live else None,
                      "state": "실행" if render_live else ("보류" if held else "대기"),
                      "owner": "scripter", "kind": "render",
                      "source": (f"칸당 {per / 60:.0f} 분 실측(실행 시간만 · 최근 10 칸)" if per else "칸당 시간 미확인")
                                + (f" · 마지막 {last.get('state')} {hm(last['at'])}" if held else ""),
                      "condition": "학습 회당 10 회 평균 ≤ 29.7 초 · P1 평가 없을 때"})
    return items


C_LAYER_OWNERS = ("c_layer_gpu1_remainder", "c_layer_queue", "record_c_layer")
BETWEEN_CELLS_S = 300


def needs_approval(item: dict) -> bool:
    """Not startable on its own only when flagged. Words in the free-text condition never gate
    (11/04: 「대기」 in a scripter condition left GPU1 idle at 13:11)."""
    return bool(item.get("needs_approval"))


def c_layer_owners(jobs: list[dict]) -> list[dict]:
    return [j for j in jobs if any(o in j["script"] for o in C_LAYER_OWNERS)]


def launcher(e: dict) -> str:
    if needs_approval(e) and not e.get("auto"):
        return "승인 뒤"
    if not e.get("auto") and e.get("argv"):
        return "dispatcher" + (f" {e['pid']}" if e.get("pid") and e.get("state") == "실행" else "")
    if e.get("auto"):
        return {"score_watch": "score_watch 자동", "scripter": "scripter 대기열"}.get(e.get("owner"), "자동")
    return f"손 · {e['owner']}" if e.get("owner") else "손"


def warnings(cfg: dict, queue: list[dict], auto: list[dict], jobs: list[dict], idle: dict,
             train: dict | None, now: float, attempts=None) -> list[str]:
    out = []
    for it in queue:
        if it["state"] == "실행" and not (pid_alive(it["pid"]) if it.get("pid")
                                         else any(on_gpu(j, it["gpu"]) for j in jobs)):
            out.append(f"대기열 {it['id']} 「{it['title']}」 는 실행인데 GPU{it['gpu']} 에 프로세스 없음")
    for gpu, since in idle.items():
        if not since:
            continue
        owners = c_layer_owners(jobs) if int(gpu) == 1 else []
        if owners:
            # Owner alive at 0 %: Kit starting or between cells. Only a long gap is a problem.
            if now - since >= BETWEEN_CELLS_S:
                out.append(f"GPU{gpu} 가 {hm(since)} 부터 0 % 인데 C층 주인 프로세스는 살아 있음 "
                           f"({' · '.join(j['script'] for j in owners)}) · 5 분 넘음")
            continue
        # Auto items have their own launcher (score_watch, scripter loop); only hand-queued work and
        # a C층 queue with no owner process left are "could start now".
        ready = [it for it in queue if it["state"] == "대기" and it["gpu"] == int(gpu)
                 and (it.get("start") is None or it["start"] <= now) and not needs_approval(it)]
        ready += [it for it in auto if it.get("kind") == "render" and it["state"] == "대기" and it["gpu"] == int(gpu)]
        if ready:
            out.append(f"GPU{gpu} 가 {hm(since)} 부터 비었는데 시작 가능한 일 있음: "
                       + " · ".join(it["title"] for it in ready))
    if train and type(train.get("iter")) is int:
        b = cfg["boundary"]
        due = (train["iter"] // b) * b
        seen = eval_attempts(cfg["eval_root"]) if attempts is None else attempts
        if due >= b and train["iter"] >= due + SAVE_EVERY + 5 and due not in {a["iteration"] for a in seen}:
            out.append(f"EX-41 {due} 경계를 지났는데 평가 기록 없음")
    return out


# ---- rendering: fixed columns measured in terminal cells (팀장 22:4x) ----
import unicodedata

ANSI = {"실행": "32", "대기": "33", "보류": "90", "경고": "31", "dim": "90", "bold": "1"}
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def cell_width(text: str) -> int:
    """Terminal cells: East Asian Wide/Fullwidth = 2, combining = 0, ANSI codes = 0."""
    w = 0
    for ch in ANSI_RE.sub("", text):
        if unicodedata.combining(ch):
            continue
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def fit(text: str, width: int, align: str = "<") -> str:
    """Pad or cut (with …) to exactly `width` cells. Plain text only (color goes on after)."""
    if cell_width(text) > width:
        out, w = "", 0
        for ch in text:
            cw = cell_width(ch)
            if w + cw > width - 1:
                break
            out, w = out + ch, w + cw
        text = out + "…"
    pad = " " * (width - cell_width(text))
    return pad + text if align == ">" else text + pad


class Paint:
    def __init__(self, on: bool):
        self.on = on

    def __call__(self, text: str, key: str) -> str:
        return f"\x1b[{ANSI[key]}m{text}\x1b[0m" if self.on and key in ANSI else text


ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004


def enable_vt(kernel32=None, isatty=None) -> bool:
    """True when the console will obey ESC sequences (cmd.exe, PowerShell window, Windows Terminal).

    On Windows the console mode is set with SetConsoleMode, then read back. No console (pipe,
    file) -> False. `kernel32` / `isatty` are injectable for CPU tests.
    """
    import os
    import sys
    if not (isatty if isatty is not None else sys.stdout.isatty)():
        return False
    if os.name != "nt" and kernel32 is None:
        return True
    try:
        import ctypes
        k = kernel32 or ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        if not mode.value & ENABLE_VIRTUAL_TERMINAL_PROCESSING:
            k.SetConsoleMode(h, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
            if not k.GetConsoleMode(h, ctypes.byref(mode)):
                return False
        return bool(mode.value & ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except (AttributeError, OSError):
        return False


SCREEN_ENTER = "\x1b[?1049h\x1b[?25l"   # alternate screen, hide cursor
SCREEN_LEAVE = "\x1b[?25h\x1b[?1049l"   # show cursor, back to the original screen


def frame(text: str) -> str:
    """Overwrite in place: home, each line then erase-to-end-of-line, then erase below."""
    return "\x1b[H" + "".join(line + "\x1b[K\n" for line in text.split("\n")) + "\x1b[J"


def bar(frac: float, width: int) -> str:
    frac = min(max(frac, 0.0), 1.0)
    full = round(frac * width)
    return "█" * full + "░" * (width - full)


def clock(ts: float | None, now: float) -> str:
    """HH:MM; +N when the day differs from now."""
    if not ts:
        return "-"
    t, n = datetime.fromtimestamp(ts), datetime.fromtimestamp(now)
    days = (t.date() - n.date()).days
    return t.strftime("%H:%M") + (f"+{days}" if days > 0 else (f"{days}" if days < 0 else ""))


def when(ts: float | None, now: float) -> str:
    """For the GPU boxes: HH:MM today, else MM-DD HH:MM."""
    if not ts:
        return "-"
    t = datetime.fromtimestamp(ts)
    return t.strftime("%H:%M") if t.date() == datetime.fromtimestamp(now).date() else t.strftime("%m-%d %H:%M")


def box(title: str, body: list[str], width: int) -> list[str]:
    inner = width - 4
    head = f"┌─ {fit(title, width - 6).rstrip()} "
    lines = [head + "─" * (width - cell_width(head) - 1) + "┐"]
    for line in body:
        if cell_width(line) > inner:
            line = fit(ANSI_RE.sub("", line), inner)
        lines.append("│ " + line + " " * (inner - cell_width(line)) + " │")
    lines.append("└" + "─" * (width - 2) + "┘")
    return lines


def current_training(cfg=LIVE, alive=None) -> dict | None:
    """None: no training (marker absent) -> GPU1 is free for prep work.
    {"state": "dead", ...}: marker left by a training process that is gone (crash) -> hold GPU1
    so a relaunch gets GPU0 (01:29~01:38). Otherwise the run's train_start_status.json."""
    alive = alive or pid_alive
    try:
        marker = read_json(Path(cfg["train_marker"]))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {"state": "unknown_marker"}
    if not alive(marker.get("pid")):
        return {"state": "dead", "pid": marker.get("pid"), "run": marker.get("run")}
    try:
        status = read_json(Path(marker["run"]) / "train_start_status.json")
    except (OSError, ValueError, KeyError, TypeError):
        return {"state": "starting", "pid": marker.get("pid"), "run": marker.get("run")}
    status.setdefault("run", marker.get("run"))
    return status


def train_status_path(cfg=LIVE) -> str:
    t = current_training(cfg)
    return str(Path(t["run"]) / "train_start_status.json") if t and t.get("run") else ""


def slow_data(cfg=LIVE, procs=None) -> dict:
    """The parts read every 10 s in watch mode: process command lines and files."""
    procs = procs if procs is not None else processes()
    train = current_training(cfg)
    try:
        queue, qerr = read_queue(cfg["queue"])["items"], None
    except ValueError as exc:
        queue, qerr = [], str(exc)
    return {"procs": procs, "train": train, "queue": queue, "qerr": qerr,
            "attempts": eval_attempts(cfg["eval_root"]), "rows": stage_rows(cfg),
            "pending": watcher_pending(cfg["eval_root"]),
            "c_files": c_layer_files(cfg),
            "read_at": datetime.now().timestamp()}


def in_c_layer_group(e: dict) -> bool:
    # 11/04 17:4x: 198 two-seed units (title 「C76 2seed …」) were listed one row each on the board.
    argv = " ".join(e.get("argv") or [])
    return (e.get("group") == "c_layer" or str(e.get("title", "")).startswith(("C층 다음 칸", "C76 2seed"))
            or "c_layer_gpu1_remainder" in argv or "c_layer_queue" in argv)


def unit_cell(e: dict) -> str | None:
    argv = e.get("argv") or []
    return argv[argv.index("--cell") + 1] if "--cell" in argv[:-1] else None


CELL_WORDS = (("stepping_stones_low", "디딤돌"), ("stepping_stones", "디딤돌"), ("pyramid_stairs_inv", "내림계단"),
              ("pyramid_stairs", "계단"), ("eval_gt", "정답"), ("eval_pred", "복원"), ("probe_prop_only", "끔"))


def short_cell(cell: str | None) -> str:
    """stepping_stones_low_L4_probe_prop_only -> 디딤돌 L4 끔 (map modes: 정답 · 복원 · 끔)."""
    if not cell:
        return "-"
    for a, b in CELL_WORDS:
        cell = cell.replace(a, b)
    return cell.replace("_", " ")


def fold_groups(entries: list[dict]) -> list[dict]:
    """All C층 rows (dispatcher units + the auto summary) become one table row."""
    group = [e for e in entries if in_c_layer_group(e)]
    if len(group) <= 1 and not any(not e.get("auto") for e in group):
        rest = [e for e in entries if not in_c_layer_group(e)]
        return rest + [_c_row(group, None)] if group else entries
    rest = [e for e in entries if not in_c_layer_group(e)]
    return rest + [_c_row(group, None)]


def _c_row(group: list[dict], _unused) -> dict:
    summary = next((e for e in group if e.get("auto")), {})
    units = [e for e in group if not e.get("auto")]
    running = [e for e in units if e["state"] == "실행"]
    per = summary.get("per_cell_s")
    left, total = summary.get("left"), summary.get("total")
    cur = summary.get("current_cell") or (summary.get("last_cell") if running else None)
    title = (f"C층 남은 칸 {left if left is not None else '?'}/{total if total is not None else '?'}"
             f" · 지금 {short_cell(cur)} · 다음 {short_cell(summary.get('next_cell'))}"
             f" · 칸당 {per / 60:.0f} 분" if per else
             f"C층 남은 칸 {left}/{total} · 지금 {short_cell(cur)} · 다음 {short_cell(summary.get('next_cell'))}"
             " · 칸당 미확인")
    if units and any(unit_cell(e) for e in units):
        # queue units carry their own cell: count them, not the old fixed manifest summary
        waiting = [e for e in units if e["state"] == "대기"]
        nxt = next((unit_cell(e) for e in waiting if unit_cell(e)), None)
        title = (f"C층 칸 촬영 · 남은 {len(units)} 칸(대기 {len(waiting)}) · 지금 "
                 f"{short_cell(unit_cell(running[0])) if running else '-'} · 다음 {short_cell(nxt)}")
    state = "실행" if running or summary.get("state") == "실행" else summary.get("state", "대기")
    row = dict(summary or units[0], title=title, state=state, auto=bool(summary) and not units,
               group="c_layer")
    if units:
        row.update(argv=units[0].get("argv"), owner="lead", pid=(running[0].get("pid") if running else None),
                   condition=units[0].get("condition"),
                   source=(summary.get("source", "") + f" · 대기열 단위 {len(units)} 건(dispatcher)").lstrip(" ·"))
    return row


def board_data(smi=None, procs=None, cfg=LIVE, now=None, slow=None) -> dict:
    now = now if now is not None else datetime.now().timestamp()
    smi = smi if smi is not None else nvidia_smi()
    slow = slow if slow is not None else slow_data(cfg, procs)
    procs, train, queue, qerr = slow["procs"], slow["train"], slow["queue"], slow["qerr"]
    jobs = live_jobs(smi, procs)
    idle = idle_update(smi, jobs, cfg["idle_state"], cfg["idle_util"], now)
    auto = auto_items(cfg, train, now, jobs, slow["attempts"], slow.get("pending"), slow.get("c_files"))
    entries = ([dict(it, auto=False) for it in queue if it["state"] not in ("끝", "실패", "취소")]
               + [dict(it, auto=True) for it in auto])
    entries = fold_groups(entries)
    # running first, then what the dispatcher will start next (by priority), then timed items
    entries.sort(key=lambda e: (e["state"] != "실행", not (e.get("argv") and not needs_approval(e)),
                                e.get("start") or float("inf"), e["priority"]))
    warn = (warnings(cfg, queue, auto, jobs, idle, train, now, slow["attempts"])
            + ([f"대기열 파일 오류: {qerr}"] if qerr else []))
    return {"now": now, "smi": smi, "jobs": jobs, "idle": idle, "train": train, "rows": slow["rows"],
            "entries": entries, "warnings": warn, "cfg": cfg}


def gpu_box(d: dict, i: int, width: int, paint: Paint) -> list[str]:
    g, now, cfg, train = d["smi"]["gpus"][i], d["now"], d["cfg"], d["train"]
    here = sorted((j for j in d["jobs"] if on_gpu(j, i)), key=lambda j: j["kind"])
    running = [e for e in d["entries"] if e["state"] == "실행" and e["gpu"] == i]
    inner = width - 4
    body = []
    owners = c_layer_owners(d["jobs"]) if i == 1 else []
    if not here and owners:
        since = d["idle"].get(str(i))
        body.append(paint("C층 렌더", "실행") + " · Kit 시작 중 · 칸 사이"
                    + (f" ({int((now - since) // 60)} 분)" if since else ""))
    elif not here:
        since = d["idle"].get(str(i))
        body.append(paint(f"쉼 · {clock(since, now)} 부터 관측", "보류") if since else "프로세스 없음")
    for j in here:
        if j["kind"] == "training" and train and type(train.get("iter")) is int:
            it, p, last = train["iter"], cfg["parent_iter"], cfg["stage_end"][-1]
            st = stage_of(it, d["rows"])
            stage = f"{st[0]} (m{p + st[1]}~m{p + st[2]})" if st else "단계 미확인"
            body.append(paint("EX-41 학습", "실행") + " · " + fit(stage, inner - 13).rstrip())
            tail = f" m{p + it} · {it}/{last}"
            body.append(f"[{bar(it / last, inner - 2 - cell_width(tail))}]{tail}")
            s = train.get("iter_s")
            if isinstance(s, (int, float)):
                nxt = (it // cfg["boundary"] + 1) * cfg["boundary"]
                body.append(f"다음 경계 {nxt} · {when(now + (nxt - it) * s, now)} · 회당 {s:.1f} 초")
                body.append(f"시작 {when(j['started'], now)} · 예상 끝 {when(now + (last - it) * s, now)} (로컬 {last})")
        else:
            label = {"render": "C층 렌더", "eval": "평가", "training": "학습"}[j["kind"]]
            body.append(paint(label, "실행") + " · " + fit(f"{j['script']} · PID {j['pid']}",
                                                          inner - cell_width(label) - 3).rstrip())
            e = next((e for e in running if e.get("kind") == j["kind"]), None)
            body.append(f"시작 {when((e or {}).get('start') or j['started'], now)} · "
                        f"예상 끝 {when(e['end'] if e else None, now)}")
    total = g.get("total_mib")
    mem = f"{g['mib'] / 1024:.1f}/{total / 1024:.0f} GB" if total else f"{g['mib'] / 1024:.1f} GB"
    tail = f" {g['util']:>3} % · {mem}"
    body.append(f"[{bar(g['util'] / 100, inner - 2 - cell_width(tail))}]{tail}")
    return box(f"GPU{i} · {g['name']}" if g.get("name") else f"GPU{i}", body, width)


COLS = (("#", 3, ">"), ("상태", 6, "<"), ("GPU", 4, "<"), ("우선", 4, "<"), ("시작", 8, "<"), ("끝", 8, "<"),
        ("띄움", 16, "<"))


TABLE_NEXT = 8


def render_board(d: dict, width: int = 120, paint: Paint | None = None, height: int | None = None,
                 detail: bool = False) -> str:
    """Head (title + GPU boxes + table head) always fits; lower sections shrink to `height`."""
    paint = paint or Paint(False)
    width = max(80, width)
    now = d["now"]
    head = [paint(fit(f"GPU 관리판 · {datetime.fromtimestamp(now):%m-%d %H:%M} · 실측 + 대기열", width), "bold")]
    gpus = sorted(d["smi"]["gpus"])
    if not gpus:
        head.append(paint(fit("nvidia-smi 읽기 실패 · GPU 상태 미확인", width), "경고"))
    elif width >= 100 and len(gpus) == 2:
        left = (width - 1) // 2
        right = width - 1 - left
        a, b = gpu_box(d, gpus[0], left, paint), gpu_box(d, gpus[1], right, paint)
        h = max(len(a), len(b))
        a = a[:-1] + ["│" + " " * (left - 2) + "│"] * (h - len(a)) + a[-1:]
        b = b[:-1] + ["│" + " " * (right - 2) + "│"] * (h - len(b)) + b[-1:]
        head += [x + " " + y for x, y in zip(a, b)]
    else:
        for i in gpus:
            head += gpu_box(d, i, width, paint)
    entries = d["entries"]
    state_w = max([6] + [cell_width(e["state"]) for e in entries])
    cols = tuple((n, state_w if n == "상태" else w, a) for n, w, a in COLS)
    title_w = width - sum(w for _, w, _ in cols) - len(cols)
    head += ["", paint(" ".join(fit(n, w, a) for n, w, a in cols) + " " + fit("내용", title_w), "bold"),
             "─" * width]

    def row(n, e):
        return " ".join([fit(str(n), 3, ">"), paint(fit(e["state"], state_w), e["state"].split(" ")[0]),
                         fit(f"GPU{e['gpu']}", 4), fit(f"P{e['priority']}", 4), fit(clock(e.get("start"), now), 8),
                         fit(clock(e.get("end"), now), 8), fit(launcher(e), 16), fit(e["title"], title_w)])

    def note(n, e):
        tag = "자동" if e["auto"] else f"대기열 {e.get('id', '-')}"
        return paint(fit(f"{n:>3}  " + " · ".join(x for x in (tag, e.get("owner"), e.get("condition"),
                                                              e.get("source")) if x), width), "dim")
    running = [e for e in entries if e["state"] == "실행"]
    waiting = [e for e in entries if e["state"] != "실행"]
    shown = entries if detail else running + waiting[:TABLE_NEXT]
    hidden = len(entries) - len(shown)
    warn = [paint(fit("경고  " + w, width), "경고") for w in d["warnings"]] or [paint(fit("경고 없음", width), "dim")]
    guards = [j for j in d["jobs"] if j["kind"] == "guard"]
    parked = [j for j in d["jobs"] if j["kind"] != "guard" and not any(on_gpu(j, i) for i in gpus)]
    tail = [paint(fit("감시 " + (" · ".join(f"{j['script']} {j['pid']}" for j in guards) or "없음")
                      + ("   GPU 안 잡은 실행기 " + " · ".join(f"{j['script']} {j['pid']}" for j in parked)
                         if parked else ""), width), "dim")]
    foot = [paint(fit("읽기 전용 · 프로세스를 띄우거나 멈추지 않음 · 끝 시각은 추정"
                      + ("" if detail else " · 전부 보기 --detail"), width), "dim")]

    def build(rows_n, with_notes, warn_n, with_tail):
        table = [row(n, e) for n, e in enumerate(shown[:rows_n], 1)]
        more = len(shown) - rows_n + hidden
        if more > 0:
            table.append(paint(fit(f"    외 {more} 건", width), "dim"))
        if not entries:
            table = [fit("(예정 없음)", width)]
        body = table + [""] + warn[:warn_n]
        if warn_n < len(warn):
            body.append(paint(fit(f"경고 외 {len(warn) - warn_n} 건", width), "경고"))
        if with_notes:
            body += ["", paint(fit("근거", width), "bold")] + [note(n, e) for n, e in enumerate(shown[:rows_n], 1)]
        if with_tail:
            body += [""] + tail
        return head + body + foot

    if detail or height is None:
        return "\n".join(build(len(shown), True, len(warn), True))
    # Shrink from the bottom: notes, then the tail line, then warnings to 1, then table rows.
    plans = [(len(shown), True, len(warn), True), (len(shown), False, len(warn), True),
             (len(shown), False, len(warn), False), (len(shown), False, 1, False)]
    plans += [(n, False, 1, False) for n in range(len(shown) - 1, -1, -1)]
    for plan in plans:
        lines = build(*plan)
        if len(lines) <= height:
            return "\n".join(lines)
    return "\n".join(lines[:max(height, len(head))])


def board(smi=None, procs=None, cfg=LIVE, now=None, width: int = 120, color: bool = False,
          height: int | None = None, detail: bool = False) -> str:
    return render_board(board_data(smi, procs, cfg, now), width, Paint(color), height, detail)


def watch(args, out=None, stop_after=None) -> int:
    """board / board --watch. `out` and `stop_after` (frames) exist for CPU tests."""
    import os
    import shutil
    import sys
    import threading
    import time
    out = out or sys.stdout
    try:
        out.reconfigure(errors="replace")
    except AttributeError:
        pass
    vt = enable_vt(isatty=out.isatty) if hasattr(out, "isatty") else False
    color = vt and not args.no_color
    width = args.width or max(80, min(160, shutil.get_terminal_size((120, 40)).columns))
    paint = Paint(color)
    height = getattr(args, "height", 0) or shutil.get_terminal_size((120, 40)).lines
    detail = getattr(args, "detail", False)
    if not args.watch:
        out.write(render_board(board_data(), width, paint, None if detail else height, detail) + "\n")
        return 0
    state = {"slow": slow_data(), "stop": False}

    def refresh():
        while not state["stop"]:
            time.sleep(args.slow_every)
            try:
                state["slow"] = slow_data()
            except Exception as exc:  # keep the last good snapshot, show the error
                state["slow_error"] = f"{type(exc).__name__}: {exc}"
    threading.Thread(target=refresh, daemon=True).start()
    if vt:
        out.write(SCREEN_ENTER)
    frames = 0
    try:
        while True:
            t0 = time.time()
            text = render_board(board_data(slow=state["slow"]), width, paint, height - 1, detail)
            slow_age = int(time.time() - state["slow"]["read_at"])
            stamp = (f"갱신 {datetime.now():%H:%M:%S} · {args.watch:g} 초 · 프로세스 · 파일은 "
                     f"{args.slow_every:g} 초마다 (지금 {slow_age} 초 전)"
                     + (f" · 읽기 오류 {state['slow_error']}" if state.get("slow_error") else "") + " · Ctrl+C 끝")
            text += "\n" + paint(fit(stamp, width), "dim")
            if vt:
                out.write(frame(text))
            else:
                os.system("cls" if os.name == "nt" else "clear")
                out.write(text + "\n")
            out.flush()
            frames += 1
            if stop_after and frames >= stop_after:
                return 0
            time.sleep(max(0.0, args.watch - (time.time() - t0)))
    except KeyboardInterrupt:
        return 0
    finally:
        state["stop"] = True
        if vt:
            out.write(SCREEN_LEAVE)
            out.flush()


# ---- dispatcher: fill GPU1 from the same queue (팀장 11/04 00:0x) ----
# One GPU1 unit at a time. Never starts training, never kills anything. P1 (score_watch
# evaluations, PRIORITY_BUSY markers, any GPU1 process it did not start) always wins at the
# next unit boundary. Training protection: no new unit while the 10-update mean > limit.
DISPATCH = {
    "gpu": 1,
    "results": "D:/mai-tmp/gpu/results",
    "logs": "D:/mai-tmp/gpu/logs",
    "idle_log": "D:/mai-tmp/gpu/idle_log.jsonl",
    "state": "D:/mai-tmp/gpu/dispatch_state.json",
    "p1_markers": ["D:/mai-tmp/gpu/PRIORITY_BUSY_GPU1"],
    "lead": "term_37f1d02b-35f8-435d-940e-d43a8a5be1de",
    "notify_every": 300,
    "train_limit_s": 29.7,
    "train_window": 10,
    "interval": 10,
    "requeue_after_s": 60,
}
ALLOWED_KINDS = frozenset({"eval", "probe", "render"})
# Same as the training launch script: Kit must not stop at the EULA prompt (stdin is closed).
KIT_ENV = {"OMNI_KIT_ACCEPT_EULA": "YES", "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}


def unit_env(it: dict, base: dict) -> dict:
    """Environment for one unit: inherited, then KIT_ENV, then the item's own values."""
    return {**base, **KIT_ENV, **{k: str(v) for k, v in (it.get("env") or {}).items()}}


def pid_alive(pid) -> bool:
    if not pid or psutil is None:
        return False
    try:
        return psutil.Process(int(pid)).is_running()
    except (psutil.Error, ValueError, OSError):
        return False


def family(pid) -> set[int]:
    """The wrapper and every process under it (the Kit child is a grandchild)."""
    out = set()
    if not pid_alive(pid):
        return out
    try:
        p = psutil.Process(int(pid))
        out.add(p.pid)
        out.update(c.pid for c in p.children(recursive=True))
    except psutil.Error:
        pass
    return out


FAIL_STREAK = 3


def item_family(it: dict) -> str:
    """Same program + same cwd = same family (a module after -m, else the script path)."""
    argv = it.get("argv") or []
    prog = argv[argv.index("-m") + 1] if "-m" in argv[:-1] else (argv[1] if len(argv) > 1 else "")
    return f"{it.get('kind')}|{prog}|{it.get('cwd') or ''}"


def failing_families(items: list[dict]) -> set[str]:
    """Families whose last FAIL_STREAK finished items all failed (technical failure loop)."""
    done = sorted((i for i in items if i.get("state") in ("끝", "실패") and i.get("done_at") is not None),
                  key=lambda i: i["done_at"])
    last: dict[str, list[str]] = {}
    for i in done:
        last.setdefault(item_family(i), []).append(i["state"])
    return {f for f, states in last.items() if len(states) >= FAIL_STREAK
            and all(s == "실패" for s in states[-FAIL_STREAK:])}


def item_ready(it: dict, now: float, exists=lambda p: Path(p).exists(), alive=pid_alive,
               blocked: set[str] | None = None) -> tuple[bool, str]:
    if it.get("state") != "대기":
        return False, "not_waiting"
    if blocked and item_family(it) in blocked and not it.get("fail_streak_ok"):
        return False, f"family_failed_{FAIL_STREAK}x"
    if it.get("kind") not in ALLOWED_KINDS:
        return False, f"kind_not_allowed:{it.get('kind')}"
    if not isinstance(it.get("argv"), list) or not it["argv"]:
        return False, "no_command"
    if needs_approval(it):
        return False, "needs_approval"
    if it.get("gpu") != DISPATCH["gpu"]:
        return False, "other_gpu"
    if it.get("start") and it["start"] > now:
        return False, "start_later"
    for p in it.get("wait_absent", []):
        if exists(p):
            return False, f"wait_absent:{p}"
    for p in it.get("wait_present", []):
        if not exists(p):
            return False, f"wait_present:{p}"
    for pid in it.get("wait_pids", []):
        if alive(pid):
            return False, f"wait_pid:{pid}"
    return True, "ready"


def train_mean(state: dict, train: dict | None, window: int) -> float | None:
    """Mean of the last `window` per-update samples from train_start_status.

    That file is rewritten every 10 updates, so a sample is one 10-update block and the guard
    acts from the first sample (no warm-up gap)."""
    hist = state.setdefault("train_hist", [])
    if train and type(train.get("iter")) is int and isinstance(train.get("iter_s"), (int, float)):
        if not hist or hist[-1][0] != train["iter"]:
            hist.append([train["iter"], float(train["iter_s"])])
            del hist[:-window]
    return sum(s for _, s in hist) / len(hist) if hist else None


def p1_busy(jobs: list[dict], ours: set[int], markers: list[str]) -> str | None:
    for m in markers:
        if marker_state(Path(m))["present"]:
            return f"marker:{m}"
    for j in jobs:
        if j["kind"] != "guard" and on_gpu(j, DISPATCH["gpu"]) and j["pid"] not in ours:
            return f"gpu1_process:{j['pid']}:{j['script']}"
    return None


def result_path(item_id) -> Path:
    return Path(DISPATCH["results"]) / f"item_{item_id}.json"


def did_not_run(it: dict, last: dict | None) -> bool:
    """C층 run-next returned without capturing: yielded, held, or pending with no capture."""
    if "c_layer_gpu1_remainder" not in " ".join(it.get("argv") or []) or not isinstance(last, dict):
        return False
    state = str(last.get("state", ""))
    ev = last.get("queue_event") if isinstance(last.get("queue_event"), dict) else {}
    ev_state = str(ev.get("state", ""))
    # run-next nests the event under queue_event; the two-seed run-one wrapper puts it at top level
    # (11/04 14:35 item 155 captured a clip but was taken for a yield and held the group).
    captured = ev.get("event") == "captured" or last.get("event") == "captured"
    if state.startswith("yielded") or "hold" in state or ev_state.startswith("yielded") or "hold" in ev_state:
        return True
    return (state == "pending" or ev_state == "pending") and not captured


def settle(it: dict, exists=lambda p: Path(p).exists(), alive=pid_alive, now: float | None = None) -> bool:
    """Running item -> 끝 / 실패 from the wrapper's result file. True when it changed."""
    if it.get("state") != "실행":
        return False
    rp = result_path(it["id"])
    if rp.exists():
        try:
            res = json.loads(read_shared_text(rp))
        except (OSError, ValueError):
            return False
        if res.get("rc") == 0 and did_not_run(it, res.get("last_json")):
            last = res.get("last_json") or {}
            it.update(state="대기", pid=None, run_at=None, log=it.get("log"),
                      yields=it.get("yields", 0) + 1, last_yield=last.get("state"),
                      start=(now if now is not None else datetime.now().timestamp()) + DISPATCH["requeue_after_s"])
            try:
                rp.unlink()
            except OSError:
                pass
            return True
        missing = [p for p in it.get("done_files", []) if not exists(p)]
        ok = res.get("rc") == it.get("done_rc", 0) and not missing
        it.update(state="끝" if ok else "실패", rc=res.get("rc"), done_at=res.get("ended"),
                  missing=missing or None)
        return True
    if not alive(it.get("pid")):
        it.update(state="실패", rc=None, done_at=datetime.now().timestamp(), missing=["wrapper_gone_no_result"])
        return True
    return False


def spawn_wrapper(item_id: int, log: str) -> int:
    """Start `runwrap` with no window, detached from this process tree. Returns wrapper PID."""
    import subprocess
    import sys
    flags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
                 | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    fh = open(log, "ab")
    try:
        p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "runwrap", str(item_id)],
                             stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,
                             creationflags=flags, close_fds=True)
    except OSError:
        # Some hosts refuse BREAKAWAY; retry without it (still no window).
        p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "runwrap", str(item_id)],
                             stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,
                             creationflags=flags & ~getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0),
                             close_fds=True)
    fh.close()
    return p.pid


def runwrap(item_id: int, cfg=LIVE) -> int:
    """Run one queue item's argv to completion and write its rc (the dispatcher reads it)."""
    import os
    import subprocess
    q = read_queue(cfg["queue"])
    it = next(i for i in q["items"] if i["id"] == item_id)
    env = unit_env(it, dict(os.environ))
    # Evaluators write into the done-file folder without creating it (items 81 · 114 · 115 failed so).
    for p in it.get("done_files", []):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now().timestamp()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    last_json = None
    try:
        child = subprocess.Popen(it["argv"], cwd=it.get("cwd") or None, env=env, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=flags)
        with child.stdout:
            for raw in child.stdout:
                line = raw.decode("utf-8", errors="replace")
                print(line, end="", flush=True)
                if line.lstrip().startswith("{"):
                    try:
                        last_json = json.loads(line)
                    except ValueError:
                        pass
        rc = child.wait()
    except OSError as exc:
        print(f"runwrap launch error: {exc}", flush=True)
        rc = -1
    rp = result_path(item_id)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps({"id": item_id, "rc": rc, "started": started, "last_json": last_json,
                              "ended": datetime.now().timestamp()}, ensure_ascii=False), encoding="utf-8")
    return rc


def notify_lead(subject: str, body: str) -> None:
    import subprocess
    try:
        subprocess.run(["orca", "orchestration", "send", "--to", DISPATCH["lead"], "--type", "status",
                        "--subject", subject, "--body", body], capture_output=True, timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        pass


def item_group(it: dict) -> str | None:
    if in_c_layer_group(it) or "c_layer_gpu1_remainder" in " ".join(it.get("argv") or []):
        return "c_layer"
    return None


def update_holds(state: dict, requeued: list[dict], train: dict | None, mean: float | None, now: float,
                 notify) -> None:
    """A C층 unit that came back held/yielded holds the whole group until training is running again,
    has advanced at least one status sample (10 updates) and passes the per-update gate.
    Hold and resume are each announced once."""
    holds = state.setdefault("holds", {})
    if train is None:
        # No training marker (prep time): the hold protects a training run that does not exist.
        for g in list(holds):
            del holds[g]
            notify(f"[dispatcher] {g} 재개", f"{hm(now)} 학습 없음 · 보류를 풀고 {g} 를 다시 띄움")
        return
    for it in requeued:
        g = item_group(it)
        if g and g not in holds:
            holds[g] = {"since": now, "reason": it.get("last_yield"),
                        "iter": (train or {}).get("iter")}
            notify(f"[dispatcher] {g} 보류 · {it.get('last_yield')}",
                   f"{hm(now)} 대기열 {it['id']} 이 {it.get('last_yield')} 로 돌아옴 · 학습이 다시 돌고 "
                   f"회당 {DISPATCH['train_limit_s']} 초 이하가 될 때까지 {g} 는 띄우지 않음 (다른 일은 계속)")
    for g, h in list(holds.items()):
        it_now = (train or {}).get("iter")
        advanced = type(it_now) is int and type(h.get("iter")) is int and it_now >= h["iter"] + 10
        if (train or {}).get("state") == "running" and advanced and mean is not None \
                and mean <= DISPATCH["train_limit_s"]:
            del holds[g]
            notify(f"[dispatcher] {g} 재개",
                   f"{hm(now)} 학습 {it_now} 회 · 회당 평균 {mean:.1f} 초 · {g} 다시 띄움")


def notify_launch(state: dict, it: dict, pid: int, log: str, now: float, notify) -> None:
    """Launch notices: at most one message per notify_every, carrying the count since the last."""
    state["launches_since_notice"] = state.get("launches_since_notice", 0) + 1
    if now - state.get("last_launch_notice", 0) >= DISPATCH["notify_every"]:
        n = state["launches_since_notice"]
        notify(f"[dispatcher] GPU1 띄움 · {it['title'][:40]}",
               f"{hm(now)} 대기열 {it['id']} P{it['priority']} {it['kind']} · wrapper PID {pid} · 로그 {log}"
               + (f" · 지난 알림 뒤 {n} 건" if n > 1 else ""))
        state["last_launch_notice"] = now
        state["launches_since_notice"] = 0


def fresh_p1(ours: set[int]) -> str | None:
    return p1_busy(live_jobs(nvidia_smi(), processes()), ours, DISPATCH["p1_markers"])


def dispatch_step(cfg=LIVE, now=None, smi=None, procs=None, spawn=spawn_wrapper, notify=notify_lead,
                  exists=lambda p: Path(p).exists(), alive=pid_alive, fam=family, recheck=fresh_p1) -> dict:
    now = now if now is not None else datetime.now().timestamp()
    try:
        state = json.loads(Path(DISPATCH["state"]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    q = read_queue(cfg["queue"])
    items = q["items"]
    before = {it["id"]: it.get("state") for it in items}
    changed = any([settle(it, exists, alive, now) for it in items])
    requeued = [it for it in items if before[it["id"]] == "실행" and it.get("state") == "대기"]
    smi = smi if smi is not None else nvidia_smi()
    procs = procs if procs is not None else processes()
    jobs = live_jobs(smi, procs)
    train = current_training(cfg)
    mean = train_mean(state, train, DISPATCH["train_window"])
    update_holds(state, requeued, train, mean, now, notify)
    held_groups = set(state.get("holds", {}))
    running = [it for it in items if it.get("state") == "실행" and it.get("gpu") == DISPATCH["gpu"]]
    ours = set()
    for it in running:
        ours |= fam(it.get("pid"))
    result = {"at": now, "train_mean": mean}
    if running:
        result.update(action="busy_own", item=running[0]["id"])
    elif (why := p1_busy(jobs, ours, DISPATCH["p1_markers"])):
        result.update(action="yield_p1", reason=why)
    elif train is not None and train.get("state") != "running":
        # train is None only when no training marker exists (prep time): GPU1 is free then.
        # A GPU1 Kit also shows up on GPU0 and blocks training's GPU0 admission (01:29~01:38):
        # nothing new while training is failed / starting / anything but running.
        result.update(action="train_not_running", reason=f"training state {train.get('state')}")
    elif mean is not None and mean > DISPATCH["train_limit_s"]:
        result.update(action="train_protect", reason=f"10-update mean {mean:.1f} s > {DISPATCH['train_limit_s']}")
    else:
        blocked = failing_families(items)
        for f in sorted(blocked - set(state.get("fail_notified", []))):
            notify("[dispatcher] 같은 작업 3 회 연속 실패 · 막음",
                   f"{hm(now)} {f} · 같은 종류가 {FAIL_STREAK} 회 연속 실패해 대기 항목을 막았다 · "
                   "고친 뒤 fail_streak_ok 를 붙여 다시 넣을 것")
        state["fail_notified"] = sorted(blocked)
        ready = sorted((it for it in items if item_ready(it, now, exists, alive, blocked)[0]
                        and item_group(it) not in held_groups),
                       key=lambda it: (it["priority"], it["id"]))
        late = recheck(ours) if ready else None
        if ready and late:
            result.update(action="yield_p1", reason=f"recheck:{late}")
        elif ready:
            it = ready[0]
            log = str(Path(DISPATCH["logs"]) / f"item_{it['id']}.log")
            try:
                result_path(it["id"]).unlink()
            except OSError:
                pass
            try:
                pid = spawn(it["id"], log)
                it.update(state="실행", pid=pid, run_at=now, log=log)
                result.update(action="launched", item=it["id"], pid=pid)
                notify_launch(state, it, pid, log, now, notify)
            except Exception as exc:  # a launch failure never stops the queue
                it.update(state="실패", rc=None, done_at=now, missing=[f"launch_error:{exc}"])
                result.update(action="launch_failed", item=it["id"], error=str(exc))
            changed = True
        else:
            g = smi["gpus"].get(DISPATCH["gpu"], {})
            result.update(action="nothing_to_fill", util=g.get("util"))
            Path(DISPATCH["idle_log"]).parent.mkdir(parents=True, exist_ok=True)
            with open(DISPATCH["idle_log"], "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": now, "event": "채울 일 없음", "util": g.get("util"),
                                     "holds": state.get("holds", {}),
                                     "waiting": [(it["id"], ("group_hold:" + item_group(it))
                                                  if item_group(it) in held_groups
                                                  else item_ready(it, now, exists, alive, blocked)[1])
                                                 for it in items if it.get("state") == "대기"]},
                                    ensure_ascii=False) + "\n")
            if now - state.get("last_notify", 0) >= DISPATCH["notify_every"]:
                notify("[dispatcher] GPU1 채울 일 없음",
                       f"{hm(now)} GPU1 {g.get('util')} % · 시작 가능한 대기열 항목 없음 · "
                       f"기록 {DISPATCH['idle_log']}")
                state["last_notify"] = now
    if changed:
        write_queue(cfg["queue"], q)
    state["last"] = result
    Path(DISPATCH["state"]).write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return result


def dispatch_loop(once: bool = False) -> int:
    import time
    while True:
        try:
            r = dispatch_step()
            print(json.dumps(r, ensure_ascii=False), flush=True)
        except Exception as exc:  # keep dispatching; log the error
            print(json.dumps({"at": datetime.now().timestamp(), "action": "error",
                              "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), flush=True)
        if once:
            return 0
        time.sleep(DISPATCH["interval"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("jobs.json"))
    sub = parser.add_subparsers(dest="action", required=True)
    st = sub.add_parser("status")
    st.add_argument("--registry", action="store_true", help="also print the hand-kept jobs.json list")
    bd = sub.add_parser("board")
    bd.add_argument("--watch", nargs="?", type=float, const=1.0, default=0,
                    help="redraw every N seconds, default 1 like mai-watch (Ctrl+C to stop)")
    bd.add_argument("--slow-every", type=float, default=10.0,
                    help="seconds between process / file rereads in watch mode")
    bd.add_argument("--width", type=int, default=0, help="columns (default: terminal width, 80..160)")
    bd.add_argument("--no-color", action="store_true")
    bd.add_argument("--height", type=int, default=0, help="rows (default: terminal height)")
    bd.add_argument("--detail", action="store_true", help="every row and every note, ignore the height")
    qp = sub.add_parser("queue")
    qs = qp.add_subparsers(dest="qaction", required=True)
    qa = qs.add_parser("add")
    qa.add_argument("--title", required=True)
    qa.add_argument("--priority", type=int, required=True)
    qa.add_argument("--gpu", type=int, required=True)
    qa.add_argument("--start")
    qa.add_argument("--end")
    qa.add_argument("--owner", default="lead")
    qa.add_argument("--cond")
    qa.add_argument("--needs-approval", action="store_true", help="never counted as startable")
    qa.add_argument("--kind", choices=sorted(ALLOWED_KINDS))
    qa.add_argument("--argv-json", help='command as a JSON list, e.g. ["python","x.py"]')
    qa.add_argument("--cwd")
    qa.add_argument("--wait-absent", action="append", default=[])
    qa.add_argument("--wait-pid", action="append", type=int, default=[])
    qa.add_argument("--done-file", action="append", default=[])
    for name in ("done", "run"):
        qs.add_parser(name).add_argument("id", type=int)
    qc = qs.add_parser("cancel", help="never ran / should not run; kept with a reason")
    qc.add_argument("id", type=int)
    qc.add_argument("--reason", required=True)
    qm = qs.add_parser("move")
    qm.add_argument("id", type=int)
    qm.add_argument("--priority", type=int)
    qm.add_argument("--gpu", type=int)
    qm.add_argument("--start")
    qm.add_argument("--end")
    dp = sub.add_parser("dispatch", help="fill GPU1 from queue.json (never training, never kills)")
    dp.add_argument("--once", action="store_true")
    rw = sub.add_parser("runwrap", help="internal: run one queue item and write its rc")
    rw.add_argument("item_id", type=int)
    gate = sub.add_parser("gate")
    gate.add_argument("job_id")
    args = parser.parse_args(argv)
    if args.action == "dispatch":
        return dispatch_loop(args.once)
    if args.action == "runwrap":
        return runwrap(args.item_id)
    if args.action == "board":
        return watch(args)
    if args.action == "queue":
        print(queue_cmd(args))
        return 0
    if args.action == "status":
        print(live_status())
        if args.registry:
            config = read_json(args.config)
            print(status(config, live_sources(config)))
        return 0
    config = read_json(args.config)
    live = live_sources(config)
    allowed, reason = admission(config, args.job_id, live)
    print(json.dumps({"job": args.job_id, "admit_next_unit": allowed, "reason": reason}, ensure_ascii=False))
    return 0 if allowed else 3


if __name__ == "__main__":
    raise SystemExit(main())
