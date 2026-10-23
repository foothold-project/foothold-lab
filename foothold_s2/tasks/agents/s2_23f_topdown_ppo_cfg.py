"""SOL-23f TopDown 지각과 PPO. EX23 PPO 수학을 쓰되 AdaSmpl을 활성화한다."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_x23_ppo_cfg import S2X23PPORunnerCfg


@configclass
class S223FTopDownPPORunnerCfg(S2X23PPORunnerCfg):
    max_iterations = 20000  # 53 §6 우리 본선 계약. START 저자 회차라는 뜻이 아니다.
    experiment_name = "foothold_s2_23f_topdown"
    def __post_init__(self):
        super().__post_init__()
        # configclass turns mutable defaults into instance fields.
        self.perception = {**self.perception, "force_gt": False,
                           "depth_delay_ticks": 0, "microbatch_envs": 64}
