> 분류: A/정책학습 · Codex Worker 작업서 (sol) · S2 B step8: ASTRA 17ae 가 찾은 결함 둘의 좁은 수정 (CPU 만)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 19:35
> 근거: `VERIFY-astra-17ae.md` 전문 (특히 1절 P1 · P2, 2절 사전 고정값, 3절 위임 범위) · 저장소 사본 `night-tools-20261013/s2_step7/` (lead 재실행 31/31 파일, 정상 273 라벨 = 정상 단계 271 + 변이 단계의 정상 선행 2, 변이 54/54)
> 요지: ASTRA 17ae 는 step7 의 닫힌 항목을 인정하면서 두 결함을 남겼다. (P1) CUDA 에서 저장 optimizer 상태 비교가 장치 불일치로 실패한다, (P2) 합성 입력의 별도 probe(+0.25)와 실제 합성 경로(-0.25)가 서로 다른 입력이다. 이 둘을 좁게 고치고 CPU 증거를 모으면 첫 plumbing 단회는 ASTRA 재의뢰 없이 lead 검증 기록 + 팀장 단회 동의로 진행할 수 있다
> 상태: 작업 지시 (GPU · Isaac 기동 금지 · 승인 json 은 만들지 않는다)

# sol 작업서: B step8

## 0. 지킬 것

- GPU · Isaac · 실제 `_eval` 슬롯 · 기존 코드 · 원자료를 **건드리지 않는다.** `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`. 새 작업 사본 `codexE/s2_step8/` (`s2_step7/` 와 저장소는 고치지 않는다). 정상 시험을 먼저 통과시킨 뒤 변이가 지정 첫 FAIL 라벨과 같을 때만 CAUGHT. em dash 금지. 첫 실패도 보고서에 그대로.
- 범위는 **아래 둘과 문서 정정뿐**이다. ASTRA 17ae 3절: 예외 무시, sensor/map 수학 변경, cfg 의미 변경, Job/잠금/격리 완화, native crash 우회, GPU 1 병렬화, iteration 확대는 포함하지 않는다.

## 1. P1: CUDA 재적재 뒤 optimizer 비교가 장치 불일치로 실패

사실(17ae): `s2_policy.py:598` 기본 Adam, torch 2.7.0+cu128 `adam.py:163-173` 은 `capturable=False` 이고 fused 가 아니면 parameter 가 CUDA 여도 `state['step']` 을 **CPU** 에 둔다. `s2_runner_17v.py:285-286` 이 그 상태를 저장하고, `s2_plumbing.py:126` 의 `torch.load(..., map_location=device)` 가 저장된 CPU step 까지 CUDA 로 옮긴다. 이어 `:141-143` 이 원래 optimizer 상태와 대조하고 `:94` 가 `torch.equal` 을 부르는데 CUDA 구현은 장치가 다르면 예외를 낸다. CPU 끼리의 기존 시험은 이 오류를 잡지 못했다(ASTRA 독립 CPU 소시험: 실제 Adam step 의 원래 장치는 cpu, `map_location='meta'` 로 읽으면 meta 로 이동).

수정(ASTRA 최소안): 저장 optimizer/control 과 현재 상태를 **장치와 분리한 내용 비교**로 대조한다. checkpoint 를 CPU 로 읽고 양쪽 tensor 를 `detach().cpu()` 한 뒤 key · shape · dtype · 값을 재귀 비교한다(key/shape/dtype 누락 허용 없음). policy 는 새 CUDA 객체에 strict load 하고 같은 입력 action/value 오차는 계속 잰다. **optimizer 검사 삭제나 device 예외를 PASS 로 바꾸는 것은 수정이 아니다.** 이 비교를 통과해도 환경 resume 성공이라고 쓰지 않는다.

시험(정상 먼저): 정상 E1 CPU roundtrip 통과. 반례(각각 지정 mismatch 에서 거절): 디스크 optimizer 의 `step` 하나 변경 · moment(`exp_avg`) 하나 변경 · control 상태 하나 변경 · key 하나 누락 · shape 불일치 · dtype 불일치. **장치 정규화가 비교보다 앞서 적용되는지** 소스로 확인하는 시험(변이: 정규화 제거 → 지정 라벨). 가능하면 `map_location='meta'` 또는 `torch.device('meta')` 로 읽은 step 이 서로 다른 장치가 되는 상황을 CPU 에서 만들어 비교 함수가 예외 없이 값 비교로 가는지 보인다(CUDA 가 없으니 meta 를 대역으로 쓰되 대역이라고 표기).

## 2. P2: 합성 입력의 정답 대조와 probe 가 서로 다른 입력

사실(17ae): 실제 합성 경로 `s2_train_entry_17v.py:197-226`·`:206` 은 `hit_z = root_z - 0.25` 이고 map offset 0.5 를 적용하면 유효 height 는 **-0.25**. 반면 `s2_plumbing.py:46-59` 의 별도 `known_input_probe` 는 `root_z=1, hit_z=0.25` → 유효 height **+0.25** 이고 자식 `result['known_input']`(`entry:446`)에 들어간다. 둘의 일치를 강제하지 않아서 rollout hash 가 실제 입력의 정답 대조처럼 읽힌다. -0.25 자체는 틀린 지형 수학이 아니다.

수정: (a) 실제 `IsaacS2Env` 의 capture → packet → map 경로(CPU 객체에 붙여서)를 정상/반례로 시험하고, **실제 기대값(-0.25, 첫 ray 의 miss/mask)과 tensor hash 를 그 경로에서 검사 · 기록**한다. 반례(hit 높이나 mask 를 바꾼 것)는 정답 검사에서 막혀야 한다. (b) `+0.25` probe 는 이름과 영수증 필드를 분리해 「함수 단독 probe」 로 표기하고 실제 경로 증거와 서로 다른 증거로 적는다. (c) A arm 은 원래 map 이 0 이라서 B 의 지도 정보 경로까지 증명하지 않는다 → 영수증/문서에 그렇게 쓴다. B 용 합성 map 은 별도 증거로 적는다. (d) `entry:468` 의 「no RayCaster data read」 는 **추가 actor map 주입부**에만 맞다. 설치 `robot_lab/tasks/go2/env_cfg.py:225-229` 의 critic height_scan 은 실제 `height_scanner` 를 계속 읽는다 → 영수증 문구를 「actor map 주입은 실센서를 읽지 않음, critic 의 height_scan 은 실센서를 읽음」 으로 정정하고 critic/입력 finite 검사는 유지. synthetic 은 전체 PPO 관측 · 보상에서 실센서를 제거하는 모드가 아니라고 `S2-STEP7-USAGE` 에 해당하는 문서(step8 판)에 박는다.

## 3. 첫 plumbing 사전 고정 요청 JSON 만들기 (ASTRA 17ae 2절 표 그대로)

`request_plumbing_A_first.json` 한 개를 `codexE/s2_step8/` 에 만든다(봉인은 하지 않는다). 값: GPU 0, UUID `GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b`, bus `41:00.0`, arm A, `input_path=synthetic_known_answer`, N=32, `updates=1`, `checkpoint_interval=1`, `rollout_steps=2`, `epochs=1`, `minibatches=1`, `encoder_mode=full_freeze`, LR schedule `fixed`, seed 11, map_init_seed 7, LR 0.001, 최대 wall 600, 완료 기대값 1 iteration / 2 vector steps / 64 transitions / 1 optimizer step. 나머지 필드(경로 · 마감 epoch · approval 경로 · 디스크 상한 등)는 `S2-STEP5-USAGE` 의 필수 목록대로 채우되 **팀장이 정할 값은 `UNDECIDED`** 로 둔다(마감 epoch · approval 경로 · 승인자). 디스크 상한은 CPU fixture 의 작은 값을 복사하지 말고 두 checkpoint + USD + 로그 크기를 산정해 근거와 함께 적는다(모르면 UNDECIDED + 필요한 측정을 적는다). 이 JSON 이 `s2_train_manifest.py` 의 UNDECIDED 거절을 제외하고 통과하는지 시험한다.

## 4. 문서 정정 (17ae 1절)

- 「지도 계산 모듈 6개가 A3 와 바이트 동일」 은 **5/6**: adapter · map_obs · sensor_tracker · policy · terrain_overlay 는 동일, `s2_ppo_17v.py` 는 다르다(loss · 그룹별 pre-clip grad · norm 기록과 비유한 grad 거절 추가). 학습 수식 변경이라고 단정하지 말고 차이를 줄 단위로 보고서에 적는다.
- 증거 수: 정상 단계 271 + 변이 단계의 정상 선행 2 = 273 라벨. 보고서 본문에 둘을 구분해 적는다. `evidence_s2_step7/final2/` 에 summary.json 이 빠졌다는 지적이 있다(저장소 사본 기준) → step8 증거에는 summary.json 이 반드시 들어가게 하고, step7 쪽에 없었던 이유를 확인해 보고한다.

## 5. 끝나면

`REPORT-s2-step8.md` (정상 PASS 수와 변이 CAUGHT/전체를 **구분해서**, 바뀐 파일, 첫 실패, 미확인), `S2-STEP8-SHA256SUMS.txt`, 수정 영향 시험(위 1~3 + plumbing 계약/실제 CPU PPO 시험) 재확인 결과. 닫힌 31개 전체를 의례적으로 다시 돌릴 필요는 없지만 시간이 되면 깨끗한 복사본에서 전체도 돌려 두면 좋다. lead 가 재실행해서 기록한다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
