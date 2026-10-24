"""EX-30 · EX-31 창 1 장기 판 진입점 (SONNET-X25 후속, 팀장 승인 전에는 띄우지 않는다).

    python -m foothold_s2.scripts.train_ex3031_window1 --exp EX-30 --headless --device cuda:0     (EX-31 은 cuda:1)

B1500(부모)에서 전환 -> 부모 지형 칸(terrain_levels/types)만 복원 -> 추가 250 갱신 -> save_interval 50 마다 저장 -> model_1750.pt 저장 뒤 정상 종료.
자식 cfg 는 B cfg 그대로, 처치(force_gt)만 다르다. 갱신 수 · cfg 는 인자로 바꿀 수 없다(ex3031_window1_contract.validate).
GPU1(화면 GPU)에서 도는 EX-31 도 학습만 하고 촬영하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from foothold_s2.ex3031_window1_contract import EXTRA_UPDATES, FINAL_ITER, PARENT_PATH, RUN_ROOT_NAME, SAVE_INTERVAL, TASK, check_outputs, make_spec, validate, write_child_spec

# tensordict 의 C 확장은 Kit 이 뜬 뒤 처음 불러오면 이 기기에서 access violation 으로 죽는다(10/20 start_gate 실측).
__import__("tensordict")
import torch  # noqa: E402

from isaaclab.app import AppLauncher  # noqa: E402

ISAAC_RSL = os.path.join(os.environ.get("ISAACLAB_PATH", "C:/isaac/IsaacLab"), "scripts", "reinforcement_learning", "rsl_rl")
sys.path.insert(0, ISAAC_RSL)
import cli_args  # noqa: E402  isort: skip

parser = argparse.ArgumentParser(description="EX-30/31 창 1")
parser.add_argument("--exp", required=True)
parser.add_argument("--parent", default=str(PARENT_PATH))
parser.add_argument("--task", default=TASK)
parser.add_argument("--agent", default="rsl_rl_cfg_entry_point")
parser.add_argument("--num_envs", type=int, default=None)
parser.add_argument("--seed", type=int, default=None)
parser.add_argument("--max_iterations", type=int, default=None)
parser.add_argument("--distributed", action="store_true", default=False)
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
validate(args_cli, hydra_args)
sys.argv = [sys.argv[0]] + hydra_args
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import traceback  # noqa: E402

import gymnasium as gym  # noqa: E402
from isaaclab.utils.io import dump_yaml  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

__import__("isaaclab_tasks")
from isaaclab_tasks.utils.hydra import hydra_task_config  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
for registry in ("foothold_s2.tasks", "foothold_s2.x15_tasks", "foothold_s2.x16_tasks", "foothold_s2.x16n_tasks", "foothold_s2.x17_tasks", "foothold_s2.x18_tasks",
                 "foothold_s2.x19_tasks", "foothold_s2.x20_tasks", "foothold_s2.x21_tasks", "foothold_s2.x22_tasks", "foothold_s2.x23_tasks", "foothold_s2.x23f_tasks"):
    __import__(registry)
from foothold_s2.ex3031_common import check_dumped_cfg_against_parent, record_realized_physics  # noqa: E402
from foothold_s2.robots import go2_params as gp  # noqa: E402
from foothold_s2.runners import manifest as run_manifest  # noqa: E402
from foothold_s2.runners.boundary_stop import boundary_stop  # noqa: E402
from foothold_s2.runners.course_runner import Ex30Runner, Ex31Runner  # noqa: E402
from foothold_s2.runners.devices import resolve_devices  # noqa: E402
from foothold_s2.runners.sol23f_runner import DeadlineReached, StepEvidence, sha256  # noqa: E402
from foothold_s2.runners.stage_transfer import file_sha256  # noqa: E402
from foothold_s2.runners.status import write_status  # noqa: E402

STATE = {"log_dir": None}


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg, agent_cfg):
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.scene.num_envs = 3072
    agent_cfg.seed = 42
    agent_cfg.max_iterations = EXTRA_UPDATES
    if agent_cfg.num_steps_per_env != 24 or agent_cfg.resume or agent_cfg.save_interval != SAVE_INTERVAL:
        raise ValueError("B rollout 24, resume 끔, save_interval 50 이어야 한다")
    env_cfg.seed = agent_cfg.seed
    resolve_devices(args_cli.device, env_cfg, agent_cfg, distributed=False, local_rank=0)

    log_dir = os.path.join(os.path.abspath(os.path.join("logs", "rsl_rl", RUN_ROOT_NAME)), datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + f"_{args_cli.exp.lower()}-w1")
    spec = make_spec(args_cli.exp, file_sha256(args_cli.parent))
    env_cfg.log_dir = log_dir
    STATE["log_dir"] = log_dir
    write_status(log_dir, {"state": "starting", "task": args_cli.task, "exp": args_cli.exp, "window": 1, "seed": agent_cfg.seed, "extra_updates": EXTRA_UPDATES})

    gym_env = gym.make(args_cli.task, cfg=env_cfg)
    physics_check = record_realized_physics(gym_env, env_cfg, log_dir, args_cli.parent)
    evidence = StepEvidence(gym_env.unwrapped, log_dir)
    env = RslRlVecEnvWrapper(gym_env, clip_actions=agent_cfg.clip_actions)
    train_cfg = agent_cfg.to_dict()
    pc = dict(train_cfg.get("perception", {}) or {})
    pc["force_gt"] = args_cli.exp == "EX-31"                                          # B cfg 그대로, 처치(force_gt)만 다름
    if pc.get("map_input") != "reconstruction":
        raise ValueError("map_input 은 reconstruction")
    train_cfg["perception"] = pc
    runner_class = Ex30Runner if args_cli.exp == "EX-30" else Ex31Runner
    runner_class = boundary_stop(runner_class, SAVE_INTERVAL)                          # STOP 은 저장 경계(50 배수)에서만 받는다
    stop_file = os.path.join(log_dir, "STOP")                                         # 이 파일을 만들면 다음 50 배수 회차 경계에서 저장하고 멈춘다
    runner = runner_class(env, train_cfg, log_dir=log_dir, device=agent_cfg.device, evidence=evidence, stop_file=stop_file)
    runner.add_git_repo_to_log(__file__)
    receipt = runner.begin_from_parent(args_cli.parent, spec)                         # 부모 상태 + 부모 지형 칸(레벨 · 종류)만 복원
    reset_info = runner.reset_segment_physics()                                       # 복원한 지형 원점에서 물리 리셋(레벨 · 종류 · 원점이 그대로인지 안에서 단언)
    write_child_spec(log_dir, spec, runner.current_learning_iteration)
    terrain = receipt["terrain_restore"]
    from foothold_s2.runners.stage_transfer import terrain_hash

    after_reset = terrain_hash(gym_env.unwrapped.scene.terrain.terrain_levels, gym_env.unwrapped.scene.terrain.terrain_types)
    if after_reset != terrain["parent_hash"]:
        raise RuntimeError("물리 리셋 뒤 지형 칸 해시가 부모와 다르다")
    terrain["after_reset_hash"] = after_reset
    terrain["reset_origin_sha256"] = reset_info["origin_sha256"]
    with open(os.path.join(log_dir, "transfer_receipt.json"), "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    print("EX3031_W1_RECEIPT " + json.dumps({"exp": args_cli.exp, "parent_iter": receipt["parent_iter"], "terrain_parent_hash": terrain["parent_hash"], "terrain_restored_hash": terrain["restored_hash"],
                                              "terrain_after_reset_hash": after_reset, "histogram": terrain["parent_histogram"], "action_std": receipt["action_std"], "child_adasmpl": receipt["child_adasmpl"]}), flush=True)
    dump_yaml(os.path.join(log_dir, "params", "env.yaml"), env_cfg)
    dump_yaml(os.path.join(log_dir, "params", "agent.yaml"), train_cfg)
    pair = check_dumped_cfg_against_parent(log_dir, args_cli.parent, args_cli.exp)
    modes = {"est_mode": runner.pcfg["est_mode"], "critic_mode": runner.pcfg["critic_mode"], "map_input": runner.pcfg.get("map_input"), "force_gt": bool(runner.pcfg.get("force_gt", False)),
             "contract": runner.pcfg["contract"], "fbg_margin_m": gp.TERMINATION["foot_below_ground_m"], "num_envs": env_cfg.scene.num_envs, "num_steps_per_env": agent_cfg.num_steps_per_env,
             "seed": agent_cfg.seed, "task": args_cli.task, "experiment": args_cli.exp, "run_kind": "ex3031_window1", "spec_sha256": spec.sha256(), "terrain_restore": spec.terrain_restore,
             "depth_delay_ticks": int(runner.perception.cfg.depth_delay_ticks), "cfg_pair_diff_count": pair, "physics_actuators_equal_parent": physics_check["actuators_equal"],
             "extra_updates": EXTRA_UPDATES, "final_iter": FINAL_ITER, "save_interval": agent_cfg.save_interval}
    manifest = run_manifest.build_manifest(repo=REPO, log_dir=log_dir, run_name=f"{args_cli.exp}-w1", cli_args={**vars(args_cli), "hydra_args": hydra_args}, modes=modes,
                                           runner=runner, env_yaml=os.path.join(log_dir, "params", "env.yaml"), agent_yaml=os.path.join(log_dir, "params", "agent.yaml"))
    run_manifest.write_manifest(log_dir, manifest)
    runner.attach_manifest(log_dir, manifest)
    if runner.pcfg.get("log_map_stats"):
        from foothold_s2.runners.map_stats import MapStatsRecorder

        MapStatsRecorder(runner, log_dir).attach()
    from foothold_s2.eval.training_trace_bridge import TrainingTraceBridge

    runner.training_trace = TrainingTraceBridge(runner)
    stopped = None
    try:
        runner.learn(num_learning_iterations=EXTRA_UPDATES, init_at_random_ep_len=True)
    except DeadlineReached as stop:                                                   # STOP 파일: 경계에서 저장하고 멈춘 것(정상 종료로 취급하되 완료는 아님)
        stopped = json.loads(str(stop))
        write_status(log_dir, {"state": "stopped_saved", "window": 1, "exp": args_cli.exp, **stopped})
        print("EX3031_W1_STOPPED " + json.dumps(stopped), flush=True)
    finally:
        runner.training_trace.close()
    if stopped is not None:
        return
    final = os.path.join(log_dir, f"model_{runner.current_learning_iteration}.pt")
    saved = torch.load(final, weights_only=False, map_location="cpu")
    result = {"exp": args_cli.exp, "window": 1, "checkpoint": final, "sha256": sha256(final), "iter": runner.current_learning_iteration, "final_iter_expected": FINAL_ITER,
              "stage_transfer": saved["stage_transfer"], "adasmpl": saved["adasmpl"], "perception_cfg_force_gt": saved["perception_cfg"]["force_gt"], "terrain_restore": terrain}
    with open(os.path.join(log_dir, "window1_result.json"), "w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    missing = check_outputs(log_dir)
    if runner.current_learning_iteration != FINAL_ITER or missing:
        raise RuntimeError(f"창 1 이 끝났는데 iter={runner.current_learning_iteration} (기대 {FINAL_ITER}) · 빠진 산출물 {missing}")
    write_status(log_dir, {"state": "done", "window": 1, "exp": args_cli.exp, "iter": runner.current_learning_iteration, "log_dir": log_dir, "checkpoint": final, "sha256": result["sha256"]})
    print("EX3031_W1_DONE " + json.dumps({k: result[k] for k in ("exp", "iter", "sha256")}), flush=True)


if __name__ == "__main__":
    # 실행 규칙(10/20 실측): 상태 파일을 쓴 뒤 env.close() · app.close() 를 부르지 않고 os._exit. 예외면 traceback 을 상태 파일에 쓰고 코드 1.
    torch.backends.cudnn.deterministic = False
    code = 0
    try:
        main()
    except SystemExit as e:
        code = 0 if e.code in (None, 0) else 1
        if code:
            detail = traceback.format_exc()
            write_status(STATE["log_dir"] or os.environ.get("TRAIN_START_STATUS_DIR"), {"state": "failed", "exit_code": e.code, "traceback": detail})
            print(detail, file=sys.stderr, flush=True)
    except BaseException:
        detail = traceback.format_exc()
        write_status(STATE["log_dir"] or os.environ.get("TRAIN_START_STATUS_DIR"), {"state": "failed", "traceback": detail})
        print(detail, file=sys.stderr, flush=True)
        code = 1
    sys.stdout.flush()
    os._exit(code)
