# `v2b-r` · `v2b-s` 걸기 «전» 준비 · 설정과 관문

> 분류: 계획
> 작성: Claude 세션 (오흥재 지시) · 2026-09-23
> 근거: `CRITERIA.md` v1.2 9 절 (9 절은 v1.1 과 같다) · `cli_args.py:71-75` · `train.py:126-127` · `train.py:199` · `rl_cfg.py:144` · 저장된 `params/env.yaml` · `agent.yaml` 네 벌 · 관문 예행 4 건 (아래 3 절)
> 요지: **둘 다 새 설정 파일이 필요 없다** · 씨앗도 장치도 실행 인자다. 관문을 가짜 런으로 미리 걸어 네 경우를 봤다. 그러다 **한 학습에 장치가 둘**인 것을 봤다 · `--device` 는 시뮬레이션만 옮기고 학습 runner 는 네 런 모두 `cuda:0` 이다 (2 절)
> 상태: 확정 · **아직 안 걸었다**
> 판: v1.5
> 기준: `CRITERIA.md` v1.2 를 따름 (이 문서는 판정문이 아니라 준비입니다)

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

부모 `v2b` 는 시뮬레이션을 `cuda:1` 에서 돌렸습니다 (`env.yaml` 의
`sim.device` · 다만 2 절을 같이 보십시오).

**작업 디렉터리가 `C:\isaac\IsaacLab` 이어야 합니다.** rsl_rl 이 `logs/` 를
현재 디렉터리 기준으로 풀고, `train_win.py` 는 디렉터리를 «안» 바꿉니다
(`os.getcwd()` 를 적기만 합니다). 실제로 지금까지의 학습 기록이 전부
`C:\isaac\IsaacLab\logs\rsl_rl\` 아래에 있고, 이어받을 원본도
`logs\rsl_rl\unitree_go2_gap_nvidia\nvidia_pretrained_source\nvidia_pretrained.pt`
입니다 `실측`.

**그래서 스크립트는 절대 경로로 부릅니다.** 저장소 안에서
`python sim\policy\train_win.py` 로 부르면 `logs\...` 도 사전학습 원본도
못 찾습니다.

```bat
REM v2b-r · 부모와 «GPU 만» 다르다 · GPU0 · 결정성을 잰다
cd /d C:\isaac\IsaacLab
python C:\Users\AI-WS01\orca\workspaces\foothold-lab\rl-v2-command-restore\sim\policy\train_win.py ^
  --task Isaac-Velocity-V2b-Unitree-Go2-v0 ^
  --num_envs 4096 --seed 42 --max_iterations 3001 ^
  --headless --device cuda:0 ^
  --resume --load_run nvidia_pretrained_source ^
  --checkpoint nvidia_pretrained.pt ^
  --guard_against logs\rsl_rl\unitree_go2_gap_nvidia\2026-09-21_11-03-28_20260921_v2b_seed42_iter3000 ^
  agent.run_name=20260923_v2br_seed42_iter3000 ^
  --guard_intended sim.device
```

```bat
REM v2b-s · 부모와 «씨앗만» 다르다 · GPU1 (부모와 같은 GPU) · 씨앗 차이를 «한 번» 본다
cd /d C:\isaac\IsaacLab
python C:\Users\AI-WS01\orca\workspaces\foothold-lab\rl-v2-command-restore\sim\policy\train_win.py ^
  --task Isaac-Velocity-V2b-Unitree-Go2-v0 ^
  --num_envs 4096 --seed 7 --max_iterations 3001 ^
  --headless --device cuda:1 ^
  --resume --load_run nvidia_pretrained_source ^
  --checkpoint nvidia_pretrained.pt ^
  --guard_against logs\rsl_rl\unitree_go2_gap_nvidia\2026-09-21_11-03-28_20260921_v2b_seed42_iter3000 ^
  agent.run_name=20260923_v2bs_seed7_iter3000 ^
  --guard_intended seed
```

**`--guard_intended` 는 «평탄화 키만» 받습니다.** `nargs="*"` 라 원래는
뒤에 오는 것을 다 삼켜서, 뒤에 둔 `agent.run_name=...` 이 의도한 키
목록으로 들어가고 `train.py` 에는 안 넘어갔습니다.

**`train_win.py` 가 이제 «처음부터 안 삼키게» 가릅니다** (`=` 가 들었거나
`-` 로 시작하면 거기서 멈춘다 · 시험 여섯). 그래서 위 명령은 어느 차례로
두어도 됩니다. 되돌려 «붙이는» 방식은 안 씁니다. 하이드라는 «마지막»
덮어쓰기를 쓰는데 뒤에 붙이면 이기는 값이 뒤집히기 때문입니다.

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

## 2. 한 학습에 «장치가 둘» 입니다 `코드확인`

관문이 `env.yaml` 을 읽는 것이 맞는지 보려다 이것을 봤습니다.
**`--device` 는 장치 둘 중 «하나만» 정합니다.**

```
train.py:127   env_cfg.sim.device = args_cli.device      <- 시뮬레이션 장치
               --device 가 여기에 닿는다 · env.yaml 에 남는다
train.py:199   OnPolicyRunner(..., device=agent_cfg.device)   <- 학습 runner 장치
               --device 가 여기에 «안» 닿는다 · agent.yaml 에 남는다
```

**`cli_args.py` 에는 `device` 라는 글자가 한 번도 안 나옵니다** (0 건).
그래서 **`--device` 로는** `agent_cfg.device` 가 안 바뀌고 기본값이
남습니다.

```
rl_cfg.py:144   device: str = "cuda:0"      <- «기본값» 이다
```

**「고정」이 아닙니다.** 기본값일 뿐이고 바꿀 길이 둘 있습니다.

```
agent.device=... 로 하이드라 덮어쓰기
--distributed     train.py:137-139 이 두 장치를 local_rank 로 같이 맞춘다
```

우리가 돌린 넷은 **둘 다 안 썼으므로** 기본값이 남은 것입니다.

네 런의 두 파일을 열어 봤습니다.

| 런 | `agent.yaml` `device` (runner) | `env.yaml` `sim.device` (시뮬) |
|---|---|---|
| `v2a` | `cuda:0` | `cuda:0` |
| **`v2b`** | **`cuda:0`** | **`cuda:1`** |
| `gapF` | `cuda:0` | `cuda:0` |
| **`gapG`** | **`cuda:0`** | **`cuda:1`** |

**`--device cuda:1` 로 건 두 런에서도 runner 는 `cuda:0` 입니다** (이 네 런에서 그렇다는 것이고, 상류가 그렇게 «못 바꾸게» 한다는 뜻은 아닙니다).

### 이것이 9 절 계획에 무슨 뜻인가

`CRITERIA.md` 9 절은 `v2b-r` 을 GPU0 에, `v2b-s` 를 GPU1 에 두고 **GPU 가
변수가 되지 않게** 짠 것입니다. 그런데 `--device` 가 시뮬레이션만 옮기므로

```
v2b-r   시뮬 GPU0 · runner GPU0
v2b-s   시뮬 GPU1 · runner GPU0     <- runner 가 GPU0 에 «같이» 올라간다
```

**「자식이 부모와 한 항목만 다르다」는 여전히 성립합니다.** 부모 `v2b` 도
runner 가 `cuda:0` 이었으므로, `v2b-s` 는 부모와 씨앗만 다르고 `v2b-r` 은
부모와 시뮬 장치만 다릅니다. 관문이 보는 `env.yaml` 도 그대로 맞습니다.

**다만 「GPU 를 나눠 쓴다」는 그림은 절반만 맞습니다.** 둘을 동시에 걸면
runner 둘이 GPU0 을 같이 씁니다. 메모리와 속도에 영향이 있을 수 있습니다.
**재 본 적은 없습니다** `미측정`.

**그리고 `v2b-r` 이 재는 「GPU 효과」는 «시뮬레이션 장치» 의 효과입니다.**
runner 장치는 부모와 같으므로 그 부분은 안 갈립니다. 9 절이 기대한 것과
같은지는 팀장이 보셔야 합니다.

### 이 절이 «말하지 않는» 것

```
실제로 어느 GPU 가 얼마나 일했는지   안 쟀다 · 두 설정 칸을 읽은 것뿐이다
runner 가 cuda:0 인 것이 성능에      모른다 · v2b 는 그 상태로 끝까지 돌았다
  문제였는지
왜 cli_args 가 device 를 안 넘기나   상류 설계이고 까닭은 안 봤다
```

---

## 3. 관문을 «미리» 걸어 봤습니다 `실측`

부모 `v2b` 의 `env.yaml` 을 복사해 손으로 한 칸씩 바꾼 가짜 런 셋을 만들고,
**`config_diff_guard.py` 를 직접** 걸었습니다. **네 경우가 다 제대로
났습니다.**

**이것은 «관문» 을 시험한 것이지 1 절의 «학습 명령» 을 돌려 본 것이
아닙니다.** 학습은 안 걸었습니다. 1 절 명령이 통째로 도는 것은 확인한
적이 없습니다.

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
씨앗 7 이 적당한 수인지        모른다 · 내가 고른 수다
재현 «분산»                    이 둘로는 «못 잰다». 씨앗 하나를 바꾼
                              «한 번» 의 차이는 관측 하나이지 분포가
                              아니다. 분산을 말하려면 여러 번이 필요하다
GPU 효과의 «크기»              이 둘로는 «못 정한다». 같은 조건으로 다시
                              돌렸을 때의 폭을 모르기 때문이다
자식 둘을 서로 견주는 것       못 한다 · GPU 와 씨앗이 «동시에» 다르다
                              (CRITERIA v1.2 9 절이 금지한 자리다)
학습이 실제로 3000 까지 가는지  안 걸었으므로 모른다
```

**`v2b-r` 이 병렬의 전제입니다** (CRITERIA 9 절). 다만 **한 번 돌린
`v2b-r` 로 「GPU 효과」를 확정할 수는 없습니다.** 같은 GPU · 같은 씨앗으로
다시 돌려도 얼마나 흔들리는지를 모르면, `v2b-r` 에서 본 차이가 장치 탓인지
그냥 실행 편차인지 못 가릅니다. `CRITERIA.md` 가 v1.1 판 이력 ⑦ 에
그렇게 적었고 v1.2 에서도 그대로입니다.

**두 자식이 주는 것은 «관측 둘» 입니다.** `v2b-r` 이 「장치를 바꿨더니
이만큼 달랐다」 하나, `v2b-s` 가 「씨앗을 바꿨더니 이만큼 달랐다」 하나.
**둘 다 한 번씩이라 어느 쪽도 «폭» 이 아닙니다.**

그래서 이 둘로 할 수 있는 말은 여기까지입니다.

```
할 수 있는 말   두 자식이 부모와 각각 이만큼 달랐다 (칸 단위로 적는다)
                축 1 · 축 2 관문을 그래도 넘는가 못 넘는가
못 하는 말      「GPU 효과가 작다 · 크다」
                「재현 분산이 이 정도다」
                「자식 A 가 자식 B 보다 낫다」
```

**「작으니 병렬해도 된다」를 이 두 판으로 선언하지 마십시오.** 그러려면
같은 조건을 여러 번 돌려 실행 편차부터 갈라야 합니다. 그 설계는 이
문서에 없습니다.

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
| v1.5 | 2026-09-23 | 기준 문서가 **v1.2** 로 올랐다 (축 2 3/4 -> 4/4). 9 절은 안 바뀌어서 이 문서의 내용은 그대로이고, 가리키는 판만 옮겼다 | 기준 변경 |
| v1.4 | 2026-09-23 | 검증 4 회차. **「씨앗 하나로 분산을 잰다」를 물렸다** · 한 번은 관측 하나이지 분포가 아니다. **「두 차이의 크기를 견주면 장치 효과를 안다」도 물렸다** · 둘 다 한 번씩이라 실행 편차를 못 가른다. 이 둘로 할 수 있는 말과 못 하는 말을 갈라 적었다 | 지적 받음 |
| v1.3 | 2026-09-23 | 검증 3 회차. **삼킴 처리를 다시 고쳤다** · 되돌려 «붙이면» 하이드라가 이기는 값이 뒤집혀서, 처음부터 안 삼키게 가르는 쪽으로 바꿨다 (차례가 그대로 남는다 · 시험 여섯). 1 절 설명도 그에 맞게 고쳤다 | 코드확인 |
| v1.2 | 2026-09-23 | 검증 2 회차에서 넷. **작업 디렉터리를 안 적었다** · `logs\...` 상대 경로는 `C:\isaac\IsaacLab` 에서만 풀리고 `train_win.py` 는 디렉터리를 안 바꾼다 · 명령을 절대 경로로 고쳤다. **「runner 가 cuda:0 «고정»」이 지나쳤다** · 기본값일 뿐이고 하이드라와 `--distributed` 로 바뀐다. **`v2b-r` 한 번으로 GPU 효과를 확정할 수 없다** (`CRITERIA` v1.1 판 이력 ⑦) · `v2b-s` 의 폭과 같이 읽어야 한다. 삼킴을 «막는 것» 이 아니라 «처음부터 안 삼키게» 가르도록 했다 | 코드확인 |
| v1.1 | 2026-09-23 | 검증에서 셋을 고쳤다. **2 절을 갈아엎었다** · 「`agent.yaml` 이 GPU 를 안 적는다」가 아니라 **한 학습에 장치가 둘**이고 `--device` 는 시뮬레이션 쪽만 정한다 (`train.py:199` 의 runner 는 `agent_cfg.device` = `cuda:0` 고정). 9 절 계획에 무슨 뜻인지 같이 적었다. **1 절 명령의 인자 순서가 틀렸다** · `--guard_intended` 가 `agent.run_name=` 을 삼켜 런 이름이 `train.py` 에 안 넘어간다 · 순서를 고치고 `train_win.py` 에 삼킴 관문을 넣었다 (시험 넷). **3 절의 「그 명령을 그대로 걸었다」를 물렸다** · 관문만 걸었고 학습은 안 걸었다 | 코드확인 |
| v1.0 | 2026-09-23 | 처음 씀. 두 자식 모두 **새 설정 파일이 필요 없다**는 것을 `--seed` 가 `env.yaml` 까지 닿는 네 단계로 확인했다. 관문 명령을 가짜 런으로 미리 걸어 네 경우를 봤다. **`agent.yaml` 의 `device` 가 실제 GPU 를 안 적는다**는 것을 네 런에서 확인했다 | 코드확인 · 실측 |
