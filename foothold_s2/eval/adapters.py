"""정책 계열별로 env 를 짓고 정책을 올리는 곳. Kit 가 떠 있어야 부를 수 있다.

  `E1Adapter`        robot_lab 의 `RobotLab-Go2-v0` (MoE-CTS student). 눈 없이 명령을 연 E1.
  `IsaacLabAdapter`  Isaac Lab 의 NVIDIA Go2 rough 태스크. NVIDIA 기본 · v2 체크포인트용.

**IsaacLabAdapter 는 아직 Kit 에서 안 돌려 봤다 (미확인).** E1Adapter 만 실측했다.

둘 다 «평가용 설정» 을 한 함수(`apply_eval_settings`)로 덮는다. 덮은 뒤에는 되읽어 확인한다
(조용히 안 덮이는 일을 막는다).
"""

import copy
import json
import math

import torch

E1_TASK = "RobotLab-Go2-v0"
NVIDIA_TASK = "Isaac-Velocity-Rough-Unitree-Go2-v0"

# E1 학습 설정의 사건 중 평가에서 끄는 것 (v2 하네스가 push · mass · com 을 끄는 것과 같은 종류).
E1_EVENTS_OFF = ("randomize_push_robot", "randomize_rigid_body_mass_base",
                 "randomize_rigid_body_mass_others", "randomize_com_positions")


def apply_reset_ranges(env_cfg, spawn_xy_range, yaw_range_deg, joint_pos_scale, changes):
    """출발 흔들기. 있는 사건에만 덮고, 덮은 것을 `changes` 에 적는다."""
    yaw = math.radians(yaw_range_deg)
    events = env_cfg.events

    if getattr(events, "reset_base", None) is not None:
        events.reset_base.params["pose_range"] = {
            "x": (-spawn_xy_range, spawn_xy_range),
            "y": (-spawn_xy_range, spawn_xy_range),
            "yaw": (-yaw, yaw),
        }
        events.reset_base.params["velocity_range"] = {k: (0.0, 0.0) for k in
                                                      ("x", "y", "z", "roll", "pitch", "yaw")}
        changes.append("reset_base pose +-%.2f m / +-%.1f deg, velocity 0" % (spawn_xy_range, yaw_range_deg))
    else:
        changes.append("reset_base: 없음 (덮지 않음)")

    if getattr(events, "reset_robot_joints", None) is not None:
        events.reset_robot_joints.params["position_range"] = (1.0 - joint_pos_scale, 1.0 + joint_pos_scale)
        events.reset_robot_joints.params["velocity_range"] = (0.0, 0.0)
        changes.append("reset_robot_joints position x[%.2f, %.2f], velocity 0"
                       % (1.0 - joint_pos_scale, 1.0 + joint_pos_scale))
    else:
        changes.append("reset_robot_joints: 없음 (덮지 않음)")


def apply_terrain_settings(env_cfg, generator, seed, difficulty, changes):
    """지형 생성기 설정. 난이도를 (d, d) 로 못 박아 타일 전부가 같은 난이도가 되게 한다."""
    generator.seed = seed
    generator.curriculum = True

    if difficulty is not None:
        generator.difficulty_range = (difficulty, difficulty)

    env_cfg.scene.terrain.terrain_generator = generator
    env_cfg.scene.terrain.max_init_terrain_level = 0

    if hasattr(env_cfg.curriculum, "terrain_levels"):
        env_cfg.curriculum.terrain_levels = None

    changes.append("terrain: seed %d, curriculum=True, difficulty %s, max_init_terrain_level 0"
                   % (seed, "(%.2f, %.2f)" % (difficulty, difficulty) if difficulty is not None
                      else "생성기 값 %r (난이도 행 그대로)" % (generator.difficulty_range,)))


class E1Adapter:
    name = "e1"

    def __init__(self):
        self.changes = []
        self.checks = {}

    def make_env(self, *, generator, num_envs, duration_s, seed, difficulty, base_cmd,
                 spawn_xy_range=0.10, yaw_range_deg=5.0, joint_pos_scale=0.05, device="cuda:0",
                 plane=False, env_spacing=None, events_off=E1_EVENTS_OFF):
        import importlib

        import gymnasium as gym
        from robot_lab.tasks.go2.env_cfg import Go2EnvCfg
        from robot_lab.tasks.go2.rsl_rl_cfg import MoECTSRunnerCfg

        importlib.import_module("robot_lab.tasks")  # RobotLab-Go2-v0 을 등록한다

        env_cfg = Go2EnvCfg()
        agent_cfg = MoECTSRunnerCfg()
        env_cfg.seed = seed
        agent_cfg.seed = seed
        env_cfg.scene.num_envs = num_envs
        env_cfg.episode_length_s = duration_s
        self.changes.append("env cfg: robot_lab Go2EnvCfg, task %s" % E1_TASK)

        if plane:
            env_cfg.scene.terrain.terrain_type = "plane"
            env_cfg.scene.terrain.terrain_generator = None
            env_cfg.scene.terrain.max_init_terrain_level = None
            env_cfg.scene.env_spacing = env_spacing or 8.0
            self.changes.append("terrain plane, env_spacing %.1f" % (env_spacing or 8.0))
        else:
            # robot_lab 명령 항은 지형 이름마다 명령 범위가 있어야 한다. 아래에서 명령을 고정하므로
            # 학습용 재표집에만 쓰이는 칸이다. 없는 이름은 obstacles 칸을 복사해 채운다.
            apply_terrain_settings(env_cfg, generator, seed, difficulty, self.changes)
            rng = env_cfg.commands.base_velocity.terrain_max_command_ranges
            added = []

            for name in generator.sub_terrains:
                if name not in rng:
                    rng[name] = dict(rng["obstacles"])
                    added.append(name)

            self.changes.append("terrain_max_command_ranges 에 채운 이름(고정 명령이라 안 쓰임): %s" % added)
            apply_reset_ranges(env_cfg, spawn_xy_range, yaw_range_deg, joint_pos_scale, self.changes)

        for name in events_off:
            setattr(env_cfg.events, name, None)

        self.changes.append("events off: %s" % ", ".join(events_off))
        self.changes.append("학습 그대로 둠: " + ", ".join(
            n for n in ("randomize_push_robot", "randomize_rigid_body_mass_base",
                        "randomize_rigid_body_mass_others", "randomize_com_positions",
                        "randomize_rigid_body_material", "randomize_actuator_gains",
                        "randomize_motor_zero_offset") if n not in events_off))

        env_cfg.curriculum.terrain_levels = None
        env_cfg.curriculum.base_linear_velocity = None
        env_cfg.curriculum.base_height_l2 = None
        env_cfg.observations.policy.enable_corruption = False
        env_cfg.observations.single_obs.enable_corruption = False
        self.changes.append("curriculum 전부 끔 · 관측 잡음 끔 (policy, single_obs)")

        cmd = env_cfg.commands.base_velocity
        if hasattr(cmd, "resampling_time"):
            cmd.resampling_time = 1.0e9

        cmd.ranges.lin_vel_x = (0.0, 0.0)
        cmd.ranges.lin_vel_y = (0.0, 0.0)
        cmd.ranges.ang_vel_yaw = (0.0, 0.0)
        cmd.limit_vel_prob = 0.0
        cmd.limit_ang_vel_at_zero_command_prob = 0.0
        cmd.command_range_curriculum = []

        if hasattr(cmd, "resampling_time_range"):
            cmd.resampling_time_range = (1.0e9, 1.0e9)

        if plane:
            from robot_lab.tasks.go2.mdp import commands as e1_cmds

            def plane_terrain_infos(term):
                term.terrain_types = []
                term.terrain_type2idx = {}
                term.terrain_idxs = torch.full((term.num_envs,), -1, dtype=torch.long, device=term.device)
                term.terrain_length = 0.0

            e1_cmds.Go2RLGymCommand._init_terrain_infos = plane_terrain_infos
            self.changes.append("Go2RLGymCommand._init_terrain_infos 를 평지용으로 바꿈 (지형 생성기 없음)")

        env_cfg.sim.device = device
        agent_cfg.device = device

        gym_env = gym.make(E1_TASK, cfg=env_cfg)

        return {"gym_env": gym_env, "raw": gym_env.unwrapped, "env_cfg": env_cfg,
                "agent_cfg": agent_cfg}

    def wrap(self, built):
        """RslRlVecEnvWrapper 를 지어 `built["env"]` 에 둔다 (짓는 순간 env.reset() 이 한 번 돈다)."""
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper

        built["env"] = RslRlVecEnvWrapper(built["gym_env"], clip_actions=None)

        return built["env"]

    def pin_command(self, raw, pin):
        """명령 항의 재표집을 «원래 명령 쓰기» 로 바꾼다. 리셋 때 원래 명령으로 돌아온다."""
        term = raw.command_manager.get_term("base_velocity")

        def resample(env_ids):
            term.commands[env_ids, :3] = pin.base[env_ids]
            term.time_left[env_ids] = 1.0e9

        term._resample = resample
        term.commands[:, :3] = pin.want
        term.time_left[:] = 1.0e9
        self.changes.append("명령 항 _resample 교체: 리셋 때 env 별 원래 명령을 쓰고 time_left 1e9")

        return term

    def load_policy(self, built, checkpoint):
        from rsl_rl.runners import OnPolicyRunnerCTS

        env = built.get("env") or self.wrap(built)
        raw = built["raw"]
        agent_cfg = built["agent_cfg"]
        runner = OnPolicyRunnerCTS(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
        runner.load(checkpoint)
        policy = runner.get_inference_policy(device=raw.device)
        obs = env.get_observations()

        # student 가 critic 입력과 정책 이력을 쓰지 않는지 · 쓰는지 되읽는다 (옛 하네스 같은 점검).
        gen = torch.Generator(device=raw.device)
        gen.manual_seed(12345)

        with torch.inference_mode():
            base = policy(obs)
            o1 = obs.clone()
            o1["critic"] = torch.randn(o1["critic"].shape, generator=gen, device=raw.device) * 10.0
            o2 = obs.clone()
            o2["policy"] = o2["policy"] + 0.1 * torch.randn(o2["policy"].shape, generator=gen,
                                                           device=raw.device)
            self.checks = {
                "teacher_input_randomized_max_abs_action_change": float((policy(o1) - base).abs().max()),
                "policy_input_perturbed_max_abs_action_change": float((policy(o2) - base).abs().max()),
                "obs_shapes": {k: list(v.shape) for k, v in obs.items()},
                "policy_class": type(runner.alg.policy).__name__,
            }

        print("[E1] checks", json.dumps(self.checks), flush=True)

        return env, policy, runner.alg.policy, obs


class IsaacLabAdapter:
    """NVIDIA 기본 · v2 체크포인트용. 옛 v2 하네스의 길을 따른다.

    지형이 있는 축(1 · 3)은 환경 설정 클래스(`env_cfg_class`)로 짓고 `ManagerBasedRLEnv` 를 직접 만든다.
    평지 축(2)은 레지스트리 기본 설정을 평면으로 바꿔 `gym.make` 한다 (옛 `eval_command_response.py`).
    """

    rebuilds_obs = True  # 평지 축 2 에서 명령을 쓴 뒤 관측을 다시 짓는다 (옛 v2 프로브와 같은 순서)

    def __init__(self, name="isaaclab", env_cfg_class=None, apply_gap_aware=None, std_form=None):
        self.name = name
        self.env_cfg_class = env_cfg_class
        self.apply_gap_aware = apply_gap_aware
        self.std_form = std_form
        self.changes = []
        self.checks = {}

    def make_env(self, *, generator, num_envs, duration_s, seed, difficulty, base_cmd,
                 spawn_xy_range=0.10, yaw_range_deg=5.0, joint_pos_scale=0.05, device="cuda:0",
                 plane=False, env_spacing=None, events_off=None):
        import importlib

        from isaaclab.envs import ManagerBasedRLEnv
        from isaaclab_tasks.utils import load_cfg_from_registry

        importlib.import_module("isaaclab_tasks")
        self._import_task()
        agent_cfg = load_cfg_from_registry(self.task_id, "rsl_rl_cfg_entry_point")
        agent_cfg.seed = seed

        if plane:
            env_cfg = load_cfg_from_registry(NVIDIA_TASK, "env_cfg_entry_point")
            env_cfg.scene.terrain.terrain_type = "plane"
            env_cfg.scene.terrain.terrain_generator = None
            env_cfg.scene.terrain.max_init_terrain_level = None
            env_cfg.scene.env_spacing = env_spacing or 8.0

            if hasattr(env_cfg.curriculum, "terrain_levels"):
                env_cfg.curriculum.terrain_levels = None

            self.changes.append("terrain plane, env_spacing %.1f (레지스트리 기본 설정)" % (env_spacing or 8.0))
        else:
            env_cfg = self.env_cfg_class()
            apply_terrain_settings(env_cfg, generator, seed, difficulty, self.changes)
            apply_reset_ranges(env_cfg, spawn_xy_range, yaw_range_deg, joint_pos_scale, self.changes)

        env_cfg.seed = seed
        env_cfg.scene.num_envs = num_envs
        env_cfg.episode_length_s = duration_s
        env_cfg.observations.policy.enable_corruption = False

        for name in ("push_robot", "base_external_force_torque", "add_base_mass", "base_com")                 if not plane else ("push_robot", "base_external_force_torque"):
            if hasattr(env_cfg.events, name):
                setattr(env_cfg.events, name, None)

        self.changes.append("관측 잡음 끔 · events off: push_robot, base_external_force_torque"
                            + ("" if plane else ", add_base_mass, base_com"))

        self._configure_command(env_cfg, base_cmd)

        if not plane and self.apply_gap_aware is not None:
            self.changes.append("gap-aware height scan 규격 2, 빗나간 광선 값: %r" % (self.apply_gap_aware(env_cfg),))

        env_cfg.sim.device = device
        agent_cfg.device = device

        if plane:
            import gymnasium as gym

            gym_env = gym.make(NVIDIA_TASK, cfg=env_cfg)
            raw = gym_env.unwrapped
        else:
            gym_env = raw = ManagerBasedRLEnv(cfg=env_cfg)

        return {"gym_env": gym_env, "raw": raw, "env_cfg": env_cfg, "agent_cfg": agent_cfg}

    task_id = NVIDIA_TASK

    def _import_task(self):
        pass

    def _configure_command(self, env_cfg, base_cmd):
        cmd = env_cfg.commands.base_velocity
        vx, vy, wz = (float(x) for x in base_cmd[0])
        cmd.ranges.lin_vel_x = (vx, vx)
        cmd.ranges.lin_vel_y = (vy, vy)
        cmd.ranges.ang_vel_z = (wz, wz)
        cmd.heading_command = False
        cmd.rel_heading_envs = 0.0
        cmd.rel_standing_envs = 0.0
        cmd.resampling_time_range = (1.0e9, 1.0e9)

        if getattr(cmd.ranges, "heading", None) is not None:
            cmd.ranges.heading = None

    def wrap(self, built):
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper

        built["env"] = RslRlVecEnvWrapper(built["gym_env"], clip_actions=built["agent_cfg"].clip_actions)

        return built["env"]

    def pin_command(self, raw, pin):
        term = raw.command_manager.get_term("base_velocity")
        term.vel_command_b[:, :3] = pin.want
        self.changes.append("명령 범위를 한 점으로 고정 (리셋 재표집이 같은 값을 냄), heading off")

        return term

    def load_policy(self, built, checkpoint):
        from rsl_rl.runners import OnPolicyRunner

        agent_cfg = built["agent_cfg"]
        env = built.get("env") or self.wrap(built)

        if self.std_form is not None:
            self.checks["std_form"] = self.std_form(agent_cfg, checkpoint)

        runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
        runner.load(checkpoint)
        policy = runner.get_inference_policy(device=built["raw"].device)
        obs = env.get_observations()
        self.checks["policy_class"] = type(runner.alg.policy).__name__
        self.checks["obs_shape"] = list(obs["policy"].shape) if hasattr(obs, "keys") else list(obs.shape)

        return env, policy, runner.alg.policy, obs


class S1Adapter(IsaacLabAdapter):
    """S1-a 학습 판(우리 env). 명령은 `fixed_cmd` 로 못 박고 깃발 env 를 끈다. 평가에서는 지연 · 세기 · 마찰 무작위를 끈다."""

    def __init__(self, variant="blind"):
        from foothold_s2.tasks.s1_env_cfg import FootholdS1aBlindEnvCfg, FootholdS1aScanEnvCfg

        cls = {"blind": FootholdS1aBlindEnvCfg, "scan": FootholdS1aScanEnvCfg}[variant]
        super().__init__(name="s1" + variant, env_cfg_class=cls)
        self.task_id = "FootholdS2-Go2-S1a-%s-v0" % variant

    def _import_task(self):
        import importlib

        importlib.import_module("foothold_s2.tasks")

    def _configure_command(self, env_cfg, base_cmd):
        cmd = env_cfg.commands.base_velocity
        cmd.fixed_cmd = tuple(float(x) for x in base_cmd[0])
        cmd.flag_stride = 0
        cmd.resampling_time_range = (1.0e9, 1.0e9)

        for name in ("actuator_gains", "motor_strength", "physics_material"):
            setattr(env_cfg.events, name, None)

        env_cfg.actions.joint_pos.max_delay_s = 0.0
        self.changes.append("S1 명령 고정 %r, 깃발 env 없음, 지연 · 세기 · 게인 · 마찰 무작위 끔" % (cmd.fixed_cmd,))


def deep_copy_generator(generator):
    return copy.deepcopy(generator)
