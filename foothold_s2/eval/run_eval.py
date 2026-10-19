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

from foothold_s2.eval import cells, manifest, rsj

parser = argparse.ArgumentParser(description="FOOTHOLD 평가 (41 설계).")
parser.add_argument("axis", choices=["axis1", "axis2", "axis3", "start"])
parser.add_argument("--policy", choices=["e1", "isaaclab"], default="e1")
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--label", default=None)
parser.add_argument("--out", required=True)
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--difficulty", type=float, default=0.5)
parser.add_argument("--episodes", type=int, default=100)
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
# START
parser.add_argument("--kinds", default="all")
parser.add_argument("--levels", default="all")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()

started_at = time.strftime("%Y-%m-%d %H:%M:%S")
os.makedirs(args.out, exist_ok=True)
manifest.write_command_txt(args.out, manifest.argv_for_record(), started_at)

app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

# ---------------------------------------------------------------- Kit 기동 후

from foothold_s2.eval import adapters, axis2_run, runtime, terrain_sets  # noqa: E402


def make_adapter():
    if args.policy == "e1":
        return adapters.E1Adapter()

    raise SystemExit("isaaclab 어댑터는 이 진입점에서 아직 연결하지 않았습니다 (미시험)")


def device_of():
    return getattr(args, "device", None) or "cuda:0"


def build_and_load(adapter, generator, num_envs, duration_s, base_cmd, **extra):
    """env 를 짓고 명령을 고정하고 정책을 올린다. 순서는 옛 하네스와 같다 (지형 -> 명령 -> reset -> 정책)."""
    built = adapter.make_env(generator=generator, num_envs=num_envs, duration_s=duration_s,
                             seed=args.seed, difficulty=args.difficulty, base_cmd=base_cmd,
                             device=device_of(), **extra)
    raw = built["raw"]
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


def finish(out_dir, record):
    base = {
        "axis": args.axis,
        "argv": sys.argv,
        "started_at": started_at,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "harness": manifest.harness_record(),
        "environment": manifest.environment_record(),
        "terrain_sources": terrain_sets.source_record(),
        "label": args.label,
        "note": args.note,
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
                     recorded, tag):
    adapter = make_adapter()
    n_env = args.envs_per_terrain * len(names)
    built, raw, pin = build_and_load(adapter, generator, n_env, duration_s, [base_cmd] * n_env)
    verify_mapping(raw, names, args.envs_per_terrain)
    raw.reset()
    env, policy, policy_nn, obs = adapter.load_policy(built, args.checkpoint)

    runner = runtime.EpisodeRunner(
        {"env": env, "raw": raw}, policy, policy_nn, pin, terrain_names=names,
        envs_per_terrain=args.envs_per_terrain, episodes=args.episodes, duration_s=duration_s,
        mode=mode, judge_kwargs=judge_kwargs, reference_m=reference_m)

    rows = []
    total = len(recorded) * args.episodes

    def on_episode(row):
        rows.append(row)
        n = len(rows)

        if n % 25 == 0 or n == total:
            print("[%s] %d/%d  last=%s J=%s S=%s" % (tag, n, total, row["terrain"],
                                                      row.get("J"), row.get("S")), flush=True)

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
    # START 시험지 넷은 8 x 4 m 칸이라 옆 · 뒤 명령의 3 m 기준 거리가 칸을 벗어난다. 이 진입점은
    # 아직 이어 붙이지 않았으므로 축 3 지형군에서 뺀다 (보고서에 「미측정」 으로 적는다).
    names = [n for n in cells.TERRAIN_GROUPS[args.group] if n not in cells.START_SHEETS]
    recorded = names if args.terrains == "all" else [t for t in args.terrains.split(",") if t]
    duration = cells.axis3_duration_s(cmd)
    generator = terrain_sets.merged_generator(names, args.difficulty, args.seed)
    judge_kwargs = dict(yaw_deviation_deg=cells.AXIS3_PARAMS["yaw_deviation_deg"])
    rows, stats, adapter, dt = run_episode_axis(
        "command", names, generator, cmd, duration, cells.REFERENCE_DISTANCE_M, judge_kwargs,
        recorded, "axis3 %s %s" % (args.group, args.cmd))

    for row in rows:
        row["group"] = args.group
        row["cmd"] = args.cmd

    save_episode_outputs("axis3", rows, recorded, rsj.summarize_axis3_cell, adapter,
                         {"group": args.group, "cmd": list(cmd), "duration_s": duration,
                          "reference_m": cells.REFERENCE_DISTANCE_M, "step_dt_s": dt,
                          "params": cells.AXIS3_PARAMS, "stats": stats},
                         {"group": args.group, "cmd": args.cmd})


def save_episode_outputs(prefix, rows, recorded, summarizer, adapter, extra, summary_extra):
    raw_path = manifest.write_csv(os.path.join(args.out, prefix + "_raw.csv"), rows)
    summary_rows = []

    for terrain in recorded:
        picked = [r for r in rows if r["terrain"] == terrain]
        summary = summarizer(picked)
        summary = dict(terrain=terrain, **summary_extra, **summary)
        summary_rows.append(summary)

    manifest.write_csv(os.path.join(args.out, prefix + "_summary.csv"), summary_rows)
    record = policy_record(adapter)
    record.update(extra)
    record["episodes_recorded"] = len(rows)
    finish(args.out, record)
    print("[DONE] %s: 원자료 %s, 줄 수 %d" % (prefix, raw_path, len(rows)), flush=True)


def do_axis2():
    result = axis2_run.run(args, adapters, runtime, device_of(), simulation_app)
    manifest.write_csv(os.path.join(args.out, "axis2_cells.csv"), result["cells"])
    finish(args.out, dict(result["record"]))
    print("[DONE] axis2 아홉 칸: " + json.dumps(
        {r["cell"]: [r["value"], r["passed"]] for r in result["cells"]}), flush=True)


def do_start():
    raise SystemExit("START 시험지 실행은 아직 연결하지 않았습니다 (생성기 L0 만 있음)")


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
