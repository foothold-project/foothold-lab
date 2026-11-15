> 분류: 운영
> 작성: sol · 2026-10-24
> 근거: 고정 `lead-tmp-start-b` 학습 코드와 10/24 B 실제 argv·manifest·model850 읽기 확인
> 요지: 현재 실행에는 model1000 직후의 정상 저장 종료를 요청할 연결된 제어 경로가 없다.
> 상태: CPU 확인 완료 · 실행 중 파일과 프로세스 미변경
> 판: v1.0

# SOL24h · B model1000 경계 종료 경로 확인

`코드확인`: 현재 종료 연결의 유무. `미확인`: 미래 model1000의 저장 완료. [실험 이슈555](https://github.com/foothold-project/foothold-lab/issues/555).

통합 후속: 이 보고서의 종료 질문에 팀장이 **1000회 촬영·분석 후1500까지 계속하고 종료**하라고 직접 답했다. [직접 답 기록](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6379481102). 현재 정상 STOP 연결이 없다는 코드 확인은 그대로이며, 새 STOP을 붙이지 않고 기존 상한의 자연 완료를 확인한다.

## 판정

현재 PID 94332의 실제 명령은 `train_23f_b.py ... --max_iterations 1501 --end-by 2026-10-24T22:30:00+09:00`이며 `--stop-file`이 없다. `b_main.json`과 manifest의 `cli_args.stop_file`도 null이다. `train_sol23f_common.py:41,177`은 그 인자만 runner에 넘기고, `sol23f_runner.py:240-252`는 `stop_file is not None`인 경우에만 파일 존재를 검사한다. 따라서 지금 새 STOP 파일을 만들어도 현재 trainer는 읽지 않는다. `run_process_1024.py:20-49` 감독기는 child를 감시하고 heartbeat만 쓰며 제어 파일이나 중단 메시지 입력이 없다. stdin도 `DEVNULL`이다.

코드에 이미 있는 정상 경계 종료는 **다음에 그 인자를 넣어 시작한 실행**에서만 쓸 수 있다. runner의 매 갱신 `log()`에서 stop 파일 또는 마감 시점을 발견하면 `model_<iter>.pt`를 임시 파일 저장 후 교체하고, manifest·`latest.pt`·`stopped_saved` 영수증을 기록한다 (`sol23f_runner.py:211-252`, `train_sol23f_common.py:218-225`). 지금 실행은 22:30 마감 또는 총 1501 갱신의 자연 완료까지 그 경로를 스스로 호출하지 않는다. 실행 중 argv/코드 수정, 신호, 외부 강제 종료는 정상 저장 종료의 대체 경로로 확인되지 않았다. 특히 `train_sol23f_common.py:245-263`의 일반 예외 경로는 실패 상태를 기록할 뿐 새 checkpoint를 저장하지 않는다.

## model1000 증거 조건

미래 checkpoint의 안전성은 그때 아래 세 층을 확인해야 한다. 이 확인은 **이번 프로세스 종료를 뜻하지 않는다**.

1. 고정 로그 폴더의 `model_1000.pt`가 존재하고 `model_1000.pt.tmp`는 없을 것. `Sol23FRunner.save()`는 `torch.save(tmp)` 뒤 `os.replace`로 번호 붙은 파일을 완성한다 (`sol23f_runner.py:211-220`).
2. `manifest.json.checkpoints["model_1000.pt"]`가 실제 SHA-256과 같고, `progress.completed_updates >= 1001`일 것. 회차는 0부터 시작하므로 `model_1000.pt`의 저장 `iter`는 1000이고 완료 갱신 수는 1001이다 (`start_runner.py:262-263,365-385,428-434`).
3. CPU `torch.load(..., map_location="cpu", weights_only=False)`에서 format `foothold-start/1`, `iter=1000`, `sol23f.variant=B_friction_only`, `force_gt=True`, `map_input=reconstruction`, `depth_delay_ticks=1`, 모델·PPO optimizer·perception·perception optimizer·AdaSmpl·env_state·rng를 확인할 것 (`start_runner.py:608-625`, `sol23f_contract.py:53-78`). 읽는 동안 파일은 수정하지 않는다.

알려진 입력 `model_850.pt`에 이 확인을 CPU에서 적용했다. 파일 24,936,402 byte, 실제 SHA와 manifest SHA가 둘 다 `c8ff98307b3d166917b685c39219f12b4339724851cc5f99b9a7fd12003db5f4`로 일치했다. 저장 `iter=850`, manifest 완료 갱신 851, PPO optimizer state 17개, perception optimizer state 105개, AdaSmpl·환경·RNG 항이 있었다. 이는 **850의 증거**이며 아직 생성되지 않은 model1000의 통과로 대체하지 않는다.

## 가장 작은 안전한 선택

현 코드와 실행 설정을 그대로 두는 조건에서 **model1000으로 판단·촬영하고 현재 학습은 자연 종료까지 두는 것**이 유일하게 확인된 정상 경로다. 팀장이 model1000 직후 추가 학습도 허용하지 않는다면, 현재 실행에서 정상 경계 종료는 불가능하다고 보고 운영 결정을 다시 받아야 한다. 강제 종료를 checkpoint 보존과 혼동하지 않는다. 다음 별도 실행에서는 시작 전에 `--stop-file <전용 경로>`를 명시하고, 완성 checkpoint SHA·manifest를 확인한 후 해당 파일을 생성하면 다음 갱신의 `stopped_saved` 경로가 작동한다. 이것은 현재 PID에는 소급되지 않으며 새 실행 제안이지 승인이나 실제 기동이 아니다.

## 이력

| 판 | 변경 |
|---|---|
| v1.0 | 실제 argv와 고정 코드·model850 CPU 증거로 현재 중단 경로와 한계 확인 |
