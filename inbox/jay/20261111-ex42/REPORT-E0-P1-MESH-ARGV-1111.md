# EX-42 E0 250 경계 P1 평가 명령

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 (lead · scripter-lx 반영) · 2026-11-11
> 근거: N1-KIT-REHEARSAL-LINUX-1111.md 51행 · ex42_chain.py · ex42_eval_once.py · PR #618
> 요지: P1은 c333 메시의 A 연속 23열 map64와 전체 보조 평가를 같은 저장본에서 측정한다.
> 상태: CPU 확인됨 · Kit 미실행

## N1의 P1 한 줄 대체

N1의 `P1=` 51행만 아래로 바꾼다. `OUT`, `DATA`, `REPO`, `ISAAC311_PYTHON`은 N1 앞줄의 값을 그대로 쓴다. 학습 명령은 lead가 고정 소스에 이 변경이 들어간 뒤 기동한다.

```bash
P1="$("$ISAAC311_PYTHON" -c 'import json,sys; out,py,mesh,repo=sys.argv[1:]; print(json.dumps([py,"-m","foothold_s2.ex42_eval_once","--checkpoint",out+"/model_{iteration}.pt","--sha-from-manifest","--out",out+"/eval/scores/m{iteration}","--device","cuda:1","--eval-seed","42","--mesh-dir",mesh,"--expected-mesh-sha256","88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95","--p1-plan",repo+"/foothold_s2/curriculum/ex42-prep.yaml","--p1-approvals",repo+"/foothold_s2/curriculum/ex42-approvals.yaml","--p1-stage-id","E0","--execute"]))' "$OUT" "$ISAAC311_PYTHON" "$DATA" "$REPO")"
```

## 소비와 출력

- `train_start`는 JSON 문자열을 `make_score_argv_factory`로 읽고 `{iteration}`을 저장본 회차로 치환한다. `ex42_chain`은 그 저장본이 `manifest.json`에 게시된 SHA와 일치할 때만 P1 대기열에 넣는다. 이 PR의 P1 관문은 `ex42_eval_once` 모듈, isaac311, cuda:1, seed 42, c333 메시 SHA, A23열, 계획 및 승인 파일, 실행 단계 ID가 `train_start.EX42_STAGE_ID=E0`와 같은지, 실행 플래그를 확인한다.
- 자식 평가기는 manifest SHA를 다시 읽어 파일과 대조한다. `map64/map_modes.json`은 64 env · 300 step · 지도 셋 · 13명령 · A23 배정이다. `stand_*` 3개와 `axis_v2`도 같은 저장본으로 측정한다. 보조 평가의 정지 지형은 기존대로 plane, axis는 L2 고정이다.
- 성공 산출은 `eval_receipt.json`의 `state=done`, `ex42_score.json`, `p1_score.json`이다. 마지막 파일은 P1 소비자가 요구하는 checkpoint 회차·SHA, 계획 SHA, 실행 단계 ID `E0`, 39칸 map_matrix 및 판정 역할을 담고 성능 기준선이 미고정이라 `judgment=HOLD`로 기록한다. 수집 실패는 `HOLD` 점수로 위장하지 않고 영수증 `state=HOLD` 및 rc5이다.

## CPU 확인과 한계

- isaac311 시험 31 passed, 1 skipped. 실제 c333 메시와 기존 m1000 manifest로 `ex42_eval_once` 계획 경로를 읽어 자식 5개와 메시 경로를 확인했다. 실제 Kit 평가는 하지 않았다.
- 원래 N1 `eval_map_modes` 명령은 메시 없이 옛 지형을 쓰고 `p1_score.json`도 만들지 않는다. 코드가 병합되지 않은 고정 사본으로 그 명령을 쓰면 E0 P1로 채택할 수 없다. E0 뒤 단계 전환 시 고정 argv의 단계 ID도 갱신해야 하며, 일치하지 않으면 관문이 거절한다.
