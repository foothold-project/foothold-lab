> 분류: 실험
> 작성: 오흥재 (luna 초안 · lead_tmp 대조) · 2026-10-21
> 근거: #555 사전 등록·판정 댓글 · NIGHT-REPORT-1021.md · eval_new/diag_s1a · sonnet-code 로그
> 요지: S1-a 설정에서 v2 정의의 발 들기 항만 더한 D1은 등록한 정지·전진 개선 기준을 충족하지 못했다.
> 상태: 기록 · 진단용 새 판 · 원자료 재집계 및 독립 판정 미실시

대조 범위: 본문 초안의 `[실측]`은 저장 기록 또는 다른 세션 보고를 가리킨다. 아래 「lead_tmp 직접 대조」에 적은 항목만 이번에 직접 확인했고, 그 밖의 값은 보고값·미확인으로 읽는다.

# EX-02 D1 · 발 들기 항 단독 진단

> 원자료 재집계: `미측정`. 수치 표는 원보고와 실행 기록을 출처로 하며 이 초안에서 다시 계산하지 않았다.
실험 식별자·경로의 숫자는 이름이다. `[코드]`는 코드·설정값, `[실측]`은 기록 측정값, `[가정]`은 해석이다. 이 초안은 결과 JSON을 다시 집계하지 않았다.

## 가설과 사전 등록

> 원문: “feet_air_time +0.1 하나만 추가”

#555 댓글 [6298590512](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6298590512)는 S1-a scan과 같은 설정·seed 42에서 이 항만 추가한다고 등록했다. 평가 조건은 random_rough 높이 `[코드] 0.01~0.06 m`, 명령 `[코드] 0.5`, `[코드] 64 env`, 정지 비율과 `[코드] 6 s` 전진 중앙값이다. 지지 기준은 정지 비율이 기준의 절반 이하이고 전진 중앙값이 기준보다 `[코드] 0.5 m` 이상인 경우였다.

## 설정과 코드

| 구분 | 기록 |
|---|---|
| 설정 파생 | S1-a 진단 설정 파생. `train_start_status.json`의 저장된 PPO 설정은 `[코드] seed 42`, `[코드] 1501 iterations`, `[코드] resume: false`다. S1-a model_5999 checkpoint에서 이어 학습한 것이 아니다 |
| 실제 변경 | `feet_air_time` 가중치 `[코드] +0.1` 한 항. NIGHT-REPORT는 당시 정의의 문턱 `[코드] 0.5 s`, 측정 항 값 `[실측] -0.006`을 보고한다 |
| 코드 기준 | 10/24 직접 정정: 실제 본 실행 바깥 폴더 `logs/s1a_diag_D1_20261021_035030/git_head.txt`는 `e6541c996112be0723e9f0fff7dc2f963334fef1`, 같은 폴더 `git_status.txt`는 빈 파일이다. 이 폴더 run.log가 Kit `03:50:35`와 Isaac Lab `03:50:41`, 0/1501 학습을 연결한다. 이전 c07fff1e·dirty 서술은 앞선 03:50:04 시도와 본 실행의 출처를 혼동했으므로 철회한다. 시작 이후 바이트 변경 전체의 부재까지 이 두 파일로 보장하지는 않는다 |
| 실행 폴더 | `logs/rsl_rl/foothold_s1a_diag/2026-10-21_03-50-41_S1a-diag-D1`; 측정 산출물은 `eval_new/diag_s1a/d1_scan_1500/feet.json` |

## 검증 기록

| 확인점 | 기록 |
|---|---|
| L0 | 이 D1 run에 귀속할 L0 결과 파일 미확인. 이 초안 작성 중 테스트하지 않음 |
| Kit | `run.log`에 headless Kit 시작, 실행 로그 `rc.txt` `[실측] 0` |
| 시작 | 폴더 시각 `[실측] 03:50:41`, PID `[실측] 74216` |
| 첫 증거 | `run.log`에서 seed `[실측] 42`, `Learning iteration 0/1501` 확인 |
| 끝 | 상태 파일 `[실측] done`, `[실측] iter 1500/1501`, 종료 기록 `[실측] 05:52:02`; `run.log` 마지막 timesteps `[실측] 147,554,304` |
| 영상 | 영상 없음 · 미확인(lead 보고: 밤 촬영·판독 없음). 보고 수치를 영상 판독으로 설명하지 않음 |

## 결과

영상: 영상 없음 · 미확인(이 카드의 평가 수치는 영상 판독이 아님).

| 지표 | S1-a scan 기준 | D1 | 판정 |
|---|---:|---:|---|
| 정지 비율 | `[실측] 0.766` | `[실측] 0.688` | 지지선 `[코드] ≤0.383`보다 큼 |
| `[코드] 6 s` 전진 중앙값 | `[실측] 0.19 m` | `[실측] 0.27 m` | 지지선 `[코드] ≥0.69 m`보다 작음 |
| 스윙 발 높이 | `[실측] 0.9 cm` | `[실측] 2.1 cm` | 보조 기록, 사전등록 성공조건 아님 |
| terrain_levels | `[실측] 3.87` | `[실측] 3.74` | 보조 기록 |

#555 사전 등록 판정은 기각이다. 정확히는 v2 정의의 `feet_air_time` 설정 추가가 주원인이라는 가설을 지지하지 못했다. 발 들기 장려 일반을 부정하는 결과는 아니다. 보고 수치는 #555 댓글 [6301263269](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6301263269)와 `inbox/jay/20261019-design/NIGHT-REPORT-1021.md`의 [D]·[C4]에서 인용했으며 원 JSON 재집계는 미실시다.

## 다음 가설

발 들기 항만으로 설명되지 않으므로, 추종 오차가 큰 상태에서도 보상이 남는 폭을 줄이면 정지 흡수가 완화되는가를 D2에서 본다. D2는 선속도와 회전 추종 std를 함께 바꾸므로 그 결과만으로 축별 원인을 나누지는 않는다.

## 근거

- [#555 D1 등록 6298590512](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6298590512), [D1 판정 6301263269](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6301263269).
- `inbox/jay/20261019-design/NIGHT-REPORT-1021.md`의 D1 행.
- sonnet-code 본 실행 HEAD `[코드] e6541c99`, `logs/s1a_diag_D1_20261021_035030/`의 run log·git_head·git_status 및 `train_start_status.json`; 측정 결과 경로 `C:/Users/AI-WS01/s2_lab/eval_new/diag_s1a/d1_scan_1500/`. [10/24 파일별 SHA와 저장 설정 대조](../20261023-experiments/figs/history-audit-1024/s1_saved_evidence.json).

## lead_tmp 직접 대조

아래 `feet.json`을 CPU로 읽어 저장 집계값과 표를 맞췄다. episode 원자료 재집계나 GPU 재평가는 아니다. 정지는 2~4초 평균 전진 속도 <0.05 m/s이며 분모는 그 구간 유효 env 수다. 전진은 6초 중앙값, 회전은 별도 명령 wz=1.0 rad/s의 `turn.yaw_follow_median`이다.

| 경로 (`eval_new/diag_s1a/` 아래) | 정지 비율·분모 | 전진 m 또는 회전 추종비 | SHA256 |
|---|---|---|---|
| `base_scan_1500/feet.json` | 0.765625000 · 64 | 전진 0.189848195 | `0460a3beb2e3e93e1ca4581417b5b5fb98f33b2d25220c595c95e0766a3f3d17` |
| `d1_scan_1500/feet.json` | 0.687500000 · 64 | 전진 0.267493236 | `20f97e2dbb75bae3387983250d52a07fa0508b9058b8ba1a6668156f27fc071a` |
