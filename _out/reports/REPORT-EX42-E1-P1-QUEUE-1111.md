> 분류: A/정책학습 · 실행 사슬
> 작성: runner-lx · 2026-11-11
> 근거: lead-lx 15:34 · reviewer #676 · verifier #678 STAGE_EVIDENCE 계약
> 요지: E1 m250~m1000 P1과 E1F materialization evidence를 한 직접 실행 사슬로 잇는다.
> 상태: CPU 확인됨 · live queue · GPU · Kit 미실행

# EX-42 E1 P1 직렬 사슬과 E1F evidence 생산

## 실행 구조

E1 종료 뒤 lead가 잠근 고정 checkout에서 한 명령으로 `ex42_e1_boundary_chain`을 실행한다. 사슬은 manifest SHA가 확인된 m250, m500, m750, m1000 순서로 각 평가를 시작하고, 앞 영수증이 완전 PASS일 때만 다음으로 간다. 각 평가기는 cuda:1 + split cuda:0을 쓰며 E1 D44 여섯 판정 칸도 기존 `ex42_eval_once --p1-stage-id E1` 안에서 확인한다. 평가 실패는 그 회차에서 사슬을 중단하고 chain receipt에 기록한다.

```bash
set -a; source ~/mai/foothold-linux.env; set +a
export FOOTHOLD_OPS_MACHINE_PROFILE="$HOME/mai/tmp/lead/ops/AI-WS01-linux-ops.json"
cd "$FIXED_REPO"
"$ISAAC311_PYTHON" -m foothold_s2.scripts.ex42_e1_boundary_chain \
  --repo "$PWD" --e1-run "$E1_RUN" \
  --plan "$PWD/foothold_s2/curriculum/ex42-prep.yaml" \
  --approvals "$PWD/foothold_s2/curriculum/ex42-approvals.yaml" --e1-ended --execute \
  --training-log "$E1_RUN/torchrun.stdout.log" \
  --p1-done "$E1_RUN/eval/e1-p1-chain-${HEAD12}.p1-done.json" \
  --w09-baseline "$W09_BASELINE_JSON" \
  --evidence-out "$E1_RUN/eval/materialize/E1F-stage-evidence.json"
```

위의 `E1_RUN` 계획·승인 파일은 그 run에서 실제 사용한 고정 plan/approvals 사본이어야 한다. `p1-done` 은 P1 네 경계가 전부 성공한 뒤에만 쓰는 완료표지이며, chain receipt는 실행 시작부터 상태 추적용으로 존재한다. 큐 대체 항목에는 `--done-file`을 붙이지 않는다. dispatcher의 `done_files`는 선행 의존성이라 실행 중 갱신되는 chain receipt를 완료 조건으로 쓰면 안 된다.

W09 결과는 실제 측정 JSON 경로로 전달한다. E1 종료 시점에 파일이 아직 없으면 네 P1 평가는 끝내고 `p1_complete_waiting_w09_baseline`과 `waiting_for_w09_baseline`을 남긴다. 완료표지는 P1만 뜻하므로 E1F 전환은 계속 보류된다. W09 baseline이 생긴 뒤 P1을 재실행하지 않고 아래 명령으로 evidence를 만든다. 경로·내용·SHA가 확인되지 않으면 evidence 생산은 거절된다.

```bash
"$ISAAC311_PYTHON" -m foothold_s2.scripts.ex42_e1_boundary_chain \
  --materialize-only --e1-run "$E1_RUN" --chain-receipt "$CHAIN_RECEIPT" \
  --plan "$FIXED_REPO/foothold_s2/curriculum/ex42-prep.yaml" \
  --training-log "$E1_RUN/torchrun.stdout.log" \
  --evaluation-mesh "$E0_MESH_DIR/terrain_mesh.npz" \
  --w09-baseline "$W09_BASELINE_JSON" \
  --evidence-out "$E1_RUN/eval/materialize/E1F-stage-evidence.json"
```

디스패처 대체 경로는 전체 사슬을 실행하는 GPU1 P1 항목 하나만 만든다. 이는 m250/m750 GPU0 항목이 GPU1 전용 배정기에서 영원히 대기하는 문제를 피한다. 직접 실행이 기본 경로이며 live queue 등록은 하지 않았다.

## E1F materialization evidence

마지막 m1000 P1가 PASS로 끝나고 W09 baseline을 읽을 수 있으면 `ex42_e1_materialize_evidence`가 verifier #678의 `foothold-ex42-materialize-evidence/1` JSON을 새 경로에 원자적으로 쓴다. baseline이 늦으면 위 `--materialize-only` 후속 실행이 동일 생산기를 호출한다. 기존 evidence 파일은 덮지 않는다. 입력은 E1 실행 plan, E1 training stdout의 rank별 preflight 및 실제 `EX42_E0_EXPOSURE` cap 기록, m1000 `p1_score.json`과 그 measurement receipt, 평가에 사용한 seed-42 `terrain_mesh.npz`/manifest, W09 baseline JSON이다.

생성 JSON에는 source E1 plan SHA, m1000 checkpoint SHA, boundary gate 파일 SHA, training-log SHA, 실제 적용 level cap, 메시 파일 SHA, W09 baseline 파일 SHA가 담긴다. 측정이 동일한 source plan을 사용하면 계약대로 `evaluation_plan`을 생략하며, 실제 측정의 plan SHA가 다르면 작성하지 않는다. 메시 identity는 plan에 고정된 mesh SHA와 NPZ bytes의 manifest `mesh_file_sha256`를 함께 대조한다. 두 rank 중 하나라도 없거나 rank·cap·approval SHA가 다르면 작성하지 않는다. 이후 verifier materializer 호출에 바로 넣을 `--evidence` 입력이며, 이 변경은 materializer 실행이나 E1F plan 발행까지 수행하지 않는다.

체인 영수증은 `eval/e1-p1-chain-<HEAD>.json`, P1 완료표지는 `eval/e1-p1-chain-<HEAD>.p1-done.json`, 로그는 `eval/e1-p1-chain-logs/<HEAD>/m<N>.log`, evidence는 `eval/materialize/E1F-stage-evidence.json`이다. 현재 운영 run에는 이 경로들 중 어느 것도 생성하지 않았다.

## 과거 항목

앞서 관측된 old-chain 대기 항목 `id=4` m250, `id=5` m500은 superseded 취소 대상으로 남긴다. 현재 live queue는 읽거나 변경하지 않았고, 두 항목을 취소하지 않았다. m750/m1000 옛 항목은 관측 당시 없었다.

## 확인

- 집중 CPU 묶음: builder, direct-chain 순서/실패격리, delayed-W09 materialize-only, materialize-evidence 생산/반례, split evaluation, dispatcher를 함께 실행.
- 결과: `148 passed, 5 skipped`.
- Python compileall 및 pyflakes: 통과.
- GPU/Kit 실행과 live queue 변경: 없음.
