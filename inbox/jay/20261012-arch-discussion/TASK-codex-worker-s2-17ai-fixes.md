> 분류: A/정책학습 · Codex Worker 작업서 (sol) · ASTRA 17ai 의 실제 결함 고치기와 발 광선 단회 실행 경로 (step16)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 21:11
> 근거: `VERIFY-astra-17ai.md` 1~2절 (평가기 P1 둘 · 변환 상한 · 환경 생명주기 · 발 광선 P1 · 정답표 · 허용치) · 5절 (막힐 세 곳) · step13 · 14 · 15 사본
> 요지: 평가기와 발 광선 단회가 CPU 시험은 통과해도 실제 기동 순서에서는 막힌다는 것을 ASTRA 가 설치된 소스로 재현했다. 이 결함들을 한 묶음으로 닫고, 발 광선 학습 0 단회의 전용 실행 경로를 완성한다. 원인 확인용 GPU 동의를 쪼개 반복하지 않도록 변경분과 양성 대조 · 반례 증거를 같이 낸다
> 상태: 작업 지시 (CPU 만 · GPU · Isaac 기동 금지 · 승인 json 은 만들지 않는다)

# sol 작업서: 17ai 결함과 발 광선 실행 경로 (step16)

## 0. 지킬 것 · lead 결정값

step15 와 같다. 새 사본 `codexE/s2_step16/` (step15 를 복사해 시작; 이전 폴더 · 저장소 · `_eval` 은 읽기만). `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I -B`. 정상 먼저, 변이는 지정 첫 FAIL, 정상 PASS 와 변이 단계 선행 PASS 를 합쳐 쓰지 않는다. 해시 목록 CR 없이, **번들 안에 닫히게**(번들 밖 형제 폴더를 읽는 시험 금지; 이번에 step15 첫 인도본이 그 때문에 격리 복사본에서 실패했다). 인도 때 **B 전체 회귀**(run_all_s2_step9.py 깨끗한 복사본)와 평가기 / 발 시험 전부의 증거를 같이 낸다. 해시 목록과 보고서 안의 파일이 서로 맞는지 마지막에 되읽는다.

lead 결정값(발 광선 허용치, 17ai 권고 채택): 알려진 분석적 평면 / 절벽의 비경계 표본에서 ray hit XY 와 Z 오차 각 **0.001 m 이하**, USD collision 중심과 독립 계산 world 좌표의 거리 **0.001 m 이하**. 별도 경계군: 모서리 XY 0.005 m 이내, 높이 20 cm 경계 ±0.002 m, 접촉 1 N 경계 ±0.05 N (위험 식의 부등호는 느슨하게 바꾸지 않는다; 각 장면에 비경계 표본을 충분히 두고 필수 경우의 누락은 HOLD).

## 1. 평가기 (step14 `s2_eval_*`)

1. **P1-a 첫 reset 초기화 순서.** `s2_eval_kit_adapter.py:95` 가 등록한 reset 함수가 `env._q_yaw`(`:63`)를 읽는데, `:173` 에서 `RslRlVecEnvWrapper(gym.make(...))` 를 먼저 만들고(`vecenv_wrapper.py:66` 의 생성자가 reset 을 부른다) `:185` 에서 `_q_yaw` 를 설정한다. 원래 환경을 먼저 보유하고 첫 reset 이전에 필요한 상태를 모두 초기화하도록 순서를 고친다. 래퍼 생성 도중 실패해도 환경을 닫는다(factory `:338~342` 정리가 `self.env` 에 의존하지 않게). `s2_eval_driver.py:235~250` 은 예외를 기록한 뒤 다음 case-arm 으로 가므로, **공통 초기화 · 정리 실패는 뒤 case 생성도 중단**하게 한다(case 고유 실패와 구분). 시험: 실제 래퍼 생성자 함수를 AST 로 추출해 실제 adapter / reset 함수에 모의 환경을 연결(ASTRA 재현과 같은 방식)하여 `_q_yaw` 누락 · 정리 누락이 재현되는 것을 먼저 보이고(반례), 고친 뒤 양성 대조 통과. 생성 도중 실패에도 close 가 정확히 1회.
2. **P1-b update 0 신원.** A / B 체크포인트의 실제 `s2_control` 내용을 검증한다: `completed_updates == 0`, `next_update_index == 0`, optimizer step 0, 부모 · 환경 · plan · encoder 설정을 job 과 대조하고 영수증에 남긴다(`s2_eval_driver.py:44~94`, `s2_eval_cpu.py:68~102`). 이후 학습 체크포인트(update 200 간격 · 2,000)도 요청 update 와 연결한다. 시험: `s2_control={}` 거절, `completed_updates=2000` 인데 job 이 0 이면 거절.
3. **변환 횟수 하드 상한.** `expect_conversions=any`, 상한 8 은 사후 감시(`s2_eval_supervisor.py:263~273`)가 아니라 **변환 생성자 진입 직전의 계수 관문에서 9번째를 거부**하게 한다. 8 까지 정상 대조, 9번째에 원 함수 미호출을 CPU 로 확인. 진입 횟수와 성공 횟수를 구분해 기록(8행 생성을 8번 변환 성공으로 쓰지 않는다). 각 case-arm → 변환 entry → 생성 USD → 실제 Robot 참조 연결을 증거에 추가.
4. **환경 생명주기.** 8개 환경을 닫고 다시 만드는 동안 Stage · SimulationContext · sensor hook · Warp mesh cache 가 다음 case 로 새지 않게. `ray_caster.py:425~428` 은 마지막 센서 객체 소멸 때만 공유 cache 를 지운다: `env.close()` 만으로 새 mesh 라고 단정하지 말고, case 별 실제 ray 답과 현재 USD tile 의 대응을 기록하고 어긋나면 해당 case 무효. pre-reset receipt(`s2_eval_kit_adapter.py:319~324` 가 버리는 것)를 증거에 남긴다. 자연 종료가 8회 중 없으면 그 분기는 「미시험」 으로 적는다.
5. **시간 단계 기록**: claim · 관찰자 준비 · lease · USD 잠금 대기 · Kit 시작 · case 별 생성 / 실행 / close · 가족 종료 / 반납을 나누어 남기고 단회 안에서 시간 한도를 다시 시작하지 않는다(900초 이하 · 절대 마감).
6. **HOLD 분류와 성공 문구** (17ai 1.2절): 환경 생성 / API · 부분 정리 · USD / 장치 / 해시 / 관찰자 / 마감은 운영 HOLD, pose · map · reset · mesh / 초기 상태 불일치는 자료 HOLD, 단순 넘어짐 · 통과 실패 · 정체는 성능 결과. 없는 case 를 실패 0 으로 채우지 않고 예정 8 · 실행 · 유효 · 미실행과 원인을 나눠 적는다. 허용 문구: 「학습 0의 4짝 연결 시험에서 검사한 경로만 확인, 미시험 분기 별도」. `INFORMATION_ONLY` · `comparison_ready=false` · `performance_verified=false`.

## 2. 발 광선 (step15 `s2_foot_*`)

1. **P1 자연 reset.** `s2_foot_query.py:148~158` 은 `episode_length_buf` 가 감소할 때만 episode 가 바뀐 것으로 본다. 설치된 `manager_based_rl_env.py:201~221,394` 의 순서(길이 증가 → reward 계산 → reset 에서 길이 0)에서는 첫 step 에서 끝난 episode 다음 첫 reward 의 길이가 1 이라 `1 → 1` 이 된다. **실제 reset ID / 세대에 연결**하고(길이 감소 추정 금지), 한-step 종료 · 일부 env reset · 명시적 reset 을 확인하는 시험(손으로 `tracker.reset` 을 부르는 시험으로 가리지 않는다). ASTRA 재현대로 `live_raycast` 실제 함수에 CPU 공급자를 붙여 `1 → 1` 반례가 `foot_frame_not_fresh` 로 실패하는 것을 먼저 보이고 고친 뒤 통과.
2. **정답표 정정.** `S2-FOOT-KIT-CHECK.md:20` 의 「직선 절벽 → 1」 은 틀렸다. 발 중심 (0,0), 간격 0.05 m, `x > 0.025 m` 의 지면을 -0.30 m 로 내린 직선 절벽은 격자 6 · 7 · 8 이 위험해 cardinal 과 diagonal 이 모두 켜져 비용 **3**, `x + y > 0.075 m` 모서리는 diagonal 8 만 위험해 **2**. 비용 1 을 시험하려면 cardinal 만 건드리는 좁은 홈 등 독립 geometry 가 필요하다. 장면 이름이 아니라 표본 좌표 · 독립 예상 hit · 접촉 조건으로 정답을 고정한다.
3. **전용 실행 경로 완성** (`s2_foot_kit_check` 범위): N ≤ 8, 총 300 control step, 학습 · optimizer 0, 명시적 wall 상한, 단회 claim · STOP · 가족 정리 · 독립 관찰자 · A3.4 감독기 계약 방식. 기존 A3.4 manifest 를 이름만 바꿔 재사용하지 않는다. 요청 검증 · 판정기 · 알려진 장면 생성(평면 · 직선 절벽 · 대각 절벽 · 유한 깊이 구멍 · 같은 장면의 다른 높이 / 위치 · 지지 / swing / reset) · 영수증. `kit_step_record(:166)` 는 300 step 제한과 실제 RewardManager 적분을 검사하지 않으므로 보강.
4. **RewardManager 실출력 대조.** `kit_step_record` 의 weighted reward 는 직접 계산한 `C × weight × dt` 이므로 그것만으로 실제 적용을 증명하지 못한다. Manager 의 해당 항 출력 / episode 누적과 독립 기대값을 대조하고, 기존 15 항 + 추가 1 항의 실제 이름 · 함수 · weight · dt 를 같이 남긴다.
5. 추가 필수 증거: 실제 USD 충돌구 중심 / 반경, body / contact ID 순서, 36개 ray 와 현재 collision mesh 의 대응, 유한 구멍 바닥 hit, 같은 단계 pose / force / hit, 비동기 reset. (Kit 에서만 확정되는 것은 계약에 그렇게 명시하고 CPU 증거와 구분.)

## 3. 끝나면

`REPORT-s2-step16.md` (결함별 재현 반례 → 고침 → 양성 대조, 변경 파일과 줄, 시험 수 · 변이 CAUGHT/전체, 첫 실패, 미확인), `S2-STEP16-SHA256SUMS.txt` (CR 없이, 번들 안에서 닫힘), #550 댓글 초안(미게시). lead 가 재실행한다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
