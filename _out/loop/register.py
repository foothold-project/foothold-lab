# -*- coding: utf-8 -*-
"""끝난 학습을 상태 파일에 **스스로** 등록한다.

분류: 운영
작성: 오흥재 · 2026-09-25
근거: 2026-09-25 · v2g·v2n 이 밤새 끝났는데 평가가 «안 걸렸다».
      `state.json` 에 등록이 안 돼 있어서 `eval_runner.py` 가 못 봤다.
      사람이 손으로 등록해야 했다.
요지: 학습 폴더를 훑어 `model_3000.pt` 가 있고 상태 파일에 «없는» 실행을
      찾아 등록한다. 로그에서 끝맺음과 죽음을 읽어 상태를 정한다.
상태: 초안
판: v1.0

왜 이것이 필요한가
    루프의 사슬이 여기서 끊겨 있었다.

        학습 끝 -> (끊김) -> 상태 파일 -> 평가 -> 판정

    watchdog 은 「선언과 실제가 다르다」고 **알리기만** 했다. 알림을 사람이
    읽어야 다음 칸이 돌았다. 그래서 「2 ~ 3 일 자동」이 아니었다.

무엇을 «안» 하나
    가설·대조군·바뀐 칸은 **사람이 적는다.** 이 스크립트는 그것을
    「미기재」로 두고 등록만 한다. 실험의 뜻을 기계가 지어내면 안 된다.

    그리고 **`halt_reason` 을 건드리지 않는다.** 멈춤은 사람이 푼다.

돌리는 법
    python _out/loop/register.py --dry-run
    python _out/loop/register.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
RUNDIR = r"C:\isaac\IsaacLab\logs\rsl_rl\unitree_go2_gap_nvidia"
LOGDIR = r"C:\isaac\IsaacLab\logs\gap_run_logs"
LAST_CKPT = 3000

# 폴더 이름 꼬리 · `<날짜>_<시각>_<실행이름>` 에서 실행 이름을 뽑는다.
DIRNAME = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_(\d{8})_(.+)$")


def short_name(dirname: str):
    """폴더 이름에서 «판 이름» 을 뽑는다. `20260925_v2s-stones10_seed42_iter3000`
    -> `v2s-stones10`. 판정문·결과 폴더가 이 이름을 쓴다."""
    m = DIRNAME.match(dirname)
    if not m:
        return None
    tail = m.group(2)
    return tail.split("_seed")[0]


def read_log(full: str) -> dict:
    """그 실행의 로그 꼬리를 읽어 끝맺음을 판단한다.

    **`full` 은 실행 이름 «전체» 다** (`20260925_v2s-stones10_seed42_iter3000`).
    2026-09-25 · 처음에 `*<짧은이름>*.log` 로 찾았더니 `v2b` 가
    `v2b-s4paired` 의 로그를 집어 «시드 43 의 죽음을 물려받았다».
    부분 문자열로 실행을 고르면 안 된다.
    """
    hits = sorted(glob.glob(os.path.join(LOGDIR, "*_%s.log" % full)))
    if not hits:
        return {"log": None, "log_count": 0}
    if len(hits) > 1:
        # 같은 이름으로 두 번 돌린 것이다. 어느 것인지 «말하고» 마지막을 쓴다.
        return dict(_tail(hits[-1]), log_count=len(hits),
                    log_warning="같은 이름의 로그가 %d 개다. 마지막을 읽었다"
                                % len(hits))
    return dict(_tail(hits[0]), log_count=1)


def _tail(p: str) -> dict:
    try:
        with io.open(p, "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - 200000))
            tail = h.read().decode("utf-8", "replace")
    except OSError:
        return {"log": p}
    its = re.findall(r"Learning iteration\s+(\d+)/(\d+)", tail)
    err = re.findall(r"^(RuntimeError|ValueError|AssertionError):\s*(.+)$",
                     tail, re.M)
    exits = re.findall(r"finished exit=(\d+)", tail)
    return {
        "log": p.replace("\\", "/"),
        "last_iter": int(its[-1][0]) if its else None,
        "exit": int(exits[-1]) if exits else None,
        "error": ("%s: %s" % err[-1]) if err else None,
    }


# **다시 등록하지 않을 판** (2026-09-26).
# 한 번 지웠는데 register.py 가 또 넣어서 평가를 낭비했다.
NEVER = {
    "v2a": "20260921-v2ab 뿌리에서 이미 평가했다",
    "v2b": "20260921-v2ab 뿌리에서 이미 평가했다",
    "v2b-p11": "v2b-r 과 체크포인트가 같다 (네 시점 state_dict 일치 확인)",
    "nvidia_gap_repro": "1500 판에서 끝난 옛 판",
    "gapwide": "1500 판에서 끝난 옛 판",
}


def scan(state: dict) -> list[dict]:
    known = {(r.get("name") or "") for r in state.get("running") or []}
    known |= set(NEVER)
    out = []
    for d in sorted(glob.glob(os.path.join(RUNDIR, "*"))):
        if not os.path.isdir(d):
            continue
        base = os.path.basename(d)
        name = short_name(base)
        if not name or name in known:
            continue

        # 폴더 이름의 «타임스탬프 뒤 전부» 가 실행 이름 전체다.
        full = base.split("_", 3)[-1]
        info = read_log(full)
        final = os.path.isfile(os.path.join(d, "model_%d.pt" % LAST_CKPT))

        # **끝난 것만 등록한다.** 도는 것은 사람이 선언한 것을 쓴다.
        if not final and info.get("exit") is None:
            continue

        if final and info.get("exit") == 0:
            status, why = "완료", "model_%d.pt 존재 + exit=0" % LAST_CKPT
        elif info.get("error"):
            status, why = "죽음", info["error"]
        elif final:
            status, why = "완료", "model_%d.pt 존재 (exit 코드를 못 읽음)" % LAST_CKPT
        else:
            # **오류 흔적이 없으면 「죽음」이라고 하지 않는다.**
            # 더 적은 판으로 «일부러» 돌린 것일 수 있다.
            status = "미확인"
            why = ("model_%d.pt 가 없고 오류 흔적도 없다 · 마지막 판 %s · "
                   "exit=%s · 사람이 판정할 것"
                   % (LAST_CKPT, info.get("last_iter"), info.get("exit")))

        out.append({
            "name": name,
            "branch": "미기재",
            "task": "미기재 · 로그의 --task 로 확인할 것",
            "seed": int(re.search(r"_seed(\d+)", base).group(1))
                    if re.search(r"_seed(\d+)", base) else None,
            "gpu": "미기재 · params/env.yaml 과 params/agent.yaml 로 확인할 것",
            "pid": None,
            "pid_kind": "끝났다",
            "log": info.get("log"),
            "out_dir": RUNDIR.replace("\\", "/") + "/*_" + full,
            "log_warning": info.get("log_warning"),
            "changed_vs_parent": "**미기재** · 사람이 적는다",
            "hypothesis": "**미기재** · 사람이 적는다",
            "control": "**미기재** · 사람이 적는다",
            "status": status,
            "finished": why,
            "last_iter": info.get("last_iter"),
            "registered_by": "_out/loop/register.py · %s"
                             % dt.datetime.now().isoformat(timespec="seconds"),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--state", default=STATE)
    args = ap.parse_args()

    with io.open(args.state, encoding="utf-8") as h:
        state = json.load(h)

    found = scan(state)
    if not found:
        print("등록할 것이 없다")
        return 0

    for r in found:
        print("%s %-16s %s · %s"
              % ("[시늉] " if args.dry_run else "등록", r["name"],
                 r["status"], r["finished"]))
    if args.dry_run:
        print("«--dry-run 이라 안 썼다»")
        return 0

    state.setdefault("running", []).extend(found)
    state["updated"] = dt.datetime.now().isoformat(timespec="seconds")
    state["updated_by"] = ("register.py 가 %d 개를 등록했다 · 가설과 대조군은 «미기재»"
                           % len(found))
    with io.open(args.state, "w", encoding="utf-8") as h:
        h.write(json.dumps(state, ensure_ascii=False, indent=1))
    print("\n%d 개 등록. **가설·대조군·바뀐 칸은 「미기재」다. 사람이 적는다.**"
          % len(found))
    return 0


if __name__ == "__main__":
    sys.exit(main())
