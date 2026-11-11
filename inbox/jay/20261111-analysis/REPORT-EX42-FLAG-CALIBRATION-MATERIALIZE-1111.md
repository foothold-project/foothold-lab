> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: verifier-lx · 2026-11-11
> 근거: lead 16:44·16:56 의뢰 · #688 4f1560aa · #678·#684 materialize 계약 · Refs #555
> 요지: 완료된 W09·W08 사슬을 원자료로 다시 센 뒤 E1F calibration·기준선·승인 SHA와 transition을 새 불변 폴더에 발행한다.
> 상태: CPU 검증 · 실제 W09/W08 자료 및 Kit 연결은 미확인 · GPU 미실행

# EX-42 W09·W08 뒤 calibration 재핀 CLI

## 바뀐 경로

`foothold_s2.ex42_stage_materialize`에 `--materialize-only --flag-chain --expected-flag-chain-sha256`를 더했다. 새 검사기는 `foothold_s2/ex42_flag_publication.py`다. 일반 materialize의 기존 인자는 유지한다. 이 CLI는 평가·학습 자식을 시작하지 않는다.

| 입력 | 되읽는 것 | 거절 조건 |
|---|---|---|
| #688 `chain_receipt.json` | 완료 상태·호출자가 준 파일 SHA·E1 gate 및 measurement SHA·부모 체크포인트 | 미완료·다른 부모·다른 관문·해시 불일치 |
| 깃발 평가 plan | 파일 SHA와 다음 단계의 깃발 계약 | pin 칸을 제외한 평가 설정 차이 |
| seed42 메시 | materialize evidence의 실제 NPZ 경로·파일 SHA와 메시 manifest | 다른 경로·논리 메시 SHA·기재된 파일 SHA 불일치 |
| W09 1회 + W08 5회 | 서로 다른 6폴더, seed 순서 42·42·42·43·44·45, 매 회 flag_one/flag_four rc0·완료 | 회차 누락·폴더 재사용·자식 실패·메시 차이 |
| 12자식 × 세 지도 모드 | NPZ·건별 JSON·영수증 경로 및 SHA, 64 env 전체 시간열 재채점 | 결측·변조·기재된 수와 원자료 재계산 불일치 |
| W09 기준선·W08 calibration | 네 판정 칸의 수와 다섯 반복 폭을 원자료에서 재생성 | JSON 내용을 바꾸고 SHA까지 다시 써도 원자료와 다르면 거절 |

발행한 plan의 `evaluation.flag_cells.calibration`, `calibration_sha256`, `flag_baseline`과 승인 칸의 `prerequisites.calibration_sha256`, `flag_baseline.path/sha256`를 채운다. 승인 파일 SHA를 새 plan에 고정한다. 기존 부모·상한·예산·승인 범위 검사는 그대로 적용하며 미승인 단계를 승인하지 않는다.

`transition.json`은 원 E1 source plan → 원 관문 → 새 plan 사슬을 유지하고, `inputs.flag_chain` 및 원자료 해시 목록을 추가한다. 출력은 새 경로에 한 번만 원자적으로 발행하며 같은 경로 재발행은 거절한다. 원 E1 plan·승인 파일·관문·학습 디렉터리는 수정하지 않는다. 원자료 파일은 복사하지 않고 경로와 SHA로 계속 검증하므로 W09/W08 원본과 평가 plan을 보존해야 한다.

## runner가 호출할 CPU 명령

아래 변수는 실제 파일과 집계에서 채워야 한다. `SOURCE_E1_PLAN`은 E1 기동 당시 plan, `TEMPLATE_PLAN`은 새 승인·깃발 계약이 든 통합 plan이다. `STAGE_EVIDENCE`는 기존 `ex42_e1_materialize_evidence`가 생성한 증거다. 깃발 평가 plan은 `FLAG_CHAIN`에 담겨 있으며 source plan으로 대신 넣지 않는다.

```bash
CUDA_VISIBLE_DEVICES='' "$ISAAC311_PYTHON" -m foothold_s2.ex42_stage_materialize \
  --materialize-only --flag-chain "$FLAG_CHAIN" \
  --expected-flag-chain-sha256 "$FLAG_CHAIN_SHA256" \
  --plan "$TEMPLATE_PLAN" --source-plan "$SOURCE_E1_PLAN" \
  --approvals "$TEMPLATE_APPROVALS" --target E1F \
  --parent-manifest "$E1_MANIFEST" --gate-receipt "$E1_PASS_RECEIPT" \
  --evidence "$STAGE_EVIDENCE" \
  --budget-limit "$BUDGET_LIMIT" --budget-used "$BUDGET_USED" --budget-basis "$BUDGET_BASIS" \
  --out "$NEW_IMMUTABLE_OUTDIR"
```

성공 rc0의 JSON에 `plan`, `approvals`, `transition`, `plan_sha256`, `launch_env.EX42_AUTO_PLAN`, `launch_env.EX42_AUTO_APPROVALS`, `training_started:false`가 나온다. 거절은 rc2·HOLD다. runner는 이 새 plan/approvals 경로를 다음 launcher에 전달해야 한다. 기존 `--flag-chain` 없는 일반 materialize만 호출하면 calibration을 새로 채우지 않는다.

## CPU 근거와 경계

- 고정 #688 `4f1560aa29f3885af1c5e87946041e3914879434`의 실제 `make_baseline`·`make_calibration`과 테스트 자료를 대조했다. 별도 사본에 고정 의존 파일을 얹은 새 시험 15개가 통과했다. 자료는 합성 64 env 정답 입력이며 실제 학습 성과 수치가 아니다.
- 새 CLI → 새 승인 validator → `validate_materialized_transition` → 실제 E1F `_calibration` → `validate_automatic_stage_launch`까지 CPU에서 통과했다. 원 입력 바이트 불변, 같은 출력 폴더 재사용 거절도 확인했다.
- W08 재계산 비교·W09 재계산 비교·자식 rc 검사 각각을 삭제한 세 제거본은 해당 반례에서 모두 `DID NOT RAISE`로 실패했다. 관문 삭제를 시험이 잡았다.
- 기존 E0 `q4_two_window_range` 및 W08 `w08_proposed_q4.json` 제안값은 적용하거나 수정하지 않는다. 기준선 재핀은 새 문턱 승인과 다르다.
- 자료·원출력·제거본: `/home/jay/mai/tmp/verifier-lx/calibration-materialize-1111/`. `dependencies.json`에 합성 사본의 #688 파일별 SHA를 기록했다. `final-v2.log`는 새 15개, `mutant-{calibration,baseline,child_rc}.log`는 제거본 결과다.
- 이 PR은 CPU 발행 경로다. 실제 W09/W08 완료 자료, 실제 E1F launcher/Kit 첫 실행, runner 사슬이 이 CLI를 부르는 연결은 미확인이다. #688 실행기 병합과 runner 호출 연결을 포함한 전체 무인 기동 완료로 해석하면 안 된다.

## 완료 기록

통합 `c9018296385019aab5ae830d4bb62ca2326b1433` 위에서 아래 다섯 파일을 CPU로 실행했다. `81 passed in 63.40s (0:01:03)`, 실패·skip 없음. #688 생산자 모듈은 이 통합 머리에 실제 포함되어 있어 마지막 실행에는 합성 파일을 덧씌우지 않았다.

```text
test_ex42_calibration_materialize_cpu.py
test_ex42_materialize_cpu.py
test_ex42_materialize_approval_guards_cpu.py
test_ex42_duration_contract_cpu.py
test_ex42_e1_materialize_evidence_cpu.py
```

원출력 `integrated-final.log`, CUDA 숨김·`-p no:cacheprovider`·전용 basetemp 적용. 수정 Python 세 파일 pyflakes 0, `git diff --check` 통과. CPU 재핀 기능 범위 막음 0. 실제 자료 발행과 후속 학습 기동은 이 검증 범위 밖이다.
