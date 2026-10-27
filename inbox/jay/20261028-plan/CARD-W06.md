# 실행 카드 W06 · EVAL-AXES-v2 v0.2 독립 검증

> 분류: 검증 의뢰
> 작성: lead · 2026-10-28 02:2x
> 근거: `fable-25a/inbox/jay/20261027-design/EVAL-AXES-v2.md` 9 절(검증 요청 목록) · analyst `astra-25b/.../VERIFY-analyst-EVAL-AXES-v2.md` · `REVIEW-analyst-EVAL-AXES-CANDIDATES.md`
> 요지: 원래 verifier(Codex) 몫인데 Codex 는 11/02 까지 쓰지 않는다. planner 가 쓴 문서라 planner 가 스스로 검증하면 독립이 아니므로 reviewer(Claude) 가 맡는다
> 상태: 의뢰 · 문서 · CPU 재계산만

## R

- [ ] R06-1 9 절 검증 요청 항목마다 「맞음 · 틀림 · 미확인」 과 근거(코드 줄 · 원자료 · 논문 원문)
- [ ] R06-2 지도 처치 셋(eval_gt · eval_pred · probe_prop_only)의 정의가 코드와 맞는지(`eval_map_modes.py`, 실제 소비 칸 `gt_used/policy_steps_x_envs` · `last_num_map_tokens`)
- [ ] R06-3 비용 5 절 숫자 재계산
- [ ] R06-4 축 후보 30 개 분류가 analyst 28 개 점검과 어긋나는 곳 목록
- [ ] R06-5 막음 · 고침 · 참고로 나눈 검토 문서 경로를 lead 에 한 줄 보고
