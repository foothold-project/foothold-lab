> 분류: A/정책학습 · Codex Worker 작업서 (sol) · S2 B 번들에 「배관 smoke」 단계 추가 (CPU 만)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 17:49
> 근거: `REPORT-s2-step5.md` (B CPU 보고, lead 재실행 정상 53 PASS · 변이 7/7) · `VERIFY-astra-17ac.md` 6절 (0단계 PASS 전 배관 smoke 조건) · 저장소 사본 `night-tools-20261013/s2_step5/`
> 요지: ASTRA 17ac 가 「200 update · 두 arm」 smoke 는 보류하고 「PPO iteration 1~2 회 수준 · plumbing_only · 참석 단회」 로 줄이라고 했다. 현재 B 계약은 smoke 가 정확히 200 update 로 박혀 있다. 이것을 17ac 6절 조건대로 바꾼 새 단계 `plumbing` 을 CPU 에서 만든다. GPU · Isaac 은 건드리지 않는다
> 상태: 작업 지시 (GPU · Isaac 기동 금지 · 승인 json 은 ASTRA/lead 가 낸다 · 팀장 새 동의 필요)

# sol 작업서: B 배관 smoke 단계

## 0. 지킬 것

- GPU · Isaac · 실제 `_eval` 슬롯을 **띄우지 않는다.** `CUDA_VISIBLE_DEVICES=-1`, 해석기 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`. 새 작업 사본은 `codexE/s2_step6/` (`s2_step5/`는 저장소 사본과 같으니 고치지 않는다). 정상 시험을 먼저 통과시킨 뒤 변이가 지정 첫 FAIL 라벨과 같을 때만 CAUGHT. em dash 금지. 저장소 공유 체크아웃 쓰기 금지(보고서와 사본은 codexE 에).
- 팀장 지시: 실험이 안 도는 시간이 가장 큰 손해다. 단, 이 단계는 **배관 확인**이며 결과를 실험 결과로 쓰지 않는다. 검증을 빼지 않는다.

## 1. 현재 계약의 걸림돌

`s2_train_contract.py:88-96` 은 `stage=="smoke"` 에서 `updates==200` 과 `checkpoint_interval==200` 을 강제한다. `short` 는 2,000 이다. 17ac 6절은 이것을 그대로 쓰지 말고 아래 조건의 별도 단계로 두라고 한다.

## 2. 만들 것 (17ac 6절을 줄 그대로)

새 단계 `stage="plumbing"`:

1. **updates 는 1 또는 2** (PPO iteration. 환경 step 과 혼용하지 않는다: manifest 에 `rollout_steps` 와 `updates` 를 따로 두고 영수증에도 둘을 따로 적는다). `checkpoint_interval == updates`. `max_wall_s <= 600`.
2. **표시와 격리:** manifest 에 `plumbing_only: true` 와 `stage0_passed: false` 를 필수로 한다. 하나라도 빠지거나 `plumbing_only` 가 false 면 거절. 출력 폴더는 새 격리 폴더만, 체크포인트 파일명은 `PLUMBING_ONLY_` 로 시작하고 같은 폴더에 `PLUMBING_ONLY.txt` (이 가중치를 A/B 성능 · 지도 효과 · 후속 학습 시작점으로 쓰지 않는다는 문장 + manifest 해시) 를 쓴다. 이후 `smoke` · `short` manifest 의 `parent` 는 E1 `model_20000.pt` SHA (`c8951b79…`) 로 이미 고정이므로, 부모 경로에 `PLUMBING_ONLY_` 가 들어간 파일이 오면 거절하는 시험을 만든다.
3. **원본 checkpoint 불변:** 실행 전후에 E1 부모 파일 SHA 를 재서 같아야 한다(영수증에 전후 값). 다르면 실패.
4. **입력 경로 선언:** manifest 에 `input_path` 를 필수로 한다. 값은 `live_raycaster_unverified` 또는 `synthetic_known_answer` 둘 중 하나. 영수증은 값을 그대로 적고, `live_raycaster_unverified` 면 「성공은 배관 연결에 한정」 문구를 넣는다. 진단용 무중력 cfg (`s2_step4a3` 의 `s2_env_config_17v.py` eight_case 분기) 가 학습 cfg 로 새지 않는지 시험으로 보인다 (학습 cfg 에 `disable_gravity=True` 나 `base_contact=None` 이 들어오면 거절).
5. **한 번의 plumbing 이 점검하는 것(CPU 대역으로 먼저 답을 아는 입력으로):** forward → loss → backward → optimizer → save → load 를 지나고, 영수증에 다음을 남긴다: loss · KL · entropy 가 유한, gradient norm 이 0 이 아니고 유한, parameter 가 실제로 바뀜 (전후 해시 다름), NaN 0, encoder freeze 일정 (`freeze_updates`) 이 manifest 대로 적용됨, 학습률, arm 별 초기화 (A 는 상수 지도 입력, B 는 이상적 지도), 저장한 checkpoint 를 다시 불러 같은 입력에서 같은 출력.
6. **두 arm:** 한 프로세스는 한 arm 이다(DDP 아님, 기존 그대로). 두 arm 을 같은 GPU 에서 **순차**로 돌리는 방식을 지원한다: arm 별 manifest 2 개, 서로 다른 출력 폴더, 두 번째는 첫 번째 영수증이 `RUN_COMPLETE_UNVERIFIED` 이고 가족 정리가 확인된 뒤에만 시작(단회 claim). 동시 기동은 거절.
7. **CPU 검사가 있어야 하는 것:** 코드 · 해석기 · 의존성 · 기동 옵션 · 종료 · 실제 Job 가족 정리 경로. 기존 A3.2 0단계 감독기(optimizer 0) 는 건드리지 않고 이 단계는 **별도 계약**이다. 자동 재시도 · 무인 · 후속 학습 · `short` 로의 자동 승격 모두 없음.

## 3. 시험 (정상 먼저, 변이는 첫 FAIL 라벨)

정상: 위 1~7 이 각각 통과하는 입력. 변이(각각 첫 FAIL 라벨을 지정해 보고): updates 3 허용 · `plumbing_only` 검사 제거 · `stage0_passed` 가 true 인 manifest 허용 · 부모 SHA 재측정 제거 · `PLUMBING_ONLY_` 부모 거절 제거 · `input_path` 선언 제거 · 무중력 cfg 학습 유입 허용 · 두 arm 동시 기동 허용 · 가중치 변화 검사 제거 · NaN 검사 제거 · 환경 step 과 iteration 혼용(영수증에 하나만). 기존 53 PASS 와 변이 7/7 은 그대로 통과해야 한다(회귀).

## 4. 끝나면

`REPORT-s2-step6.md` (정상 PASS 수 · 변이 CAUGHT/전체 · 처음 실패도 함께 · 바뀐 파일 목록 · 미확인), 해시 목록, #550 댓글 초안(미게시). lead 가 재실행해서 ASTRA 에 넘긴다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적어 보고한다. 이 작업서의 범위 밖(lead 가 한다): 0단계 A3.2 · 4차 수집 · A4 무인.
