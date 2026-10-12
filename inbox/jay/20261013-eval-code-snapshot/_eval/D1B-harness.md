> 분류: A/정책학습 · 평가 하네스 · D1-B 준비 검사
> 작성: 오흥재 (lead 세션 하위 작업 · Claude 실행) · 2026-10-11
> 근거: `inbox/jay/20261008-546-design/VERIFY-astra-5.md` 1절 · 2절 (1)~(6) · 코드 `go2_rl_robotlab` 28b4516 (추적 파일 수정 없음) · Isaac Lab 로컬 소스 (`observation_manager.py` 404~407 · `mesh_terrains.py` 559~598 · `terrain_generator.py` 272~292 · `manager_based_rl_env.py` 215~237 · `contact_sensor.py` 144~152) · 원자료 `_eval/out/d1b_final/` 외
> 요지: 하네스 여덟 항목 중 G0 실제 연결 · 오류 분류 · 동적 계약 · gap 기하 · 발 착지 계측은 시험을 통과했다. 접지 안정화는 「조건마다 별도 프로세스」 방식에서만 hash 가 일치하고 1 s PD 로는 정지 상태가 되지 않는다. 무접촉 추락 규칙은 합성 10 개와 낙하 · 보행 · 도약 · reset 경계에서 오탐 · 누락 0 이지만, 다리가 틈에 빠진 채 걸린 상태를 잡지 못한다. 본 평가는 돌리지 않았다
> 상태: 판 1 · D1-B 본 평가 0 회 · holdout 정책 실행 0 회 · 계약 값은 ASTRA 제안 그대로 매개변수로만 사용 · 저장소 원본 수정 없음 · 커밋 없음

# D1-B 하네스와 시험 (본 평가 아님)

## 0. 한눈에

| 항목 | 판정 | 핵심 수치 | 상태 |
|---|---|---|---|
| 1 G0 실제 연결 | 통과 | 평지 최종 −0.30 (차 4.8e-6), 이중 처리 없음 · no-hit legacy −2.5 / G0 +2.5 · finite 칸 bitwise 동일 · 다른 block bitwise 동일 · teacher mean 경로 차 0 | 확인됨 |
| 2 오류 분류 | 통과 | 다섯 종류를 따로 셈 · 주입 4 종 각 75/75 표시, 정상 env 오표시 0 · 표시가 나오면 rollout 정지 (합성 표시로 확인) | 확인됨 (실 rollout 중 실제 오류 발생은 0 건이라 실발생 정지는 미확인) |
| 3 동적 계약 | 통과 | 1200 env × 300 step: no-hit 불일치 0 / 4,375,497 · 관측 block 과 「현재」 자세 기대값 차 9.7e-6 (직전 자세와는 4.25) · 강제 auto-reset 120 env 도 stale 없음 | 확인됨 |
| 4 gap 기하 · manifest | 통과 | 틈 위 CPU 레이 17,340 개 위아래 모두 hit 0 · 지면 외 collider 는 지형 mesh 하나 · USD mesh = 생성기 재생성 · holdout 생성 · 검사 후 봉인 (정책 0 회) | 확인됨 |
| 5 접지 안정화 · 복원 | 부분 | 별도 프로세스끼리 settled · 복원 · 첫 관측 hash 동일, 같은 조건 50 step 재생 bitwise 동일 · 한 프로세스 안 재복원은 contact 보고가 남아 재생이 1 step 째부터 갈라짐 · 1 s 뒤에도 몸통 속도 중앙값 0.12 m/s | 확인됨 (계약 확정 필요) |
| 6 무접촉 추락 | 부분 | 합성 10 개 통과 · 시뮬 smoke 보행 266 · 낙하 266 · 평지 도약 133 · reset 경계 136 오탐 · 누락 0 · 감지 0.40 s = 해석값 0.40 s · 「다리가 틈에 빠져 걸림」 은 규칙 밖 | 확인됨 (걸림 처리 계약 확정 필요) |
| 7 발 착지 계측 | 통과 | USD collider 구 반지름 0.022 m · 답을 아는 배치 6 종 위험 판정 300/300 일치, 여유 오차 ≤ 0.76 mm · 평지 보행 지지면 착지만, gap 에서 벽 · 틈 접촉 분리 | 확인됨 (contact point 미사용 근사) |
| 8 stepping stones | 손대지 않음 | | |

GPU 1 만 썼다. 이번 작업의 GPU 1 실행은 합계 약 11 분 (19 회, 회당 약 15~80 s)이다. 기록한 시점의 최대 사용은 9.6 GB (여유 6.6 GB) 였다. GPU 0 (E2 pid 173044) 와 pid 25916 은 건드리지 않았고 끝난 뒤에도 살아 있다.

## 1. 만든 것 (저장소 밖 `_eval/`)

| 파일 | 내용 |
|---|---|
| `d1b_lib.py` | Isaac 없이 도는 함수: G0 raw 대입 · 오류 mask · 무접촉 추락 · touchdown/liftoff · 지지면 여유 · 위험 판정 · slip · 방향 · 셀 좌표 · DR manifest · 결과 판정 (`gap_outcome`) |
| `test_d1b_lib.py` | 답을 아는 시험 60 개 (ASTRA 합성 궤적 10 개 포함). 결과 `out/d1b_cpu_tests.json` |
| `d1b_harness.py` | Isaac 하네스. 단계 geom · g0 · settle · dyn · fall · foot · halttest · main (main 은 이번에 1 s 경로 시험만) |
| `run_d1b_harness.sh` | 실행 선언 머리 · GPU 1 여유 관문 (여유 − 5.6 GB ≥ 4 GB) |
| `run_d1b_main.sh` · `d1b_pair_check.py` | 본 평가 실행기 (팀장 확정 표시 없으면 거부, 시험함) · 조건 간 짝 검사 |

관문을 깨뜨려 봤다. `d1b_lib.py` 를 열 가지로 망가뜨린 사본 (`_mut/d1b/`) 에서 시험이 10/10 모두 실패했다 (`out/d1b_mutation.json`). 짝 검사도 첫 관측 hash 하나를 바꾼 사본에서 실패를 냈다.

## 2. 항목별 결과

### 2.1 G0 실제 연결 (통과 · 확인됨)

critic 의 `height_scan` 함수를 평가 스크립트 안에서만 `height_scan_switch` 로 바꿔 끼웠다. legacy env 는 Isaac Lab 식 그대로 (`sensor_z − hit_z − 0.5`), G0 env 는 raw 단계에서 비유한 값을 +1 로 바꾼다. clip(−1, 1) 과 scale 2.5 는 manager 가 한 번만 한다. 실제 ObservationManager 최종 block 에서 잰 값이다 (`out/d1b_final/g0.json`).

| 검사 | 결과 |
|---|---|
| 평지 base 0.38 m | legacy · G0 모두 −0.30 (최대 차 4.8e-6). 두 번 처리했을 때의 −0.75 가 아님 |
| 0.10 m 단차 경계 | −0.30 과 −0.05 두 값, G0 − legacy = 0 |
| gap030 위 no-hit 13,550 레이 | legacy −2.5 · G0 +2.5 |
| 오류 없는 env 의 finite 칸 | G0 와 legacy bitwise 동일 |
| legacy 경로 vs Isaac Lab 원 함수 | bitwise 동일 |
| height 밖 critic · policy · single_obs | bitwise 동일 |
| teacher mean 수식 vs 모듈 `act(is_teacher=True)` 평균 (G0 입력) | 차 0 |
| teacher 행동 G0 − legacy | gap env 최대 5.37 · 평지 env 0 |
| student 행동 G0 − legacy | 0 |
| permutation 2026 (인코딩 뒤 block 에 한 번, slice 는 term 이름으로 88~275 확인) | gap env 최대 행동 차 2.11 |

### 2.2 오류 분류 (통과 · 실발생 정지는 미확인)

`base/sensor pose invalid` · `hit NaN` · `hit −inf` · `정상 +inf no-hit` · `finite 입력 overflow` 를 따로 센다. 앞의 넷은 오류이고 no-hit 은 오류가 아니다. CPU 시험 외에 실제 sensor 버퍼에 주입했다.

| 주입 (각 75 env) | 해당 mask | 오류 표시 | G0 최종값 | legacy 최종값 |
|---|---:|---:|---|---|
| hit NaN | 75 | 75 | +2.5 | NaN |
| hit −inf | 75 | 75 | +2.5 | +2.5 |
| sensor z NaN | 75 | 75 | +2.5 | NaN |
| finite overflow (3e38 − (−3e38)) | 75 | 75 | +2.5 | +2.5 |

주입하지 않은 900 env 의 오표시는 0 이다. G0 대입은 NaN 전파만 막는다. 표시된 episode 는 rollout 을 멈추고 env 와 표본 번호를 남긴다. 합성 표시 (env 3, 표본 2) 로 정지 경로를 확인했다 (`out/d1b_halt/halttest.json`). 이번 rollout 전부 (dyn · fall · foot · 경로 시험) 에서 실제 오류와 비유한 기체 상태는 0 건이었다. 그래서 「실제로 생긴 오류에서 멈춤」 은 미확인이다.

### 2.3 동적 계약 (통과 · 확인됨)

검증 12 셀의 복원 시작점에서 teacher 로 300 step 돌렸다. 네 조건을 env 마다 나눠 섞었다. 각 셀 10 env 는 제자리 yaw 회전 (wz 0.5) 으로, 10 env 는 150 step 째 time-out 으로 auto-reset 되게 했다. 매 step 현재 root 자세와 해석 기하로 기대값을 계산해 비교했다 (`out/d1b_final/dyn.json`).

| 검사 | 결과 |
|---|---|
| sensor 위치 − root 위치 | 1.9e-6 (|y| ≈ 22 m 에서 float32 한 칸) |
| 레이 xy − 현재 자세 기대값 | 3.8e-6 |
| no-hit mask − 해석 틈 | 불일치 0 (no-hit 4,375,497 개, lip ±1 mm 128,834 개는 제외) |
| 관측 block − 현재 자세 기대값 | 9.7e-6 |
| 관측 block − 직전 step 자세 기대값 | 4.25 (stale 이면 이쪽이 0 이 된다) |
| 강제 auto-reset 직후 120 env | block 차 9.7e-6 · no-hit 불일치 0 · reset 표시 123 (자연 종료 3 포함) |
| 187 순서 | x 가 빠른 17 × 11 격자와 정확히 같음, 모든 env 같음 |

한 가지는 stale 이다. reset 직후 첫 표본의 contact sensor 값은 reset 전 마지막 PhysX contact 보고다 (`contact_sensor.py` 144~152 는 버퍼를 0 으로 두지만 다음 읽기에서 마지막 보고를 다시 가져온다). 이 때문에 앞 단계의 접촉이 새 episode 의 첫 표본에 base contact 로 나타나 오탐 1 건이 났다. 고친 규칙: 접촉 기반 판정 (base contact · touchdown) 의 표본 0 은 표본 1 값으로 둔다. 고친 뒤 오탐은 0 이다. critic 의 첫 contact_force 관측도 같은 값을 받는데, 본 평가 방식 (2.5) 에서는 모든 조건이 같은 settle 의 마지막 보고를 받는다.

### 2.4 gap 기하 · 시작 · manifest (통과 · 확인됨)

9 × 9 m tile · 중앙 3 × 3 m platform · `gap_width_range=(w, w)` 로 0.10 / 0.20 / 0.30 고정 · difficulty 0.5 기록 · 평지 대조는 plane tile. 본 평가 배치 (검증 4 열) 와 하네스 배치 (smoke 전용 2 열 추가) 를 둘 다 검사했다 (`out/d1b_final/geom.json`, `out/d1b_geom_main/geom.json`).

| 검사 | 결과 |
|---|---|
| 지형 외 collider | `/World/ground/terrain/mesh` 하나 (다른 plane 없음) |
| USD mesh vs 같은 설정 생성기 재생성 | 정규화 hash 동일 (두 배치 모두) |
| 틈 위 CPU 레이 (네 변 · 모서리, 폭 안쪽 9 줄) | 0.10: 5,600 · 0.20: 5,780 · 0.30: 5,960 개, 위에서 아래로 hit 0, z −50 m 에서 위로 hit 0 |
| bank · tile 테두리 1,080 점 | 전부 z = 0 에서 hit |
| GPU ray caster, 무작위 자세 1,346,400 레이 | no-hit 과 해석 틈 불일치 0 |
| tile 안 머무름 | goal 뒤 0.5 s 와 scanner footprint 의 가장 앞 x 3.67 m < 4.5 m |

시작 · goal · 방향 (제안 값): 시작 base xy = (a − 0.80 + δ, 0), δ 는 episode manifest · goal x = a + w + 0.80 · 방향 α 에서 yaw = −α, body 명령 0.30 (cos α, sin α, 0). 다섯 방향 모두 world 속도 (+0.30, 0) 을 CPU 로 확인했다.

DR manifest: 검증 시드 12000 · episode 1000~1099, holdout 시드 22000 · 2000~2099. 학습 EventCfg 와 같은 범위 (base 질량 ±1 kg, 나머지 ×0.9~1.1, base COM ±0.03 m, 재질 64 bucket, gain ×0.9~1.1, motor offset ±0.035, delay 0~4) 를 episode 번호로 정한 값으로 만들고 DR event 를 끈 뒤 직접 넣었다. 읽어 낸 COM · 재질은 manifest 와 bitwise 같고, 질량 · 관성은 float32 반올림 차 (4.8e-7 · 3e-8) 다. gain · offset · delay 는 reset 마다 다시 넣고 차 0 (offset 6e-8) 이다.

holdout (platform 2.5 · 폭 0.15 / 0.25 · −45 / −90 도) 은 생성기로 mesh 를 만들고 틈 4,788 / 4,968 점에서 hit 0 을 확인한 뒤 봉인했다 (`manifest_holdout_SEALED.json`, 정책 실행 0 회). local 좌표 비교:

- holdout gap tile 은 어느 검증 tile 과도 같지 않다.
- 시드만 22000 으로 바꾼 검증 설정은 tile 이 완전히 같다. ASTRA 가 말한 「시드만 바꾸면 같은 기하」 가 실제로 그렇다.
- holdout 평지 대조 tile 은 검증 평지와 같은 plane 이다. 다른 것은 시작 0.45 m · goal · 방향뿐이다.
- 셀 (platform, 폭, 방향) 겹침 0, 시작 δ 겹침 0.

### 2.5 접지 안정화와 복원 (부분 · 계약 확정 필요)

절차: 시작 자세에서 가장 낮은 발 구 바닥을 상면 위 2 mm 에 두고, action 0 목표 (기본 자세 + 그 episode 의 motor offset) 로 1 s PD hold (200 physics step). 저장한 뒤 env.reset 안의 restore event 로 root · joint 상태 · PD 목표 · reset 형 DR 을 쓴다.

| 검사 | 결과 |
|---|---|
| 서로 다른 프로세스 4 개 (같은 조건 둘, 다른 조건 둘) | settled hash 같음 · 복원 PhysX 읽기 hash 같음 |
| 첫 관측 | policy · single_obs bitwise 같음, critic 은 height block 만 다름 (조건별 인코딩), 나머지 bitwise 같음 |
| 같은 조건을 다른 프로세스에서 50 step | 궤적 bitwise 같음 |
| 저장값 vs 복원 읽기 | joint 상태 차 0 · root 위치 1.9e-6 (float32 한 칸, PhysX 왕복) |
| 한 프로세스 안에서 rollout 뒤 다시 복원 | 상태 hash 는 같지만 첫 critic 의 contact_force 가 0.075 다르고, 재생이 1 step 째부터 갈라짐 (50 step 에 0.43) |

그래서 조건 전환은 프로세스 단위로만 한다. 본 평가 실행기는 이 방식이고, 경로 시험 (24 env × 50 step, 세 조건) 에서 짝 검사가 통과했다 (`out/d1b_dry/pair_check.json`). 한 프로세스 안 재복원은 짝 맞춤에 쓰지 않는다.

1 s PD hold 는 정지 상태가 아니다. Go2 자체 gain (Kp 25 · Kd 0.5) 에서 1 s 시점 몸통 속도 중앙값 0.12 m/s · 최소 0.06 · 최대 0.16, joint 속도 최대 0.84 rad/s 로 1200 env 모두 몸통 0.05 m/s 를 넘는다. 3 s 까지 늘리면 최대 0.07 m/s 다. 진단으로 settle 동안만 감쇠를 4 배로 하면 1 s 에 최대 0.037 m/s, 2 s 더 두면 0.002 m/s 다 (`out/d1b_kd4/settle.json`). 시작 상태는 결정적이고 조건 간에 같으므로 짝 맞춤은 지켜진다. 다만 「안정화된 접지 상태」 라고 부르려면 계약을 정해야 한다 (4 절).

### 2.6 무접촉 추락 판정 (부분)

규칙 (제안 값): z_ref = bank 상면 0 · (z < z_ref − 0.10 그리고 world vz < −0.20 이 0.10 s, 6 표본) · (z ≤ z_ref − 0.50 즉시) · 기존 base contact > 1 N 과 기울기 60 도 0.20 s (11 표본) 보존 · 처음 감지에서 latch · reset 전 상태 저장 · all_local_miss 는 따로 셈. 기체 NaN 은 하네스 오류.

CPU: ASTRA 합성 궤적 10 개가 모두 같은 결과를 냈다 (자유낙하 감지 0.42 s 등). 경계 (0.08 s 미감지 / 0.10 s 감지, z = −0.50 즉시) 와 기존 규칙 보존도 통과했다.

시뮬 smoke (`out/d1b_final/fall.json`). 정답은 실행 전에 정했다: 보행 · 낙하 · 평지 도약 · reset 경계는 구성으로 정한 답 (유효 조건을 따로 확인), 나머지는 끝 상태 (base z < 0.10 또는 기울기 > 60 도 또는 base contact 로 reset 이면 추락, z > 0.20 그리고 기울기 < 30 도면 정상, 사이는 판단 보류).

| 장면 (각 133~136 env) | 감지 맞음 | 누락 | 오탐 | 정상 맞음 | 판단 보류 | 비고 |
|---|---:|---:|---:|---:|---:|---|
| 평지 보행 (student) | | 0 | 0 | 133 | | |
| 평지 보행 (teacher G0) | | 0 | 0 | 133 | | |
| 0.60 m 시험 틈 가운데로 낙하 | 133 | 0 | 0 | | | 0.5 s 동안 접촉 0, 감지 0.40 s = 해석값 0.40 s, 레이 일부는 bank 를 맞힘 |
| 테두리 너머 낙하 | 133 | 0 | 0 | | | 감지 0.40 s |
| 평지 제자리 도약 (vz 1.0) | | 0 | 0 | 133 | | |
| 0.20 틈 너머 도약 | 51 | 0 | 0 | 15 | 67 | 감지는 전부 기울기 규칙 |
| reset 경계 (낙하 뒤 0.8 s 에 time-out reset) | 136 | 0 | 0 | | | latch 0.40 s 유지 · reset 표본에는 reset 전 z −2.81 m 기록 · reset 뒤 서 있는 상태는 이어 붙이지 않음 · 결과 fall |
| 0.30 틈 가운데 옆으로 놓기 | 4 | 3 | 0 | 119 | 7 | 누락 3 은 다리가 틈에 빠진 채 base 0.05~0.10 m · 기울기 36~50 도로 정지 |
| 0.30 틈에 앞발을 걸치기 | | | | 1 | 132 | base 0.15~0.25 m, 예시 env 는 앞발 z −0.12 · −0.16, 기울기 약 23 도로 걸림. 어떤 규칙도 안 걸림 |

정리하면 보행 · 무접촉 낙하 · 평지 도약 · reset 경계는 오탐 · 누락 0 이다. 「기울어 걸림」 은 0 이 아니다. 다리가 틈에 빠져 몸통이 lip 에 걸린 상태는 base 가 z_ref − 0.10 보다 위에 있고 수직 속도가 0 이라 제안 규칙에 걸리지 않는다. dyn rollout 에서도 같은 모양이 4 env (끝 상태 base < 0.10 m, 감지 없음) 나왔다. 발 구 중심이 bank 상면 5 cm 아래에 1 s 이상 있었는데 감지가 없던 env 는 116 / 1200 이다 (대부분 0.10 · 0.20 틈. 걸림만이 아니라 건너는 중의 일시적 빠짐도 포함). 이 값은 추락 규칙이 아니라 진단 칸 `feet_below_bank_1s` 로 따로 기록한다.

제안 판정 규칙에서 이런 episode 는 fall 이 아니라 timeout 이나 path 로 끝난다. 성공률에는 영향이 없고 실패 분류와 「touchdown 없이 추락」 수에 영향이 있다. 문턱을 실측에 맞춰 움직이지 않았다.

또 하나: 0.10~0.30 틈의 teacher rollout 에서 추락 감지 165 건 (dyn 전체) 은 전부 base contact (126) 나 기울기 (39) 가 먼저 잡았다. 새 sink · deep 규칙이 먼저 걸린 것은 0.60 시험 틈과 테두리 너머뿐이다. all_local_miss 는 0.10~0.30 틈에서 0 env 였다. 작은 scanner (0.4 × 0.3 m, 0.1 m 간격) 는 0.30 이하 틈 위에서 레이가 전부 빠지는 자리가 사실상 없다 (추정, 기하로 계산).

### 2.7 발 착지 계측 최소 범위 (통과 · 근사의 한계 있음)

USD 에서 읽은 foot collider: 네 발 모두 구 하나, 반지름 0.022 m, 발 frame 에서 (−0.002, 0, 0). 기록: 네 발 구 중심 world 위치 · 속도 · 수직 접촉력 · 표본 시각. touchdown = 연속 2 표본 수직력 > 1 N, 시각은 둘째 표본. liftoff = 연속 2 표본 ≤ 1 N. 표본 0 부터 이미 접촉이면 착지가 아니라 「처음 서 있음」 으로 따로 둔다. 분류: 구 바닥이 상면 ±1 cm 이고 중심이 platform 위면 inner, 바깥 bank 위면 outer, 틈 위거나 상면 아래면 벽 · 틈 접촉 (지지 착지 아님). 위험 = 지지 영역 외곽선까지 거리 − 반지름 < 0.02 m. 외곽선 거리는 모서리에서 Euclid 거리다. slip = 착지부터 liftoff 까지 수평 이동.

답을 아는 배치: 0.30 틈에서 뒷발을 바깥 bank, 앞발을 안쪽 platform 의 정한 여유에 두고 5 mm 위에서 PD hold 로 내려놓았다. 이 시험만 motor offset · delay 0, 마찰 1 인 중립 로봇을 썼다 (manifest 그대로 두면 착지 전에 발이 최대 39 mm 움직여 정답이 흐려진다).

| 배치 (발 두 개 × 150 env) | 기대 | 결과 |
|---|---|---|
| 바깥 0.08 · 0.045 | 안전 | 300/300 안전 |
| 바깥 0.03 · 0.015 | 위험 | 300/300 위험 |
| 안쪽 0.08 | 안전 | 300/300 안전 |
| 안쪽 0.03 | 위험 | 300/300 위험 |
| 바깥 −0.03 · 안쪽 −0.03 (구 중심이 틈 위) | 지지 착지 없음 | 300/300 착지 없이 틈으로 빠짐 |

계산한 여유와 설계 여유의 차는 최대 0.76 mm 다. 0.045 배치는 문턱에서 3 mm 떨어져 있는데 모두 안전으로 나왔다.

smoke (dyn, 6 s): 평지 건너기 셀은 발당 1.28~1.53 회/s 착지, 모두 지지면, 구 바닥 높이 −0.45~+0.07 mm, 위험 0. gap 셀은 벽 · 틈 접촉 5~77 건, 위험 착지 37~160 건이고, 셀마다 lip 에 가장 가까운 바깥 bank 착지는 lip 뒤 0.4~17 mm 다. 그럴듯하다.

한계: contact point · normal 을 쓰지 않고 구 중심 위치와 수직력으로 근사했다. 힘은 policy 표본 시각의 마지막 physics substep 값이다. lip 모서리에 구가 걸린 접촉은 중심이 틈 위면 벽 · 틈 접촉으로 분류된다.

### 2.8 stepping stones

손대지 않았다.

## 3. 시험하며 바꾼 것

- 처음 판에서는 한 프로세스 안 재복원으로 조건을 바꾸려 했다. joint_torque 가 직전 PD 목표로 다시 계산되어 0.17 이 달랐다. PD 목표 복원을 규칙에 넣어 고쳤다. 그 뒤에도 contact 보고 차가 남아 프로세스 단위로 바꿨다.
- 처음 판의 낙하 smoke 는 유효 조건에서 대부분 빠졌다. 원인은 2.3 의 stale contact 였다. 표본 0 규칙으로 고친 뒤 266/266 이 유효했다.
- 하네스 최종 판으로 전 단계를 다시 돌려 직전 판과 모든 결과 칸이 같음을 확인했다 (결정적).

## 4. 팀장 확정이 필요한 것 (계약)

이번 값은 모두 ASTRA 5 의 제안을 매개변수로 쓴 것이다. 승인된 계약으로 쓰지 않았다.

1. 조건마다 별도 프로세스, 시작 전 순서 동일 (env 생성 · manifest DR · settle · 복원 한 번). 짝은 hash 로 검사한다.
2. 접지 안정화: 제안대로 자체 gain 1 s (결정적이지만 0.12 m/s 로 움직이는 시작) · 더 길게 · settle 동안만 감쇠를 올리기 중 하나. 하네스는 `--settle_s` · `--settle_kd_scale` 로 어느 쪽이든 돈다.
3. 다리가 틈에 빠져 걸린 상태를 fall 로 셀지, timeout 으로 둘지. 세려면 규칙을 새로 정하고 판을 올려 양군 모두 다시 잰다.
4. 접촉 기반 판정의 표본 0 은 표본 1 값으로 둔다는 규칙.
5. holdout 평지 대조는 검증과 같은 plane 이고 시작 · goal · 방향만 다르다는 점.
6. 위험 착지 정의 (구 중심 근사, 2 cm) 와 「4 발 바깥 bank 착지」 판정에 구 중심 근사를 쓰는 것.

## 5. 본 평가를 바로 돌릴 수 있는가

돌릴 수 있다. 위 계약이 정해지면 `D1B_CONTRACT_CONFIRMED=<확정 근거> bash run_d1b_main.sh model_20000` (또는 model_20499) 하나로 다섯 조건 (teacher 네 조건 + student 대조) 을 프로세스마다 돌리고 짝 검사까지 한다. 확정 표시가 없으면 거부한다 (시험함). 결과 칸: 셀별 success 와 Wilson 구간 · fall / path / timeout · 위험 착지 / 지지 착지 · 지지 착지 없이 추락 · `feet_below_bank_1s` · Q1 MAE (첫 1 s 제외) · |y| 최대.

예상 GPU 시간 (추정): 이번 dyn 단계가 1200 env × 300 step 을 검사 포함 31 s 에 돌았고, Q-E1 teacher 1100 env × 1000 step 이 53~71 s 였다. 프로세스 하나 (1200 env × 1000 step, 시작 · settle · 후처리 포함) 를 약 2 분으로 보면 checkpoint 하나에 다섯 조건 약 10 분, E1 두 checkpoint 약 20 분이다. GPU 1 사용은 약 5 GB 를 더한다 (이번 기록 최대 9.6 GB). 500 episode 확대는 6000 env 가 여유 4 GB 관문을 넘으므로 셀을 나눠 돌려야 한다 (프로세스당 약 1,500 env 안팎, 추정).

## 6. 재현

```
cd C:/isaac/ext/go2_rl_robotlab/_eval
python test_d1b_lib.py                                   # 60 checks
bash run_d1b_harness.sh geom,g0,settle,dyn,fall,foot d1b_final
EXTRA="--cond legacy-normal" bash run_d1b_harness.sh settle d1b_final_xpA       # 같은 조건 두 번 + 다른 조건 한 번
EXTRA="--settle_kd_scale 4 --settle_diag_s 2.0" bash run_d1b_harness.sh settle d1b_kd4
EXTRA="--layout main --cond legacy-normal --episodes 2 --main_T 50" bash run_d1b_harness.sh main d1b_dry   # 경로 시험
python d1b_pair_check.py out/d1b_dry
```

원자료: `out/d1b_final/` (geom · g0 · settle · dyn · fall · foot · manifest), `out/d1b_final_xp{A,A2,B}/`, `out/d1b_kd4/`, `out/d1b_dry/`, `out/d1b_halt/`, `out/d1b_geom_main/`. permutation 2026 sha256 `8c40566f…`, 검증 manifest 행 sha256 `3221f8ff…`, holdout `07062312…`. checkpoint 는 E1 시드 42 `model_20000.pt`.

## 7. 이번에 하지 않은 것

- D1-B 본 평가 (teacher 네 조건 × 9 gap 셀 × 100 episode) 는 돌리지 않았다. main 단계는 24 env × 1 s 경로 시험만 했고 그 숫자는 결과가 아니다.
- holdout 에서 정책을 돌리지 않았다.
- E2 checkpoint 는 다루지 않았다.
- noise on 확인은 하지 않았다 (제안대로 별도 단계).
- 저장소 원본 파일은 고치지 않았고 커밋하지 않았다.
