> 분류: 리서치
> 작성: jay · 2026-10-21
> 근거: #555 등록·판정 댓글 · NIGHT-REPORT-1021.md · eval_new/diag_s1a · sonnet-code 로그
> 요지: D3는 D2 대비 선속도 커널만 좁히고 회전 커널을 되돌렸으나 정지·전진·회전 등록 조건을 통과하지 못했다.
> 상태: 초안 · 진단용 새 판 · 원자료 재집계 및 독립 판정 미실시

# D3 · 선속도만 좁힌 커널

> 원자료 재집계: `미측정`. 수치 표는 원보고와 실행 기록을 출처로 하며 이 초안에서 다시 계산하지 않았다.
실험 식별자·경로의 숫자는 이름이다. `[코드]`는 설정·기준값, `[실측]`은 기록된 결과, `[가정]`은 해석이다. 원자료를 다시 집계하지 않았다.

## 가설과 사전 등록

> 원문: “D3 = lin 0.25 · ang 0.5(회전 저하가 ang 커널 탓인지)”

#555 댓글 [6302009721](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6302009721)는 D2에서 나빠진 회전 추종이 ang 커널 때문인지 보기 위해 D3를 등록했다. 판정선은 정지 `[코드] ≤0.383`, `[코드] 6 s` 전진 `[코드] ≥0.69 m`, 회전 추종 `[코드] ≥0.264`다.

## 설정과 코드

| 구분 | 기록 |
|---|---|
| 설정 파생 | S1-a 진단 cfg 파생, 새 학습. 저장된 설정 `[코드] seed 42`, `[코드] 1501 iterations`, `[코드] resume: false`. S1-a 모델 체크포인트 이어받기 아님 |
| D2 대비 변경 | lin std는 `[코드] 0.25`로 유지. ang std만 `[코드] 0.25 → 0.5`로 되돌림. 즉 D2와 D3 차이는 ang 축 한 항목 |
| 코드 기준 | 실행 HEAD `[코드] 2fbac752`; 저장소 상태에 진단 파일 변경 기록이 있어 커밋만으로 전체 실행 파일이 clean이었다고 간주하지 않음 |
| 실행 폴더 | `logs/rsl_rl/foothold_s1a_diag/2026-10-21_06-36-49_S1a-diag-D3-lin025-ang05`; 결과 `eval_new/diag_s1a/d3_scan_1500/feet.json`, `d3_scan_1500_turn1/feet.json` |

## 검증 기록

| 확인점 | 기록 |
|---|---|
| L0 | 해당 D3 run의 L0 결과 파일 미확인. 이 카드 작성 중 테스트하지 않음 |
| Kit | `run.log` headless Kit 기록, `rc.txt` `[실측] 0` |
| 시작 | 폴더 시각 `[실측] 06:36:49`, PID `[실측] 76708` |
| 첫 증거 | `run.log`에 seed `[실측] 42`, `Learning iteration 0/1501` |
| 끝 | 상태 `[실측] done`, `[실측] iter 1500/1501`, 종료 기록 `[실측] 08:54:57`; 마지막 timesteps `[실측] 147,554,304` |
| 영상 | lead 확인상 밤 보행 영상 없음 |

## 결과

| 지표 | 등록 기준 | D3 값 | 판정 |
|---|---:|---:|---|
| 정지 비율 | `[코드] ≤0.383` | `[실측] 0.766` | 불통과 |
| `[코드] 6 s` 전진 중앙값 | `[코드] ≥0.69 m` | `[실측] 0.56 m` | 불통과 |
| 회전 추종 | `[코드] ≥0.264` | `[실측] 0.230` | 불통과 |
| 비교할 D2 회전 손실 | `[실측] D2 0.264 → 0.039` at `[코드] 1,500회` | D3 `[실측] 0.230` | 회전만 보면 D2보다 높지만 정지·전진은 기준 미달. ang 원인의 단독 증명 아님 |

D3의 `[실측] 0.766`은 D2의 `[실측] 1,500회 seed42 0.078`과 동일 실험 결과가 아니다. D3는 선속도만 좁혔기 때문에 두 설정 조합의 전체 차이가 존재한다. 결과는 #555 댓글 [6304758796](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304758796) 및 `NIGHT-REPORT-1021.md` [D]·[C7]의 보고값이다. 원 JSON 재집계 없음. 영상 없음.

## 다음 가설

D3는 lin만 좁힌 구성에서 정지 개선 기준을 못 넘었다. 따라서 #555 결정은 D2의 lin·ang 동시 축소를 회복 처방의 일부로 유지하고, `foot_below_ground` 여유와 `clip_actions`를 함께 넣는 세 변경 본 학습에서 중간 성능을 확인하는 것이다. 세 변경이 묶여 있으므로 어느 한 항목의 단독 효과를 주장할 수 없다.

## 근거

- [#555 D2·D3 등록 6302009721](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6302009721), [D3 결과·세 변경 결정 6304758796](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304758796).
- `inbox/jay/20261019-design/NIGHT-REPORT-1021.md` D3 표 및 근거 경로.
- sonnet-code HEAD `[코드] 2fbac752`, saved `params/agent.yaml`, `train_start_status.json`; 결과 `C:/Users/AI-WS01/s2_lab/eval_new/diag_s1a/d3_scan_1500/`.
