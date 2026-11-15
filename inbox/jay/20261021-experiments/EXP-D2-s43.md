> 분류: 실험
> 작성: 오흥재 (luna 초안 · lead_tmp 대조) · 2026-10-21
> 근거: #555 댓글 · NIGHT-REPORT-1021.md · eval_new/diag_s1a · sonnet-code 로그
> 요지: seed 43 판은 발산으로 등록 회차를 채우지 못했으며, 1,100회 정지 비교와 clip17 짧은 재검사를 각각 기록한다.
> 상태: 기록 · D2 재현 시도와 후속 원인 진단을 분리 · 장기 안정성 미확인

대조 범위: 본문 초안의 `[실측]`은 저장 기록 또는 다른 세션 보고를 가리킨다. 아래 「lead_tmp 직접 대조」에 적은 항목만 이번에 직접 확인했고, 그 밖의 값은 보고값·미확인으로 읽는다.

# EX-04 D2-s43 · 두 번째 시드와 발산 진단

> 원자료 재집계: `미측정`. 수치 표는 원보고와 실행 기록을 출처로 하며 이 초안에서 다시 계산하지 않았다.
실험 식별자·경로의 숫자는 이름이다. `[코드]`는 코드·설정값, `[실측]`은 기록 측정값, `[가정]`은 해석이다. 이 초안에서 원 JSON·체크포인트를 재분석하지 않았다.

## 가설과 사전 등록

> 원문: “D2-s43 = D2 그대로 시드 43(재현)”

#555 댓글 [6302009721](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6302009721)은 D2와 같은 scan 설정에서 seed만 `[코드] 43`으로 바꾼 `[코드] 1,501회` 재현 판을 등록했다. 등록된 판정 수를 채우지 못하면 D2의 효과를 같은 정밀도로 재현했다고 쓰지 않는 것이 경계다.

## 설정과 코드

| 구분 | 기록 |
|---|---|
| 초기 판 | D2 설정 파생, saved `agent.yaml`은 `[코드] seed 43`, `[코드] 1501 iterations`, `[코드] resume: false`. 초기 판은 S1-a checkpoint 이어 학습이 아님 |
| 발산 뒤 재개 | #555 보고는 같은 seed43 run의 `latest` `[실측] model_1100`에서 다시 시작했다고 적음. 해당 후속 run의 saved `agent.yaml`도 `[코드] resume: false`라서 실제 checkpoint 로더 경로는 이 설정만으로 설명되지 않는다. S1-a model_5999를 부모로 삼았다는 증거도 없음 |
| 실제 설정 변화 | 재현 판의 본 처방 변화 없음. 후속 원인 확인에서 `clip_actions` `[코드] 17`을 넣어 model_1100부터 짧게 재검사 |
| 코드 기준 | 초기 실행 폴더 기록 HEAD `[코드] 2fbac752`; 후속 clip 설정 코드 `[코드] e6efed92`. 원인 분석 기록은 `eval_new/diag_s1a/blowup`, clip 결과는 `blowup_clip17` |
| 실행 폴더 | `logs/rsl_rl/foothold_s1a_diag/2026-10-21_06-36-49_S1a-diag-D2-s43`; 재개·발산·clip run의 상세는 NIGHT-REPORT 및 #555 댓글 참조 |

## 검증 기록

| 확인점 | 기록 |
|---|---|
| L0 | 재현 및 clip 후속 판에 귀속하는 L0 결과 파일 미확인. 이 초안 작성 중 테스트하지 않음 |
| Kit | 초기 run.log에 headless Kit 실행. 발산 판은 정상 완료로 보지 않음. 후속 clip 로그 `rc.txt` `[실측] 0`은 단기 테스트 종료 코드 |
| 시작 | 초기 폴더 시각 `[실측] 06:36:49`, PID `[실측] 49464`로 저장된 상태 기록에 나타남. 재개 run은 별도 PID·폴더이며 동일 실행으로 합치지 않음 |
| 첫 증거 | 원인 분석 보고는 iteration `[실측] 1115~1125`에서 value loss 발산을 기록. 세부 최초 iteration은 범위로 보존 |
| 끝 | lead 보고상 `[실측] 08:11`경 종료, 저장 상태 스냅샷은 iteration `[실측] 1120`을 나타냄. 등록 `[코드] 1501회` 미달. 1100에서 재개한 뒤 같은 구간의 재발산 보고로 학습 종료 |
| clip 후속 | lead 보고는 model_1100에서 clip17로 `[코드] 1100~1130회` 재검사했다고 기록. saved `agent.yaml`의 `resume: false`와 로더 선택 관계는 미확인. 스텝 보상 `< -100`은 `[실측] 0건` 보고. 해당 짧은 구간 밖 장기 무발산은 미확인 |
| 영상 | 영상 없음 · 미확인(lead 보고: 밤 촬영·판독 없음) |

## 결과

영상: 영상 없음 · 미확인(이 카드의 평가 수치는 영상 판독이 아님).

| 비교 구분 | 회차·분모 | 정지 비율 | `[코드] 6 s` 전진 중앙값 | 의미 |
|---|---|---:|---:|---|
| D2 기준 scan | `[코드] 1,100회`, seed42 | `[실측] 0.921` | `[실측] 0.11 m` | D2-s43과 같은 회차 비교의 기준 |
| D2 seed42 | `[코드] 1,100회`, 분모 `[실측] 64` | `[실측] 0.203` | `[실측] 2.22 m` | 기준과 별도 seed 판 |
| D2-s43 | `[코드] 1,100회`, 분모 `[실측] 64` | `[실측] 0.203` | `[실측] 1.41 m` | 정지 감소 방향 재현. 등록 `[코드] 1,500회` 재현 아님 |
| 생존·정지 분모 | 기준·seed42·seed43 | 종료 생존 `[실측] 62/64/59`; 정지율 분모 `[실측] 63/64/64` | 해당 없음 | 분모와 생존 수가 다름 |
| 발산 | seed43 학습 | `[실측]` value loss `[실측] 0.05 → inf`, 한 env step reward `[실측] -7e7` 보고 | 해당 없음 | 물리 폭주로 단정하지 않음 |
| 원인·완화 시험 | blowup 분석 및 clip17 후속 | 평균 절대 action `[실측] 251 → 4042` / `[실측] 49 steps`; action_rate 벌점 `[실측] -6426`, 총 보상의 `[실측] 99.9%`라고 보고 | clip17 단기 run에서 `< -100` `[실측] 0건` | clip 효과의 장기 재현은 미확인 |

값은 #555 댓글 [6304255937](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304255937), [6304310458](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304310458) 및 `inbox/jay/20261019-design/NIGHT-REPORT-1021.md` [D]·[C6]에서 인용했다. 보고된 action 증가 원인은 관측·되먹임에 관한 추정이다. 물리 속도·토크·자세 정상 및 NaN 없음이라는 보고만으로 모든 학습 불안정 원인을 제거하지 않는다. 원자료 재계산은 하지 않았다.

## 다음 가설

D2-s43은 두 시드의 `[실측] 1,100회` 비교에서 정지 감소 방향을 보였지만 등록 `[코드] 1,500회` 완주 재현은 실패했다. D3로 ang 축만 되돌려 회전 추종 손실을 분리하고, 본 학습 처방의 `clip_actions` 효과는 별도 평가에서 장기 안정성과 보행 성능을 함께 확인해야 한다.

## 근거

- [#555 D2·D2-s43 등록 6302009721](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6302009721), [발산·1,100회 비교 6304255937](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304255937), [action 원인·clip17 단기 확인 6304310458](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304310458).
- `inbox/jay/20261019-design/NIGHT-REPORT-1021.md` [D]·[C6].
- sonnet-code `logs/rsl_rl/foothold_s1a_diag/2026-10-21_06-36-49_S1a-diag-D2-s43`; 원인 진단 및 clip 기록 경로 `C:/Users/AI-WS01/s2_lab/eval_new/diag_s1a/blowup/`, `blowup_clip17/`.

## lead_tmp 직접 대조

아래 `feet.json`을 CPU로 읽어 저장 집계값과 표를 맞췄다. episode 원자료 재집계나 GPU 재평가는 아니다. 정지는 2~4초 평균 전진 속도 <0.05 m/s이며 분모는 그 구간 유효 env 수다. 전진은 6초 중앙값, 회전은 별도 명령 wz=1.0 rad/s의 `turn.yaw_follow_median`이다.

| 경로 (`eval_new/diag_s1a/` 아래) | 정지 비율·분모 | 전진 m 또는 회전 추종비 | SHA256 |
|---|---|---|---|
| `base_scan_1100/feet.json` | 0.920634921 · 63 | 전진 0.105776137 | `ee7bc00c8f5f898d282d0ffd8430861029a70fbf75aafb9c30ec158407763393` |
| `d2_scan_1100/feet.json` | 0.203125000 · 64 | 전진 2.216363789 | `d0b97db1b42edf69a29d33f2a4e70fb1e873f83977a692670c70753c8dd7e8f6` |
| `d2s43_scan_1100/feet.json` | 0.203125000 · 64 | 전진 1.414587898 | `edf0e2d56f0d1c75f48917b04893ccb198a2857a5f27ce697d248cb23643846a` |

원 보고의 전진 1.42 m는 저장 값 1.414587898 m와 반올림이 다르므로 표를 **1.41 m**로 바로잡았다. 종료 생존은 기준·seed42·seed43 각각 62·64·59, 정지 분모는 63·64·64임을 JSON에서 확인했다. seed43 상태 파일은 08:11:06의 running·iter1120에 멈춰 있다. 이것만으로 현재 실행 중이라고 읽지 않는다. clip 후속 1100~1130의 종료 코드 보고와 `blowup_clip17`의 events=[]는 다른 증거다. 특정 재학습의 장기 안정성을 확인했다는 뜻이 아니다.
