# EX-40 7단계 점수기 저장본·종료 계약
> 분류: A/평가
> 작성: 오흥재 · 2026-10-30
> 근거: `EX40-BASIC-GAIT-STAGES.md` 278~288행, runner v7 `c3b08c44`, 점수기 Kit 짧은 확인 2차 PASS 보고, `start_runner.py` 저장 경로와 `manifest.py`
> 요지: 250회 저장본의 SHA 확정, 늦은 점수 원장, 7단계 경계 평가, m6500 뒤 잔여 평가 완료 조건을 연결했다.
> 상태: CPU 검사 완료 · 새 고정 사본의 실제 Kit 장기 실행 미확인
> 판: v1.0

## 적용 범위

새 작업 사본 `C:/mai/wt/foothold-lab/scripter-ex40-score-v7`은 runner v7 `c3b08c44`에 점수기 `91d28e6d`와 Kit 인자 수정 `647a4aa2`를 각각 새 커밋으로 적용한 뒤 이번 수정을 더했다. 도는 학습·평가 사본은 건드리지 않았다. runner v7 YAML의 일곱 단계 `B0, B1, B2, B3a, B3b, B3c, T0`와 단계 끝 저장본 `1500, 3000, 4500, 5000, 5500, 6000, 6500`을 코드가 대조한다.

| 지적 | 변경 | 답 아는 CPU 입력 |
|---|---|---|
| (a) 파일 존재만으로 예약 | `manifest.json`의 완료 회차와 `checkpoints.model_N.pt` SHA를 읽고, 파일 크기·SHA를 두 번 재서 일치할 때만 평가한다. 한 번호는 원장 한 행이며 중복 행은 거절한다. | manifest 소실, 파일 변조, 측정 중 재작성, 중복 행 거절 |
| (b) 늦은 점수 | 저장본 번호 당시의 `stage_enter`를 찾아 점수기 단독 `score_ledger.jsonl`에 단계·SHA·점수 경로를 `fsync`로 기록한다. `stage_log.jsonl`은 읽기 참조만 한다. T0 점수도 점수 디렉터리에 내보낸다. | m1500 점수를 B1 입장 뒤 B0로 기록, 재시작 뒤 원장으로 중복 없이 복원, 원본 stage_log 바이트 동일 |
| (c) 최종 종료 | 6500 파일·SHA, 학습 `done`·iter6500·manifest 완료6501, 500부터 6500까지 250 간격 25개 점수와 각 평가 영수증·출력을 확인한 뒤 `watch_completion.json`을 쓴다. 하나라도 평가가 남으면 계속 기다린다. HOLD는 모든 남은 저장본을 처리한 뒤 종료 코드 5로 남긴다. | running, 최종 점수 결측, HOLD와 결측 동시, 최종 증거 소실 반례 |
| (d) 단계 끝 평가 | 단계 끝 7개는 건너뛰지 않는다. 현재 감시기는 어느 250회 저장본도 건너뛰지 않는다. 경계에서는 W15 전체 13명령×3모드, 정지 3모드, W57 결과를 필수로 검사한다. B0/B1 경계도 W57 기록을 요구하며 해당 단계에서 W57 수치 문턱은 새로 만들지 않았다. | m1500 W57 소실은 HOLD, 경계 출력 소실은 완료 거절, T0 최종 점수 보존 |

학습이 쓰는 `stage_log.jsonl`에는 점수기가 쓰지 않는다. 점수기가 내보낸 `score_N_*.json`은 학습 측의 기존 읽기 경로와 호환되며, 지난 단계 점수와 T0 점수의 사후 이력은 독립 원장에 남는다. 점수기 사본 이전의 `watch_state.json`에는 이 원장이 없으므로 기존 감시 루트에 덮어 시작하지 않는다.

## 확인 결과와 한계

`C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -m pytest -q foothold_s2/tests/test_ex40_v4_cpu.py foothold_s2/tests/test_w55_continuous_cpu.py foothold_s2/tests/test_ex40_scorer_cpu.py foothold_s2/tests/test_ex40_kit_argv_cpu.py foothold_s2/tests/test_axis_v2_run_cpu.py foothold_s2/tests/test_axis_v2_cells.py foothold_s2/tests/test_ex40_v7_continue_cpu.py`: **67 passed**. 변경 Python 파일의 `ruff check --select F`: **All checks passed!**. `git diff --check` 이상 없음. GPU와 Kit는 실행하지 않았다. Kit 2차 PASS는 이전 점수기 인자 수정 사본의 결과이며 이번 7단계 감시·종료 경로에 대한 Kit 증거는 아니다.

단계별 W57의 문턱은 기존 `axis_goal`이 켜진 단계에만 적용한다. B0/B1 경계에서 W57은 필수 기록으로만 검사한다. 점수기의 모든 250회 평가가 실제 GPU1 시간 예산 안에 들어오는지는 미측정이다. 평가 자식이 HOLD를 냈다면 최종 완료로 게시하지 않고 운영자가 해당 점수를 확인해야 한다. SHA 목록은 `EX40-SCORER-V7-SHA256SUMS.txt`다.
