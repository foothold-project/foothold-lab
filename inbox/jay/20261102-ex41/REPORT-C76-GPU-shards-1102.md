# C층 1차 GPU 두 장 배정

> 분류: A/평가
> 작성: 오흥재 · 2026-11-02
> 근거: 고정 5027e4ad 대기열 · D131 m6000 · GPU별 CPU 계획 검증
> 요지: 216칸을 GPU1 앞 108칸과 GPU0 뒤 108칸으로 나누고 기존 GPU1 산출을 보존한다.
> 상태: 계획 검증 완료 · GPU 촬영 미실행

## 계획과 보존

| GPU | 계획 | SHA256 | 지정 출력 | 배정 |
|---|---|---|---|---:|
| 1 | `D:/mai-tmp/c_layer_m6000_phase1_shards/phase1_gpu1.json` | `fba7d8d8c4b7185046f554ef81d18999e08cb3e1639e08fa7ad4c8614fae6db1` | `D:/mai-tmp/c_layer_m6000_phase1_v2/out` | 108 |
| 0 | `D:/mai-tmp/c_layer_m6000_phase1_shards/phase1_gpu0.json` | `9ca1380f53730ad537d3cdbd3c9a7feab19ad9ead76e384071ebbe16e48f76a7` | `D:/mai-tmp/c_layer_m6000_phase1_gpu0/out` | 108 |

- 교집합 0, 합집합 216이다. GPU1의 앞쪽 칸에는 현재 성공 영수증 8편이 있으며 재사용한다. GPU0 출력은 별도 잠금 파일을 쓴다.
- 녹화기와 대기열 파일은 detach 고정 사본 `D:/mai-wt/foothold-lab/c-layer-run-5027e4ad`의 바이트를 유지한다. 대기열 SHA는 `8ded3a65fcc21be31b18520152bbac81902dba310dd4072d76b94ab87a99baff`다.
- 고정 대기열은 등록부 216칸을 요구하므로 두 계획 모두 등록부 전체를 담되 `execution_shard.assigned_cells`를 108칸씩 둔다. **계획을 고정 대기열에 직접 실행하면 216칸 전체를 순회하므로 안 된다.** 아래 래퍼만 배정 목록을 `--only-cell`로 한 칸씩 넘긴다.
- 래퍼 SHA `24f2f5252a09cabf38d023cfd27e4ed38244d387feeb4509e2bd899905eb9891`이며 생성 시 D: 계획 폴더에 복사됐다. GPU0는 `TRAINING_BUSY` 또는 `TRAINING_BUSY_GPU0` 파일이 생기면 다음 칸 전에 양보한다. 원래 C층 관문도 이 표식을 재확인한다. GPU1은 EX-41 평가 P1 표식을 따른다.
- 자식 프로세스의 `TMP`와 `TEMP`는 `D:/mai-tmp/c_layer_gpu0/tmp`와 `D:/mai-tmp/c_layer_gpu1/tmp`로 분리한다. 이 경로 분리의 실제 Kit USD 효과는 미확인이다.

## lead가 칸 경계에서 쓰는 명령

GPU1 기존 반복기는 칸 경계에서 멈춘 뒤 이 래퍼로 전환해야 배정이 겹치지 않는다. 아래 명령은 각각 한 번에 최대 한 칸이다.

```powershell
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' 'D:/mai-tmp/c_layer_m6000_phase1_shards/c_layer_shard.py' 'D:/mai-tmp/c_layer_m6000_phase1_shards/phase1_gpu1.json' --out 'D:/mai-tmp/c_layer_m6000_phase1_v2/out' --gpu 1
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' 'D:/mai-tmp/c_layer_m6000_phase1_shards/c_layer_shard.py' 'D:/mai-tmp/c_layer_m6000_phase1_shards/phase1_gpu0.json' --out 'D:/mai-tmp/c_layer_m6000_phase1_gpu0/out' --gpu 0
```

CPU 점검은 각 명령 끝에 `--check-only`를 붙인다. 실제 촬영은 lead가 기동한다.

## 답을 아는 CPU 증거

- `pytest _out/tools/tests/test_c_layer_shard_cpu.py`: 3 passed. 배정 교집합, GPU0 P0 표식, TMP 분리, 기존 성공 영수증 변조 거절을 확인했다.
- 두 계획에 대해 고정 대기열의 `validate_plan`을 실제로 호출한 `--check-only`가 각각 `ready: 216`, 배정 108을 통과했다. `pyflakes`와 `ruff F` 지적은 0건이다.
- GPU0 학습 표식 파일의 실제 생산과 동시 Kit 두 개의 임시 USD 충돌 여부는 아직 미확인이다. 표식 생산자가 없으면 GPU0는 P0를 알 수 없으므로 lead가 기동 전 연결을 확인해야 한다.
