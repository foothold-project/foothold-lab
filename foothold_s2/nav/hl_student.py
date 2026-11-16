"""HiPAN 모드 2 student (설계 §3 N4 · 21 §6 4 · 6): depth 180x320 -> CNN -> GRU -> (z_s, x_m 추정) -> MLP -> 명령 (vx vy wz). teacher 를 DAgger 로 흉내 낸다.

student 관측 = 전방 depth (n, 1, 180, 320) + o_p (45) + 최종 목표의 몸 틀 상대 위치 (2) (논문 526~531 행). teacher 의 잠재 z (32) 와 몸 속도 x_m (6) 은 라벨로만 쓴다.
논문이 값을 적지 않은 칸은 `ASSUMED` (영수증에 그대로 찍는다): 깊이 최대 거리 · 혼합 일정 · 데이터 크기 · 학습률 · 시퀀스 길이.
Kit 가 필요한 것은 `depth_camera_cfg` 뿐이다 (RayCasterCamera 180x320, 35 도 아래, 메시는 방의 벽 · 탁자 · 상자 포함): CPU 시험은 가짜 depth 로 한다.
메모리는 미측정: depth 는 float16 으로 쌓고 `max_rollouts` 개 이전 것부터 버린다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

DEPTH_H, DEPTH_W = 180, 320
CAMERA_PITCH_DEG = 35.0                  # J-C: D435i 한 대, 아래로 35 도 (장착 위치 · pitch 는 실측으로 교체)
NUM_ENVS = 128                           # 설계 §3 (논문 student 128 로봇)
ASSUMED = ("depth_max_m", "lr", "seq_len", "epochs", "batch_seqs", "rollout_steps", "max_rollouts", "beta0", "beta_decay", "gru_hidden", "w_z", "w_xm")


@dataclass(frozen=True)
class StudentCfg:
    num_envs: int = NUM_ENVS
    depth_max_m: float = 10.0
    lr: float = 3.0e-4
    seq_len: int = 16
    epochs: int = 2
    batch_seqs: int = 32
    rollout_steps: int = 32
    max_rollouts: int = 8
    beta0: float = 1.0                  # 첫 회는 teacher 가 몬다 (DAgger 혼합: 회마다 beta 를 줄인다)
    beta_decay: float = 0.7
    gru_hidden: int = 128
    w_z: float = 1.0
    w_xm: float = 1.0
    latent: int = 32
    action_dim: int = 3
    o_p: int = 45
    goal_dim: int = 2
    x_m: int = 6

    def as_dict(self) -> dict:
        return asdict(self)


def depth_camera_cfg(num_envs: int = NUM_ENVS, mesh_prim_paths=("/World/ground",)):
    """Kit 쪽에서만. RayCasterCamera 180x320. 부르는 쪽이 로봇 몸통 prim 경로 · 장착 위치를 채운다 (미확인: 이 cfg 는 Kit 에서 만들어 본 적 없음)."""
    from isaaclab.sensors import RayCasterCameraCfg, patterns

    return RayCasterCameraCfg(prim_path="{ENV_REGEX_NS}/Robot/base", mesh_prim_paths=list(mesh_prim_paths), update_period=0.1,
                              data_types=["distance_to_image_plane"],
                              pattern_cfg=patterns.PinholeCameraPatternCfg(focal_length=1.93, horizontal_aperture=3.68, height=DEPTH_H, width=DEPTH_W),
                              debug_vis=False)


def preprocess_depth(depth, max_m: float):
    """(n, H, W) 또는 (n, 1, H, W) -> (n, 1, H, W) 0..1 (inf · NaN 은 먼 쪽 1)."""
    import torch

    d = torch.as_tensor(depth, dtype=torch.float32)
    if d.dim() == 3:
        d = d.unsqueeze(1)
    if tuple(d.shape[-2:]) != (DEPTH_H, DEPTH_W):
        raise ValueError(f"depth must be {DEPTH_H}x{DEPTH_W}, got {tuple(d.shape[-2:])}")
    return torch.nan_to_num(d, nan=max_m, posinf=max_m, neginf=0.0).clamp(0, max_m) / max_m


def goal_in_body(goal_xy, pos_xy, yaw):
    from foothold_s2.nav.teacher_obs import subgoal_in_body

    return subgoal_in_body(pos_xy, yaw, goal_xy)


def build_student(cfg: StudentCfg | None = None):
    import torch
    from torch import nn

    cfg = cfg or StudentCfg()

    class Student(nn.Module):
        def __init__(self):
            super().__init__()
            self.cfg = cfg
            self.cnn = nn.Sequential(nn.Conv2d(1, 16, 5, 2, 2), nn.ELU(), nn.Conv2d(16, 32, 3, 2, 1), nn.ELU(), nn.Conv2d(32, 64, 3, 2, 1), nn.ELU(),
                                     nn.Conv2d(64, 64, 3, 2, 1), nn.ELU(), nn.AdaptiveAvgPool2d((2, 4)), nn.Flatten(), nn.Linear(512, 128), nn.ELU())
            prop = cfg.o_p + cfg.goal_dim
            self.gru = nn.GRUCell(128 + prop, cfg.gru_hidden)
            self.z_head = nn.Linear(cfg.gru_hidden, cfg.latent)
            self.xm_head = nn.Linear(cfg.gru_hidden, cfg.x_m)
            self.policy = nn.Sequential(nn.Linear(cfg.latent + cfg.x_m + prop, 128), nn.ELU(), nn.Linear(128, cfg.action_dim))

        def init_hidden(self, n, device=None):
            return torch.zeros(n, self.cfg.gru_hidden, device=device)

        def forward(self, depth, prop, h):
            """depth (n,1,H,W) 0..1 · prop (n, 47) · h (n, hidden) -> action (n,3), z (n,32), xm (n,6), h."""
            h = self.gru(torch.cat([self.cnn(depth), prop], dim=1), h)
            z, xm = self.z_head(h), self.xm_head(h)
            return self.policy(torch.cat([z, xm, prop], dim=1)), z, xm, h

    return Student()


class Aggregate:
    """DAgger 집합: 회마다 (T, n, ...) 한 덩이를 쌓고 `max_rollouts` 를 넘으면 가장 오래된 덩이를 버린다. depth 는 float16."""

    def __init__(self, max_rollouts: int):
        self.max, self.chunks = int(max_rollouts), []

    def add(self, chunk: dict) -> None:
        self.chunks.append(chunk)
        del self.chunks[:-self.max]

    def __len__(self) -> int:
        return sum(c["act"].shape[0] * c["act"].shape[1] for c in self.chunks)

    def sample(self, batch: int, seq_len: int, gen):
        """(batch) 개 시퀀스: 덩이 · env · 시작 시각을 무작위로. 돌려주는 값: dict (seq_len, batch, ...) . 끝남 표시 `done` 으로 GRU 상태를 끊는다."""
        import torch

        out = {k: [] for k in self.chunks[0]}
        for _ in range(batch):
            c = self.chunks[int(torch.randint(len(self.chunks), (1,), generator=gen))]
            T, n = c["act"].shape[:2]
            e, t0 = int(torch.randint(n, (1,), generator=gen)), int(torch.randint(max(T - seq_len, 0) + 1, (1,), generator=gen))
            for k, v in c.items():
                out[k].append(v[t0:t0 + seq_len, e])
        return {k: torch.stack(v, dim=1) for k, v in out.items()}


def beta_at(cfg: StudentCfg, iteration: int) -> float:
    return float(cfg.beta0 * cfg.beta_decay ** iteration)


class StudentEnv:
    """`TeacherVecEnv` 위에 student 관측을 얹는다. depth_fn() -> (n, H, W) 현재 depth (Kit 쪽: RayCasterCamera 출력). 끝난 env 의 depth 는 이미 새 에피소드 값이다 (GRU 는 done 에서 끊는다)."""

    def __init__(self, vec, depth_fn, cfg: StudentCfg | None = None):
        self.vec, self.depth_fn, self.cfg = vec, depth_fn, cfg or StudentCfg()
        self.n = vec.n

    def _obs(self, t_obs, done):
        import torch
        from foothold_s2.nav import teacher_obs as to

        lay = to.TeacherObsLayout()
        s, task = self.vec.state, self.vec.task
        org = None if task.origin_xy is None else np.asarray(task.origin_xy)
        pos = to.to_room_frame(s.pos_local, org)[:, :2]
        goal = torch.as_tensor(goal_in_body(task.goal, pos, to.yaw_from_quat_wxyz(s.quat_w)), dtype=torch.float32, device=t_obs.device)
        a, b = lay.offsets["o_p"]; c, d = lay.offsets["x_m"]
        return {"teacher": t_obs, "depth": preprocess_depth(self.depth_fn(), self.cfg.depth_max_m).to(t_obs.device),
                "prop": torch.cat([t_obs[:, a:b], goal], dim=1), "x_m": t_obs[:, c:d], "done": done}

    def reset(self):
        import torch

        t = self.vec.reset()
        return self._obs(t, torch.zeros(self.n, dtype=torch.bool, device=t.device))

    def step(self, action):
        t, _r, d, _to, _info = self.vec.step(action)
        return self._obs(t, d)


def rollout(env, o, teacher_act, student, cfg: StudentCfg, beta: float, gen, device="cpu"):
    """student (혼합 beta: 확률 beta 로 env 마다 teacher 행동을 쓴다) 로 `rollout_steps` 틱을 굴리고 teacher 라벨을 붙인다.
    env: `step(a) -> o` · o = dict(teacher (n, D), depth (n,1,H,W), prop (n, 47), done (n,) bool, x_m (n, 6)) .
    teacher_act(teacher_obs) -> (action (n,3), z (n,32)). 시작 관측 o 를 받는다. 돌려주는 값: (덩이 dict (T, n, ...), 마지막 o)."""
    import torch

    n = o["prop"].shape[0]
    h = student.init_hidden(n, device)
    rec = {k: [] for k in ("depth", "prop", "act", "z", "xm", "done")}
    for _ in range(cfg.rollout_steps):
        with torch.no_grad():
            t_act, t_z = teacher_act(o["teacher"])
            s_act, _z, _xm, h = student(o["depth"], o["prop"], h)
            use_teacher = torch.rand(n, generator=gen, device=device) < beta
            a = torch.where(use_teacher[:, None], t_act, s_act)
        rec["depth"].append(o["depth"].half()); rec["prop"].append(o["prop"]); rec["act"].append(t_act); rec["z"].append(t_z); rec["xm"].append(o["x_m"])
        o = env.step(a)
        rec["done"].append(o["done"].float())
        h = h * (1 - o["done"].float())[:, None]
    return {k: torch.stack(v) for k, v in rec.items()}, o


def fit(student, opt, agg: Aggregate, cfg: StudentCfg, gen, device="cpu") -> dict:
    """집합에서 시퀀스를 뽑아 teacher 라벨 (명령 · z · x_m) 을 따라가게 한다 (MSE). 시퀀스마다 GRU 상태는 0 에서 시작하고 끝남에서 끊는다."""
    import torch

    total = max(1, len(agg) // cfg.seq_len // max(1, cfg.batch_seqs))
    last = {}
    for _ in range(cfg.epochs * total):
        b = agg.sample(cfg.batch_seqs, cfg.seq_len, gen)
        h = student.init_hidden(b["act"].shape[1], device)
        la = lz = lx = 0.0
        loss = 0
        for t in range(b["act"].shape[0]):
            a, z, xm, h = student(b["depth"][t].float().to(device), b["prop"][t].to(device), h)
            ea, ez, ex = (a - b["act"][t]).pow(2).mean(), (z - b["z"][t]).pow(2).mean(), (xm - b["xm"][t]).pow(2).mean()
            loss = loss + ea + cfg.w_z * ez + cfg.w_xm * ex
            h = h * (1 - b["done"][t])[:, None]
            la, lz, lx = la + float(ea), lz + float(ez), lx + float(ex)
        loss = loss / b["act"].shape[0]
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0); opt.step()
        T = b["act"].shape[0]
        last = {"loss": float(loss), "act": la / T, "z": lz / T, "xm": lx / T}
    return last


def teacher_from_checkpoint(path, ppo, device="cpu"):
    """`hl_train` 체크포인트에서 teacher actor 를 불러 `teacher_act(obs) -> (평균 행동, 잠재 z)` 를 만든다."""
    import torch
    from foothold_s2.nav import hl_ppo_cfg as cfg, hl_train

    ck = torch.load(path, map_location=device, weights_only=False)
    if ck.get("format") != hl_train.CKPT_FORMAT:
        raise ValueError("not a teacher checkpoint")
    if ck["ppo"] != ppo.as_dict():
        raise ValueError("teacher checkpoint was trained with a different PPO configuration")
    actor, _critic = cfg.build_actor_critic(ppo)
    actor.load_state_dict(ck["actor"]); actor.to(device).eval()

    def act(obs):
        z = actor[0](obs)
        return actor[1:](z), z

    return act


def dagger(env, teacher_act, cfg: StudentCfg, *, iterations: int, seed: int = 0, device="cpu", student=None, opt=None, start_iteration: int = 0, log=print, after=None):
    """DAgger 바깥 고리: 회마다 (혼합 beta 로 굴리기 -> 집합에 쌓기 -> fit). 돌려주는 값: student · opt · 마지막 회 번호."""
    import json
    import torch

    gen = torch.Generator(device=device).manual_seed(seed)
    student = student or build_student(cfg).to(device)
    opt = opt or torch.optim.Adam(student.parameters(), lr=cfg.lr)
    agg = Aggregate(cfg.max_rollouts)
    o = env.reset()
    for it in range(start_iteration + 1, start_iteration + iterations + 1):
        beta = beta_at(cfg, it - 1)
        chunk, o = rollout(env, o, teacher_act, student, cfg, beta, gen, device)
        agg.add(chunk)
        stats = fit(student, opt, agg, cfg, gen, device)
        log(json.dumps({"iteration": it, "beta": round(beta, 4), **stats}))
        if after is not None:
            after(it, student, opt)
    return student, opt, start_iteration + iterations
