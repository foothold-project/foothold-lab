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
import os
import runpy
import sys

# **이 세 줄이 이 파일의 존재 이유다.** Kit 보다 먼저 들어가야 한다.
# 순서를 바꾸거나 아래로 내리지 마십시오.
import torch  # noqa: F401,E402
from tensordict import TensorDict  # noqa: F401,E402
import rsl_rl.runners  # noqa: F401,E402

DEFAULT_ISAACLAB = r"C:\isaac\IsaacLab"
TRAIN_RELATIVE = os.path.join(
    "scripts", "reinforcement_learning", "rsl_rl", "train.py")


def resolve_train_script(argv):
    """`train.py` 경로와, 그것을 뺀 나머지 인자.

    `--isaaclab_root` 는 **우리가 더한 팔**이라 여기서 걷어낸다. 그대로 넘기면
    `train.py` 의 argparse 가 모르는 인자라고 죽는다.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--isaaclab_root", type=str, default=None)

    known, rest = parser.parse_known_args(argv)

    root = (known.isaaclab_root
            or os.environ.get("ISAACLAB_PATH")
            or DEFAULT_ISAACLAB)

    return os.path.join(root, TRAIN_RELATIVE), rest


def main():
    train_script, rest = resolve_train_script(sys.argv[1:])

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

    runpy.run_path(train_script, run_name="__main__")


if __name__ == "__main__":
    main()
