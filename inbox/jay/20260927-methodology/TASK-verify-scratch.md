# 검증 의뢰 · resume 에서 처음부터로 옮기는 것이 타당한가

> 분류: 검증 의뢰
> 작성: 오흥재 · 2026-09-28 01:0x
> 근거: 이 문서가 인용하는 소스와 실측값 전부. 아래 「읽을 것」의 파일을 직접 열어 확인하십시오.
> 요지: 물음 다섯에 **문서와 소스를 근거로** 답하십시오. 이 문서의 서사를 되돌려 주지 마십시오.
> 상태: 의뢰
> 판: v1.0

---

## 0. 이 의뢰가 요구하는 것

**세션의 해석을 승인해 달라는 것이 아닙니다.** 아래 물음 다섯에 **원본 문서와
소스를 열어** 답하십시오.

**반드시 지킬 것**

1. 이 문서가 「확인됨」이라고 적은 값도 **직접 다시 재십시오.** 2026-09-27 하루에
   세션이 넷을 틀렸고 전부 이미 문서에 답이 있었습니다.
2. **동의하는 답을 쓰지 마십시오.** 틀린 곳을 찾는 것이 이 의뢰의 목적입니다.
3. 근거 없는 칸은 **「미확인」**으로 두십시오. 추측으로 채우지 마십시오.
4. **한국어로** 쓰십시오. em dash 를 쓰지 마십시오. 「씨앗」이 아니라 **「시드」**
   입니다. actor · critic · optimizer 는 원어로 두십시오.

---

## 1. 읽을 것 (전부)

| 파일 | 무엇 |
|---|---|
| `inbox/jay/20260918-v2-command-restore.md` | v1.5 확정 · 명령 능력 · 능력 13 가지 · 기준선 셋 |
| `inbox/jay/20260921-v2-design.md` | v2 설계 |
| `inbox/jay/20260919-E-design.md` · `20260920-FG-design.md` · `20260920-H-design.md` | E · F · G · H 설계 |
| `inbox/jay/20260927-methodology/DECISIONS-resume-vs-scratch.md` | 이번 전환 제안 |
| `inbox/jay/20260927-methodology/PLAN-from-scratch.md` | 첫 짝 설계 |
| `inbox/jay/20260927-methodology/QUESTIONS-20260927.md` | 팀장 물음 원본 |
| `docs/DECISIONS.md` · `docs/LEDGER.md` | 확정 결정과 진행 현황 |
| `sim/eval/eval_command_response.py` | 축 2 하네스 |
| `sim/eval/verdict_manifest.py` | 축 2 문턱 |
| `_out/loop/verdict.py` | 판정 엔진 |

**소스**

```
C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/modules/actor_critic.py
C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/algorithms/ppo.py
C:/isaac/IsaacLab/source/isaaclab/isaaclab/envs/mdp/commands/velocity_command.py
C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/terrain_importer.py
C:/isaac/IsaacLab/source/isaaclab_tasks/.../go2/gap_training/v2a_env_cfg.py
C:/isaac/IsaacLab/source/isaaclab_tasks/.../go2/gap_training/gap_ppo_cfg.py
C:/isaac/IsaacLab/source/isaaclab_tasks/.../go2/agents/rsl_rl_ppo_cfg.py
C:/isaac/IsaacLab/source/isaaclab_tasks/.../go2/rough_env_cfg.py
C:/isaac/IsaacLab/scripts/reinforcement_learning/rsl_rl/train.py
```

---

## 2. 세션이 주장하는 것 (검증 대상)

### 2-1. 「비교 기준」과 「출발점」을 섞어 썼다

NVIDIA 를 비교 기준으로 쓰는 것은 **평가가 같을 것**만 요구하고, 출발점과 무관하다.
그런데 우리는 「NVIDIA 가 비교 기준이니 NVIDIA 에서 resume 한다」고 했다.

### 2-2. fine-tuning 전용으로 정한 값 셋

| 칸 | NVIDIA 처음부터 | 우리 | 근거 |
|---|---|---|---|
| `learning_rate` | 1.0e-3 | **1.0e-4** | `gap_ppo_cfg.py:18` · docstring 에 「gentler」 |
| `max_init_terrain_level` | `None` (0~9) | **2** (0~2) | `v2a_env_cfg.py:156` · `terrain_importer.py:340-347` |
| `feet_air_time` | 0.01 | fine-tune 델타로 고름 | `rough_env_cfg.py` |

### 2-3. 계보 숫자

| 판 | 출발 | 우리가 돌린 판 | 학습률 | 총 |
|---|---|---|---|---|
| NVIDIA rough | 처음부터 | 1499 | 1e-3 | 1499 |
| foothold-v1 | NVIDIA | 1500 | 1e-4 | 약 3000 |
| v2 계열 | NVIDIA | 3000 | 1e-4 | 약 4500 |

### 2-4. resume 은 관측 차원을 고정한다

`actor.0.weight` 가 `(512, 235)` 다. height scan 해상도를 바꾸면 235 가 바뀌고
resume 이 불가능하다. 로드맵 3 단계(신경망)가 봉쇄된다.

### 2-5. 폭주 9 건이 어느 손잡이로도 안 갈린다

매개화 · 보상 가중치 · 시드 · optimizer 처리 전부에서 완주와 사망이 섞여 나온다.
전부 같은 문구 `RuntimeError: normal expects all elements of std >= 0.0`.

`actor_critic.py` 에 `clamp` · `clip` · `isnan` · `isfinite` 가 하나도 없다.
`ppo.py:376` 의 `clip_grad_norm_` 은 NaN 을 막지 않고 **퍼뜨린다** (실측:
`[1.0, 2.0, NaN, 3.0]` -> `[NaN, NaN, NaN, NaN]`).

### 2-6. 처음부터 판이 하나 있고 터지지 않았다

`logs/rsl_rl/unitree_go2_rough/2026-08-11_20-32-58` · `resume: false` · `lr 0.001`
· 1499 완주 · `std 0.4258~0.7880`. **다만 지형 6 종 환경이고 명령이 넓다.**

### 2-7. 축 2 의 `turn` 미달이 판정 불가다

`verdict_manifest.py:81` 이 `("turn","fell_ratio"): ("<=", 0.10)`.
`v2g2-feetair01` 이 **7/64 = 0.1094**.

```
7/64  Wilson 95% [0.0540, 0.2090]   <- 문턱 0.10 이 구간 «안» 에 있다
6/64  Wilson 95% [0.0437, 0.1898]
n=4096 에서도 판정 안 되는 참값의 띠가 0.0907 ~ 0.1092
```

---

## 3. 물음 다섯

### Q1. 계보 서술이 원본과 어긋나는가

2-3 절의 표와 `20260918-v2-command-restore.md` 0-1-1 절을 대조하십시오.
**어긋나는 곳을 행 번호와 함께** 적으십시오. 없으면 없다고 적으십시오.

### Q2. 처음부터 전환이 «무엇을 무효화하는가»

아래 각각에 대해 **무효 · 유효 · 부분**으로 답하고 근거를 적으십시오.

| 대상 | 무엇이 걸리나 |
|---|---|
| v2 계열 판 전부 (v2b-r · v2g2 · v2n · v2s · v2sg · v2L · v2LG · s42A~D) | 계보가 달라지면 같은 표에 실을 수 있나 |
| `_out/loop/verdict.py:41` 의 `CKPTS = (1500,2000,2500,3000)` | 처음부터 4500 판에서 이 네 점이 무엇을 뜻하나 |
| CRITERIA v1.4 의 재현 조항 | 시드 하나로 시작하는 것이 어긋나나 |
| 보류 집합 설계 (`DESIGN-holdout.md`) | 출발점이 바뀌면 보류 집합이 바뀌나 |
| `foothold-v1` 을 「현재선」으로 쓰는 것 | 계보가 달라도 그 역할이 유효한가 |

### Q3. `fs1` · `fs2` 가 정말 한 칸만 다른가

```
fs1-scratch-f001   처음부터 · lr 1.0e-3 · feet_air_time 0.01 · 시드 42 · 4500 판
fs2-scratch-f01    위와 같고 feet_air_time 0.1
환경  Isaac-Velocity-V2b-Unitree-Go2-v0 · 4096 대 · max_init_terrain_level 2
관문  σ 하한 «없음» · 비유한수 건너뛰기 «없음»
```

**숨은 둘째 변수가 있는지** 찾으십시오. 특히

- `max_init_terrain_level = 2` 를 그대로 둔 것이 처음부터 학습에서 무엇을 바꾸나
  (NVIDIA 처음부터 값은 `None` 이다)
- `lr 1.0e-3` 이 우리 지형 여덟에 맞나. `schedule=adaptive` · `desired_kl=0.01`
  이 그것을 어디까지 흡수하나
- 4500 판이 수렴에 충분한가. NVIDIA 는 지형 6 종에 1499 였다

### Q4. `fell_ratio <= 0.10` 을 n=64 에서 판정하는 것이 타당한가

- 지금 관문에 신뢰구간이 없다. 이대로 두는 것이 맞나
- 신뢰구간 판정(상한 ≤ 문턱이면 통과 · 하한 > 문턱이면 미달 · 아니면 **미판정**)
  으로 바꾸면 **CRITERIA v1.4 가 어떻게 바뀌나**
- 참값이 0.0907~0.1092 안에 있으면 실용적인 n 으로 안 갈린다. 그 경우
  **무엇을 판정 근거로 삼아야 하나**
- 이 변경은 관문을 «느슨하게» 만드는 일이다. **그래도 해야 하나**

### Q5. 이 전환이 프로젝트 주제에 맞나

주제는 **「미경험 험지 지형 정책 적응」**이다.

- 처음부터 학습이 그 주제에 **더** 맞나, **덜** 맞나, 무관한가
- `rails` 가 학습과 unseen10 에 둘 다 있어 미경험이 **아홉 종**인 것
  (`v2a_env_cfg.py:20`) 이 전환으로 바뀌나
- 9/30 MVP 중간발표(`docs/DECISIONS.md:100`)를 앞두고 이 전환이
  **무엇을 위험하게 하나**

---

## 4. 답을 낼 곳

```
inbox/jay/20260927-methodology/VERIFY-scratch-astra.md
inbox/jay/20260927-methodology/VERIFY-scratch-fable.md
```

(AUDIT12 · AUDIT13 과 같은 자리입니다. `inbox/jou` 는 없습니다.)

머리 여섯 줄(분류 · 작성 · 근거 · 요지 · 상태 · 판)을 지키십시오.

**서로의 답을 보지 말고 각각 쓰십시오.**
