> 분류: A/평가 · #550 17t CPU 고침 인계 초안
> 작성: Codex Worker · 2026-10-15
> 근거: REPORT-17t.md · evidence_17t/run_20261015_010804_121484/summary.json
> 요지: 17t 결함 수정과 CPU 시험 결과, 운영 미확인 사항을 팀장에게 인계한다
> 상태: 댓글 초안 · 미게시

# 1043 평가 후보 17t CPU 고침 요약

17t에서 PID 재사용 시 부모 `(pid, create_time)`을 재확인한 뒤에만 자식을 등록하도록 고쳤습니다. 소유권이 불명확하면 자식에게 신호를 보내지 않고 lease를 보유합니다. 필수 지문 누락은 `held`와 이유로 기록하며, 승인 B의 비교 규칙·이름·재기동 범위·종료 정책 값은 기동 전에 검증합니다. 공통 지문 차이, 전체 run 비용, 반복 미실행 사유, 공통 allowlist의 와일드카드·디렉터리 거절도 추가했습니다.

수정 전 `cand/`는 `cand_17t_base/`에 SHA256 전수 일치로 보존했습니다. 최종 CPU 묶음 `evidence_17t/run_20261015_010804_121484/summary.json`은 15/15 통과했습니다. 17r 입력 변조 12종과 별개로 17s 코드 변이 6/6, 17t 신규 코드 변이 3/3을 정상 시험 선통과와 지정 첫 실패 문구 일치로 확인했습니다. PID 재사용 시험은 가짜 psutil 표만 사용했고 실제 프로세스에 신호를 보내지 않았습니다.

후보 165개 SHA256은 `CAND-17T-SHA256SUMS.txt`, 변경 13개 대응은 `CAND-17T-CHANGES.json`, 상세 고침·시험·첫 실패·한계는 `REPORT-17t.md`에 있습니다. `_eval` 등록 원본 11개 해시 일치, 최상위 후보 파일 0개를 읽기 전용으로 확인했습니다. GPU·Isaac은 실행하지 않았고 manifest의 팀장 결정값은 모두 `UNDECIDED`입니다. ASTRA 권고값은 manifest에 반영하지 않았습니다.

실제 GPU, slot v3·guard·isolate·Kit, 공통 lease 참여, 실제 PID 재사용 경주는 미확인입니다. `test_17s_original.py`의 slot·로그·USD·traceback은 가상화되고, 17r 연결 시험의 일부 진단 검증과 runtime fixture 관문도 대체되어 있습니다. 운영 진단 기동 결정은 별도입니다.
