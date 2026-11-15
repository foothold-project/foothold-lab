"""EX-21 agent cfg (SONNET-X21): EX-18 agent 와 같은 perception(est_mode oracle_vel · 잡음 0.1 · clean52 · clip 17 · START 명령 계약 검사), 301 회 · 50 회마다 저장, 실험 폴더 foothold_s2_x21."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_x18_ppo_cfg import S2X18PPORunnerCfg


@configclass
class S2X21PPORunnerCfg(S2X18PPORunnerCfg):
    experiment_name = "foothold_s2_x21"
