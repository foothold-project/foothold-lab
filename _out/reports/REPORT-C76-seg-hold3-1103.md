# C층 비0 env 분할 실패와 샤드 HOLD3
> 분류: C/운영 · 인프라 · 자동화 · 깃 · 웹 · 예산 · 일정
> 작성: 오흥재 · scripter 반영 · 2026-11-03
> 근거: C76 GPU1·GPU0 원영수증, 고정 코드 5027e4ad, CPU 알려진 입력 시험
> 요지: 반복 기술 실패로 GPU가 같은 칸에 묶이는 결함을 막고 첫 프레임 원인 분리용 진단판을 고정했다.
> 상태: HOLD3 CPU 확인, 분할 실패의 물리·렌더 원인 미확인, Kit 실행 대기

## 확인한 것

| 항목 | 원자료와 결과 |
|---|---|
| GPU1 역계단 L0 · 정답 지도 | `D:/mai-tmp/c_layer_m6000_phase1_v2/out/attempts/pyramid_stairs_inv_L0_eval_gt/01~06/child.log`: 여섯 건 모두 첫 프레임 `robot_pixel_evidence`의 `selected robot instance IDs missing`. 해당 `failure.json`은 모두 시드 42, `closed.json`은 실패다. 요약의 `attempts=0`, `technical_failures=6`, `next_ordinal=7`이다. |
| 같은 GPU1 일반 계단 L0 | 성공 `review.json`의 첫 프레임은 env 0 로봇 픽셀 40,577, 다른 로봇 0이다. |
| 배정 차이 | 계획의 일반 계단은 env 0, 역계단은 env 5, GPU0 실패 stage_stairs는 env 22다. 비0 env 라벨 또는 가시성 경로가 공통 원인일 가능성이 있으나 실패 당시 RGB·`idToLabels`가 저장되지 않아 확정할 수 없다. GPU1 고유 결함으로도 단정할 수 없다. |
| 큐 동작 | 고정 `c_layer_queue.py:297-315,520-522`가 기술 실패를 시드 예산에서 빼고 `pending`으로 돌린다. 옛 샤드는 실패 수 상한 없이 같은 칸을 다시 보냈다. |

## HOLD3

커밋 `b23770b3`: `c_layer_shard.py`는 닫힌 `failure.json`과 `closed.json`을 직접 대조해 기술 실패 3회 이상인 칸을 `out/shard_holds/<cell>.json`에 `cell_technical_hold`로 기록하고 다음 배정 칸으로 간다. 성공 영수증이 있으면 먼저 검증하고 통과한다. 열린 시도는 HOLD로 건너뛰지 않는다. 모든 반환 JSON에 `state`가 있다. 기술 실패를 시드 소비나 성공으로 바꾸지 않는다.

| 계획 | 경로 · SHA256 | CPU 확인 |
|---|---|---|
| GPU1 | `D:/mai-tmp/c_layer_m6000_phase1_shards_hold3/phase1_gpu1.json` · `d19e1c198e9e32d27717506a8039d5ec864c0b1a02dd926bc901942a47d27728` | `state=checked`, 108칸, 큐 SHA `8ded3a65...`. 실제 여섯 실패에 대한 `technical_hold`는 `technical_failures=6`, `seed_budget_spent=0`. Lead가 새 래퍼로 반복기를 재기동했다. |
| GPU0 | `D:/mai-tmp/c_layer_m6000_phase1_shards_hold3/phase1_gpu0.json` · `ab3a18dccb1a74e6e15a87eb3f00547708fbe9d809c1b1f93a72ef0a5a779d98` | `state=checked`, 108칸, P0 점유 표식·별도 TMP 유지. GPU0 Kit 실행은 아직 하지 않았다. |

GPU0 한 칸 명령은 기존 반복기와 겹치지 않는 것을 lead가 확인한 뒤 사용한다:

```powershell
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' 'D:/mai-tmp/c_layer_m6000_phase1_shards_hold3/c_layer_shard.py' 'D:/mai-tmp/c_layer_m6000_phase1_shards_hold3/phase1_gpu0.json' --out 'D:/mai-tmp/c_layer_m6000_phase1_gpu0/out' --gpu 0
```

## 첫 프레임 진단판

고정 5027e4ad 녹화기 SHA `94647fd6...`에서 해당 호출부만 바꾼 별도 파일이다. 선택한 USD 로봇 prim 경로·실제 가시성, 첫 RGB PNG, 카메라 투영, `idToLabels` 로봇 경로와 실제 픽셀이 있는 ID를 `segmentation_failure.json`에 남긴다. 분할 라벨이 준비되지 않은 경우 물리 시각·step·root·명령·접촉 시각이 그대로인지 검사하며 최대 8회 렌더만 다시 한다. 라벨이 나타나면 이어 촬영하고, 계속 없으면 실패한다. 가림인지 라벨 생성 문제인지 이 한 편 원자료로 갈라야 한다. 진단 결과를 정본 영상으로 자동 채택하지 않는다.

진단 plan `D:/mai-tmp/c_layer_seg_probe_v1/diagnostic_plan.json` SHA `6f6e0b5dfb10ebd6dfe2cdef56b1753907c7b17daf88e3be6ba3d60bcc674912`, recorder SHA `1be8a4abcc43b1df18b33cb1f6cddf2047514f52a065f33e39a453991e9b5f2e`. 원 큐의 216칸 등록 검사는 CPU에서 `ready=216`이었다. Lead가 GPU1에서 **한 칸만** 확인할 명령:

```powershell
$env:PYTHONPATH='D:/mai-wt/foothold-lab/c-layer-run-5027e4ad'; $env:TMP='D:/mai-tmp/c_layer_seg_probe_v1/tmp'; $env:TEMP=$env:TMP; & 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' 'D:/mai-wt/foothold-lab/c-layer-run-5027e4ad/foothold_s2/eval/c_layer_queue.py' 'D:/mai-tmp/c_layer_seg_probe_v1/diagnostic_plan.json' --out 'D:/mai-tmp/c_layer_seg_probe_v1/out' --run-one --only-cell pyramid_stairs_inv_L0_eval_gt
```

이번 원자료에는 첫 프레임 RGB·라벨이 없으므로 지형 가림, 선택 로봇 USD 가시성, Replicator 분할 라벨 누락 중 어느 것인지 미확인이다. 이 결과를 본 뒤 녹화기 원인 고침과 기존 HOLD 칸의 새 판 재촬영 계획을 별도로 고정해야 한다.

## 시험

`isaac311 python -m pytest -q -p no:cacheprovider --basetemp D:/mai-tmp/scripter/c_layer_shard_hold3b _out/tools/tests/test_c_layer_shard_cpu.py`: 6 passed. `test_c_layer_seg_probe_cpu.py`: 4 passed. `ruff check --select F`와 `pyflakes`는 변경 Python 5개에서 0건. GPU·Kit 미실행.
