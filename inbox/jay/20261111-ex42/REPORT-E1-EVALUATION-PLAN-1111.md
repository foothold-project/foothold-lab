# EX-42 E1 실행 계획과 평가 정책 분리
> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 (scripter-lx 반영) · 2026-11-11 18:11
> 근거: lead 18:06 결정 · E1 실기동 manifest · D44 평가 계약
> 요지: P1 실행 신원은 기동 계획에 묶고 D44와 출구 판정은 평가 계획에서 읽는다.
> 상태: CPU 확인됨 · 새 Kit 평가 미실행

`--p1-plan` 은 단계 ID, 부모, 회차, 승인과 P1 `plan_sha256` 신원에만 쓴다. 새 `--evaluation-plan` 은 D44 자식·깃발 자식·유지표 정책·exit judge를 고른다. P1 점수와 평가 영수증에 평가 계획의 절대 경로와 SHA256을 남긴다. 측정 원자료의 `maintenance_source_sha256`도 평가 계획 SHA로 고정하고, 두 SHA가 다르면 P1 판정을 거절한다. 기존처럼 두 계획이 같은 경우는 그대로 허용한다.

실제 E1 m500 저장본 CPU 사전 점검 원출력: `/home/jay/mai/tmp/scripter/ex42-eval-plan-preflight.json`. 점검 다섯은 체크포인트 manifest SHA, 기동 계획의 E1 신원, 평가 계획 D44 여섯 칸, c333 메시 SHA, 기동 승인표로 모두 PASS다. 기동 계획 SHA `e542961d9c65...`, 평가 계획 SHA `a2007c8f00fd...`로 실제로 다르다. DRY 명령 원출력 `/home/jay/mai/tmp/scripter/ex42-eval-plan-dry-receipt.json`은 D44 planned 6칸이고 rc 0이다.

CPU 회귀: `test_ex42_e1_judge_cpu.py`, `test_ex42_e1f_flag_cpu.py`, `test_ex42_split_eval_cpu.py` 67 passed. 새 반례는 실행 계획에 D44 칸이 없어도 평가 계획의 여섯 칸으로 PASS를 검증하고 P1 `plan_sha256`은 실행 계획 SHA로 유지한다. 평가 계획 SHA를 바꾸면 거절한다.

runner 전달 계약: P1 argv에 `--evaluation-plan <고정된 평가 사본>/foothold_s2/curriculum/ex42-prep.yaml`을 `--p1-plan <기동 사본>/foothold_s2/curriculum/ex42-prep.yaml`과 함께 넣는다. runner가 사슬에 반영하고 고정 사본에서 재검사하기 전까지 운영 연결은 미확인이다.
