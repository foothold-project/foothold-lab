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


FRESH_PATH_RANGE_M = (5.0, 30.0)         # HiPAN 원문 시험 구간 [5,10] [10,20] [20,30] m 을 덮는 학습 과제 경로 길이 (lead 11/22 01:28 P2)


def fresh_tasks(environ=None) -> bool:
    """P2 스위치 HIPAN_FRESH_TASKS (lead 11/22 01:28 · planner HIPAN-M2000-BENCH-S0-CAUSE-1122 3 절 · 기본 꺼짐 = m2000 학습 조건 그대로):
    켜면 (a) 같은 과제 연속 실패 자르기 끔 (HIPAN_NEW_TASK_AFTER_FAILS 가 있어도 0) (b) 시작점 64 x 목표 32 고정표를 만들지 않고 새 과제마다 목표를 방 지도에서
    새로 뽑음 (충돌 없는 칸 · 최단 경로 FRESH_PATH_RANGE_M · 굴곡 winding_min 1.2 위 몫 winding_frac 0.5 · nav_task._pick_goal 그대로) (c) 나머지 (보상 · 수준 · v_des ·
    시간 상한) 그대로. 시작은 Isaac 의 env 원점 (방마다 n_starts 곳 · 방 영수증 · 이어 받기와 묶여 그대로)."""
    env = os.environ if environ is None else environ
    v = str(env.get("HIPAN_FRESH_TASKS", "")).strip()
    if v not in ("", "0", "1"):
        raise ValueError(f"HIPAN_FRESH_TASKS must be 0 or 1, got {v!r}")
    return v == "1"


def fresh_no_cut(environ=None) -> bool:
    """P2 2차 (lead 11/22 02:04 · planner REVIEW-hipan-p2-1122 4 절 권고 1): HIPAN_FRESH_NO_CUT. 비어 있거나 1 = P2 1차 판 그대로 (켬이면 자르기 끔).
    0 = 켬이어도 HIPAN_NEW_TASK_AFTER_FAILS (또는 factory task_new_after_fails) 자르기를 그대로 둔다 (새 과제가 들어오는 문을 둘로)."""
    env = os.environ if environ is None else environ
    v = str(env.get("HIPAN_FRESH_NO_CUT", "")).strip()
    if v not in ("", "0", "1"):
        raise ValueError(f"HIPAN_FRESH_NO_CUT must be 0 or 1, got {v!r}")
    return v != "0"


def final_successes(environ=None) -> int:
    """P2 2차 (planner 권고 2): HIPAN_FINAL_SUCCESSES = 마지막 수준에서 새 과제를 요청할 연속 성공 수. 비어 있으면 5 (옛 값 · pgcl 기본 · 가정 22 §4 표)."""
    env = os.environ if environ is None else environ
    v = str(env.get("HIPAN_FINAL_SUCCESSES", "")).strip()
    if v == "":
        return 5
    if not v.isdigit() or int(v) < 1:
        raise ValueError(f"HIPAN_FINAL_SUCCESSES must be an integer >= 1, got {v!r}")
    return int(v)


def path_clear_m(environ=None) -> float:
    """P3 스위치 HIPAN_PATH_CLEAR_M (lead 11/22 02:42 · 기본 꺼짐 = 0): 길 계획을 몸 폭 지도 (grade_map.body_clear_grade) 에서. 값 = 벽 · 막힌 칸 중심과의 최소 거리 (m).
    Go2 몸 폭 약 0.31 m (반폭 0.155) + 여유. 0 또는 비어 있으면 끔."""
    env = os.environ if environ is None else environ
    v = str(env.get("HIPAN_PATH_CLEAR_M", "")).strip()
    if v in ("", "0"):
        return 0.0
    try:
        c = float(v)
    except ValueError:
        raise ValueError(f"HIPAN_PATH_CLEAR_M must be a number in (0, 0.6], got {v!r}") from None
    if not 0.0 < c <= 0.6:
        raise ValueError(f"HIPAN_PATH_CLEAR_M must be in (0, 0.6], got {c}")
    return c


def apply_path_clear(task, assets, clear_m: float) -> dict:
    """P3 켜짐: 방마다 몸 폭 지도를 만들어 task.plan_grades 에. 돌려주는 값 = 방마다 막힌 칸이 는 몫 (시작 줄 · 시험용)."""
    from foothold_s2.nav import grade_map as gm

    if not clear_m:
        return {}
    task.plan_grades = [gm.body_clear_grade(a.grade, a.room, clear_m) for a in assets]
    task.plan_clear_m = float(clear_m)
    return {r: round(float(((pg.grade == gm.BLOCKED) & (a.grade.grade != gm.BLOCKED)).mean()), 4) for r, (pg, a) in enumerate(zip(task.plan_grades, assets))}


def new_task_after_fails(cfg: dict, environ=None) -> int:
    """처방 A 스위치 (planner HIPAN-STICKY-TASK-1120 · 논문 밖): factory 설정 task_new_after_fails 또는 환경 변수 HIPAN_NEW_TASK_AFTER_FAILS (Pod 은 --remote-env). 0 (기본) = 끔 = 옛 동작. N >= 1 = 같은 과제 연속 N 번 실패하면 표에서 새 과제."""
    env = os.environ if environ is None else environ
    nf = int(cfg.get("task_new_after_fails", env.get("HIPAN_NEW_TASK_AFTER_FAILS", 0)) or 0)
    if fresh_tasks(env) and fresh_no_cut(env):
        return 0                                    # P2 (a): 실패 자르기 끔 (HIPAN_FRESH_NO_CUT=0 이면 자르기 유지 · P2 2차)
    if nf < 0:
        raise ValueError(f"task_new_after_fails must be >= 0, got {nf}")
    return nf


def task_level_reset_on_new_task(cfg: dict, environ=None) -> bool:
    """수준 되돌림 스위치 (HiPAN 논문의 마지막 수준 K 는 그 과제의 경로 길이라 수준은 과제마다): factory 설정 task_level_reset_on_new_task 또는 환경 변수 HIPAN_LEVEL_RESET_ON_NEW_TASK (Pod 은 --remote-env). 0 (기본) = 끔 = 옛 동작 (수준은 오르기만). 1 = 새 과제를 뽑을 때 그 env 의 수준 1 · 연속 성공 0."""
    env = os.environ if environ is None else environ
    v = cfg.get("task_level_reset_on_new_task", env.get("HIPAN_LEVEL_RESET_ON_NEW_TASK", 0))
    key = str(v).strip().lower()
    if key in ("0", "", "false", "off", "no", "none"):
        return False
    if key in ("1", "true", "on", "yes"):
        return True
    raise ValueError(f"task_level_reset_on_new_task must be 0/1 (or on/off), got {v!r}")


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


def make_task(assets, num_envs: int, seed: int, rows, env_origins_xy, table_starts=None, per_start: int = 32, reach_m: float | None = None):
    """table_starts = 방마다 시작점 (K, 2) 목록이면 시작 · 목표 · 경로 표를 미리 만든다 (학습 중 새 과제는 표에서 뽑기만). None 이면 옛 꼴 (뽑을 때마다 길을 냄)."""
    from foothold_s2.nav import nav_task

    task = nav_task.NavTask(assets, num_envs, np.random.default_rng(seed)) if reach_m is None else nav_task.NavTask(assets, num_envs, np.random.default_rng(seed), reach_m=reach_m)
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

    fresh = fresh_tasks()
    per_start = 0 if fresh else int(cfg.get("task_table_per_start", 32))          # P2 (b): 고정표 없음 → 새 과제마다 방 지도에서
    starts = None if not per_start else [rg.start_points(a.room, int(cfg["n_starts"]), seed=int(cfg["room_seed"]) + row)[:, :2] for row, a in enumerate(prepared["assets"])]
    task = make_task(prepared["assets"], int(cfg["num_envs"]), int(cfg["seed"]), rows, raw.scene.env_origins[:, :2].cpu().numpy(), starts, per_start, reach_m=float(cfg["reach_m"]) if "reach_m" in cfg else None)
    if fresh:
        task.path_range_m, task.strict_winding = FRESH_PATH_RANGE_M, True
    pc = path_clear_m()
    if pc and per_start:
        raise ValueError("HIPAN_PATH_CLEAR_M (P3) needs HIPAN_FRESH_TASKS=1: the start/goal table is built before the body-clearance grade exists")
    if pc:
        shut = apply_path_clear(task, prepared["assets"], pc)
        print(f"HIPAN_PATH_CLEAR_M {pc:g} (P3: 길 계획 몸 폭 지도 · 막힌 칸이 는 몫 방별 {shut})", flush=True)
    fs = final_successes()
    for _p in task.pgcl:
        _p.final_successes = fs
    print(f"PGCL_FINAL_SUCCESSES {fs}" + ("" if fs == 5 else " (P2 2차: 마지막 수준 연속 성공 수 바꿈 · 기본 5)"), flush=True)
    print(f"HIPAN_FRESH_TASKS {'on' if fresh else 'off'} table={'none' if fresh else per_start} path_range_m={list(task.path_range_m)} winding_min={task.winding_min} "
          f"winding_frac={task.winding_frac} strict_winding={task.strict_winding} cut_after_fails={new_task_after_fails(cfg)}", flush=True)
    if task.reach_m <= 0:
        raise ValueError(f"reach_m must be > 0, got {task.reach_m}")
    from foothold_s2.nav import pgcl as _pgcl
    print(f"REACH_M={task.reach_m:g} paper={_pgcl.REACH_M:g}" + ("" if task.reach_m == _pgcl.REACH_M else " OUTSIDE_PAPER (부목표 도달 반경을 논문 값 밖으로 바꿈: PGCL 도달 판정 · r1 arrive 같은 값)"), flush=True)
    shape = str(cfg.get("shaping", "off"))                                # off (기본) | path_potential (논문 밖 덧붙임, 남은 경로 길이가 준 만큼 보상)
    if shape not in ("off", "path_potential"):
        raise ValueError(f"shaping must be off or path_potential, got {shape!r}")
    task.shape_w = float(cfg.get("shaping_w", 5.0)) if shape == "path_potential" else 0.0
    sd = str(cfg.get("shape_decay", "on"))
    if sd not in ("on", "off"):
        raise ValueError(f"shape_decay must be on or off, got {sd!r}")
    task.shape_decay = sd == "on"
    sl = str(cfg.get("shape_levels", "1"))
    if sl not in ("1", "all"):
        raise ValueError(f"shape_levels must be 1 or all, got {sl!r}")
    task.shape_all_levels = sl == "all"
    vr = str(cfg.get("visit_reset", "episode"))
    if vr not in ("episode", "task", "shared"):
        raise ValueError(f"visit_reset must be episode, task or shared, got {vr!r}")
    if vr == "shared":
        task.use_shared_visit()
    else:
        task.visit_reset = vr
    print(f"VISIT_RESET={vr}" + ("" if vr == "episode" else " TASK_SCOPED (논문 밖: 방문 격자 η 를 새 과제를 뽑을 때만 비움)" if vr == "task"
                                  else " SHARED (방마다 격자 하나를 모든 env 가 함께 쌓고 비우지 않음 · [38] 의 통상의 뜻 · 본문 미확인)"), flush=True)
    print(f"SHAPING={shape} w={task.shape_w:g} clip={task.shape_clip} start_frac={task.shape_start_frac} decay_iters={task.shape_decay_iters} decay={sd}" + ("" if sd == "on" else " DECAY_OFF (논문 밖: 배율 1.0 고정)"), flush=True)
    print(f"SHAPE_LEVELS={sl}" + ("" if sl == "1" else " ALL_LEVELS (논문 밖: 수준 2 이상 env 에도 r_shape)"), flush=True)
    task.redraw_on_fall = bool(cfg.get("task_redraw_on_fall", False))           # False (기본) = 같은 과제 유지 (논문) · True = 넘어지면 표에서 새 과제 (02:2x 판)
    print(f"TASK_RESET_ON_FALL {'new_task_from_table' if task.redraw_on_fall else 'same_task_kept'} table_tol_m {task.table_tol_m}", flush=True)
    nf = new_task_after_fails(cfg)
    task.new_task_after_fails = nf
    print("TASK_CUT_AFTER_FAILS " + (f"off (same task kept until {fs} final successes)" if not nf else f"n={nf} (논문 밖: 같은 과제 연속 {nf} 번 실패하면 표에서 새 과제 · 수준 그대로)"), flush=True)
    task.level_reset_on_new_task = task_level_reset_on_new_task(cfg)
    print("TASK_LEVEL_RESET_ON_NEW_TASK " + ("on (새 과제를 뽑을 때 그 env 의 PGCL 수준 1 · 연속 성공 0 · --resume-levels 로 넣은 수준도 첫 과제에서 1 로)" if task.level_reset_on_new_task else "off (수준은 오르기만 · 옛 동작)"), flush=True)
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
