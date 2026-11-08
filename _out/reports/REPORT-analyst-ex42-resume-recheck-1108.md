> 분류: A/평가 · EX42 자기 이어 가기 재감사
> 작성: analyst · 2026-11-08 16:47 KST
> 근거: runner 86120a5e · 실제 EX41 m6000/EX42 m350 · 실제 호출부 AST · 설치 Isaac reset 코드
> 요지: H1 미해소. 복원 함수에 EX42 저장본 대신 EX41 부모가 전달됨. 새 시작 경로에 막음 H2 추가.
> 상태: 막음 2(자기 재개 1 · 새 시작 1) · L1 검증 우회 닫힘, 영수증 원본 보존은 낮음 잔여

# EX42 자기 이어 가기 H1 · L1 재확인

**86120a5e를 막음 0으로 볼 수 없다.** 새 지형 복원 함수는 m350을 직접 넣으면 CPU에서 맞지만, 실행기는 그 함수에 EX41 부모 m6000을 준다. 이후 m350의 원점을 다시 덮으므로 첫 rollout 전 위치 검사에서 거절된다. 기존의 조용한 위치 불일치가 오류로 드러나게 된 것은 개선이나, 자기 이어 가기는 아직 진행되지 않는다.

R6·M15는 실제 설치 코드·실제 저장본·실제 호출 인자로, M14는 연결부 반례로 확인했다. GPU·Kit·운영 run·runner 소스 수정 없음. 기존 준비·감사 보고는 [50e20f66 판](REPORT-analyst-ex42-resume-1108.md)에 보존했다.

## 1. 판정표

| 항목 | 닫혔나 | 직접 재현한 것 · 필요한 수정 |
| --- | --- | --- |
| H1 · 자기 재개 지형과 로봇 위치 | **아니오 · 막음 1** | `train_start.py:477`의 CLI 결과 `EX42_STAGE_ZERO_CHECKPOINT`는 EX41 m6000이다. 새 호출 `:945`가 이를 전달한다. 실제 m350과 level이 1100/3072개 다르며 type은 0개 다르다. 실제 호출 AST → 설치 reset 함수 본문 → 실제 `_load_env_state(m350)` → 새 readback을 연결하면 범위 위반 1100개. m350을 helper에 직접 준 대조 입력은 0개. 자기 재개 파일을 pre-reset 입력으로 선택해야 한다. |
| L1 · 잘못된 기존 영수증을 builder가 덮어 검증 우회 | **닫힘** | 기존 plan SHA 오류를 넣으면 builder 호출 0회로 거절되고 기존 오류 영수증도 보존된다. 새 `build_stage_zero_chain_with_receipt_checks`의 실제 함수와 실제 constructor를 D: 시험 폴더에서 실행. |
| L1 · 기존 영수증 내용 보존 | **부분 · 낮음 잔여** | 유효한 identity에 추가 provenance 필드를 둔 기존 영수증은 constructor가 여전히 교체한다. previous SHA와 changed=true는 남지만 이전 내용은 안 남는다. 새 resume 파일로 분리하거나 이전 바이트를 보존할 것. 이 항목은 새 GPU 기동 막음으로 올리지 않았다. |
| H2 · 새 시작 경로의 지역변수 | **새 막음 1 · 자기 재개에는 해당 없음** | `main`의 `:1049`에서 `EX42_STAGE_ZERO_ROOT_XY_READBACK`을 자기 재개 분기 안에서만 대입한다. 새 실행은 그 분기를 건너뛰지만 `:1279`에서 읽는다. Python은 이를 지역변수로 취급해 `UnboundLocalError`. 모듈 위의 None 초기화로 해결되지 않는다. main 초기에 로컬을 None으로 두거나 명시적 전역 설계를 적용해야 한다. |

**자기 이어 가기만 한정하면 막음 H1 한 건이다.** 같은 수정본으로 새 EX42 0 단계를 시작하는 경로까지 합하면 H2 포함 두 건이다. H2는 현재 학습 프로세스에서 발생했다는 뜻이 아니다.

## 2. 실제 자료에서 확인한 연결

- 고정 HEAD: `86120a5ea6aa2a4a070a4cd92501daa7161a992a`.
- 읽은 사본: `D:/mai-wt/foothold-lab/runner-ex42-resume-w65`, 처음 clean, 끝 HEAD와 세 실행 소스 SHA 일치.
- 부모 manifest: `C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/manifest.json`.
- 실제 CLI preflight가 돌려준 checkpoint iter: **6000**. 부모 SHA: `1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613`.
- 자기 재개 파일: `C:/Users/AI-WS01/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914/model_350.pt`.
- 자기 재개 SHA: `7c01f11657b2d66b5fe3b5324f889aea5749c0cebb00333472fb6322342ca75c`.

`ex42_training_entry.py:71`의 `inspect_ex42_stage_zero_parent`가 부모를 읽고 `:78`에서 돌려준다. 자기 재개 여부가 이 반환값을 m350으로 바꾸지는 않는다. 이후 `train_start.py:1033`에서 m350을 따로 읽는 흐름이다. 따라서 helper 단독 시험에서 임의의 saved 배열을 넣어 통과한 것으로는 실제 실행 연결이 확인되지 않는다.

H1 CPU 결과는 초기 타일 격자를 8 m 간격으로 놓고, 실제 두 체크포인트의 레벨·유형 배열을 적용해 얻었다. 원점 차이는 평균 **4.315104 m**, p95 **16 m**, 최대 **32 m**, reset XY 허용범위 밖 **1100/3072**. **이 거리는 알려진 CPU 격자 반례이며 실제 Kit에서 로봇이 이동한 거리나 사고 규모가 아니다.** 실제 저장본 사이 레벨이 다른 1100개라는 값과 구별한다. 이 반례는 reset event 부분만 실행하며 전체 Isaac curriculum/물리를 실행하지 않는다.

설치 reset은 `C:/isaac/isaaclab/source/isaaclab/isaaclab/envs/mdp/events.py:1074`의 함수 본문을 그대로 읽어 썼고, 난수만 0으로 고정한 CPU pose 수신 객체에 기록했다. 기존 명시적 reset과 wrapper reset을 나타내기 위해 event를 두 번 실행해도 잘못 선택한 부모 원점은 m350 원점이 되지 않는다. 실제 전체 reset은 `manager_based_rl_env.py:356`에서 curriculum을 먼저 계산하므로, 고친 뒤 그 효과도 첫 관측 readback으로 확인해야 한다.

H2는 원 `main`에 해당 변수의 global 선언이 없음을 확인한 뒤 실제 대입 AST와 manifest IF AST를 함수 안에 추려 실행했다. 재개 없음·EX42 계획 있음 입력에서 정확히 `UnboundLocalError: cannot access local variable 'EX42_STAGE_ZERO_ROOT_XY_READBACK' where it is not associated with a value`가 났다. Kit 실행을 했다는 주장이 아니다.

## 3. 시험 범위와 산출

- 실제 관련 CPU 파일 두 개 재실행: **21 PASS · 1 SKIP**, 5.44초. SKIP은 EX41 부모 시험용 환경변수 미지정. 별도 감사에서는 실제 CLI로 그 부모와 m350을 모두 읽었다.
- 독립 감사 [recheck_86120a5e.py](ex42-resume-1108/recheck_86120a5e.py), [원자료 JSON](ex42-resume-1108/recheck_86120a5e.json), [실행 로그](ex42-resume-1108/recheck_86120a5e.log).
- CPU 해석기: `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe`.
- scratch: `D:/mai-tmp/analyst/ex42-resume-86120a5e`. 운영 폴더에 쓰지 않았다.
- 첫 감사에서 확인한 12 상태 묶음·351/12351·1000 상한은 이번 diff에서 해당 소비자가 변경되지 않았다. 이번에는 H1/L1 및 새로 영향을 받은 새 시작 경로만 재검했다. 전체 물리 재개 성공은 여전히 미확인이다.

다음 고침의 닫는 조건은 둘이다. pre-reset 함수가 **CLI로 지정한 EX42 자기 저장본**을 받는 실제 호출 시험을 통과하고, 새 실행·자기 재개 양쪽 manifest 경로에서 readback 변수가 정의돼야 한다. 그 뒤 짧은 Kit 예행에서 3072 root XY 범위 위반 0과 첫 local 회차를 확인해야 한다.
