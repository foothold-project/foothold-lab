> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 (lead_tmp 취합·직접 대조) · 2026-10-23
> 근거: EX-23 원자료 · START v1 · sol 고정 코드82331727 · ASTRA-23e · luna 평가 도구
> 요지: EX-28 B와 EX-29 START 본류의 코드·검증·실행 전 미확인을 한곳에서 구분한다.
> 상태: 고정 구현·독립 검토·CPU 검증 완료 · 실제 Kit·GPU 실행 전

# EX-28·29 구현과 실행 준비 기록

실험 설계 정본은 [B·START TopDown 계획](PLAN-B-START-TOPDOWN-1023.md)이다. 이 문서는 구현 증거와 남은 기계 확인만 다룬다. START 원문 코드는 비공개이므로 논문 기반 재구현이며, 저자 바이트 재현이나 보행 성공을 선언하지 않는다.

## 고정 코드와 확인한 범위

공유 코드: [ea664f1e](https://github.com/foothold-project/foothold-lab/tree/ea664f1e92c3fa7223e0d372816c6ca752966690/foothold_s2) · 브랜치 `feature/start-topdown-b-jay`. 로컬 실행 준비 자리: `C:/mai/wt/foothold-lab/lead-tmp-start-b`. 원격 HEAD도 같은 커밋임을 직접 확인했다. 학습 코드 sol82331727과 촬영기 luna5651b5f6를 결합했다. [구현 출처와 파일 SHA](https://github.com/foothold-project/foothold-lab/blob/ea664f1e92c3fa7223e0d372816c6ca752966690/inbox/jay/20261023-experiments/IMPLEMENTATION-B-START-1023.md).

학습 코드의 최종 고정 출처는 sol 브랜치의 `8233172777e592877861c6e78918fc1f3bcfc0fe`이다. `foothold_s2/`를 `git archive`로 꺼내 독립 통합 자리 `C:/mai/wt/foothold-lab/lead-tmp-start-b`에서 확인했다. 다른 세션의 미커밋 파일과 원자료를 가져오지 않았다.

| 항목 | 이번에 확인한 것 | 아직 뜻하지 않는 것 |
|---|---|---|
| B 변경 | EX-23 상속, 로봇 material 정적·동적 마찰 범위만 변경. 별도10 update 예행과1501 update 본판 | 과거 EX-23의 초기 물성 배열·GPU 난수 궤적 완전 복원 |
| 실제 물성 기록 | 환경×shape×3 배열·SHA, 질량·COM·gain·strength, floor cfg 기록 경로 | PhysX 바닥 material readback은 미확인 |
| 초기 지지 | 표집된 관절의 FK를 써 root XY를 지지판 안으로 보정, TD yaw0·B 기존 yaw 보존 | 실제 Kit FK·네 발 접촉 |
| 깊이 입력 | TD 추가 지연0이 checkpoint와 평가 loader에 전달됨. 첫 카메라 광선 갱신 뒤 cache 무효화 | 실제 렌더 첫 프레임·광선·센서 타이밍 |
| 저장·재개 | 원자 checkpoint, 새segment, 부모SHA, optimizer·지형 원점·별도 curriculum RNG. 초기 snapshot 재개 거절 | 물리 simulator와 이전 episode의 연속 궤적 복원 |
| 재개 배치 | label/type 복원 뒤 실제 env reset. 그 reset에서 curriculum 한 번 더 전진하지 않음 | 실제 Kit 재개 시험 |
| 발 XY | reset 전 종료 스텝의 유효 접촉 표본도 적분. L·T·L/T 기록 | 발 접촉점·경사 법선을 보정한 실제 미끄러짐 |

`확인됨`: lead_tmp가 고정 archive에서 아래 다섯 파일을 직접 실행해 **39 PASS,7.34초**를 확인했다. GPU를 숨긴 `isaac311` Python이고 Kit를 만들지 않았다. 다른 선택 집합인 sol의88·96개와 합산하지 않는다.

```powershell
$env:CUDA_VISIBLE_DEVICES='-1'
$env:PYTHONDONTWRITEBYTECODE='1'
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -B -m pytest -q -p no:cacheprovider foothold_s2/tests/test_sol23f_b_cpu.py foothold_s2/tests/test_sol23f_launch_cpu.py foothold_s2/tests/test_sol23f_followup_cpu.py foothold_s2/tests/test_sol23f_topdown_cpu.py foothold_s2/tests/test_sol23g_tail_cpu.py
```

중간 점검 요청기는 별도 CPU9시험, 기존 촬영 자료 감사는3시험을 lead_tmp가 확인했다. 이는 촬영과 사람의 분석까지 자동 완료됐다는 뜻이 아니다. 요청 상태의 `completed`는 촬영 영수증 확인 완료다.

## 촬영기 결합 확인

`확인됨`: 결합한 고정 사본에서 녹화 계약15개와 기존 seq_video9개를 직접 재실행해 **24 PASS,7.31초**를 확인했다. 첫 호출의 출력이 일부만 수집되어 로그 파일로 같은 범위를 다시 실행한 값이다. 이24개는 학습39개와 다른 범위다.

```powershell
$env:CUDA_VISIBLE_DEVICES='-1'
$env:PYTHONDONTWRITEBYTECODE='1'
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -B -m pytest -q -p no:cacheprovider foothold_s2/eval/tests/test_record_sol23f.py foothold_s2/eval/tests/test_seq_video.py
```

고친 것은 native 지형 생성의 행/level 대응, TopDown의 추가 증강 해제, Kit 전 tensordict 선적재, reset 뒤에도 같은 명령 유지, 공통 물리 조건 대 학습 조건 구별, 32×16 지도 공통 높이 표시, 파일 flush 뒤 성공/실패 종료다. 복원 전용은 첫 스텝과 reset 뒤 GT 선택0을 확인한다. 실제 Kit의 카메라·물성·동영상·종료가 이대로 동작하는지는 아직 미확인이다. [luna 수정 기록](REPORT-luna-23eval.md).

ASTRA 독립 검토의 현재 판정은 [보고서16절](VERIFY-astra-23e-topdown.md)이다. 앞부분의 최초 불가·잔여 지적은 수정 이력이다. 이번 고정본은 지적한 CPU/코드 경로를 닫았지만, 실제 기계 검증과 보행 결과를 대신하지 않는다.

## 보고 간 차이와 미판정

ASTRA의 B 수학 동등 대조는 `be26f565`, CPU1 thread, 가짜환경2개,4 step×2 update, 양쪽 GRU cache를 비운 조건에서 tensor를 직접 비교한 결과다. sol의 다른 고정본·실행 조건에서 얻은 최종 SHA 불일치를 그 결과로 닫지 않는다. 같은 학습 수학을 상속했다는 확인과 모든 독립 실행의 동일 궤적 보장은 다르다. 과거 대조인 B의 해석 한계는 계획§2·9에 남겼다.

sol이 선택 범위 밖에서 시작한 전체 저장소 CPU 시험 `pytest -q foothold_s2/tests`는 PID103564로 남아 있으며22:09 직접 조회에서 프로세스가 살아 있었다. 완결 결과는 미판정이다. 관련39 PASS와 합산하지 않고, 이를 전체 시험 통과라고 쓰지 않는다. 이 세션이 프로세스를 종료하지 않았다.

코드 묶음은 sol 원본289개와 촬영기·시험2개를 취합했다. 첫 Git 수입 때 원본 CRLF285개가 LF로 정규화되어 저장소와 원본 SHA가 달랐고, cat-file로 직접 발견했다. 모두 줄바꿈 이외 차이가 없음을 확인한 뒤 실행 사본도 LF로 맞췄다. 폴더 `.gitattributes`를 포함한 최종292개는 작업 사본·Git blob·SHA 목록이 모두 일치한다. 옛 코드 두 곳의 공백 경고(`deploy/DESIGN-policy-node.md:40`, `tasks/s1_env_cfg.py:215`)는 고정 원본 보존을 위해 그대로이며, 전체 사본의 diff check가 깨끗했다고 보고하지 않는다. 이번 새 문서 변경은 별도 검사한다.

`torque_clipped_frac`는 현재 PD 출력 차이에 motor strength 효과가 섞일 수 있어 실제 토크 포화율로 해석하지 않는다. 이 값만으로 불안정 원인을 단정하지 않는다.

## 실행에서만 확인할 것

첫10 update 예행에서 task·시드·환경수·실현 마찰·네 발 출발 지지·depth·GT/pred 실제 마스크·손실 갱신·마감 저장과 재로드를 확인한다. 두 학습과 촬영1개의 VRAM·진전은 실제 실행으로만 판단한다. 결과에 따라 무조건 환경 수나 구조를 줄이는 우회는 하지 않는다.

마감은 정상 update 경계에서 저장하는 협력적 종료다. GPU/Kit가 멎은 프로세스를 강제로 죽이는 OS 마감 장치가 이미 검증됐다는 뜻은 아니다. 절대 마감과 첫 실행 시각을 등록하며, 마감 직전에는 최신 완결 checkpoint와 영수증을 먼저 보존한다. 임의 강제 종료나 Linux 설치는 이 문서로 승인되지 않는다.

이번 준비 중 새 학습·평가·렌더는 하지 않았다. 새 실험의 영상·성공률·보행 개선은 아직 없다. 기존 비교 근거는 [RESULT-EX23-25](../20261021-experiments/RESULT-EX23-25.md)이며, 이번의 코드 검증으로 그 결과를 새 실험 결과처럼 바꾸지 않는다.

## 기동 인계 순서

1. 위 고정 코드 사본과 SHA 목록, 두 task·seed·3072환경·마감 ISO 시각을 실행 manifest에 등록한다. EULA 등 팀장이 이전에 직접 허용한 환경만 사용하며 새 동의를 대신 만들지 않는다.
2. `foothold_s2/scripts/train_23f_b.py`와 `train_23f_topdown.py`의 `--smoke-updates 10 --end-by <시간대 포함 마감>`으로 실제 짧은 실행을 먼저 확인한다. 두 Isaac은30초 간격이며 창을 띄우지 않는다. 예행과 본판 폴더는 분리한다. 아직 실행하지 않았다.
3. 예행의 실제 소비값·첫 체크포인트를 확인한 뒤 본판을 기동한다. B는1501update, 본류는20,000상한과24h 이하의 등록 마감이다. 상태 파일·PID·첫update를1~2분 안에 직접 읽는다.
4. `monitor_23d.py scan`의 run·state·deadline을 실제 두 판에 연결하고 반복 호출을 세션 밖 프로세스로 건다. 현재 도구는 요청 생산자이며 반복 감시/촬영 소비자를 이미 띄운 것이 아니다. 알려진 완료 체크포인트로 pending→claimed→영수증 검증을 먼저 확인한다.
5. 촬영은 새 `foothold_s2/eval/record_sol23f.py`와 `seq_video.py`를 사용해 한 번에1개만 소비한다. `physics_mode=fixed`와`training`, 지도 `pred`와`gt`를 구분한다. 요청 완료는 파일 검증이고 사람의 판독은 별도다. 학습2개+촬영1개의 실측 여유가 없으면 B 종료 뒤 촬영하며 학습을 임의 종료하지 않는다.
6. 모든500/1000/1500 및 본류 추가1000회/3h 점검에서 영상·위상·관절·곡선을 해석한 문서를 남긴다. 최종100episode 독립 명령 정량 묶음은 계획이며 이번 순차12초 recorder가 그 평가를 대신하지 않는다.

문서 연결 검사는 `python tools/exp_sync_check.py`에서 확인51·누락0·종료0을 직접 확인했다. 이것은 문서 연결 검사이며 실험 성공 검사가 아니다.

검수 도구 `.github/scripts/review_inbox.py`는 이 문서 worktree의 sparse 파일에 없어 실행되지 않았다. 이번 변경13개 문서의 머리5줄·em dash0·상대경로는 별도 직접 검사했다. 문서 `git diff --check`는0이다.
