"""HiPAN 모드 2 주행 환경 cfg (N1 · 설계 §3). 하위 (EX-42 과제 `FootholdS2-Go2-S2-SB-v0`) 의 cfg 를 평가 꼴로 고쳐 방 메시를 단다.

새 gym 과제를 등록하지 않는다 (EX-42 학습 경로 파일은 안 건드림): 하위 과제를 그대로 만들고 `nav_env.NavEnv` 가 그 위에 얹힌다.
`configure_lower_env_cfg` 는 D44 평가기 (`eval/ex42_d44_eval.py::_configure`) 와 같은 값을 쓰되 마찰 정책 (평가 전용) 은 뺀다.
Kit 가 필요한 부분 (`mesh_file_generator_cfg` · `start_obs` · gym.make · LowerPolicy.load) 은 함수 인자로 받거나 `build_nav_env` 안에서만 부른다
-> `configure_lower_env_cfg` 는 가짜 cfg 로 시험하고, `build_nav_env` 는 Kit 에서만 돈다 (Kit 확인 전에는 「미확인」).
"""
from __future__ import annotations

LOWER_TASK = "FootholdS2-Go2-S2-SB-v0"
NO_RESAMPLE = (1.0e9, 1.0e9)


def foot_below_room_floor(env, sensor_cfg, asset_cfg, margin: float = 0.25):
    """주행 환경의 「발이 바닥 아래」 종료: 발이 env 의 바닥 높이 (env 원점 z) 보다 `margin` 아래면 끝.
    하위 학습 env 의 옛 판정 (`mdp_extra.foot_below_ground`) 은 발에서 가장 가까운 높이 스캔 점 (위에서 쏜 광선의 첫 면) 을 지면으로 본다.
    방에서는 그 첫 면이 벽 윗면 (1.2 m) 이나 탁자 윗면이라서, 벽 옆이나 탁자 밑을 걷는 발이 「1.2 m - 0.25 m 보다 낮음」 으로 오판된다 (G3 L40S 종료 까닭의 대부분)."""
    del sensor_cfg
    feet_z = env.scene[asset_cfg.name].data.body_pos_w[:, asset_cfg.body_ids, 2]
    return (feet_z < env.scene.env_origins[:, 2][:, None] - margin).any(dim=1)


DEFAULT_EPISODE_S = 90.0


def nav_force_reset(env):
    """종료 항: 상위가 요청한 env (과제 성공 종료) 를 이 스텝에 되돌린다. 읽고 바로 비운다."""
    import torch

    f = getattr(env, "_nav_force", None)
    if f is None:
        return torch.zeros(env.num_envs, dtype=torch.bool, device=env.device)
    out = f.clone()
    f.zero_()
    return out


def nav_episode_timeout(env):
    """종료 항 (time_out): env 별 최대 스텝 (`env._nav_max_steps`, 상위가 경로 길이로 정함) 에 닿으면. 없으면 고정 90 초."""
    import torch

    lim = getattr(env, "_nav_max_steps", None)
    if lim is None:
        return env.episode_length_buf >= int(DEFAULT_EPISODE_S / float(env.step_dt))
    return env.episode_length_buf >= lim


def configure_lower_env_cfg(env_cfg, agent_cfg, *, num_envs: int, device: str, seed: int, terrain_generator,
                            disable_dr=None, start_obs_module=None, done_term_cls=None) -> dict:
    """하위 env cfg 를 주행용으로 고친다. 돌려주는 값: 고친 내용 요약 (영수증용)."""
    if num_envs < 1:
        raise ValueError("num_envs must be >= 1")
    env_cfg.scene.num_envs = int(num_envs)
    env_cfg.seed = agent_cfg.seed = int(seed)
    env_cfg.sim.device = agent_cfg.device = device
    terrain = env_cfg.scene.terrain
    terrain.terrain_type = "generator"
    terrain.terrain_generator = terrain_generator
    env_cfg.observations.policy.enable_corruption = False
    if start_obs_module is None:
        from foothold_s2.sensors import start_obs as start_obs_module
    start_obs_module.AUG.enabled = False
    if disable_dr is None:
        from foothold_s2.eval.adapters import disable_eval_randomization as disable_dr
    disabled = list(disable_dr(env_cfg))
    for name in ("terrain_levels", "command_range"):
        if hasattr(env_cfg.curriculum, name):
            setattr(env_cfg.curriculum, name, None)
    command = env_cfg.commands.base_velocity
    command.resampling_time_range = NO_RESAMPLE
    command.dynamic_flags = False
    command.flag_stride = 0
    reset_base = getattr(getattr(env_cfg, "events", None), "reset_base", None)
    if reset_base is not None and isinstance(getattr(reset_base, "params", None), dict):      # 리셋 때 몸이 env 원점 (= 과제 시작 자리) 그대로 서게: x y 흔들기 끔 (yaw 는 그대로)
        pr = dict(reset_base.params.get("pose_range", {}))
        pr["x"], pr["y"] = (0.0, 0.0), (0.0, 0.0)
        reset_base.params = {**reset_base.params, "pose_range": pr}
    terms = getattr(env_cfg, "terminations", None)
    custom = "absent"
    if terms is not None and hasattr(terms, "time_out"):         # 성공 종료 (상위 요청) · env 별 시간 초과 (경로 길이 / 0.3 + 10 초) 로 기본 시간 초과를 바꾼다
        if done_term_cls is None:
            from isaaclab.managers import TerminationTermCfg as done_term_cls
        env_cfg.episode_length_s = 600.0                         # 기본 시간 초과 (20 초) 는 끈다. 길이는 nav_episode_timeout 이 정한다
        terms.time_out = None
        terms.nav_timeout = done_term_cls(func=nav_episode_timeout, time_out=True)
        terms.nav_success = done_term_cls(func=nav_force_reset)
        custom = "nav_timeout+nav_success"
    fbg = getattr(getattr(env_cfg, "terminations", None), "foot_below_ground", None)
    if fbg is not None:                      # 방 메시: 벽 · 탁자 윗면을 지면으로 읽는 스캔 판정을 env 바닥 높이 판정으로 바꾼다
        fbg.func = foot_below_room_floor
        fbg.params = {k: v for k, v in fbg.params.items() if k != "scanner_cfg"}
    return {"num_envs": int(num_envs), "seed": int(seed), "device": device, "dr_disabled": disabled,
            "command_resampling": "off", "flags": "off", "curriculum": "off", "observation_corruption": "off",
            "foot_below_ground": "room_floor" if fbg is not None else "absent", "episode_terms": custom,
            "reset_jitter_xy": "off" if reset_base is not None else "absent"}


def build_nav_env(*, checkpoint, expected_sha256: str, room_mesh_npz, room_mesh_sha256: str, num_envs: int, device: str,
                  seed: int, map_mode: str = "eval_gt", command_mode: str = "clip", prep_path=None, extra_scene=None, pose_receipt=None):
    """Kit python 에서만. 하위 env 를 만들고 하위 정책을 올려 `NavEnv` 를 돌려준다 (Kit 에서 돌려 본 적 없음: 미확인).
    순서는 D44 평가기와 같다: cfg -> 저장본 sha · 입력 폭 검사 (gym.make 전) -> gym.make -> 러너 -> 명령 항 heading 끄기."""
    import gymnasium as gym
    import isaaclab_tasks  # noqa: F401
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
    from isaaclab_tasks.utils import load_cfg_from_registry

    import foothold_s2.sb_tasks  # noqa: F401
    from foothold_s2.nav import command_space, lower_adapter
    from foothold_s2.nav.nav_env import NavEnv
    from foothold_s2.terrains.ex42_mesh_mount import mesh_file_generator_cfg

    env_cfg = load_cfg_from_registry(LOWER_TASK, "env_cfg_entry_point")
    agent_cfg = load_cfg_from_registry(LOWER_TASK, "rsl_rl_cfg_entry_point")
    summary = configure_lower_env_cfg(env_cfg, agent_cfg, num_envs=num_envs, device=device, seed=seed,
                                      terrain_generator=mesh_file_generator_cfg(room_mesh_npz, room_mesh_sha256))
    if extra_scene is not None:         # 예: student 의 depth 카메라를 scene 에 더한다 (gym.make 전에만 가능)
        extra_scene(env_cfg)
    state, prep = lower_adapter.prepare(env_cfg, checkpoint, expected_sha256)
    from foothold_s2.nav import pose_actions
    if pose_actions.enabled():          # 상위 5 차원: 하위 관측 pose_cmd 를 상위가 낸 [dh, roll] 로 (자세 영수증이 맞아야 NavEnv 가 받음)
        if not lower_adapter.pose_active_from_receipt(pose_receipt, prep["checkpoint_sha256"]):
            raise ValueError("HIPAN_POSE_ACTIONS=1 needs a posture receipt for this lower checkpoint (factory lower_pose_receipt)")
        env_cfg.observations.pose_cmd.pose_cmd.func = pose_actions.pose_obs
        env_cfg.observations.pose_cmd.pose_cmd.params = {}
        print(f"HIPAN_POSE_ACTIONS on H0={pose_actions.H0} receipt stage={pose_receipt.get('stage_id')} lower={prep['checkpoint_sha256'][:12]}", flush=True)
    env = RslRlVecEnvWrapper(gym.make(LOWER_TASK, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
    lower = lower_adapter.LowerPolicy.load(checkpoint, env, device, map_mode, agent_cfg=agent_cfg.to_dict(),
                                           checkpoint_state=state, checkpoint_sha256=prep["checkpoint_sha256"], pose_receipt=pose_receipt)
    if prep_path is None:
        from pathlib import Path
        prep_path = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"
    space = command_space.CommandSpace(command_space.slots_from_stage_row(prep_path, "E1F"), command_mode,
                                       pose_active=lower.pose_active)
    return NavEnv(env, lower, space), dict(summary, lower=lower.capabilities, preparation=prep)
