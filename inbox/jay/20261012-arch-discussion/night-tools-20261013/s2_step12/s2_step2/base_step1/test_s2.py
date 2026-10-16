# -*- coding: utf-8 -*-
"""S2 A/B 입력 경로의 알려진 답 시험 T1 ~ T14 (판 3 · CPU · Isaac 앱 없이 · GPU 를 가림).

분류: A/정책학습 · S2 「이상적 지도 입력 비교」 A/B 입력 경로 1 단계 판 3 시험
작성: 오흥재 (lead 세션 · Claude 하위 작업 작성) · 판 1 2026-10-13 19:21 · 판 2 2026-10-13 23:32 · 판 3 2026-10-14 00:50
근거: inbox/jay/20261012-arch-discussion/DESIGN-s2-ab-v1.md 4 절 · 6 절 (다르면 6 절) · VERIFY-astra-17d.md 6.2 · 6.3 · 6.4 ·
      VERIFY-astra-17f2.md 2.1 · 3.1 · 3.2 · 4 · 5.3 (판 3: T9 고쳐 씀 · T11 ~ T14 새로)
      E1 params/env.yaml 446 ~ 490 · 865 ~ 1177 · agent.yaml · IsaacLab observations.py height_scan · patterns.py grid_pattern ·
      utils/math.py quat_apply_yaw · sensors/ray_caster/ray_caster.py 218 ~ 224 · 278 ~ 279 · utils/warp/ops.py 71 ·
      actor_critic_moe_cts.py · algorithms/moe_cts.py 278 ~ 311 (adaptive lr · 모든 group 에 같은 lr) · 313 ~ 335 (PPO 손실) ·
      365 ~ 366 (clip) · runners/on_policy_runner_cts.py 108 · 140 · 173 · 278 (runner 번호)
요지: 기대값은 s2_map_obs · s2_policy 를 부르지 않고 손으로 적는다 (구현을 복제한 시험이 되지 않게). 부모 동치는 시험이
      스스로 지은 ActorCriticMoECTS (손으로 적은 구조 · 실제 E1 model_20000 strict 적재) 와 비트로 견준다. 광선 배치 · yaw 는
      IsaacLab 의 grid_pattern · quat_apply_yaw 를 파일에서 직접 불러 RayCaster 의 ray_starts (offset z 20 포함) 를 CPU 로 따라 만든다.
      판 3 의 학습 흉내 (s2_update) 는 부모 moe_cts.update 의 순서 (forward · adaptive lr · 모든 group 덮어쓰기 · backward · clip · step)
      를 옮겨 적고 그 사이에 enforce_groups 를 끼운다. 부모 꼴 두 줄은 시험이 moe_cts.py 소스에서 찾아 같은지 본다.
상태: 시험 파일. 변이 (mutate_s2.py) 가 이 시험을 깨 본다. 실제 collision mesh 의 광선이 아니고, 실제 학습 루프 연결도 아니다

실행: CUDA_VISIBLE_DEVICES=-1 C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I test_s2.py [T1 T4 ...]
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
import inspect  # noqa: E402
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
ISAACLAB = "C:/isaac/IsaacLab/source/isaaclab/isaaclab"
ISAACLAB_PATTERNS = ISAACLAB + "/sensors/ray_caster/patterns/patterns.py"
ISAACLAB_MATH = ISAACLAB + "/utils/math.py"
ISAACLAB_OBS = ISAACLAB + "/envs/mdp/observations.py"
N_POL, N_CRIT, N_SINGLE, N_ACT, N_LAT = 450, 275, 45, 12, 32     # 체크포인트 가중치 모양에서 (student 450 · critic 307-32 · actor 77-32)
R, MAPD = 187, 374
FRONT = [k for k in range(187) if k % 17 >= 9]                    # 몸 앞쪽 x >= 0.1 (x 가 가장 빨리 도는 17 x 11)
CRIT_H0 = 88   # critic obs 의 height_scan 시작 열: 3+3+3+3+12+12+12+12+12+16 (env.yaml 871 ~ 1144 항 순서 · contact_force 4 발 x 4)
# PPO 손실 값 (E1 agent.yaml algorithm)
CLIP, VALUE_COEF, ENTROPY_COEF, MAX_GRAD_NORM = 0.2, 1.0, 0.01, 1.0
DESIRED_KL = 0.01                       # E1 agent.yaml algorithm.desired_kl (schedule adaptive)
EPOCHS, MBS = 2, 2                      # 시험용 update 한 번의 epoch x minibatch (E1 은 5 x 4 = 20 step · 여기선 4 step 으로 줄임)
N_ENC = 16                              # student encoder 매개변수 텐서 수 (T5 에서 셈)
MOE_CTS = "C:/isaac/ext/go2_rl_robotlab/source/rsl_rl/rsl_rl/algorithms/moe_cts.py"
RUNNER_CTS = "C:/isaac/ext/go2_rl_robotlab/source/rsl_rl/rsl_rl/runners/on_policy_runner_cts.py"
NEW_KEYS = {"map_encoder.network.0.weight", "map_encoder.network.0.bias", "map_encoder.network.2.weight",
            "map_encoder.network.2.bias", "actor_in_map.weight"}
STUDENT_PREFIX = "student_moe_encoder."
MAPENC_PREFIX = "map_encoder."
INF, NAN = math.inf, math.nan


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
    """float32 텐서의 비트 동일 (NaN 도 비트로 견줌)."""
    return (a.shape == b.shape and a.dtype == b.dtype == torch.float32
            and torch.equal(a.contiguous().view(torch.int32), b.contiguous().view(torch.int32)))


def close(a, b, atol=1e-6):
    b = torch.as_tensor(b, dtype=a.dtype).expand_as(a)
    return bool(torch.allclose(a, b, atol=atol, rtol=0.0))


def raises(exc, fn):
    try:
        fn()
    except exc:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


def raises_exact(exc, fn):
    """예외 형이 정확히 exc 인가 (하위 형은 아님 · S2IndexError 와 S2ControlError 를 가르려고)."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        return type(e) is exc
    return False


def same_tensor(a, b):
    if a.dtype == torch.float32:
        return bits_equal(a, b)
    return a.dtype == b.dtype and a.shape == b.shape and torch.equal(a, b)


def tensors_sha(named):
    """{이름: 텐서} 를 이름 순서로 이어 붙인 바이트의 sha256 (가중치 바이트가 그대로인지)."""
    h = hashlib.sha256()
    for k in sorted(named):
        h.update(k.encode("utf-8"))
        h.update(named[k].detach().contiguous().numpy().tobytes())
    return h.hexdigest()


def lr_of(opt, name):
    return [g["lr"] for g in opt.param_groups if g.get("name") == name][0]


# ------------------------------------------------------------------ IsaacLab RayCaster 를 CPU 로 따라 하기 (IsaacLab 함수를 파일에서 직접)
_IL = {}


def isaaclab(name):
    if name not in _IL:
        path = {"patterns": ISAACLAB_PATTERNS, "math": ISAACLAB_MATH}[name]
        sp = importlib.util.spec_from_file_location(f"isaaclab_{name}_cpu", path)
        mod = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(mod)
        _IL[name] = mod
    return _IL[name]


def yaw_quat_wxyz(yaw):
    z = torch.zeros_like(yaw)
    return torch.stack([torch.cos(yaw / 2), z, z, torch.sin(yaw / 2)], dim=-1)


def isaac_like_hits(pos_w, yaw, terrain_z):
    """RayCaster (ray_alignment yaw) 의 ray_starts 를 IsaacLab 코드로 만든다: grid_pattern + offset (0, 0, 20) (ray_caster.py 224) ·
    quat_apply_yaw(quat.repeat(1, R), starts) + pos_w (278 ~ 279). 수직 광선이 높이장 terrain_z(x, y) 와 만나는 점이 hit.
    terrain_z 가 inf · nan 이면 그 자리에 mesh 가 없는 것으로 보고 xyz 를 모두 +inf 로 둔다 (ops.py 71 의 초기값).
    돌려줌: (ray_hits_w [N, R, 3], ray_starts_w [N, R, 3])"""
    cfg = types.SimpleNamespace(size=(1.6, 1.0), resolution=0.1, ordering="xy", direction=(0.0, 0.0, -1.0))
    starts, _dirs = isaaclab("patterns").grid_pattern(cfg, "cpu")
    starts = starts + torch.tensor([0.0, 0.0, 20.0])
    n = pos_w.shape[0]
    starts = starts.repeat(n, 1, 1)
    starts_w = isaaclab("math").quat_apply_yaw(yaw_quat_wxyz(yaw).repeat(1, R), starts) + pos_w.unsqueeze(1)
    z = terrain_z(starts_w[..., 0], starts_w[..., 1]).to(pos_w.dtype)
    hits = torch.stack([starts_w[..., 0], starts_w[..., 1], z], dim=-1)
    miss = ~torch.isfinite(z)
    return torch.where(miss.unsqueeze(-1), torch.full_like(hits, INF), hits), starts_w


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


def make_obs(n, seed, m=None, critic=None):
    from tensordict import TensorDict
    g = torch.Generator().manual_seed(seed)
    d = {"policy": torch.randn(n, N_POL, generator=g), "single_obs": torch.randn(n, N_SINGLE, generator=g),
         "critic": torch.randn(n, N_CRIT, generator=g)}
    if critic is not None:
        d["critic"] = critic
    if m is not None:
        d["map"] = m
    return TensorDict(d, batch_size=[n])


def with_map(obs, m):
    o = obs.clone()
    o["map"] = m
    return o


def random_b_map(n, seed):
    """손으로 만든 B 꼴 지도: height U(-1, 1) · mask 70 % 1 · mask 0 칸은 height 1 (정상 miss 꼴)."""
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
    """단 (0.3 m 마다 0 / 0.12 m) · mesh 없음 (inf · 정상 miss) · 깊은 구덩이 바닥 (-2 m · 유한)."""
    z = 0.12 * (torch.floor(x / 0.3).remainder(2))
    cell = (torch.floor(x / 0.2) + 3 * torch.floor(y / 0.2)).remainder(7)
    z = torch.where(cell == 0, torch.full_like(z, INF), z)
    z = torch.where(cell == 3, torch.full_like(z, -2.0), z)
    return z


def terrain_block(bx, by):
    """한 광선만 맞도록 반폭 0.04 m 의 0.1 m 높이 블록 (광선 간격 0.1 m)."""
    return lambda x, y: torch.where(((x - bx).abs() < 0.04) & ((y - by).abs() < 0.04), 0.1, 0.0)


# ------------------------------------------------------------------ PPO 손실 모양 (algorithms/moe_cts.py 313 ~ 335 · agent.yaml 값)
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
            "adv": torch.randn(n, generator=g), "returns": values + torch.randn(n, 1, generator=g), "mu": mu, "sigma": sigma}


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


def opt_no_freeze(pol, lr):
    """encoder 고정 없이 (schedule W 0 · r 1) 만든 optimizer 와 control. 시험용 값이며 등록 값이 아니다 (T5 · T7: 지도 · encoder gradient 경로)."""
    return P.make_optimizer(pol, lr, encoder_mode="schedule", encoder_freeze_updates=0, encoder_lr_ratio=1.0)


# ------------------------------------------------------------------ 부모 moe_cts.update 의 꼴 (옮겨 적음 · T13 이 소스와 대조)
def parent_adaptive_lr(lr, kl_mean):
    """moe_cts.py 298 ~ 301 의 규칙 (E1 desired_kl 0.01)."""
    if kl_mean > DESIRED_KL * 2.0:
        lr = max(1e-5, lr / 1.5)
    elif kl_mean < DESIRED_KL / 2.0 and kl_mean > 0.0:
        lr = min(1e-2, lr * 1.5)
    return lr


def parent_overwrite(optimizer, lr):
    """moe_cts.py 310 ~ 311 의 꼴: 모든 param group 에 같은 lr 을 쓴다 (S2 의 encoder 묶음 비를 깨는 꼴)."""
    for param_group in optimizer.param_groups:
        param_group["lr"] = lr


def kl_mean_now(pol, bb):
    """moe_cts.py 280 ~ 287 의 KL (rollout 때 분포 대비 · 행동 차원 합 · 평균)."""
    with torch.inference_mode():
        mu, sigma = pol.action_mean, pol.action_std
        kl = torch.sum(torch.log(sigma / bb["sigma"] + 1.0e-5)
                       + (torch.square(bb["sigma"]) + torch.square(bb["mu"] - mu)) / (2.0 * torch.square(sigma)) - 0.5, dim=-1)
        return float(torch.mean(kl))


def s2_update(pol, opt, ctl, k, obs, b, lr, probe=None):
    """S2 PPO update 한 번. 부모 moe_cts.update 의 순서 (forward · adaptive lr · 모든 group 덮어쓰기 · zero_grad · backward · clip · step)
    에 enforce_groups 를 step 앞에 끼운다. clip 은 trainable_params. probe(pol, opt, ctl, k, j) 는 enforce 뒤 · step 전에 불린다.
    돌려줌: (다음 update 로 넘길 lr, 이 update 가 고정이었나)."""
    frozen = ctl.begin_update(k, lr)
    chunks = torch.arange(obs.batch_size[0]).chunk(MBS)
    j = 0
    for _e in range(EPOCHS):
        for idx in chunks:
            o = obs[idx]
            bb = {key: v[idx] for key, v in b.items()}
            loss = ppo_like_loss(pol, o, bb)
            lr = parent_adaptive_lr(lr, kl_mean_now(pol, bb))
            parent_overwrite(opt, lr)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(P.trainable_params(pol), MAX_GRAD_NORM)
            ctl.enforce_groups(opt, lr)
            if probe is not None:
                probe(pol, opt, ctl, k, j)
            opt.step()
            j += 1
    ctl.end_update(k)
    return lr, frozen


def terrain_obs(n, seed):
    pos, yaw = random_pose(n, seed)
    return with_map(make_obs(n, seed + 1), M.map_obs("B", pos, isaac_like_hits(pos, yaw, terrain_rough)[0])[0])


def grad_norm(params):
    return math.sqrt(sum(float(p.grad.double().pow(2).sum()) for p in params if p.grad is not None))


def non_encoder(pol):
    eids = {id(p) for p in pol.student_moe_encoder.parameters()}
    return [p for p in pol.parameters() if id(p) not in eids]


# =========================================================================== T1
@test("T1", "평지: 센서 0.4 m · 맞은 점 0 -> height -0.1 · mask 1 (187 칸 모두) · 고장 0 · 배치 [height, mask] · 센서 기준 (세계 높이 · xy 무관) · A 는 0")
def t1(c):
    src = open(ISAACLAB_OBS, encoding="utf-8").read()
    c.ok("def height_scan(env: ManagerBasedEnv, sensor_cfg: SceneEntityCfg, offset: float = 0.5)" in src, "IsaacLab height_scan offset 기본 0.5")
    c.ok("return sensor.data.pos_w[:, 2].unsqueeze(1) - sensor.data.ray_hits_w[..., 2] - offset" in src, "IsaacLab height_scan 식")
    g = torch.Generator().manual_seed(1)
    pos = torch.tensor([[0.0, 0.0, 0.4], [3.0, -2.0, 10.4], [-5.0, 7.0, 0.4]])
    hits = torch.zeros(3, R, 3)
    hits[..., 0:2] = torch.rand(3, R, 2, generator=g) * 20 - 10      # 맞은 점 xy 는 height 와 무관해야 함
    hits[1, :, 2] = 10.0                                              # 세계 높이 10 m 에 선 env
    h, mk, f = M.height_and_mask(pos, hits)
    c.ok(tuple(h.shape) == (3, R) and tuple(mk.shape) == (3, R), f"모양 {tuple(h.shape)} {tuple(mk.shape)}")
    c.ok(close(h, -0.1), f"height -0.1 이어야 함: {h.min().item():.6f} ~ {h.max().item():.6f}")
    c.ok(torch.equal(mk, torch.ones(3, R)), f"mask 1 이어야 함: 0 인 칸 {int((mk == 0).sum())}")
    c.ok(f.total == 0 and f.n_sensor == 0 and f.n_packet == 0, f"고장 0 이어야 함: {f.as_dict()}")
    mo, fb = M.map_obs_b(pos, hits)
    c.ok(tuple(mo.shape) == (3, MAPD), f"map_obs_b 모양 {tuple(mo.shape)}")
    c.ok(close(mo[:, :R], -0.1) and torch.equal(mo[:, R:], torch.ones(3, R)), "배치 [height 0~186, mask 187~373]")
    c.ok(torch.equal(M.map_obs("B", pos, hits)[0], mo), "map_obs('B') == map_obs_b")
    c.ok(torch.equal(M.map_obs("A", pos, hits)[0], torch.zeros(3, MAPD)), "A 는 height 0 · mask 0")
    c.ok(M.MAP_DIM == 374 and M.NUM_RAYS == 187, f"MAP_DIM {M.MAP_DIM} · NUM_RAYS {M.NUM_RAYS}")


# =========================================================================== T2
@test("T2", "단차 · 정상 miss · 깊은 바닥 (판 2 의미): 앞쪽 +0.1 m -> 그 칸만 -0.2 · xyz +inf -> mask 0 · height 1 · 유한한 깊은 바닥 -> mask 1 · height clip 1 · 1 m 분류 없음 · 높은 장애물 -1")
def t2(c):
    pos = torch.tensor([[0.0, 0.0, 0.4]])
    hits = torch.zeros(1, R, 3)
    hits[0, FRONT, 2] = 0.1
    hits[0, 0, :] = INF               # 정상 miss (raycast_mesh 꼴: xyz 모두 +inf)
    hits[0, 2, 2] = -2.0              # 깊이 2 m 구멍 바닥 (센서 아래 2.4 m · 유한) -> mask 1 · clip 1
    hits[0, 4, 2] = -0.5              # 센서 아래 0.9 m -> 0.4 · mask 1
    hits[0, 6, 2] = -0.7              # 센서 아래 1.1 m -> 0.6 · mask 1 (1 m 분류 없음)
    hits[0, 20, 2] = 1.5              # 센서보다 1.1 m 위 (높은 장애물) -> clip -1 · mask 1
    hits[0, 22, 2] = -10.0            # holes_depth -10 바닥 -> clip 1 · mask 1
    hits[0, 24, 2] = 0.45             # 센서보다 0.05 m 위 -> -0.55 · mask 1
    h, mk, f = M.height_and_mask(pos, hits)
    exp_h = torch.full((1, R), -0.1)
    exp_h[0, FRONT] = -0.2
    for k, v in ((0, 1.0), (2, 1.0), (4, 0.4), (6, 0.6), (20, -1.0), (22, 1.0), (24, -0.55)):
        exp_h[0, k] = v
    exp_m = torch.ones(1, R)
    exp_m[0, 0] = 0.0
    special = (0, 2, 4, 6, 20, 22, 24)
    c.ok(len(FRONT) == 88, f"앞쪽 광선 수 {len(FRONT)}")
    c.ok(bool(torch.isfinite(h).all()), "height 에 inf · nan 이 남지 않음")
    c.ok(close(h, exp_h), f"height 칸별 대조 · 최대 차 {(h - exp_h).abs().nan_to_num(99.0).max().item():.6f}")
    c.ok(close(h[0, FRONT], -0.2) and close(h[0, [k for k in range(R) if k % 17 <= 8 and k not in special]], -0.1),
         "단 위 칸만 -0.2 · 나머지 평지 -0.1")
    c.ok(torch.equal(mk, exp_m), f"mask 칸별 대조 · mask 0 위치 {torch.nonzero(mk[0] == 0).flatten().tolist()} (0 번만이어야 함)")
    c.ok(set(torch.unique(mk).tolist()) <= {0.0, 1.0}, f"mask 값 {torch.unique(mk).tolist()}")
    c.ok(h[0, 0].item() == 1.0 and h[0, 2].item() == 1.0 and mk[0, 0].item() == 0.0 and mk[0, 2].item() == 1.0,
         "정상 miss 와 유한한 깊은 바닥은 height 가 같고 (1) mask 로만 갈린다 (0 vs 1)")
    c.ok(f.total == 0, f"정상 miss 는 고장이 아님: {f.as_dict()}")
    mo, _ = M.map_obs_b(pos, hits)
    c.ok(torch.equal(mo[:, R:], exp_m) and close(mo[:, :R], exp_h), "map_obs_b 에도 같은 값")


# =========================================================================== T3
@test("T3", "광선 순서: grid xy (x 가 가장 빨리) · 0 · 1 · 16 · 17 · 93 · 186 번의 몸체 좌표가 손 계산 · IsaacLab grid_pattern (CPU) 과 같음 · env.yaml 설정 · 순서 보존")
def t3(c):
    hand = {0: (-0.8, -0.5), 1: (-0.7, -0.5), 16: (0.8, -0.5), 17: (-0.8, -0.4), 93: (0.0, 0.0), 186: (0.8, 0.5)}
    gb = M.grid_ray_xy_body()
    c.ok(tuple(gb.shape) == (R, 2), f"grid_ray_xy_body 모양 {tuple(gb.shape)}")
    for k, xy in hand.items():
        c.ok(close(gb[k], torch.tensor(xy)), f"광선 {k}: {gb[k].tolist()} != {xy}")
    cfg = types.SimpleNamespace(size=(1.6, 1.0), resolution=0.1, ordering="xy", direction=(0.0, 0.0, -1.0))
    starts, dirs = isaaclab("patterns").grid_pattern(cfg, "cpu")
    c.ok(tuple(starts.shape) == (R, 3), f"IsaacLab grid_pattern 광선 수 {tuple(starts.shape)}")
    for k, xy in hand.items():
        c.ok(close(starts[k, :2], torch.tensor(xy)), f"IsaacLab 광선 {k}: {starts[k, :2].tolist()} != {xy}")
    c.ok(torch.equal(gb, starts[:, :2]), "grid_ray_xy_body == IsaacLab grid_pattern (187 광선 모두 비트 동일)")
    c.ok(torch.equal(dirs, torch.tensor([0.0, 0.0, -1.0]).expand(R, 3)), "광선 방향 아래")
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
    pos = torch.tensor([[0.0, 0.0, 0.4]])
    hits = torch.zeros(1, R, 3)
    hits[0, :, 2] = torch.arange(R, dtype=torch.float32) * 0.001
    hits[0, 17, :] = INF
    mo, _ = M.map_obs_b(pos, hits)
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
    p2, meta = P.load_parent_cpu(CKPT)
    s2p = p2.state_dict()
    c.ok(set(s2p) == set(sd) and all(torch.equal(s2p[k], sd[k]) for k in sd), "load_parent_cpu 의 부모 == 파일")
    c.ok(meta["dims"] == {"policy": N_POL, "critic": N_CRIT, "single_obs": N_SINGLE, "actions": N_ACT, "latent": N_LAT}, f"dims {meta['dims']}")
    c.ok(meta["last_lr"] == PARENT_LAST_LR and meta["iter"] == 20000, f"last_lr {meta['last_lr']} · iter {meta['iter']}")
    B = P.S2MapActorCritic(ref, "B").eval()
    A = P.S2MapActorCritic(ref, "A").eval()
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
    N = 256
    obs = make_obs(N, 1)
    pos, yaw = random_pose(N, 2)
    terr_map, _ = M.map_obs_b(pos, isaac_like_hits(pos, yaw, terrain_rough)[0])
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
@test("T5", "gradient 경로 (PPO 손실 모양 · 한 번 갱신 · 고정 구간 없음 W 0): 갱신 전 새 열 gradient 있음 · map encoder 0 · student encoder 있음 · 갱신 뒤 B map encoder 0 아님 · A 첫 층 weight 0 (bias 아님)")
def t5(c):
    ref = ref_parent()
    N = 256
    obs0 = make_obs(N, 11)
    pos, yaw = random_pose(N, 12)
    hits = isaac_like_hits(pos, yaw, terrain_rough)[0]
    hits2 = isaac_like_hits(pos, yaw, terrain_flat)[0]
    for mode in ("B", "A"):
        pol = P.S2MapActorCritic(ref, mode).train()
        opt, ctl = opt_no_freeze(pol, PARENT_LAST_LR)
        ids_opt = [id(p) for g in opt.param_groups for p in g["params"]]
        c.ok(len(ids_opt) == len(set(ids_opt)) and set(ids_opt) == {id(p) for p in pol.parameters()},
             f"{mode}: optimizer 가 모든 매개변수를 한 번씩 덮음 ({len(ids_opt)} vs {len(list(pol.parameters()))})")
        c.ok(all(g["lr"] == PARENT_LAST_LR for g in opt.param_groups), f"{mode}: lr 이 부모 마지막 값 (r 1)")
        obs = with_map(obs0, M.map_obs(mode, pos, hits)[0])
        b = rollout(pol, obs, seed=13)
        ctl.begin_update(0, PARENT_LAST_LR)
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
             f"{mode} 갱신 전: student encoder gradient 가 매개변수마다 있음 (forward 에 no_grad 없음) {[(k, nz(g[k])) for k in stu if nz(g[k]) == 0][:3]}")
        c.ok(nz(g["std"]) > 0 and nz(g["actor_in.weight"]) > 0, f"{mode} 갱신 전: std · actor 첫 층 gradient 있음")
        c.ok(all(nz(v) > 0 for k, v in g.items() if k.startswith("critic.")), f"{mode} 갱신 전: critic gradient 있음")
        torch.nn.utils.clip_grad_norm_(P.trainable_params(pol), MAX_GRAD_NORM)
        ctl.enforce_groups(opt, PARENT_LAST_LR)
        opt.step()
        ctl.end_update(0)
        c.ok(nz(pol.actor_in_map.weight) > 0, f"{mode}: 한 번 갱신 뒤 새 열이 0 이 아님 ({nz(pol.actor_in_map.weight)} 원소)")
        opt.zero_grad(set_to_none=True)
        ppo_like_loss(pol, obs, b).backward()
        g = grads(pol)
        if mode == "B":
            c.ok(all(g[k] is not None and nz(g[k]) > 0 for k in men),
                 f"B 갱신 뒤: map encoder gradient 가 매개변수마다 0 아님 {[(k, nz(g[k])) for k in men]}")
            with torch.no_grad():
                d = (pol.act_inference(obs) - pol.act_inference(with_map(obs0, M.map_obs("B", pos, hits2)[0]))).abs().max().item()
            c.ok(d > 0.0, f"B 갱신 뒤: 지도를 바꾸면 action 이 바뀜 (최대 차 {d:.3e})")
            print(f"    T5 B 갱신 뒤 지도 바꿈 action 최대 차 {d:.3e}", flush=True)
        else:
            c.ok(g["map_encoder.network.0.weight"] is not None and nz(g["map_encoder.network.0.weight"]) == 0,
                 f"A 갱신 뒤: map encoder 첫 층 weight gradient 0 이어야 함 ({nz(g['map_encoder.network.0.weight'])})")
            c.ok(nz(g["map_encoder.network.0.bias"]) > 0 and nz(g["map_encoder.network.2.weight"]) > 0,
                 "A 갱신 뒤: 첫 층 bias · 둘째 층 weight gradient 는 0 아님")
    pol = P.S2MapActorCritic(ref, "B").train()
    obs = with_map(obs0, M.map_obs("B", pos, hits)[0])
    pol.evaluate(obs).pow(2).mean().backward()
    g = grads(pol)
    c.ok(all(nz(g[k]) == 0 for k in g if k.startswith(STUDENT_PREFIX)), "value 손실만: student encoder gradient 0 (latent.detach)")
    c.ok(all(g[k] is None for k in g if k.startswith(MAPENC_PREFIX)) and g["actor_in_map.weight"] is None, "value 손실만: 지도 경로 gradient 없음")
    c.ok(all(nz(g[k]) > 0 for k in g if k.startswith("critic.")), "value 손실만: critic gradient 있음")


# =========================================================================== T6
@test("T6", "A 의 정보 차단: A 에서 실제 지형 (평지 vs 단 · 정상 miss · 구덩이) 을 바꿔도 policy 입력 · action 이 안 바뀜 (새 열 0 아님에서도) · B 는 바뀜 · A 에 실제 지도를 넣으면 거부")
def t6(c):
    ref = ref_parent()
    N = 128
    pos, yaw = random_pose(N, 21)
    h_flat = isaac_like_hits(pos, yaw, terrain_flat)[0]
    h_rough = isaac_like_hits(pos, yaw, terrain_rough)[0]
    h_holes = h_flat.clone()
    h_holes[:, ::3, :] = INF                          # 직접 넣은 정상 miss
    mb = {k: M.map_obs("B", pos, h)[0] for k, h in (("flat", h_flat), ("rough", h_rough), ("holes", h_holes))}
    c.ok(int((mb["rough"][:, R:] == 0).sum()) > 0 and int((mb["holes"][:, R:] == 0).sum()) > 0 and not torch.equal(mb["flat"], mb["rough"]),
         "시험 지형이 실제로 다름 (B 지도에 mask 0 · 값 차이)")
    ma = {k: M.map_obs("A", pos, h)[0] for k, h in (("flat", h_flat), ("rough", h_rough), ("holes", h_holes))}
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
    c.ok(d2 > 1e-5, f"B action 은 정상 miss (mask) 에 따라 바뀜 (최대 차 {d2:.3e})")
    for k in ("rough", "holes"):
        c.ok(raises(ValueError, lambda k=k: A.act_inference(with_map(obs, mb[k]))), f"A 정책에 B 지도 ({k}) 를 넣으면 ValueError")


# =========================================================================== T7
@test("T7", "부모 보존: 체크포인트 sha256 이 시험 전후 같음 (손으로 적은 값) · 부모 state_dict 키 · 값이 복사본과 같음 · S2 갱신 뒤에도 부모 그대로 · 저장소 공유 없음")
def t7(c):
    ref = ref_parent()
    sd = file_state_dict()
    pol = P.S2MapActorCritic(ref, "B").train()
    opt, ctl = opt_no_freeze(pol, 1e-2)
    obs = with_map(make_obs(64, 31), random_b_map(64, 32))
    before = {k: v.detach().clone() for k, v in pol.state_dict().items()}
    ctl.begin_update(0, 1e-2)
    ppo_like_loss(pol, obs, rollout(pol, obs, 33)).backward()
    ctl.enforce_groups(opt, 1e-2)
    opt.step()
    ctl.end_update(0)
    moved = [k for k, v in pol.state_dict().items() if not torch.equal(v, before[k])]
    c.ok(any(k.startswith("actor_in.") for k in moved) and any(k.startswith("critic.") for k in moved)
         and any(k.startswith(STUDENT_PREFIX) for k in moved) and "std" in moved, f"S2 갱신이 실제로 일어남 (바뀐 열쇠 {len(moved)})")
    rs = ref.state_dict()
    c.ok(set(rs) == set(sd), "부모 모듈 열쇠 == 파일 열쇠")
    diff = [k for k in sd if not torch.equal(rs[k], sd[k])]
    c.ok(not diff, f"부모 모듈 값 == 파일 값 (앞 시험들과 이 갱신 뒤) · 다른 열쇠 {diff[:4]}")
    pptr = {t.data_ptr() for t in ref.state_dict().values()}
    shared = [k for k, p in pol.named_parameters() if p.data_ptr() in pptr]
    c.ok(not shared, f"S2 매개변수가 부모와 저장소를 나누지 않음 · 나누는 것 {shared[:4]}")
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
    after = sha256(CKPT)
    c.ok(SHA_BEFORE == PARENT_SHA256, f"시험 전 sha256 {SHA_BEFORE[:16]} != 기록 {PARENT_SHA256[:16]}")
    c.ok(after == PARENT_SHA256 and after == SHA_BEFORE, f"시험 뒤 sha256 {after[:16]} (전 {SHA_BEFORE[:16]})")
    print(f"    T7 sha256 전 {SHA_BEFORE} · 뒤 {after}", flush=True)


# =========================================================================== T8
@test("T8", "입력 의미 (ASTRA 17d 6.4): 센서 NaN · inf 와 ray packet 손상은 구멍이 아니라 고장으로 따로 셈 · strict 예외 · A · B 같은 고장 판정 · 관문 · 20 m offset 을 다시 더하지 않음 · 평행 이동과 yaw 90 도에서 발밑 · 앞 칸이 옮겨짐")
def t8(c):
    zero_row = torch.zeros(MAPD)
    # (a) 센서 위치 비유한
    pos = torch.tensor([[0.0, 0.0, 0.4], [NAN, 0.0, 0.4], [0.0, 0.0, INF]])
    hits = torch.zeros(3, R, 3)
    mo, f = M.map_obs_b(pos, hits)
    c.ok(f.sensor_bad.tolist() == [False, True, True] and f.n_sensor == 2 and f.n_packet == 0,
         f"센서 비유한 env 2 개만 고장 (packet 으로 두 번 세지 않음): {f.sensor_bad.tolist()} · {f.as_dict()}")
    c.ok(f.env_bad.tolist() == [False, True, True], f"env_bad {f.env_bad.tolist()}")
    c.ok(close(mo[0, :R], -0.1) and torch.equal(mo[0, R:], torch.ones(R)), "고장 없는 env 0 은 정상 (-0.1 · 1)")
    c.ok(torch.equal(mo[1], zero_row) and torch.equal(mo[2], zero_row), "센서 고장 env 의 지도는 자리표시 (height 0 · mask 0)")
    c.ok(not bool(((mo[1:, :R] == 1.0) & (mo[1:, R:] == 0.0)).any()), "센서 고장이 정상 miss 꼴 (height 1 · mask 0) 로 바뀌지 않음 (구멍 아님)")
    c.ok(bool(torch.isfinite(mo).all()), "지도에 NaN · inf 가 나가지 않음")
    # (b) ray packet 손상 (센서 정상)
    pos1 = torch.tensor([[0.0, 0.0, 0.4]])
    hp = torch.zeros(1, R, 3)
    hp[0, 10, 2] = NAN                   # z NaN
    hp[0, 11, 2] = -INF                  # z -inf
    hp[0, 12, 0] = NAN                   # x NaN · z 유한
    hp[0, 13, 2] = INF                   # z 만 +inf (xy 유한)
    hp[0, 14, :] = INF                   # 정상 miss
    hp[0, 15, :] = torch.tensor([INF, INF, -INF])
    mp, fp = M.map_obs_b(pos1, hp)
    bad = torch.nonzero(fp.packet_bad[0]).flatten().tolist()
    c.ok(bad == [10, 11, 12, 13, 15] and fp.n_packet == 5 and fp.n_sensor == 0, f"packet 고장 위치 {bad} (10 · 11 · 12 · 13 · 15 이어야 함)")
    c.ok(fp.env_bad.tolist() == [True], "packet 고장이 있는 env 는 env_bad")
    exp_h = torch.full((R,), -0.1)
    exp_m = torch.ones(R)
    for k in (10, 11, 12, 13, 15):
        exp_h[k], exp_m[k] = 0.0, 0.0
    exp_h[14], exp_m[14] = 1.0, 0.0
    c.ok(close(mp[0, :R], exp_h) and torch.equal(mp[0, R:], exp_m), "고장 칸 (0, 0) · 정상 miss 칸 (1, 0) · 나머지 (-0.1, 1)")
    # (c) strict
    clean = torch.zeros(1, R, 3)
    clean[0, 14, :] = INF
    c.ok(not raises(Exception, lambda: M.height_and_mask(pos1, clean, strict=True)), "strict: 정상 miss 만 있으면 예외 없음")
    c.ok(raises(M.MapObsFault, lambda: M.height_and_mask(pos, hits, strict=True)), "strict: 센서 고장 -> MapObsFault")
    c.ok(raises(M.MapObsFault, lambda: M.map_obs("B", pos1, hp, strict=True)), "strict: packet 고장 -> MapObsFault (B)")
    c.ok(raises(M.MapObsFault, lambda: M.map_obs("A", pos1, hp, strict=True)), "strict: packet 고장 -> MapObsFault (A 도 같게)")
    # (d) A · B 같은 고장 판정
    for name, (pp, hh) in (("센서", (pos, hits)), ("packet", (pos1, hp))):
        ma, fa = M.map_obs("A", pp, hh)
        _mb, fb = M.map_obs("B", pp, hh)
        c.ok(torch.equal(fa.sensor_bad, fb.sensor_bad) and torch.equal(fa.packet_bad, fb.packet_bad) and fa.total == fb.total > 0,
             f"{name} 고장: A · B 고장 판정이 같음 ({fa.as_dict()} vs {fb.as_dict()})")
        c.ok(torch.equal(ma, torch.zeros(pp.shape[0], MAPD)), f"{name} 고장: A 지도 입력은 그대로 0")
    # (e) rollout 유효성 관문
    gate = M.RunValidityGate()
    c.ok(gate.valid, "새 관문은 유효")
    gate.add_map(M.map_obs("B", pos1, clean)[1])
    c.ok(gate.valid and gate.counts["map_steps"] == 1, f"정상 miss 만 넣으면 유효 {gate.counts}")
    gate.add_map(fp)
    c.ok(not gate.valid and gate.counts == {"map_steps": 2, "sensor_nonfinite_envs": 0, "ray_packet_bad": 5,
                                            "critic_input_nonfinite": 0, "value_nonfinite": 0}, f"packet 고장 뒤 무효 {gate.counts}")
    c.ok(raises(M.MapObsFault, gate.require_valid), "무효 관문은 require_valid 에서 MapObsFault")
    g2 = M.RunValidityGate()
    g2.add_map(f)
    c.ok(not g2.valid and g2.counts["sensor_nonfinite_envs"] == 2, f"센서 고장 뒤 무효 {g2.counts}")
    g3 = M.RunValidityGate()
    g3.add_nonfinite("advantage", torch.tensor([0.0, NAN]))
    c.ok(not g3.valid and raises(M.MapObsFault, g3.require_valid), "advantage 의 NaN 도 무효")
    # (f) 20 m offset 을 다시 더하지 않음 (ray 시작은 pos z + 20 · height 는 pos z 기준)
    p = torch.tensor([[1.0, 2.0, 0.4]])
    hits20, starts_w = isaac_like_hits(p, torch.tensor([0.3]), lambda x, y: torch.full_like(x, 0.3))
    h20, m20, f20 = M.height_and_mask(p, hits20)
    c.ok(close(starts_w[..., 2], 20.4, atol=1e-5), f"IsaacLab 식 ray 시작 z = 20.4 ({starts_w[..., 2].min().item():.4f})")
    c.ok(close(h20, -0.4) and torch.equal(m20, torch.ones(1, R)) and f20.total == 0, f"지면 0.3 -> height -0.4 · mask 1 (20 m 를 다시 더하면 clip 1): {h20.max().item():.4f}")
    # (g) 평행 이동 · yaw: 한 광선만 맞는 블록 (0.1 m) 이 어느 광선에 걸리는가 (손 계산 광선 번호)
    cases = (("yaw 0 · 블록 앞 0.3 m", (2.0, 1.0), 0.0, (2.3, 1.0), 96),
             ("yaw 0 · 0.3 m 앞으로 옮김 -> 발밑", (2.3, 1.0), 0.0, (2.3, 1.0), 93),
             ("yaw +90 · 블록 세계 +y 0.3 m (몸 앞)", (2.0, 1.0), math.pi / 2, (2.0, 1.3), 96),
             ("yaw +90 · 몸 앞으로 0.3 m 옮김 -> 발밑", (2.0, 1.3), math.pi / 2, (2.0, 1.3), 93),
             ("yaw +90 · 블록 세계 +x 0.3 m (몸 오른쪽 -y)", (2.0, 1.0), math.pi / 2, (2.3, 1.0), 42),
             ("yaw -90 · 블록 세계 +x 0.3 m (몸 왼쪽 +y)", (2.0, 1.0), -math.pi / 2, (2.3, 1.0), 144))
    for name, (px, py), yw, (bx, by), k in cases:
        pp = torch.tensor([[px, py, 0.4]])
        hb, _sw = isaac_like_hits(pp, torch.tensor([yw]), terrain_block(bx, by))
        hh, mm, ff = M.height_and_mask(pp, hb)
        on = torch.nonzero(hh[0] < -0.15).flatten().tolist()
        c.ok(on == [k] and close(hh[0, k], -0.2) and close(hh[0, [j for j in range(R) if j != k]], -0.1) and ff.total == 0,
             f"{name}: 블록 광선 {on} ({k} 이어야 함)")


# =========================================================================== T9
@test("T9", "schedule 모드 (판 2 의 고정 구간 · 판 3 API): W · r 은 schedule 에서 필수 (기본값은 「안 넘김」 표시뿐) · r 0 거부 · 처음 W update 동안 student encoder 비트 불변 (gradient 없음) · actor 는 움직임 · 그 뒤 encoder lr = r x actor lr · 첫 encoder 걸음 크기 r x lr 이하")
def t9(c):
    ref = ref_parent()
    sig = inspect.signature(P.make_optimizer)
    c.ok(sig.parameters["encoder_freeze_updates"].default is P._UNSET and sig.parameters["encoder_lr_ratio"].default is P._UNSET,
         "make_optimizer 의 W · r 기본값은 「안 넘김」 표시 (쓸 수 있는 값 없음)")
    sig2 = inspect.signature(P.EncoderControl.__init__)
    c.ok(all(sig2.parameters[k].default is P._UNSET for k in ("freeze_updates", "encoder_lr_ratio")), "EncoderControl 의 W · r 기본값도 「안 넘김」 표시")
    pol0 = P.S2MapActorCritic(ref, "B")

    def S(**kw):
        return P.make_optimizer(pol0, PARENT_LAST_LR, encoder_mode="schedule", **kw)

    c.ok(raises(TypeError, lambda: S()) and raises(TypeError, lambda: S(encoder_freeze_updates=3))
         and raises(TypeError, lambda: S(encoder_lr_ratio=0.1)), "schedule 에 W · r 을 안 넘기면 TypeError")
    c.ok(raises(TypeError, lambda: S(encoder_freeze_updates=None, encoder_lr_ratio=0.1))
         and raises(TypeError, lambda: S(encoder_freeze_updates=3, encoder_lr_ratio=None)), "None 은 TypeError")
    c.ok(all(raises(ValueError, lambda a=a: S(encoder_freeze_updates=a[0], encoder_lr_ratio=a[1]))
             for a in ((-1, 0.1), (2.5, 0.1), (True, 0.1), (3, -0.1), (3, NAN), (3, INF), (3, True))),
         "W 음수 · 정수 아님 · bool · r 음수 · NaN · inf · bool 은 ValueError")
    c.ok(raises(ValueError, lambda: S(encoder_freeze_updates=3, encoder_lr_ratio=0.0))
         and raises(ValueError, lambda: S(encoder_freeze_updates=3, encoder_lr_ratio=0)),
         "r 0 은 ValueError (17f-2 3.1: lr 0 은 실제 고정이 아님 · 끝까지 고정은 full_freeze)")
    c.ok(all(p.requires_grad for p in pol0.parameters()), "인자 오류는 정책을 건드리기 전에 난다 (requires_grad 그대로)")
    W, r = 3, 0.25                       # 시험 값 (등록 값 아님)
    ENC_LR = 4.271484375000002e-05       # 0.25 x 0.00017085937500000009 (손 계산)
    pol = P.S2MapActorCritic(ref, "B").train()
    opt, ctl = P.make_optimizer(pol, PARENT_LAST_LR, encoder_mode="schedule", encoder_freeze_updates=W, encoder_lr_ratio=r)
    enc_params = list(pol.student_moe_encoder.parameters())
    c.ok(all(not p.requires_grad for p in enc_params), "만들자마자 update 0 규칙: encoder requires_grad 꺼짐")
    c.ok([g["name"] for g in opt.param_groups] == ["student_encoder", "map_encoder", "actor", "critic", "std"],
         f"schedule: encoder 묶음이 optimizer 에 있음 (고정 중 lr 0) {[g['name'] for g in opt.param_groups]}")
    pos, yaw = random_pose(128, 41)
    obs = with_map(make_obs(128, 42), M.map_obs("B", pos, isaac_like_hits(pos, yaw, terrain_rough)[0])[0])
    b = rollout(pol, obs, 43)
    enc0 = {k: v.detach().clone() for k, v in pol.student_moe_encoder.state_dict().items()}
    exp_frozen = [True, True, True, False, False]
    for u in range(5):
        frozen = ctl.begin_update(u, PARENT_LAST_LR)
        lrs = {g["name"]: g["lr"] for g in opt.param_groups}
        c.ok(frozen == exp_frozen[u], f"update {u}: 고정 {frozen} (기대 {exp_frozen[u]})")
        exp_enc = 0.0 if exp_frozen[u] else ENC_LR
        c.ok(lrs["student_encoder"] == exp_enc and all(v == PARENT_LAST_LR for n, v in lrs.items() if n != "student_encoder"),
             f"update {u}: lr {lrs} (encoder {exp_enc} · 나머지 {PARENT_LAST_LR})")
        enc_before = {k: v.detach().clone() for k, v in pol.student_moe_encoder.state_dict().items()}
        act_before = {k: v.detach().clone() for k, v in pol.actor_rest.state_dict().items()}
        opt.zero_grad(set_to_none=True)
        ppo_like_loss(pol, obs, b).backward()
        if exp_frozen[u]:
            c.ok(all(p.grad is None for p in enc_params), f"update {u}: 고정 중 encoder gradient 없음")
        torch.nn.utils.clip_grad_norm_(P.trainable_params(pol), MAX_GRAD_NORM)
        ctl.enforce_groups(opt, PARENT_LAST_LR)
        opt.step()
        ctl.end_update(u)
        enc_now = pol.student_moe_encoder.state_dict()
        act_now = pol.actor_rest.state_dict()
        c.ok(any(not torch.equal(act_now[k], act_before[k]) for k in act_now), f"update {u}: actor 는 움직임")
        if exp_frozen[u]:
            c.ok(all(bits_equal(enc_now[k], enc0[k]) for k in enc0), f"update {u}: encoder 매개변수가 처음과 비트 동일")
        if u == 3:
            dmax = max((enc_now[k] - enc_before[k]).abs().max().item() for k in enc_now)
            # Adam 첫 걸음 |d| = lr |g| / (|g| + eps) <= lr. float32 저장 반올림 (원소 값의 ulp) 만큼은 허용
            within = all(((enc_now[k] - enc_before[k]).abs()
                          <= ENC_LR * 1.000001 + (torch.nextafter(enc_before[k].abs(), torch.tensor(INF)) - enc_before[k].abs())).all()
                         for k in enc_now)
            c.ok(within and dmax >= 0.5 * ENC_LR, f"풀린 첫 update: encoder 최대 걸음 {dmax:.3e} (원소마다 r x lr = {ENC_LR:.3e} + ulp 이하 · 최대는 절반 이상)")
            steps_enc = {float(opt.state[p]["step"]) for p in enc_params}
            steps_act = {float(opt.state[p]["step"]) for p in pol.actor_rest.parameters()}
            c.ok(steps_enc == {1.0} and steps_act == {4.0}, f"Adam step: encoder {steps_enc} (1 · 고정 중 moment 안 쌓임) · actor {steps_act} (4)")
            c.ok(all(p.requires_grad for p in enc_params), "풀린 뒤 encoder requires_grad 켜짐")
            print(f"    T9 풀린 첫 update encoder 최대 걸음 {dmax:.4e} (r x lr {ENC_LR:.4e})", flush=True)
    c.ok(any(not torch.equal(pol.student_moe_encoder.state_dict()[k], enc0[k]) for k in enc0), "풀린 뒤 encoder 가 움직임")


# =========================================================================== T10
@test("T10", "critic 점검: critic 입력 · value 유한성 · 정상 miss 광선 칸의 critic 입력 값 (부모 식 -inf -> clip -1 -> x 2.5 = -2.5) 을 기록 · 값과 입력은 안 바뀜 · A · B 같음 · 관문 연결")
def t10(c):
    ref = ref_parent()
    sd = file_state_dict()
    c.ok(P.CRITIC_HEIGHT_START == CRIT_H0 and sd["critic.network.0.weight"].shape[1] == N_LAT + CRIT_H0 + R,
         f"critic height 열 시작 {P.CRITIC_HEIGHT_START} (88) · critic 첫 층 입력 {sd['critic.network.0.weight'].shape[1]} = 32 + 88 + 187")
    txt = open(ENV_YAML, encoding="utf-8").read()
    crit = txt[txt.index("\n  critic:\n"):txt.index("\n  single_obs:\n")]
    terms = re.findall(r"\n    ([a-z_]+):\n      func:", crit)
    c.ok(terms == ["base_lin_vel", "base_ang_vel", "projected_gravity", "velocity_commands", "joint_pos", "joint_vel", "actions",
                   "joint_acc", "joint_torque", "contact_force", "height_scan"], f"env.yaml critic 항 순서 {terms}")
    N = 4
    pos = torch.tensor([[0.0, 0.0, 0.4], [1.0, 0.0, 0.4], [2.0, 0.0, 0.4], [3.0, 0.0, 0.4]])
    hits = torch.zeros(N, R, 3)
    hits[0, 0:5, :] = INF               # env 0: 정상 miss 5
    hits[1, 10, 2] = NAN                # env 1: packet 고장 (NaN)
    hits[3, 100:102, :] = INF           # env 3: 정상 miss 2
    # 부모 critic 의 height 항을 IsaacLab 식으로 손으로: clip(pos z - hit z - 0.5, -1, 1) x 2.5 (observation_manager: clip 다음 scale)
    hcrit = (pos[:, 2:3] - hits[..., 2] - 0.5).clamp(-1.0, 1.0) * 2.5
    g = torch.Generator().manual_seed(51)
    critic = torch.cat([torch.randn(N, CRIT_H0, generator=g), hcrit], dim=-1)
    B = P.S2MapActorCritic(ref, "B").eval()
    A = P.S2MapActorCritic(ref, "A").eval()
    obs_b = make_obs(N, 52, m=M.map_obs("B", pos, hits)[0], critic=critic)
    obs_a = make_obs(N, 52, m=M.map_obs("A", pos, hits)[0], critic=critic)
    crit_before = obs_b["critic"].clone()
    with torch.no_grad():
        v_before = B.evaluate(obs_b)
    rep = P.critic_check(B, obs_b, pos, hits)
    with torch.no_grad():
        v_after = B.evaluate(obs_b)
    c.ok(rep["miss_rays"] == 7, f"정상 miss 광선 7 (env 0 의 5 + env 3 의 2): {rep.get('miss_rays')}")
    c.ok(rep["critic_at_miss_values"] == [-2.5] and rep["critic_at_miss_min"] == -2.5 and rep["critic_at_miss_max"] == -2.5,
         f"정상 miss 칸의 critic 입력 = -2.5 (벽 쪽): {rep.get('critic_at_miss_values')}")
    c.ok(rep["critic_input_nonfinite"] == 1 and rep["critic_input_nonfinite_envs"] == 1, f"critic 입력 NaN 1 칸 · 1 env: {rep}")
    c.ok(rep["value_nonfinite"] == 1, f"value NaN 1 (env 1): {rep['value_nonfinite']}")
    c.ok(bits_equal(obs_b["critic"], crit_before), "critic_check 가 critic 입력을 바꾸지 않음 (NaN 포함 비트)")
    c.ok(bits_equal(v_before, v_after), "critic_check 앞뒤 value 비트 동일")
    c.ok(P.critic_check(A, obs_a, pos, hits) == rep, "A 와 B 의 critic 점검이 같음 (critic 같음)")
    clean = P.critic_check(B, obs_b[2:3], pos[2:3], hits[2:3])
    c.ok(clean["critic_input_nonfinite"] == 0 and clean["value_nonfinite"] == 0 and clean["miss_rays"] == 0, f"고장 없는 env: {clean}")
    gate = M.RunValidityGate()
    gate.add_critic(clean)
    c.ok(gate.valid, "고장 없는 critic 점검은 관문 유효")
    gate.add_critic(rep)
    c.ok(not gate.valid and gate.counts["critic_input_nonfinite"] == 1 and gate.counts["value_nonfinite"] == 1, f"NaN 뒤 관문 무효 {gate.counts}")


# =========================================================================== T11
@test("T11", "전 구간 고정 full_freeze (17f-2 3.1 · 4): encoder_mode 기본값 없음 · W · r 을 넘기면 오류 · encoder 가 optimizer 에 없고 requires_grad False · 어떤 번호에서도 안 풀림 · 여러 step 뒤 encoder 가중치 바이트 · 고정 입력 latent 불변 · step 마다 grad None · Adam 상태 없음 · 판 2 의 r 0 꼴은 delta 0 인데도 이 칸들에 걸림")
def t11(c):
    ref = ref_parent()
    sd = file_state_dict()
    c.ok(inspect.signature(P.make_optimizer).parameters["encoder_mode"].default is inspect.Parameter.empty
         and inspect.signature(P.EncoderControl.__init__).parameters["encoder_mode"].default is inspect.Parameter.empty,
         "make_optimizer · EncoderControl 의 encoder_mode 기본값 없음")
    pol0 = P.S2MapActorCritic(ref, "B")
    c.ok(raises(TypeError, lambda: P.make_optimizer(pol0, PARENT_LAST_LR)), "encoder_mode 없이 부르면 TypeError")
    c.ok(raises(ValueError, lambda: P.make_optimizer(pol0, PARENT_LAST_LR, encoder_mode="freeze")), "모르는 encoder_mode 는 ValueError")
    for kw in ({"encoder_freeze_updates": 50}, {"encoder_lr_ratio": 0.1}, {"encoder_freeze_updates": 50, "encoder_lr_ratio": 0.1},
               {"encoder_freeze_updates": None}, {"encoder_lr_ratio": 0.0}):
        c.ok(raises(TypeError, lambda kw=kw: P.make_optimizer(pol0, PARENT_LAST_LR, encoder_mode="full_freeze", **kw)),
             f"full_freeze 에 {kw} 를 넘기면 TypeError")
    c.ok(all(p.requires_grad for p in pol0.parameters()), "인자 오류는 정책을 건드리기 전에 난다")
    pol = P.S2MapActorCritic(ref, "B").train()
    opt, ctl = P.make_optimizer(pol, PARENT_LAST_LR, encoder_mode="full_freeze")
    enc = list(pol.student_moe_encoder.parameters())
    enc_ids = {id(p) for p in enc}
    opt_ids = [id(p) for g in opt.param_groups for p in g["params"]]
    c.ok(len(enc) == N_ENC, f"student encoder 매개변수 {len(enc)}")
    c.ok([g["name"] for g in opt.param_groups] == ["map_encoder", "actor", "critic", "std"], f"group {[g['name'] for g in opt.param_groups]} (student_encoder 없음)")
    c.ok(not (enc_ids & set(opt_ids)), "encoder 매개변수가 optimizer 에 하나도 없음")
    c.ok(len(opt_ids) == len(set(opt_ids)) and set(opt_ids) == {id(p) for p in pol.parameters()} - enc_ids, "encoder 밖 매개변수는 모두 한 번씩 optimizer 에")
    c.ok(all(not p.requires_grad for p in enc) and all(p.requires_grad for p in non_encoder(pol)), "encoder requires_grad False · 나머지 True")
    idxs = (0, 1, 49, 50, 51, 1999, 2000, 20000, 10 ** 9)
    c.ok(all(ctl.is_frozen(i) for i in idxs), f"번호 {idxs} 모두 고정")
    obs_fix = make_obs(64, 61)
    with torch.no_grad():
        lat0 = pol.student_latent(obs_fix).clone()
        lat_parent = ref.student_moe_encoder(obs_fix["policy"])[0]
    c.ok(bits_equal(lat0, lat_parent), "시작 latent == 부모 student encoder latent (비트)")
    sha0 = tensors_sha(pol.student_moe_encoder.state_dict())
    c.ok(sha0 == tensors_sha({k[len(STUDENT_PREFIX):]: v for k, v in sd.items() if k.startswith(STUDENT_PREFIX)}),
         "시작 encoder 가중치 바이트 == 파일의 student encoder")
    other0 = {k: v.detach().clone() for k, v in pol.state_dict().items() if not k.startswith(STUDENT_PREFIX)}
    obs = terrain_obs(128, 62)
    log = []

    def probe(pol_, opt_, ctl_, k, j):
        log.append((all(p.grad is None for p in enc), all(not p.requires_grad for p in enc), not any(p in opt_.state for p in enc),
                    "student_encoder" not in [g["name"] for g in opt_.param_groups]))

    lr = PARENT_LAST_LR
    n_upd = 3
    n_steps = n_upd * EPOCHS * MBS
    for k in range(n_upd):
        lr, frozen = s2_update(pol, opt, ctl, k, obs, rollout(pol, obs, 64 + k), lr, probe)
        c.ok(frozen, f"update {k} 고정")
    c.ok(len(log) == n_steps and all(all(x) for x in log), f"step {len(log)} 번 모두 encoder grad None · requires_grad False · Adam 상태 없음 · 묶음 없음")
    c.ok(ctl.completed_updates == n_upd and ctl.next_update_index == n_upd and ctl.steps_total == n_steps,
         f"완료 {ctl.completed_updates} · 다음 {ctl.next_update_index} · step {ctl.steps_total}")
    c.ok(lr != PARENT_LAST_LR, f"부모 꼴 adaptive lr 이 실제로 lr 을 바꿈 (덮어쓰기 길이 돌았음 · {lr})")
    c.ok(tensors_sha(pol.student_moe_encoder.state_dict()) == sha0, "여러 step 뒤 encoder 가중치 바이트 그대로 (sha256)")
    with torch.no_grad():
        lat1 = pol.student_latent(obs_fix)
    c.ok(bits_equal(lat1, lat0), "여러 step 뒤 고정 입력의 latent 비트 동일")
    c.ok(not any(p in opt.state for p in enc) and len(opt.state) == len(opt_ids), f"optimizer state 에 encoder 항목 없음 · 항목 {len(opt.state)} == {len(opt_ids)}")
    c.ok({float(s["step"]) for s in opt.state.values()} == {float(n_steps)}, f"encoder 밖 Adam step == {n_steps}")
    moved = [k for k, v in pol.state_dict().items() if not k.startswith(STUDENT_PREFIX) and not torch.equal(v, other0[k])]
    c.ok(any(k.startswith("actor_in.") for k in moved) and any(k.startswith(MAPENC_PREFIX) for k in moved)
         and any(k.startswith("critic.") for k in moved) and "std" in moved, f"actor · map encoder · critic · std 는 움직임 ({len(moved)} 열쇠)")
    # 반례: 판 2 의 「W 뒤 r 0」 꼴 (encoder 가 optimizer 에 lr 0 · requires_grad True · 전체 매개변수 clip). control 없이 같은 횟수.
    polz = P.S2MapActorCritic(ref, "B").train()
    optz = torch.optim.Adam([{"params": ps, "name": n} for n, ps in polz.param_groups().items()], lr=PARENT_LAST_LR)
    encz = list(polz.student_moe_encoder.parameters())
    shaz = tensors_sha(polz.student_moe_encoder.state_dict())
    lrz = PARENT_LAST_LR
    for k in range(n_upd):
        bz = rollout(polz, obs, 64 + k)
        for _e in range(EPOCHS):
            for idx in torch.arange(obs.batch_size[0]).chunk(MBS):
                bb = {key: v[idx] for key, v in bz.items()}
                loss = ppo_like_loss(polz, obs[idx], bb)
                lrz = parent_adaptive_lr(lrz, kl_mean_now(polz, bb))
                for g in optz.param_groups:                       # 판 2 EncoderSchedule.apply (r 0 · 풀린 뒤)
                    g["lr"] = 0.0 if g["name"] == "student_encoder" else lrz
                optz.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(polz.parameters(), MAX_GRAD_NORM)
                optz.step()
    c.ok(tensors_sha(polz.student_moe_encoder.state_dict()) == shaz, "반례 (r 0): encoder delta 0 (가중치 바이트만 보면 통과한다)")
    c.ok(all(p.grad is not None for p in encz) and sum(nz(p.grad) for p in encz) > 0, "반례 (r 0): encoder grad 가 계산됨 (위 grad None 칸에 걸림)")
    c.ok(all(p in optz.state for p in encz) and {float(optz.state[p]["step"]) for p in encz} == {float(n_steps)},
         "반례 (r 0): encoder Adam step · moment 가 진행됨 (위 Adam 상태 칸에 걸림)")


# =========================================================================== T12
@test("T12", "S2 갱신 번호 (17f-2 2.1): 0 부터 · 부모 20000 · runner 번호 · 건너뜀 · 되풀이 · bool 거부 · W50 이면 0 ~ 49 고정 50 해제 · 상태 변경은 그 update 의 첫 minibatch 전 · 저장 · 재개가 끊김 없는 학습과 비트 동일 (full_freeze · schedule W3 경계) · 다른 규칙 재개 거부")
def t12(c):
    ref = ref_parent()
    LR = PARENT_LAST_LR
    src_r = open(RUNNER_CTS, encoding="utf-8").read()
    c.ok("start_it = self.current_learning_iteration" in src_r and "            self.current_learning_iteration = it\n" in src_r
         and 'self.current_learning_iteration = loaded_dict["iter"]' in src_r and '"iter": self.current_learning_iteration' in src_r,
         "runner 번호 규칙 (소스 대조): 시작 = current_learning_iteration · 끝난 it 를 적음 · 저장 iter · 재개 때 저장 iter 로")
    parent_iter = int(torch.load(CKPT, map_location="cpu", weights_only=True)["iter"])
    c.ok(parent_iter == 20000, f"부모 checkpoint iter {parent_iter}")
    pol = P.S2MapActorCritic(ref, "B").train()
    opt, ctl = P.make_optimizer(pol, LR, encoder_mode="full_freeze")
    c.ok(ctl.next_update_index == 0 and ctl.in_update is None, "새 control 의 다음 번호 0")
    c.ok(raises_exact(P.S2IndexError, lambda: ctl.begin_update(parent_iter, LR)), "부모 checkpoint iter 20000 -> S2IndexError")
    runner_after_parent_load = parent_iter      # runner.load(model_20000) 뒤 current_learning_iteration (on_policy_runner_cts.py 278)
    c.ok(raises_exact(P.S2IndexError, lambda: ctl.begin_update(runner_after_parent_load, LR)), "부모를 읽은 runner 의 current_learning_iteration -> S2IndexError")
    c.ok(raises_exact(P.S2IndexError, lambda: ctl.begin_update(1, LR)), "첫 번호 1 (0 을 건너뜀) -> S2IndexError")
    c.ok(raises(TypeError, lambda: ctl.begin_update(False, LR)) and raises(TypeError, lambda: ctl.begin_update(0.0, LR))
         and raises(TypeError, lambda: ctl.begin_update(torch.tensor(0), LR)), "번호가 bool · float · tensor 면 TypeError (False == 0 이어도)")
    c.ok(ctl.next_update_index == 0 and ctl.in_update is None and ctl.steps_total == 0, "거절된 호출은 상태를 바꾸지 않음")
    obs = terrain_obs(64, 91)
    b = rollout(pol, obs, 93)
    ctl.begin_update(0, LR)
    c.ok(raises_exact(P.S2IndexError, lambda: ctl.begin_update(0, LR)) and raises_exact(P.S2IndexError, lambda: ctl.begin_update(1, LR)),
         "끝나지 않은 update 위에 다시 시작 -> S2IndexError")
    c.ok(raises_exact(P.S2IndexError, ctl.state_dict), "update 도중 저장 -> S2IndexError")
    c.ok(raises_exact(P.S2IndexError, lambda: ctl.end_update(1)), "다른 번호로 끝냄 -> S2IndexError")
    c.ok(raises_exact(P.S2ControlError, lambda: ctl.end_update(0)), "optimizer step 없는 update 를 끝내면 S2ControlError (갱신 생략)")
    opt.zero_grad(set_to_none=True)
    ppo_like_loss(pol, obs, b).backward()
    torch.nn.utils.clip_grad_norm_(P.trainable_params(pol), MAX_GRAD_NORM)
    ctl.enforce_groups(opt, LR)
    opt.step()
    ctl.end_update(0)
    c.ok(ctl.next_update_index == 1 and ctl.steps_total == 1, f"한 update 뒤 다음 번호 {ctl.next_update_index} · step {ctl.steps_total}")
    ctl50 = P.EncoderControl(P.S2MapActorCritic(ref, "B"), "schedule", freeze_updates=50, encoder_lr_ratio=0.1)
    c.ok([ctl50.is_frozen(i) for i in (0, 1, 48, 49, 50, 51, 1999)] == [True, True, True, True, False, False, False],
         "W50: 번호 0 ~ 49 고정 · 50 부터 해제")
    # 저장 · 재개: 끊김 없는 5 update vs 2 update 뒤 저장 (메모리에 둔 채 원래 학습을 이어 감) · 새 정책으로 재개해 3 update
    obs = terrain_obs(96, 95)

    def snap(pol_, opt_, ctl_, k, j, log):
        e = list(pol_.student_moe_encoder.parameters())
        log.append({"k": k, "j": j, "frozen": ctl_.frozen, "grad": [p.grad is not None for p in e], "rg": [p.requires_grad for p in e],
                    "lrs": {g["name"]: g["lr"] for g in opt_.param_groups}, "base": ctl_.base_lr})

    def run(pol_, opt_, ctl_, ks, lr, log):
        for k in ks:
            lr, _f = s2_update(pol_, opt_, ctl_, k, obs, rollout(pol_, obs, 300 + k), lr, probe=lambda *a: snap(*a, log))
        return lr

    for mode, kw, other in (("full_freeze", {}, ("schedule", {"encoder_freeze_updates": 3, "encoder_lr_ratio": 0.25})),
                            ("schedule", {"encoder_freeze_updates": 3, "encoder_lr_ratio": 0.25},
                             ("schedule", {"encoder_freeze_updates": 4, "encoder_lr_ratio": 0.25}))):
        polU = P.S2MapActorCritic(ref, "B").train()
        optU, ctlU = P.make_optimizer(polU, LR, encoder_mode=mode, **kw)
        logU = []
        lr_mid = run(polU, optU, ctlU, range(0, 2), LR, logU)
        sd_ctl = ctlU.state_dict()
        sd_pol = {k: v.detach().clone() for k, v in polU.state_dict().items()}
        c.ok(sd_ctl["completed_updates"] == 2 and sd_ctl["next_update_index"] == 2 and sd_ctl["base_lr"] == lr_mid
             and sd_ctl["encoder_mode"] == mode and sd_ctl["unit"] == "ppo_iteration",
             f"{mode}: 저장에 완료 수 · 다음 번호 · lr · 규칙 · 단위 {[(k, sd_ctl[k]) for k in ('completed_updates', 'next_update_index', 'base_lr')]}")
        if mode == "schedule":
            c.ok(not any(i < N_ENC for i in sd_ctl["optimizer"]["state"]), "schedule 고정 중 저장: encoder (첫 group · 번호 0 ~ 15) 의 Adam 상태 없음")
        lr_end = run(polU, optU, ctlU, range(2, 5), lr_mid, logU)
        buf = io.BytesIO()
        torch.save({"policy": sd_pol, "s2_control": sd_ctl}, buf)
        buf.seek(0)
        saved = torch.load(buf, map_location="cpu", weights_only=True)
        polR = P.S2MapActorCritic(ref, "B").train()
        polR.load_state_dict(saved["policy"])
        optR, ctlR = P.make_optimizer(polR, LR, encoder_mode=mode, **kw)
        ctlR.load_state_dict(saved["s2_control"])
        c.ok(ctlR.next_update_index == 2 and ctlR.completed_updates == 2 and ctlR.base_lr == lr_mid,
             f"{mode} 재개: 다음 번호 {ctlR.next_update_index} · lr {ctlR.base_lr} (저장 {lr_mid})")
        runner_resume_it = 1   # S2 runner 가 0 · 1 을 끝내고 저장하면 iter 1 (runner 140 · 173) · 재개 loop 는 1 부터 (108)
        c.ok(raises_exact(P.S2IndexError, lambda: ctlR.begin_update(runner_resume_it, ctlR.base_lr))
             and raises_exact(P.S2IndexError, lambda: ctlR.begin_update(0, ctlR.base_lr))
             and raises_exact(P.S2IndexError, lambda: ctlR.begin_update(3, ctlR.base_lr)),
             f"{mode} 재개: runner 번호 1 · W 다시 시작 0 · 건너뜀 3 -> S2IndexError")
        lrR = run(polR, optR, ctlR, range(2, 5), ctlR.base_lr, [])
        sU, sR = polU.state_dict(), polR.state_dict()
        c.ok(set(sU) == set(sR) and all(bits_equal(sU[k], sR[k]) for k in sU), f"{mode}: 재개 뒤 정책 매개변수가 끊김 없는 학습과 비트 동일")
        oU, oR = optU.state_dict(), optR.state_dict()
        c.ok(oU["state"].keys() == oR["state"].keys()
             and all(oU["state"][i].keys() == oR["state"][i].keys() and all(same_tensor(oU["state"][i][q], oR["state"][i][q]) for q in oU["state"][i])
                     for i in oU["state"]), f"{mode}: optimizer 상태 (step · exp_avg · exp_avg_sq) 비트 동일 ({len(oU['state'])} 항목)")
        c.ok([(g["name"], g["lr"]) for g in oU["param_groups"]] == [(g["name"], g["lr"]) for g in oR["param_groups"]]
             and lrR == lr_end and ctlR.base_lr == ctlU.base_lr, f"{mode}: group lr · base lr 같음 ({lr_end})")
        c.ok(ctlR.completed_updates == ctlU.completed_updates == 5 and ctlR.steps_total == ctlU.steps_total == 5 * EPOCHS * MBS,
             f"{mode}: 완료 {ctlU.completed_updates} · step {ctlU.steps_total}")
        if mode == "schedule":
            encU = list(polU.student_moe_encoder.parameters())
            c.ok({float(optU.state[p]["step"]) for p in encU} == {float(2 * EPOCHS * MBS)}, "schedule W3: encoder Adam step = 해제 뒤 step 수 (update 3 · 4)")
            k2 = [x for x in logU if x["k"] == 2]
            c.ok(len(k2) == EPOCHS * MBS and all(x["frozen"] and not any(x["grad"]) and not any(x["rg"]) and x["lrs"]["student_encoder"] == 0.0 for x in k2),
                 "W3: update 2 의 모든 minibatch 고정 (grad None · requires_grad False · encoder lr 0)")
            f3 = [x for x in logU if x["k"] == 3][0]
            c.ok(f3["j"] == 0 and not f3["frozen"] and all(f3["grad"]) and all(f3["rg"]) and f3["lrs"]["student_encoder"] == 0.25 * f3["base"]
                 and all(v == f3["base"] for n, v in f3["lrs"].items() if n != "student_encoder"),
                 "W3: update 3 의 첫 minibatch 부터 해제 (grad 있음 · requires_grad True · encoder lr = 0.25 x base)")
            c.ok([x["frozen"] for x in logU if x["j"] == 0] == [True, True, True, False, False], "update 0 ~ 4 첫 minibatch 의 고정 [T T T F F]")
        polX = P.S2MapActorCritic(ref, "B")
        _ox, ctlX = P.make_optimizer(polX, LR, encoder_mode=other[0], **other[1])
        c.ok(raises(ValueError, lambda: ctlX.load_state_dict(saved["s2_control"])), f"{mode} 저장을 다른 규칙 {other} 에 읽으면 ValueError")
        bad = dict(saved["s2_control"])
        bad["next_update_index"] = 3
        polY = P.S2MapActorCritic(ref, "B")
        _oy, ctlY = P.make_optimizer(polY, LR, encoder_mode=mode, **kw)
        c.ok(raises(ValueError, lambda: ctlY.load_state_dict(bad)), f"{mode}: 다음 번호 != 완료 수 인 저장은 ValueError")


# =========================================================================== T13
@test("T13", "group lr 덮어쓰기 막기 (17f-2 3.2): 부모 moe_cts 꼴 (모든 group 에 같은 lr · 소스 대조) 뒤 enforce_groups 가 encoder 묶음을 0 · r x base 로 되돌림 · enforce 없는 step · enforce 뒤 바뀐 step · update 밖 step 은 hook 이 멈춤 · 고정 위반 다섯을 하나씩 (각 1 문제) 예외 · base_lr 오류")
def t13(c):
    ref = ref_parent()
    src = open(MOE_CTS, encoding="utf-8").read()
    c.ok(re.search(r"\n\s+for param_group in self\.optimizer\.param_groups:\n\s+param_group\[\"lr\"\] = self\.learning_rate\n", src) is not None,
         "부모 moe_cts: adaptive lr 뒤 모든 param group 에 같은 lr (흉내 낸 꼴이 소스와 같음)")
    c.ok(re.search(r"if kl_mean > self\.desired_kl \* 2\.0:\n\s+self\.learning_rate = max\(1e-5, self\.learning_rate / 1\.5\)\n"
                   r"\s+elif kl_mean < self\.desired_kl / 2\.0 and kl_mean > 0\.0:\n\s+self\.learning_rate = min\(1e-2, self\.learning_rate \* 1\.5\)", src) is not None,
         "부모 moe_cts: adaptive lr 규칙 (1.5 배 · 상하한) 이 시험의 parent_adaptive_lr 과 같음")
    c.ok("params_to_clip = itertools.chain.from_iterable(g['params'] for g in self.optimizer.param_groups)" in src,
         "부모 moe_cts: clip 은 PPO optimizer 묶음의 매개변수 (encoder 는 따로 · 365 ~ 366 · 411)")
    LR = PARENT_LAST_LR
    LR2 = 0.0002562890625000001          # 1.5 x 0.00017085937500000009 (손 계산 · KL 이 desired / 2 보다 작을 때)
    ENC2 = 2.5628906250000014e-05        # r x base = 0.1 x 0.0002562890625000001 (손 계산 · 0.1 x 1.5 x LR 순서로 곱하면 ...017e-05 로 1 ulp 다름)
    c.ok(parent_adaptive_lr(LR, DESIRED_KL / 4) == LR2, "adaptive lr 손 계산 1.5 배")
    obs = terrain_obs(64, 71)
    # (a) schedule W1 r0.1: update 0 고정 · update 1 해제
    pol = P.S2MapActorCritic(ref, "B").train()
    opt, ctl = P.make_optimizer(pol, LR, encoder_mode="schedule", encoder_freeze_updates=1, encoder_lr_ratio=0.1)
    b = rollout(pol, obs, 73)

    def backward_once(p_, o_, b_):
        o_.zero_grad(set_to_none=True)
        ppo_like_loss(p_, obs, b_).backward()
        torch.nn.utils.clip_grad_norm_(P.trainable_params(p_), MAX_GRAD_NORM)

    ctl.begin_update(0, LR)
    parent_overwrite(opt, LR)
    c.ok(lr_of(opt, "student_encoder") == LR, "부모 꼴 덮어쓰기는 고정 중 encoder 묶음 lr 을 0 에서 base 로 바꿈 (막지 않으면 깨짐)")
    c.ok(len(ctl.audit(opt, LR)) == 1, f"audit 이 그 하나를 잡음: {ctl.audit(opt, LR)}")
    backward_once(pol, opt, b)
    fixed = ctl.enforce_groups(opt, LR)
    c.ok(fixed == {"student_encoder": (LR, 0.0)} and lr_of(opt, "student_encoder") == 0.0, f"enforce_groups 가 고정 중 encoder lr 을 0 으로 되돌림 {fixed}")
    opt.step()
    ctl.end_update(0)
    ctl.begin_update(1, LR)
    parent_overwrite(opt, LR2)
    backward_once(pol, opt, b)
    fixed = ctl.enforce_groups(opt, LR2)
    c.ok(fixed == {"student_encoder": (LR2, ENC2)} and lr_of(opt, "student_encoder") == ENC2
         and all(g["lr"] == LR2 for g in opt.param_groups if g["name"] != "student_encoder"),
         f"해제 뒤 adaptive lr 1.5 배 · 덮어쓰기 -> encoder 0.1 x base = {ENC2} · 나머지 {LR2} ({fixed})")
    opt.step()
    backward_once(pol, opt, b)
    ctl.enforce_groups(opt, LR2)
    parent_overwrite(opt, LR2)
    c.ok(raises_exact(P.S2ControlError, opt.step), "enforce 뒤 부모 꼴 덮어쓰기 -> step 전 hook 이 S2ControlError")
    ctl.enforce_groups(opt, LR2)
    opt.step()
    c.ok(raises_exact(P.S2ControlError, opt.step), "enforce 없이 이어서 step -> S2ControlError (step 마다 enforce)")
    ctl.end_update(1)
    c.ok(ctl.steps_total == 3 and ctl.completed_updates == 2, f"막힌 step 은 세지 않음 (step {ctl.steps_total})")
    c.ok(raises_exact(P.S2ControlError, opt.step), "update 밖 step -> S2ControlError")
    c.ok(raises_exact(P.S2ControlError, lambda: ctl.enforce_groups(opt, LR2)), "update 밖 enforce -> S2ControlError")
    # (b) full_freeze: 부모 꼴 덮어쓰기가 encoder 에 닿지 않음 · 위반 주입
    polf = P.S2MapActorCritic(ref, "B").train()
    optf, ctlf = P.make_optimizer(polf, LR, encoder_mode="full_freeze")
    bf = rollout(polf, obs, 74)
    ctlf.begin_update(0, LR)
    parent_overwrite(optf, LR2)
    backward_once(polf, optf, bf)
    fixed = ctlf.enforce_groups(optf, LR2)
    c.ok(fixed == {} and all(g["lr"] == LR2 for g in optf.param_groups) and len(ctlf.audit(optf, LR2)) == 0,
         f"full_freeze: 덮어쓰기가 encoder 에 닿지 않음 (optimizer 에 없음) · 고칠 것 없음 {fixed}")
    enc = list(polf.student_moe_encoder.parameters())
    actor_group = [g for g in optf.param_groups if g["name"] == "actor"][0]

    def inject(name, do, undo):
        do()
        try:
            n = len(ctlf.audit(optf, LR2))
            hit = raises_exact(P.S2ControlError, lambda: ctlf.enforce_groups(optf, LR2))
        finally:
            undo()
        c.ok(n == 1 and hit, f"{name}: audit 문제 {n} 개 (1 이어야 함) · enforce 예외 {hit}")

    inject("encoder 매개변수를 actor 묶음에 끼움", lambda: actor_group["params"].append(enc[0]), lambda: actor_group["params"].pop())
    inject("encoder requires_grad True", lambda: enc[0].requires_grad_(True), lambda: enc[0].requires_grad_(False))
    inject("고정 encoder 에 남은 grad", lambda: setattr(enc[0], "grad", torch.zeros_like(enc[0])), lambda: setattr(enc[0], "grad", None))
    inject("encoder 의 Adam 상태", lambda: optf.state[enc[0]].update({"step": torch.tensor(1.0)}), lambda: optf.state.pop(enc[0]))
    inject("encoder 밖 매개변수 requires_grad False", lambda: polf.std.requires_grad_(False), lambda: polf.std.requires_grad_(True))
    c.ok(all(raises(ValueError, lambda v=v: ctlf.enforce_groups(optf, v)) for v in (NAN, INF, 0.0, -1e-4))
         and raises(TypeError, lambda: ctlf.enforce_groups(optf, True)) and raises(TypeError, lambda: ctlf.enforce_groups(optf, torch.tensor(LR))),
         "base_lr NaN · inf · 0 · 음수 ValueError · bool · tensor TypeError")
    c.ok(all(g["lr"] == LR2 for g in optf.param_groups), "거절된 base_lr 은 group lr 을 바꾸지 않음")
    # 같은 묶음 · 같은 lr 로 만든 쌍둥이 optimizer: audit 은 통과하는 꼴이라 「묶인 optimizer 인가」 확인만이 잡는다 (판 3 변이 1 차에서 q28 을 놓친 뒤 고침)
    twin = torch.optim.Adam([{"params": list(g["params"]), "name": g["name"]} for g in optf.param_groups], lr=LR2)
    c.ok(len(ctlf.audit(twin, LR2)) == 0, "쌍둥이 optimizer 는 audit 을 통과하는 꼴")
    c.ok(raises_exact(P.S2ControlError, lambda: ctlf.enforce_groups(twin, LR2)), "묶이지 않은 (쌍둥이) optimizer -> S2ControlError")
    other_opt = torch.optim.Adam(polf.actor_rest.parameters(), lr=LR)
    c.ok(raises_exact(P.S2ControlError, lambda: ctlf.enforce_groups(other_opt, LR2)), "묶음이 다른 optimizer -> S2ControlError")
    c.ok(len(ctlf.audit(optf, LR2)) == 0 and ctlf.enforce_groups(optf, LR2) == {}, "되돌린 뒤 audit 빈 목록 · enforce 통과 (관문이 늘 예외인 것이 아님)")
    optf.step()
    ctlf.end_update(0)


# =========================================================================== T14
@test("T14", "clipping 범위 (17f-2 3.1): trainable_params 에 고정 encoder 없음 · 실제 역전파에서 encoder grad None · clip norm == encoder 밖 손 계산 norm · 반례 (actor 3 · encoder 4 · 한도 1) 에서 판 2 방식 actor 0.6 · 판 3 방식 1 · 실제 역전파의 r 0 꼴도 norm 이 커짐")
def t14(c):
    ref = ref_parent()
    LR = PARENT_LAST_LR
    obs = terrain_obs(128, 81)
    polf = P.S2MapActorCritic(ref, "B").train()
    optf, ctlf = P.make_optimizer(polf, LR, encoder_mode="full_freeze")
    enc_ids = {id(p) for p in polf.student_moe_encoder.parameters()}
    tp = P.trainable_params(polf)
    c.ok(not ({id(p) for p in tp} & enc_ids) and len(tp) == len(list(polf.parameters())) - N_ENC,
         f"trainable_params 에 encoder 없음 ({len(tp)} = 전체 {len(list(polf.parameters()))} - {N_ENC})")
    c.ok({id(p) for p in tp} == {id(p) for g in optf.param_groups for p in g["params"]}, "full_freeze: trainable_params == optimizer 의 매개변수")
    b = rollout(polf, obs, 83)
    ctlf.begin_update(0, LR)
    optf.zero_grad(set_to_none=True)
    ppo_like_loss(polf, obs, b).backward()
    c.ok(all(p.grad is None for p in polf.student_moe_encoder.parameters()), "실제 역전파: 고정 encoder grad None")
    hand = grad_norm(non_encoder(polf))
    tot = float(torch.nn.utils.clip_grad_norm_(P.trainable_params(polf), float("inf")))
    c.ok(hand > 0 and abs(tot - hand) <= 1e-5 * hand, f"clip norm {tot:.6e} == encoder 밖 손 계산 norm {hand:.6e}")
    ctlf.enforce_groups(optf, LR)
    optf.step()
    ctlf.end_update(0)

    def set_grads(pol_, other_norm, enc_norm, seed):
        g = torch.Generator().manual_seed(seed)
        enc_ = list(pol_.student_moe_encoder.parameters())
        for group, target in ((non_encoder(pol_), other_norm), (enc_, enc_norm)):
            if target is None:
                for p in group:
                    p.grad = None
                continue
            raw = [torch.randn(p.shape, generator=g, dtype=torch.float64) for p in group]
            s = target / math.sqrt(sum(float(x.pow(2).sum()) for x in raw))
            for p, x in zip(group, raw):
                p.grad = (x * s).to(torch.float32)

    # 판 2 방식: W 뒤 r 0 (encoder requires_grad True · grad 있음) 에서 전체 매개변수로 clip (판 2 test_s2.py 465 · 697)
    pol2 = P.S2MapActorCritic(ref, "B").train()
    set_grads(pol2, 3.0, 4.0, 84)
    pre_a, pre_e = grad_norm(non_encoder(pol2)), grad_norm(pol2.student_moe_encoder.parameters())
    tot2 = float(torch.nn.utils.clip_grad_norm_(pol2.parameters(), 1.0))
    a2 = grad_norm(non_encoder(pol2))
    # 판 3 방식: full_freeze · trainable_params 로 clip. encoder 에 남은 grad (norm 4) 가 있어도 norm 에 안 들어감
    pol3 = P.S2MapActorCritic(ref, "B").train()
    P.make_optimizer(pol3, LR, encoder_mode="full_freeze")
    set_grads(pol3, 3.0, 4.0, 84)
    tot3 = float(torch.nn.utils.clip_grad_norm_(P.trainable_params(pol3), 1.0))
    a3 = grad_norm(non_encoder(pol3))
    e3 = grad_norm(pol3.student_moe_encoder.parameters())
    set_grads(pol3, 3.0, None, 84)
    tot3n = float(torch.nn.utils.clip_grad_norm_(P.trainable_params(pol3), 1.0))
    a3n = grad_norm(non_encoder(pol3))
    c.ok(abs(pre_a - 3.0) < 1e-4 and abs(pre_e - 4.0) < 1e-4, f"반례 준비: encoder 밖 norm {pre_a:.6f} · encoder norm {pre_e:.6f}")
    c.ok(abs(tot2 - 5.0) < 1e-4 and abs(a2 - 0.6) < 1e-4, f"판 2 방식: 전체 norm {tot2:.6f} (5) · clip 뒤 encoder 밖 norm {a2:.6f} (약 0.6)")
    c.ok(abs(tot3 - 3.0) < 1e-4 and abs(a3 - 1.0) < 1e-4 and abs(e3 - 4.0) < 1e-4,
         f"판 3 방식: clip norm {tot3:.6f} (3 · encoder 안 들어감) · encoder 밖 {a3:.6f} (약 1) · 남은 encoder grad {e3:.6f} 안 건드림")
    c.ok(abs(tot3n - 3.0) < 1e-4 and abs(a3n - 1.0) < 1e-4, f"판 3 방식 (encoder grad None): encoder 밖 {a3n:.6f}")
    print(f"    T14 반례 (actor 3 · encoder 4 · 한도 1): 판 2 방식 encoder 밖 norm {a2:.6f} · 판 3 방식 {a3:.6f}", flush=True)
    # 실제 역전파: 판 2 의 r 0 꼴 (encoder requires_grad True) 은 encoder grad 가 생겨 clip 전체 norm 이 커짐 · encoder 밖 grad 는 같음
    polz = P.S2MapActorCritic(ref, "B").train()
    polq = P.S2MapActorCritic(ref, "B").train()
    P.make_optimizer(polq, LR, encoder_mode="full_freeze")
    bz = rollout(polz, obs, 85)
    ppo_like_loss(polz, obs, bz).backward()
    ppo_like_loss(polq, obs, bz).backward()
    ez, oz, oq = grad_norm(polz.student_moe_encoder.parameters()), grad_norm(non_encoder(polz)), grad_norm(non_encoder(polq))
    tot_v2, tot_v3 = math.hypot(oz, ez), oq
    c.ok(ez > 0 and abs(oz - oq) <= 1e-5 * oq and tot_v2 > tot_v3,
         f"실제 역전파: r 0 꼴 encoder norm {ez:.4e} · encoder 밖 norm {oz:.4e} vs 판 3 {oq:.4e} · clip 전체 norm {tot_v2:.4e} > {tot_v3:.4e}")
    print(f"    T14 실제 역전파 (한 minibatch): encoder 밖 norm {oq:.4e} · r 0 꼴 encoder norm {ez:.4e} · 한도 1 에서 encoder 밖 배율 "
          f"판 2 {min(1.0, 1.0 / (tot_v2 + 1e-6)):.4f} · 판 3 {min(1.0, 1.0 / (tot_v3 + 1e-6)):.4f}", flush=True)


def main():
    only = set(sys.argv[1:])
    fails, cells = 0, 0
    # T7 (부모 보존 · 체크포인트 sha256 「시험 뒤」) 은 다른 시험을 모두 돈 뒤에 돈다
    for tid, desc, fn in [t for t in TESTS if t[0] != "T7"] + [t for t in TESTS if t[0] == "T7"]:
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
