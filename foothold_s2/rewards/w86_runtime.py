"""W86 EX41 n0 registration and per-env diagnostics/quarantine contract.

No Isaac import at module load. These functions never mutate a running EX40.
"""


def prepare_env_cfg(env_cfg, plan) -> dict:
    """Call ONCE before gym.make, after existing EX40 reward setup.

    Registers new zero_yaw/swing + preregistered-zero terms and invalid-env
    termination. Keeps existing collision/action_smoothness/joint_power,
    changes existing stumble only once. Returns JSON registration receipt.
    zero-yaw positive abs cost gets -0.5, swing squared cost -10, existing
    stumble -2. All times dt are applied by RewardManager exactly once.
    Separate recorder evaluates zero-weight terms skipped by RewardManager.
    """
    raise NotImplementedError('EX41 interface only')


def attach_runtime(env, plan, log_dir):
    """Call after gym.make but before VecEnvWrapper reset/first rollout.

    Returns adapter with flush(iteration)->dict, state_dict/load_state_dict.
    Installs per-env finite checks, support-ray cache and foot-cycle recorder.
    Termination check precedes rewards as in installed ManagerBasedRLEnv.
    Missing ray is logged invalid terrain, not an assumed zero-height surface.
    """
    raise NotImplementedError('EX41 interface only')


def quarantine_actions(runner, actions):
    """Call immediately after PPO act, before env.step.

    Nonfinite action/transition input rows are recorded for env-only reset.
    Returns finite actions (bad rows zero), marks bad rows in adapter.
    Does not terminate unrelated envs or replace optimizer/model NaNs.
    """
    raise NotImplementedError('EX41 interface only')


def quarantine_step(runner, observations, rewards, dones, extras):
    """Call immediately after env.step, BEFORE trace/finite/replay/PPO handling.

    Returns (observations,rewards,dones,extras), same container interfaces.
    Invalid physical/action rows are terminated/reset only in that env;
    reward becomes finite zero, dones true, time_outs false. Pending transition
    observation/value/action/log_prob/mean/std rows are sanitized (std=1),
    existing valid rows untouched. Records reason and row IDs in NEW run.
    Normal done processing then resets pstate/replay/episode counters.
    Persistent invalid post-reset row is explicitly reported, never hidden as
    valid experience. Policy/optimizer-wide nonfinite remains an error.
    """
    raise NotImplementedError('EX41 interface only')
