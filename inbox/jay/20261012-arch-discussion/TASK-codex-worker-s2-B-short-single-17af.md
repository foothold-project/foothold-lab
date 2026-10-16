> 분류: A/정책학습 · Codex Worker 작업서 (sol) · S2 B 첫 짧은 A/B 를 「연장 없는 단회 2,000회」 로 바꾸기 (CPU 만)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 11:06
> 근거: `VERIFY-astra-17af.md` 1절(P1 넷 · P2 넷) · 3절(GPU 0 순차 · 자원 측정) · 4절(합격 문구 · HOLD · 최소 비교 계약) · 이전 작업서 `TASK-codex-worker-s2-B-short-ready.md` 의 barrier 계약 생성기 · pair grant 부분은 **폐기**
> 요지: ASTRA 가 현재 step8 short 를 보류했다. 2,000회 종료와 +500 강제가 충돌하고, 출력 폴더 생성이 충돌하고, 같은 GPU 의 생존 barrier 가 다음 arm 을 막고, USD 증거가 결과에서 빠진다. 가장 작은 수정은 첫 A/B 에서 연장을 빼는 것이다. 각 arm 이 E1 에서 시작해 정확히 2,000회를 마치고 저장 · 종료 · 정리한 뒤 다음 arm 이 시작한다
> 상태: 작업 지시 (step9 진행 중이면 barrier 쪽은 멈추고 이 범위로 방향을 바꾼다 · GPU · Isaac 기동 금지 · 승인 json 은 만들지 않는다)

# sol 작업서: 연장 없는 단회 short (step9 방향 전환)

## 0. 지킬 것

GPU · Isaac · `_eval` 슬롯 · 기존 원자료를 건드리지 않는다. `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`. 새 사본 `codexE/s2_step9/` 에서 이어 간다 (이미 만든 `request_short_*.json` · `MEASURE-N1024.md` 는 이 범위에 맞게 고친다). `s2_step8/` 와 저장소는 고치지 않는다. 정상 먼저, 변이는 지정 첫 FAIL. em dash 금지. 첫 실패도 보고서에. **barrier 계약 생성기 · pair grant · `max_total_updates>=2500` · 증분 +500 은 이번 범위에서 뺀다** (코드를 지우지 말고 첫 단회 경로가 쓰지 않게만 한다). 바꿔야 하는 이유가 Job/잠금/격리 의미에 닿으면 막힌 줄만 적고 멈춘다.

## 1. 닫을 것 (ASTRA 17af 가 독립 CPU 로 재현한 결함)

각 항목에 정상 통과 시험과 변이(첫 FAIL 지정)를 붙인다.

**P1**
1. **출력 폴더 충돌:** `s2_train_entry_17v.py:660~663` 이 `out_root/usd/device_binding.json` 을 먼저 쓰고 `execute_barrier():570~571` 이 같은 `out_root` 를 `exist_ok=False` 로 만든다. plumbing 에 있는 「USD 하위 폴더만 있는 정상 시작은 허용, 남의 산출물이 섞인 시작은 거절」 경계를 short 단회에도 둔다. 두 경우를 구분하는 시험.
2. **2,000회 종료 계약:** `stage=short` 의 단회 계약을 새로 고정한다. `extension_disabled=true`, 총량 정확히 2,000, 자동 grant 없음, 2,001회 · +500 추가 거절. manifest 봉인 · 계약 검사(`s2_train_contract.py:180~185`) · child 분기(`entry:607~610`) · 감독기의 합격 경계(`launch:170~174`)가 **모두 같은 2,000** 을 가리켜야 한다. `2500` 을 `2000` 으로만 바꾸거나 `--barrier_contract` 를 빼는 식의 부분 수정은 상위 검사가 거절하므로 안 된다.
3. **순차 arm:** arm A 가 정상 종료하고 독립 정리가 끝난 뒤에만 arm B 가 시작한다. arm 마다 실행 ID · manifest · claim · 출력이 분리된다. A 가 살아 있는 동안 B 진입 거절, A 정리 미확인 상태에서 B 진입 거절 시험.
4. **USD 증거:** `entry:612~615` 의 `chain_result.json` 에 `usd_reference_paths` 가 없어 감독기 `usd_evidence()` 가 `usd_actual_reference_mismatch` 로 거절한다. 올바른 변환 기록 · 생성 파일 · refs 가 있는 정상 입력은 통과하고, 현재 short 결과 필드만 주면 거절되는 것을 먼저 재현한 뒤 고친다.

**P2**
5. **중간 로그 보존:** `entry:578~600` 은 segment 가 끝나야 `updates.jsonl` 을 쓴다. 매 update 기록을 flush 하고 실패 시 최초 구체 사유와 마지막 완료 번호를 남긴다. 3번째 update 에 알려진 sensor fault 를 넣어 앞의 두 기록과 실패 기록이 남는지 시험.
6. **저장 주기:** 고정 목록 **0 · 매 200 · 2,000**. 실제 저장과 매니페스트가 같다. 디스크 · 저장 시간 예산에 반영(보고서에 적는다).
7. **종료 판정을 short 에도:** `launch:217~219` 의 부모 SHA 불변 강제와 `:258~274` 의 cleanup 뒤 영수증 갱신이 plumbing 전용이다. short 에도 부모 불변 · 가족 정리 · lease/USD 해제 실패 시 HOLD. release 오류를 기록만 하고 이전 완료 영수증을 유지하면 안 된다.
8. **조우 계측:** `entry:249~250` 이 실제 Isaac 에서도 `encounters=[]` 를 반환한다. 이번 범위에서는 구현하지 말고 **보고만** 한다: (a) 저장소에 이미 검증된 고정 checkpoint 평가 경로가 있는지(예: sol 이 만든 `s1043` 평가 드라이버 · 비교기가 B 의 checkpoint 를 읽을 수 있는지, B 는 actor 앞에 지도 상수/이상적 입력이 더해지는 정책이다) (b) 읽지 못하면 필요한 최소 변경과 그 크기. 결과를 만들기 전에 어느 쪽을 쓸지 lead 가 정한다.

## 2. 숫자를 코드에서 읽어 와 동결할 것

- PPO 값(rollout steps · epochs · minibatches · LR · schedule · clip · gamma · lam · entropy 등)을 E1 `params/agent.yaml` 과 E1 학습 기록에서 읽어 값과 출처 줄 번호를 보고서에 적는다. **배관용 LR 0.001 · rollout 2 를 short 기본값으로 복사하지 않는다** (17af 4절). 17v 학습 후보와 대조해 어긋나면 어긋난 항목표.
- `request_short_A.json` / `request_short_B.json`: 두 arm 의 차이는 추가 actor map 의 상수 / 이상적 입력 하나뿐이어야 한다. seed 11 · map_init_seed 7 · E1 SHA `c8951b79…` · `full_freeze` · gap/stones 각 0.15 · N=1,024 · updates 2,000 · 체크포인트 목록 위 6항. 팀장이 정할 값(마감 · 승인자 · 경로)은 `UNDECIDED`. 마감은 **10/17(토) 정오 이전 완료** 상한을 필드로 둔다.
- 요청에 `exploratory_short=true`, `map_contract_verified=false` (0단계 4차 결과를 보기 전), `stage0_state=<필드>` 를 둔다. 결과 문구 도구는 위 두 값이 `exploratory_short=true`, `map_contract_verified=false` 인 동안 「효과 주장」 문구를 내지 못한다.

## 3. 자원 측정

별도 진단 단계를 늘리지 않는다 (17af 3절). 허가된 short 의 **첫 10 update 를 참석 중간 확인 지점**으로 쓴다. 이를 위해 매 update 한 줄 (update 번호 · 그 update 의 wall 초 · `torch.cuda.max_memory_allocated` · NVML 장치 사용량 · 최소 여유)을 화면에 찍고 로그에 남기는 것으로 충분하다. 기존 STOP 으로 중단할 수 있다. 새로운 barrier 를 만들지 않는다. `MEASURE-N1024.md` 를 이 방식으로 다시 쓴다 (시간 · VRAM 필드 · 읽는 법 · 「NVML 표본 최대는 진짜 최고치가 아니다」 단서).

## 4. 끝나면

`REPORT-s2-step9.md` (8개 닫은 항목 표 · 8번 보고 · 동결한 PPO 값 표와 출처 줄 번호 · 시험 수 · 변이 CAUGHT/전체 · 첫 실패 · 미확인), `S2-STEP9-SHA256SUMS.txt`, #550 댓글 초안(미게시). 깨끗한 복사본 `-I` 전체 회귀(step8 의 33개 파일 + 새 것). lead 가 재실행한다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
