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


_APP = None                                      # Kit 앱 (한 프로세스에 하나). isaaclab 모듈은 앱이 뜬 뒤에만 import 할 수 있다 (11/17 첫 로컬 실행: 앱 없이 isaaclab_tasks import 에서 죽음)


def launch_app(cfg: dict, with_camera: bool):
    """Kit 을 헤드리스로 한 번 띄운다 (n1_kit_check 와 같은 AppLauncher 호출). 이미 떴으면 그대로."""
    global _APP
    if _APP is None:
        from isaaclab.app import AppLauncher

        _APP = AppLauncher(headless=True, device=cfg["device"], enable_cameras=bool(with_camera)).app
    return _APP


def finish(rc: int, seconds: float = 90.0) -> None:
    """Kit 앱이 떠 있으면 닫는다. app.close() 는 프로세스를 바로 끝내 종료 코드가 0 이 되고 (Traceback 은 호출자가 먼저 남겨야 한다), 멈추기도 한다
    (로컬 2.3.2 에서 20 분 넘게 CPU 100 %): 일정 뒤 같은 rc 로 강제 종료하는 감시를 건다. 앱이 안 떴으면 아무것도 안 한다."""
    if _APP is None:
        return
    import sys
    import threading

    def _kill():
        sys.stdout.flush(); sys.stderr.flush()
        os._exit(rc)
    t = threading.Timer(seconds, _kill)
    t.daemon = True
    t.start()
    _APP.close()
    t.cancel()


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


def make_task(assets, num_envs: int, seed: int, rows, env_origins_xy, table_starts=None, per_start: int = 32):
    """table_starts = 방마다 시작점 (K, 2) 목록이면 시작 · 목표 · 경로 표를 미리 만든다 (학습 중 새 과제는 표에서 뽑기만). None 이면 옛 꼴 (뽑을 때마다 길을 냄)."""
    from foothold_s2.nav import nav_task

    task = nav_task.NavTask(assets, num_envs, np.random.default_rng(seed))
    task.set_rooms_from_rows(rows, env_origins_xy)
    if table_starts is not None:
        import time

        t0 = time.time()
        sha = task.build_table(table_starts, per_start=per_start, seed=seed, log=lambda m: print(m, flush=True))
        print(f"TASK_TABLE sha256 {sha} secs {time.time() - t0:.0f} per_start {per_start}", flush=True)
    return task


def _build(cfg: dict, with_camera: bool):
    from foothold_s2.lab_compat import th
    from foothold_s2.nav import hl_student
    from foothold_s2.tasks.nav_env_cfg import build_nav_env

    from foothold_s2.lab_compat import require_declared_major

    launch_app(cfg, with_camera)                  # isaaclab 을 import 하는 build_nav_env 보다 먼저
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
    from foothold_s2.nav import room_generator as rg

    starts = None if not int(cfg.get("task_table_per_start", 32)) else [rg.start_points(a.room, int(cfg["n_starts"]), seed=int(cfg["room_seed"]) + row)[:, :2] for row, a in enumerate(prepared["assets"])]
    task = make_task(prepared["assets"], int(cfg["num_envs"]), int(cfg["seed"]), rows, raw.scene.env_origins[:, :2].cpu().numpy(), starts, int(cfg.get("task_table_per_start", 32)))
    task.redraw_on_fall = bool(cfg.get("task_redraw_on_fall", True))            # False = 넘어져도 같은 과제 재도전 (PGCL 수준 올리기 옛 뜻 · 시작 자리만 표에서)
    print(f"TASK_RESET_ON_FALL {'new_task_from_table' if task.redraw_on_fall else 'same_task_retry'} table_tol_m {task.table_tol_m}", flush=True)
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
