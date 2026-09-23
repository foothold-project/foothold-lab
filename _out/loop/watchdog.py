# -*- coding: utf-8 -*-
"""루프 감시 · «읽기만» 하는 판.

분류: 운영
작성: 오흥재 · 2026-09-23
근거: `inbox/jay/20260923-lineage/LOOP-RUNTIME.md` 3 절 · 8 절
요지: 상태 파일을 읽고 실제 상황과 맞는지 확인해 `STATE.md` 를 다시 쓴다.
      그리고 학습이 끝났으면 **평가만** 건다.
상태: 초안
판: v1.1

무엇을 걸고 무엇을 안 거는가 (2026-09-23 · 팀장 승인)
    건다      평가. `eval_runner.py` 를 떼어 놓고 띄운다
              걸 것이 없으면 그쪽이 스스로 판단해 바로 나온다
    안 건다   학습. 잘못 걸면 세 시간이고 같은 이름의 결과가 둘 생기면
              어느 것이 무엇인지 알 수 없게 된다
    안 건다   죽은 것 다시 걸기. 위와 같은 까닭

왜 PowerShell 이 아니라 Python 인가
    2026-09-23 에 PowerShell 판을 먼저 썼다가 버렸다. Windows PowerShell
    5.1 은 BOM 없는 UTF-8 을 ANSI 로 읽는다. 한글 주석이 깨지고 파싱까지
    실패했다. 저장소의 다른 도구가 전부 Python 이므로 여기에 맞춘다.

왜 «평가만» 거는가
    잘못 걸었을 때 잃는 것이 다르다. 학습은 세 시간이고 같은 이름의 결과가
    둘 생긴다. 평가는 수 분이고 같은 자리에 덮어쓸 뿐이다.
    학습 거는 기능은 판정과 분기 코드가 시험을 통과한 뒤에 켠다.

돌리는 법
    python _out/loop/watchdog.py
"""

from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
HUMAN = os.path.join(HERE, "STATE.md")
LOG = os.path.join(HERE, "watchdog.log")
EVAL = os.path.join(HERE, "eval_runner.py")
EVAL_LOCK = os.path.join(HERE, "eval_runner.lock")

# 학습으로 볼 프로세스의 최소 메모리. v2a/v2b 가 6.3 ~ 6.4 GB 였다.
TRAIN_MIN_BYTES = 1 * 1024 ** 3


def log(msg: str) -> None:
    line = "%s  %s\n" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    with io.open(LOG, "a", encoding="utf-8") as handle:
        handle.write(line)


def read_gpu() -> list[str]:
    """`nvidia-smi` 한 줄씩. 못 부르면 그 사실을 문자열로 남긴다."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=20, check=True).stdout
        return [ln.strip() for ln in out.splitlines() if ln.strip()]
    except Exception as exc:                                  # noqa: BLE001
        return ["nvidia-smi 실패: %s" % exc]


def read_big_python() -> list[tuple[int, float]]:
    """메모리가 큰 python 프로세스. (pid, GB) 목록."""
    rows = []
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-Process python -ErrorAction SilentlyContinue | "
             "ForEach-Object { \"$($_.Id) $($_.WorkingSet64)\" }"],
            capture_output=True, text=True, timeout=30).stdout
        for ln in out.splitlines():
            parts = ln.split()
            if len(parts) != 2:
                continue
            pid, ws = int(parts[0]), int(parts[1])
            if ws >= TRAIN_MIN_BYTES:
                rows.append((pid, ws / 1024 ** 3))
    except Exception as exc:                                  # noqa: BLE001
        log("프로세스 조회 실패: %s" % exc)
    return rows


def eval_running() -> bool:
    """평가가 이미 돌고 있나. 잠금 파일의 PID 로 본다."""
    if not os.path.isfile(EVAL_LOCK):
        return False
    try:
        with io.open(EVAL_LOCK, encoding="utf-8") as handle:
            pid = int((handle.read().split() or ["0"])[0])
    except Exception:                                         # noqa: BLE001
        return False
    if not pid:
        return False
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "if (Get-Process -Id %d -ErrorAction SilentlyContinue) "
             "{ 'yes' } else { 'no' }" % pid],
            capture_output=True, text=True, timeout=30).stdout
        return "yes" in out
    except Exception:                                         # noqa: BLE001
        return True      # 모르면 «돌고 있다» 로 본다. 두 번 거는 것보다 낫다


def launch_eval() -> str:
    """평가를 떼어 놓고 띄운다. **학습은 절대 안 띄운다.**

    걸 것이 있는지는 `eval_runner.py` 가 스스로 판단한다. 여기서 또
    판단하면 같은 규칙이 두 곳에 생기고 반드시 갈라진다.
    """
    if eval_running():
        return "평가가 이미 돌고 있다"
    try:
        subprocess.Popen(
            [sys.executable, EVAL],
            cwd=os.path.abspath(os.path.join(HERE, "..", "..")),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        return "평가를 띄웠다"
    except Exception as exc:                                  # noqa: BLE001
        return "평가를 못 띄웠다: %s" % exc


def find_mismatch(state: dict, big: list) -> list[str]:
    """상태 파일이 실제와 어긋나는 곳. **고치지 않고 적기만 한다.**"""
    out = []
    declared = state.get("running") or []

    if declared and not big:
        out.append("상태 파일은 «학습 중» 인데 큰 python 프로세스가 없다. "
                   "죽었을 수 있다. 자동으로 다시 걸지 «않는다»")
    if not declared and big:
        out.append("상태 파일은 «없음» 인데 큰 python 프로세스가 %d 개 돈다"
                   % len(big))

    now = dt.datetime.now()
    for run in declared:
        end = run.get("expected_end")
        if not end:
            continue
        try:
            when = dt.datetime.fromisoformat(end)
        except ValueError:
            out.append("«%s» 의 expected_end 를 못 읽는다: %r"
                       % (run.get("name"), end))
            continue
        over = (now - when.replace(tzinfo=None)).total_seconds() / 60.0
        budget = float(run.get("expected_minutes") or 0) * 0.5
        if over > max(budget, 15.0):
            out.append("«%s» 이 예상 종료를 %d 분 넘겼다"
                       % (run.get("name"), int(over)))
    return out


def render(state: dict, gpu: list, big: list, mismatch: list) -> str:
    stage = state.get("stage") or {}
    nxt = state.get("next") or {}
    budget = state.get("budget") or {}
    docs = state.get("docs") or {}
    declared = state.get("running") or []

    if declared:
        running = "\n          ".join(
            "%s  GPU %s  PID %s  시작 %s"
            % (r.get("name"), r.get("gpu"), r.get("pid"), r.get("started"))
            for r in declared)
    else:
        running = "없음"

    mm = "없음" if not mismatch else "\n".join("- " + m for m in mismatch)

    return """# 루프 상태 · 사람이 읽는 판

> 이 파일은 `watchdog.py` 가 `state.json` 에서 자동으로 만듭니다.
> 손으로 고치지 마십시오. 고치려면 `state.json` 을 고치십시오.

**이 내용이 된 때** {now} · 감시 스크립트 (평가를 거는 판)

> 이 시각은 «마지막으로 확인한 때» 가 아니라 «내용이 마지막으로 바뀐 때» 입니다.
> 내용이 그대로면 이 파일을 다시 쓰지 않습니다. 10 분마다 다시 쓰면 작업 트리가
> 늘 더러워져서 진짜 변경이 묻힙니다.
> 마지막 확인 시각은 `_out/loop/watchdog.log` 의 마지막 줄에 있습니다.

## 지금

```
단계      [{branch}] {sname} · {phase}
          {note}
도는 것   {running}
막힌 것   {halt}
다음      {nxt}
          (막는 것: {blocked})
```

## 실제로 잰 것

```
GPU       {gpu}
큰 python 프로세스   {nbig} 개{biglist}
```

## 상태 파일과 실제가 어긋나는 것

{mm}

## 예산

```
학습 판   {runs} 회 · 누적 {hours} 시간
codex     이번 주 {pct} %
          {bnote}
```

## 이어받는 사람이 읽을 순서

```
1  git pull origin main
2  이 파일
3  {criteria}
4  {branch_table}
5  막힌 것이 있으면 그것부터
   없으면 감시 스크립트가 도는지만 확인하고 «건드리지 않는다»
```

**대화 기록을 읽을 필요가 없어야 합니다.** 읽어야 했다면 이 파일이 부족한 것입니다.

## 이 스크립트가 지금 «안» 하는 것

```
학습을 걸지 않는다 · 커밋하지 않는다
죽은 학습을 «자동으로 다시 걸지 않는다» · 같은 이름의 결과가 둘 생기면
어느 것이 무엇인지 알 수 없게 된다

«평가는» 건다 (2026-09-23 팀장 승인) · eval_runner.py 를 떼어 놓고 띄운다
걸 것이 없으면 그쪽이 스스로 판단해 바로 나온다
```
""".format(
        now=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        branch=stage.get("branch"), sname=stage.get("name"),
        phase=stage.get("phase"), note=stage.get("note") or "",
        running=running,
        halt=state.get("halt_reason") or "없음",
        nxt=nxt.get("from_branch_table") or "",
        blocked=nxt.get("blocked_by") or "없음",
        gpu="\n          ".join(gpu),
        nbig=len(big),
        biglist="" if not big else "\n          " + "\n          ".join(
            "PID %d · %.1f GB" % (p, g) for p, g in big),
        mm=mm,
        runs=budget.get("train_runs", 0), hours=budget.get("train_hours", 0),
        pct=budget.get("codex_week_pct_reported", "?"),
        bnote=budget.get("note", ""),
        criteria=docs.get("criteria", ""), branch_table=docs.get("branch_table", ""))


# 첫 줄은 「GPU       0, 0 %, 0 MiB」이고 이어지는 줄은 「1, 7 %, 1873 MiB」다.
# 접두어를 선택으로 두지 않으면 첫 줄이 그물을 빠져나간다.
# 2026-09-23 에 실제로 빠져나갔고, GPU 0 이 마침 0 % 0 MiB 로 안 흔들려서
# 시험이 «운으로» 통과했다.
GPU_ROW = re.compile(r"^(?:GPU\s+)?(\d+),\s*(\d+)\s*%,\s*(\d+)\s*MiB$")
PID_ROW = re.compile(r"^PID (\d+) · ([\d.]+) GB$")

# 이 아래면 「비어 있다」로 본다. 데스크톱 앱이 항상 1 ~ 2 GB 를 쓴다.
GPU_IDLE_MIB = 3000


def strip_volatile(text: str) -> str:
    """매번 흔들리는 값을 «뭉개서» 비교용 본문을 만든다.

    왜 필요한가
        이것이 없으면 10 분마다 시각과 GPU 사용률만 바뀐 파일이 다시 쓰여
        `git status` 가 늘 더럽다. 진짜 변경이 그 잡음에 묻힌다.

    왜 «지우지» 않고 «뭉개는가»
        지우면 GPU 가 0 MiB 에서 12 GB 로 올라가도 파일이 안 바뀐다.
        그러면 STATE.md 가 거짓말을 한다. 그래서 잡음만 없애고
        «비었다 / 쓰는 중» 같은 상태 전이는 그대로 남긴다.
    """
    keep = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("**이 내용이 된 때**"):
            continue
        m = GPU_ROW.match(s)
        if m:
            used = int(m.group(3))
            keep.append("GPU%s %s" % (
                m.group(1), "비었음" if used < GPU_IDLE_MIB else "쓰는중"))
            continue
        m = PID_ROW.match(s)
        if m:
            keep.append("PID%s %.0fGB" % (m.group(1), float(m.group(2))))
            continue
        keep.append(line)
    return "\n".join(keep)


def main() -> int:
    if not os.path.isfile(STATE):
        log("state.json 이 없다. 멈춘다")
        return 1
    with io.open(STATE, encoding="utf-8") as handle:
        state = json.load(handle)

    gpu = read_gpu()
    big = read_big_python()
    mismatch = find_mismatch(state, big)

    fresh = render(state, gpu, big, mismatch)
    old = ""
    if os.path.isfile(HUMAN):
        with io.open(HUMAN, encoding="utf-8") as handle:
            old = handle.read()

    changed = strip_volatile(fresh) != strip_volatile(old)
    if changed:
        with io.open(HUMAN, "w", encoding="utf-8") as handle:
            handle.write(fresh)

    stage = state.get("stage") or {}
    if stage.get("phase") in ("학습 중", "평가 중"):
        log("  " + launch_eval())

    log("확인 · 단계 [%s] %s · 도는 것 %d · 어긋남 %d · %s"
        % (stage.get("branch"), stage.get("phase"),
           len(state.get("running") or []), len(mismatch),
           "STATE.md 다시 씀" if changed else "내용 그대로"))
    for m in mismatch:
        log("  어긋남 · " + m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
