> 분류: 운영 · 평가 실행
> 작성: 오흥재 (runner 반영) · 2026-10-30
> 근거: EX-40 v7 의뢰, WORKLIST D72, RULES-HUB R6 · R20 · M02 · M15 · M76 · M77
> 요지: EX-40 B3 단계 세분화와 CPU 전용 재개 판정 및 실행 전 DRY 점검
> 상태: CPU 시험 통과, Kit · GPU 미실행

# EX-40 v7 단계 표와 재개 절차

## 변경 사항

전용 작업 사본 `C:/mai/wt/foothold-lab/runner-ex40-v7` 에서 변경했다. 기준은 `fcb76e4c` 이고 커밋은 `b80da55f8e1f1ed53194eab0f5371b91e4191af8` 이다. push하지 않았다.

| 단계 | 첫 update | 변경 | 지도 입력 |
|---|---:|---|---|
| B0 | 0 | 기본 구간 | GT |
| B1 | 1501 | 기존 B1 설정 | GT |
| B2 | 3001 | 기존 B2 설정 | GT |
| B3a | 4501 | B3 진입, forward 0.3~1.5, spin 절대값 0.5~1.5 | GT |
| B3b | 5001 | spin 하한 0.3 | GT |
| B3c | 5501 | forward 범위 0.1~1.5, low-forward 비율 0.20 | GT |
| T0 | 6001 | B3c 명령 유지, force_gt 해제 및 reconstruction 입력 | reconstruction |

전체 실행 계획은 m0부터 m6500까지 `max_iterations=6501` 이다. 단계의 명령 비율은 기존 표를 유지했다. Kit smoke는 업데이트 경계 3, 6, 9, 12, 15 를 지나며 B0부터 B3c까지 확인하는 18 update 구성이다. smoke 종료 체크는 `model_17.pt` 를 확인한다. 그림자 승급 상태는 유지되며 자동 승인으로 취급하지 않는다.

재개 검증기는 manifest 에 SHA가 기록된 `model_N.pt` 중 가장 높은 온전한 번호를 확인한다. 체크포인트 파일명과 저장된 iteration, manifest SHA, v7 처리 설정, 3072 환경 각각의 terrain level/type, 단계 상태, 지도 전환 상태, 전역 RNG 및 command RNG 가 맞아야 한다. 훼손된 최신 저장본은 건너뛰고 그보다 앞선 검증 가능한 저장본을 선택한다. 이 검증만으로 물리적 재개가 완전히 동일하다고 보증하지 않는다.

## 재개 절차

1. 원래 실행이 살아 있는지 확인한다. 살아 있으면 기다린다. 프로세스 상태를 알 수 없고 실행 상태가 running이면 보류한다. 종료 상태나 프로세스 종료를 확인하기 전에는 이어서 실행하지 않는다.
2. 원 실행의 `manifest.json`, `train_start_status.json`, 단계 및 소비 기록과 체크포인트를 읽는다. manifest 에 SHA가 없는 저장본, 번호와 저장 iteration이 다른 저장본, v7 처리 조건이나 저장 상태가 맞지 않는 저장본은 재개 부모로 쓰지 않는다.
3. 완료 영수증이 update 6500 완료를 나타내면 이미 완료로 표시한다. 그렇지 않으면 가장 높은 검증 통과 저장본을 부모로 고르고 해당 파일 SHA 전체값을 영수증과 함께 검토한다.
4. 새 `end-by` 는 시간대가 명시된 ISO8601 값이어야 하고 예상 종료보다 최소 24시간 뒤여야 한다. 원래 실행의 curriculum, arm, seed, 환경 수, 지도 전환 및 명령 설정을 보존해 `--resume_from` 과 `--basic-ex40-parent-sha` 를 함께 준비한다. 한 옵션만 있거나 smoke receipt 를 재개에 사용하면 거부한다.
5. 이어 달리기는 별도 승인 뒤 담당자가 실행한다. 세 번 연속 실패하면 중단하고 상태를 보고한다. 이 도구는 프로세스를 시작하거나 종료하지 않는다.

실행 전 점검 명령은 아래와 같다. `<END_BY>` 는 시간대가 포함된 종료 시각으로, 경로는 작업 사본 밖의 새 임시 로그/점수 디렉터리로 바꾼다.

```powershell
$env:LIVE='0'
& 'C:\Program Files\Git\bin\bash.exe' foothold_s2/run_ex40.sh B cuda:0 <END_BY> /c/Users/AI-WS01/AppData/Local/Temp/ex40-v7-dry-main /c/Users/AI-WS01/AppData/Local/Temp/ex40-v7-score-main main
$env:LIVE='0'
& 'C:\Program Files\Git\bin\bash.exe' foothold_s2/run_ex40.sh B cuda:0 <END_BY> /c/Users/AI-WS01/AppData/Local/Temp/ex40-v7-dry-smoke /c/Users/AI-WS01/AppData/Local/Temp/ex40-v7-score-smoke smoke
```

실제 이어달리기 전에는 담당자가 원 프로세스 종료 증거, 부모 저장본과 SHA, 종료 여유시간을 확인해야 한다. 이 제출에서는 실제 저장본을 소비하지 않았고 실제 재개 명령을 실행하지 않았다.

## 검증 기록

- CPU 시험: 최초 v7 구현은 `31 passed in 6.02s` (`test_ex40_v7_continue_cpu.py`, `test_w55_continuous_cpu.py`, `test_ex40_v4_cpu.py`). 후속 수정 시험은 아래 부록에 기록한다.
- `python -m compileall -q foothold_s2`: 완료. 기존 `ex35_priority_marker.py` 에 invalid escape SyntaxWarning 2건이 출력됐으며 이번 범위에서 수정하지 않았다.
- `git diff --check`: 통과.
- main DRY: `prestart_pass`, `source_git_clean=true`, `training_started=false`, `max_iterations=6501`, 경계 B0=0, B1=1501, B2=3001, B3a=4501, B3b=5001, B3c=5501, T0=6001. 영수증: `C:/Users/AI-WS01/AppData/Local/Temp/ex40-v7-dry-main/receipts/ex40/B_main_20261030_205233_1098074/launch_receipt.json`.
- smoke DRY: `prestart_pass`, `source_git_clean=true`, `training_started=false`, `max_iterations=18`, 경계 B0=0, B1=3, B2=6, B3a=9, B3b=12, B3c=15. 영수증: `C:/Users/AI-WS01/AppData/Local/Temp/ex40-v7-dry-smoke/receipts/ex40/B_smoke_20261030_205251_1098103/launch_receipt.json`.
- GPU 또는 Kit 실행은 요청에 따라 하지 않았다. Kit smoke 성공 및 실제 재개는 미확인이다.

## 후속: terrain 고정 및 같은 실행 재개

`ex40.yaml` 기본 `terrain_curriculum: fixed_l02`를 실행 설정에 적용한다. `gym.make` 전에 최대 시작 레벨을 2로 두고 `curriculum.terrain_levels=None`으로 지형 승급을 끈다. 시작 영수증, manifest, checkpoint 연속 상태에 레벨별 실제 환경 수, 최소/최대 레벨, level/type 배열 SHA, 적용 정책을 기록한다. 고정 모드에서 L3 이상이 관측되거나 영수증과 checkpoint 상태가 다르면 실행 및 재개 검증이 실패한다. `auto`는 실제 승급 term이 있는 설정에서만 허용한다.

카드에는 요청된 문구 「S-B10 대비 의도된 차이 2: 지형 자동 승급 끔(L0~2 고정, 팀장 결정 대기)」를 추가했다. 이 설정의 최종 연구 결정은 미확인이다.

재개는 원 scratch launch 영수증과 SHA가 manifest에 고정된 checkpoint를 resume spec으로 입력받는다. 부모 회차와 저장 segment를 검증한 뒤 같은 arm, 장치, 로그/점수 위치, curriculum, optimizer 및 학습률, B1 시작 기준, 지도 전환, 수집 update를 유지하는 다음 segment 인자를 만든다. 새 segment 번호는 부모 번호보다 1 커야 한다. launcher는 기본적으로 CPU 준비와 prestart 검사만 하며, 실제 실행 상태·Kit·GPU는 이 작업에서 확인하지 않았다.

- 후속 CPU 시험: `34 passed in 5.09s` (`test_ex40_v7_continue_cpu.py`, `test_w55_continuous_cpu.py`, `test_ex40_v4_cpu.py`). 포함: fixed L0..L2 실제 레벨 영수증, L3 반례, 자동 모드 승급 term 누락, Kit 영수증의 승급/레벨 분포 및 manifest 반례, source receipt와 parent SHA를 쓰는 resume 준비 및 segment 연속성.
- 후속 main DRY: `prestart_pass`, `source_git_clean=true`, `training_started=false`, `terrain_curriculum=fixed_l02`. 영수증 폴더: `C:/Users/AI-WS01/AppData/Local/Temp/ex40-v7-followup-main/receipts/ex40/B_main_20261030_212054_1100119/`.
- 후속 smoke DRY: `prestart_pass`, `source_git_clean=true`, `training_started=false`, `terrain_curriculum=fixed_l02`. 영수증 폴더: `C:/Users/AI-WS01/AppData/Local/Temp/ex40-v7-followup-smoke/receipts/ex40/B_smoke_20261030_212102_1100139/`.
- 후속 resume DRY: 알려진 CPU `model_5500.pt` fixture와 manifest SHA를 source receipt/spec에 연결했다. `prestart_pass`, `source_git_clean=true`, `start=resume`, `segment_index=1`, `terrain_curriculum=fixed_l02`, `training_started=false`. 영수증 폴더: `C:/Users/AI-WS01/AppData/Local/Temp/ex40-v7-followup-resume/logs/receipts/ex40/B_resume_20261030_212154_1100205/`.
- 이 DRY는 실제 Kit 배치 분포, 실제 저장본 재개, optimizer의 실기 연속성 검증이 아니다. Kit와 GPU는 실행하지 않았다.
