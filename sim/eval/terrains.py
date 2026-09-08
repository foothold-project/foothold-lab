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
