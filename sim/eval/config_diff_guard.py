# -*- coding: utf-8 -*-
"""두 학습을 견주기 «전» 에 `env.yaml` 을 전수 대조하는 관문.

분류: 도구
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: v2a 대 v2b 실측. 685 칸 중 셋이 달랐고 그중 `sim.device` 를 못 보고 있었다
요지: 의도한 칸 말고 다른 칸이 다르면 «비교하기 전에» 막는다
상태: 확정
판: v1.0

## 왜 필요한가 `확인됨`

2026-09-21. v2a 와 v2b 를 **「`rel_standing_envs` 한 칸만 다르다」**로
판정문에 적었다. 검증에서 걸렸다.

```
env.yaml 평탄화 685 칸 중 다른 칸 3
  commands.base_velocity.rel_standing_envs   0.02    대  0.1      의도한 것
  sim.device                                 cuda:0  대  cuda:1   **못 보고 있었다**
  log_dir                                    (경로)
```

두 판을 동시에 돌리려고 GPU 를 갈랐는데, 그것이 **두 번째 차이**가 됐다.
`PREDICTION.md` 에 장치를 적어 두고도 **「이것도 두 판을 가르는 차이다」를
못 알아봤다.**

**의도한 칸만 보면 절대 안 나온다.** 그래서 전수로 훑고, **모르는 차이가
하나라도 있으면 0 이 아닌 값으로 끝낸다.**

## 쓰는 법

```
python sim/eval/config_diff_guard.py ^
  --run_a <v2a 런 폴더> --run_b <v2b 런 폴더> ^
  --intended commands.base_velocity.rel_standing_envs
```

`--ignore` 는 기본으로 `log_dir` 하나다. **`sim.device` 는 기본으로 안
무시한다** · 그것이 이 도구가 생긴 까닭이다.

## 재현 판(`v2b-r`)에는 «새 설정 파일이 필요 없다» `확인됨`

장치는 설정 클래스가 아니라 **`--device` 팔**에서 온다
(`SimulationCfg.device` · `simulation_cfg.py:355`). 그리고 **`env.yaml` 에는
클래스 이름도 태스크 이름도 안 남는다** (685 칸 전수 확인 · 0 건).

곧 **같은 태스크를 장치만 바꿔 걸면 그것이 재현 판이다.** 따로
`v2b_r_env_cfg.py` 를 만들면 **같은 `env.yaml` 을 내는 클래스가 둘**이 되고,
「모든 칸이 같아야 한다」는 주장이 오히려 흐려진다.

```
python sim/policy/train_win.py ^
  --task Isaac-Velocity-V2b-Unitree-Go2-v0 ^
  --num_envs 4096 --seed 42 --max_iterations 3001 ^
  --headless --device cuda:0 ^
  --resume --load_run nvidia_pretrained_source ^
  --checkpoint nvidia_pretrained.pt ^
  agent.run_name=20260921_v2br_seed42_iter3000
```

걸고 나서 **이 관문으로 「장치만 다른지」를 확인한다.**

```
python sim/eval/config_diff_guard.py ^
  --run_a <v2b 런> --run_b <v2b-r 런> --intended sim.device
```

**의도한 차이 하나만 나와야 한다.** 장치를 바꿨더니 `sim.physx` 쪽 값이
같이 움직인다면 그것도 여기서 잡힌다.
"""

from __future__ import annotations

import argparse
import io
import os
import sys

# 기록용이라 달라도 되는 칸. **여기에 무엇을 더할 때마다 한 번 더 생각한다.**
DEFAULT_IGNORE = ("log_dir",)


def flatten(value, prefix=""):
    """중첩 사전을 `a.b.c -> repr(값)` 으로 편다.

    값을 `repr` 로 두는 것은 0.1 과 '0.1' 을 안 섞기 위해서다.
    """
    out = {}
    if isinstance(value, dict):
        for key, item in value.items():
            child = "%s.%s" % (prefix, key) if prefix else str(key)
            out.update(flatten(item, child))
    elif isinstance(value, (list, tuple)):
        # 목록은 통째로 하나의 값으로 본다. 길이가 달라도 한 줄로 잡힌다.
        out[prefix] = repr(list(value))
    else:
        out[prefix] = repr(value)
    return out


def load_env_yaml(run_dir):
    import yaml

    path = os.path.join(run_dir, "params", "env.yaml")
    if not os.path.exists(path):
        raise SystemExit("env.yaml 이 없다: %s" % path)
    return flatten(yaml.unsafe_load(io.open(path, encoding="utf-8")))


def compare(flat_a, flat_b, intended=(), ignore=DEFAULT_IGNORE):
    """`(의도한 차이, 모르는 차이, 의도했는데 «안» 다른 칸)`.

    셋째가 중요하다. **「바꿨다고 적었는데 실제로는 안 바뀐 것」** 도 관문이
    잡아야 할 사고다.
    """
    intended = tuple(intended)
    ignore = tuple(ignore)
    keys = set(flat_a) | set(flat_b)

    expected, unexpected, unchanged = [], [], []
    for key in sorted(keys):
        left, right = flat_a.get(key), flat_b.get(key)
        if key in ignore:
            continue
        if left == right:
            if key in intended:
                unchanged.append((key, left))
            continue
        if key in intended:
            expected.append((key, left, right))
        else:
            unexpected.append((key, left, right))
    return expected, unexpected, unchanged


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_a", required=True)
    parser.add_argument("--run_b", required=True)
    parser.add_argument("--intended", nargs="*", default=[],
                        help="다를 «예정» 인 평탄화 키들")
    parser.add_argument("--ignore", nargs="*", default=list(DEFAULT_IGNORE))
    args = parser.parse_args()

    flat_a = load_env_yaml(args.run_a)
    flat_b = load_env_yaml(args.run_b)
    expected, unexpected, unchanged = compare(
        flat_a, flat_b, args.intended, args.ignore)

    print("A %s" % os.path.basename(args.run_a.rstrip("/\\")))
    print("B %s" % os.path.basename(args.run_b.rstrip("/\\")))
    print("평탄화 칸 %d · 무시 %d" % (len(set(flat_a) | set(flat_b)), len(args.ignore)))
    print()

    for key, left, right in expected:
        print("  의도한 차이   %-46s %s 대 %s" % (key, left, right))
    for key, value in unchanged:
        print("  **안 바뀜**   %-46s 둘 다 %s" % (key, value))
    for key, left, right in unexpected:
        print("  **모르는 차이** %-44s %s 대 %s" % (key, left, right))

    problems = len(unexpected) + len(unchanged)
    print()
    if problems:
        print("**막는다** · 모르는 차이 %d · 안 바뀐 의도 %d"
              % (len(unexpected), len(unchanged)))
        print("이 둘을 «한 칸만 다르다» 로 견주면 안 된다.")
    else:
        print("통과 · 의도한 %d 칸만 다르다" % len(expected))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
