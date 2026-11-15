# CE12 v2 native 체크포인트 장치 매핑 수정 보고서
> 분류: A/평가
> 작성: Codex Worker B · 2026-10-14
> 근거: v2_native_17k_0650 로그와 run.json, 설치된 RSL-RL 코드, CPU 역직렬화 재현, 회귀·변이 시험
> 요지: v2 기록기의 runner.load에 기록기 장치를 명시해 CUDA:1 저장 텐서를 현재 장치로 읽는다
> 상태: CPU 검증 완료 · GPU/Isaac 재실행 미확인
> 판: v2 native mapfix 1

## 원인과 변경 범위

`_eval/out_ce12/native/v2_native_17k_0650.log` 189~222행과 대응 `_attempts/v2_native_17k_0650-20261014-065026-35316/run.json`을 읽었다. 자식은 종료 코드 0을 기록했으나 필수 `native.npz`, `meta.json`, `signature.json`이 없어 실행기가 `output_problem`, 종료 코드 88로 마감했다. 로그의 실제 예외는 `dump_native_v2.py:242`의 `runner.load(ckpt)`에서 시작한다. 설치된 `source/rsl_rl/rsl_rl/runners/on_policy_runner.py`의 시그니처는 `load(self, path, load_optimizer=True, map_location: str | None=None)`이고 310행의 `torch.load(path, weights_only=False, map_location=map_location)`에 `None`이 전달된다. CUDA:1 태그의 텐서가 든 `models/foothold-v2.pt`를 논리 CUDA 장치 한 개의 실행에서 읽자 PyTorch `restore_location`의 `_validate_device`가 `Attempting to deserialize object on CUDA device 1 but torch.cuda.device_count() is 1`을 냈다.

수정 전에 로드·장치 경로를 확인했다. `dump_native_v2.py`의 체크포인트 로드는 이 한 곳이다. 229행 `dev = raw_env.device`가 기록기의 장치를 정하고 241행 `OnPolicyRunner(..., device=dev)`, 243행 `get_inference_policy(device=dev)`와 텐서 생성에도 같은 `dev`를 쓴다. 따라서 242행만 `runner.load(ckpt, map_location=dev)`로 수정했다. 다른 직접 `torch.load` 또는 `.cuda()` 호출은 이 파일에 없다. `adapters.py`의 두 CPU 체크포인트 판독은 이미 `map_location="cpu"`다. CTS 기록기는 별도 러너와 체크포인트 경로라 이번 범위에서 고치지 않았다.

## 보관과 파일 해시

첫 수정 전에 `_eval/ce12/` 전체 27개 파일을 `_eval/ce12/v_17k/`에 복사했다. 보관본의 상위 12개 파일은 `night-tools-20261013/ce12_fix17i/SHA256SUMS.txt`와 **12/12** 일치한다. 복사 직후 원본 27개와 보관본 27개의 바이트 해시도 일치했다. 최종 원본의 기존 12개 중 기준과 다른 것은 `dump_native_v2.py` 하나뿐이고, 새 회귀 시험 파일 하나를 더했다.

| 파일 | SHA256 |
|---|---|
| 수정 전 보관본 `v_17k/dump_native_v2.py` | `53192fcb55c01b18af7ced6db8bfc79a4fe3021efac96f78e2575c68695b7157` |
| 수정 후 `dump_native_v2.py` | `251220254fc70b7b0adf1bbd2dd85d998c0218a38595c9c598ef3d626015be82` |
| 새 `test_v2_load_device.py` | `ab27ade793c9b713bd0b42550c0f8ebbdfd72ab188429acc348b12cd020f9a01` |

해시 원자료는 `baseline_sha256.json`과 위 파일들이며 기준 `SHA256SUMS.txt` 자체의 SHA256은 `c4e853b792efa0ce46dbb2eae04e540af2e93927f307102426387895d2a896dc`다. 기존 `v_astra17i/`는 수정하지 않았다.

## CPU 재현과 회귀·변이

절대 해석기 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe`와 `CUDA_VISIBLE_DEVICES=-1`, `PYTHONDONTWRITEBYTECODE=1`, `-B`를 사용했다. 출력·변이 사본·실자료 fixture 복사본은 전부 이 `codexB3/` 아래에 두었다. GPU와 Isaac은 실행하지 않았다.

새 `test_v2_load_device.py`는 CPU storage를 `torch.serialization.register_package`로 CUDA:1 태그를 붙여 `torch.save`한 뒤, 설치된 실제 `OnPolicyRunner.load`와 PyTorch `restore_location`을 통과시킨다. `torch.cuda.device_count()`만 1로 모의했다. map_location을 주지 않은 정상 대조군은 예상한 CUDA:1 RuntimeError를 냈다. 기록기 AST에서 실제 `runner.load` 호출과 `dev = raw_env.device`를 추출해 호출식을 실행한다. 수정 전 **실패** (`test_v2_red.log`), 수정 후 CPU 매핑과 tensor·iteration 확인 **통과** (`test_v2_green.log`), 한 줄을 되돌린 변이는 242행 호출과 `_validate_device`의 동일 RuntimeError를 거쳐 `AssertionError: v2_runner_load_map_location`으로 **CAUGHT** (`test_v2_mutant.log`)였다. import 오류나 다른 위치의 예외는 검출로 세지 않았다.

기존 CE12 검사는 `codexB3/eval/`의 격리 사본에서 돌렸다. 보호된 E1 원자료는 읽어 `codexB3/eval/out_ce12/native/`에 복사했고, 시험의 임시 산출물 정리는 `codexB3/retained/`로 보관하도록 격리 사본만 조정했다. 정상 소스에서 `test_adapters.py` **23/23**, `test_run_dump.py` **139/139** 통과했다. 이후 기존 변이 `mutate_adapters.py` **24/24**, `mutate_run_dump.py` **65/65**, `mutate_17i.py` **11/11 CAUGHT**였다. 변이 판정은 지정 시험 실패와 종료 코드 1을 확인하며, 격리 사본의 판정기에 `ImportError` 및 `ModuleNotFoundError` 배제를 추가했다. 원본 CE12 변이 실행기는 수정하지 않았다. 로그는 `test_adapters.log`, `test_run_dump_final.log`, `mutate_adapters.log`, `mutate_run_dump.log`, `mutate_17i.log`다.

첫 실패도 기록한다. 격리본 구성 중 `codexB3/eval/ce12`를 디렉터리보다 먼저 파일로 만들었고, 그 파일을 같은 B3 안의 `ce12_misplaced_copy.py`로 옮긴 뒤 정확한 격리본을 만들었다. 첫 `test_run_dump.py` 실행은 E1 fixture의 slot·guard·attempt 파일 일부가 빠져 `VA-real`에서 **138/139**였다 (`test_run_dump.log`). 빠진 보호 파일은 읽기 전용으로 B3에 복사하고 `VA-real` **1/1**, 전체 **139/139**로 다시 확인했다. `mutate_17i.py` 첫 실행은 11개 모두 CAUGHT를 출력했지만 내부 결과 파일과 `Tee-Object`가 같은 `mutate_17i.log`를 잡아 최종 기록에서 `PermissionError`가 났다. 콘솔 로그를 `mutate_17i_console_retry.log`로 분리해 다시 **11/11** 정상 종료했다. 이 세 실패를 성공 분모에 섞지 않았다.

## lead가 다시 돌릴 명령

GPU 1의 진행 중인 v6 full이 끝나고 lead가 관문 상태를 확인한 뒤 실행할 명령이다. 기존 기록과 같은 checkpoint·셀·reset·전환 조건이며, 새 tag로 이전 보호 출력과 충돌하지 않는다. `--deadline 0`은 시간 제한 없음이므로 lead가 운영 마감 시각이 있으면 새 epoch 초로 바꾼다. 아래 명령은 이 작업자가 실행하지 않았다.

```powershell
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' 'C:/isaac/ext/go2_rl_robotlab/_eval/ce12/run_dump.py' --which v2 --checkpoint 'C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/models/foothold-v2.pt' --tag v2_native_17n_mapfix --gpu 1 --min_free_mib 4096 --deadline 0 -- --cells stand,fwd03,yawL05 --envs_per_cell 4 --steps 60 --reset_envs 1,6 --reset_step 30 --switch_env 0 --switch_step 40 --switch_cell fwd03
```

실행 뒤 새 tag의 `native.npz`, `meta.json`, `signature.json`, `run.json`, 로그와 `validate_dump.py` 결과를 함께 확인해야 한다. 현재 실제 GPU 1에서 로드·기록·검증이 통과하는지는 **미확인**이다. `_eval/out*`, slot, branch, rand_scenes, s2, handover에 쓰지 않았고 파일 삭제도 하지 않았다. `run_dump.py`의 실제 실행 경로는 이 작업자가 호출하지 않았다.

## 이력

| 판 | 일시 | 내용 |
|---|---|---|
| v2 native mapfix 1 | 2026-10-14 | v2 runner.load 장치 매핑, CPU 실제 역직렬화 재현, CE12 회귀·변이 재검 |
