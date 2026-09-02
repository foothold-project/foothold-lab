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
ADDED_TERRAIN_NAMES = (
    "flat",  # #125 2번. 기준선 10 m 직진을 재는 자.
)

TERRAIN_NAMES = SNAPSHOT_TERRAIN_NAMES + ADDED_TERRAIN_NAMES

# 험지가 아닌 지형. 기준선용이라 험지 통계에서 빼고 볼 때가 있습니다.
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
