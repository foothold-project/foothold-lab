> 분류: A/정책학습 · Codex Worker 작업서 (sol) · S2 B 번들 step7: ASTRA 17ad 결함 수정과 plumbing 보강 (CPU 만)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 18:13
> 근거: `VERIFY-astra-17ad.md` 전문 (특히 1절 P1 · P2, 2절 1~7, 3절, 4절) · 저장소 사본 `night-tools-20261013/s2_step6/` (lead 재실행 기존 53 + 새 42 PASS, 변이 7/7 + 11/11) · 0단계 A3.2 의 실제 Kit 기동 기록 `s2_stage0_first_collection/attempt3_20261015_1506/out/device_binding.json`
> 요지: ASTRA 17ad 는 step5 의 실제 기동을 보류했다. 장치 결박 API 가 설치 torch 에 없고(재현됨), 실행별 USD 격리가 없고, 시험 묶음 의존 파일이 빠졌다. plumbing 계약은 방향이 맞지만 일곱 곳을 보강하라고 했다. 이것을 모두 닫은 step7 을 CPU 에서 만들면 ASTRA 가 「완성된 step6/7 변경분 + 결함 수정 + CPU 증거」 한 묶음을 1회 좁게 확인한다
> 상태: 작업 지시 (GPU · Isaac 기동 금지 · 승인 json 은 ASTRA/lead 가 낸다 · 팀장 새 동의 필요)

# sol 작업서: B step7

## 0. 지킬 것

- GPU · Isaac · 실제 `_eval` 슬롯 · 기존 코드 · 원자료를 **건드리지 않는다.** `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`. 새 작업 사본 `codexE/s2_step7/` (`s2_step6/` 와 저장소는 고치지 않는다). 정상 시험을 먼저 통과시킨 뒤 변이가 지정 첫 FAIL 라벨과 같을 때만 CAUGHT. em dash 금지. 첫 실패도 보고서에 그대로.
- 팀장은 실험이 안 도는 시간을 가장 큰 손해로 본다. 완벽한 설계보다 **ASTRA 가 한 번에 통과시킬 닫힌 묶음**이 먼저다. 단, 검증을 빼지 않는다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.

## 1. 닫을 결함 (VERIFY-astra-17ad.md 줄 그대로)

**A. 장치 결박 (P1, 재현됨).** 사본의 `s2_device_binding_a2.py:20` 은 `torch.cuda.cudart().cudaDeviceGetPCIBusId(...)` 를 부른다. 설치 torch 2.7.0+cu128 의 `torch._C._cudart` 에는 그 속성이 없어 `DeviceHold: cudart_bus_unavailable` 로 막힌다. 반면 **0단계 A3 번들의 `s2_step4a3/s2_device_binding_a2.py` 는 실제 Kit 에서 두 번 통과했다**(attempt 2 · 3 의 `device_binding.json`: `torch_uuid` 는 `str(props.uuid)` 로 읽고 Kit `/physics/cudaDevice` `/renderer/activeGpu` 를 읽어 0 과 비교). 두 파일의 차이를 읽고, B 의 결박을 **A3 의 검증된 방식**으로 바꾼다(예외 무시나 검사 삭제는 수정이 아니다). 시험: 정상 매핑 · 다른 물리 GPU UUID · 조회 불가(예: 속성 없음) 각각 `DeviceHold`. 실제 설치 torch 객체의 속성 존재 여부를 시험에 넣되 CUDA 초기화는 하지 않는다.

**B. 실행별 USD 격리 (P1).** B5 `s2_train_launch.py:88-97` 은 공통 잠금만 잡고 entry 를 바로 실행한다. 1043 셸은 `isaac_slot.py → gpu_guard.py → usd_isolate_run.py → branch_run.py` 로 기동하고 0단계 A3 는 `usd_isolate_run_v3.py` 래퍼(`C:/isaac/ext/go2_rl_robotlab/_eval/usd_isolate_run_v3.py`, SHA `30dc2ea930f400948474b11c648aa389ff495d2a1bd764b4b9b984b931d11efb`)와 `FOOTHOLD_USD_ROOT` 를 쓴다. B 도 **실행별 USD root 를 새 출력 아래로 고정**하고 변환 전후 기록(`usd_isolate_state.json` 에 해당하는 것)과 실제 참조 경로 대조를 영수증에 남긴다. 참고: `RobotLab-Go2-v0` 의 Go2 는 설치 `robot_lab/assets/unitree.py:127-129` 에서 URDF 변환 cfg 를 쓴다(ASTRA). 변환이 필요한지, 필요하면 `expected_conversions` 를 어떻게 정할지 소스로 확인하고 모르는 것은 「미확인」 으로 적는다. A3 의 `s2_zero_supervisor.py` 가 이 일을 하는 방식(`FOOTHOLD_USD_ROOT` 환경, 래퍼 argv)을 먼저 읽고 같은 계약으로 간다.

**C. 기동 동등성 표 바로잡기.** 표가 `isaac_slot_v3.py:459` 를 인용하는데 1043 셸이 실제로 부르는 것은 `isaac_slot.py` 이다(SHA `90ae613b…` 대 `974919b0…`, `usd_isolate_run.py` `366a3c13…` 대 `_v3.py` `30dc2ea9…`). **셸의 실제 argv 가 부르는 파일과 당시 실행 영수증의 해시**를 기준으로 표를 다시 쓴다. 영수증이 없으면 「현재 파일을 읽은 사실이며 당시 바이트는 미확인」 이라고 쓴다.

**D. 시험 묶음 재현성 (P2).** 사본의 `test_s2_17v_entry.py:9` 가 외부 `test_s2_step3_entry.py`(`../s2_step3`) 를 import 해서 사본 폴더에서 종료 1 이다. 그 원본의 해시 · 경로를 묶거나 같은 계약의 자체 fixture 로 바꾸고, **깨끗한 폴더(`-I`)에서 전체 시험 묶음이 재현**됨을 보인다. 런타임 import 성공과 시험 묶음 재현은 다른 주장이다.

**E. 센서 mount 하드코딩.** `s2_train_entry_17v.py:136-145` 가 mount 를 `(0,0,0)` 으로 박는다. 0단계 A3.2 에서 확인한 사실: RayCaster 의 `cfg.offset.pos` 는 **광선 시작점**(+20 m)이고 `pos_w` 는 센서 view 의 `_offset`(`scanner._offset`) 만 적용된다. B 의 학습 cfg 에서 실제 `_offset` 을 런타임에 읽어(모든 env 같음 · 회전 단위 · drift 0) 기록하고, 0 이 아니거나 읽을 수 없으면 거절하도록 바꾼다(`s2_step4a3/s2_connect_diag_17v.py` 의 `mount_offset()` 참고).

**F. 변이/시험의 정직성.** 기존 변이(`h5py_after_kit` 등)는 이름을 `_late` 로 바꾸는 소스 감사라서 native 적재 순서나 실제 Job 가족 정리의 실행 증거가 아니다. 보고서에 그렇게 적고, 가능하면 실제 import 순서를 CPU 에서 실행해 확인하는 시험을 하나 더 둔다. `test_s2_step5_live.py:79-82` 는 checkpoint 에 `b"zero"` 만 써도 `RUN_COMPLETE_UNVERIFIED` 영수증을 통과한다 → 실제 저장물을 load 해서 확인하는 시험으로 바꾸거나 이 영수증 문구의 의미를 「자식 종료 0 · 가족 0 · 필요 파일 존재/크기/해시」 로 한정해 문서에 박는다. `IsaacS2Env.step()` 이 조우 목록을 항상 비우므로 조우 수는 「미계측」 으로 표기한다(0 이라고 쓰지 않는다).

## 2. plumbing 보강 (VERIFY-astra-17ad.md 2절)

1. **실행기와 자식이 함께 범위 강제.** `stage=plumbing` 에서 barrier · resume · 증분 · 200/2000 회와 범위 밖 argv 거절. 설정 파일만 1~2 로 바꾸고 `validated(live=True)` 의 200/2000 제한을 우회하지 않는다. 시작/완료 iteration, vector step, transition, optimizer step 을 따로 기록: 정상 완주는 U, U×T, U×T×N, U×epochs×minibatches. bootstrap · reset 용 센서 읽기는 따로 센다.
2. **결과 재사용 방지.** checkpoint **내용**에 plumbing 상태 · manifest 해시 · 원본 parent 해시를 넣고, 후속 부모 선택은 파일명이 아니라 허용된 E1 내용 해시(`c8951b79…`)로 제한한다. 파일명을 바꾼 plumbing checkpoint 도 거절.
3. **실제 입력 기록.** `live_raycaster_unverified` 는 shape · mask · finite · packet 신선도 등 기존 유효성 검사를 계속 거친다(stage0 HOLD 를 이유로 끄지 않는다). `synthetic_known_answer` 는 삽입 지점, 알려진 tensor 해시/정답, 실센서를 읽지 않았다는 사실을 남긴다. 합성 지도가 실제 Isaac 관측 · PPO 로 들어간 시험과 FakeS2Env CPU 시험을 구분해 표기.
4. **최종 cfg 보존.** base cfg 이름만이 아니라 적용 후 cfg 내용 · 해시, 상위 학습 cfg 대비 차이를 남긴다. 진단 개입(무중력 · base_contact 제거 · root 고정 · 속도 덮어쓰기)이 없어야 한다. 실제 센서 mount · 관측 shape 검사. 소스 문자열에 `disable_gravity=True` 가 없는지만 보는 검사는 불충분 → **실제 최종 cfg 값**을 검사.
5. **그룹별 미분 · 변화 검사.** 전역 grad norm 하나는 critic 만 갱신되어도 통과한다. actor · critic · map 경로 · 동결 student encoder 를 나누어 pre-clip grad norm, optimizer 포함 여부, 실제 LR, 변경 tensor 수 · 최대 차이 · finite 를 기록. 동결 부분은 변화 0. 반대로 「모든 그룹의 첫 grad 가 0 보다 커야 한다」 는 조건은 틀리다: `s2_policy.py:163-168` 의 지도 투영 가중치는 0 초기화라 첫 backward 에서 상류 map encoder grad 가 0 일 수 있다 → **비퇴화 known-answer 입력**으로 지도 투영의 연결을 확인하고 변화가 예상되는 부분만 요구. 1~2회로 W=50 이후 해제까지 확인했다고 쓰지 않는다.
6. **저장 · 재적재.** 새 policy 객체에 디스크의 가중치를 strict load 하고, 보존한 동일 관측 · 지도 입력에서 deterministic action/value 를 비교(허용 오차는 실행 전에 상수로 고정, 최대 차이를 남김). 저장한 객체를 계속 써서 자기 자신과 비교하면 무효. optimizer/control 상태도 저장 내용과 대조하되 환경 resume 성공이라 부르지 않는다.
7. **두 arm 의 두 번째 실행.** 자동 승격이 아니다. 각자 manifest · claim · 출력 · 상한. 첫 영수증의 `RUN_COMPLETE_UNVERIFIED` 만으로 부족 → 배관 필수 검사 PASS 와 가족 정리 완료를 사람이 확인하고 **두 번째 단회에 팀장의 직접 동의**(동의 파일) 필요. 실패 시 다음 arm/재시도 없음.
8. **작은 N 허용.** 1,024 가 필수가 아니다. N 은 실행 전에 상수로 고정(예: 32), batch/minibatch 나눗셈 · 표본 수 조건을 먼저 검사. 작은 N 의 성공은 VRAM 수용 · 처리량 · 조우 커버리지 · 장시간 안정성 · 학습 효과를 증명하지 않는다고 영수증 문구에 박는다.
9. **성공 표기.** 성공은 `plumbing_checks=PASS`, `stage0_passed=false`, `performance_verified=false` 로만. 기존 실행 상태 문자열과 기능 검사 판정을 분리. 영수증 필수 항목은 VERIFY-astra-17ad.md 3절 표(정확한 실행 / 실제 장치 · 격리 / 실제 데이터 흐름 / 실제 학습 / 저장 · 복원 / 종료)를 줄 그대로 채운다. HOLD 조건도 그 목록 그대로(필수 증거 누락 · 대역 대체 · 잘못된 물리 GPU · USD 경로 미확인/공유 · 예상 외 cfg · packet 검사 실패 · discard · 비유한 값(NaN 뿐 아니라 Inf) · 예정 step 미완료 · 필요한 학습 경로 단절 · 동결 parameter 변화 · 부모 변경 · load 불일치 · native crash/OOM · STOP/마감 · 가족 정리 미확인). `s2_train_launch.py:138-156` 의 예외 영수증이 finally cleanup 보다 먼저 쓰이므로 **최종 정리 확인을 별도로** 남긴다.

## 3. 하지 말 것

- GPU 1 병렬화, Job/잠금/마감/권한 변경, 새 USD 격리 방식의 발명(A3 의 검증된 방식을 쓴다), 입력 유효성 검사 완화, sensor/map 수학 · cfg 의미 변경, 합격 조건 변경, iteration 확대, 학습 · 평가 · 무인 승격. ASTRA 가 별도 검토 대상이라고 한 것들이다.
- 단 `gpu_index==0`, `CUDA_VISIBLE_DEVICES=0`, `meter.probe(0)` 고정은 그대로 둔다(GPU 0 순차 경로만 검토됨).

## 4. 끝나면

`REPORT-s2-step7.md` (정상 PASS 수 · 변이 CAUGHT/전체 · 실제 설치 torch 로 확인한 사실과 대역의 구분 · 바뀐 파일 · 처음 실패 · 미확인), `S2-STEP7-SHA256SUMS.txt`, #550 댓글 초안(미게시). lead 가 재실행해서 ASTRA 에 넘긴다. 0단계 A3.2 · 4차 수집 · A4 무인은 이 작업서의 범위 밖(lead 가 한다).
