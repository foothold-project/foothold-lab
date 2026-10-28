> 분류: 리서치
> 작성: analyst · 2026-10-29
> 근거: E1/E2 원본 저장본·YAML·평가 CSV/JSON, 17f863ea·bd6122da·a299d1aa·8e75f32e, 90-DECISIONS D1/D16, W15 45d2d6f3
> 요지: E1 model_20000은 기본 보행 선생 후보로 다시 잴 가치가 있다. 후진·횡이동 증거는 있지만 잡음 있는 정지는 약하며, 현재 W15에는 그대로 넣을 수 없다.
> 상태: CPU 독립 재계산 완료 · GPU/Kit/학습/실행 코드 변경 없음 · W15 직접 실행 막음 1

# MoE-CTS 학습·평가 이력과 기본 보행 선생 후보

**권고: E1 model_20000을 첫 비교 후보로 쓰되, W15 명령·측정 코드를 E1Adapter에 연결한 뒤 판단한다.** 현재 START 전용 W15 실행기에 파일만 바꾸어 넣으면 안 된다. E2 model_20000은 다른 학습 시드의 확인 후보다. 가장 나중 파일이라는 이유로 model_20499나 CMD-R model_24000을 우선하지 않는다.

여기서 「선생」은 이미 배운 행동을 비교하거나 가르침에 쓸 정책이라는 뜻이다. MoE-CTS 내부의 특권 관측 teacher와는 구분한다. 아래 성능 수치는 원칙적으로 **배포용 student** 결과다. 이것을 START 가중치에 바로 이어 붙일 수 있다는 뜻도 아니다.

## 1. 먼저 확인된 것

| 물음 | 독립 확인 결과 | 해석 |
|---|---|---|
| E1에 뒤·옆 명령이 있었나 | 있었다. 초기 vx·vy 각각 −0.5~+0.5 m/s, wz −1~+1 rad/s. 20,000 경계부터 각각 ±1.0·±1.0·±1.5 | 지금 START 판의 전진 중심 명령과 다르다 |
| 완전 정지를 학습했나 | 명령 분포 검사 20k 전·후 각각 6,144,000 env-step에서 `(0,0,0)` 0개. `zero_command_prob=0.1`은 XY를 0으로 만들고 yaw는 남기는 경로 | 설정 이름만 보고 정지 10%라고 해석하면 틀린다. 그렇다고 정지 행동을 전혀 못 한다는 뜻은 아니다 |
| 뒤·옆을 실제로 잘했나 | CMD-R 부모 재평가 평지에서 후진 −0.3, 좌·우 0.3 m/s, 좌·우 회전 0.5 rad/s 각각 100/100 통과. 장애물 지형 횡이동은 85/100·90/100 | 근거가 있다. W15의 후진 −1.0·회전 반전·다른 지형 조건까지 증명하지는 않는다 |
| 정지는 어떤가 | 잡음 켠 CMD-R 부모 정지 90/500 통과. 별도 10/19 잡음 끈 축 2는 64 env 모두 생존하고 정지 유지 잔류속도 평균 0.000882 m/s | 평가 조건에 민감하다. 「축 2 9/9」만으로 잡음 있는 정지를 가르칠 선생으로 확정하면 안 된다 |
| E1 축 1 0.4479는 맞나 | 2,150/4,800 = 44.79%, 기존 CSV와 일치. 0.5·1.0 m/s만은 2,150/3,200 = 67.19% | 1.5 m/s는 학습 명령 범위 밖이다. 전체 수치만으로 기본 보행 전체를 부정하면 안 된다 |
| START로 바꾼 직접 이유 | 10/18 D1은 E1에 MARG/AME-2 일부만 붙인 1단계의 충실도 문제, D2는 START→HiPAN 선택. E1 축 1·2 완료 D16은 10/19 | 다음 날 평가가 전날 전환 결정의 원인이라고 거꾸로 쓰면 안 된다 |
| W15에 바로 넣을 수 있나 | 불가. W15는 StartRunner·S2Policy·perception 상태와 B 환경 사건 이름을 전제한다. E1/E2/CMD-R 12개 저장본 CPU 로드에는 모두 START perception 상태가 없다 | E1 관측·행동 경로를 보존하는 어댑터 연결이 필요하다 |

위 숫자는 이번에 원자료에서 다시 센 `확인됨`이다. 과거 영상의 새 판독이나 현재 W15에서의 물리 실행은 하지 않았다.

## 2. 찾은 학습판과 저장본

경로의 공통 부분을 다음처럼 줄였다. 아래 표의 경로는 이 루트와 합쳐진 실제 로컬 경로다.

- `R` = `C:/isaac/ext/go2_rl_robotlab`
- `S` = `C:/Users/AI-WS01/s2_lab`
- `E1` = `R/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192`
- `E2` = `R/logs/rsl_rl/go2_moe_cts/2026-10-11_12-39-32_e2_seed43_n8192`
- `W15` = `C:/mai/wt/foothold-lab/scripter-w15` @ `45d2d6f301600284ff963529d896c05cfbfbc543`

E1/E2 각각 `model_0,500,…,20000,20499.pt` 42개가 남아 있다. 원본 저장소 HEAD는 `28b4516d22617b11aeaf8ead63cc00b0c0bcd1bd`, 추적 코드 변경은 없었다. 각 저장본 파일의 SHA를 직접 계산했고 주요 판은 `torch.load(map_location='cpu')`로 안의 회차도 확인했다.

| 학습판 | 저장본 경로 | 회차·환경·시드 | 명령·정지와 평가 상태 |
|---|---|---|---|
| E1 원본 | `E1/model_20000.pt`, `model_20499.pt` | 처음부터 20,500 갱신 설정, 8,192 env, seed 42 | §3 범위. Q/QC/QD·지도 이용 진단·미경험·축 1·2 기록 있음. 20,000이 공통 부모 |
| E2 원본 | `E2/model_20000.pt`, `model_20499.pt` | 같은 설정, 8,192 env, seed 43 | E1의 다른 학습 시드. 명령·지형 동일. 10/19 v2 축 1·2는 E1만 해당 |
| CMD-R seed1042 OFF | `R/_eval/out/branch/cmdr_s1042_off_u4000/model_24000.pt` | E1 20,000에서 4,000 갱신, 8,192 env | vx·vy ±1, wz ±1.5. reset 직전 episode 길이를 사용하는 원래 명령 경로. 정지·저속 문제 남음 |
| CMD-R seed1042 ON | `R/_eval/out/branch/cmdr_s1042_on_u4000/model_24000.pt` | 같은 부모·갱신·환경 | 명령 reset 때만 episode age를 0으로 읽게 함. 지도 켬/끔 실험이 아니다. 사전 개선 조건 미달 (§4.3) |
| CMD-R seed1043 OFF | `R/_eval/out_branch/cmdr_s1043_off_u4000/model_24000.pt` | E1에서 4,000 갱신, 8,192 env, 10/13 18:57~10/14 00:18 | 두 번째 학습 시드의 반복. 저장·종료 기록 확인, 이 판의 평가 집계는 이번 재계산 범위 밖 |
| CMD-R seed1043 ON | `R/_eval/out_branch/cmdr_s1043_on_u4000/model_24000.pt` | E1에서 4,000 갱신, 8,192 env, 10/14 00:18~05:45 | reset-age 수정 반복. 1042 판의 성적을 이 판에 대신 붙이면 안 된다 |
| 구 S2 A | `S/s2_step27_run/runs/shortA-20261017-181213-890c5c24/out/checkpoint_002000.pt` | E1 기반, 추가 2,000, 1,024 env, seed 11, encoder full_freeze | 지도 A/B 실험. gap 15%·stones 15% 등록. 이 요청에서 실제 명령 분포는 미확인. 최종 집계 `불명`, 성능 확인 false |
| 구 S2 B | `S/s2_step29a_run/frozen_delivery/runs/shortB-20261017-211253-3bfaf5cd/out/checkpoint_002000.pt` | 동일한 추가 학습량·환경·시드 | 같은 한계. START S2나 현재 S-B10과 다른 구 MoE-CTS 지도 추가판 |
| Step1 M1 b3 | `S/step1_run_b3/logs/rsl_rl/go2_step1_moects_marg/2026-10-18_16-46-16_step1_M1_seed42/model_22069.pt` | E1 기반, 저장 회차 22,069, 추가 2,070, 4,096 env | MARG식 지도 MLP 추가. 저장 metadata의 실제 vx·vy ±1, wz ±1.5, zero 확률 0.1 확인. 학습 중 D1 방향 변경으로 종료 |
| Step1 M2 b4 | `S/step1_run_b4/logs/rsl_rl/go2_step1_moects_marg/2026-10-18_17-17-20_step1_M2_seed42/model_20073.pt` | 저장 회차 20,073, 4,096 env | attention 갈래·chunk 갱신. 짧은 실행, 완성된 보행 선생으로 비교한 자료 없음 |
| Step1 M2 b5 | `S/step1_run_b5/logs/rsl_rl/go2_step1_moects_marg/2026-10-18_18-09-41_step1_M2_seed42/model_20089.pt` | 저장 회차 20,089, 4,096 env | 별도 실행판. b4/b6를 같은 학습의 연속 회차처럼 합치지 않음 |
| Step1 M2 b6 | `S/step1_run_b6/logs/rsl_rl/go2_step1_moects_marg/2026-10-18_18-34-27_step1_M2_seed42/model_20086.pt` | 저장 회차 20,086, 4,096 env | AME-2 공식 크기에 맞춘 지형 갈래. D1으로 종료. P1 평가기 문서는 CPU 인도이며 실제 성능 완료 증거가 아님 |

M2 세 판의 YAML에는 E1과 같은 초기·20k·50k 명령 일정이 있다. 이번에 실행 중 명령 metadata까지 재확인한 것은 M1이며, M2 실제 명령 표본 분포는 미확인이다. CMD-R 네 실행은 각각 20,500~24,000의 500 간격 저장본 8개를 보존한다. OFF/ON은 두 경우 모두 E1 같은 부모에서 갈라졌다. E2를 이어받은 판이 아니다.

짧은 시험도 별개로 남아 있다: `step1_run_b2/.../15-46-24.../model_20000.pt`, `step1_run_b3/.../16-38-35.../model_20009.pt`, `.../16-38-56.../model_20000.pt`; `R/_eval/out/branch/gate_*`; `R/_eval/out/resume_test/`의 연속/분할/복원 시험. 이들을 새로 수렴한 정책으로 세지 않았다. `S/step1_moects_marg/`는 구현·보고·fixture 자리이며 본 학습 저장본은 위 `step1_run_b*`에 있다.

### 주요 파일 SHA256

| 파일 | SHA256 |
|---|---|
| E1 19,500 | `6a8ce13c7ffd741b6e5d36cfc45796ecfef2059cb69ca522b51c5d3a174325f2` |
| E1 20,000 | `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8` |
| E1 20,499 | `7e52a5026086660308fbc270f30ebf983064b1cb8695aca73652136ebf02f904` |
| E2 19,500 | `af35efcd556161da676f70b4347001e9294cdde18420c6346cb4b5a9bc29c4c5` |
| E2 20,000 | `d75bfd12c59c15e7e12e70394add4c64cf1dca854e37104414c0a25359577ba8` |
| E2 20,499 | `ac4c9240704aa083e0701b402ff854643c3bc9437e99e719a68fc16149946971` |
| CMD-R 1042 OFF 22,000 | `35afb9f2f8b4ac3c508f42235100b294a0818087e32d77c144f11cb7c494a3b6` |
| CMD-R 1042 ON 22,000 | `cc06a1c45a8c60668b2959d2e8bbace1cc8443dce6dcb572351aaee7ad73fdbc` |
| CMD-R 1042 OFF 24,000 | `77c2fb648348dab5704d35fb94a6128ae2789b6ebb5470042b76e2548a6e86c1` |
| CMD-R 1042 ON 24,000 | `9d26717c70061ef3a3de33a6e3cc040596682ccc9e650b45cc36b9a1a02c8b25` |
| CMD-R 1043 OFF 22,000 | `5659566bc538cdd8ed549ddd60e0b22f9460ed4978430265f55910f041006f6d` |
| CMD-R 1043 ON 22,000 | `f8070d487d3d5a5eec3b77ea4cd433e3a136b35ed3760315d316ee9ca4948d42` |
| CMD-R 1043 OFF 24,000 | `2ea3b5e8303a5a7150532c3fa784b319c39e085c092f0c13cc5b07af6a04fa69` |
| CMD-R 1043 ON 24,000 | `e548b51602bb5cf848f497e6a7a40afbbf4f8f65fb59149d19b71ae0a52be454` |
| 구 S2 A 추가 2,000 | `0881c0b81557beb72a60d940511de28f739f838c85b320a90f752a7fde3ab57b` |
| 구 S2 B 추가 2,000 | `9e7328198aff8c587c22ef25d9bcc6398a7ae8f8384e85234deb5602368026bc` |
| M1 b3 22,069 | `9c3b3db0cdc5d36047d13544363d2156a3ab7b61dbb85dd4d6a966538678ca88` |
| M2 b4 20,073 | `5ebab61b3fdda68bff0d9aa2003324457ab7ee4726510a02c89a0d0b01ab34bc` |
| M2 b5 20,089 | `c52185d7b4cd846437f0c5c0d7d4d86d430c76f4c74cc54afc2a8ae23700d5cc` |
| M2 b6 20,086 | `a75097f7034be5e53bda27215107cbc3b6379801dd149705d628a792ce2b3144` |

## 3. E1/E2가 실제 배운 입력과 명령

원본 `params/agent.yaml:1~75`, `params/env.yaml:2086~2304`, `R/source/robot_lab/robot_lab/tasks/go2/mdp/commands.py:126~259`를 대조했다.

| 항목 | 실제 값·경로 | 주의 |
|---|---|---|
| 학습 회차 | max_iterations 20,500, rollout 24, 8,192 env | 파일 20,000은 확대 전에 저장한 순수한 판이 아니다 |
| 명령 초기 범위 | vx·vy `[-0.5,0.5]`, wz `[-1,1]` | 뒤·옆·이동 중 회전도 생성될 수 있다 |
| 20,000 경계 범위 | vx·vy `[-1,1]`, wz `[-1.5,1.5]` | 대부분의 학습은 이전 좁은 범위였다. m20000에서 새 범위를 오래 배웠다고 해석하지 않는다 |
| 50,000 예정 범위 | vx `[-2,2]`, vy `[-1,1]`, wz `[-2,2]` | 두 원본 학습은 도달하지 않음 |
| 명령 재추출 | 5 s, 동적 하한·지형별 제한·limit 확률 존재 | 세 숫자를 독립 균등 추출한 단순 분포가 아니다 |
| zero curriculum | 0~1,500에 확률 0→0.1 | XY 0·yaw 잔류. 완전 정지 10%가 아님 |
| 정책 입력 | 몸 감각·명령 등의 45열 × 10 step = 450, 현재 45열 | 50 Hz에서 0.2 s 역사 |
| 배포 student | MoE 8 experts, 실제 저장 설정 hidden `[512,256,256]`, latent 32 | 클래스 기본 인자 `[512,256,128]`와 혼동 금지 |
| actor | latent 32 + 현재 관측 45 = 77열, hidden `[512,256,128]`, 관절 행동 12 | START 입력·체크포인트 구조와 다름 |
| 내부 teacher | 특권 관측 275열을 `[512,256]`로 latent 32에, 학습 teacher env 비율 0.75 | 배포 `act_inference`는 이 입력을 직접 쓰지 않는다 |
| 지형 | wave .05, slope_up .10, slope_down .10, rough_slope .05, stairs_up .25, stairs_down .10, obstacles .20, flat .15. stones/gap 0 | YAML의 상대 가중 합은 **1.10**. 그대로 퍼센트라고 쓰면 안 됨. 구멍·징검다리 학습은 없었음 |

명령 분포는 저장 정책으로 생성기를 조사한 별도 probe다. E1 전체 학습의 모든 명령을 저장한 로그는 아니다. `R/_eval/out/cmd_dist/{pre20k,post20k}/cmd_steps.npy`를 직접 다시 세었다. 분모는 각각 **1,500 step × 4,096 env = 6,144,000 env-step**이다.

| 명령 분류 | 20k 전 | 20k 뒤 |
|---|---:|---:|
| 완전 정지, XY 및 yaw 모두 1e-6 미만 | 0 | 0 |
| 평면 정지·제자리 회전 | 412,621 (6.716%) | 486,213 (7.914%) |
| 뒤 성분 우세, vx<0·abs(vx)≥abs(vy) | 1,415,335 (23.036%) | 1,424,668 (23.188%) |
| 옆 성분 우세, abs(vy)>abs(vx) | 2,291,479 (37.296%) | 2,247,211 (36.576%) |
| 평면 속도 0 초과·0.2 미만 | 175,334 (2.854%) | 93,073 (1.515%) |

추가로 과거 `CMD-RESUME.md`는 reset 시점의 남은 시간 계산 때문에 초반 명령이 대각 상한에 몰리는 현상과, 원래 resume이 env 시계·지형·학습률 변수 등을 그대로 복원하지 않는 문제를 기록했다. CMD-R은 그 중 **명령 reset의 age만** 고친 비교다. 새로운 정지 슬롯을 만든 실험이 아니다. 코드 `R/_eval/branch/branch_lib.py:59~83` 확인.

## 4. 평가 수치 재확인

### 4.1 후진·옆·회전: 오래된 자료에도 증거가 있다

아래는 `R/_eval/out/cq_p20000_<지형>_<명령>_on_s1000/episodes.csv`를 다시 센 값이다. 각 칸 n=100, 관측 잡음 켬, 이동·회전은 `span_q1_pass`, 정지는 `span_q2_pass`. 예전 Q 문턱을 유지했으며 W15 통과로 바꾸어 부르지 않는다.

| 지형 | 뒤 −0.3 | 옆 +0.3 | 옆 −0.3 | 회전 +0.5 | 회전 −0.5 | 전진 후 정지 |
|---|---:|---:|---:|---:|---:|---:|
| flat | 100 | 100 | 100 | 100 | 100 | 19 |
| wave | 100 | 99 | 99 | 100 | 100 | 1 |
| slope_up | 100 | 100 | 100 | 100 | 100 | 16 |
| slope_down | 100 | 100 | 100 | 100 | 100 | 16 |
| rough_slope | 100 | 100 | 100 | 100 | 100 | 3 |
| stairs_up | 100 | 99 | 100 | 100 | 100 | 11 |
| stairs_down | 100 | 100 | 100 | 100 | 100 | 4 |
| obstacles | 94 | 85 | 90 | 100 | 100 | 14 |

단위는 통과 수/100. Q1은 첫 1 s를 뺀 body-frame vx·vy MAE 각 ≤0.15 m/s, yaw MAE ≤0.20 rad/s와 생존을 본다. **몸 기준 속도 추종을 잘해도 세계 좌표에서 방향을 유지하며 목적지까지 간다는 보장은 없다.** 실제 같은 평지 후진 100판의 Q1은 100/100이나 Q3 경로 기준은 3/100이다. 기본 속도 선생과 목표 도달 선생을 구분해야 하는 이유다.

E2도 독립 학습판이 있다. 원래 Q 잡음 켬 9실행·11,600 episode를 다시 합산하면 E1 10,138/11,600, E2 10,172/11,600이며 기존 `E12-summary.json`과 일치한다. 이 합은 중앙 8종과 띠 출발 조건을 섞은 과거 Q 요약일 뿐 W15 점수가 아니다. 평지 E2의 뒤·옆·회전 각 100/100, 정지 20/100이었다. 원자료 `R/_eval/out/{m20000_noise_*,e2_m20000_noise_*}/episodes.csv`.

### 4.2 10/19 E1 대 v2: 축 1·2

`S/eval_e1_v2axes/axis1/{rough6,unseen10}/d0.5/v{0.5,1.0,1.5}/generalization_raw.csv` 4,800행의 5개 성공 열을 직접 합산했다. **48칸 × 5축 모두 17f863ea의 E1 열과 일치**한다. 원자료의 policy SHA도 전 행 E1 model_20000과 같다.

| 평가 지형군·속도 | 종합 통과 | 생존 | 해석 |
|---|---:|---:|---|
| rough6 · 0.5 m/s | 482/600 (80.33%) | 600/600 | 일부 방향 이탈 |
| rough6 · 1.0 m/s | 457/600 (76.17%) | 596/600 | 내리막 계단 추종 통과 20/100, 종합 18/100 |
| rough6 · 1.5 m/s | 0/600 | 593/600 | 추종 축 0. 넘어진 것과 다름, 학습 명령 범위 밖 |
| unseen10 · 0.5 m/s | 600/1,000 (60.0%) | 850/1,000 | 틈·징검다리 약함 |
| unseen10 · 1.0 m/s | 611/1,000 (61.1%) | 794/1,000 | 같은 약점 |
| unseen10 · 1.5 m/s | 0/1,000 | 811/1,000 | 추종 축 0, 범위 밖 |
| 전체 0.5·1.0만 | 2,150/3,200 (67.19%) | 2,840/3,200 | 범위 안의 별도 집계 |
| 전체 세 속도 | 2,150/4,800 (44.79%) | 4,244/4,800 | D16의 0.4479 |

gap은 0.5 m/s에서 0/100, 1.0에서 **1/100**이다. 따라서 기록의 「틈·징검다리 0」은 요약 표현이며 모든 칸의 정확한 0은 아니다. stepping_stones는 세 속도 종합 모두 0/100이었다. 이 평가는 난이도 0.5, 종합 = 생존·진척·추종·방향의 AND다. 옛 Q와 성공 기준이 다르다. v2의 기존 대조 수치는 [17f863ea 축 1 표](https://github.com/foothold-project/foothold-lab/blob/17f863ea/inbox/jay/20261019-design/evidence/E1-vs-v2-axis1.csv)에 있으며, 이번 재계산은 E1 원자료를 대상으로 했다.

축 2는 `S/eval_e1_v2axes/axis2/{stop,hold,turn,ramp}/per_env.json`을 env별로 평균했다. manifest와 일치한다.

| 조건 | E1 재계산 | 범위 |
|---|---:|---|
| turn·stop·hold 낙상 | 각각 0/64 | 평지, 관측 잡음 끔 |
| hold 마지막 1 s 잔류속도 | 평균 0.000882 m/s | 20 s 전 명령 0 |
| hold 마지막 1 s 관절 목표 변화 | 평균 0.002645 rad/step | 힘·보행 위상 판정과 별개 |
| 전진 후 stop 잔류속도·정지 시간 | 0.002709 m/s·0.554 s | 1.0 m/s 4 s 후 정지 |
| yaw +0.5 / +1.0 | 추종비 0.9353 / 0.9839 | 18 s 계단 명령 |
| yaw −0.5 / −1.0 | 추종비 0.8369 / 0.9352 | 같은 시험 |

등록된 축 2 아홉 칸은 9/9 통과했다. 하지만 이것은 **평지·관측 잡음 끔·해당 18/20 s 프로토콜**이다. W15의 ±1.2 반전과 같지 않다. 당시 manifest는 push만 끄고 질량·COM·재질·gain·영점은 학습 설정대로 두었다고 명시한다. 현재 공통 E1Adapter는 mass·COM도 끄므로 같은 이름의 축 2라도 물리 조건을 다시 맞춰야 과거 수치와 직접 비교할 수 있다.

### 4.3 CMD-R은 해결책으로 확정되지 않았다

평지·관측 잡음 켬, 평가 seed 1000~1004 각 100판. 원자료 `cq_<판>_flat_<칸>_on_s<seed>/episodes.csv` 7,500행을 다시 셌다. 저속은 절대 MAE만으로 서 있음을 통과시키지 않는 `span_q1a_pass`를 쓴다.

| 목표 칸 | 부모 20,000 | OFF 22,000 | ON 22,000 | OFF 24,000 | ON 24,000 |
|---|---:|---:|---:|---:|---:|
| 전진 후 정지 | 90/500 | 18/500 | 52/500 | 36/500 | 55/500 |
| 전진 0.1 | 180/500 | 222/500 | 98/500 | 140/500 | 188/500 |
| 전진 0.2 | 499/500 | 496/500 | 457/500 | 483/500 | 496/500 |

ON−OFF 세 칸 평균은 22,000에서 −8.60%p, 24,000에서 +5.33%p이다. 사전 등록한 평균 +10%p 이상을 못 넘었다. 24,000이 무조건 더 좋은 선생이라는 근거가 아니다. 출처 `eval-cmdr-morning/handover-1635/v10/CMDR-tables.md:3~15`; 사전 문턱과 원자료 수 모두 확인했다.

## 5. 찾은 평가·진단 기록 전체 지도

「찾음」과 「이 의뢰에서 다시 계산함」을 나눴다. `_eval/out`에는 같은 판의 smoke·실패·재시도가 함께 있으므로 폴더 수를 곧 실험 수나 유효 표본 수로 세지 않는다.

| 묶음 | 정리 문서·원자료 자리 | 무엇을 확인했나 |
|---|---|---|
| 10/10 E1·E2 재현 계획 | `bd6122da:inbox/jay/20261008-546-design/EXP-weekend-moects.md`; `R/_runs/e{1,2}_seed*_n8192.log`와 각 run TensorBoard·YAML | 20,500 학습·두 시드·원본 저장본 확인 |
| 기본 명령 Q | `inbox/jay/20261008-546-design/eval-q-e1/Q-E1.md`; `R/_eval/out/m{20000,20499}_*`, `e2_m*` | 정지·저속·옆·뒤·회전. 이번에 E1/E2 20k 잡음 켬 episode 합 재계산 |
| 회차별 QC | 같은 루트 `eval-qc-e1/QC-E1.md`; `R/_eval/out/QC-E1-cells.csv`, `m{5000,10000,15000,19500}_*` | 학습 곡선·능력 변화 기록 찾음. 모든 회차를 이번에 다시 채점하지 않음 |
| 난이도 QD | `eval-qd-e1/QD-E1.md`; `R/_eval/out/qd*`, `e2_qd*` | 난이도 .2/.5/.8, 별도 지형 시드 2000. 문서·원자료 위치 확인 |
| 내부 teacher의 지도 이용 D1-A | `eval-d1-e1/D1-E1.md`; `R/_eval/out/t20000_*`, `tp20000_*`, 20499 대응 폴더 | 정상 height와 순열 비교, student 음성 대조. 배포 student 직접 지도 사용 증거로 쓰지 않음 |
| 높이 no-hit·gap 하네스 | `eval-g0/G0.md`, `eval-d1b-harness/D1B-harness.md`; `R/_eval/out/g0_probe`, `d1b_*` | 입력 반전·낙하/접촉 기록 검사. 이 문서들의 G0·D1 이름은 현재 G0-B나 결정 D1과 다름 |
| 학습 명령·resume | `eval-cmd-resume/CMD-RESUME.md`; `R/_eval/out/cmd_dist`, `resume_test` | 명령 NPY 재집계. 복원 시험은 별도 작은 실행이며 E1 본체 학습 결과가 아님 |
| CMD-R 1042 | `eval-branch-cmdr/BRANCH-CMDR-tools.md`, `eval-cmdr-morning/handover-1635/v10/`; `R/_eval/out/branch`, `cq_*` | 4k 짝 학습과 평가. 이번 핵심 목표·부모 이동 칸 재계산 |
| CMD-R 1043 | `inbox/jay/20261012-arch-discussion/night-tools-20261013/cmdr1043_eval_*`; `R/_eval/out_branch/cmdr_s1043_*` | 학습 결과·SHA 확인. 후보 평가 코드의 CPU 검증 보고를 실제 평가 완료로 바꾸어 말하지 않음 |
| 미경험 지형 | `R/_eval/out/UNSEEN-cells.csv`, `un_*`; `R/_eval/out_uncr_v6/{UNCR-cells-v6.csv,post_v6.json}` | E1/E2 및 CMD-R의 별도 미경험 평가. v6 집계는 32 요청 칸 complete·결측/무효/hold/unpaired 0. 이번 성능 재채점은 안 함 |
| 같은 시험지 CE12 | `R/_eval/out_ce12/native/cts_e1_m20000*`, `v2_native_*`; `night-tools-20261013/ce12*` | native 정책 기록·map_location/시작점 수정의 이력. 실패한 초회와 후속판을 섞지 않음 |
| RAND | `R/_eval/out_rand/`; `night-tools-20261013/rand*` | 지형 무작위화 smoke·검증 이력. 새로 수렴한 teacher checkpoint로 세지 않음 |
| 구 S2 A/B | `S/s2_step32_run/results_u2000/S2-AB-UPDATE2000.json`, `S/s2_step34_run/results_full/S2-AB-RESULT.json` | 추가 2,000 A/B 저장본 확인. 후자 `verdict=불명`, `comparison_ready=false`, `performance_verified=false`. 성공판으로 승격하지 않음 |
| 10/18 Step1 M1/M2 | `S/step1_moects_marg/REPORT-step1-*.md`, `HANDOFF-step1-18b.md`; `step1_run_b2~b6` | 지형 encoder 이식·chunk·resume·큐·평가기 CPU 작업과 실제 짧은 학습을 구분 |
| 10/19 E1 v2 축 1·2 | `17f863ea:evidence/E1-vs-v2-axis*.csv`; `S/eval_e1_v2axes/` | 4,800 episode 및 축 2 env 요약 재계산 (§4.2) |
| 과거 영상 페이지 | `inbox/jay/20261008-546-design/e12-page/README.md`; `R/_eval/out/web_list.csv`, `unseen_web_list.csv`, 해당 parquet·영상 | E1/E2 본편·19,500·미경험 영상 목록 있음. 이번 새 영상 판독 없음 |

범위는 제공받은 커밋·설계, 로컬 원본 저장소 `_eval`·`logs`, `s2_lab/step1*`와 연결된 구 S2 기록이다. 외장 장치·NAS·RunPod 전체에 별도 MoE-CTS 기록이 더 있는지는 미확인이다. 로그 파일이 있다는 이유만으로 정상 완료나 비교 가능성을 인정하지 않았다.

## 6. START 전환 이유를 날짜와 함께 읽어야 한다

1. **MoE-CTS 재현 뒤 기본 보행·명령을 조사했다.** E1은 전진만 배운 정책이 아니다. 10/11부터 정지·횡·뒤·회전·난이도·지도 이용을 나눠 평가했고 정지 잡음 민감도·저속·방향 이탈과 미경험 틈을 확인했다.
2. **10/18에는 E1에 지도 encoder를 붙이는 Step1을 시도했다.** `a299d1aa:DESIGN-step1-moects-plus-marg.md`, `8e75f32e:DESIGN-v2-moects-terrain-modules.md`의 M1/M2다. E1이 곧 MARG나 AME-2 전체인 것은 아니었다.
3. **D1의 직접 이유는 방법을 축소한 접목의 충실도였다.** `90-DECISIONS.md:17`은 MARG 추정기·ReLU 등의 생략 문제를 지적하며 1단계를 정지하고 재설계한 결정이다. 「MoE-CTS가 걸을 수 없어 버렸다」는 기록이 아니다.
4. **D2는 START→HiPAN 본선 선택, D3는 E1을 비교선에 보존했다.** `90-DECISIONS.md:18~22`, `DECISIONS-step2-lead.md` 참조. 실기 지각·하위 보행·주행 연결이라는 프로젝트 방향과 방법·예산 검토의 결과다.
5. **D16 평가는 다음 날이다.** `90-DECISIONS.md:33`의 축 1 0.4479·축 2 9/9는 전환 뒤 비교 기준을 확보한 결과다. 전환의 사후 근거로 보탤 수 있지만 전날 결정의 직접 원인으로 소급하지 않는다.

의뢰의 `APPROVED-DIRECTION.md:59`는 조회한 판에서 DDP 행이고, E1 결과는 **53행**이다. 줄 번호가 이동했으므로 내용과 D16의 evidence 링크를 기준으로 대조했다. `90-DECISIONS`의 결정 D1과 `eval-d1-e1`의 지도 순열 실험 D1은 서로 다르다.

## 7. W15 연결 가능성

### 그대로 실행: 막음 1

| 경계 | 현재 코드·증거 | 판단 |
|---|---|---|
| 저장본 구조 | `W15/foothold_s2/eval/adapters.py:473~516`은 StartRunner를 만들고 `perception_state_dict`를 요구 | E1에는 없음. `--modes none`으로도 해결되지 않음 |
| 물리 사건 이름 | `eval_map_modes.py:62~74`는 B의 `physics_material`, `add_base_mass` 두 사건이 꺼졌는지 엄격히 검사 | E1의 `randomize_*` 이름과 다름. task 이름만 바꾸면 통과하지 않음 |
| 추론 경로 | `eval_map_modes.py:100~117,155,281~285`는 지각 선택·지도 토큰·S2Policy를 전제 | E1 배포 student에 GT/PRED/가림을 붙이는 것은 의미가 다름 |
| 관측 계약 | E1 history450·single45·critic275, actor77. CPU strict load·유한 12행동·critic 교란 무반응·history 교란 반응을 E1/E2/CMD-R 12개 파일에서 확인 | 원래 정책망을 보존한 CPU 추론은 가능. START 환경 관측을 그대로 꽂는 것은 불가 |
| 기존 E1 길 | `adapters.py:79~224`의 E1Adapter, `run_eval.py:80~82,221~263,294~298` | 축 1·2·3의 별도 E1 경로는 이미 있음. W15 확장 명령 루프와 아직 연결 안 됨 |

이번 CPU 합성 입력에서 E1 m20000의 critic 교란 행동 차는 **0**, history 0.1 교란 행동 최대 차는 **1.0048151**이었다. 이는 합성 입력의 경로 검사이며 보행 성능 수치가 아니다. 원본 `actor_critic_moe_cts.py:225~234`의 배포 student 경로를 썼다.

### W15와 같은 과제를 재려면

새 학습은 필요 없다. **E1Adapter를 W15의 명령·측정 루프에 연결하는 작업**이 필요하다. 분석자가 이번에 코드를 고치지는 않았다.

| 유지해야 할 계약 | 필요한 연결 |
|---|---|
| 같은 명령 과제 | `map_mode_cells.py:14~35`의 전진 .5/1, 회전 ±1.2, 후진 −.5/−1, 횡 ±.5, 대각 네 가지, 정지, 좌→우·우→좌·정지/재출발 그대로 |
| 같은 시간 | 기본 300 step × .02 s = 6 s. 회전 반전 두 구간 각 3 s, 정지/재출발 네 구간 각 1.5 s. 순서 중간 reset 없음 |
| 원래 정책 | RobotLab-Go2-v0의 관측·정규화·이력·관절 순서·action scale·PD를 보존. deterministic student mean action. 모드는 `native_student`처럼 기록하고 START 지도 켬/끔으로 위장하지 않음 |
| 명령의 실제 소비 | E1은 history를 쓴다. 명령을 쓴 뒤 history를 임의 재구성해 같은 step을 두 번 넣거나 이전 명령으로 추론하지 않도록 현재 axis2_run의 명령 주입 순서를 보존 |
| 지형과 reset | 같은 지형 종류·레벨·mesh·초기 상태를 대조. 64 env 전체를 지형별 64개로 오해하지 않음. 사망/reset 뒤 자료를 생존 추종 평균에 합치지 않음 |
| DR 조건 | 기존 E1Adapter는 push·mass·COM·관측 잡음을 끄지만 material/gain/영점은 남김. W15와 어떤 물리값을 맞출지 manifest에 명시. 원래 native 결과와 공통 물리 조건 결과를 섞지 않음 |
| device 복원 | E1Adapter의 `runner.load(checkpoint)`에는 map_location 인자가 없음. 원본 CTS loader는 인자를 지원한다(`on_policy_runner_cts.py:260~261`). 다른 GPU 번호에 올릴 때 명시적으로 해당 device에 복원하는 연결 필요 |
| 숫자·영상 | W15의 env별 지형/행/명령, 거리·생존·Q/C/kept·정지·반전 응답을 같은 식으로 기록. 좋은 Q만으로 trot나 발끌림이 좋다고 결론내리지 않음 |

W15의 back1.0와 spin±1.2는 m20000이 대부분 학습한 범위보다 넓다. **학습 범위 안의 기본 능력과 확장 스트레스 칸을 따로 표시**해야 한다. E1이 이 칸에서 떨어져도 바로 기본 보행 선생 탈락이라고 해석하지 않는다. 반대로 후진 .3의 과거 성공으로 −1.0의 W15 통과를 대신할 수 없다.

### 이미 존재하는 E1 평가 명령 예시

아래는 현재 E1Adapter의 기존 축 2·3 진단 명령이다. **정확한 W15 실행 명령이 아니다.** 현재 코드로 W15를 직접 돌리는 유효한 명령은 없으며 위 연결 뒤에 정해야 한다. 이 예시는 이번에 실행하지 않았고 실행 담당자의 GPU 배정·Kit 예행이 필요하다. 축 3는 시간·거리·시작·성공 기준도 W15와 다르다.

```powershell
# cwd: C:/mai/wt/foothold-lab/scripter-w15
$moePy = 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe'
$moeCk = 'C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192/model_20000.pt'

# 평지 기존 stop/ramp/turn/hold. W15 반전 시퀀스와 다름.
& $moePy -m foothold_s2.eval.run_eval axis2 --policy e1 --checkpoint $moeCk --label e1-m20000-native --scenario all --num_envs 64 --seed 42 --out C:/Users/AI-WS01/s2_lab/eval_moects_history/new_axis2 --headless --device cuda:0

# 연속 지형 뒤/옆. 출력 폴더는 실행마다 새로 정한다.
& $moePy -m foothold_s2.eval.run_eval axis3 --policy e1 --checkpoint $moeCk --group continuous --direction back --cmd=-0.5,0,0 --episodes 100 --envs_per_terrain 10 --difficulty 0.5 --seed 42 --out C:/Users/AI-WS01/s2_lab/eval_moects_history/new_back05 --headless --device cuda:0
& $moePy -m foothold_s2.eval.run_eval axis3 --policy e1 --checkpoint $moeCk --group continuous --direction left --cmd=0,0.5,0 --episodes 100 --envs_per_terrain 10 --difficulty 0.5 --seed 42 --out C:/Users/AI-WS01/s2_lab/eval_moects_history/new_left05 --headless --device cuda:0
& $moePy -m foothold_s2.eval.run_eval axis3 --policy e1 --checkpoint $moeCk --group continuous --direction right --cmd=0,-0.5,0 --episodes 100 --envs_per_terrain 10 --difficulty 0.5 --seed 42 --out C:/Users/AI-WS01/s2_lab/eval_moects_history/new_right05 --headless --device cuda:0
```

실행 환경에서 실제 import되는 `rsl_rl`은 원본 `R/source/rsl_rl`인지 먼저 확인해야 한다. Step1 M1/M2의 수정 rsl_rl이나 START용 패키지가 대신 불리면 이 CPU strict-load 결과와 다른 코드가 된다. axis2 all의 네 시나리오를 따로 잘라 실행하면 난수 소비가 달라 과거 표와 직접 비교할 수 없다는 주석도 `axis2_run.py:1~7`에 있다.

## 8. 선생 후보에 대한 최종 판단

**E1 m20000은 검토할 가치가 충분하지만 아직 W15로 선정된 선생은 아니다.** 몸 감각 역사만으로 뒤·옆·양방향 회전을 해낸 실제 자료가 있고, 원본 가중치·코드·명령·평가가 함께 보존돼 있다. 이것이 가장 큰 장점이다. 약한 정지·저속과 방향 유지, 학습하지 않은 gap·stones까지 우수하다고 확대해서는 안 된다.

- 첫 후보는 **E1 m20000**, 다른 학습 시드 확인은 **E2 m20000**. 서로의 대표 영상을 대신 보거나 두 모델 수치를 평균해 하나의 능력으로 쓰지 않는다.
- **E1 m19500**도 보존할 가치가 있다. 과거 QC는 20k 명령 확대 전후의 저속·정지 변화를 다뤘다. 20k와 비교할 때 「500회 덜 배웠다」뿐 아니라 명령 범위 경계가 있다는 점을 기록한다. 이 요청에서는 W15 우열 미확인이다.
- CMD-R·M1/M2·구 S2는 별도 갈래다. 최근 저장본이라는 이유만으로 선택하지 않는다. CMD-R 1042는 등록 개선 목표 미달, M1/M2는 짧은 실행·방향 변경, 구 S2는 최종 성능 불명이다.
- 장차 START를 가르치는 교사로 쓴다면 observation·action 계약이 다른 정책 간 행동 증류 또는 별도 인터페이스 설계가 필요하다. 단순 `resume`으로 학습을 이어야 한다는 권고가 아니다.

**lead가 정할 것:** E1Adapter를 W15에 연결해 E1 m20000과 현재 후보를 같은 과제로 재볼지. 연결 전에는 현재 W15 직접 실행을 막는다. 새 학습은 이번 조사에서 요구하지 않는다.

## 9. 재계산 방법·근거 보존

CPU 작업 폴더: `C:/mai/wt/foothold-lab/analyst-ame2/_out/moects_history/`.

| 파일 | 내용 |
|---|---|
| `checkpoints.json`, `selected_checkpoints.json`, `additional_checkpoints.json` | 실제 파일 path·SHA·회차·key·shape, 중간 저장본 목록 |
| `configs.json` | run별 원본 YAML 명령·지형·agent 값 |
| `recompute.py`, `recomputed.json` | 4,800행 축 1, 축 2 env 요약, 1,228.8만 command env-step, CMD-R 핵심 칸 재집계와 입력 파일 SHA |
| `e12_raw_q.json` | E1/E2 잡음 켬 각 11,600 episode 집계. 중앙 출발·띠 출발 원본 경로를 따로 보존 |
| `check_native_cpu.py`, `native_cpu.json` | 원본 class strict load·critic 음성 대조·history 양성 대조. 12개 저장본, CPU만 사용 |

답을 아는 입력: CSV 문자열 `False`를 참으로 세지 않는지 확인; 정지·제자리 yaw·후진·옆 네 명령을 각각 1개로 분류; 원본 파일 SHA 대조; 축 1 기존 48칸×5축과 완전 일치. 축 2는 env 요약을 재집계했으며 parquet 전 시계열의 metric 함수를 새로 재실행한 것은 아니다. 과거 Q의 생역학·영상·미끄럼을 이번 수치 표만으로 재판정하지 않았다.

원문 연결:

- [E1/E2 재현 계획 bd6122da](https://github.com/foothold-project/foothold-lab/blob/bd6122da/inbox/jay/20261008-546-design/EXP-weekend-moects.md)
- [Step1 최초 설계 a299d1aa](https://github.com/foothold-project/foothold-lab/blob/a299d1aa/inbox/jay/20261018-next-arch/DESIGN-step1-moects-plus-marg.md)
- [Step1 지형 모듈 v2 8e75f32e](https://github.com/foothold-project/foothold-lab/blob/8e75f32e/inbox/jay/20261018-next-arch/DESIGN-v2-moects-terrain-modules.md)
- [E1 축 1 원표 17f863ea](https://github.com/foothold-project/foothold-lab/blob/17f863ea/inbox/jay/20261019-design/evidence/E1-vs-v2-axis1.csv), [축 2 원표](https://github.com/foothold-project/foothold-lab/blob/17f863ea/inbox/jay/20261019-design/evidence/E1-vs-v2-axis2.csv)
- [결정 기록 D1·D16](https://github.com/foothold-project/foothold-lab/blob/feature/verify-v2-mvp-jay/inbox/jay/20261019-design/90-DECISIONS.md), [Q-E1 평가 문서](https://github.com/foothold-project/foothold-lab/blob/feature/verify-v2-mvp-jay/inbox/jay/20261008-546-design/eval-q-e1/Q-E1.md), [CMD-R 동결 표](https://github.com/foothold-project/foothold-lab/blob/feature/verify-v2-mvp-jay/inbox/jay/20261008-546-design/eval-cmdr-morning/handover-1635/v10/CMDR-tables.md)

| 판 | 변경 |
|---|---|
| v1.0 · 2026-10-29 | 이력·저장본 SHA·명령·과거 평가 독립 재집계·전환 이유·W15 연결 한계 정리 |
