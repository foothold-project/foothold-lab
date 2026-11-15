> 분류: 운영
> 작성: super2 · 2026-11-08 20:18
> 근거: 실측 (CPU 회귀시험 · 되돌림 시험) · analyst `REPORT-analyst-linux-windows-pins-1108.md` 2 절 · Orca CLI 소스 (`resolveOrchestrationCliExecutable`)
> 요지: 텔레그램 발송 두 곳과 Orca 맨 이름 호출 한 곳을 Windows 가 아닐 때만 바꾸고, 깨지던 반례를 시험으로 고정했다. Linux 실측은 아직 없다
> 상태: 검토중 (lead 병합 대기 · Linux 실측 미확인)

# Linux 전 고칠 곳 (7)(8) · lead 11/08 19:3x 카드

공통: Windows 동작은 바이트 그대로 두고 `sys.platform` / `os.name` 이 Windows 가 아닐 때만 새 길로 간다. 경로는 기기 프로필(`machines/AI-WS01-linux.yaml` 의 `telegram_outbox` · `telegram_script`)에서 온다. 지금 도는 학습 PID 93176 · GPU 배분기 · 감시기 · 운영 사본은 건드리지 않았다. 고칠 때마다 반례 시험을 두고, 고친 줄을 빼면 그 시험이 실패하는지 다시 쟀다.

## 고친 곳 · 시험

| 자리 (근거 줄) | 무엇을 | 가지 · 커밋 | 시험 |
|---|---|---|---|
| mai-tools `tools/tg-send/tg_send.py` (새 파일, 시스템 쪽 발송기) | `tg-send.ps1` 과 같은 계약: outbox(UTF-8) + `.env` 두 줄 → sendMessage(`parse_mode=HTML`) → `sent ok=True` / `FAIL: ...`. 다른 점 하나: 실패면 종료값 1 (ps1 은 실패해도 0). 키는 출력 · 기록에 안 나오고 오류 글에서도 가린다 | `super2/tg-send-py` `083c7d3` | 5 통과 (보낸 내용이 ps1 과 같음 · 실패 1 · ok=false · outbox 없음/빔 · `.env` 줄 빠짐에 키 미노출) |
| `_out/tools/ex41/tg_send.py:17,38` (O) | Windows 가 아니면 프로필의 outbox · 발송기(이 가지엔 machine_profile 이 없어 같은 두 변수 `TELEGRAM_OUTBOX` · `TELEGRAM_SCRIPT`)로 파이썬 발송기를 부른다. 첫 줄 · 15줄 · 되읽기 SHA · `ok=True` 검사는 그대로. `.ps1` 이면 거절 | `super2/linux-pins-ops` `b4095943` | 새 7 통과 · 기존 `test_ops_check.py` 22 통과 · 고친 줄을 빼면 3 실패 |
| `foothold_s2/chain/runner.py:178,186` (S) | `default_tg_sender` 가 Windows 가 아니면 `posix_tg_sender` 로: 설정에 경로가 없으면 `machine_path("telegram_outbox" / "telegram_script")`, C: 기본값으로 안 떨어짐. 성공 = 종료값 0 **그리고** `ok=True` (ps1 의 「실패해도 0」을 성공으로 읽던 구멍이 Linux 에서는 닫힘). `.ps1` 이면 아무것도 안 부르고 False. `ex41_ops._send_telegram` 도 이 함수를 쓰므로 함께 고쳐짐 | `super2/linux-pins-runner` (이 보고와 같은 커밋) | 새 6 통과 · 고친 줄을 빼면 2 실패 · 기존 `test_chain.py` 는 아래 |
| `_out/msgs/inbox_wait.py:20,29` (ML) | Orca 와 같은 순서로 실행기를 고름: `ORCA_CLI_COMMAND` → `ORCA_DEV_REPO_ROOT` 면 `orca-dev` → Linux `orca-ide` → 그 밖 `orca`. Windows 가 아니면 실행기가 없거나 JSON 이 아닐 때 한 시간 기다리지 않고 바로 멈춤. 순번 파일 이름에 호스트 이름을 붙여, 다른 기기에서 복사한 `.inbox_seq` 를 읽지 않음 | `super2/linux-pins-msgs` `7c680d3d` | 10 통과 · 고친 줄을 빼면 3 실패 |
| `_out/msgs/orch_wait.py:3` (MH) | 고치지 않음. 저장소에 없는 lead_tmp 로컬 파일. 런북 L-14 끝에 「Linux 에서 쓰지 않는다 · 대기는 inbox_wait.py」 | 해당 없음 | 해당 없음 |
| mai-os `os/linux-runbook.md` L-14 끝 | 세 줄: (7) 그날 둘 변수와 도착 확인 · (8) 실행기 순서와 `.inbox_seq` 를 복사하지 않음 · orch_wait 쓰지 않음 | mai-os main | 해당 없음 |

**기존 `test_chain.py`:** `test_require_file_holds_the_job_until_the_file_exists` 가 이 기기에서 끝나지 않는다. **고치기 전 원래 커밋 `55060aad` 에서도 똑같이 멈춘다** (120 초 상한, base_rc 143). 그래서 이 변경과 무관한 원래 결함으로 본다. 그 하나를 뺀 나머지는 원래 커밋과 이 가지가 똑같이 43 통과다 (아래 「대조」).

## 남은 Linux 실측 (미확인)

| 무엇 | 어떻게 재나 |
|---|---|
| 발송기가 Linux 에서 폰에 **읽을 수 있는 모양으로** 도착하는가 | `TELEGRAM_OUTBOX=~/.mai/tg/tg-outbox.txt` · `TELEGRAM_SCRIPT=~/mai/mai-tools/tools/tg-send/tg_send.py` 를 두고 `[EX-` 로 시작하는 시험 한 통. 폰 화면을 본다 (`ok=True` 는 확인이 아님). **외부 발송이라 팀장 확인 뒤** |
| 같은 발송기를 Windows 에서 지금 outbox 로 먼저 돌려 같은 모양이 오는가 | 런북 L-11 텔레그램 줄의 순서. 위와 같은 이유로 팀장 확인 뒤 |
| Linux 의 Orca CLI 이름이 실제로 `orca-ide` 인가 · 관리 터미널에 `ORCA_CLI_COMMAND` 가 들어오는가 | 런북 L-14 첫 절 (`command -v orca-ide`, 관리 터미널 환경) |
| 새 호스트의 첫 `inbox_wait.py` 실행이 그 자리의 순번을 새로 잡는가 | Linux 에서 한 번 돌려 `_out/msgs/.inbox_seq.<호스트>` 가 생기는지 |
| `parse_mode=HTML` 에서 `<` 가 든 글 (런북 9 절 「HTML 꺾쇠」) | runner 는 `tg_escape` 로 이스케이프하지만 ex41 `tg_send.py` 는 이스케이프하지 않는다 (Windows 와 같음). 이번 범위 밖이라 그대로 둠 |
| ps1 이 실패해도 종료값 0 인 것 (Windows) | Windows 동작이라 이번에 안 바꿈. runner 는 Windows 에서 여전히 종료값만 본다 |

## 대조

(아래는 원래 커밋과 이 가지에서 같은 명령으로 돌린 `test_chain.py` 결과다. 멈추는 한 시험은 뺐다.)

| 판 | 명령 | 결과 |
|---|---|---|
| 원래 `55060aad` | `python -m pytest -v foothold_s2/tests/test_chain.py --deselect ...::test_require_file_holds_the_job_until_the_file_exists` | 43 passed, 1 deselected (24.97s) |
| 이 가지 | 같은 명령 | 43 passed, 1 deselected (24.95s) |
| 이 가지 | `python -m pytest foothold_s2/tests/test_linux_tg_sender_cpu.py` | 6 passed |
