> 분류: A/정책학습 · Codex Worker 작업서 (sol) · A3.4: ASTRA 17ah 의 조건을 A3.3 에 반영 + 배관 재시도의 Kit 안 기록 (step12)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 16:49
> 근거: `VERIFY-astra-17ah.md` 1절(설정 결함 · 실행 조건) · 2절(배관 재시도 기록) · 3절(연속 동의 조건) · 4절(첫 16 step 판별을 같은 Kit 안에) · `REPORT-s2-step11.md` (probe 도구 CPU 핵심, 실기동 연결 차단 사유) · `REPORT-s2-step10.md`
> 요지: ASTRA 가 PhysX 질의 전부 miss 의 직접 원인을 찾았다. 4차 `final_cfg.json` 의 `sim.enable_scene_query_support` 가 False(Isaac Lab 기본값, GUI 가 있을 때만 켜짐, 해당 실행은 headless)이다. 현재 A3.3 은 이를 포함하지 않는다. 또 첫 16 step 판별은 별도 16 step 도구가 아니라 **기존 256 step 의 첫 16 step 안에서** 관찰을 더하라고 했다. 이 둘과 자산 · USD 증거 보강을 A3.3 위에 얹은 묶음(A3.4)을 CPU 에서 만든다
> 상태: 작업 지시 (CPU 만 · GPU · Isaac 기동 금지 · 승인 json 은 만들지 않는다 · foot reward 작업서는 이 일 뒤)

# sol 작업서: A3.4 (step12)

## 0. 지킬 것

step10 · 11 과 같다. `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I -B`. 새 사본 `codexE/s2_step12/` (`s2_step11/` 과 `s2_step4a33/` 를 복사해 시작, 이들과 저장소는 고치지 않는다). 새 수집 묶음 이름 `s2_step4a34/` (A3.3 복사본 위에서 변경), 새 `SHA256SUMS.txt` (CR 없이). 정상 먼저, 변이는 지정 첫 FAIL. em dash 금지. 첫 실패도 보고서에. 지도 모듈 · 점검 코드(`s2_connect_check_17v.py`) · 허용 오차는 바꾸지 않는다(바꿔야 하면 이유와 줄을 먼저 보고하고 멈춘다). 단계 수는 **256 그대로**, 최대 900초 그대로. 16 step 을 더 앞에 얹으면 272 step 의 다른 실험이 된다.

## 1. A3.4 수집 묶음에 넣을 것

1. **scene query 지원을 켠다.** 수집 진단 cfg 에서 환경 / physics scene 생성 **전에** `sim.enable_scene_query_support = True`. 학습 cfg 는 건드리지 않는다(진단 cfg 차이로 `cfg_diff` 에 기록). 생성 뒤 실제 값을 되읽어 기록하고, 알려진 지면의 **양성 대조** ray 응답을 남긴다. CPU 시험: 켜짐 정상, 꺼짐(False)이면 거절, 학습 cfg 에는 안 들어감.
2. **첫 16 step 안의 관찰** (step11 의 `s2_physx_probe_diag.py` 핵심과 `s2_physx_probe_live.py` adapter 를 이 수집의 connect diag 에 연결): 
   - 알려진 세 위치(평지 · 솟은 면 · 구멍)를 로봇에 가려지지 않는 좌표로 명시. world 좌표 · 미터 · 방향 · 거리 상한 · scene path 를 기록. 구멍만 miss 인 것과 질의 기능 전체가 죽은 것을 구분.
   - 같은 물리 상태에서 tuple 과 `carb.Float3` 호출을 비교. 조회 사이에 숨은 simulation step · render/update 를 넣지 않는다. 첫 형식 실패를 성공한 형식으로 덮어쓰지 않는다. 질의 설정 · 필터를 바꾸면 별도 표시.
   - 각 ray 의 예정 / 실행 / 경계 제외 / 가림 / 오류 / hit / miss 분모. 모든 구멍 ray 가 가려졌는데 성공이라 하지 않는다.
   - 네 발 body 이름과 인덱스, world 위치, 접촉력(좌표계 · 단위 · 센서 갱신 시각), root 각속도 · pose · 같은 step 식별자. 0.005 s 물리 substep 의 짧은 충격을 0.02 s 끝 시점만 보고 「접촉 없음」 으로 읽지 않도록 가능한 범위의 contact history 최댓값과 표본 한계를 기록. quaternion 허용 0.002 는 바꾸지 않는다.
   - 기존 `s2_zero_supervisor.py` 의 `--steps 256` · 계약(`s2_stage0_contract_a2.py:91`)을 우회하지 않는다. 이 관찰은 **그 256 step 의 첫 16 step 안에서** 일어난다. 감독기 · lease · USD 잠금 · 가족 정리 · 관찰자 계약은 A3.3 의 것을 그대로 쓴다.
3. **자산 출처 고정:** URDF 내용 SHA256 (ASTRA 가 읽은 값 `f130b1d2cc61f3c1e54dab8f8b9ad27b0b54f85c968d89ea242c6d70ab2a5810` 와 대조) 뿐 아니라 URDF 가 참조하는 mesh 파일 목록 · 해시, RobotLab cfg 의 자산 선언과 변환기 출처를 시작 때와 종료 때 대조한다. 현재 `asset_ref_sha256` 은 경로 문자열 해시이고 `asset_sha256_of` 는 URDF 하나만 읽는다. 둘 다 전체 의존 파일의 불변 증명이 아니라는 사실을 보고서에 적고 고친다.
4. **USD 격리 증거:** 새 빈 시도 루트, 기존 OS 변환 잠금의 정상 취득, 요청 `expect_conversions=1`, 자식 환경 전달, `assigned.jsonl` 의 입력 자산과 격리 경로, 생성된 USD 및 실제 Robot prim 참조가 그 루트를 가리킨다는 증거를 묶는다. **`usd_isolate_run_v3.py:157` 의 `conversions` 는 생성자 진입 횟수이며 `orig_init` 성공 전에 증가한다.** 값 1 만으로 「변환 성공」 이라고 쓰지 않고 실제 출력 · 참조 · 환경 생성 완료를 함께 확인한다. 0회 · 2회 · 경로 이탈 · 경고는 HOLD. 기존 캐시 · 다른 실행의 루트는 지우거나 재사용하지 않는다.
5. **시간:** 잠금 대기 · Kit 기동 · 변환 · 수집의 시각을 각각 기록한다. 900초와 절대 마감은 그대로(변환 때문에 늘리지 않는다).

## 2. 배관 재시도 쪽 (B 묶음, `s2_step12/` 안)

ASTRA 17ah 2절: 같은 재시도의 Kit 안에서 **optimizer 이전에** 다음을 기록하고 검사한다. 이미 있으면 위치를 보고하고, 없으면 더하며, 이름이 존재한다는 로그만으로 끝내지 않는다.

- task 명, 실제 termination 키와 활성 함수, `disable_gravity=False`, `fix_base=False`, 부모 대비 허용 cfg 차이, 런타임 import 경로(robot_lab · isaaclab · 본 번들 모듈의 `__file__`).
- 그 관문을 지난 실제 관측 생성 → 합성 입력 연결 → 1 update → 저장 / 재로드 → 정리까지의 단계별 기록(이전 실행은 첫 관문에서 멈췄으므로 그 뒤는 Kit 에서 한 번도 안 돌았다). 다른 오류가 나면 그 오류에서 HOLD 하도록 하고 fallback 이나 예외 무시를 넣지 않는다.
- 요청 JSON 은 바꾸지 않는다: N=32, update 1, rollout 2, epoch 1, minibatch 1, 최대 600초, arm A, 합성 입력. 새 코드 해시이므로 manifest 는 다시 봉인한다(`UNDECIDED` 는 그대로).

## 3. 시험

- 정상 먼저. 필요한 변이(ASTRA 4절 마지막 문단): query 비활성, 모든 miss, 오류를 miss 로 바꿈, 다른 prim 가림을 지형 hit 로 바꿈, 좌표 / +20 m 중복, 발 인덱스 교환, 오래된 force 시각, 추가 step 또는 reset, 시간 예산 초과. 기존 관문에서 이미 재현한 항목은 재사용하고 새 연결부에만 변이를 더한다. 자산 해시 · 의존 mesh 한 개 변경 · USD 격리 이탈 · `conversions` 값만 보고 성공이라 쓰는 경로에도 변이.
- CPU 가짜 질의가 통과해도 실제 `carb.Float3` 호출과 PhysX 응답은 Kit 에서 확인해야 한다는 점을 보고서에 적는다(미확인으로).
- 깨끗한 복사본 `-I` 전체 회귀(step11 B 시험 전부 + A3.4 수집 시험 전부). 정상 PASS 수와 변이 CAUGHT/전체를 구분해서, 정상 단계와 변이 단계 선행 확인 라벨을 합쳐 「정상 N개」 라고 쓰지 않는다(ASTRA 17ah 가 지적: 331 은 정상 329 + 변이 단계 선행 2 이다).

## 4. 끝나면

`REPORT-s2-step12.md` (1~2절 항목별 위치 · 시험 수 · 변이 CAUGHT/전체 · 첫 실패 · 미확인), `S2-STEP12-SHA256SUMS.txt` (CR 없이, 인도 파일 전부), #550 댓글 초안(미게시). lead 가 재실행한다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
