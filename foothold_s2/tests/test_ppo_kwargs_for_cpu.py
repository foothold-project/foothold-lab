"""Isaac Lab 3.0 의 RslRlPpoAlgorithmCfg 가 rsl_rl 3.1.2 PPO 가 모르는 칸 (optimizer 등) 을 넘겨도 PPO 를 만들 수 있다."""
from foothold_s2.runners.start_runner import ppo_kwargs_for


class Old:
    def __init__(self, policy, learning_rate=1e-3, desired_kl=0.01, device="cpu", multi_gpu_cfg=None): ...


class Open:
    def __init__(self, policy, **kwargs): ...


def test_unknown_keys_dropped_with_one_log_line():
    lines = []
    cfg = {"learning_rate": 1e-3, "desired_kl": 0.01, "optimizer": "adam", "share_cnn_encoders": False, "use_mixed_precision": False}
    out = ppo_kwargs_for(Old, cfg, log=lines.append)
    assert out == {"learning_rate": 1e-3, "desired_kl": 0.01}
    assert len(lines) == 1 and "PPO_CFG_DROPPED" in lines[0] and "WARNING" not in lines[0]


def test_non_default_dropped_value_warns():
    lines = []
    ppo_kwargs_for(Old, {"learning_rate": 1e-3, "optimizer": "adamw"}, log=lines.append)
    assert len(lines) == 1 and "WARNING" in lines[0] and "adamw" in lines[0]


def test_2x_cfg_unchanged_and_silent():
    lines = []
    cfg = {"learning_rate": 1e-3, "desired_kl": 0.01}
    assert ppo_kwargs_for(Old, cfg, log=lines.append) == cfg and lines == []
    assert ppo_kwargs_for(Open, {"x": 1, "optimizer": "adam"}, log=lines.append) == {"x": 1, "optimizer": "adam"} and lines == []


def test_real_rsl_rl_ppo_accepts_result():
    import inspect
    from rsl_rl.algorithms import PPO
    out = ppo_kwargs_for(PPO, {"learning_rate": 1e-3, "optimizer": "adam", "use_mixed_precision": False}, log=lambda *_: None)
    assert set(out) == {"learning_rate"} and set(out) <= set(inspect.signature(PPO.__init__).parameters)
