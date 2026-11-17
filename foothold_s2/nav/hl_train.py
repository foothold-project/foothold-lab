"""HiPAN 모드 2 teacher PPO 학습 루프 (설계 §3 N3). Kit 없이 CPU 에서 시험할 수 있게 환경 꼴만 요구한다.

환경 꼴 (`TeacherVecEnv` 또는 같은 메서드의 가짜): `n` · `reset() -> obs (n, D)` · `step(action (n, 3)) -> obs, reward (n,), done (n,), timeout (n,), info`.
`TeacherVecEnv` = `NavEnv` (N1) + `NavTask` (N2): 상위 틱마다 하위 5 스텝 -> 보상 · 부목표 -> 끝난 env 는 실제 몸 위치로 `reset_envs` -> 관측.
저장: 50 회마다 `model_<회>.pt` (덮어쓰지 않음) · 이어 받기는 같은 PPO 설정일 때만 (다르면 거절). 첫 호출이 환경을 기동하는 일은 이 파일이 하지 않는다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

CKPT_FORMAT = "foothold-hipan-teacher-ckpt/1"


class TeacherVecEnv:
    def __init__(self, nav_env, task, device="cpu"):
        import torch

        if int(nav_env.n) != int(task.n):
            raise ValueError(f"NavEnv has {nav_env.n} envs, NavTask has {task.n}")
        self.nav, self.task, self.n = nav_env, task, int(nav_env.n)
        self.device, self._torch = device, torch
        try:                                                  # 상위 틱 한 번의 초 (회차 통계의 에피소드 길이 · 초)
            self.task.tick_s = float(nav_env.hold) * float(nav_env.raw.step_dt)
        except (AttributeError, TypeError, ValueError):
            pass

    def take_nav_stats(self) -> dict:
        take = getattr(self.task, "take_stats", None)
        return take() if take is not None else {}

    def _pos_room(self, state, ids):
        from foothold_s2.nav import teacher_obs

        org = None if self.task.origin_xy is None else np.asarray(self.task.origin_xy)[ids]
        return teacher_obs.to_room_frame(state.pos_local[ids], org)[:, :2]

    def _obs(self, state):
        return self._torch.as_tensor(self.task.observation(state)["flat"], device=self.device)

    def reset(self):
        state = self.state = self.nav.reset()
        ids = np.arange(self.n)
        self.task.reset_envs(ids, start_xy=self._pos_room(state, ids))
        return self._obs(state)

    def step(self, action):
        t = self._torch
        state = self.state = self.nav.step(action.detach().cpu().numpy())
        out = self.task.step(state)
        done = np.asarray(state.done, bool)
        self.task_reached = np.asarray(out["task_reached"], bool).copy()      # reset_envs 가 PGCL 을 되돌리기 전 값 (평가가 읽음)
        ids = np.flatnonzero(done | out["task_reached"])
        # 끝난 env: Isaac 이 이미 새 에피소드로 되돌렸으므로 지금 몸 위치가 새 시작 (G1). 과제를 끝낸 env 는 PGCL 이 새 과제를 요청한다.
        if len(ids):
            self.task.reset_envs(ids, start_xy=self._pos_room(state, ids))
        r = t.as_tensor(np.asarray(out["reward"], np.float32), device=self.device)
        d = t.as_tensor(done, device=self.device)
        to = t.as_tensor(np.asarray(state.timed_out, bool), device=self.device)
        info = {"task_reached": int(out["task_reached"].sum()), "fell": int((done & ~np.asarray(state.timed_out, bool)).sum()),
                "task_fallback": int(getattr(self.task, "task_fallbacks", 0)) - getattr(self, "_fb0", 0),
                "task_new": int(getattr(self.task, "task_new", 0)) - getattr(self, "_new0", 0), "task_winding": int(getattr(self.task, "task_winding", 0)) - getattr(self, "_wind0", 0)}
        for k, v in (getattr(self.nav, "term_counts", None) or {}).items():       # 종료 까닭별 env 수 (몸 닿음 · 기울기 · 시간 ...)
            info["term_" + k] = int(v)
        col = getattr(state, "collision", None)
        info["fell_with_collision"] = 0 if col is None else int((done & ~np.asarray(state.timed_out, bool) & np.asarray(col, bool)).sum())
        info["task_redraw"] = int(getattr(self.task, "task_redraw_on_reset", 0)) - getattr(self, "_rd0", 0)
        info["table_miss"] = int(getattr(self.task, "task_table_miss", 0)) - getattr(self, "_tm0", 0)
        self._rd0, self._tm0 = int(getattr(self.task, "task_redraw_on_reset", 0)), int(getattr(self.task, "task_table_miss", 0))
        self._fb0 = int(getattr(self.task, "task_fallbacks", 0))
        self._new0, self._wind0 = int(getattr(self.task, "task_new", 0)), int(getattr(self.task, "task_winding", 0))
        return self._obs(state), r, d, to, info


def _policy_parts(ppo):
    import torch
    from torch import nn
    from foothold_s2.nav import hl_ppo_cfg as cfg

    actor, critic = cfg.build_actor_critic(ppo)
    log_std = nn.Parameter(torch.full((cfg.ACTION_DIM,), float(np.log(ppo.init_noise_std))))
    return actor, critic, log_std


def train(env, ppo, *, out_dir, iterations, receipt: dict, resume=None, device="cpu", seed=0, log=print):
    """`iterations` = 이 호출에서 돌 회 수. 돌려주는 값: 마지막 회 번호 · 저장 경로 목록."""
    import torch

    torch.manual_seed(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    actor, critic, log_std = _policy_parts(ppo)
    actor.to(device), critic.to(device)
    log_std.data = log_std.data.to(device)
    params = list(actor.parameters()) + list(critic.parameters()) + [log_std]
    opt = torch.optim.Adam(params, lr=ppo.learning_rate)
    it0, lr = 0, ppo.learning_rate
    if resume:
        ck = torch.load(resume, map_location=device, weights_only=False)
        if ck.get("format") != CKPT_FORMAT:
            raise ValueError("resume file is not a teacher checkpoint")
        if ck["ppo"] != ppo.as_dict():
            raise ValueError("resume checkpoint was trained with a different PPO configuration")
        if ck["receipt_sha256"] != receipt["receipt_sha256"]:
            raise ValueError("resume checkpoint belongs to a different start receipt (lower policy, rooms or plan differ)")
        actor.load_state_dict(ck["actor"]); critic.load_state_dict(ck["critic"]); log_std.data.copy_(ck["log_std"]); opt.load_state_dict(ck["optimizer"])
        it0, lr = int(ck["iteration"]), float(ck["lr"])
    n, T = env.n, ppo.num_steps_per_env
    obs = env.reset()
    saved = []
    for it in range(it0 + 1, it0 + iterations + 1):
        t0 = time.time()
        O, A, LP, V, R, D = [], [], [], [], [], []
        stats = {"task_reached": 0, "fell": 0, "task_fallback": 0, "task_new": 0, "task_winding": 0}
        with torch.no_grad():
            for _ in range(T):
                std = log_std.exp()
                mu = actor(obs)
                dist = torch.distributions.Normal(mu, std)
                a = dist.sample()
                v = critic(obs).squeeze(-1)
                nobs, r, d, to, info = env.step(a)
                # 시간 초과는 끝이 아니다: 다음 가치로 이어 받는다 (부트스트랩)
                r = r + ppo.gamma * v * to.float()
                O.append(obs), A.append(a), LP.append(dist.log_prob(a).sum(-1)), V.append(v), R.append(r), D.append(d.float())
                for k, v in info.items():
                    if k in stats or k.startswith(("term_", "fell_", "task_redraw", "table_")):
                        stats[k] = stats.get(k, 0) + v
                obs = nobs
            last_v = critic(obs).squeeze(-1)
        adv, gae = torch.zeros(T, n, device=device), torch.zeros(n, device=device)
        for t in reversed(range(T)):
            nv = last_v if t == T - 1 else V[t + 1]
            delta = R[t] + ppo.gamma * nv * (1 - D[t]) - V[t]
            gae = delta + ppo.gamma * ppo.lam * (1 - D[t]) * gae
            adv[t] = gae
        ret = adv + torch.stack(V)
        bO, bA, bLP = torch.stack(O).flatten(0, 1), torch.stack(A).flatten(0, 1), torch.stack(LP).flatten()
        bAdv, bRet = adv.flatten(), ret.flatten()
        bAdv = (bAdv - bAdv.mean()) / (bAdv.std() + 1e-8)
        total = bO.shape[0]
        mb = total // ppo.num_mini_batches
        for _ in range(ppo.num_learning_epochs):
            perm = torch.randperm(total, device=device)
            for k in range(ppo.num_mini_batches):
                idx = perm[k * mb:(k + 1) * mb]
                std = log_std.exp()
                dist = torch.distributions.Normal(actor(bO[idx]), std)
                lp = dist.log_prob(bA[idx]).sum(-1)
                ratio = (lp - bLP[idx]).exp()
                pg = -torch.min(ratio * bAdv[idx], ratio.clamp(1 - ppo.clip_param, 1 + ppo.clip_param) * bAdv[idx]).mean()
                vf = (critic(bO[idx]).squeeze(-1) - bRet[idx]).pow(2).mean()
                loss = pg + 0.5 * vf - ppo.entropy_coef * dist.entropy().sum(-1).mean()
                opt.zero_grad(); loss.backward()
                torch.nn.utils.clip_grad_norm_(params, ppo.max_grad_norm)
                opt.step()
            with torch.no_grad():       # 적응형 학습률: KL 이 목표의 두 배 넘으면 줄이고 절반 미만이면 키운다 (rsl-rl 방식)
                full = torch.distributions.Normal(actor(bO), log_std.exp())
                kl = (bLP - full.log_prob(bA).sum(-1)).mean().item()
            lr = max(1e-5, lr / 1.5) if kl > ppo.desired_kl * 2 else min(1e-2, lr * 1.5) if 0 < kl < ppo.desired_kl / 2 else lr
            for g in opt.param_groups:
                g["lr"] = lr
        stats.update(getattr(env, "take_nav_stats", lambda: {})())
        row = {"iteration": it, "reward_mean": float(torch.stack(R).mean()), "value_loss": float(vf), "kl": kl, "lr": lr,
               "noise_std": float(log_std.exp().mean()), "seconds": round(time.time() - t0, 2), **stats}
        log(json.dumps(row))
        if it % ppo.save_interval == 0:
            path = out / f"model_{it}.pt"
            if path.exists():
                raise FileExistsError(f"{path} exists (never overwritten)")
            torch.save({"format": CKPT_FORMAT, "iteration": it, "ppo": ppo.as_dict(), "receipt_sha256": receipt["receipt_sha256"], "lr": lr,
                        "actor": actor.state_dict(), "critic": critic.state_dict(), "log_std": log_std.data, "optimizer": opt.state_dict()}, path)
            saved.append(str(path))
    return it0 + iterations, saved
