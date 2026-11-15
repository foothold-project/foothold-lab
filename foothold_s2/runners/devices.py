"""학습 장치 맞춤 (SONNET-X11d). Kit 없이 시험된다.

Isaac Lab 표준 rsl_rl train.py 처럼 비분산일 때도 `--device` 가 시뮬(env_cfg.sim.device)과 신경망 · PPO · 지각(agent_cfg.device)에 같이 간다.
예전 train_start.py 는 시뮬만 바꿔서 `--device cuda:1` 이어도 runner 는 기본 cuda:0 에 남았다(시뮬 GPU 1 · 신경망 GPU 0, 매 step GPU 간 복사).
"""


def resolve_devices(cli_device, env_cfg, agent_cfg, distributed=False, local_rank=0):
    """env_cfg.sim.device · agent_cfg.device 를 정한다. 분산이면 rank 의 GPU, 아니면 --device(없으면 기존 값)."""
    if distributed:
        env_cfg.sim.device = f"cuda:{local_rank}"
        agent_cfg.device = f"cuda:{local_rank}"
    elif cli_device is not None:
        env_cfg.sim.device = cli_device
        agent_cfg.device = cli_device

    return env_cfg.sim.device, agent_cfg.device
