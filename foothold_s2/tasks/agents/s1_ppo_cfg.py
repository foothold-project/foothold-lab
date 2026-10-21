"""S1-a PPO cfg (18 §1 · 13). 24 스텝 · 5 에폭 · 4 미니배치 · lr 1e-3 adaptive · 6,000 회. MLP [512, 256, 128] ELU."""

from isaaclab.utils import configclass
from isaaclab_rl.rsl_rl import RslRlOnPolicyRunnerCfg, RslRlPpoActorCriticCfg, RslRlPpoAlgorithmCfg


@configclass
class S1aPPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 24
    max_iterations = 6000
    save_interval = 100
    experiment_name = "foothold_s1a"
    # env 에 넣는 action 상한 (lead 10/21 사전 등록: 정상 걷는 구간 원소별 |action| p99.9 = 10.80(S1-a scan 5999) · 6.52(D2 1500) > 3 이므로
    # clip = ceil(max p99.9 x 1.5) = 17). 되먹임으로 action 이 수천까지 폭주해 action_rate 항이 -6426 이 된 발산을 막는다 (D2-s43 iter 1111).
    # 학습(train_s1) 과 평가(S1Adapter.wrap) 모두 이 값을 읽는다. S1-b · 진단 판이 상속한다.
    clip_actions = 17.0
    obs_groups = {"policy": ["policy"], "critic": ["critic"]}
    policy = RslRlPpoActorCriticCfg(
        init_noise_std=1.0,
        actor_obs_normalization=False,
        critic_obs_normalization=False,
        actor_hidden_dims=[512, 256, 128],
        critic_hidden_dims=[512, 256, 128],
        activation="elu",
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.01,
        num_learning_epochs=5,
        num_mini_batches=4,
        learning_rate=1.0e-3,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.01,
        max_grad_norm=1.0,
    )


@configclass
class S1bPPORunnerCfg(S1aPPORunnerCfg):
    """S1-b: S1-a blind 와 같은 PPO 값. iteration 은 S1-a 에서 이어 6000 -> 9000 (전체 목표 9,000 = 3,000 회 더)."""

    max_iterations = 9000
    experiment_name = "foothold_s1b"


@configclass
class S1aDiagPPORunnerCfg(S1aPPORunnerCfg):
    """진단 학습(D1 등): S1-a 와 같은 PPO 값 · 시드(기본 42), 실험 폴더만 따로. 1501 회로 model_1500.pt 까지 만든다."""

    max_iterations = 1501
    experiment_name = "foothold_s1a_diag"


@configclass
class S1aV11PPORunnerCfg(S1aPPORunnerCfg):
    """S1a-v1.1: S1-a 와 같은 PPO 값 · 6000 회 · 시드 42 · clip_actions 17(상속). 실험 폴더만 따로."""

    experiment_name = "foothold_s1a_v11"
