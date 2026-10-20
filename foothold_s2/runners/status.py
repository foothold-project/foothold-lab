"""무인 학습의 상태 파일 (「띄움 · 첫 증거 · 끝」 규칙). Kit 없이 import 된다.

한 파일 `train_start_status.json` 을 학습 중에도 계속 덮어쓴다. 쓰다 죽어도 반쯤 쓰인 파일이 남지 않게 임시 파일에 쓰고
os.replace 로 바꾼다. 읽는 쪽(감시 · 사람)은 state 와 time 으로 판정한다:

    state = "starting"  프로세스가 떴고 env 를 만드는 중
    state = "running"   iteration 이 돌고 있다 (iter · reward · iter_s · gpu_GiB). 첫 iteration 이 끝난 순간부터 나온다 = 첫 증거
    state = "done"      끝남 (iter = 마지막)
    state = "failed"    예외 (traceback)

`time` 이 오래 안 바뀌면 멈춘 것이다(감시가 iter_s 의 몇 배를 기다릴지는 감시 쪽 규칙). 종료 코드는 판정에 쓰지 않는다.
"""

from __future__ import annotations

import json
import os
import time

NAME = "train_start_status.json"


def write_status(log_dir: str | None, payload: dict) -> str:
    path = os.path.join(log_dir or ".", NAME)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    body = dict(payload)
    body["time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    body["pid"] = os.getpid()
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=1, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path


def read_status(log_dir: str) -> dict | None:
    try:
        with open(os.path.join(log_dir, NAME), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
