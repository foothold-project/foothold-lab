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

- `/home/jay/miniforge3/envs/isaac311/bin/python -m pytest -q -p no:cacheprovider --basetemp=/home/jay/mai/tmp/scripter/test-e1f-flags foothold_s2/tests/test_ex42_e1f_flag_cpu.py` · **8 passed**. 답 아는 64 env 완주·낙상·정지 속도·전체 시간·두 창·실패 우선·47/48 분모·세 모드 역할·원자료 및 반복 영수증 변조를 포함한다.
- `python -m py_compile` 평가 자식·CPU 집계·판정 4 파일 · **rc 0**. Isaac EULA 입력창이 생기는 `--help` 호출은 CPU 검증으로 쓰지 않았다. 실제 Kit 자식 동작과 지도 소비 영수증은 **미확인**이다.
- #670 진입 어댑터 이름 허용과 #672 일반 `StageJudge` 배관 병합 후 등록 import 및 두 count 자식 호출을 결선해야 한다. 병합 전 이 PR 단독으로 EX-42 전체 CPU suite 또는 E1F 출구가 통과한다고 주장하지 않는다.
- E1 졸업본에서 W09 기준선과 깃발 다섯 반복 평가를 수행한 뒤, `evaluation.flag_cells.calibration` 에 파일 경로·SHA 를 채우고 plan·approval SHA 를 재고정해야 한다. 이 보고의 값은 실측 아님.

## 실행 계약, 아직 GPU 실행하지 않음

두 자식의 공통 꼴은 `python -m foothold_s2.eval.ex42_flag_eval --checkpoint <E1F model_N.pt> --plan <고정 prep.yaml> --mesh-dir <고정 ABCDE mesh> --expected-mesh-sha256 <승인된 SHA> --seed 42 --envs 64 --device cuda:1 --headless --count flag_one --out <평가>/flag_cells/flag_one` 이다. 두 번째는 `--count flag_four --out <평가>/flag_cells/flag_four` 이다. 결과 `flag_cells.json` 이 둘 다 있어야 한다. 다섯 반복의 CPU 합산 명령은 `python -m foothold_s2.eval.ex42_flag_calibrate --plan <반복 당시 prep.yaml> --checkpoint <E1 졸업본> --repeat-root <회1> ... --repeat-root <회5> --out <새 calibration.json>` 이다. 운영 argv 는 #672 배관·E1F materialize 뒤 실제 경로와 다시 대조해야 한다.
