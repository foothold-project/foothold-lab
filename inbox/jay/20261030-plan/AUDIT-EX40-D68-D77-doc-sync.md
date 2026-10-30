> 분류: A/평가 · 문서 정합 확인
> 작성: analyst · 2026-10-31 00:34 KST
> 근거: WORKLIST D68~D77 · planner794f96d0 · runner30365957 및 bdb32f3d · verifier B11
> 요지: 세 문서를 두 방향으로 대조하고 EX-40 회차 예외·DR·권한을 반영했으며 실행 결함은 남겼다
> 상태: 문서 수정 완료 · planner 검토 대기 · B11 막음6 처리 중 · B12/B13 미실행 · B14 금지

# EX-40 D68~D77 문서 정합

## 1. 범위

분기점은 planner `feature/fable-25a-jay`의794f96d029bf0c703bec9dc5d8bd9daa07c28e33이다. planner 미커밋 인계 두 파일은 가져오거나 수정하지 않았다. 기존 CURRICULUM v0.6c 전문은 새 현재 절 아래 그대로 보존했다. FLOW 원본은 현재 규칙 입구가 지정한 lead_tmp `inbox/jay/20261028-plan/FLOW-experiment-cycle-1029.md`다. 체크리스트 B2의 옛 `EXPERIMENT-FLOW §1.8` 표기는 현재 FLOW §1a로 연결해야 한다.

Orca가 처음 만든 작업 공간은 옛 기본 경로 `C:/Users/AI-WS01/orca/workspaces/foothold-lab/analyst-ex40-docs-1031`에 생겼다. 이동은 Permission denied였으며 그 사본은 편집·삭제·프로세스 종료하지 않았다. 실제 작업은 같은 커밋에서 `C:/mai/wt/foothold-lab/analyst-ex40-doc-sync`로 새로 분기했다.

## 2. 두 번 대조

| 회차 | 대조 방향 | 확인 결과 |
|---|---|---|
| 1 | 결정 D68~D77 → CURRICULUM·카드·FLOW | scratch·정지·arm B·8보상·대칭/깃발 끔·fixed+shadow·B3분리·D/T0·noise고정·D75범위·D76밀기·D77권한 모두 대응 |
| 2 | 고정 YAML·score config·B11 원자료 → 세 문서 |8단계 시작0/1501/3001/4501/5001/5501/6001/7501, shares8행 합1, 저속전체5%,최종8000,총8001,전이589897728 확인. 첫평가500/간격250/31개로 정정 |
| 이력 | planner 원문 → 새 문서 끝부분 | v0.6c 원문 전체가 동일하게 보존됨을 문자열 대조. 옛 규칙은 현재 실행이 아닌 이력으로 표시 |
| 형식 | 세 파일 | 머리5줄·em dash0, 상대 문서링크 대상 존재, git diff --check 통과 |

D75 범위 검산은 COM각축±.05, gain/strength.9~1.1,delay0~.015를 YAML에서 직접 읽었다. D76 x/y각축±1·10~15s,noise1fixed,마지막T0만force_gt False를 단언했다. 이는 문서·설정 일치 확인이며 물리 효과·학습 성능 확인이 아니다.

## 3. 남은 것과 실행 경계

B11 원문 `C:/mai/wt/foothold-lab/verifier-w56/_out/reports/VERIFY-EX40-B11-1031.md`의 H1 공식smoke 입구,H2 추가DR event의 검사기 거부,H3 잘못된실현값 거짓PASS,P1 자동재개감시 미연결,P2 재개부모/사망/손상처리,P3 문서정합을 한 묶음으로 runner에게 넘긴다. H1 후속 bdb32f3d는 별도 고정돼 있으며 이 문서가 재검증 PASS를 대신하지 않는다. P3은 본 문서 커밋과 최종 실행 사본 카드 동기화로 확인한다.

18갱신smoke가 실제로 지나는것은 B0~B3c 여섯 단계다. DR probe0/4500/6001과 학습경계D/T0를 구별한다. B13 전체평가 경로는 scripter가 CPU 준비 중이다. 추가 준비 결과는 runner 단일 수정 묶음에 합치며 같은 결함을 조각으로 재의뢰하지 않는다.

현재는 기존 부모YAML·실행설정·단계문서의 대조이며 새 EX40 params/env.yaml은 B12 이후에만 나온다. B11 막음0 뒤 B12/B13 각1회, B14는 analyst가 실행하지 않는다. planner 사후확인은 lead00:1x 판단으로 대기 표기하며 실질적 코드/설정 불일치를 면제하지 않는다.

## 4. 입력·산출 해시

| 파일 | SHA256 |
|---|---|
| C:/mai/wt/foothold-lab/runner-ex40-b12-smoke/foothold_s2/curriculum/ex40.yaml | 793659f951a9f53bec88de1dd040bd226becb17b750fd55b3bec9a276b4f3ed9 |
| C:/mai/wt/foothold-lab/runner-ex40-b12-smoke/foothold_s2/curriculum/ex40_score_config.json | a6cc9abc0a6263ee581daf8181216d39702d3480fbd99e27daf169f5cd345dca |
| C:/mai/wt/foothold-lab/analyst-ex40-doc-sync/inbox/jay/20261026-experiments/CURRICULUM-GATES.md | 44a0be904939315ada797dfe5762eec77f4075a1387f7ccdebb4f055409d8935 |
| C:/mai/wt/foothold-lab/analyst-ex40-doc-sync/inbox/jay/20261030-plan/CARD-EX40-1030.md | 6cae5f0c82ee4ddaba4ddc7fabc366ab848c9986cfc08b7c82470ab72e87e87b |
| C:/mai/wt/foothold-lab/analyst-ex40-doc-sync/inbox/jay/20261028-plan/FLOW-experiment-cycle-1029.md | 692064933fbc971771caf68f7a800f303cb25a6296ddc10fe750b53cb489cb12 |
