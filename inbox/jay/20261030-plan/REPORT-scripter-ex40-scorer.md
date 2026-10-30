# EX-40 단계 점수기 CPU 준비
> 분류: A/평가
> 작성: 오흥재 · 2026-10-30
> 근거: EX-40 점수기 의뢰 · D72 7단계 그림자 결정 · OPINION-analyst-EX40-plan-1030.md §4.2 · continuous.py:423~510 · 설치된 W15 실측 JSON
> 요지: 저장본별 64 env 평가, 7단계 그림자 점수, 감시기와 model_14 Kit 짧은 확인 경로를 CPU에서 준비했다.
> 상태: CPU 검증 완료 · 새 7단계 runner 병합 대기 · Kit 미실행 · 평가 시간 미측정
> 판: v1.0

## 구현

| 경로 | 하는 일 | 확인 |
|---|---|---|
| `foothold_s2/ex40_score_watch.py` | m500부터 250 간격 저장본의 크기와 SHA 안정 확인, 실제 단계 로그 대조, 평가 한 건씩 실행, 실패 HOLD, 중복 방지, 평가가 간격보다 오래 걸리면 낡은 미평가본 건너뜀 | 합성 정상, 실패, 중복, 지연 CPU 시험 |
| `foothold_s2/ex40_eval_once.py` | 고정 코드판에서 W15 13명령 3모드, 단계별 추가 칸, 평지 정지, B2 이후 W57을 순차 Kit 자식으로 실행. cuda:1, 숨김 창, 단계별 시간과 rc 영수증 | 자식 기동은 아직 미실행 |
| `foothold_s2/ex40_score.py` · `curriculum/ex40_score_config.json` | §4.2의 GT/지도 끔 판정, PRED 기록, 생존·추종·발별 정지·B2 목표정지·B3a 걸으며 회전, B3b 낮은 제자리 회전, B3c 저속 축, 단계 첫 저장본 대비 하락 HOLD. `continuous.py`가 읽는 `foothold-ex40-score/2` 파일 | 실제 Runtime parser 양성 시험 |
| `foothold_s2/eval/ex40_stand_eval.py` | 평지, 64 env, 3초 중 첫 1초 제외, 네 발의 1N 접촉·Fz/mg·충돌반경 보정 간격과 몸 속도 원시 NPZ/JSON | CPU 구조 점검만, 실제 물리값 미측정 |
| `foothold_s2/ex40_score_smoke.py` | v5의 `model_14.pt`로 한 명령·한 지도 모드·평지 정지 64 env Kit 짧은 확인과 원자료 해시 판독 | 합성 영수증 양성/결측 CPU 시험 |

B1은 기존 8명령에 걸으며 회전 `walk±0.5` 두 칸을 EX-40 전용 묶음에서 추가 판정한다. 좌우 반전과 정지 후 재출발 시퀀스는 원자료와 단계 점수에 별도 진단값으로 기록한다. §4.2가 이 시퀀스의 수치 문턱을 주지 않아 임의 문턱은 만들지 않았다. B2는 W57 목표정지, B3a는 `walk±1.0`, B3b는 `spin±0.3`, B3c는 저속 0.1/0.2/0.3을 단계적으로 더 판정한다. B0~B3c의 PRED는 기록이고, T0는 세 모드를 그림자 점수로 측정한다. D72에 따라 `promotion: fixed, shadow_gate: true`만 감시기에서 허용하며 이 점수가 자동 승급시키지 않는다.

## CPU 검증

- `isaac311/python.exe -m pytest -q foothold_s2/tests/test_ex40_scorer_cpu.py foothold_s2/tests/test_axis_v2_run_cpu.py foothold_s2/tests/test_axis_v2_cells.py`: **31 passed**.
- 기존 `test_w55_continuous_cpu.py`와 `test_ex40_v4_cpu.py`까지 포함한 관련 회귀: **56 passed**.
- 실제 완료된 EX-39B W15 `m4501` 평가 JSON을 새 파서로 읽어 **64 env, 13명령, 64칸, 시퀀스 3종**을 확인했다. 원본: `C:/Users/AI-WS01/s2_lab/basic_gait_runs/eval_w15/ex39b/m4501/attempt_1793337758535148100/map64/map_modes.json`.
- `ruff check --select F` 변경 Python 전부 **0건**. 새 모듈의 `pyflakes` **0건**. `eval_map_modes.py`는 기존 선적재 import 때문에 pyflakes 단독 0건 계약 대상에서 제외하고 ruff F로 확인했다.
- 감시기와 짧은 확인기 CLI의 `--help`를 실제 isaac311 interpreter로 호출했다. GPU·Kit은 실행하지 않았다.
- `continuous.py`의 `Runtime.on_checkpoint()`가 점수의 단계·일정 SHA·체크포인트 SHA·시각·verdict를 수용하는 양성 시험, 실패 영수증 HOLD, 파일 변경과 걸으며 회전 오차·GT 사용 누락 변이를 포함한다. 점수 설정 파일 SHA는 점수에 기록하지만 현재 `continuous.py`가 독립 재검증하지 않는다.

## lead가 실행할 첫 Kit 짧은 확인

다음은 **실행 준비 명령**이며 이 작업에서 실행하지 않았다. 코드판을 커밋하고 reviewer 검토 뒤 빈 출력 폴더에 사용한다.

```powershell
cd C:/mai/wt/foothold-lab/scripter-ex40-scorer
$env:CUDA_DEVICE_ORDER='PCI_BUS_ID'
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m foothold_s2.ex40_score_smoke --checkpoint C:/Users/AI-WS01/s2_lab/ex40/v5_kit_smoke_20261030_lead1/smoke/EX-40-B-kit-smoke_20261030_195209_73840/model_14.pt --out C:/Users/AI-WS01/s2_lab/ex40/scorer_kit_smoke_first
```

본 감시기 CLI는 `python -m foothold_s2.ex40_score_watch --run-dir <실제 학습 로그 폴더> --out-root <새 평가 폴더> --score-dir <학습 기동 때 지정한 curriculum-score-dir와 동일한 절대경로> --arm B --table <D72 7단계 일정 파일>`이다. 실행 코드와 입력은 고정 사본에서 읽으며 Kit 자식은 한 번에 하나다. **현재 이 사본의 `continuous.py`와 `ex40.yaml`은 아직 5단계**여서 본 감시기는 의도적으로 시작 거절한다. runner 담당자의 D72 7단계 코드와 일정이 합쳐진 고정 사본에서만 위 CLI를 쓴다. model_14 짧은 확인은 기존 B0 경로를 별도 허용한다.

## 한계와 다음 검증

Kit 짧은 확인, D72 runner 병합, 평지 접촉 센서 실제값, W57 한 자식 완료, 저장본 하나 평가 시간은 미확인이다. 첫 Kit에서 출력 JSON의 64 env·지도 선택·발별 Fz/간격·소스 해시를 대조하고, 평가 시간이 체크포인트 250회 간격보다 짧은지 재야 한다. RR 탐침의 지면 근사와 이번 평지 충돌반경 간격 정의도 실제 값으로 대조한다.

R6·R20에 따라 가짜 영수증만으로 Kit 통과를 선언하지 않는다. R21에 따라 시간은 상한이며 회차 완료 보장이 아니다. R24와 M prelaunch-real-path-check에 따라 lead가 실제 산출을 읽어 처음과 끝을 확인해야 한다. M dont-edit-a-running-shell-script에 따라 운영 중인 학습 사본은 수정하지 않았다.

## 이력

| 판 | 내용 |
|---|---|
| v1.0 | 단계 점수, 순차 감시기, 기존 W15·W57 연결, model14 Kit 확인 경로 CPU 준비 |
