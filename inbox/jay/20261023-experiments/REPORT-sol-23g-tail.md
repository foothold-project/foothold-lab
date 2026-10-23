> 분류: A/정책학습
> 작성: 오흥재 (sol 작성·lead_tmp 취합) · 2026-10-23
> 근거: SOL-23g 후속 지시 · 코드 기준 c0038e80 · 좁은 CPU 시험
> 요지: TopDown 출발 yaw, curriculum RNG 재개, 초기 진단 스냅샷의 재개 거절을 고쳤다.
> 상태: CPU 확인됨 · Kit 및 학습 미확인

# SOL-23g 잔여 세 항목 CPU 수정

취합 출처: 작업자 고정 커밋 `82331727`. 아래 시험 숫자는 작업자 보고이며, lead_tmp 직접 재실행 범위는 [준비 기록](READINESS-B-START-1023.md)에 별도로 적었다. 머리 형식과 이 안내만 취합 시 정리했다.



## 변경

| 항목 | 수정 | 확인 |
|---|---|---|
| TopDown 출발 | reset yaw `(0, 0)` 명시. 논문 미기재 팀 선택. | AST에서 실제 대입을 실행해 0 확인. B 설정은 공통 yaw `(-3.14, 3.14)`를 유지하며 B 파일은 미수정. 회전 명령 및 PIE DR 미수정. |
| Curriculum 재개 | TopDown env hook에 `_s2_rng.bit_generator.state`를 저장하고 복원. | `StartRunner`의 실제 env 상태 저장 및 복원 경로로 다음 10개 난수 draw 일치. 물리 상태와 에피소드 reset의 동일성은 보장하지 않음. |
| 초기 스냅샷 | `model_initial.pt`에 `initial_snapshot=true` 표시, `resume_parent`에서 표시 또는 옛 파일명을 거절. | 초기 파일과 이름을 바꾼 초기 파일 모두 거절. 완료된 `model_0.pt` 수용. |

## 검증

- CUDA 숨긴 CPU 실행: `python -m pytest -q foothold_s2/tests/test_sol23g_tail_cpu.py foothold_s2/tests/test_sol23f_launch_cpu.py::test_resume_parent_is_validated_before_new_segment_and_old_files_untouched` 결과 4 passed.
- 새 시험 첫 실행의 2 failed는 시험 AST 비교와 초기 저장의 공유 딕셔너리 오염을 드러냈고, 수정 뒤 4 passed.
- 바뀐 Python 파일에 `ruff check --select F`: 0건. `git diff --check`: 통과.
- 이전 전체 suite PID 103564의 결과는 이 작업에서 기다리거나 판정하지 않았다. GPU, Kit, 학습, 프로세스 종료는 실행하지 않았다.

## 바뀐 파일과 한계

코드: `s2_23f_topdown_cfg.py`, `s2_23f_topdown_env.py`, `sol23f_runner.py`, `train_sol23f_common.py`, `sol23f_contract.py`. 시험: `test_sol23g_tail_cpu.py`. SHA는 동봉 `SHA256SUMS-sol-23g-tail.txt`에 있다. 실제 Kit 환경 reset과 체크포인트 재개는 미확인이다.
