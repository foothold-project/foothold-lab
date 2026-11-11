> 분류: A/정책학습
> 작성: verifier-lx · 2026-11-11
> 근거: 팀장 결정 c5471d370d634ed2a381d8249a10c652c143f699 · lead 11:30 의뢰 · 승인 해시 재고정 절차 406
> 요지: 승인 칸과 직전 단계 PASS 증거가 함께 있는 범위만 자동 기동 허용으로 기록하고 재고정
> 상태: CPU 확인됨 · 승인 계약 범위 막음 0 · reviewer 검토 전 · 실제 자동 기동기 연결은 별도

# EX-42 승인 칸 안 자동 기동 계약

## 변경과 범위

기준은 통합 ab8aa018. `ex42-approvals.yaml`의 `automatic_launch_allowed`를 `mode: approved_stage_only`, `require_gate_pass: true`, `notify: true`, 결정 원본 SHA로 바꿨다. 전역 `production_launch_allowed: false`, 기존 단계별 부모·회차·DR·연장 범위는 보존했다. E1은 E0 m250 부모에서 기본 1000회, 250회 평가, 연장 false다. E1F 이후는 승인 칸이 없어 열리지 않는다.

기존 `ex42_prep.py`의 단계 0/E0/E1 승인 소비자 세 곳이 `automatic_launch_allowed is False`만 허용했으므로, 승인 파일만 바꾸면 기존 승인 진입도 거부한다. 이 세 소비자는 false 또는 정확한 새 정책만 허용하도록 바꿨다. scalar true, 넓은 범위, PASS 조건 누락 등은 거부한다. 전체 계획의 전역 기동 차단은 유지된다.

`ex42_auto_authorization.validate_automatic_stage_launch`는 다음을 CPU에서 확인하는 승인 검사 함수다.

- 승인 파일 SHA와 계획 pin, 정책 형식, 대상 단계의 기존 승인 칸·한도.
- 실제 부모 manifest와 체크포인트 파일 SHA.
- 호출자가 지정한 관문 영수증 SHA, 직전 단계, 같은 계획 SHA, complete/PASS, 정확한 부모 회차·SHA.
- 기존 39칸 map matrix, 판정 26/기록 13 계약, 연결된 측정 파일 SHA.
- 성공 결과에도 `training_started: false`와 `notification_required: true`를 명시.

**이 PR은 자동 기동 프로세스·대기열·알림 송신기를 만들거나 실행하지 않는다.** 기동기는 위 함수를 호출한 뒤 기존 기동 전 검사와 필요한 알림을 수행해야 한다. 현재 통합 코드에는 이 새 함수의 운영 호출자가 없다. 따라서 이 PR의 CPU PASS를 실제 자동 기동 완료나 GPU 실행 승인으로 읽으면 안 된다. 이번 의뢰인 승인 파일과 그 소비 호환성은 완료, 자동 기동기 연결·실행은 lead가 후속 담당을 연결할 부분이다.

## 해시 재고정 및 실제 자료

| 항목 | 확인값 |
|---|---|
| 이전 승인 파일 SHA | `25c9ba971a0c429960fbfd4bd13c757f744411077eed7a0142d4a27f0069bb78` |
| 새 승인 파일 SHA 및 plan pin | `507af8ce351be8ca2e07ad2d5f3e354ae92025ef3e073aacad28fdedf4be7921` |
| 새 계획 파일 SHA | `815d4e369d7d088ba757db0bc777f48177648c1b925735164d3d940c210ede8d` |
| E0 m250 실제 체크포인트 SHA | `680c820b73646d9c11f62f184fd35e6cc096ffd04681951d542b2b4b472d779e` |
| 새 계획으로 CPU 재판정한 score SHA | `48fb690c607a58b2081f8790368a81ce35fc21e710f8882803336c1423b832f7` |
| 새 P1 영수증 SHA | `82e323fc553d025e32b4ec601665ebe6d9404832984536e3dca017adbd2e09d0` |
| 재판정 및 승인 검사 | PASS · E1 1000회 · 연장 false · 알림 필수 · 실행 안 함 |

원본은 `/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218/`의 manifest·model_250.pt·eval/scores/m250. 읽기만 했다. 새 계산은 `/home/jay/mai/tmp/verifier-lx/scoped-auto-1111/rejudge/`, 실제 승인 결과는 같은 상위 폴더 `authorization-proof.json`에 보존했다. 원본 HOLD를 수정하지 않았다. 기준선 고정 뒤의 재판정 PASS를 사용했다.

## 시험

isaac311, CUDA 숨김, GPU/Kit 미실행. 지정 CPU 7파일 최종 원출력:

```text
151 passed, 2 skipped in 7.65s
```

`pytest-final.log`는 `/home/jay/mai/tmp/verifier-lx/scoped-auto-1111/`에 있다. 새 시험은 구현 전 import 오류를 확인한 뒤 통과시켰다. E0·E1 정상 승인, HOLD/FAIL/null, pending, 다른 단계·계획·체크포인트·회차, 빈 matrix, 영수증·측정·체크포인트·승인 바이트 변조, E1F/E2/E6b, 승인 범위 확대, PASS/알림 조건 제거를 다뤘다.

회귀 대상은 `test_ex42_scoped_auto_cpu.py`, `test_ex42_e1_approval_pin_cpu.py`, `test_ex42_prep_cpu.py`, `test_ex42_speed_probe_e0_cpu.py`, `test_ex42_e1_entry_cpu.py`, `test_ex42_training_entry_cpu.py`, `test_ex42_gate_checks_cpu.py`다. skip 2건은 Windows 공유잠금 시험과 별도 환경 변수로 지정하는 EX-41 부모 체크포인트 시험이다. E0 실물 부모는 위 별도 경로로 확인했다.

통합본의 `test_ex42_e1_entry_cpu.py`에는 #632 병합 전 기대인 「E1 승인 칸 없음」이 남아 있어 1건 실패했다. 이를 현재 1000회·연장 false·후속 단계 false 검사로 고쳤다. 승인 칸을 지운 반례 거부는 기존 별도 시험에 남아 있다.

## reviewer 확인 요청

새 정책을 단순 truthy로 해석하는 우회가 없는지, E1F 이후·조건 누락을 막는지, 재고정된 승인 SHA와 실제 부모/P1 연결을 독립 확인한다. 자동 기동기·알림 실행은 미확인 경계로 유지한다.

## 11:45 의뢰 후속: 계획 선언 정합과 운영 E1 읽기 경로

#639 병합은 11:45에 시작한 E1 종료까지 보류한다. E1F 승인 칸은 없으므로 이번 자동 기동 대상이 아니다. `ex42-prep.yaml:35`의 `launch.automatic`을 `approved_stage_only`로 맞추고 선언 일치 시험을 추가했다. 고치기 전 해당 시험은 `False != approved_stage_only`로 실패, 수정 뒤 관련 CPU 36 passed. 이전 v0.16 시험의 automatic=false 기대도 현재 결정으로 갱신했다.

이번 재고정에서 승인 파일 바이트는 추가로 바뀌지 않았다. 다시 계산한 승인 SHA는 기존 `507af8ce351be8ca2e07ad2d5f3e354ae92025ef3e073aacad28fdedf4be7921`과 같고 plan pin도 일치한다. 최종 계획 SHA는 **`19e86a25c846ed7ceb3a543a91077cb30e1b04b02987bb1f6468906795291167`**이다. 위 표의 `815d4e36...`은 첫 커밋의 이력값이다. 새 계획으로 원본 E0 자료를 CPU 재판정한 결과도 PASS이며 `rejudge-plan-aligned/rejudge_receipt.json`에 score `2bcf0aa7b830476364daa9ec5ac3ae6704e65f2fa4fec012b1f1d97b0a77d05a`, P1 `5c1f5327d34bbb482320033ed03d3d13c49804ea1fdc4f0fed2aa415507cdadc`를 남겼다.

**운영 E1 한 줄 결론:** 실제 PID 3119663의 학습 `--ex42_plan`과 경계 평가 `--p1-plan`은 모두 `/home/jay/mai/wt/foothold-lab/ex42-launch-b379eb98/foothold_s2/curriculum/ex42-prep.yaml`이고, 파일 모드 444·실제 SHA `e542961d9c65a588ae893b81a8d07d39cd66ca068f2f118410c3e2d1d7a2d982`가 startup_receipt와 일치하므로 #639나 통합 가지 변경을 자동으로 읽는 경로는 현재 argv에 없다.

경계와 한계: 고정 사본 `ex42_score_watch.py:48`은 전달받은 메모리 plan의 SHA를 기록한다. `ex42_chain.py:383`이 그 객체를 넘기고, 별도 평가 자식 `ex42_eval_once.py:146`은 `--p1-plan` 파일을 다시 읽는다. 그 함수만 보면 파일 변경 시 다른 계획을 읽을 수 있지만 현재 실제 인자는 고정 사본 경로다. 다른 SHA를 가진 P1 결과는 `ex42_chain.py:462~465`에서 기동 시 plan SHA와 비교해 거부한다. 이 확인은 250 경계 실제 완료 실측이 아니라 기동 인자·파일·영수증과 소비 코드 대조다. 운영 사본·프로세스·원자료는 수정하지 않았다. 되읽기 증거는 `/home/jay/mai/tmp/verifier-lx/scoped-auto-1111/live-e1-plan-readback.json`.

## 11:50 reviewer 고침 1 후속

`REVIEW-0858295c.md`의 생존 돌연변이 세 건을 겨냥해 시험만 보강했다. bounded 정책의 truthy 값 세 가지는 단계 0/E0/E1 소비자와 전체 launch_blockers까지 거부하는지 확인한다. 정확한 정책에 `later_stages_authorized: true`를 더하면 strict/bounded/API 모두 거부한다. E1F는 단순 ValueError가 아니라 대상 표에서 거절한 메시지까지 확인해, 부모 검사에 우연히 막힌 결과를 같은 통과로 세지 않는다.

| CPU 입력 | 결과 |
|---|---|
| 정상 scoped_auto + e1_entry | 45 passed in 5.00s |
| `bounded_automatic_policy`를 false 또는 bool(value)로 바꿈 | 4 failed, 30 passed · pytest rc1 |
| 정책 키 집합 대조 제거 | 1 failed, 33 passed · pytest rc1 |
| 대상 validators에 E1F 추가 | 1 failed, 33 passed · pytest rc1 |

돌연변이는 새 CPU 프로세스의 모듈 메모리 안에서만 적용했고 소스 파일을 고치지 않았다. 재현 스크립트·원출력은 `/home/jay/mai/tmp/verifier-lx/scoped-auto-1111/mutants/`의 `check.py`, `truthy.log`, `extra_key.log`, `e1f.log`다.

#634 선행 병합 순서에 맞춰 `test_ex42_e1_entry_cpu.py`의 충돌한 첫 함수는 206c0848과 정확히 같은 이름·본문으로 맞췄고 부분 문자열 바이트 대조 PASS를 확인했다. sonnet-code-lx에 이 방식을 직접 전달했고 turn_started 영수증을 확인했다. 승인·계획·운영 코드는 이번 시험 보강에서 바뀌지 않았다. #639의 E1 종료 전 병합 보류는 유지한다.
