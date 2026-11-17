"""N3 · N4 실행기가 부르는 `--env-factory` (설계 §3). 설정은 json 한 파일 (환경 변수 `HIPAN_FACTORY_CONFIG`) 에서 읽는다:
{"lower_checkpoint", "lower_sha256", "num_envs", "device", "seed", "room_count", "room_seed", "n_starts", "room_dir", "grade_table", "prep_path"(선택)}.
CPU 로 시험하는 부분 (`prepare_rooms`: 방 만들기 · 한 메시 쓰기 · 방 자산 · NavTask 틀) 과 Kit 에서만 도는 부분 (`_build`) 을 나눴다.
Kit 부분은 아직 Kit 에서 돌려 본 적 없다 (미확인): terrain_levels 가 방 줄이라는 가정 · env_origins 열 · 카메라 데이터 이름은 첫 Kit 실행에서 맞춘다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

CONFIG_ENV = "HIPAN_FACTORY_CONFIG"
REQUIRED = ("lower_checkpoint", "lower_sha256", "num_envs", "device", "seed", "room_count", "room_seed", "n_starts", "room_dir", "grade_table")


def load_config(path=None) -> dict:
    path = path or os.environ.get(CONFIG_ENV)
    if not path:
        raise RuntimeError(f"set {CONFIG_ENV} to a json config file")
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in cfg]
    if missing:
        raise ValueError(f"factory config lacks {missing}")
    if cfg["room_count"] < 1 or cfg["num_envs"] < 1 or cfg["n_starts"] < 1:
        raise ValueError("room_count, num_envs and n_starts must be >= 1")
    return cfg


def prepare_rooms(cfg: dict) -> dict:
    """방 `room_count` 개를 만들어 한 메시로 쓰고 (방 번호 = 줄) 방 자산 목록을 돌려준다. 이미 쓴 폴더는 거절 (덮어쓰지 않음)."""
    from foothold_s2.nav import grade_map as gm, nav_task, room_generator as rg

    out = Path(cfg["room_dir"])
    if (out / "terrain_mesh.npz").exists():
        raise FileExistsError(f"{out}/terrain_mesh.npz exists (never overwritten)")
    table = gm.load_grade_table(cfg["grade_table"])
    rooms = [rg.make_room(int(cfg["room_seed"]) + i)[1] for i in range(int(cfg["room_count"]))]
    manifest = rg.write_rooms(rooms, out, n_starts=int(cfg["n_starts"]), start_seed=int(cfg["room_seed"]))
    return {"manifest": manifest, "mesh": out / "terrain_mesh.npz", "assets": [nav_task.make_asset(r, table) for r in rooms]}


def make_task(assets, num_envs: int, seed: int, rows, env_origins_xy):
    from foothold_s2.nav import nav_task

    task = nav_task.NavTask(assets, num_envs, np.random.default_rng(seed))
    task.set_rooms_from_rows(rows, env_origins_xy)
    return task


def _build(cfg: dict, with_camera: bool):
    from foothold_s2.lab_compat import th
    from foothold_s2.nav import hl_student
    from foothold_s2.tasks.nav_env_cfg import build_nav_env

    from foothold_s2.lab_compat import require_declared_major

    require_declared_major()
    prepared = prepare_rooms(cfg)
    extra = None
    if with_camera:
        def extra(env_cfg):
            env_cfg.scene.depth_camera = hl_student.depth_camera_cfg()
    nav, _summary = build_nav_env(checkpoint=cfg["lower_checkpoint"], expected_sha256=cfg["lower_sha256"], room_mesh_npz=prepared["mesh"],
                                  room_mesh_sha256=prepared["manifest"]["mesh_sha256"], num_envs=int(cfg["num_envs"]), device=cfg["device"],
                                  seed=int(cfg["seed"]), prep_path=cfg.get("prep_path"), extra_scene=extra)
    raw = nav.raw
    rows = raw.scene.terrain.terrain_levels.cpu().numpy()
    task = make_task(prepared["assets"], int(cfg["num_envs"]), int(cfg["seed"]), rows, raw.scene.env_origins[:, :2].cpu().numpy())
    depth_fn = (lambda: th(raw.scene["depth_camera"].data.output["distance_to_image_plane"])) if with_camera else None
    return nav, task, depth_fn


def teacher_env():
    """`train_nav_teacher --env-factory foothold_s2.nav.kit_factories:teacher_env` -> (NavEnv, NavTask)."""
    nav, task, _ = _build(load_config(), with_camera=False)
    return nav, task


def student_env():
    """`train_nav_student --env-factory foothold_s2.nav.kit_factories:student_env` -> (TeacherVecEnv, depth_fn)."""
    from foothold_s2.nav import hl_train

    cfg = load_config()
    nav, task, depth_fn = _build(cfg, with_camera=True)
    return hl_train.TeacherVecEnv(nav, task, device=cfg["device"]), depth_fn
