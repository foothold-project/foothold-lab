# `floating_ring` · 난이도 스윕 원시 기록

> 분류: 실험
> 작성: 오흥재 · 2026-09-10
> 근거: 실측 (Isaac Lab · NVIDIA 공식 체크포인트 · RTX 5080 2대)
> 요지: `floating_ring` 한 종을 난이도 10단계 x 속도 3단계로 3000판 잰 원시 기록
> 상태: 초안

이 폴더의 `floating_ring_sweep.csv` 는 **모아 놓은 것**이고, 정본 원시 파일은
`../../runs/<칸>/generalization_raw.csv` 입니다. 모으면서 더한 열은
맨 앞 셋(`difficulty` · `command_vx` · `eval_duration_s`)뿐이고,
나머지 24열은 `metrics.RAW_COLUMNS` 그대로입니다.

## 무엇을 쟀나

| 항목 | 값 |
|---|---|
| 지형 | `floating_ring` |
| 난이도 | 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0 |
| 명령 속도 | 0.5 m/s, 1.0 m/s, 1.5 m/s |
| 칸 | 30 |
| 판 | 3000 |
| 정책 sha256 | `f2aa77bf0349c10ec2a00071162e37123d0cf80f3447c3989c17a618e1b24ad2` |

**거리 예산을 6 m 로 고정했습니다.** 속도가 바뀌어도 로봇이 갈 수 있는
거리는 6 m 로 같고, 제한 시간만 `6.0 / 속도` 로 바뀝니다
(12초 · 6초 · 4초). 그래서 속도축을 가로질러 전진거리를 그대로 비교할 수
있습니다. 통과선은 세 속도 모두 3 m 입니다.

## 그대로 다시 돌리는 법

아래는 **기계가 `run_manifest.json` 에 적은 `argv` 를 그대로 옮긴 것**입니다.
사람이 옮겨 적은 것이 아닙니다. Windows 에서는 앞에
`OMNI_KIT_ACCEPT_EULA=YES` 와 `CUDA_VISIBLE_DEVICES=<번호>` 가 필요합니다.

```bash
# v0.5-d0.1
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.1 --episodes 100 --envs_per_terrain 10 --eval_duration 12 --command_vx 0.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v0.5-d0.1 --note "difficulty sweep 20260910 | vx=0.5 difficulty=0.1 | gpu0"

# v0.5-d0.2
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.2 --episodes 100 --envs_per_terrain 10 --eval_duration 12 --command_vx 0.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v0.5-d0.2 --note "difficulty sweep 20260910 | vx=0.5 difficulty=0.2 | gpu0"

# v0.5-d0.3
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.3 --episodes 100 --envs_per_terrain 10 --eval_duration 12 --command_vx 0.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v0.5-d0.3 --note "difficulty sweep 20260910 | vx=0.5 difficulty=0.3 | gpu0"

# v0.5-d0.4
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.4 --episodes 100 --envs_per_terrain 10 --eval_duration 12 --command_vx 0.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v0.5-d0.4 --note "difficulty sweep 20260910 | vx=0.5 difficulty=0.4 | gpu0"

# v0.5-d0.5
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.5 --episodes 100 --envs_per_terrain 10 --eval_duration 12 --command_vx 0.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v0.5-d0.5 --note "difficulty sweep 20260910 | vx=0.5 difficulty=0.5 | gpu0"

# v0.5-d0.6
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.6 --episodes 100 --envs_per_terrain 10 --eval_duration 12 --command_vx 0.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v0.5-d0.6 --note "difficulty sweep 20260910 | vx=0.5 difficulty=0.6 | gpu1"

# v0.5-d0.7
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.7 --episodes 100 --envs_per_terrain 10 --eval_duration 12 --command_vx 0.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v0.5-d0.7 --note "difficulty sweep 20260910 | vx=0.5 difficulty=0.7 | gpu1"

# v0.5-d0.8
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.8 --episodes 100 --envs_per_terrain 10 --eval_duration 12 --command_vx 0.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v0.5-d0.8 --note "difficulty sweep 20260910 | vx=0.5 difficulty=0.8 | gpu1"

# v0.5-d0.9
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.9 --episodes 100 --envs_per_terrain 10 --eval_duration 12 --command_vx 0.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v0.5-d0.9 --note "difficulty sweep 20260910 | vx=0.5 difficulty=0.9 | gpu1"

# v0.5-d1.0
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 1 --episodes 100 --envs_per_terrain 10 --eval_duration 12 --command_vx 0.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v0.5-d1.0 --note "difficulty sweep 20260910 | vx=0.5 difficulty=1 | gpu1"

# v1.0-d0.1
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.1 --episodes 100 --envs_per_terrain 10 --eval_duration 6 --command_vx 1 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.0-d0.1 --note "difficulty sweep 20260910 | vx=1 difficulty=0.1 | gpu0"

# v1.0-d0.2
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.2 --episodes 100 --envs_per_terrain 10 --eval_duration 6 --command_vx 1 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.0-d0.2 --note "difficulty sweep 20260910 | vx=1 difficulty=0.2 | gpu0"

# v1.0-d0.3
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.3 --episodes 100 --envs_per_terrain 10 --eval_duration 6 --command_vx 1 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.0-d0.3 --note "difficulty sweep 20260910 | vx=1 difficulty=0.3 | gpu0"

# v1.0-d0.4
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.4 --episodes 100 --envs_per_terrain 10 --eval_duration 6 --command_vx 1 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.0-d0.4 --note "difficulty sweep 20260910 | vx=1 difficulty=0.4 | gpu0"

# v1.0-d0.5
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.5 --episodes 100 --envs_per_terrain 10 --eval_duration 6 --command_vx 1 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.0-d0.5 --note "difficulty sweep 20260910 | vx=1 difficulty=0.5 | gpu0"

# v1.0-d0.6
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.6 --episodes 100 --envs_per_terrain 10 --eval_duration 6 --command_vx 1 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.0-d0.6 --note "difficulty sweep 20260910 | vx=1 difficulty=0.6 | gpu1"

# v1.0-d0.7
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.7 --episodes 100 --envs_per_terrain 10 --eval_duration 6 --command_vx 1 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.0-d0.7 --note "difficulty sweep 20260910 | vx=1 difficulty=0.7 | gpu1"

# v1.0-d0.8
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.8 --episodes 100 --envs_per_terrain 10 --eval_duration 6 --command_vx 1 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.0-d0.8 --note "difficulty sweep 20260910 | vx=1 difficulty=0.8 | gpu1"

# v1.0-d0.9
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.9 --episodes 100 --envs_per_terrain 10 --eval_duration 6 --command_vx 1 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.0-d0.9 --note "difficulty sweep 20260910 | vx=1 difficulty=0.9 | gpu1"

# v1.0-d1.0
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 1 --episodes 100 --envs_per_terrain 10 --eval_duration 6 --command_vx 1 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.0-d1.0 --note "difficulty sweep 20260910 | vx=1 difficulty=1 | gpu1"

# v1.5-d0.1
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.1 --episodes 100 --envs_per_terrain 10 --eval_duration 4 --command_vx 1.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.5-d0.1 --note "difficulty sweep 20260910 | vx=1.5 difficulty=0.1 | gpu0"

# v1.5-d0.2
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.2 --episodes 100 --envs_per_terrain 10 --eval_duration 4 --command_vx 1.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.5-d0.2 --note "difficulty sweep 20260910 | vx=1.5 difficulty=0.2 | gpu0"

# v1.5-d0.3
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.3 --episodes 100 --envs_per_terrain 10 --eval_duration 4 --command_vx 1.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.5-d0.3 --note "difficulty sweep 20260910 | vx=1.5 difficulty=0.3 | gpu0"

# v1.5-d0.4
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.4 --episodes 100 --envs_per_terrain 10 --eval_duration 4 --command_vx 1.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.5-d0.4 --note "difficulty sweep 20260910 | vx=1.5 difficulty=0.4 | gpu0"

# v1.5-d0.5
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.5 --episodes 100 --envs_per_terrain 10 --eval_duration 4 --command_vx 1.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.5-d0.5 --note "difficulty sweep 20260910 | vx=1.5 difficulty=0.5 | gpu0"

# v1.5-d0.6
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.6 --episodes 100 --envs_per_terrain 10 --eval_duration 4 --command_vx 1.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.5-d0.6 --note "difficulty sweep 20260910 | vx=1.5 difficulty=0.6 | gpu1"

# v1.5-d0.7
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.7 --episodes 100 --envs_per_terrain 10 --eval_duration 4 --command_vx 1.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.5-d0.7 --note "difficulty sweep 20260910 | vx=1.5 difficulty=0.7 | gpu1"

# v1.5-d0.8
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.8 --episodes 100 --envs_per_terrain 10 --eval_duration 4 --command_vx 1.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.5-d0.8 --note "difficulty sweep 20260910 | vx=1.5 difficulty=0.8 | gpu1"

# v1.5-d0.9
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 0.9 --episodes 100 --envs_per_terrain 10 --eval_duration 4 --command_vx 1.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.5-d0.9 --note "difficulty sweep 20260910 | vx=1.5 difficulty=0.9 | gpu1"

# v1.5-d1.0
python sim/eval/eval_generalization.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --terrains gap,rails,pit,stepping_stones,floating_ring --difficulty 1 --episodes 100 --envs_per_terrain 10 --eval_duration 4 --command_vx 1.5 --min_progress_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 --seed 42 --headless --device cuda:0 --output_dir C:\work\foothold-lab-sweep\sim\eval\results\20260910-difficulty-sweep\runs\v1.5-d1.0 --note "difficulty sweep 20260910 | vx=1.5 difficulty=1 | gpu1"

```

요약을 다시 뽑으려면 (Isaac 도 GPU 도 필요 없습니다):

```bash
python sim/eval/sweep_aggregate.py sim/eval/results/20260910-difficulty-sweep
python sim/eval/report.py floating_ring_sweep.csv
```
