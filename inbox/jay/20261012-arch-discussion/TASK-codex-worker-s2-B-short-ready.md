> 분류: A/정책학습 · Codex Worker 작업서 (sol) · S2 B 짧은 A/B(short) 실행 준비 (CPU 만)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 10:51
> 근거: `night-tools-20261013/s2_step8/` (lead 재실행 293 PASS · 변이 57/57) · `S2-STEP5-USAGE.md` 의 short 계약 · `TASK-astra-17af-s2-AB-short.md` (ASTRA 에게 병렬로 묻는 중) · E1 부모 `model_20000.pt` 와 `params/agent.yaml`
> 요지: 팀장이 「아직도 A B 비교 실험이 진행이 안됐다고?」 라고 크게 화났다. 0단계 4차와 첫 배관은 동의만 기다린다. ASTRA 가 short 단계를 허용하는 순간 바로 띄울 수 있도록, 짧은 A/B 의 요청 JSON · barrier 계약 · 비교 도구를 CPU 에서 미리 닫아 둔다
> 상태: 작업 지시 (GPU · Isaac 기동 금지 · 승인 json 은 만들지 않는다)

# sol 작업서: B short 준비

## 0. 지킬 것

GPU · Isaac · `_eval` 슬롯 · 기존 코드 · 원자료를 건드리지 않는다. `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`. 새 사본 `codexE/s2_step9/` (`s2_step8/` 와 저장소는 고치지 않는다). 정상 먼저, 변이는 지정 첫 FAIL. em dash 금지. 첫 실패도 보고서에. 범위는 아래뿐이다: 실행 코드의 의미 · 입력 검사 · Job/잠금/격리를 바꾸지 않는다(바꿔야 하는 이유가 나오면 막힌 줄만 적고 멈춘다).

## 1. 만들 것

1. **요청 JSON 두 개** `request_short_A.json` `request_short_B.json`: GPU 0, 각 arm 한 개, `stage=short`, N=1,024, gap/stones 각 0.15, updates 2,000, checkpoint_interval 200, 증분 +500(`max_total_updates>=2500`), E1 부모 SHA `c8951b79…` 고정. **PPO 값(rollout_steps · epochs · minibatches · LR · clip · gamma · lam · entropy 등)은 E1 `params/agent.yaml` 과 E1 학습 기록에서 읽어 와서 값과 출처 줄 번호를 보고서에 적는다.** 임의의 fixture 값을 쓰지 않는다. encoder 는 `full_freeze`(ASTRA 17f-2 권고, 팀장 확정 대기) 로 두고, `schedule` 변형은 만들지 않는다. seed · map_init_seed 는 두 arm 이 **같은 값**(비교 조건 동일)이어야 한다: 값은 11 / 7 로 둔다. 팀장이 정할 값(마감 · 승인자 · 경로)은 `UNDECIDED`.
2. **barrier 계약 생성기** `make_barrier_contract.py`: 같은 `chain_id` · `arm` · `approval_id` · `stop_file` · `deadline_epoch` · `initial_short_updates=2000` · `max_total_updates>=2500` · `allowed_increments=[500]` 를 담은 JSON 을 만들고 `s2_increment_barrier.py` 의 두 arm grant · pair commit 규칙에 맞는지 CPU 시험(정상 + 반례: arm 불일치 · 증분 400 · 총합 초과 · 다른 chain).
3. **비교 도구 점검:** `s2_compare_ab.py` 가 두 arm 의 영수증과 checkpoint 경계(0 · 200 · … · 2,000)를 읽어 같은 seed · 같은 부모 · 같은 평가 조건인지 확인하고 「잠정」 표기를 붙여 비교하는지 CPU 대역 데이터로 시험한다. 같은 조건이 아니면 비교를 거절해야 한다. 0단계가 PASS 가 아니면 결과 문구가 「잠정 · 0단계 미통과」 로 나오게 한다(필드 `stage0_passed`).
4. **실행 시간 · VRAM 짧은 측정 단회 계획서** `MEASURE-N1024.md`: N=1,024 로 2 iteration(plumbing 계약의 `updates=2`)을 돌려 iteration 당 시간과 VRAM 최고치만 기록하는 단회를 어떻게 구성할지(어떤 필드를 영수증에 더 남기는지) 적는다. 코드 변경이 필요하면 최소안을 적되 만들지 않는다.
5. 시험: 정상 PASS 수와 변이 CAUGHT/전체를 구분해서, 깨끗한 복사본 `-I` 로 전체 회귀(33개 파일 + 새 것).

## 2. 끝나면

`REPORT-s2-step9.md` (바뀐 파일 · 출처 줄 번호가 있는 PPO 값 표 · 시험 수 · 첫 실패 · 미확인), `S2-STEP9-SHA256SUMS.txt`, #550 댓글 초안(미게시). lead 가 재실행한다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
