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

W86는 유한 입력도 제곱 비용에서 overflow가 날 수 있음을 답 아는 큰 torque 입력으로 재현(수정 전1실패). 파생 비용의 비유한 행도 env 단위 quarantine하고 집계는 float64로 올렸다. 기록이 마지막 flush에서 NaN 때문에 터지는 경로를 막았다. CPU 정상 env와 유효 집계 보존 확인. 전역 오류·Kit 한계는 위 절 그대로다. DR의 요청 배율과 실제 env별 물리 분포는 다르며, reset/interval 이벤트로 차츰 소비되므로 readback을 함께 확인해야 한다.
