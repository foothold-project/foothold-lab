"""EX-30 · EX-31 짧은 Kit 시험 진입점 (SONNET-X25, 학습 본 실행이 아님).

    fresh : python -m foothold_s2.scripts.train_ex3031_smoke --exp EX-30 --mode fresh --headless --device cuda:0
            B 부모(model_1500)에서 전환 -> 10 갱신 -> model_1510.pt (+ child_spec.json)
    resume: python -m foothold_s2.scripts.train_ex3031_smoke --exp EX-30 --mode resume --child_ckpt <fresh 폴더>/model_1510.pt --headless --device cuda:0
            새 프로세스에서 자식 체크포인트를 받아 2 갱신 -> model_1512.pt (기록: 추가 12 · 총 1513)

자식 cfg 는 B cfg 그대로, 처치(force_gt)만 다르다. task/agent cfg/hydra 는 B 학습과 같은 경로를 쓰고(hydra_task_config), Kit 선적재 순서도 train_sol23f_common 과 같다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from foothold_s2.ex3031_smoke_contract import PARENT_PATH, TASK, UPDATES, make_spec, read_child_spec, resume_log_dir, validate, write_child_spec

# tensordict 의 C 확장은 Kit 이 뜬 뒤 처음 불러오면 이 기기에서 access violation 으로 죽는다(10/20 start_gate 실측).
__import__("tensordict")
import torch  # noqa: E402

from isaaclab.app import AppLauncher  # noqa: E402

ISAAC_RSL = os.path.join(os.environ.get("ISAACLAB_PATH", "C:/isaac/IsaacLab"), "scripts", "reinforcement_learning", "rsl_rl")
sys.path.insert(0, ISAAC_RSL)
import cli_args  # noqa: E402  isort: skip

parser = argparse.ArgumentParser(description="EX-30/31 짧은 Kit 시험")
parser.add_argument("--exp", required=True)
parser.add_argument("--mode", required=True)
parser.add_argument("--parent", default=str(PARENT_PATH))
parser.add_argument("--child_ckpt", default=None)
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
from foothold_s2.robots import go2_params as gp  # noqa: E402
from foothold_s2.runners import manifest as run_manifest  # noqa: E402
from foothold_s2.runners.course_runner import Ex30Runner, Ex31Runner  # noqa: E402
from foothold_s2.runners.devices import resolve_devices  # noqa: E402
from foothold_s2.runners.sol23f_runner import StepEvidence, save_material_array, sha256, tensor_summary  # noqa: E402
from foothold_s2.runners.stage_transfer import file_sha256, yaml_pair_diff  # noqa: E402
from foothold_s2.runners.status import write_status  # noqa: E402

STATE = {"log_dir": None}
AGENT_PAIR_IGNORE = ("log_dir", "device", "run_name", "max_iterations")                                      # 운영 칸. 처치는 perception.force_gt 하나(EX-31 은 부모와 같아 차이 없음)


def record_realized_physics(gym_env, env_cfg, log_dir, parent_ckpt):
    """train_sol23f_common 과 같은 기록(realized_material.json · realized_physics.json)을 남기고 부모 실행의 기록과 대조한다.
    구동기 값과 dynamic<=static 은 결정적이라 어긋나면 멈춘다. 질량 · 무게중심 · 재질 배열은 무작위 추출이라 같은지만 적는다."""
    robot = gym_env.unwrapped.scene["robot"]
    material = save_material_array(robot.root_physx_view.get_material_properties(), log_dir)
    floor = env_cfg.scene.terrain.physics_material
    material["floor_material_cfg"] = {"static_friction": floor.static_friction, "dynamic_friction": floor.dynamic_friction, "restitution": floor.restitution,
                                      "friction_combine_mode": floor.friction_combine_mode, "restitution_combine_mode": floor.restitution_combine_mode}
    material["floor_material_physx_readback"] = "API unverified; cfg recorded only"
    with open(os.path.join(log_dir, "realized_material.json"), "w", encoding="utf-8") as stream:
        json.dump(material, stream, ensure_ascii=False, indent=2)
    if not material["dynamic_le_static_all"]:
        raise RuntimeError("realized material violates dynamic<=static")
    physx = robot.root_physx_view
    physics = {"material": material, "masses": tensor_summary(physx.get_masses()), "com_poses": tensor_summary(physx.get_coms()), "actuators": {},
               "camera_and_delay": "recorded after first reset in step evidence"}
    for name, actuator in robot.actuators.items():
        physics["actuators"][name] = {"stiffness": tensor_summary(actuator.stiffness), "damping": tensor_summary(actuator.damping),
                                      "strength_scale": tensor_summary(actuator.strength_scale) if hasattr(actuator, "strength_scale") else "not_configured"}
    with open(os.path.join(log_dir, "realized_physics.json"), "w", encoding="utf-8") as stream:
        json.dump(physics, stream, ensure_ascii=False, indent=2)
    print("EX3031_REALIZED_PHYSICS " + json.dumps({k: physics[k] for k in ("masses", "com_poses", "actuators")}), flush=True)
    parent_file = os.path.join(os.path.dirname(os.path.abspath(parent_ckpt)), "realized_physics.json")
    check = {"parent_file": parent_file, "actuators_equal": None, "masses_equal": None, "com_equal": None}
    if os.path.isfile(parent_file):
        with open(parent_file, encoding="utf-8") as stream:
            parent = json.load(stream)
        check.update(actuators_equal=parent["actuators"] == json.loads(json.dumps(physics["actuators"])), masses_equal=parent["masses"] == json.loads(json.dumps(physics["masses"])),
                     com_equal=parent["com_poses"] == json.loads(json.dumps(physics["com_poses"])))
    with open(os.path.join(log_dir, "physics_vs_parent.json"), "w", encoding="utf-8") as stream:
        json.dump(check, stream, ensure_ascii=False, indent=2)
    if check["actuators_equal"] is not True:
        raise RuntimeError("구동기 값이 부모 실행 기록과 같다는 것을 확인하지 못했다: %r" % (check,))

    return check


def check_dumped_cfg_against_parent(log_dir, parent_ckpt, exp, env_allowed=()):
    """덤프한 env.yaml · agent.yaml 을 부모 실행의 같은 파일과 잎 단위로 대조해 json 으로 남기고, 처치 칸 밖 차이가 있으면 학습 전에 멈춘다.
    env_allowed: env.yaml 에서 허용할 경로(기본 없음 = 창 1 · 2 와 같은 엄격한 대조). 창 3 처방은 window3_prescription.ENV_ALLOWED 를 넘긴다."""
    pdir = os.path.join(os.path.dirname(os.path.abspath(parent_ckpt)), "params")
    env_diff = yaml_pair_diff(os.path.join(pdir, "env.yaml"), os.path.join(log_dir, "params", "env.yaml"), allowed_paths=tuple(env_allowed))
    agent_diff = yaml_pair_diff(os.path.join(pdir, "agent.yaml"), os.path.join(log_dir, "params", "agent.yaml"), allowed_paths=("perception.force_gt",), ignore_names=AGENT_PAIR_IGNORE)
    with open(os.path.join(log_dir, "cfg_pair_diff.json"), "w", encoding="utf-8") as stream:
        json.dump({"exp": exp, "env_allowed": list(env_allowed), "env_yaml": env_diff, "agent_yaml": agent_diff, "sha256": {"parent_env": file_sha256(os.path.join(pdir, "env.yaml")), "parent_agent": file_sha256(os.path.join(pdir, "agent.yaml")),
                   "child_env": file_sha256(os.path.join(log_dir, "params", "env.yaml")), "child_agent": file_sha256(os.path.join(log_dir, "params", "agent.yaml"))}}, stream, ensure_ascii=False, indent=2, default=str)
    if env_diff or agent_diff:
        raise RuntimeError("부모 params 와 처치 칸 밖의 차이가 있다(cfg_pair_diff.json): env %d칸 · agent %d칸" % (len(env_diff), len(agent_diff)))

    return 0


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg, agent_cfg):
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.scene.num_envs = 3072
    agent_cfg.seed = 42
    agent_cfg.max_iterations = UPDATES[args_cli.mode]
    if agent_cfg.num_steps_per_env != 24 or agent_cfg.resume:
        raise ValueError("B rollout 24, resume 끔이어야 한다")
    env_cfg.seed = agent_cfg.seed
    resolve_devices(args_cli.device, env_cfg, agent_cfg, distributed=False, local_rank=0)

    if args_cli.mode == "fresh":
        log_dir = os.path.join(os.path.abspath(os.path.join("logs", "rsl_rl", "foothold_s2_ex3031_smoke")), datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + f"_{args_cli.exp.lower()}-fresh")
        spec = make_spec(args_cli.exp, file_sha256(args_cli.parent))
        parent_iter = None
    else:
        spec, parent_iter = read_child_spec(os.path.dirname(os.path.abspath(args_cli.child_ckpt)))
        if spec.experiment_id != args_cli.exp:
            raise ValueError("child_spec.json 의 실험이 --exp 와 다르다")
        log_dir = str(resume_log_dir(os.path.abspath(args_cli.child_ckpt), datetime.now().strftime("%Y%m%d_%H%M%S"), os.getpid()))
    env_cfg.log_dir = log_dir
    STATE["log_dir"] = log_dir
    write_status(log_dir, {"state": "starting", "task": args_cli.task, "exp": args_cli.exp, "mode": args_cli.mode, "seed": agent_cfg.seed})

    gym_env = gym.make(args_cli.task, cfg=env_cfg)
    physics_check = record_realized_physics(gym_env, env_cfg, log_dir, args_cli.parent)                              # B 기동 스크립트(train_sol23f_common)가 남기던 실적용 재질 · 물리 기록
    evidence = StepEvidence(gym_env.unwrapped, log_dir)
    env = RslRlVecEnvWrapper(gym_env, clip_actions=agent_cfg.clip_actions)
    train_cfg = agent_cfg.to_dict()
    pc = dict(train_cfg.get("perception", {}) or {})
    pc["force_gt"] = args_cli.exp == "EX-31"                                          # B cfg 그대로, 처치(force_gt)만 다름
    if pc.get("map_input") != "reconstruction":
        raise ValueError("map_input 은 reconstruction")
    train_cfg["perception"] = pc
    runner_class = Ex30Runner if args_cli.exp == "EX-30" else Ex31Runner
    runner = runner_class(env, train_cfg, log_dir=log_dir, device=agent_cfg.device, evidence=evidence)
    runner.add_git_repo_to_log(__file__)
    receipt = None
    if args_cli.mode == "fresh":
        receipt = runner.begin_from_parent(args_cli.parent, spec)
        write_child_spec(log_dir, spec, runner.current_learning_iteration)
        with open(os.path.join(log_dir, "transfer_receipt.json"), "w", encoding="utf-8") as stream:
            json.dump(receipt, stream, ensure_ascii=False, indent=2)
        print("EX3031_TRANSFER_RECEIPT " + json.dumps({k: receipt[k] for k in ("parent_sha256", "parent_iter", "parent_completed_updates", "new_completed_updates", "action_std", "child_adasmpl")}), flush=True)
    else:
        print("EX3031_CHILD_CKPT_SHA256 " + sha256(args_cli.child_ckpt), flush=True)
        runner.set_spec(spec, parent_iter)
        runner.load(args_cli.child_ckpt)
        runner.reset_segment_physics()                                                # 새 시뮬은 복원한 지형 원점에서 리셋하고 시작
        print(f"EX3031_RESUMED iter={runner.current_learning_iteration}", flush=True)
    dump_yaml(os.path.join(log_dir, "params", "env.yaml"), env_cfg)
    dump_yaml(os.path.join(log_dir, "params", "agent.yaml"), train_cfg)
    pair = check_dumped_cfg_against_parent(log_dir, args_cli.parent, args_cli.exp)                                    # 처치 칸 밖의 차이가 0 이어야 학습을 시작한다
    modes = {"est_mode": runner.pcfg["est_mode"], "critic_mode": runner.pcfg["critic_mode"], "map_input": runner.pcfg.get("map_input"), "force_gt": bool(runner.pcfg.get("force_gt", False)),
             "contract": runner.pcfg["contract"], "fbg_margin_m": gp.TERMINATION["foot_below_ground_m"], "num_envs": env_cfg.scene.num_envs, "num_steps_per_env": agent_cfg.num_steps_per_env,
             "seed": agent_cfg.seed, "task": args_cli.task, "experiment": args_cli.exp, "run_kind": f"ex3031_kit_smoke_{args_cli.mode}", "spec_sha256": spec.sha256(),
             "depth_delay_ticks": int(runner.perception.cfg.depth_delay_ticks), "cfg_pair_diff_count": pair, "physics_actuators_equal_parent": physics_check["actuators_equal"]}
    manifest = run_manifest.build_manifest(repo=REPO, log_dir=log_dir, run_name=f"{args_cli.exp}-smoke-{args_cli.mode}", cli_args={**vars(args_cli), "hydra_args": hydra_args}, modes=modes,
                                           runner=runner, env_yaml=os.path.join(log_dir, "params", "env.yaml"), agent_yaml=os.path.join(log_dir, "params", "agent.yaml"))
    run_manifest.write_manifest(log_dir, manifest)
    runner.attach_manifest(log_dir, manifest)
    if runner.pcfg.get("log_map_stats"):
        from foothold_s2.runners.map_stats import MapStatsRecorder

        MapStatsRecorder(runner, log_dir).attach()
    runner.learn(num_learning_iterations=UPDATES[args_cli.mode], init_at_random_ep_len=args_cli.mode == "fresh")
    final = os.path.join(log_dir, f"model_{runner.current_learning_iteration}.pt")
    saved = torch.load(final, weights_only=False, map_location="cpu")
    result = {"exp": args_cli.exp, "mode": args_cli.mode, "checkpoint": final, "sha256": sha256(final), "iter": runner.current_learning_iteration,
              "stage_transfer": saved["stage_transfer"], "adasmpl": saved["adasmpl"], "perception_cfg_force_gt": saved["perception_cfg"]["force_gt"]}
    with open(os.path.join(log_dir, "smoke_result.json"), "w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    write_status(log_dir, {"state": "done", "iter": runner.current_learning_iteration, "log_dir": log_dir, "checkpoint": final, "sha256": result["sha256"]})
    print("EX3031_SMOKE_DONE " + json.dumps({k: result[k] for k in ("exp", "mode", "iter", "stage_transfer")}), flush=True)


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
