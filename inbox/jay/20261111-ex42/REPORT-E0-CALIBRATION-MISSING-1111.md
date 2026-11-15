# EX-42 E0 calibration 결측값 재요약

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 · 2026-11-11
> 근거: `foothold_s2/ex42_calibrate.py`, 저장된 E0 평가 다섯 회
> 요지: 다섯 회 모두 측정된 칸만 폭을 내고 결측 칸과 회차를 따로 기록한다.
> 상태: 76열 참고판 CPU 재요약 확인, A23 정식판 마지막 회 대기
> 판: v1.0

## 확인

- 76열 참고판 원자료: `/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261108_123914/eval/calib-e0-1111/repeat_00`부터 `repeat_04`까지의 `ex42_score.json`, `eval_receipt.json`, `map64/map_modes.json`.
- CPU 재요약: `/home/jay/mai/tmp/scripter/ex42-calib-e0-76-reference-1111.json`. 공통 숫자 경로 3,498개에 폭을 계산했다. 결측 경로 42개는 `missing_by_repeat`에 남았다. 이 중 39개는 다섯 회 모두 결측, 3개는 일부 회차만 결측이다. 일부 결측 3개는 세 지도 모드의 `goal_right_delta030/phase_from_FL_cycle_median/1`이다.
- 이 76열 결과는 부모와 같은 A23 지형 배정이 아니므로 `comparison_scope=historical_76_reference`로 표시했다. 성능 판정에 쓰지 않는다.
- A23 정식판 원자료: `/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261108_123914/eval/calib-e0-a23-1111`. 이 문서 작성 시점에 `repeat_04/ex42_score.json`이 없어서 정식판 수치 요약은 하지 않았다. `--summarize-only`는 다섯 회가 모두 완료되지 않으면 실패한다.
- GPU와 Kit 실행 없음. EX-42 CPU 전체 378 passed, 3 skipped. 결측 키, 명시적 null, 비유한 값 거절, 원자료만 읽는 CLI, 산출 덮어쓰기 거절을 시험했다.

## 재요약 명령

`python -m foothold_s2.ex42_calibrate --checkpoint <m1000 저장본> --expected-sha256 20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768 --mesh-dir /mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333 --expected-mesh-sha256 88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95 --out <다섯 repeat가 있는 폴더> --device cuda:0 --summarize-only --summary-output <새 JSON 경로>`

76열 옛 참고판만 `--historical-76-reference`를 추가한다. 이 명령은 평가 자식을 띄우지 않는다. `--summary-output`은 기존 파일이면 거절한다.
