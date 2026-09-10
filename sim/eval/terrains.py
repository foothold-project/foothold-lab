"""지형 이름과 그 순서. 하네스와 설정이 같은 목록을 보게 하는 자리.

이 순서가 곧 **지형 인덱스**입니다. Isaac Lab 이 `sub_terrains` 의 등록 순서대로
열을 배정하고, 하네스는 `TERRAIN_NAMES[terrain_type]` 으로 이름을 되찾습니다.
그래서 이 목록과 `generalization_env_cfg.py` 의 `sub_terrains` 순서가
**한 칸이라도 어긋나면 이름과 지형이 뒤바뀝니다.**

`tests/test_terrains.py` 가 둘을 매번 대조합니다.

`isaaclab` 을 쓰지 않으므로 Windows 에서 그대로 임포트됩니다.
"""

# Candidate 스냅샷의 10종. **순서를 바꾸지 마십시오.**
# 500판 기록이 이 인덱스로 저장돼 있습니다. 앞에 무언가를 끼우면 전부 밀립니다.
SNAPSHOT_TERRAIN_NAMES = (
    "discrete_obstacles",
    "wave",
    "stepping_stones",
    "gap",
    "pit",
    "rails",
    "star",
    "floating_ring",
    "repeated_boxes",
    "repeated_cylinders",
)

# 우리가 더한 지형. 스냅샷에 없던 것은 여기 있는 것뿐입니다.
# 새 지형은 **맨 뒤에** 붙입니다. 기존 인덱스를 지키기 위해서입니다.
# 2026-09-08 에 비웠다. 팀장 결정이다.
#
#   평지는 «미경험 험지» 가 아니다. 한 표에 섞이면 험지 평균이 부풀려진다.
#   험지 10종 평균 0.394 에 평지 0.98 이 끼면 11종 평균이 0.447 이 되어
#   5.3 퍼센트포인트가 그냥 오른다. 성공률을 올리는 실험 중에 이 정도면
#   결론이 바뀐다.
#
#   #125 2번이 「평지 10 m 직진을 재려면 평지 cfg 가 필요하다」로 flat 을
#   더했다. 목적은 맞았지만 «가르는 코드» 가 없었다. ROUGH_TERRAIN_NAMES 와
#   is_flat() 을 만들어 놓고 어느 파일도 부르지 않았다.
#
#   평지 기준선은 `docs/research/flat-straight-baseline-10m.md` 가 정본이다.
#   다시 재야 하면 여기에 "flat" 을 넣고 generalization_env_cfg 의 cfg 도
#   함께 살린 뒤, «집계에서 가르는 코드까지» 만들고 나서 쓴다.
ADDED_TERRAIN_NAMES = ()

TERRAIN_NAMES = SNAPSHOT_TERRAIN_NAMES + ADDED_TERRAIN_NAMES

# 험지가 아닌 지형. 지금은 평가 목록에 없다(위 ADDED_TERRAIN_NAMES 참조).
# 이름을 남겨 두는 이유는 다시 넣을 때 가르는 자리를 잊지 않기 위해서다.
FLAT_TERRAIN_NAMES = ("flat",)

ROUGH_TERRAIN_NAMES = tuple(
    name for name in TERRAIN_NAMES if name not in FLAT_TERRAIN_NAMES
)


def terrain_index(name):
    """지형 이름의 인덱스. Isaac Lab 의 `terrain_types` 값과 같아야 한다."""
    return TERRAIN_NAMES.index(name)


def terrain_name(index):
    """인덱스에서 지형 이름. 하네스의 `TERRAIN_NAMES[terrain_type]` 과 같다."""
    return TERRAIN_NAMES[index]


def is_flat(name):
    """험지가 아닌 기준선 지형인가."""
    return name in FLAT_TERRAIN_NAMES


# ---------------------------------------------------------------- 학습에서 본 험지 6종

# NVIDIA 공식 체크포인트가 **학습에 쓴** 지형이다. 위 10종(미경험)과 성격이 반대다.
#
# 순서는 Isaac Lab 원본 `ROUGH_TERRAINS_CFG` 의 `sub_terrains` 등록 순서 그대로다.
# 이 순서가 곧 열 번호이고, `rough6_env_cfg.py` 의 등록 순서와 한 칸이라도
# 어긋나면 이름과 지형이 뒤바뀐다. `tests/test_terrains.py` 가 둘을 대조한다.
ROUGH6_TERRAIN_NAMES = (
    "pyramid_stairs",
    "pyramid_stairs_inv",
    "boxes",
    "random_rough",
    "hf_pyramid_slope",
    "hf_pyramid_slope_inv",
)

# 하네스가 `--terrain_set` 으로 고르는 자리. 값은 (이름 목록, 설정 모듈, 설정 클래스).
TERRAIN_SETS = {
    "unseen10": (TERRAIN_NAMES, "generalization_env_cfg", "UnitreeGo2GeneralizationEnvCfg"),
    "rough6": (ROUGH6_TERRAIN_NAMES, "rough6_env_cfg", "UnitreeGo2Rough6EnvCfg"),
}


def terrain_set(name):
    """이름으로 지형 집합을 고른다. 모르는 이름이면 죽는다."""
    if name not in TERRAIN_SETS:
        raise ValueError(
            f"모르는 지형 집합: {name}. 있는 것: {sorted(TERRAIN_SETS)}"
        )

    return TERRAIN_SETS[name]

# ---------------------------------------------------------------- 장애물 구간

# Isaac Lab 이 하위 지형을 굽는 식에서 그대로 읽은 상수.
#
# `rails_terrain()` 과 `pit_terrain(double_pit=True)` 가 둘째 링을
# `platform + (size - platform) * 0.6` 자리에 놓는다. 0.6 이 그 비율이다.
# 근거: `isaaclab/terrains/trimesh/mesh_terrains.py` (Isaac Lab 0.54.2 · 410행
# `rail_2_ratio = 0.6`, 467행 `ring_2_ratio = 0.6`) 를 2026-09-10 에 직접 열어
# 확인했다 `확인됨`. **렌더해서 눈으로 재보지는 않았다** `미확인`.
_SECOND_RING_RATIO = 0.6


def _lerp(value_range, difficulty):
    """Isaac Lab 이 난이도로 값을 고르는 식. `low + d x (high - low)`."""
    low, high = value_range

    return low + difficulty * (high - low)


def _platform_half_m(cfg):
    """가운데 평탄 플랫폼의 절반 폭. 플랫폼이 없는 지형은 0.0."""
    width = getattr(cfg, "platform_width", None)

    if width is None:
        return 0.0

    return float(width) / 2.0


def obstacle_zone_m(cfg, difficulty, tile_size_x_m):
    """그 지형에서 **장애물이 실제로 놓인** 전진 구간. `(시작 m, 끝 m, 근거)`.

    출발점(타일 중앙)에서 앞으로 잰 거리입니다. `speed_drop_ratio` 가 이 구간
    안에서 최저 속도를 집습니다 (`metrics.speed_drop_ratio`).

    ## 구간을 어떻게 잡나

    | 무엇 | 어떻게 |
    |---|---|
    | 시작 | `platform_width / 2`. 가운데 평탄 플랫폼이 끝나는 자리 |
    | 끝 | 아래 표. 지형 설정에서 계산한다 |

    **지형 이름으로 숫자를 박아 두지 않습니다.** 설정 객체의 종류와 그 안의
    값에서 계산하므로, `difficulty` 를 바꾸면 구간도 함께 움직입니다.

    | 설정 종류 | 끝 | 근거 (Isaac Lab 0.54.2) |
    |---|---|---|
    | `MeshGapTerrainCfg` | `플랫폼/2 + 틈폭(d)` | `gap_terrain()` 588행 |
    | `MeshFloatingRingTerrainCfg` | `플랫폼/2 + 고리폭(d)` | `floating_ring_terrain()` 634행 |
    | `MeshRailsTerrainCfg` | 바깥 레일의 **바깥 모서리** | `rails_terrain()` 417~420행 |
    | 그 밖 전부 | `tile_size_x_m / 2` (타일 절반) | 장애물이 타일을 채운다 |

    `tile_size_x_m` 은 **부모 생성기의 `size[0]`** 입니다 (여기서는 8.0 m).
    하위 지형 설정의 `size` 를 읽지 않습니다. 그 칸은 `TerrainGenerator` 가
    지형을 굽기 **직전에** 채우므로(`terrain_generator.py` 125행), 굽기 전에
    읽으면 기본값이 잡힙니다. 부모에서 받아 오면 그 순서 함정이 아예 없습니다.

    「그 밖」에는 험지 여섯(`discrete_obstacles` `wave` `stepping_stones` `star`
    `repeated_boxes` `repeated_cylinders`)과 `pit` 이 듭니다. 앞 여섯은 장애물이
    정말 타일 전체에 깔립니다. `pit` 은 다릅니다. **로봇이 구덩이 바닥에서
    출발**하고(`pit_terrain()` 492행이 원점을 `-total_depth` 로 둡니다) 장애물은
    플랫폼 가장자리의 턱 하나뿐이라, 「끝」을 그 턱으로 잡으면 구간의 폭이 0 이
    됩니다. 그래서 타일 절반을 씁니다. **구간이 넓어질 뿐 턱은 그 안에 듭니다.**

    ## 넓게 잡는 것이 왜 안전한가

    이 구간에서 집는 것이 **최솟값**이기 때문입니다. 구간을 넓히면 평지 표본이
    더 들어오는데, 평지에서는 로봇이 명령 속도로 걷고 있으므로 최솟값을 안
    끌어내립니다. 반대로 구간을 짧게 잡아 장애물을 **놓치면** 그 에피소드는
    「안 줄였다」로 잘못 읽힙니다. 그래서 모르면 넓게 잡습니다.

    ## 한계 (재보지 않은 것)

    · 설정 종류를 **클래스 이름**으로 가릅니다. Isaac Lab 이 이름을 바꾸면
      「그 밖」으로 떨어지고, 그때도 죽지 않고 타일 절반을 씁니다. 어느 규칙이
      걸렸는지는 셋째 값(`근거`)에 남고 `run_manifest.json` 에 기록됩니다.
    · 출발점은 타일 중앙이 아니라 **로봇이 실제로 선 자리**입니다. 하네스가
      `--spawn_xy_range` 만큼(기본 0.10 m) 흔들어 놓습니다. 그만큼 구간이
      앞뒤로 밀립니다 `미확인` (그 오차가 결과를 얼마나 바꾸는지 안 재봤습니다).
    · `difficulty` 는 부르는 쪽이 넘깁니다. `num_rows == 1` 이고
      `difficulty_range` 가 `(d, d)` 면 타일의 실제 난이도가 정확히 `d` 입니다.
      범위가 넓으면 타일마다 다르고, 이 함수는 그 대표값 하나만 받습니다.
    """
    start = _platform_half_m(cfg)
    tile_half = float(tile_size_x_m) / 2.0

    kind = type(cfg).__name__

    end = None
    basis = ""

    if kind == "MeshGapTerrainCfg":
        end = start + _lerp(cfg.gap_width_range, difficulty)
        basis = "gap_width_range"

    elif kind == "MeshFloatingRingTerrainCfg":
        end = start + _lerp(cfg.ring_width_range, difficulty)
        basis = "ring_width_range"

    elif kind == "MeshRailsTerrainCfg":
        platform = float(cfg.platform_width)
        outer_thickness = float(cfg.rail_thickness_range[1])

        inner = platform + (float(tile_size_x_m) - platform) * _SECOND_RING_RATIO

        end = inner / 2.0 + outer_thickness
        basis = "rail_2_outer_edge"

    # 규칙이 없거나(그 밖 전부) 폭이 0 이하로 나오면 타일 절반을 쓴다.
    # **조용히 넘기지 않는다.** 어느 쪽이 걸렸는지가 셋째 값에 남는다.
    if end is None or end <= start:
        return (start, tile_half, "tile_half:" + kind)

    return (start, end, basis)
