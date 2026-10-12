## 15. 판 2 · ASTRA 4 반영 (재집계 · noise 켬 8 지형 · 짝 fingerprint)

ASTRA 4 (`inbox/jay/20261008-546-design/VERIFY-astra-4.md`) 의 판정은 「고친 뒤 진행」 이다. 계약 결정 (a) 저속 상대 MAE · (b) noise 켬 주 조건 · (c) Q3 open/closed 는 팀장 확정 전이라 **판정은 바꾸지 않고 현행과 제안을 나란히** 적는다. 재집계는 저장된 궤적 (`traj.npz`) 에서 CPU 로만 했고 시뮬레이션은 다시 돌리지 않았다. 새 시뮬레이션은 noise 켬 student 실행과 짝 확인 실행뿐이다.

**측정기 시험 (판 2 추가).** `test_q_metrics_v2.py` 의 답을 아는 합성 궤적 31 건이 모두 통과했다. 경계는 먼저 시험했다: 50 표본 정지는 현행에서 정지 · 제안에서 정지 아님, 51 표본은 둘 다 정지. 정지 시작 j = 300 (t 6.00 s) 은 두 정의 모두 통과, j = 301 은 둘 다 실패. 기울기 10 표본은 현행에서 낙상 · 제안에서 낙상 아님, 11 표본은 둘 다 낙상. 저속 (a) 의 0.05 · 0.10 경계, 횡 명령 축, Q2 분해 세 갈래, 최대 이탈 · 순변위 · 속도 RMS, 부호 있는 속도를 먼저 평균하지 않는 0.10 s 창 RMS, 정지 전에 넘어진 episode, Holm 보정의 알려진 예도 넣었다. 결함 셋 (제안 정의를 현행과 같게 · (a) 문턱을 0.15 로 · 최대 이탈을 끝점 거리로) 을 사본에 넣으면 각각 실패로 잡힌다. 기존 51 건도 그대로 통과한다.

**재처리 회귀. 확인됨.** 저장된 실행 전부 (100 tag) 를 새 `q_post.py` 로 다시 처리하기 전에 이전 `episodes.csv` · `cells.json` 을 `out/_bak_v1/` 에 두고, 이전에 있던 모든 열과 키의 값이 그대로인지 대조했다. 바뀐 값은 0 건이고 새 열만 23 개 늘었다. 1~9절의 숫자가 판 1 과 같은 근거다.

### Q2 시간 정의와 분해

{{TA1}}

ASTRA 4 의 독립 재계산 세 값 (20000 stairs_up noise 끔 73 → 72, 같은 지형 noise 켬 8 → 7, 20499 평지 500 확대 446 → 445) 이 이 표와 같다. 제안 정의로 바뀐 episode 는 cell 당 0~1 개이고 cell 판정이 뒤집힌 곳은 없다. Q2 실패는 거의 모두 「정지 자체 미달」 이다. 「전진 미달」 은 obstacles 띠 출발 (8~11 건) 과 noise 켬 stairs_up 띠의 20499 (10 건) 를 빼면 0~4 건이다.

{{TA2}}

기울기 0.2 s 를 11 표본으로 바꿔도 Q-E1 의 생존과 Q1 은 한 episode 도 바뀌지 않는다. D1-A 에서만 4 episode 의 생존과 2 episode 의 Q1 이 바뀐다.

### 정지 진단 (판정에 쓰지 않음)

{{TA3}}

noise 를 끈 조건에서 20000 은 0.10 s 창 기준으로 거의 언제나 문턱 아래인데 (0.95~1.00), 20499 는 wave · stairs_down 중앙과 wave · slope_down · rough_slope · stairs_up · stairs_down 띠에서 그 비율이 0.82~0.93 으로 떨어지고 최대 이탈과 yaw 변화가 커진다. noise 를 켜면 두 체크포인트 모두 yaw rate RMS 가 약 두 배가 되고 (평지 0.024 → 0.057, 20000), 0.10 s 창 정지 비율이 지형에 따라 0.37~0.97 로 내려간다. 0.10 s 창은 보조 진단이고 Q2 를 통과로 바꾸지 않는다.

### 저속 제안 (a)

{{TA4}}

(a) 는 0.1 m/s 에서 문턱을 0.05 m/s 로 낮춘다. 서 있기만 하는 episode 는 (a) 에서 탈락한다 (2절 0 행동 시험과 같은 방향). 평지 fwd01 은 ASTRA 4 의 계산과 같다 (20000 100 / 38 / 36 %, 20499 100 / 12 / 5 %). 0.2 m/s 에서 (a) 의 문턱은 0.10 m/s 라 이동 보조와 비슷하거나 조금 더 엄하다 (예: 20499 obstacles 중앙 이동 보조 86 % · (a) 78 %). 50 % 라는 값은 팀장 확정이 필요한 선별 제안이다. 이 수치는 사후 분석이며 같은 문턱을 E2 와 별도 validation 에도 똑같이 적용해야 한다.

### 관측 noise 켬 · 8 지형 중앙과 7 띠

{{TB1}}

학습과 같은 관측 noise (policy · single_obs) 를 켜고 student 를 Q-E1 주 실행 · 띠 출발과 같은 조건으로 두 체크포인트 모두 쟀다 (판 1 의 평지 · stairs_up 에 wave · slope_up · slope_down · rough_slope · stairs_down · obstacles 와 띠 출발 7 지형을 더함). 정지만 모든 묶음에서 무너지고, 생존과 정지 밖 Q1 은 거의 그대로이거나 조금 오른다. noise 짝 차가 유의한 cell 은 정지 말고는 모두 noise 쪽이 나은 방향이다 (stairs_up left03 · back03, stairs_down back03 · 띠 yawR05).

### 다중 비교

{{TA5}}

### 짝 fingerprint (판 2)

판 1 의 짝 hash 는 root 자세 · 관절각 · 몸 질량 · 「관절 강성」 넷이었다. Go2 actuator 는 explicit 형이라 Isaac Lab 이 sim 관절 강성 · 감쇠를 0 으로 쓰고 (`articulation.py:1760`~1769) 무작위 게인은 actuator 객체에 둔다 (`events.py` 의 `randomize_actuator_gains`, :627~646). 그래서 판 1 의 「관절 강성」 hash 는 상수 0 을 잰 것이었다 (판 2 에서 최소 · 최대 0 · 0 확인). 판 2 는 COM · 마찰 · 반발 · actuator 강성 · 감쇠 · 모터 영점 · 지연을 더했다. 값이 실제로 무작위임도 기록했다: 강성 22.5~27.5, 감쇠 0.45~0.55, 정지 마찰 0.02~1.96, 모터 영점 ±0.035 rad, 지연 0~4 step 이 거의 고르게 (1,100 env 중 222 · 199 · 226 · 232 · 221). 확인은 둘이다.

- stairs_up 주 실행 설정을 student · teacher · teacher 순열 × 두 체크포인트로 rollout 전까지만 다시 띄운 6 실행 (`out/fp_*`, 실행마다 약 20 s) 에서 넓힌 fingerprint 가 모두 같고, 옛 hash 셋 (root · 관절각 · 질량) 은 기존 Q-E1 · D1-A 실행과 같다.
- 판 2 noise 켬 실행 7 쌍 (6 지형 중앙 + 띠) 은 넓힌 fingerprint 가 두 체크포인트 사이에서 같고, 옛 hash 셋과 메시는 noise 끈 실행과 같다.

그 밖의 기존 실행 짝에서 넓힌 DR 의 동일성은 같은 시드 · 설정 · 코드 경로에서 나온 추정이다 (DR 은 정책을 읽기 전 env 생성 · 시드 reset 때 정해진다).

### 판 2 장치와 실행

실행 직전 다시 쟀다: GPU 1 = UUID 315d098f · 4,066 MiB 사용 · 그 위에 데스크톱 앱과 pid 25916 (9/29 렌더). E2 는 pid 173044 로 GPU 0. 작은 실행 하나 (noise 켬 wave, env 1,100) 로 최대 사용 9,619 MiB (+5.1 GB, 여유 6.7 GB) 를 잰 뒤 지형별로 나눠 돌렸다. 여유 4 GiB 관문은 걸리지 않았다 (최소 여유 5,568 MiB, 띠 실행). GPU 0 은 14,611 MiB 그대로, pid 25916 그대로. 판 2 GPU 사용은 약 22 분 (짝 확인 6 실행 2 분 + noise 켬 14 실행 약 20 분). 모든 실행 로그 106 개에서 Kit 렌더 장치는 315d098f 하나다.

### 판 2 에서 더한 파일

| 파일 | 내용 |
|---|---|
| `q_metrics.py` (판 2) · `q_metrics_v1.py` | `time_def` (`n50` 현행 · `span` 제안) · (a) · Q2 분해 · 정지 진단 · 0.10 s 창 · Holm. 기본값은 판 1 과 같다 |
| `test_q_metrics_v2.py` | 판 2 추가분의 답을 아는 시험 31 건 |
| `q_post.py` (판 2) · `q_post_v1.py` | 두 시간 정의를 함께 계산 (`span_` 접두 열) |
| `q_repost_all.py` | 저장 궤적 전부를 다시 처리하고 이전 값과 대조 (`out/_bak_v1/` 에 이전 판) |
| `q_astra4.py` → `out/Q-E1-astra4-tables.md` · `out/Q-E1-astra4.json` | 이 절의 표 |
| `q_eval.py` (판 2) · `q_eval_batch4.py` | 넓힌 fingerprint · `--fingerprint_only`. 판 2 직전 판은 `q_eval_batch4.py` |
| `run_noise6.sh` | 판 2 실행 묶음 (`fp` · `probe` · `rest` 단계, 머리에 실행 전 선언 · GPU 관문) |
| `out/fp_*` · `out/m<it>_noise_*` | 짝 확인 실행 · noise 켬 실행 |
