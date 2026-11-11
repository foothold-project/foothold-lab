> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: verifier-lx · 2026-11-12
> 근거: 통합 7d93df13 · 원장 7121e018:420~423 · CG 368d03e2:193,322~337 · CPU 시험
> 요지: ④ E1F 미승인 연장 차단 · ⑥ wall 성과 사다리 연결. ⑤ M 실행 연결은 증거 생산자 계약 확인 대기이며 완료 아님.
> 상태: 부분 구현 · GPU/Kit 미실행 · M 자동 진입/복귀 미완료

# EX-42 E1F 연장 · M 복귀 · wall 대조

## 요청별 결과와 결정 대기

| 요청 | 원장 및 정본 | 확인 · 변경 | 남은 것 |
|---|---|---|---|
| ④ E1F 연장 | [7121e018 decisions.tsv:420](https://github.com/foothold-project/foothold-lab/blob/7121e0188cf1cbe558704764227e306e6097149f/inbox/jay/20261104-ex41-restart/decisions.tsv#L420): 12:02 E1F 진입, 연장 별도. CG 368d03e2:188의 +500×1은 가정 | prep 기본 상한 750 · 가정 500×1 보존. 승인 파일 false 바이트 보존. materialize가 13:07 전체 승인만으로 E1F 연장을 true로 만들던 경로 차단. 별도 승인 없이 true+전체 계획 계약을 넣어도 validator 거절. 750 HOLD는 자동 연장 없이 알림 | **E1F 연장 승인은 결정 대기.** 19:38 ④는 E1 연장 승인이며 E1F로 확대하지 않음 |
| ⑤ M 복귀 실행 | [같은 원장:423](https://github.com/foothold-project/foothold-lab/blob/7121e0188cf1cbe558704764227e306e6097149f/inbox/jay/20261104-ex41-restart/decisions.tsv#L423): 원천 단계 복귀 · 원천 상한 제외 · EX42 합계 포함 · 1000 실패 알림 후 복귀 · p_map_off 0.3 · 새 두 창 | 선언은 존재하지만 실행 연결 없음. 아래 직접 호출 결과로 확인. 이 PR에서 임의의 source/return_stage나 실측 칸을 채우지 않음 | **미완료.** 고정 레벨 진입/종료 증거 생산자와 스키마, M 부모 이식 뒤 원천 단계 회차를 보존하는 소비자 연결 필요. 00:20 run 질문 msg_daa54e42cfd1 |
| ⑥ wall | [같은 원장:420](https://github.com/foothold-project/foothold-lab/blob/7121e0188cf1cbe558704764227e306e6097149f/inbox/jay/20261104-ex41-restart/decisions.tsv#L420): 벽 높이 1.20 m · 통로 폭 0.80 m 확정 | prep의 치수 미정 주석 제거. 기존 high_ledge → crawl 다음 wall L0를 K 사다리에 연결. 실제 CPU 기하의 높이/통로 폭 및 성과 입력 뒤 wall 5% 노출 확인 | Kit 실제 노출은 미확인. 시작부터 wall을 동시에 노출하지 않음. 기존 연속 몫 하한과 종류 하한은 유지 |

## 변경 소비 경로

- `foothold_s2/ex42_stage_materialize.py:299`: E1F에는 전체 계획 승인으로 HOLD 연장을 만들어 주지 않는다.
- `foothold_s2/curriculum/ex42_prep.py:419`: E1F의 true 연장 계약을 거절한다. 향후 별도 결정이 오면 그 결정 계약을 별도로 구현해야 한다.
- `foothold_s2/curriculum/ex42-prep.yaml:393,1216,1342`: 가정 회차와 승인 상태의 구분, 확정 wall 치수 주석, K 순서의 wall 추가.
- `foothold_s2/terrains/hipan_posture.py:22~23`: 기존 기하 상수 1.20/0.80. 이미 맞으므로 생성기 변경 없음.
- `foothold_s2/terrains/ex42_k_ladder.py:83~108`: 기존 성과 기반 사다리 소비. 첫 창 PASS만으로 모든 종류를 동시에 올리지 않는다. high_ledge와 crawl이 목표 레벨까지 도달해 easy 몫으로 내려간 입력에서 wall 5%가 열린다. 공급 몫이 부족하면 기존 거절을 유지한다.

## M에서 확인한 실행 공백

`EX42Plan.load` 뒤 실제 호출, 출처 `/home/jay/mai/tmp/verifier-lx/m-return-1112/m-consumer-audit.json`:

```json
{
  "m_approved": true,
  "m_enabled": false,
  "m_source_ids": [],
  "m_exit_judge": null,
  "following_E5": "M",
  "following_M": "E6a",
  "return_stage_id": null,
  "entry_adapter_ready": false,
  "validator_error": "ValueError: EX-42 stage source contract is unresolved or invalid"
}
```

따라서 승인 자체가 없는 문제가 아니다. 다음 연결이 필요하며 어느 것도 구현 완료로 표기하지 않는다.

1. CG:193의 L3·L6·L9, GT/OFF 각 64 종료 에피소드 증거. 현 `ex42_eval_once.py:49~53`의 axis 자식은 설정한 고정 레벨 하나만 실행한다. 일반 map64를 세 레벨 자료로 간주할 수 없다. 다른 축 변경 0의 증거도 필요하다.
2. M 진입 시 실제 원천 단계, 사용 회차, 적용된 노출/레벨 상한/명령 몫과 부모 SHA를 고정. 현재 `ex42_stage_materialize.py:263~264`는 선행 PASS만 받으며, M 진입 조건/원천 상태를 재구성하는 분기가 없다.
3. `ex42_prep.py:696`의 선형 다음 단계와 `ex42_stage_handoff.py:106~135`의 PASS 다음 단계 경로를 조건부 진입/원천 복귀로 연결. M 1000 HOLD를 PASS로 바꾸는 방식은 쓰지 않아야 한다.
4. 원천 단계 카운터와 EX42 누적 카운터를 분리해 복귀 체크포인트/승인/영수증에 보존. 현재 E1 validator는 1000 상한과 E0 부모 재판정을 명시적으로 검사한다(`ex42_prep.py:191~225`). 단순히 M 부모를 덮으면 이 경로가 거절된다.
5. 부모 cfg를 그대로 복사하는 `configure_ex42_stage_zero_train_cfg`(`scripts/ex42_training_entry.py:1390~1401`)와 실제 지도 추첨 소비자까지 p_map_off 0.3 연결. 원천 단계 복귀 뒤 새 두 창의 run/경계 식별자를 보존해야 한다.

M 실행 연결은 미완료다. 평가 생산자 계약을 run으로 문의했고 답변을 기다린다. 현재 M 기동 거절을 보존한다.

## CPU 검증

관련 8개 파일 **133 passed in 97.47s**. pyflakes 오류 0 · `git diff --check` 통과.

- 고치기 전 반례: E1F materialize false→true, 전체 승인만 넣은 E1F true 허용, wall K 순서 누락. 세 시험 모두 FAIL 확인.
- 고친 뒤: E1F 750 HOLD는 `stage_bound_reached_not_ready` · `action=notify`, 새 500 회 자동 연장 없음.
- wall: CPU 실제 기하 1.20/0.80, 성과 자료 없으면 노출 없음, 선행 목표 도달 입력에서는 wall L0 5%.
- 승인 파일은 기준 7d93df13과 바이트 동일. approval SHA `e64284789730d426eba1732c2e41186bfc5a46b7007eba595567a0a7cf220db7`.
- 시험 명령·로그: `/home/jay/mai/tmp/verifier-lx/m-return-1112/`의 `red.log`, `final.log`, `m-consumer-audit.json`.
- GPU · Kit · 기동 · 실행 중 원자료 · 고정 사본 변경 없음.
