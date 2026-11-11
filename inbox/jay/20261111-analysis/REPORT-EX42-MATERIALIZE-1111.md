> 분류: A/정책학습 · 실행 증거 발행
> 작성: verifier-lx · 2026-11-11
> 근거: lead 13:06·13:12·14:45·14:50·14:58 의뢰 · 원장 2b94ea58 · 통합 44f6347a
> 요지: 앞 단계 PASS와 실제 부모·상한·증거 SHA를 새 불변 curriculum 묶음으로 발행
> 상태: CPU 및 실제 E0 자료 DRY 확인 · GPU/Kit 미실행 · 실제 E1F 발행은 종료·기준선 증거 대기

# EX-42 materialize

## 변경과 검증 범위

`foothold_s2.ex42_stage_materialize`는 파일 발행만 한다. 기동·GPU 대기열·운영 원장을 건드리지 않는다. 승인 false를 true로 바꾸지 않으며 승인 신원은 기존 셀에서 보존한다. J는 단계 표에 없어서 거절한다.

| 항목 | 실제 처리 | 확인 |
|---|---|---|
| 상대경로 의존성 | curriculum 아래 YAML·JSON을 원래 상대 배치로 복사. 원 template과 실제 source plan의 의존 파일도 `provenance/`에 보존 | 새 폴더 EX42Plan.load 및 작성자 worktree 변경 후 재검증 통과 |
| 첫 구간 scope | 표 minimum_updates와 승인 scope가 같은지 대조, 부모 SHA만 실측으로 채움 | E1F 750, 1250을 첫 scope로 넣은 입력 거절 |
| 연장 | 첫 scope와 분리하여 `extension_contract`에 HOLD 전용·표 최대·증분·전체 승인 원장을 기록 | E1F 750 후 HOLD 때 +500, 최대1250. 이 도구는 연장을 실행하지 않음 |
| 부모 | model_N 파일·manifest·P1의 회차와 SHA 대조. 누적 회차는 앞 단계 부모 누적+완료 회차 | 오염 체크포인트 거절. 실제 E0 m250 `680c820b…` 재확인 |
| E1F cap | rank별 PREFLIGHT의 승인 SHA와 rank0 실행 경로를 대조하고 실제 EX42_E0_EXPOSURE의 활성 열 `level_caps`를 읽음 | 현재 E1 두 rank 모두5. 상한6 입력은6 보존, rank 불일치 거절. 관측 최대 레벨을 사용하지 않음 |
| 증거 | 계약에 등록된 dotted path만 파일 SHA 또는 JSON pointer로 채움. 기준선 path와 SHA는 같은 파일로 결합 | 미등록 키·결측·비유한 값·변조 거절 |
| plan 사슬 | P1을 다시 쓰지 않고 `prior_plan_sha`, `gate_sha256`, `new_plan_sha`, `parent_sha256`를 transition.json으로 연결 | 실제 E0의 옛 plan SHA `19e86a25…` 그대로 새 plan 승인까지 통과 |
| 허용 변경 | 입력 snapshot에서 결과를 다시 구성하여 전체 문서 대조 | 새 plan에서 지형 preset을 바꾸고 새 SHA도 다시 적은 반례 거절 |
| 부모 소비 | EX42Plan.verify_parent_manifest가 materialized target이면 transition 전체를 다시 읽음 | 부모 영수증 변조 반례 거절 |
| 판정 기준 | 기동 source plan과 점수의 maintenance_source_sha256를 분리. 다르면 명시적 evaluation_plan 파일과 SHA 필요 | 서로 다른 두 plan을 구분하는 시험 통과 |
| 발행 | 배타 잠금, 임시 폴더 검증 후 rename, 파일 읽기 전용. 기존 outdir 재사용 거절 | 실패 시 결과 폴더 미발행, 입력 파일 변경0 |

E1의 D44는 현재 통합의 여섯 칸·두 창 원자료를 읽는다. 이후 단계는 sonnet `ex42_stage_judges.adapter_for`의 verify 계약을 재사용한다. 등록되지 않은 판정기나 빈 증거는 발행을 거절한다. M이 아직 disabled 또는 source_stage_ids 미정이면 거절한다. 이 PR은 M의 조건·복귀 정책이나 뒤 단계 노출표를 추측해서 채우지 않는다.

## 호출 계약

```bash
python -m foothold_s2.ex42_stage_materialize \
  --plan /absolute/approved-template/ex42-prep.yaml \
  --source-plan /absolute/finished-run-plan/ex42-prep.yaml \
  --approvals /absolute/approved-template/ex42-approvals.yaml \
  --target E1F --parent-manifest /absolute/finished-run/manifest.json \
  --gate-receipt /absolute/finished-run/eval/p1_score.json \
  --evidence /absolute/stage-evidence.json \
  --budget-limit N --budget-used K --budget-basis explicit-counting-convention \
  --out /absolute/new-immutable-directory
```

N·K·계수 기준은 호출자가 명시한다. 20,000을 부모 포함 누적 또는 EX-42 신규 회차로 임의 해석하지 않는다. 현재 도구는 첫 구간의 예산 예약을 확인하며, 전체 경로 예산 원장을 자동 집계하는 도구는 아니다. 발행 후 `plan`, `approvals`, `transition`, `launch_env.EX42_AUTO_PLAN`, `launch_env.EX42_AUTO_APPROVALS`를 JSON으로 반환한다. 오류는 rc2와 HOLD 사유를 남긴다.

E1F 증거 JSON의 계약은 다음과 같다. 아래는 형식 설명이며 실측값이 아니다.

```json
{
  "format": "foothold-ex42-materialize-evidence/1",
  "target_stage": "E1F",
  "source_stage": "E1",
  "source_plan_sha256": "앞 단계 기동 plan의 실제 SHA",
  "checkpoint_sha256": "앞 단계 종료 체크포인트 SHA",
  "gate_sha256": "P1 영수증 파일 SHA",
  "evaluation_plan": {"path": "판정 기준 plan", "sha256": "점수 maintenance_source_sha256와 같은 SHA"},
  "exposure_receipt": {"path": "완료된 두 rank 실행 로그", "sha256": "그 로그 파일 SHA"},
  "bindings": {
    "prerequisites.predecessor_exit.evaluation_mesh_sha256": {"path": "평가 메시 원파일", "sha256": "그 파일 SHA"},
    "prerequisites.flag_baseline.sha256": {"path": "W09 기준선 파일", "sha256": "그 파일 SHA"}
  }
}
```

평가 기준과 기동 plan이 같고 점수 SHA도 같으면 `evaluation_plan`은 생략한다. 문자열·boolean 실측 필드는 해당 파일 reference에 `pointer`를 추가한다. `critic_mirror`는 E1 이후 true를 유지한다. 실행 로그는 완료된 고정 기록을 공급해야 한다. 진행 중 로그가 바뀌면 SHA 검사에서 거절하며 이전 cap으로 조용히 대체하지 않는다.

sonnet 소비자는 `validate_materialized_transition(plan, target_stage=..., gate_receipt_path=..., expected_gate_sha256=...)`를 사용할 수 있다. 반환값은 source_plan_sha256·source_stage_id·parent·transition_path이다. 현재 부모 소비 경로에서도 같은 검사를 호출한다. 세 SHA 문자열만 맞춘 수기 transition을 충분한 증거로 간주하지 않는다.

## 실측과 시험

- 새 시험은 구현 전14실패. 후속 반례는 첫 scope·rank1 별도 폴더·transition 변조·부모 소비에서 실패를 먼저 확인했다.
- CPU 최종 묶음: `156 passed in 31.68s` (새 materialize31개 포함). `CUDA_VISIBLE_DEVICES=''`, cacheprovider 끔, isaac311. pyflakes 0. ruff는 미설치여서 사용하지 않았다.
- 제거본5: 예산 제한 제거, source plan 검사 제거, rank 상한 대조 제거, cap5 하드코딩, 전체 문서 허용 변경 대조 제거. 정상 대조군 통과 후 각각 지정 시험 rc1로 검출했다.
- 실제 E1 `torchrun.stdout.log` snapshot: 두 rank 적용 cap5, 원 기동 plan SHA `e542961d9c65a588ae893b81a8d07d39cd66ca068f2f118410c3e2d1d7a2d982`. 파일 SHA는 `actual-cap.json`에 보존했다.
- 실제 E0 P1와 `model_250.pt`를 사용한 materialize 및 통합 #674 자동 승인 대조 통과. 이어 sonnet #670 `1e8bb602` + 본 변경을 합친 CPU 사본에서 launcher `--dry-run` rc0, `app_launcher_started=false`, `training_requested=false`. 최신 통합에 #670이 아직 없어서 이 조합을 명시한다.

원출력·재현 스크립트: `/home/jay/mai/tmp/verifier-lx/materialize-1111/`의 `final-release.log`, `mutants.json`, `real_e0_probe_v3.py`, `real-e0-v3.log`, `launcher_dry_v3.sh`, `real-e0-launcher-dry-v3.log`, `actual-cap.json`. 실제 종료 이전인 E1F 발행이나 학습 성공으로 확대하지 않는다.

## 남은 연결

1. runner가 E1 종료 P1, 완료 로그, W09/W08 등 실제 산출물로 evidence JSON을 만들고 materialize를 호출해야 한다. 지금 null을 가짜 SHA로 채운 운영 파일은 없다.
2. sonnet handoff가 새 plan/approvals/transition 경로를 선택하고 기동하는 연결, 이후 단계 judge 등록·노출·부모 상태 로드는 각각 담당 PR 범위다. 본 실측은 CPU 진입까지이며 Kit·학습은 미실행이다.
3. M 조건부 진입·복귀 자료, 뒤 단계 미작성 정책과 측정이 없으면 여전히 HOLD다. 이것을 전체 단계 준비 완료라고 보고하지 않는다.

Refs #555.

## #672 통합 뒤 지적분 재검증 (2026-11-11)

통합 `864cd398`를 #678 가지에 merge했다. 수정 전 동일 materialize 시험에서 `19 failed, 12 passed`를 재현했다. 두 `adapter.verify` 호출에 `plan=policy.document`를 전달하고, E1 시험 자료를 #672 생산자의 실제 형식(`required_cases`, 정규화된 D44 판정 행, 원자료 `d44_cells`)에 맞췄다. 정답으로 기대하는 성공·생존 수와 문턱은 직접 구성했다.

`ENTRY_GATE_ADAPTERS = ('map39', 'flag_two_window', 'pending')` 및 준비 여부 표현을 #670 `f60e19a5`와 동일하게 맞췄다. 발행되는 승인·plan의 옛 `stage_exit_v1` 이름은 `flag_two_window`로 바꿨다. 실제 검증기는 계속 앞 단계의 `policy.document`와 source stage로 선택하므로 E1 졸업을 E1F 깃발 졸업으로 바꾸어 검사하지 않는다. critic_mirror는 기존 #678의 E1 이후 켬 규칙을 보존했다.

최신 CPU: materialize `33 passed in 11.29s`, 관련 묶음과 E1 판정 회귀 `176 passed in 30.36s`. 두 호출을 각각 plan 없이 되돌린 제거본은 각각 `1 failed, 1 passed`로 검출했고, 정상 대조는 `2 passed`. pyflakes 0. GPU/Kit 미실행. 원출력은 `/home/jay/mai/tmp/verifier-lx/materialize-1111/r2/`의 `red.log`, `green.log`, `regression.log`, `mutation-results.json`이다.
