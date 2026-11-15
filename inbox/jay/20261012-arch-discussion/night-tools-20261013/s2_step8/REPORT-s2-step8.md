# S2 B step8 · ASTRA 17ae 제한 수정 보고

> 분류: A/정책학습 · CPU 구현 보고
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-s2-B-fix17ae.md · VERIFY-astra-17ae.md · `s2_step8/evidence_s2_step8/final/summary.json` 원시 시험
> 요지: optimizer 상태의 장치 중립 비교와 실제 합성 capture 정답 검사를 보강하고 첫 A 배관 요청 초안을 고정했다.
> 상태: CPU 시험 통과 · GPU·Isaac 미실행 · 요청 미봉인 · 단회 승인 없음

## 수정 파일과 경계

`codexE/s2_step7/`를 `codexE/s2_step8/`로 복사했다. 공유 저장소와 step7, `_eval`, 기존 slot·guard, 부모 코드는 수정하지 않았다. 실행 코드 변경은 `s2_plumbing.py`, `s2_train_entry_17v.py`, `s2_train_launch.py` 세 파일이다. `test_s2_step6_contract.py`, `test_s2_step7.py`는 영수증 필드 정정을 반영했고, `test_s2_step8.py`, `test_s2_step8_mutants.py`, `run_all_s2_step8.py`, `S2-STEP8-USAGE.md`, `request_plumbing_A_first.json`을 추가했다. 센서·지도 수학, cfg 의미, Job·잠금·USD 격리, iteration 한도는 바꾸지 않았다.

P1: `roundtrip_policy`는 저장 checkpoint를 `map_location="cpu"`로 읽는다. `_same`은 양쪽 텐서의 key, shape, dtype을 보존해 비교하고 `detach().cpu()` 뒤 값을 비교한다. optimizer와 control 전체 재귀 비교, 새 policy 객체 strict load, 같은 입력의 action/value 최대 오차 `1e-6` 검사를 유지했다. 실제 E1 CPU 1 update 뒤 checkpoint 17,940,318바이트를 저장하고 정상 roundtrip을 통과했다. 디스크의 Adam step, `exp_avg`, control 값, optimizer key, step shape, step dtype을 각각 바꾼 여섯 반례는 모두 `checkpoint_optimizer_control_mismatch`에서 거절됐다. CPU의 `map_location='meta'` 소시험은 Adam step이 meta로 이동함을 보였으나 meta에는 값이 없어 내용 비교의 CUDA 성공 대역은 아니다. 장치 정규화가 비교 앞에 있는지 소스와 변이로 확인했다. 환경 resume 성공은 주장하지 않는다.

P2: `IsaacS2Env.capture_packet_after_sensor_update`가 만든 `AtomicPacket`을 실제 `training_map`에 넣어 B용 광선 정답을 검사한다. 정상 B는 첫 ray `(height=1, mask=0)`, 나머지 186개 `(height=-0.25, mask=1)`다. 두 env의 B tensor SHA256은 `f586d7f757413ef2d938efdc842264ba95c6d34b11e8aa7ea2a174d16ac85061`이다. A actor map은 영 행렬이고, 두 env의 SHA256은 `cda258b2a722a9336224ca9bb3997f0761213a8dac68d24b5fed88d80f18e2a3`이다. 두 pose, yaw 0과 π/2, episode reset을 CPU 객체에서 시험했다. 실제 scanner `data` 접근은 예외를 내도록 한 fixture에서 호출되지 않았다. hit z 또는 첫 ray mask를 바꾼 packet은 지정한 `synthetic_capture_map_answer_mismatch`에서 거절됐다. 매 capture 검사 수와 실제 정답 SHA를 live 영수증에서 대조한다.

`function_only_probe`는 root z=1, hit z=.25의 **+0.25** 함수 단독 시험으로, 실제 capture의 **-0.25** 정답과 별도 필드다. 첫 A 참석은 B 지도 정보 경로를 증명하지 않는다. B의 합성 map은 별도 정답으로 검증했고, 두 번째 arm 실행에는 별도 동의가 필요하다. 합성 actor map 주입은 RayCaster data를 읽지 않지만 설치 Go2 critic `height_scan`은 실제 `height_scanner`를 읽는다. 따라서 합성 모드는 PPO 관측·보상 전체의 실센서를 제거하지 않는다. 기존 입력·critic finite 검사는 유지했다.

## 첫 A 요청과 디스크 근거

`request_plumbing_A_first.json`은 GPU 0, UUID `GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b`, bus `41:00.0`, A, `synthetic_known_answer`, N=32, update 1, checkpoint interval 1, rollout 2, epoch 1, minibatch 1, `full_freeze`, fixed LR, seed 11, map seed 7, LR .001, wall 600초를 고정한다. 기대 계수는 iteration 1, vector step 2, transition 64, optimizer step 1이다. gap/stones와 나머지 PPO 값은 fixture 계약값을 명시했다. 기존 코드가 요구하는 공통 USD 잠금 경로는 그대로 적었다.

CPU checkpoint 실측 17,940,318바이트 두 개 35,880,636바이트, 기존 Go2 USD 격리 폴더 7개 파일의 합 18,819,145바이트로 기본 산정은 54,699,781바이트다. 로그·임시 파일 128MiB를 더한 188,917,509바이트의 약 5.7배인 1GiB를 제안 `max_disk_bytes`로, 여유 공간 요구는 2GiB로 적었다. 실제 새 USD·로그·GPU checkpoint 크기와 현재 여유 공간은 실행 직전에 다시 측정해야 한다. 부모 E1 26,367,183바이트는 별도 읽기 입력이다.

마감 epoch, 승인자와 approval 파일, 새 output·status·log·claim·GPU lease·STOP 경로, VRAM 문턱은 `UNDECIDED`다. 요청은 봉인하지 않았고 승인 JSON도 만들지 않았다. 실제 `seal()`은 `undecided_value`로 거절한다. CPU 시험에서만 이 값에 임시 fixture를 대입하니 `seal()`과 `validate(...,check_files=False)`가 통과했다. 이 fixture 승인 객체는 메모리 안의 계약 시험이며 실기 승인 근거가 아니다.

## 시험, 첫 실패, 문서 정정

최종 `evidence_s2_step8/final/summary.json`은 깨끗한 임시 복사본에서 `-I -B`, `CUDA_VISIBLE_DEVICES=-1`로 33개 시험 파일을 정상 먼저 실행한 기록이다. 정상 단계 **291 PASS**, 변이 단계의 정상 선행 **2 PASS**, 합계 **293 PASS 라벨**이다. 변이 **57/57 CAUGHT**이고 지정 첫 FAIL과 want가 전부 일치했다. 이번 수정 영향 시험에는 step6 계약·실제 CPU PPO·영수증 검증, step7 장치·USD 경계, step8 정상·반례·변이가 포함된다. 33개 전체도 최종 파일 기준으로 통과했다. summary와 로그를 `s2_step8/evidence_s2_step8/final/`에 보존했다.

첫 실패는 세 갈래였다. 첫 직접 `python -I test_s2_step8.py` 호출은 격리 모드에서 작업 폴더가 import 경로에 없어 `ModuleNotFoundError: s2_plumbing`으로 끝났고, 명시적 임시 `sys.path` 주입으로 시험 호출을 바로잡았다. 첫 mask 반례는 시험용 hit XY가 광선 정답과 달라 지도 정답보다 앞의 `ray ordering, yaw alignment or scan time mismatch`에서 막혔다. XY를 맞춘 뒤 지정 `synthetic_capture_map_answer_mismatch`에서 거절됨을 재확인했다. 첫 변이 실행의 `optimizer_cpu_load` 치환 문자열은 소스에 두 번 있어 anchor 검사가 실패했다. `roundtrip_policy`의 정확한 한 줄로 좁힌 뒤 정상 먼저, 변이 지정 FAIL을 확인했다. 추가 계약 시험은 초안의 임시 USD lock 경로가 `usd_lock_path`에서 거절돼 기존 고정 경로로 정정했다.

ASTRA 17ae의 과거 증거 수는 저장소 lead 사본 기준 정상 271 + 변이 선행 2 = 273이다. 이 작업 폴더의 step7 `final3/summary.json`은 추가 정상 검사 1개가 있어 정상 272 + 선행 2 = 274다. 서로 다른 실행을 같은 수로 부르지 않는다. 저장소 사본 step7 `evidence_s2_step7/final2/`에는 로그 2개만 있고 summary가 없으나, 이 작업 폴더의 원본 step7 `final2/`에는 summary가 있다. 저장소 사본으로 옮길 때 누락된 시점과 원인은 미확인이다. step8 최종 증거에는 summary가 있다.

A3 `s2_step4a3/`와 SHA를 다시 비교하면 adapter, map_obs, sensor_tracker, policy, terrain_overlay **5/6**이 바이트 동일하다. `s2_ppo_17v.py`는 다르다. 차이는 A3 원본 94행의 metrics에 loss 추가, 97행 부근 grad 배열 추가, 136행의 clip 앞 그룹별 preclip norm·비유한 grad 거절 추가, 142행의 loss 누적, 150행 반환의 grad 최소·최대·그룹 기록 추가다. 이 차이만으로 학습 수식 변경이라고 단정하지 않는다.

실제 CUDA optimizer 재적재, Isaac capture·critic 센서 읽기, UUID·VRAM, USD 참조, Job 가족 정리와 잠금 재획득은 이번 CPU 시험에서 미확인이다. 현재 요청 JSON은 실행 불가이며, 첫 GPU 0 단회는 lead 재검증과 팀장의 해당 단회 직접 동의 뒤 별도로 판단해야 한다.
