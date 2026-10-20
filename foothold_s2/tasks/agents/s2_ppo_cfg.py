"""S2 PPO cfg (18 §1 · 53). rl 의 StartRunner 가 dict 로 받는다. 정책 클래스는 StartActorCritic, 지각 설정은 `perception`."""

from isaaclab.utils import configclass
from isaaclab_rl.rsl_rl import RslRlOnPolicyRunnerCfg, RslRlPpoActorCriticCfg, RslRlPpoAlgorithmCfg


@configclass
class S2PPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 24
    max_iterations = 20000
    save_interval = 1000
    experiment_name = "foothold_s2"
    obs_groups = {}
    policy = RslRlPpoActorCriticCfg(
        class_name="StartActorCritic", init_noise_std=1.0,
        actor_obs_normalization=False, critic_obs_normalization=False,
        actor_hidden_dims=[512, 256, 128], critic_hidden_dims=[512, 256, 128], activation="elu")
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0, use_clipped_value_loss=True, clip_param=0.2, entropy_coef=0.01,
        num_learning_epochs=5, num_mini_batches=4, learning_rate=1.0e-3, schedule="adaptive",
        gamma=0.99, lam=0.95, desired_kl=0.01, max_grad_norm=1.0)
    # rl runner 의 지각 설정 기본값 (start_runner.PERCEPTION_DEFAULTS 와 같은 값). hydra 로 `agent.perception.<키>=값` 을 덮어쓸 수 있게 키를 둔다.
    perception: dict = {"microbatch_envs": 256, "replay_autocast": "none", "kl_fp32": False}
