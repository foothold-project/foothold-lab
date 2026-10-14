> 분류: A/평가 · Codex Worker 작업서 · 1043 쌍 평가 준비 1 단계 (읽기 · 설계 메모만 · 코드 쓰기 없음)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 09:5x
> 근거: VERIFY-astra-17p.md 5 절 · VERIFY-astra-17.md 3.2 ~ 4 절 · NIGHT-PLAN-20261014.md · `C:/isaac/ext/go2_rl_robotlab/_eval/cmdr_eval_driver_v37.py` · `cmdr_post_v10.py`
> 요지: GPU 0 이 05:46 부터 비어 있다. CMD-R 시드 1043 쌍 (off · on) 학습은 끝났고 평가가 없다. 1042 쌍은 `cmdr_eval_driver_v37.py` 로 평가했고 그 드라이버는 1042 에 하드코딩돼 있다. 1043 평가를 안전하게 돌릴 최소 설계를 코드 쓰기 전에 메모로 낸다
> 상태: 의뢰 (1 단계 · 메모만)

# Codex Worker 작업서 · 1043 평가 설계 메모 (1 단계)

## 0. 규칙

- 너는 **Codex Worker (gpt-6-sol)** 이고 검증자가 아니다. 설계 메모는 제안이고 ASTRA 가 따로 검증한다. 규칙은 `TASK-codex-worker-17g-fix.md` 1 절 · `TASK-codex-worker-17i-fix.md` 0 절을 그대로 따른다 (YOLO 세션 · 커밋 금지 · 삭제 금지 · GPU · Isaac 실행 금지 · `CUDA_VISIBLE_DEVICES=-1` · 키 · 토큰 안 다룸 · em dash 금지 · 정직한 보고).
- **이번 1 단계는 읽기와 메모만이다.** 작업 폴더 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexD/` 안에만 쓴다 (`MEMO.md` · 읽은 근거의 발췌 · 시험 스크립트가 필요하면 그 안에). `C:/isaac/ext/go2_rl_robotlab/_eval/` 안의 어떤 파일도 만들거나 고치지 않는다. `_eval/out*` · `slot` · `branch` · `s2` · `handover*` · `rand_scenes` · `ce12` · 동결 파이썬은 쓰기 금지 (`_eval/out/` 은 다른 일의 자리라 **읽기도 아래 1.4 항목만**).
- 해석기: `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe` (시험 · 읽기용). 시작에서 `sys.executable` 을 출력한다.

## 1. 해야 할 일

**1.1 읽기.** `VERIFY-astra-17p.md` 5 절 전체 · `VERIFY-astra-17.md` 3.2 ~ 4 절 (CMD-R 목표 세 칸 · 사전 판정 규칙) · `cmdr_eval_driver_v37.py` 전체 (75 KB · 머리 주석 포함) · `cmdr_post_v10.py` 전체 · 그 둘이 부르는 도구 (`q_eval_cmdr.py` · `q_eval.py` · `q_metrics.py` · `q_post.py` · `paired_ci.py` · `gpu_guard.py` · `isaac_slot*.py` · `usd_isolate_run_v3.py`) 의 **인터페이스** (인자 · 입출력 · 장치 지정 방식).

**1.2 1042 하드코딩 전수 목록.** v37 드라이버와 post_v10 (과 필요하면 도우미) 에서 **1042 · GPU 1 · 구형 slot (v2) · 구형 registry · 옛 출력 루트 `out/` 에 묶인 곳** 을 줄 번호와 함께 표로: 무엇에 쓰이는가 · 1043 에서 바뀌어야 하는 값 · 바꾸지 않으면 어떤 오류 (또는 조용한 오류) 가 나는가. 최소한 `MODELS` (180 ~ 184) · `EXPERIMENT` (213) · 인계 (hand-over) 가 `result.json` 을 읽는 조건 (87 ~ 88 · 298 ~ 320) · `bundle` 비교 (454 ~ 459) · 코드 해시 (275) · q 도구 호출 (989 ~ 1018) 을 포함.

**1.3 1043 쪽 입력 확인.** 실제 1043 파일 `C:/isaac/ext/go2_rl_robotlab/_eval/out_branch/cmdr_s1043_{off,on}_u4000/` (읽기만): 체크포인트 목록과 해시 (22000 · 24000 포함) · `result.json` · `bundle.json` · `validate_stamp.json` 의 시드 · 부모 · update 수 · 종료 상태. 1042 와 같은 부모 해시 (`c8951b…`) 인지. 1042 의 `MODELS` 가 쓴 체크포인트 (p20000 · off22000 · off24000 · on22000 · on24000) 대응 1043 목록.

**1.4 1042 평가 시간 기록 (읽기만, 이 항목에 한해 `_eval/out/` 읽기 허용).** 1042 쌍 평가의 드라이버 로그 (`_eval/out/cmdr_eval_driver*.json` 같은 것) 에서 실행 한 건의 시간 · 전체 실행 수 · 실제 마감까지 걸린 시간을 읽어 1043 의 예상 실행 수와 시간 (GPU 0 에서) 을 추정한다. 못 읽으면 못 읽었다고 적는다.

**1.5 설계 메모 `codexD/MEMO.md`.** ASTRA 17p 5 절의 요구를 구체화한다:
- 두 길을 비교: **(가)** v37 을 복사한 새 판 (`cmdr_eval_driver_s1043.py` 같은 이름 · 원본 v37 은 동결 · 새 파일) 에서 1042 하드코딩을 등록 입력 (manifest) 하나로 바꾸기 **(나)** 다른 구성 (예: 평가 호출만 새로 짜고 post 는 재사용). 각 길의 변경 줄 수 · 위험 · 필요한 시험 · 예상 작업 시간.
- 등록 입력 (manifest) 항목: 부모 · off · on 경로와 내용 해시 · seed 1043 · bundle 두 쌍 · 완료 근거 · 평가 칸 (**목표 세 칸은 평지 stop03 · fwd01 · fwd02**) · 평가 시드 (1000 ~ 1004 · 각 100 쌍 등 기존 규약) · 관측 · reset · 명령 계약 · 물리 GPU UUID · 별도 출력 · 보고 · 작업 루트 · 마감 · STOP.
- 보호 요건: v3 slot + isolate v3 + gpu_guard + v3 registry (구형 registry 는 읽기만) · attempt 별 USD 루트 · `--expect_conversions` · 공통 변환 lock · 기동 직전 장치 UUID 와 여유 · 코드 · 입력 해시 고정 후 실행 중 변경 검출 · 새 승인 json (ASTRA 승인에 묶이는 코드 manifest) · 1042 등록 해시나 옛 승인 json 을 재사용하지 않음. 1042 결과를 읽어 재사용하지 않고 **부모도 새로 맞춰 수집**.
- **기존 CMD-R 수집 · 집계 규약 (ASTRA 17 가 말한 것) 이 무엇인지** 실제 코드와 문서에서 확인해 요약: 칸 · 시드 · n · 짝 구간 (95 % 하한 > 0) · 동일 가중 평균 ≥ +10 %p · 부모 대비 손실 표시 · 보류 규칙. 코드가 문서와 다르면 그 차이를 적는다.
- 쓰면 안 되는 일반화 (학습 시드 두 개를 합쳐 일반 효과 등) 와 그 문구가 새 판 출력에서 어떻게 강제되는지.
- **lead 가 팀장에게 물어야 할 것** 과 팀장 결정을 바꾸지 않고 먼저 준비할 수 있는 것을 가른다 (규약 교정의 의미 · 부모 승격 · 위험 허용선 · GPU 배정은 팀장 몫).
- 지형 재현 · 회귀 후보 (ASTRA 17p 5 절 표: floating_ring fwd05 · rails fwd03 · gap fwd03) 는 이 평가와 **다른 드라이버 (v6 UNCR 계열)** 가 필요하다. 그 쪽의 최소 변경도 한 문단으로 (코드는 쓰지 않는다).
- 총 작업 추정: 새 판 작성 · 합성 시험 · 변이 시험 · ASTRA 검증 · 기동까지 단계별 시간.

## 2. 보고

`codexD/MEMO.md` 에 머리 다섯 줄 (분류 · 작성 · 근거 · 요지 · 상태) 뒤에 위 항목을 쓰고, 읽은 파일의 경로 · SHA256 표와 **미확인** (실제 GPU 실행 · 새 판 동작 · 시간 추정의 오차) 을 적는다. 끝나면 이슈 foothold-project/foothold-lab#550 에 요약 댓글을 남기고 되읽어 확인한다 (🤖 꼬리말 금지). 이번 단계에서 `_eval` 안에 만든 파일은 0 개여야 하고, 그것을 보고서 마지막에 확인해 적는다.
