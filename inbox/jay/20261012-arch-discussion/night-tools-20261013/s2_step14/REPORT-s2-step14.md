# S2 체크포인트 Kit 평가기 step14 CPU 보고
> 분류: A/평가
> 작성: Codex · 2026-10-16
> 근거: TASK-codex-worker-s2-eval-kit2.md · 1043 Q 평가 코드 · A3.4 감독 코드 · Isaac Lab 정적 소스 · evidence_s2_step14
> 요지: 평가 전용 단회 감독 계약, reset 직전 물리 상태 훅, case별 실제 mesh 및 초기 상태 지문 adapter를 CPU에서 묶고 시험했다.
> 상태: CPU 확인 · Kit/GPU 미실행 · 첫 실기동 판정 HOLD

## step13 확정본 정정

`REPORT-s2-step13.md`와 #550 댓글 초안의 변이 수를 14/14로 고쳤다. `S2-STEP13-SHA256SUMS.txt`를 현재 바이트로 다시 만들고 1243/1243 행을 되읽어 검증했다. `s2_eval_driver.py`와 격리 evidence 사본 SHA는 둘 다 `f7a2118fb262c435e829a7ba4ef16c2cb0cd760d9fc49721c911d3af0bbb7b05`, `test_s2_step13_eval.py`와 사본 SHA는 둘 다 `45fe2d56868669cd406dfa983c90c6fab8c9e3a256dec12d58116625bc1a41be`이다. CPU 재실행은 정상 16 PASS, 변이 14 CAUGHT였다. 이는 step13 고정본의 값이며 step14 변경 코드의 해시와 구분한다.

## 만든 것

| 위치 | 역할 | 확인 |
|---|---|---|
| `s2_step14/s2_eval_scope.py:34,49,67` | `s2_eval_driver.py`만 허용하는 정확한 argv, 정보 수집 목적, 학습 0회, smoke 2/2/0/0, fwd10, 단회 claim, 코드 및 입력 SHA, 900초 이하 마감, URDF와 mesh 자산 폐쇄 확인 | CPU 정상 및 변이 |
| `s2_step14/s2_eval_supervisor.py:35,86,184` | 별도 watchdog의 PID/생성 시각과 대상 확인, GPU lease, 기존 USD OS 잠금, Job Object 가족 소유, STOP/마감/자원 관찰, 종료 후 정보 전용 영수증 | 가짜 owner와 lease 시험 |
| `s2_step14/s2_eval_usd_provenance.py` | 최대 여덟 환경 생성의 변환 root, 배정, 산출물 및 robot 참조를 검증 | 합성 2회와 9회 반례 |
| `s2_step14/s2_eval_pre_reset.py:30` | Isaac Lab `ManagerBasedRLEnv.step`의 `_reset_idx` 호출 직전 모든 env 상태를 복사하고, reset 뒤 관측과 분리 | 한 env reset, 다른 env 보존 시험 |
| `s2_step14/s2_eval_case_fingerprint.py:33,65,80,102` | 1043 row 배정, 해당 타일의 world USD mesh SHA, root/관절/물성/명령/dt 지문 | 타일 및 물성 변화 시험 |
| `s2_step14/s2_eval_kit_adapter.py:131,205,227,256,319` | 1043 난도 0.5 지형 설정, 고정 명령, reset seed, 센서 packet, 접촉력과 높이 포함 reset 직전 기록, 실제 USD 및 초기 물성 지문 | CPU import와 정적 소스 대조만 |
| `s2_step14/s2_eval_driver.py:259,280` | 봉인 입력으로 Kit 자식 실행, 장치 UUID 확인, runtime 기록, 누락 시 HOLD 종료 | 기존 step13 회귀와 CPU import |
| `s2_step14/S2-EVAL-KIT-SMOKE.md` | 사전 고정값, manifest/영수증 필드, HOLD 조건 | 문서와 코드 대조 |

1043 `q_eval_cmdr.py:228-301,335-386`에서 난도 0.5, family별 단일 열, 10행, ordinal `%8`, seed reset, fixed command를 읽어 평가 adapter에 옮겼다. Isaac Lab `manager_based_rl_env.py:204-241`에서 종료 판정 뒤 reset, reset 뒤 관측 순서를 확인했다. 학습 경로 `IsaacS2Env`와 A3.4 감독기 원본은 수정하지 않았다. `_eval`과 slot 파일은 읽기만 했다.

## CPU 증거와 첫 실패

`s2_step14/evidence_s2_step14/summary.json`을 최종 시험 영수증으로 남겼다. `verify_s2_step14.py`가 CUDA를 `-1`로 두고 4개 명령을 별도로 실행해 원문 로그를 저장했다.

| 관문 | 결과 | 원문 |
|---|---:|---|
| step14 정상 단위 및 가짜 owner 시험 | 14 PASS | `normal.log` |
| step14 변이 사전 시험 | 8 CAUGHT, want 8/8 일치 | `mutants.json` |
| step13 회귀 | 16 PASS, 14 CAUGHT | `step13_regression.json` |
| 평가 Kit adapter CPU import | PASS | `adapter_import.log` |

변이 첫 실패는 `exact_argv`, `evaluation_only_scope`, `evaluation_conversion_scope`, `approval_digest_or_expiry`, `code_closure_sha256:s2_eval_kit_adapter.py`, `reset_ids_vs_done`, `tile_mesh_empty`, `usd_isolation_state_or_count`였다. 정상 시험과 변이 사전 시험의 수를 합쳐 쓰지 않았다. 가짜 owner 시험은 child 실행 없이 `INFORMATION_ONLY` 영수증과 가족 비움 뒤 lease 및 USD 잠금 해제 순서를 확인했다. 실제 자식 실행은 하지 않았다.

## 남은 미확인과 첫 Kit 단회 HOLD 기준

Kit 실기동에서의 `height_scanner_small` reset 직전 갱신, USD stage의 tile face world 좌표, RobotLab 물성 API와 액추에이터 지연 필드, 여러 case를 한 Kit 프로세스에서 반복 생성할 때의 정리, 첫 격리 변환 횟수는 미확인이다. 이 호출들은 `s2_eval_kit_adapter.py:131,205,227,256`에서 첫 단회 원자료로 확인해야 한다. 평가 자식은 A/B 네 case에서 최대 여덟 환경을 만들 수 있으므로 기존 1회 변환 상한을 그대로 쓰지 않았다. 원본 격리 래퍼는 유지하고 평가 전용으로 `expect_conversions=any`, `usd_conversion_cap=8`, 관찰 주기 중 상한 검사와 사후 배정 및 산출물 검증을 둔다. 실제 횟수가 1~8 범위를 벗어나거나 정보 수집이 실패하거나 한 case라도 누락되면 `s2_eval_supervisor.py:86`의 HOLD 이유에 남는다. 실제 성능, 학습 효과, 전체 60쌍 비교는 아직 측정하지 않았다.

첫 Kit 실행에는 이 코드와 별도로 lead가 결과 전에 봉인할 smoke case JSON 및 eval seed 네 개와 모든 학습 seed 목록, update 0 A/B 체크포인트와 SHA, job JSON, 실제 GPU UUID/index/bus, 900초 이하 마감, watchdog 등록, 해당 scope의 직접 승인값이 필요하다. 이번 CPU 작업은 승인 JSON을 만들거나 GPU/Isaac을 띄우지 않았다. `S2-STEP14-SHA256SUMS.txt`는 이 보고서와 `s2_step14` 파일의 최종 바이트를 담는다.
