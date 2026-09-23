# `v2b-r` · `v2b-s` 걸기 «전» 준비 · 설정과 관문

> 분류: 계획
> 작성: Claude 세션 (오흥재 지시) · 2026-09-23
> 근거: `CRITERIA.md` v1.0 9 절 · `cli_args.py:71-75` · `train.py:126` · 저장된 `params/env.yaml` 네 벌 · 관문 예행 4 건 (아래 3 절)
> 요지: **둘 다 새 설정 파일이 필요 없다.** 씨앗도 GPU 도 실행 인자다. 관문 명령을 가짜 런으로 미리 걸어 네 경우를 확인했다
> 상태: 확정 · **아직 안 걸었다**
> 기준: `CRITERIA.md` v1.0 으로 판정함

**승인 전이라 걸지 않았습니다.** 이 문서는 설정과 관문만 준비한 것입니다.

---

## 0. 물음에 대한 답 · 새 설정 파일이 필요 없다

| 갈래 | 부모와 다른 한 항목 | 새 파일 | 어떻게 준다 |
|---|---|---|---|
| `v2b-r` | GPU | **필요 없다** | `--device cuda:0` |
| `v2b-s` | 씨앗 | **필요 없다** | `--seed <다른 수>` |

**씨앗이 실행 인자인 것을 코드에서 확인했습니다** `코드확인`.

```
train.py:28                --seed 를 받는다
cli_args.py:71-75          args_cli.seed -> agent_cfg.seed
train.py:126               agent_cfg.seed -> env_cfg.seed
저장된 env.yaml:83         seed: 42        <- 관문이 읽는 자리
```

**세 단계가 다 이어져 있어야 `--seed` 가 듣습니다.** 하나라도 끊겨 있으면
`v2b-s` 가 `v2b` 와 «같은 씨앗으로» 돌고 그것을 모른 채 재현 분산을 쟀다고
보고하게 됩니다. 그래서 네 줄을 다 열어 봤습니다.

`v2b-r` 은 기존 `v2b` 를 `--device` 만 바꿔 다시 거는 것이라 파일이 필요
없다는 것이 `config_diff_guard.py:41-48` 에 이미 적혀 있습니다.

---

## 1. 걸 명령 (아직 걸지 마십시오)

부모 `v2b` 는 `cuda:1` 에서 돌았습니다 (`env.yaml` 의 `sim.device`).

```bat
REM v2b-r · 부모와 «GPU 만» 다르다 · GPU0 · 결정성을 잰다
python sim\policy\train_win.py ^
  --task Isaac-Velocity-V2b-Unitree-Go2-v0 ^
  --num_envs 4096 --seed 42 --max_iterations 3001 ^
  --headless --device cuda:0 ^
  --resume --load_run nvidia_pretrained_source ^
  --checkpoint nvidia_pretrained.pt ^
  --guard_against logs\rsl_rl\unitree_go2_gap_nvidia\2026-09-21_11-03-28_20260921_v2b_seed42_iter3000 ^
  --guard_intended sim.device ^
  agent.run_name=20260923_v2br_seed42_iter3000
```

```bat
REM v2b-s · 부모와 «씨앗만» 다르다 · GPU1 (부모와 같은 GPU) · 재현 분산을 잰다
python sim\policy\train_win.py ^
  --task Isaac-Velocity-V2b-Unitree-Go2-v0 ^
  --num_envs 4096 --seed 7 --max_iterations 3001 ^
  --headless --device cuda:1 ^
  --resume --load_run nvidia_pretrained_source ^
  --checkpoint nvidia_pretrained.pt ^
  --guard_against logs\rsl_rl\unitree_go2_gap_nvidia\2026-09-21_11-03-28_20260921_v2b_seed42_iter3000 ^
  --guard_intended seed ^
  agent.run_name=20260923_v2bs_seed7_iter3000
```

**지켜야 할 것 셋.**

```
max_iterations 3001    부모 v2b 가 3001 로 돌아 model_3000.pt 를 냈다 `실측`
                       (agent.yaml 의 max_iterations: 3001 · 런 폴더에 model_3000.pt)
                       3000 을 주면 마지막이 2999 라 네 점의 끝이 빈다
CUDA_VISIBLE_DEVICES   쓰지 않는다 · --device 로 고른다
환경 변수              OMNI_KIT_ACCEPT_EULA=YES · KMP_DUPLICATE_LIB_OK=TRUE
                       없으면 «오류 없이 exit 0» 으로 죽는다
```

**씨앗 7 은 제가 고른 수입니다.** 다른 수를 원하시면 `--seed` 와 `run_name`
두 곳만 바꾸면 됩니다.

---

## 2. `agent.yaml` 의 `device` 를 믿으면 안 됩니다 `실측`

관문이 `env.yaml` 을 읽는 것이 맞는지 보려고 네 런을 열었습니다.

| 런 | `agent.yaml` 의 `device` | `env.yaml` 의 `sim.device` | 실제 |
|---|---|---|---|
| `v2a` | `cuda:0` | `cuda:0` | GPU0 |
| **`v2b`** | **`cuda:0`** | **`cuda:1`** | **GPU1** |
| `gapF` | `cuda:0` | `cuda:0` | GPU0 |
| **`gapG`** | **`cuda:0`** | **`cuda:1`** | **GPU1** |

**`agent.yaml` 의 `device` 는 네 런 모두 `cuda:0` 입니다.** 실제 GPU 와
무관하게 같은 값입니다. **그 칸으로는 GPU 를 가릴 수 없습니다.**
`config_diff_guard` 가 `env.yaml` 을 읽는 것은 그래서 맞습니다.

**이것은 「`agent.yaml` 이 GPU 를 안 적는다」까지만 말합니다.** 왜 안 적는지는
안 봤습니다.

---

## 3. 관문을 «미리» 걸어 봤습니다 `실측`

부모 `v2b` 의 `env.yaml` 을 복사해 손으로 한 칸씩 바꾼 가짜 런 셋을 만들고,
위에 적은 그 명령을 그대로 걸었습니다. **네 경우가 다 제대로 났습니다.**

| 가짜 런 | `--intended` | 바라는 것 | 결과 |
|---|---|---|---|
| 씨앗만 42 -> 7 | `seed` | 통과 | **exit 0** · 「의도한 1 칸만 다르다」 |
| GPU 만 1 -> 0 | `sim.device` | 통과 | **exit 0** · 「의도한 1 칸만 다르다」 |
| 씨앗 «과» GPU 둘 다 | `seed` | **막힘** | **exit 1** · 모르는 차이 1 |
| GPU 만 바꾸고 `seed` 를 의도라고 함 | `seed` | **막힘** | **exit 1** · 안 바뀐 의도 1 |

**셋째 줄이 이 관문의 요지입니다.** 두 항목이 같이 움직이면 그 둘은 부모와
«한 칸만 다른» 것이 아니고, 자식을 부모와 견주는 것 자체가 성립하지
않습니다. 넷째 줄은 반대쪽입니다. **바꿨다고 적어 놓고 안 바뀐 것**도
막습니다.

실제 `v2a` 대 `v2b` 로도 걸어 봤습니다. `sim.device` 와
`commands.base_velocity.rel_standing_envs` **둘이 나와서 막힙니다.** 이 둘을
「한 칸만 다르다」로 견주면 안 된다는 것이 그대로 나왔습니다.

---

## 4. 이 준비가 «답하지 못하는» 것

```
씨앗 7 이 적당한 수인지        모른다 · 씨앗 하나로는 분산을 «재는» 것이지
                              분산이 «작다» 를 보이는 것이 아니다
자식 둘을 서로 견주는 것       못 한다 · GPU 와 씨앗이 «동시에» 다르다
                              (CRITERIA 9 절이 금지한 자리다)
학습이 실제로 3000 까지 가는지  안 걸었으므로 모른다
```

**`v2b-r` 이 병렬의 전제입니다** (CRITERIA 9 절). GPU 효과가 0 에 가까우면
그 뒤로 자유롭게 병렬하고, 크면 직렬로 바꿉니다. 그 판단은 `v2b-r` 이
끝나야 섭니다.

---

## 근거 원문

`train.py` 와 `cli_args.py` 는 **우리 코드가 아니라 Isaac Lab 상류의 파일**
입니다. 아래가 그 원문입니다.

- Isaac Lab `https://github.com/isaac-sim/IsaacLab`
- 이 기계에 설치된 자리 · `C:/isaac/IsaacLab/scripts/reinforcement_learning/rsl_rl/`
  (`train.py:28` · `train.py:126` · `cli_args.py:71-75`)

우리 쪽 근거는 저장소 안에 있습니다.

- `sim/eval/config_diff_guard.py:41-48` · 재현 판에 새 설정 파일이 필요 없는 까닭
- `sim/policy/train_win.py` · `--guard_against` · `--guard_intended`
- 저장된 `params/env.yaml` 네 벌 · `logs/rsl_rl/unitree_go2_gap_nvidia/`

---

## 판 이력

| 판 | 날짜 | 무엇 | 근거 |
|---|---|---|---|
| v1.0 | 2026-09-23 | 처음 씀. 두 자식 모두 **새 설정 파일이 필요 없다**는 것을 `--seed` 가 `env.yaml` 까지 닿는 네 단계로 확인했다. 관문 명령을 가짜 런으로 미리 걸어 네 경우를 봤다. **`agent.yaml` 의 `device` 가 실제 GPU 를 안 적는다**는 것을 네 런에서 확인했다 | 코드확인 · 실측 |
