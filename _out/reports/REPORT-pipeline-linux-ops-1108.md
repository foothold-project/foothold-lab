> 분류: C/운영 · Linux 운영 도구 이전
> 작성: pipeline · 2026-11-08
> 근거: #555 · lead 19:3x 의뢰 · analyst REPORT-analyst-linux-windows-pins-1108 §2~3 · 운영 기준 662f58e7
> 요지: 새 사본의 Linux 운영 경로 단일화, POSIX 프로세스·경로 경계 검증
> 상태: Windows/WSL CPU 시험 확인 · native Linux 전환 미확인 · 운영 사본 전환 안 함

# 결과

작업 가지 `feature/linux-ops-profile-pipeline`는 `lead/ex41-dispatch-on-measure@662f58e7`에서 분기했다. lead 운영 사본은 작업 시작·완료 확인에서 같은 HEAD와 clean 상태였다. 학습 PID 93176, 배분기·감시기·운영 큐·표식은 제어하거나 교체하지 않았다. 새 가지에만 반영하고 병합·설치·재기동하지 않았다.

| 고친 곳 · 근거의 기준 줄 | CPU 시험 | 남은 Linux 실측 |
|---|---|---|
| `dispatch.py:228,236,244,1174` · queue/ledger/results/log/idle/state·학습 및 P1 표식을 Linux machine profile 하나로 선택 | WSL에서 기존 D:/ 기본값을 반환하는 실패 재현. 같은 임시 root를 board·ops_check·lead_rounds가 읽는지 대조. 분리 wrapper가 CPU 자식 종료값과 결과 JSON을 같은 root에 남김 | 실제 mount/권한·표식 생산자와 동일 경로·실제 run stage/eval/ledger를 native에서 대조 |
| `jobs.json:3`의 P1 표식과 등록 경로 · dispatch 및 gpu_jobs의 v2 레지스트리 읽기 | Windows JSON 자체는 보존. Linux gate가 새 위치의 깨진 표식을 두 CLI 모두 읽어 rc3. 이전에는 잘못된 위치를 읽어 rc0 허용. W28 serve의 실제 외부 gate도 같은 표식을 읽고 차단 | Linux 생산자가 쓰는 실제 P1 표식의 PID+생성시각. raw jobs.json만 직접 읽는 구형 도구는 별도 점검 |
| `queue_w28.py:29,185` · Linux 브라우저 실행 이름 | 알려진 chrome compute 행은 데스크톱으로 처리, Python·미확인 이름은 계속 차단. GPU UUID/순위 미변경 | native NVIDIA 프로세스명과 사용량, 오허용·과차단 여부 |
| `dispatch.py:1363,1374` · POSIX wrapper 분리 | 첫 시험에서 start_new_session 인자 없음 재현. 실제 WSL CPU 자식의 SID=wrapper PID, PPID=wrapper PID, 부모 SID와 다름, rc0. profile 교체 뒤 다른 큐의 같은 ID를 실행하는 반례 RED, 부모 SHA와 다르면 실행 전 거절 GREEN | 실제 Orca 터미널 종료·서비스 세션 전환 뒤 생존, Linux native 장시간 운영 |
| `ops_check.py:23,25,271` · queue/표식/WORKLIST · `116,130,164` 경로 신원 | /EX42와 /ex42 및 /EX42-other를 동일 작업으로 잡던 반례를 막음. 학습은 --ex41_log_root, watcher는 --run-dir만 검사. 다른 run의 --score-dir만 같은 반례도 거절. 기존 Windows 시험은 기존 동작 유지 | 운영 프로세스 argv·심볼릭 링크·실제 평가 저장 경로 대조 |
| `lead_rounds.py:20,27,117` · Orca/WORKLIST/queue/retry · `boundary_report.py:13` · m6000 기준표 | 실제 round 함수에 임시 TSV/queue와 가짜 CLI 응답 제공. Linux CLI argv와 두 GPU retry 인자 확인. 미매핑 작업 창은 누락 경고. 실제 경계 보고기가 선택된 baseline을 여는 것 확인 | native Orca 수신함/핸들 계약과 기준표 SHA. 기존 Claude 임시 폴더 canon_retry는 복원한 사본을 명시하고 별도로 검증 |

## 적용 방법

Windows는 기존 설정·명령을 그대로 쓴다. Linux는 `_out/tools/machines/AI-WS01-linux-ops.example.json`을 별도 로컬 파일로 복사하고 `FOOTHOLD_OPS_MACHINE_PROFILE`에 그 파일의 절대경로를 지정한다. `gpu_root` 예시는 `~/mai/tmp/gpu`. 큐·결과·로그·idle·GPU0 학습 및 GPU1 P1 표식은 이 root의 이름으로 함께 파생한다. 다른 항목은 설치 날 승인된 실경로로 채운다. 예시의 EX41-CHECKOUT·EX41-RUN·LEAD-WORKLIST·EX40-BASELINE·LEAD-TOOLS는 실제 위치가 아니다.

Linux에서 dispatch, gpu_jobs, EX-41 점검/보고 CLI 및 W28 GPU serve는 프로필이 없으면 Windows 기본 경로로 진행하지 않는다. 이 운영 프로필은 runner 학습 YAML `FOOTHOLD_MACHINE_PROFILE`의 대체물이 아니다. 의존성을 추가하지 않고 표준 라이브러리로 읽으며, 두 쪽의 물리 GPU와 출력/표식 경로는 실제 기동 전에 대조해야 한다. W28은 별도 큐 형식이므로 `--queue`로 자체 큐를 지정한다. 공통화 대상은 P1 표식이지 서로 다른 큐 파일 형식이 아니다.

runner의 `eval/a_push_video.py:264~265`, `eval/c_layer_queue.py:112~114`는 JSON 원문을 직접 읽는다. 새 운영 CLI의 Linux 경로 해석을 거치지 않으므로 이 두 호출부를 그대로 Linux에서 써도 된다고 보지 않는다. 후자는 Windows 표식 문자열을 강제하는 별도 수정이 필요하며, 영상 plan과 config SHA도 함께 다시 검증해야 한다.

**전환 전 필수:** runner 표식 생산자 `scripts/train_start.py`, `eval/ex41_gpu_priority.py`, `eval/ex41_push250_watch.py`가 선택한 실제 경로와 이 프로필의 경로가 일치하고 P1 표식 쓰기·해제 때 두 gate가 차단·해제를 관측하는지 확인한다. 이 변경은 생산자 코드를 바꾸지 않는다. 실제 생산자가 다른 곳에 쓰면 소비자는 표식 부재를 유휴로 볼 수 있으므로, 함께 확인할 때까지 Linux GPU 배분기를 켜지 않는다.

Linux Orca 명령은 `ORCA_CLI_COMMAND` 우선, 없으면 `orca-ide`. Linux용 작업 창은 실제로 확인한 `worker_handles`, 알림은 검증된 `lead_mailbox`를 입력한다. mailbox null이면 dispatcher 송신은 하지 않는다. 이전 Windows의 PID·lock·대기/실행 큐 항목·절대 argv는 자동 이관하지 않는다. 현재 데이터와 새 설정을 확인하기 전 운영 프로필을 켜지 않는다. 배분기 부모와 wrapper는 동일 profile 원문 SHA를 요구하므로, 운용 중 profile을 덮어써 설정을 전환하지 않는다.

## 검증

- Windows 수정 전 대상 묶음: **149 passed**. WSL 수정 전 추가 반례 7개 실패(경계 기준표 반례는 필요한 score/map64 fixture를 채운 뒤 Windows 경로를 실제로 여는 실패까지 확인).
- WSL 수정 후: **154 passed, 6 skipped**. POSIX에 해당하지 않는 기존 OS별 시험은 skip. 신규 11개 포함.
- Windows 수정 후: **149 passed, 11 skipped**. 신규 POSIX 시험 11개만 skip.
- 읽기 전용 검토에서 POSIX 이름까지 Windows식으로 정규화되던 예외를 발견했다. `Chrome` 반례 RED 후 Linux 분기에서 정확한 basename만 허용, 역슬래시가 실제 이름의 일부인 경우도 차단으로 고정했다.
- 시험 범위: `_out/tools/gpu_jobs`, `_out/tools/ex41/test_ops_check.py`, `_out/tools/tests/test_ops_linux_profile.py`. WSL은 기존 Ubuntu-24.04 CPU deps 재사용. nvidia-smi/Kit/학습·촬영·실제 알림 시험은 하지 않았다.

재실행: 두 OS에서 `python -m pytest -q _out/tools/gpu_jobs _out/tools/ex41/test_ops_check.py _out/tools/tests/test_ops_linux_profile.py -p no:cacheprovider`. 이번 Windows는 isaac311 Python, WSL은 Python3.12 및 기존 CPU deps 경로를 PYTHONPATH에, mai-work 사본을 MAI_WORK_DIR에 지정했다. 실제 운영 프로필이 아니라 pytest 임시 프로필을 썼다.
