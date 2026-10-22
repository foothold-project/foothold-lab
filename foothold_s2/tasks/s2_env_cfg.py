"""S2 env cfg 뼈대 (14 · 15 · 16 · 53). Kit 안에서만 불린다. S1 scan 판을 상속해 아래만 바꾼다.

- policy 묶음은 o_t 45 만 (높이 스캔 187 을 뺀다). 지각 센서와 runner 관측 묶음 다섯은 rl 의 `apply_start_perception` 이 붙인다.
- env 3072, 열 50 (15 §2). 지형은 이어진 지형 + 듬성한 지형.
- 명령 term 은 S1 의 MixedVelocityCommand 를 그대로 쓰고 깃발은 `flag_provider` 로 갈아 끼운다.

아직 없는 것 (이 파일이 «구멍» 으로 드러낸다, 자리만 있음):
  1. (만듦) 듬성한 지형 생성기 `terrains/sparse_terrains.py`
  2. (만듦) p_advance 재배정 term `tlm.terrain_levels_s2`. env 생성 뒤 reset 전에 `tlm.attach_s2_tables(env, sparse_terrains.SIDE_TABLE, s2_layout.Layout())` 를 한 번 불러야 한다 (학습 실행기 몫)
  3. 발 가장자리 보상의 마스크 조회 (G3 만, 16 §5). G0 · G1 은 가중치 0 이라 지금 뼈대로 가능
"""

from isaaclab.managers import CurriculumTermCfg as CurrTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass

from foothold_s2.curriculum import terrain_levels_mixed as tlm
from foothold_s2.rewards import mgdp_terms

from foothold_s2.tasks.s1_env_cfg import FootholdS1aScanEnvCfg
from foothold_s2.terrains import columns

NUM_ENVS_S2 = 3072


def _sparse_subterrains():
    try:
        from foothold_s2.terrains import sparse_terrains
    except ImportError as exc:
        raise NotImplementedError("듬성한 지형 생성기(terrains/sparse_terrains.py)가 아직 없다 (15 §8)") from exc

    return sparse_terrains.sparse_subterrains()


BACKOFF_PARAMS = {"backoff_prob": 0.15, "backoff_vmin": 0.1, "backoff_vmax": 0.3, "backoff_s": 2.0}


def apply_full_terrain_and_flags(cfg, t_start=1000, t_end=8000):
    """50 열 생성기(이어진 7 종 + 듬성한 지형) · 동적 깃발(듬성한 칸은 항상 깃발) · 물러나기 · p_advance 재배정 term. S2 와 S1-b 가 같이 쓴다."""
    from foothold_s2.terrains.rough_go2_cfg import build_generator, continuous_subterrains

    cfg.commands.base_velocity.dynamic_flags = True
    cfg.commands.base_velocity.params = dict(BACKOFF_PARAMS)   # 물러나기 (14 §3, D39): 한 깃발 이상 지난 뒤 확률 0.15 로 -0.1~-0.3 m/s 를 2 s (최대 0.6 m)
    subs = {**continuous_subterrains(), **_sparse_subterrains()}
    cfg.scene.terrain.terrain_generator = build_generator(subs, columns.FULL_COLS)
    cfg.curriculum.terrain_levels = CurrTerm(func=tlm.terrain_levels_s2, params={"t_start": t_start, "t_end": t_end})


@configclass
class FootholdS2G0EnvCfg(FootholdS1aScanEnvCfg):
    """G0: 눈만 끈 기준선 (`--map_input none`). 정답 높이 스캔도 지도도 actor 에 없다. 센서와 관측 묶음은 runner 계약이라 있다."""

    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = NUM_ENVS_S2
        self.observations.policy.height_scan = None
        self.rewards.foot_edge.weight = 0.0
        self.use_full_terrain()
        from foothold_s2.sensors.start_obs import apply_start_perception   # runner 계약상 G0 도 묶음은 있어야 한다 (map_input none 이 입력만 끈다)

        apply_start_perception(self)

    def use_full_terrain(self):
        """이어진 7 종 + 듬성한 지형으로 50 열 생성기를 만든다 (듬성한 지형 생성기가 생기면)."""
        apply_full_terrain_and_flags(self)


@configclass
class FootholdS2G1EnvCfg(FootholdS2G0EnvCfg):
    """G1: G0 와 같은 env, 지도 입력은 학습 실행기의 `--map_input reconstruction` 이 켠다. 발 가장자리 벌점 없음."""


@configclass
class FootholdS2G3EnvCfg(FootholdS2G1EnvCfg):
    """G3: G1 + 발 가장자리 벌점 (가중치는 core.WEIGHTS, 마스크 조회 구현 뒤)."""

    def __post_init__(self):
        super().__post_init__()
        from foothold_s2.rewards import core

        self.rewards.foot_edge.weight = core.WEIGHTS["foot_edge"]


@configclass
class FootholdS2DiagG0StartEnvCfg(FootholdS2G0EnvCfg):
    """G0-start (lead 10/21 진단): S2-G0 와 같고 명령만 START 원문(`start_mode`). 깃발 없음 · 정지 없음 · heading 없음, 재표집 4 s 그대로."""

    def __post_init__(self):
        super().__post_init__()
        cmd = self.commands.base_velocity
        cmd.dynamic_flags = False
        cmd.flag_stride = 0
        cmd.params = {"start_mode": True}


@configclass
class FootholdS2X11EnvCfg(FootholdS2DiagG0StartEnvCfg):
    """EX-11 · EX-12 공통 환경 (SONNET-X11 X1). 두 판은 이 env 가 같고 est 처치만 runner 의 est_mode 로 다르다.

    지형: S1 의 이어진 지형 7종 · 23 열 · 초기 레벨 · 승급 · 강등 · 범위 커리큘럼 · reset 원점을 S1 과 같게 둔다(S1SceneCfg · S1 CurriculumCfg 를 그대로 상속).
    50 열 생성기 · 듬성한 지형 재배정 · 깃발 공급자는 쓰지 않는다(use_full_terrain 을 비운다, env 클래스도 side table 을 붙이지 않는 ManagerBasedRLEnv).
    명령: START 원문(start_mode · 깃발 없음 · 정지 없음 · 4 s 재표집). start_mode 는 범위 커리큘럼의 vmax 를 읽지 않는다(mixed_core.resample_start).
    보상 커널 B std 0.5 · 종료 여유 0.25 · clip 17 은 G0 그대로(agent cfg).
    """

    def use_full_terrain(self):
        return None


@configclass
class FootholdS2X14EnvCfg(FootholdS2X11EnvCfg):
    """EX-14 (SONNET-X13): EX-11 환경 + feet_air_time +1.0 하나만 (MGDP 식 그대로, rewards/mgdp_core.py). 나머지는 EX-11 과 같다(est 처치는 agent cfg 의 est_mode)."""

    def __post_init__(self):
        super().__post_init__()
        self.rewards.feet_air_time = RewTerm(
            func=mgdp_terms.feet_air_time_mgdp, weight=1.0,
            params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot"), "command_name": "base_velocity"})


@configclass
class FootholdS2X13EnvCfg(FootholdS2X14EnvCfg):
    """EX-13 (SONNET-X13, MGDP 묶음 넷): EX-14 의 feet_air_time +1.0 에 motion_trot -0.1 · stand_still -0.1 · only_positive_rewards 를 더한다.
    only_positive_rewards 는 env 클래스(FootholdS2PosRewardEnv)가 이 칸을 읽어 보상 합을 0 아래로 자른다."""

    only_positive_rewards: bool = True

    def __post_init__(self):
        super().__post_init__()
        self.rewards.motion_trot = RewTerm(func=mgdp_terms.motion_trot_mgdp, weight=-0.1)
        self.rewards.stand_still = RewTerm(func=mgdp_terms.stand_still_mgdp, weight=-0.1, params={"command_name": "base_velocity"})
