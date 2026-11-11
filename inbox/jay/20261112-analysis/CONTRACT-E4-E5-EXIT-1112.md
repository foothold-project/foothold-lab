# E4 · E5 출구 원자료 소비 계약

> 분류: A/평가
> 작성: 오흥재 · 2026-11-12
> 근거: lead-lx 11/12 E4/E5 배정 · CURRICULUM-GATES v0.17b E4/E5 · scripter b97d60ce 공통 서명
> 요지: 논문 과제와 후진·옆걸음의 NPZ를 다시 계산하고, 빠진 공통 근거는 HOLD로 남긴다.
> 상태: 구현 중 · CPU 확인 · Kit 미실행
> 판: v0.1

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

## StageJudge 연결 포트 (E3 소비자 구현 대기)

`ex42_late_stage_judge.LateKindTwoWindowJudge`는 E4/E5 이름을 등록한다. 선택적 E3 함수 `read_stage_bundle(ctx, current, previous=prior, stage_id=...)`는 원자료를 확인한 뒤 아래를 반환해야 한다. 함수가 없으면 `stage_common_kind_consumer_unavailable`로 HOLD다. 이 이름은 analyst가 제안한 추가 포트이며, b97d60ce에 이미 있다는 뜻이 아니다.

- `items`: `exposure`, `kind_current`, `kind_previous`, `level_targets` 네 판정. 모두 `role=judge`.
- `kind_now`, `kind_previous`: 모드별 원자료 하위 칸. `kind_subcells`의 정확한 이름과 대응한다.
- `registered_kind_passes`: `(family, kind)` 키의 bool. 직전 원자료 통과에서만 만든다.
- `execution_plan`: 실제 학습 계획의 `path`, `sha256`. 템플릿 목표를 실제 노출로 간주하지 않는다.
- 실제 노출과 대표 레벨이 평가 요청 목록과 맞는지는 `exposure`와 `level_targets`에서 확인한다. 공통 소비자는 `current`의 실제 D44·깃발 원자료를 읽어 교환 감시에 제공한다.

공통 함수에는 `stage_id`, `kind_score_key='late_kind'`, `kind_subcells`를 넘긴다. `learned_cells_min=32` 승인 칸도 실제 실행 계획의 승인 파일에서 확인한다. 이 승인 칸이나 공통 종류 원자료가 아직 없으면 HOLD다. 출구 판정은 학습 프로세스를 종료시키는 명령이 아니다.

P1 검증은 저장된 결과의 PASS 문자열을 믿지 않는다. 체크포인트·계획·설정 SHA를 대조한 뒤 현재·직전 NPZ와 공통 소비자를 다시 실행한다.
