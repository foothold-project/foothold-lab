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

        return lab_major_of_installed(version("isaaclab")) or 2
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


def lab_major_of_installed(pkg_version: str) -> int | None:
    """isaaclab 패키지 버전 -> Isaac Lab 주 버전. 실측 표: 이 기기 0.54.2 (Lab 2.3.2) -> 2 · Pod 28.0.0 (Lab 3.0) -> 3. 표 밖이면 None (판단 안 함)."""
    head = int(pkg_version.split(".")[0])
    if head == 0:
        return 2
    if head >= 28:
        return 3
    return None


def require_declared_major() -> int:
    """Kit 을 띄우는 진입점이 부른다: FOOTHOLD_LAB_MAJOR 선언이 없으면 거절. 설치 버전이 실측 표 (0.x -> 2 · 28.x -> 3) 에 있고 선언과 다르면 거절.
    버전을 못 읽거나 표 밖이면 선언을 믿는다 (reviewer 14:08: 패키지 버전 번호 자체는 Lab 주 버전이 아니다)."""
    raw = os.environ.get(_ENV)
    if raw not in ("2", "3"):
        raise RuntimeError(f"{_ENV} must be set to 2 or 3 before starting Kit (got {raw!r})")
    try:
        from importlib.metadata import version

        mapped = lab_major_of_installed(version("isaaclab"))
    except Exception:
        return int(raw)
    if mapped is not None and mapped != int(raw):
        raise RuntimeError(f"{_ENV}={raw} but the installed isaaclab maps to Lab {mapped} (package table: 0.x -> 2, 28.x -> 3)")
    return int(raw)


# ---------------------------------------------------------------- 옮겨진 모듈 (v3.0.0 원문 대조 · Runpod N1 첫 판 실패 11/17 13:54)
def velocity_mdp():
    """Isaac Lab 의 velocity 과제 mdp 모듈. 2.x: isaaclab_tasks.manager_based.locomotion.velocity.mdp · 3.0: isaaclab_tasks.core.velocity.mdp (v3.0.0 에 manager_based 폴더 없음)."""
    import importlib

    return importlib.import_module("isaaclab_tasks.core.velocity.mdp" if lab_major() >= 3 else "isaaclab_tasks.manager_based.locomotion.velocity.mdp")


def uniform_noise_cfg_cls():
    """덧셈 균등 잡음 cfg. 2.x: isaaclab.utils.noise.AdditiveUniformNoiseCfg · 3.0: UniformNoiseCfg (operation 기본 'add' 라 같은 뜻 · n_min · n_max 같음)."""
    from isaaclab.utils import noise

    return noise.UniformNoiseCfg if lab_major() >= 3 else noise.AdditiveUniformNoiseCfg


def velocity_go2_module(name: str):
    """Isaac Lab 의 Go2 velocity 설정 모듈 (예: 'rough_env_cfg'). 2.x: ...manager_based.locomotion.velocity.config.go2.<name> · 3.0: isaaclab_tasks.core.velocity.config.go2.<name>."""
    import importlib

    base = "isaaclab_tasks.core.velocity.config.go2" if lab_major() >= 3 else "isaaclab_tasks.manager_based.locomotion.velocity.config.go2"
    return importlib.import_module(f"{base}.{name}")


# ---------------------------------------------------------------- 물리 백엔드 (lead 14:08 · 팀장: 3.0 도 PhysX 로 고정)
def apply_physx_sim(sim_cfg, gpu_max_rigid_patch_count: int) -> None:
    """2.x: sim.physx.gpu_max_rigid_patch_count 를 쓴다. 3.0: SimulationCfg 에 physx 칸이 없고 `physics` 가 백엔드 cfg 라서 PhysxCfg (Isaac Sim PhysX · TGS solver_type 1) 를 직접 박는다
    (stock 과제는 physics=RoughPhysicsCfg 프리셋이라 기본이 newton_mjwarp 로 뜬 적이 있다 · R3b 로그). 프리셋 이름 isaacsim_physx 와 같은 cfg 다."""
    if lab_major() >= 3:
        from isaaclab_physx.physics import PhysxCfg

        sim_cfg.physics = PhysxCfg(gpu_max_rigid_patch_count=int(gpu_max_rigid_patch_count), solver_type=1)
    else:
        sim_cfg.physx.gpu_max_rigid_patch_count = int(gpu_max_rigid_patch_count)


def physics_report(raw_env) -> dict:
    """만든 env 가 실제로 쓰는 물리 백엔드: {'manager': 클래스 이름, 'cfg': cfg 클래스 이름, 'solver_type': ..., 'is_physx': bool}. 2.x 는 늘 PhysX."""
    if lab_major() < 3:
        return {"manager": "PhysxInterface(2.x)", "cfg": "PhysxCfg(2.x)", "solver_type": getattr(getattr(raw_env.cfg.sim, "physx", None), "solver_type", None), "is_physx": True}
    ctx = raw_env.sim
    manager = getattr(getattr(ctx, "physics_manager", None), "__name__", type(getattr(ctx, "physics_manager", None)).__name__)
    cfg = getattr(raw_env.cfg.sim, "physics", None)
    return {"manager": manager, "cfg": type(cfg).__name__, "solver_type": getattr(cfg, "solver_type", None),
            "is_physx": "physx" in manager.lower() and "newton" not in manager.lower()}


def require_physx(raw_env) -> dict:
    """PhysX 가 아니면 (newton 등) 예외 -> 시작하지 않는다. 결과 dict 를 돌려준다 (로그에 PHYSICS_BACKEND 로 찍는 용)."""
    rep = physics_report(raw_env)
    if not rep["is_physx"]:
        raise RuntimeError(f"physics backend is not PhysX: {rep}")
    return rep
