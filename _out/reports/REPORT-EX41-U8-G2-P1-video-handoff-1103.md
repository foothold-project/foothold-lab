# EX-41 평가 로더와 W78 영상 소비 전달
> 분류: 실행 전 검증
> 작성: 오흥재 · scripter 반영 · 2026-11-03
> 근거: EX41-PRELAUNCH-MASTER.md A의 U8 · G2 · P1, runner e2131ce3, C76 첫 칸 원자료
> 요지: 공통 평가 로더, W78 소비기, C층 GPU1 가시성 수정을 한 소스 HEAD에 연결했다.
> 상태: CPU 확인됨 · EX-41 W78 Kit 첫 편과 최종 기동 영수증은 미확인

## 전달 범위

| 항목 | 연결과 증거 | 남은 확인 |
|---|---|---|
| G2 | `ex41_eval_loader.load_checkpoint_for_eval`을 W78 기록기의 `gym.make` 전에 호출한다. 체크포인트의 `ex41_pose_commands`, actor 98, critic 666을 검증하고 `pose_cmd` 두 0열을 준비한다. 같은 `checkpoint_state`를 `adapters.load_s2_runner`에 넘기며 첫 실제 관측에서 `verify_ex41_pose_observation`을 호출한다. `review.json`의 `w78_video`에 준비와 첫 관측 결과를 남긴다. EX-40 m6000 실제 저장본을 사용한 이식 시험은 `9 passed, 1 skipped`, 별도 로더·W78·C층 CPU 묶음은 `50 passed`다. | 최종 EX-41 저장본으로 Kit 첫 편을 runner와 lead가 확인한다. |
| U8 · D149 | W78 소비기 인자는 `--device cuda:1`만 받는다. 자식 기록기 argv도 정확히 `--device cuda:1`이며 `recorder_child_env`가 상속된 `CUDA_VISIBLE_DEVICES`를 제거하고 `CUDA_DEVICE_ORDER=PCI_BUS_ID`를 넣는다. 부모가 GPU0을 가려도 자식 물리 GPU1 번호가 유지되는 답 아는 CPU 시험을 통과했다. | 최종 시작 스크립트에서 학습 `cuda:0`, 평가·촬영 `cuda:1`, 활성 작업 비충돌을 실제 영수증으로 확인한다. |
| P1 영상 쪽 | 고정 소스의 공통 로더 파일 존재, Git HEAD·추적 파일 청결, 요청의 manifest/체크포인트 SHA, 기록기·합성기 SHA를 촬영 전 검사한다. 실제 통합 소스 루트에서 가짜 체크포인트를 명시한 `--plan-only`는 rc0, 12조합·`cuda:1`을 반환했다. 이 시험은 모델 성능이나 Kit 성공의 증거가 아니다. | 최종 m6000 부모·실제 출력 ROOT·실제 계획을 쓴 학습 DRY는 runner 담당이다. |
| C층 가시성 | env5 GPU1 한 편 `D:/mai-tmp/c_layer_visibility_fix_v1/smoke_gpu1_out/attempts/pyramid_stairs_inv_L0_eval_gt/01`은 450프레임 전수 검사 PASS, 분할 450행에서 선택 로봇 최소 40590픽셀, 다른 로봇 최대 0픽셀이다. 선택 env를 숨기던 문제의 수정이 포함된다. | GPU0 env0은 같은 분할 조건으로 실패했다. GPU0 C층은 HOLD이며 이 전달을 GPU0 통과로 읽지 않는다. |

## 소스와 시험

- 통합 근거: runner 공유 로더 `e2131ce3`, scripter C층 수정 `8f1a4809`, GPU0 진단 `7b443dfa`, W78 소비기 `976be7e0`을 현재 브랜치에 포함했다.
- 주요 파일 SHA256: `ex41_eval_loader.py` `04e0c134c16cb70313903eeab867199e08152361c70d36f2f8d3aee76ee01030`; `record_c_layer.py` `19f68899a9a870e6e73824d1316e0de7b6977213fd40e1ae1860e7c52432ee40`; `w78_video_consumer.py` `79adce4d9f4a5884c65fbcda0435d9b6c7531b5f107423d96c268405ccdd369e`.
- 시험 명령: `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest -q foothold_s2/tests/test_c_layer_queue.py foothold_s2/tests/test_c_layer_segmentation.py foothold_s2/eval/tests/test_w78_video_consumer_cpu.py foothold_s2/tests/test_ex41_eval_loader_cpu.py --basetemp D:/mai-tmp/scripter/ex41_video_full -p no:cacheprovider` → `50 passed in 7.61s`.
- 실제 m6000 부모 이식: `EX41_PARENT_6000_CHECKPOINT`에 `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/model_6000.pt`, 기대 SHA `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5`, `EX41_COORDINATE_METADATA`에 같은 run의 `training_trace/coordinate_metadata.json`을 지정하고 `test_ex41_b345.py`를 CPU로 실행했다. 결과 `9 passed, 1 skipped in 10.82s`이며 skip은 m7500 환경 변수가 없어서다.
- `ruff check --select F`는 변경 Python 파일 5개에 대해 `All checks passed!`; `compileall`과 `git diff --check`도 통과했다.

## runner 연결 계약

W78 소비기는 `--source-root <통합 고정 HEAD> --recorder <그 HEAD>/foothold_s2/eval/video25/record_c_layer.py --composer <그 HEAD>/foothold_s2/eval/video25/compose_25e_v2style10.py --python C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe --gpu-jobs-config <그 HEAD>/_out/tools/gpu_jobs/jobs.json --device cuda:1 --request <run>/w78_video_requests/request_mNNNNN_<id>.json --out <D: 영상 출력>`을 받는다. 부모 학습 명령은 `--device cuda:0`이다. 자식의 `CUDA_DEVICE_ORDER=PCI_BUS_ID`와 `CUDA_VISIBLE_DEVICES` 제거는 소비기 안에서 강제한다. 최종 스크립트의 실제 argv·GPU 점유 영수증은 runner가 확인한다.

R6의 가짜 CPU cfg 경고는 실제 m6000 이식 시험과 실제 소스 루트 plan-only를 구분해 기록했다. R20의 경로 오류는 절대 경로와 SHA로 막는다. R24의 전달 확인은 runner의 회신으로 확인한다. M02 때문에 실행 중 C층 GPU1 고정 사본은 수정하지 않았다.
