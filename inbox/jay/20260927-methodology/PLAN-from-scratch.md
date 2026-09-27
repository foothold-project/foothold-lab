# 처음부터 학습 · 첫 짝의 학습 조건

> 분류: 계획
> 작성: 오흥재 · 2026-09-27 23:4x
> 근거: 설정 소스 실측(`rough_env_cfg.py` · `velocity_env_cfg.py` · `gap_ppo_cfg.py` · `v2a_env_cfg.py` · `terrain_importer.py`) · 폭주 9 건 · 학습 시간 실측
> 요지: **우리 설정 셋이 「fine-tuning 이라서」 정해진 값이다.** 처음부터 학습하면 그 셋이 근거를 잃는다. 어느 것을 되돌리고 어느 것을 그대로 둘지가 이 문서의 결정이다.
> 상태: 팀장 결정 대기
> 판: v1.0

---

## 1. fine-tuning 때문에 정한 값 셋 `확인됨`

| 칸 | NVIDIA 처음부터 | 우리 (fine-tune) | 어디에 |
|---|---|---|---|
| `learning_rate` | **1.0e-3** | **1.0e-4** | `rsl_rl_ppo_cfg.py:32` 대 `gap_ppo_cfg.py:18` |
| `max_init_terrain_level` | **None** | **2** | `rough_env_cfg.py` 대 `v2a_env_cfg.py:156` |
| `feet_air_time.weight` | **0.01** | 0.01 ~ 1.0 실험 | `rough_env_cfg.py` |

`gap_ppo_cfg.py` 의 docstring 이 이유를 그대로 적어 두었다.

> Keep the pretrained network architecture and use a **gentler learning rate**.

곧 **1.0e-4 는 「수렴한 정책을 살살 건드리려고」 고른 값이다.** 처음부터 학습하는
판에서는 그 근거가 없다. 그대로 쓰면 NVIDIA 가 쓴 속도의 **10 분의 1** 로 돈다.

`max_init_terrain_level = None` 이 무슨 뜻인지 소스로 확인했다.
`terrain_importer.py:340-347`

```python
if self.cfg.max_init_terrain_level is None:
    max_init_level = num_rows - 1          # 모든 행
else:
    max_init_level = min(self.cfg.max_init_terrain_level, num_rows - 1)
self.terrain_levels = torch.randint(0, max_init_level + 1, (num_envs,), ...)
```

- NVIDIA: 처음 난이도를 **0~9 에서 고르게** 뽑는다
- 우리: **0~2 에서만** 뽑는다

---

## 2. 계보를 숫자로 확정했다 `확인됨`

| 판 | 출발 | 우리가 돌린 판 | 학습률 | 총 |
|---|---|---|---|---|
| NVIDIA rough 배포본 | 처음부터 | **1499** | 1e-3 | 1499 |
| **foothold-v1** | NVIDIA | **1500** (`iter=1500`) | **1e-4** | 약 3000 |
| v2 계열 (v2g2 등) | NVIDIA | 3000 | 1e-4 | 약 4500 |

근거

- `models/foothold-v1.agent.yaml` : `resume: true` · `load_run: nvidia_pretrained_source` · `max_iterations: 1501` · `learning_rate: 0.0001`
- `models/foothold-v1.pt` : `iter = 1500` · `optimizer_state_dict` 있음 · `actor.0.weight (512, 235)`
- 공식 NVIDIA 체크포인트가 `iter = 1499` 이고 우리 `nvidia_pretrained.pt` 는
  그것을 **`iter` 만 0 으로 되감은 사본**이다 (`sim/eval/eval_command_response.py`
  머리글에 팀장 실측으로 이미 기록돼 있다). `max_iterations = 1500` 설정값과 맞는다.

**앞 문서에서 「NVIDIA 학습 판 수 미확인」이라고 적은 것을 정정한다. 1499 다.**

---

## 3. 지금 학습 조건 전부 `확인됨`

### 3-1. 지형 여덟 (`v2a_env_cfg.py:54-63`)

| 지형 | 비중 | 평가에서 |
|---|---|---|
| pyramid_stairs | 0.15 | rough6 |
| pyramid_stairs_inv | 0.15 | rough6 |
| boxes | 0.15 | rough6 |
| random_rough | 0.15 | rough6 |
| hf_pyramid_slope | 0.10 | rough6 |
| hf_pyramid_slope_inv | 0.10 | rough6 |
| omni_gap | 0.10 | **평가에 없다** |
| **rails** | 0.10 | **unseen10 에 «있다»** |

`rails` 가 학습과 unseen10 에 **둘 다** 있다. 이건 이미 `v2a_env_cfg.py:20` 에
적혀 있다.

> **학습에 넣은 지형으로 평가하므로 `rails` 는 「미경험 험지」주장에서 빠진다.**

곧 미경험은 **아홉 종**이다. 열 종이 아니다.

### 3-2. 명령 (`v2a_env_cfg.py:109-115`)

```
heading_command      = True
rel_heading_envs     = 1.0     <- wz 를 heading 추종으로 «덮어쓴다»
ang_vel_z            = (-1.0, 1.0)   (덮어써져서 안 쓰인다)
lin_vel_x            = (0.4, 1.5)
lin_vel_y            = (0.0, 0.0)
rel_standing_envs    = 0.02
resampling_time_range= (10.0, 10.0)
```

**학습에 없는 것**

| 없는 것 | 왜 없나 | 증상 |
|---|---|---|
| **제자리 회전** (vx≈0 · wz≠0) | `rel_heading_envs=1.0` 이 wz 를 덮고 `lin_vel_x` 하한이 0.4 | **축 2 의 유일한 실패 칸이 `turn/fell_ratio` 0.1094** (기준 ≤0.1) |
| **횡 이동** | `lin_vel_y = (0.0, 0.0)` | 축 2 에 횡 칸이 없어 안 드러난다 |
| **후진 · 저속** | `lin_vel_x` 하한 0.4 | 미측정 |

**원인과 증상이 이미 짝지어져 있다.** 최고 모델이 못 넘는 한 칸이, 학습이 한 번도
안 뽑는 행동이다.

### 3-3. 보상 (`rough_env_cfg.py` · `velocity_env_cfg.py`)

```
track_lin_vel_xy_exp  1.5      feet_air_time        0.01
track_ang_vel_z_exp   0.75     dof_torques_l2      -0.0002
action_rate_l2       -0.01     undesired_contacts   None (껐다)
flat_orientation_l2   0.0
```

우리가 건든 것은 **`feet_air_time` 하나뿐**이다. MARG 에서 고른 다른 방향
(feet center 등) 은 아직 안 건드렸다.

### 3-4. 신경망과 PPO

```
actor_hidden_dims  [512, 256, 128]     num_steps_per_env   24
critic_hidden_dims [512, 256, 128]     num_learning_epochs 5
activation         elu                 gamma 0.99 · lam 0.95
init_noise_std     1.0                 desired_kl 0.01 · schedule adaptive
noise_std_type     scalar              clip_param 0.2 · entropy_coef 0.01
actor.0.weight     (512, 235)          max_grad_norm 1.0
save_interval      25
```

---

## 3-5. **처음부터 판이 «이미 있다»** `확인됨`

팀장이 2026-08-11 에 돌린 재현본이 **처음부터 학습한 판**이다.
`logs/rsl_rl/unitree_go2_rough/2026-08-11_20-32-58`

```
resume: false              <- 처음부터
learning_rate: 0.001       <- 1e-3
max_iterations: 1500       <- 1499 «완주» · 체크포인트 31 개
init_noise_std: 1.0 · noise_std_type: scalar · schedule: adaptive
max_init_terrain_level: 5
model_1499.pt  iter=1499 · actor.0.weight (512, 235) · std 0.4258 ~ 0.7880
NVIDIA 배포본과 텐서 열쇠·모양이 «전부 같다» -> 우리 평가 하네스에 그대로 올라간다
```

**앞 문서와 이 문서 5 절에서 「처음부터 돌린 판이 하나도 없다」고 적은 것을 정정한다.
있다.** 그리고 그 판은 **터지지 않았다.**

독립적으로 처음부터 돌린 판의 std 가 0.426~0.788 로, NVIDIA 배포본의
0.443~0.810 과 거의 같은 자리에 수렴했다. 재현이 잘 된 판이다.

**다만 환경이 다르다.** 지형 6 종이고 명령이 넓다(아래 3-6). 그래서 이 판은
「처음부터 학습이 터지지 않는다」의 근거가 되지만, **「우리 v2b 지형 여덟에서도
안 터진다」의 근거는 아니다.**

### 이 판으로 먼저 할 것 (계산 시간 거의 안 든다)

**평가만 돌린다.** 텐서 모양이 같으니 축 1·축 2 하네스에 그대로 올라간다.
그러면 「NVIDIA 레시피를 처음부터 1499 판 돌린 정책」이 우리 두 축에서
어디에 있는지 숫자로 나온다. **새 기준선이 공짜로 생긴다.**

---

## 3-6. **NVIDIA 레시피에는 횡 이동과 후진이 «있다». 우리가 없앴다** `확인됨`

팀장 재현본의 `env.yaml` 실측.

| 명령 | NVIDIA rough | **우리 v2b** |
|---|---|---|
| `lin_vel_x` | **(-1.0, 1.0)** | **(0.4, 1.5)** |
| `lin_vel_y` | **(-1.0, 1.0)** | **(0.0, 0.0)** |
| `rel_standing_envs` | 0.02 | 0.02 (같다) |
| `rel_heading_envs` | 1.0 | 1.0 (같다) |
| `heading_command` | true | true (같다) |
| `max_init_terrain_level` | 5 | **2** |
| 지형 | **6 종** (0.2×4 · 0.1×2) | **8 종** (0.15×4 · 0.10×2 + omni_gap · rails) |
| `feet_air_time` | 0.01 | 0.01 (기본은 같다) |

**곧 물음이 「횡 이동을 넣을까」가 아니다. 「왜 뺐나」다.**

- `lin_vel_y` 를 **(-1.0, 1.0) 에서 (0.0, 0.0) 으로** 닫았다. 횡 이동을 학습에서 **없앴다**
- `lin_vel_x` 를 **(-1.0, 1.0) 에서 (0.4, 1.5) 로** 옮겼다. 후진과 저속을 **없애고** 고속을 더했다

`v2a_env_cfg.py:7` 이 `lin_vel_x` 쪽 결정의 이유를 적어 두었다.

> 축 1 을 먼저 고정한다. `lin_vel_x` 하한을 «안 열고» 정지는 `rel_standing` 으로 산다

`lin_vel_y` 를 닫은 이유는 이 파일에 적혀 있지 않다. `_verify_overrides` 는
(0.0, 0.0) 을 «기대값» 으로 검사만 한다. 상류에서 닫힌 것을 물려받았을
가능성이 있다. **미확인**이다.

**우리가 비교하는 기준선보다 좁은 명령으로 학습했다.** 그리고 축 2 의 유일한
실패 칸이 `turn` 이다. 우연으로 보기 어렵다.

---

## 4. 폭주의 기전 · 왜 처음부터가 다를 것인가

`init_noise_std = 1.0` 이라 **처음부터 학습하면 σ 가 1.0 에서 시작해 천천히 줄어든다.**
resume 판은 NVIDIA 에서 **σ 0.443 ~ 0.810** 을 물려받는다 (실측).

같은 크기의 gradient 한 걸음이 작은 σ 에서는 **비율로 훨씬 큰 교란**이다.
게다가 `actor_critic.py` 에 σ 를 가두는 코드가 **없다**.

이것이 「resume + 보상 변경」이 수치적으로 약한 이유의 후보다.

**정황이 하나 더 생겼다.** 3-5 절의 팀장 재현본이 처음부터 lr 1e-3 으로
1499 판을 «완주» 했다. 관문 없이, scalar 로. 지형 6 종 환경이지만
「처음부터는 터지지 않았다」가 실측으로 한 판 있다.

여전히 **증명은 아니다.** 우리 v2b 지형 여덟에서 처음부터 돌린 판이 없다.
이 짝이 그것을 잰다.

---

## 5. 첫 짝 · GPU 두 장에 두 판

**한 칸만 다르다. `feet_air_time` 이다.**

| | 판 A | 판 B |
|---|---|---|
| 이름 | `fs1-scratch-f001` | `fs2-scratch-f01` |
| 환경 | `Isaac-Velocity-V2b-Unitree-Go2-v0` | 같음 |
| 출발 | **처음부터** (resume 없음) | 같음 |
| `learning_rate` | **1.0e-3** | 같음 |
| **`feet_air_time`** | **0.01** (NVIDIA 값) | **0.1** |
| 시드 | 42 | 42 |
| 판 수 | 6000 | 6000 |
| 환경 수 | 4096 | 4096 |
| `max_init_terrain_level` | 2 (그대로) | 같음 |
| 명령 | v2b 그대로 | 같음 |
| GPU | cuda:0 | cuda:1 |

### 왜 이 짝인가

**판 A 가 새 기준선이다.** 「우리 지형·명령 + NVIDIA 보상」을 처음부터 돌린 것이다.
앞으로 모든 것을 이것에 대고 잰다.

**판 B 가 우리 기여다.** `feet_air_time 0.1` 은 resume 판에서 최고였다
(`v2g2-feetair01` · 축 1 통과 · 축 2 8/9). 처음부터도 좋은지는 **모른다.**
fine-tune 에서 좋았던 값이 처음부터도 좋을 이유가 없다.

**같은 시드다.** 한 칸만 다르게 하려면 시드를 맞춰야 한다.

### 왜 이 셋은 «안» 바꾸나

| 안 바꾸는 것 | 왜 |
|---|---|
| `max_init_terrain_level` 2 | 바꾸면 v2b 가 아니게 된다. `_verify_overrides` 가 2 를 검사해서 **학습이 시작조차 안 된다**. 새 env 클래스가 필요하다. 별도 실험으로 둔다 |
| 명령 (횡·후진·제자리 회전) | 이 짝의 물음은 「처음부터가 되나」다. 명령까지 열면 못 나오면 무엇 때문인지 안 갈린다. **다음 실험이다** |
| **σ 하한 · 비유한수 건너뛰기** | **넣으면 이 실험을 망친다.** 「처음부터도 터지나」를 재는 판인데 관문을 넣으면 그 물음이 사라진다. **관문 없이 돌린다** |

### 이건 선택이라고 밝힌다

`learning_rate` 를 1e-3 으로 올리는 것은 **선택이다.** 「fine-tuning 이라서 낮춘
값을 되돌린다」는 근거가 있지만, 그래도 한 칸을 바꾸는 것이다.
1e-4 로 처음부터 돌리면 NVIDIA 가 1499 판에 한 것을 하는 데 훨씬 오래 걸린다.
**그 판을 굳이 태우는 것은 권하지 않는다.**

---

## 6. 먼저 고칠 것 넷

| | 무엇 | 왜 |
|---|---|---|
| 1 | `run_gap_train.ps1` 이 `--resume --load_run --checkpoint` 를 **박아 넣는다** (83~89 행) | 처음부터 경로가 **없다.** 스위치를 더해야 한다 |
| 2 | `learning_rate` 를 명령줄로 준다 (`agent.algorithm.learning_rate=1.0e-3`) | 로그에 남아야 근거가 된다 |
| 3 | `verdict.py:41` 의 `CKPTS = (1500, 2000, 2500, 3000)` 이 **박혀 있다** | 6000 판을 돌려도 뒤쪽을 안 본다. 인자로 받게 고친다 |
| 4 | 새 이름은 `fs1` `fs2` · `register.py` 의 `NEVER` 집합과 안 겹치는지 본다 | 옛 계보와 섞이면 안 된다 |

3 번은 학습이 도는 중에 고쳐도 된다. 1·2·4 는 걸기 «전» 이다.

---

## 7. 걸리는 시간

```
한 판 3.7 ~ 3.9 초 (4096 환경 · RTX 5080 한 장) · 실측
6000 판  약 6 시간 20 분
두 장 동시  벽시계로도 약 6 시간 20 분
```

---

## 8. 그다음 순서

| | 실험 | 왜 이 순서인가 |
|---|---|---|
| 1 | **이 짝** · 처음부터 되나 + feet_air_time | 아래 전부가 여기에 기댄다 |
| 2 | **제자리 회전을 명령에 넣는다** | 축 2 의 **유일한** 실패 칸과 직결. resume 에서는 위험했지만 처음부터면 레시피의 일부다 |
| 3 | 횡 이동 · 후진 · 저속 | 축 2 에 칸을 먼저 만들어야 잴 수 있다 |
| 4 | stepping_stones | 축 1 최대 구멍. 최고 모델도 d0.5 · 1.0 m/s 에서 24 % |
| 5 | 관측 · 신경망 | **처음부터라서 열린다.** resume 은 `(512, 235)` 로 막았다 |

---

## 9. 미확인으로 남기는 것

| 항목 | 왜 |
|---|---|
| **우리 v2b 지형 여덟에서** 처음부터 돌리면 안 터지나 | 이 짝이 재는 것이다. (지형 6 종에서는 팀장 재현본이 완주했다 · 3-5 절) |
| 6000 판이면 수렴하나 | 곡선을 봐야 한다. 모자라면 더 돌린다 |
| 처음부터가 resume 성적에 도달하나 | 도달 못 할 수도 있다. 그러면 그것이 결과다 |
| `max_init_terrain_level` None 이 더 나은가 | 별도 실험 |
| 1e-3 이 우리 지형 여덟에 맞나 | `schedule=adaptive` 가 `desired_kl=0.01` 로 조절하지만 시작값은 선택이다 |

---

## 10. 개정 이력

| 판 | 날짜 | 무엇을 | 근거 |
|---|---|---|---|
| v1.0 | 2026-09-27 | 처음 씀. 팀장이 「학습 조건을 구체적으로 정해야 한다」고 해서. 설정 소스 다섯 개를 열어 fine-tuning 전용 값 셋을 찾았고, NVIDIA 1499 를 확정했다 | 실측 |
