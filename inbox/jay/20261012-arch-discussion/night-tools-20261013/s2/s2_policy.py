# -*- coding: utf-8 -*-
"""S2 A/B 정책 (판 2): 부모 E1 20000 의 student 경로에 0 으로 시작하는 지도 열을 붙인 actor-critic (CPU 로 짓기 · 학습 없음).

분류: A/정책학습 · S2 「이상적 지도 입력 비교」 A/B 입력 경로 1 단계 판 2 (CPU · 학습 없음)
작성: 오흥재 (lead 세션 · Claude 하위 작업 작성) · 판 1 2026-10-13 19:21 · 판 2 2026-10-13 23:32
근거: inbox/jay/20261012-arch-discussion/DESIGN-s2-ab-v1.md 3 절 · 4 절 · 6 절 (다르면 6 절) · VERIFY-astra-17d.md 6.1 ~ 6.3
      source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py 17 ~ 40 (StudentMoEEncoder) · 86 ~ 247 (act · act_inference · evaluate)
      source/rsl_rl/rsl_rl/networks/moe.py (MLP · MoE · L2Norm) · algorithms/moe_cts.py 93 ~ 101 (optimizer 묶음 · lr)
      E1 run params/agent.yaml (구조 값) · params/env.yaml 865 ~ 1177 (critic 항 순서 · height_scan 이 마지막 187 열)
      model_20000.pt (optimizer_state_dict lr 0.00017085937500000009)
요지: 지도 입력 m [N, 374] -> map encoder (374 -> 128 -> 64 · ELU) -> z_map 64. actor 첫 층은 [latent 32, single_obs 45] 77 열은
      부모 값 그대로, z_map 64 열은 0 으로 시작. forward 에 no_grad 는 없고, student encoder 의 고정 · 학습률은 EncoderSchedule
      (처음 W update 고정 · 그 뒤 actor 학습률의 r 배 · W · r 은 기본값 없이 인자로만) 이 정한다.
      critic 은 부모 구조 · 가중치에서 시작 (latent.detach() + critic obs) 하고 값은 바꾸지 않는다. critic_check 가 critic 입력 ·
      value 의 유한성과 정상 miss 광선 칸의 critic 입력 값을 잰다. teacher encoder 는 가져오지 않는다.
      A · B 는 구조 · 초기값이 같고 actor 의 지도 입력만 다르다 (A 도 지형 정보가 든 critic 을 학습 신호로 쓴다).
상태: CPU 시험 (test_s2.py) · 변이 (mutate_s2.py) 만 거침. 학습 · Isaac · GPU 실행 없음

설계와 형태가 다른 곳 (값 · 수식은 같음)
  actor 첫 층을 Linear(141) 한 장이 아니라 Linear(77, 512) (부모 값) + Linear(64, 512, bias 없음, 0 시작) 두 장의 합으로 둔다.
  [W_parent | W_map] @ [x; z] + b 와 수식이 같고, Adam 은 원소별 · grad clip 은 전체 norm 이라 학습도 같다.
  까닭: 0 초기화 동치를 「부모와 같은 모양의 matmul + 정확한 0」 으로 만들어, BLAS 가 K (77 vs 141) 에 따라 합 순서를 바꿔도
  부모와 비트 동일이 깨지지 않게 한다. 141 열 행렬이 필요하면 actor_first_layer_weight() 로 꺼낸다.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import os
import sys

import torch
import torch.nn as nn
from torch.distributions import Normal

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import s2_map_obs as M  # noqa: E402  (같은 폴더의 것 · 변이 사본에서는 사본 폴더의 것)

E1_RUN = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192"
E1_CKPT = E1_RUN + "/model_20000.pt"
MAP_HIDDEN_DIMS = (128,)
MAP_LATENT_DIM = 64
MAP_INIT_SEED = 0             # A · B 가 같은 시드로 map encoder 를 지어 출발점이 같다
PARENT_OBS_GROUPS = {"policy": ["policy"], "critic": ["critic"]}
# critic obs 항 순서 (env.yaml 865 ~ 1177 · history 없음 · 항끼리 이음): base_lin_vel 3 · base_ang_vel 3 · projected_gravity 3 ·
# velocity_commands 3 · joint_pos 12 · joint_vel 12 · actions 12 · joint_acc 12 · joint_torque 12 · contact_force 16 (발 4 x (이력 3 + 1))
# = 88 다음에 height_scan 187 (열 88 ~ 274 · 체크포인트 critic 첫 층 307 - latent 32 = 275 와 맞음)
CRITIC_HEIGHT_START = 88


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _load_agent_yaml(path: str) -> dict:
    """rsl_rl 이 적은 agent.yaml (!!python/tuple 포함) 을 객체 생성 없이 읽는다."""
    import yaml

    class _Loader(yaml.SafeLoader):
        pass

    _Loader.add_constructor("tag:yaml.org,2002:python/tuple", lambda ld, node: tuple(ld.construct_sequence(node)))
    with open(path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=_Loader)


def load_parent_cpu(ckpt: str = E1_CKPT, agent_yaml: str | None = None):
    """부모 ActorCriticMoECTS 를 CPU 에 짓고 체크포인트를 strict 로 읽는다. 파일은 읽기만 한다.

    구조 값은 학습 run 의 params/agent.yaml 에서, 입력 차원은 체크포인트 가중치 모양에서 읽는다.
    돌려주는 meta: dims · iter · last_lr (부모 PPO optimizer 의 마지막 lr) · betas · sha256.
    """
    from tensordict import TensorDict
    from rsl_rl.modules.actor_critic_moe_cts import ActorCriticMoECTS

    agent_yaml = agent_yaml or os.path.join(os.path.dirname(ckpt), "params", "agent.yaml")
    agent = _load_agent_yaml(agent_yaml)
    pc = agent["policy"]
    ck = torch.load(ckpt, map_location="cpu", weights_only=True)
    sd = ck["model_state_dict"]
    latent_dim = int(pc["latent_dim"])
    n_pol = sd["student_moe_encoder.moe.experts.backbone.network.0.weight"].shape[1]
    n_crit = sd["critic.network.0.weight"].shape[1] - latent_dim
    n_single = sd["actor.network.0.weight"].shape[1] - latent_dim
    n_act = int(sd["std"].shape[0])
    obs = TensorDict({"policy": torch.zeros(1, n_pol), "critic": torch.zeros(1, n_crit), "single_obs": torch.zeros(1, n_single)},
                     batch_size=[1])
    kw = {k: pc[k] for k in ("actor_hidden_dims", "critic_hidden_dims", "teacher_encoder_hidden_dims", "student_encoder_hidden_dims",
                             "expert_num", "activation", "init_noise_std", "noise_std_type", "state_dependent_std", "latent_dim",
                             "norm_type", "actor_obs_normalization", "critic_obs_normalization") if k in pc}
    with contextlib.redirect_stdout(io.StringIO()):
        parent = ActorCriticMoECTS(obs, copy.deepcopy(PARENT_OBS_GROUPS), n_act, **kw)
    parent.load_state_dict(sd, strict=True)
    parent.eval()
    lrs = sorted({float(g["lr"]) for g in ck["optimizer_state_dict"]["param_groups"]})
    if len(lrs) != 1:
        raise ValueError(f"부모 PPO optimizer 의 param group lr 이 하나가 아니다: {lrs}")
    meta = {
        "ckpt": ckpt,
        "agent_yaml": agent_yaml,
        "iter": int(ck["iter"]),
        "dims": {"policy": n_pol, "critic": n_crit, "single_obs": n_single, "actions": n_act, "latent": latent_dim},
        "last_lr": lrs[0],
        "student_encoder_lr": float(ck["optimizer_stu_enc_state_dict"]["param_groups"][0]["lr"]),
        "betas": tuple(float(b) for b in agent["algorithm"]["betas"]),
        "weight_decay": float(agent["algorithm"]["weight_decay"]),
        "ckpt_sha256": sha256_file(ckpt),
    }
    return parent, meta


class S2MapActorCritic(nn.Module):
    """설계 3 절 구조. obs 는 parent 와 같은 열쇠 (policy · single_obs · critic) 에 「map」 [N, 374] 을 더한 것."""

    is_recurrent: bool = False

    def __init__(self, parent: nn.Module, mode: str, map_dim: int = M.MAP_DIM, map_hidden_dims=MAP_HIDDEN_DIMS,
                 map_latent_dim: int = MAP_LATENT_DIM, map_init_seed: int = MAP_INIT_SEED, guard_a_constant: bool = True):
        super().__init__()
        from rsl_rl.networks.moe import MLP

        if mode not in ("A", "B"):
            raise ValueError(f"mode 는 A 또는 B: {mode!r}")
        if getattr(parent, "state_dependent_std", False) or getattr(parent, "noise_std_type", "scalar") != "scalar":
            raise NotImplementedError("부모가 scalar std 가 아니다 (E1 은 scalar · state_dependent_std false)")
        if getattr(parent, "actor_obs_normalization", False) or getattr(parent, "critic_obs_normalization", False):
            raise NotImplementedError("부모가 관측 정규화를 쓴다 (E1 은 actor · critic 모두 끔)")
        self.mode = mode
        self.guard_a_constant = guard_a_constant
        self.obs_groups = copy.deepcopy(parent.obs_groups)
        self.num_actions = parent.num_actions
        self.num_single_obs = parent.num_single_obs
        self.map_dim = map_dim
        self.map_latent_dim = map_latent_dim

        # 부모에서 복사 (깊은 복사: 부모와 텐서 저장소를 나누지 않는다)
        self.student_moe_encoder = copy.deepcopy(parent.student_moe_encoder)
        self.actor_obs_normalizer = nn.Identity()
        self.single_obs_normalizer = nn.Identity()
        self.critic_obs_normalizer = nn.Identity()
        net = parent.actor.network
        self.actor_in = copy.deepcopy(net[0])            # Linear(latent + single_obs = 77, 512) · 부모 값
        self.actor_rest = copy.deepcopy(net[1:])         # ELU · Linear(512, 256) · ... · Linear(128, 12) · 열쇠 1 ~ 6 그대로
        self.critic = copy.deepcopy(parent.critic)
        self.std = nn.Parameter(parent.std.detach().clone())

        # 새 부분: map encoder (A · B 같은 시드) 와 0 으로 시작하는 actor 첫 층의 지도 열
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(map_init_seed)
            self.map_encoder = MLP(map_dim, map_latent_dim, list(map_hidden_dims), activation="elu")
        self.actor_in_map = nn.Linear(map_latent_dim, self.actor_in.out_features, bias=False)
        nn.init.zeros_(self.actor_in_map.weight)

        self.distribution = None
        Normal.set_default_validate_args(False)

    # ------------------------------------------------------------------ 입력
    def get_actor_obs(self, obs) -> torch.Tensor:
        return torch.cat([obs[g] for g in self.obs_groups["policy"]], dim=-1)

    def get_critic_obs(self, obs) -> torch.Tensor:
        return torch.cat([obs[g] for g in self.obs_groups["critic"]], dim=-1)

    def map_input(self, obs) -> torch.Tensor:
        m = obs["map"]
        if m.shape[-1] != self.map_dim:
            raise ValueError(f"지도 입력 열 수 {m.shape[-1]} != {self.map_dim}")
        if self.mode == "A" and self.guard_a_constant and not M.is_a_constant(m, self.map_dim // 2):
            raise ValueError("A 정책에 상수가 아닌 지도 입력이 들어왔다 (A 는 height · mask 모두 상수)")
        return m

    def student_latent(self, obs) -> torch.Tensor:
        obs_a = self.actor_obs_normalizer(self.get_actor_obs(obs))
        latent, _ = self.student_moe_encoder(obs_a)
        return latent

    # ------------------------------------------------------------------ actor
    def actor_mean(self, obs) -> torch.Tensor:
        single_obs = self.single_obs_normalizer(obs["single_obs"])
        latent = self.student_latent(obs)
        z_map = self.map_encoder(self.map_input(obs))
        pre = self.actor_in(torch.cat([latent, single_obs], dim=-1)) + self.actor_in_map(z_map)
        return self.actor_rest(pre)

    def _update_distribution(self, mean: torch.Tensor) -> None:
        self.distribution = Normal(mean, self.std.expand_as(mean))

    def act(self, obs, is_teacher: bool = False, **kwargs) -> torch.Tensor:
        if is_teacher:
            raise ValueError("S2 정책에는 teacher 경로가 없다 (모방 제거)")
        self._update_distribution(self.actor_mean(obs))
        return self.distribution.sample()

    def act_inference(self, obs) -> torch.Tensor:
        return self.actor_mean(obs)

    # ------------------------------------------------------------------ critic (부모 evaluate(is_teacher=False) 와 같은 식)
    def evaluate(self, obs, is_teacher: bool = False, **kwargs) -> torch.Tensor:
        if is_teacher:
            raise ValueError("S2 정책에는 teacher 경로가 없다 (모방 제거)")
        obs_c = self.critic_obs_normalizer(self.get_critic_obs(obs))
        latent = self.student_latent(obs)
        return self.critic(torch.cat([latent.detach(), obs_c], dim=-1))

    # ------------------------------------------------------------------ 분포 (부모와 같은 꼴)
    @property
    def action_mean(self) -> torch.Tensor:
        return self.distribution.mean

    @property
    def action_std(self) -> torch.Tensor:
        return self.distribution.stddev

    @property
    def entropy(self) -> torch.Tensor:
        return self.distribution.entropy().sum(dim=-1)

    def get_actions_log_prob(self, actions: torch.Tensor) -> torch.Tensor:
        return self.distribution.log_prob(actions).sum(dim=-1)

    def reset(self, dones=None) -> None:
        pass

    def forward(self):
        raise NotImplementedError

    def update_normalization(self, obs) -> None:
        pass

    # ------------------------------------------------------------------ 기록용
    def actor_first_layer_weight(self) -> torch.Tensor:
        """설계 3 절의 actor 첫 층 [512, 141] = [부모 77 열 | 지도 64 열]."""
        return torch.cat([self.actor_in.weight, self.actor_in_map.weight], dim=1)

    def param_groups(self) -> dict:
        return {
            "student_encoder": list(self.student_moe_encoder.parameters()),
            "map_encoder": list(self.map_encoder.parameters()),
            "actor": list(self.actor_in.parameters()) + list(self.actor_in_map.parameters()) + list(self.actor_rest.parameters()),
            "critic": list(self.critic.parameters()),
            "std": [self.std],
        }


def build_s2(mode: str, parent: nn.Module | None = None, ckpt: str = E1_CKPT, **kw):
    """S2 정책을 짓는다. parent 를 주면 그것을 복사하고 (부모는 바꾸지 않음), 안 주면 ckpt 에서 읽는다."""
    meta = None
    if parent is None:
        parent, meta = load_parent_cpu(ckpt)
    return S2MapActorCritic(parent, mode, **kw), parent, meta


class EncoderSchedule:
    """student encoder 고정 구간과 학습률 비 (설계 6 절 · ASTRA 17d 6.3). 두 군에 같은 규칙.

    freeze_updates (W): update_index < W 인 동안 student encoder 를 고정한다 (requires_grad 끔 · 그 묶음 lr 0).
        고정 동안 gradient 가 생기지 않으므로 Adam moment 도 쌓이지 않고, 풀리는 첫 update 에서 encoder 의 Adam 상태가 새로 시작한다.
    encoder_lr_ratio (r): 풀린 뒤 student encoder 묶음의 lr = r x (actor 와 나머지 묶음의 lr).
    W · r 은 기본값이 없다 (A/B 결과를 보기 전에 등록할 값). update_index 의 단위 (PPO iteration 한 번 = alg.update() 한 번,
    또는 optimizer step 한 번) 도 W 와 함께 등록한다. 이 코드는 넘겨받은 번호만 센다.
    """

    def __init__(self, freeze_updates: int, encoder_lr_ratio: float):
        if freeze_updates is None or encoder_lr_ratio is None:
            raise TypeError("encoder 고정 구간 W 와 학습률 비 r 은 반드시 넘긴다 (기본값 없음)")
        if isinstance(freeze_updates, bool) or not isinstance(freeze_updates, int) or freeze_updates < 0:
            raise ValueError(f"W 는 0 이상의 정수: {freeze_updates!r}")
        r = float(encoder_lr_ratio)
        if not (r >= 0.0 and r < float("inf")):
            raise ValueError(f"r 은 0 이상의 유한한 수: {encoder_lr_ratio!r}")
        self.freeze_updates = freeze_updates
        self.encoder_lr_ratio = r

    def is_frozen(self, update_index: int) -> bool:
        return update_index < self.freeze_updates

    def apply(self, policy: "S2MapActorCritic", optimizer: torch.optim.Optimizer, update_index: int, lr: float) -> bool:
        """update_index 번째 update 직전에 부른다 (0 부터). PPO adaptive lr 이 바뀔 때마다 다시 불러 비를 지킨다.
        돌려줌: 이번 update 에서 encoder 가 고정인가."""
        frozen = self.is_frozen(update_index)
        for p in policy.student_moe_encoder.parameters():
            p.requires_grad_(not frozen)
        for g in optimizer.param_groups:
            if g.get("name") == "student_encoder":
                g["lr"] = 0.0 if frozen else self.encoder_lr_ratio * lr
            else:
                g["lr"] = lr
        return frozen


def make_optimizer(policy: S2MapActorCritic, lr: float, *, encoder_freeze_updates, encoder_lr_ratio,
                   betas=(0.9, 0.999), weight_decay: float = 0.0):
    """새 Adam 과 EncoderSchedule. 새 Adam 은 「선택」 이다 (부모 매개변수의 moment 를 옮길 수는 있다 · 설계 6 절).
    lr 은 부모 마지막 값을 넘긴다 (두 군 같게). 만들자마자 update 0 의 규칙 (W > 0 이면 encoder 고정) 을 건다.
    돌려줌: (optimizer, schedule). 학습기는 update 마다 schedule.apply(policy, optimizer, update_index, lr) 를 부른다."""
    schedule = EncoderSchedule(encoder_freeze_updates, encoder_lr_ratio)
    groups = [{"params": ps, "name": name} for name, ps in policy.param_groups().items()]
    optimizer = torch.optim.Adam(groups, lr=lr, betas=betas, weight_decay=weight_decay)
    schedule.apply(policy, optimizer, 0, lr)
    return optimizer, schedule


def critic_check(policy: S2MapActorCritic, obs, sensor_pos_w: torch.Tensor | None = None,
                 ray_hits_w: torch.Tensor | None = None) -> dict:
    """critic 입력 · value 의 유한성과 정상 miss 광선 칸의 critic 입력 값을 잰다 (값 · 입력은 바꾸지 않는다).

    부모 critic 의 height 항 (IsaacLab height_scan · clip [-1, 1] · x 2.5) 은 critic obs 의 열 CRITIC_HEIGHT_START ~ +186 이다.
    정상 miss 광선 (센서 정상 · hit xyz 모두 +inf) 칸의 그 값을 모아 돌려준다 (부모 식으로는 -inf -> clip -1 -> -2.5 · B actor 의 지도는 같은 광선을
    height 1 · mask 0 으로 읽는다. 설계 6 절: 「부모 value 함수가 gap 에서 맞다」 는 주장은 하지 않는다).
    """
    with torch.no_grad():
        obs_c = policy.get_critic_obs(obs)
        value = policy.evaluate(obs)
    rep = {
        "n_env": int(obs_c.shape[0]),
        "critic_input_nonfinite": int((~torch.isfinite(obs_c)).sum()),
        "critic_input_nonfinite_envs": int((~torch.isfinite(obs_c)).any(dim=-1).sum()),
        "value_nonfinite": int((~torch.isfinite(value)).sum()),
    }
    if ray_hits_w is not None:
        if sensor_pos_w is None:
            raise ValueError("정상 miss 판정에는 sensor_pos_w 도 넘긴다")
        _hit_valid, normal_miss, _faults = M.classify_rays(sensor_pos_w, ray_hits_w)
        hcols = obs_c[:, CRITIC_HEIGHT_START:CRITIC_HEIGHT_START + ray_hits_w.shape[1]]
        vals = hcols[normal_miss]
        rep["miss_rays"] = int(normal_miss.sum())
        rep["critic_at_miss_values"] = sorted({float(v) for v in vals.tolist()})[:8]
        rep["critic_at_miss_min"] = float(vals.min()) if vals.numel() else None
        rep["critic_at_miss_max"] = float(vals.max()) if vals.numel() else None
    return rep
