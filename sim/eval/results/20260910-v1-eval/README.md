> **[규격 1 · 결함]** 이 폴더의 `gap` 성적은 빗나간 광선을 `-1`(장애물)로 읽던
> 규격으로 잰 것입니다. **보행 능력을 잰 것이 아닙니다.** 규격 2 성적은
> `docs/research/20260911-eval-protocol-v2.md` 를 보십시오.

> 분류: 실험
> 작성: 오흥재 · 2026-09-10 22:52
> 근거: 실측 (Isaac Sim · RTX 5080 x2)
> 요지: 새로 학습한 모델(model_1500.pt)을 정본 조건 한 점에서 16종 전부에 대해 잰다. 1차 배포 판단의 근거.
> 상태: 진행중

# 새 모델 v1 · 정본 조건 한 점 평가 (계획 A)

## 왜 이 한 점인가

난이도 곡선 전체(계획 B)는 오래 걸린다. **정본 조건 한 점이면 1차 배포 판단이
선다.** 그래서 이것을 먼저 돌린다.

## 모델

| 항목 | 값 |
|---|---|
| 산출물 | `C:\isaac\IsaacLab\logs\rsl_rl\unitree_go2_gap_nvidia\2026-09-10_20-47-27_20260910_nvidia_gap_repro_seed42_iter1500\model_1500.pt` |
| SHA256 | `54064c779eda52b6f35ebe9d016388031e9d1e7fda9cc6b3aea386f9c5024f5c` |
| 크기 | 6,882,293 바이트 |
| 저장 시각 | 2026-09-10 22:22 |
| 기준선 모델 | NVIDIA 공식 · SHA256 `f2aa77bf0349c10ec2a00071162e37123d0cf80f3447c3989c17a618e1b24ad2` |

**학습이 끝난 근거**: `model_1500.pt` 파일이 실제로 있고, 크기가 직전
체크포인트(`model_1475.pt` 6,882,293 바이트)와 같다. 로그의 「완료」 문구가 아니라
파일로 확인했다. 확인 시각 22:40 에 GPU 0 은 0 MiB · 0% 로 비어 있었다.

해시는 칸마다 `runs/<칸>/run_manifest.json` 의 `policy_sha256` 에 자동으로 남는다.

## 격자

| 항목 | 값 |
|---|---|
| 지형 | 16종 = 미경험 10 (`unseen10`) + 기존 6 (`rough6`) |
| 난이도 | 0.5 한 점 |
| 속도 | 0.5 · 1.0 · 1.5 m/s |
| 에피소드 | 지형·칸당 100 |
| 합 | 16 x 3 x 100 = **4,800 에피소드** |
| 시계열 | **켬** (`--timeseries` · HUD 재료) |

**지형 집합 둘을 한 번에 못 돈다.** `unseen10` 과 `rough6` 은 환경 설정 모듈이
서로 다르다(`generalization_env_cfg` · `rough6_env_cfg`). 그래서 결과 폴더를
`unseen10/` 과 `rough6/` 로 갈라 순서대로 돈다. 칸 이름이 양쪽 다
`v1.0-d0.5` 라서, 폴더를 안 가르면 **뒤엣것이 앞엣것을 덮어쓴다.**

## 조건이 기준선과 같은가

09-03 정본은 `--eval_duration 6.0 --command_vx 1.0 --min_progress_m 3.0` 이었다.
거리 예산 6 m 를 고정해 `eval_duration = 6.0 / 속도` 로 맞춘다(앞선 스윕과 같은 식).

| 속도 | 제한 시간 |
|---|---|
| 0.5 m/s | 12.0 s |
| 1.0 m/s | 6.0 s (정본과 동일) |
| 1.5 m/s | 4.0 s |

## 실행 명령 전문

`sim/eval/sweep_run.ps1` 에 `-Timeseries` 스위치를 더해서 쓴다. 하네스에는
`--timeseries` 가 오늘(#394) 들어왔는데 **스윕 실행기에는 그 팔이 없었다.**
9줄짜리 추가이고, 안 주면 예전과 똑같이 돈다.

```powershell
$runner = "C:\work\foothold-lab-easy5\sim\eval\sweep_run.ps1"
$base   = "C:\work\foothold-lab-easy5\sim\eval\results\20260910-v1-eval"
$ckpt   = "C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-10_20-47-27_20260910_nvidia_gap_repro_seed42_iter1500/model_1500.pt"
$cells  = "1.0:0.5,0.5:0.5,1.5:0.5"

& $runner -Gpu 0 -Cells $cells -Root (Join-Path $base "unseen10") `
    -TerrainSet unseen10 -Terrains "all" -Checkpoint $ckpt -Timeseries

& $runner -Gpu 0 -Cells $cells -Root (Join-Path $base "rough6") `
    -TerrainSet rough6 -Terrains "all" -Checkpoint $ckpt -Timeseries
```

실행기가 칸마다 `--min_progress_m 3.0 --max_lateral_drift 0.75
--max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --episodes 100
--envs_per_terrain 10` 을 붙인다.

## 시계열

`--timeseries` 는 `pyarrow` 가 있어야 돈다. 이 기계의 `isaac311` 에 21.0.0 이
깔려 있다(확인함). 켜면 칸마다 `runs/<칸>/timeseries/ep****.parquet` 이 쌓인다.
**깃발이 받아들여졌는지가 아니라 파일이 실제로 생기는지를 봤다** · 첫 칸에서
640개가 쌓이는 것을 셌다.

## 함정 기록

- **`conda run` 을 둘 동시에 띄우지 않는다.** 활성화 임시파일을 서로 밟아 한쪽이
  exit=3 으로 죽는다. 실행기는 환경의 `python.exe` 를 직접 부른다.
- **`sweep_run.ps1` 은 UTF-8 BOM 이 있어야 한다.** BOM 없이 저장하면 PowerShell
  5.1 이 한글 주석을 ANSI 로 읽어 59행에서 파싱이 깨진다. 그러면 `Start-Process`
  는 PID 를 정상으로 돌려주는데 **프로세스는 곧바로 죽는다.** 22:47 에 실제로
  겪었고, PID 만 보고 살아 있다고 믿었으면 못 잡았을 실패다. 고친 뒤
  `[Parser]::ParseFile` 로 파싱을 먼저 시험하고 띄웠다.
- **`tail -f` 를 driver 로그에 붙이지 않는다.** 윈도우가 파일을 잠가 기록이
  얼어붙는다. 진행 상황의 정본은 `runs/<칸>/run_manifest.json` 이다.
