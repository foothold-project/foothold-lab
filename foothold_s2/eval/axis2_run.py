"""축 2 (평지 명령 응답) 실행. Kit 쪽.

네 시나리오를 «한 프로세스에서 이어» 돈다. turn 만 따로 돌리면 난수 소비가 달라 값이 바뀌므로
판정은 이어 돈 값이다 (v2 6-9 의 주의, 41 §3).

명령 쓰기 순서: 시나리오의 시각 t+dt 명령을 `env.step` «전» 에 써 두어, step 이 돌려주는
관측이 그 명령을 담게 한다 (E1 정책은 관측 이력 10 스텝을 쓴다. 관측을 다시 지으면 이력에 안 든다).
표본은 스텝 «전» 에 쌓는다.
"""

import json
import os
import time

import numpy as np
import torch

from foothold_s2.eval import axis2_metrics, cells, manifest

TURN_STEPS = (-1.0, -0.5, 0.0, 0.5, 1.0)


def _stop(t):
    return (1.0, 0.0, 0.0) if t < 4.0 else (0.0, 0.0, 0.0)


def _ramp(t):
    return (max(0.0, min(1.5, 1.5 * t / 20.0)), 0.0, 0.0)


def _turn(t):
    """제자리 요레이트 계단 다섯, 계단마다 3 초. 앞 1.5 초와 끝 뒤는 0."""
    if t < 1.5:
        return (0.0, 0.0, 0.0)

    index = int((t - 1.5) // 3.0)

    return (0.0, 0.0, TURN_STEPS[index]) if index < len(TURN_STEPS) else (0.0, 0.0, 0.0)


def _hold(t):
    return (0.0, 0.0, 0.0)


SCENARIOS = {
    "stop": (_stop, 10.0),
    "ramp": (_ramp, 20.0),
    "turn": (_turn, 18.0),
    "hold": (_hold, 20.0),
}

# 축 2 는 푸시만 끈다. 질량 · 무게중심 무작위는 학습 그대로 둔다 (v2 프로브가 학습 사건을 두는 것과 같은 방침).
EVENTS_OFF = ("randomize_push_robot",)


def _cmd(term):
    """명령 버퍼. robot_lab 항은 `commands`, Isaac Lab 항은 `vel_command_b`."""
    return term.commands if hasattr(term, "commands") else term.vel_command_b


def run(args, adapter, runtime, device):
    names = list(cells.AXIS2_PARAMS["scenarios"]) if args.scenario == "all" \
        else [n.strip() for n in args.scenario.split(",")]
    unknown = [n for n in names if n not in SCENARIOS]

    if unknown:
        raise RuntimeError("모르는 시나리오 %r (있는 것 %r)" % (unknown, list(SCENARIOS)))

    n_env = args.num_envs
    longest = max(SCENARIOS[n][1] for n in names)
    built = adapter.make_env(generator=None, num_envs=n_env, duration_s=longest + 1.0, seed=args.seed,
                             difficulty=args.difficulty, base_cmd=[(0.0, 0.0, 0.0)] * n_env,
                             device=device, plane=True, env_spacing=8.0, events_off=EVENTS_OFF)
    raw = built["raw"]
    from foothold_s2.tasks.robot_mass import log_robot_mass

    log_robot_mass(raw, "eval axis2 " + args.policy)                          # 평가 시작에 로드 뒤 로봇 총질량 한 줄 (난수를 쓰지 않는다)
    pin = runtime.CommandPin(n_env, raw.device, [(0.0, 0.0, 0.0)] * n_env)

    # 순서가 값을 바꾼다 (10/20 hold 조사). 래퍼를 먼저 지어 reset 을 한 번 소비하고, 그 뒤 reset 을 하고,
    # 그 뒤에 명령 항을 고친다. 옛 축 2 하네스와 같은 순서이고, 이 순서에서만 hold 단독 실행이 옛 하네스
    # 단독 실행과 같은 값(잔류 속도 0.00083, 관절 목표 변화 0.00185)이 나온다. 다른 순서는 reset 무작위
    # 뽑기가 달라져 hold 값이 0.0017~0.0034 · 0.0073~0.0112 로 흔들린다 (정의는 같다).
    adapter.wrap(built)
    raw.reset()
    term = adapter.pin_command(raw, pin)
    env, policy, policy_nn, _obs = adapter.load_policy(built, args.checkpoint)

    robot = raw.scene["robot"]
    dt = raw.step_dt
    rebuild = getattr(adapter, "rebuilds_obs", False)
    summary = {}
    per_scenario_env = {}

    for name in names:
        profile, duration = SCENARIOS[name]
        n_steps = int(round(duration / dt))
        print("[axis2] %s: %.1f s, %d 스텝" % (name, duration, n_steps), flush=True)

        first = torch.tensor(profile(0.0), device=raw.device, dtype=torch.float32)
        pin.base[:] = first
        pin.want[:] = first
        raw.reset()
        obs = env.get_observations()

        n_joint = robot.data.joint_pos_target.shape[1]
        width = 2 + 1 + 3 + n_joint
        buf = torch.zeros((n_env, n_steps, width), device=raw.device)
        alive = torch.ones(n_env, dtype=torch.bool, device=raw.device)
        n_valid = torch.zeros(n_env, dtype=torch.long, device=raw.device)
        fell_at = torch.full((n_env,), float("nan"), device=raw.device)
        env_index = torch.arange(n_env, device=raw.device)

        for step in range(n_steps):
            t = step * dt

            if rebuild:
                # Isaac Lab 계열(관측 이력 없음): 옛 v2 프로브처럼 시각 t 의 명령을 쓰고 관측을 다시 짓는다.
                # 안 하면 reset 직후 첫 행동이 reset 때 뽑힌 0 명령을 본다 (stop 의 첫 스텝이 1.0 이어야 한다).
                cur = torch.tensor(profile(t), device=raw.device, dtype=torch.float32)
                pin.base[:] = cur
                pin.want[:] = cur
                _cmd(term)[:, :3] = cur
                obs = env.get_observations()

            sample = torch.cat([robot.data.root_lin_vel_b[:, :2], robot.data.root_ang_vel_b[:, 2:3],
                                _cmd(term)[:, :3], robot.data.joint_pos_target], dim=1)
            room = env_index[alive]

            if room.numel():
                buf[room, n_valid[room]] = sample[room]
                n_valid[room] += 1

            with torch.inference_mode():
                action = policy(obs)

            if not rebuild:
                nxt = torch.tensor(profile(t + dt), device=raw.device, dtype=torch.float32)
                pin.base[:] = nxt
                pin.want[:] = nxt
                _cmd(term)[:, :3] = nxt

            # step 은 inference_mode 밖에서 부른다. 안에서 부르면 다음 시나리오의 raw.reset() 이
            # 「inference tensor 를 밖에서 고친다」 로 죽는다 (옛 축 2 하네스와 같은 구조).
            obs, _r, dones, _e = env.step(action)

            if not rebuild:
                policy_nn.reset(dones)

            newly = alive & raw.termination_manager.terminated

            if newly.any():
                fell_at[newly] = t + dt
                alive = alive & ~newly

            if not alive.any():
                print("[axis2] %s: %.2f s 에 전부 넘어짐" % (name, t + dt), flush=True)
                break

        per_env = []
        data = buf.cpu().numpy().astype(np.float64)
        valid = n_valid.cpu().tolist()
        fell = fell_at.cpu().tolist()

        for e in range(n_env):
            n = valid[e]

            if n < 2:
                per_env.append(axis2_metrics.env_metrics(np.zeros(n), np.zeros(n), np.zeros(n),
                                                         np.zeros((n, 3)), np.zeros((n, 1)), dt, fell[e]))
                continue

            d = data[e, :n]
            per_env.append(axis2_metrics.env_metrics(d[:, 0], d[:, 1], d[:, 2], d[:, 3:6], d[:, 6:],
                                                     dt, fell[e]))

        per_scenario_env[name] = per_env
        summary[name] = axis2_metrics.aggregate_scenario(per_env)

    cells_table = axis2_metrics.judge_cells(summary)

    with open(os.path.join(args.out, "axis2_summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    with open(os.path.join(args.out, "axis2_per_env.json"), "w", encoding="utf-8") as handle:
        json.dump(per_scenario_env, handle, ensure_ascii=False, indent=1, default=float)

    env.close()
    record = {
        "policy_kind": adapter.name,
        "checkpoint": args.checkpoint,
        "checkpoint_sha256": manifest.file_sha256(args.checkpoint),
        "adapter_changes": adapter.changes,
        "adapter_checks": adapter.checks,
        "scenarios": names,
        "num_envs": n_env,
        "step_dt_s": dt,
        "events_off": list(EVENTS_OFF),
        "wall_finished": time.strftime("%Y-%m-%d %H:%M:%S"),
        "params": cells.AXIS2_PARAMS,
    }

    return {"cells": [dict(r, value=r["value"]) for r in cells_table], "record": record}
