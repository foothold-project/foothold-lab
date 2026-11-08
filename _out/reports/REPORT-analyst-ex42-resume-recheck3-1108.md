> 분류: A/평가 · EX42 자기 이어 가기 재감사
> 작성: analyst · 2026-11-08 17:03 KST
> 근거: runner cc7586db · 실제 EX42 m350 · 설치 Isaac reset 본문 · 실제 호출부 AST · CPU 원자료
> 요지: H1·H2 모두 닫힘. 변경 경로에서 새 막음 0. 실제 Kit 첫 rollout 성공과는 구별한다.
> 상태: CPU 재감사 완료 · 막음 0 · Kit 결과는 이 감사에서 측정하지 않음

# EX42 자기 이어 가기 세 번째 감사

**고정 HEAD `cc7586db9f58b4bf43ef2ce5658e40bede3e7003`의 H1·H2는 닫혔다.** 같은 실제 m350과 설치 reset 함수로 다시 실행했고, 두 고침을 메모리 안에서 각각 되돌린 반례도 이전 오류를 잡았다. 관련 CPU 시험은 **22 PASS, 0 SKIP, 6.31초**다. 새 막음은 이번 변경 경로에서 찾지 못했다.

R6·M15에 따라 실제 저장본과 설치 코드를 읽고, M14에 따라 고침을 제거한 입력도 검사했다. runner 소스·운영 폴더·원장·GPU는 변경하지 않았다. 앞선 결과는 [두 번째 감사](REPORT-analyst-ex42-resume-recheck-1108.md)에 보존한다.

| 항목 | 이번 판정 | 실제 확인한 근거 |
| --- | --- | --- |
| H1 · reset 전 잘못된 부모 선택 | **닫힘** | `train_start.py:945`의 실제 IF AST가 지정된 `model_350.pt`를 CPU로 읽어 지형 복원에 준다. 설치 reset event를 두 번 실행하고 실제 `StartRunner._load_env_state(m350)`를 적용한 뒤 3072개 root XY 범위 위반 **0개**. 레벨·종류도 m350과 같음. |
| H1 · 반례 검출력 | **확인됨** | AST 사본에서 복원 인자 하나만 EX41 부모로 되돌리면 범위 위반 **1100개**가 다시 나옴. runner 파일에는 쓰지 않음. |
| H2 · 새 시작 지역변수 초기화 | **닫힘** | `main:745`의 None 초기화와 실제 manifest IF `:1281`를 같은 함수 범위에 놓고 실행. 새 시작은 `resume_root_xy_readback=null`, 자기 재개는 3072개 readback을 기록하며 예외 없음. |
| H2 · 반례 검출력 | **확인됨** | 초기화 AST만 빼면 새 시작에서 다시 `UnboundLocalError`. |
| 새로 바뀐 저장본 재사용 | **확인됨** | `:1038`의 `resume_saved = ex42_resume_saved`가 pre-reset에서 읽은 동일 Python 객체를 검증에 사용. `runner.load` 자체는 같은 경로를 별도로 읽으며, 감사 앞뒤 m350 파일 SHA는 동일. |
| manifest 소비 세 곳 | **확인됨** | `:1284`, `:1304`, `:1327` 모두 초기화된 같은 지역변수 사용. 옛 대문자 변수 참조 0개. |
| L1 · 기존 영수증 원본 내용 보존 | **기존 낮음 잔여** | 이번 diff에서 해당 함수·constructor는 변경 없음. 이전 감사에서 잘못된 identity 검증 우회는 닫혔으나, 유효한 이전 영수증의 추가 provenance 내용은 SHA만 남고 교체됨. 새 막음으로 올리지 않음. |

## 원자료와 재현 범위

- 읽은 사본: `D:/mai-wt/foothold-lab/runner-ex42-resume-w65`. 시작·끝 HEAD 일치, clean. 실행 소스 네 파일 SHA도 시작·끝 일치.
- 실제 자기 저장본: `C:/Users/AI-WS01/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914/model_350.pt`.
- m350 SHA: `7c01f11657b2d66b5fe3b5324f889aea5749c0cebb00333472fb6322342ca75c`.
- 실제 EX41 부모 SHA: `1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613`. 실제 CLI는 여전히 부모 iter 6000을 반환하지만, 이번 pre-reset 경로는 이를 쓰지 않고 자기 m350을 선택함.
- 두 저장본의 실제 terrain level 차이는 1100/3072, type 차이는 0/3072. m350 레벨별 환경 수는 L1 20 · L2 138 · L3 312 · L4 588 · L5 2014.
- 설치 reset: `C:/isaac/isaaclab/source/isaaclab/isaaclab/envs/mdp/events.py:1074`, 위치 계산 `:1104`, pose 쓰기 `:1115`. 실제 함수 AST를 실행하되 난수는 0으로 고정하고 pose 수신부만 CPU 객체로 대체.
- CPU 격자는 행·열 8 m 간격인 답을 아는 입력이다. 이번 root 거리 0 m와 반례 거리 평균 4.315104 m·최대 32 m는 **이 CPU 입력에서 나온 값**이다. 실제 Kit 로봇의 거리·성능으로 읽지 않는다.

독립 감사 [스크립트](ex42-resume-1108/recheck_cc7586db.py) · [JSON](ex42-resume-1108/recheck_cc7586db.json) · [실행 로그](ex42-resume-1108/recheck_cc7586db.log). 실제 저장본·설치 reset 준비 부분은 같은 폴더의 `recheck_86120a5e.py`를 읽어 재사용하며 그 파일 SHA도 JSON에 기록한다. 코드 돌연변이는 AST 복사본에서만 실행한다.

관련 pytest [실행 로그](ex42-resume-1108/pytest_cc7586db.log). `isaac311/python.exe`로 `test_ex42_stage_zero_cpu.py`, `test_ex42_training_entry_cpu.py`를 실행했고 `EX42_W65_PARENT_CHECKPOINT`에 실제 EX41 `model_6000.pt`를 지정해 이전 SKIP도 실행했다. 임시는 `D:/mai-tmp/analyst/resume-cc7586db-pytest`, cacheprovider 끔.

## 남은 확인과 해석 한계

이번 diff는 `train_start.py`의 H1·H2 연결, 그 문자열 검사, 보고서뿐이다. 앞서 확인한 optimizer·RNG·curriculum·map-switch 등 12 상태 묶음, local 351·누적 12351, 승인 상한 1000의 소비 코드는 변경되지 않았다. 그 전체 시험을 반복한 것은 아니다.

**CPU 막음 0은 실제 학습 성공 또는 기동 승인이라는 뜻이 아니다.** 이번에는 전체 Isaac reset의 curriculum 계산·물리·CUDA 난수열을 실행하지 않았다. 승인된 Kit 예행에서 동일 HEAD, 3072개 root XY 범위 위반 0, 첫 local 351·누적 12351, 첫 update와 저장 영수증을 확인해야 한다. 이 문서가 그 결과를 대신하지 않는다.
