> 분류: A/정책학습 · ASTRA 의뢰 17ac · S2 첫 수집 세 번째 시도 판독, A3.2 범위, smoke 허용 범위
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 16:10
> 근거: 3차 증거 `night-tools-20261013/s2_stage0_first_collection/attempt3_20261015_1506/` · 판독 스크립트와 출력 `attempt3_analysis.py` `attempt3_analysis_output.txt` · 검사기 `s2_step4a3/s2_connect_check_17v.py` · 진단 `s2_connect_diag_17v.py` · 환경 설정 `s2_env_config_17v.py`
> 요지: 3차는 256행을 끝까지 수집했고(검증 보류), 검사기 HOLD 13개를 원자료로 풀었다. 10개는 진단이 기록을 안 채운 것이고 3개는 실제 데이터 문제(로봇 낙하와 자동 리셋)다. 센서에서 지도로 바꾸는 식은 걸리지 않았다. 이 판독이 맞는지, A3.2 범위가 적절한지, 0단계 PASS 전에 학습 배관 smoke를 허용할지를 묻는다
> 상태: 의뢰 (GPU 둘 다 계산 0 · 승인 json 없음 · 팀장은 채팅에 있고 시도마다 새 동의를 받음)

# ASTRA 17ac

비판적이면서도 냉정하고 현실적인 전문가로서 답해 주십시오. 분량 `VERIFY-astra-17ac.md` 한 파일, 첫 줄 한 문장 판정. 코드 수정 · GPU · Isaac · 커밋 금지, em dash 금지. 17ab에서 닫힌 것은 다시 보지 말고 아래만 봐 주세요.

## 사실 (직접 읽을 것)

- 3차(15:06:39, chain `s2-stage0-a3-live-20261015-150639`): 정상 완료 걸음 256, 원시 행 256, Traceback 0, 변환 0, 가족 0, 자식 종료 코드 0, 감독기 42. A3.1 선적재로 2차의 접근 위반이 사라졌다(통제 비교는 아님).
- 검사기 HOLD 사유 13개: `boundary_evidence_content` `boundary_evidence_hash` `boundary_mask` `boundary_unreported` `case_assignment` `fixed_pose_evidence` `mesh_evidence_hash` `provenance_missing` `root_sensor_transform` `scene_hit_mask` `sensor_timestamp` `stale_packet` `world_height_answer`.
- 진단이 쓰는 meta에는 isaac/kit/torch/driver 버전, mesh 증거, 경계 증거, `root_sensor_offset_b`, `boundary_count`가 없고 `*_verified`는 항상 false다(`s2_connect_diag_17v.py` 끝부분 주석: 뼈대). 그래서 `provenance_missing` `*_evidence_*` `boundary_unreported` `root_sensor_transform` `case_assignment` `mesh_evidence_hash`는 구조상 PASS가 불가능했다.
- 데이터에서 나온 실제 문제(`attempt3_analysis_output.txt`, env 별 trace는 capture.npz):
  1. 로봇이 고정되지 않는다. 스폰 z 0.4가 16걸음 안에 0.17~0.25로 내려앉고 x로 0.06~0.08 m 미끄러진다(`fixed_pose_evidence`).
  2. `terminations.base_contact`가 켜져 있어 자동 리셋이 난다: env 4가 36 · 183 · 246, env 5가 58, env 6이 168(128은 의도한 개입). `stale_packet`(128 이전 에피소드 번호가 상수가 아님)과 `sensor_timestamp`(리셋마다 시각이 0으로 되감김, 음의 차이 13곳)가 여기서 걸린다. 의도한 128 리셋도 같은 이유로 걸리므로 검사기가 리셋 경계를 모른다.
  3. gap_90(env 5)은 구멍으로 떨어져 step 255에서 root z 상대값이 -66.6 m다. 스캐너 오프셋이 z +20 m이라서 z가 -20 아래로 내려간 뒤(step 191부터 miss 187/187) 광선 시작점이 지면 아래가 되어 전부 miss다. oracle은 XY로만 예상하므로 15,521개가 `scene_hit_mask` `world_height_answer`에서 걸렸다. gap_0(env 4)의 miss 2,527개는 oracle과 정확히 같다.
  4. `boundary_mask`의 1개 차이(stones_0 env 6)는 진단이 `ray_starts_w`(float32)에서, 검사기가 `pos_w`와 yaw(float64)에서 경계 거리를 계산하기 때문이다.
- 걸리지 않은 것: `terrain_assignment` `intervention_missing` `fixed_schedule` `reset_not_changed` `translation_not_seen` `height_range` `ray_index` `quaternion_bad` `yaw_case_bad` `bad_ray` `grid_or_yaw` `height_or_offset` `scene_hit_z` `marker_missing_*` `gap_two_cases`.

## 제 계획 (A3.2, 구현은 제가 한다. 이 의뢰는 방향 판독)

1. `s2_env_config_17v.py` eight_case: 로봇 `rigid_props.disable_gravity=True`, `terminations.base_contact=None`(최종 cfg 덤프로 경로 확인함). 진단 전용이며 학습 설정에는 쓰지 않는다.
2. 검사기 `sensor_timestamp`: 음의 차이는 같은 env의 `episode_ids`가 늘어난 곳에서만 허용하고 거기서는 되감김이 있어야 한다.
3. 진단 meta: isaac/kit/torch/driver 버전, 자산 해시, `root_sensor_offset_b`(스캐너 cfg), 경계 증거 파일(검사기와 같은 float64 식으로 계산한 바이트)과 개수와 해시, `edge_excluded`도 같은 식으로.
4. mesh 증거 파일: (a) USD 메시 해시(기존 probe), (b) Warp 메시(`RayCaster.meshes`)의 점과 인덱스를 USD와 수치 비교, (c) PhysX scene query로 같은 광선을 쏘아 RayCaster hit 높이와 비교한 결과. (c)가 허용 오차 안일 때만 `kind=observed_collision_mesh`, 아니면 사유와 함께 HOLD. 새 API는 모두 예외를 삼켜 증거 파일에 오류를 적고 256행 수집은 계속한다.
5. 모든 변경은 시험(정상 통과 뒤 변이 CAUGHT)과 목록 해시를 새로 만든다.

## 질문 (확인됨 / 추정 / 미확인으로)

1. 위 판독(10개는 기록 누락, 3개는 데이터 문제, 센서 식은 걸리지 않음)이 맞는가. 놓친 것이 있는가.
2. 진단에서 중력과 `base_contact` 종료를 끄는 것은 "같은 시험지"를 해치는가. 센서와 지도 변환이 중력과 무관하다는 것을 0단계 PASS의 근거로 받을 수 있는가, 아니면 로봇 고정을 다른 방식(매 걸음 루트 상태 쓰기)으로 해야 하는가.
3. "관측된 충돌 메시"로 무엇을 인정하는가. 4-(c)의 PhysX scene query 비교가 충분한가, 아니면 더 필요한가. 인정 못 하면 어떤 증거가 가능한가(PhysX가 쿠킹한 메시는 직접 접근이 안 된다고 본다. 미확인).
4. 2번 검사기 수정(리셋 인지)을 받을 수 있는가. 다른 형태가 낫다면?
5. A3.2 4차 시도는 허용 범위 안에서 진단 · 환경 설정 · 검사기만 바뀌는 것으로 족한가.
6. **0단계 PASS 전에 B 번들 smoke(학습 배관 확인: 200 update, 두 arm, 결과를 실험 결과로 쓰지 않음)를 허용할 수 있는가.** 허용한다면 조건과 GPU 배정(GPU 1은 데스크톱 앱이 10.6 GB 점유, 팀장이 정리 중)을 말해 달라. sol이 B 실기동 경로를 작업 중이라 코드는 아직 없다.
7. 시도마다 새 ASTRA 판정이 필요하면, 진단 · 환경 설정 · 검사기만 바뀌는 연속 시도에 대해 "lead의 해시 목록과 CPU 시험 기록 제출 + 팀장 새 동의"로 족한 경우를 정의해 줄 수 있는가(왕복을 줄이기 위함. 거절 가능).

## 하지 말 것

- 무인, 자동 재시도, 후속 학습 허용으로 읽히는 표현. 기존 17z 무인 보류는 유지.
