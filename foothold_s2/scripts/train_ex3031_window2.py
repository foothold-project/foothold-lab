"""EX-30 · EX-31 창 2 장기 판 진입점 (SONNET-X25 후속). 자동 기동 판정(window2_gate.py)이 통과시킨 뒤에만 띄운다.

    python -m foothold_s2.scripts.train_ex3031_window2 --exp EX-30 --child_ckpt <창 1 폴더>/model_1750.pt --headless --device cuda:0

창 1 의 자식 model_1750 에서 정확 재개(restore_child: 같은 spec 의 자식만) -> 저장된 지형 칸 복원 -> 추가 250 갱신 -> 50 마다 저장 -> model_2000.pt 뒤 정상 종료.
cfg 는 B 그대로, 처치(force_gt)는 창 1 과 같다. 에피소드 길이는 시작 때 흩는다(init_at_random_ep_len=True, reviewer 고침 1): 새 env 의 길이 버퍼가 모두 0 이면
전 env 가 같은 때 time-out 해 p_smpl 이 얼어붙는다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from foothold_s2.ex3031_window2_contract import CHILD_SPEC_NAME, EXTRA_UPDATES, FINAL_ITER, PARENT_PATH, RUN_ROOT_NAME, SAVE_INTERVAL, START_ITER, TASK, check_outputs, validate
from foothold_s2.ex3031_smoke_contract import read_child_spec

# tensordict 의 C 확장은 Kit 이 뜬 뒤 처음 불러오면 이 기기에서 access violation 으로 죽는다(10/20 start_gate 실측).
__import__("tensordict")
import torch  # noqa: E402

from isaaclab.app import AppLauncher  # noqa: E402

ISAAC_RSL = os.path.join(os.environ.get("ISAACLAB_PATH", "C:/isaac/IsaacLab"), "scripts", "reinforcement_learning", "rsl_rl")
sys.path.insert(0, ISAAC_RSL)
import cli_args  # noqa: E402  isort: skip

parser = argparse.ArgumentParser(description="EX-30/31 창 2")
parser.add_argument("--exp", required=True)
parser.add_argument("--child_ckpt", required=True)
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
from foothold_s2.runners.stage_transfer import file_sha256, terrain_hash  # noqa: E402
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

    child_dir = os.path.dirname(os.path.abspath(args_cli.child_ckpt))
    spec, parent_iter = read_child_spec(child_dir)
    log_dir = os.path.join(os.path.abspath(os.path.join("logs", "rsl_rl", RUN_ROOT_NAME)), datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + f"_{args_cli.exp.lower()}-w2")
    env_cfg.log_dir = log_dir
    STATE["log_dir"] = log_dir
    write_status(log_dir, {"state": "starting", "task": args_cli.task, "exp": args_cli.exp, "window": 2, "seed": agent_cfg.seed, "extra_updates": EXTRA_UPDATES})

    gym_env = gym.make(args_cli.task, cfg=env_cfg)
    physics_check = record_realized_physics(gym_env, env_cfg, log_dir, args_cli.parent)
    evidence = StepEvidence(gym_env.unwrapped, log_dir)
    env = RslRlVecEnvWrapper(gym_env, clip_actions=agent_cfg.clip_actions)
    train_cfg = agent_cfg.to_dict()
    pc = dict(train_cfg.get("perception", {}) or {})
    pc["force_gt"] = args_cli.exp == "EX-31"                                          # 창 1 과 같은 처치
    if pc.get("map_input") != "reconstruction":
        raise ValueError("map_input 은 reconstruction")
    train_cfg["perception"] = pc
    runner_class = Ex30Runner if args_cli.exp == "EX-30" else Ex31Runner
    runner_class = boundary_stop(runner_class, SAVE_INTERVAL)                          # STOP 은 저장 경계(50 배수)에서만 받는다
    stop_file = os.path.join(log_dir, "STOP")
    runner = runner_class(env, train_cfg, log_dir=log_dir, device=agent_cfg.device, evidence=evidence, stop_file=stop_file)
    runner.add_git_repo_to_log(__file__)

    ckpt_sha = sha256(args_cli.child_ckpt)
    print("EX3031_W2_CHILD_CKPT_SHA256 " + ckpt_sha, flush=True)
    saved = torch.load(args_cli.child_ckpt, weights_only=False, map_location="cpu")
    saved_terrain = terrain_hash(saved["env_state"]["terrain_levels"], saved["env_state"]["terrain_types"])
    runner.set_spec(spec, parent_iter)
    runner.load(args_cli.child_ckpt)                                                  # 같은 spec 의 자식만 받는다(부모 체크포인트 거절)
    if runner.current_learning_iteration != START_ITER:
        raise RuntimeError(f"재개한 회차 {runner.current_learning_iteration} 가 {START_ITER} 가 아니다")
    terrain = runner.env.unwrapped.scene.terrain
    restored_terrain = terrain_hash(terrain.terrain_levels, terrain.terrain_types)
    reset_info = runner.reset_segment_physics()                                       # 복원한 지형 원점에서 물리 리셋(레벨 · 종류 · 원점이 그대로인지 안에서 단언)
    after_reset = terrain_hash(terrain.terrain_levels, terrain.terrain_types)
    if not (saved_terrain == restored_terrain == after_reset):
        raise RuntimeError(f"지형 칸 해시가 저장 {saved_terrain[:12]} · 복원 {restored_terrain[:12]} · 리셋 뒤 {after_reset[:12]} 에서 같지 않다")
    receipt = {"exp": args_cli.exp, "child_ckpt": os.path.abspath(args_cli.child_ckpt), "child_ckpt_sha256": ckpt_sha, "start_iter": runner.current_learning_iteration, "spec_sha256": spec.sha256(),
               "parent_iter": parent_iter, "child_spec_file": os.path.join(child_dir, CHILD_SPEC_NAME), "terrain": {"saved_hash": saved_terrain, "restored_hash": restored_terrain, "after_reset_hash": after_reset,
               "reset_origin_sha256": reset_info["origin_sha256"]}, "stage_transfer_in_ckpt": saved["stage_transfer"], "adasmpl_in_ckpt": saved["adasmpl"]}
    with open(os.path.join(log_dir, "transfer_receipt_w2.json"), "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2, default=str)
    print("EX3031_W2_RECEIPT " + json.dumps({"exp": args_cli.exp, "start_iter": receipt["start_iter"], "terrain": receipt["terrain"], "adasmpl": receipt["adasmpl_in_ckpt"]}, default=str), flush=True)
    dump_yaml(os.path.join(log_dir, "params", "env.yaml"), env_cfg)
    dump_yaml(os.path.join(log_dir, "params", "agent.yaml"), train_cfg)
    pair = check_dumped_cfg_against_parent(log_dir, args_cli.parent, args_cli.exp)
    modes = {"est_mode": runner.pcfg["est_mode"], "critic_mode": runner.pcfg["critic_mode"], "map_input": runner.pcfg.get("map_input"), "force_gt": bool(runner.pcfg.get("force_gt", False)),
             "contract": runner.pcfg["contract"], "fbg_margin_m": gp.TERMINATION["foot_below_ground_m"], "num_envs": env_cfg.scene.num_envs, "num_steps_per_env": agent_cfg.num_steps_per_env,
             "seed": agent_cfg.seed, "task": args_cli.task, "experiment": args_cli.exp, "run_kind": "ex3031_window2", "spec_sha256": spec.sha256(), "terrain_restore": spec.terrain_restore,
             "depth_delay_ticks": int(runner.perception.cfg.depth_delay_ticks), "cfg_pair_diff_count": pair, "physics_actuators_equal_parent": physics_check["actuators_equal"],
             "extra_updates": EXTRA_UPDATES, "start_iter": START_ITER, "final_iter": FINAL_ITER, "save_interval": agent_cfg.save_interval, "init_at_random_ep_len": True}
    manifest = run_manifest.build_manifest(repo=REPO, log_dir=log_dir, run_name=f"{args_cli.exp}-w2", cli_args={**vars(args_cli), "hydra_args": hydra_args}, modes=modes,
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
        write_status(log_dir, {"state": "stopped_saved", "window": 2, "exp": args_cli.exp, **stopped})
        print("EX3031_W2_STOPPED " + json.dumps(stopped), flush=True)
    finally:
        runner.training_trace.close()
    if stopped is not None:
        return
    final = os.path.join(log_dir, f"model_{runner.current_learning_iteration}.pt")
    done = torch.load(final, weights_only=False, map_location="cpu")
    result = {"exp": args_cli.exp, "window": 2, "checkpoint": final, "sha256": sha256(final), "iter": runner.current_learning_iteration, "final_iter_expected": FINAL_ITER,
              "stage_transfer": done["stage_transfer"], "adasmpl": done["adasmpl"], "perception_cfg_force_gt": done["perception_cfg"]["force_gt"], "receipt": receipt["terrain"]}
    with open(os.path.join(log_dir, "window2_result.json"), "w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, default=str)
    missing = check_outputs(log_dir)
    if runner.current_learning_iteration != FINAL_ITER or missing:
        raise RuntimeError(f"창 2 가 끝났는데 iter={runner.current_learning_iteration} (기대 {FINAL_ITER}) · 빠진 산출물 {missing}")
    write_status(log_dir, {"state": "done", "window": 2, "exp": args_cli.exp, "iter": runner.current_learning_iteration, "log_dir": log_dir, "checkpoint": final, "sha256": result["sha256"]})
    print("EX3031_W2_DONE " + json.dumps({k: result[k] for k in ("exp", "iter", "sha256")}), flush=True)


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
