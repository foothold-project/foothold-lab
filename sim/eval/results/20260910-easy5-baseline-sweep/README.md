> **[규격 1 · 결함]** 이 폴더의 `gap` 성적은 빗나간 광선을 `-1`(장애물)로 읽던
> 규격으로 잰 것입니다. **보행 능력을 잰 것이 아닙니다.** 규격 2 성적은
> `docs/research/20260911-eval-protocol-v2.md` 를 보십시오.

> 분류: 실험
> 작성: 오흥재 · 2026-09-10 22:50
> 근거: 실측 (Isaac Sim · RTX 5080 x2)
> 요지: 미경험 10종 가운데 정본 조건에서 잘 걷던 성공 5종의 난이도 기준선 스윕. 실패 5종과 같은 격자로 재서 대조가 성립하게 한다.
> 상태: 진행중

# 성공 5종 기준선 스윕 (NVIDIA 공식 체크포인트)

## 왜 도는가

`20260910-difficulty-sweep/` 은 **실패 5종**(gap · rails · pit · stepping_stones ·
floating_ring)만 돌았다. 미경험 10종의 **나머지 다섯**은 기준선 곡선이 없다.
새 모델(`model_1500.pt`)과 대조하려면 기준선이 있어야 하므로 그 빈자리를 채운다.

## 무엇을 쟀는가

| 항목 | 값 |
|---|---|
| 지형 | `discrete_obstacles` · `wave` · `star` · `repeated_boxes` · `repeated_cylinders` |
| 모델 | NVIDIA 공식 체크포인트 (기준선) |
| 모델 SHA256 | `f2aa77bf0349c10ec2a00071162e37123d0cf80f3447c3989c17a618e1b24ad2` |
| 난이도 | 38칸 (아래 격자) |
| 속도 | 0.5 · 1.0 · 1.5 m/s |
| 에피소드 | 칸·지형당 100 (칸마다 500행) |

**모델 해시는 실패 5종 스윕의 `run_manifest.json` 에 적힌 `policy_sha256` 과
같은 값이다**(대조하여 확인). 즉 같은 정책으로 잰 것이고 두 결과는 이어 붙는다.
해시는 칸마다 `runs/<칸>/run_manifest.json` 의 `policy_sha256` 에 자동으로 남는다.

## 난이도 격자

실패 5종 스윕의 `sweep_summary.csv` 에서 **읽어서** 맞췄다(손으로 적지 않았다).

```
vx=0.5   0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0                       (10칸)
vx=1.0   0.02 0.04 0.06 0.08 0.1 0.12 0.14 0.16 0.18                   (세밀화 8칸 + 0.1)
         0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0                           (합 18칸)
vx=1.5   0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0                       (10칸)
```

세밀화 구간(0.02 씩)은 **1.0 m/s 만** 돈다. 실패 5종이 그렇게 했다.

## 조건이 정본과 같은가

09-03 정본은 `--eval_duration 6.0 --command_vx 1.0 --min_progress_m 3.0` 이었다.
스윕 실행기가 **거리 예산 6 m 를 고정**하여 `eval_duration = 6.0 / 속도` 로 맞춘다.
속도가 바뀌어도 갈 수 있는 거리는 안 바뀐다.

| 속도 | 제한 시간 |
|---|---|
| 0.5 m/s | 12.0 s |
| 1.0 m/s | 6.0 s (정본과 동일) |
| 1.5 m/s | 4.0 s |

## 실행 명령 전문

`sim/eval/sweep_run.ps1` 을 그대로 쓴다(실패 5종과 같은 실행기 · 같은 팔).
**`--timeseries` 는 켜지 않았다.** 기준선끼리 조건을 맞추기 위해서다
(실패 5종 스윕에도 시계열이 없다).

GPU 1 · 속도 1.0 의 18칸. 어려운 쪽부터 돌려 벽 자리를 먼저 본다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  C:\work\foothold-lab-easy5\sim\eval\sweep_run.ps1 `
  -Gpu 1 `
  -Cells "1.0:1.0,1.0:0.1,1.0:0.9,1.0:0.8,1.0:0.7,1.0:0.6,1.0:0.5,1.0:0.4,1.0:0.3,1.0:0.2,1.0:0.18,1.0:0.16,1.0:0.14,1.0:0.12,1.0:0.08,1.0:0.06,1.0:0.04,1.0:0.02" `
  -Root "C:\work\foothold-lab-easy5\sim\eval\results\20260910-easy5-baseline-sweep" `
  -TerrainSet unseen10 `
  -Terrains "discrete_obstacles,wave,star,repeated_boxes,repeated_cylinders"
```

GPU 0 · 속도 0.5 와 1.5 의 20칸 (계획 A 가 끝난 뒤).

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  C:\work\foothold-lab-easy5\sim\eval\sweep_run.ps1 `
  -Gpu 0 `
  -Cells "0.5:0.1,0.5:0.2,0.5:0.3,0.5:0.4,0.5:0.5,0.5:0.6,0.5:0.7,0.5:0.8,0.5:0.9,0.5:1.0,1.5:0.1,1.5:0.2,1.5:0.3,1.5:0.4,1.5:0.5,1.5:0.6,1.5:0.7,1.5:0.8,1.5:0.9,1.5:1.0" `
  -Root "C:\work\foothold-lab-easy5\sim\eval\results\20260910-easy5-baseline-sweep" `
  -TerrainSet unseen10 `
  -Terrains "discrete_obstacles,wave,star,repeated_boxes,repeated_cylinders"
```

실행기가 칸마다 `--min_progress_m 3.0 --max_lateral_drift 0.75
--max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --episodes 100
--envs_per_terrain 10` 을 붙인다. `CUDA_VISIBLE_DEVICES` 로 GPU 를 가르므로
`cuda:0` 은 보이는 그 한 대를 뜻한다.

## 실측 소요 시간

칸당 **약 130초** (첫 칸 129.7초 · 500행). 속도 1.0 의 18칸이면 약 39분.
속도 0.5 는 제한 시간이 두 배라 더 걸린다.

## 읽을 때 주의

**진행 상황의 정본은 `_driver-gpu*.log` 가 아니라 `runs/<칸>/run_manifest.json`
이다.** 이 로그에 `tail -f` 를 붙이면 윈도우가 파일을 잠가 기록이 그 자리에서
얼어붙는다(2026-09-10 에 실제로 겪음). `Get-Content -Tail` 로 한 번씩 읽는다.
