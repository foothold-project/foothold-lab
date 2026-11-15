> 분류: A/정책학습
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-s2-17v-fix.md · VERIFY-astra-17v.md · codexE/s2_step4/evidence_s2_step4a/run_20261015_0500_a1
> 요지: 17v 0 단계의 CPU 후보, 알려진 답, OS 소유 경계와 남은 라이브 보류 사유
> 상태: A CPU 중간 보고 · 실제 GPU/Isaac 접속 미실행 · 0 단계 라이브 PASS 미확인

# S2 17v · A 단계 중간 보고

## 범위와 격리

이번 A는 오래된 센서 packet과 비유한 yaw 두 P1, 8환경 접속 진단, 여섯 호출의 정적 대조, 0 단계 전용 감독기와 판정이다. 시간제한 종료·조우·PPO·학습 사슬·비교기·encoder는 이미 만든 파일을 보존하고 B에서 최종 회귀·보고한다. 작업 파일은 `codexE/s2_step4/`에만 썼다. `_eval`, slot v3, guard, 부모 및 2·3단계 원본에는 쓰지 않았다. `CUDA_VISIBLE_DEVICES=-1`, GPU·Isaac 실행 0, 커밋·외부 발송 0이다.

기존 2단계 16개와 3단계 12개의 등록 SHA256을 재대조해 불일치 0이었다. A 파일 목록과 해시는 `S2-STEP4A-SHA256SUMS.txt`에 둔다.

## 고침과 증거

| 요구 | 사본과 실제 고침 | 정상·반례 |
|---|---|---|
| 동일 센서 packet | `s2_packet_17v.py`는 obs·raw hit·pose·episode·sim step·센서 세대·원자료 SHA를 한 packet으로 받는다. `s2_sensor_tracker_17v.py`는 RayCaster의 private 갱신 호출을 관찰하고 env별 세대와 source receipt를 만든다. runner는 별도 source receipt를 재조회한다. | `test_s2_17v_core.py`에서 같은 XY·다른 높이 reset, 일부 env reset, 번호만 새로 붙인 과거 raw, yaw 같은 이동 반례. `test_s2_sensor_tracker_17v.py` 4 PASS. source receipt를 빼는 코드 변이의 첫 실패 `old_raw_new_numbers_rejected` CAUGHT. 실제 Isaac private hook 시점은 미확인. |
| yaw | `s2_env_adapter_17v.py`는 yaw·quaternion·월드 변환의 유한성과 quaternion norm ±0.001을 앞에서 검사한다. | NaN/Inf yaw 및 비정규 quaternion 반례. 앞뒤 유한성 검사를 함께 제거한 변이의 첫 실패 `nonfinite_yaw_rejected` CAUGHT. |
| 8×256 진단 | `s2_env_config_17v.py`는 한 장면의 4 terrain 열에 환경 0/1·2/3·4/5·6/7을 배치한다. `s2_connect_diag_17v.py`는 256 제어 step, 16 warmup, 64 이동·128 새 위치/높이 reset·192 yaw를 기록한다. `s2_connect_check_17v.py`는 x-fast 187칸, yaw 90° 첫 좌표, height/offset, 전체 +inf miss와 깊은 유한 바닥, 비유한 raw, 2mm 내부 허용·5mm 경계 제외 수, raw 세대·배정·출처를 독립 검사한다. | 분석식 8×256 정상 및 stale·ray 순서·20m 재가산·yaw NaN·숨은 plane·경계 누락 6반례와 개입표 총 8 PASS. ray geometry 검사를 없앤 코드 변이 `ray_order_rejected` CAUGHT. 실제 단차·돌 비대칭 표식의 mesh·충돌체 해시와 고정 자세는 아직 메타가 비어 있어 라이브 결과 HOLD. |
| 최소 OS 감독기 | `s2_job_owner.py`는 Windows 자식을 suspended 생성하고 Job Object 배정 뒤 resume한다. KILL_ON_JOB_CLOSE를 설정하고 PID로 재조회해 신호하지 않는다. `s2_resource_lease.py`는 UUID별 byte lock과 별도의 호스트 USD lock을 제공한다. `s2_zero_supervisor.py`는 외부 승인/파일 해시·단회 claim·STOP·마감·상태·영수증·가족 종료 후 lease 반납을 묶는다. `s2_stage_gate_17v.py`는 0단계 raw 256×8, optimizer 0, source SHA, artifact SHA를 재검한다. | 가상 kernel 표 5 PASS: 배정 전 resume 금지, PID 재사용 시 다른 PID 무신호, AccessDenied, 새 후손, 가족 비기 전 반납 금지. 실제 Windows Job Object는 시험용 CPU 자식 자연 종료·active 0·exit 0 1 PASS. lease 4 PASS, 가짜 0단계 정상·위조 영수증·255 step·마감·claim 6 PASS. claim 검사를 없앤 변이 `approval_claim_once`, Job 배정 호출을 없앤 변이 `assign_before_resume` CAUGHT. |

정적 호출 근거 여섯과 줄 번호는 `s2_step4/S2-17V-CONNECT-SOURCE.md`에 있다. 원점·terrain type/level, RayCaster private 갱신, Isaac 판, 부분 상태 저장, RayCaster mesh와 contact force, `close()`는 찾았다. Kit/driver 판, 환경 전체 재개, 장애물별 조우 이벤트, 단일 AppLauncher 안 순차 scene 재생성의 안전성은 정적으로 확인하지 못했다. 진단은 한 장면 8환경을 쓰며 순차 재생성을 요구하지 않는다.

## 재실행과 변이

`evidence_s2_step4a/run_20261015_0500_a1/summary.json`: 정상 7/7 종료 코드 0, 로그의 PASS 라벨 합 44개. 16개가 포함된 core 시험은 B에 해당하는 선행 알려진 답도 포함하므로 44개를 A 전용 검증 수로 해석하지 않는다. A 코드 변이 5/5는 각 정상 사본이 같은 입력에서 먼저 통과하고, 변이의 **첫 FAIL 라벨이 want와 같을 때만** CAUGHT로 기록했다. 코드 변이와 위의 입력 반례는 별개다.

첫 예비 변이에서는 yaw 앞 검사만 지웠지만 뒤의 월드 좌표 유한성 검사가 계속 막아 `NOT_CAUGHT`였다. 변이의 실제 의미를 두 유한성 검사를 제거한 것으로 바꾼 뒤 새 예비 묶음과 A 최종 묶음에서 `CAUGHT`를 확인했다. Job 변이 예비 실행의 가짜 kernel 함수 인자 수가 새 시그니처와 달라 정상 사본부터 실패했다. 시험 fixture를 고친 뒤 다시 실행했다. 두 실패를 A 최종 5/5에 넣지 않았다.

## 실제 0 단계의 남은 보류

0 단계 코드는 GPU나 Isaac을 이번에 실행하지 않았다. 진단 메타는 `mesh_collision_verified=false`와 `fixed_pose_verified=false`를 명시하며 Kit·driver 판, RayCaster가 실제 읽은 vertices/faces/world transform과 충돌 mesh, 숨은 plane 부재, 고정 자세가 아직 확인되지 않았다. 따라서 현재 스크립트로 실제 raw를 캡처하더라도 검사기는 의도대로 HOLD한다. 첫 GPU 진단으로 이 필드를 실측하는 accessor와 자세 유지 절차를 검토해야 하며, 값을 꾸며 PASS로 바꾸면 안 된다. 2mm/5mm는 ASTRA 시험안이지 실측 정밀도가 아니다.

Windows Job Object의 suspended 배정과 자연 종료는 CPU에서 재현했다. 감독기 자신의 Orca/CLI 세션 이탈 후 생존, 감독기 hang에 대한 독립 hard deadline 감시, 다른 GPU 실행기의 동일 UUID lease 참여는 미확인이다. `s2_zero_supervisor.py`는 감독기가 살아 있을 때 STOP·wall/monotonic 마감을 감시하고 죽으면 Job handle 닫힘으로 자식 가족을 정리하지만, 독립 watchdog까지 확인된 것은 아니다. 현재 승인 JSON은 없으며 실제 기동값은 `UNDECIDED`다.

기존 `_eval/isaac_slot_v3.py:145~152`의 PID 재조회 kill, `:361,500~505`의 직계 wrapper 종료 기준, `_eval/gpu_guard.py:29~48`의 직계 기준은 수정하지 않았다. A의 진단 자식은 이 두 도구를 호출하지 않고 감독기의 Job Object 안에서 직접 띄우도록 제안한다. 기존 예약 실행기와 S2가 같은 UUID lease를 사용하지 않는 경로가 남으면 전체 자원 배제는 성립하지 않는다.

## lead와 ASTRA에 확인할 것

1. 첫 GPU 접속 진단의 실제 mesh/collision 및 고정 자세 증거를 어느 설치 API로 채울지, private sensor hook이 reset 직후에도 모든 env를 포착하는지 확인이 필요하다.
2. Kit/driver 판과 장치 UUID·VRAM의 실제 accessor, 기존 예약 실행기의 lease 참여 범위가 필요하다.
3. 0단계 감독기의 세션 분리와 독립 hard deadline 감시가 필요한 운영 경계인지 판정을 요청한다. 현재 후보는 CPU 가짜 단계 검증과 보류 조건까지의 중간본이다.

팀장 결정값은 제안으로만 둔다. ASTRA의 N=1,024·smoke200·짧은2,000·+500·LR 0.000170859375 등은 B manifest 출발 후보일 뿐 승인값이 아니다.
