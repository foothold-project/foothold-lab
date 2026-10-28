> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 (scripter) · 2026-10-28
> 근거: pipeline W33b `NEXT-RUN.md` · 기본 보행 DRY 영수증 네 건 · CPU 답 아는 입력
> 요지: 기본 보행 두 판의 학습 진입과 W15 평가 사슬에 D: Kit 캐시 인자를 전달한다
> 상태: 코드 준비 · CPU 확인됨 · Kit 소비 미확인 · 학습 시작 아님

# 기본 보행 W33b Kit 캐시 인자

## 변경

W33b 원문 `C:/mai/wt/foothold-lab/pipeline-w33b-next/inbox/jay/20261028-w33b/NEXT-RUN.md`의 `localCachePath` 값을 `--kit_args=--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache` 한 토큰으로 고정했다. 공통 값은 `foothold_s2/basic_gait_kit.py`에 둔다. 부모와 처음부터 판의 smoke/main argv, `run_basic_gait.sh` 검사, 기동 영수증에 같은 값을 넣었다. 누락되거나 중복되면 기동 전 거절한다.

W15 평가 사슬의 `basic_gait_eval_once.py`가 자식 환경에 같은 인자를 넣는다. `run_sb_eval.sh`는 turn16과 map64 각각의 Kit 자식에 한 토큰을 전달한다. 기본 보행 평가가 아닌 기존 호출에는 해당 환경 변수가 없으므로 인자를 더하지 않는다. 학습 설정, 보상, 평가 판정값은 바꾸지 않았다.

## 답을 아는 확인

| 확인 | 결과 |
|---|---|
| 부모 · 처음부터 판, smoke · main DRY 영수증 네 건 | 네 건 모두 정확히 한 토큰, `training_approved=false`, 학습 미기동 |
| CPU 평가 가짜 Kit 자식 | turn16과 map64 각각 정확히 한 토큰 |
| CPU 기본 보행 · W15 회귀 | 25 PASS |
| 변경 Python의 `ruff check --select F` | 0건 |
| 두 셸의 `bash -n` · `git diff --check` | 통과 |

DRY 영수증은 `C:/Users/AI-WS01/AppData/Local/Temp/basic-gait-w33b-dry-1028/receipts/{smoke,main}/`에서 되읽었다. 평가 시험은 실제 Kit 대신 가짜 자식의 argv를 기록했다. 따라서 실제 Kit의 캐시 사용, 속도와 디스크 생성은 미확인이다. GPU, Isaac, 학습은 실행하지 않았다. 기존 예행 산출과 다른 세션의 `logs/`, `logs_gate/`, `outputs/2026-10-28/`은 보존했다.
