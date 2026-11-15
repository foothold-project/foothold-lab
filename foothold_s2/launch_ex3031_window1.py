"""EX-30 (GPU0) 와 EX-31 (GPU1) 창 1 을 30 초 간격으로 숨김 띄움 (SONNET-X25 후속). 팀장 승인 전에는 실행하지 않는다.

    python foothold_s2/launch_ex3031_window1.py [--dry-run]

하는 일: GPU 여유 확인 -> EX-30 띄움 -> 30 초 -> EX-31 띄움 -> 두 판의 첫 update 줄(Learning iteration 1501)을 기다려 확인 줄을 찍음
-> 두 영수증의 부모 지형 해시가 같은지 단언 -> launch_status.json 을 쓰고 런처는 끝난다(학습 프로세스는 CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP 로 따로 산다).
GPU1 은 화면 GPU 라 학습만 하고 촬영은 하지 않는다. 확인이 실패해도 학습 프로세스를 죽이지 않는다(죽이는 것은 팀장 확인 뒤).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from foothold_s2.ex3031_window1_contract import DEVICE, EXTRA_UPDATES, PARENT_ITER, RUN_ROOT_NAME, STAGGER_SECONDS  # noqa: E402
from foothold_s2.runners.stage_transfer import compare_window1_receipts  # noqa: E402

BASH = r"C:\Program Files\Git\bin\bash.exe"
MAX_USED_MIB = {0: 2000, 1: 8000}                                        # 띄우기 전 장치별 사용 메모리 상한(GPU1 은 화면용 약 4.5 GB 가 이미 있다)
FIRST_UPDATE = re.compile(r"Learning iteration %d/\d+" % (PARENT_ITER + 1))
ORDER = ("EX-30", "EX-31")                                               # 30 초 간격으로 이 순서


def gpu_used_mib(smi_text: str) -> dict:
    """nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits 출력 -> {index: MiB}."""
    out = {}

    for line in smi_text.strip().splitlines():
        idx, used = [x.strip() for x in line.split(",")[:2]]
        out[int(idx)] = int(used)

    return out


def guard(used: dict) -> list[str]:
    return [f"GPU{i} 사용 {used.get(i)} MiB 가 상한 {lim} MiB 를 넘거나 읽을 수 없다" for i, lim in MAX_USED_MIB.items() if used.get(i) is None or used[i] > lim]


def command(exp: str, out_dir: str) -> list[str]:
    dev = DEVICE[exp]
    sh = f'cd "{ROOT.replace(chr(92), "/")}" && bash foothold_s2/run_ex3031_window1.sh {exp} {dev} "{out_dir.replace(chr(92), "/")}"'

    return [BASH, "-c", sh]


def start(exp: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP                  # DETACHED_PROCESS 와 같이 쓰면 창이 뜬다
    p = subprocess.Popen(command(exp, out_dir), cwd=ROOT, creationflags=flags, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)

    return p


def wait_for(path: str, pattern: re.Pattern, timeout_s: float, proc=None):
    t0 = time.time()

    while time.time() - t0 < timeout_s:
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = re.sub(r"\x1b\[[0-9;]*m", "", fh.read())
            m = pattern.search(text)

            if m:
                return m.group(0), time.time() - t0
            if "Traceback" in text:
                return None, time.time() - t0
        if proc is not None and proc.poll() is not None and not os.path.isfile(path):
            return None, time.time() - t0
        time.sleep(5)

    return None, time.time() - t0


def run_dir(exp: str, since: float):
    cands = [d for d in glob.glob(os.path.join(ROOT, "logs", "rsl_rl", RUN_ROOT_NAME, f"*_{exp.lower()}-w1")) if os.path.getmtime(d) >= since - 1]

    return max(cands, key=os.path.getmtime) if cands else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--first-update-timeout", type=float, default=900)
    args = ap.parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = os.path.join(ROOT, "logs", f"ex3031_w1_{stamp}")
    outs = {exp: os.path.join(root, exp) for exp in ORDER}

    if args.dry_run:
        for exp in ORDER:
            print("DRY", exp, DEVICE[exp], json.dumps(command(exp, outs[exp]), ensure_ascii=False))
        return 0

    smi = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True).stdout
    refused = guard(gpu_used_mib(smi))

    if refused:
        print("W1_REFUSED " + "; ".join(refused), flush=True)
        return 2

    since = time.time()
    status = {"stamp": stamp, "extra_updates": EXTRA_UPDATES, "runs": {}}
    procs = {}

    for i, exp in enumerate(ORDER):
        if i:
            time.sleep(STAGGER_SECONDS)
        procs[exp] = start(exp, outs[exp])
        status["runs"][exp] = {"pid": procs[exp].pid, "device": DEVICE[exp], "started": datetime.now().strftime("%m/%d %H:%M:%S"), "out": outs[exp]}
        print(f"W1_LAUNCHED {exp} pid={procs[exp].pid} {DEVICE[exp]} {status['runs'][exp]['started']} out={outs[exp]}", flush=True)

    ok = True

    for exp in ORDER:
        line, waited = wait_for(os.path.join(outs[exp], "train.log"), FIRST_UPDATE, args.first_update_timeout, procs[exp])
        status["runs"][exp]["first_update"] = line
        status["runs"][exp]["first_update_wait_s"] = round(waited, 1)
        print(f"W1_FIRST_UPDATE {exp} {line!r} after {waited:.0f}s", flush=True)
        ok = ok and line is not None

    if ok:
        try:
            receipts = {}

            for exp in ORDER:
                d = run_dir(exp, since)
                status["runs"][exp]["log_dir"] = d

                with open(os.path.join(d, "transfer_receipt.json"), encoding="utf-8") as fh:
                    receipts[exp] = json.load(fh)
            status["terrain_pair"] = compare_window1_receipts(receipts["EX-30"], receipts["EX-31"])
            print("W1_TERRAIN_PAIR " + json.dumps(status["terrain_pair"]), flush=True)
        except Exception as exc:                                                              # 확인 실패는 보고한다. 학습은 죽이지 않는다
            ok = False
            status["terrain_pair_error"] = repr(exc)
            print("W1_TERRAIN_PAIR_FAILED " + repr(exc), flush=True)

    status["ok"] = ok
    os.makedirs(root, exist_ok=True)

    with open(os.path.join(root, "launch_status.json"), "w", encoding="utf-8") as fh:
        json.dump(status, fh, ensure_ascii=False, indent=2)
    print("W1_LAUNCH_" + ("OK" if ok else "CHECK_FAILED") + f" status={os.path.join(root, 'launch_status.json')}", flush=True)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
