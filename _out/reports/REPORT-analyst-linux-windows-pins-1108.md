> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: analyst · 2026-11-08
> 근거: cc7586db 고정 소스 전수 문자열 검색 · 운영 파일 바이트 목록 · CPU 반례 14개
> 요지: OS만 바꾸려면 경로 프로필 외에 실행 영수증 위치, 운영 대기열, GPU 식별, 보고 경로를 함께 옮겨야 한다
> 상태: 읽기 전용 감사 완료 · Linux 및 Kit 실행 미확인 · 구현 수정 없음

# Linux 전환 전 Windows 종속 자리 감사

현재 코드를 그대로 복사해서 Linux에서 같은 운영이 된다고 말할 수는 없다. EX-42 학습 진입점과 EX-41 평가기에는 이미 machine profile이 들어갔지만, 운영 대기열과 영상 계약, 일부 공통 출력 경로에는 Windows 값이 남아 있다. 특히 **같은 체크포인트라도 Windows 실행 폴더가 기록된 manifest를 그대로 복사하면 EX-42 자기 이어 가기가 거절된다.**

이번 결과는 **코드와 CPU 반례에 근거한 이전 점검표**다. Linux 실행 성공이나 학습 결과 동등성을 확인한 보고서가 아니다. `cuda:0/1`, Windows 실행 플래그, 역슬래시가 검색됐다는 이유만으로 결함으로 세지 않았다. 실제 분기와 소비 경로를 아래에서 구분했다.

## 1. 범위와 판본

| 표기 | 읽은 대상 | 고정 방법 |
|---|---|---|
| S | `D:/mai-wt/foothold-lab/runner-ex42-resume-w65/foothold_s2` 전체 | `git archive cc7586db9f58b4bf43ef2ce5658e40bede3e7003 foothold_s2`의 바이트. 움직이는 작업 파일을 감사 기준으로 쓰지 않음 |
| O | `D:/mai-wt/foothold-lab/lead-dispatch-measure/_out/tools/gpu_jobs`, 같은 자리 `ex41` | 운영 사본 HEAD `662f58e76647dd67af594fcd1f6f502354cec287`, 파일별 SHA256 목록 |
| ML | `D:/mai-wt/foothold-lab/lead-worklist-1103/_out/msgs` | 현재 lead의 메시지 도구 |
| MH | `C:/mai/wt/foothold-lab/lead_tmp-20261023/_out/msgs` | 기존 lead_tmp 메시지 도구와 과거 생성기 |

요청한 runner와 lead-dispatch-measure에는 `_out/msgs`가 없어서 ML·MH 두 실제 위치를 함께 조사했다. 다른 메시지 도구 사본까지 조사했다는 뜻은 아니다. 표의 `S/...:줄`은 **foothold_s2 아래 상대 경로**, `O/...:줄`은 **_out/tools 아래 상대 경로**다. 모든 정확한 파일·줄은 [검색 후보 CSV](linux-pins-1108/candidates.csv)에 있다.

감사 도중 runner HEAD가 `55060aad2f9862bf5a64327d1897911ae905db1a`로 바뀐 것을 읽어서 확인했다. 이 후속본은 EX-42 0단계 학습 장치를 `cuda:1`에서 `cuda:0`으로 바꾸고 관련 시험을 고쳤다. **아래 전수 집계는 의뢰한 cc7586db 그대로**다. GPU 행에는 이 후속 변경을 별도로 표시한다.

관련 사고 방지: FAILURE-LOG **M21**에 따라 전수의 검색식·제외 대상·목록을 남겼다. **R6**에 따라 Linux/Kit 실행을 CPU 확인으로 대신하지 않았고, **M14**에 따라 검색망에 답을 아는 입력을 먼저 넣었다. 실행·운영 사본, 원장, 프로세스, GPU는 변경하지 않았다.

## 2. 이전 전에 함께 정해야 하는 자리

`있음`은 가중치가 반드시 달라진다는 뜻이 아니다. 학습 기동, 평가 자료, 승급 근거, GPU 배타 사용 또는 무인 운영의 동일성을 깨뜨릴 수 있다는 뜻이다. 담당은 현재 파일 소유에 따른 수정 제안이며 새 작업 지시가 아니다.

| 파일:줄 | 무엇이 묶였나 | Linux에서 어떻게 깨지나 · 닫는 방법 | 고칠 주인 | 실험 결과 영향 |
|---|---|---|---|---|
| **S/scripts/ex42_training_entry.py:116** | manifest의 `run.log_dir`와 현재 checkpoint 부모를 절대경로로 대조 | Windows `C:/...`는 POSIX에서 절대경로가 아니다. 복사 후 경로가 달라 동일 run 검사가 거절된다. 원본 manifest·checkpoint SHA를 보존하는 **이전 영수증과 위치 재연결**이 필요하다. 경로를 조용히 전부 치환하면 안 된다 | runner · pipeline | **있음**, 이어 가기 차단 |
| **S/machine_profile.py:29,59,79** | Linux 프로필 명시 선택, 27개 환경변수 참조 | `FOOTHOLD_MACHINE_PROFILE`이 없으면 즉시 거절. `machines/AI-WS01-linux.yaml`의 필수 7개 외 선택 경로 20개도 값이 없으면 거절한다. 선택 경로에 `D:/...`를 넣으면 현재는 통과하므로 Linux 절대경로까지 별도 확인 필요. CPU로 세 경우 재현 | runner · pipeline | **있음**, import/기동 차단 또는 잘못된 출력 위치 |
| **O/gpu_jobs/dispatch.py:228,236,244,1174** · **O/gpu_jobs/jobs.json:3** | 학습·평가 표식, queue/ledger/results/log/idle 파일, 기존 EX-41 run의 C:/D: 기본값 | 없는 경로를 읽거나 작업 폴더 밑 `D:` 디렉터리를 쓸 수 있다. 학습 중인데 유휴로 읽거나 반대로 평가가 영원히 대기할 위험. Linux용 queue/config와 실제 표식의 경로를 하나로 고정해야 함 | lead 운영 도구 · runner | **있음**, 평가 누락·중복 점유·잘못된 상태 보고 |
| **S/eval/c_layer_queue.py:91,114,118** | P1 표식 문자열이 `D:/mai-tmp/gpu/PRIORITY_BUSY_GPU1`와 정확히 같아야 함. runtime source 목록의 키도 절대경로 | Linux 경로로 바꾸어도 114줄에서 거절된다. marker 계약을 Linux 프로필과 맞추고, 영상 plan의 경로·해시 영수증을 새로 발행해야 함. 원본 plan 보존 | scripter · runner | **있음**, C층 촬영 사슬 차단 |
| **S/scripts/ex42_training_entry.py:26,49** · **S/ex42_chain.py:315** · **S/experiment_registry.py:24** · **O/gpu_jobs/queue_w28.py:27,134** | 학습·평가 ordinal 및 두 GPU UUID의 대응이 고정 | cc7586db는 학습 cuda:1, P1 대기열도 gpu=1. 후속 **55060aad는 학습 cuda:0으로 수정됨을 확인**. 그래도 Linux에서 ordinal·UUID·PCI bus·Kit 렌더 장치의 실제 대응을 재야 한다. 16GB 두 장의 역할이 바뀌면 OOM·중복 점유가 가능. UUID 값 자체는 OS가 바뀐다고 반드시 바뀌는 값이 아님 | runner · pipeline | **있음**, 자원 충돌·처리량·평가 누락 |
| **O/ex41/ops_check.py:23,25,271** · **O/ex41/boundary_report.py:13** · **O/ex41/lead_rounds.py:20,27,117** | queue·학습 표식·WORKLIST·m6000 기준표·Orca bin·옛 Claude job 스크립트의 고정 경로 | 프로세스가 돌아도 점검기는 이전 자료를 보거나 파일을 못 찾는다. 학습 경로만 옮겨서는 감시·경계 보고가 이어지지 않음. 새 run 기준표와 코드 SHA를 유지하며 운영 도구 설정을 분리 | lead 운영 도구 · pipeline | **있음**, 기준 비교와 무인 점검 단절 |
| **O/ex41/tg_send.py:17,38** · **S/chain/runner.py:178,186** | C: outbox·`.ps1`·`powershell` 실행 | Linux에 같은 이름의 실행 파일과 스크립트가 없으면 통보 실패. `pwsh` 이름만 바꾸는 것으로 메시지 경로·반환 계약까지 보장되지 않음. 시스템의 Linux 송신기로 연결하고 실제 도착 확인 필요 | super2 · pipeline, 연결 runner | **있음**, 실패 알림·운영 대응 누락. 학습 수학 직접 변경 없음 |
| **ML/inbox_wait.py:20,29** · **MH/orch_wait.py:3** | bare `orca`와 `.inbox_seq`, 과거 run/handle에 기대는 호출 | Linux의 Orca 비관리 터미널에서 `orca`는 GNOME 화면 읽기 도구일 수 있다. 설치된 Orca CLI 계약의 `ORCA_CLI_COMMAND`/`orca-ide`를 확인해야 한다. 새 호스트의 수신함 sequence/run을 확인하지 않고 상태 파일을 복사하면 새 메시지를 건너뛸 수 있음 | super2 · pipeline | **있음**, 지시·보고 경로 단절 |

첫 행은 단순한 코드 위치 변경 문제와 구분해야 한다. **S/runners/manifest.py:280**에는 기존 imported source 기준선을 보존하며 새 소스 경로를 기록하는 `rebase_files_for_resume`가 이미 있다. 하지만 이것이 **앞서 수행하는 run.log_dir 검사**를 통과시켜 주지는 않는다. 새 운영 사본의 경로와 checkpoint 내용 동일성을 함께 입증하는 이전 절차가 필요하다.

## 3. 해당 도구를 Linux에서 계속 쓸 때 고칠 자리

| 파일:줄 | 무엇이 묶였나 | Linux에서 어떻게 깨지나 · 적용 범위 | 고칠 주인 | 실험 결과 영향 |
|---|---|---|---|---|
| S/scripts/ex41_startup.py:242,257,293,610 | D: rehearsal·C: production/smoke 강제 | 실제 `_require_d_drive`에 `/data/...`를 넣으면 거절. production 경로 함수는 None을 반환하며 `:290` 점수 출력은 `run/shadow-score-watch`로 바뀐다. **EX-41 기동/공통 출력 helper를 재사용할 때** 문제이며 EX-42 본류가 무조건 이 검사로 죽는다고 단정하지 않음 | runner | **있음**, 재생산·평가 폴더 계약 |
| S/ex40_eval_once.py:24,40 · S/basic_gait_chain_plan.py:14 · S/basic_gait_eval_once.py:61 · S/window2_gate.py:26 | `C:/...python.exe`, Git Bash 기본값 | 해당 구형 평가·실행기를 호출하면 실행 파일 부재로 거절. EX-41 최신 평가기는 `machine_path('conda_python')`와 Python 모듈 직접 실행을 쓰므로 별개. 역사 재평가용 실행기까지 쓰려면 이관 필요 | runner | **있음**, 과거 대조 평가 재현 |
| S/eval/run_kit.sh:6,15 · S/run_axis_v2.sh:13,30 · S/run_eval_map_modes.sh:6,18 · S/run_terrain_skill.sh:13,30 · S/run_s2_x23.sh:7,17 외 | `/c/...`, Windows conda `Library/bin`, `Scripts`, `python.exe` | MSYS의 `/c` 매핑은 일반 Linux `/c`가 아님. 이름만 .sh라서 이식된 것은 아니다. 전체 해당 파일·줄은 후보 CSV에 포함. 현행 Python 모듈 경로로 통합하거나 별도 Linux 실행기를 사용 | runner | **있음**, 과거 학습·평가·촬영 경로 |
| S/basic_gait_kit.py:3 · S/run_axis_v2.sh:35 · S/run_terrain_skill.sh:35 | Kit cache `D:/mai-cache/...` | 구형 cache 인자를 소비하면 무효/상대경로 또는 쓰기 실패 가능. 최신 프로필 cache 소비 여부를 기동 영수증에서 확인. **실제 Kit 오류 형태는 미확인** | runner · pipeline | **있음**, 기동·시간·디스크 |
| S/chain/runner.py:31,35 · S/chain/chain_s1a_night.yaml:11 | Bash 후보가 Windows 경로뿐, 옛 yaml의 실행 경로 | Linux에서는 `FOOTHOLD_BASH=/실제/bash`를 명시하지 않으면 탐색 실패. shell과 yaml의 경로를 함께 이전 | runner | **있음**, 구형 자동 사슬 |
| S/launch_ex3031_window1.py:59 | `subprocess.CREATE_NO_WINDOW`를 무조건 참조 | POSIX subprocess에는 해당 상수가 없어 AttributeError. **EX-30/31 구형 실행기**에서만 직접 확인한 문제. Windows 분기 필요 | runner | **있음**, 해당 재현 기동 실패 |
| S/eval/ex35_eval_chain.sh:22 · ex35_eval_chain2.sh:29 · post_train_eval2.sh:27 · S/run_ex35_chained.sh:21,81 | PowerShell `Get-CimInstance`, `taskkill` | Linux 명령/프로세스 API가 달라 해당 감시·종료 절차 실패. 이 감사에서 종료 실행은 하지 않음 | runner | **있음**, 구형 사슬 종료/감시 |
| O/ex41/launch_ex41r.ps1:7,19,26 | C:/D:·`Start-Process -WindowStyle Hidden`·python.exe | Windows 시작 스크립트를 그대로 실행할 수 없음. 학습 인자는 보존하고 POSIX 시작·로그·세션 분리 장치 필요 | runner · pipeline | **있음**, 학습 시작과 장기 생존 |
| S/eval/ex41_push250_watch.py:53,188 | psutil 접근 실패 때 `tasklist` fallback | Linux에 tasklist가 없으면 현재 FileNotFoundError가 밖으로 나감. **접근 실패 조건에서** 발생. 추출한 실제 함수에 missing-command 반례로 확인 | runner | **있음**, 밀기 평가의 자원 입장 검사 |
| O/gpu_jobs/queue_w28.py:29,185 | desktop 허용 이름이 `chrome.exe` 등 Windows 이름뿐 | 같은 compute 행에서 chrome.exe는 유휴, Linux chrome은 busy. 실제 함수 CPU 반례 확인. Linux에서 그런 compute client가 나타나는지는 미측정. 무턱대고 모든 GUI를 허용할 일은 아님 | lead 운영 도구 · pipeline | **있음**, 평가가 계속 대기할 가능성 |
| O/gpu_jobs/dispatch.py:1363,1374 | Windows는 분리 플래그, POSIX는 flags=0이나 새 session 없음 | `creationflags=0` 자체는 오류 아님. 다만 Linux에서 터미널 세션 종료 후에도 산다는 보장이 부족. SIGHUP 처리·service/session 관리 실측 필요. **S/chain/runner.py:112**의 `start_new_session=True`와 구분 | lead 운영 도구 · pipeline | **있음**, 무인 사슬 생존 가능성 |
| O/ex41/lock_checkout.py:31 | `S_IWRITE`만 제거해 읽기 전용 사본을 주장 | POSIX 0664 입력이 0464가 되어 group write가 남는다. 또 디렉터리가 쓰기 가능하면 읽기 전용 파일도 교체 가능. 파일 쓰기 방지와 원천 불변 감시는 별개. 권한/마운트/해시 장치를 함께 검토 | lead 운영 도구 · pipeline | **있음**, 실행 중 소스 변경 방지 |
| O/ex41/ops_check.py:116,130,164 · S/eval/video25/record_c_layer.py:503,1020 | 경로를 `.casefold()`로 비교 | POSIX에서 `/runs/EX42`와 `/runs/ex42`는 다른 경로인데 같게 취급. 점검기와 일부 구형 영상 source profile에서 잘못된 신원 연결 가능. 파일 동일성은 실제 resolve·파일 identity로 확인 | 운영 도구 · scripter | **있음**, 다른 run/영상 오인 |
| S/eval/record_clip.py:93 · S/eval/video25/record_25e_x28.py:1269 외 | Windows Fonts 절대경로 | fallback 없는 구형 촬영은 폰트 로드 실패. `record_c_layer.py:1827`와 compose v9/v10은 기본 폰트 fallback 있음. 다만 한글·크기·배치 동일성은 미확인 | scripter | **없음**, 물리·정책 수치 직접 영향 없음. 영상 증거 생산·가독성 영향 있음 |
| MH/msgs_0120.py:2 · msgs_0155.py:2 · msgs_0215.py:2 | 과거 메시지 파일 출력 위치 C: | Linux에서 재실행하면 잘못된 출력 위치/파일 부재. edit_hub/edit_agenda의 일부 C:는 문서에 삽입하는 과거 인용이라 실행경로 아님. 현재 운영에서 이 옛 생성기를 부르는지는 미확인 | lead 운영 도구 | **없음**, 사용 중이 아니면 영향 없음. 재사용 시 보고 생성 영향 |

## 4. 검색됐지만 곧바로 결함이라고 할 수 없는 것

| 범주 · 근거 | 확인한 것 | 남은 현장 확인 |
|---|---|---|
| msvcrt · O/gpu_jobs/queue_w28.py:49,68 | Windows는 msvcrt, POSIX는 fcntl.flock으로 갈라짐. Linux에 msvcrt가 없어 전체 queue가 import 실패한다는 주장은 틀림 | Linux 실제 저장 매체에서 두 프로세스 동시 claim 시험. 이번 감사에서는 실행 안 함 |
| Windows shared-read · O/gpu_jobs/dispatch.py:45,55 | Win32 파일 공유 함수는 Windows에서만 사용, POSIX는 일반 읽기 | Linux 실행 중 JSON 교체/읽기 경계의 실제 영수증 |
| 숨김 플래그 · S/ex40_score_watch.py:145,432 · ex40_stage_publish.py:207 · ex41_eval_once.py:114 | `getattr(subprocess, ..., 0)` 패턴은 POSIX에서 0. 이 사실만으로 오류가 나지 않음. DEVNULL도 POSIX에서 사용 가능 | 장기 프로세스 독립 생존은 별도. 모든 flags 사용이 안전하다는 뜻 아님 |
| 구분자 · S/chain/runner.py:463 · S/eval/c_layer_queue.py:49 | PYTHONPATH를 os.pathsep로 연결. Windows `;`를 POSIX에도 강제하는 코드가 아님 | 큐에 이미 저장된 argv/cwd는 JSON 데이터이므로 별도 이관 |
| 줄끝 · S/curriculum/continuous.py:42 · ex42_prep.py:140 · S/ex42_gate_checks.py:144 | 일부 정본 해시는 CRLF를 LF로 정규화. 이번 git blob의 678개 텍스트는 모두 CRLF 0. O/ML/MH의 CRLF Python/JSON 파일도 그 자체가 Linux 오류는 아님 | Windows working tree는 core.autocrlf=true. 원본 raw SHA 영수증까지 LF 파일로 바꾸면 해시는 달라짐. raw hash와 normalized hash 계약을 구별해 복사해야 함 |
| 실행 권한 · git ls-tree의 .sh 51개 | 51개 모두 100644. `bash script.sh`는 실행 비트 불필요. `./script.sh`를 새로 쓰면 권한 오류 | Linux 시작 명령에서 실제 호출 형태 확인. 이번에 chmod하지 않음 |
| 대소문자 파일명 · inventory | 조사 목록에서 casefold 후 겹치는 상대 파일명 0쌍 | 외부 USD/URDF, 설치 패키지, runtime data의 참조 철자까지 검증한 것은 아님 |
| `cuda:0/1` · S/runners/devices.py 및 장치 계약 | CUDA 번호 문법 자체는 Windows 전용이 아님. CPU 텐서를 GPU에 고정 배치한 코드와 CLI 기본값·예제는 별개 | PyTorch ordinal과 Kit graphics/physics 및 nvidia-smi UUID를 같은 영수증으로 대조 |
| Windows 소스 인용 · S/tasks/s2_x17_cfg.py:3 등 | 과거 env.yaml의 경로를 docstring으로 인용. 실행 시 그 파일을 여는 코드가 아님 | 역사 출처는 보존. 이식한다고 이런 기록 경로까지 삭제하지 않음 |

**코드에 안 보이는 이사 대상도 있다.** queue JSON의 argv/cwd/done_file, 점수·영상 plan과 영수증, m3u8 절대경로, pid 표식은 이 코드가 소비하는 외부 데이터다. 이번 요청 범위의 실행 중 데이터 전체를 훑거나 바꾸지는 않았다. 새 Linux run이 Windows PID/lock/미완료 queue 항목을 그대로 유효하다고 받아들이지 않는지 별도 이전 확인이 필요하다.

## 5. 전수 검색의 뜻과 재현 방법

전수는 **아래 판별식에 대해 대상 파일을 빠짐없이 훑었다**는 뜻이다. 모든 운영체제 차이를 정적으로 증명했다는 뜻이 아니다. 정규식은 주석·시험·과거 원자료까지 넓게 잡아 거짓 양성이 있고, 최종 위험 판단은 위 표처럼 실제 분기를 읽어 했다.

먼저 `S/basic_gait_chain_plan.py:14`의 알려진 `C:/...python.exe` 한 줄을 Python 검색기와 독립 `git grep`으로 잡는지 확인했다. 13개 범주별 답을 아는 입력과 URL 음성 대조도 통과했다. 검색기에서 C:/ 판별식을 없애면 이 제어 입력을 통과할 수 없다. 그 뒤 본 검색을 수행했다.

```powershell
git -C D:/mai-wt/foothold-lab/runner-ex42-resume-w65 grep -n -I -P '(?i)(?<![A-Za-z0-9_])[a-z]:[/\\]' cc7586db -- foothold_s2/basic_gait_chain_plan.py
```

모든 판별식은 [patterns.txt](linux-pins-1108/patterns.txt)에 한 줄씩 있다. 파일 목록은 [inventory.json](linux-pins-1108/inventory.json), 결과 행은 [candidates.csv](linux-pins-1108/candidates.csv), 파일별 요약은 [CANDIDATE-INDEX.md](linux-pins-1108/CANDIDATE-INDEX.md)다. CSV는 소스 내용을 복제하지 않고 파일·줄·역할·범주만 남긴다. `rg -n -I --pcre2 -f patterns.txt <범위>`로 같은 판별식을 쓸 수 있다. 단, 움직이는 worktree와 고정 git blob은 줄끝·판본이 다를 수 있으므로 이번 기준은 아래 스크립트다.

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe _out/reports/linux-pins-1108/scan.py
& C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe _out/reports/linux-pins-1108/probes.py
```

각 스크립트는 D:/mai-tmp/analyst/linux-pins-1108에 감사 자료만 쓴다. 모델·Isaac·운영 실행기를 import하거나 실행하지 않는다. probes는 순수 profile 코드와 필요한 함수만 AST로 추출해 실행한다. **14 PASS는 문제 재현/안전 분기 확인이 맞았다는 뜻이며 Linux 이식 14개가 통과했다는 뜻이 아니다.**

현장에서는 먼저 프로필·실제 Python/RSL-RL 위치와 API, checkpoint/manifest 이전 영수증, GPU 역할, 큐·표식·평가 출력·알림 도착을 각각 대조해야 한다. 그 다음 승인된 같은 입력의 짧은 학습·평가·영상 확인으로 Windows 기준과 비교할 수 있다. 이번 감사는 그 실행을 승인하거나 대신하지 않는다.

<!-- GENERATED-INVENTORY -->

## 6. 자동 집계와 증거

검색 시각: **2026-11-08T18:58:25.801240+09:00**. 줄 번호는 `rg -n`과 같은 LF 물리 줄 기준이다.

| 범위 | 목록 파일 수 | 검색한 텍스트 파일 수 |
|---|---:|---:|
| S | 680 | 678 |
| O | 28 | 18 |
| ML | 1 | 1 |
| MH | 57 | 17 |
| 합계 | 766 | 714 |

제외: binary 2개(ONNX·NPZ), 메시지 payload/상태/이미지 40개, pytest cache 10개.
`__pycache__` 디렉터리는 생성물이라 처음부터 대상 목록에서 제외했다.
키·토큰 값, 메시지 본문은 산출물에 싣지 않았다. 소스 전체 snapshot은 scratch에만 있다.

**2335개 일치 줄 · 419개 파일**이다.
역할별 일치 줄: runtime/config 1285,
test 938, doc 24,
historical-result 88.
이 숫자는 결함 개수가 아니다. 한 줄이 여러 범주에 걸릴 수 있어 아래 합계는 중복된다.

| 판별 범주 | 일치 줄 수 |
|---|---:|
| drive | 389 |
| gpu | 560 |
| exe | 150 |
| separator | 958 |
| winenv_binary | 24 |
| winapi | 84 |
| permissions | 14 |
| shell | 16 |
| line_encoding | 287 |
| casefold | 112 |
| msys | 48 |
| drive_guard | 5 |
| lock | 17 |

검색망: 범주별 제어 입력 13개 통과 · 알려진 실제 C:/ 줄 통과 · URL 음성 대조 통과.
순수 CPU 반례: **14 PASS**. [probes.json](linux-pins-1108/probes.json)에 실제 관측값을 남겼다.
파일명 대소문자 충돌 0쌍, undecodable 텍스트 0개, git .sh 51개 모두 100644.
Linux·Kit·GPU 시험 0회. 학습 및 운영 파일 수정 0건.

수정 재감사는 고정 HEAD와 새 Linux 프로필/실행 명령을 받은 뒤 위 표의 해당 행을 닫는 방식으로 하면 된다.
이 보고서의 전체 문자열 일치를 0으로 만드는 것이 목표는 아니다. 역사 기록과 Windows 지원 분기는 남아도 된다.
