"""RSL-RL configuration for fine-tuning NVIDIA's pretrained Go2 policy."""

from isaaclab.utils import configclass

from ..agents.rsl_rl_ppo_cfg import UnitreeGo2RoughPPORunnerCfg


@configclass
class UnitreeGo2GapPPORunnerCfg(UnitreeGo2RoughPPORunnerCfg):
    """Keep the pretrained network architecture and use a gentler learning rate."""

    def __post_init__(self):
        super().__post_init__()

        self.experiment_name = "unitree_go2_gap_nvidia"
        self.max_iterations = 100
        self.save_interval = 25
        self.algorithm.learning_rate = 1.0e-4
