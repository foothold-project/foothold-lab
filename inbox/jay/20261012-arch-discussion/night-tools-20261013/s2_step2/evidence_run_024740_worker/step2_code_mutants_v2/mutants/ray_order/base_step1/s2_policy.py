# -*- coding: utf-8 -*-
"""S2 A/B 정책 (판 3): 부모 E1 20000 의 student 경로에 0 으로 시작하는 지도 열을 붙인 actor-critic (CPU 로 짓기 · 학습 없음).

분류: A/정책학습 · S2 「이상적 지도 입력 비교」 A/B 입력 경로 1 단계 판 3 (CPU · 학습 없음)
작성: 오흥재 (lead 세션 · Claude 하위 작업 작성) · 판 1 2026-10-13 19:21 · 판 2 2026-10-13 23:32 · 판 3 2026-10-14 00:50
근거: inbox/jay/20261012-arch-discussion/DESIGN-s2-ab-v1.md 3 절 · 4 절 · 6 절 (다르면 6 절) · VERIFY-astra-17d.md 6.1 ~ 6.3
      VERIFY-astra-17f.md 5 절 · VERIFY-astra-17f2.md 2.1 · 3.1 · 3.2 · 4 · 5.3 (판 3 의 encoder 고정 · 갱신 번호 · group lr · clipping)
      source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py 17 ~ 40 (StudentMoEEncoder) · 86 ~ 247 (act · act_inference · evaluate)
      source/rsl_rl/rsl_rl/networks/moe.py (MLP · MoE · L2Norm) · algorithms/moe_cts.py 93 ~ 101 (optimizer 묶음 · lr) ·
      278 ~ 311 (adaptive lr 이 모든 param group 에 같은 lr 을 씀 · 310 ~ 311) · 365 ~ 366 (clip 은 optimizer 묶음의 매개변수) ·
      runners/on_policy_runner_cts.py 108 · 140 · 173 · 278 (runner 번호 · 저장 iter · 재개 번호)
      E1 run params/agent.yaml (구조 값) · params/env.yaml 865 ~ 1177 (critic 항 순서 · height_scan 이 마지막 187 열)
      model_20000.pt (optimizer_state_dict lr 0.00017085937500000009)
요지: 지도 입력 m [N, 374] -> map encoder (374 -> 128 -> 64 · ELU) -> z_map 64. actor 첫 층은 [latent 32, single_obs 45] 77 열은
      부모 값 그대로, z_map 64 열은 0 으로 시작. forward 에 no_grad 는 없고, student encoder 의 고정은 EncoderControl 이 정한다.
      판 3: encoder_mode (기본값 없음) 를 둔다. 「full_freeze」 는 encoder 를 requires_grad False 로 두고 optimizer 에 넣지 않으며
      어떤 번호에서도 풀지 않는다 (17f-2 4 절 첫 A/B 권고). 「schedule」 은 판 2 의 W · r 규칙이며 r 0 은 받지 않는다 (17f-2 3.1).
      S2 갱신 번호는 control 이 0 부터 센다 (부모 20000 · runner 번호를 넘기면 S2IndexError · 17f-2 2.1). enforce_groups 가
      adaptive lr 덮어쓰기 뒤 group lr 을 다시 맞추고 고정 상태를 확인하며, optimizer step 전 hook 이 그것이 불렸는지 본다 (17f-2 3.2).
      clipping 은 trainable_params (requires_grad 켜진 것만) 로 한다 (17f-2 3.1).
      critic 은 부모 구조 · 가중치에서 시작 (latent.detach() + critic obs) 하고 값은 바꾸지 않는다. critic_check 가 critic 입력 ·
      value 의 유한성과 정상 miss 광선 칸의 critic 입력 값을 잰다. teacher encoder 는 가져오지 않는다.
      A · B 는 구조 · 초기값이 같고 actor 의 지도 입력만 다르다 (A 도 지형 정보가 든 critic 을 학습 신호로 쓴다).
상태: CPU 시험 (test_s2.py) · 변이 (mutate_s2.py) 만 거침. 학습 루프 연결 · Isaac · GPU 실행 없음

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
import math
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


# ====================================================================== 판 3: encoder 고정 · S2 갱신 번호 · group lr · clipping
ENCODER_MODES = ("full_freeze", "schedule")
ENCODER_GROUP = "student_encoder"
GROUP_NAMES = ("student_encoder", "map_encoder", "actor", "critic", "std")    # S2MapActorCritic.param_groups() 의 순서
# S2 갱신 번호 하나 = rollout 한 번 뒤의 PPO update 한 번 (그 안의 epoch x minibatch optimizer step 전부 · 17f-2 2.1)
S2_UPDATE_UNIT = "ppo_iteration"
CONTROL_STATE_FORMAT = "s2-encoder-control-v3"


class _Unset:
    """W · r 을 「안 넘김」 표시 (None · 0 과 구별한다). 값으로 쓰지 않는다."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "<안 넘김>"


_UNSET = _Unset()


class S2ControlError(RuntimeError):
    """encoder 고정 · group lr · optimizer 구성 규칙 위반. 학습을 멈추라는 뜻이다 (고쳐서 이어 가지 않는다)."""


class S2IndexError(S2ControlError):
    """S2 갱신 번호 위반 (부모 iteration · runner 번호 · 건너뜀 · 되풀이 · 끝나지 않은 갱신 · 갱신 도중 저장)."""


def _check_index(i) -> int:
    if isinstance(i, bool) or not isinstance(i, int):
        raise TypeError(f"S2 갱신 번호는 int (bool · float · tensor 아님): {i!r}")
    return i


def _check_lr(lr) -> float:
    if isinstance(lr, bool) or not isinstance(lr, (int, float)):
        raise TypeError(f"base_lr 은 수 (bool · tensor 아님): {lr!r}")
    lr = float(lr)
    if not (lr > 0.0 and math.isfinite(lr)):
        raise ValueError(f"base_lr 은 0 보다 큰 유한한 수: {lr!r}")
    return lr


class EncoderControl:
    """student encoder 의 고정 규칙 · S2 갱신 번호 · optimizer group lr 을 한곳에서 지킨다 (17f-2 2.1 · 3.1 · 3.2). 두 군에 같은 규칙.

    encoder_mode (기본값 없음):
      "full_freeze": 전 구간 고정 (17f-2 4 절 첫 A/B 권고). student encoder 는 requires_grad False 이고 optimizer 에 아예 없으며
                     어떤 S2 갱신 번호에서도 풀리지 않는다. W · r 을 넘기면 TypeError.
      "schedule":    S2 갱신 번호 0 ~ W-1 고정 · W 부터 해제 · 풀린 뒤 encoder 묶음 lr = r x base_lr. W · r 필수 (기본값 없음).
                     고정 동안은 optimizer 에 있어도 requires_grad False 라 grad · Adam 상태가 생기지 않는다.
                     r 은 0 보다 커야 한다: r 0 은 gradient 가 계산되어 clip norm 에 섞이고 Adam 상태가 진행되므로 실제 고정이 아니다
                     (17f-2 3.1). 끝까지 고정하려면 full_freeze 를 쓴다.
    S2 갱신 번호: S2 첫 rollout 의 PPO update 가 0 이다. control 이 완료 수를 세고 begin_update 는 「다음 번호」 만 받는다. 부모 checkpoint
      iter (20000) 나 runner current_learning_iteration (재개 때 마지막 완료 번호로 되돌아감) 을 넘기면 S2IndexError.
    학습기의 PPO update 한 번 (상태 변경은 begin_update 에서만 · 그 update 의 첫 minibatch 전):
        frozen = ctl.begin_update(k, base_lr)
        for 각 epoch · minibatch:
            forward · adaptive lr (base_lr 바뀜 · 부모 꼴이면 모든 group lr 을 같은 값으로 덮어씀)
            optimizer.zero_grad() · loss.backward()
            clip_grad_norm_(trainable_params(policy), max_grad_norm)
            ctl.enforce_groups(optimizer, base_lr)   # group lr 을 규칙대로 다시 쓰고 고정 상태를 확인 · 어긋나면 S2ControlError
            optimizer.step()                         # step 전 hook: enforce 없이 step 이거나 enforce 뒤 바뀌었으면 S2ControlError
        ctl.end_update(k)
    재개: 갱신 사이에서 ctl.state_dict() (완료 수 · 다음 번호 · optimizer 상태 · lr) 를 정책 state_dict 와 함께 저장하고, 새 정책에 읽은 뒤
      make_optimizer (같은 mode · W · r) · ctl.load_state_dict(sd). 학습기는 lr 을 ctl.base_lr 에서 이어 받는다. 난수 상태는 여기 없다.
    """

    def __init__(self, policy: "S2MapActorCritic", encoder_mode, *, freeze_updates=_UNSET, encoder_lr_ratio=_UNSET):
        if encoder_mode not in ENCODER_MODES:
            raise ValueError(f"encoder_mode 는 {ENCODER_MODES} 중 하나: {encoder_mode!r}")
        if encoder_mode == "full_freeze":
            given = [n for n, v in (("freeze_updates", freeze_updates), ("encoder_lr_ratio", encoder_lr_ratio)) if v is not _UNSET]
            if given:
                raise TypeError(f"full_freeze 에는 W · r 을 넘기지 않는다 (넘김: {given})")
            W, r = None, None
        else:
            if freeze_updates is _UNSET or encoder_lr_ratio is _UNSET or freeze_updates is None or encoder_lr_ratio is None:
                raise TypeError("schedule 은 W (freeze_updates) 와 r (encoder_lr_ratio) 을 반드시 넘긴다 (기본값 없음)")
            if isinstance(freeze_updates, bool) or not isinstance(freeze_updates, int) or freeze_updates < 0:
                raise ValueError(f"W 는 0 이상의 정수: {freeze_updates!r}")
            if isinstance(encoder_lr_ratio, bool) or not isinstance(encoder_lr_ratio, (int, float)):
                raise ValueError(f"r 은 수: {encoder_lr_ratio!r}")
            r = float(encoder_lr_ratio)
            if not (r > 0.0 and r < float("inf")):
                raise ValueError(f"r 은 0 보다 큰 유한한 수 (r 0 은 실제 고정이 아니다 · 끝까지 고정은 full_freeze): {encoder_lr_ratio!r}")
            W = freeze_updates
        self.policy = policy
        self.encoder_mode = encoder_mode
        self.freeze_updates = W
        self.encoder_lr_ratio = r
        self.optimizer = None
        self.base_lr = None
        self.completed_updates = 0
        self.steps_total = 0
        self.steps_this_update = 0
        self._in_update = None
        self._enforced_lr = None
        self._hook = None
        self._frozen = self.is_frozen(0)
        self._apply_freeze(self._frozen)      # 만들자마자 번호 0 의 규칙 (full_freeze 와 W > 0 은 고정으로 시작)

    # ------------------------------------------------------------------ 규칙
    def is_frozen(self, s2_update_index) -> bool:
        update_index = _check_index(s2_update_index)
        if self.encoder_mode == "full_freeze":
            return True                       # 어떤 번호에서도 풀리지 않는다
        return update_index < self.freeze_updates

    @property
    def next_update_index(self) -> int:
        return self.completed_updates

    @property
    def frozen(self) -> bool:
        return self._frozen

    @property
    def in_update(self):
        """진행 중인 S2 갱신 번호 (begin_update ~ end_update 사이) · 없으면 None."""
        return self._in_update

    def encoder_params(self) -> list:
        return list(self.policy.student_moe_encoder.parameters())

    def expected_group_names(self) -> tuple:
        if self.encoder_mode == "full_freeze":
            return tuple(n for n in GROUP_NAMES if n != ENCODER_GROUP)
        return GROUP_NAMES

    def expected_lr(self, name, base_lr: float) -> float:
        if name == ENCODER_GROUP:
            return 0.0 if self._frozen else self.encoder_lr_ratio * base_lr
        return base_lr

    def _apply_freeze(self, frozen: bool) -> None:
        for p in self.policy.student_moe_encoder.parameters():
            p.requires_grad_(not frozen)

    def _set_lrs(self, base_lr: float) -> dict:
        fixed = {}
        for g in self.optimizer.param_groups:
            want = self.expected_lr(g.get("name"), base_lr)
            if g["lr"] != want:
                fixed[g.get("name")] = (g["lr"], want)
                g["lr"] = want
        return fixed

    def audit(self, optimizer, base_lr: float) -> list:
        """optimizer 와 encoder 의 지금 상태가 규칙과 맞는지 본다 (고치지 않는다). 어긋난 것을 한 줄씩 돌려준다 (빈 목록이면 맞음)."""
        probs = []
        groups = optimizer.param_groups
        names = tuple(g.get("name") for g in groups)
        if names != self.expected_group_names():
            probs.append(f"group 이름 {names} != 규칙 {self.expected_group_names()}")
        enc = self.encoder_params()
        enc_ids = {id(p) for p in enc}
        pol_ids = {id(p) for p in self.policy.parameters()}
        opt_ids = [id(p) for g in groups for p in g["params"]]
        if len(opt_ids) != len(set(opt_ids)) or not set(opt_ids) <= pol_ids:
            probs.append("optimizer 매개변수가 겹치거나 정책 밖의 것이 있다")
        enc_in_opt = enc_ids & set(opt_ids)
        if self.encoder_mode == "full_freeze" and enc_in_opt:
            probs.append(f"full_freeze 인데 student encoder 매개변수 {len(enc_in_opt)} 개가 optimizer 에 있다")
        missing = (pol_ids - enc_ids if self.encoder_mode == "full_freeze" else pol_ids) - set(opt_ids)
        if missing:
            probs.append(f"학습 대상 매개변수 {len(missing)} 개가 optimizer 에 없다")
        rg_bad = [p for p in enc if p.requires_grad != (not self._frozen)]
        if rg_bad:
            probs.append(f"student encoder requires_grad 가 {'고정' if self._frozen else '해제'} 규칙과 다른 매개변수 {len(rg_bad)} 개")
        other_off = [n for n, p in self.policy.named_parameters() if id(p) not in enc_ids and not p.requires_grad]
        if other_off:
            probs.append(f"encoder 밖의 매개변수가 requires_grad False: {other_off[:3]}")
        if self._frozen:
            g_bad = [p for p in enc if p.grad is not None]
            if g_bad:
                probs.append(f"고정 중 student encoder grad 가 None 이 아닌 매개변수 {len(g_bad)} 개")
            s_bad = [p for p in enc if p in optimizer.state and len(optimizer.state[p]) > 0]
            if s_bad:
                probs.append(f"고정 중 student encoder 의 optimizer 상태 {len(s_bad)} 개 (Adam moment · step 이 진행됨)")
        for g in groups:
            want = self.expected_lr(g.get("name"), base_lr)
            if g["lr"] != want:
                probs.append(f"group {g.get('name')} lr {g['lr']!r} != 규칙 {want!r}")
        return probs

    @staticmethod
    def _raise_if(problems: list, where: str) -> None:
        if problems:
            raise S2ControlError(f"{where}: " + " | ".join(problems))

    # ------------------------------------------------------------------ 학습기 연결
    def bind(self, optimizer, lr) -> None:
        """make_optimizer 가 부른다. group lr 을 번호 0 의 규칙으로 쓰고 step 전 hook 을 건 뒤 상태를 확인한다."""
        if self.optimizer is not None:
            raise S2ControlError("control 하나에 optimizer 하나")
        self.optimizer = optimizer
        self.base_lr = _check_lr(lr)
        self._set_lrs(self.base_lr)
        self._hook = optimizer.register_step_pre_hook(self._pre_step)
        self._raise_if(self.audit(optimizer, self.base_lr), "optimizer 를 만들 때")

    def begin_update(self, s2_update_index, base_lr) -> bool:
        """S2 갱신 번호 s2_update_index 의 첫 minibatch 전에 부른다. 고정 상태를 바꾸는 유일한 자리. 돌려줌: 이번 update 에서 고정인가."""
        idx = _check_index(s2_update_index)
        if self.optimizer is None:
            raise S2ControlError("make_optimizer (bind) 전에는 update 를 시작하지 않는다")
        if self._in_update is not None:
            raise S2IndexError(f"S2 갱신 {self._in_update} 이 끝나지 않았는데 {idx} 를 시작한다")
        if idx != self.completed_updates:
            raise S2IndexError(f"S2 갱신 번호 {idx} != 다음 번호 {self.completed_updates} (S2 첫 rollout 의 update 가 0 이다. 부모 checkpoint "
                               "iter 20000 이나 runner current_learning_iteration 을 넘기지 않는다. 재개 때 W 를 다시 시작하거나 건너뛰지 않는다)")
        base_lr = _check_lr(base_lr)
        frozen = self.is_frozen(idx)
        self._frozen = frozen
        self._apply_freeze(frozen)            # 상태 변경 (이 update 의 첫 minibatch 전)
        self._in_update = idx
        self.steps_this_update = 0
        self._enforced_lr = None
        self.base_lr = base_lr
        self._set_lrs(base_lr)
        self._raise_if(self.audit(self.optimizer, base_lr), f"S2 갱신 {idx} 시작")
        return frozen

    def enforce_groups(self, optimizer, base_lr) -> dict:
        """adaptive lr 이 group lr 을 바꾼 뒤 · optimizer.step() 바로 전에 minibatch 마다 부른다 (backward · clip 뒤).
        1) group lr 을 규칙대로 다시 쓴다 (encoder 묶음: 고정이면 0 · 풀렸으면 r x base_lr · 나머지: base_lr).
        2) 고정 상태 (requires_grad · grad None · Adam 상태 없음 · optimizer 구성) 를 확인한다. 고치지 않는다 (forward · backward 가
           이미 지나가서 여기서 고치면 늦다). 어긋나면 S2ControlError.
        돌려줌: 다시 쓴 group 의 {이름: (전 lr, 새 lr)} (부모 꼴 덮어쓰기를 잡은 기록)."""
        if optimizer is not self.optimizer:
            raise S2ControlError("이 control 에 묶인 optimizer 가 아니다")
        if self._in_update is None:
            raise S2ControlError("enforce_groups 는 begin_update ~ end_update 사이에서 부른다")
        base_lr = _check_lr(base_lr)
        fixed = self._set_lrs(base_lr)
        self._raise_if(self.audit(optimizer, base_lr), f"S2 갱신 {self._in_update} step 전")
        self.base_lr = base_lr
        self._enforced_lr = base_lr
        return fixed

    def _pre_step(self, optimizer, args, kwargs):
        """optimizer.step() 전 hook. enforce_groups 가 이 step 앞에서 불렸고 그 뒤 아무것도 바뀌지 않았는지 다시 본다."""
        if self._in_update is None:
            raise S2ControlError("optimizer.step() 이 begin_update ~ end_update 밖에서 불렸다")
        if self._enforced_lr is None:
            raise S2ControlError("enforce_groups 없이 optimizer.step() (adaptive lr 의 group lr 덮어쓰기를 못 막는다 · 17f-2 3.2)")
        self._raise_if(self.audit(optimizer, self._enforced_lr), f"S2 갱신 {self._in_update} step 직전 (enforce 뒤 바뀜)")
        self._enforced_lr = None              # step 마다 enforce 를 새로 요구한다
        self.steps_this_update += 1
        self.steps_total += 1
        return None

    def end_update(self, s2_update_index) -> None:
        idx = _check_index(s2_update_index)
        if self._in_update is None or idx != self._in_update:
            raise S2IndexError(f"끝내는 번호 {idx} != 진행 중인 번호 {self._in_update}")
        if self.steps_this_update == 0:
            raise S2ControlError(f"S2 갱신 {idx} 에 optimizer step 이 없다 (갱신 생략은 W 의 뜻을 바꾼다)")
        self.completed_updates += 1
        self._in_update = None
        self._enforced_lr = None

    # ------------------------------------------------------------------ 저장 · 재개
    def state_dict(self) -> dict:
        """갱신 사이에서만. 완료 갱신 수 · 다음 번호 · optimizer 상태 (깊은 복사) · base lr · group lr · 규칙을 담는다."""
        if self._in_update is not None:
            raise S2IndexError(f"S2 갱신 {self._in_update} 도중에는 저장하지 않는다 (end_update 뒤에)")
        if self.optimizer is None:
            raise S2ControlError("make_optimizer (bind) 전에는 저장할 optimizer 가 없다")
        return {
            "format": CONTROL_STATE_FORMAT,
            "unit": S2_UPDATE_UNIT,
            "encoder_mode": self.encoder_mode,
            "freeze_updates": self.freeze_updates,
            "encoder_lr_ratio": self.encoder_lr_ratio,
            "completed_updates": self.completed_updates,
            "next_update_index": self.completed_updates,
            "steps_total": self.steps_total,
            "base_lr": self.base_lr,
            "group_lrs": [(g.get("name"), g["lr"]) for g in self.optimizer.param_groups],
            "optimizer": copy.deepcopy(self.optimizer.state_dict()),
        }

    def load_state_dict(self, sd: dict) -> None:
        """새로 만든 control (make_optimizer 직후 · 같은 mode · W · r) 에만 읽는다. 다음 begin_update 는 sd 의 next_update_index 다."""
        if self.optimizer is None:
            raise S2ControlError("make_optimizer (bind) 뒤에 읽는다")
        if self._in_update is not None or self.completed_updates != 0 or self.steps_total != 0:
            raise S2ControlError("새로 만든 control 에만 읽는다 (갱신한 control 에 덮어 읽지 않는다)")
        if sd.get("format") != CONTROL_STATE_FORMAT or sd.get("unit") != S2_UPDATE_UNIT:
            raise ValueError(f"저장 형식 {sd.get('format')!r} · 단위 {sd.get('unit')!r} 가 {CONTROL_STATE_FORMAT} · {S2_UPDATE_UNIT} 와 다르다")
        for k in ("encoder_mode", "freeze_updates", "encoder_lr_ratio"):
            if sd[k] != getattr(self, k):
                raise ValueError(f"재개 규칙이 다르다 · {k}: 저장 {sd[k]!r} · 지금 {getattr(self, k)!r} (다른 실험)")
        completed = _check_index(sd["completed_updates"])
        if completed < 0 or sd["next_update_index"] != completed:
            raise ValueError(f"완료 수 {completed!r} 와 다음 번호 {sd['next_update_index']!r} 가 맞지 않는다")
        saved_lr = _check_lr(sd["base_lr"])
        self.optimizer.load_state_dict(sd["optimizer"])
        if [(g.get("name"), g["lr"]) for g in self.optimizer.param_groups] != [tuple(x) for x in sd["group_lrs"]]:
            raise S2ControlError("optimizer 를 읽은 뒤 group 이름 · lr 이 저장과 다르다")
        self.completed_updates = completed
        self.steps_total = int(sd["steps_total"])
        self.base_lr = saved_lr
        self._frozen = self.is_frozen(completed)
        self._apply_freeze(self._frozen)
        self._set_lrs(saved_lr)
        self._raise_if(self.audit(self.optimizer, saved_lr), "재개 직후")


def trainable_params(policy: nn.Module) -> list:
    """gradient clipping 에 넣을 학습 대상 (requires_grad 가 켜진 매개변수만). 고정된 student encoder 는 들어가지 않는다 (17f-2 3.1).
    판 2 시험처럼 policy.parameters() 전체를 넣으면, encoder 에 grad 가 있을 때 (r 0 · stale grad) 그 norm 이 actor 의 clip 비율을 줄인다."""
    return [p for p in policy.parameters() if p.requires_grad]


def make_optimizer(policy: S2MapActorCritic, lr: float, *, encoder_mode, encoder_freeze_updates=_UNSET, encoder_lr_ratio=_UNSET,
                   betas=(0.9, 0.999), weight_decay: float = 0.0):
    """새 Adam 과 EncoderControl. 새 Adam 은 「선택」 이다 (부모 매개변수의 moment 를 옮길 수는 있다 · 설계 6 절).
    encoder_mode 는 기본값이 없다 ("full_freeze" 또는 "schedule"). W · r 은 schedule 에서만 받는다 (기본값 없음 · full_freeze 에 넘기면 TypeError).
    lr 은 부모 마지막 값을 넘긴다 (두 군 같게). 만들자마자 번호 0 의 규칙을 건다. 돌려줌: (optimizer, control)."""
    control = EncoderControl(policy, encoder_mode, freeze_updates=encoder_freeze_updates, encoder_lr_ratio=encoder_lr_ratio)
    groups = []
    for name, ps in policy.param_groups().items():
        if name == ENCODER_GROUP and encoder_mode == "full_freeze":
            continue                          # 전 구간 고정: student encoder 를 optimizer 에 아예 넣지 않는다
        groups.append({"params": ps, "name": name})
    optimizer = torch.optim.Adam(groups, lr=lr, betas=betas, weight_decay=weight_decay)
    control.bind(optimizer, lr)
    return optimizer, control


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
