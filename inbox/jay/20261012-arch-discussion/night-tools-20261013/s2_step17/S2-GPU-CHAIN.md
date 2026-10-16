# S2 네 노드 참석 실행 연결표
> 분류: A/정책학습
> 작성: sol · 2026-10-16
> 근거: VERIFY-astra-17ai.md 3절 · TASK-codex-worker-s2-launchers-n3-n4.md · 기존 참석 기동기 A3.4/B12
> 요지: 네 단회를 노드별 독립 봉인·관찰·원자료 확인으로 잇고, 앞 노드 결함에 따라 다음 노드를 멈춘다.
> 상태: CPU 도구 및 모의 시험 확인됨 · 실제 GPU/Kit 실행 미확인

## 순서와 독립 경계

1. A3.4 수집, `s2_attended_launch_a34.py`. 기존 lead 도구. 최대 실행 wall 900초.
2. 배관 재시도, `s2_attended_launch_b12.py`. 기존 lead 도구. 최대 실행 wall 600초.
3. 평가기 update 0 연결, `launch/s2_attended_launch_eval0.py`. 최대 실행 wall 900초. A/B의 새 S2 체크포인트 2개, gap 2와 stepping_stones 2 case. 정보 수집만 한다.
4. 발 광선 확인, `launch/s2_attended_launch_foot.py`. 최대 실행 wall 900초. 8장면, N=2, 각 2~37 step, 총 300 step 이하. 학습과 optimizer는 0이다.

네 실행 wall 상한의 합은 3300초, 즉 55분이다. 체크포인트 생성, Kit 시작, prelaunch, watchdog/관찰자 정리, 노드 사이 lead의 확인 시간은 미측정이다. 따라서 55분을 전체 참석 시간의 상한이나 완료 예상치로 쓰지 않는다. 앞의 두 도구는 각자 1500초 deadline slack도 쓰므로 실제 마감과 실행 wall을 구별해야 한다. 노드 3과 4는 manifest 마감과 실행 wall을 동일하게 900초 이하로 봉인한다.

각 노드는 고유한 새 `runs/<node>-.../`을 쓰며, `in/manifest.json`, 코드 폐쇄 SHA, 입력 SHA, 단회 claim, `ctl/STOP`, `ctl/status.json`, `ctl/prelaunch.json`, 관찰자 등록·log, supervisor receipt와 자식 원자료를 분리한다. 각 노드는 `--rehearse`로 먼저 봉인·prelaunch GO까지만 확인한다. 실제 참석 실행은 노드 scope가 정확한 직접 동의 파일, `--live --attendee NAME --confirm LAUNCH-ATTENDED`를 받아야 한다. 이 도구들은 승인 파일을 배포하지 않고 live 시도 안에서만 생성한다. 자동 재시도나 다음 노드 자동 시작은 없다.

## 노드 사이 lead 확인 원자료

| 확인 | 파일과 내용 |
|---|---|
| 예정 대비 실행 | 각 노드 `in/manifest.json`, 입력 SHA, `ctl/prelaunch.json`, 감독기 `ctl/status.json`, claim receipt, `summary.json`. 예정/실행/skip/HOLD와 실제 argv·해석기·import·GPU를 대조한다. |
| 시간과 소유 | watchdog 등록·log, supervisor와 child PID 생성시각, 시작/종료/단계 시각, STOP/마감, 가족 잔존 0, lease와 USD lock 반납, 독립 `family_observation.json`. |
| A3.4 | 수집 raw pose/ray/USD/시간·reset·hash, 고정 pose 준비 결과, 해당 단회 영수증. |
| 배관 | 실제 32 env·2 step의 shape/load/기본 환경 생성, 입력 센서·지도·관측·optimizer raw, bundle hash, 정리 영수증. |
| 평가기 | `in/checkpoint_{A,B}_update000000.pt`와 SHA, `checkpoint_receipt.json`의 update/optimizer/forward, `in/job.json`, `in/cases.json`, `out/episodes.json`, eval receipt. 평가 seed가 학습 seed와 분리되고 실제 mesh·초기상태·명령 지문이 짝을 이루는지 확인한다. |
| 발 광선 | `in/request.json`, `out/foot_result.json`, foot receipt. 36 ray와 현재 USD 충돌 mesh/중심, 같은 단계의 pose·force·hit, 자연/부분 reset, RewardManager 실제 항과 누적을 분석 정답과 대조한다. |

다음 노드 전 lead는 원자료 경로와 해시, CPU 예상 답과 실제 결과, skip/HOLD 이유, 다음 노드가 가능한 근거를 별도 참석 기록에 남긴다. 독립 관찰자는 다른 PID의 watchdog 준비·생존·종료를 확인한다. watchdog 생존만으로 과학적 합격을 선언하지 않는다.

## 앞 노드 결과별 뒤 노드 처리

아래 표는 `VERIFY-astra-17ai.md` 3절의 분기를 그대로 옮겼다. 결과를 본 뒤 유리한 쪽으로 분기를 바꾸지 않는다.

| 앞 결과 | 뒤 노드 처리 |
|---|---|
| 자산/입력 hash 변경, 장치·USD·잠금·정리 실패, watchdog 상실, STOP/마감, 원인 미확인 crash | 공통 실행 기반을 쓰는 뒤 노드는 중단. 재시도 소모 여부를 따로 남김 |
| A3.4 고정 pose 준비 조건만 실패, 공통 운영 기반 정상 | 17ah처럼 독립인 합성 배관은 사전에 정한 분기에서 가능. 지도 효과 short의 근거로 승격하지 않음 |
| 배관 shape·load·기본 환경 생성 실패 | 같은 경로를 쓰는 평가/학습 차단. 독립인 발 진단까지 차단할지는 결함 의존성으로 판단 |
| 평가기의 지표/짝 지문만 HOLD, 공통 환경과 cleanup 정상 | 별도 구현·동의된 발 진단은 가능. 평가 성공이나 full 평가 허용으로 쓰지 않음 |
| 발 광선 geometry·reward/reset HOLD | reward-off A0/B0의 독립 근거를 훼손하지 않는 한 준비는 계속 가능. A1/B1은 차단 |

## lead 리허설 입력

두 새 도구는 `--max-wall-s`와 네 자원 값 `--min-free-vram-bytes`, `--running-floor-vram-bytes`, `--min-free-disk-bytes`, `--max-disk-bytes`를 필수로 받는다. 발 도구는 `--seed`와 `--steps-per-scene`도 필수다. 이 값은 사용자가 정한 실행값 그대로 manifest에 기록된다. 노드 3의 평가 seed는 도구 상수 3101, 3109, 3119, 3121이다. 실행 전 학습 seed 집합과 다시 대조한다.

실제 GPU 0 identity/free VRAM, 임대와 USD 잠금은 `--rehearse`에서 lead가 확인해야 한다. 이 작업에서는 GPU 및 Isaac을 실행하지 않았으므로 실제 GO, 실제 평가 물리 결과와 발 광선 결과는 미확인이다.
