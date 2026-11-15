# S2 B 실기동 경로 CPU 보고
> 분류: A/정책학습
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-s2-B-live.md · VERIFY-astra-17aa.md · 1043 실제 기동기 · step5 시험 로그
> 요지: S2 B 참석 학습 진입의 기동 동등성과 CPU 경계 시험을 마쳤고 실제 GPU·Isaac 결과는 미확인이다.
> 상태: CPU 확인됨 · GPU/Isaac 미실행 · 팀장 결정값 미입력

## 산출물

- 새 작업 사본 `codexE/s2_step5/`에 B 런타임, 참석 감독기, manifest 봉인기, 동등성 표와 시험을 모았다. 기존 `s2_step4/`, `s2_step4a2_frozen/`, 부모 코드, `_eval`, slot, guard, 저장소 공유 체크아웃 쓰기 0.
- `S2-STEP5-LAUNCH-PARITY.md`는 1043 `_eval/branch/night_20261013_cmdr1043_v3.sh`, `branch_run.py`, `isaac_slot_v3.py`와 B 후보의 interpreter, cwd, EULA, unbuffered, CUDA 순서·표시 장치, h5py/torch/tensordict 선적재, argv, AppLauncher, stdin, 로그·STOP·claim, 소유권을 줄별로 대조한다. `s2_launch_parity.py` 17/17 확인.
- `s2_train_entry_17v.py`는 승인 manifest와 정확한 argv를 Kit import 전에 검사한다. h5py, torch, tensordict를 Kit 앞에서 적재한다. headless `cuda:0`, RobotLab Go2 등록 cfg, N=1,024, gap/stepping stones 각 15%, E1 부모 SHA 고정, A/B 한 arm PPO, 0·200·2,000·+500 체크포인트 경계를 연결했다. 단계 PASS 대신 `RUN_COMPLETE_UNVERIFIED`를 기록한다.
- `s2_train_launch.py`는 EULA YES, `PYTHONUNBUFFERED=1`, `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `CUDA_VISIBLE_DEVICES=0`, NUL stdin, GO 보고서 60초 제한, GPU lease, 기존 USD byte lock, Windows Job Object 가족, heartbeat·STOP·마감·단회 claim·결과/체크포인트/로그 SHA 영수증을 구현했다. child 시작 직전 경쟁 Isaac 프로세스를 재확인한다. 독립 watchdog을 갖춘 무인 A4 r2 gate는 0단계 scope라 학습에 재사용하지 않았다.
- `s2_train_manifest.py`와 `S2-STEP5-USAGE.md`는 팀장 선택값을 요청 JSON으로 받아 코드·부모·Python·hook 해시와 정확한 argv를 봉인하는 방법을 적는다. 승인 JSON은 팀장이 별도로 만든다. 값 `UNDECIDED`는 거절한다.

## CPU 검증

최종 증거 `s2_step5/evidence_s2_step5/r20261015_step5_final6/summary.json`: 8개 시험 프로세스 exit 0, 정상 PASS 라벨 53개, 정상 뒤 코드 변이 7/7 CAUGHT. 각 변이의 첫 FAIL이 지정 want와 일치한다. 런타임 의존 파일 19개만 깨끗한 임시 폴더에 복사한 import도 통과했다. `CUDA_VISIBLE_DEVICES=-1`, `isaac311-moects/python.exe -B`로 실행했다. GPU·Isaac 실행 0회.

실제 E1 체크포인트를 CPU strict load한 뒤 arm A 초기 action은 16개 입력에서 부모와 비트 동일했다. 기존 실제 PPO runner의 CPU 1 update와 같은 프로세스 2구간 시험이 통과했다. 200 update의 finite loss/KL/entropy 및 0·200 checkpoint, 2,000+500 같은 runner의 영수증·checkpoint 경계는 **결정적 가짜 runner**로 확인했다. 이는 Isaac 200회 학습 실측이 아니다. 가짜 meter·owner·lease로 승인 누락, EULA 거절, 잘못된 N/지형/GPU/argv/hash, 잘못된 짧은 사슬 승인, 단회 claim, 영수증을 확인했다.

코드 변이: EULA 누락은 `candidate_eula`, unbuffered 누락은 `candidate_unbuffered`, GPU 1 변경은 `candidate_visible_zero`, h5py/tensordict 선적재 훼손은 각각 `candidate_preload_h5py`/`candidate_preload_tensordict`, argv 관문 제거는 `candidate_argv`, Job 배정 제거는 `candidate_owned_family`가 첫 FAIL이었다. 각 변이는 정상 동등성 17/17 통과 뒤 임시 복사본에서만 실행했다.

첫 묶음 `r20261015_step5_final1`은 이전 packet 시험 fixture가 A2 영수증 벡터 필드를 쓰지 않아 실패했다. fixture를 현재 packet 계약에 맞추고 다시 시험했다. `r20261015_step5_final4`는 `UNDECIDED` 우선 거절을 넣은 뒤 기존 음성 시험의 기대 첫 FAIL이 바뀌어 실패했다. 거절 입력을 `DENIED`로 구분하고 새 run-id 전체 묶음 `final6`를 통과시켰다. 두 실패 로그도 보존했다.

## 미확인과 다음 판단

실제 Kit 기동, RobotLab cfg/terrain key와 원점 배치, sensor private hook와 root mount 변환, 장치 UUID/bus, VRAM·디스크 여유, E1 부모를 사용한 Isaac 200회 업데이트의 finite 지표와 조우 판정은 미확인이다. A4 r2의 무인 gate/watchdog은 여전히 0단계 전용이며 B 학습 자동 진행을 허용하는 근거가 아니다. `RUN_COMPLETE_UNVERIFIED`를 단계 합격으로 읽지 않아야 한다. 팀장·ASTRA 승인값은 manifest에 미리 넣지 않았다.

다음은 lead의 요청·승인 JSON과 참석 감독 아래 단회 prelaunch GO, 그 뒤 실제 기동 증거 대조다. 현재 CPU 결과만으로 GPU 기동 승인이나 EULA 동의를 대신하지 않는다. 완결 파일 해시는 `S2-STEP5-SHA256SUMS.txt`에 기록했다.
