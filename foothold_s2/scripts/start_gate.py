"""10/27 S2 통합 관문 (12 §6.1 · §9 L1 · 70 §1 · rl 책임): 64 env · GPU 한 장에서 한 사이클.

    수집 -> PPO update -> 지각 update(두 손실) -> reset(terminal 마스크) -> 저장 -> 새 runner 복원 -> 같은 입력 같은 출력

환경은 이 관문 전용이다(Isaac Lab Go2 rough env + D435i 광선 카메라 + 정답 지도 광선 센서). 본 학습 env(tasks/s2_env_cfg.py,
lead) 가 아니다. 그래서 보상은 Isaac Lab Go2 기본값이고 **발 가장자리 보상 · 14 명령 생성기 · 15 지형은 이 관문에 없다**.

실행 예 (Windows, 저장소 뿌리에서):
    C:/isaac/IsaacLab/isaaclab.bat -p foothold_s2/scripts/start_gate.py --headless --num_envs 64 --device cuda:0 --out <폴더>

결과: <out>/gate_result.json (판정 항목 · 메모리 다섯 지점 · 손실 · 리셋 수 · 복원 차이) · depth_sample.npy · 체크포인트.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback

# tensordict 의 C 확장은 Kit 이 뜬 뒤 처음 불러오면 이 기기에서 access violation 으로 죽는다(10/20 실측 두 번).
# 그래서 Kit 앞에서 먼저 불러 둔다.
import tensordict  # noqa: F401,E402
import torch  # noqa: E402

from isaaclab.app import AppLauncher  # noqa: E402

parser = argparse.ArgumentParser(description="START S2 통합 관문 한 사이클")
parser.add_argument("--num_envs", type=int, default=64)
parser.add_argument("--iterations", type=int, default=2)
parser.add_argument("--out", type=str, required=True)
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--microbatch", type=int, default=None, help="지각 microbatch env 수 (기본 256 · 12 §6.1)")
parser.add_argument("--replay_impl", type=str, default=None, help="지각 재생 구현 loop · a1 · a2 · a3 (RL-3)")
parser.add_argument("--autocast", type=str, default=None, help="지각 재생 autocast: bf16 (RL-3 B)")
parser.add_argument("--measure", action="store_true", default=False,
                    help="18 §5.2 메모리 측정: 단계별 peak · iteration 시간. 같은 프로세스 복원 대조는 건너뛴다")
parser.add_argument("--restore_from", type=str, default=None,
                    help="앞 실행의 out 폴더. 주면 학습하지 않고 새 프로세스에서 체크포인트를 복원해 같은 입력 같은 출력만 본다")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402
from isaaclab.managers import ObservationGroupCfg as ObsGroup  # noqa: E402
from isaaclab.managers import ObservationTermCfg as ObsTerm  # noqa: E402
from isaaclab.utils import configclass  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp  # noqa: E402
from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.rough_env_cfg import UnitreeGo2RoughEnvCfg  # noqa: E402

from foothold_s2.sensors.start_obs import apply_start_perception  # noqa: E402


@configclass
class GateObsCfg:
    @configclass
    class Policy(ObsGroup):
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel, scale=0.25)
        projected_gravity = ObsTerm(func=mdp.projected_gravity)
        velocity_commands = ObsTerm(func=mdp.generated_commands, params={"command_name": "base_velocity"}, scale=(2.0, 2.0, 0.25))
        joint_pos = ObsTerm(func=mdp.joint_pos_rel)
        joint_vel = ObsTerm(func=mdp.joint_vel_rel, scale=0.05)
        actions = ObsTerm(func=mdp.last_action)

        def __post_init__(self):
            self.enable_corruption = False
            self.concatenate_terms = True

    policy: Policy = Policy()


@configclass
class StartGateEnvCfg(UnitreeGo2RoughEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.scene.height_scanner = None
        self.observations = GateObsCfg()
        apply_start_perception(self)  # s2_env_cfg 와 같은 함수로 센서 · 관측 묶음을 붙인다
        self.curriculum.terrain_levels = None
        # 측정 판은 Isaac Lab 기본 rough 지형 크기(10 x 20 칸)를 그대로 둔다. 관문 판만 줄인다
        if self.scene.terrain.terrain_generator is not None and not args.measure:
            self.scene.terrain.terrain_generator.num_rows = 4
            self.scene.terrain.terrain_generator.num_cols = 4
            self.scene.terrain.terrain_generator.curriculum = False


def agent_cfg(num_steps: int = 24, perception: dict | None = None) -> dict:
    """18 §1 PPO 값(Isaac Lab Go2 cfg · 가정) · 12 §6.1 지각 optimizer 값(가정)."""
    return {
        "num_steps_per_env": num_steps,
        "save_interval": 1000,
        "obs_groups": {},
        "policy": {"class_name": "StartActorCritic", "init_noise_std": 1.0,
                   "actor_obs_normalization": False, "critic_obs_normalization": False},
        "algorithm": {"class_name": "PPO", "num_learning_epochs": 5, "num_mini_batches": 4, "clip_param": 0.2,
                      "gamma": 0.99, "lam": 0.95, "value_loss_coef": 1.0, "entropy_coef": 0.01, "learning_rate": 1e-3,
                      "max_grad_norm": 1.0, "schedule": "adaptive", "desired_kl": 0.01},
        "perception": dict(perception or {}),
    }


def policy_outputs(r, b) -> torch.Tensor:
    """재생 버퍼 한 묶음을 지각 -> actor 평균 행동까지 통과시킨 (T, B, 12)."""
    r.eval_mode()
    hp, ht = b["h_prop0"], b["h_terr0"]
    outs = []
    with torch.no_grad():
        for t in range(r.num_steps_per_env):
            hp, ht, o = r.perception._advance(hp, ht, b["hist"][t], b["depth2"][t].float(), b["tick"][t], b["first"][t],
                                              b["use_gt"][t], b["gt_map"][t])
            est = torch.cat([o["mu"], o["v"], o["zf"], o["zb"]], -1)
            outs.append(r.alg.policy.act_inference({"actor_in": torch.cat([b["obs"][t], est], -1)}))
    return torch.stack(outs)


def make_env(dev: str):
    cfg = StartGateEnvCfg()
    cfg.scene.num_envs = args.num_envs
    cfg.seed = args.seed
    cfg.sim.device = dev
    base = ManagerBasedRLEnv(cfg)
    return base, RslRlVecEnvWrapper(base)


def restore_main() -> dict:
    """새 프로세스 복원 시험: 앞 실행의 gate_ckpt.pt 와 ref_io.pt 로 같은 입력 같은 출력(1e-6) 을 본다."""
    from foothold_s2.runners.start_runner import StartRunner

    dev = args.device or "cuda:0"
    res: dict = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "restore", "restore_from": args.restore_from,
                 "pid": os.getpid()}
    torch.manual_seed(args.seed + 2000)  # 앞 실행과 다른 초기 가중치에서 시작해 복원만으로 같아지는지 본다
    _, env = make_env(dev)
    r = StartRunner(env, agent_cfg(), log_dir=None, device=dev)
    ref = torch.load(os.path.join(args.restore_from, "ref_io.pt"), weights_only=False)
    b = {k: v.to(dev) for k, v in ref["batch"].items()}
    before = float((policy_outputs(r, b).cpu() - ref["out"]).abs().max())
    ck = torch.load(os.path.join(args.restore_from, "gate_ckpt.pt"), weights_only=False)
    r.load(os.path.join(args.restore_from, "gate_ckpt.pt"))
    after = float((policy_outputs(r, b).cpu() - ref["out"]).abs().max())
    po = r.perception_optimizer.state_dict()["state"]
    opt_same = all(torch.equal(torch.as_tensor(v).cpu(), torch.as_tensor(ck["perception_optimizer_state_dict"]["state"][i][k]).cpu())
                   for i, s in po.items() for k, v in s.items())
    res.update({"max_abs_diff_before_load": before, "max_abs_diff_after_load": after,
                "adasmpl_same": r.adasmpl.state_dict() == ref["adasmpl"], "perception_optimizer_same": opt_same,
                "iter": r.current_learning_iteration})
    res["checks"] = {"traceback": False, "differs_before_load": before > 1e-3, "same_after_load": after <= 1e-6,
                     "adasmpl_same": res["adasmpl_same"], "perception_optimizer_same": opt_same}
    return res


holder: dict = {}


def precision_check(runner, dev: str) -> dict:
    """마지막 재생 버퍼의 env 64 개로 같은 잡음 · 같은 가중치에서 loop fp32 대 (지금 구현 · fp32) 대 (지금 구현 · bf16) 손실."""
    b = runner.replay.gather(torch.arange(min(64, runner.env.num_envs), device=dev))
    eps = torch.randn(b["obs"].shape[0], b["obs"].shape[1], 16, device=dev, generator=torch.Generator(dev).manual_seed(0))
    impl = runner.pcfg["replay_impl"]
    out = {}
    keys = ("l_tr", "l_ie", "kl", "o_next", "v", "hf", "hb")
    tf32 = torch.backends.cudnn.allow_tf32
    with torch.no_grad():
        torch.backends.cudnn.allow_tf32 = False
        ref = runner.perception.sequence_loss(b, eps=eps, impl="loop")
        fast = runner.perception.sequence_loss(b, eps=eps, impl=impl) if impl != "loop" else ref
        torch.backends.cudnn.allow_tf32 = tf32
        fast_tf32 = runner.perception.sequence_loss(b, eps=eps, impl=impl)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            bf = runner.perception.sequence_loss(b, eps=eps, impl=impl)
    for k in keys:
        out[k] = {"loop_fp32": float(ref[k]), "impl_fp32": float(fast[k]), "impl_tf32": float(fast_tf32[k]), "impl_bf16": float(bf[k])}
    out["max_abs_impl_vs_loop"] = max(abs(v["impl_fp32"] - v["loop_fp32"]) for v in out.values() if isinstance(v, dict))
    out["max_abs_bf16_vs_loop"] = max(abs(v["impl_bf16"] - v["loop_fp32"]) for v in out.values() if isinstance(v, dict))
    out["impl"] = impl
    return out


def main() -> dict:
    from foothold_s2.runners.start_runner import StartRunner

    os.makedirs(args.out, exist_ok=True)
    res: dict = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "num_envs": args.num_envs, "iterations": args.iterations,
                 "device": args.device, "seed": args.seed}
    holder["res"] = res
    dev = args.device or "cuda:0"
    torch.manual_seed(args.seed)
    base, env = make_env(dev)
    res["gt_map_rays"] = int(base.scene["gt_map_scan"].num_rays) if hasattr(base.scene["gt_map_scan"], "num_rays") else None
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats(dev)
    obs0 = env.get_observations()
    res["obs_shapes"] = {k: list(v.shape) for k, v in obs0.items()}
    torch.save(obs0["depth"][:4].reshape(-1, 60, 60).cpu(), os.path.join(args.out, "depth_sample.pt"))
    if torch.cuda.is_available():
        res.setdefault("memory_GiB", {})["1_sensors"] = torch.cuda.max_memory_allocated(dev) / 2**30

    # reset 이 실제로 일어났는지 센다
    resets = {"n": 0}
    orig_step = env.step

    def counting_step(a):
        o, r, d, e = orig_step(a)
        resets["n"] += int((d > 0).sum())
        return o, r, d, e

    env.step = counting_step
    pc = {"measure_phases": bool(args.measure)}
    if args.microbatch:
        pc["microbatch_envs"] = args.microbatch
    if args.replay_impl:
        pc["replay_impl"] = args.replay_impl
    if args.autocast:
        pc["replay_autocast"] = args.autocast
    res["perception_cfg"] = pc
    holder["runner"] = runner = StartRunner(env, agent_cfg(perception=pc), log_dir=args.out, device=dev)
    t0 = time.time()
    runner.learn(args.iterations, init_at_random_ep_len=True)
    res["learn_seconds"] = time.time() - t0
    res["resets"] = resets["n"]
    res["perception_losses"] = runner.last_perception_losses
    res["adasmpl_p"] = runner.adasmpl.p
    res["memory_GiB"].update({k: v / 2**30 for k, v in runner.memory_marks.items()})
    res["memory_log"] = runner.memory_log
    res["iter_log"] = runner.iter_log
    res["replay_bytes"] = runner.replay.nbytes()
    if args.measure:
        res["precision_check"] = precision_check(runner, dev)
        res["checks"] = {"traceback": False, "measured": True}
        return res
    ck = os.path.join(args.out, "gate_ckpt.pt")
    runner.save(ck)
    res["ckpt_keys"] = sorted(torch.load(ck, weights_only=False).keys())

    # 새 runner 로 복원 -> 같은 입력 같은 출력 (1e-6). 새 프로세스 판은 --restore_from 으로 따로 돈다
    torch.manual_seed(args.seed + 1000)
    runner2 = StartRunner(env, agent_cfg(), log_dir=None, device=dev)
    runner2.load(ck)
    b = runner.replay.gather(torch.arange(min(8, args.num_envs), device=dev))
    diffs = {"a": policy_outputs(runner, b), "b": policy_outputs(runner2, b)}
    torch.save({"batch": {k: v.cpu() for k, v in b.items()}, "out": diffs["a"].cpu(), "adasmpl": runner.adasmpl.state_dict()},
               os.path.join(args.out, "ref_io.pt"))
    res["restore_max_abs_diff"] = float((diffs["a"] - diffs["b"]).abs().max())
    res["restore_same"] = res["restore_max_abs_diff"] <= 1e-6
    res["adasmpl_same"] = runner.adasmpl.state_dict() == runner2.adasmpl.state_dict()
    res["checks"] = {
        "traceback": False,
        "collected_and_two_losses": all(k in runner.last_perception_losses for k in ("l_tr", "l_ie")),
        "reset_happened": resets["n"] > 0,
        "restore_same": res["restore_same"] and res["adasmpl_same"],
        "edge_reward_connected": "s2_env_cfg 대기",  # 이 관문 env 에는 없다(lead 의 s2_env_cfg · 16 발 가장자리 보상)
    }
    return res


if __name__ == "__main__":
    out: dict = {}
    name = "gate_restore_result.json" if args.restore_from else "gate_result.json"
    try:
        out = restore_main() if args.restore_from else main()
    except Exception:
        out = dict(holder.get("res", {}))
        out["traceback"] = traceback.format_exc()
        r = holder.get("runner")
        if r is not None:  # OOM 이면 어느 단계까지 갔는지 남긴다
            out["memory_log"] = r.memory_log
            out["iter_log"] = r.iter_log
        if torch.cuda.is_available():
            out["max_allocated_at_fail_GiB"] = torch.cuda.max_memory_allocated() / 2**30
        out.setdefault("checks", {})["traceback"] = True
        print(out["traceback"], flush=True)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, name), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    ok = all(v is True or isinstance(v, str) for k, v in out.get("checks", {}).items() if k != "traceback") and not out.get("checks", {}).get("traceback", True)
    print("GATE_RESULT", json.dumps(out.get("checks", {}), ensure_ascii=False), flush=True)
    # app.close() 가 이 기기에서 결과 기록 뒤 멈춘다(10/20 11:29 실행). 결과를 쓴 뒤 강제 종료하고, 종료 코드로 판정을 낸다
    # (Isaac 은 예외 뒤에도 0 을 낼 수 있어 코드 0 만으로 믿지 않는다 · 판정은 위 json)
    sys.stdout.flush()
    os._exit(0 if ok else 1)
