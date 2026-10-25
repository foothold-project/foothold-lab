"""EX-33 S-B agent: B 의 PPO · 지각 설정 그대로에서 p_map_off 한 칸만 더한다(기본 0.5, 팀장 확인 뒤 확정). force_gt 는 B 와 같이 참."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_23f_b_ppo_cfg import S223FBPPORunnerCfg

P_MAP_OFF_DEFAULT = 0.5


@configclass
class S2SBPPORunnerCfg(S223FBPPORunnerCfg):
    experiment_name = "foothold_s2_sb"

    def __post_init__(self):
        super().__post_init__()
        self.perception = {**self.perception, "p_map_off": P_MAP_OFF_DEFAULT}
