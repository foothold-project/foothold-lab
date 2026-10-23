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
import os

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
            env_cfg = self._plane_env_cfg(load_cfg_from_registry)
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

            gym_env = gym.make(self.task_id, cfg=env_cfg)
            raw = gym_env.unwrapped
        else:
            if getattr(self, "viewer_resolution", None):
                env_cfg.viewer.resolution = tuple(self.viewer_resolution)       # 영상 촬영용 (record_clip.py)

            gym_env = raw = ManagerBasedRLEnv(cfg=env_cfg, render_mode=getattr(self, "render_mode", None))

        return {"gym_env": gym_env, "raw": raw, "env_cfg": env_cfg, "agent_cfg": agent_cfg}

    task_id = NVIDIA_TASK

    def _import_task(self):
        pass

    def _plane_env_cfg(self, load_cfg_from_registry):
        """평지 축(2)의 env 설정. 기본은 레지스트리의 NVIDIA 설정."""
        return load_cfg_from_registry(NVIDIA_TASK, "env_cfg_entry_point")

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
        from foothold_s2.tasks.s1_diag_cfg import FootholdS1aDiagC1ScanEnvCfg, FootholdS1aDiagC2BlindEnvCfg
        from foothold_s2.tasks.s1_env_cfg import FootholdS1aBlindEnvCfg, FootholdS1aScanEnvCfg

        cls = {"blind": FootholdS1aBlindEnvCfg, "scan": FootholdS1aScanEnvCfg,
               "c1scan": FootholdS1aDiagC1ScanEnvCfg, "c2blind": FootholdS1aDiagC2BlindEnvCfg}[variant]      # c2blind 는 관측이 528 (몸 선속도 포함)
        super().__init__(name="s1" + variant, env_cfg_class=cls)
        self.task_id = {"c1scan": "FootholdS2-Go2-S1a-diag-C1-scan-v0", "c2blind": "FootholdS2-Go2-S1a-diag-C2-blind-v0"}.get(
            variant, "FootholdS2-Go2-S1a-%s-v0" % variant)

    def _import_task(self):
        import importlib

        importlib.import_module("foothold_s2.tasks")

    def _plane_env_cfg(self, load_cfg_from_registry):
        return self.env_cfg_class()                  # 우리 정책은 우리 관측(495 · 232)이라 NVIDIA 설정을 쓰면 안 된다

    def _configure_command(self, env_cfg, base_cmd):
        cmd = env_cfg.commands.base_velocity
        cmd.fixed_cmd = tuple(float(x) for x in base_cmd[0])
        cmd.flag_stride = 0
        cmd.resampling_time_range = (1.0e9, 1.0e9)

        for name in ("actuator_gains", "motor_strength", "physics_material", "add_base_mass", "base_com"):
            setattr(env_cfg.events, name, None)

        env_cfg.actions.joint_pos.max_delay_s = 0.0

        for name in ("terrain_levels", "command_range", "penalty_on"):        # 평가에서는 커리큘럼을 돌리지 않는다
            if hasattr(env_cfg.curriculum, name):
                setattr(env_cfg.curriculum, name, None)
        self.changes.append("S1 명령 고정 %r, 깃발 env 없음, 지연 · 세기 · 게인 · 마찰 · 질량 · 무게중심 무작위 끔" % (cmd.fixed_cmd,))


class S2Policy:
    """S2 정책 한 벌(actor + 지각 상태). 지도 선택은 체크포인트의 force_gt 를 따른다."""

    def __init__(self, runner, n, z_mode=None, act_mode=None):
        """z_mode: mean(지각 z 를 평균으로) | sample(학습 수집처럼 z 를 표집). act_mode: mean(결정 행동) | sample(표집 행동).
        지정이 없으면 환경 변수 S2_Z · S2_ACT (옛 S2_SAMPLE=1 은 S2_ACT=sample 과 같다: z 는 평균)."""
        import torch

        self.z_mode = z_mode or os.environ.get("S2_Z", "mean")
        self.act_mode = act_mode or os.environ.get("S2_ACT") or ("sample" if os.environ.get("S2_SAMPLE") == "1" else "mean")

        if self.z_mode not in ("mean", "sample") or self.act_mode not in ("mean", "sample"):
            raise ValueError("S2_Z · S2_ACT 는 mean 또는 sample: %r %r" % (self.z_mode, self.act_mode))

        if self.z_mode == "sample" and not runner.perception.cfg.sample_latent_in_rollout:
            raise ValueError("지각 cfg 의 sample_latent_in_rollout 이 꺼져 있어 z 표집을 켤 수 없다")

        self.runner = runner
        self.n = n
        self.pstate = runner.perception.init_state(n, runner.device)
        # 학습의 AdaSmpl(force_gt=True)는 첫 스텝과 매 reset 에서 모두 GT 를 고른다.
        # 그 밖의 평가에서는 기존처럼 복원 지도를 사용한다. map_input=none 은
        # StartPerception._advance 에서 지도를 소비하지 않는다.
        self.pstate.use_gt = torch.full(
            (n,), runner.perception.cfg.force_gt, dtype=torch.bool, device=runner.device
        )
        self.no_gt = self.pstate.use_gt.clone()  # reset 플래그. 외부 진단 도구와의 호환 이름.

    def __call__(self, obs):
        import torch

        r = self.runner

        with torch.inference_mode():
            raw = obs.to(r.device)
            o, depth, gmap, _gfeet, _vel, _con = r._split(raw)
            inp = r.perception.ingest(self.pstate, o, depth)
            est = r.perception.step(self.pstate, inp, gmap, deterministic=(self.z_mode == "mean"))
            ppo_obs = r._ppo_obs(raw, est)                    # est mask(EX-11)는 runner 의 이 함수 안에 있어 학습 · 평가가 같은 자리를 쓴다
            self.last_est = est                               # 명령 반응 시험(diag_cmd_response)이 같은 est 를 다시 쓴다

            if self.act_mode == "sample":
                return r.alg.policy.act(ppo_obs)

            return r.alg.policy.act_inference(ppo_obs)

    def reset(self, dones):
        import torch

        with torch.inference_mode():                       # 상태 텐서가 inference 모드에서 만들어져 밖에서는 제자리 쓰기가 막힌다
            self.runner.perception.reset_envs(self.pstate, dones > 0, self.no_gt)

    def act(self, obs):
        return self(obs)


def load_s2_runner(env, train_cfg, checkpoint, device, expect=None):
    """평가 경계: 체크포인트의 est_mode · critic_mode · map_input · force_gt 를 복원한다.
    `expect` ({"est_mode": ..., "critic_mode": ...})가 저장값과 다르면 거부한다(훈련 CLI override 를 사람이 기억하는 방식에 기대지 않는다).
    옛 체크포인트에 칸이 없으면 그때의 동작(learned · legacy · none · force_gt=False)으로 본다. 돌려주는 값: (runner, 체크포인트 dict)."""
    import torch

    from foothold_s2.runners.start_runner import MODE_DEFAULTS, StartRunner

    sd = torch.load(checkpoint, weights_only=False, map_location=device)
    saved = sd.get("perception_cfg") or {}
    pc = dict(train_cfg.get("perception", {}) or {})
    pc["map_input"] = saved.get("map_input", "none")
    force_gt = saved.get("force_gt", False)
    if not isinstance(force_gt, bool):
        raise ValueError("체크포인트의 force_gt 는 bool 이어야 한다: %r" % (force_gt,))
    pc["force_gt"] = force_gt
    delay = saved.get("depth_delay_ticks", 1)
    if not isinstance(delay, int) or delay not in (0, 1):
        raise ValueError("checkpoint depth_delay_ticks must be 0 or 1")
    if (sd.get("sol23f") or {}).get("variant") == "START_TopDown" and delay != 0:
        raise ValueError("TopDown checkpoint missing depth_delay_ticks=0")
    pc["depth_delay_ticks"] = delay
    pc["oracle_vel_noise"] = 0.0                      # 평가는 관측 잡음을 끈다(est_mode=oracle_vel 체크포인트도 실제 선속도를 잡음 없이 넣는다)

    for key, default in MODE_DEFAULTS.items():
        value = saved.get(key, default)

        if expect and expect.get(key) not in (None, value):
            raise ValueError("체크포인트의 %s=%r 와 요청 %r 가 다르다" % (key, value, expect[key]))

        pc[key] = value

    cfg = dict(train_cfg)
    cfg["perception"] = pc
    runner = StartRunner(env, cfg, log_dir=None, device=device)
    runner.alg.policy.load_state_dict(sd["model_state_dict"])
    runner.perception.load_state_dict(sd["perception_state_dict"])
    runner.alg.policy.eval()
    runner.perception.eval()

    return runner, sd


class S2Adapter(S1Adapter):
    """S2 평가 판. 관측은 45 + 지각 묶음, 지도 입력은 체크포인트의 map_input 이 정한다.

    S1Adapter 와 같은 평가 규칙(명령 고정 · 깃발 없음 · 무작위 끔 · 커리큘럼 끔). 체크포인트는 정책과 지각 상태만 읽는다
    (StartRunner.load 는 학습 env 의 지형 단계를 복사해서 평가 env 크기와 안 맞는다).
    """

    def __init__(self, variant="open"):
        from foothold_s2.tasks.s2_env_cfg import FootholdS2G0EnvCfg

        IsaacLabAdapter.__init__(self, name="s2" + variant, env_cfg_class=FootholdS2G0EnvCfg)
        self.task_id = "FootholdS2-Go2-S2-diag-G0-%s-v0" % variant

    def _configure_command(self, env_cfg, base_cmd):
        super()._configure_command(env_cfg, base_cmd)
        cmd = env_cfg.commands.base_velocity
        cmd.dynamic_flags = False
        cmd.params = {}
        self.changes.append("S2: dynamic_flags 끔, 물러나기 · start_mode 끔 (명령 고정)")

    def load_policy(self, built, checkpoint):
        agent_cfg = built["agent_cfg"]
        env = built.get("env") or self.wrap(built)
        runner, sd = load_s2_runner(env, agent_cfg.to_dict(), checkpoint, agent_cfg.device, expect=getattr(self, "expect_modes", None))
        policy = S2Policy(runner, env.num_envs)
        obs = env.get_observations()
        self.checks["policy_class"] = type(runner.alg.policy).__name__
        self.checks["checkpoint_iter"] = int(sd.get("iter", -1))
        self.checks["restored_modes"] = {"est_mode": runner.pcfg["est_mode"], "critic_mode": runner.pcfg["critic_mode"],
                                         "map_input": runner.pcfg.get("map_input"), "force_gt": runner.perception.cfg.force_gt}
        self.checks["obs_keys"] = sorted(obs.keys())

        return env, policy, policy, obs


def deep_copy_generator(generator):
    return copy.deepcopy(generator)


def sparse_start_root_height(adapter):
    """환경을 만들기 전에 같은 로봇 cfg의 기본 자세를 검사한다. Kit 기동은 하지 않는다."""
    from foothold_s2.robots.go2_kinematics import root_height_from_cfg
    if isinstance(adapter, E1Adapter):
        from robot_lab.tasks.go2.env_cfg import Go2EnvCfg
        cfg = Go2EnvCfg()
    else:
        cfg = adapter.env_cfg_class()
    return root_height_from_cfg(cfg.scene.robot)
