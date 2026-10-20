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
from isaaclab.utils import configclass

from foothold_s2.curriculum import terrain_levels_mixed as tlm

from foothold_s2.tasks.s1_env_cfg import FootholdS1aScanEnvCfg
from foothold_s2.terrains import columns

NUM_ENVS_S2 = 3072


def _sparse_subterrains():
    try:
        from foothold_s2.terrains import sparse_terrains
    except ImportError as exc:
        raise NotImplementedError("듬성한 지형 생성기(terrains/sparse_terrains.py)가 아직 없다 (15 §8)") from exc

    return sparse_terrains.sparse_subterrains()


@configclass
class FootholdS2G0EnvCfg(FootholdS1aScanEnvCfg):
    """G0: 눈만 끈 기준선 (`--map_input none`). 정답 높이 스캔도 지도도 actor 에 없다. 센서와 관측 묶음은 runner 계약이라 있다."""

    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = NUM_ENVS_S2
        self.observations.policy.height_scan = None
        self.rewards.foot_edge.weight = 0.0
        self.commands.base_velocity.dynamic_flags = True
        # 물러나기 (14 §3, D39): 깃발 env 가 한 깃발 이상 지난 뒤 확률 0.15 로 -0.1~-0.3 m/s 를 2 s (최대 0.6 m)
        self.commands.base_velocity.params = {"backoff_prob": 0.15, "backoff_vmin": 0.1, "backoff_vmax": 0.3, "backoff_s": 2.0}
        self.use_full_terrain()
        from foothold_s2.sensors.start_obs import apply_start_perception   # runner 계약상 G0 도 묶음은 있어야 한다 (map_input none 이 입력만 끈다)

        apply_start_perception(self)

    def use_full_terrain(self):
        """이어진 7 종 + 듬성한 지형으로 50 열 생성기를 만든다 (듬성한 지형 생성기가 생기면)."""
        from foothold_s2.terrains.rough_go2_cfg import build_generator, continuous_subterrains

        subs = {**continuous_subterrains(), **_sparse_subterrains()}
        self.scene.terrain.terrain_generator = build_generator(subs, columns.FULL_COLS)
        self.curriculum.terrain_levels = CurrTerm(func=tlm.terrain_levels_s2)


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
