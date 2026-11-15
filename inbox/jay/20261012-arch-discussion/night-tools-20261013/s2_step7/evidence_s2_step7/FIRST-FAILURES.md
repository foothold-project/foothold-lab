# S2 step7 첫 실패 기록

> 분류: A/정책학습 · 시험 기록
> 작성: Codex Worker · 2026-10-15
> 근거: 같은 폴더의 clean1~clean3 원시 로그 · `evidence_s2_step6/step7_initial` 및 `step7_normal2` 로그 · 도구 출력
> 요지: 수정 전 첫 실패를 남기고 최종 통과 기록과 구분한다.
> 상태: CPU 관측 기록 · GPU·Isaac 미실행

| 순서 | 처음 실패한 자리 | 조치 |
|---|---|---|
| 직접 E1 CPU 실행 | `execute_plumbing()`에서 `AttributeError: Namespace has no attribute barrier_contract` | CPU fixture Namespace에는 없는 선택 필드를 `getattr`로 읽게 했다. 당시 출력은 별도 파일로 저장하지 못했고 도구 출력에서 관측했다. |
| `step7_initial` | 기존 기동 감사의 `candidate_cwd`, `candidate_argv`가 구 호출 문자열을 기대해 `test_s2_step5_live.py` 종료 1 | 실제 무접미사 slot과 래퍼 argv 기준으로 감사식을 수정했다. |
| `step7_normal2` | `test_s2_step6_contract.py`의 첫 fixture가 `usd_root`를 갖지 않아 `usd_isolation_contract` | fixture에 실행별 root를 채웠다. |
| `clean1` | 복사 묶음의 `test_s2_sensor_tracker_17v.py`가 현 tracker의 필수 source·pose 인자 없이 호출해 TypeError | tracker fixture를 현재 계약에 맞췄다. |
| `clean2` | 복사한 `test_s2_step3_entry.py`가 `s2_train_entry`를 찾지 못해 ModuleNotFoundError | 묶음 내부 `s2_step3`를 향하게 했다. |
| `clean3` | 정상 24개 파일 뒤 첫 변이 `test_s2_step4_mutants.py`가 `--out` 누락으로 종료 2 | 깨끗한 시험 실행기가 변이별 출력 인자를 넘기고 원시 요약의 첫 실패를 대조하게 했다. |
| live 증거 관문 도입 | CPU FakeS2Env가 `plumbing_proof:cpu_fixture_not_live`로 감독기에서 HOLD | 기대 동작으로 유지했다. 구조 시험과 실제 참석 증거를 분리했고, 두 번째 arm 계약은 별도 손수 만든 CPU fixture로만 시험했다. |

최종 `final1/summary.json`은 위 실패 이후의 새 복사본 전체 시험이다. 실패 로그를 PASS로 세지 않았다.
