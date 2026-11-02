# C층 정본 촬영기 C1~C6 CPU 인도
> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 · scripter 반영 · 2026-11-02
> 근거: D131, W75/W76, EX-40 model_6000.pt, CPU 시험
> 요지: m6000 고정 계획 216칸과 한 칸 시험 경로를 준비하고 영상 품질 및 영수증 관문을 연결했다.
> 상태: CPU 확인, Kit 한 편 미확인

## 고정 입력

- 정본 후보: `C:\Users\AI-WS01\s2_lab\ex40_main_20261031_041313\main\EX-40-B-main_20261031_041337_26240\model_6000.pt`.
- 저장본 SHA256: `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5`.
- 계획: `C:\Users\AI-WS01\s2_lab\c_layer_m6000\plan.json`, SHA256 `3c3b214ca97327a26bf7327ba33bc0bf3e20c5da04c93035cb07149d27d02587`.
- 계획의 216칸 등록 확인. 연속 첫 칸과 듬성 `gaps` 첫 칸에서 실제 기록기 `--plan-only` 각각 rc 0. Kit 생성과 촬영은 미실행.
- `plan.before-queue-pin.json`은 큐 SHA 고정 전의 CPU 초안이며 실행 대상이 아니다.

## 닫은 항목

| 항목 | 커밋 | CPU 근거 |
|---|---|---|
| C1 기술 실패와 영상 결과 시드 분리 | `bc9f8223` | 실패 4회 뒤 같은 첫 시드 재시도 |
| C2 지형 생성 시드 고정 | `b3a48b22` | 촬영 시드 42~45와 기하 시드 분리 |
| C3 HUD 합성 영상 정본화 | `223977b9` | 기존 m6000 원자료 합성 화면 확인 |
| C4 전 프레임 영상 감사 | `ff8ec9a0` | CPU 반례와 기존 m6000 375프레임 통과 |
| C5 공용 재생 목록 | `03c3fda7` | 확인된 영수증만 전체·실패 목록에 반영 |
| C6 m6000 계획 · 한 칸 시험 | `c60f0cec`, `5ad7c76a` | 27 시험 PASS, ruff F 0, 계획 216칸 완비 |

## lead 첫 한 편 명령

작업 폴더 `C:\mai\wt\foothold-lab\scripter-w75-w76`에서 아래 명령을 쓴다. 실행 전 GPU 작업 상태와 세 우선순위 표식의 실제 생산자를 확인해야 한다. 계획은 `cuda:1`로 고정됐다.

```powershell
$env:PYTHONPATH='C:/mai/wt/foothold-lab/scripter-w75-w76'
$env:PYTHONUTF8='1'
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m foothold_s2.eval.c_layer_queue C:/Users/AI-WS01/s2_lab/c_layer_m6000/plan.json --out C:/Users/AI-WS01/s2_lab/c_layer_m6000/out --run-one --only-cell pyramid_stairs_L0_eval_gt
```

`--only-cell`도 216칸 계획 전체를 검증한 뒤 목표 칸 한 시드만 찍는다. 한 번 호출하면 영상 한 편이다. 첫 Kit 영상의 실제 450프레임, 품질 검사, 지도 모드, 정본 영수증, 재생 목록은 lead가 확인해야 한다.

## 남은 막음

계획의 `TRAINING_BUSY`, `EVALUATION_BUSY`, `A_LAYER_BUSY` 경로는 지금 생산자를 확인하지 못했다. 표식이 없다는 사실만으로 상위 GPU 작업이 없다고 추론할 수 없다. 무인 전체 대기열은 표식 생산 또는 GPU 작업 관리판 연동 전까지 시작하지 않는다. 첫 한 편은 lead가 GPU 상태를 직접 확인한 뒤 실행한다.
