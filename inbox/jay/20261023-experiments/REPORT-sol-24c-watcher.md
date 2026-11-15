# SOL-24c B 본학습 임시 CPU watcher

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: sol · 2026-10-24
> 근거: B `process.json` · `manifest.json` 읽기, `run_process_1024.py` 상태 계약, `mai_resume.runner.safe_send` 반환값, CPU 정답 시험
> 요지: 검증된 완료 갱신 경계와 자식 종료를 lead 창에 한 번씩 알리는 임시 watcher를 준비했다.
> 상태: CPU 확인됨 · watcher 미기동 · GPU/Kit 미실행

## 계약

`watch_sol24c_b.py`는 설정에 적힌 B 본학습의 `process.json`과 `manifest.json`만 읽는다. 완료 갱신 100, 200, 500, 1000, 1500과 자식 종료 코드 0 또는 실패를 lead 창에 `mai_resume send`로 알린다. 기존 학습 파일, 소비기, GPU 프로세스를 변경하거나 종료하지 않는다. 이 알림은 중간 분석 요청이며 자동 중단이나 새 학습 명령이 아니다.

경계는 manifest의 `progress.completed_updates`가 해당 값 이상이고 schema, run 이름, 단조 증가, 자식 PID 및 신선한 감독기 heartbeat가 맞을 때만 만든다. 감독기와 manifest가 어긋나면 `state.json`의 `mismatch`에 이유와 관측값을 남기며 경계 알림을 보류한다. 종료 코드 0도 완료 갱신 수가 미확인이면 `종료 관측, 진행 증거 미확인`으로 알린다. 감독기 오류의 자식 상태는 미확인으로 적는다.

원자료 밖의 `state.json`과 OS 잠금 파일이 중복 기동을 막는다. 각 송신 전에 `sending` 의도를 영속 기록하고 반환 코드 0에서만 `sent`로 바꾼다. 코드 4는 상대 입력이 바빠 미송신된 것으로 보고 다음 poll에 재시도한다. 다른 종료 코드, 예외, 송신 도중 재시작은 `uncertain`으로 남기고 자동 재송신하지 않는다. 이는 중복 방지용 보수적 보류이며 사람이 실제 도착 여부를 확인해야 한다. TTL `2026-10-24T22:30:00+09:00`부터 새 알림 없이 종료한다.

## 지정 CPU 확인

`CUDA_VISIBLE_DEVICES=-1`을 둔 `isaac311-moects` Python으로 `python -B -m pytest -q -p no:cacheprovider inbox/jay/20261023-experiments/test_watch_sol24c_b.py`: **14 PASS**. 경계 직전 99에서는 미송신, 다섯 경계의 영속 중복 방지, stale heartbeat, manifest 후퇴, 프로세스 재시작 식별, 코드 4 재시도와 같은 tick의 뒤 경계 보류, 코드 2와 송신 예외의 불확실 보류, 재시작 중간 의도, 종료 증거가 사라졌을 때의 보류, 자연 종료와 실패, 감독기 오류, TTL, OS 잠금, 명령 인자를 답 아는 입력으로 시험했다. Ruff `check --select F` 0건이다.

실제 원자료를 `inspect()`로 읽기만 한 2026-10-24 07:16 KST 표본은 `process_state=running`, `completed_updates=51`, `mismatch=[]`였다. 이것은 그 순간의 정적 확인이며 watcher를 실행하거나 lead에게 알림을 보낸 증거가 아니다.

## root 기동용 구성과 명령

예시 구성은 [watch_sol24c_b.example.json](watch_sol24c_b.example.json)이다. root는 이 JSON을 런타임 디렉터리에 복사해 동적 경로와 대상 창을 확인한 뒤 별도 detached 프로세스로 아래 명령을 실행한다. 이 세션은 실행하지 않았다.

```powershell
& 'C:/Users/AI-WS01/anaconda3/python.exe' -B 'C:/mai/wt/foothold-lab/sol-23a/inbox/jay/20261023-experiments/watch_sol24c_b.py' --config 'C:/Users/AI-WS01/s2_lab/run_20261024/watch_sol24c_b/config.json'
```

기본 송신 명령은 설정의 `sender_python`으로 `-m mai_resume send --to term_d0d6549f-2da1-433c-9d05-58ce534224d7 --text <한 줄> --wait 15`를 실행하며 작업 폴더는 `C:/mai/mai-tools/tools/mai-resume`다. `--once`는 한 번의 읽기와 필요한 알림을 수행하므로 전송 없이 보는 dry run이 아니다.

## 한계

- 반환 코드 0은 `mai_resume`의 전달 성공 보고다. lead가 내용을 읽고 판단했다는 증거는 아니다.
- 송신 의도를 기록한 뒤 watcher가 죽으면 실제 도착 여부를 자동 판별할 수 없다. `uncertain`을 자동 재시도하지 않는다.
- 감독기 heartbeat 허용 나이는 예시에서 120초다. 파일 갱신이 늦으면 실제 학습 진행 중에도 경계 알림이 보류될 수 있다.
- TTL 전에 시작한 `mai_resume send` 호출은 최대 45초 기다릴 수 있다. watcher는 어떤 프로세스도 강제로 중단하지 않는다.
