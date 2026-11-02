> 분류: A/정책학습 · 구현 계획
> 작성: 오흥재 (analyst 정리) · 2026-11-02 12:02 KST
> 근거: D80·D89·D93·D96·D101·D110·D116·D117, lead 11/02 구현 분담과 가중 결정
> 요지: EX-40 코드를 보존하며 EX-41 설정·경계 적용·보상과 env 단위 무효 처리를 연결한다.
> 상태: 구현 중 · CPU만 · 통합 및 Kit 미확인

# EX-41 B1·B2 구현 계획

목표: 실제 부모 m7500에서 만든 EX-41을 단계 끝까지 같은 계약으로 운영한다. 제품 코드 기준은 2df419b0, W86 수식은 1fc1f5c7. 본기동·EX-40 실행 사본·원장·GPU를 건드리지 않는다. RULES R20·M76은 실제 YAML/소비 경로 대조, M14는 답 아는 반례, M02는 독립 worktree로 막는다.

구현 계획·TDD 스킬을 적용한다. 사용자가 이미 구현과 두 겹 검토를 지시했으므로 이 계획을 별도 승인 관문으로 쓰지 않는다.

## 파일과 인터페이스

| 주인 | 파일 | 계약 |
|---|---|---|
| analyst | curriculum/continuous.py | load_plan(path, arm, smoke_boundaries), make_runtime(plan, env_count, device, log_dir, score_dir, terrain_policy, segment_index). EX-40 기존 Plan/Runtime 보존 |
| analyst | curriculum/ex41.py, ex41.yaml | EX41Plan·EX41Runtime, 자체 n1부터 시작·parent7500, T0_prime 표기. stage_changed(stage, effective) callback, state_dict/load_state_dict |
| analyst | curriculum/w72.py, ex41-boundary.yaml, ex41-approvals.yaml | 경계에서 커밋된 두 파일을 같은 HEAD로 읽고 승인값 대조. snapshot 이후 변경은 다음 경계. 한 적용 영수증, 중복 score 소비 방지, 원래 설정 유지형 거절 |
| analyst | rewards/w86.py, w86_runtime.py | prepare_env_cfg(env_cfg, plan), W86 측정/보상/종료 함수, NaN quarantine hook. Isaac import는 Kit 경로 안에서만 |
| scripter | runners/start_runner.py·자체 이식/거울 모듈 | 입력 이식·새 판 시작과 재개·critic 전용 mirror·stage_changed 소비·quarantine hook 소비 |
| analyst | curriculum/ex41.py B5 | level_cap·world-frame 성과 승급·지형 종류별 env 수와 레벨 분포 |
| runner | 학습 진입점·시작/평가/루프 | factory와 prepare_env_cfg를 실제 경로에서 호출. 설정과 평가 score SHA를 연결 |

## 진행 순서와 시험

- [ ] 실제 슬롯 표를 EX-41 파서로 읽어 유효 명령을 표집. 잘못된 합·범위 축소·나중 보상 추가 거절, EX40 그대로.
- [ ] W72의 승인된 경계값 적용. dirty·미승인·막는 칸·NaN·경계 뒤 변경·중복/오래된 점수·재개를 답 아는 입력으로 시험.
- [ ] ±1%p/±2%p, 자동 계수 절반 1회, critic 발동, 성과 승급·S2c 연장 한 번·D110 상한 T0_prime·마지막 완료를 상태기로 시험.
- [ ] W86 비용·n0 등록·기존 유지 및 단일 stumble. 광선 무효와 로봇 NaN을 구별, 유효 env 유지, 보상0 항 별도 기록, 완전 스윙 주기·끌림 분모 확인.
- [ ] 범위 내 CPU 회귀·diff·최종 commit/push, 통합 소비자에게 계약 전달 후 verifier 두 겹 검토 의뢰. Kit은 lead 승인 뒤.

검토 초점: 마지막 checkpoint 복원 시 설정 재적용/중복 자동 조정, W72 일부 반영 후 실패, 평가가 늦을 때 미래 점수 소비, RewardManager의0가중 건너뛰기, 종료가 보상보다 먼저 실행되는 Isaac 순서. 모든 코드 시험은 이 다섯을 포함한다.

## 12:42 CPU 중간본과 소비 계약

이 커밋은 B1/B5 구현 초안이다. **B2 w86_runtime은 아직 빈 함수, 통합·Kit 미확인**이므로 실행 고정본으로 쓸 수 없다. 기존 EX40 경로는 보존한다.

- authorization: `gate=W72`, `status=APPROVED`, `approval_id=approval_sha256`, `decision_ids`, `config_commit`, `config_sha256`, `approval_sha256`, `boundary_file`, `approval_file`. 두 경로는 실제 절대경로다. callback 전 승인 정보이며 callback 성공 뒤에만 applied 영수증을 쓴다.
- 공유 `tests/fixtures/ex41_authorization.json`의 a/b/c 해시는 거절용 예시. 양성은 `tests/ex41_authorization_fixture.py:real_authorization`가 임시 Git 저장소에 실제 파일을 커밋해 같은 dict를 만든다. snapshot 뒤 파일을 바꿔 이전 True 복구까지 거절되면 False로 다시 적용, effective와 rejected 영수증을 OFF로 맞추고 학습을 계속한다.
- runner 연결: `continuous.apply_terrain_policy`가 EX41에서 B5의 n0 curriculum term을 등록한다. callback은 `partial(ex41.apply_runtime_fields, runner)`가 소비한다. `attach_runtime`는 EX40 DR 숫자 일정을 EX41 일정으로 바꾼다. 최초 wrapper reset 전에도 `_ex40_dr_scale=1`이어야 한다.
- S2a/S2b는 고정 회차 종료가 아니라 성과 대기이므로 runtime `max_updates=None`이다. runner는 `finished/stop_requested`와 별도 운영 예산을 소비해야 한다. B1만 합치고 기존 유한 반복기를 그대로 쓰면 미연결이다.
- score 형식은 `foothold-ex41-score/1`, `iteration`은 EX41 local n이다. stage_id·schedule_sha256·parent_sha256·checkpoint 실제 경로/해시·created_at·maintenance_pass/stage_pass/safety_stop(bool)·metrics·evidence(경로/해시)·baseline_checkpoint_sha256를 요구한다. stage 판정 수치 생산은 runner 점수기와 통합할 부분이며 B1은 그 bool을 대신 발명하지 않는다.
- 남은 B1 검증: 저장 상태 엄격 검증, 소비 readback 값 대조, 실제 score 생산과 늦게 도착한 점수 연결, W71 승인 갱신, D121 종료조건 개방의 구체 필드, smoke 전 경로. 자동 걸림 상향의 발동 조건은 미확정이며 지금은 승인 범위 내 경계값 변경만 구현했다.

확인됨: 12:43 B1 CPU 23통과(5.40초), 실제 파일 변경 rollback 시험 포함. `test_ex41_runtime_cpu.py · test_ex41_boundary_cpu.py · test_w72_cpu.py`, isaac311-moects Python, CUDA 숨김, pytest cache 끔. `git diff --check` 오류0. 선택한 구판 시험 4실패는 읽기 전용 2df419b0 고정본에서도 똑같이 재현: 날짜가 지난 end_by 예제1개, runtime_adapter_status를 implementation_in_progress로 기대하는 EX40 DR 시험3개. 그 사본은 고치지 않았다. isaac311-moects는 pyflakes 미설치. scripter 개발 중 사본을 독립 재시험한 3실패는 고정 HEAD 재확인 전까지 미해소이며 과거 5통과 보고를 현재 통과로 쓰지 않는다.

## 보상 가중 계산

EX-40 params/env.yaml:1890~1894의 전진 추종은 exp 항 가중2.0. :21 dt0.005·:84 decimation4이므로 step_dt0.02. 설치 reward_manager.py:150은 모든 항에 가중×dt, :157의 기록은 다시 dt로 나눔.

가정 계산: 두 발이 목표보다0.08m 낮고 각 발 수평속도0.5m/s이면 비용=2×0.08²×tanh(1)=0.0097484. 가중−10이면 −0.097484/s, 추종2.0×0.8=1.6/s의6.09%. dt 적용 후 −0.00194968 대0.032로 같은 비율. 속도1.0m/s이면7.71%. 이는 보상 크기 설계 계산이며 실측 보행 효과가 아니다. lead 11/02 12:0x 범위 안에서 swing−10, 허용[−20,−2], stumble 단일항−2, 허용[−3,−1]을 쓴다.
