# E4 · E5 출구 원자료 소비 계약

> 분류: A/평가
> 작성: 오흥재 · 2026-11-12
> 근거: lead-lx 11/12 E4/E5 배정 · CURRICULUM-GATES v0.17b E4/E5 · scripter b97d60ce 공통 서명
> 요지: 논문 과제와 후진·옆걸음의 NPZ를 다시 계산하고, 빠진 공통 근거는 HOLD로 남긴다.
> 상태: 공통 소비자 연결 · CPU 확인 · Kit 미실행
> 판: v0.2

## 평가 요청과 원자료

`foothold_s2.eval.ex42_late_stage_tasks.requirements(plan, stage_id)`가 필요한 평가 목록을 만든다. 정적 계획은 준비 목록이며, 실제 학습 노출이나 졸업 증거가 아니다. 실제 노출 영수증은 scripter의 단계 공통 소비자에서 다시 계산해야 한다.

각 평가 폴더는 `evaluation/task_cells/<family>_<kind>_L<level>_<group>/`다. 그 안에 기존 `ex42_task_suite.create_request`가 만든 `request.json`, `result/task_cells.json`, 모드별 JSON과 NPZ를 둔다. 방향 평지 짝은 같은 폴더의 `flat_result/`다. 체크포인트·시드·모드·명령·시간이 같은 평지 짝이어야 한다.

| 단계 | 새 과제 | 이미 정해진 판정 | 원자료 소비 |
|---|---|---|---|
| E4 | 경사 30/35도, 전진 계단 0.15/0.20/0.25 m, 후진 계단 0.10 m | 정답·복원 판정, 끔 기록 | 6종 각각 실제 기하에서 계산한 완주 시간과 NPZ를 대조 |
| E5 | 노출 종류 대표 레벨의 후진·옆좌·옆우 | 동일 평지 명령 투영거리 중앙값의 50% 이상, 생존 60/64; 유효 48 하한과 비례 문턱 | 각 300 step, 같은 조건의 평지 짝 NPZ와 함께 재집계 |
| E5 전진 300 step | 방향 기록 | 기록만 | 완주·깃발 두 창의 대체물이 아님 |

E5 첫 방향 창은 기록만이다. 첫 창을 나중에 PASS로 바꾸지 않는다. 두 개의 판정 창을 요구하면 가장 이른 출구는 세 번째 경계다. 이것은 기존 첫 창 기록 규칙과 두 창 규칙을 함께 적용한 해석이며, 변경 결정이 오면 코드·시험을 함께 고친다.

## 공통 소비자

scripter b97d60ce 서명:

```python
judge_two_boundaries(checkpoint, *, stage_id, plan, plan_sha256,
                     interval, min_episodes, previous_kind_pass=False,
                     registered_kind_passes=None)
compare(now, previous, *, measured, baseline, kind_now, kind_previous,
        stage_id=None, kind_score_key='e2_kind',
        kind_subcells=('forward', 'flag_four'))
```

추가로 필요한 실제 근거는 열린 종류·대표 레벨, 종류별 전진·깃발 원자료, 단계 공통 유지·교환 감시다. 공통 소비자나 원자료가 없으면 HOLD다. 이름을 등록했거나 정적 계획의 목표 레벨에 도달했다고 적혀 있다는 사실로 PASS를 만들지 않는다.

## 확인 범위

`확인됨`: 실제 CPU NPZ 고정물로 80% 이동 통과, 49% 실패, 첫 창 기록, 원자료/시드/단계/계획/메시 불일치 HOLD, 잘린 NPZ HOLD, 논문 과제 기하별 시간 대조, 직전 경계 건너뛰기 거절을 확인했다. 합격 수는 최종 보고서에 시험 원문으로 적는다.

`미측정`: E4/E5 Kit 평가. 학습과 운영 파일은 바꾸지 않았다.

근거: [CG E4/E5](https://github.com/foothold-project/foothold-lab/blob/feature/fable-25a-jay/inbox/jay/20261026-experiments/CURRICULUM-GATES.md), [작업 #729](https://github.com/foothold-project/foothold-lab/issues/729).

## StageJudge 연결 (v0.2 · 공통 소비자 연결됨)

`ex42_late_stage_judge.common_inputs`는 더 이상 선택적 E3 함수를 기다리지 않는다. E3 공통 읽개(`ex42_stage_kind_bundle.read_e3_window`, `read_stage_kind_bundle`, `ex42_e3_judge._mesh`)를 단계 id 인자로 재사용하는 `eval/ex42_late_stage_kinds.py`가 다음을 원자료에서 다시 센다.

- 열린 종류: 그 단계의 학습 노출 영수증(`read_stage_exposure(stage_id=E4/E5)`). 정적 계획의 목표 레벨은 노출 증거가 아니다. 영수증이 없으면 `exposure` HOLD이고 원자료를 읽지 않는다.
- 레벨 목표: prep `evaluation.late_kind_exit`(E4: 연 종류 전부 L3 이상 · 확장 E 경사 L6 · 이미 높은 상한은 낮추지 않음 / E5: 현재 상한 유지). 선언된 종류가 안 열렸거나 낮으면 `level_targets` HOLD. 모든 칸이 PASS여도 이것이 HOLD면 출구 HOLD.
- 대표 레벨 칸: L0 · L5 · 현재 상한. 칸마다 전진 NPZ와 깃발 NPZ(연속 A는 단계 전역 flag_four)를 두 판정 모드로 다시 세어 `kind_current`, 직전 창은 `kind_previous`.
- `learned_cells`: 실행 계획 SHA(점수의 `execution_plan_sha256`)와 직전 창 원자료 통과 종류로 `judge_two_boundaries`. 문턱 32는 prep `late_kind_exit.learned_cells_min`(CG:480 일반값 · **가정**).
- `exchange_watch`: 두 창에 공통인 칸마다 `compare(kind_score_key='late_kind')`. 비교할 직전 칸이 없으면 HOLD.
- 자식 실행: `ex42_eval_once`가 E4/E5 경계에서 `ex42_task_suite` 자식(E4 paper 6종 · E5 directions)과 종류 자식(`kind_cells_e4` / `kind_cells_e5`)을 띄우고, 자식 실패는 표식 파일 HOLD다.

승인 파일(`ex42-approvals.yaml`)은 바꾸지 않았다. 문턱을 승인 칸이 아니라 prep에 둔 것은 E4/E5 승인 칸에 `exit_gate`가 없기 때문이며, prep SHA가 바뀌므로 재고정은 lead 몫이다.
