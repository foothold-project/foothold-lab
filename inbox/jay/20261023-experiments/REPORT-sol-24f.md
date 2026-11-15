# SOL-24f · 실행 중 TopDown 저장 종료 경로

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: sol · 2026-10-24
> 근거: 고정 코드 `lead-tmp-start-b` d9517fb9, `td_main_segment1.json`, `process.json`, `run.log` 읽기
> 요지: 현재 실행은 50/100회 조기 저장 종료 통로가 없으며, 다음 구간에서는 시작할 때 종료 파일을 결선해야 한다
> 상태: 코드·실행 기록 대조 확인, 실제 재개 미확인

## 현재 실행의 종료 통로

`C:/Users/AI-WS01/s2_lab/run_20261024/td_main_segment1.json`의 자식 argv는 `train_23f_topdown.py --headless --device cuda:1 --num_envs 3072 --seed 42 --max_iterations 1001 --map_input reconstruction --run_name ex29-td-main --end-by 2026-10-24T09:55:00+09:00`이다. `--stop-file`은 없다. 읽을 당시 `process.json`은 감독기 PID 117160, 자식 PID 130816, `running`을 기록했다. 08:20 기동 뒤 `run.log`의 누적 transition 1,179,648은 3072 × 24 × 16이므로 16회 수집분이다. 이는 읽은 시점의 기록이며 실시간 진행 보증은 아니다.

`foothold_s2/scripts/train_sol23f_common.py:38-42,175,216-223`은 시작 때 마감과 선택적 종료 파일을 runner에 전달한다. `foothold_s2/runners/sol23f_runner.py:164-169,235-252`는 완료한 update의 log에서 마감 도달 또는 지정된 종료 파일 존재를 확인한 뒤 `model_<iter>.pt`, manifest, `latest.pt`를 저장하고 `stopped_saved`로 끝낸다. 현재는 종료 파일 인자가 `None`이어서 나중에 파일을 만들어도 이 분기는 작동하지 않는다. 실행 중 JSON을 고쳐도 이미 파싱한 자식 인자가 바뀌지 않는다. 이 고정 코드와 현 argv에는 정확히 50회나 100회에서 정상 저장 종료시키는 통로가 없다. 지정된 09:55 마감은 갱신 경계에서 저장 종료할 수 있지만 50/100회 목표를 충족하지 않는다. 기존 `model_0.pt`, 주기 저장본 또는 `latest.pt`에서 다시 시작해 최근 완료 갱신을 버리는 방안은 사용하지 않는다. 프로세스·출력·GPU는 건드리지 않았다.

## 다음 구간에서의 재개와 계획 종료

정상 종료로 생성된 **최신 완료** 체크포인트와 상태 `stopped_saved`의 경로·SHA를 확인한 뒤 별도 구간으로 시작한다. 다음 구간을 시작할 때 `--resume_from <검증한 model_N.pt> --max_iterations 1001 --stop-file <새 구간 전용 STOP 경로> --end-by <새 승인 마감>`을 기존 TopDown 명령에 추가할 수 있다. 종료 파일은 실행 시작부터 인자로 결선돼야 하며 만들기 전까지 학습을 계속한다. 더 정확한 누적 50/100회 목표를 다음 구간에 적용하려면 `--max_iterations 51` 또는 `101`로 별도 구간을 계획할 수 있다. `train_sol23f_common.py:211-217`은 저장된 0 기반 `iter`에 1을 더해 완료 회차를 세고 목표와의 차이만 학습한다. 목표 구간이 끝난 뒤 다시 새 구간에서 누적 1001회를 설정한다. 이는 현재 실행에 소급 적용할 수 없다.

`foothold_s2/sol23f_contract.py:53-85`는 진단용 `model_initial.pt`를 거절하고 형식·variant·깊이 지연·필수 상태·SHA를 검사해 새 segment 폴더를 만든다. `foothold_s2/runners/start_runner.py:608-665`는 정책과 PPO optimizer, 적응 학습률, 지각망과 그 optimizer, AdaSmpl, 환경 상태, RNG, 누적 iteration을 저장·복원한다. `foothold_s2/scripts/train_sol23f_common.py:181-190`과 `foothold_s2/runners/sol23f_runner.py:173-195`는 새 simulator에서 지형 원점·난도 복원 후 물리 reset을 수행하고 `physical_resume_identical=false`를 남긴다. 따라서 학습 상태 재개는 가능하도록 설계됐지만 동일 에피소드·GRU 이력·물리 궤적의 연속 재현을 뜻하지 않는다. 실제 Kit 재개 성공은 이번 읽기 검토로 확인하지 않았다.

## 깊이와 분산 학습 계약

`foothold_s2/sensors/depth_cam_cfg.py:15-17,54-68`의 학습용 깊이 센서는 D435i 모사 `RayCasterCameraCfg` + pinhole 광선, `distance_to_image_plane`, 원래 60 × 60, 0.1초 갱신, `debug_vis=False`다. RTX RGB 렌더 카메라가 아니다. `foothold_s2/sensors/start_obs.py:30-32`는 `(N,60,60,1)` 깊이를 증강·정규화한 뒤 `(N,3600)`으로 넘긴다. `foothold_s2/models/start_perception.py:33-34,68-82,113-119,287-298`은 최근 두 60 × 60 프레임을 DepthCNN으로 1024 특징으로 바꿔 TR-Net/GRU에 준다. 학습 시 깊이 tick은 5 제어 step이고 TopDown 설정의 지연은 0 tick이다(`s2_23f_topdown_ppo_cfg.py:15-16`). 기록 도구의 영상 기본값 960 × 540은 별도의 viewer/MP4 출력 해상도다(`foothold_s2/eval/record_sol23f.py:304-306,387`). 기록 도구의 깊이 지도 표시 입력은 여전히 60 × 60이고, GT/rough/refined 높이 지도는 각 32 × 16이다(`:158-171`). 실제 런타임 프레임 값은 이번 읽기 검토에서 재지 않았다.

`foothold_s2/scripts/train_sol23f_common.py:32-33`에 `--distributed` 인자는 있지만 `foothold_s2/sol23f_contract.py:19-20`이 이를 시작 전에 거절한다. 기저 `start_runner.py`에 일부 분산 분기가 있어도 **이 SOL-23f TopDown 진입점은 DDP를 지원하지 않는다**. 두 GPU로 현재 실행의 update를 분산하는 명령은 없다.

## 실행 판단에 필요한 한계

50/100회 조기 종료를 위해 현 실행을 죽이거나, 과거 체크포인트로 되돌리거나, 실행 중 코드·상태 파일을 바꾸는 행동은 하지 않았다. 현재 실행의 다음 정상 종료는 이미 설정된 마감 또는 자연 완료뿐이다. 다음 구간의 종료 파일 경로·마감·체크포인트 선택 및 실제 기동은 root가 별도로 결정해야 한다.
