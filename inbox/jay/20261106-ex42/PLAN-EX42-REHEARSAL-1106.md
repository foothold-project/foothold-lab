> 분류: C/운영
> 작성: Codex runner · 2026-11-06
> 근거: EX-42 v0.16 · D182 · W20/W19 작업 HEAD e798992d
> 요지: 승인 후 EX-42 11단계를 짧게 통과시키는 Kit 예행의 입력 · 평가 · 종료 조건
> 상태: 계획안 · 실행 및 GPU/Kit 기동 승인 아님

# EX-42 단축 Kit 예행 계획

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

예행은 총 110 update다. 각 경계 평가가 늦거나 실패해도 학습 update와 예정 DR 단계는 멈추지 않는다. 빈 점수는 판정으로 쓰지 않고 측정 공백으로 기록한다. 점수가 있으면 score watcher의 `stage_id`가 직전 적용 transition receipt와 일치해야 한다. 0단계 이후 적용 전환 영수증이 없으면 watcher는 단계 이름을 추측하지 않고 보류한다.

각 stage 끝은 별도 영수증으로 남긴다. 평가 항목은 dispatch priority 2, 영상 항목은 priority 3으로 임시 예행 queue `D:/mai-tmp/runner/ex42-rehearsal-queue.json`에 등록한다. 학습 중 GPU1이 평가/영상에 실제 할당된 동안 같은 GPU를 쓰는 항목은 기다린다. queue 완료 파일은 작업별 새 경로로 기록한다.

## 확인 명령

현재 사용 가능한 사전 점검은 CPU 전용이다.

```powershell
.\foothold_s2\run_ex42.ps1 -Mode ops-check -Exp EX-42
```

`ops-check`는 현재 `runtime_integration_pending`, `explicit_lead_approval_missing`, `ex41_graduation_receipt_missing`, `terrain_manifest_missing`, `design_assumptions_pending`, `environment_import_unavailable`를 반환했다. `stage_dr_schedule_unapproved`는 반환하지 않았다. `kit_started=false`, `training_started=false`, `production_launch_allowed=false`도 확인했다.

현재 rehearsal wrapper는 다음 입력을 검사하는 CPU 계획 검증기다. 실제 Kit 또는 학습을 시작하지 않으므로 이 명령을 실제 Kit 예행으로 취급하면 안 된다.

```powershell
git -C D:/mai-wt/foothold-lab/runner-ex42-v016 worktree add --detach D:/mai-wt/foothold-lab/ex42-rehearsal-e798992d e798992d5dec65ca5da938d5288f9dc09aea6527
D:/mai-wt/foothold-lab/ex42-rehearsal-e798992d/foothold_s2/run_ex42.ps1 -Mode rehearsal -Exp EX-42 -SourceRoot D:/mai-wt/foothold-lab/ex42-rehearsal-e798992d -ExpectedHead e798992d5dec65ca5da938d5288f9dc09aea6527 -RehearsalOutput D:/mai-tmp/runner/ex42_rehearsal_20261107_120000 -RehearsalStageUpdates 10 10 10 10 10 10 10 10 10 10 10
```

위 두 명령은 CPU 계획 확인만 한다. 예행용 clean worktree를 만든 뒤 `ops-check`와 rehearsal plan validation을 통과시키는 데 쓴다. 실제 Kit 예행의 총 소요 시간은 아직 측정되지 않았다.

실제 Kit 예행을 위한 실행 인자는 이 HEAD에 아직 없다. EX42 runtime이 `NotImplementedError`로 막혀 있고, 현재 rehearsal은 `kit_started=false`를 반환한다. 따라서 GPU dispatcher에 실행 작업을 올릴 명령도 아직 안전하게 만들 수 없다. runtime attachment, 짧은 단계 설정을 실행에 적용하는 격리 경로, 실제 stage-end P2/P3 등록기 연결 뒤에 실행 명령을 고정한다. 위 blocker를 닫고 lead가 Kit 실행을 별도로 승인한 다음에만 그 명령을 만들고 queue에 등록한다.

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
