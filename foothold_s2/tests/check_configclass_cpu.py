"""Check the installed Isaac Lab configclass and RSL config implementations.

Run in an isolated CPU process. Only rendering package initializers are bypassed;
the decorators, dataclass transformation and base configuration code are real.
"""
import importlib
import os
from pathlib import Path
import sys
import types


def main():
    root = Path(os.environ.get("ISAACLAB_PATH", "C:/isaac/IsaacLab"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    utils = types.ModuleType("isaaclab.utils")
    utils.__path__ = [str(root / "source/isaaclab/isaaclab/utils")]
    sys.modules["isaaclab.utils"] = utils
    utils.configclass = importlib.import_module("isaaclab.utils.configclass").configclass
    rsl = types.ModuleType("isaaclab_rl.rsl_rl")
    rsl.__path__ = [str(root / "source/isaaclab_rl/isaaclab_rl/rsl_rl")]
    sys.modules["isaaclab_rl.rsl_rl"] = rsl
    cfg = importlib.import_module("isaaclab_rl.rsl_rl.rl_cfg")
    for name in ("RslRlOnPolicyRunnerCfg", "RslRlPpoActorCriticCfg", "RslRlPpoAlgorithmCfg"):
        setattr(rsl, name, getattr(cfg, name))
    from foothold_s2.tasks.agents.s2_x23_ppo_cfg import S2X23PPORunnerCfg
    from foothold_s2.tasks.agents.s2_23f_b_ppo_cfg import S223FBPPORunnerCfg
    from foothold_s2.tasks.agents.s2_23f_topdown_ppo_cfg import S223FTopDownPPORunnerCfg
    parent, b, td = S2X23PPORunnerCfg(), S223FBPPORunnerCfg(), S223FTopDownPPORunnerCfg()
    assert not hasattr(S2X23PPORunnerCfg, "perception")
    assert parent.perception["microbatch_envs"] == 256
    assert b.perception == {**parent.perception, "microbatch_envs": 64}
    assert td.perception == {**parent.perception, "microbatch_envs": 64,
                             "force_gt": False, "depth_delay_ticks": 0}
    b.perception["force_gt"] = False
    assert S223FBPPORunnerCfg().perception["force_gt"] is True
    assert td.max_iterations == 20000
    print("REAL_CONFIGCLASS_AND_RSL_CFG_CHECKS_PASS")


if __name__ == "__main__":
    main()
