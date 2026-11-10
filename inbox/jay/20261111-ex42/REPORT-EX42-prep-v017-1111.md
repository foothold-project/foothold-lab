# EX-42 v0.17 준비 계약 반영

> 분류: A/정책학습 · 실험 준비
> 작성: 오흥재 (scripter-lx 반영) · 2026-11-11
> 근거: EX42-V017-PREP-LINES-1111.md A~E · 팀장 결정 285348de · 71a3d51f
> 요지: 6144 env M3 준비, E0 부모 핀, 승인 가정, 지형별 밀기 제외를 등록하고 CPU 관문을 확인했다.
> 상태: 준비 코드 확인됨 · 생산 학습 승인 아님

## 변경과 경계

- 전체 계획은 6144 env, GPU당 3072, M3 두 rank로 선언했다. stage zero의 3072 env 단일 프로세스 계약과 승인 해시를 유지했다.
- E0 부모는 m13000 `model_1000.pt` SHA `20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768`으로 등록했다. 부모 manifest의 완료 회차, 파일 이름, 실제 파일 SHA를 따로 검사한다.
- proxy 지형 측정값은 3072 env의 격자 광선 값이다. 6144 env 실센서 측정값으로 해석하지 않는다.
- E0 `kind_task`는 지형별 밀기 제외 선언이다. 실제 물리 이벤트의 제외 경로는 #600 `ex42_column_reset`의 열별 gate 하나만 쓴다. 이 PR의 별도 `interval_push` 마스크는 제거했다. E0 메시 장착은 여전히 차단되어 있어 학습에서 gate가 적용됐다고 주장하지 않는다.
- `push_baseline`은 E0 local update 0 뒤 생성할 예정 경로이다. 파일은 아직 없다. 승인 파일과 `stage_zero.approval_sha256`는 수정하지 않았다.
- `runtime_integration.merged`가 null이고 생산 승인도 없으므로 전체 기동은 계속 차단된다. 기존 E0 단독 진입의 250회, 3072 env 계약은 별도 범위라 유지했다.

## CPU 확인

- 최초 준비 코드의 isaac311 CPU 묶음: 209 passed, 2 skipped, 1 deselected. 출력: `/home/jay/mai/tmp/scripter/ex42prep-test/latest.log`.
- #600 결합 메시를 합친 뒤 reviewer 고침의 관련 CPU 묶음: 191 passed, 1 skipped. 출력: `/home/jay/mai/tmp/scripter/ex42prep-test/review-single-gate.log`. E1 거울 setter를 준비한 시험으로 옛 선택 제외 한 건도 실행했다.
- EX-40 DR CPU 묶음 중 2건은 Windows 절대 경로 `C:/isaac/...`를 직접 열어 Linux에서 실패한다. 새 검증은 별도 마스크 대신 #600 열 gate의 B/beam 제외와 A/flat 허용을 본다.
- `git diff --check` 통과. Kit, GPU, 학습은 실행하지 않았다.

## Reviewer 고침

- M3의 두 rank는 각각 3072 env를 가진다. 런타임은 `WORLD_SIZE=2`, 유효한 `RANK`, `env_count=3072`, 전체 6144를 함께 대조한다. 단독 3072와 잘못된 rank는 거절한다.
- E0 부모의 별도 pin은 계획 표의 E0 pin과 먼저 대조하고, manifest의 완료 회차·파일명·바이트 SHA를 이어 확인한다. 단계 0 승인 파일과 `stage_zero.approval_sha256`는 건드리지 않았다.
- reviewer의 밀기 마스크 관련 돌연변이는 중복 경로를 제거해 적용 대상이 사라졌다. 남은 부모 pin·manifest·3072 단독·운영 정의·M3 parser 반례를 CPU 시험으로 확인했다. 모든 준비 코드는 아직 Kit/E0 생산 경로 검증을 대신하지 않는다.
