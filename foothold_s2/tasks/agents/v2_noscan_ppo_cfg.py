"""EX-24 agent cfg (SONNET-X23): v2 와 같은 표준 rsl_rl OnPolicyRunner · ActorCritic · PPO 설정(설치본 UnitreeGo2GapPPORunnerCfg: lr 1e-4 · 512/256/128 · 24 스텝 등)에서
실험 이름 · 1501 회 · 50 회마다 저장만 바꾼다. resume 은 쓰지 않는다: v2 는 NVIDIA 사전학습 체크포인트에서 이어 학습했지만(agent.yaml resume true · load_run nvidia_pretrained_source),
사전학습 actor 의 입력이 스캔 포함 235 칸이라 스캔을 뺀 입력(48 칸)에는 읽을 수 없다. 그래서 처음부터 학습한다."""

from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.gap_training.gap_ppo_cfg import UnitreeGo2GapPPORunnerCfg


@configclass
class FootholdV2bNoScanPPORunnerCfg(UnitreeGo2GapPPORunnerCfg):
    def __post_init__(self):
        super().__post_init__()
        self.experiment_name = "foothold_v2_noscan"
        self.max_iterations = 1501
        self.save_interval = 50
