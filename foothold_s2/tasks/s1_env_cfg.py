"""S1-a env cfg (13 · 14 · 15 · 16 · 17 · 18 · 52). Kit 안에서만 불린다.

scan 판: actor 입력 o_t 45 + 높이 스캔 187 = 232. blind 판: 고유수용 이력 11 스텝 x 45 = 495.
critic(두 판 공통, 가정): o_t(잡음 없음) + 몸 선속도 3 + 발 접촉 4. 문서에 S1 critic 구성이 없어 이렇게 둔다 (인계 문서 참고).
S2 는 이 클래스를 상속해 명령 · 지형 · 보상만 바꾼다.
"""

import isaaclab.sim as sim_utils
import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from isaaclab.envs import ManagerBasedRLEnvCfg
from isaaclab.managers import CurriculumTermCfg as CurrTerm
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sensors import ContactSensorCfg, RayCasterCfg, patterns
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.utils import configclass
from isaaclab.utils.assets import ISAACLAB_NUCLEUS_DIR
from isaaclab.utils.noise import AdditiveUniformNoiseCfg as Unoise

from foothold_s2.commands.mixed_command import MixedVelocityCommandCfg
from foothold_s2.curriculum import terrain_levels_mixed as tlm
from foothold_s2.rewards import penalty_log
from foothold_s2.rewards import start_rewards
from foothold_s2.rewards.start_rewards import StartRewardsCfg
from foothold_s2.robots import go2_params as gp
from foothold_s2.robots.go2_cfg import GO2_S1_CFG
from foothold_s2.tasks import mdp_extra
from foothold_s2.tasks.delayed_action import DelayedJointPositionActionCfg
from foothold_s2.terrains.rough_go2_cfg import s1a_generator

FEET = ".*_foot"
HISTORY_STEPS = 11


@configclass
class S1SceneCfg(InteractiveSceneCfg):
    terrain = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="generator",
        terrain_generator=s1a_generator(),
        max_init_terrain_level=2,
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="multiply", restitution_combine_mode="multiply",
            static_friction=1.0, dynamic_friction=1.0),
        visual_material=sim_utils.MdlFileCfg(
            mdl_path=f"{ISAACLAB_NUCLEUS_DIR}/Materials/TilesMarbleSpiderWhiteBrickBondHoned/"
                     "TilesMarbleSpiderWhiteBrickBondHoned.mdl",
            project_uvw=True, texture_scale=(0.25, 0.25)),
        debug_vis=False,
    )
    robot = GO2_S1_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")
    height_scanner = RayCasterCfg(
        prim_path="{ENV_REGEX_NS}/Robot/base",
        offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 20.0)),
        ray_alignment="yaw",
        pattern_cfg=patterns.GridPatternCfg(resolution=0.1, size=[1.6, 1.0]),   # 17 x 11 = 187 점
        debug_vis=False,
        mesh_prim_paths=["/World/ground"],
    )
    contact_forces = ContactSensorCfg(prim_path="{ENV_REGEX_NS}/Robot/.*", history_length=3, track_air_time=True)
    sky_light = None


@configclass
class CommandsCfg:
    base_velocity = MixedVelocityCommandCfg(
        asset_name="robot", resampling_time_range=(4.0, 4.0), debug_vis=False, seed=0,
        flag_stride=5, flag_count=4)


@configclass
class ActionsCfg:
    joint_pos = DelayedJointPositionActionCfg(asset_name="robot", joint_names=[".*"], scale=0.25,
                                           use_default_offset=True)


@configclass
class ObservationsCfg:
    @configclass
    class PolicyCfg(ObsGroup):
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel, noise=Unoise(n_min=-0.2, n_max=0.2))
        projected_gravity = ObsTerm(func=mdp.projected_gravity, noise=Unoise(n_min=-0.05, n_max=0.05))
        velocity_commands = ObsTerm(func=mdp.generated_commands, params={"command_name": "base_velocity"})
        joint_pos = ObsTerm(func=mdp.joint_pos_rel, noise=Unoise(n_min=-0.01, n_max=0.01))
        joint_vel = ObsTerm(func=mdp.joint_vel_rel, noise=Unoise(n_min=-1.5, n_max=1.5))
        actions = ObsTerm(func=mdp.last_action)
        height_scan = ObsTerm(func=mdp.height_scan, params={"sensor_cfg": SceneEntityCfg("height_scanner")},
                              noise=Unoise(n_min=-0.1, n_max=0.1), clip=(-1.0, 1.0))

        def __post_init__(self):
            self.enable_corruption = True
            self.concatenate_terms = True

    @configclass
    class CriticCfg(ObsGroup):
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel)
        projected_gravity = ObsTerm(func=mdp.projected_gravity)
        velocity_commands = ObsTerm(func=mdp.generated_commands, params={"command_name": "base_velocity"})
        joint_pos = ObsTerm(func=mdp.joint_pos_rel)
        joint_vel = ObsTerm(func=mdp.joint_vel_rel)
        actions = ObsTerm(func=mdp.last_action)
        base_lin_vel = ObsTerm(func=mdp.base_lin_vel)
        foot_contact = ObsTerm(func=mdp_extra.foot_contact,
                               params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=FEET)})

        def __post_init__(self):
            self.enable_corruption = False
            self.concatenate_terms = True

    policy: PolicyCfg = PolicyCfg()
    critic: CriticCfg = CriticCfg()


@configclass
class EventCfg:
    """PIE 도메인 무작위화 (17 §5). push 없음. 행동 지연 0~15 ms 는 DelayedJointPositionAction, 모터 세기 0.9~1.1 은 randomize_motor_strength."""

    physics_material = EventTerm(
        func=mdp.randomize_rigid_body_material, mode="startup",
        params={"asset_cfg": SceneEntityCfg("robot", body_names=".*"),
                "static_friction_range": gp.PIE["friction"], "dynamic_friction_range": gp.PIE["friction"],
                "restitution_range": (0.0, 0.0), "num_buckets": 64, "make_consistent": True})
    add_base_mass = EventTerm(
        func=mdp.randomize_rigid_body_mass, mode="startup",
        params={"asset_cfg": SceneEntityCfg("robot", body_names="base"),
                "mass_distribution_params": gp.PIE["base_mass_add_kg"], "operation": "add"})
    base_com = EventTerm(
        func=mdp.randomize_rigid_body_com, mode="startup",
        params={"asset_cfg": SceneEntityCfg("robot", body_names="base"),
                "com_range": {"x": gp.PIE["com_shift_m"], "y": gp.PIE["com_shift_m"], "z": gp.PIE["com_shift_m"]}})
    actuator_gains = EventTerm(
        func=mdp.randomize_actuator_gains, mode="startup",
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=".*"), "operation": "scale",
                "stiffness_distribution_params": gp.PIE["gain_scale"],
                "damping_distribution_params": gp.PIE["gain_scale"], "distribution": "uniform"})
    motor_strength = EventTerm(
        func=mdp_extra.randomize_motor_strength, mode="startup",
        params={"asset_cfg": SceneEntityCfg("robot"), "scale_range": gp.PIE["gain_scale"]})
    reset_base = EventTerm(
        func=mdp.reset_root_state_uniform, mode="reset",
        params={"pose_range": {"x": (-0.5, 0.5), "y": (-0.5, 0.5), "yaw": (-3.14, 3.14)},
                "velocity_range": {k: (0.0, 0.0) for k in ("x", "y", "z", "roll", "pitch", "yaw")}})
    reset_robot_joints = EventTerm(
        func=mdp.reset_joints_by_scale, mode="reset",
        params={"position_range": gp.PIE["reset_joint_scale"], "velocity_range": (0.0, 0.0)})


@configclass
class TerminationsCfg:
    """몸통 접촉 종료 없음 (17 §7). 기울기 1.5 rad · 발이 지면 0.2 m 아래."""

    time_out = DoneTerm(func=mdp.time_out, time_out=True)
    bad_orientation = DoneTerm(func=mdp.bad_orientation,
                               params={"limit_angle": gp.TERMINATION["max_tilt_rad"]})
    foot_below_ground = DoneTerm(
        func=mdp_extra.foot_below_ground,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=FEET),
                "scanner_cfg": SceneEntityCfg("height_scanner"),
                "asset_cfg": SceneEntityCfg("robot", body_names=FEET),
                "margin": gp.TERMINATION["foot_below_ground_m"]})


@configclass
class CurriculumCfg:
    terrain_levels = CurrTerm(func=tlm.terrain_levels_mixed)
    command_range = CurrTerm(func=tlm.command_range_curriculum)
    penalty_on = CurrTerm(func=penalty_log.penalty_activation)


@configclass
class FootholdS1aScanEnvCfg(ManagerBasedRLEnvCfg):
    scene: S1SceneCfg = S1SceneCfg(num_envs=4096, env_spacing=2.5)
    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    commands: CommandsCfg = CommandsCfg()
    rewards: StartRewardsCfg = StartRewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()
    events: EventCfg = EventCfg()
    curriculum: CurriculumCfg = CurriculumCfg()
    track_lin_form: str = "B"
    """선속도 추종식. "B"(정확 추종, 기본, 팀장 승인) 또는 "A"(START 원문 min 식, 16 §3 대조용)."""

    def __post_init__(self):
        self.decimation = 4
        self.episode_length_s = 20.0
        self.sim.dt = 0.005
        self.sim.render_interval = self.decimation
        self.sim.physics_material = self.scene.terrain.physics_material
        self.sim.physx.gpu_max_rigid_patch_count = 10 * 2**15

        self.scene.height_scanner.update_period = self.decimation * self.sim.dt
        self.scene.contact_forces.update_period = self.sim.dt
        self.scene.terrain.terrain_generator.curriculum = True

        if self.track_lin_form == "A":
            self.rewards.track_lin_vel.func = start_rewards.track_lin_vel_min_form
        elif self.track_lin_form != "B":
            raise ValueError("track_lin_form 은 A 또는 B: %r" % (self.track_lin_form,))


@configclass
class FootholdS1aBlindEnvCfg(FootholdS1aScanEnvCfg):
    """눈 없는 판: 높이 스캔을 actor 에서 빼고 고유수용 이력 11 스텝을 이어 붙인다 (45 x 11 = 495)."""

    def __post_init__(self):
        super().__post_init__()
        self.observations.policy.height_scan = None
        self.observations.policy.history_length = HISTORY_STEPS
        self.observations.policy.flatten_history_dim = True

