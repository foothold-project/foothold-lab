판정: 현재 step5의 실제 기동은 보류하며, 장치 결박과 USD 격리 결함을 닫고 별도 plumbing 계약을 구현·검증한 뒤에만 0단계 PASS 전 참석 단회를 검토할 수 있다.

> 분류: A/정책학습 · 독립 검증
> 작성: ASTRA · 2026-10-15 18:10 KST
> 근거: TASK-astra-17ad 전문 · step5 고정 사본과 CPU 원시 로그 · 설치된 PyTorch 및 실제 1043 기동 소스 · 독립 CPU 재현
> 요지: 53 PASS 기록은 실제 기동 증명이 아니다. 장치 확인의 재현 가능한 실패, USD 격리 누락, 시험 의존 파일 누락을 확인했고 배관 단회의 합격 범위를 한정한다.
> 상태: 현재 기동 HOLD · 계약 방향 조건부 수용 · step6 구현 및 GPU/Isaac 실측 미확인

# ASTRA 17ad · B 학습 진입과 plumbing 계약

이하 `B5/`는 `night-tools-20261013/s2_step5/`다. B 번들과 실험 arm B를 구분한다. 수정 중인 step6는 이번 검증 대상이 아니다. GPU·Isaac·실제 slot·기존 코드·원자료·프로세스를 건드리지 않았다. CPU 시험은 `isaac311-moects/python.exe -B`, `CUDA_VISIBLE_DEVICES=-1`, 임시 폴더에서 수행했다.

## 1. CPU 증거와 실제 진입의 공백

### 직접 대조한 범위

| 대상 | 확인 결과 | 해석 한계 |
|---|---|---|
| B5 `SHA256SUMS.txt` | 55/55 일치, 누락·불일치 0. 목록 자체 SHA `b8f0d3d28ee26e25a021278db646914f15a003458b5cafac006603a289930cc3` | 이 바이트에 대한 판정 |
| lead `evidence_s2_step5/lead_rerun_1602/` | 8개 로그와 summary 대조. 정상 7개 스크립트의 PASS 라벨 53개, 변이 스크립트의 별도 정상 선행 1개, CAUGHT 7/7의 first_FAIL=want | 기록 수는 맞다. 전체 53개를 이번에 재실행했다는 뜻은 아니다 |
| 독립 `test_s2_step5_live.py` | 18 PASS, 종료 0 | owner·meter·lease·프로세스 목록은 대역 |
| 독립 `test_s2_step5_mutants.py` | 정상 선행 통과, 7/7 지정 첫 FAIL 일치 | 실제 변이 자식을 기동한 시험이 아니라 소스 감사 시험 |
| 독립 `test_s2_17v_entry.py` | 종료 1. 9행 `test_s2_step3_entry` import 실패 | 사본의 `../s2_step3` 의존 시험 파일이 없다. lead의 기존 통과 기록을 현 사본에서 그대로 재현하지 못함 |
| 별도 실제 E1+S2PPO CPU 시험 | arm B, FakeS2Env, N=2, rollout=4, epochs=1, minibatches=1, iteration=1. 실제 optimizer 1회, 상태 PASS, 저장 파일 17,941,734 bytes, CUDA 초기화 False | 실제 PPO의 좁은 연결 확인. 센서·물리·GPU·재적재 확인 아님 |

마지막 CPU 시험의 surrogate `1.1548399925231934e-07`, value `5.884485721588135`, entropy `1.5614545345306396`, KL `0.0001201629638671875`는 유한했고 폐기 transition 0이었다. 부모 SHA는 전후 모두 `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8`. 이 시험은 누락된 기존 시험 5개를 대체하거나 53개 전체 통과를 복구하지 않는다.

### 실제 기동 전 닫아야 할 결함

**P1 · 장치 확인 API가 설치판에 없다. 확인됨.**

`s2_device_binding_a2.py:20`은 `torch.cuda.cudart().cudaDeviceGetPCIBusId(...)`를 호출한다. 지정 해석기의 torch는 `2.7.0+cu128`이며 `torch._C._cudart`에 그 속성이 없다. CUDA 가용성·장치 수·현재 장치만 대역으로 통과시키고 cudart 반환값에는 **실제 설치 모듈**을 넣었더니 다음으로 실패했다.

```text
DeviceHold: cudart_bus_unavailable
cause: AttributeError: module 'torch._C._cudart' has no attribute 'cudaDeviceGetPCIBusId'
CUDA initialized: False → False
Isaac/omni import: 없음
```

이는 GPU 실측은 아니지만 호출 API의 비호환은 직접 재현했다. 실제 진입은 `s2_train_entry_17v.py:405~410`에서 Kit 기동 뒤 이 함수를 반드시 부른다. 도달하면 현재 설치판에서 막힌다. 기존에 확인한 UUID 결박 경로 또는 실제 지원되는 장치 조회 API로 연결하고, 정상 매핑·다른 물리 GPU·조회 불가를 시험해야 한다. 예외 무시나 결박 검사 삭제는 수정이 아니다.

**P1 · USD 잠금만 있고 실행별 변환 격리가 없다. 확인됨.**

1043 셸 `night_20261013_cmdr1043_v3.sh:45~49`는 `isaac_slot.py → gpu_guard.py → usd_isolate_run.py → branch_run.py`로 기동한다. B5는 `s2_train_launch.py:88~97`에서 공통 잠금을 잡고 entry를 바로 실행한다. 실행별 USD root 할당·변환 경로 기록·실제 참조 경로 대조가 없다. `RobotLab-Go2-v0`의 Go2는 설치 `robot_lab/assets/unitree.py:127~129`에서 **URDF 변환 cfg**를 쓰므로 A3의 직접 USD 경로와 동일하다고 볼 수 없다.

잠금은 동시 변환을 직렬화할 수 있지만, 실행별 경로 격리나 과거 산출물 재사용 검증을 대신하지 않는다. 잠금을 먼저 해제하고 이미 실행 중인 다른 참여자도 있을 수 있다. B 전용 실제 USD/참조 경로를 새 출력 아래로 고정하고 변환 전후 증거를 남기거나, 검증된 격리 경로를 정확한 해시로 재사용해야 한다. 이것이 없는 상태로 “기동 동등성 확보”라고 쓰면 틀리다.

기동표는 셸이 부르는 `isaac_slot.py` 대신 `isaac_slot_v3.py:459`를 인용한다. 현재 두 파일의 SHA는 각각 `90ae613b…`, `974919b0…`이고 다른 소스다. `usd_isolate_run.py`와 `_v3.py`도 각각 `366a3c13…`, `30dc2ea9…`로 다르다. 현재 읽은 무접미사 파일에는 v2 구현이 있다. **실제 argv가 호출하는 파일과 당시 실행 영수증의 해시**를 기준으로 표를 바로잡아야 한다. 현재 파일을 읽은 사실만으로 과거 실행 당시 바이트까지 확정하지 않는다.

**P2 · CPU 시험 묶음의 의존 파일과 검증 범위를 바로잡아야 한다.**

- 실제 PPO 시험이 외부 `test_s2_step3_entry.py`를 요구한다. 해당 원본과 해시·경로를 묶거나 같은 계약의 자체 fixture를 포함하고 깨끗한 폴더에서 재현해야 한다. 런타임 19개 import 성공은 시험 묶음 재현성과 다른 주장이다.
- 변이의 `h5py_after_kit`/`tensordict_after_kit`은 실제 import를 뒤로 옮긴 것이 아니라 모듈 이름을 `_late`로 바꾼다. `no_job_assign`도 `assign` 문자열을 바꾼 뒤 감사 함수가 이를 찾는 시험이다(`test_s2_step5_mutants.py:15~22, 43~46`). 7/7은 인정하지만 native 적재 순서나 실제 Job 가족 정리의 실행 증거로 승격하면 안 된다.
- 진짜 Isaac 경계인 registry cfg 생성, wrapper 반환의 관측 키·shape·dtype·device, reset/timeout, 센서 갱신 시점, 부모와 입력 호환은 가짜 runner가 통과시키지 못한다. 지도 모듈 6개의 A3와 byte 일치는 직접 확인했지만 cfg·packet·센서 소비 경로가 다르다.
- live packet은 mount를 `(0,0,0)`으로 하드코딩한다(`s2_train_entry_17v.py:136~145`). 현재 학습 cfg의 실제 `_offset`이 0인지 확인하고 그 전제를 기록해야 한다. A3.2의 sensor offset 정정이 B에 자동 적용되는 것은 아니다.

### `RUN_COMPLETE_UNVERIFIED`의 정확한 뜻

현재 의미는 **예정 iteration 수를 완료했다고 자식이 기록했고, 감독기가 종료 0·가족 0·필요 파일 존재/크기와 해시를 확인했다**는 것이다. `test_s2_step5_live.py:79~82`는 checkpoint에 `b"zero"`, `b"two-hundred"`만 써도 이 영수증을 통과한다. 실제 저장물을 load한 증거가 아니다.

`s2_runner_17v.py:274~291`은 checkpoint 저장은 하지만 `resume_supported=False`이고 `load()`를 명시적으로 거절한다. 따라서 환경까지 복원·재개된다는 주장은 틀리다. 별도 새 policy에 가중치를 strict load하여 동일 입력 출력을 비교하는 검증은 가능하다.

`IsaacS2Env.step()`은 조우 목록을 항상 비운다(`s2_train_entry_17v.py:156~157`). 조우 수가 전부 0인 것은 **미계측**이지 조우가 없었다는 결과가 아니다. 상태가 이 문자열이어도 stage0·지도 시간/기하·성능·후속 학습은 통과하지 않는다.

## 2. plumbing 계약: 방향은 맞지만 그대로는 부족하다

iteration 1~2, `checkpoint_interval==updates`, wall 600초 이하, 부모 불변, 새 격리 출력, `plumbing_only=true`, `stage0_passed=false`, 입력 경로 명시, 참석 단회는 수용한다. 다음을 보완한다.

1. **범위를 실행기와 자식이 함께 강제한다.** `stage=plumbing`에서 barrier/resume/증분/200·2000회 실행을 거절하고 범위 밖 argv도 거절한다. 설정 파일만 1~2로 바꾸고 B5 `validated(live=True)`의 200/2000 제한을 우회하는 방식은 안 된다. 실제 시작·완료 iteration, vector step, transition, optimizer step을 따로 기록한다. 정상 완주는 각각 U, U×T, U×T×N, U×epochs×minibatches다. bootstrap·reset용 센서 읽기는 별도로 센다.
2. **결과를 재사용 못 하게 한다.** 파일 접두사·표지는 사람이 읽는 표시다. checkpoint 내용에도 plumbing 상태·manifest 해시·원본 parent 해시를 넣고, 후속 부모 선택은 파일명 검사가 아니라 허용된 E1 내용 해시로 제한한다. 재명명한 plumbing checkpoint도 거절해야 한다.
3. **실제 입력을 기록한다.** `live_raycaster_unverified`는 shape·mask·finite·packet 신선도 등 기존 유효성 검사를 계속 거쳐야 한다. stage0가 HOLD라는 이유로 이 검사를 끄면 안 된다. synthetic은 삽입 지점을 적고 알려진 tensor 해시/정답과 실센서를 읽지 않았다는 사실을 남긴다. synthetic 지도가 실제 Isaac 관측·PPO로 들어간 시험과 FakeS2Env CPU 시험을 구분한다.
4. **최종 cfg를 보존한다.** base cfg 이름뿐 아니라 적용 후 cfg 내용·해시와 상위 학습 cfg 대비 차이를 남긴다. 진단 gravity off, base_contact 제거, root 고정·속도 덮어쓰기 등 진단 개입이 없어야 한다. 실제 센서 mount·관측 shape도 함께 검사한다. 소스에 `disable_gravity=True`라는 문자열이 없는지만 검사하는 것은 불충분하다.
5. **미분과 parameter 변화는 그룹별 의미로 검사한다.** 전역 grad norm 하나는 critic만 갱신되어도 통과한다. actor·critic·map 경로·동결 student encoder를 나누어 pre-clip grad norm, optimizer 포함 여부, 실제 LR, 변경 tensor 수/최대 차이와 finite 여부를 기록한다. 동결 부분은 변화 0이어야 한다. 반대로 모든 그룹의 첫 grad가 0보다 커야 한다는 조건도 틀리다. `s2_policy.py:163~168`의 지도 투영 가중치는 0 초기화라 첫 backward에서 상류 map encoder grad가 0일 수 있다. 비퇴화 known-answer 입력으로 지도 투영의 연결을 확인하고, 변화가 예상되는 부분만 요구한다. 1~2회로 W=50 이후 해제까지 확인했다고 쓰지 않는다.
6. **저장·재적재의 대상을 좁힌다.** 새 policy 객체에 디스크의 가중치를 strict load하고, 보존한 동일 관측·지도 입력에서 deterministic action/value를 비교한다. 허용 오차는 실행 전에 정하고 최대 차이를 남긴다. 저장한 객체를 계속 써서 자기 자신과 비교하면 무효다. optimizer/control 상태도 저장 내용과 대조하되 환경 resume 성공으로 부르지 않는다.
7. **두 arm의 두 번째 실행은 자동 승격이 아니다.** 각자 manifest·claim·출력·상한을 갖는다. 첫 영수증이 단지 `RUN_COMPLETE_UNVERIFIED`인 것만으로 부족하다. 아래 배관 필수 검사 PASS와 가족 정리 완료를 사람이 확인하고, 해당 두 번째 단회까지 팀장에게서 직접 받은 동의가 있어야 한다. 실패 시 다음 arm/재시도 없음.

**작은 N은 허용할 수 있다. 1,024가 배관 증명의 필수값은 아니다.** 예를 들어 N=32 같은 작은 값을 실행 전에 고정하고, 동일 관측·action·센서·PPO 경로를 유지한다. batch/minibatch 나눗셈 및 표본 수 조건을 먼저 검사한다. 실제 지형 배정 표본이 줄어드므로 “gap/stones 각 15%를 모든 실행에서 충분히 경험했다”는 뜻도 아니다. N=1을 특별히 고집할 이유는 없다.

작은 N의 성공은 1,024환경의 VRAM 수용·처리량·분포/조우 커버리지·장시간 수치 안정성·학습 효과를 증명하지 않는다. N을 줄여도 지형 메시 크기가 그대로일 수 있으므로 메모리가 선형 감소한다고 예산을 잡지 않는다. GPU 1의 10.5 GB 점유는 의뢰문 수치이며 현재 직접 측정하지 않았다.

## 3. 첫 실제 배관 시험의 필수 증거와 HOLD

성공 표기는 **`plumbing_checks=PASS`, `stage0_passed=false`, `performance_verified=false`**로 한정한다. 기존 실행 상태 문자열과 기능 검사 판정을 분리한다.

| 필수 | 남겨야 하는 증거 |
|---|---|
| 정확한 실행 | 실행 ID, 동결 코드·manifest·입력 해시, 해석기 및 실제 import된 torch/rsl_rl/Isaac 경로·버전, 부모 전후 SHA, 최종 cfg와 차이, 실제 argv·입력 경로·arm |
| 실제 장치·격리 | 논리 CUDA와 물리 UUID/bus 연결, Kit/PhysX 장치의 관측 여부, 직전·실행 중 가용 VRAM/디스크와 사전 한계, 실제 USD/참조 경로와 변환 기록, 해당 Job·lease 소유권 |
| 실제 데이터 흐름 | wrapper 관측·map·action·reward·done/timeout의 shape/dtype/device, live면 실제 packet generation/timestamp/episode와 offset 전제, 입력·출력 비유한 값 수 |
| 실제 학습 | 예정/완료 iteration·transition·optimizer step, 매 update loss/KL/entropy, 위 그룹별 grad/parameter 변화·freeze·실제 LR, NaN뿐 아니라 Inf도 0 |
| 저장·복원 | 0회와 최종 plumbing checkpoint 해시, strict load 결과, 고정 입력 해시, 새 객체 action/value 최대 차이와 사전 tolerance, 원본 부모 불변 |
| 종료 | 정상 rc와 자식 결과·감독기 영수증 일치, 제한 내 종료, cleanup 이후 Job 가족 수 0, 잠금 해제 확인, 원시 로그와 영수증 해시 |

**HOLD:** 위 필수 증거 누락·대역으로 대체, 잘못된 물리 GPU, USD 경로 미확인/공유, 예상 외 cfg, 기존 packet 검사 실패, discard 발생, 비유한 값, 예정 step 미완료, 필요한 학습 경로 단절, 동결 parameter 변화, 부모 변경, load 불일치, native crash/OOM, STOP/마감 도달, 가족 정리 미확인. 실패를 고쳐 같은 manifest로 자동 재시도하지 않는다. B5 예외 영수증은 finally cleanup보다 먼저 기록되므로(`s2_train_launch.py:138~156`) 최종 정리 확인을 별도로 남겨야 한다.

**선택:** 영상, gradient 분포 그림, 상세 profiler·메모리 곡선. 성능 성공률·지도 효과·지형 조우 개선은 이 시험의 합격 요건으로 넣지 않는다. 조우는 미계측으로 표시한다. 짧은 실행에서 reset이 안 일어났다면 reset 경로는 미실행으로 남기며, 그 확인만을 위해 임의로 iteration을 늘리지 않는다.

## 4. GPU 배정과 4차 수집의 순서

**권고는 4차 GPU 0 수집 종료·가족 정리·lease 해제 확인 후, 같은 GPU 0에서 작은 plumbing 한 arm이다.** 시간 순서의 권고이지 stage0 PASS를 배관 시험의 절대 선행 조건으로 되살리는 것은 아니다. stage0가 기하 검증에서 HOLD여도 별도 synthetic 배관은 가능하다. 반면 native crash·장치 격리·미정리 프로세스·공유 자산 결함이 원인이면 이를 해결하지 않고 다음 일을 띄우면 안 된다.

**원칙적으로 4차 GPU 0과 배관 GPU 1의 병렬은 목적이 다른 두 진단이므로 일률 금지는 아니다. 현재 B5로는 불가하다.** `gpu_index==0`, `CUDA_VISIBLE_DEVICES=0`, `meter.probe(0)`가 모두 고정돼 있다. GPU 1 문자열만 바꿔서는 물리 GPU·NVML·Kit 결박이 일치하지 않는다. 공통 USD 잠금도 자식 전체 수명 동안 잡으며, 경쟁 검사는 GPU 구분 없이 kit/isaac-sim 이름을 찾는다. 반대로 Python에 내장된 Kit를 이 이름 검사만으로 모두 찾는다는 보장도 없다.

병렬을 원하면 별도 물리 장치 결박, 서로 다른 출력·USD root, 두 참여자의 동일 lease 규약, 공통 잠금의 정확한 보유/해제 범위, 호스트 RAM/디스크/데스크톱 여유와 두 실행 관찰 가능성을 먼저 검증해야 한다. lease root가 실행마다 달라 같은 UUID를 서로 못 보는 구성은 허용하지 않는다. 이는 현재 GPU 0 단회의 사소한 옵션 변경이 아니다. GPU를 채우기 위한 병렬화 때문에 이 범위를 지금 추가할 필요는 없다.

## 5. 추가 ASTRA 판정이 필요한 범위

**현재 제출물만으로 lead가 바로 기동해도 된다는 위임은 하지 않는다.** 새 step6는 아직 검토하지 않았고, 이번에 닫아야 할 장치·USD·합격 판정 경로가 있다. 최초 plumbing에 대해서는 **완성된 step6의 변경분과 위 결함 수정, CPU 정상/반례 실행 증거를 한 묶음으로 좁게 1회 확인**하는 것이 필요하다. 닫힌 A3나 전체 S2 설계를 다시 읽는 검증은 요구하지 않는다.

그 뒤 다음 범위는 **lead 검증 기록 + 팀장의 해당 단회 직접 동의**로 처리할 수 있다.

- 검토된 참석 GPU 0 순차 경로 안에서 새 attempt/출력/마감, 사전 허용된 N·iteration 1/2·arm을 고르는 것. 승인된 두 arm 진단의 두 번째 실행도 필수 배관 검사와 정리 완료를 확인한다.
- 판정 의미를 바꾸지 않는 로그·직렬화·명시적 API accessor 호환 수정. 원인, 바뀐 파일, 정상 소스 통과, 변이의 지정 실패 위치, 실제 해석기·원시 출력·해시를 보존한다. skip/hold를 pass로 세지 않는다.
- 실행 바이트를 새로 동결하고 기존 상한·격리·입력 검사·부모 불변·후속 사용 금지를 유지한다. CPU 시험 의존 파일까지 동결한다.

**별도 검토 대상:** GPU 1 병렬화, Job/잠금/마감/권한 변경, 새로운 USD 격리 방식, native crash 우회, 입력 유효성 검사 완화, sensor/map 수학이나 cfg의 의미 변경, 합격 조건 변경, iteration 확대, 학습·평가·무인 승격. ASTRA 재검 횟수가 목적은 아니며, 범위가 같은 제한 실행을 매번 새 의뢰로 묶지는 않는다.

17z 무인 보류는 유지한다. 이 문서는 실행 승인 JSON이나 팀장의 직접 동의를 대신하지 않는다.
