# S2 0 단계 A2 · ASTRA 17w 고침 보고
> 분류: A/정책학습 · CPU 작업 보고
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-s2-17w-fix.md · VERIFY-astra-17w.md · CPU 실행 로그
> 요지: A2 정보 수집 전용 경로를 고치고 완결 묶음의 독립 import와 반례를 확인했다.
> 상태: CPU 확인됨 · 실제 GPU/Isaac 미실행 · 결과와 기동 승인 UNDECIDED

## 범위와 격리

- 작업 원본은 `codexE/s2_step4a2/`, 최종 고정본은 `codexE/s2_step4a2_frozen/`이다. 앞선 고정 시도의 바이트는 `s2_step4a2_frozen_precheck/`에 보존했다. 최종 고정본은 복사 후 수정하지 않았다.
- `_eval`, IsaacLab `source`, 부모 코드, 기존 slot/guard를 수정하지 않았다. 커밋, GPU 조회나 실행, Isaac 실행을 하지 않았다. 모든 실행 시험은 `CUDA_VISIBLE_DEVICES=-1`인 CPU 자식 또는 가짜 provider를 사용했다. 실제 lock 파일도 획득하지 않았다.
- B 작업은 현재 CPU 단위를 마친 뒤 중단했고 이어 갈 위치를 `HANDOFF.md`에 남겼다. 팀장 결정값을 manifest에 쓰지 않았다.

## 환경 연결과 정답 장면

설치 `rough.py:16,21`의 기본 지형 키에는 네 진단 키가 없다. `s2_env_config_17v.py`는 등록된 `Isaac-Velocity-Rough-Unitree-Go2-v0` 환경 cfg를 불러온 다음, `s2_known_scene_a2.py`의 명시적 네 지형 생성기로 교체한다. `terrain_generator.py:238-266`의 curriculum 열 선택과 `terrain_importer.py:335-353`의 환경별 열 배정에 맞춰 1행×4열, 각 두 환경을 flat, obstacles, gap, stepping_stones 순서로 둔다. 높이 스캐너의 원래 지형 prim은 `velocity_env_cfg.py:66-72`의 `/World/ground`다. `s2_scene_answer_a2.json`에 비대칭 단차·돌의 0.2 m 윗면, gap의 -2 m 깊은 바닥과 실제 void를 고정했다. 답 JSON SHA-256은 `b3a9c5be54e4e16856249c2426d39640f450b18778e24e979fc1a1f1d18a4296`이다.

CPU 기하 시험은 이 작업자 Python에 `trimesh`가 없어 삼각형·box 대역을 주입한 뒤 실제 지형 생성 함수를 호출했다. 네 mesh, 두 0.2 m 표식, gap의 유한 바닥과 +inf miss, void 아래 수평면 부재를 확인했다. Isaac에서 만들어질 USD/Warp mesh와 충돌 대응은 미확인이다. 최종 Isaac cfg는 기동 때 `final_cfg.json`에 원문과 SHA-256을 기록한다. CPU 환경에서 그 최종 해시를 미리 계산하거나 승인값이라고 쓰지 않았다. 부모 checkpoint는 해시만 기록하며 정책 추론에는 쓰지 않는다.

## 고침과 증거

| 항목 | 고침 | 정상 로그 · 반례 | 코드 변이 want와 실제 의미 |
|---|---|---|---|
| 세계 기준 정답 | `s2_connect_check_17v.py`가 finite/range, 16/240 mode, 원센서 transform, 정적 mesh oracle, 환경·구간별 비대칭 표식, 실제 경계 거리와 외부 파일 SHA를 확인한다. reset 뒤 평지 hit Z=0, 센서 Z=.7이면 height=.2가 정답이다. | `test_s2_connect_a2.py.log` 10 PASS. NaN, fixed 1, root+100 m, step90, stones90, 정적 평지 reset, 경계 및 mesh hash 반례가 각각 HOLD. | `height_nan_height_nonfinite`, `fixed_one_fixed_schedule`, `root_100m_root_sensor_transform`, `marker_step90_scene_hit_z`: 해당 검사 호출 자체를 무력화해 각 반례가 지정 사유로 거절되지 않음을 증명했다. |
| 센서 결박 | `s2_sensor_tracker_17v.py`가 `_update_buffers_impl` 직후 env별 raw/pose digest, timestamp, generation과 설치된 hook 소스 경로·해시를 동결하고 snapshot에서 대조한다. `s2_packet_17v.py`는 mount quaternion 변환을 검사한다. | `test_s2_sensor_tracker_17v.py.log` 7 PASS, `test_s2_17v_core.py.log` 17 PASS. 버퍼·pose 되돌림과 root+100 m 포함. | A 회귀 `yaw_finite`는 world XY 경로의 두 finite guard 제거, `independent_sensor_receipt`는 외부 출처 대조 제거다. 각각 지정 FAIL. |
| 부분 자료·로그 | `s2_capture_journal_a2.py`가 launch를 초기 import 전 저장하고 256 raw 행 각각을 지도 검증 전 원자 기록한다. 실패 행·마지막 유효 행·traceback·정리 결과와 자식 stdout/stderr를 남긴다. live 결과는 강제 `HOLD_INFORMATION_ONLY`, 재시도 0이다. | `test_s2_capture_journal_a2.py.log` 4 PASS. step64 지도 오류에도 0/63/64 raw와 partial 65, 미완료 상태 보존. | `raw_row_before_map_error`: raw 선기록 줄을 제거하니 오류 행 보존 시험이 처음 FAIL. |
| 장치·자원·소유 | `s2_stage0_resources_a2.py`와 `s2_device_binding_a2.py`가 NVML UUID/index/bus, 자식 torch bus, 관찰 가능한 Kit 선택, VRAM·디스크 하한/상한을 검사한다. `s2_zero_supervisor.py`는 기존 host USD byte lock을 GPU lease와 함께 획득하고 새 USD root, Job 소유 가족, STOP/마감, 단회 claim, 상태·receipt를 관리한다. | `test_s2_device_binding_a2.py.log` 4, `test_s2_stage0_contract_a2.py.log` 11, `test_s2_job_owner.py.log` 5, `test_s2_job_object_os.py.log` 2, `test_s2_resource_lease.py.log` 4, `test_s2_zero_supervisor.py.log` 6 PASS. cuda:1, 다른 UUID, disk 1 byte, 누락 의존 파일, VRAM/출력 제한 반례 거절. | `disk1_rejected`: 최소 raw 출력 예산 검사를 제거. `torch_bus_mismatch_rejected`: 자식 PCI bus 불일치 거절을 제거. A 회귀 `claim_exclusive`: 단회 claim의 `exist_ok=False`를 `True`로 변경. `job_assign_before_resume`: Job 배정 호출 제거. 모두 지정 첫 FAIL. |
| 사전 관문·묶음 | `s2_stage0_contract_a2.py`는 23개 필수 파일의 정확한 이름/해시 집합과 전체 필수 CLI를 확인한다. `s2_stage0_prelaunch.py`는 기동 전 GO/NO_GO 기록을 만든다. | 새 통합 실행 `r20261015_17w_a2_final3/summary.json` complete true. 정상 시험 84 PASS, A 기존 코드 변이 5/5, A2 새 코드 변이 7/7 CAUGHT. | A 회귀 `ray_geometry`는 ray XY 거절 호출을 무력화했다. 지정 `ray_order_rejected` 첫 FAIL. |

변이는 입력 변조와 별도로 셌다. 코드 변이 12개 모두 정상본 같은 시험이 먼저 PASS하고, 바꾼 소스에서 예상한 첫 `FAIL <want>`만 CAUGHT로 셌다. 각 정상·변이 stdout과 `summary.json`은 `s2_step4a2/evidence_s2_step4a2/r20261015_17w_a2_final3/`에 있다. Windows fixture의 torch import가 중복 OpenMP 런타임 오류를 낸 첫 예비 실행은 실패로 보존했다. 최종 fixture 자식에만 `KMP_DUPLICATE_LIB_OK=TRUE`를 사용했고 live launcher에는 넣지 않았다.

## 완결 복사와 독립 import

고정 폴더의 top-level 39개 파일 전부를 별도 깨끗한 `%TEMP%/s2_a2_run_clean_50h_7t91/`로 복사했다. `SHA256SUMS.txt`와 복사본 해시가 전부 일치했다. `python -I -B`에서 원래 작업 폴더를 `PYTHONPATH`에서 제외한 채 필수 Python 모듈 22개를 모두 복사본 경로에서 import했다. `frozen_clean_import.log`와 `summary.json`이 이 결과를 기록한다. 이것은 import 가능성 시험이며 Isaac 생성·실행 시험은 아니다.

## 첫 정보 수집의 한계와 보류 항목

- 실제 registry override, cfg serialization, RayCaster hook, 8환경 배정, reset·고정 자세, 256행, 실제 mesh/충돌체/숨은 plane, Kit renderer 물리 선택, driver 버전은 미확인이다. `s2_mesh_probe_a2.py`는 가능한 prim/cache와 USD vertex/face/transform hash 및 오류를 먼저 모으지만 collision agreement를 판정하지 않는다. 진단 메타의 `terrain_assignment_verified`, `mesh_collision_verified`, `fixed_pose_verified`는 의도적으로 false다. 실제 0단계 PASS가 아니다.
- 기존 USD lock과 동일한 파일·byte 0 규약을 코드에 연결했다. 이 CPU 작업에서 lock을 획득하지 않았고 기존 slot/guard도 수정하지 않았다. 실제 참여자 호환, 변환 발생 여부와 변환 경로, 격리 USD root 외부의 Kit 임시 출력은 미확인이다. 기동 코드는 승인된 asset 경로와 최종 cfg 경로를 대조한다. 예기치 않은 변환을 완전히 추적하는 accessor는 아직 없다.
- 감독기 자체 hang을 끊는 독립 watchdog은 없다. **참석자가 터미널을 유지하는 한 번의 관찰**에만 해당하며 무인 기동·후속 학습은 이 묶음으로 허용하지 않는다. 실제 Windows 후손 강제 종료와 감독기 crash 뒤 lease 경쟁도 미확인이다.
- 기동 직전 VRAM/디스크·경쟁 Isaac·예약·마감·장치 매핑은 worker가 재지 않았다. 가짜 meter/provider 결과를 실제 호스트 여유라고 전하지 않는다. `prelaunch`의 GO만으로 학습 PASS를 만들지 않는다.

## lead가 동결할 값과 사용 순서

| 승인 입력 | ASTRA 17w의 출발 권고 · 현재 상태 |
|---|---|
| 장치 | GPU 0 후보 UUID `GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b`, bus `41:00.0`. 실제 UUID/index/bus/torch/Kit 대조 필요. GPU 1 제외. UNDECIDED. |
| 시간·범위 | 8 env, 256 step, 16 warmup, 개입 64/128/192, optimizer 0, 단회 claim, retry 0. `max_wall_s=900`, 절대 마감 2026-10-17 12:00 KST 이전은 권고. 시작/승인 만료/남은 시간 동결 필요. UNDECIDED. |
| 자원 | 초기 free VRAM ≥8 GiB, 실행 중 <2 GiB면 HOLD, 초기 free disk ≥2 GiB, 출력 상한 1 GiB는 권고값. 실제 사전·실행 중 측정 필요. UNDECIDED. |
| 입력·경로 | python/criteria/parent/asset/hook와 최종 cfg, 23 필수 번들 파일 해시, 새 out/USD/log/status/STOP/lease/claim 경로, 동일 host lock, 담당자/by·승인 ID·digest·expires. 모두 실행 전 lead가 동결. UNDECIDED. |

lead는 최종 고정 폴더의 `s2_stage0_prelaunch.py --manifest <manifest.json> --approval <approval.json>`을 먼저 실행해 `prelaunch_report_path`의 GO와 실제 측정·경쟁 부재를 되읽는다. 같은 manifest·approval로 `s2_zero_supervisor.py --manifest ... --approval ...`을 **참석한 터미널**에서 한 번 실행한다. stdout 로그, status, Job family, STOP/마감, receipt 및 부분 raw를 관찰한다. 실행 전 승인 digest가 바뀌면 새 attempt와 승인으로만 다시 시작한다. 어느 결과도 자동 학습 단계로 잇지 않는다.

## 최종 고정 폴더 전체 SHA-256

다음은 `s2_step4a2_frozen/SHA256SUMS.txt`의 전체 목록이다. 이 파일 자체는 자기 해시 대상에서 제외했다.

```text
475d17c73e8d1b21cf1d84a2664faed1e74aaa8b72440b9e767ab5f02f70e426  run_all_s2_step4a.py
1a4196d01bac99ed382f92384546f9c22e03e23cba8c9235d25fc726105c8239  run_all_s2_step4a2.py
11c2f4a71b66c30b8011cc6f566aa2bfaef1cc7d80b6f322b8280946994f7621  s2_capture_journal_a2.py
a052829950b13ab721dcbf138f573af74e6681fac26a7291447ed459abbab1d4  s2_connect_check_17v.py
3275b7e1e49a3c96f04fb231010e06c9a8e3fe1d18e9162e54279e30d5c88a14  s2_connect_diag_17v.py
a6de36474ecb6439ceb933a1728ddfe38671896f6c5bd73a93a172fde3dcaab1  s2_device_binding_a2.py
ebac0f1e2225959da1cacf0fc63aeef6a441e9fd5a08c0d11b7a899fdec496a7  s2_env_adapter_17v.py
ab4c626f2403605ca7ef1393ff66243f859666050035dc4385eb0399e0fc889a  s2_env_config_17v.py
0c258a6101bf6c7804967b99e307e42d3032a7d2387cb09c75c695ff86db1ac2  s2_job_owner.py
9a4a38bfbcc530e8e8f28b7ecbf1c2f4ecaeae3dcd9b217ae8fe73f1bf7aac07  s2_known_scene_a2.py
cf05528619052c73facba9268cc8823156f3106d9ce65ddacf16be30961f348b  s2_map_obs.py
4ba3eab29d671290cf169089b99b5cb7efd3fd015cdb7da2b06e778355004eda  s2_mesh_probe_a2.py
7ffe1d2ba6b77fb538b8cc087ed957d5878f2ffec93161b25d87d4e4d12d691b  s2_packet_17v.py
01e57d10843c086fd78b026fa579d78224f10de44ae210edd8829b590257308d  s2_policy.py
bdeef4fb0167f01bdb33c9f6f595caf533226ade646e819f2988fbc3901ab8df  s2_ppo_17v.py
4acf6fc6aa9c76ba2cd6feea376a973c71c7d7630187fea540c5aa2732fd9add  s2_resource_lease.py
7d1158df2923dffe72436f43b5e4673167ced611afec4912ccaef782035b4ddc  s2_runner_17v.py
b3a9c5be54e4e16856249c2426d39640f450b18778e24e979fc1a1f1d18a4296  s2_scene_answer_a2.json
5bca01b9f4755299d45d1c47e98d22aa06212243fc796c9e36da25c4c654fe02  s2_sensor_tracker_17v.py
1a0629d09789b77ed5047b1467a16df174bc367d8e8a7cbb1f970ca7dd6d123b  s2_stage0_contract_a2.py
8f4caa60f7634c0ad82b54cc2e2b7ed0cc103f9b564ad2435249f9fba1e12b59  s2_stage0_prelaunch.py
29de9914707bb463baef3c449bfed873b3bb9d134efda86fac041eb9422db1d4  s2_stage0_resources_a2.py
296cfcda1ca2d7ed4c4122878c8ef344fde836c99d18e2950bbdbe899a2f144e  s2_stage_gate_17v.py
04db8a09f090bea00097bac6f5bb262d6d9ac0c2ffe81cfa3d38e5f3bf6c9bca  s2_terrain_overlay_17v.py
5eb793ed435f27a6582acdf4bc4e41f9f023383e6253277229a481770ceced58  s2_zero_supervisor.py
d0bd4d733a248c9a76b90223c53c9d608e0f32899f888e1788ef1a62f2f794da  test_s2_17v_core.py
15db62677113a8b24948e3287e168c8057941c6bf00fc76509371beeb342aa52  test_s2_a2_mutants.py
be3b4ca19ee88acaec5f7065e018a73de5b27e31eaf565eccea06cc350dd19af  test_s2_capture_journal_a2.py
a844cdeb9c110d67fc741c9690bea28f058c6c8ba9e9d7f2ad0eaecb9f412070  test_s2_connect_17v.py
9bd20379f430ac52171a4602b90b2101d866db3e3c689b4c0335210a8eb3b4a8  test_s2_connect_a2.py
bda2b106b728591b54a32c936db2e10b10e56c3dbab2baaa3e3457a45cd133f4  test_s2_device_binding_a2.py
a767b23ef29b2c7a29b7def10a678c8fbf8587197239b66616c99186f259f26c  test_s2_job_object_os.py
bd7cbe5b05dd98f06724fc21444eddafc5272a64a8b3a2aca7530e7be0c6618c  test_s2_job_owner.py
c4acb0281c50c2870d37a9687cf9819a6430b1b52c03401db0b95ad53aafeff7  test_s2_resource_lease.py
ea70efc2e61ab054a261e150b0eed29387b536e1f9a83a051229ba55bbdd6ad3  test_s2_scene_a2.py
05a3536e3396b661323ce0ca09202270286723aea399576a11f37ff7a29d457b  test_s2_sensor_tracker_17v.py
3c8dc6a3e48ef4044108203a1cd7a54160b2caf360210e754893376a02a473d7  test_s2_stage0_contract_a2.py
d103e6caf223e766e329a4cb788a1f28e6fbd5063dcfe4104c4c0d8cc2eaa88d  test_s2_step4_mutants.py
75bbd6e59126645e190cddb0f0a523826b172caa6b5dab7ef70a609d5e7149c8  test_s2_zero_supervisor.py
```
