"""S2 Kit 짧은 확인: 물러나기가 실제로 켜졌는지 (깃발 하나를 지난 것으로 만들고 재추출 비율을 센다). isaac311 python 으로."""

import argparse

import tensordict  # noqa: F401
import torch  # noqa: F401

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

from foothold_s2.tasks.s2_env import FootholdS2Env  # noqa: E402
from foothold_s2.tasks.s2_env_cfg import FootholdS2G0EnvCfg  # noqa: E402
from foothold_s2.commands import mixed_core as mc  # noqa: E402


def main():
    cfg = FootholdS2G0EnvCfg()
    cfg.scene.num_envs = 256
    cfg.sim.device = args.device
    env = FootholdS2Env(cfg)
    env.reset()
    term = env.command_manager.get_term("base_velocity")
    fl = term.is_flag_env.nonzero(as_tuple=False).flatten()
    term.flag_state.passed[term._flag_row[fl]] = 1
    n_on = 0
    trials = 40

    for _ in range(trials):
        term.flag_state.backoff_left[:] = 0.0
        mc.flag_resample(term.flag_state, term._flag_row[fl], term.gen, term.params)
        n_on += int((term.flag_state.backoff_left[term._flag_row[fl]] > 0).sum())

    frac = n_on / (trials * len(fl))
    v = term.flag_state.backoff_v[term._flag_row[fl]]
    on = term.flag_state.backoff_left[term._flag_row[fl]] > 0
    print(f"[PROBE] backoff prob in cfg {term.params.backoff_prob} measured {frac:.3f} over {trials * len(fl)} draws; "
          f"v range {float(v[on].min()):.3f}..{float(v[on].max()):.3f}; flag envs {len(fl)}/{env.num_envs}")
    ok = abs(frac - 0.15) < 0.03 and 0.1 - 1e-6 <= float(v[on].min()) and float(v[on].max()) <= 0.3 + 1e-6
    print(f"[PROBE] RESULT {'PASS' if ok else 'FAIL'}")
    env.close()


if __name__ == "__main__":
    main()
    app.close()
