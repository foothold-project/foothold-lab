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
- E0 `kind_task` 밀기 제외 종을 이벤트 직전 실제 지형 열로 거른다. EX-40과 EX-42 stage zero는 기존 이벤트 경로를 유지한다. 지형 열 또는 등록표가 없으면 E0 이후 이벤트는 거절한다.
- `push_baseline`은 E0 local update 0 뒤 생성할 예정 경로이다. 파일은 아직 없다. 승인 파일과 `stage_zero.approval_sha256`는 수정하지 않았다.
- `runtime_integration.merged`가 null이고 생산 승인도 없으므로 전체 기동은 계속 차단된다. 기존 E0 단독 진입의 250회, 3072 env 계약은 별도 범위라 유지했다.

## CPU 확인

- isaac311 환경에서 EX-42 CPU 묶음: 209 passed, 2 skipped, 1 deselected. 출력: `/home/jay/mai/tmp/scripter/ex42prep-test/latest.log`.
- 선택 제외 1건은 기존 `test_stage_transition_consumes_only_complete_approved_dr_schedule`: E1 거울 setter 없는 가짜 runner로 E1 전환을 호출해 기존 코드에서 실패한다. 이번 변경의 E0 밀기 마스크 이전에 거절되는 반례다.
- EX-40 DR CPU 묶음 중 2건은 Windows 절대 경로 `C:/isaac/...`를 직접 열어 Linux에서 실패한다. 이번 패치의 새 밀기 마스크는 답을 아는 4 env 입력과 EX-40 불변 경로로 별도 통과했다.
- `git diff --check` 통과. Kit, GPU, 학습은 실행하지 않았다.
