> 분류: A/평가 · 1043 드라이버 후보 변경 기록
> 작성: Codex Worker · 2026-10-14
> 근거: v37 원본 c351fde3… · VERIFY-astra-17q.md · cand/diff-driver.patch · CPU 시험
> 요지: v37을 A 45회 전용 1043 후보로 이식하고 새 manifest·기동 관문·출처·판정 경로를 연결
> 상태: CPU 후보 · GPU 및 Isaac 실행 미확인 · 운영 반영 금지

# 드라이버 변경

기준은 `_eval/cmdr_eval_driver_v37.py` SHA256 `c351fde3e038ff27f37a4bb47e2e20492274abf79b5c2547f12f488564f2212a`다. 전체 줄별 변경은 `cand/diff-driver.patch`에 보존했다.

| 갈래 | 변경 | 함수·영역 |
|---|---|---|
| ① manifest·경로 | `--manifest`와 후보 해시를 받는다. 부모·off/on 모델, 실험, 출력·로그·attempt·STOP·registry·lock을 계약에서 읽는다. q에 `--outdir`와 평가 조건을 명시한다. 모델 역할은 등록한 정확한 부모 경로로 구분한다. | 모듈 설정, `pins`, `q`, `stop_requested`, `main` |
| ② 기동 관문 | 기존 자체 변환 잠금을 사용하지 않는다. 별도 실행 lease를 자식 종료까지 보유하고 slot v3에 명시적 변환 잠금·v3 registry·attempt USD 루트·`--expect_conversions 1`을 넘긴다. 기동 직전 물리 UUID·여유를 확인하고 slot 뒤 첫 자식인 `frozen_exec_s1043.py`가 입력을 다시 본다. 미참여 Isaac과 미결정 계약은 기동을 막는다. | `gate`, `run_lease`, `gpu_preflight`, `guarded`, `frozen_exec_s1043.py` |
| ③ 출처·단계 | 첫 배포 CLI는 A 45개만 허용한다. B·remeasure는 종료 코드 8로 거절한다. off/on 양쪽 학습 결과·stamp·종료 근거와 1043 비교 보고를 요구한다. 동일 A 로그의 재시도만 재검하며 새 stamp에 계약 해시·실험·stage·origin을 쓴다. 1042 및 legacy stamp는 재사용하지 않는다. | `training_done`, `ready`, `jobs`, `start`, `process`, `stamp_ok`, `write_stamp`, `main` |
| ④ 판정·표시 | 100 episode·seed·noise·장치·출력 경로·bundle·slot 기록·짝 지문 검사를 보존하고 등록값 대조를 더했다. A 완료는 계획 45개 모두 valid일 때만 로그에서 참이다. post 결합 판정은 다음 단계에 남는다. | `validate`, `main_base`, `tests`, `main` |

새 이름에 맞게 `PARTICIPANT`를 바꾸었다. 태그 접두는 밑줄 없는 `cq`로 유지했다. 1042의 `out/branch` 기본 출력·고정 seed 비교기·구형 pin과 `gate_c1` 시작 시험은 가져오지 않았다. 현재 1043 비교기와 off/on 24,000 시작 시험을 참조한다. v37의 `main_remeasure` 함수 본문은 소스 대조용으로 남아 있지만 CLI에서 진입하지 못한다. B/remeasure를 켜려면 별도 단계의 새 코드 검증과 A 재사용 영향 검토가 필요하다.

CPU에서 `cand/test_driver_cpu.py --run-id stage_c_2`의 다섯 항목이 통과했다. A 계획은 45개 고유 태그, B 잔여 510개였다. B와 remeasure는 rc 8, 자기 해시 오류는 rc 3, q의 `--outdir`와 부모·분기 모델 역할이 일치했다. 첫 시험 시 PowerShell 하위 프로세스 출력의 cp949 디코딩 오류로 시험 기록이 끊겼다. 시험 호출에 UTF-8 디코딩을 명시한 뒤 다시 실행했다. 이 첫 실패는 통과 분모에 넣지 않았다.

통합 단계에서 `--cpu_plan`도 manifest의 v3 registry·공통 변환 잠금·별도 실행 lease 구조를 검사하도록 강화했다. `test_driver_cpu.py --run-id final2`의 같은 다섯 항목과 통합 반례의 v2 registry·분리된 변환 잠금 거절을 다시 확인했다.

**기동 제한:** 후보 manifest의 GPU·UUID·마감·승인·위험 한도, 공통 lease 참가 확인, 변환 잠금 공유 확인은 미정이다. 실제 운영의 공통 변환 잠금이 현재 후보의 `codexE` 잠금과 동일하다는 근거가 없다. 따라서 이 코드는 GPU에서 실행 가능하다는 결론이 아니며, `launch_errors()`가 기동을 거절한다. slot·guard·Isaac의 실제 연쇄, GPU peak와 q 알려진 답은 GPU 단계에서만 확인할 수 있다.
