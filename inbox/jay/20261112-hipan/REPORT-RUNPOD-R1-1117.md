> 분류: B/항법 · 외부 GPU 예행 결과 (Runpod R1, 4090 두 번과 5090 한 번)
> 작성: sonnet-code-lx · 2026-11-17 12:1x
> 근거: `/home/jay/data/foothold/hipan/runpod_r1/{4090,4090b,5090}/` (`check.txt` · `remote/*.log` · `remote/vram_*.txt`) · `/home/jay/mai/tmp/lead/runpod_r1/r1.log` · 실행기 `/home/jay/mai/tmp/lead/runpod_r1.py` (이미지 `nvcr.io/nvidia/isaac-lab:2.3.2` · Isaac Sim 5.1 · Python 3.11)
> 요지: 세 Pod 모두 드라이버 595.91 · CUDA 13.2 였고, 카메라 벤치 아홉 번이 전부 시작 직후 `librtx.scenedb.plugin.so` 에서 Segmentation fault 로 죽었다. Go2 rough 4096 env 학습은 4090 이 회당 약 3.75 초, 5090 이 약 3.11 초로 돌았다. 5090 은 26 분 켜 둬서 약 0.61 달러가 들었고 (상한 20 분 초과), Pod 중지 API 는 404 였다. 세 Pod 합계 약 0.88 달러.
> 상태: 확정 (원자료에서 읽은 값) · 5090 비용과 시간은 로그 시각으로 계산한 값 · R3 칸은 lead 가 채움

## 한 줄 결론

595.91 / CUDA 13.2 호스트에서는 Isaac Sim 5.1 (Isaac Lab 2.3.2) 의 카메라가 시작도 못 한다. 같은 이미지의 Go2 학습은 같은 호스트에서 정상으로 돌았으니, 문제는 GPU 종류가 아니라 렌더 경로 (rtx.scenedb) 와 드라이버 조합이다. 우리 기기 (드라이버 580.178 · CUDA 13.0) 에서는 같은 벤치가 된다 (lead 전달 · 이 보고서에서 다시 재지는 않음).

## GPU 별 표

| 항목 | 4090 (첫 번째) | 4090b (두 번째) | 5090 |
|---|---|---|---|
| 드라이버 / CUDA | 595.91.07 / 13.2 | 595.91.07 / 13.2 | 595.91.07 (`go2.log` · `bench_*.log` 의 Kit 표) · CUDA 칸은 `check.txt` 가 없어 미확인 |
| GPU 메모리 | 24564 MiB | 24564 MiB | 32853 MB (Kit 표) |
| 만든 시각 → RUNNING | 02:31:05 → 353 초 | 02:51:03 → 347 초 | 03:00:09 → 523 초 |
| sshd 준비까지 | 376 초 | 369 초 | 527 초 |
| 켜 둔 시간 | 550 초 | 543 초 | 1574 초 (26.2 분) |
| 시간당 단가 | 0.89 달러 | 0.89 달러 | 1.39 달러 |
| 비용 | 0.136 달러 (`r1.log`) | 0.134 달러 (`r1.log` 누적 0.27 에서 계산) | 약 0.61 달러 (1.39 × 1574 초 / 3600 · `r1.log` 에 비용 줄 없음, 계산값) |
| Go2 rough 4096 env, 10 회 | 89 초 · rc 0 | 87 초 · rc 0 | 학습은 돌았음 (10 회 줄 있음) · 총 초는 `check.txt` 없어 미확인 |
| 회당 시간 (10 회의 중앙 / 최소 / 최대) | 3.75 / 3.72 / 5.42 초 | 3.75 / 3.54 / 5.35 초 | 3.11 / 3.04 / 4.37 초 |
| 처리량 (마지막 회 `steps/s`) | 25671 | 26082 | 31128 |
| VRAM 최대 | Go2 6959 MiB | Go2 6959 MiB | 8183 MiB (Go2 구간으로 보임, 아래 주의) |
| 카메라 벤치 | 셋 모두 실패 | 셋 모두 실패 | 셋 모두 실패 |

회당 시간의 최대 값은 첫 회 (컴파일 · 워밍업) 가 들어간 값이라, 속도는 중앙 값으로 읽는다. 5090 은 4090 보다 회당 약 17 % 빠르지만 단가가 1.56 배라서 시간당 비용 대비로는 4090 쪽이 싸다 (같은 10 회에 4090 약 0.0093 달러 · 5090 약 0.0120 달러, 회당 시간 × 단가로 계산).

## 카메라 벤치 셋 (Isaac Lab 2.3.2 `scripts/benchmarks/benchmark_cameras.py`)

| 벤치 | 4090 | 4090b | 5090 |
|---|---|---|---|
| 광선 (ray caster) depth 180x320 · N=128 | rc 1 · 32 초 · Segfault | rc 1 · 31 초 · Segfault | Segfault (`bench_rc128.log`) |
| 광선 depth 180x320 · N=512 | rc 1 · 23 초 · Segfault | rc 1 · 24 초 · Segfault | Segfault (`bench_rc512.log`) |
| tiled depth 180x320 · N=128 | rc 1 · 24 초 · Segfault | rc 1 · 23 초 · Segfault | Segfault (`bench_td128.log`) |

- 아홉 로그 모두 `Segmentation fault (core dumped)` 1 줄, `librtx.scenedb.plugin.so` 가 든 줄 5 줄, `[Fatal]` 59 줄로 같다 (grep 으로 센 값). 크래시 덤프는 `/isaac-sim/kit/data/Kit/Isaac-Sim/5.1/` 아래에 쓰였다.
- 죽은 시점이 Kit 시작 후 200 ms ~ 4 초라서, 벤치 내용 (광선인지 tiled 인지) 이 달라도 결과가 같다. 광선 카메라 (렌더 안 쓰는 쪽) 도 같은 길로 죽는 것은 `benchmark_cameras.py` 가 Kit 와 렌더 확장을 먼저 띄우기 때문으로 보이나, 그 원인은 로그만으로는 확정 못 했다 (미확인).
- 이 시간 동안의 VRAM 최대는 4090 이 619 MiB, 5090 이 751 MiB 로 시작 단계 값뿐이다. 카메라 렌더 메모리는 한 번도 잴 수 없었다.

## 잘못한 것 (변명 없이)

1. **5090 을 상한 20 분보다 길게, 26.2 분 켜 뒀다.** 비용 약 0.61 달러로 한 대에 계획 (20 분 ≈ 0.46 달러) 보다 0.15 달러 더 들었다. 원자료: 03:09:52 에 카메라 벤치 셋이 끝난 뒤 GPU 가 약 15 분 (`vram_td128.txt` 에서 100 MiB 미만 899 초) 놀았고, Go2 는 03:25 쯤에야 시작해 77 초 돌았다 (100 MiB 이상 77 초). 놀았던 15 분의 원인은 로그에 없어 미확인이다 (원격 `check.txt` 도 5090 은 못 받았다). 실행기가 Pod 안 확인을 nohup 으로 분리하지 않고 ssh 한 세션에 매달아 둔 구조가 의심되나 확인한 것은 아니다. 이 구조는 R2 · R3 실행기에서 Pod 안 nohup + 끝 표식 파일 방식으로 고쳤다.
2. **Pod 중지 API 가 404 였다.** `/pods/<id>/stop` 과 `/pods/<id>/actions/stop` 이 둘 다 404 (`The requested path was not found.`) 여서, 마지막 수단 `DELETE /pods/<id>` (204) 로 지웠다. 이후 같은 id 조회는 404 (지워짐 확인). 이 계정의 v2 REST 에는 stop 이 없고 지우기만 있는 것으로 R2 · R3 실행기에 반영했다.
3. **5090 의 `check.txt` 를 못 받았다.** 5090 쪽 원격 폴더에 `remote/*.log` 와 `vram_*.txt` 는 있으나 확인 요약 파일이 없어서, 이 표의 5090 드라이버 · CUDA · Go2 총 초는 다른 로그에서 읽거나 「미확인」 으로 뒀다. 또 5090 의 VRAM 파일 이름이 `vram_td128.txt` 하나뿐인 것은 tiled 벤치용 측정기가 Go2 구간까지 안 꺼져서 Go2 값이 거기 섞인 것으로 보인다 (파일 길이 976 줄 = 03:09:52 ~ 03:26:18 과 맞음). 그래서 8183 MiB 가 Go2 최대라는 것은 추정이다.
4. **L40S · 5090 만들기 실패가 여러 번 있었다** (`r1.log`: `There are no longer any instances available`, 02:31 · 02:40 · 03:00). 재고 문제이고 비용은 없었다. 5090 은 03:00 에 세 번째 시도로 잡혔다.

## 원자료 위치와 재는 법

- 표의 시간 · 비용: `r1.log` 의 `created` · `status RUNNING` · `sshd ready` · `elapsed_s` · `spent_total_usd` 줄. 5090 은 `created 03:00:09` 와 `stop` 줄 (03:26:23) 의 차 1574 초에 단가를 곱함.
- 회당 시간: `go2.log` 의 `Iteration time` 10 줄의 중앙 · 최소 · 최대. `steps/s` 는 마지막 `Computation` 줄.
- 벤치 실패: `bench_*.log` 의 `Segmentation fault` · `librtx.scenedb` · `[Fatal]` 줄 수.
- VRAM: `vram_*.txt` (1 초마다 `nvidia-smi` 의 memory.used) 의 최대.

## 이 보고서가 말하지 않는 것

- 595 드라이버 + Isaac Sim 6.x (Isaac Lab 3.0) 에서는 카메라가 되는지: 아래 R3 칸.
- 580 대 드라이버 호스트가 Runpod 에 있는지: R2 (`allowedCudaVersions ["13.0"]`) 가 그 시험이었고, 승인 전이라 돌리지 않았다.
- 크래시의 정확한 원인: 로그에 `librtx.scenedb` 스택만 있고, 드라이버 595 가 원인이라는 것은 우리 기기 580.178 에서는 같은 벤치가 된다는 비교로 세운 추정이다.

## R3 (isaac-lab 3.0 · 595) 결과: lead 가 채움

| 항목 | 값 |
|---|---|
| Pod · 시각 | |
| 드라이버 / CUDA | |
| 광선 depth 180x320 · N=128 | |
| tiled depth 180x320 · N=128 | |
| VRAM 최대 | |
| Go2 rough 10 회 (`Isaac-Velocity-Rough-UnitreeGo2`) | |
| 비용 | |
| 판정 | |
