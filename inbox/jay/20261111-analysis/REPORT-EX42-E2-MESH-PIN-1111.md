> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: verifier-lx · 2026-11-11
> 근거: lead E2 메시 자동 선택 의뢰와 실제 부모 미발행 답변 · 통합 f694e702 · analyst #716 · Refs #555
> 요지: E2 이후 깃발 메시를 계획에서 자동 선택하고 파일 SHA를 materialize·기동·학습 사전검사에 고정한다.
> 상태: CPU 연결 막음 0 · 실제 E2 부모 미발행에 따른 기동 거절 보존 · GPU/Kit 미실행

# E2 이후 메시 선택과 실제 소비

`training_mesh_profiles.e2_named_flags_v2`에 analyst 사본 경로와 파일 세 개의 SHA를 기록했다. E2·E3·E4·E5·M·E6a·E6b의 `training_mesh_profile`은 이 프로필을 가리킨다. E1F에는 필드를 추가하지 않아 기존 공통 환경의 메시를 계속 사용한다. 단계 회차·노출·명령·보상·승인 내용은 변경하지 않았다.

| 항목 | 직접 계산한 SHA256 |
|---|---|
| NPZ 전체 파일, 깃발 포함 | `59b0bf3e3023f40da828b86eebff4513222e13452c70fc49b8951d7e8d42d771` |
| mesh_manifest.json | `c6954b6c7ffaaeee2e17c3b9365a40b4391dd2ef33bafd2ab4b526daf42851a7` |
| terrain_manifest.json | `7e9dab9420c3c6694df9e2e5d5d9155ff4a5448d1ac7a9936a96c07d2a7a6740` |
| 기하, vertices+faces | `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95` |

계획 경로는 `/home/jay/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2`이다. 이 기기의 해당 경로는 `/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2`로 해석된다. 영수증에는 정규화한 경로를 쓴다. 같은 폴더의 별칭은 허용하지만 다른 단계별 경로나 SHA를 환경 변수로 덮으려 하면 거절한다. 공통 환경에 옛 메시가 남아 있어도 프로필이 있는 단계에는 적용되지 않는다.

| 소비 자리 | 변경 |
|---|---|
| `ex42_stage_mesh.pinned_stage_mesh` | 경로·파일 세 개 SHA·manifest 내부 기하/NPZ 연결·실제 기하 SHA·사용 가능한 flags 배열 검사. 선언된 프로필이 잘못되면 공통 경로로 돌아가지 않음 |
| `scripts/ex42_stage_launcher.build` | plan에서 프로필 선택. 학습 및 P1 argv에 같은 경로와 기하 SHA 전달. 자식의 EX42_MESH_DIR_단계/EX42_MESH_SHA256_단계 자동 설정. 요약 영수증 training_mesh에 세 파일 SHA 기록 |
| `ex42_stage_materialize._prepare` | 대상 프로필 재검사. transition.training_mesh와 artifacts.training_mesh.*에 경로/SHA 기록. 발행 직전 artifacts 재검사와 transition 재구성 검사에도 포함 |
| `materialize.launch_env` | 새 plan/approvals 외에 대상 단계 메시 환경 변수도 자동 생성 |
| `scripts/ex42_training_entry.run_ex42_stage_e0_entry` | 파일과 terrain manifest 경로를 재검사해 사전검사 영수증에 기록. 오류를 dry의 일반 manifest 결측 안내로 삼켜 rc 0으로 넘기지 않음 |
| `prepare_e0_env_cfg` | 환경에 메시를 장착하기 전에 파일 pin과 실제 인자 디렉터리를 다시 검사 |

기하 SHA는 NPZ 전체 SHA가 아니다. P1의 기존 `--expected-mesh-sha256`에는 기하 SHA를 유지하며, 깃발을 포함하는 NPZ 바이트는 별도의 파일 SHA로 고정했다. 기계 공통 환경 파일과 실행 중인 사본·큐는 수정하지 않았다.

## CPU 시험과 독립 재대조

- 새 시험 수정 전 16 실패, 학습 소비자 연결 전 추가 2 실패를 확인했다.
- 변경 경계 회귀 9개 파일: **159 passed, 1 skipped in 54.27s**. skip을 통과로 세지 않는다.
- 동일 경로 별칭 반례를 추가한 최종 launcher/메시 시험: **45 passed in 7.07s**. 위 집합과 겹치므로 시험 수를 더하지 않는다.
- 파일 SHA 대조를 제거한 돌연변이는 4개 반례가 실패했다. 프로필 선택을 없애 공통 환경으로 돌린 돌연변이는 17개 반례가 실패했다.
- 직접 읽은 #713 `7f222a3a606eafe600bdb6fe8820ce0134d34a0c`의 named-kind guard AST만 CPU로 실행했다. 실제 새 NPZ의 비연속 종류 32개 × 레벨 10개 = **320 조합**이 모두 guard를 통과했다. 각 호출은 64 env·flag_four이다. 동일 guard에 깃발 없는 원본을 넣으면 `EX-42 named kind flags missing from the pinned mesh`로 거절됐다. 이는 배열·소비 계약 확인이며 학습 성과나 Kit 성공률이 아니다.
- E2~E6b/M의 자동 선택 결과가 같은 파일 SHA임을 별도로 기록했다. 따라서 뒤 단계가 공통 원본으로 되돌아가서 생기는 named-kind 결측 경로를 막는다. 이후 새 메시를 채택할 때에는 해당 단계 프로필과 파일 pin을 함께 바꿔야 한다.
- 변경 Python pyflakes와 `git diff --check` 통과. 원자료 메시·manifest는 읽기만 했다.

원출력·반례·재현 스크립트는 `/home/jay/mai/tmp/verifier-lx/e2-mesh-pin-1111/`에 있다. 핵심 파일은 `regression.log`, `alias-green.log`, `mutant-sha.log`, `mutant-fallback.log`, `audit_named_flags.py`, `named-kind-readback.json`이다. 메시 측정은 #716의 기존 기하 측정 승계이며 이 작업에서 새 Kit 측정을 하지 않았다.

## 잠근 실제 소스에서 한 두 가지 dry

소스 고정 커밋은 `47f45ce0800002796418ced194b3844d19ced663`이다. `git archive`에서 만든 읽기 전용 사본 `locked-47f45ce0`의 925개 파일 SHA를 실행 전후 대조해 모두 일치했다. 공식 `foothold_s2/scripts/ex42_stage_launcher.sh --dry-run`을 실행했고, 단계 메시 환경 변수는 손으로 주입하지 않았다. CUDA는 숨겼으며 사전검사에서 `app_launcher_started=false`, `training_requested=false`를 확인했다.

| 입력 | 결과 | 해석 |
|---|---|---|
| 실제 승인·plan 그대로, E2 parent=null | **rc 2**, `stage 'E2' has no pinned parent ... (startable: E0, E1)` | 실제 E1F가 아직 안 돌았으므로 E2 기동을 거절하는 정상 경계. 성과/부모 증거를 만들어 채우지 않음 |
| 실제 메시 + 격리 CPU fixture plan/approval/합성 부모 | **rc 0**, `stage_e2_preflight_passed`, `training_blockers=[]` | 메시 자동 선택·파일 핀·46행 측정 manifest·CPU 사전검사 배관이 이어짐. 실제 E2 기동 승인이나 부모 실측으로 읽으면 안 됨 |

합성 부모 파일에는 `CPU-ONLY synthetic E1F parent; NOT A TRAINABLE CHECKPOINT`를 적었으며 실제 모델을 사칭하지 않았다. fixture와 README는 `cpu-fixture-final/`에 있다. 학습 출력 폴더 생성도 없었다. 최초 시험 사본에서 tools 패키지를 빠뜨려 import가 실패한 기록도 보존했고, 최종 사본에는 같은 커밋의 tools를 포함해 위 결과를 얻었다.

최종 원출력: `dry-results-final.json`, `actual_unfilled-final.stderr.log`, `cpu_fixture-final.stdout.log`, `locked-source-final.json`, `dry_probe.py`. 실제 운영 사슬은 E1 관문 및 E1F 완료 뒤 실제 materialize 영수증이 필요하다. 이번 PR은 그 미완료를 우회하지 않는다.

## Reviewer 후속: 시험 공백 두 곳

생산 코드·계획·승인 파일을 바꾸지 않고 시험만 보강했다. 선언된 프로필 이름이 null·빈 문자열·미등록 이름이거나 프로필 등록부가 없을 때 직접 함수와 실제 launcher가 모두 거절하는지 확인한다. E1F처럼 프로필 선언 자체가 없는 경우의 공통 경로 허용은 별도로 유지한다.

`no_empty_flags` 시험은 실제 NPZ에서 flags 키를 뺀 경우와 flags 전부가 NaN인 경우를 각각 만든다. NPZ 파일 SHA와 mesh_manifest 내부 NPZ SHA 및 manifest 파일 SHA를 모두 다시 고정해, 오래된 SHA 때문이 아니라 `no usable named-kind flag table` 계약으로 거절되는지 확인했다.

최종 두 파일 시험 원출력: **50 passed in 8.20s**. 프로필 결측 때 예외 대신 None을 반환하는 돌연변이는 4개 반례에서 `DID NOT RAISE ValueError`로 실패했다. 깃발 표 검사를 끈 돌연변이는 all_nan 반례에서 같은 이유로 실패했다. None 배열에 대한 우연한 TypeError를 검출 근거로 삼지 않았다. 원출력·시험 프로세스 안 치환 스크립트는 `/home/jay/mai/tmp/verifier-lx/e2-mesh-pin-1111/review-tests/`의 `green.log`, `mutant-profile.log`, `mutant-flags.log`, `review_mutant.py`다. pyflakes와 diff 검사 통과. GPU/Kit·원자료·앞서 잠근 사본은 변경하거나 실행하지 않았다.
