> 분류: A/운영 · 자동화 · 깃
> 작성: 오흥재 (runner 반영) · 2026-11-02
> 근거: lead G14 지시 · 07f0d2db · isaac311 CPU 시험
> 요지: EX-40 숨김 자식 프로세스의 stdin 차단과 2단 실제 시험 기록
> 상태: CPU 확인 · Kit/GPU 미실행

# G14 숨김 자식 stdin 보강

## 변경

`ex40_score_watch.py`의 평가 자식과 Telegram sender 호출, `ex40_supervisor.py`의 점수 감시 · 학습 · 재개 사전검사 자식, `ex40_eval_once.py`의 Git 확인 자식 모두에 `stdin=subprocess.DEVNULL`을 명시했다. Telegram sender 자체는 실행하지 않았다.

기존 `07f0d2db`의 `ex40_eval_once._run` 및 shell `sha256sum` stdin 수정은 현재 runner HEAD에 남아 있다. analyst `75df4e87` 파일에는 해당 줄이 없지만 `git merge-tree`로 통합을 미리 계산했을 때 `ex40_eval_once.py`는 충돌 없이 runner 쪽 `07f0d2db` 추가가 남는다. `ex40_supervisor.py`는 별도 내용 충돌이 있어 해결 후 이번 G14 stdin 줄을 보존해야 한다. 실제 병합은 하지 않았다.

## 답을 아는 입력 시험

명령: `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest foothold_s2/tests/test_ex40_no_window_stdio_cpu.py foothold_s2/tests/test_ex41_pose_observation_cpu.py foothold_s2/tests/test_ex41_startup_integration_cpu.py -q`

결과: `16 passed in 6.90s`.

새 2단 시험은 실제 Windows `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP` 플래그로 숨김 부모를 띄우고, 그 부모가 `ex40_eval_once._run`을 통해 다시 숨김 자식을 실행한다. 부모와 자식이 각자 결과 파일을 남기고 종료코드 0을 반환한 것을 확인했다. 별도 AST 관문은 대상 세 파일의 `subprocess.run`, `Popen`, `check_output` 호출에 `stdin=DEVNULL`이 빠지면 실패한다.

## 경계

CPU 프로세스 시험만 수행했다. Kit · GPU · 학습 · 평가 · 외부 알림은 실행하지 않았다. W71 production launch 상태를 바꾸지 않았다.

