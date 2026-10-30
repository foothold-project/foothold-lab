# EX-40 점수기 Kit 인자 수정
> 분류: A/평가
> 작성: 오흥재 · 2026-10-30
> 근거: EX-40 점수기 첫 Kit 로그 `C:/Users/AI-WS01/s2_lab/ex40/scorer_kit_smoke_first/map64/run.log`, 설치 Isaac Lab `app_launcher.py`, `eval_map_modes.py`, `ex40_stand_eval.py`, `run_axis_v2.sh`
> 요지: Kit 캐시 값을 평가기 파서의 `--kit_args` 인자로 전달하고 map64, stand, W57 자식 인자를 실제 소스 정의로 CPU 검사했다.
> 상태: CPU 검사 통과 · Kit 재확인 대기
> 판: v1.0

## 원인과 수정

첫 Kit 자식은 `eval_map_modes.py: error: unrecognized arguments: --/UJITSO/datastore/localCachePath=...`로 종료 코드 2를 냈다. `ex40_eval_once.py`가 캐시 값을 맨 끝의 독립 인자로 전달했기 때문이다. 기존 `basic_gait_kit.py`의 `KIT_CACHE_ARG`를 사용해 `--kit_args=--/UJITSO/datastore/localCachePath=...` 한 토큰으로 넘기고 환경 변수에도 같은 형식을 기록한다. 물리, 평가 지표, 명령, 지형 설정은 바꾸지 않았다.

## CPU 검사

`C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -m pytest -q foothold_s2/tests/test_ex40_scorer_cpu.py foothold_s2/tests/test_ex40_kit_argv_cpu.py` 결과 **10 passed**. 새 시험은 `evaluate()`가 생성한 map64 두 건과 stand 세 건의 자식 인자, `run_axis_v2.sh`의 W57 인자를 검사한다. 설치 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/app/app_launcher.py`와 두 평가기 소스의 실제 `add_argument` AST를 격리 실행해 `parse_args()`를 부른다. Kit를 부르는 import는 실행하지 않는다. 수정된 캐시 인자는 세 종류 모두 수락되며 기존 원시 캐시 인자는 종료 코드 2로 거절된다. 점수기 실행 함수의 자식 호출은 CPU에서 가로챘다. 별도 단계 표가 아직 5단계라 B3a 계획 관문만 이 명령줄 시험에서 대역으로 바꾸었다. 따라서 7단계 runner 통합과 실제 Kit 완료를 이 시험의 통과로 주장하지 않는다.

`C:/Users/AI-WS01/anaconda3/Scripts/ruff.exe check --select F foothold_s2/ex40_eval_once.py foothold_s2/tests/test_ex40_kit_argv_cpu.py` 결과 **All checks passed!**. `git diff --check` 이상 없음.

## 인도

GPU와 Kit는 실행하지 않았다. lead가 고정 사본에서 model14 Kit 짧은 확인을 재실행해야 한다. 변경 파일의 SHA-256은 `EX40-SCORER-KITFIX-SHA256SUMS.txt`에 있다.
