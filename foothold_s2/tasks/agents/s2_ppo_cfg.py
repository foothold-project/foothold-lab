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
    clip_actions = 17.0          # 공통 수정 (S1 과 같은 값 · 정상 걷는 구간 |action| p99.9 × 1.5 올림, 되먹임 발산 방지)
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


@configclass
class S2DiagPPORunnerCfg(S2PPORunnerCfg):
    """S2-G0 진단 판(lead 10/21): S2-G0 설계 그대로, clip 17(상속), 1501 회(model_1500 까지), 실험 폴더만 따로."""

    max_iterations = 1501
    save_interval = 100
    experiment_name = "foothold_s2_diag"


@configclass
class S2X11PPORunnerCfg(S2PPORunnerCfg):
    """EX-11 · EX-12 (SONNET-X11): 3072 env 는 env cfg 쪽, rollout 24, seed 42(실행 인자), 1501 회(model_1500 까지, 완료 update 수는 manifest), 500 회마다 저장.
    두 판은 est_mode 한 칸만 다르다: EX-11 `agent.perception.est_mode=zero`, EX-12 기본 learned. critic 은 잡음 없는 52 + 지도 512 + 발 지도 100 = 664."""

    max_iterations = 1501
    save_interval = 500
    experiment_name = "foothold_s2_x11"
    perception: dict = {"microbatch_envs": 256, "replay_autocast": "none", "kl_fp32": False,
                        "est_mode": "learned", "critic_mode": "clean52", "log_action_stats": True, "log_kl": True, "log_reward_split": True,
                        "contract": "start", "stop_on_nonfinite": True}


@configclass
class S2X13PPORunnerCfg(S2X11PPORunnerCfg):
    """EX-13 · EX-14 (SONNET-X13): 기준은 EX-11 = est 0(est_mode zero), clean critic 664, clip 17, rollout 24, 1501 회, 500 회마다 저장. 보상만 env cfg 가 다르다."""

    experiment_name = "foothold_s2_x13"
    perception: dict = {"microbatch_envs": 256, "replay_autocast": "none", "kl_fp32": False,
                        "est_mode": "zero", "critic_mode": "clean52", "log_action_stats": True, "log_kl": True, "log_reward_split": True,
                        "contract": "start", "stop_on_nonfinite": True}
