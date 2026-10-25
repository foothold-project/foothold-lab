> 분류: 리서치 · 측정 계획 (한 장)
> 작성: 오흥재 (planner) · 2026-10-25 20:54
> 근거: DESIGN-NEXT-draft v0.2.1 §7 · VERIFY-analyst-DN25 v0.2 §6 · 9.5 · 실제 로그 구조를 열어 확인: `train_extra.jsonl`(kl_probe ppo/phi 가지별 · reward_split, B 1501 행 · b50 50 행 · EX-30 창 2 250 행) · `training_trace/conditions_*.npz`(command · reward · reset 스텝별, B 754 파일) · `runners/kl_probe.py` `command_branch`(walk · spin · stand, 부호 분리 없음) · `eval/fixed_terrain.py` `LEVELS_USED = 3` 고정 · `onset_sweep/sweep.sh` · `probe_ab.sh`
> 요지: 여섯 가설 중 넷(H1 노출 · H3 갱신 폭 · H5 시계 동기 · H6 지각 간섭) 은 **이미 있는 로그를 CPU 로 읽으면 지금 잴 수 있다**(GPU 0). GPU1 이 필요한 것은 H4 재평가 3 분과 H2 험지 칸 9 분이고, H2 는 작은 코드 추가(고정 칸 레벨 선택) 가 먼저다. 좌 · 우 분리 KL 과 방향별 보상 항은 다음 학습 전에 넣을 로그 구현이다.
> 상태: v0.2 · lead 요청(10/25 20:5x) · **결과(10/25 22시)**: H4 끝(B1500 재평가 `onset_sweep/b_m1500_repeat/map_modes.json` 좌 0.8705 · 우 0.1451, 원값 대비 −0.003 · −0.003, 한 쌍이라 「큰 잡음 미발견」) · H1 · H3 · H5 는 SOL-25e CPU 측정으로 **못 가름**, H6 좁은 예측(spin phi KL > walk) 은 **반박**(비 0.47~0.81, 다섯 실행, `impl-t5/logs/sol25e/REPORT-sol-25e.md`) · 1 절의 「4.02 · 8.04 s = 첫 2 갱신」 은 틀림(갱신 8 · 16, value loss 최대는 갱신 3) · 남은 것: 로그 셋 구현(좌우 분리 KL · 방향별 track_ang_vel · 전체 env 명령 변경 수) 과 H2(고정 칸 레벨 오프셋 인자 뒤 9 분) · 실행 승인 아님 · 학습 · GPU 기동 없음

# H1~H6 최소 측정 한 장

## 1. 무엇을 가르는지 · 어디서 · 얼마나

| 가설 | 가르는 물음 | 자료가 지금 있나 | 장소 · 예상 시간 | 결과를 읽는 규칙(결과 전 고정) |
|---|---|---|---|---|
| H1 노출 · 보상 합산 | 약한 방향의 노출 시간 · 보상이 강한 방향보다 체계적으로 적은가. 노출 변화 뒤에 그 방향 성적만 움직이는가 | **일부 있음.** `training_trace` 의 command(3) · reward(스칼라 합) · reset 으로 방향별(spin+ · spin− · walk) 노출 스텝 수와 평균 보상은 셀 수 있다. **항별(track_ang_vel) 분리는 없다** → 로그 구현 | CPU(scripter) 약 30 분(추정, B 754 파일 + a50 · b50) · GPU 0 | 방향별 노출 비율이 10 % ± 2 %p 를 벗어나거나, 방향별 평균 보상 차가 §1.1 의 좌우 추종 차와 같은 부호로 50 회 단위 상관 > 0.5 면 H1 후보 강화. 노출만 같다고 H1 기각은 아님(상태 분포 · advantage 미측) |
| H2 지형 커리큘럼 | 레벨 3~5 칸에서 재면 오르내림의 진폭 · 위상이 다른가 | **없음.** `fixed_terrain.py` 는 `LEVELS_USED = 3`(레벨 0~2) 고정 | 구현: 고정 칸에 레벨 시작값 인자(예 `--fixed-terrain-level-offset 3`) 추가 + 답 아는 입력 시험(offset 0 이면 SHA c3884d686592 그대로). 그 뒤 GPU1 3 분 × 3 저장본(m1100 · m1450 · m1500) = **9 분** | 세 저장본의 좌 · 우 순서(1100 높음 · 1450 낮음 · 1500 좌만 높음) 가 험지 칸에서도 같으면 「평가 분포 차이」 후보 약화. 순서가 뒤집히면 H2 강화. 세 점이라 경향만 |
| H3 갱신 폭 | PPO 갱신 직후 행동 분포 이동이 큰 갱신과 50 회 추종 변화가 같이 가는가 | **있음.** `train_extra.jsonl` `kl_probe.ppo.{all,walk,spin}.{mean,p95,max}` 매 갱신(B 1501 · a50 · b50 50 · 창 2 250). **spin 의 좌 · 우 분리는 없음** | CPU 약 20 분(추정) · GPU 0. 좌우 분리는 `kl_probe.command_branch` 에 wz 부호 가지 둘 추가(코드 5 줄 + 시험) | 50 회 구간 spin KL 합(또는 p95 평균) 과 §1.1 추종 변화 절댓값의 Spearman 상관. > 0.5 면 후보 강화. 상관이 있어도 LR 처방을 바로 정하지 않음. actor L2 는 참고열 |
| H4 평가 잡음 | 같은 저장본 · 같은 칸을 다시 재면 중앙값이 얼마나 튀나 | 없음(반복 없음) | GPU1 **3 분**: B1500 을 sweep.sh 와 같은 명령으로 한 번 더(아래 2 절) | 좌 · 우 · 전진 차의 절댓값을 적는다. 차 > 0.10 이면 「큰 잡음 있음」 으로 §5.2 문턱을 다시 본다. 차 ≤ 0.05 라도 **기각이 아니라 「한 쌍에서 큰 잡음 미발견」** 으로 적는다(analyst 9.5) |
| H5 시계 동기 잔존 | 긴 학습에서도 많은 env 가 같은 스텝에 명령을 바꾸는 주기가 남나 | **있음.** `training_trace` 의 command 변화 스텝 · reset 스텝(B 754 파일, 창 1 · 2 트레이스) | CPU 약 20 분(추정) · GPU 0 | 갱신마다 「명령이 바뀐 env 수」 histogram 의 최댓값/평균 비. 첫 2 갱신(흩기 전 4.02 · 8.04 s 봉우리) 과 그 뒤를 나눠 적는다. 뒤 구간에서도 비 > 3 이면 잔존. value loss 봉우리(TensorBoard) 와 시각 대조 |
| H6 지각 · PPO 동시 갱신 간섭 | phi 갱신 직후 행동 분포 이동(KL) 이 spin 에서 walk 보다 크고 추종 하락과 같이 가는가 | **있음.** 같은 파일 `kl_probe.phi.{all,walk,spin}`(B 끝 구간 0.086~0.098, VERIFY-astra-25b 표). 좌 · 우 분리 없음 | H3 과 같은 CPU 분석에서 함께(추가 0) | H3 과 같은 상관을 phi KL 로. phi 가 PPO 보다 상관이 높고 B 자신에서도 같으면 H6 후보 강화. 「GT 판이라 간섭 없음」 은 성립하지 않음(I-E 는 GT 아래서도 변한다) |

**지금 GPU1 로 할 일은 H4 3 분 하나**다. H2 9 분은 코드 추가 뒤. 나머지는 CPU 이며 scripter 몫으로 돌릴 수 있다. 다음 학습 전에 넣을 로그 구현 둘: (가) `kl_probe` spin 부호 분리, (나) 방향별 `track_ang_vel` 항 합계. 둘 다 학습 경로를 바꾸지 않는 기록만이고, 답 아는 입력 시험(가지 수 합 = 전체 n) 을 붙인다.

## 2. GPU1 명령(lead 가 띄움 · sweep.sh 와 같은 틀)

H4 (약 3 분):

```bash
MODULE=foothold_s2.eval.eval_map_modes DEVICE=cuda:1 bash /c/mai/wt/foothold-lab/impl-t5/foothold_s2/eval/run_kit.sh \
  /c/mai/wt/foothold-lab/impl-t5/logs/onset_sweep/b_m1500_repeat \
  --task FootholdS2-Go2-S2-23f-B-v0 \
  --checkpoint /c/mai/wt/foothold-lab/lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main/model_1500.pt \
  --envs 64 --steps 300 --modes eval_gt,eval_pred --fixed-terrain < /dev/null
```

읽기: `b_m1500_repeat/map_modes.json` 의 `assignment_sha256` 이 c3884d686592 로 같은지 먼저, 그 다음 `eval_gt.spin±1.2.yaw_follow_median` 과 원래 값(좌 0.873 · 우 0.15, `fixed_table_b1500_vs_ex25.md`) 의 차.

H2 (구현 뒤, 약 9 분): 위 명령에 `--fixed-terrain-level-offset 3`(제안 이름) 을 더해 `b_m1100_hi` · `b_m1450_hi` · `b_m1500_hi` 세 폴더. 저장본 경로는 `onset_sweep/list_gpu0.txt` 의 b_m1100 · b_m1450 행과 위 model_1500.pt.

## 3. CPU 분석(scripter 몫 제안 · GPU 0)

- 입력: `lead-tmp-start-b/.../ex28-b-main/train_extra.jsonl` · `training_trace/`, `impl-stagger/.../ex31r-{a50,b50}/` 같은 두 파일, `impl-w2/.../ex-30-w2/` 같은 두 파일, 평가는 `onset_sweep/*/map_modes.json`.
- 출력: 한 표(50 회 구간 × {spin KL ppo · phi, 방향별 노출 비율 · 평균 보상, 명령 변경 env 수 비, 좌 · 우 추종 변화}) 와 상관 넷. 수치마다 파일 경로. 상관은 추정이며 인과 확정 아님.
- 답 아는 입력: train_extra 한 행의 `walk.n + spin.n + stand.n == all.n`(위 b50 첫 행 4918 + 1226 + 0 = 6144, 내가 확인) 을 모든 행에 단언.

## 4. 재지 않은 것
- 좌 · 우 분리 KL 과 항별 보상(로그 없음). H2 험지 칸(도구 없음). 시간 추정은 B 754 파일 크기를 안 열어 본 추정.
