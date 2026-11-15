"""G0-B agent: B 의 PPO · 지각 설정 그대로에서 지도 입력만 끈다(map_input none, force_gt 거짓). EX-25(G0)의 agent 설정과 같다."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_23f_b_ppo_cfg import S223FBPPORunnerCfg


@configclass
class S2G0BPPORunnerCfg(S223FBPPORunnerCfg):
    experiment_name = "foothold_s2_g0b"

    def __post_init__(self):
        super().__post_init__()
        self.perception = {**self.perception, "map_input": "none", "force_gt": False}
