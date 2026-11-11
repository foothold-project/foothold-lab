# EX-42 E1F 깃발 출구 판정과 평가 입력

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 · 2026-11-11
> 근거: CURRICULUM-GATES v0.16 §E1F:248 · REVIEW-EX42-STAGE-CHECKLIST-REMEASURE-1111 §2 #5·6·8 · lead-lx 15:12 담당 확정
> 요지: E1F 는 깃발 한 개와 네 개의 정답·복원 64 env 칸을 두 창에서 판정하고, 끔 칸은 기록만 한다.
> 상태: CPU 코드·답 아는 시험 통과 · Kit 실측과 W09 기준선·다섯 반복 폭 핀 대기 · E1F 기동 승인 아님

## 입력과 판정

`foothold_s2/curriculum/ex42-prep.yaml` 의 E1F 행에 `exit_judge: flag_two_window` 및 같은 이름의 진입 어댑터를 적었다. `evaluation.flag_cells` 의 목표 반경 0.3 m, 마지막 목표 근처 정지 0.5 s, 64 env, 유효 하한 48, 성공 52/64, 생존 60/64, 두 창은 CG §E1F 가정과 D176 유효 분모 규칙이다. 정지는 월드 수평 속도 ≤ 0.05 m/s 로 구현했다. 이 속도 수치와 평가 12 s, 깃발 명령 속도 1.0 m/s 는 E1 D44 정지 관례와 기존 명령 상한에서 택한 **E1F 평가 가정**이며 Kit 전 팀장 확인 대상이다. 유효 분모가 48~64이면 문턱은 `ceil(52/64 × valid)`와 `ceil(60/64 × valid)`이다. 한 칸 FAIL 은 다른 칸 HOLD 보다 우선한다.

평가 자식 `foothold_s2/eval/ex42_flag_eval.py` 는 한 프로세스에 깃발 수 한 종류와 지도 세 모드를 실행한다. 두 깃발 수를 각자 실행해야 한다. 고정 A 연속 23 열의 L0~2 배정, env 64, 동일 시드, 무작위 DR·명령 교체·행 커리큘럼 끔, 전체 정해진 시간 원자료가 없는 경우 영수증을 쓰지 않는다. 원래 학습 명령의 깃발 진행 반경 0.5 m 대신 평가에서 0.3 m 를 명시한다. `S2Policy` 가 정답·복원·지도 끔 입력을 실제로 선택했는지 검사하고, 깃발 좌표가 칸 원점에서 +x 0.5·1.5·2.5·3.5 m 인지 검사한다. 원자료 NPZ, 건별 JSON, 전체 영수증은 SHA 로 묶는다. `read_evidence` 는 원자료를 다시 계산하고 배정·좌표·전체 시간·서명 없는 칸을 거절한다.

`foothold_s2/ex42_e1f_judge.py` 는 #672 `StageJudge` 의 `judge(ctx,score)`와 `verify(score,judgment,expected,plan=plan)` 꼴이다. 출력 `stage_exit` 에 adapter, 두 창, 각 `check_id`, 역할, PASS/HOLD/FAIL, 증거 `{path,sha256}`가 있다. 현재·직전 유지표 26 칸은 검토된 E0 비교기를 재사용한다. `flag_calibration.json` 핀이 없으면 깃발 판정은 HOLD 이다. 다섯 반복은 시드 42·42·43·44·45의 깃발 한 개·네 개, 세 지도 모드를 원자료까지 다시 읽어 폭을 계산한다. 기준선 W09 경로와 SHA 는 E1 졸업 뒤 materialize 되어야 한다. 지금 prep 의 calibration 핀은 null 이므로 PASS 가 날 수 없다.

## CPU 검증과 남은 관문

- isaac311 CPU 관련 시험 묶음 **42 passed** (`test_ex42_e1f_flag_cpu.py` · `test_ex42_e1_judge_cpu.py` · `test_ex42_d44_four_cells_cpu.py`). 답 아는 64 env 완주·낙상·정지 속도·전체 시간·두 창·실패 우선·47/48 분모·세 모드 역할·원자료 및 반복 영수증 변조를 포함한다.
- `ex42_eval_once.py` 가 E1F 단계에서 깃발 한 개·네 개 자식을 차례로 부르고 두 `flag_cells.json` 원자료와 실제 GPU UUID 를 확인한 뒤 점수를 만든다. 자식 하나 실패나 영수증 누락은 해당 칸의 실패 이유를 `child_failures.json` 에 남기고 P1 HOLD 점수와 handoff 영수증까지 쓴다. CPU 주입 시험에서 rc 0, `p1_score.json` HOLD, 같은 단계 이어 가기 notice 를 확인했다. 실제 이어 학습 실행은 **미확인**이다. 부모 명령 형성·영수증·GPU 신원 반례와 실제 `ex42_flag_eval.py` argparse 가 부모 argv 를 받는 경로를 CPU 로 확인했다. 실제 Kit 자식 동작과 지도 소비 영수증은 **미확인**이다.
- #672 일반 `StageJudge` 배관과 E1F 이름 등록은 결선했다. #670 진입 어댑터 병합 및 E1F plan materialize 후 전체 실행 경로를 다시 확인해야 한다.
- E1 졸업본에서 W09 기준선과 깃발 다섯 반복 평가를 수행한 뒤, `evaluation.flag_cells.calibration` 에 파일 경로·SHA 를 채우고 plan·approval SHA 를 재고정해야 한다. 이 보고의 값은 실측 아님.

## 실행 계약, 아직 GPU 실행하지 않음

두 자식의 공통 꼴은 `python -m foothold_s2.eval.ex42_flag_eval --checkpoint <E1F model_N.pt> --plan <고정 prep.yaml> --mesh-dir <고정 ABCDE mesh> --expected-mesh-sha256 <승인된 SHA> --seed 42 --envs 64 --device cuda:1 --headless --count flag_one --out <평가>/flag_cells/flag_one` 이다. 두 번째는 `--count flag_four --out <평가>/flag_cells/flag_four` 이다. 결과 `flag_cells.json` 이 둘 다 있어야 한다. 다섯 반복의 CPU 합산 명령은 `python -m foothold_s2.eval.ex42_flag_calibrate --plan <반복 당시 prep.yaml> --checkpoint <E1 졸업본> --repeat-root <회1> ... --repeat-root <회5> --out <새 calibration.json>` 이다. 운영 argv 는 E1F materialize 뒤 실제 경로와 다시 대조해야 한다.

## #677 검토 지적 반영

- 통합판의 E1F 입구 관문은 준비됨으로 시험 기대를 갱신했다. 공통 PASS 만 담은 점수는 E1F 전용 `stage_exit` 검증에서 거절한다.
- 검토의 생존 돌연변이 여덟 개에 답 아는 CPU 반례를 추가했다. FAIL 우선, 비례 문턱 올림, 생존 하한, trace SHA, 직전 깃발 칸과 직전 유지표 창 결측, stage_id 위조, calibration 위조를 각각 검사한다.
- 자식 실패 원인을 HOLD 마커에 기록하고, 부분 영수증이 남아 있어도 실패한 깃발 수의 칸을 채택하지 않는다. 자식 실패가 P1 전체 출력 누락으로 번지지 않는다는 CPU 제어 흐름 시험을 추가했다. `test_ex42_e1f_flag_cpu.py` · `test_ex42_future_approval_cpu.py` · `test_ex42_stage_continue_cpu.py` · `test_ex42_stage_handoff_cpu.py`: 110 passed. 이 시험은 Kit 실행과 실제 GPU handoff 성공을 뜻하지 않는다.
