> 분류: A/정책학습 · 독립 hard deadline watchdog (lead 작성 · 0 단계 무인 단회용)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 07:0x
> 근거: ASTRA 17w 3 절 (무인 단회는 독립 마감 장치가 먼저) · `s2_step4a2` 의 `s2_zero_supervisor.py` (하트비트 `heartbeat_epoch` · Job Object KILL_ON_JOB_CLOSE)
> 요지: 감독기와 별개인 분리 프로세스가 감독기를 (pid, 생성 시각) 으로만 식별하고, 하트비트 정지 또는 절대 마감 초과 때 그 감독기 하나만 종료한다. 감독기가 죽으면 Job 핸들이 닫혀 OS 가 소유 가족을 종료한다
> 상태: CPU 시험 13 PASS · 코드 변이 4/4 CAUGHT · 실제 감독기와 Isaac 은 미연결 · ASTRA 17x 에 추가 검토 요청

# 파일
- `s2_hard_watchdog.py` 감시기. 종료 코드 0 (감독기가 스스로 끝났거나 이 감시기가 끝냄) · 2 (종료 실패) · 3 (식별 불일치, 아무 것도 건드리지 않음) · 4 (인자 오류).
- `s2_launch_stage0.py` 감독기와 감시기를 이 터미널과 분리해(DETACHED) 띄우고 감독기 pid 와 생성 시각을 기동 직후 기록해 감시기에 넘긴다. 곧 종료한다.
- `test_s2_hard_watchdog.py` 13 PASS: 건강한 감독기는 건드리지 않음 · 하트비트 정지 시 이유 `heartbeat_stale` 로 종료 · 하트비트가 신선해도 절대 마감에 종료 · 생성 시각이 다르면 거절하고 아무 것도 종료하지 않음 · 상태 파일이 끝내 없으면 시작 유예 뒤 종료 · 과거 마감은 인자 오류 · 기동기가 사라진 뒤에도 감시기가 살아 있다가 멈춘 감독기를 종료 · 무관한 대조 프로세스(decoy)는 모든 시험에서 그대로.
- `test_s2_hard_watchdog_mutants.py` 코드 변이 4: `identity_check_disabled` · `heartbeat_stale_disabled` · `hard_deadline_disabled` · `kill_call_removed` 모두 정상 복사본이 먼저 통과하고 변이의 첫 `FAIL` 이 want 와 같을 때만 CAUGHT.

# 정직한 기록
- 변이 첫 실행은 3/4 였다. `heartbeat_stale_disabled` 의 want 라벨을 시험에 「종료 이유 검사」 를 더하기 전의 라벨로 적어 두어 첫 FAIL 라벨이 달랐다(NOT_CAUGHT). 변이가 놓친 것이 아니라 lead 가 want 를 잘못 지정한 것이라 want 를 이유 검사 라벨로 정정하고 다시 돌려 4/4 를 얻었다.
- 이 감시기는 Windows 의 psutil 로만 시험했다. 감독기를 종료해 Job 핸들이 닫히면 자식 가족이 끝난다는 것은 1 단계 감독기의 `KILL_ON_JOB_CLOSE` 에 의존하며 이 시험에서는 실제 Job 자식으로 확인하지 않았다(가짜 감독기만 사용).
- 감시기 자신이 죽으면 마감 장치가 없다. 감시기 둘을 쓰는 안은 하지 않았다.
