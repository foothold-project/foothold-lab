# S2 B 기동 동등성 표 · 17ad 정정

> 분류: A/정책학습 · 기동 검토
> 작성: Codex Worker · 2026-10-15
> 근거: `_eval/branch/night_20261013_cmdr1043_v3.sh` · 현재 `_eval` 파일 해시 · step7 소스
> 요지: 1043 셸이 실제 호출하는 무접미사 slot과 USD 실행기를 기준으로 B 참석 기동을 비교한다.
> 상태: CPU 정적 확인 · 1043 당시 실행 바이트와 S2 실제 기동은 미확인

| 경계 | 1043 셸의 실제 argv 또는 파일 | step7 B 경로 | 검증 상태 |
|---|---|---|---|
| 해석기 | 셸의 `$PY` | manifest 고정 `isaac311-moects/python.exe -B` | 경로·파일 해시 CPU 확인 |
| cwd | 셸 17행의 `_eval/branch` | JobOwner가 step7을 cwd로 전달 | CPU 대역 시험 |
| 환경 | 셸 `OMNI_KIT_ACCEPT_EULA=YES`, `PYTHONUNBUFFERED=1`, `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `CUDA_VISIBLE_DEVICES=0` | 감독기 child env와 승인 EULA | CPU 대역 시험 |
| slot | 셸 45행 `../isaac_slot.py --watch_log ... --record ... --attempt ... --usd_root ... --lock ... --registry ... --scan_dirs ... --stop_file ... --deadline ... --` | 공통 lease, USD lock, Job 소유, deadline, 상태 파일 | 역할 비교. 구현 동일성 주장은 아님 |
| GPU guard | 셸 48행 `../gpu_guard.py --gpu 0 --min_free_mib 256 --log ... --summary ... --` | NvmlMeter 사전·실행 중 계측과 GPU 0 UUID 결박 | 실제 NVML·Kit 결과 미확인 |
| USD 래퍼 | 셸 49행 `../usd_isolate_run.py branch_run.py ...` | 검증된 v3 래퍼를 동일 해시로 번들에 복사, 실행별 `out_root/usd` | CPU 정적·대역 확인. 실제 변환 미확인 |
| entry | 셸 49행 `branch_run.py --headless --tag --parent --seed --num_envs --updates --cmdr` | `s2_train_entry_17v.py --stage plumbing --headless --device cuda:0` 등 봉인 argv | 다른 정책·환경·인자. 동등성 주장 아님 |
| native 선적재 | `branch_run.py`의 h5py, tensordict가 Kit보다 앞 | step7 entry의 h5py, torch, tensordict가 Kit보다 앞 | 실제 CPU import 성공. Kit 네이티브 순서는 GPU 미실행 |
| 종료 | 셸 rc 확인 후 validate_branch | 감독기 rc, 가족 0, checkpoint 내용, 배관 증거, USD 참조, 정리 후 영수증 | CPU 대역 시험. 실기 미확인 |

현재 읽은 SHA256: 셸 `c53dd90cfb1eaa7102168d6424a2e4364bedad5ff95a89b311877433bd57df9e`, 무접미사 `isaac_slot.py` `90ae613b0e7e791fa24bf82866eb0a0285eafe5cd10f0e201ba2f5af9fa19c47`, 무접미사 `usd_isolate_run.py` `366a3c13aac3499e711ea717441ae7e3da67871302b5c6e432b1cbc20ea0a87f`. 기존 표가 잘못 인용한 `isaac_slot_v3.py`는 `974919b0717b684fb9f0a57a0282aeb5a0b321f4bc7d4131aedcc461e2d3945a`, 채택한 `usd_isolate_run_v3.py`는 `30dc2ea930f400948474b11c648aa389ff495d2a1bd764b4b9b984b931d11efb`다.

1043 해당 실행의 slot 영수증은 확인하지 못했다. 위 무접미사 해시는 현재 파일을 읽은 값이며 당시 실행 바이트는 미확인이다. 기존 `h5py_after_kit`, `tensordict_after_kit`, `no_job_assign` 변이는 소스 문자열 변경 검사다. native Kit 적재 순서나 실제 Job 가족 정리 증거로 쓰지 않는다.
