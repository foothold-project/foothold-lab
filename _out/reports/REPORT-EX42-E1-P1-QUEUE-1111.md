> 분류: A/정책학습 · 실행 사슬
> 작성: runner-lx · 2026-11-11 16:19 KST
> 근거: lead-lx 15:34 · reviewer #676 · verifier #678 STAGE_EVIDENCE 계약 · lead-lx 16:28 W08 순서 지시
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
  --plan "$SOURCE_PLAN" --evaluation-plan "$INTEGRATED_EVALUATION_PLAN" \
  --approvals "$PWD/foothold_s2/curriculum/ex42-approvals.yaml" --e1-ended --execute \
  --training-log /mnt/win-d/mai/tmp/runner/E1_20261111_114505/torchrun.stdout.log \
  --p1-done "$E1_RUN/eval/e1-p1-chain-${HEAD12}.p1-done.json" \
  --w09-baseline "$W09_BASELINE_JSON" \
  --evidence-out "$E1_RUN/eval/materialize/E1F-stage-evidence.json"
```

위의 `E1_RUN` 계획·승인 파일은 그 run에서 실제 사용한 고정 plan/approvals 사본이어야 한다. `p1-done` 은 P1 네 경계가 전부 성공한 뒤에만 쓰는 완료표지이며, chain receipt는 실행 시작부터 상태 추적용으로 존재한다. 큐 대체 항목에는 `--done-file`을 붙이지 않는다. dispatcher의 `done_files`는 선행 의존성이라 실행 중 갱신되는 chain receipt를 완료 조건으로 쓰면 안 된다.

W09 결과는 실제 측정 JSON 경로로 전달한다. E1 종료 시점에 파일이 아직 없으면 네 P1 평가는 끝내고 `p1_complete_waiting_w09_baseline`과 `waiting_for_w09_baseline`을 남긴다. 완료표지는 P1만 뜻하므로 E1F 전환은 계속 보류된다. W09 baseline이 생긴 뒤 P1을 재실행하지 않고 아래 명령으로 evidence를 만든다. 경로·내용·SHA가 확인되지 않으면 evidence 생산은 거절된다. `--plan`은 E1 실행에 사용한 고정 source plan이고, `--evaluation-plan`은 D44/maintenance 측정에 사용한 통합 evaluation plan이다. 두 값을 혼합하지 않는다.

```bash
"$ISAAC311_PYTHON" -m foothold_s2.scripts.ex42_e1_boundary_chain \
  --materialize-only --e1-run "$E1_RUN" --chain-receipt "$CHAIN_RECEIPT" \
  --plan "$SOURCE_PLAN" --evaluation-plan "$INTEGRATED_EVALUATION_PLAN" \
  --training-log /mnt/win-d/mai/tmp/runner/E1_20261111_114505/torchrun.stdout.log \
  --evaluation-mesh "$E0_MESH_DIR/terrain_mesh.npz" \
  --w09-baseline "$W09_BASELINE_JSON" \
  --evidence-out "$E1_RUN/eval/materialize/E1F-stage-evidence.json"
```

디스패처 대체 경로는 전체 사슬을 실행하는 GPU1 P1 항목 하나만 만든다. 이는 m250/m750 GPU0 항목이 GPU1 전용 배정기에서 영원히 대기하는 문제를 피한다. 직접 실행이 기본 경로이며 live queue 등록은 하지 않았다.

## E1F materialization evidence

마지막 m1000 P1가 PASS로 끝나고 W09 baseline을 읽을 수 있으면 `ex42_e1_materialize_evidence`가 verifier #678의 `foothold-ex42-materialize-evidence/1` JSON을 새 경로에 원자적으로 쓴다. baseline이 늦으면 위 `--materialize-only` 후속 실행이 동일 생산기를 호출한다. 기존 evidence 파일은 덮지 않는다. 입력은 E1 실행 plan, E1 training stdout의 rank별 preflight 및 실제 `EX42_E0_EXPOSURE` cap 기록, m1000 `p1_score.json`과 그 measurement receipt, 평가에 사용한 seed-42 `terrain_mesh.npz`/manifest, W09 baseline JSON이다.

생성 JSON에는 source E1 plan SHA, m1000 checkpoint SHA, boundary gate 파일 SHA, training-log SHA, 실제 적용 level cap, 메시 파일 SHA, W09 baseline 파일 SHA가 담긴다. 측정의 `maintenance_source_sha256`은 evaluation plan과 대조한다. source plan SHA는 gate와 exposure 출처를 검증할 때 별도로 유지하며 둘이 다르면 `evaluation_plan` 참조를 증거에 넣는다. 메시 identity는 source plan의 고정 mesh SHA와 NPZ bytes의 manifest `mesh_file_sha256`를 함께 대조한다. 두 rank 중 하나라도 없거나 rank·cap·approval SHA가 다르면 작성하지 않는다. 이후 verifier materializer 호출에 넣을 `--evidence` 입력이며, 이 변경은 verifier materializer 실행이나 E1F plan 발행까지 수행하지 않는다.

체인 영수증은 `eval/e1-p1-chain-<HEAD>.json`, P1 완료표지는 `eval/e1-p1-chain-<HEAD>.p1-done.json`, 로그는 `eval/e1-p1-chain-logs/<HEAD>/m<N>.log`, evidence는 `eval/materialize/E1F-stage-evidence.json`이다. 현재 운영 run에는 이 경로들 중 어느 것도 생성하지 않았다.

## 과거 항목

앞서 관측된 old-chain 대기 항목 `id=4` m250, `id=5` m500은 superseded 취소 대상으로 남긴다. 현재 live queue는 읽거나 변경하지 않았고, 두 항목을 취소하지 않았다. m750/m1000 옛 항목은 관측 당시 없었다.

## 확인

- 집중 CPU 묶음: builder, direct-chain 순서/실패격리, delayed-W09 materialize-only, materialize-evidence 생산/반례, split evaluation, dispatcher를 함께 실행.
- 결과: `148 passed, 5 skipped`.
- Python compileall 및 pyflakes: 통과.
- GPU/Kit 실행과 live queue 변경: 없음.

## Reviewer 재확인과 W08 사람 없는 진행 점검

실제 E1 stdout을 CPU로 읽어 applied cap 파서를 확인했다. 로그는 `/mnt/win-d/mai/tmp/runner/E1_20261111_114505/torchrun.stdout.log` (SHA256 `958c445954cc6000a467f32627844d0729b5b57642a7baa37f73a4016b3e784c`)이고, E1 run manifest는 `/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261111_114505/main/EX-42-B-E1_20261111_114505/manifest.json`이다. 두 실제 `EX42_E0_EXPOSURE` 행에는 rank · world_size · stage_id가 없으므로, rank 완결성은 `EX42_STAGE_E1_PREFLIGHT` 행으로 확인하고 실제 exposure 두 행은 23개 노출 열의 cap이 모두 5인지 확인한다. 결과는 `applied_level_cap=5`; source plan `/home/jay/mai/wt/foothold-lab/ex42-launch-b379eb98/foothold_s2/curriculum/ex42-prep.yaml` SHA `e542961d9c65a588ae893b81a8d07d39cd66ca068f2f118410c3e2d1d7a2d982`이다.

코드는 `foothold_s2.ex42_stage_materialize.read_applied_cap`를 런타임에 우선 호출한다. 이 runner 고정판에는 아직 해당 verifier 모듈이 없어 CPU 사전검사에서는 같은 인자·영수증 규약의 호환 함수를 사용했다. verifier 모듈이 통합된 뒤 직접 호출 경로는 해당 함수로 전환된다. 현재 결과는 실제 로그에서 얻은 값이며, 두 구현의 동일성 검토는 verifier 통합 뒤 남는다.

W08 이후 순서는 이제 명시적으로 직렬화했다: E1 P1 m250 → m500 → m750 → m1000, W09 flag baseline, W08 반복 1 → 2 → 3 → 4 → 5, W08 materialize/repin, 그 뒤 E1F 예행이다. 각 W08 반복은 직전 반복 완료를 필요로 하며, E1F는 materialize/repin 완료 전 진행할 수 없다. 실제 `ex42_post_e1_gpu_chain` CPU plan은 `rc=2`, `state=blocked`, `queue_mutated=false`, `kit_started=false`를 냈다. 순서 검사는 통과하지만 다음 연결은 아직 실행 불가다.

| 고리 | 현재 근거 | 상태 |
|---|---|---|
| W09 flag baseline 실행 | `W09_flag_cell_evaluator_command_missing`; graduation checkpoint SHA 산출 경로 없음 | 막힘 |
| W08 5회 Kit 평가 | `flag_cell_calibration_producer_missing`; 다섯 결과를 묶는 receipt schema 없음 | 막힘 |
| calibration 파일 생성 · plan 재핀 | `W08_calibration_artifact_schema_missing`; materialize-only/repin 명령 계약 없음 | 막힘 |
| E1F 시작 전 완료 보장 | 첫 E1F 항목이 앞의 repin 완료를 요구하도록 계획에 연결했으나 앞 고리가 실행 불가 | 막힘, Kit 시간 추정 불가 |

기존 `ex42_calibrate.py`는 동일 checkpoint/mesh의 5회 EX-42 전체 평가를 요약하는 도구이고 깃발 칸 calibration producer로 확인되지 않았다. verifier `ex42_stage_materialize.py` CLI는 `--plan --source-plan --approvals --target --parent-manifest --gate-receipt --evidence --budget-* --out`을 받아 새 immutable plan/approval 디렉터리를 만든다. 이 CLI에는 `--materialize-only` 플래그가 없다. 이 PR의 `ex42_e1_boundary_chain --materialize-only`는 P1 후 E1F evidence JSON만 만들며 plan/approval을 재핀하지 않는다. 따라서 W08 완료 전에 자동으로 calibration을 materialize하고 E1F m250 전에 끝난다고 현재 증거로 보장할 수 없다. 사람 없는 완주를 열었다고 보고하지 않는다.

CPU 결과: 관련 묶음 `149 passed, 5 skipped` (8.10 s). 실제 로그 사전검사는 `cap=5`로 통과했다. GPU · Kit · 실제 queue는 사용하지 않았다.
