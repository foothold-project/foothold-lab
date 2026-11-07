> 분류: C/운영
> 작성: Codex runner · 2026-11-06
> 근거: EX-42 v0.16 · D182 · W20/W19 · W51 체인 2ad96345
> 요지: W51 체인 기준 EX-42 예행 준비 명령 · 단계별 증거 · fail-closed 조건
> 상태: 계획안 · Kit 호출자 미연결 · 실행 승인 아님

# EX-42 단축 Kit 예행 계획

## 2026-11-07 갱신 · W24 실행 준비 기준

이 절이 이전 초안의 실행 관련 내용을 덮어쓴다. 기준 체인은 W51 통합 커밋 `2ad96345478d73d65c973c982985b3fde7fe8370`이며 부모는 `0e2ecab02692dfa2ef595e0984019224d817cbca`다. lead가 전달한 깨끗한 사본 결과는 41 passed이나, 여기서 다시 실행하지 않았으므로 전달된 시험 결과로만 기록한다.

`2ad96345`의 `EX42TrainingChain`은 `StartRunner` 경계에서 업데이트 전 `on_runner_update_start`, 모델과 manifest 저장 직후 `on_checkpoint_saved`를 부를 수 있고, P1 등록은 dispatcher `queue_cmd`를 사용한다. P1 등록 오류는 retryable 영수증/경보로 격리된다. 그러나 이 커밋에도 `train_start`가 체인을 만들고 `attach_ex42_training_chain()`에 전달하는 호출자는 없다. `preparation_only`도 유지된다. 따라서 아래 명령은 실제 Kit 시작 명령이 아니다. 현 HEAD로 실행 가능한 정확한 명령은 CPU 사전점검뿐이며, Kit 실행 argv는 실제 호출자와 승인된 런타임 경로가 생길 때까지 미정으로 둔다. 이를 임의 명령으로 채우거나 dispatcher에 넣지 않는다.

OS/런타임 결정이 난 날의 첫 명령은 다음 CPU 사전점검이다. 환경 변수는 그 PowerShell 세션 안에서만 설정한다.

```powershell
$repo = 'D:/mai-wt/foothold-lab/runner-ex42-v016'
$src = 'D:/mai-wt/foothold-lab/ex42-rehearsal-2ad96345'
$head = '2ad96345478d73d65c973c982985b3fde7fe8370'
git -C $repo worktree add --detach $src $head
$env:FOOTHOLD_MACHINE_PROFILE = 'machines/AI-WS01-windows.yaml'
$env:TEMP = 'D:/mai-tmp/runner'
$env:TMP = 'D:/mai-tmp/runner'
git -C $src status --porcelain
if ((git -C $src rev-parse HEAD).Trim() -ne $head) { throw 'Pinned rehearsal HEAD mismatch' }
if (git -C $src status --porcelain) { throw 'Pinned rehearsal worktree is dirty' }
& "$src/foothold_s2/run_ex42.ps1" -Mode ops-check -Exp EX-42 -SourceRoot $src -ExpectedHead $head
```

이 명령의 모든 blocker가 0이 된 뒤에만 CPU 계획 검증 명령을 실행한다. 예시 시각은 새롭고 비어 있는 출력 경로로 바꾼다. 11단계 길이는 격리된 예행 오버라이드이며 운영표에는 쓰지 않는다.

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$out = "D:/mai-tmp/runner/ex42_rehearsal_$stamp"
& "$src/foothold_s2/run_ex42.ps1" -Mode rehearsal -Exp EX-42 -SourceRoot $src -ExpectedHead $head -RehearsalOutput $out -RehearsalStageUpdates @(10,10,10,10,10,10,10,10,10,10,10)
```

현재 구현에서는 두 번째 명령도 `rehearsal_plan_only`이며 `rehearsal_runtime_not_integrated` blocker를 내는 것이 맞다. 이를 Kit PASS로 해석하지 않는다. Kit 실행에 필요한 별도 dispatcher 명령은 아직 만들 수 없다. 먼저 `train_start`가 승인된 실험 정의를 읽어 체인을 구성·연결하고, 실제 Kit entrypoint 및 단계 끝 evaluator/renderer argv를 제공해야 한다. 연결 이후에는 이 명령들의 argv를 dispatcher 큐 `D:/mai-tmp/runner/ex42-rehearsal-queue.json`에 P4 · 승인 필요 항목으로 넣고, 별도의 lead 승인 없이는 dispatcher를 실행하지 않는다.

### 실행 전 정지 조건

- 고정 HEAD가 다르거나 worktree가 dirty, Python/Isaac 기기 프로필이 미확정, 출력 폴더가 이미 존재하면 여기서 중단한다.
- `ops-check`에 blocker가 하나라도 있거나 `preparation_only`가 아닌 승인 없는 상태이면 중단한다. blocker가 없어도 실제 Kit caller가 아직 없으면 queue item을 만들지 않는다.
- 승인 후 단계별 실행에서 부모 checkpoint SHA, stage ID, DR=1.0 승인값, 저장된 `model_N.pt`와 manifest SHA 중 하나라도 어긋나면 해당 예행을 실패로 기록하고 성공 판정을 하지 않는다.
- 기술적 평가 실패는 retryable/measurement-gap으로 분리한다. 학습을 안전하게 계속할지에 관한 구현 계약을 바꾸거나 임의로 프로세스를 종료하지 않는다. 무결성/체크포인트 오류는 이후 단계 검증을 중단하고 기록을 보존한다.
- GPU/Kit 실행은 OS 결정 뒤에도 lead가 별도 승인하고 P4 queue item을 검토하기 전에는 하지 않는다.

### 단계별 기대 산출물

모든 산출물은 예행 ROOT 아래에 둔다. 계획상 필요한 증거를 적었다. 실제 실행에서는 caller 연결 후에만 산출되며, 아직 미연결 항목은 완료로 치지 않는다.

| 단계 | 계획상 필요한 증거 · 현재 미연결 여부 | 수용 확인 |
|---|---|---|
| `EX42_0_T0_prime` | `train_start_status.json`, `manifest.json`, `model_N.pt`, 부모 SHA와 첫 상태 기록 | 첫 update, 부모 SHA, 승인 DR 1.0, 파일 SHA/manifest 항목 일치 |
| `E0` ~ `E6b` 각 경계 | `ex42_application.jsonl`의 transition 행, 저장 후 P1 등록 행, dispatcher queue의 checkpoint SHA/iteration. P1 hook은 체인 attach 때만 동작하고 실제 caller는 미연결 | 적용 stage ID와 P1 checkpoint가 같은 경계인지 대조 |
| 각 stage 종료 | `stage_reports/<stage_id>_<iteration>.json`, 해당 `components/` 영수증, 경계 checkpoint 및 manifest. 자동 등록 caller 및 component 생산자는 미연결 | 모든 필수 component가 실제 영수증으로 채워졌는지 확인 |
| 실패 주입 경계 | retry 시도/실패 또는 측정 공백 영수증과 alert 결과 | 학습 진행과 실패 격리가 계약에 맞고 실패 측정값이 점수로 오인되지 않는지 확인 |
| 마지막 `E6b` | 종료 상태와 최종 manifest/checkpoint SHA | 정확한 종료 stage 및 결과 ROOT 확인 |

현재 `EX42TrainingChain`의 stage report는 다섯 구성요소(`number`, `terrain`, `w78`, `video_sample`, `video_delivery`)를 요구한다. `train_start` 연결과 component 생산자들이 실제 실행 가능한지 확인되기 전에는 이 표를 실제 산출 완료로 간주하지 않는다.


## 목적과 고정 입력

이 예행은 실제 학습 성능을 평가하지 않는다. 단계 연결, 경계 점수 요청, 점수 단계 귀속, 단계 끝 작업 등록, 감시기와 알림의 운영 경로를 확인한다. lead의 별도 승인 전에는 Kit, GPU, 외부 알림을 시작하지 않는다.

예행은 깨끗한 detached source와 고정 HEAD에서 D: 임시 출력으로만 진행한다. 학습은 EX-42 정의의 `cuda:0`, 경계 평가와 영상/W78은 정의의 `cuda:1`을 사용하고, 한 실험 도중 역할 장치는 바꾸지 않는다. 예행용 단계 길이는 격리된 실행 설정에서만 10회로 줄이고 EX-42 운영 정의와 승인 파일은 바꾸지 않는다.

부모는 EX-41 `model_6000.pt`, SHA `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5`다. 0단계 `EX42_0_T0_prime`은 EX-41 `T0_prime`의 명령 비율, 범위, 지도 선택, terrain policy를 쓰며 예행에서는 10회, 운영 정의에서는 1000회다. 승인 DR은 1.0이다.

## 단계와 평가 흐름

| 순서 | 단계 | 예행 회수 | 단계 끝 증거 |
|---:|---|---:|---|
| 1 | EX42_0_T0_prime | 10 | 시작 상태, 부모 SHA, DR 1.0, m10 checkpoint |
| 2 | E0 | 10 | stage transition, 경계 P1 점수 요청, 단계 끝 등록 |
| 3 | E1 | 10 | stage transition, 경계 P1 점수 요청, 단계 끝 등록 |
| 4 | E1F | 10 | stage transition, 경계 P1 점수 요청, 단계 끝 등록 |
| 5 | E2 | 10 | stage transition, 경계 P1 점수 요청, 단계 끝 등록 |
| 6 | E3 | 10 | stage transition, 경계 P1 점수 요청, 단계 끝 등록 |
| 7 | E4 | 10 | stage transition, 경계 P1 점수 요청, 단계 끝 등록 |
| 8 | E5 | 10 | stage transition, 경계 P1 점수 요청, 단계 끝 등록 |
| 9 | M | 10 | stage transition, 경계 P1 점수 요청, 단계 끝 등록 |
| 10 | E6a | 10 | stage transition, 경계 P1 점수 요청, 단계 끝 등록 |
| 11 | E6b | 10 | 마지막 stage receipt와 종료 상태 |

각 단계마다 아래 파일을 확인한다. `N_i`는 해당 단계의 실제 종료 회차를 manifest와 transition 영수증에서 읽는다. 예행이 시작 전환을 별도로 기록하지 않으면 예상 회차를 추측해 대입하지 않는다.

| 단계 | 단계별 출력 확인 |
|---|---|
| `EX42_0_T0_prime` | `train_start_status.json`; `manifest.json`의 부모 참조와 `model_<N_0>.pt` 체크포인트 SHA; 시작/첫 reset 상태 영수증 |
| `E0` | `ex42_application.jsonl`의 경계 전환; `manifest.json`의 `model_<N_1>.pt`; 저장 후 P1 등록 영수증 및 예행 queue 항목 |
| `E1` | `ex42_application.jsonl`의 경계 전환; `manifest.json`의 `model_<N_2>.pt`; 저장 후 P1 등록 영수증 및 예행 queue 항목 |
| `E1F` | `ex42_application.jsonl`의 경계 전환; `manifest.json`의 `model_<N_3>.pt`; 저장 후 P1 등록 영수증 및 예행 queue 항목 |
| `E2` | `ex42_application.jsonl`의 경계 전환; `manifest.json`의 `model_<N_4>.pt`; 저장 후 P1 등록 영수증 및 예행 queue 항목 |
| `E3` | `ex42_application.jsonl`의 경계 전환; `manifest.json`의 `model_<N_5>.pt`; 저장 후 P1 등록 영수증 및 예행 queue 항목 |
| `E4` | `ex42_application.jsonl`의 경계 전환; `manifest.json`의 `model_<N_6>.pt`; 저장 후 P1 등록 영수증 및 예행 queue 항목 |
| `E5` | `ex42_application.jsonl`의 경계 전환; `manifest.json`의 `model_<N_7>.pt`; 저장 후 P1 등록 영수증 및 예행 queue 항목 |
| `M` | `ex42_application.jsonl`의 경계 전환; `manifest.json`의 `model_<N_8>.pt`; 저장 후 P1 등록 영수증 및 예행 queue 항목 |
| `E6a` | `ex42_application.jsonl`의 경계 전환; `manifest.json`의 `model_<N_9>.pt`; 저장 후 P1 등록 영수증 및 예행 queue 항목 |
| `E6b` | `ex42_application.jsonl`의 종료 상태; `manifest.json`의 `model_<N_10>.pt`와 최종 SHA; 종료 상태 파일 |

`model_<N_i>.pt`에서 `<N_i>`는 단계 순번이 아니라 manifest에 나온 해당 단계의 실제 종료 update 숫자로 치환한다. 각 stage-end 등록은 `stage_reports/<stage_id>_<N_i>.json`, `components/` 영수증, 예행 queue item과 개별 done-file로 확인한다. 해당 자동 등록 경로는 현재 미연결이므로 파일이 없으면 단계 성공으로 처리하지 않는다.

예행은 총 110 update다. 각 경계 평가가 늦거나 실패해도 학습 update와 예정 DR 단계는 멈추지 않는다. 빈 점수는 판정으로 쓰지 않고 측정 공백으로 기록한다. 점수가 있으면 score watcher의 `stage_id`가 직전 적용 transition receipt와 일치해야 한다. 0단계 이후 적용 전환 영수증이 없으면 watcher는 단계 이름을 추측하지 않고 보류한다.

각 stage 끝은 별도 영수증으로 남긴다. 평가 항목은 dispatch priority 2, 영상 항목은 priority 3으로 임시 예행 queue `D:/mai-tmp/runner/ex42-rehearsal-queue.json`에 등록한다. 학습 중 GPU1이 평가/영상에 실제 할당된 동안 같은 GPU를 쓰는 항목은 기다린다. queue 완료 파일은 작업별 새 경로로 기록한다.

## 사전점검 명령과 기존 blocker 기록

기준 HEAD, 격리 worktree 생성, CPU ops-check와 plan-only 검증 명령은 위의 「2026-11-07 갱신」 절만 사용한다. 아래 종료 조건도 실제 Kit caller 연결과 lead 승인 전에는 계획 항목이며 실행 증거가 아니다.

## 종료 조건

실제 예행을 승인받아 실행할 때 아래 항목이 전부 출력과 파일에서 확인돼야 한다.

1. 부모 SHA와 m6000 시작 증거가 일치하고 EX42_0_T0_prime 10회가 완결된다.
2. 11개 stage 각각 시작 · 끝과 연속 stage transition이 남고 최종 상태가 E6b 종료다.
3. 각 stage 끝 model 파일명과 SHA가 manifest에 있고, P1 경계 점수는 같은 checkpoint에 묶인다. 점수의 stage id는 적용 transition history를 따른다.
4. P1 측정 실패를 주입해도 학습은 다음 stage로 진행하며, 미완료 score는 측정 공백으로 남는다.
5. P2 평가 및 P3 영상 작업이 임시 queue에 stage별로 등록되고, 각 작업의 child receipt와 done-file이 일치한다.
6. 감시기는 새 checkpoint 및 score receipt를 읽고, 예행 종료 뒤 자체 종료한다.
7. 승인된 orchestration/Telegram 경로에 예행 경보가 한 번만 도착한다. 실제 전송은 lead 승인 뒤 수행한다.
8. 최종 receipt에 source HEAD, 단계 길이 override, queue ID, GPU UUID, 시작/끝 시각, 오류 및 미확인 항목이 기록된다.

현재 준비도는 `blocked`다. 이 문서는 실행 허가가 아니며, runtime 경로와 env import를 해결한 뒤 lead가 command와 출력 ROOT를 확인해야 한다.


## W32 R4 runtime-install measurement

Add the successful real parser and environment import check to the install-day evidence list. It is intentionally outside default pytest discovery so an absent local Isaac/RSL runtime is reported by the portable ops-check test instead of being skipped or treated as a successful import. On the installed runtime only, run explicitly:

```powershell
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest foothold_s2/tests/ex42_runtime_install_day.py -p no:cacheprovider --basetemp=D:/mai-tmp/runner/pytest-runtime-install-day -q
```

Pass requires the real train parser and environment class import to succeed, while `kit_started` remains false. Until that explicit install-day run, the successful runtime import is unmeasured.
