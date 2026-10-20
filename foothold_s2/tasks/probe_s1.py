"""S1 Kit 짧은 확인 셋 (L1): 행동 지연 · 모터 세기 · 발 지면 아래 종료의 참 양성. 숫자로 출력한다.

사용: python -m foothold_s2.tasks.probe_s1 --headless --device cuda:1
"""

import argparse

import h5py  # noqa: F401
import torch
import tensordict  # noqa: F401
import rsl_rl.runners  # noqa: F401

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402

from foothold_s2.tasks.s1_env_cfg import FootholdS1aBlindEnvCfg  # noqa: E402


def main():
    cfg = FootholdS1aBlindEnvCfg()
    cfg.scene.num_envs = 64
    cfg.sim.device = args.device
    env = ManagerBasedRLEnv(cfg)
    env.reset()
    dev = env.device
    asset = env.scene["robot"]
    term = env.action_manager.get_term("joint_pos")
    ok = True

    # (1) 행동 지연: 제어 스텝 둘을 수동으로 돌려 하위 스텝마다 목표를 읽는다
    a1 = torch.randn(env.num_envs, 12, device=dev)
    a2 = torch.randn(env.num_envs, 12, device=dev)
    term.process_actions(a1)
    term.reset(None)                      # 지연 표집 + prev 를 현재 관절로
    term.process_actions(a1)
    first_target = term.processed_actions.clone()
    term.process_actions(a2)
    prev, new = first_target, term.processed_actions.clone()
    seen = []

    for sub in range(env.cfg.decimation):
        term.apply_actions()
        seen.append(asset.data.joint_pos_target[:, term._joint_ids].clone())

    bad = 0

    for e in range(env.num_envs):
        d = int(term.delay[e])

        for sub in range(env.cfg.decimation):
            want = prev[e] if sub < d else new[e]
            bad += int(not torch.allclose(seen[sub][e], want, atol=1e-6))

    print(f"[PROBE] delay values {sorted(set(term.delay.tolist()))} mismatches {bad}")
    ok &= bad == 0 and len(set(term.delay.tolist())) > 1

    # (2) 모터 세기
    ratios = []

    for name, act in asset.actuators.items():
        base = {"hip_thigh": 23.5, "calf": 45.43}[name]
        r = act.effort_limit[:, 0] / base
        ratios.append(r)
        sat_equal = bool(torch.allclose(act._saturation_effort, act.effort_limit))
        print(f"[PROBE] {name}: effort_limit ratio min {float(r.min()):.4f} max {float(r.max()):.4f} "
              f"unique {len(torch.unique(r))} sat==limit {sat_equal}")
        ok &= 0.9 - 1e-4 <= float(r.min()) and float(r.max()) <= 1.1 + 1e-4 and len(torch.unique(r)) > 1 and sat_equal

    # (3) 발 지면 아래 종료: 정상 상태 오탐 0, 몸을 0.6 m 내려 발을 땅 속에 넣으면 참 양성
    zero = torch.zeros(env.num_envs, 12, device=dev)

    for _ in range(5):
        env.step(zero)

    pos = asset.data.root_state_w.clone()
    base_hits = int(env.termination_manager.get_term("foot_below_ground").sum())
    pos[:, 2] -= 0.6
    asset.write_root_pose_to_sim(pos[:, :7])
    asset.write_root_velocity_to_sim(torch.zeros(env.num_envs, 6, device=dev))
    env.scene.write_data_to_sim()
    env.sim.step(render=False)
    env.scene.update(env.physics_dt)
    env.scene.sensors["height_scanner"].update(env.physics_dt, force_recompute=True)
    done = env.termination_manager.compute()
    below = env.termination_manager.get_term("foot_below_ground")
    print(f"[PROBE] foot_below_ground false positives before {base_hits}, after forcing 0.6 m down: "
          f"{int(below.sum())} of {env.num_envs}")
    ok &= base_hits == 0 and int(below.sum()) > 0.5 * env.num_envs
    print(f"[PROBE] RESULT {'PASS' if ok else 'FAIL'}")
    del done
    env.close()


if __name__ == "__main__":
    main()
    app.close()
