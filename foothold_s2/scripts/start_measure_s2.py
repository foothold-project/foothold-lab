"""RL-3 (3): 실제 S2 env(sonnet-code 의 FootholdS2-Go2-S2-G0 · G1 · G3) 로 3072 env 메모리 · iteration 시간 측정.

S2 env 코드(foothold_s2.tasks · commands · terrains · rewards 등)는 sonnet-code 사본에 있고, 지각 · runner 는 이 사본(rl)
것이 최신이다. 그래서 `foothold_s2` 패키지 경로에 이 사본을 먼저, sonnet-code 사본을 뒤에 둔다: 이 사본에 있는 모듈
(models · runners · sensors) 은 여기서, 없는 모듈(tasks 등) 은 sonnet-code 에서 온다. 측정 전용 · 학습 진입점이 아니다.

실행 예:
    isaac311/python foothold_s2/scripts/start_measure_s2.py --headless --device cuda:0 --task G1 --microbatch 256 \
        --autocast bf16 --kl_fp32 --out <폴더>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback

import tensordict  # noqa: F401  (Kit 앞에서 먼저: 뒤에서 부르면 access violation, 10/20 실측)
import torch

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--task", choices=["G0", "G1", "G3"], default="G1")
parser.add_argument("--num_envs", type=int, default=3072)
parser.add_argument("--iterations", type=int, default=3)
parser.add_argument("--microbatch", type=int, default=256)
parser.add_argument("--replay_impl", default="a3")
parser.add_argument("--autocast", default=None)
parser.add_argument("--kl_fp32", action="store_true", default=False)
parser.add_argument("--tasks_root", default="C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code")
parser.add_argument("--out", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
import foothold_s2  # noqa: E402

foothold_s2.__path__.append(os.path.join(args.tasks_root, "foothold_s2"))  # 이 사본 먼저, 없는 모듈만 sonnet-code 에서

import gymnasium as gym  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

holder: dict = {}


def main() -> dict:
    import foothold_s2.tasks  # noqa: F401
    from foothold_s2.runners.measure import precision_check, summarize
    from foothold_s2.runners.start_runner import StartRunner
    from foothold_s2.tasks import s2_env_cfg
    from foothold_s2.tasks.agents.s2_ppo_cfg import S2PPORunnerCfg

    dev = args.device or "cuda:0"
    res: dict = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "args": vars(args), "pid": os.getpid()}
    holder["res"] = res
    cfg = getattr(s2_env_cfg, f"FootholdS2{args.task}EnvCfg")()
    cfg.scene.num_envs = args.num_envs
    cfg.sim.device = dev
    gen = cfg.scene.terrain.terrain_generator
    res["terrain"] = {"num_rows": gen.num_rows, "num_cols": gen.num_cols, "size": list(gen.size)} if gen is not None else None
    env = RslRlVecEnvWrapper(gym.make(f"FootholdS2-Go2-S2-{args.task}-v0", cfg=cfg), clip_actions=None)
    # 어느 사본의 모듈이 실제로 쓰였는지 남긴다 (start_obs 는 env cfg 가 만들어질 때 처음 import 된다)
    res["module_files"] = {m: getattr(sys.modules.get(m), "__file__", None) for m in (
        "foothold_s2.runners.start_runner", "foothold_s2.models.start_perception", "foothold_s2.models.replay_fast",
        "foothold_s2.sensors.start_obs", "foothold_s2.tasks.s2_env_cfg")}
    if torch.cuda.is_available():
        res["sensors_GiB"] = torch.cuda.max_memory_allocated(dev) / 2**30
    agent = S2PPORunnerCfg()
    agent.device = dev
    tc = agent.to_dict()
    tc["perception"] = {"map_input": "none" if args.task == "G0" else "reconstruction", "microbatch_envs": args.microbatch,
                        "replay_impl": args.replay_impl, "replay_autocast": args.autocast, "kl_fp32": args.kl_fp32,
                        "measure_phases": True}
    res["perception_cfg"] = tc["perception"]
    holder["runner"] = runner = StartRunner(env, tc, log_dir=None, device=dev)
    runner.learn(args.iterations, init_at_random_ep_len=True)
    res["iter_log"], res["memory_log"] = runner.iter_log, runner.memory_log
    res["perception_losses"] = runner.last_perception_losses
    res["summary"] = summarize(res)
    if args.task != "G0":
        res["precision_check"] = precision_check(runner, dev)
    res["checks"] = {"traceback": False, "measured": True}
    return res


if __name__ == "__main__":
    out: dict = {}
    try:
        out = main()
    except Exception:
        out = dict(holder.get("res", {}))
        out["traceback"] = traceback.format_exc()
        r = holder.get("runner")
        if r is not None:
            out["iter_log"], out["memory_log"] = r.iter_log, r.memory_log
        if torch.cuda.is_available():
            out["max_allocated_at_fail_GiB"] = torch.cuda.max_memory_allocated() / 2**30
        out["checks"] = {"traceback": True}
        print(out["traceback"], flush=True)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "measure_result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("MEASURE_RESULT", json.dumps({**out.get("checks", {}), **out.get("summary", {})}, ensure_ascii=False, default=str), flush=True)
    sys.stdout.flush()
    os._exit(0 if not out["checks"].get("traceback") else 1)
