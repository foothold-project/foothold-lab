# EX-42 E2 이후 유지 평가와 학습 종료 원장 연결

> 분류: 평가
> 작성: 오흥재 (scripter-lx 반영) · 2026-11-11
> 근거: lead-lx 16:59 지시 · CG E1/E1F 이후 유지 칸 · sonnet #687 learned_cells 원자료 형식
> 요지: E2 이후 D44와 깃발 평가를 계속 실행하고 원자료를 점수에 붙인다. 학습 종료 원장은 검증해 읽되 등록 칸 정의 승인 전에는 HOLD다.
> 상태: CPU 확인됨 · Kit 미실행

## 변경과 확인

| 항목 | 결과 |
|---|---|
| 자식 구성 | 단계 목록 순서에서 E1 이후 D44, E1F 이후 깃발을 유지한다. E2 이후에도 두 자식이 계획에 보인다. |
| 점수 원자료 | D44와 깃발 JSON을 해당 평가 폴더에서 읽고 계획·저장본·시드·원자료 SHA를 기존 read_evidence로 대조한다. 실패한 깃발 자식의 영수증은 성공 원자료로 소비하지 않는다. |
| learned_cells | #687의 `learned_cells_<it>_rank<N>.json`을 창·단계·계획 SHA·rank 완전성·칸 합계로 검사한다. 원자료가 없거나 rank가 결측이면 HOLD다. |
| 판정 한계 | `maintenance.learned_cells`의 승인된 등록 칸 목록이 prep에 아직 없다. 현재 32개 문턱을 임의 칸에 적용하면 근거 없는 PASS가 되므로 원자료 수량을 남기고 HOLD를 유지한다. 팀장 결정 뒤 등록 칸 정책을 추가해야 한다. |

isaac311 CPU 시험: `test_ex42_retained_evidence_cpu.py` 및 E1/E1F/E2·score·chain·P1 관련 묶음 102 passed. 실제 Kit 자식 실행은 하지 않았다. #687 생산자와 이 판의 파일 형식은 소스 대조만 했으며 학습 경계의 실제 원장 파일은 아직 없다.
