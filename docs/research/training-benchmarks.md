# 학습 성능 실측 — Go2 험지 (AI-WS01)

> 작성 2026-08-09 · 측정 환경 **AI-WS01** (RTX 5080 ×2 · Threadripper 7970X · 256GB RAM · Windows 11)
> 성격: **웹 조사가 아니라 이 기계에서 실제로 돌린 숫자.** 전부 로그에서 추출.
> 관련: [`SETUP_GUIDE`](../../../02_team/SETUP_GUIDE.md) · `cloud-gpu-options.md` · `ros2-isaacsim-integration.md`

---

## 0. 세 줄

1. **험지 학습 처리 속도 = 약 23,000 steps/s** (4096 envs, RTX 5080 1장). 1 iteration 4.17초.
2. **`collisionApproximateCylinders=true` 플래그로 53,141 steps/s — 2.25배.** 다만 **물리 영향 검증 중**.
3. **학습은 실제로 된다** — 193 iteration 만에 보상 −2.32 → **+10.78**, 에피소드 길이 425 → **983.82 step(최대 1000)**.

---

## 1. 측정 조건 (재현용)

```powershell
conda activate isaac311
cd C:\isaac\IsaacLab
$env:OMNI_KIT_ACCEPT_EULA="YES"

python train_go2_win.py --task Isaac-Velocity-Rough-Unitree-Go2-v0 `
    --num_envs 4096 --max_iterations 300 --seed 42 --headless
```
※ `train_go2_win.py` = Windows 우회 래퍼(네이티브 확장 선점 import). `SETUP_GUIDE` §5 참조.

**환경 설정 (실제 파일에서 확인)**

| 항목 | 값 | 파일 |
|---|---|---|
| `num_steps_per_env` | **24** | `.../go2/agents/rsl_rl_ppo_cfg.py:13` |
| `max_iterations` (기본) | **1500** | 같은 파일 `:14` — NVIDIA 기본값, 변경 가능 |
| `sim.dt` | **0.005초** (200Hz) | `velocity_env_cfg.py:311` |
| `decimation` | **4** → 정책 **50Hz** | `:308` |
| `episode_length_s` | **20.0초** → 최대 **1000 step** | `:309` |
| 지형 | 8m×8m 타일 **10행 × 20열 = 200개** | `terrains/config/rough.py` |

**단위 환산**
```
1 step        = 물리 4틱 = 0.02초 (정책 1회 명령)
1 iteration   = 4096 envs × 24 step = 98,304 env-steps
              = 로봇 1대 기준 32.8분치 경험
에피소드 최대 = 20초 = 1000 step
```

---

## 2. ★ 플래그 A/B — `collisionApproximateCylinders`

**배경**: 사전조사에서 *"Go2 험지가 평지 대비 6배 느리다. 원인은 다리 실린더 콜리전. 우회 플래그 있음"*으로 나왔으나 **미검증 상태**였다.

```powershell
# B 조건에만 추가
--kit_args="--/physics/collisionApproximateCylinders=true"
```

### 1차 측정 (30 iteration, ⚠️ **시드 미고정**)

| | A (플래그 없음) | B (플래그 있음) | 차이 |
|---|---|---|---|
| **처리 속도** | 23,591 steps/s | **53,141 steps/s** | **+125%** |
| iteration 1회 | 4.17초 | **1.85초** | −56% |
| 벽시계 (30 iter) | 2.64분 | 1.43분 | |
| 샘플 수 | 28 (워밍업 2회 제외) | 28 | |
| 범위 | 21,602 ~ 24,740 | 44,656 ~ 60,342 | **겹치지 않음** |
| 학습 총량 | 2,949,120 | 2,949,120 | 동일 |
| 마지막 평균 보상 | −2.32 | −2.49 | |
| **마지막 평균 에피소드 길이** | **425.53 step** | **212.82 step** | ⚠️ **절반** |

### ⚠️ 해석 주의 — 두 가지

**① 속도 향상은 확실하다.** 범위가 겹치지 않고 벽시계도 절반이다.

**② 에피소드 길이 절반은 아직 결론 낼 수 없다.**
- 1차 측정은 **시드를 고정하지 않았다.** 강화학습은 무작위성이 커서 같은 설정도 매번 다르다
- 30 iteration은 학습 극초반이라 값이 요동친다
- → **시드 42 고정 · 300 iteration 재측정 진행 중** (결과 나오면 이 문서 갱신)

**가설(미검증)**: 플래그가 Go2 정강이의 원통 콜리전을 근사하므로 접촉 형상이 달라져 넘어지는 빈도가 바뀔 수 있다.

### 실무 함의 (속도만 놓고 보면)

| | 1,500 iteration 학습 시간 | 하루(8시간) 가능 횟수 |
|---|---|---|
| A | **104분** | 약 4~5회 |
| B | **46분** | 약 10회 |

> ⚠️ **단 GPU 처리량이 병목이 아니다.** 1 사이클 = 학습(46~104분) + 결과 판독(15분) + 판단(30분) + 수정(15분).
> **사람의 판단이 병목**이므로 실질 사이클은 하루 4~5회다.

---

## 3. 학습이 실제로 되는가 — 진행 곡선

**같은 실행(A 조건, 시드 42) 안에서의 변화:**

| iteration | Mean reward | Mean episode length | 최대 대비 | 실제 생존 |
|---|---|---|---|---|
| 30 | **−2.32** | 425.53 step | 42.6% | 8.5초 |
| **193** | **+10.78** | **983.82 step** | **98.4%** | **19.7초** |

**읽는 법**
- **보상이 음수 → 양수로 넘어갔다.** 음수는 *"벌이 상보다 크다"* = 아직 못 걷는다. 양수는 걷는다는 뜻
- **에피소드 길이 983.82 / 1000** = 20초 중 19.7초를 버틴다. 거의 안 넘어진다
- 30 iteration일 때 −2.32였던 건 **정상**이다. `train.py`는 사전학습 체크포인트를 쓰지 않고 **랜덤 초기화에서 시작**한다

> ⚠️ **혼동 주의**: `play.py --use_pretrained_checkpoint`로 보는 영상은 **NVIDIA가 1,500 iteration 완주시킨 정책**이다.
> `train.py`는 **처음부터** 배운다. 둘은 다른 실험이다.

---

## 4. 보상 설계 — 우리가 실제로 건드릴 곳

**위치**: `source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py` 의 `class RewardsCfg`

| 항목 | 가중치 | 뜻 |
|---|---|---|
| `track_lin_vel_xy_exp` | **+1.0** | 명령한 속도대로 감 — **가장 큰 상** |
| `track_ang_vel_z_exp` | **+0.5** | 명령한 회전대로 함 |
| `feet_air_time` | **+0.125** | 발을 적절히 공중에 띄움 (질질 끌기 방지) |
| `lin_vel_z_l2` | **−2.0** | 위아래로 튐 — **가장 큰 벌** |
| `undesired_contacts` | **−1.0** | 발 아닌 부위가 땅에 닿음 (무릎·몸통) |
| `ang_vel_xy_l2` | −0.05 | 좌우로 기우뚱 |
| `action_rate_l2` | −0.01 | 명령이 급변 (덜덜 떨기 방지) |
| `dof_torques_l2` | −1.0e-5 | 관절 힘 소모 |
| `dof_acc_l2` | −2.5e-7 | 관절 가속 |
| `flat_orientation_l2` / `dof_pos_limits` | 0.0 | 험지에선 꺼둠 |

**출처**: NVIDIA Isaac Lab 기본값. 계보는 Rudin et al. 2021 legged_gym.

> ⚠️ **한 번에 하나씩만 바꿀 것.** NVIDIA 본인들도 평지→험지 전환에 **7곳을 연동 변경**했고
> 그중 `feet_air_time`은 **0.01 → 0.25로 25배** 바뀌었다. 여러 개를 동시에 바꾸면 무엇 때문인지 알 수 없다.

**"Mean reward"의 정의** (rsl_rl 소스 확인): 에피소드 하나가 끝날 때 그동안 받은 보상을 **전부 더한 값(총점)**을 기록하고, **최근 100개 에피소드 총점의 평균**을 표시한다. 스텝당 평균이 아니다.

---

## 5. 멀티 GPU — 미측정

- **RTX 50 시리즈에는 NVLink가 없다.** 실측 확인: Isaac Sim 기동 로그에 `CUDA peer access: Not supported`
- → **VRAM 16+16=32GB로 합쳐지지 않는다.** 각 GPU는 여전히 16GB
- **다만 DDP(분산 데이터 병렬)는 가능하다** — `train.py`에 `--distributed` 플래그 실재(`:31`)
- **아직 측정하지 않았다.** 다음 측정 대상

**구조적으로 유리할 것으로 보이는 이유(추론, 미검증)**: 교환할 것은 gradient뿐인데 학습이 0.14초, 시뮬이 4초다. **통신할 게 적고 계산할 게 많은 구조**는 DDP가 잘 먹히는 조건이다. 다만 **실측 전까지는 추론이다.**

---

## 6. 미확인 / 다음 측정

| 항목 | 상태 |
|---|---|
| 300 iteration 시드 고정 A/B | **진행 중** |
| 플래그가 물리를 바꾸는가 | **미결** — 위 결과로 판정 |
| GPU 2장 DDP 효과 | **미측정** |
| 1,500 iteration 완주 실측 | 미측정 (추정 A 104분 / B 46분) |
| GUI 모드 렌더 성능 (Path Tracing) | 미측정 |

## 변경 이력
- 2026-08-09 v1: 플래그 A/B 1차(30 iter) + 학습 진행 곡선(193 iter) 기록. 300 iter 재측정 진행 중.
