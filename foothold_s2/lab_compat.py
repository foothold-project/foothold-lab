"""Isaac Lab 2.3.2 와 3.0 의 차이를 한 곳에 모은다 (HiPAN 모드 2 · lead 11/17 13:22 · 목록 hipan-isaaclab3-migration-grep.md).
조용히 틀리는 두 가지를 여기서 막는다:
  1. 쿼터니언 순서: 2.x 는 (w x y z) · 3.0 은 (x y z w). 이 저장소의 numpy 쪽 (yaw_from_quat_wxyz 등) 은 wxyz 로 두고, 경계에서만 바꾼다
     (`quat_wxyz` = 시뮬이 준 값 -> wxyz · `quat_cfg` = wxyz 로 적은 값 -> cfg 에 넣을 순서).
  2. 데이터 속성: 3.0 은 torch.Tensor 대신 ProxyArray (`.torch` 로 텐서) 를 준다 (`th`). 2.x 의 텐서는 그대로 지나간다.
Isaac 없이 부를 수 있다 (표준 라이브러리 + 넘겨받은 배열). 판은 환경 변수 FOOTHOLD_LAB_MAJOR (2 또는 3) 로 덮어쓸 수 있고, 없으면 설치된 isaaclab 패키지 버전, 그것도 없으면 2.
"""
from __future__ import annotations

import os

_ENV = "FOOTHOLD_LAB_MAJOR"


def lab_major() -> int:
    raw = os.environ.get(_ENV)
    if raw:
        if raw not in ("2", "3"):
            raise ValueError(f"{_ENV} must be 2 or 3, got {raw!r}")
        return int(raw)
    try:
        from importlib.metadata import version

        return int(version("isaaclab").split(".")[0])
    except Exception:                                    # 설치 안 됨 (CPU 시험) 또는 버전 못 읽음
        return 2


def th(x):
    """ProxyArray -> torch.Tensor (`.torch`). 이미 텐서 · numpy 면 그대로."""
    return getattr(x, "torch", x)


def quat_wxyz(q, major: int | None = None):
    """시뮬이 준 쿼터니언 (…, 4) -> wxyz. torch · numpy 둘 다 (마지막 축 재배열)."""
    q = th(q)
    return q[..., [3, 0, 1, 2]] if (lab_major() if major is None else major) >= 3 else q


def quat_cfg(q_wxyz, major: int | None = None) -> tuple:
    """wxyz 로 적은 쿼터니언 -> 이 판 cfg (OffsetCfg.rot 등) 가 받는 순서의 튜플."""
    w, x, y, z = (float(v) for v in q_wxyz)
    return (x, y, z, w) if (lab_major() if major is None else major) >= 3 else (w, x, y, z)


def quat_to_sim(q_wxyz, major: int | None = None):
    """wxyz 쿼터니언 (…, 4) 텐서 · 배열 -> 이 판의 시뮬 쓰기 함수 (write_root_pose_to_sim 등) 가 받는 순서. `quat_wxyz` 의 역."""
    return q_wxyz[..., [1, 2, 3, 0]] if (lab_major() if major is None else major) >= 3 else q_wxyz
