현재 step7 바이트로 첫 GPU 0 참석 plumbing은 보류하며, CUDA 재적재의 optimizer 비교 결함과 합성 입력 증거 불일치를 좁게 고친 뒤 아래 CPU 확인·실행 동결·팀장의 단회 직접 동의 조건으로 진행할 수 있다.

> 분류: A/정책학습 · 독립 검증
> 작성: 오흥재 (ASTRA 세션 작성) · 2026-10-15 19:31
> 근거: TASK-astra-17ae 전문 · VERIFY-astra-17ad · s2_step7 고정 사본·원시 시험 로그 · 설치 PyTorch/IsaacLab 소스 · 독립 CPU 시험
> 요지: 기존 결함은 상당 부분 닫혔으나 CPU 통과가 가린 CUDA 상태 비교 오류가 남았다. 합성 지도와 실센서·성능 검증도 구분해야 한다.
> 상태: 현 바이트 기동 보류 · 제한 수정 뒤 참석 단회 조건 제시 · GPU/Isaac 미실행

# ASTRA 17ae · B step7 변경분 확인

경로의 기준은 이 문서와 같은 폴더다. 이하 B7은 `night-tools-20261013/s2_step7/`이다. 닫힌 A3와 전체 S2 설계는 재심하지 않았다. 기존 파일·실행 출력·잠금은 수정하지 않았고, 보고서만 새로 썼다. CPU 시험은 별도 임시 사본/메모리에서 실행했다.

## 1. 기존 지적의 종결 여부와 새 결함

### 먼저 바로잡을 증거 수와 범위

| 항목 | 독립 확인 결과 |
|---|---|
| 대상 바이트 | B7 `SHA256SUMS.txt`의 99/99 파일 일치. 목록 SHA256 `868b6d2780b468454838f0cfdaa1a6df68afa9a4a22205a8ef1dfa884b38ac11` |
| lead 원시 기록 | `lead_rerun_1908/summary.json`의 정상 단계 24파일·271 PASS, 변이 단계 7파일·정상 선행 검사 2 PASS. 합계 31파일·273 PASS 라벨, 기록된 종료 코드는 전부 0 |
| 변이 기록 | 54 CAUGHT의 실제 첫 실패를 로그와 시험의 지정 want에 대조해 54/54 일치. 전체 54개를 이번에 재실행했다는 뜻은 아니다 |
| 이번 독립 실행 | `test_s2_17v_entry.py` 5, `test_s2_step6_contract.py` 27, `test_s2_step6_execution.py` 2, `test_s2_step6_proof.py` 16, `test_s2_step7.py` 18. 합계 68 PASS, 다섯 스크립트 종료 0 |
| 이번 독립 변이 실행 | `test_s2_step7_mutants.py`의 UUID·Kit 관측 누락·mount·USD 참조 4/4 지정 첫 실패 일치, 각 정상 선행 검사 통과 |
| 시험 환경 | `isaac311-moects/python.exe -I -B`, `CUDA_VISIBLE_DEVICES=-1`. 실제 E1+PPO CPU 시험은 FakeS2Env를 사용. Kit·물리·GPU 실행 증거가 아니다 |

**의뢰문의 “sol 본문 271이 틀렸다”는 정정이 오히려 틀렸다.** sol 보고서는 정상 단계 271이라고 썼고 그 수는 맞다. 273은 변이 단계의 정상 선행 검사 2개까지 더한 값이다. 또 제출 사본의 `evidence_s2_step7/final2/`에는 로그 두 개만 있고 `summary.json`이 없다. sol final2와 lead 전체 결과가 같다는 주장은 이 사본으로는 **미확인**이다. lead의 완전한 로그와 위 독립 시험은 따로 유효하다.

“지도 계산 모듈 6개가 A3와 바이트 동일”도 틀렸다. adapter·map_obs·sensor_tracker·policy·terrain_overlay는 동일하나 `s2_ppo_17v.py`는 다르다. 차이는 loss·그룹별 pre-clip grad·norm 기록과 비유한 grad 거절 추가다. 현재 차이를 학습 수식 변경으로 단정하지는 않지만 **5/6 동일**이라고 써야 한다.

### 17ad 항목별 판정

| 항목 | 판정과 근거 |
|---|---|
| P1 장치 API | **기존 결함 닫힘, 실기 결박 미확인.** `s2_device_binding_a2.py:25~53`이 지원되지 않는 cudart API를 버리고 UUID를 비교한다. 필수 Kit renderer/physics 관측값 누락·0 이외 값도 거절한다. UUID raw 값도 남긴다 |
| P1 USD 격리 | **기존 누락 닫힘, 실제 변환 미확인.** `s2_train_contract.py:43~44`가 해시 고정 v3 wrapper를 argv에 넣고 실행별 root를 전달한다. `s2_train_launch.py:26~50`이 변환 기록·할당 폴더·생성 파일·실제 참조를 대조한다 |
| 기동표 | **문구 정정 닫힘.** `S2-STEP5-LAUNCH-PARITY.md`가 실제 무접미사 파일을 인용하고 과거 실행 바이트를 미확인으로 제한한다. “역할 비교”이지 같은 구현·동일 실기 동작 증명이 아니다 |
| P2 시험 의존 | **지정 결함 닫힘.** step2/step3 fixture가 포함됐고 독립 깨끗한 사본의 entry·실제 CPU PPO 시험도 통과했다 |
| mount | **하드코딩 결함 닫힘.** `s2_train_entry_17v.py:52~66,175`가 `_offset`을 읽고 shape·finite·env 간 동일성·단위 회전을 확인한다. 추가로 translation이 정확히 0이어야 한다. 비영점 mount를 지원한다는 뜻은 아니다 |
| 변이·영수증 표현 | 소스 문자열 변이가 native 적재/Job 종료 증거가 아니라는 정정은 맞다. `s2_train_launch.py:235~274`가 cleanup 뒤 영수증·해시를 다시 쓰는 것도 개선됐다. 실제 가족 종료는 여전히 5절의 독립 확인이 필요하다 |
| plumbing ① 범위·횟수 | 실행기 계약 `s2_train_contract.py:102~118`과 자식 `s2_train_entry_17v.py:415~417`이 별도로 제한한다. 반복·step 계수와 작은 N 조건도 생겼다 |
| plumbing ② 재사용 금지 | 자식 checkpoint 내부 표지·manifest·부모 SHA, 원래 E1 내용 SHA 제한이 구현됐다. 파일명만 바꾸어 다음 부모로 쓰는 것을 허용하지 않는다 |
| plumbing ③ 실제 입력 | 삽입 지점은 존재하나 아래 **P2**가 남는다. synthetic 결과를 live 센서 검증으로 부를 수 없다 |
| plumbing ④ cfg | 최종 cfg·해시·부모 대비 diff와 진단 개입 거절이 구현됐다. 실제 registry cfg와 wrapper를 통과했다는 증거는 아직 없다 |
| plumbing ⑤ 그룹별 변화 | actor·critic·map encoder/projection·동결 encoder의 grad/LR/변화 기록이 구현됐다. A에서 지도 변화, B 첫 backward에서 상류 encoder의 양수 grad를 강요하지 않는 점도 맞다 |
| plumbing ⑥ 재적재 | 새 policy strict load와 action/value 비교는 CPU에서 통과했으나 아래 **P1** 때문에 CUDA 경로는 닫히지 않았다 |
| plumbing ⑦ 두 번째 arm | `s2_plumbing.py:154~193`이 첫 PASS·같은 GPU·부모·가족 정리·다른 출력·사람 검토·두 번째 직접 동의를 요구한다. 단순 완료 문자열만으로 넘어가지 않는다 |

### P1 · CUDA 재적재 뒤 optimizer 비교가 장치 불일치로 실패한다

**확인됨:** `s2_policy.py:598`은 기본 Adam을 만든다. 설치판 torch는 `2.7.0+cu128`이고, `torch/optim/adam.py:163~173`은 `capturable=False`, `fused` 비활성일 때 parameter가 CUDA여도 `state['step']`을 CPU에 둔다. `s2_runner_17v.py:285~286`은 그 optimizer 상태를 그대로 저장한다.

그런데 `s2_plumbing.py:126`의 `torch.load(..., map_location=device)`는 저장된 CPU step까지 policy의 CUDA 장치로 옮긴다. 이어 `:141~143`이 원래 optimizer 상태와 대조하고, `:94`는 `torch.equal`을 직접 호출한다. PyTorch 2.7.0 공식 CUDA 구현은 두 tensor의 장치가 다르면 예외를 낸다. [공식 cuda_equal 구현](https://github.com/pytorch/pytorch/blob/v2.7.0/aten/src/ATen/native/cuda/Equal.cpp#L18)

따라서 **다른 선행 검사를 통과해 이 지점에 도달하면**, 정상 CUDA 학습도 roundtrip에서 실패한다는 소스 근거가 있다. 실제 GPU에서 재현했다는 뜻은 아니다. 독립 CPU 소시험에서도 실제 Adam step의 원래 장치는 cpu였고, `map_location='meta'`로 읽으면 그 step까지 meta로 이동했다. CUDA 초기화는 False, Isaac import는 없었다. CPU끼리의 기존 roundtrip 통과로는 이 오류를 잡을 수 없다.

최소 수정은 저장 optimizer/control과 현재 상태를 **장치와 분리한 내용 비교**로 대조하는 것이다. 예컨대 checkpoint를 CPU로 읽고 tensor를 양쪽 모두 `detach().cpu()`하여 key·shape·dtype·값을 재귀 비교한다. policy는 새 CUDA 객체에 strict load하고 같은 입력 action/value 오차를 계속 측정한다. optimizer 검사를 삭제하거나 device 예외를 PASS로 바꾸면 안 된다. 이 비교를 통과해도 환경 resume 성공은 아니다.

### P2 · 합성 주입값과 별도 정답 검사가 서로 다른 입력이다

`s2_train_entry_17v.py:197~226`은 실제 Isaac 관측을 받은 뒤 추가 actor map용 합성 rays를 만든다. `s2_runner_17v.py:94~123`이 이를 검증하고 `frame['map']`에 넣으므로 삽입 위치 자체는 타당하다. 다만 두 값은 구분해야 한다.

- 실제 합성 경로 `:206`: `hit_z = root_z - 0.25`. map의 offset 0.5를 적용하면 유효 height는 **-0.25**다.
- `s2_plumbing.py:46~59`의 별도 `known_input_probe`: `root_z=1`, `hit_z=0.25`이므로 유효 height는 **+0.25**다. 이것이 자식 `result['known_input']`에 들어간다(`entry:446`).

독립적으로 **실제 IsaacS2Env의 capture 메서드**를 CPU 객체에 붙여, 두 pose·yaw 0/π÷2·episode reset을 시험했다. 실제 scanner의 `data`를 읽으면 즉시 실패하도록 했는데 읽지 않았고, packet·geometry 검사를 통과했다. B는 각 env에서 유효 186개 height -0.25, 첫 ray만 `(height=1, mask=0)`이고 A는 모두 0이었다. 두 env B tensor SHA256은 `f586d7f757413ef2d938efdc842264ba95c6d34b11e8aa7ea2a174d16ac85061`이다. 이 시험은 Kit 없이 메서드를 확인한 것이며 실제 Isaac 주입 완료를 뜻하지 않는다.

**-0.25 자체가 잘못된 지형 수학은 아니다.** 문제는 +0.25 정답 probe와 별도로 남긴 rollout hash를 실제 입력의 정답 대조처럼 읽을 수 있다는 것이다. 현재는 이 둘의 일치를 강제하지 않는다. probe를 분리 표기하고, 실제 capture → map의 알려진 height/mask와 tensor hash를 해당 경로에서 검사·기록해야 한다. A는 원래 map이 0이므로 A 한 번으로 B의 지도 정보 경로까지 증명했다고 쓰면 안 된다.

또 `entry:468`의 “no RayCaster data read”는 **추가 actor map 주입부**에만 맞는다. 설치 `robot_lab/tasks/go2/env_cfg.py:225~229`의 critic height_scan은 실제 `height_scanner`를 계속 읽는다. synthetic은 전체 PPO 관측·보상에서 실센서를 제거하는 모드가 아니다. 입력·critic finite 검사도 유지하고 이 한계를 영수증에 적어야 한다.

### 실기에서 아직 막힐 수 있는 경계

- **장치:** UUID 속성/표현, CUDA visible count, Kit 설정 key의 실제 존재와 타입이 맞아야 한다. 설정의 index 0 관측을 renderer의 물리 UUID까지 독립 실측했다는 뜻으로 쓰지 않는다. 실제 NVML UUID/bus·자식 CUDA UUID·Kit 관측을 한 기록으로 연결한다. 미관측을 0으로 채우지 않는다.
- **USD 변환 1회의 근거:** 현재 Go2 cfg는 `UnitreeUrdfFileCfg`이고, 설치 IsaacLab의 `sim/spawners/from_files/from_files.py:118`이 변환기를 호출한다. `sim/utils/prims.py:714~715,739`의 clone 경로는 원본 하나를 spawn한 뒤 복제한다. 따라서 N=32라고 32번 변환을 기대하는 것은 아니다. **현재 단일 로봇 cfg에서 1회라는 정적 근거는 있다.** 다른 변환 자산 추가까지 포괄하는 일반 법칙은 아니다.
- **stage 참조:** `entry:167~173`은 env_0/Robot의 reference metadata를 읽고 `launch:41~45`는 예상 생성 파일 하나와 정확히 비교한다. 실제 prim 위치·metadata list·파일명은 미확인이다. 상대 assetPath가 나오면 현재 `Path.resolve()`는 USD layer가 아닌 cwd 기준이므로 정상 참조도 거절할 수 있다. 그런 HOLD 때는 raw list-op·layer 식별자·resolved path를 보존해 경로 문제로 좁혀야 한다. 검사 자체를 끄거나 임의 glob으로 통과시키면 안 된다. 현재 소스에서 실제 상대 참조가 발생했다고 주장하지는 않는다.

## 2. 첫 참석 단회의 사전 고정값

**GPU 0 · arm A · synthetic_known_answer · N=32 · iteration 1**을 권고한다. live_raycaster_unverified는 먼저 할 이유가 없다. 다만 A의 목적은 기존 관측/정책/optimizer/저장 배관 점검이며 추가 지도 효과 확인이 아니다.

“sol 기본값”은 모호하므로 다음처럼 숫자를 적어 동결한다. 실제 CPU PPO fixture `s2_step3/test_s2_step3_entry.py:43~54`에 맞춘 작은 첫 시험안이다.

| 값 | 첫 단회 권고 |
|---|---|
| rollout_steps / epochs / minibatches | **2 / 1 / 1** |
| encoder / LR schedule | `full_freeze` / `fixed`. W·r을 이 모드에 끼워 넣지 않음 |
| seed / map_init_seed / LR | **11 / 7 / 0.001**, 다른 PPO·terrain 인자도 fixture와 실제 manifest의 값을 나란히 확인 |
| checkpoint_interval | **1**, 0회와 최종 1회 checkpoint 둘 다 plumbing 표지 |
| 최대 wall | **600초 이하**, 절대 마감·STOP·새 attempt/claim/output 고정 |
| 완료 기대값 | **1 iteration, 2 vector steps, 64 transitions, 1 optimizer step**. 센서 snapshot/bootstrap/reset은 별도 집계 |

이 작은 batch는 연결 시험용이며 유의미한 보행·지형 조우·수렴 판정용이 아니다. 2 step 동안 reset이 없으면 reset 경로는 미실행으로 남긴다. 초기 기동·URDF 변환도 시간/자원 예산에 넣고, 두 checkpoint·USD·로그를 담을 디스크 상한을 실제 크기로 산정한다. CPU fixture의 작은 디스크 예산을 실기값으로 복사하지 않는다.

B는 첫 A의 필수 검사 PASS와 정리 완료를 사람이 확인하고 **B에 대한 별도 직접 동의**를 받은 뒤 새 manifest/claim에서만 가능하다. 두 단회의 결과를 A/B 성능 비교로 부르지 않는다.

## 3. 수정 뒤 lead 기록과 직접 동의만으로 진행 가능한 범위

**현 B7 그대로는 불가하다.** 그러나 이번에 발견한 두 경로를 아래처럼 좁게 고쳤다는 CPU 증거가 확보되면, 같은 참석 GPU 0 단회를 매번 ASTRA에 다시 의뢰할 필요는 없다. lead의 수정·시험 기록과 팀장의 해당 단회 직접 동의로 진행할 수 있다.

1. **roundtrip 내용 비교:** 정상 E1 CPU roundtrip을 다시 통과시킨다. 디스크의 optimizer step 하나, moment 하나, control 상태 하나를 각각 바꾼 반례는 지정 mismatch에서 거절해야 한다. 양쪽 tensor의 device 정규화가 비교보다 앞서 적용되는지 소스로 확인하고, key/shape/dtype 누락도 허용하지 않는다. CUDA 성공으로 보고하지 않고 첫 실제 단회에서 strict load·오차·장치별 상태를 확인한다.
2. **실제 synthetic 메서드의 정답:** 위 capture → packet → map 경로를 정상/반례로 시험한다. 실제 기대값 -0.25와 miss/mask를 기록하며 hit 높이나 mask를 바꾼 반례는 정답 검사에서 막혀야 한다. 별도 +0.25 probe·A의 0 map·B용 합성 map을 서로 다른 증거로 적는다. critic의 실제 센서 입력은 유지됨을 명시한다.
3. **변경된 실행 묶음 동결:** 수정 파일·CPU 시험·manifest·부모·해석기·실제 import 경로의 출처를 남기고 새 체크섬 목록을 만든다. 위 정상 시험과 그 변경에 영향받은 plumbing 계약/실제 CPU PPO 시험을 재확인한다. 닫힌 31개 전체나 A3를 의례적으로 다시 돌릴 필요는 없다. 결과는 예정·실행·PASS·skip·HOLD·정상 선행·변이 want로 구분한다.
4. **직전 관문:** 아래 4·5절 정리, 실제 장치/VRAM/디스크, 새 격리 경로, 참석 관찰자와 STOP·마감·단회 동의를 확인한다. GPU 현재 상태와 용량은 이번 검증에서 미측정이다.

이 위임은 **내용 비교의 장치 정규화와 증거를 일치시키는 제한 수정**에 한한다. 예외 무시, sensor/map 수학 변경, cfg 의미 변경, Job/잠금/격리 완화, native crash 우회, GPU 1 병렬화, iteration 확대는 포함하지 않는다. 미확인 경계에서 실패하면 해당 단회는 HOLD이고 자동 재시도는 없다.

## 4. A3.2 4차 수집과 plumbing의 순서

**4차 종료 → 독립 가족 정리 확인 → GPU lease/USD 잠금 해제 확인 → 새 참석 plumbing** 순서를 유지한다. 이 문서는 A3.2 4차 자체의 기동 동의가 아니다.

4차가 다음 이유로 HOLD여도 별도 synthetic plumbing을 검토할 수 있다. 원인이 기하/시간 정합의 정답 불일치처럼 **분류된 검증 실패**이고, native 기동·장치·자산 격리·종료가 정상이며, 이번 synthetic 추가 map이 그 미확인 센서 값에 의존하지 않아야 한다. critic의 실제 관측 유효성 검사는 여전히 통과해야 한다. stage0는 그대로 HOLD로 남긴다.

**이어서는 안 되는 경우:** native crash/접근 위반, 장치 결박 실패, USD 변환·공유 자산 문제, OOM/자원 회복 미확인, 종료·잠금 해제 미확인, 원인 불명 예외, 입력/해시 변조, STOP/마감이 이미 다음 실행도 금지하는 경우. 단순히 프로세스가 안 보이거나 다음 실행이 시작 가능하다는 이유로 원인을 해결했다고 하지 않는다. 미지원 참조 accessor 같은 명시적 API 문제는 원인·수정 영향·증거를 좁혀 고친 뒤 판단한다.

## 5. 가족 정리의 독립 실측 최소 요건

`chain.receipt.json`의 family 0·release true는 감독기 자신의 주장이다. 최소한 **그 Job 밖의 관찰자 프로세스**가 다음을 동일 attempt·시각·해시에 묶어 남겨야 한다. 이 감사에서는 프로세스 종료·잠금 획득·NVML 호출을 하지 않았다.

| 증거 | 남길 최소 내용 |
|---|---|
| OS 프로세스 | 기동 당시 감독기/자식의 PID **및 생성 시각**, executable·attempt 식별을 기록. 종료 뒤 수초 간격의 두 관측에서 동일 신원의 프로세스와 해당 attempt 자손이 없음을 확인. PID 재사용을 사망 증거로 혼동하지 않음. 조회 거부는 없음이 아니라 미확인 |
| Job/종료 | 자식 rc·감독기 최종 cleanup 영수증·family count·영수증 SHA가 일치해야 함. 독립 관찰은 최종 파일이 쓰이고 감독기가 종료한 뒤 수행. 생성 중인 임시 영수증으로 PASS하지 않음 |
| GPU | 지정 **물리 UUID/bus**의 실행 전·중·후 NVML compute PID를 OS 신원과 대조해 이 attempt의 GPU 프로세스가 남지 않았음을 확인. 머신 전체 프로세스 수 0이나 VRAM 0을 요구하지 않음. WDDM/권한으로 목록이 미지원이면 미확인으로 기록하고, OS/Job/자원 재획득 증거와 그 한계를 사람이 확인해야 함. 이를 “NVML compute 0 실측”으로 바꾸지 않음 |
| 잠금 | 소유자 종료 뒤 별도 프로세스에서 **같은 canonical lease root·GPU UUID·공통 USD 잠금**을 비차단으로 잠깐 획득하고 즉시 해제한 결과. lock 파일 존재/삭제 여부는 대체 증거가 아님. 다른 정당한 소유자가 있으면 지우거나 종료하지 말고 소유권을 확인 |
| 합격 범위 | OS 잔존/조회 미확인, Job 결과 충돌, 이 attempt의 GPU PID 잔존, 잠금 미해제 중 하나라도 남으면 다음 실행 보류. NVML 미지원 자체를 다른 증거가 없는 상태의 허용 근거로 쓰지 않음 |

성공 표기는 `plumbing_checks=PASS`, `stage0_passed=false`, `performance_verified=false`, 조우 `unmeasured`로 제한한다. 본 문서는 무인·자동 재시도·200/2000 update·후속 학습·A/B 성능 비교·실행 승인 JSON을 허용하지 않으며 17z 무인 보류도 그대로다.
