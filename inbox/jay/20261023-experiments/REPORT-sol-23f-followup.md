> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 (sol 작성·lead_tmp 취합) · 2026-10-23
> 근거: `PLAN-B-START-TOPDOWN-1023.md` · ASTRA-23e 후속 반례 · Isaac Lab 2.3.2 설치 소스 · CPU 정답 시험
> 요지: 예행 분리, 물성 원본, 재개 구간·물리 reset, 상태 해시, 지형 원점, 종료 발속도와 TopDown 초기 지지·카메라 첫 프레임·지연 소비를 고쳤다.
> 상태: 커밋 고정 · CPU 확인됨 · 실제 Kit와 GPU 미실행

# SOL-23f 후속 · B와 TopDown 기동 전 반례 수리

취합 출처: 작업자 고정 커밋 `c0038e80`. 아래 시험 숫자는 작업자 보고이며, lead_tmp 직접 재실행 범위는 [준비 기록](READINESS-B-START-1023.md)에 별도로 적었다. 머리 형식과 이 안내만 취합 시 정리했다.



## 1. 고정 범위

작업 사본은 `C:/mai/wt/foothold-lab/sol-23a`이다. 기존 SOL-23f의 B `be26f565` 및 TopDown `2b6f6d02` 위에 여섯 결함을 `7cf1d73f`로, 이후 받은 TopDown 두 반례를 `2455c8d1`로 각각 추가 커밋했다. 추가 재개 물리 reset·`--resume` 거부·TopDown 깊이 지연 소비는 `f5bfc15c`로 고정했다. 기존 EX23 환경·학습 본체의 마찰 이외 물리 설정과 PPO 수학은 변경하지 않았다. 공유 또는 실행 중인 소비 사본은 건드리지 않았다.

| 문제 | 변경 및 답을 아는 CPU 증거 | 남은 확인 |
|---|---|---|
| B의 1501회 고정 때문에 Kit 10회 예행 불가 | `--smoke-updates 10`은 B에서만 허용하고 내부 목표 10회, 실행 이름 `_smoke10`, manifest `run_kind=B_kit_smoke_10_updates`로 본 실행과 분리했다. 시드42·3072 env·24 step은 그대로다. 9·11회, 본판 `--max_iterations 10`, TopDown smoke, smoke 재개는 거절한다. | 실제 Kit 10회 예행은 미실행 |
| 물성 min/max만 기록 | 실제 PhysX 로봇 배열 전체 `[env,shape,3]`를 CPU `.npy`로 쓰고 SHA·dtype·shape를 JSON에 기록한다. 내부 셀 하나만 바꾼 반례는 min이 같아도 SHA가 달라진다. 바닥 재료 값과 combine mode는 cfg를 기록한다. **바닥 PhysX 실제 readback API는 미확인**이라고 분리했다. | Kit readback·바닥 실제값 미확인 |
| 재개가 원본 실행 폴더에 덮어씀 | 체크포인트 format·variant·필수 키·SHA를 읽고 새 형제 segment 폴더를 정한다. 실제 load 직전 SHA를 다시 대조하고 `resume_parent.json`에 부모 경로·SHA·완료 회차를 기록한다. 원본 manifest·YAML·물성은 그대로다. | 새 시뮬레이터의 물리 episode는 연속 복원이 아님 |
| 0차원 optimizer step 해시 실패 | tensor를 `reshape(-1)`한 뒤 바이트로 읽는다. scalar SHA 계산 반례 통과, 기존 1차원 벡터의 옛 해시와 바이트 일치를 확인했다. | 실제 Kit optimizer 생성 경로 미실행 |
| level/type 복원 뒤 원점 미복원 | `terrain_origins[level,type]`로 `terrain.env_origins`를 복원하고 `scene.env_origins` 일치를 요구한다. CPU level0→1에서 실제 reset이 읽는 원점 `[4,4,0]`을 `[12,4,0]`으로 고친다. scene 별도 사본이 낡았으면 거절한다. | 실제 물리 상태·episode는 새 segment에서 reset |
| 종료 step 발속도 0으로 누락 | `termination_manager.compute()` 직후는 reset 전이므로 `done` 환경의 유효한 접촉 발속도도 적분한다. CPU 종료 step 5 m/s, dt 0.02 s는 0.1 m 및 0.02 s로 기록된다. 다음 reset 후 위치 점프는 이 훅이 읽지 않는다. | 실제 접촉점의 미끄러짐이 아닌 몸체 발 중심 대용값 |
| TopDown 출발 앞발 pit | Isaac Lab의 관절 0.5~1.5 배 표집을 유지하고 그 **실제 표집된 관절**로 Go2 URDF FK를 계산한다. 같은 yaw에서 네 발이 출발 지지면 안에 들도록 root XY를 허용 교집합에 보정한다. 불가능하면 명시 오류다. `x=.85` 반례와 무작위 1000건, 지형 종류별 10행의 출발판 범위를 CPU 검사했다. 지원 조건을 적용한 위치 분포는 원문 미기재 우리 선택이다. | 실제 Kit FK·접촉·첫 reset 미확인 |
| 카메라 첫 프레임의 옛 fx | `camera.data`가 오래된 광선을 먼저 cast하는 getter이므로 cached `_data`를 읽어 새 intrinsic과 ray를 넣은 뒤 마지막에 `reset(ids)`로 invalidate한다. CPU 가짜 센서에서 reset 전 render 0회, 첫 read의 렌더 fx와 새 intrinsic fx 일치를 검사했다. | 설치 API 정적 확인만, 실제 광선 영상 미확인 |
| 재개 후 물리 root가 옛 원점 | wrapper 생성 때 초기 reset이 먼저 돌고 체크포인트 level/type은 뒤에 복원된다. 명시적 checkpoint load 뒤 새 segment에서 한 번 더 물리 reset한다. 그 한 번만 curriculum compute를 건너뛰어 저장 label/type을 지키고, 원점·counter 불변을 검사한다. `resume_parent.json`에 물리 reset과 origin SHA를 기록한다. `--resume` 및 agent cfg의 묵시 재개는 거절하고 `--resume_from`만 받는다. CPU 가짜 reset에서 level1과 root `[12,4,0]`을 확인했다. | 실제 Kit 물리 재개는 미확인, 이전 episode 연속성은 주장하지 않음 |
| TopDown 깊이 지연이 loader에서 1로 복귀 | TopDown agent cfg에 `depth_delay_ticks=0`을 명시하고 StartRunner가 그 칸을 실제 `PerceptionCfg`에 넘긴다. 체크포인트 소유 칸과 지각 cfg에 저장하고 재개 시 대조한다. 평가 `load_s2_runner`도 저장 칸을 소비해 이력 프레임 2개를 만들고, TopDown의 누락·1 값을 거절한다. CPU 정상 checkpoint와 누락 변이를 실행했다. B와 옛 판의 기본 1은 유지한다. | 실제 TopDown 영상 첫 두 프레임 미확인 |

## 2. 시험과 포함 관계

`CUDA_VISIBLE_DEVICES=-1`, conda `isaac311`에서 최종 변경 worktree의 관련 8개 시험 파일 **88 PASS**를 실행했고, 커밋 `f5bfc15c941ec4e87db1016aa2a5a3559f905398`의 `git archive`만 푼 깨끗한 사본에서도 같은 목록 **88 PASS**를 재실행했다. 최종 사본은 `C:/Users/AI-WS01/AppData/Local/Temp/sol23f-final-cf13f581ea714e13bf46ffb10a7fe42c/source`다. 이 88개에는 B·TopDown 기존 정답/반례, 새 scalar·원점·물성·종료·예행·재개 물리 reset·출발·카메라·깊이 지연 시험, 기존 StartRunner·X11·X13·S2 평가 GT 회귀가 포함된다.

앞선 `REPORT-sol-23f.md`의 **96 PASS**는 그때의 더 넓은 관련 시험 집합이고, **26 PASS**는 당시 새 SOL-23f 시험 부분집합이다. 이번 88은 다른 선택 집합이므로 96에 더하거나 96 전체를 다시 통과했다고 계산하지 않는다. 변경 시험은 이전 26을 보존하면서 새 반례를 덧붙였다. 이전 보고의 “종료 환경 발속도 제외” 문구는 이 후속 보고로 바로잡는다.

새·변경 Python은 `ruff check --select F` 통과, 별도 `pyflakes.exe` 검사 통과다. SHA 목록 `SHA256SUMS-sol-23f-followup.txt`는 원래 18개 코드·시험 파일과 새/공통 5개를 더한 23개를 가리키며, 최종 바이트 대조 **23/23 일치**다. 목록 자체의 SHA-256은 `8706ffe88f90636bbb6856f7c1e56c81f5a653556ccbc7810b4fe347e7173366`이다.

선택 범위 밖 저장소 전체 `pytest -q foothold_s2/tests`도 같은 이전 archive 사본에서 시작했으나 `test_chain` 약 24건 뒤 출력이 멈추어 **미판정**이다. PID `103564`, 명령은 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest -q foothold_s2/tests`, 시작 약 21:20 KST다. 로그는 별도 파일 없이 PTY 표준 출력에 점 24개 뒤 침묵한 상태이며 완결 결과가 없다. lead 지시에 따라 이 별도 시험 프로세스를 종료하지 않고 실행 중으로 남긴다. 최종 88 PASS와 혼합하지 않는다.

두 CPU 학습 실행을 독립 생성해 `StartRunner`와 `BRunner` 최종 상태 SHA를 그대로 비교한 추가 탐색은 **일치하지 않았다**. 초기 정책·지각·torch RNG 해시는 일치했고, B는 부모의 `learn`과 `update_perception` 함수를 그대로 상속하며 두 update 완료·유한 파라미터 시험은 통과했다. 독립 CPU 실행 간 난수 진행 차이는 이번 범위에서 원인이 확정되지 않았으므로 **동일 궤적 재현은 미확인**이다. ASTRA의 앞선 CPU 2 update 수학 대조를 새로운 동일 궤적 보장으로 확대하지 않는다. B cfg는 EX23의 로봇 startup 마찰 외 처치를 바꾸지 않는 AST 반례 시험을 유지한다.

## 3. lead 참석 명령과 읽을 증거

아래는 실행 명령 형식이다. 이 세션은 실행하지 않았다. 마감은 실제 시작 시각에 맞는 팀장 운영값으로 지정한다.

```powershell
python foothold_s2/scripts/train_23f_b.py --headless --device cuda:0 --smoke-updates 10 --end-by <시간대_포함_ISO8601> --max-wall-s <초>
python foothold_s2/scripts/train_23f_b.py --headless --device cuda:0 --end-by <시간대_포함_ISO8601> --max-wall-s <초>
python foothold_s2/scripts/train_23f_topdown.py --headless --device cuda:1 --end-by <시간대_포함_ISO8601> --max-wall-s <초>
```

예행에는 별도 `_smoke10` 실행 폴더, 실제 `robot_material_env_shape_3.npy`와 SHA, `realized_material.json`의 floor cfg 및 API 미확인 표시, `manifest.json`의 `run_kind`, `step_evidence.jsonl`, 10회 완료 체크포인트가 있어야 한다. 재개에는 `--resume_from <완료된_pt>`를 주고 새 형제 segment의 `resume_parent.json`·checkpoint SHA·`physical_reset.performed=true`·`physical_resume_identical=false`를 확인한다. TopDown은 첫 reset 네 발의 지지와 첫 깊이 fx, 정책 깊이 이력 길이 2를 Kit에서 확인해야 한다. Kit·GPU 결과와 성능은 현재 미확인이다.
