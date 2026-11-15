> 분류: A/정책학습 · Codex Worker(sol) 작업서 · S2 Isaac 접속 확인 · 학습 진입 · 단계별 사슬 후보 (CPU 전용 · 학습 기동 아님)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 04:00
> 근거: `REPORT-s2-step2.md` (sol 보고) · `TASK-astra-17v-s2-step2.md` 4~6 절 (ASTRA 가 지금 같은 후보를 검증 중) · 팀장 10/15 「GPU 는 절대 놀면 안 된다 · 계획만 잘 세우면 단계별로 계속 돌릴 수 있다」
> 요지: 2 단계 후보에 없는 것 셋을 만든다. (1) 실제 Isaac 에서 지도가 맞는지 보는 접속 확인 스크립트(학습 없음, 첫 GPU 일) (2) 실제 Isaac 학습 진입점(`S2_TRAIN_ENTRY`) (3) 접속 확인 → smoke → 짧은 A/B 를 합격 판정 스크립트로 잇는 단계별 사슬 정의. 전부 CPU 에서 검토 가능한 후보로 만들고, 실행은 하지 않는다. ASTRA 가 사슬 전체를 한 번에 검증해 GPU 가 승인 사이에 놀지 않게 하려는 것이다
> 상태: 의뢰 (CPU 전용 · `_eval` 은 읽기만 · GPU · Isaac 실행 금지)

# Codex Worker 작업서 · S2 Isaac 접속 확인과 학습 진입, 단계별 사슬

## 0. 규칙

- 앞 작업서(`TASK-codex-worker-s2-step2.md`) 1 절 규칙 그대로: 커밋 금지 · 삭제 금지 · GPU · Isaac 실행 금지 · `CUDA_VISIBLE_DEVICES=-1` · `_eval` 과 `C:/isaac/ext/go2_rl_robotlab/source` 쓰기 금지(읽기만) · 부모 파일 수정 금지 · 정직한 보고 · em dash 금지 · 팀장 / ASTRA 결정 값은 제안으로만, 코드에 기본값 없이 인자 필수.
- ASTRA 17v 가 같은 후보를 검증 중이다. 판정이 오면 바뀔 수 있는 부분(접속 확인의 불합격 조건 · 사슬의 승인 구조)은 코드 한 곳에 모아 두어 쉽게 고치게 한다.
- 새 파일은 `codexE/s2_step3/` 에 둔다. 2 단계 파일은 `codexE/s2_step2/` 에서 해시 대조 후 import 만 하고 고치지 않는다(고칠 일이 생기면 보고서에 적고 사본에서 고친다).
- Isaac / Kit 쪽 호출은 **기존 승인된 도구의 패턴을 그대로** 따른다(읽기만): `_eval/ce12/run_dump.py`(+ `dump_native_v2.py`), `_eval/rand_scenes/rand_lib.py`, `_eval/unseen_driver_cmdr_v6.py`, `_eval/isaac_slot_v3.py` · `gpu_guard.py` · `usd_isolate_run_v3.py` 의 인수 형태, `night-tools-20261013/night_20261013_cmdr1043_v3.sh` 의 순차 실행 · STOP · 마감 패턴. 어디서 무엇을 따랐는지 줄 번호로 대응표를 보고서에 둔다. 모르는 Isaac API 는 추측하지 말고 기존 코드에서 쓰는 호출만 쓴다. 기존 코드에 없는 호출이 꼭 필요하면 「미확인 호출」 목록에 적는다.
- Codex 주간 한도가 21 % 이나 reset 권이 있다. 필요한 만큼 읽되 같은 파일 되풀이 읽기는 줄인다. 압축이 오면 `HANDOFF.md` 와 이 작업서를 읽고 이어 간다. **중간에 멈추지 말고 끝까지.**

## 1. 만들 것

1. **`s2_connect_diag.py` (Isaac 접속 확인 · 학습 없음 · 첫 GPU 일 후보).** 학습 환경과 같은 설정에 2 단계의 희소 지형 겹침을 얹어, 평지 · 단 하나짜리 단차 · gap · 징검다리 지형에 로봇을 두고(작은 환경 수 · 제자리 서기 또는 0 행동, 수십 step) RayCaster 를 읽어 다음 원자료를 쓴다: `height_scanner` 의 `pos_w` · `ray_hits_w`(원자료 그대로), env origin · terrain type / level · 로봇 자세, reset 직후와 N step 뒤의 두 시점, 2 단계 어댑터(`strict=True`)를 통과한 height · mask, Isaac / torch / 드라이버 판 · 설정 해시 · 코드 해시. 출력은 격리된 루트 한 곳에만. 체크포인트 · 학습 로그는 만들지 않는다. 종료 코드 규약(성공 0 · 데이터 이상 보류 코드 따로)과 Traceback 감시를 기존 패턴대로.
2. **`s2_connect_check.py` (CPU 검증기).** 1 의 산출물을 알려진 답과 대조한다: 평지에서 센서 z 와 hit z 가 일정하고 height 값이 설계 의미(DESIGN-s2-ab-v1 6 절 · README 4 절)와 같음 · 광선 187 개 순서가 `grid_pattern` 과 같음(x-fast) · 20 m offset 이중 가산 없음 · yaw 를 돌리면 지도가 정해진 방식으로 회전 · gap 에서 hit 이 없거나 깊게 나오는 칸이 mask 규칙대로 · 징검다리의 높이 · 간격이 `terrain_probe` 기하와 맞음 · reset 직후 값이 이전 episode 와 섞이지 않음 · NaN / inf 분류. **불합격 조건을 한 곳(표)에 모으고**, 합성 산출물(정상 + 각 불합격 반례)로 CPU 시험한다. 불합격 임계값은 제안으로만.
3. **`s2_train_entry.py` (실제 Isaac 학습 진입점 후보 · `S2_TRAIN_ENTRY`).** 필수 인자(기본값 없음): 부모 체크포인트 경로 · 시드 · 환경 수 · update 수 · rollout 길이 · epoch · minibatch · `encoder_mode`(+ schedule 이면 W · r) · arm(A 또는 B) · 지형 비율 · 출력 루트 · STOP 파일 · 마감. 부모 E1 20000 은 CPU strict 적재(1 단계 코드 재사용) 후 요구되는 장치로 이동, 2 단계 `S2Runner` · `S2PPO` 를 구동, 환경은 접속 확인 스크립트와 같은 구성 함수를 공유(두 스크립트가 서로 다른 환경을 만들면 안 됨). 출력: update 마다 로그, 일정한 간격의 체크포인트(`ctl.state_dict()` 포함), 단계 결과 `result.json`(예정 대비 실행 update 수 · 고장 횟수 · 폐기량 · 지형 조우 기록 · 장치 전체 peak / 최저 여유 · 시간당 iteration · 종료 이유). STOP 파일 · 마감은 update 사이에서 협조적으로 확인. **`--cpu_dry` 모드**: 가짜 환경으로 같은 코드 경로를 돌려 CPU 시험(인수 검증 · 저장 / 재개 · STOP · 마감 · 결과 파일).
4. **단계별 사슬 정의 `S2-CHAIN-draft.md` + `s2_chain_manifest.json` + `s2_stage_gate.py`.** 0 단계(접속 확인) → 1 단계(smoke: A · B 각각 수백 update, 시간당 iteration · VRAM 실측) → 2 단계(짧은 A / B 학습)를 하나의 사슬로 정의한다. 각 단계에: 입력(이전 단계 산출물 해시) · 예산(launch · wall · update 수) · **자동 합격 / 보류 판정 규칙**(종료 코드 · Traceback · 산출물 존재 · 고장 횟수 · NaN · 지문 · 지도 시점 · step 수 == 계획 · 접속 확인 합격) · 중단 조건 · 단회 claim · 마감. `s2_stage_gate.py` 는 단계 산출물을 읽어 합격 / 보류를 판정하고 합격일 때만 다음 단계 인수를 만들어 주는 순수 CPU 프로그램이다. 합성 산출물(정상 / 각 보류 사유)로 시험하고 코드 변이(판정 규칙을 하나씩 끔)를 만든다. 사슬 전체를 승인하려면 무엇이 불변이어야 하는지(승인 후 바뀌면 안 되는 해시 · 인수 목록)를 표로.
5. **기동 스크립트 초안 갱신 `night_s2_chain_draft.sh` (실행 금지, 맨 앞 `exit 99` 유지).** 위 1~4 를 기존 사슬(승인 json → 슬롯 → 가드 → 격리 → 진입)에 어떻게 끼우는지 단계별로. 한 번에 하나의 Isaac, 단계 사이 가드 확인, 실패 시 다음 단계 안 띄움.

## 2. 시험과 보고

- CPU 시험: 합성 산출물 · 가짜 환경으로 알려진 답을 손으로 적고 판다. 변이는 정상 소스에서 같은 시험이 먼저 통과하고 지정한 시험이 의도한 라벨로 실패할 때만 CAUGHT. 코드 변이와 입력 변조를 따로 센다. 2 단계 시험 · 변이가 그대로 통과하는지 회귀를 같은 묶음에서(`run_all_s2_step3.py`, 새 run-id 증거 폴더).
- 보고서 `codexE/REPORT-s2-step3.md`: 머리 다섯 줄 · 격리 단언 · 파일 해시 · 기존 도구 패턴 대응표(줄 번호) · 항목 1~5 별 「만든 것 · 시험 이름 · 정상 로그 · 반례 위치 · 변이 want 일치」 · **미확인 호출 목록**(기존 코드에 없는 Isaac 호출) · 시험이 못 보는 것(실제 Isaac · GPU · VRAM · 시간) · 팀장 / ASTRA 결정 필요 값 목록 · lead 가 ASTRA 에 물을 질문 5 개. 끝나면 `ISSUE-550-s2-step3-comment.md` 짧은 요약. 사본 · 커밋 · #550 댓글은 lead 가 한다. 완료를 SendMessage 로 알리지 말고 보고서 위치만 마지막 메시지로 적는다.
