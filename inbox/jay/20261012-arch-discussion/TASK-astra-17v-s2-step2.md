> 분류: A/정책학습 · ASTRA 의뢰 17v · S2 지도 실험 학습 연결 2 단계 CPU 후보 검증과 첫 GPU 일의 단계별 승인 설계
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 03:59
> 근거: 팀장 10/15 새벽 지시 (아래 1 절) · 작업자 sol 의 보고 `REPORT-s2-step2.md` (사본 `night-tools-20261013/s2_step2/`) · lead 재실행 (`evidence_run_034845_lead/`) · `night-tools-20261013/s2/README-s2-step1.md` 3 · 8 절 · `DESIGN-s2-ab-v1.md` 6 절 · VERIFY-astra-17d · 17f · 17f-2 · 17u
> 요지: 지도 실험(S2)의 학습 루프 후보가 가짜 환경에서 시험을 통과했다. (1) 이 후보가 CPU 로 볼 수 있는 범위에서 맞는지 (2) 실제 Isaac 에서 아직 한 번도 안 한 「접속 확인」 이 첫 GPU 일인데 그 범위와 승인 구조 (3) GPU 가 승인 사이에 놀지 않도록 **단계별로 미리 승인하는 사슬** 이 가능한지, 가능하면 무엇을 갖춰야 하는지 판정해 달라
> 상태: 의뢰 (GPU 는 둘 다 비어 있음 · 이 의뢰는 기동 허용을 구하지만 값과 진입 코드가 채워지기 전에는 승인 json 을 발급하지 말 것)

# ASTRA 17v

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. 작업자 sol 의 보고와 lead 요약을 평소보다 더 신중하게 원자료(코드 · 로그 · 반례)로 독립 대조해 주십시오. 17j ~ 17u 의 기준(시험이 실제 기동 경로를 타는지 · 변이는 정상 소스의 같은 시험 통과와 의도한 실패 위치 · 입력 변조와 코드 변이를 섞어 세지 않기 · 변이의 «실제로 바뀐 의미» 를 정확히 쓰기 · 가상화된 주변 관문을 숨기지 않기 · 장치 전체 값 vs 몫 · 「X 없음」 은 기록으로)을 적용해 주십시오.

**분량:** `VERIFY-astra-17v.md` 한 파일. 첫 줄 한 문장 판정, 질문마다 「판정 · 근거 · 남길 미확인」. 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out/` 은 읽기만. em dash 금지.

## 1. 팀장 지시 (10/15 새벽, 이 의뢰의 배경)

- GPU 는 절대 놀면 안 된다. GPU 는 팀장의 로컬 자원이므로 **세션 한도와 무관하게, 계획만 잘 세우면 단계별로 계속 돌릴 수 있다.**
- 곁다리가 아니라 **실제 gap · stepping_stones 를 건너는 실험**을 해야 한다. MoE-CTS 구조로는 원하는 결과를 얻기 어렵다고 팀장은 본다. 먼저 MoE-CTS 방식에서 「지도를 준 student」 단계까지 실험하고, 그 결과로 어떤 논문을 바탕으로 신경망을 다시 설계할지 정한다.
- 11/7 은 마지막 날짜일 뿐이고 그 전에 **방향을 빠르게** 내야 한다. 방향이 맞으면 학습량을 올려 오래 학습한다. Linux 이전은 방향이 선 뒤로 이어진다(날짜는 super2 에 확인 중).
- 팀장 결정(「권고대로」): 틈 · 징검다리 연습을 지도 실험 안에 같이 넣고 지도를 준 모델과 안 준 모델을 나란히 비교한다. 1043 채점기는 ASTRA 17u 가 소유 경계(OS 수준) 와 전체 실행 lease 연결을 요구해 **보류** 중이다(lead 제안, 팀장 확인 대기).
- Codex 주간 한도 21 % 이나 팀장에게 reset 권이 있어 ASTRA 세션에 말해 반영하면 된다. 한도 때문에 검증을 줄이지는 않는다.

## 2. 대상과 보고

작업자 sol(Codex Worker · gpt-6-sol · 검증자 아님)의 후보. 바이트 고정은 `night-tools-20261013/s2_step2/SHA256SUMS.txt`(10 줄)과 작업자 전체 목록 `S2-STEP2-SHA256SUMS.txt`(16 줄 · 목록 SHA256 `91737d563dab78778a51b72dcca42a20f6b7358fecf12b97cf20ee21aef8c5e9`). 1 단계 파일 여섯은 `night-tools-20261013/s2/SHA256SUMS.txt` 와 같다(작업자의 `base_step1/` 사본과 대조 불일치 0 이라고 보고). 부모 `moe_cts.py` SHA256 `136a1c10…058f6` · `on_policy_runner_cts.py` `6800c786…44a9` 가 시작 · 끝 같다고 보고.

작업자 주장(`REPORT-s2-step2.md`): 만든 것 여섯.
1. `s2_ppo.py`: PPO 손실만(teacher / student 나눔 · 재구성 손실 · 별도 encoder optimizer 제거), 1 단계 `EncoderControl` 의 `begin_update` → epoch × minibatch 마다 `enforce_groups` + `trainable_params` clip → `end_update`, 부모 adaptive lr 문턱 그대로.
2. `s2_runner.py`: rollout 이 지도(height 187 + mask 187)를 관측 시점 그대로 저장, bootstrap 은 다음 관측의 지도, reset 뒤 이전 episode 지도 혼합 거절, `RunValidityGate` 를 rollout 마다 update 전에, update 마다 계획된 step 수 == epoch × minibatch 기록, 저장 · 재개(정책 · control · optimizer · 환경 · torch CPU / CUDA · numpy · python 난수 · 환경 해시), 갱신 도중 저장 거절, 다른 arm / 규칙 / 설정 재개 거절, `WORLD_SIZE != 1` 거절.
3. `s2_env_adapter.py`: Isaac 를 import 하지 않는 지도 공급 인터페이스 + RayCaster(`height_scanner.pos_w` · `ray_hits_w`) 어댑터(실행하지 않음), `strict=True`, 광선 순서 x-fast · 20 m offset 재가산 금지 · yaw 90° 시험.
4. `s2_terrain_overlay.py`: 부모 설정 deep copy 위에 gap(0.10~0.25 m) · 징검다리(폭 0.50~0.70 · 간격 0.10) 덮어쓰기. 최종 비율은 인자 필수. 배정 · 접근 · 통과 · 회피 · 추락 · 정체를 따로 셈.
5. `S2-SMOKE-PREREG-draft.md`: README 8.2 의 7 행 사전 등록 초안(별표 = 결과 전에 정할 값).
6. `night_s2_smoke_draft.sh` + `s2_launch_gate.py`: 검토용 초안. 맨 앞에서 무조건 `exit 99`. `S2_TRAIN_ENTRY`(실제 Isaac 학습 진입점)는 **아직 없음**.

작업자 시험(`run_all_s2_step2.py`): 네 실행 모두 exit 0. 1 단계 14/14 PASS(292 칸) · 1 단계 변이 69/69(**소스 변이 68 + 입력 해시 관문 변조 1**, 합산 주장 안 함) · 2 단계 알려진 답 26 PASS · 2 단계 코드 변이 6/6 CAUGHT(`adaptive_lr` · `ray_order` · `map_snapshot` · `validity_gate` · `terrain_geometry` · `approval_gate`).
**작업자가 적은 한계(그대로 인용):** 실제 Isaac / RayCaster / collision mesh · GPU · VRAM · 시간당 iteration · 실제 학습 안정성 · CUDA RNG 저장 / 복원(이 CPU 시험에서 미측정) · 공유 lease 의 다른 작업과의 상호 배제 · 스크립트 인수 호환성 · smoke 이후 독립 평가는 미확인. CPU 가짜 환경의 비트 동일 재개를 실제 Isaac 결정성으로 확대하지 않음. 이 단계가 곧 GPU smoke 준비 완료는 아님. 첫 PowerShell 복사가 0 건이었던 예비 실패는 분모에 안 넣음.

## 3. lead 재실행

**실행(10/15 03:48:44 ~ 03:56:41 · lead):** 작업자의 `run_all_s2_step2.py` 를 새 run-id `run_20261015_034845_150772` 로 한 번 돌렸다(`CUDA_VISIBLE_DEVICES=-1` · 해석기 `isaac311-moects` · `-B -u`). 네 실행 모두 exit 0: `step1_14` 6.53 s · `step1_69_mutants` 417.52 s · `step2_known_answers` 4.05 s(PASS 26) · `step2_code_mutants` 48.61 s. 1 단계 BASELINE 14/14 PASS · 변이 `ALL CAUGHT 69/69`. 2 단계 코드 변이 6 건 모두 정상 exit 0 · 변이 exit 1 · `failed` = `want`. summary 의 `step1_hashes_match` · `parent_hashes_unchanged` 모두 true. 후보 16 파일 해시는 재실행 전후 모두 일치했고 부모 두 파일 해시도 같다. 로그는 `evidence_run_034845_lead/`(저장소 사본), 스크립트는 `lead_rerun/`.
**사본:** 저장소 `night-tools-20261013/s2_step2/` (작업자 `s2_step2/` 와 파일 단위 `cmp` 불일치 0).
**lead 가 하지 않은 것:** 후보 코드의 줄 단위 검토 · 부모 대응표의 줄 번호 대조 · 변이가 의도한 검사만 바꿨는지 코드 대조 · 맵 시점 어긋남 · reset 누출 · A 정보 차단 · 재개 동치를 ASTRA 방식 반례로 직접 재현 · 실제 Isaac · GPU 연쇄 · 어떤 UNDECIDED 값도 채우지 않음.

## 4. 물음

1. **CPU 후보의 정상성.** 부모 대응(`moe_cts.py` 93~101 · 124~129 · 132~202 · 227~411 · 278~311, `on_policy_runner_cts.py` 108~145 · 167~181 · 260~278) 이 의도한 차이 외에 동작을 바꾸지 않는지. PPO 만 쓰는 갱신이 부모의 teacher / student 나눔을 뺀 것 말고 부모와 같은 PPO 인지(advantage 정규화 · value loss clipping · entropy · mini-batch 구성 · lr 적용 순서). 맵 시점 보존(관측 시점 vs 다음 시점 어긋남 반례) · reset 격리 · bootstrap 의 지도 · A 정보 차단 · 두 arm 이 같은 경로를 타는지 · 재개 비트 동일 · 고장 관문(`RunValidityGate`) 이 update 전에 실제로 걸리는지 · adaptive lr 이 두 군에서 같은 규칙인지. 가상화된 주변 관문(가짜 환경 · 가짜 정책 입력)이 어디까지인지와 변이 6 종 + 69 종의 실제 의미 분류.
2. **첫 GPU 일: Isaac 접속 확인(학습 없음).** 팀장의 목표는 실제로 gap · 징검다리를 건너는 것이므로 지도가 실제 시뮬 지형에서 올바른지 먼저 봐야 한다. 이 확인에 어떤 원자료를 모아야 하고 어떤 조건이 불합격인가(작업자 질문 1: RayCaster `pos_w` · `ray_hits_w` 의 187 칸 순서 · yaw · 20 m offset · no-hit · collision mesh 의 평지 / 단차 / 빈 공간 · reset 직후 frame). 평지 · 단차 · gap · 징검다리를 어떤 지형 배치로 몇 환경 · 몇 step 동안 볼지, 알려진 답은 무엇인지.
3. **기존 승인 사슬의 재사용 가능성.** 지금까지 ASTRA 가 허용한 Isaac 실행(CE12 · 미경험 v6 · RAND smoke · v2 기록)은 `approval json` + `frozen_exec` + `isaac_slot_v3` + `gpu_guard` + `usd_isolate_run_v3` 사슬을 썼다. **17u 의 소유 경계 결함(PID 재사용 · 후손 놓침) 은 1043 후보가 새로 만든 감시기의 문제인가, 아니면 S2 가 같은 사슬로 학습 / 접속 확인을 띄울 때도 적용되는가?** 적용된다면 S2 의 첫 일은 어떤 최소 조건을 갖춰야 하는가. 전체 실행 lease 가 어느 실행기에도 없다는 17u 5 절 사실이 S2 의 동시 실행(다른 Isaac 과 겹치지 않기)에 어떻게 영향을 주는가(GPU 하나에 Isaac 하나만 띄우는 운영 규칙으로 충분한가).
4. **단계별 사슬 승인(팀장 원칙을 지키기 위한 핵심 물음).** 지금은 GPU 일 하나마다 ASTRA 판정이 있어야 해서 판정 사이에 GPU 가 몇 시간씩 논다. 그래서 다음처럼 **사슬 전체를 미리 한 번에 검증 · 승인**하는 방식을 제안한다. 허용될 수 있는가, 있다면 무엇을 갖춰야 하는가, 어떤 변화는 반드시 새 판정이 필요한가.
   - 0 단계: Isaac 접속 확인(학습 없음, 분 단위).
   - 1 단계: 짧은 smoke(A · B 각각 수백 update). 시간당 iteration · VRAM 실측.
   - 2 단계: 짧은 A / B 학습(두 GPU 에 한 arm 씩 또는 한 GPU 에 순차).
   - 각 단계 끝에 **스크립트가 자동으로 합격 / 보류를 판정**하고(종료 코드 · 로그 Traceback · 산출물 · 고장 횟수 · NaN · 지문 · 지도 시점), 합격일 때만 다음 단계를 띄운다. 보류면 멈추고 사람과 ASTRA 에 넘긴다.
   - ASTRA 는 사슬의 정의(단계 · 예산 · 합격 기준 · 중단 조건 · 단회 claim · 마감) 와 판정 스크립트를 검증해 한 번에 승인한다.
   이 방식이 17u 까지의 기준(승인 한 묶음 · 단회 claim · 재시작은 새 승인)과 충돌하지 않는 조건을 구체적으로 적어 달라.
5. **사전 등록할 값과 제안(작업자 질문 2~5 포함).** 결과를 보기 전에 정해야 하는 값에 대해 ASTRA 의 권고 범위를 달라: 첫 A / B 의 `encoder_mode`(lead 는 17f-2 권고대로 `full_freeze`), 환경 수 · 시드 · rollout 길이 · epoch · minibatch · smoke 와 짧은 학습의 update 수와 중단 기준, 진단 corpus · 로그 최소 집합(부모 동치 · gradient · optimizer · group LR · KL · latent), gap · 징검다리 배정 비율 후보와 조우 기록, 최종 평가의 표본 · 시드 · 명령 · checkpoint 선택 규칙. **「지도가 효과 있다」 의 기준**에 대한 lead 제안: 지도를 준 모델(B)의 틈 · 징검다리 통과율이 안 준 모델(A)보다 확실히 높을 것(예: 목표 칸마다 95 % 구간 하한 > 0 이고 평균 차 ≥ 10 %p, 기존 평가 기준 계열). 이 기준이 한 시드 · 예비 비교에 적절한가, 표본 수는 얼마여야 하나, 성능을 본 뒤 기준을 바꾸지 않는 규칙을 어떻게 사전 등록하나.
6. **견적과 병행.** 지금부터 0 단계 / 1 단계 / 2 단계 기동까지의 현실적인 단계 목록과 병목. sol 이 ASTRA 검증을 기다리는 동안 CPU 로 할 수 있는 일은 「Isaac 접속 확인 스크립트 후보」 와 「학습 진입 스크립트 후보」 작성이다(lead 가 곧 맡길 예정). 이 둘을 지금 병행해도 되는지, 접속 확인 결과 없이 학습 진입을 쓰면 안 되는 부분이 어디인지.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17v.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
