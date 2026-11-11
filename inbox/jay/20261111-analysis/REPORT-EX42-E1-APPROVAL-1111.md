# EX-42 E1 조건부 승인 칸과 해시 재고정

> 분류: 구현 검증
> 작성: verifier-lx · 2026-11-11
> 근거: 팀장 결정 7ef023f5 · lead-lx 10:30 의뢰 · decisions.tsv 406 재고정 절차
> 요지: E0 m250을 부모로 E1 1000회만 기록하며 E0 재판정 PASS 조건과 이후 단계 비승인을 보존
> 상태: 확인됨 · 승인 범위 막음 0 · 소비자 평가간격 확인 1건 · GPU/Kit 없음

## 승인 범위와 실제 부모

팀장 결정 7ef023f58027f43c985c34a521d53a52252cabdf의 승인 2는 「E1 진입 (재판정 통과 조건)」이다. 승인 1의 부모 기준값·calibration 고정과 E0 m250 재판정이 선행한다. 조건을 없앤 무조건 기동 승인으로 바꾸지 않는다.

부모 원본: `/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218/model_250.pt`.
직접 파일 SHA256은 `680c820b73646d9c11f62f184fd35e6cc096ffd04681951d542b2b4b472d779e`이며 같은 폴더 manifest.checkpoints.model_250.pt와 일치한다. manifest.progress.completed_updates는 250이다.
CPU 확인 스크립트·영수증은 `/home/jay/mai/tmp/verifier-lx/e1-approval-1111/probe_parent.py`, `parent.json`.

## 변경의 경계

이 작업은 승인 기록·승인 파일 바이트 해시 재고정이다. E0 및 stage-zero 기존 승인 범위, 전역 production/automatic false, DR 1.0과 push 제외 목록은 보존한다. E1의 이후 단계 비승인은 E1F와 E2 이후도 열지 않는다. 본 단계의 설계상 체류 길이를 250으로 바꾸는 작업이 아니며, 승인된 이번 구간만 1000회로 한정한다.

현재 확인한 통합 4cc326c7의 validate_ex42_stage_e_cli는 E0만 허용한다. E1 소비자 구현·재판정 영수증 검증·실제 기동은 이번 기록 작업이 완료됐다는 이유만으로 통과 처리할 수 없다.

## 순서와 최종 변경

scripter PR #631 `437a593b9627a672f1f919a768b4de5b1ac5fcfd`를 먼저 fast-forward로 포함한 뒤 수정했다. 그 커밋의 q4 실측값·기준선·점수 설정을 그대로 보존했다. 승인 파일은 `stage_e1_authorization` 한 칸 추가, prep은 `stage_zero.approval_sha256` 한 줄만 변경했다. 파싱한 두 문서를 부모와 대조하여 그 밖 변경 0을 확인했다.

10:30 의뢰의 250회는 lead가 10:48에 정정했다. 최종 E1 scope는 최대 **1000회**, `extension_authorized: false`, `boundary_evaluation_interval_updates: 250`, `later_stages_authorized: false`. E0 부모 250회와 E1 새 구간 1000회를 혼동하지 않는다. 팀장 승인 원문 시간은 분 단위 `2026-11-11T10:29+09:00`로 보존했다.

승인 SHA는 `c4c76916f8d126694c7c8c9be81430919d99cf09a27375379f727cc19c24f680`에서 **`25c9ba971a0c429960fbfd4bd13c757f744411077eed7a0142d4a27f0069bb78`**로 마지막에 재고정했다. 새 plan SHA는 `a0d9d0669374136eb3efd25c0c22afc6c22694c0b673ed08328db1bce2afb9d0`이다.

## CPU 검증과 재판정 조건

- 신규 시험은 승인 칸이 없는 부모에서 2 failed를 확인한 뒤 수정했다. 최종 신규·E0 approval-pin·prep·v017·E0 baseline 다섯 파일은 **25 passed in 1.82s**. 승인 파일 한 줄 추가는 기존 stage-zero SHA 검사에서 거절된다. 기존 E0 250회·stage-zero 1000회 승인 범위는 보존된다.
- 아직 병합되지 않은 sonnet PR #630 `55100109`의 `validate_stage_e1_authorization` 함수 AST를 그대로 추출해 실제 새 승인 YAML과 plan으로 실행했다. **stage_e1_only_authorized**. 최대250/1001·다른 부모·이후 단계 허용·DR0.8 다섯 반례 모두 ValueError. 이는 해당 함수의 CPU 호환성 검사이며 E1 전체 CLI·사슬·Kit 실행 시험이 아니다.
- scripter의 원본 재판정 영수증을 직접 되읽고 score·P1 파일 SHA를 대조했다. 그 뒤 **동일 원평가를 자기 사본에서 CPU 재판정**했다. 원본 운영 원장은 수정하지 않았다.
- 재고정 전 재판정 PASS. score SHA `7c656fbb99a7be8d56819bf99d40c0a252d24e2136b6939f586ae60f54eb9bcb`로 scripter와 동일했다.
- 최종 승인 핀으로 다시 실행한 재판정도 **PASS**, score SHA `5d858e593acb55f73681a26d27c02cd60957b92da3b6b8038fcb6f4306919a9e`, P1 SHA `1b5a7b87b598a406204ca40056085845b54aeba83e77a484ccf29faaf4e66a84`. 재고정 전후 score의 유일한 차이는 `maintenance_source_sha256`(plan SHA)이며 측정·판정 값은 불변이다.
- 경로: `/home/jay/mai/tmp/verifier-lx/e1-approval-1111/green.log`, `consumer_probe.py`, `consumer_probe.log`, `rejudge/`, `rejudge-final-pin/`. GPU 숨김·isaac311·pytest cache 끔, GPU/Kit 미실행.

## 남은 통합 확인

**승인 기록·재고정 범위 막음 0. 기동 전 소비자 확인 1건.** PR #630 `55100109`의 `train_start.py:105,623`은 E1에서도 `p1_interval=EX42_STAGE_UPDATES=1000`을 전달한다. 10:48 지시의 경계 평가 250회 간격과 다르다. 본 승인 칸에는 250을 기록했지만 이 필드는 현재 그 소비자에서 읽지 않는다. lead에 보고했으며 생산 코드 고침은 이 PR 범위 밖이다.

PR #630의 승인 검사 함수는 `prerequisites`를 검증하지 않는다. 이번 부모의 PASS는 위 원자료 재판정으로 직접 확인했지만, 이 YAML만으로 향후 다른 영수증까지 자동 검증된다고 주장하지 않는다. E1 전체 기동 허용 여부는 소비자 통합과 기존 Kit 관문에서 따로 확인해야 한다.
