# S2 step16 · ASTRA 17ai 결함 수정 보고
> 분류: A/정책학습
> 작성: sol · 2026-10-16
> 근거: TASK-codex-worker-s2-17ai-fixes.md · VERIFY-astra-17ai.md · 설치된 Isaac Lab 소스 · `evidence_s2_step9/step16_release/summary.json`
> 요지: 평가기의 첫 reset·신원·USD 상한과 발 광선 reset·정답표·전용 단회 경로를 CPU에서 고쳤다. 실제 Kit 결과는 미확인이다.
> 상태: CPU 구현 및 회귀 확인됨 · GPU/Isaac 미기동 · lead 재실행 대기

## 범위와 결과

step15 전체를 `s2_step16`으로 복사한 뒤 이 사본만 수정했다. 저장소, 부모 코드, `_eval`, 기존 slot과 guard는 쓰지 않았다. `CUDA_VISIBLE_DEVICES=-1`과 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I -B`로 시험했다. GPU와 Isaac을 시작하지 않았고 승인 JSON을 만들지 않았다.

평가기와 발 검사 경로의 코드 및 계약은 준비됐다. 허용되는 평가 판정은 `INFORMATION_ONLY`, `comparison_ready=false`, `performance_verified=false`다. 실제 Kit의 물리·USD·센서·보상 영수증은 **미확인**이다. 발 검사 감독기는 누락이나 불일치를 HOLD로 분류하며 자동 재시도하지 않는다.

## 결함별 반례, 수정, 양성 대조

| 결함 | 반례의 첫 FAIL | 수정과 양성 대조 |
|---|---|---|
| 평가 첫 reset | 설치된 래퍼 `__init__` AST가 reset을 먼저 호출할 때 `_q_yaw` 누락 | [s2_eval_kit_adapter.py](s2_eval_kit_adapter.py) 165행에서 원환경 보유 및 `_q_yaw` 선설정. 같은 실제 생성자 AST와 reset 함수로 정상 생성, 정상 close 1회, 생성 도중 실패 close 1회 확인. [s2_eval_driver.py](s2_eval_driver.py) 250행은 공통 생성·정리 실패 뒤 나머지 case-arm을 미실행으로 남기고 중단한다. |
| 체크포인트 신원 | `s2_control={}` 및 checkpoint update 2000 대 job update 0이 이전 로더에서 통과 | [s2_eval_cpu.py](s2_eval_cpu.py) 64행에서 completed/next update, optimizer 0 상태, plan·encoder·parent 메타를 검사한다. [s2_eval_driver.py](s2_eval_driver.py) 56행은 job의 plan·encoder·parent 핀을 받으며 로더 영수증을 결과에 남긴다. 빈 control, update, parent, plan, optimizer 변이 모두 거절. |
| USD 변환 상한 | 사후 감시는 9번째 원 변환 호출을 막지 못함 | [usd_isolate_run_v3.py](usd_isolate_run_v3.py) 159행에서 생성자 진입 직전 상한 8 검사. CPU 원 함수 호출 8회, 9번째 미호출 확인. entry와 success 별도 계수, case-arm·entry·생성 USD·Robot reference 결합 검사 추가. [s2_train_contract.py](s2_train_contract.py) 24행 고정 SHA도 새 래퍼 바이트에 맞췄다. |
| 평가 환경 생명주기 | `env.close()`만으로 Warp cache 소멸을 보장할 수 없음 | adapter close 뒤 SimulationContext와 RayCaster 잔존을 확인하고 HOLD. [s2_eval_case_fingerprint.py](s2_eval_case_fingerprint.py)는 현재 Stage USD 삼각형과 원 ray hit를 case별 비교한다. pre-reset receipt와 자연 종료 시험 여부를 행에 보존한다. |
| 발 자연 reset | 고정된 이전 [s2_foot_query.py](fixtures_17ai/old_s2_foot_query.py)의 실제 `live_raycast`에 CPU 공급자를 붙여 1→1에서 `foot_frame_not_fresh` 재현 | [s2_foot_query.py](s2_foot_query.py) 123행이 실제 `_reset_idx`의 ID를 받아 세대를 올린다. 일부 env 자연 reset과 명시적 reset에서 1→1 및 비동기 frame을 확인했다. |
| 발 정답표 및 단회 | 직선 절벽 비용 1은 좌표상 틀림 | [S2-FOOT-KIT-CHECK.md](S2-FOOT-KIT-CHECK.md)를 직선 6·7·8 위험 및 비용 3, 대각 8 및 비용 2, 좁은 cardinal 홈 비용 1로 고쳤다. [s2_foot_scenes.py](s2_foot_scenes.py)의 분석식과 8장면 mesh CPU 대조 통과. |
| 실제 보상·감독 계약 | 계산식 `C×weight×dt`만으로 RewardManager 적용 확인 불가 | [s2_foot_manager_evidence.py](s2_foot_manager_evidence.py)는 실제 term rate와 reset 전 episode 누적 차이를 독립 기대값과 대조한다. [s2_foot_kit_driver.py](s2_foot_kit_driver.py)는 같은 단계의 pose·force·36 ray·현재 USD 충돌구 중심/반경을 기록한다. [s2_foot_kit_scope.py](s2_foot_kit_scope.py)와 [s2_foot_kit_supervisor.py](s2_foot_kit_supervisor.py)는 전용 요청, 단회 claim, STOP, 외부 관찰자, 소유 가족 정리, 자원·lease·USD lock·절대 마감 및 HOLD 영수증을 강제한다. 모의 claim 재사용·승인 digest·STOP 변이를 거절했다. |

평가 감독기 [s2_eval_supervisor.py](s2_eval_supervisor.py)는 claim, 관찰자, lease, USD lock 대기, Kit 시작, 종료, 가족 정리, 반납 시각을 남긴다. 자식 결과에는 case-arm별 생성·실행·close 시각이 있다. 예정 8, 실행, 유효, 미실행과 사유를 분리한다. 운영 HOLD, 자료 HOLD, 성능 결과를 구분하며 자연 종료 미관측 분기를 `untested_branches`로 남긴다.

## CPU 시험 증거

| 시험 | 측정 결과 | 증거 |
|---|---|---|
| step16 직접 시험 | 정상 29/29, 반례·변이 13/13 `want` 포함 첫 FAIL | [test_s2_step16.py](test_s2_step16.py), [clean log](evidence_s2_step9/step16_release/test_s2_step16.py.log) |
| step15 발 기존 시험 | 16/16 | [test_s2_step15_foot.py](test_s2_step15_foot.py), [clean log](evidence_s2_step9/step16_release/test_s2_step15_foot.py.log) |
| B 전체 깨끗한 복사본 | 52/52 파일, 정상 40개 파일의 PASS 라벨 356 및 CAUGHT 라벨 3, 변이 12개 파일의 CAUGHT 라벨 84 및 선행 PASS 라벨 2. 총 PASS 라벨 358, CAUGHT 라벨 87. 모든 변이 파일의 첫 FAIL이 `want`와 일치 | [summary.json](evidence_s2_step9/step16_release/summary.json) |

전체 회귀 실행기는 `test_s2_step16.py`의 JSON 내부 29 PASS·13 CAUGHT를 라벨 수에 합산하지 않는다. 위 직접 시험 수를 별도로 적은 이유다. 전체 회귀의 앞선 두 시도는 고정 fixture의 새 USD 상태 필드 누락, 훈련 계약의 낡은 래퍼 SHA 때문에 각각 정상 시험에서 멈췄다. [test_s2_step14_usd.py](test_s2_step14_usd.py) fixture와 훈련 계약 SHA를 갱신하고 `step16_release`에서 전체를 다시 실행해 통과했다.

## 인도 및 미확인

- `s2_eval_scope`의 실제 Kit 범위는 이제 arm별 `plan_sha256`, `encoder_mode`, `parent_sha256`을 요구한다. 체크포인트에도 부모 SHA가 `plumbing_meta.parent_sha256`으로 있어야 한다. 기존 요청이나 체크포인트가 이 핀을 갖지 않으면 HOLD이며, lead가 같은 바이트를 다시 봉인해야 한다. 기존 훈련 manifest도 새 `usd_isolate_run_v3.py` SHA로 다시 봉인해야 한다.
- 발 전용 요청은 `scope=s2_foot_kit_check_once`, 분석적 8장면, N 최대 2, `steps_per_scene` 2~37, 총 300 step 이하, 학습·optimizer 0, `max_wall_s` 900 이하를 요구한다. 팀장 GPU·마감·자원 결정값은 여기서 만들지 않았다. 승인 JSON도 없다.
- 실제 Kit에서 USD 충돌구 중심/반경, ray 대 현재 collision mesh, RewardManager 15+1 항, 지지/swing, 유한 구멍 바닥, Stage 및 Warp cache 소멸은 미확인이다. 검증기는 불일치나 증거 누락을 HOLD로 남긴다. 실제 자연 종료가 없으면 해당 분기는 미시험이다.
- `S2-STEP16-SHA256SUMS.txt`는 이 보고서와 댓글 초안까지 포함한 번들 파일 SHA 목록이다. 자기 자신은 제외한다. CR 없이 만들고 전 행을 되읽어 재계산한다.
