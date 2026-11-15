> 분류: A/평가 · ASTRA 의뢰 17s · 1043 쌍 평가 새 판 17r 고침 검증과 진단 단계 승인 조건
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 21:49
> 근거: VERIFY-astra-17r.md 전문 · 작업자 E 의 고침 보고 `codexE/REPORT-17r.md` (사본 `night-tools-20261013/cmdr1043_eval_cand_17r/`) · lead 재실행 (`cmdr1043_eval_cand_17r/lead_rerun/`) · #550 댓글
> 요지: 17r 이 찾은 P1 여섯 건과 추가 네 건 · 시험 보강 셋을 작업자 E 가 CPU 로 고쳤다고 보고한다. 이 고침이 17r 의 반례를 실제로 닫는지, 새로 생긴 결함이 없는지, GPU 0 **진단 한 묶음** (부모 flat stop03 · seed 1000 · 100 episodes 로 q 원본 · q_cmdr 작은 버퍼 · q_cmdr 기본 버퍼) 의 승인 조건을 정해 달라. 팀장 결정이 필요한 값과 lead 가 측정해 채울 값, ASTRA 승인 json 발급 조건을 가르는 것까지
> 상태: 의뢰 (GPU 는 둘 다 비어 있음 · 이 의뢰는 기동 허용을 구하지만 값이 채워지기 전에는 승인 json 을 발급하지 말 것)

# ASTRA 17s

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. 작업자 E 의 보고와 lead 요약을 평소보다 더 신중하게 원자료 (코드 · 로그 · 반례) 로 독립 대조해 주십시오. 17j ~ 17r 의 기준 (시험이 실제 기동 경로를 타는지 · 변이는 정상 소스의 같은 시험 통과와 의도한 실패 위치 · 문서와 코드의 차이 · 장치 전체 값 vs 몫 · 「X 없음」 은 기록으로) 을 적용해 주십시오.

**분량:** `VERIFY-astra-17s.md` 한 파일. 첫 줄 한 문장 판정, 질문마다 「판정 · 근거 · 남길 미확인」. 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out/` 은 읽기만 · `slot/` · `handover_*` · `handover-1635` 에는 쓰지 마십시오. em dash 금지.

## 1. 대상과 보고

작업자 E (Codex Worker · gpt-6-sol · 검증자 아님) 의 고침 후보. 바이트 고정은 `night-tools-20261013/cmdr1043_eval_cand_17r/SHA256SUMS.txt`. 17r 이 본 판은 `cmdr1043_eval_cand/` (해시 6 개) 이고 작업자가 고치기 전에 `codexE/cand_17r_base/` 로 145 파일을 보존했다 (바이트 대조 0 불일치). 변경된 기존 파일 7 개: `build_manifest_s1043.py` · `cmdr_bundle_compare_s1043.py` · `cmdr_eval_driver_s1043.py` · `cmdr_post_s1043.py` · `frozen_exec_s1043.py` · `manifest_s1043.json` · `s1043_manifest.py`. 새 시험: `test_17r_b.py` · `test_17r_c.py` · `test_17r_d.py` · `test_17r_e.py` · `test_17r_post_cli.py` · `test_17r_mutants.py` · 묶음 실행기 `run_all_17r.py` · 가짜 slot (CPU 경계 시험용).

작업자 주장 (`REPORT-17r.md`): 17r 항목 1 ~ 15 를 각각 고치고 CPU 증거를 남김. 핵심: GPU index 를 정수 0/1 만 수용 (bool · 문자열 배제) · smoke 원본 해시를 등록된 `source_q_eval.py` 로 · 시작 시험 9 개 계약을 manifest 에 등록하고 frozen 이 guard→isolate→q 전체 argv 를 재구성해 정확히 비교 (중복 옵션 거부) · 승인 대상에 코드 5 개 해시 · 비교 보고서 해시 · stage · 물리 GPU · UUID · CUDA · 마감 · 위험 한도 · lock · lease · registry · Python · 원본 반복 결정을 묶고 바깥에서 받은 승인 SHA256 을 대조 (`stage=diagnostic` 와 `stage=A` 분리) · lock / lease 의 정규 경로와 실제 파일 동일성 · lease 는 slot wrapper 와 관찰된 자식 PID · 생성 시각이 모두 끝날 때까지 보유 · post 가 물리 UUID 와 자식 논리 CUDA 0 을 별도 대조 · 타 드라이버 log root 를 그 프로세스의 manifest 로 해석 · USD 를 전체 정규 경로로 비교 · 비유한 MAE 한 건이 전체 run 무효 (`invalidate_entire_run`) · reset 값을 q 원본의 범위 · 동작 지점과 대조 (XY ±9 m 거부) · `execution.CUDA_VISIBLE_DEVICES` 필수 · 평평한 배치 (candidate_dir · write_root · source_eval 을 manifest 로) · **진단 전용 모드** (세 실행 뒤 멈춤 · A 자동 진행 없음 · 반복은 사전 예산이 있을 때만).
작업자 시험: 6 개 스크립트 모두 exit 0 (`evidence_17r/run_20261014_125138_107212/summary.json`) · 정상 연결 (`start→tests→guarded→가짜 slot→frozen`) 을 실제 CPU 자식 CLI 로 통과 (정상 로그가 반례보다 먼저) · 반례: 참 on-only 완료 결손 · 승인 위험 상한 · 코드 해시 변조 · 고아 자식 · slot 대기 뒤 입력 변경 (rc 92) · 변이 12 개 CAUGHT (want 문구 대조).
**작업자가 적은 한계 (그대로 인용):** GPU · Isaac · 실제 `isaac_slot_v3.py` · `gpu_guard.py` · `usd_isolate_run_v3.py` · Kit 연결 · peak · 정지 동작은 미실행 (가짜 slot 은 CPU 경계) · 공통 lease / 변환 lock 을 다른 모든 운영 실행기가 쓴다는 증거 없음 (OS 경쟁 시험은 이 후보와 가짜 slot 한정) · 매우 짧게 생겼다 사라지는 관찰 전 자식은 PID 조사의 한계 · 진단의 JSON 의미 일치와 파일 SHA 일치는 다른 주장. 작업자가 띄운 CPU 시험 프로세스 하나 (PID 175820) 가 옛 판으로 대기 중 (종료 승인을 팀장에게 요청 · 강제 종료 안 함).

## 2. lead 재실행

(lead 가 `run_all_17r.py` 를 새 증거 폴더로 한 번 더 돌린 결과는 `cmdr1043_eval_cand_17r/lead_rerun/` · 이 의뢰문 작성 시점에 끝났으면 아래에 적음)
**실행 (10/14 12:55:00 ~ 12:55:35 · lead):** 작업자 E 의 `run_all_17r.py` 를 새 run-id `run_20261014_125500_26228` 로 한 번 돌렸다 (`CUDA_VISIBLE_DEVICES=-1` · 해석기 `isaac311-moects` · `-B -u`). 여섯 시험 모두 종료 0 (`test_17r_b` 3.95 s · `test_17r_c` 1.33 s · `test_17r_d` 0.44 s · `test_17r_e` 26.19 s · `test_17r_post_cli` 3.06 s · `test_17r_mutants` 0.33 s). 로그는 `evidence_17r_run_125500_lead/` (저장소 사본) · 실행 스크립트와 출력은 `lead_rerun/`. 작업자 자신의 마지막 실행은 `evidence_17r_run_125138_worker/`.
**변이:** `test_17r_mutants.log` 에 `CAUGHT` 12 줄. 각 줄에 `want` 문구와 `got` 목록이 같이 찍혀 있고, 12 줄 모두 `want` 가 `got` 안에 있음을 lead 가 로그에서 눈으로 대조했다 (GPU index 문자열 · 후보 해시 scalar · 확인값 scalar · 승인 위험 결박 · 후보 코드 digest · CUDA 선택 · 변환 lock 과 실행 lease 같은 파일 · reset XY 9 m · 후보 배치 · 중복 outdir · 시작 태그 미등록 · 진단 단계의 A 작업). 정상 소스가 같은 시험을 통과한다는 것은 `test_17r_e.log` 의 정상 연결 로그가 반례보다 앞에 있는 것으로 확인했다. 12 개가 서로 독립 종류인지, 각 변이가 의도한 검사만 껐는지는 lead 가 코드 대조하지 않았다.
**사본:** 저장소 `night-tools-20261013/cmdr1043_eval_cand_17r/` 는 작업자 E 의 `cand/` 에서 코드 · 시험 · 가짜 slot · manifest · 패치 · 보고서를 복사한 것이고 (파일 단위 `cmp` 불일치 0) `SHA256SUMS.txt` 25 줄을 새로 만들었다. 시험이 만든 `mutant_*.py` 18 개 · `work/` (fixture 30 MB) · `reports/` · `__pycache__` 는 사본에 넣지 않았다 (원본은 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexE/cand/` 에 그대로 있음).
**lead 가 하지 않은 것:** 고침 코드의 줄 단위 검토 · 변이 12 개가 의도한 검사만 끈 것인지 코드 대조 · 17r 의 반례를 ASTRA 의 방식으로 직접 재현 · 실제 slot v3 · guard · isolate 연쇄 · 승인 JSON 발급 · 어떤 값 (UNDECIDED) 도 채우지 않음.

## 3. 물음

1. **17r 의 항목별 재현 반례가 닫혔는가.** 17r 이 낸 6 건 (GPU 0 거절 · smoke 의 `HERE/q_eval.py` · 시작 시험 태그 문법 · 타입 / 승인 결박 · lock 동일성 · argv 중복) 과 추가 (논리 / 물리 장치 · 타 작성자 / USD 경로 · MAE · reset · lease 트리 · 평평한 배치 · 진단 자동 진행) 를 ASTRA 가 17r 에서 쓴 방식 (같은 합성 CLI · 같은 경계 시험) 으로 다시 재현해 달라. 고침이 반례를 막는 방식이 17r 이 말한 「조건을 통째로 없애는 것」 이 아닌지. 새로 생긴 결함 (예: 승인 digest 에 포함한 필드 누락 · 정수 검사의 새 우회 · 시작 시험 계약이 너무 좁아 정상 argv 를 거절 · lease 가 영영 안 풀리는 경우 · 평평한 배치의 경로 검사 약화) 이 있는지.
2. **시험 신뢰 범위 (17r 3 절의 지적에 대한 재판정).** 이번 연결 시험이 실제 `start→tests→guarded→slot→frozen` 코드 경로를 타는가 (가짜 slot 이 어디까지 대체하는가) · 「참 on-only」 · 실제 OS lock / registry 공유 · slot 대기 뒤 변경이 실제 대기 경로에서 걸리는가 · 변이 12 개의 독립 종류 수 (17r: 12 개 mutant 파일은 두 차례 생성물) · 시험이 못 보는 것 (GPU 의 slot · guard · isolate · Kit 연쇄 · 알려진 답 · 물리 버퍼 · peak) 을 구분.
3. **진단 단계의 계약.** 진단 모드의 세 실행 (q 원본 · q_cmdr 작은 버퍼 · q_cmdr 기본 버퍼) 이 17r 5 절 2 ~ 4 가 말한 형식인가 (같은 조건 · 각각 별도 Isaac · 알려진 답은 JSON 의미 일치와 파일 SHA 를 구분 · 비결정성이 나타나면 원본 반복 여부를 사전 예산대로 판단 · 보고 항목). 진단이 끝난 뒤 A 로 자동 진행하지 않는 것이 코드와 시험에서 사실인가. 진단 결과로 A 의 예산 · 마감을 정하는 것은 허용되고 성능을 본 뒤 판정선을 바꾸면 안 된다는 규칙이 manifest 에 어떻게 반영돼 있는가.
4. **UNDECIDED 와 승인 json 발급 조건.** manifest 의 `UNDECIDED` 를 (i) lead 가 측정해 채울 값 (물리 UUID · index · 여유 · 해석기 / NumPy / torch / Isaac 판과 경로 · 코드 · 원자료 해시 · canonical lock / registry 경로) (ii) 팀장 결정이 필요한 값 (GPU 배정 · 독점 실행 범위 · 마감 · 위험 한도 · 중단 / 재시도 예산 · 진단 단계의 원본 반복 예산) (iii) ASTRA 승인이 필요한 것 (승인 json) 으로 정확히 나눠 달라. **ASTRA 가 진단 범위 승인 json 을 발급하는 조건과 순서** (어떤 값이 채워졌고 어떤 CPU 반례가 통과한 뒤인지 · 발급할 json 의 정확한 필드와 해시 대상). 진단 승인과 A 승인을 별도로 두는 설계가 코드에서 강제되는가.
5. **운영 반영과 첫 GPU 진단 순서.** 17r 5 절의 배치 (새 파일 추가 · 구판 보존 · 해시 고정) 를 이번 후보로 구체화해 달라: `_eval` 의 어느 경로에 어떤 파일을 둘지 (manifest 의 candidate_dir · write_root · source_eval 과 일치) · 반영 직후 CPU 재검 (원본 38 개 입력 · 양 군 종료 · SAME · 코드와 승인 결박) · 기동 직전 확인 목록 · 중단 조건 · 보고 문구. **진단 한 묶음의 예상 소요 (Isaac 세 번)** 와 A 45 회 별도 승인 전에 필요한 것.
6. **견적 갱신.** 17r 6 절의 남은 준비 3 ~ 6.25 시간을 이번 진행 (작업자 E 가 12:12 ~ 12:54 에 고침) 으로 갱신해 달라. 지금부터 GPU 진단 시작까지의 현실적인 단계 목록과 각 단계의 병목 (ASTRA 검증 · 팀장 결정 · lead 측정 · 배치).

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17s.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
