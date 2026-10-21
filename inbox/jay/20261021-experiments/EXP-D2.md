> 분류: 실험
> 작성: 오흥재 (luna 초안 · lead_tmp 대조) · 2026-10-21
> 근거: #555 사전 등록·판정 댓글 · NIGHT-REPORT-1021.md · eval_new/diag_s1a · sonnet-code 로그
> 요지: 선속도·회전 추종 커널을 함께 좁힌 D2는 seed 42에서 정지를 크게 줄였고 회전 추종 손실도 동반했다.
> 상태: 기록 · 진단용 새 판 · 1,500회와 1,100회 비교를 분리 · 원자료 재집계 미실시

대조 범위: 본문 초안의 `[실측]`은 저장 기록 또는 다른 세션 보고를 가리킨다. 아래 「lead_tmp 직접 대조」에 적은 항목만 이번에 직접 확인했고, 그 밖의 값은 보고값·미확인으로 읽는다.

# EX-03 D2 · 추종 커널 동시 변경

> 원자료 재집계: `미측정`. 수치 표는 원보고와 실행 기록을 출처로 하며 이 초안에서 다시 계산하지 않았다.
실험 식별자·경로의 숫자는 이름이다. `[코드]`는 코드·설정값, `[실측]`은 기록 측정값, `[가정]`은 해석이다. 여기서 지표는 보고값이며 평가 JSON 재집계 결과가 아니다.

## 가설과 사전 등록

> 원문: “지표 · 판정선은 D1 과 같음(기준 멈춤 0.766 · 전진 0.19 m → 지지 멈춤 ≤ 0.383 · 전진 ≥ 0.69 m), 회전 추종은 기록용.”

결과 전 등록은 #555 [6299099683](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6299099683)이다. S1-a scan과 같은 설정·seed 42에서 lin·ang std를 함께 0.5에서 0.25로 바꾸고, 정지 ≤0.383 AND 전진 ≥0.69 m를 본다. **회전 0.264는 D2 합격 기준이 아니다.** [6302009721](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6302009721)은 D2 결과 발표와 D3·D2-s43의 후속 등록이며, 회전 ≥0.264는 그중 D3 조건이다. 두 댓글의 선후를 보존한다.

## 설정과 코드

| 구분 | 기록 |
|---|---|
| 설정 파생 | S1-a 진단 cfg 파생, 새 학습. 저장된 `agent.yaml`은 `[코드] seed 42`, `[코드] 1501 iterations`, `[코드] resume: false`. 부모는 설정 계보이지 S1-a 학습 체크포인트가 아님 |
| 실제 변경 | `track_lin_vel.std`와 `track_ang_vel.std`를 각각 `[코드] 0.5 → 0.25`. 둘을 하나의 동시 변경 묶음으로 취급 |
| 코드 기준 | 본 학습 로그 HEAD `[코드] 87d71df7`; 진단 코드의 저장소 상태는 변경 파일이 있어 이 커밋만으로 모든 실행 파일이 깨끗했다고 보지 않음 |
| 실행 폴더 | `logs/rsl_rl/foothold_s1a_diag/2026-10-21_04-14-45_S1a-diag-D2-kernel025`; 평가 산출물 `eval_new/diag_s1a/d2_scan_1500/feet.json`, `d2_scan_1500_turn/feet.json` |

## 검증 기록

| 확인점 | 기록 |
|---|---|
| L0 | 이 D2 학습 run에 귀속할 L0 결과 파일 미확인. 이 초안 작성 중 테스트하지 않음 |
| Kit | `run.log`에 headless Kit 기록, `rc.txt` `[실측] 0` |
| 시작 | 폴더 시각 `[실측] 04:14:45`, PID `[실측] 65176` |
| 첫 증거 | `run.log`에서 seed `[실측] 42`, `Learning iteration 0/1501` 확인 |
| 끝 | 상태 파일 `[실측] done`, `[실측] iter 1500/1501`, 종료 기록 `[실측] 06:28:51`; `run.log` 마지막 timesteps `[실측] 147,554,304` |
| 영상 | 영상 없음 · 미확인(lead 보고: 밤 촬영·판독 없음). 수치 평가만 기록 |

## 결과

영상: 영상 없음 · 미확인(이 카드의 평가 수치는 영상 판독이 아님).

| 비교 묶음 | 회차·seed | 정지 비율 | `[코드] 6 s` 전진 중앙값 | 회전 추종 | 해석 |
|---|---|---:|---:|---:|---|
| D2 1차 | `[코드] 1,500회`, `[코드] seed 42` | `[실측] 0.766 → 0.078` | `[실측] 0.19 → 1.94 m` | `[실측] 0.264 → 0.039` | 정지 개선 지지, 회전 저하 동반 |
| D2 재현 비교 | `[코드] 1,100회`, 기준·seed42·seed43 | `[실측] 0.921 → 0.203 / 0.203` | `[실측] 0.11 → 2.22 / 1.41 m` | 이 표의 1,500회 회전값과 혼합하지 않음 | 정지 감소 방향이 두 시드에서 같음. 등록한 1,500회 재현은 아님 |

두 행은 회차가 다르고 기준 정지율도 `[실측] 0.766`과 `[실측] 0.921`로 다르다. 같은 판정 분모로 합산하지 않는다. 1,100회 비교의 종료 생존은 기준·seed42·seed43 순으로 `[실측] 62/64/59`, 각 정지율 분모는 `[실측] 63/64/64`로 보고됐다. 따라서 정지율만으로 생존 개선을 주장하지 않는다.

각 지표는 #555 댓글 [6302009721](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6302009721)와 [6304255937](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304255937), `inbox/jay/20261019-design/NIGHT-REPORT-1021.md` [D]·[C5]·[C6]의 보고값이다. 원 JSON은 재집계하지 않았다. 영상 없음.

## 다음 가설

D2는 두 축을 같이 바꿔 회전 손실 원인을 분리하지 못했다. D2-s43에서 정지 감소의 재현 방향을 확인하고, D3에서 ang만 기준값으로 돌려 회전 손실이 ang 축과 연관되는지 시험한다. blind에 대한 진단은 별도이며 scan 결과를 그대로 확장하지 않는다.

## 근거

- [#555 D2 결과·후속 등록 6302009721](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6302009721), [D2-s43 1,100회 6304255937](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304255937).
- `inbox/jay/20261019-design/NIGHT-REPORT-1021.md` D2 표와 실행 로그 경로.
- sonnet-code HEAD `[코드] 87d71df7`, saved `params/agent.yaml`, `train_start_status.json`; 평가 경로 `C:/Users/AI-WS01/s2_lab/eval_new/diag_s1a/d2_scan_1500/` 및 `d2_scan_1500_turn/`.

## lead_tmp 직접 대조

아래 `feet.json`을 CPU로 읽어 저장 집계값과 표를 맞췄다. episode 원자료 재집계나 GPU 재평가는 아니다. 정지는 2~4초 평균 전진 속도 <0.05 m/s이며 분모는 그 구간 유효 env 수다. 전진은 6초 중앙값, 회전은 별도 명령 wz=1.0 rad/s의 `turn.yaw_follow_median`이다.

| 경로 (`eval_new/diag_s1a/` 아래) | 정지 비율·분모 | 전진 m 또는 회전 추종비 | SHA256 |
|---|---|---|---|
| `base_scan_1500/feet.json` | 0.765625000 · 64 | 전진 0.189848195 | `0460a3beb2e3e93e1ca4581417b5b5fb98f33b2d25220c595c95e0766a3f3d17` |
| `d2_scan_1500/feet.json` | 0.078125000 · 64 | 전진 1.939456366 | `122d68fb34ed3af5ab4c4a1cd1d218f74476321dc13decd29b9905edb5b95faa` |
| `base_scan_1500_turn/feet.json` | 해당 없음 | 회전 0.263751159 | `5a71211ac23f6b9af93fab419b4c1d8775a0548fe4f55e8f606f571732e9eacf` |
| `d2_scan_1500_turn/feet.json` | 해당 없음 | 회전 0.039473474 | `814a572e604b634c7a6f70f1f1509862d93441f5b415dc06013582d09e66b249` |
