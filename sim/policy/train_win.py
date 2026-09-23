# -*- coding: utf-8 -*-
"""Isaac Lab `train.py` 를 **Windows 에서 죽지 않게** 감싸는 실행기.

분류: 운영
작성: Claude 세션 (오흥재 지시) · 2026-09-18
근거: 실측. 이 워크스테이션에서 표준 train.py 가 exit 5 (access violation) 로 죽는 것을 재현
요지: Kit 보다 먼저 torch · tensordict · rsl_rl 을 들인다. IsaacLab 은 한 줄도 안 고친다
상태: 확정
판: v1.0

## 무엇이 문제인가 `확인됨`

이 워크스테이션에서 `scripts/reinforcement_learning/rsl_rl/train.py` 를 그냥
부르면 **시작하자마자 죽는다** (2026-09-18 · exit 5).

```
Windows fatal exception: access violation
  ... tensordict/_lazy.py line 38
  ... tensordict/utils.py line 44
```

`train.py` 는 **51행**에서 `AppLauncher(args_cli)` 로 Kit 를 띄우고 **그 뒤**
**84~85행**에서 `torch` 와 `rsl_rl.runners` 를 처음 들인다. Kit 가 올라온 뒤에
`tensordict` 를 처음 들이면 프로세스가 통째로 죽는다.

**이 저장소는 이미 이 함정을 알고 있다.** `eval_generalization.py` ·
`record_flat_baseline.py` · `eval_command_response.py` 가 전부 머리에 같은
주석을 달고 순서를 뒤집어 놓았다.

```python
# 별표. Windows 우회. Kit 를 띄운 뒤에 `rsl_rl.runners` 를 처음 import 하면
# 프로세스가 통째로 죽는다.
import torch
from tensordict import TensorDict
import rsl_rl.runners
```

**`train.py` 만 그 우회를 안 갖고 있다.**

## 왜 `train.py` 를 안 고치나

`C:\\isaac\\IsaacLab` 는 우리 저장소가 아니다. 거기를 고치면 다음 사람이
`git pull` 로 날리거나, 반대로 우리가 모르는 채 상류와 갈라진다. 이 파일은
**아무것도 안 고치고** 인자를 그대로 넘긴다.

## 또 하나 · `--resume` 은 반드시 «팔» 로 줘야 한다 `확인됨`

hydra 로 `agent.resume=true` 를 넘기면 **조용히 무시된다.** 오류가 안 난다.
2026-09-18 에 그것으로 19 iter 를 무작위 초기화에서 돌았다.

원인은 `cli_args.py` 76행이다.

```python
if args_cli.resume is not None:
    agent_cfg.resume = args_cli.resume
```

`--resume` 이 `action="store_true", default=False` 라 **언제나 not-None** 이고,
hydra 가 무엇을 넣었든 무조건 덮어쓴다. 이 경로로는 override 가 절대 안 먹는다.

**그래서 `--resume --load_run <폴더> --checkpoint <파일>` 로 준다.**

## 걸고 나서 반드시 되읽는다

학습이 시작되면 `logs/rsl_rl/<실험>/<런>/params/agent.yaml` 을 열어
`resume` 과 `load_checkpoint` 를 눈으로 확인한다. **97분을 엉뚱한 출발점에서
돌고 끝에서야 아는 것보다 낫다.**

```bash
grep -E "^resume:|^load_run:|^load_checkpoint:|^max_iterations:|^seed:" \
  logs/rsl_rl/unitree_go2_gap_nvidia/<런>/params/agent.yaml
```

로그에 이 줄이 떠야 한다.

```
[INFO]: Loading model checkpoint from: ...\nvidia_pretrained.pt
```

## 쓰는 법

`train.py` 에 주던 인자를 그대로 준다. D 를 돌린 명령 전문은 이렇다.

```bat
python sim\\policy\\train_win.py ^
  --task Isaac-Velocity-GapWideCmd-Unitree-Go2-v0 ^
  --num_envs 4096 --seed 42 --max_iterations 1501 ^
  --headless --device cuda:0 ^
  --resume --load_run nvidia_pretrained_source ^
  --checkpoint nvidia_pretrained.pt ^
  agent.run_name=20260918_gapwidecmd_seed42_iter1500
```

**`CUDA_VISIBLE_DEVICES` 를 쓰지 않는다.** `--device` 로 고른다.
`max_iterations` 를 안 주면 `gap_ppo_cfg.py` 의 **100** 이 쓰인다.

IsaacLab 위치가 다르면 `--isaaclab_root` 나 `ISAACLAB_PATH` 로 준다.
"""

import argparse
import glob
import os
import runpy
import subprocess
import sys
import threading
import time

# **이 세 줄이 이 파일의 존재 이유다.** Kit 보다 먼저 들어가야 한다.
# 순서를 바꾸거나 아래로 내리지 마십시오.
import torch  # noqa: F401,E402
from tensordict import TensorDict  # noqa: F401,E402
import rsl_rl.runners  # noqa: F401,E402

DEFAULT_ISAACLAB = r"C:\isaac\IsaacLab"
# 런 폴더가 생기고 `params/env.yaml` 이 떨어질 때까지 기다리는 한도.
WATCH_TIMEOUT_S = 600
WATCH_POLL_S = 2.0
NEWLINE = chr(10)
TRAIN_RELATIVE = os.path.join(
    "scripts", "reinforcement_learning", "rsl_rl", "train.py")



def _split_guard_intended(argv):
    """`--guard_intended` 가 «평탄화 키만» 먹게 미리 가른다.

    돌려주는 것: (키를 걷어낸 argv, 걷어낸 키 목록 또는 None)

    `--guard_intended` 는 `nargs="*"` 라 뒤에 오는 것을 다 삼킨다. 삼킨 것을
    «뒤에 붙여» 되돌리면 이번엔 차례가 바뀌고, 하이드라는 «마지막»
    덮어쓰기를 쓰므로 이기는 값이 뒤집힌다. 그래서 처음부터 안 삼키게
    가른다. **차례를 안 바꾼다.**

    멈추는 조건은 셋이다. `=` 가 들었거나 `-` 또는 `~` 로 시작하면 키가
    아니다. `~key` 는 하이드라의 «삭제» 문법이라 `=` 가 없다.

    **`-` 로 시작하는 평탄화 키가 «절대» 없다는 뜻은 아니다.** 사전 열쇠가
    음수면 `flatten` 이 `'-1'` 을 낼 수 있다. 우리가 본 세 런 2048 칸에는
    없었을 뿐이다. 그런 키를 주면 여기서 안 걷히고 학습 인자로 넘어가는데,
    그러면 의도 목록에서 빠져 **설정 관문이 「모르는 차이」로 막는다.**
    틀리는 방향이 안전한 쪽이다.

    플래그가 여러 번 나오면 **전부** 가른다.
    """
    argv = list(argv)
    if not any(a == "--guard_intended" or a.startswith("--guard_intended=")
               for a in argv):
        return argv, None
    out, keys, index = [], [], 0
    while index < len(argv):
        item = argv[index]
        # `--guard_intended=seed` 꼴도 여기서 받는다. 안 받으면 argparse 가
        # 따로 읽고, 우리가 나중에 `taken` 으로 덮어써서 그 값이 사라진다.
        if item.startswith("--guard_intended="):
            keys.append(item.split("=", 1)[1])
            index += 1
            continue
        if item != "--guard_intended":
            out.append(item)
            index += 1
            continue
        index += 1
        while index < len(argv):
            nxt = argv[index]
            if nxt.startswith(("-", "~")) or "=" in nxt:
                break
            keys.append(nxt)
            index += 1
    return out, keys


def resolve_train_script(argv):
    """`train.py` 경로와, 그것을 뺀 나머지 인자.

    `--isaaclab_root` 는 **우리가 더한 팔**이라 여기서 걷어낸다. 그대로 넘기면
    `train.py` 의 argparse 가 모르는 인자라고 죽는다.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--isaaclab_root", type=str, default=None)
    parser.add_argument("--guard_against", type=str, default=None,
                        help="이 런 폴더의 env.yaml 과 대조한다")
    parser.add_argument("--guard_intended", nargs="*", default=[],
                        help="다를 «예정» 인 평탄화 키들")

    # `--guard_intended` 는 `nargs="*"` 라 **뒤에 오는 것을 다 삼킨다.**
    # `--guard_intended seed agent.run_name=X` 로 쓰면 `agent.run_name=X` 가
    # 의도한 키 목록에 들어가고 `train.py` 에는 «안 넘어간다». 런 이름이
    # 조용히 사라진다.
    #
    # 삼킨 것을 «뒤에 붙여» 되돌리면 이번엔 차례가 바뀐다. 하이드라는
    # «마지막» 덮어쓰기를 쓰므로 `agent.run_name` 이 둘이면 이긴 쪽이
    # 뒤집힌다. 그래서 되돌리지 않고 **처음부터 안 삼키게** 가른다.
    # 원래 차례가 그대로 남는다.
    argv, taken = _split_guard_intended(argv)

    known, rest = parser.parse_known_args(argv)
    if taken is not None:
        known.guard_intended = taken

    root = (known.isaaclab_root
            or os.environ.get("ISAACLAB_PATH")
            or DEFAULT_ISAACLAB)

    return os.path.join(root, TRAIN_RELATIVE), rest, root, known


def run_name_from(rest):
    """`agent.run_name=...` 값. 없으면 `None`.

    **여럿이면 «마지막» 을 쓴다.** 하이드라가 마지막 덮어쓰기를 쓰므로,
    앞엣것을 고르면 «감시하는 런» 과 «실제로 생기는 런» 이 달라진다.
    그러면 설정 관문이 엉뚱한 폴더를 보거나 아예 못 찾고 건너뛴다.
    """
    found = None
    for arg in rest:
        if arg.startswith("agent.run_name="):
            found = arg.split("=", 1)[1]
    return found


def find_run_dir(isaaclab_root, run_name):
    """그 `run_name` 으로 끝나는 가장 새 런 폴더. 없으면 `None`.

    rsl_rl 이 `<타임스탬프>_<run_name>` 으로 만든다. 이름을 우리가 주므로
    **다른 사람 런을 집을 일이 없다.**
    """
    if not run_name:
        return None
    pattern = os.path.join(
        isaaclab_root, "logs", "rsl_rl", "*", "*_" + run_name)
    hits = [d for d in glob.glob(pattern) if os.path.isdir(d)]
    return max(hits, key=os.path.getmtime) if hits else None


def write_launch_record(run_dir, rest, train_script):
    """**무엇으로 띄웠는가** 를 런 폴더에 남긴다.

    런 폴더에 `events.out.tfevents` · `git/` · `params/` 는 있는데 «명령»이
    없었다. 재현 판을 걸 때 「같은 명령이었나」를 사람 기억에 묻게 된다.
    """
    path = os.path.join(run_dir, "launch_command.txt")
    if os.path.exists(path):
        return
    lines = [
        "# 이 런을 띄운 명령. train_win.py 가 남긴 것이다.",
        "# 이것이 정본이다. 문서에 적힌 명령과 다르면 «이쪽» 이 맞다.",
        "",
        "python " + os.path.basename(__file__) + " " + " ".join(rest),
        "",
        "train.py  : " + train_script,
        "python    : " + sys.executable,
        "cwd       : " + os.getcwd(),
        "argv      : " + repr(sys.argv),
    ]
    with io_open(path, "w") as handle:
        handle.write(NEWLINE.join(lines) + NEWLINE)
    print("[train_win] 명령을 남겼습니다: " + path, flush=True)


def io_open(path, mode):
    import io as _io
    return _io.open(path, mode, encoding="utf-8")


def guard_against(run_dir, reference_run, intended):
    """이 런의 `env.yaml` 을 기준 런과 견준다. `(문제 있나, 설명)`."""
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval"))
    import config_diff_guard as diff

    flat_new = diff.load_env_yaml(run_dir)
    flat_ref = diff.load_env_yaml(reference_run)
    expected, unexpected, unchanged = diff.compare(
        flat_ref, flat_new, intended)
    if not unexpected and not unchanged:
        return (False, "설정 관문 통과 · 의도한 %d 칸만 다릅니다" % len(expected))

    lines = ["설정 관문이 막았습니다."]
    for key, left, right in unexpected:
        lines.append("  모르는 차이  %s : 기준 %s 대 이번 %s" % (key, left, right))
    for key, value in unchanged:
        lines.append("  안 바뀜      %s : 둘 다 %s" % (key, value))
    return (True, NEWLINE.join(lines))


def watch_and_check(isaaclab_root, rest, train_script, reference_run, intended):
    """런 폴더를 기다렸다가 명령을 남기고, 기준 런이 있으면 대조한다.

    **어긋나면 이 프로세스를 죽인다.** 세 시간을 쓴 뒤가 아니라 1 분 안에
    잡으려는 것이다. 죽이는 것은 «우리 프로세스» 뿐이다.
    """
    run_name = run_name_from(rest)
    if not run_name:
        print("[train_win] agent.run_name 이 없어 런 폴더를 못 찾습니다. "
              "명령 기록과 설정 관문을 건너뜁니다.", flush=True)
        return

    deadline = time.time() + WATCH_TIMEOUT_S
    while time.time() < deadline:
        run_dir = find_run_dir(isaaclab_root, run_name)
        env_yaml = (os.path.join(run_dir, "params", "env.yaml")
                    if run_dir else None)
        if env_yaml and os.path.exists(env_yaml):
            try:
                write_launch_record(run_dir, rest, train_script)
            except Exception as error:  # 기록 실패로 학습을 죽이지 않는다
                print("[train_win] 명령 기록 실패: %r" % (error,), flush=True)
            if reference_run:
                try:
                    bad, message = guard_against(
                        run_dir, reference_run, intended)
                except Exception as error:
                    print("[train_win] 설정 관문이 못 돌았습니다: %r" % (error,),
                          flush=True)
                    return
                print("[train_win] " + message, flush=True)
                if bad:
                    print("[train_win] **학습을 멈춥니다.** 어긋난 설정으로 "
                          "세 시간을 쓰지 않습니다.", flush=True)
                    sys.stdout.flush()
                    os._exit(3)
            return
        time.sleep(WATCH_POLL_S)
    print("[train_win] 런 폴더를 %d 초 안에 못 찾았습니다. 명령 기록과 "
          "설정 관문을 건너뜁니다." % WATCH_TIMEOUT_S, flush=True)


def main():
    train_script, rest, isaaclab_root, opts = resolve_train_script(sys.argv[1:])

    if not os.path.isfile(train_script):
        raise SystemExit(
            "train.py 가 없습니다: {}\n"
            "--isaaclab_root 나 ISAACLAB_PATH 로 IsaacLab 위치를 주십시오."
            .format(train_script)
        )

    if "--resume" in rest:
        if "--load_run" not in rest or "--checkpoint" not in rest:
            raise SystemExit(
                "--resume 을 줬으면 --load_run 과 --checkpoint 도 줘야 합니다.\n"
                "안 주면 가장 최근 런에서 이어받아 출발점이 조용히 달라집니다."
            )

    for arg in rest:
        if arg.startswith("agent.resume"):
            raise SystemExit(
                "`agent.resume=...` 은 조용히 무시됩니다 (cli_args.py 76행).\n"
                "`--resume --load_run <폴더> --checkpoint <파일>` 로 주십시오."
            )

    # `train.py` 가 `import cli_args` 를 한다. 같은 폴더를 경로에 올린다.
    sys.path.insert(0, os.path.dirname(train_script))

    # `argparse` 가 `sys.argv[0]` 을 쓰고 hydra 가 나머지를 읽는다.
    sys.argv = [train_script] + rest

    print("[train_win] torch · tensordict · rsl_rl 을 Kit 보다 먼저 들였습니다.",
          flush=True)
    print("[train_win] train.py : {}".format(train_script), flush=True)
    print("[train_win] 인자      : {}".format(" ".join(rest)), flush=True)
    print("[train_win] 시작되면 params/agent.yaml 의 resume 과 "
          "load_checkpoint 를 되읽어 확인하십시오.", flush=True)
    if opts.guard_against:
        print("[train_win] 설정 관문 · 기준 런 {} · 의도한 칸 {}"
              .format(opts.guard_against, opts.guard_intended or "(없음)"),
              flush=True)

    watcher = threading.Thread(
        target=watch_and_check,
        args=(isaaclab_root, rest, train_script,
              opts.guard_against, opts.guard_intended),
        daemon=True)
    watcher.start()

    runpy.run_path(train_script, run_name="__main__")


if __name__ == "__main__":
    main()
