"""평가 실행 진입점. 저장소 루트에서 `python -m foothold_s2.eval.run_eval <축> ...` 로 부른다.

  axis1  --set rough6|unseen10 --speed 0.5|1.0|1.5      (한 번에 한 칸 묶음, 옛 하네스와 같은 단위)
  axis2  평지 네 시나리오를 이어 돈다 (stop ramp turn hold)
  axis3  --group continuous|stairs|sparse --cmd vx,vy,wz  (명령 하나에 지형군 하나)
  start  START 시험지 (종류 x 레벨)

Isaac 은 예외 뒤에도 종료 코드 0 을 내므로 끝에서 `manifest.check_run_dir` 로 산출물을 점검한다.
GPU: `--device cuda:0` 을 쓰고 `CUDA_VISIBLE_DEVICES` 로 가리지 않는다 (렌더 장치가 가려지면 창 생성에서 멈춘다).
"""

# 아래 네 줄의 순서를 바꾸지 말 것. Kit 를 띄운 뒤 `rsl_rl.runners` 를 처음 import 하면 프로세스가 죽는다
# (Windows, 옛 하네스 머리글 실측). Kit 를 띄우기 전에 네이티브 확장을 먼저 불러 둔다.
import importlib

for _preload in ("h5py", "torch", "tensordict", "rsl_rl.runners"):
    importlib.import_module(_preload)

import argparse
import json
import os
import sys
import time
import traceback

from isaaclab.app import AppLauncher

from foothold_s2.robots import go2_params as gp
from foothold_s2.eval import cells, manifest, rsj

parser = argparse.ArgumentParser(description="FOOTHOLD 평가 (41 설계).")
parser.add_argument("axis", choices=["axis1", "axis2", "axis3", "start"])
parser.add_argument("--policy", choices=["e1", "nvidia", "v2", "s1blind", "s1scan"], default="e1")
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--label", default=None)
parser.add_argument("--out", required=True)
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--difficulty", type=float, default=0.5)
parser.add_argument("--episodes", type=int, default=100)
parser.add_argument("--gate", action="store_true", help="관문 평가: 칸당 판 수 200 (41 §8 · fable 20s). S0 기록은 100 판 그대로")
parser.add_argument("--envs_per_terrain", type=int, default=10)
parser.add_argument("--terrains", default="all")
parser.add_argument("--wall_limit_s", type=float, default=None)
parser.add_argument("--note", default="")
# 축 1
parser.add_argument("--set", dest="terrain_set", choices=["rough6", "unseen10"], default="rough6")
parser.add_argument("--speed", type=float, default=0.5)
# 축 2
parser.add_argument("--scenario", default="all")
parser.add_argument("--num_envs", type=int, default=64)
# 축 3
parser.add_argument("--group", choices=list(cells.TERRAIN_GROUPS), default="continuous")
parser.add_argument("--cmd", default="0.5,0,0")
parser.add_argument("--direction", default="")
parser.add_argument("--cmd_basis", default="")
# START
parser.add_argument("--kinds", default="all")
parser.add_argument("--levels", default="all")
parser.add_argument("--tile_envs", type=int, default=1)
parser.add_argument("--instances", type=int, default=10)
parser.add_argument("--tile_episodes", type=int, default=50)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()

if args.gate:
    args.episodes = 200      # 관문 칸당 판 수 (stats.GATE_N)

started_at = time.strftime("%Y-%m-%d %H:%M:%S")
os.makedirs(args.out, exist_ok=True)
manifest.write_command_txt(args.out, manifest.argv_for_record(), started_at)

app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

# ---------------------------------------------------------------- Kit 기동 후

from foothold_s2.eval import adapters, axis2_run, runtime, start_sheet, terrain_sets  # noqa: E402


def make_adapter(set_name=None):
    if args.policy == "e1":
        return adapters.E1Adapter()

    if args.policy.startswith("s1"):
        return adapters.S1Adapter(args.policy[2:])

    # axis3 의 병합 생성기는 unseen10 쪽 환경 설정 클래스를 바탕으로 한다 (merged_generator 와 같은 선택).
    return terrain_sets.isaaclab_adapter(args.policy, set_name or "unseen10")


def device_of():
    return getattr(args, "device", None) or "cuda:0"


def build_and_load(adapter, generator, num_envs, duration_s, base_cmd, **extra):
    """env 를 짓고 명령을 고정하고 정책을 올린다. 순서는 옛 하네스와 같다 (지형 -> 명령 -> reset -> 정책)."""
    built = adapter.make_env(generator=generator, num_envs=num_envs, duration_s=duration_s,
                             seed=args.seed, difficulty=args.difficulty, base_cmd=base_cmd,
                             device=device_of(), **extra)
    raw = built["raw"]
    from foothold_s2.tasks.robot_mass import log_robot_mass

    if not getattr(args, "_mass_logged", False):                        # 평가 시작에 로드 뒤 로봇 총질량 한 줄
        log_robot_mass(raw, "eval " + args.policy)
        args._mass_logged = True

    pin = runtime.CommandPin(num_envs, raw.device, base_cmd)
    adapter.pin_command(raw, pin)

    return built, raw, pin


def verify_mapping(raw, names, envs_per_terrain):
    """env 가 어느 지형에 앉았나를 되읽는다 (지형 순서가 어긋나면 이름과 지형이 뒤바뀐다)."""
    types = raw.scene.terrain.terrain_types.detach().cpu().tolist()
    cfg_names = list(raw.cfg.scene.terrain.terrain_generator.sub_terrains.keys())

    if cfg_names != list(names):
        raise RuntimeError("지형 열 순서가 다릅니다: 설정 %r, 기대 %r" % (cfg_names, list(names)))

    for env_id, t in enumerate(types):
        if int(t) != env_id // envs_per_terrain:
            raise RuntimeError("env %d 가 지형 %d 에 앉았습니다 (기대 %d)"
                               % (env_id, t, env_id // envs_per_terrain))

    print("[PASS] env -> 지형 배정 %d 칸 확인" % len(types), flush=True)


def _s1_clip_actions():
    from foothold_s2.tasks.agents.s1_ppo_cfg import S1aPPORunnerCfg

    return S1aPPORunnerCfg().clip_actions      # configclass 의 값은 클래스가 아니라 객체에서 읽힌다 (dry 평가에서 AttributeError 로 확인)


def finish(out_dir, record):
    base = {
        "axis": args.axis,
        "argv": sys.argv,
        "started_at": started_at,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "harness": manifest.harness_record(),
        "gates": manifest.gates_record(),            # 판정 규칙 파일(gates-v1.json)의 경로 · sha256
        "environment": manifest.environment_record(),
        "terrain_sources": terrain_sets.source_record(),
        "label": args.label,
        "note": args.note,
        "fbg_margin_m": gp.TERMINATION["foot_below_ground_m"] if args.policy.startswith("s1") else None,
        "clip_actions": _s1_clip_actions() if args.policy.startswith("s1") else None,   # foot_below_ground 종료 문턱 (S1 계열 env 만)
    }
    base.update(record)
    manifest.write_json(os.path.join(out_dir, "run_manifest.json"), base)


def policy_record(adapter):
    return {
        "policy_kind": adapter.name,
        "checkpoint": args.checkpoint,
        "checkpoint_sha256": manifest.file_sha256(args.checkpoint),
        "adapter_changes": adapter.changes,
        "adapter_checks": adapter.checks,
    }


def run_episode_axis(mode, names, generator, base_cmd, duration_s, reference_m, judge_kwargs,
                     recorded, tag, command_s=None, fixed_start=False):
    adapter = make_adapter(args.terrain_set if args.axis == "axis1" else None)
    n_env = args.envs_per_terrain * len(names)
    built, raw, pin = build_and_load(adapter, generator, n_env, duration_s, [base_cmd] * n_env)
    verify_mapping(raw, names, args.envs_per_terrain)
    if fixed_start:
        terrain_sets.sparse_starts.install_fixed_reset(raw, names, generator.axis3_starts)
        adapter.changes.append("축 3 뒤·옆: 네 발 XY 지지·높이차 3 cm 이하, 선택 yaw, 기본 관절, 발 바닥 최소 1 cm, 발 구 가장자리 여유 5 cm")
    raw.reset()
    env, policy, policy_nn, obs = adapter.load_policy(built, args.checkpoint)

    runner = runtime.EpisodeRunner(
        {"env": env, "raw": raw}, policy, policy_nn, pin, terrain_names=names,
        envs_per_terrain=args.envs_per_terrain, episodes=args.episodes, duration_s=duration_s,
        mode=mode, judge_kwargs=judge_kwargs, reference_m=reference_m, command_s=command_s)

    rows = []
    total = len(recorded) * args.episodes

    def on_episode(row):
        rows.append(row)
        n = len(rows)

        if n % 25 == 0 or n == total:
            print("[%s] %d/%d  last=%s J=%s S=%s" % (tag, n, total, row["terrain"],
                                                      row.get("J_body"), row.get("S")), flush=True)

    stats = runner.run(recorded, on_episode, wall_limit_s=args.wall_limit_s, obs=obs)
    env.close()

    return rows, stats, adapter, raw.step_dt


def do_axis1():
    names = list(cells.AXIS1_SETS[args.terrain_set])
    duration = cells.AXIS1_SPEEDS[args.speed]
    p = cells.AXIS1_PARAMS
    generator, _cls = terrain_sets.v2_generator(args.terrain_set)
    recorded = names if args.terrains == "all" else [t for t in args.terrains.split(",") if t]
    judge_kwargs = dict(min_progress_m=p["min_progress_m"],
                        max_lateral_drift_m=p["max_lateral_drift_m"],
                        max_velocity_mae_mps=p["max_velocity_mae_mps"])
    rows, stats, adapter, dt = run_episode_axis(
        "axis1", names, generator, (args.speed, 0.0, 0.0), duration, None, judge_kwargs,
        recorded, "axis1 %s v%.1f" % (args.terrain_set, args.speed))

    for row in rows:
        row["set"] = args.terrain_set
        row["speed"] = args.speed

    save_episode_outputs("axis1", rows, recorded, rsj.summarize_axis1_cell, adapter,
                         {"terrain_set": args.terrain_set, "speed": args.speed,
                          "duration_s": duration, "step_dt_s": dt, "params": p, "stats": stats},
                         {"set": args.terrain_set, "speed": args.speed})


def do_axis3():
    cmd = tuple(float(x) for x in args.cmd.split(","))
    # START 네 별칭은 merged_generator에서 8x8 학습 칸으로 연결한다. 8x4 시험지와 별개다.
    names = list(cells.TERRAIN_GROUPS[args.group])
    recorded = names if args.terrains == "all" else [t for t in args.terrains.split(",") if t]
    rule = cells.axis3_rule(args.group, args.direction, cmd)
    duration, reference_m = rule["duration_s"], rule["reference_m"]
    starts = None
    excluded = []
    root_height_m = adapters.sparse_start_root_height(make_adapter()) if rule['rule'] == 'sparse_short' else .4
    generator = terrain_sets.merged_generator(
        names, args.difficulty, args.seed, start_cmd=cmd if rule["rule"] == "sparse_short" else None,
        root_height_m=root_height_m)
    if rule["rule"] == "sparse_short":
        starts = generator.axis3_starts
        excluded = [n for n in recorded if starts[n]["status"] != "ready"]
        names = list(generator.sub_terrains)
        recorded = [n for n in recorded if n not in excluded]
        manifest.write_json(os.path.join(args.out, "axis3_starts.json"), starts)
    judge_kwargs = dict(yaw_deviation_deg=cells.AXIS3_PARAMS["yaw_deviation_deg"])
    if recorded:
        rows, stats, adapter, dt = run_episode_axis(
            "command", names, generator, cmd, duration, reference_m, judge_kwargs,
            recorded, "axis3 %s %s" % (args.group, args.cmd), command_s=rule["command_s"],
            fixed_start=starts is not None)
    else:
        rows, stats, adapter, dt = [], {"episodes": 0}, None, None

    for row in rows:
        row["group"] = args.group
        row["direction"] = args.direction
        row["cmd"] = args.cmd
        row["cmd_basis"] = args.cmd_basis

    save_episode_outputs("axis3", rows, recorded, rsj.summarize_axis3_cell, adapter,
                         {"group": args.group, "cmd": list(cmd), "duration_s": duration,
                          "reference_m": reference_m, "command_s": rule["command_s"],
                          "axis3_rule": rule["rule"], "step_dt_s": dt,
                          "params": cells.AXIS3_PARAMS, "stats": stats,
                          "start_plan": starts, "excluded_start_terrains": excluded,
                          "episodes_per_terrain": args.episodes},
                         {"group": args.group, "direction": args.direction, "cmd": args.cmd,
                          "cmd_basis": args.cmd_basis, "axis3_rule": rule["rule"],
                          "reset_condition": "N1e default joints, selected yaw, no jitter, height spread <= 0.03, min sole gap 0.01, min foot edge clearance 0.05" if starts is not None
                          else "existing reset"})


def save_episode_outputs(prefix, rows, recorded, summarizer, adapter, extra, summary_extra):
    raw_path = manifest.write_csv(os.path.join(args.out, prefix + "_raw.csv"), rows,
                                  fieldnames=None if rows else ["terrain"])
    summary_rows = []

    for terrain in recorded:
        picked = [r for r in rows if r["terrain"] == terrain]
        summary = summarizer(picked)
        summary = dict(terrain=terrain, **summary_extra, **summary)
        summary_rows.append(summary)

    # 판이 없는 지형을 실패 0점으로 꾸미지 않는다. 별도 상태 행과 manifest에 남긴다.
    for terrain in extra.get("excluded_start_terrains", []):
        summary_rows.append(dict(terrain=terrain, **summary_extra, status="no_start",
                                 label="시작점 없음 · 판정 제외", eligible=False))
    fields = list(dict.fromkeys(key for row in summary_rows for key in row))
    summary_rows = [{key: row.get(key) for key in fields} for row in summary_rows]
    manifest.write_csv(os.path.join(args.out, prefix + "_summary.csv"), summary_rows,
                       fieldnames=fields or ["terrain"])
    record = policy_record(adapter) if adapter is not None else {"policy_loaded": False}
    record.update(extra)
    record["episodes_recorded"] = len(rows)
    finish(args.out, record)
    print("[DONE] %s: 원자료 %s, 줄 수 %d" % (prefix, raw_path, len(rows)), flush=True)


def do_axis2():
    result = axis2_run.run(args, make_adapter(), runtime, device_of())
    manifest.write_csv(os.path.join(args.out, "axis2_cells.csv"), result["cells"])
    finish(args.out, dict(result["record"]))
    print("[DONE] axis2 아홉 칸: " + json.dumps(
        {r["cell"]: [r["value"], r["passed"]] for r in result["cells"]}), flush=True)


def do_start():
    """START 시험지: 종류(열) x 레벨(행) 칸마다 env 를 못 박고 전진 0.5 m/s 로 6.5 m(스폰에서 도착 단까지)를 건너게 한다.

    도달(R_body) 뒤에는 명령 0 으로 시간 T(= 2 x 기준 거리 / 속도 = 26 s)까지 서 있게 해 생존(S)을 잰다.
    MEV(가장자리 디딤 비율)는 발 디딤 위치를 안 쌓으므로 이 실행에서는 재지 않는다(미측정).
    """
    kinds = list(start_sheet.KINDS) if args.kinds == "all" else [k for k in args.kinds.split(",") if k]
    levels = list(range(start_sheet.LEVELS)) if args.levels == "all" else [int(v) for v in args.levels.split(",")]
    speed = 0.5
    duration = 2.0 * start_sheet.REFERENCE_M / speed
    k = args.tile_envs
    inst = args.instances
    tiles = [(lv, ki * inst + i) for lv in levels for ki in range(len(kinds)) for i in range(inst)]
    n_env = len(tiles) * k
    generator = terrain_sets.start_generator(kinds=tuple(kinds), seed=args.seed, instances=inst)

    adapter = make_adapter(None)
    built = adapter.make_env(generator=generator, num_envs=n_env, duration_s=duration, seed=args.seed,
                             difficulty=None, base_cmd=[(speed, 0.0, 0.0)] * n_env, device=device_of())
    raw = built["raw"]
    env_levels = [lv for (lv, _c) in tiles for _ in range(k)]
    env_types = [c for (_lv, c) in tiles for _ in range(k)]
    terrain_sets.assign_tiles(raw, env_levels, env_types)

    got_t = raw.scene.terrain.terrain_types.detach().cpu().tolist()
    got_l = raw.scene.terrain.terrain_levels.detach().cpu().tolist()

    if got_t != env_types or got_l != env_levels:
        raise RuntimeError("START 칸 배정이 안 먹었습니다")

    print("[PASS] START 칸 배정 %d env = %d 칸 x %d" % (n_env, len(tiles), k), flush=True)
    pin = runtime.CommandPin(n_env, raw.device, [(speed, 0.0, 0.0)] * n_env)
    adapter.pin_command(raw, pin)
    raw.reset()
    env, policy, policy_nn, obs = adapter.load_policy(built, args.checkpoint)

    import torch

    base, extra = divmod(args.tile_episodes, k)
    targets = torch.tensor([base + (1 if (i % k) < extra else 0) for i in range(n_env)], dtype=torch.long)
    tags = [{"kind": kinds[env_types[i] // inst], "level": env_levels[i], "instance": env_types[i] % inst}
            for i in range(n_env)]
    runner = runtime.EpisodeRunner(
        {"env": env, "raw": raw}, policy, policy_nn, pin, terrain_names=[kinds[c // inst] for c in range(len(kinds) * inst)], envs_per_terrain=1,
        episodes=args.tile_episodes, duration_s=duration, mode="command",
        judge_kwargs=dict(yaw_deviation_deg=cells.AXIS3_PARAMS["yaw_deviation_deg"]),
        reference_m=start_sheet.REFERENCE_M)
    rows = []
    total = int(targets.sum().item())

    def on_episode(row):
        row["crossing_ratio"] = start_sheet.crossing_ratio(row["cmd_progress_m"])
        rows.append(row)

        if len(rows) % 100 == 0 or len(rows) == total:
            print("[start] %d/%d" % (len(rows), total), flush=True)

    stats = runner.run(sorted(set(runner.terrain_names)), on_episode, wall_limit_s=args.wall_limit_s, obs=obs,
                       targets=targets, env_tags=tags)
    env.close()

    manifest.write_csv(os.path.join(args.out, "start_raw.csv"), rows)
    summary = []

    for kind in kinds:
        for level in levels + ["ALL"]:
            picked = [r for r in rows if r["kind"] == kind and (level == "ALL" or r["level"] == level)]
            cell = rsj.summarize_axis3_cell(picked)
            cell["mean_crossing_ratio"] = (sum(r["crossing_ratio"] for r in picked) / len(picked)) if picked else None
            summary.append(dict(kind=kind, level=level, **cell))

    manifest.write_csv(os.path.join(args.out, "start_summary.csv"), summary)
    record = policy_record(adapter)
    record.update({"kinds": kinds, "levels": levels, "tile_envs": k, "tile_episodes": args.tile_episodes,
                   "instances_per_kind_level": inst,
                   "episodes_recorded": len(rows), "duration_s": duration, "speed": speed,
                   "reference_m": start_sheet.REFERENCE_M, "stats": stats,
                   "mev": "미측정 (발 디딤 위치를 쌓지 않음)",
                   "sheet": {"size": list(start_sheet.SIZE), "spawn": list(start_sheet.SPAWN_XY),
                             "zone_x": list(start_sheet.ZONE_X), "goal_x": start_sheet.GOAL_X}})
    finish(args.out, record)
    print("[DONE] start: 줄 수 %d" % len(rows), flush=True)


try:
    {"axis1": do_axis1, "axis2": do_axis2, "axis3": do_axis3, "start": do_start}[args.axis]()
except BaseException:
    # Isaac 은 예외 뒤에도 종료 코드 0 을 내는 일이 있다. 로그에 Traceback 을 남기고 1 로 끝낸다.
    traceback.print_exc()
    sys.stdout.flush()
    sys.stderr.flush()
    manifest.append_exit(args.out, 1)
    os._exit(1)

manifest.append_exit(args.out, 0)
simulation_app.close()
