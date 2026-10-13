# -*- coding: utf-8 -*-
"""S2 A/B 입력 경로의 알려진 답 시험 T1 ~ T7 (CPU · Isaac 없이 · GPU 를 가림).

분류: A/정책학습 · S2 「이상적 지도 입력 비교」 A/B 입력 경로 1 단계 시험
작성: 오흥재 (lead 세션 · Claude 하위 작업 작성) · 2026-10-13 19:21
근거: inbox/jay/20261012-arch-discussion/DESIGN-s2-ab-v1.md 4 절 (T1 ~ T7) · E1 params/env.yaml 446 ~ 480 · agent.yaml
      IsaacLab observations.py height_scan · patterns.py grid_pattern · actor_critic_moe_cts.py · algorithms/moe_cts.py 297 ~ 334 (PPO 손실)
요지: 기대값은 s2_map_obs · s2_policy 를 부르지 않고 손으로 적는다 (구현을 복제한 시험이 되지 않게). 부모 동치는 시험이
      스스로 지은 ActorCriticMoECTS (손으로 적은 구조 · 실제 E1 model_20000 strict 적재) 의 act_inference 와 비트로 견준다.
상태: 시험 파일. 변이 (mutate_s2.py) 가 이 시험을 깨 본다

실행: CUDA_VISIBLE_DEVICES=-1 C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe test_s2.py [T1 T4 ...]
출력: 시험마다 「PASS Tn (k 칸) 설명」 또는 「FAIL Tn 설명: 사유」 한 줄. 끝에 SUMMARY. 하나라도 FAIL 이면 종료 코드 1.
      시험 대상 모듈은 이 파일과 같은 폴더의 s2_map_obs.py · s2_policy.py (변이 사본에서는 사본 폴더의 것).
"""
import os

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # torch 를 부르기 전에 GPU 를 가린다
import sys  # noqa: E402

sys.dont_write_bytecode = True  # 남의 폴더 (rsl_rl · IsaacLab) 에 pyc 를 쓰지 않는다
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp949 콘솔 · 로그에서 한글이 깨지지 않게

import contextlib  # noqa: E402
import copy  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import io  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402
import types  # noqa: E402

import torch  # noqa: E402

torch.set_num_threads(4)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s2_map_obs as M  # noqa: E402
import s2_policy as P  # noqa: E402

# ------------------------------------------------------------------ 손으로 적은 값 (파일을 열어 옮김 · 구현을 안 부른다)
E1_RUN = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192"
CKPT = E1_RUN + "/model_20000.pt"
ENV_YAML = E1_RUN + "/params/env.yaml"
# sha256sum 으로 잰 값 (2026-10-13 19:2x). 변이의 관문 자체 시험만 환경 변수로 바꾼다
PARENT_SHA256 = os.environ.get("S2_EXPECT_PARENT_SHA256", "c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8")
PARENT_LAST_LR = 0.00017085937500000009   # model_20000.pt optimizer_state_dict param_groups[*].lr (네 묶음 같음)
ISAACLAB_PATTERNS = "C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/patterns/patterns.py"
ISAACLAB_OBS = "C:/isaac/IsaacLab/source/isaaclab/isaaclab/envs/mdp/observations.py"
N_POL, N_CRIT, N_SINGLE, N_ACT, N_LAT = 450, 275, 45, 12, 32     # 체크포인트 가중치 모양에서 (student 450 · critic 307-32 · actor 77-32)
R, MAPD = 187, 374
FRONT = [k for k in range(187) if k % 17 >= 9]                    # 몸 앞쪽 x >= 0.1 (x 가 가장 빨리 도는 17 x 11)
# PPO 손실 값 (E1 agent.yaml algorithm)
CLIP, VALUE_COEF, ENTROPY_COEF, MAX_GRAD_NORM = 0.2, 1.0, 0.01, 1.0
NEW_KEYS = {"map_encoder.network.0.weight", "map_encoder.network.0.bias", "map_encoder.network.2.weight",
            "map_encoder.network.2.bias", "actor_in_map.weight"}
STUDENT_PREFIX = "student_moe_encoder."
MAPENC_PREFIX = "map_encoder."


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


SHA_BEFORE = sha256(CKPT)   # 모든 시험 전
TESTS = []


def test(tid, desc):
    def deco(fn):
        TESTS.append((tid, desc, fn))
        return fn
    return deco


class Cells:
    """한 시험의 칸들. 실패해도 다음 칸을 이어 본다 (변이가 어느 칸에서 걸렸는지 보이게)."""

    def __init__(self):
        self.n = 0
        self.fail = []

    def ok(self, cond, what):
        self.n += 1
        if not bool(cond):
            self.fail.append(str(what))

    def done(self):
        if self.fail:
            raise AssertionError(f"{len(self.fail)}/{self.n} 칸 실패: " + " | ".join(self.fail[:8]))


def bits_equal(a, b):
    return (a.shape == b.shape and a.dtype == b.dtype == torch.float32
            and torch.equal(a.contiguous().view(torch.int32), b.contiguous().view(torch.int32)))


def close(a, b, atol=1e-6):
    b = torch.as_tensor(b, dtype=a.dtype).expand_as(a)
    return bool(torch.allclose(a, b, atol=atol, rtol=0.0))


# ------------------------------------------------------------------ 부모 (시험이 스스로 짓는다)
_REF = {}


def ref_parent():
    """손으로 적은 구조 (E1 agent.yaml) 로 ActorCriticMoECTS 를 짓고 model_20000 을 strict 로 읽는다. 한 번만."""
    if "m" not in _REF:
        from tensordict import TensorDict
        from rsl_rl.modules.actor_critic_moe_cts import ActorCriticMoECTS
        obs = TensorDict({"policy": torch.zeros(1, N_POL), "critic": torch.zeros(1, N_CRIT), "single_obs": torch.zeros(1, N_SINGLE)},
                         batch_size=[1])
        with contextlib.redirect_stdout(io.StringIO()):
            m = ActorCriticMoECTS(obs, {"policy": ["policy"], "critic": ["critic"]}, N_ACT,
                                  actor_hidden_dims=[512, 256, 128], critic_hidden_dims=[512, 256, 128],
                                  teacher_encoder_hidden_dims=[512, 256], student_encoder_hidden_dims=[512, 256, 256],
                                  expert_num=8, activation="elu", init_noise_std=1.0, noise_std_type="scalar",
                                  state_dependent_std=False, latent_dim=N_LAT, norm_type="l2norm",
                                  actor_obs_normalization=False, critic_obs_normalization=False)
        sd = torch.load(CKPT, map_location="cpu", weights_only=True)["model_state_dict"]
        m.load_state_dict(sd, strict=True)   # 열쇠 · 모양이 하나라도 다르면 여기서 예외
        m.eval()
        _REF["m"] = m
    return _REF["m"]


def file_state_dict():
    return torch.load(CKPT, map_location="cpu", weights_only=True)["model_state_dict"]


def make_obs(n, seed, m=None):
    from tensordict import TensorDict
    g = torch.Generator().manual_seed(seed)
    d = {"policy": torch.randn(n, N_POL, generator=g), "single_obs": torch.randn(n, N_SINGLE, generator=g),
         "critic": torch.randn(n, N_CRIT, generator=g)}
    if m is not None:
        d["map"] = m
    return TensorDict(d, batch_size=[n])


def with_map(obs, m):
    o = obs.clone()
    o["map"] = m
    return o


def random_b_map(n, seed):
    """손으로 만든 B 꼴 지도: height U(-1, 1) · mask 70 % 1 · mask 0 칸은 height 1."""
    g = torch.Generator().manual_seed(seed)
    h = torch.rand(n, R, generator=g) * 2 - 1
    mk = (torch.rand(n, R, generator=g) < 0.7).float()
    h = torch.where(mk > 0, h, torch.ones_like(h))
    return torch.cat([h, mk], dim=-1)


def random_pose(n, seed):
    g = torch.Generator().manual_seed(seed)
    pos = torch.cat([torch.rand(n, 2, generator=g) * 10 - 5, 0.30 + 0.15 * torch.rand(n, 1, generator=g)], dim=-1)
    yaw = (torch.rand(n, generator=g) * 2 - 1) * math.pi
    return pos, yaw


def terrain_flat(x, y):
    return torch.zeros_like(x)


def terrain_rough(x, y):
    """단 (0.3 m 마다 0 / 0.12 m) · 구멍 (inf · 안 맞음) · 깊은 구덩이 (-2 m)."""
    z = 0.12 * (torch.floor(x / 0.3).remainder(2))
    cell = (torch.floor(x / 0.2) + 3 * torch.floor(y / 0.2)).remainder(7)
    z = torch.where(cell == 0, torch.full_like(z, math.inf), z)
    z = torch.where(cell == 3, torch.full_like(z, -2.0), z)
    return z


# ------------------------------------------------------------------ PPO 손실 모양 (algorithms/moe_cts.py 297 ~ 334 · agent.yaml 값)
def rollout(pol, obs, seed):
    g = torch.Generator().manual_seed(seed)
    with torch.no_grad():
        pol.act(obs)
        mu = pol.action_mean.clone()
        sigma = pol.action_std.clone()
        actions = mu + sigma * torch.randn(mu.shape, generator=g)
        old_logp = pol.get_actions_log_prob(actions).clone()
        values = pol.evaluate(obs).clone()
    n = mu.shape[0]
    return {"actions": actions, "old_logp": old_logp, "values": values,
            "adv": torch.randn(n, generator=g), "returns": values + torch.randn(n, 1, generator=g)}


def ppo_like_loss(pol, obs, b):
    pol.act(obs)
    logp = pol.get_actions_log_prob(b["actions"])
    value = pol.evaluate(obs)
    entropy = pol.entropy
    ratio = torch.exp(logp - b["old_logp"])
    surrogate = torch.max(-b["adv"] * ratio, -b["adv"] * torch.clamp(ratio, 1.0 - CLIP, 1.0 + CLIP)).mean()
    v_clipped = b["values"] + (value - b["values"]).clamp(-CLIP, CLIP)
    value_loss = torch.max((value - b["returns"]).pow(2), (v_clipped - b["returns"]).pow(2)).mean()
    return surrogate + VALUE_COEF * value_loss - ENTROPY_COEF * entropy.mean()


def grads(pol):
    return {k: p.grad for k, p in pol.named_parameters()}


def nz(t):
    return 0 if t is None else int(torch.count_nonzero(t))


# =========================================================================== T1
@test("T1", "평지: 센서 0.4 m · 맞은 점 0 -> height -0.1 · mask 1 (187 칸 모두) · 배치 [height, mask] · 센서 기준 (세계 높이 · xy 무관) · A 는 0")
def t1(c):
    src = open(ISAACLAB_OBS, encoding="utf-8").read()
    c.ok("def height_scan(env: ManagerBasedEnv, sensor_cfg: SceneEntityCfg, offset: float = 0.5)" in src, "IsaacLab height_scan offset 기본 0.5")
    c.ok("return sensor.data.pos_w[:, 2].unsqueeze(1) - sensor.data.ray_hits_w[..., 2] - offset" in src, "IsaacLab height_scan 식")
    g = torch.Generator().manual_seed(1)
    pos = torch.tensor([[0.0, 0.0, 0.4], [3.0, -2.0, 10.4], [-5.0, 7.0, 0.4]])
    hits = torch.zeros(3, R, 3)
    hits[..., 0:2] = torch.rand(3, R, 2, generator=g) * 20 - 10      # 맞은 점 xy 는 height 와 무관해야 함
    hits[1, :, 2] = 10.0                                              # 세계 높이 10 m 에 선 env
    h, mk = M.height_and_mask(pos, hits)
    c.ok(tuple(h.shape) == (3, R) and tuple(mk.shape) == (3, R), f"모양 {tuple(h.shape)} {tuple(mk.shape)}")
    c.ok(close(h, -0.1), f"height -0.1 이어야 함: {h.min().item():.6f} ~ {h.max().item():.6f}")
    c.ok(torch.equal(mk, torch.ones(3, R)), f"mask 1 이어야 함: 0 인 칸 {int((mk == 0).sum())}")
    mo = M.map_obs_b(pos, hits)
    c.ok(tuple(mo.shape) == (3, MAPD), f"map_obs_b 모양 {tuple(mo.shape)}")
    c.ok(close(mo[:, :R], -0.1) and torch.equal(mo[:, R:], torch.ones(3, R)), "배치 [height 0~186, mask 187~373]")
    c.ok(torch.equal(M.map_obs("B", pos, hits), mo), "map_obs('B') == map_obs_b")
    c.ok(torch.equal(M.map_obs("A", pos, hits), torch.zeros(3, MAPD)), "A 는 height 0 · mask 0")
    c.ok(M.MAP_DIM == 374 and M.NUM_RAYS == 187, f"MAP_DIM {M.MAP_DIM} · NUM_RAYS {M.NUM_RAYS}")


# =========================================================================== T2
@test("T2", "단차 · 구멍: 앞쪽 절반 +0.1 m -> 그 칸만 -0.2 · inf/nan/-inf -> mask 0 · height 1 · 깊이 2 m -> mask 0 · 1 m 경계 · 벽 clip -1 · yaw")
def t2(c):
    pos = torch.tensor([[0.0, 0.0, 0.4]])
    hits = torch.zeros(1, R, 3)
    hits[0, FRONT, 2] = 0.1
    hits[0, 0, :] = math.inf          # 안 맞음 (raycast_mesh 꼴: xyz 모두 inf)
    hits[0, 18, 2] = math.nan
    hits[0, 36, 2] = -math.inf
    hits[0, 2, 2] = -2.0              # 깊이 2 m 구멍 바닥 (센서 아래 2.4 m)
    hits[0, 4, 2] = -0.5              # 센서 아래 0.9 m -> mask 1 · height 0.4
    hits[0, 6, 2] = -0.7              # 센서 아래 1.1 m -> mask 0 · height 1
    hits[0, 20, 2] = 1.5              # 센서보다 1.1 m 위 (벽) -> mask 1 · height clip -1
    h, mk = M.height_and_mask(pos, hits)
    exp_h = torch.full((1, R), -0.1)
    exp_h[0, FRONT] = -0.2
    exp_h[0, [0, 18, 36, 2, 6]] = 1.0
    exp_h[0, 4] = 0.4
    exp_h[0, 20] = -1.0
    exp_m = torch.ones(1, R)
    exp_m[0, [0, 18, 36, 2, 6]] = 0.0
    c.ok(len(FRONT) == 88, f"앞쪽 광선 수 {len(FRONT)}")
    c.ok(bool(torch.isfinite(h).all()), "height 에 inf · nan 이 남지 않음")
    c.ok(close(h, exp_h), f"height 칸별 대조 · 최대 차 {(h - exp_h).abs().nan_to_num(99.0).max().item():.6f}")
    c.ok(close(h[0, FRONT], -0.2) and close(h[0, [k for k in range(R) if k % 17 <= 7 and k not in (0, 18, 36, 2, 4, 6, 20)]], -0.1),
         "단 위 칸만 -0.2 · 나머지 평지 -0.1")
    c.ok(torch.equal(mk, exp_m), f"mask 칸별 대조 · mask 0 위치 {torch.nonzero(mk[0] == 0).flatten().tolist()}")
    c.ok(set(torch.unique(mk).tolist()) <= {0.0, 1.0}, f"mask 값 {torch.unique(mk).tolist()}")
    c.ok(int((mk == 0).sum()) == 5, f"mask 0 칸 수 {int((mk == 0).sum())} (5 이어야 함)")
    mo = M.map_obs_b(pos, hits)
    c.ok(torch.equal(mo[:, R:], exp_m) and close(mo[:, :R], exp_h), "map_obs_b 에도 같은 값")
    # yaw 정렬 (시험용 RayCaster 흉내): 몸 앞쪽 (x > 0.05) 광선이 세계의 어느 쪽을 보는가
    for yaw, step in ((0.0, lambda x, y: torch.where(x - 1.0 > 0.05, 0.1, 0.0)),
                      (math.pi / 2, lambda x, y: torch.where(y - 2.0 > 0.05, 0.1, 0.0)),
                      (-math.pi / 2, lambda x, y: torch.where(2.0 - y > 0.05, 0.1, 0.0))):
        p = torch.tensor([[1.0, 2.0, 0.4]])
        hh, mm = M.height_and_mask(p, M.ray_hits_from_terrain(p, torch.tensor([yaw]), step))
        c.ok(close(hh[0, FRONT], -0.2) and close(hh[0, [k for k in range(R) if k % 17 < 9]], -0.1) and torch.equal(mm, torch.ones(1, R)),
             f"yaw {yaw:+.3f}: 앞쪽 88 광선만 -0.2")
    p = torch.tensor([[1.0, 2.0, 0.4]])
    hh, mm = M.height_and_mask(p, M.ray_hits_from_terrain(p, torch.tensor([math.pi]),
                                                          lambda x, y: torch.where(1.0 - x > 0.05, math.inf, 0.0)))
    c.ok(torch.equal(mm[0, FRONT], torch.zeros(88)) and close(hh[0, FRONT], 1.0) and int(mm.sum()) == R - 88,
         "yaw pi: 몸 앞쪽 (세계 -x) 구멍 -> 앞쪽 88 광선 mask 0 · height 1")


# =========================================================================== T3
@test("T3", "광선 순서: grid xy (x 가 가장 빨리) · 0 · 1 · 16 · 17 · 93 · 186 번의 몸체 좌표가 손 계산 · IsaacLab grid_pattern (CPU) 과 같음 · env.yaml 설정 · 순서 보존")
def t3(c):
    hand = {0: (-0.8, -0.5), 1: (-0.7, -0.5), 16: (0.8, -0.5), 17: (-0.8, -0.4), 93: (0.0, 0.0), 186: (0.8, 0.5)}
    gb = M.grid_ray_xy_body()
    c.ok(tuple(gb.shape) == (R, 2), f"grid_ray_xy_body 모양 {tuple(gb.shape)}")
    for k, xy in hand.items():
        c.ok(close(gb[k], torch.tensor(xy)), f"광선 {k}: {gb[k].tolist()} != {xy}")
    sp = importlib.util.spec_from_file_location("isaaclab_patterns_cpu", ISAACLAB_PATTERNS)
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    cfg = types.SimpleNamespace(size=(1.6, 1.0), resolution=0.1, ordering="xy", direction=(0.0, 0.0, -1.0))
    starts, dirs = mod.grid_pattern(cfg, "cpu")
    c.ok(tuple(starts.shape) == (R, 3), f"IsaacLab grid_pattern 광선 수 {tuple(starts.shape)}")
    for k, xy in hand.items():
        c.ok(close(starts[k, :2], torch.tensor(xy)), f"IsaacLab 광선 {k}: {starts[k, :2].tolist()} != {xy}")
    c.ok(torch.equal(gb, starts[:, :2]), "grid_ray_xy_body == IsaacLab grid_pattern (187 광선 모두 비트 동일)")
    c.ok(torch.equal(dirs, torch.tensor([0.0, 0.0, -1.0]).expand(R, 3)), "광선 방향 아래")
    # env.yaml (학습 때 쓴 설정) 과 상수 대조
    txt = open(ENV_YAML, encoding="utf-8").read()
    blk = txt[txt.index("\n  height_scanner:\n"):txt.index("\n  height_scanner_small:")]
    for pat in (r"prim_path: /World/envs/env_\.\*/Robot/base\n", r"offset:\n      pos: !!python/tuple\n      - 0\.0\n      - 0\.0\n      - 20\.0\n",
                r"ray_alignment: yaw\n", r"resolution: 0\.1\n", r"size:\n      - 1\.6\n      - 1\.0\n", r"ordering: xy\n",
                r"drift_range: !!python/tuple\n    - 0\.0\n    - 0\.0\n",
                r"ray_cast_drift_range:\n      x: !!python/tuple\n      - 0\.0\n      - 0\.0\n      y: !!python/tuple\n      - 0\.0\n      - 0\.0\n"
                r"      z: !!python/tuple\n      - 0\.0\n      - 0\.0\n"):
        c.ok(re.search(pat, blk) is not None, f"env.yaml height_scanner 에 {pat!r} 없음")
    c.ok(M.GRID_SIZE == (1.6, 1.0) and M.GRID_RESOLUTION == 0.1 and M.GRID_ORDERING == "xy",
         f"s2_map_obs 상수 {M.GRID_SIZE} {M.GRID_RESOLUTION} {M.GRID_ORDERING}")
    # 순서 보존: 광선 k 의 맞은 점 z = 0.001 k -> height[k] = 0.4 - 0.001 k - 0.5 · 광선 17 만 안 맞음 -> mask 칸 187 + 17 만 0
    pos = torch.tensor([[0.0, 0.0, 0.4]])
    hits = torch.zeros(1, R, 3)
    hits[0, :, 2] = torch.arange(R, dtype=torch.float32) * 0.001
    hits[0, 17, :] = math.inf
    mo = M.map_obs_b(pos, hits)
    exp = -0.1 - 0.001 * torch.arange(R, dtype=torch.float32)
    exp[17] = 1.0
    c.ok(close(mo[0, :R], exp), f"height 순서 보존 · 최대 차 {(mo[0, :R] - exp).abs().max().item():.2e}")
    em = torch.ones(R)
    em[17] = 0.0
    c.ok(torch.equal(mo[0, R:], em), f"mask 순서 보존 · 0 위치 {torch.nonzero(mo[0, R:] == 0).flatten().tolist()}")


# =========================================================================== T4
@test("T4", "0 초기화 동치: 실제 E1 model_20000 CPU strict · 무작위 이력 · 무작위 지도에서 B · A 의 action 이 부모 act_inference 와 비트 동일 · 대조군 (새 열 0.01) 은 지도에 따라 바뀜")
def t4(c):
    ref = ref_parent()
    sd = file_state_dict()
    # s2_policy 의 적재기도 같은 부모를 만드는가 (strict · 차원 · lr)
    p2, meta = P.load_parent_cpu(CKPT)
    s2p = p2.state_dict()
    c.ok(set(s2p) == set(sd) and all(torch.equal(s2p[k], sd[k]) for k in sd), "load_parent_cpu 의 부모 == 파일")
    c.ok(meta["dims"] == {"policy": N_POL, "critic": N_CRIT, "single_obs": N_SINGLE, "actions": N_ACT, "latent": N_LAT}, f"dims {meta['dims']}")
    c.ok(meta["last_lr"] == PARENT_LAST_LR and meta["iter"] == 20000, f"last_lr {meta['last_lr']} · iter {meta['iter']}")
    B = P.S2MapActorCritic(ref, "B").eval()
    A = P.S2MapActorCritic(ref, "A").eval()
    # 구조
    c.ok(tuple(B.actor_in_map.weight.shape) == (512, 64) and nz(B.actor_in_map.weight) == 0, "새 64 열 [512, 64] 이 모두 0")
    W = B.actor_first_layer_weight()
    c.ok(tuple(W.shape) == (512, 141) and torch.equal(W[:, :77], sd["actor.network.0.weight"]) and nz(W[:, 77:]) == 0,
         "actor 첫 층 [512, 141] = [부모 77 열 | 0 64 열]")
    c.ok(torch.equal(B.actor_in.bias, sd["actor.network.0.bias"]), "첫 층 bias 부모 값")
    me = dict(B.map_encoder.named_parameters())
    c.ok({k: tuple(v.shape) for k, v in me.items()} == {"network.0.weight": (128, 374), "network.0.bias": (128,),
                                                          "network.2.weight": (64, 128), "network.2.bias": (64,)},
         f"map encoder 374 -> 128 -> 64: {[(k, tuple(v.shape)) for k, v in me.items()]}")
    c.ok(isinstance(B.map_encoder.network[1], torch.nn.ELU) and len(B.map_encoder.network) == 3, "map encoder ELU 한 겹 · 출력 선형")
    sa, sb = A.state_dict(), B.state_dict()
    c.ok(set(sa) == set(sb) and all(torch.equal(sa[k], sb[k]) for k in sa), "A · B 의 state_dict 가 열쇠 · 값 모두 같음 (같은 출발점)")
    # 동치
    N = 256
    obs = make_obs(N, 1)
    pos, yaw = random_pose(N, 2)
    terr_map = torch.cat(M.height_and_mask(pos, M.ray_hits_from_terrain(pos, yaw, terrain_rough)), dim=-1)
    maps = {"무작위 1": random_b_map(N, 3), "무작위 2": random_b_map(N, 4), "거친 지형": terr_map,
            "큰 값": torch.randn(N, MAPD, generator=torch.Generator().manual_seed(5)) * 100.0}
    with torch.no_grad():
        a_ref = ref.act_inference(obs)
        for name, m in maps.items():
            c.ok(bits_equal(B.act_inference(with_map(obs, m)), a_ref), f"B ({name}) action 이 부모와 비트 동일")
        c.ok(bits_equal(A.act_inference(with_map(obs, torch.zeros(N, MAPD))), a_ref), "A action 이 부모와 비트 동일")
        ref.act(obs, is_teacher=False)
        mu_r, sd_r = ref.action_mean.clone(), ref.action_std.clone()
        B.act(with_map(obs, maps["무작위 1"]))
        c.ok(bits_equal(B.action_mean, mu_r) and bits_equal(B.action_std, sd_r), "act() 분포 평균 · std 가 부모와 비트 동일")
        v_r = ref.evaluate(obs, is_teacher=False)
        c.ok(bits_equal(B.evaluate(with_map(obs, maps["무작위 1"])), v_r), "evaluate (critic) 가 부모 is_teacher=False 와 비트 동일")
    # 대조군: 새 열에 작은 값 -> B 의 action 이 지도에 따라 바뀜 (위 비트 동일이 헛돌지 않음을 보임)
    Bc = copy.deepcopy(B)
    with torch.no_grad():
        Bc.actor_in_map.weight.copy_(0.01 * torch.randn(512, 64, generator=torch.Generator().manual_seed(6)))
        a1 = Bc.act_inference(with_map(obs, maps["무작위 1"]))
        a2 = Bc.act_inference(with_map(obs, maps["무작위 2"]))
    d12 = (a1 - a2).abs().max().item()
    d1p = (a1 - a_ref).abs().max().item()
    c.ok(d12 > 1e-5, f"대조군: 지도 1 vs 2 action 최대 차 {d12:.3e} (> 1e-5 이어야 함)")
    c.ok(d1p > 1e-5, f"대조군: 부모 대비 최대 차 {d1p:.3e} (> 1e-5 이어야 함)")
    print(f"    T4 대조군 action 최대 차: 지도 1 vs 2 = {d12:.3e} · 부모 대비 = {d1p:.3e}", flush=True)


# =========================================================================== T5
@test("T5", "gradient 경로 (PPO 손실 모양 · 한 번 갱신): 갱신 전 새 열 gradient 있음 · map encoder 0 · student encoder 있음 (no_grad 풀림) · 갱신 뒤 B map encoder 0 아님 · A 첫 층 weight 0 (bias 아님)")
def t5(c):
    ref = ref_parent()
    N = 256
    obs0 = make_obs(N, 11)
    pos, yaw = random_pose(N, 12)
    hits = M.ray_hits_from_terrain(pos, yaw, terrain_rough)
    hits2 = M.ray_hits_from_terrain(pos, yaw, terrain_flat)
    for mode in ("B", "A"):
        pol = P.S2MapActorCritic(ref, mode).train()
        opt = P.make_optimizer(pol, lr=PARENT_LAST_LR, betas=(0.9, 0.999))
        ids_opt = [id(p) for g in opt.param_groups for p in g["params"]]
        c.ok(len(ids_opt) == len(set(ids_opt)) and set(ids_opt) == {id(p) for p in pol.parameters()},
             f"{mode}: optimizer 가 모든 매개변수를 한 번씩 덮음 ({len(ids_opt)} vs {len(list(pol.parameters()))})")
        c.ok(all(g["lr"] == PARENT_LAST_LR for g in opt.param_groups), f"{mode}: lr 이 부모 마지막 값")
        obs = with_map(obs0, M.map_obs(mode, pos, hits))
        b = rollout(pol, obs, seed=13)
        opt.zero_grad(set_to_none=True)
        ppo_like_loss(pol, obs, b).backward()
        g = grads(pol)
        stu = [k for k in g if k.startswith(STUDENT_PREFIX)]
        men = [k for k in g if k.startswith(MAPENC_PREFIX)]
        c.ok(len(stu) == 16 and len(men) == 4, f"{mode}: 매개변수 수 student {len(stu)} · map encoder {len(men)}")
        c.ok(nz(g["actor_in_map.weight"]) > 0, f"{mode} 갱신 전: 새 열 gradient 0 아닌 원소 {nz(g['actor_in_map.weight'])}")
        c.ok(all(g[k] is not None for k in men), f"{mode} 갱신 전: map encoder 가 계산 그래프에 있음 (grad None 없음)")
        c.ok(all(nz(g[k]) == 0 for k in men), f"{mode} 갱신 전: map encoder gradient 0 이어야 함 {[(k, nz(g[k])) for k in men]}")
        c.ok(all(g[k] is not None and nz(g[k]) > 0 for k in stu),
             f"{mode} 갱신 전: student encoder gradient 가 매개변수마다 있음 (no_grad 풀림) {[(k, nz(g[k])) for k in stu if nz(g[k]) == 0][:3]}")
        c.ok(nz(g["std"]) > 0 and nz(g["actor_in.weight"]) > 0, f"{mode} 갱신 전: std · actor 첫 층 gradient 있음")
        c.ok(all(nz(v) > 0 for k, v in g.items() if k.startswith("critic.")), f"{mode} 갱신 전: critic gradient 있음")
        torch.nn.utils.clip_grad_norm_(pol.parameters(), MAX_GRAD_NORM)
        opt.step()
        c.ok(nz(pol.actor_in_map.weight) > 0, f"{mode}: 한 번 갱신 뒤 새 열이 0 이 아님 ({nz(pol.actor_in_map.weight)} 원소)")
        opt.zero_grad(set_to_none=True)
        ppo_like_loss(pol, obs, b).backward()
        g = grads(pol)
        if mode == "B":
            c.ok(all(g[k] is not None and nz(g[k]) > 0 for k in men),
                 f"B 갱신 뒤: map encoder gradient 가 매개변수마다 0 아님 {[(k, nz(g[k])) for k in men]}")
            with torch.no_grad():
                d = (pol.act_inference(obs) - pol.act_inference(with_map(obs0, M.map_obs("B", pos, hits2)))).abs().max().item()
            c.ok(d > 0.0, f"B 갱신 뒤: 지도를 바꾸면 action 이 바뀜 (최대 차 {d:.3e})")
            print(f"    T5 B 갱신 뒤 지도 바꿈 action 최대 차 {d:.3e}", flush=True)
        else:
            c.ok(g["map_encoder.network.0.weight"] is not None and nz(g["map_encoder.network.0.weight"]) == 0,
                 f"A 갱신 뒤: map encoder 첫 층 weight gradient 0 이어야 함 ({nz(g['map_encoder.network.0.weight'])})")
            c.ok(nz(g["map_encoder.network.0.bias"]) > 0 and nz(g["map_encoder.network.2.weight"]) > 0,
                 "A 갱신 뒤: 첫 층 bias · 둘째 층 weight gradient 는 0 아님")
    # critic 손실만: student encoder 로 안 감 (부모 evaluate 의 latent.detach 와 같음) · critic 에 지도 없음
    pol = P.S2MapActorCritic(ref, "B").train()
    obs = with_map(obs0, M.map_obs("B", pos, hits))
    pol.evaluate(obs).pow(2).mean().backward()
    g = grads(pol)
    c.ok(all(nz(g[k]) == 0 for k in g if k.startswith(STUDENT_PREFIX)), "value 손실만: student encoder gradient 0 (latent.detach)")
    c.ok(all(g[k] is None for k in g if k.startswith(MAPENC_PREFIX)) and g["actor_in_map.weight"] is None, "value 손실만: 지도 경로 gradient 없음")
    c.ok(all(nz(g[k]) > 0 for k in g if k.startswith("critic.")), "value 손실만: critic gradient 있음")


# =========================================================================== T6
@test("T6", "A 의 정보 차단: A 에서 실제 지형 (평지 vs 단 · 구멍 · 구덩이) 을 바꿔도 policy 입력 · action 이 안 바뀜 (새 열 0 아님에서도) · B 는 바뀜 · A 에 실제 지도를 넣으면 거부")
def t6(c):
    ref = ref_parent()
    N = 128
    pos, yaw = random_pose(N, 21)
    h_flat = M.ray_hits_from_terrain(pos, yaw, terrain_flat)
    h_rough = M.ray_hits_from_terrain(pos, yaw, terrain_rough)
    h_holes = h_flat.clone()
    h_holes[:, ::3, :] = math.inf                     # 직접 넣은 구멍 (안 맞음)
    mb = {k: M.map_obs("B", pos, h) for k, h in (("flat", h_flat), ("rough", h_rough), ("holes", h_holes))}
    c.ok(int((mb["rough"][:, R:] == 0).sum()) > 0 and int((mb["holes"][:, R:] == 0).sum()) > 0 and not torch.equal(mb["flat"], mb["rough"]),
         "시험 지형이 실제로 다름 (B 지도에 mask 0 · 값 차이)")
    ma = {k: M.map_obs("A", pos, h) for k, h in (("flat", h_flat), ("rough", h_rough), ("holes", h_holes))}
    for k, m in ma.items():
        c.ok(torch.equal(m, torch.zeros(N, MAPD)), f"A 지도 입력 ({k}) == 0 (height 0 · mask 0) · 0 아닌 원소 {nz(m)}")
    A = P.S2MapActorCritic(ref, "A").eval()
    B = P.S2MapActorCritic(ref, "B").eval()
    w = 0.01 * torch.randn(512, 64, generator=torch.Generator().manual_seed(22))
    with torch.no_grad():
        A.actor_in_map.weight.copy_(w)
        B.actor_in_map.weight.copy_(w)
    obs = make_obs(N, 23)
    with torch.no_grad():
        aa = {k: A.act_inference(with_map(obs, m)) for k, m in ma.items()}
        ab = {k: B.act_inference(with_map(obs, m)) for k, m in mb.items()}
    c.ok(bits_equal(aa["flat"], aa["rough"]) and bits_equal(aa["flat"], aa["holes"]), "A action 이 지형과 상관없이 비트 동일")
    d = (ab["flat"] - ab["rough"]).abs().max().item()
    c.ok(d > 1e-5, f"B action 은 지형에 따라 바뀜 (평지 vs 거친 지형 최대 차 {d:.3e})")
    d2 = (ab["flat"] - ab["holes"]).abs().max().item()
    c.ok(d2 > 1e-5, f"B action 은 구멍 (mask) 에 따라 바뀜 (최대 차 {d2:.3e})")
    for k in ("rough", "holes"):
        try:
            with torch.no_grad():
                A.act_inference(with_map(obs, mb[k]))
            raised = False
        except ValueError:
            raised = True
        c.ok(raised, f"A 정책에 B 지도 ({k}) 를 넣으면 ValueError")


# =========================================================================== T7
@test("T7", "부모 보존: 체크포인트 sha256 이 시험 전후 같음 (손으로 적은 값) · 부모 state_dict 키 · 값이 복사본과 같음 · S2 갱신 뒤에도 부모 그대로 · 저장소 공유 없음")
def t7(c):
    ref = ref_parent()
    sd = file_state_dict()
    # S2 를 짓고 큰 lr 로 한 번 갱신해도 부모 모듈이 파일과 같은가
    pol = P.S2MapActorCritic(ref, "B").train()
    opt = P.make_optimizer(pol, lr=1e-2)
    obs = with_map(make_obs(64, 31), random_b_map(64, 32))
    before = {k: v.detach().clone() for k, v in pol.state_dict().items()}
    ppo_like_loss(pol, obs, rollout(pol, obs, 33)).backward()
    opt.step()
    moved = [k for k, v in pol.state_dict().items() if not torch.equal(v, before[k])]
    c.ok(any(k.startswith("actor_in.") for k in moved) and any(k.startswith("critic.") for k in moved)
         and any(k.startswith(STUDENT_PREFIX) for k in moved) and "std" in moved, f"S2 갱신이 실제로 일어남 (바뀐 열쇠 {len(moved)})")
    rs = ref.state_dict()
    c.ok(set(rs) == set(sd), "부모 모듈 열쇠 == 파일 열쇠")
    diff = [k for k in sd if not torch.equal(rs[k], sd[k])]
    c.ok(not diff, f"부모 모듈 값 == 파일 값 (T4 ~ T6 과 이 갱신 뒤) · 다른 열쇠 {diff[:4]}")
    pptr = {t.data_ptr() for t in ref.state_dict().values()}
    shared = [k for k, p in pol.named_parameters() if p.data_ptr() in pptr]
    c.ok(not shared, f"S2 매개변수가 부모와 저장소를 나누지 않음 · 나누는 것 {shared[:4]}")
    # 복사본 == 부모 (손으로 적은 열쇠 대응)
    fresh = P.S2MapActorCritic(ref, "B").state_dict()

    def s2_key(k):
        if k.startswith("teacher_encoder."):
            return None
        if k.startswith("actor.network.0."):
            return "actor_in." + k[len("actor.network.0."):]
        if k.startswith("actor.network."):
            return "actor_rest." + k[len("actor.network."):]
        return k

    mapped = {s2_key(k): k for k in sd if s2_key(k) is not None}
    c.ok(len(mapped) == 33, f"복사 대상 열쇠 수 {len(mapped)} (부모 39 - teacher 6 = 33)")
    miss = [k2 for k2 in mapped if k2 not in fresh]
    c.ok(not miss, f"복사본에 없는 열쇠 {miss[:4]}")
    bad = [k2 for k2, k in mapped.items() if k2 in fresh and not torch.equal(fresh[k2], sd[k])]
    c.ok(not bad, f"복사본 값 != 부모 값 {bad[:4]}")
    c.ok(set(fresh) - set(mapped) == NEW_KEYS, f"새 열쇠 {sorted(set(fresh) - set(mapped))}")
    c.ok(not any(k.startswith("teacher_encoder.") for k in fresh), "teacher encoder 를 가져오지 않음")
    c.ok(P.E1_CKPT == CKPT, f"s2_policy 의 부모 경로 {P.E1_CKPT}")
    # 체크포인트 파일 (마지막에 잰다)
    after = sha256(CKPT)
    c.ok(SHA_BEFORE == PARENT_SHA256, f"시험 전 sha256 {SHA_BEFORE[:16]} != 기록 {PARENT_SHA256[:16]}")
    c.ok(after == PARENT_SHA256 and after == SHA_BEFORE, f"시험 뒤 sha256 {after[:16]} (전 {SHA_BEFORE[:16]})")
    print(f"    T7 sha256 전 {SHA_BEFORE} · 뒤 {after}", flush=True)


def main():
    only = set(sys.argv[1:])
    fails, cells = 0, 0
    for tid, desc, fn in TESTS:
        if only and tid not in only:
            continue
        c = Cells()
        try:
            fn(c)
            c.done()
            cells += c.n
            print(f"PASS {tid} ({c.n} 칸) {desc}", flush=True)
        except AssertionError as e:
            fails += 1
            print(f"FAIL {tid} {desc}: {str(e)[:900]}", flush=True)
        except Exception as e:  # noqa: BLE001  (예외도 FAIL 한 줄로)
            fails += 1
            print(f"FAIL {tid} {desc}: {type(e).__name__}: {str(e)[:600]}", flush=True)
    n = len([t for t in TESTS if not only or t[0] in only])
    print(f"SUMMARY {n - fails}/{n} PASS · 통과한 시험의 칸 {cells} · map_obs={M.__file__} · policy={P.__file__}", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
