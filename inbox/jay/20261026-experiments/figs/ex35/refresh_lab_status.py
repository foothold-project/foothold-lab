"""Refresh the local lab status snapshot without starting GPU work."""

from __future__ import annotations

import argparse
import json
import msvcrt
import os
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


LAB = Path("C:/Users/AI-WS01/s2_lab/lab_status/index.html")
LOG = LAB.with_name("refresh.jsonl")
LOCK = LAB.with_name("refresh.lock")
KST = timezone(timedelta(hours=9))
GPU_QUERY = "index,uuid,memory.used,memory.free,utilization.gpu"


def gpu_rows(output: str) -> list[dict[str, str]]:
    rows = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 5 or not parts[0].isdigit() or not all(x.isdigit() for x in parts[2:]):
            raise ValueError(f"invalid nvidia-smi GPU row: {line!r}")
        rows.append(dict(zip(("index", "uuid", "used", "free", "util"), parts)))
    if {row["index"] for row in rows} != {"0", "1"}:
        raise ValueError("expected GPU 0 and 1")
    return sorted(rows, key=lambda row: row["index"])


def measure_gpus() -> list[dict[str, str]]:
    result = subprocess.run(
        ["nvidia-smi", f"--query-gpu={GPU_QUERY}", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    return gpu_rows(result.stdout)


def active_experiments() -> list[int]:
    import psutil

    pids = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (process.info["name"] or "").lower()
            argv = " ".join(process.info["cmdline"] or []).lower()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
        if not ("python" in name or "kit" in name):
            continue
        if any(token in argv for token in ("render_queue", "refresh_lab_status", "pytest")):
            continue
        if any(token in argv for token in ("train_sol", "train_step", "eval_map_modes", "record_sol", "isaac-sim", "isaaclab.sh")):
            pids.append(process.info["pid"])
    return sorted(pids)


def replace_one(source: str, pattern: str, replacement: str) -> str:
    changed, count = re.subn(pattern, lambda _: replacement, source, count=1)
    if count != 1:
        raise ValueError(f"status page marker missing: {pattern}")
    return changed


def render(source: str, now: datetime, gpus: list[dict[str, str]], active: list[int], decision_count: int) -> str:
    stamp = now.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")
    short = now.astimezone(KST).strftime("%m/%d %H:%M KST")
    source = replace_one(source, r"마지막 원자료 대조 <b>[^<]+</b>", f"마지막 원자료 대조 <b>{stamp}</b>")
    source = replace_one(source, r"팀장이 정할 것 · [^<]+</h2>", f"팀장이 정할 것 · {short}</h2>")
    run_text = "실행 중인 학습·평가 후보 없음" if not active else f"실행 후보 PID {', '.join(map(str, active))} · 상태 확인 필요"
    if decision_count < 1:
        raise ValueError("pending decisions missing")
    decision_label = "여덟" if decision_count == 8 else str(decision_count)
    for gpu in gpus:
        index = gpu["index"]
        row = (
            f'<div class="row"><div class="k">GPU{index}</div><div>'
            f'<span class="pill wait">실측 {short}</span>'
            f'사용 {gpu["used"]} MiB · 여유 {gpu["free"]} MiB · 사용률 {gpu["util"]}% · '
            f'UUID {gpu["uuid"]}. {run_text}. '
            '<a href="https://github.com/foothold-project/foothold-lab/blob/feature/verify-v2-mvp-jay/'
            'inbox/jay/20261026-experiments/RESULT-EX35-1027.md">EX-35 RESULT v1.5</a>: '
            f'창 STOP 6행 · 팀장 결정 대기 {decision_label} 건.</div></div>'
        )
        source = replace_one(source, rf'<div class="row"><div class="k">GPU{index}</div><div>.*?</div></div>', row)
    return source.replace("\u2014", " · ")


def write_atomic(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".refresh.tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    for attempt in range(20):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def refresh(page: Path = LAB, log: Path = LOG) -> dict:
    from lab_ex35_results import ensure_figure, load_sources, render_cards, render_decisions, render_page

    now = datetime.now(KST)
    gpus = measure_gpus()
    active = active_experiments()
    data, agenda, result, a11 = load_sources()
    cards = render_cards(data, agenda, result, a11)
    decisions = render_decisions(data, agenda)
    decision_count = decisions.count('class="row"')
    output = render(page.read_text(encoding="utf-8"), now, gpus, active, decision_count)
    output = render_page(output, cards, decisions)
    ensure_figure(data)
    write_atomic(page, output)
    receipt = {"at": now.isoformat(), "gpus": gpus, "experiment_candidate_pids": active}
    with log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    return receipt


def loop(interval_s: int, page: Path = LAB, log: Path = LOG, lock: Path = LOCK) -> None:
    with lock.open("a+b") as stream:
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        while True:
            started = time.monotonic()
            try:
                refresh(page, log)
            except Exception as exc:
                with log.open("a", encoding="utf-8") as out:
                    out.write(json.dumps({"at": datetime.now(KST).isoformat(), "error": str(exc)}, ensure_ascii=False) + "\n")
            time.sleep(max(0, interval_s - (time.monotonic() - started)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-s", type=int, default=1200)
    args = parser.parse_args()
    if args.interval_s < 1:
        parser.error("interval must be positive")
    if args.loop:
        loop(args.interval_s)
    else:
        print(json.dumps(refresh(), ensure_ascii=False))


if __name__ == "__main__":
    main()
