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
