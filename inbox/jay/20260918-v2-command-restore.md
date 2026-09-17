# v2 설계 · 명령 능력 복원 · foothold-v1 학습 조건 전수 감사

> 분류: 계획
> 작성: 오흥재 · 2026-09-18 01:40
> 근거: 실측. 팀장 AI-WS01 기준선 `logs/rsl_rl/unitree_go2_rough/2026-08-11_20-32-58/params/env.yaml`(처음부터 1500 iter) 과 임석헌 원본 `0909_nvidia_gap_v3_seed42_iter900/params/env.yaml`(NAS 백업) 의 키 650 대 674 전수 대조 · `models/foothold-v1.env.yaml`(학습 시각 직렬화본)
> 요지: foothold-v1 은 석헌 gap 레시피를 정확히 재현한 것이고 레시피 자체가 전진 전용이었다. 명령 손잡이 4개만 되돌린 D 한 판(97분)이 「명령을 좁힐 필요가 있었는가」에 답한다.
> 상태: 확정
> 판: v1.0
> 이슈: #428 #409 #392

---

## 0. 목표 · 이 문서를 받는 모든 세션이 먼저 읽는다

**이 절을 읽지 않고 작업에 들어가지 않는다.** 이번 일은 목표를 안 적어서 생긴 사고다. 같은 실수를 두 번 하지 않는다.

### 0-1. 최종 목표

> **FOOTHOLD 는 Unitree Go2 를 실제 험지에서 자율 보행시킨다.**

그러려면 정책이 **둘 다** 해야 한다.

1. **험지를 통과한다** (gap · pit · rails · stepping_stones · floating_ring 등)
2. **외부 명령에 안전하게 반응한다** (멈춤 · 감속 · 회전 · 방향 전환)

**둘 중 하나만으로는 실기에 못 올린다.** 통과만 하고 못 멈추면 사람 앞에서 못 선다. 멈추기만 하고 못 넘으면 험지를 못 간다.

### 0-2. 이번 작업으로 **얻어야 할 것**

| # | 얻을 것 | 어떻게 확인하나 |
|---|---|---|
| **G1** | **정지 능력.** 속도 명령 0 을 받으면 무게중심을 지키며 멈추고, 멈춘 자세를 유지한다 | 정지 프로브 · NVIDIA 원본 대비 |
| **G2** | **저속 보행.** 0 초과 0.5 미만 구간에서 걷는다 | 명령 대 실속도 응답곡선 |
| **G3** | **회전 능력.** `ang_vel_z` 명령을 받으면 그만큼 돈다 | 회전 프로브 · 추종비 |
| **G4** | **재현 가능성.** 바꾼 값이 전부 기록으로 남는다 | `run_manifest.json` 출발 체크포인트 칸 |

**G1 ~ G3 은 NVIDIA Go2 rough 가 원래 갖고 있던 능력이다.** 새로 만드는 것이 아니라 **되찾는 것**이다.

### 0-3. 이번 작업으로 **절대 잃으면 안 되는 것**

| # | 잃지 말 것 | 기준값 (`models/foothold-v1.json`) |
|---|---|---|
| **K1** | **gap 통과** | 0.5 / 1.0 / 1.5 m/s 에서 **90 / 100 / 68 %** |
| **K2** | **pit · floating_ring · discrete_obstacles · wave · star · repeated_boxes · repeated_cylinders** | 대부분 100 %, floating_ring 95 / 99 / 87 % |
| **K3** | **rails** | 70 / 48 / 21 % (이미 낮다. 더 떨어뜨리지 않는다) |
| **K4** | **기존 험지 6종(rough6)** | 99 ~ 100 % |
| **K5** | **gap 폭 곡선** | 1.0 m/s 에서 폭 1.0 m 까지 100 % |

> **K1 ~ K5 중 하나라도 유의하게 떨어지면 그 판은 채택하지 않는다.** gap 을 되돌리면서 정지를 얻는 것은 손해다.

### 0-4. 이번 작업에서 **건드리지 않는 것**

| 건드리지 않음 | 이유 |
|---|---|
| 보상 11항 전부 | 석헌도 안 건드렸다. 손잡이를 늘리면 원인을 못 가린다 |
| `reset_base.pose_range` | **틈을 만나는 표본을 지키는 장치다** (3-2 절) |
| `max_init_terrain_level` 2 | 학습 가능성을 지키는 장치다. 하네스 성적의 근거이기도 하다 |
| `forward_gap` 비율 0.1 · 폭 0.15~0.40 | B 와 같아야 비교가 된다 |
| `height_scan_with_gap` · `fell_below_terrain` | gap 학습에 필수 |
| 물리 · PhysX · 액추에이터 · seed 42 · 4096 envs · 1501 iter | 같아야 비교가 된다 |

**한 번에 하나씩 본다. 이것이 이번 사고의 교훈이다.**

---

## 1. 무슨 일이 있었나

### 1-1. 사실

**foothold-v1 은 임석헌의 gap 레시피를 정확히 재현한 것이다.** 팀장 재현에 오류가 없었다. 틈 폭 한 줄(0.05~0.20 → 0.15~0.40)만 넓힌 것이 B 이고 그것이 배포본이다.

**그 레시피는 NVIDIA Go2 rough 에서 17개 값을 바꾸고 2블록을 더한 것이다.** 그중 **9개가 「전진 전용」 제약**이다.

**그 사실이 배포 시점에 아무 문서에도 없었다.** 팀장은 「gap 지형 0.1 추가 + `height_scan_with_gap` 관측」만 바뀐 것으로 알고 배포했다.

### 1-2. 왜 안 보였나

**평가 하네스가 0.5 / 1.0 / 1.5 m/s 직진만 잰다.** 학습 명령 범위가 (0.5, 1.5) 이므로 **학습 범위 안에서만 시험을 본 것**이다. 잃은 능력은 시험지에 없었다.

### 1-3. 어떻게 드러났나

인지 쪽에서 외부 제어로 감속·정지 명령을 넣었을 때 로봇이 그 자세 그대로 굳고, 일정 시간 뒤 무게중심이 무너졌다.

---

## 2. 전수 대조표 `확인됨`

**기준선**: 팀장이 2026-08-11 AI-WS01 에서 직접 돌린 처음부터 학습본 (`resume: false` · 1500 iter · seed 42)
**대상**: 임석헌 `0909_nvidia_gap_v3_seed42_iter900` (NAS 백업)
**방법**: YAML 키 단위 전수 비교 (650 대 674). 기준선에만 있고 석헌에 없는 항목 **0개**

### 2-1. 값이 다른 17개

| 묶음 | 항목 | 팀장 기준선 | 석헌 = foothold-v1 |
|---|---|---|---|
| **명령 6** | `lin_vel_x` | (-1.0, 1.0) | **(0.5, 1.5)** |
| | `lin_vel_y` | (-1.0, 1.0) | **(0.0, 0.0)** |
| | `ang_vel_z` | (-1.0, 1.0) | **(0.0, 0.0)** |
| | `heading_command` | True | **False** |
| | `rel_heading_envs` | 1.0 | **0.0** |
| | `rel_standing_envs` | 0.02 | **0.0** |
| **리셋 3** | `pose_range.yaw` | (-3.14, 3.14) | **(-0.05, 0.05)** |
| | `pose_range.x` | (-0.5, 0.5) | **(-0.1, 0.1)** |
| | `pose_range.y` | (-0.5, 0.5) | **(-0.2, 0.2)** |
| **관측 1** | `height_scan.func` | `height_scan` | **`height_scan_with_gap`** |
| **커리큘럼 1** | `max_init_terrain_level` | 5 | **2** |
| **지형 비율 6** | `pyramid_stairs` 외 3종 | 0.2 | **0.18** |
| | `hf_pyramid_slope` 외 1종 | 0.1 | **0.09** |

### 2-2. 새로 더한 2블록

- **`forward_gap`** · proportion 0.1 · `gap_width_range` (0.05, 0.2) · `gap_center_ratio` 0.5 · `approach_distance` 1.5 · `slab_thickness` 1.0 · `minimum_spawn_x` 0.75
- **`fell_below_terrain`** 종료항 · `minimum_relative_height` -3.0

### 2-3. 안 바뀐 것

**보상 11항 전부 · 물리 · PhysX · 액추에이터 · `episode_length_s` 20 · `num_envs` 4096 · `seed` 42 · `decimation` 4.**

### 2-4. 임석헌 계보 `확인됨`

| 런 | iter | 출발 |
|---|---|---|
| (100 iter 판) | 100 | NVIDIA Go2 rough |
| `0908_nvidia_gap_v2_seed42_iter500` | 500 | 위 |
| **`0909_nvidia_gap_v3_seed42_iter900`** | 900 | `0908_v2/model_499.pt` |
| `0911_nvidia_gap_v4_gap30_sedd42_add1500` | 1500 | `0909_v3/model_899.pt` |
| `0914_rails` | 1500 | **`foothold-v1.pt`** |
| `0914_rough7_control` | 1500 | **`foothold-v1.pt`** |

**누적 100 → 500 → 900 = 1,500 계보이고 최초 출발은 NVIDIA Go2 rough 다.** 우리 A · B 는 NVIDIA 에서 각각 1501 iter 단판이라 출발 구조가 다르다.

---

## 3. 진단

### 3-1. 설계 자체는 목적에 맞았다

`forward_gap` 은 **+x 단방향 지형**이다. 슬래브 앞에 틈이 있고(`approach_distance` 1.5 · `minimum_spawn_x` 0.75) **로봇이 앞으로 걸어가야만 틈을 만난다.**

| 안 좁혔으면 | 무슨 일이 |
|---|---|
| `reset yaw` ±3.14 | 로봇 절반이 틈을 등지고 스폰. 표본 버려짐 |
| `ang_vel_z` ±1.0 | 돌다가 틈을 비껴감 |
| `lin_vel_y` ±1.0 | 옆으로 새서 틈을 안 만남 |
| `lin_vel_x` 하한 0.5 | 저속으로는 틈을 건널 관성이 안 나옴 |
| `rel_standing_envs` 0.02 | 서 있는 로봇은 틈을 영영 못 만남 |
| `max_init_terrain_level` 5 | 처음부터 어려운 틈을 주면 학습이 안 됨 |

**9개 제약 전부가 「틈을 만나는 표본을 최대화한다」는 하나의 목적에 정렬돼 있다.** 900 iter 만에 gap 을 뚫은 것이 그 효과다.

### 3-2. 잘못은 설계가 아니라 다룬 방식이다

1. **기술 습득용 특화 산출물을 범용 vN 으로 배포했다**
2. **그 대가를 아무도 기록하지 않았다**

### 3-3. 손잡이를 기능별로 나누면

| 손잡이 | 무엇을 위한 것 | 되돌리면 얻는 것 | 되돌리면 잃을 위험 |
|---|---|---|---|
| ① `reset pose_range` | 틈을 **만나게** 함 (표본) | 임의 방향 시작 적응 | **gap 표본 급감** |
| ② `lin_vel_x` 하한 | 건널 **관성** | 저속 · 정지 | 도약력 |
| ③ `ang_vel_z` · `heading` · `standing` | 옆으로 **안 새게** | 회전 · 정지 | 표본 효율 |
| ④ `max_init_terrain_level` | 학습 **가능**하게 | 고난도 노출 | 초기 학습 불안정 |

> **①과 ④는 「틈을 만나는 것」이고 ②③은 「어떻게 걷는가」다. 목적이 다르다.**
>
> 그래서 **①④는 유지하고 ②③만 되돌린다.** 로봇은 여전히 틈을 향해 서지만 멈추고 돌 줄 알게 된다.

---

## 4. D 설계

**foothold-v1 학습 설정을 그대로 복사하고 명령 손잡이 4개만 되돌린다.**

### 4-1. 바꾸는 것 (4개)

| 항목 | B (배포본) | **D** |
|---|---|---|
| `commands.base_velocity.ranges.lin_vel_x` | (0.5, 1.5) | **(0.0, 1.5)** |
| `commands.base_velocity.ranges.ang_vel_z` | (0.0, 0.0) | **(-1.0, 1.0)** |
| `commands.base_velocity.heading_command` | False | **True** |
| `commands.base_velocity.rel_heading_envs` | 0.0 | **1.0** |
| `commands.base_velocity.rel_standing_envs` | 0.0 | **0.02** |

`heading_command` 와 `rel_heading_envs` 는 한 쌍이라 함께 움직인다. 손잡이 수로는 넷이다.

### 4-2. 유지하는 것 (B 와 완전 동일)

```
reset_base.pose_range        x ±0.1 · y ±0.2 · yaw ±0.05
max_init_terrain_level       2
forward_gap                  proportion 0.1 · width (0.15, 0.40)
height_scan_with_gap         offset 0.5 · miss_value 1.0
fell_below_terrain           -3.0
lin_vel_y                    (0.0, 0.0)
보상 11항                     전부 그대로
seed 42 · num_envs 4096 · max_iterations 1501 · episode_length_s 20
출발 체크포인트                NVIDIA Isaac-Velocity-Rough-Unitree-Go2-v0 (iter=0 으로 되감은 사본)
```

### 4-3. `lin_vel_y` 를 왜 0 으로 두나

Go2 에 횡보행 수요가 낮고, 손잡이를 하나 더 열면 원인 분리가 흐려진다. **필요해지면 다음 판에서 연다.**

### 4-4. 구현

`gap_wide_env_cfg.py` 와 같은 방식으로 **새 파일 하나**를 만든다. `gap_env_cfg.py` 와 `gap_wide_env_cfg.py` 를 **고치지 않는다.** A · B 를 다시 재현할 수 있어야 한다.

새 클래스는 `UnitreeGo2GapWideEnvCfg` 를 상속하고 `__post_init__` 에서 위 다섯 줄만 덮는다. 그리고 **덮였는지 검사해서 안 덮였으면 즉시 예외를 던진다**(`gap_wide_env_cfg.py` 의 조용한 실패 방지 패턴을 그대로 따른다).

---

## 5. 판정 기준 (돌리기 전에 확정한다)

**두 축의 AND 다. 하나라도 못 넘으면 채택하지 않는다.**

### 5-1. 축 1 · 회귀 방지 (0-3 절 K1 ~ K5)

기존 하네스 `sim/eval/eval_generalization.py` 규격 2 · difficulty 0.5 · 지형마다 100 에피소드 · 0.5 / 1.0 / 1.5 m/s.

**`models/foothold-v1.json` 의 점수표가 정답지다.** Wilson 신뢰구간을 함께 본다.

### 5-2. 축 2 · 신규 획득 (0-2 절 G1 ~ G3)

**기준선이 필요하다. v1 은 이 축에서 구조적으로 0 점이라 기준이 될 수 없다.**

| 비교 대상 | 역할 |
|---|---|
| **NVIDIA Go2 rough 원본** | **목표선.** 원래 되던 수준 |
| foothold-v1 | 현재선. 얼마나 잃었나 |
| **D** | 되찾았나 |

**세 정책의 구조가 같다**(actor 235 → 512 → 256 → 128 → 12 · ELU · RNN 없음). 같은 프로브에 그대로 들어간다.

### 5-3. 프로브가 재는 것

| 재는 것 | 왜 |
|---|---|
| 명령 0 도달 시각 · 마지막 1초 잔류속도 | G1 정지와 **정지 유지** |
| 관절 목표각의 시간 변화량 | 정책 출력이 **상수로 굳는가**. 「얼음」의 정체 |
| 몸통 피치 · 롤 최대 · 낙상 여부 | 무게중심 유지 |
| 명령 대 실속도 응답곡선 (0 ~ 1.5 를 훑음) | G2 저속. **분포 경계가 어디서 갈라지나** |
| `ang_vel_z` 추종비 | G3 회전 |
| 발 미끄러짐 · 네 발 동시 접지 지속시간 | 멈춘 방식의 질 |

---

## 6. 실행 순서

| # | 무엇 | 선행 | 비용 |
|---|---|---|---|
| 1 | 프로브 도구 제작 (`sim/eval` 에 **새 파일**. 판정 코드 불간섭) | | 반나절 |
| 2 | **NVIDIA 원본**과 **foothold-v1** 을 프로브로 측정 → 기준선 확보 | 1 | 학습 없음 |
| 3 | D 환경 설정 파일 작성 + 자기검사 | | |
| 4 | **D 학습** | 3 | **약 97분** |
| 5 | D 를 하네스(축 1) + 프로브(축 2) 로 평가 | 2 · 4 | |
| 6 | 판정 | 5 | |

**2번이 4번보다 먼저다.** 기준선 없이 학습부터 돌리면 결과를 해석할 수 없다.

---

## 7. D 가 기대와 다르면

| 증상 | 해석 | 다음 |
|---|---|---|
| K 유지 + G 획득 | **명령을 좁힐 필요가 없었다** | **v1 을 D 로 교체 배포.** 끝 |
| K 하락 + G 획득 | 명령 좁히기가 gap 에 기여했다 | iter 2000~3000 또는 `forward_gap` 비율 상향. **명령을 되돌리지 않는다** |
| K 유지 + G 미획득 | 원인이 명령이 아니다 | 보상 설계를 본다 (발 높이 항 부재 등) |
| 둘 다 실패 | 리셋까지 봐야 한다 | ① 손잡이를 여는 E 판 |

---

## 8. 함께 고칠 문서 (D 학습이 도는 97분 안에 끝난다)

| # | 무엇 | 어디 |
|---|---|---|
| 1 | 학습 조건표에 **17항목 + 2블록 전부** | 종합보고서 |
| 2 | 성능표에 **「0.5 ~ 1.5 m/s 직진 조건에서 측정」** 명시 | 종합보고서 |
| 3 | **한계 절 신설**: 「전진 전용으로 학습되어 정지 · 저속 · 회전 · 횡이동은 평가되지 않았다」 | 종합보고서 |
| 4 | 석헌 계보(2-4 절) + 명령 조건 17항목 기록 | 이슈 #428 |
| 5 | `run_manifest.json` 에 **출발 체크포인트 칸** 신설 | `sim/eval` |

---

## 9. 재발 방지

**이번 사고의 원인은 「바꾼 것을 안 적었다」 하나다.** 셋을 건다.

| 관문 | 무엇 |
|---|---|
| **학습 전** | 기준선 `env.yaml` 과 **전수 diff** 를 떠서 바뀐 항목을 전부 이슈에 적는다. 항목 수가 예상과 다르면 학습을 시작하지 않는다 |
| **배포 전** | 평가가 **학습 명령 범위 밖**을 최소 한 점 포함하는지 확인한다. 범위 안에서만 재면 잃은 능력이 안 보인다 |
| **배포 시** | 모델 카드(`models/*.json`)에 **「학습한 명령 범위」** 칸을 둔다 |

---

## 부록 A · 근거 경로

```
팀장 기준선 (처음부터 1500 iter)
  C:\isaac\IsaacLab\logs\rsl_rl\unitree_go2_rough\2026-08-11_20-32-58\params\env.yaml
  같은 폴더 agent.yaml: resume false · max_iterations 1500 · seed 42

배포본 학습 시각 직렬화본
  models/foothold-v1.env.yaml  (log_dir 에 rsl_rl 학습 경로 · num_envs 4096)
  models/foothold-v1.agent.yaml  (resume true · load_run nvidia_pretrained_source)
  models/foothold-v1.json  (점수표 · 계보 · 시간)

임석헌 원본 (NAS 백업 · RunPod Network Storage 사본)
  ssh -i ~/.ssh/ai-nas01-backup-admin-20260912 VFXPEDIA@100.80.160.84
  /volume1/foothold/runpod-backup/_system/published-views/<스냅샷>/data/limseokheon/
    isaaclab/logs/rsl_rl/unitree_go2_gap_nvidia/
      0909_nvidia_gap_v3_seed42_iter900/params/{env,agent}.yaml
      0911_nvidia_gap_v4_gap30_sedd42_add1500/   (#392 gap 30cm)
      0914_rails/                                 (#409 rails)
      0914_rough7_control/                        (대조군)

NVIDIA 소스
  C:\isaac\IsaacLab\source\isaaclab_tasks\isaaclab_tasks\manager_based\locomotion\velocity\
    velocity_env_cfg.py                    상류 기본
    config\go2\rough_env_cfg.py            Go2 공식
    config\go2\gap_training\gap_env_cfg.py         A
    config\go2\gap_training\gap_wide_env_cfg.py    B
```

**스냅샷 이름은 회전한다.** 경로가 없으면 `find /volume1/foothold/runpod-backup -path '*limseokheon*' -name env.yaml` 로 현재 것을 찾는다.

## 부록 B · 근거 사용 규칙

**팀장이 확인 · 테스트했거나 지시한 자료만 근거로 쓴다.** 다른 팀원의 실행 기록을 임의로 끌어와 기준선으로 삼지 않는다. 필요하면 먼저 묻는다.

---

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-09-18 | 처음 씀. 팀장 기준선과 석헌 원본의 키 전수 대조로 17항목 + 2블록을 확정하고, 손잡이를 기능별로 나눠 ②③만 되돌리는 D 를 설계했다. 목표(G1~G4)와 잃지 말 것(K1~K5)을 0절에 명시했다 | 전수 대조 실측 |
