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
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402
from isaaclab.managers import ObservationGroupCfg as ObsGroup  # noqa: E402
from isaaclab.managers import ObservationTermCfg as ObsTerm  # noqa: E402
from isaaclab.managers import SceneEntityCfg  # noqa: E402
from isaaclab.sensors import RayCasterCfg, patterns  # noqa: E402
from isaaclab.utils import configclass  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp  # noqa: E402
from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.rough_env_cfg import UnitreeGo2RoughEnvCfg  # noqa: E402

from foothold_s2.sensors.depth_aug import DepthAugCfg, augment  # noqa: E402
from foothold_s2.sensors.depth_cam_cfg import make_depth_camera_cfg  # noqa: E402

FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
AUG = DepthAugCfg()


# ---------------------------------------------------------------- 관측 함수 (12 §3 · 13 §2)
def depth_obs(env, sensor_cfg: SceneEntityCfg):
    d = env.scene.sensors[sensor_cfg.name].data.output["distance_to_image_plane"]  # (N, 60, 60, 1) m
    return augment(d[..., 0], AUG).flatten(1)


def height_rel_base(env, sensor_cfg: SceneEntityCfg):
    """h = z_hit - z_base, clip ±1 m (12 §3 가정). 못 맞힌 광선은 -1."""
    s = env.scene.sensors[sensor_cfg.name]
    z = s.data.ray_hits_w[..., 2]
    base_z = env.scene["robot"].data.root_pos_w[:, 2:3]
    h = torch.nan_to_num(z - base_z, nan=-1.0, posinf=-1.0, neginf=-1.0)
    return h.clamp(-1.0, 1.0)


def feet_height(env):
    return torch.cat([height_rel_base(env, SceneEntityCfg(f"foot_scan_{i}")) for i in range(4)], -1)


def feet_contact(env, sensor_cfg: SceneEntityCfg):
    f = env.scene.sensors[sensor_cfg.name].data.net_forces_w[:, sensor_cfg.body_ids]
    return (f.norm(dim=-1) > 1.0).float()


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

    @configclass
    class Depth(ObsGroup):
        depth = ObsTerm(func=depth_obs, params={"sensor_cfg": SceneEntityCfg("depth_cam")})

    @configclass
    class GtMap(ObsGroup):
        gt_map = ObsTerm(func=height_rel_base, params={"sensor_cfg": SceneEntityCfg("gt_map_scan")})

    @configclass
    class GtFeet(ObsGroup):
        gt_feet = ObsTerm(func=feet_height)

    @configclass
    class BaseVel(ObsGroup):
        base_vel = ObsTerm(func=mdp.base_lin_vel)

    @configclass
    class Contacts(ObsGroup):
        contacts = ObsTerm(func=feet_contact, params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=list(FEET))})

    policy: Policy = Policy()
    depth: Depth = Depth()
    gt_map: GtMap = GtMap()
    gt_feet: GtFeet = GtFeet()
    base_vel: BaseVel = BaseVel()
    contacts: Contacts = Contacts()


@configclass
class StartGateEnvCfg(UnitreeGo2RoughEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.scene.height_scanner = None
        self.scene.depth_cam = make_depth_camera_cfg()
        # 정답 H^b: 32 x 16 칸 중심 x -0.475..1.075 · y -0.375..0.375 (12 §3 가정) -> 크기 1.55 x 0.75 · 가운데 x 0.3
        self.scene.gt_map_scan = RayCasterCfg(
            prim_path="{ENV_REGEX_NS}/Robot/base",
            offset=RayCasterCfg.OffsetCfg(pos=(0.3, 0.0, 20.0)),
            ray_alignment="yaw",
            pattern_cfg=patterns.GridPatternCfg(resolution=0.05, size=[1.55, 0.75], ordering="yx"),
            mesh_prim_paths=["/World/ground"],
        )
        for i, foot in enumerate(FEET):
            setattr(self.scene, f"foot_scan_{i}", RayCasterCfg(
                prim_path=f"{{ENV_REGEX_NS}}/Robot/{foot}",
                offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 20.0)),
                ray_alignment="yaw",
                pattern_cfg=patterns.GridPatternCfg(resolution=0.05, size=[0.2, 0.2], ordering="yx"),
                mesh_prim_paths=["/World/ground"],
            ))
        self.observations = GateObsCfg()
        self.curriculum.terrain_levels = None
        if self.scene.terrain.terrain_generator is not None:
            self.scene.terrain.terrain_generator.num_rows = 4
            self.scene.terrain.terrain_generator.num_cols = 4
            self.scene.terrain.terrain_generator.curriculum = False


def agent_cfg(num_steps: int = 24) -> dict:
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
        "perception": {},
    }


def main() -> dict:
    from foothold_s2.runners.start_runner import StartRunner

    os.makedirs(args.out, exist_ok=True)
    res: dict = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "num_envs": args.num_envs, "iterations": args.iterations,
                 "device": args.device, "seed": args.seed}
    dev = args.device or "cuda:0"
    torch.manual_seed(args.seed)
    cfg = StartGateEnvCfg()
    cfg.scene.num_envs = args.num_envs
    cfg.seed = args.seed
    cfg.sim.device = dev
    base = ManagerBasedRLEnv(cfg)
    res["gt_map_rays"] = int(base.scene["gt_map_scan"].num_rays) if hasattr(base.scene["gt_map_scan"], "num_rays") else None
    env = RslRlVecEnvWrapper(base)
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
    runner = StartRunner(env, agent_cfg(), log_dir=args.out, device=dev)
    t0 = time.time()
    runner.learn(args.iterations, init_at_random_ep_len=True)
    res["learn_seconds"] = time.time() - t0
    res["resets"] = resets["n"]
    res["perception_losses"] = runner.last_perception_losses
    res["adasmpl_p"] = runner.adasmpl.p
    res["memory_GiB"].update({k: v / 2**30 for k, v in runner.memory_marks.items()})
    ck = os.path.join(args.out, "gate_ckpt.pt")
    runner.save(ck)
    res["ckpt_keys"] = sorted(torch.load(ck, weights_only=False).keys())

    # 새 runner 로 복원 -> 같은 입력 같은 출력 (1e-6)
    torch.manual_seed(args.seed + 1000)
    runner2 = StartRunner(env, agent_cfg(), log_dir=None, device=dev)
    runner2.load(ck)
    b = runner.replay.gather(torch.arange(min(8, args.num_envs), device=dev))
    diffs = {}
    with torch.no_grad():
        for name, r in (("a", runner), ("b", runner2)):
            r.eval_mode()
            hp, ht = b["h_prop0"], b["h_terr0"]
            outs = []
            for t in range(runner.num_steps_per_env):
                hp, ht, o = r.perception._advance(hp, ht, b["hist"][t], b["depth2"][t].float(), b["tick"][t], b["first"][t],
                                                  b["use_gt"][t], b["gt_map"][t])
                est = torch.cat([o["mu"], o["v"], o["zf"], o["zb"]], -1)
                outs.append(r.alg.policy.act_inference({"actor_in": torch.cat([b["obs"][t], est], -1)}))
            diffs[name] = torch.stack(outs)
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
    try:
        out = main()
    except Exception:
        out["traceback"] = traceback.format_exc()
        out.setdefault("checks", {})["traceback"] = True
        print(out["traceback"], flush=True)
    finally:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "gate_result.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1, default=str)
        print("GATE_RESULT", json.dumps(out.get("checks", {}), ensure_ascii=False), flush=True)
        app.close()
