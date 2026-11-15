# S2 B 기동기 동등성 표
> 분류: A/정책학습 · 기동 계약
> 작성: Codex Worker · 2026-10-15
> 근거: `_eval/branch/night_20261013_cmdr1043_v3.sh` · `_eval/branch/branch_run.py` · `_eval/isaac_slot_v3.py` · A4 r2
> 요지: 검증된 1043 학습 기동 경로와 S2 B 자식 기동 경로의 필수 줄을 대조한다.
> 상태: CPU 정적 계약 및 대역 시험 대상 · 실제 S2 GPU 기동 미확인

| 줄 | 1043 학습 기동의 실제 줄 | S2 B 대응 | CPU 관문 |
|---|---|---|---|
| interpreter | `night_20261013_cmdr1043_v3.sh:18` isaac311-moects Python | manifest `python_path`, 정확한 파일 해시 | interpreter 경로·해시 |
| cwd | 1043 셸 `:17`에서 `_eval/branch`로 `cd`; slot `isaac_slot_v3.py:459`는 cwd 상속 | `s2_step5/`로 고정 | 다른 cwd 거절 |
| EULA | 1043 셸 `:26`의 `OMNI_KIT_ACCEPT_EULA=YES` | 승인된 EULA 확인 뒤 자식 env에 `YES` | 누락 변이 첫 FAIL |
| 로그 | 같은 줄의 `PYTHONUNBUFFERED=1` | 자식 env `1`, stdout/stderr 지정 로그 | 누락 거절 |
| 물리 순서 | 같은 줄의 `CUDA_DEVICE_ORDER=PCI_BUS_ID` | 자식 env 동일 | 누락 거절 |
| 보이는 장치 | 같은 줄의 `CUDA_VISIBLE_DEVICES=0` | 승인 UUID/index/bus 대조 뒤 `0`, 자식 논리 `cuda:0` | 다른 index 거절 |
| preload 1 | `branch_run.py:45`의 `h5py` | entry에서 Kit import 앞 `h5py` | 삭제 변이 첫 FAIL |
| preload 2 | `ce12/dump_native_v2.py:32`의 `torch` | entry에서 Kit import 앞 `torch` | 순서 변이 첫 FAIL |
| preload 3 | `branch_run.py:46`의 `tensordict` | entry에서 Kit import 앞 `tensordict` | 삭제 변이 첫 FAIL |
| AppLauncher | `branch_run.py:47,49-52`가 인자를 등록하고 `headless=True`로 만든다 | entry가 사전 승인 확인 후 인자 등록, `--headless --device cuda:0` 한 번씩 요구 | 중복·cuda:1 거절 |
| argv | 1043 셸 `:49`는 `branch_run.py --headless --tag --parent --seed --num_envs --updates --cmdr` | 승인 manifest에 고정한 entry argv와 실제 argv 바이트 배열이 일치해야 한다 | 변조 거절 |
| stdin | 1043 셸 비대화형; slot은 `Popen`으로 상속(`isaac_slot_v3.py:459`) | A4 r2 `s2_unattended_launch.py:49-51`의 `DEVNULL` 방식. EULA는 env가 해결해야 한다 | stdin이 DEVNULL인지 대역 확인 |
| 출처·출력 | 1043 셸 `:22,26,38-49`의 별도 출력, STOP, attempt, USD/guard 경로 | 새 out/log/status/claim과 STOP, 승인 해시, Job 소유 가족 | 기존 출력·claim 재사용 거절 |
| 단회 보호 | 1043 셸 `:39-49`의 slot, guard, USD 격리 및 자식 rc 확인 | B 참석 감독기의 GPU lease, 공통 USD lock, 사전 자원 측정, Job 소유 가족, heartbeat/STOP/마감 | 가짜 owner/meter 관문 |

이 표는 기능 동일성을 주장하지 않는다. 1043은 E1의 8192환경·CMD-R, B는 1024환경·S2 arm 한 개다. A4 r2 무인 gate/watchdog는 17z 보류 때문에 이 참석 B 기동의 승인 근거로 재사용하지 않는다. 표의 `stdin` 대응은 1043의 상속과 의도적으로 다르며, `YES`가 없으면 비대화형 자식이 실패한다는 오늘의 실측을 반영한다.
