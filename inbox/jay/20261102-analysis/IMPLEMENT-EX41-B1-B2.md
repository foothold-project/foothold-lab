> 분류: 계획
> 작성: 오흥재 · 2026-11-02
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

확인됨: 12:43 B1 CPU 23통과(5.40초), 실제 파일 변경 rollback 시험 포함. `test_ex41_runtime_cpu.py · test_ex41_boundary_cpu.py · test_w72_cpu.py`, isaac311-moects Python, CUDA 숨김, pytest cache 끔. `git diff --check` 오류0. 선택한 구판 시험 4실패는 읽기 전용 2df419b0 고정본에서도 똑같이 재현: 날짜가 지난 end_by 예제1개, runtime_adapter_status를 implementation_in_progress로 기대하는 EX40 DR 시험3개. 그 사본은 고치지 않았다. isaac311-moects는 pyflakes 미설치. scripter 개발 중 사본의 3실패는 이후 고정140f9a79에서 직접 6통과(9.53초)로 재확인했다. 양측 실제 승인 fixture SHA는 e1f786ed8fbfed1f8b2fa981f56d0b0db3f4efef324c2b9b81d0d1948775b16f로 같다.

## 보상 가중 계산

EX-40 params/env.yaml:1890~1894의 전진 추종은 exp 항 가중2.0. :21 dt0.005·:84 decimation4이므로 step_dt0.02. 설치 reward_manager.py:150은 모든 항에 가중×dt, :157의 기록은 다시 dt로 나눔.

가정 계산: 두 발이 목표보다0.08m 낮고 각 발 수평속도0.5m/s이면 비용=2×0.08²×tanh(1)=0.0097484. 가중−10이면 −0.097484/s, 추종2.0×0.8=1.6/s의6.09%. **0.8은 보행 실측이 아니라 정규화 추종 보상이 최대값의80%라는 설명용 가정**이다. dt 적용 후 −0.00194968 대0.032로 같은 비율. 속도1.0m/s이면7.71%이며, 추종1.0(최대값) 기준으로는0.123395/2.0=**6.17%**다. 이는 보상 크기 설계 계산이며 실측 보행 효과가 아니다. lead 11/02 12:0x 범위 안에서 swing−10, 허용[−20,−2], stumble 단일항−2, 허용[−3,−1]을 쓴다.

## 13:10 B2 CPU 본문과 추가 반례

이 절은 앞의 12:42 중간 상태를 갱신한다. **B2 빈 함수는 구현했고 단위 시험은 통과했다. 실제 학습 진입점 통합·두 겹 검토·Kit은 미확인이다.** 부모 m6000 제안은 별도 `OPINION-EX41-PARENT-1309.md`; 이 커밋의 기존 YAML m7500을 변경 승인으로 읽지 않는다.

확인됨: isaac311 Python, CUDA 숨김, pytest cache 끔으로 B1/B5/W72/W86 **55통과 4.65초**. 명령은 `python -m pytest -p no:cacheprovider foothold_s2/tests/test_ex41_runtime_cpu.py foothold_s2/tests/test_ex41_boundary_cpu.py foothold_s2/tests/test_w72_cpu.py foothold_s2/tests/test_w86_preparation.py foothold_s2/tests/test_w86_runtime_cpu.py -q`. stage hook의 setter 호출을 try/except로 감쌌고 상위 transaction이 rejected를 기록한다. 저장본 복원에서도 ON 승인 거절 시 OFF 적용 후 다음 갱신으로 간다. 복원 반례는 수정 전1실패, 소비 readback 불일치와 잘못된 자동 점수 반례는 수정 전2실패였다.

| 연결 자리 | 소비 계약 | 현재 확인 |
|---|---|---|
| gym.make 전 | `w86_runtime.prepare_env_cfg(env_cfg, plan)` | n0 신규 항·종료·reset 등록. 기존 collision−10/smooth−.01/power−2e−5 보존, 기존 stumble만−2 |
| gym.make 뒤 첫 wrapper reset 전 | `attach_runtime(raw_env,plan,log_dir)` | PhysicalSource 발·관절 이름 명시, 실제 지형 mesh 광선 0/.05/.10m. Isaac/Warp import는 이때만 |
| alg.act 뒤 env.step 전 | `quarantine_actions(runner,actions)` | 나쁜 행만 행동0, 정상행 그대로 |
| env.step 직후 | `quarantine_step(runner,raw,rewards,dones,extras)` | 기록·finite 검사·replay.add_post·PPO process 전에. 나쁜 env만 done/reset, 보상0, transition행0(std1), timeoutFalse |
| 매 update 끝 | `raw_env._ex41_w86.flush(n)` | 0가중 네 항도 별도 기록, 광선 무효·발별 끌림·완전 스윙 주기 분자/분모 |
| checkpoint와 재개 | W86 `state_dict/load_state_dict` | 집계 이어받음. 실제 물리 에피소드 reset 때문에 반쪽 스윙을 완전 주기로 잇지 않음 |
| stage hook | `partial(ex41.apply_runtime_fields,runner)` | 실제 소비값 불일치 거절. 승인 파일 변경과 rollback 재켜기 실패 모두 OFF+rejected |

광선 무효는 높이0 정답으로 간주하지 않고 해당 발 비용을 제외해 무효 비율을 남긴다. 로봇 상태 NaN과 구별한다. 몸 yaw90°에서 전진 광선이 world+y로 이동하는 입력과 발바닥 높이를 CPU로 확인했다. 접촉 판정1N, 이동 명령norm>.1, 앞광선 .05/.10m, 끌림 높이.02m·속도.05m/s는 우리 기록/설계 값이며 효과 미측정이다. 비용은 Spot `C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/spot/mdp/rewards.py:187~189` 꼴, 지수 출력은 쓰지 않는다.

미확인·통합 주의:
- runner 기존 `ex40_dr.require_launchable`은 EX41 DR schema를 바로 읽지 못한다. EX41 전용 진입 검증과 첫 reset 전 scale1 설정을 runner에게 전달했다. 기본값 verified를 근거 없이 붙이지 않는다.
- 점수 생산자의 `foothold-ex41-score/1` 연결과 runtime `finished/stop_requested` 소비는 runner/scripter 통합 후 실제 경로 시험이 필요하다. S2a/S2b는 임의 회차 상한을 만들지 않았다.
- 활성 물리/action/관측 NaN은 env 단위 처리하지만 전역 신경망 parameter NaN, reset 후에도 지속되는 물리 이상은 복구됐다고 가장하지 않고 별도 오류로 남긴다. 정상적인 한 env NaN 복구는 CPU 확인, Kit 복구와 비용은 미측정이다.
- parser/저장 상태의 추가 엄격 검증 및 W71 실제 점수 입력은 독립 검토 범위다. 자동 stumble 상향은 발동 조건 미확정이므로 승인 범위 경계 변경만 구현했다. 실제 GPU 학습을 준비 완료로 선언하지 않는다.

## 13:18 부모·DR 설정 분리와 비용 overflow

13:0x 의뢰대로 m6000/m7500을 파서에서 모두 허용하고 `plan.initial_dr_scale`을 `domain_randomization.scale`에서 읽는다. runtime 초기값·n0 영수증 부모·DR wrapper가 이 값을 소비한다. runner도 **첫 reset 전 이 속성**을 써야 한다. 부모 checkpoint·tensor·optimizer 이식은 scripter 소유이며 새 부모 실행 승인은 아니다. 기존 YAML m7500/1은 보존했다. m6000/.5 후보도 초기 경계 파일의 dr가 .5/0이어야 시작하며, 이전1/0 파일을 그대로 써서 첫 reset 뒤 몰래1로 뛰는 반례를 거절한다. 이후 목표/길이는 승인된 W72 경계 설정으로 현재값에서 램프가 계산된다. 자동 단계별 목표 배정은 아직 설계 미확정으로 추가하지 않았다.

확인됨: 두 실제 파일의 SHA256을 직접 읽음. m6000 `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5`, m7500 `3a2cd2902c77b069ef1072d08e8254deadf663b56a9c95be704b07db52db2368`. CPU는 두 후보 초기값·중간값·도달값과 초기 mismatch, **59통과5.89초**, pyflakes/diff check 오류0. 부모·DR 반례 수정 전3실패. 이 시험은 checkpoint 해시 확인과 runtime 일정 소비 시험이며 새 부모의 신경망 이식 성공을 대신하지 않는다.

## 13. 080d0a4a 검토 후속 묶음 · 11/02 13:36

확인됨: lead 막음3과 verifier H1/H2를 한 후속본으로 고쳤다. 새 반례14개 모두 수정 전 실패, 수정 후 관련 CPU 합계 **78통과15.23초**, pyflakes·diff check 오류0. Python은 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe`, CUDA_VISIBLE_DEVICES 빈 값으로 실행했다. GPU·실행 EX40·실행 원장 변경 없음.

| 지적 | 소비 경로의 고침 | 답을 아는 시험 |
|---|---|---|
| 점수 JSON 하나로 학습 종료 | 해시 읽기도 try 안, 최상위 dict와 evidence dict 검증, 오류 기록 후 이웃 정상 파일 계속 소비 | 목록 JSON·*.json 디렉터리·scan 뒤 파일 소실 각 반례 |
| 큰 유한 발 높이 | 지형 상대 높이/목표 오차5m 초과 또는 swing 비용100m² 초과 env만 격리 | 1e6m 발 높이, 유한 비용101, world 높이1000m지만 상대 높이 정상은 유지 |
| smoke 경계 누락 | smoke 명시 경계만 순차 소비, 마지막+2에서 끝, 본판250경계 유지 | (1,3,5,7)에서 네 전환·9끝. smoke는 졸업=false. W71 미준비면 S2b에 남음 |
| H1 자동 몫 상한 우회 | D93 승인 상한을 파서와 소비 함수 둘 다 +/−1 %p, 누적+/−2 %p 이하로 제한 | YAML step/limit .05와 직접 함수 .05 거절. 동률 .02→.01→0 |
| H2 오류 설정이 안전 점수를 가림 | 경계 설정 검증 전에 증거 검증된 안전 점수를 읽어 stop_requested에 반영 | 금지 clip_param 입력과 safety_stop=True 점수를 같이 줘도 중단 요구 유지 |
| _effective 예외·다음 단계 몫 | 순수 계산 실패도 rejected, 다음 단계 몫으로 명령 제거 반례 검사 | 계산 ValueError 반환·현재 몫엔 맞고 다음 몫엔 안 맞는 짝 변경 거절 |
| DR 경계 점프 | 부모 m6000=.5·m7500=1 고정 대조, 목표 변경 시 양의 ramp_updates 필수 | 잘못된 부모/배율 조합·길이0 목표 변경 거절 |
| W71 대기 사유 | 성과 자료 부족과 w71_not_ready를 따로 기록 | 두 성공 점수지만 W71=False인 S2b 유지 |

5m·100m²는 정상 높이를 학습시키는 문턱이나 보상 자르기가 아니라 이상 수치 격리용 코드 상한이다. 100=4발×5²로 계산했다. 대상 env의 해당 transition은 PPO에서 버리며 전체 학습을 중단하지 않는다. 실제 Kit 물리 오탐률은 미측정이다.

격리 계약은 `extras['ex41_ppo_valid']` bool[N]으로 확정. `quarantine_actions`의 pending을 포함해 매 step 반환하고 pending을 비우기 전에 복제한다. 정상 done은 True, 격리 행만 False. 기존 log_prob0·mean0·sigma1 채움은 수치 방어용일 뿐 학습 제외를 대신하지 않는다. **advantage 정규화·GAE·모든 손실·KL·거울 손실 유효 분모 소비는 scripter 변경이 필요하며 이 커밋만으로 통합 완료가 아니다.** 해당 PPO 시험과 통합본 두 겹 검토는 미확인.

n0 적용·resume·부모6000/7500 세 시험 함수는 항등 hook·가짜 승인 해시 대신 `tests/ex41_runtime_fixture.py`의 실제 임시 Git 커밋과 `apply_runtime_fields` 소비 함수를 쓴다. 나머지 단위 반례의 의도적인 오류 주입 mock은 유지했다. 실제 시뮬 소비 성공을 뜻하지 않는다.

13:3x 최신 방향은 부모m6000, DR 켠 평가1.0이다. 새 단계 길이·S2d·고정 회차 승급은 논의 중이다. 본 후속본은 앞 검토의 오류 수정 범위이고 기존 YAML m7500/1·5단계 성과승급을 새 실행 승인으로 쓰면 안 된다. 새 일정 채택 뒤 그 설정·상태복원·끝점 시험을 별도 반영해야 한다. 의견은 `OPINION-EX41-RAMP-1333.md`에15줄로 보존했다.

## 14. 막음 0 뒤 남은 세 항목 · 11/02 13:43

lead가61deb654 독립 재검에서 막음0·78개 재현을 보고했다. 추가 낮은 항목 셋도 고쳤다. (1) 큰 유한 몸 yaw100rad/s 초과를 env 단위로 격리한다.100은 명령 상한1.5보다 충분히 큰 이상 수치 검사용 상한이며 실측 안정 한계가 아니다. (2) 설정 오류 경계에서 읽은 점수는 history에 보존하고, 고친 다음 경계에 아직 신선하고 미소비인 최신 점수로 자동 조정을 한 번 적용한다. 만료·다른 단계·이미 적용한 점수는 재사용하지 않는다. (3) `test_ex41_runtime_cpu.runtime()` 자체를 실제 임시Git 파일과 `apply_runtime_fields` 소비 함수로 바꿨다. 가짜 a/b/c 해시 helper는 제거했고 설정 오류도 파일을 고쳐 커밋한 뒤 실제 reader로 거절한다. 실패 동작 주입 전용 callback은 반례 목적상 유지한다.

확인됨: 큰 yaw1e6·거절 뒤 점수 재사용 반례2개는 수정 전2FAIL, 고친 뒤 관련6파일 **80PASS64.78초**. Git 파일 생성/대조가 늘어 시험 시간이 길어졌다. pyflakes·diff check 오류0. PPO 소비와 새 일정은 §13의 미확인 범위 그대로다. 이번 추가 고침도 GPU·실험 원장·EX40 실행 사본을 바꾸지 않았다.

W86는 유한 입력도 제곱 비용에서 overflow가 날 수 있음을 답 아는 큰 torque 입력으로 재현(수정 전1실패). 파생 비용의 비유한 행도 env 단위 quarantine하고 집계는 float64로 올렸다. 기록이 마지막 flush에서 NaN 때문에 터지는 경로를 막았다. CPU 정상 env와 유효 집계 보존 확인. 전역 오류·Kit 한계는 위 절 그대로다. DR의 요청 배율과 실제 env별 물리 분포는 다르며, reset/interval 이벤트로 차츰 소비되므로 readback을 함께 확인해야 한다.

## 15. 실제 PPO 소비 연결에서 발견한 공유 std 오염 · 11/02 13:57

확인됨: scripter 고정본 `36f6cddf4eb7e34ba21a7c6a0aa95f34dbfc34bd`를 별도 읽기 사본 `C:/mai/wt/foothold-lab/analyst-ex41-consumer-36f6cddf`에 두고 실제 isaac311 PPO와 연결했다. `transition.action_sigma`가 정책 std의 expanded view여서, W86가 불량 행을1로 채우면 정책 전체 std가0.46에서1로 바뀌었다. dict·TensorDict 원본 보존2개와 실제 PPO 연결4개, **수정 전6FAIL8.91초**로 재현했다. 앞의 생산자 단위 통과는 이 통합 안전을 입증하지 못했다.

고침: `_sanitize`는 원본을 수정하지 않고 별도 tensor 저장공간을 반환하며 transition 필드를 그 복사본으로 교체한다. 중첩 dict와 TensorDict의 형식·batch_size를 보존한다. 코드 공유나 실행 EX40 수정 없이 analyst 소유 `w86_runtime.py`만 고쳤다.

확인됨: W86 runtime·비용·PPO bridge **35PASS6.90초**, 경고0, pyflakes·diff check 오류0. bridge는 거울 끔/켬과 일부/전부 격리 네 조합에서 pending을 비우기 전 bool[4] mask 전달, 정상 std0.46 보존, 정상 행 GAE/advantage, 손실·adaptive learning rate·갱신 뒤 parameter 동등성을 확인한다. 전부 격리면 optimizer 갱신0이다. 원본 observation도 보존한다. 시험 명령: `EX41_PPO_CONSUMER_ROOT`를 위 고정 사본으로 두고 `python -m pytest -p no:cacheprovider foothold_s2/tests/test_w86_runtime_cpu.py foothold_s2/tests/test_w86_preparation.py foothold_s2/tests/test_ex41_ppo_bridge.py -q`.

소비자 자체 시험도 별도 확인했다:16PASS2SKIP14.80초 후, 실제 m6000/m7500 경로·SHA·coordinate_metadata 환경변수로 누락된 부모 두 시험을 다시 실행해2PASS7.45초. 이 소비자와의 CPU 계약 확인이며, 전체 StartRunner·Kit·GPU·지각 replay/phi 손실의 격리까지 검증했다는 뜻이 아니다. 시작 설정 `ex41_w86_required=true`와 실행 진입점 연결은 runner 통합본에서 확인해야 한다. scripter 후속68cffa0f는 fixture/test만 바뀌었고 실행 파일 diff0이다.

14:0x 확정 5000회·부모m6000·DR.5 시작·유지/재개 일정은 다음 별도 구현 단위다. 이 std 수정 커밋의 옛 일정 YAML로 본기동하지 않는다.

## 16. 14:0x 확정 실행 일정과 DR 유지·재개

실행판은 `foothold_s2/curriculum/ex41-fixed5000.yaml`이다. 이전 `ex41.yaml`은 앞 검토·회귀 시험용으로 보존한다. factory 시그니처는 같고 새 계획만 `EX41FixedRuntime`으로 보낸다. 기존 EX40 `Plan/Runtime`은 그대로다. 부모 m6000 SHA는 `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5`이며 n은 부모 회차를 더하지 않은 추가 학습 회차다. n0부터 S2a의 보상·몫을 등록하고 첫 학습은 n1이다.

| 단계 | 기본 추가 회차 | 길이 | DR 요청 배율 | 지형 · 지도 |
|---|---:|---:|---|---|
| S2a | 1~750 | 750 | 0.5 유지 | L0~2 고정 · GT |
| S2b | 751~1750 | 1000 | 0.5→0.65 | L0~2 고정 · GT |
| S2c | 1751~2750 | 1000 | 0.65→0.8 | L0~2 고정 · GT |
| S2d | 2751~4000 | 1250 | 0.8→1.0 | 성과 승강 · 상한 L5 · GT |
| S2e | 4001~4500 | 500 | 1.0 유지 | 성과 승강 · 상한 L5 · GT |
| T0′ | 4501~5000 | 500 | 1.0 유지 | 성과 승강 · 상한 L5 · AdaSmpl 강제 해제 |

회차 표는 유지·연장 없는 경우다. 램프는 완료 회차 기준으로 .15/1000, .15/1000, .2/1250이고 다음 경계에서 목표 배율에 닿는다. 상승 구간에서 DR을 유지한 동안 일정 진행도도 멈춰 뒤 단계가 같은 만큼 늦어진다. 성과가 먼저 나와도 단계 길이를 줄이지 않는다. 끝났다는 표식은 졸업을 뜻하지 않으며 최종 판단을 요청한다.

유지 기준은 직접 SHA를 확인한 `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/scores-b/score_6000_d5e9ec400f33.json`이다. SHA `a1457a3d9ff780bac2804f0949875e305559fa761dc609be09c33ee9a19b85a6`. `cells`의 GT13·몸감각만13·복원13, 총39개의 `alive_envs_at_end`를 읽는다. `flat_stand`는 제외한다. 비교 기준은 단계마다 바꾸지 않고 이 부모로 고정한다.

점수 생산 계약은 기존 `foothold-ex41-score/1` 안에 `metrics.maintenance_counts={cell:{passed:int,baseline_passed:int,total:64}}`를 더한다. key39개는 `ex41_fixed.CELLS` 정본이며 복원 모드 `_record_only` 접미사도 유지한다. `baseline_checkpoint_sha256`은 항상 부모m6000이다. 빠진 칸·다른 분모·바뀐 baseline 값은 회복 증거로 쓰지 않는다. 생존 숫자 비교이며 추종 오차나 보행 전체의 합격을 대신하지 않는다.

- 어느 유지 칸이든 현재 생존 수가 부모−3보다 작으면 다음 DR 상승을 유지한다. 정확히 부모−3은 허용한다. 자료가 없거나 잘못되면 상승 구간에서 증거 부족 유지로 기록한다.
- 새로운 250회 간격 평가 두 개에서39칸이 모두 부모−3 이상이면 같은 기울기로 재개한다. 같은 평가를 두 번 읽거나500회 떨어진 두 평가를 연속 회복으로 세지 않는다.
- 유지 누적1000회 소진 뒤에도 미회복이면 현재 배율을 고정하고 남은 단계는 진행한다. T0′가1.0 미만에서 끝나면 `full_dr_reached=false`로 보고한다. 강제 배율 상승·새 학습 중단은 없다.
- 자동 보상 변경은 어느 모드든 `stand_min_passed<61`일 때 스윙 크기만 한 번 반감(−10→−5). 회전 L1·걸림 등은 그대로다. 자동 짝 몫·일반 보상 반감·거울 켬은 이 실행판에서 작동하지 않는다.
- D110 +500 한 번은 S2e 끝에서, DR1.0·유지통과·정지61/64 이상·기존 지형 레벨 상승0.5 조건을 모두 만족할 때만 붙는다. 이 조건은 새 효과 실측이 아니라 앞 결정의 등록 조건이다.
- 명목5000, DR유지최대1000, 선택연장500으로 실제 추가학습 상한6500. n5001(최대6501)의 시작 hook에서 완료를 확인하고 그 회차의 rollout은 하지 않는다. 시작 스크립트는 이 상한과 runtime.finished를 함께 소비해야 한다.

고정 일정과 W72 수동 변경을 분리했다. 새 경계 파일이 잘못되면 거절 영수증을 남기고 이전 승인 설정으로 등록된 일정·DR 유지 판단은 계속한다. 잘못된 설정이 안전 점수나 유지 판단을 가리지 않는다. 값은 고정 스냅샷으로 소비하며 기존 safety_stop은 별도로 유지한다.

시작 전 남은 연결: `ex41_w86_required=true`, m6000 이식, 점수39칸 생산, W71 실제 소비 확인. 새 경계 YAML의 `w71_ready=false`는 미검증 표식이다. **W71 확인과 승인 필드를 넣은 커밋 없이 fixed 실행은 시작을 거절한다.** smoke는5경계 `(2,4,6,8,10)`로6단계, n12 완료이며 졸업 증거가 아니다. runner는 기존4경계 smoke를 그대로 쓰면 안 된다. 새 W57/기록 항 제안은 정지 진입 각속도·누적 heading 흐름·후진 횡이탈이며 새 벌점은 없다.

확인됨: 새 일정15시험과 기존 회귀·PPO 연결을 합쳐 **101PASS119.25초**, isaac311·CUDA 숨김. pyflakes·diff check 오류0. 정확히 부모−3/−4 경계, 어느 한 복원 칸 저하, 누락 칸·다른 baseline, 두 연속 회복·동일 점수 재사용·평가 회차 간격,1000소진 후6000회 종료, D110 연장 후5500회 종료, pause 중 저장·재개, 조기 성과로 길이 단축 금지, 새 과제 미달 때 고정 단계 진행, 정지 복원 한 번,5경계 smoke, 잘못된 경계 설정과 안전 점수/DR 유지 동시 입력을 확인했다. 새 일정 완료는 졸업=false로 남긴다.

부모39칸 생존 범위는60~64였다. 가장 낮은 `probe_prop_only/back1.0`은60이므로 그 칸 유지 하한은57이다. 이 규칙은 부모보다 크게 떨어지는지 보는 비교이며, 절대 생존61/64 관문으로 바꿔 말하면 안 된다. `flat_stand`의 별도61/64 조건과도 다르다.

GPU·Kit·실험 중인 EX40·그림자 루프·실행 원장은 변경하지 않았다. 통합 두 겹 검토와 실제 예행은 별도다. score의 stage_id·local n·39개 cell·증거 SHA를 만드는 runner 경로가 아직 소비 계약을 맞춰야 한다.

## 17. ced6c43a 경계 반례와 점수 생산 계약 고침 · 11/02 14:2x

lead 지적을 한 후속본으로 처리했다. R20에 따라 실제 부모 점수 파일을 helper에 넣었고, M14에 따라 **수정 전 반례 8개가 모두 실패(12.13초)**하는 것을 확인했다. 반례는 상한 경계 두 번째 회복, 늦은 경계의 유지 예산 초과, 낡은 점수 재사용과 무경고, 잘못된 저장 회차·시계 네 경우, 정지 점수 누락이다. 수정 후 시험 수와 시간은 아래 검증 기록에 적는다.

| 지적 | 고친 소비 경로 | 답을 아는 입력 |
|---|---|---|
| A: 상한 소진이 회복을 가림 | 회복 두 경계를 먼저 확인하고, 아직 미회복일 때만 현재 배율 고정 | n751 유지, n1501 회복1, n1751 회복2이면 재개. n2001 DR=0.5375. 미회복이면0.5고정 |
| B: maintenance_counts 생산 계약 없음 | `build_maintenance_counts(native_score, baseline, *, total_envs)` 추가. 정확한39/26키와64분모 검증 | 실제 m6000 파일. `alive_envs_at_end=60`, `passed_envs=64`가 함께 있어도 passed=60. alive 없는 입력 거절 |
| 점수 두 경계 누락 | `maintenance_evidence_missing_warning`에 누락 연속 횟수·필요 칸 수·점수 회차 기록, 재개 상태에도 보존 | 점수750 뒤 n1001·1251에서 새 점수 없으면 n1251 경고 |
| 낡은 점수·단계 전환 이력 | 회복·정지 복원·연장 판단은 `n−250 ≤ 점수 회차 < n`만. 단계 전환 때 부모 비교 이력 보존 | n1001에서 점수750은 회복 증거 아님. 보존 이력이 최신 창을 대체하지 않음 |
| 거절 뒤 시계 되돌림 | 소비자가 설정을 거절해도 지나간 시간·유지 예산은 되돌리지 않음. 적용 안 된 연장 결정만 되돌림 | n1501 적용 거절 뒤 n1751에서도 유지 예산1000, 저장·재개 가능. 늦은 경계도 예산1000 초과 없음 |
| 정지 누락·상수 문턱 | 승인 설정 `automatic.stand_min_passed=61`을 읽음. 값 누락은 `stand_evidence_missing`, 반감·연장하지 않음 | 누락을64로 간주하지 않음. 승인값60으로 바꾼 계획 거절 |
| 저장 시계 검증 | anchor·last_boundary·저장 회차·마지막 점수 회차 형식/순서, 경과+유지=anchor−1 대조 | 문자열·미래 점수 회차·잘못된 anchor·누적 회차 불일치 거절 |
| 유지+연장 끝 경계 | 유지1000과 연장500이 모두 있으면 n6501에서 종료. 그때 등록된 안전 중단이 있으면 안전 중단 우선 | 정상 종료와 safety_stop 두 경우를 각각 저장·재개까지 확인 |

점수 reader의 최대 나이500은 과거 증거와 등록 안전 점수를 읽는 범위로 남긴다. 실제 자동 판단의 최신 창은250이다. 이 둘은 다르며, 오래된 정상 점수로 DR을 다시 올리지 않는다. 지형 상승 계산에 쓰는 단계별 `_level_history`는 이전대로 새 단계에서 비운다. 부모 유지 비교의 `_history`만 보존한다.

### runner가 잇는 정확한 계약

```python
from foothold_s2.curriculum.ex41_fixed import baseline_counts, build_maintenance_counts
baseline = baseline_counts(plan)  # 고정 부모 파일의 SHA와 m6000 일치 검증
metrics['maintenance_counts'] = build_maintenance_counts(
    native_score, baseline, total_envs=64,
)
```

`passed`는 `native_score['cells'][key]['alive_envs_at_end']`다. 추종 성공률이나 `flat_stand.passed_envs`가 아니다. `baseline_passed`는 SHA 고정 부모의 같은 생존 수다. 각 행은 `{passed: int, baseline_passed: int, total: 64}`만 가진다. 실제 배치64개 확인은 생산자 몫이며, helper에64라고 적는 것만으로 실측을 대신하지 않는다. helper가 score envelope의 체크포인트·원자료 SHA, 단계명, local iteration을 만들어 주지는 않는다. runner는 기존 검증된 envelope에 이 metrics를 연결해야 한다.

키 정본은 `maintenance_cells()`다. 세 모드는 `eval_gt/`, `probe_prop_only/`, `eval_pred/`이며, 명령은 fwd0.5·fwd1.0·spin+1.2·spin-1.2·back0.5·back1.0·side+0.5·side-0.5·diag-fwd+side+·diag-fwd+side-·diag-back+side+·diag-back+side-·stop의13개다. 복원 모드 키 끝에는 `_record_only`가 붙는다. `flat_stand`는 포함하지 않는다.

`fixed_schedule.include_record_only: true`가 기본39칸이다. false이면 GT·몸감각26칸만 DR 유지에 쓴다. **false 채택은 아직 팀장 미결**이며 기본값은 바꾸지 않았다. 바꾸면 계획 SHA가 바뀌므로 기존 판과 같은 계획이라고 기록할 수 없다. 26칸 선택 시험은 복원 한 칸의 생존0을 유지 판정에 넣지 않는 반례로 확인한다.

확인됨: 최종 일정 시험 **34PASS77.90초**, 관련 경계·회귀 **23PASS28.14초**, 합계 **57PASS**. 명령은 `python -m pytest -p no:cacheprovider foothold_s2/tests/test_ex41_fixed_cpu.py -q` 및 `python -m pytest -p no:cacheprovider foothold_s2/tests/test_ex41_boundary_cpu.py foothold_s2/tests/test_ex41_review_regressions.py -q`다. 실행 경로는 isaac311이며 GPU를 숨겼다. 남은 통합 확인은 runner의 helper 실제 연결, W71·유효 PPO mask의 실행 경로, 통합본 독립 검토와 승인 뒤 Kit 예행이다. 본 후속본으로 실행 승인이나 GPU 검증 완료를 주장하지 않는다.

결정·작업 연속성은 [이슈 #555의 직전 기록](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6569612303)에 이어 남긴다. 이 문서는 analyst가 정리했다. pyflakes와 git diff 검사는 통과했다. own worktree에는 review_inbox.py가 없어 lead 사본으로 읽었다. 그 검사기는 문서의 확인됨 표기를0개, 금지 줄표를205개로 보고하여 자동 문서 검사는 통과로 적지 않는다. 별도 문자 검사에서 U+2014는0개였고, 이 문서의 확인됨 문장은 위에 보존했다. 검사기 수정은 이 후속본 범위 밖이다.

## 18. G5·G6·G7: 최신 오류 보존과 원자료 점수 생성

G4는 a0581766에서 상한 회복 우선 시험으로 처리했다. 그 뒤 verifier H1/H2와 lead G5~G7을 받았다. 시간창을250으로 줄이는 것만으로 충분하지 않았다. 실제 reader에 n1000 정상 → n1200 정상 + n1250 NaN/체크포인트 SHA 오류/정지 숫자 누락을 넣으면 **수정 전 세 경우 모두FAIL14.42초**였고 DR이 다시 올라갔다.

고침: 점수 파일의 최신 오류를 `score_rejections`로 따로 보존하고 저장·재개에도 잇는다. 경계의 최신 오류 회차가 정상 점수보다 같거나 크면 `latest_score_invalid_hold`로 남기고 과거 PASS를 사용하지 않는다. malformed JSON·잘못된 iteration도 파일명의 회차를 보고, 회차를 알 수 없으면 관측한 현재 창의 미확인 증거로 남긴다. 새로운 유효 점수가 두250경계 연속으로 와야 DR을 재개한다. 오래된 오류 자체가 이후의 더 새로운 정상 점수를 영원히 막지는 않는다. 같은 회차의 상충 파일도 정상 점수로 숨기지 않는다.

`stand_min_passed` 누락은 고정 일정뿐 아니라 EX41 reader에서 불완전 점수로 거절한다. 옛 자동 조정 함수의 누락64 기본값도 제거했다. 오류가 난 최신 점수는 유지 판단에서 증거 부족이다. 신원과 원자료 SHA가 확인된 등록 안전 중단은 정지 지표 완전성 검사보다 먼저 읽어 보존한다.

숫자 생성의 정본은 `curriculum/ex41_scoring.py`다. runner의 `ex41_score.py`·`scripts/ex41_startup.py`는 읽었으며 직접 고치지 않았다. 아래 함수가 기존 draft를 받아 정확한 숫자와 증거 SHA를 붙인다. stage_pass·safety_stop은 기존 등록 판정을 보존하며 새 문턱을 만들지 않는다.

```python
enrich_score_metrics(draft, map_modes_path, stand_paths, plan)
# stand_paths: eval_gt / probe_prop_only / eval_pred 각각의 stand.json
# 반환 metrics: maintenance_counts, stand_counts, stand_min_passed
```

`maintenance_counts_from_map_modes`는 세 지도 모드, extended13명령,64개 고유 env 번호와 alive boolean 합을 대조한 뒤 §17의 helper 하나로 변환한다. `measurement_bundle`은 실제 checkpoint SHA·명령값·평가300스텝·지형 manifest와 각 stand_raw.npz SHA도 확인한다. 정지 성공의 발 접촉·하중·틈·몸속도·yaw 정의는 기존 `ex40_score._stand_rows/_stand_pass`를 재사용했다. EX40의 전체 성공 문턱60을 EX41에 가져온 것이 아니다. 여기서는 모드별 통과 숫자만 만들며 EX41 복원 조건은 승인된61이다.

확인됨: m6000의 `score-watch-b/model_6000_d5e9ec400f33/map64/map_modes.json`이 부모 유지 기준의 원본이다. extended13명령×3모드로 **39/39 숫자 일치, 차이0**. 정지 세 모드는64/64·64/64·64/64로 부모표와 일치했다. `map64_b3`는 walk·작은 spin·저속의9명령으로 별도 과제이며 유지39칸을 대신하면 거절한다. 이 선택은 새 기준 선택이 아니라 SHA고정 부모표의 실제 출처 대조다.

읽기 전용 재계산 산출은 [부모 숫자 계약 JSON](evidence/EX41-m6000-score-contract.json), SHA256 `ddd06c8eaa542ad81bf088d858d229e3a539d0a7e87ed09bc49761145a586e25`다. 이 파일은 실행 원장이나 살아 있는 EX41 점수가 아니다. 원자료 경로·SHA와 칸별 숫자를 보존한 CPU 대조 자료다. 시험은 별도 임시 폴더에 score/1 파일을 생성하고 되읽어39칸·정지 숫자를 확인한다.

검증 기록: isaac311·CUDA 숨김으로 fixed/runtime/boundary/review_regressions/scoring 다섯 시험 파일 **96PASS170.29초**, pyflakes·git diff 검사 통과. 실제 reader의 NaN·체크포인트 SHA·원자료 SHA·정지 숫자 누락·깨진 JSON·잘못된 회차 반례와 오류 상태 저장·재개 뒤 새 점수 두 개의 회복을 확인했다. G5·G7의 runtime 고침과 G6 helper/원자료 대조를 닫을 수 있어도, G6 전체는 runner 진입점이 이 함수를 실제 호출하는 통합본을 확인해야 닫는다. 낮은 항목 D121 과제 변경 평가 연결·W72 추가 승인 칸·D93 히스토그램은 이 커밋에서 닫았다고 하지 않는다. 후속 교차검증의 명령 몫2차 S2c 이동과 m6000 lin_vel_z 실측은 이 묶음 다음 작업이다.
