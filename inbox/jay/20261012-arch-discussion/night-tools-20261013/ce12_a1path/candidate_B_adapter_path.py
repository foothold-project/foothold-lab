# -*- coding: utf-8 -*-
"""CE12-v1 이식 진단 1 단계 · 정책별 관측 · 행동 adapter (Isaac 없이 torch 만).

분류: A/평가 · 공통 평가 계약 CE12-v1 구현 1 단계 (이식 진단 1)
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 18:19
근거: inbox/jay/20261012-arch-discussion/DESIGN-astra-12-common-eval.md 2.1 · 2.2 · 2.4 · 5.2
      robot_lab/tasks/go2/env_cfg.py (PolicyCfg · SingleObsCfg · ActionsCfg · JOINT_NAMES)
      IsaacLab managers/observation_manager.py compute_group (clip 다음 scale · term 별 이력 flatten 후 term 끼리 이음)
      IsaacLab utils/buffers/circular_buffer.py append (첫 표본을 모든 칸에) · reset (칸을 0 으로 · 횟수 0)
      IsaacLab envs/mdp/actions/joint_actions.py process_actions (target = raw * scale + offset 뒤 clip)
      foothold-lab models/foothold-v2.env.yaml · sim/eval/gap_observations.py
요지: 원시 상태 (관절 이름이 붙은) 를 받아 native 와 같은 관측 텐서와 joint target 을 만든다.
      값 (순서 · scale · clip · 이력 · 기본 자세) 은 원래 설정 파일을 읽어 정한다. 상수로 적어 두지 않는다.
상태: CPU 시험 (test_adapters.py) · 변이 (mutate_adapters.py) 만 거쳤다. native 기록과의 대조 (compare_native.py) 는 미실행

계약 문서와 코드가 다른 곳 (코드를 따랐다)
  1. 계약 2.2 는 「joint target = q_default + scale x clipped_raw」 라고 적었다. Isaac Lab 코드는 clip 을 raw 가 아니라
     target 에 건다 (joint_actions.py process_actions). CTS 는 target 을 [-100, 100] rad 로 자르고 v2 는 clip 이 없다.
     RslRlVecEnvWrapper 의 clip_actions 는 두 평가기 모두 None 이다 (agent.yaml clip_actions: null).
  2. CMD-R 평가기 (q_eval_cmdr.py) 는 motor zero offset DR (+-0.035 rad, events.py randomize_action_joint_pos_offset) 을
     끄지 않는다. 그래서 native 의 offset 은 q_default 와 다르다. decode_action 에 offset 을 넘기면 그 값을 쓰고,
     안 넘기면 q_default 를 쓴다 (P0 · R0 는 motor offset 이 꺼져 있다).
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
import torch

CONTRACT = "CE12-v1"
ADAPTER_VERSION = "ce12-step1-adapters-v1"

RL_ROOT = os.environ.get("CE12_RL_ROOT", "C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab")
CTS_ENV_CFG = os.path.join(RL_ROOT, "tasks", "go2", "env_cfg.py").replace("\\", "/")
CTS_ASSETS = os.path.join(RL_ROOT, "assets", "unitree.py").replace("\\", "/")
LAB_ROOT = os.environ.get("CE12_LAB_ROOT", "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab")
V2_ENV_YAML = LAB_ROOT + "/models/foothold-v2.env.yaml"
V2_AGENT_YAML = LAB_ROOT + "/models/foothold-v2.agent.yaml"
V2_CHECKPOINT = LAB_ROOT + "/models/foothold-v2.pt"
CTS_E1_RUN = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192"

# observation_manager.py _prepare_terms 가 term 이 아니라고 건너뛰는 그룹 설정 열쇠
GROUP_KEYS = ("enable_corruption", "concatenate_terms", "history_length", "flatten_history_dim", "concatenate_dim")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# --------------------------------------------------------------------------------------------- 이름


def resolve_name_values(pattern_values: dict, names: Sequence[str]) -> dict:
    """Isaac Lab string.resolve_matching_names_values 와 같은 규칙: re.fullmatch, 한 이름이 둘 이상 걸리면 오류,
    아무 이름에도 안 걸린 패턴도 오류. 여기서는 어떤 패턴에도 안 걸린 이름도 오류로 둔다 (기본 자세 · scale 이 빠지면 안 됨)."""
    items = list(pattern_values.items())
    used = [False] * len(items)
    out = {}
    for n in names:
        hit = None
        for k, (pat, _v) in enumerate(items):
            if re.fullmatch(pat, n):
                if hit is not None:
                    raise ValueError(f"이름 {n!r} 이 두 패턴에 걸린다: {items[hit][0]!r} · {pat!r}")
                hit = k
        if hit is None:
            raise ValueError(f"이름 {n!r} 에 걸리는 패턴이 없다: {[p for p, _ in items]}")
        used[hit] = True
        out[n] = items[hit][1]
    unused = [items[k][0] for k in range(len(items)) if not used[k]]
    if unused:
        raise ValueError(f"어느 이름에도 안 걸린 패턴: {unused}")
    return out


def name_index(src_names: Sequence[str], dst_names: Sequence[str]) -> list:
    """dst 순서로 src 열을 읽는 index. 이름으로만 맞춘다 (자리 순서를 믿지 않는다)."""
    src = list(src_names)
    if len(set(src)) != len(src):
        raise ValueError(f"관절 이름이 겹친다: {src}")
    pos = {n: i for i, n in enumerate(src)}
    missing = [n for n in dst_names if n not in pos]
    if missing:
        raise KeyError(f"입력에 없는 관절 이름: {missing}")
    return [pos[n] for n in dst_names]


def take_by_names(x: torch.Tensor, src_names: Sequence[str], dst_names: Sequence[str]) -> torch.Tensor:
    return x[..., name_index(src_names, dst_names)]


# --------------------------------------------------------------------------------------------- 원시 상태


@dataclass
class RawState:
    """정책 한 step 의 원시 상태 (N 대).

    joint_names       joint_pos · joint_vel 열의 이름. 순서는 아무래도 된다 (adapter 가 이름으로 맞춘다)
    joint_pos/vel     (N, J) 관절 위치 · 속도 (기본 자세를 빼기 전 값)
    ang_vel_b         (N, 3) 몸통 좌표 각속도 (robot.data.root_ang_vel_b)
    projected_gravity_b (N, 3)
    command           (N, 3) 정책에 보일 (vx, vy, wz) · 이 step 의 관측에 들어갈 값
    lin_vel_b         (N, 3) v2 전용 (CTS student 는 안 본다)
    last_action_raw   (N, A) 정책 자기 action 순서의 직전 raw action. None 이면 adapter 가 기억한 값 (decode_action) 을 쓴다
    height_sensor_z   (N,)   v2 전용. RayCaster data.pos_w[:, 2] (몸통 프림 위치 · 광선 시작점의 +20 m 는 안 들어 있다)
    ray_hits_z        (N, R) v2 전용. RayCaster data.ray_hits_w[..., 2] (못 맞히면 inf)
    """
    joint_names: Sequence[str]
    joint_pos: torch.Tensor
    joint_vel: torch.Tensor
    ang_vel_b: torch.Tensor
    projected_gravity_b: torch.Tensor
    command: torch.Tensor
    lin_vel_b: torch.Tensor | None = None
    last_action_raw: torch.Tensor | None = None
    height_sensor_z: torch.Tensor | None = None
    ray_hits_z: torch.Tensor | None = None


def height_scan_with_gap_values(sensor_z: torch.Tensor, ray_hits_z: torch.Tensor, offset: float = 0.5,
                                miss_value: float = 1.0) -> torch.Tensor:
    """sim/eval/gap_observations.py height_scan_with_gap 과 같은 식 (같은 연산 순서).
    height = pos_w_z - hit_z - offset · 못 맞힌 광선 (inf · NaN) 은 miss_value. clip 은 관측 항 설정 (여기 아님)."""
    height = sensor_z.unsqueeze(1) - ray_hits_z - offset
    valid_hit = torch.isfinite(ray_hits_z) & torch.isfinite(height)
    return torch.where(valid_hit, height, torch.full_like(height, float(miss_value)))


def grid_pattern_local(size=(1.6, 1.0), resolution=0.1, ordering="xy") -> torch.Tensor:
    """IsaacLab sensors/ray_caster/patterns/patterns.py grid_pattern 과 같은 식으로 광선 i 의 지역 (x, y).
    ordering xy 면 x 가 가장 빨리 돈다: i = iy * nx + ix. offset (0, 0, 20) 은 더하지 않는다."""
    if ordering not in ("xy", "yx"):
        raise ValueError(ordering)
    indexing = ordering if ordering == "xy" else "ij"
    x = torch.arange(start=-size[0] / 2, end=size[0] / 2 + 1.0e-9, step=resolution)
    y = torch.arange(start=-size[1] / 2, end=size[1] / 2 + 1.0e-9, step=resolution)
    gx, gy = torch.meshgrid(x, y, indexing=indexing)
    return torch.stack([gx.flatten(), gy.flatten()], dim=-1)


# --------------------------------------------------------------------------------------------- 관측 항


@dataclass(frozen=True)
class TermSpec:
    name: str                 # 관측 그룹 안의 열쇠 (cfg 이름)
    func: str                 # 원래 함수 이름 (base_ang_vel 등)
    dim: int
    scale: float | None
    clip: tuple | None
    params: tuple = ()        # (("offset", 0.5), ("miss_value", 1.0)) 같은 짝


class TermHistory:
    """circular_buffer.py 와 같은 규칙을 oldest -> newest 배열로 직접 든다.
    append: 맨 앞을 버리고 맨 뒤에 넣는다. 그 env 의 첫 append 면 모든 칸을 그 표본으로 (circular_buffer.py:136-139).
    reset: 횟수 0 · 칸 0 (circular_buffer.py:106-110)."""

    def __init__(self, num_envs: int, length: int, dim: int, device="cpu"):
        self.N, self.H, self.dim = num_envs, length, dim
        self.buf = None
        self.num_pushes = torch.zeros(num_envs, dtype=torch.long, device=device)

    def append(self, x: torch.Tensor):
        if self.buf is None:
            self.buf = torch.zeros((self.N, self.H, self.dim), dtype=x.dtype, device=x.device)
        self.buf = torch.cat([self.buf[:, 1:], x.unsqueeze(1)], dim=1)
        first = self.num_pushes == 0
        if bool(first.any()):
            self.buf[first] = x[first].unsqueeze(1).expand(-1, self.H, -1)
        self.num_pushes += 1

    def reset(self, ids):
        self.num_pushes[ids] = 0
        if self.buf is not None:
            self.buf[ids] = 0.0

    def flat(self) -> torch.Tensor:
        return self.buf.reshape(self.N, self.H * self.dim)


def _process(term: TermSpec, v: torch.Tensor) -> torch.Tensor:
    """observation_manager.py compute_group 의 순서: (modifier 없음 · 평가에서 noise 끔) -> clip -> scale."""
    if term.clip:
        v = v.clamp(min=term.clip[0], max=term.clip[1])
    if term.scale is not None:
        v = v * torch.tensor(term.scale, dtype=torch.float32, device=v.device)
    return v


class _AdapterBase:
    model = "base"
    inference = ""

    def _init_common(self, *, terms, obs_joint_names, action_joint_names, default_joint_pos, default_joint_vel,
                     action_scale, action_clip, num_envs, device, source):
        self.terms = list(terms)
        self.obs_joint_names = list(obs_joint_names)
        self.action_joint_names = list(action_joint_names)
        if len(set(self.obs_joint_names)) != len(self.obs_joint_names) or len(set(self.action_joint_names)) != len(self.action_joint_names):
            raise ValueError("관절 이름이 겹친다")
        if set(self.obs_joint_names) != set(self.action_joint_names):
            raise ValueError("관측 관절과 행동 관절의 이름 집합이 다르다")
        self.N = int(num_envs)
        self.device = device
        self.default_joint_pos = {n: float(v) for n, v in default_joint_pos.items()}
        self.default_joint_vel = {n: float(v) for n, v in default_joint_vel.items()}
        self._q0 = torch.tensor([self.default_joint_pos[n] for n in self.obs_joint_names], dtype=torch.float32, device=device)
        self._dq0 = torch.tensor([self.default_joint_vel[n] for n in self.obs_joint_names], dtype=torch.float32, device=device)
        self._offset0 = torch.tensor([self.default_joint_pos[n] for n in self.action_joint_names], dtype=torch.float32, device=device)
        self.action_scale = {n: float(action_scale[n]) for n in self.action_joint_names}
        self._act_scale = torch.tensor([self.action_scale[n] for n in self.action_joint_names], dtype=torch.float32, device=device)
        self.action_clip = None if action_clip is None else {n: (float(action_clip[n][0]), float(action_clip[n][1]))
                                                             for n in self.action_joint_names}
        self._act_clip = None if action_clip is None else torch.tensor(
            [self.action_clip[n] for n in self.action_joint_names], dtype=torch.float32, device=device)
        self.A = len(self.action_joint_names)
        self._last_raw = torch.zeros((self.N, self.A), dtype=torch.float32, device=device)
        self.source = dict(source or {})
        for t in self.terms:
            want = self._func_dim(t)
            if want is not None and t.dim != want:
                raise ValueError(f"관측 항 {t.name} 차원 {t.dim} != {want}")

    def _func_dim(self, t: TermSpec):
        if t.func in ("base_lin_vel", "base_ang_vel", "projected_gravity", "generated_commands"):
            return 3
        if t.func in ("joint_pos_rel", "joint_vel_rel"):
            return len(self.obs_joint_names)
        if t.func == "last_action":
            return len(self.action_joint_names)
        if t.func == "height_scan_with_gap":
            return None
        raise ValueError(f"모르는 관측 함수 {t.func!r} (이 adapter 는 아는 함수만 받는다)")

    # -- 관측 항 원값 (clip · scale 전) ----------------------------------------------------------------
    def _term_value(self, t: TermSpec, s: RawState, last_raw: torch.Tensor) -> torch.Tensor:
        f = t.func
        if f == "base_lin_vel":
            if s.lin_vel_b is None:
                raise ValueError("lin_vel_b 가 필요하다")
            v = s.lin_vel_b
        elif f == "base_ang_vel":
            v = s.ang_vel_b
        elif f == "projected_gravity":
            v = s.projected_gravity_b
        elif f == "generated_commands":
            v = s.command
        elif f == "joint_pos_rel":
            v = take_by_names(s.joint_pos.to(torch.float32), s.joint_names, self.obs_joint_names) - self._q0
        elif f == "joint_vel_rel":
            v = take_by_names(s.joint_vel.to(torch.float32), s.joint_names, self.obs_joint_names) - self._dq0
        elif f == "last_action":
            v = last_raw
        elif f == "height_scan_with_gap":
            if s.height_sensor_z is None or s.ray_hits_z is None:
                raise ValueError("height_sensor_z · ray_hits_z 가 필요하다")
            p = dict(t.params)
            v = height_scan_with_gap_values(s.height_sensor_z.to(torch.float32), s.ray_hits_z.to(torch.float32),
                                            offset=p["offset"], miss_value=p["miss_value"])
        else:
            raise ValueError(f"모르는 관측 함수 {f!r}")
        v = v.to(dtype=torch.float32, device=self.device).clone()
        if tuple(v.shape) != (self.N, t.dim):
            raise ValueError(f"관측 항 {t.name} 모양 {tuple(v.shape)} != {(self.N, t.dim)}")
        return v

    def _samples(self, s: RawState) -> list:
        last = self._last_raw if s.last_action_raw is None else s.last_action_raw.to(torch.float32)
        return [_process(t, self._term_value(t, s, last)) for t in self.terms]

    # -- 행동 -------------------------------------------------------------------------------------------
    def decode_action(self, raw: torch.Tensor, out_joint_names: Sequence[str] | None = None,
                      offset: torch.Tensor | None = None, remember: bool = True) -> torch.Tensor:
        """joint_actions.py process_actions 와 같은 식: target = raw * scale + offset, clip 이 있으면 target 에 건다.
        raw 는 정책 자기 action 순서 (self.action_joint_names). out_joint_names 를 주면 그 이름 순서로 돌려준다.
        offset 은 정책 action 순서의 (N, A). 안 주면 기본 자세 (use_default_offset).
        remember=True 면 raw 를 다음 관측의 last_action 으로 기억한다 (action_manager.process_action 의 _action)."""
        raw = raw.to(dtype=torch.float32, device=self.device)
        if tuple(raw.shape) != (self.N, self.A):
            raise ValueError(f"raw 모양 {tuple(raw.shape)} != {(self.N, self.A)}")
        if remember:
            self._last_raw = raw.clone()
        off = self._offset0.expand_as(raw) if offset is None else offset.to(dtype=torch.float32, device=self.device)
        target = raw * self._act_scale + off
        if self._act_clip is not None:
            target = torch.clamp(target, min=self._act_clip[:, 0], max=self._act_clip[:, 1])
        if out_joint_names is not None:
            target = take_by_names(target, self.action_joint_names, out_joint_names)
        return target

    def raw_from_target(self, target_by_name: dict) -> torch.Tensor:
        """시험용 역변환 (clip 이 안 걸리는 범위만): raw = (target - q_default) / scale, 정책 action 순서."""
        t = torch.tensor([[target_by_name[n] for n in self.action_joint_names]] * self.N, dtype=torch.float32)
        return (t - self._offset0) / self._act_scale

    # -- 서명 ------------------------------------------------------------------------------------------
    def _base_signature(self) -> dict:
        return {
            "contract": CONTRACT,
            "adapter": type(self).__name__,
            "adapter_version": ADAPTER_VERSION,
            "model": self.model,
            "inference": self.inference,
            "joint_names": {"observation": self.obs_joint_names, "action": self.action_joint_names,
                            "matching": "이름으로 맞춘다 (입력 열 순서를 믿지 않는다)"},
            "default_joint_pos": {n: self.default_joint_pos[n] for n in self.obs_joint_names},
            "default_joint_vel": {n: self.default_joint_vel[n] for n in self.obs_joint_names},
            "action": {
                "dim": self.A,
                "raw_representation": "정책 출력 그대로 (wrapper clip_actions None). 다음 관측의 last_action 항이 이 값",
                "formula": "target = clip(raw * scale + offset)  (joint_actions.py process_actions · clip 은 target 에)",
                "scale": self.action_scale,
                "offset": "default_joint_pos (use_default_offset=True). native 평가기의 motor offset DR 이 있으면 그 값",
                "clip_on_target": self.action_clip,
            },
            "observation_noise": "끔 (평가 설정 · 학습의 관측 잡음은 재현하지 않는다)",
            "source": self.source,
        }

    def signature(self) -> dict:
        raise NotImplementedError


def signature_sha256(sig: dict) -> str:
    return hashlib.sha256(json.dumps(sig, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def write_signature(adapter: _AdapterBase, path: str) -> dict:
    sig = adapter.signature()
    sig = dict(sig, signature_sha256=signature_sha256(sig))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sig, f, ensure_ascii=False, indent=1)
    return sig


# --------------------------------------------------------------------------------------------- CTS student


class CTSStudentAdapter(_AdapterBase):
    """robot_lab Go2 MoE-CTS student 의 policy (이력 450) 와 single_obs (45).

    policy:     term-major. 각 term 의 이력 H 칸을 oldest -> newest 로 편 뒤 term 끼리 잇는다 (observation_manager.py:424 · 433).
    single_obs: 같은 term 들의 이력 1 칸 (= 이번 표본).
    갱신:       observe(update_history=True) 가 정책 step 마다 정확히 한 번. update_history=False 는 저장된 버퍼를 돌려줄 뿐 전진하지 않는다.
    reset(ids): 그 env 의 이력 횟수 0 · 칸 0 · 기억한 raw action 0. 다음 갱신이 첫 표본을 H 칸에 반복한다."""

    model = "cts_student"
    inference = "ActorCriticMoECTS.act_inference: student_moe_encoder(policy) + single_obs -> actor. critic · teacher 입력 안 씀"

    def __init__(self, spec: dict, num_envs: int, device="cpu"):
        self.spec = spec
        self.H = int(spec["history_length"])
        self.H_single = int(spec["single_history_length"])
        self._init_common(terms=spec["policy_terms"], obs_joint_names=spec["obs_joint_names"],
                          action_joint_names=spec["action"]["joint_names"],
                          default_joint_pos=resolve_name_values(spec["default_joint_pos_patterns"], spec["obs_joint_names"]),
                          default_joint_vel=resolve_name_values(spec["default_joint_vel_patterns"], spec["obs_joint_names"]),
                          action_scale=spec["action"]["scale_by_name"], action_clip=spec["action"]["clip_by_name"],
                          num_envs=num_envs, device=device, source=spec.get("source"))
        self._hist = {t.name: TermHistory(self.N, self.H, t.dim, device) for t in self.terms}
        self._single = {t.name: TermHistory(self.N, self.H_single, t.dim, device) for t in self.terms}

    @classmethod
    def from_source(cls, num_envs: int, env_cfg_path: str = CTS_ENV_CFG, assets_path: str = CTS_ASSETS, device="cpu"):
        return cls(parse_cts_source(env_cfg_path, assets_path), num_envs, device)

    def reset(self, env_ids=None):
        ids = slice(None) if env_ids is None else env_ids
        for h in list(self._hist.values()) + list(self._single.values()):
            h.reset(ids)
        self._last_raw[ids] = 0.0

    def _initialized(self) -> bool:
        return all(h.buf is not None for h in self._hist.values())

    def _flatten(self, hist: dict) -> torch.Tensor:
        return torch.cat([hist[t.name].flat() for t in self.terms], dim=-1)

    def observe(self, state: RawState, update_history: bool = True) -> dict:
        if update_history:
            for t, v in zip(self.terms, self._samples(state)):
                self._hist[t.name].append(v)
                self._single[t.name].append(v)
            hist, single = self._hist, self._single
        elif self._initialized():
            hist, single = self._hist, self._single
        else:
            # observation_manager.py:411-420: 버퍼가 아직 없을 때의 외부 읽기는 임시 버퍼에 한 번 넣어 돌려주고 저장하지 않는다
            hist = {t.name: TermHistory(self.N, self.H, t.dim, self.device) for t in self.terms}
            single = {t.name: TermHistory(self.N, self.H_single, t.dim, self.device) for t in self.terms}
            for t, v in zip(self.terms, self._samples(state)):
                hist[t.name].append(v)
                single[t.name].append(v)
        return {"policy": self._flatten(hist), "single_obs": torch.cat([single[t.name].flat() for t in self.terms], dim=-1)}

    def layout(self, group: str) -> list:
        """[(term, start, stop, history_length, dim)] · native 관측 텐서의 칸 배치."""
        H = self.H if group == "policy" else self.H_single if group == "single_obs" else None
        if H is None:
            raise KeyError(group)
        out, a = [], 0
        for t in self.terms:
            out.append((t.name, a, a + H * t.dim, H, t.dim))
            a += H * t.dim
        return out

    def history_slice(self, group: str, term: str, slot: int) -> tuple:
        """slot 0 = 가장 오래된 칸, -1 = 최신."""
        for name, a, b, H, d in self.layout(group):
            if name == term:
                s = slot % H
                return a + s * d, a + (s + 1) * d
        raise KeyError(term)

    def locate(self, group: str, index: int) -> dict:
        for name, a, b, H, d in self.layout(group):
            if a <= index < b:
                slot, elem = divmod(index - a, d)
                t = next(x for x in self.terms if x.name == name)
                out = {"group": group, "index": int(index), "term": name, "history_slot": int(slot),
                       "history_slot_meaning": "0 = 가장 오래된 칸 · %d = 최신" % (H - 1), "element": int(elem)}
                if t.func in ("joint_pos_rel", "joint_vel_rel"):
                    out["joint"] = self.obs_joint_names[elem]
                elif t.func == "last_action":
                    out["joint"] = self.action_joint_names[elem]
                return out
        raise IndexError(index)

    def infer(self, policy_module, obs: dict) -> torch.Tensor:
        """act_inference 에 policy · single_obs 만 넣는다 (critic 열쇠 없이). 정보가 새는 길을 만들지 않는다."""
        from tensordict import TensorDict
        td = TensorDict({"policy": obs["policy"], "single_obs": obs["single_obs"]}, batch_size=[obs["policy"].shape[0]])
        with torch.inference_mode():
            return policy_module.act_inference(td)

    def signature(self) -> dict:
        sig = self._base_signature()
        sig["observation"] = {
            "groups": [
                {"name": "policy", "dim": int(sum(t.dim for t in self.terms) * self.H), "history_length": self.H,
                 "layout": "term-major: term 마다 이력 H 칸을 oldest -> newest 로 편 뒤 term 끼리 잇는다",
                 "terms": [{"name": n, "start": a, "stop": b, "history_length": H, "dim": d} for n, a, b, H, d in self.layout("policy")]},
                {"name": "single_obs", "dim": int(sum(t.dim for t in self.terms) * self.H_single), "history_length": self.H_single,
                 "terms": [{"name": n, "start": a, "stop": b, "dim": d} for n, a, b, H, d in self.layout("single_obs")]},
            ],
            "term_processing": [{"name": t.name, "func": t.func, "dim": t.dim, "scale": t.scale,
                                 "clip": list(t.clip) if t.clip else None} for t in self.terms],
            "order": "clip 다음 scale (observation_manager.py compute_group)",
            "history_init": "reset 뒤 첫 표본을 H 칸 모두에 (circular_buffer.py append)",
            "history_update": "정책 step 마다 한 번 (update_history=True). 디버그 읽기 (False) 는 전진하지 않는다",
            "latest_command_slice_policy": list(self.history_slice("policy", self._cmd_term(), -1)),
            "command_slice_single_obs": list(self.history_slice("single_obs", self._cmd_term(), -1)),
        }
        return sig

    def _cmd_term(self) -> str:
        return next(t.name for t in self.terms if t.func == "generated_commands")


# --------------------------------------------------------------------------------------------- v2


class V2Adapter(_AdapterBase):
    """foothold-v2 (rsl_rl ActorCritic · 관측 235 · 이력 없음).

    관절 순서: v2 는 joint_pos_rel/joint_vel_rel 이 asset_cfg 없이 (= 전 관절 · articulation 순서) 읽고, 행동은 `.*`
    preserve_order=False 라 역시 articulation 순서다. 그 순서는 원래 USD 를 띄운 런타임에서만 알 수 있으므로 이름 목록을
    반드시 인자로 받는다 (기본값 없음)."""

    model = "v2"
    inference = "rsl_rl ActorCritic.act_inference: actor(policy 235)"

    def __init__(self, spec: dict, obs_joint_names: Sequence[str], num_envs: int,
                 action_joint_names: Sequence[str] | None = None, device="cpu"):
        if obs_joint_names is None:
            raise ValueError("v2 관절 순서는 런타임 기록에서 받아야 한다 (추측 금지)")
        self.spec = spec
        obs_joint_names = list(obs_joint_names)
        action_joint_names = list(obs_joint_names if action_joint_names is None else action_joint_names)
        act = spec["action"]
        if act["joint_names"] != [".*"] or act["preserve_order"]:
            raise ValueError(f"v2 행동 관절 설정이 예상과 다르다: {act}")
        scale = {n: act["scale"] for n in action_joint_names} if not isinstance(act["scale"], dict) else \
            resolve_name_values(act["scale"], action_joint_names)
        clip = None if act["clip"] is None else resolve_name_values(act["clip"], action_joint_names)
        self._init_common(terms=spec["policy_terms"], obs_joint_names=obs_joint_names, action_joint_names=action_joint_names,
                          default_joint_pos=resolve_name_values(spec["default_joint_pos_patterns"], obs_joint_names),
                          default_joint_vel=resolve_name_values(spec["default_joint_vel_patterns"], obs_joint_names),
                          action_scale=scale, action_clip=clip, num_envs=num_envs, device=device, source=spec.get("source"))
        self.height = spec["height_scanner"]

    @classmethod
    def from_env_yaml(cls, obs_joint_names: Sequence[str], num_envs: int, action_joint_names=None,
                      env_yaml: str = V2_ENV_YAML, device="cpu"):
        return cls(parse_v2_env_yaml(env_yaml), obs_joint_names, num_envs, action_joint_names, device)

    def reset(self, env_ids=None):
        ids = slice(None) if env_ids is None else env_ids
        self._last_raw[ids] = 0.0

    def observe(self, state: RawState, update_history: bool = True) -> dict:
        # 이력 항이 없다: native compute 는 갱신 여부와 관계없이 매번 새로 계산한다
        return {"policy": torch.cat(self._samples(state), dim=-1)}

    def layout(self, group: str = "policy") -> list:
        if group != "policy":
            raise KeyError(group)
        out, a = [], 0
        for t in self.terms:
            out.append((t.name, a, a + t.dim, 1, t.dim))
            a += t.dim
        return out

    def locate(self, group: str, index: int) -> dict:
        for name, a, b, H, d in self.layout(group):
            if a <= index < b:
                elem = index - a
                t = next(x for x in self.terms if x.name == name)
                out = {"group": group, "index": int(index), "term": name, "history_slot": 0, "element": int(elem)}
                if t.func in ("joint_pos_rel", "joint_vel_rel"):
                    out["joint"] = self.obs_joint_names[elem]
                elif t.func == "last_action":
                    out["joint"] = self.action_joint_names[elem]
                elif t.func == "height_scan_with_gap":
                    xy = grid_pattern_local(self.height["size"], self.height["resolution"], self.height["ordering"])[elem]
                    out["ray"] = int(elem)
                    out["ray_local_xy"] = [round(float(xy[0]), 4), round(float(xy[1]), 4)]
                return out
        raise IndexError(index)

    def infer(self, policy_module, obs: dict) -> torch.Tensor:
        from tensordict import TensorDict
        td = TensorDict({"policy": obs["policy"]}, batch_size=[obs["policy"].shape[0]])
        with torch.inference_mode():
            return policy_module.act_inference(td)

    def signature(self) -> dict:
        sig = self._base_signature()
        sig["observation"] = {
            "groups": [{"name": "policy", "dim": int(sum(t.dim for t in self.terms)), "history_length": 0,
                        "terms": [{"name": n, "start": a, "stop": b, "dim": d} for n, a, b, H, d in self.layout("policy")]}],
            "term_processing": [{"name": t.name, "func": t.func, "dim": t.dim, "scale": t.scale,
                                 "clip": list(t.clip) if t.clip else None, "params": dict(t.params)} for t in self.terms],
            "order": "clip 다음 scale (scale 은 모두 None)",
            "height_scan": {"formula": "clip(where(유효, pos_w_z - hit_z - offset, miss_value), -1, 1)",
                            "pos_w": "RayCaster data.pos_w (몸통 프림 위치 · 광선 시작 offset 20 m 는 안 더함)",
                            "scanner": self.height},
        }
        return sig


# --------------------------------------------------------------------------------------------- 원래 설정 읽기


def _call_name(node) -> str:
    f = node.func
    return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ast.unparse(f)


def _kw(call: ast.Call) -> dict:
    return {k.arg: k.value for k in call.keywords}


def _find_class(body, name):
    for n in body:
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    raise KeyError(f"class {name} 없음")


def _post_init_sets(cls: ast.ClassDef) -> dict:
    out = {}
    for n in cls.body:
        if isinstance(n, ast.FunctionDef) and n.name == "__post_init__":
            for s in ast.walk(n):
                if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Attribute) \
                        and isinstance(s.targets[0].value, ast.Name) and s.targets[0].value.id == "self":
                    out[s.targets[0].attr] = ast.literal_eval(s.value)
    return out


def parse_cts_source(env_cfg_path: str = CTS_ENV_CFG, assets_path: str = CTS_ASSETS) -> dict:
    """robot_lab env_cfg.py 와 assets/unitree.py 를 ast 로 읽어 student 관측 · 행동 · 기본 자세를 뽑는다 (import 하지 않는다)."""
    src = open(env_cfg_path, encoding="utf-8").read()
    tree = ast.parse(src)
    consts = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            try:
                consts[n.targets[0].id] = ast.literal_eval(n.value)
            except Exception:
                pass
    joint_names = list(consts["JOINT_NAMES"])

    def ref(node):
        if isinstance(node, ast.Name) and node.id in consts:
            return consts[node.id]
        return ast.literal_eval(node)

    obs_cls = _find_class(tree.body, "ObservationsCfg")
    pol = _find_class(obs_cls.body, "PolicyCfg")
    single = _find_class(obs_cls.body, "SingleObsCfg")
    if not (single.bases and isinstance(single.bases[0], ast.Name) and single.bases[0].id == "PolicyCfg"):
        raise ValueError("SingleObsCfg 가 PolicyCfg 를 물려받지 않는다")
    terms, obs_joint_names = [], None
    for n in pol.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and _call_name(n.value) == "ObsTerm":
            kw = _kw(n.value)
            func = kw["func"].attr if isinstance(kw["func"], ast.Attribute) else kw["func"].id
            if func in ("joint_pos_rel", "joint_vel_rel"):
                ac = _kw(kw["params"].values[[ast.literal_eval(k) for k in kw["params"].keys].index("asset_cfg")])
                names = ref(ac["joint_names"])
                if not ast.literal_eval(ac.get("preserve_order", ast.Constant(False))):
                    raise ValueError("CTS 관절 관측이 preserve_order=True 가 아니다 (런타임 순서가 필요)")
                if obs_joint_names is not None and list(names) != obs_joint_names:
                    raise ValueError("관절 관측 둘의 이름 목록이 다르다")
                obs_joint_names = list(names)
            clip = tuple(ast.literal_eval(kw["clip"])) if "clip" in kw else None
            scale = float(ast.literal_eval(kw["scale"])) if "scale" in kw else None
            terms.append((n.targets[0].id, func, clip, scale))
    post_p, post_s = _post_init_sets(pol), _post_init_sets(single)
    if not post_p.get("concatenate_terms", False) or not post_p.get("flatten_history_dim", False):
        raise ValueError("PolicyCfg 가 concatenate · flatten 이 아니다")
    act_cls = _find_class(tree.body, "ActionsCfg")
    act = None
    for n in act_cls.body:
        if isinstance(n, ast.Assign) and n.targets[0].id == "joint_pos":
            kw = _kw(n.value)
            act = {"class": _call_name(n.value), "joint_names": list(ref(kw["joint_names"])),
                   "scale": ast.literal_eval(kw["scale"]), "clip": ast.literal_eval(kw["clip"]) if "clip" in kw else None,
                   "use_default_offset": ast.literal_eval(kw["use_default_offset"]),
                   "preserve_order": ast.literal_eval(kw["preserve_order"])}
    if act is None or not act["use_default_offset"] or not act["preserve_order"]:
        raise ValueError(f"ActionsCfg.joint_pos 가 예상과 다르다: {act}")
    scene = _find_class(tree.body, "Go2SceneCfg")
    robot_cfg = None
    for n in scene.body:
        if isinstance(n, ast.AnnAssign) and n.target.id == "robot":
            robot_cfg = n.value.func.value.id  # GO2_CFG_UNITREE.replace(...)
    a_tree = ast.parse(open(assets_path, encoding="utf-8").read())
    init = None
    for n in a_tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == robot_cfg:
            init = _kw(_kw(n.value)["init_state"])
    if init is None:
        raise KeyError(f"{robot_cfg} 의 init_state 를 못 찾음")
    nj, na = len(obs_joint_names), len(act["joint_names"])
    dims = {"base_ang_vel": 3, "projected_gravity": 3, "generated_commands": 3, "joint_pos_rel": nj, "joint_vel_rel": nj,
            "last_action": na, "base_lin_vel": 3}
    policy_terms = [TermSpec(name, func, dims[func], scale, clip) for name, func, clip, scale in terms]
    scale_by_name = resolve_name_values(act["scale"], act["joint_names"]) if isinstance(act["scale"], dict) else \
        {n: act["scale"] for n in act["joint_names"]}
    clip_by_name = None if act["clip"] is None else resolve_name_values(act["clip"], act["joint_names"])
    return {
        "model": "cts_student",
        "joint_names_const": joint_names,
        "obs_joint_names": obs_joint_names,
        "policy_terms": policy_terms,
        "history_length": int(post_p["history_length"]),
        "single_history_length": int(post_s["history_length"]),
        "enable_corruption_in_source": bool(post_p.get("enable_corruption", False)),
        "action": dict(act, scale_by_name=scale_by_name, clip_by_name=clip_by_name),
        "robot_cfg": robot_cfg,
        "default_joint_pos_patterns": ast.literal_eval(init["joint_pos"]),
        "default_joint_vel_patterns": ast.literal_eval(init["joint_vel"]),
        "source": {"env_cfg.py": {"path": env_cfg_path, "sha256": sha256_file(env_cfg_path)},
                   "unitree.py": {"path": assets_path, "sha256": sha256_file(assets_path)}},
    }


def load_loose_yaml(path: str) -> dict:
    """rsl_rl 이 적은 env.yaml (python 태그 포함) 을 객체를 만들지 않고 읽는다. tuple · slice 는 list 가 된다."""
    import yaml

    class _Loose(yaml.SafeLoader):
        pass

    def _any(loader, suffix, node):
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node, deep=True)
        if isinstance(node, yaml.MappingNode):
            return loader.construct_mapping(node, deep=True)
        return loader.construct_scalar(node)

    _Loose.add_multi_constructor("tag:yaml.org,2002:python/", _any)
    with open(path, encoding="utf-8") as f:
        return yaml.load(f, _Loose)


def parse_v2_env_yaml(path: str = V2_ENV_YAML) -> dict:
    d = load_loose_yaml(path)
    pol = d["observations"]["policy"]
    if pol.get("history_length") not in (None, 0):
        raise ValueError("v2 policy 그룹에 이력이 있다 (이 adapter 는 이력 없는 v2 만)")
    hs = d["scene"]["height_scanner"]
    pat = hs["pattern_cfg"]
    n_rays = int(grid_pattern_local(pat["size"], pat["resolution"], pat["ordering"]).shape[0])
    terms = []
    for name, t in pol.items():
        if name in GROUP_KEYS:
            continue
        if t.get("history_length", 0) not in (0, None):
            raise ValueError(f"v2 관측 항 {name} 에 이력이 있다")
        func = t["func"].split(":")[-1]
        params = t.get("params") or {}
        if func in ("joint_pos_rel", "joint_vel_rel") and "asset_cfg" in params:
            raise ValueError("v2 관절 관측에 asset_cfg 가 있다 (이 adapter 는 전 관절 articulation 순서만)")
        clip = tuple(t["clip"]) if t.get("clip") else None
        scale = None if t.get("scale") is None else float(t["scale"])
        if func == "height_scan_with_gap":
            if params.get("sensor_cfg", {}).get("name") != "height_scanner":
                raise ValueError("height_scan 센서가 height_scanner 가 아니다")
            tp = (("offset", float(params["offset"])), ("miss_value", float(params["miss_value"])))
            dim = n_rays
        else:
            tp = ()
            dim = {"base_lin_vel": 3, "base_ang_vel": 3, "projected_gravity": 3, "generated_commands": 3,
                   "joint_pos_rel": 12, "joint_vel_rel": 12, "last_action": 12}[func]
        terms.append(TermSpec(name, func, dim, scale, clip, tp))
    a = d["actions"]["joint_pos"]
    if not str(a["class_type"]).endswith(":JointPositionAction") or not a["use_default_offset"] or float(a.get("offset") or 0.0) != 0.0:
        raise ValueError(f"v2 행동 설정이 예상과 다르다: {a}")
    rob = d["scene"]["robot"]["init_state"]
    return {
        "model": "v2",
        "policy_terms": terms,
        "action": {"class": a["class_type"], "joint_names": list(a["joint_names"]), "scale": a["scale"], "clip": a["clip"],
                   "preserve_order": bool(a["preserve_order"]), "use_default_offset": bool(a["use_default_offset"])},
        "default_joint_pos_patterns": rob["joint_pos"],
        "default_joint_vel_patterns": rob["joint_vel"],
        "height_scanner": {"size": list(pat["size"]), "resolution": float(pat["resolution"]), "ordering": pat["ordering"],
                           "offset_pos": list(hs["offset"]["pos"]), "ray_alignment": hs.get("ray_alignment"), "num_rays": n_rays},
        "sim": {"dt": d["sim"]["dt"], "decimation": d["decimation"]},
        "source": {"foothold-v2.env.yaml": {"path": os.path.abspath(path).replace("\\", "/"), "sha256": sha256_file(path)}},
    }


# --------------------------------------------------------------------------------------------- CPU 정책 적재


def load_cts_policy_cpu(checkpoint: str, agent_yaml: str | None = None, critic_dim: int | None = None):
    """ActorCriticMoECTS 를 CPU 에 짓고 체크포인트를 strict 로 읽는다. 구조 값은 학습 run 의 params/agent.yaml 에서.
    생성자가 critic 차원을 요구하므로 critic 열쇠 차원은 체크포인트의 teacher_encoder 첫 층에서 읽는다 (추론에는 안 쓴다)."""
    from tensordict import TensorDict
    from rsl_rl.modules.actor_critic_moe_cts import ActorCriticMoECTS
    agent_yaml = agent_yaml or os.path.join(os.path.dirname(checkpoint), "params", "agent.yaml")
    pc = load_loose_yaml(agent_yaml)["policy"]
    sd = torch.load(checkpoint, map_location="cpu", weights_only=False)["model_state_dict"]
    n_pol = sd["student_moe_encoder.moe.experts.backbone.network.0.weight"].shape[1]
    n_crit = critic_dim or sd["teacher_encoder.0.network.0.weight"].shape[1]
    n_single = sd["actor.network.0.weight"].shape[1] - int(pc["latent_dim"])
    n_act = sd["actor.network.6.weight"].shape[0] if "actor.network.6.weight" in sd else int(sd["std"].shape[0])
    obs = TensorDict({"policy": torch.zeros(1, n_pol), "critic": torch.zeros(1, n_crit), "single_obs": torch.zeros(1, n_single)},
                     batch_size=[1])
    kw = {k: pc[k] for k in ("actor_hidden_dims", "critic_hidden_dims", "teacher_encoder_hidden_dims", "student_encoder_hidden_dims",
                             "expert_num", "activation", "init_noise_std", "noise_std_type", "state_dependent_std", "latent_dim",
                             "norm_type", "actor_obs_normalization", "critic_obs_normalization") if k in pc}
    m = ActorCriticMoECTS(obs, {"policy": ["policy"], "critic": ["critic"]}, n_act, **kw)
    m.load_state_dict(sd, strict=True)
    m.eval()
    return m, {"agent_yaml": agent_yaml, "agent_yaml_sha256": sha256_file(agent_yaml), "checkpoint_sha256": sha256_file(checkpoint),
               "dims": {"policy": n_pol, "critic": n_crit, "single_obs": n_single, "actions": n_act}}


def load_v2_policy_cpu(checkpoint: str = V2_CHECKPOINT, agent_yaml: str = V2_AGENT_YAML):
    from tensordict import TensorDict
    from rsl_rl.modules import ActorCritic
    pc = load_loose_yaml(agent_yaml)["policy"]
    sd = torch.load(checkpoint, map_location="cpu", weights_only=False)["model_state_dict"]
    n_obs = sd["actor.0.weight"].shape[1]
    n_act = sd["actor.6.weight"].shape[0]
    obs = TensorDict({"policy": torch.zeros(1, n_obs)}, batch_size=[1])
    kw = {k: pc[k] for k in ("actor_hidden_dims", "critic_hidden_dims", "activation", "init_noise_std", "noise_std_type",
                             "state_dependent_std", "actor_obs_normalization", "critic_obs_normalization") if k in pc}
    m = ActorCritic(obs, {"policy": ["policy"], "critic": ["policy"]}, n_act, **kw)
    m.load_state_dict(sd, strict=True)
    m.eval()
    return m, {"agent_yaml": agent_yaml, "agent_yaml_sha256": sha256_file(agent_yaml), "checkpoint_sha256": sha256_file(checkpoint),
               "dims": {"policy": n_obs, "actions": n_act}}


# --------------------------------------------------------------------------------------------- native 기록 형식

# dump_native_*.py 가 쓰고 compare_native.py 가 읽는 npz 열쇠. T = 정책 step 수, N = env 수, J = articulation 관절 수.
# 시각 약속: 지표 k 의 상태 · 관측은 action[k] 를 고르기 직전 (정책이 본 그 값). action[k] 를 적용한 뒤가 k+1.
DUMP_COMMON = {
    "art_joint_names": "(J,) robot.data.joint_names",
    "obs_joint_names": "(12,) 관절 관측 항이 읽는 이름 순서 (런타임 asset_cfg 해석)",
    "action_joint_names": "(12,) 행동 항 _joint_names",
    "default_joint_pos": "(N, J) robot.data.default_joint_pos (articulation 순서)",
    "default_joint_vel": "(N, J)",
    "root_pos_w": "(T+1, N, 3)", "root_quat_w": "(T+1, N, 4)",
    "lin_vel_b": "(T+1, N, 3)", "ang_vel_b": "(T+1, N, 3)", "projected_gravity_b": "(T+1, N, 3)",
    "command": "(T+1, N, 3) 관측 시각의 명령 항 값",
    "joint_pos": "(T+1, N, J) articulation 순서", "joint_vel": "(T+1, N, J)",
    "last_action": "(T+1, N, 12) action_manager.action (관측 시각)",
    "obs_policy": "(T+1, N, D)",
    "raw_action": "(T, N, 12) 정책 출력", "action_offset": "(T, N, 12) step k 의 process_action 이 쓴 _offset",
    "joint_target": "(T, N, 12) processed_actions (step k)",
    "reset_after_step": "(T, N) step k 안에서 reset 된 env (관측 k+1 은 reset 뒤)",
    "terminated": "(T, N)", "time_out": "(T, N)",
    "cell_index": "(N,)", "cell_names": "(C,)", "cell_cmd": "(C, 3)",
}
DUMP_CTS = {"obs_single_obs": "(T+1, N, 45)", "obs_critic": "(T+1, N, 275)"}
DUMP_V2 = {"height_sensor_pos_w": "(T+1, N, 3) RayCaster data.pos_w", "ray_hits_w": "(T+1, N, R, 3)",
           "ray_starts_local": "(R, 3) sensor.ray_starts[0] (offset 포함)"}


def check_dump_keys(d, model: str) -> list:
    want = dict(DUMP_COMMON, **(DUMP_CTS if model == "cts_student" else DUMP_V2))
    return [k for k in want if k not in d]


def state_from_dump(d, k: int, with_last_action: bool = False) -> RawState:
    t = lambda a: torch.as_tensor(np.asarray(a), dtype=torch.float32)  # noqa: E731
    return RawState(
        joint_names=[str(x) for x in d["art_joint_names"]],
        joint_pos=t(d["joint_pos"][k]), joint_vel=t(d["joint_vel"][k]),
        ang_vel_b=t(d["ang_vel_b"][k]), projected_gravity_b=t(d["projected_gravity_b"][k]), command=t(d["command"][k]),
        lin_vel_b=t(d["lin_vel_b"][k]),
        last_action_raw=t(d["last_action"][k]) if with_last_action else None,
        height_sensor_z=t(d["height_sensor_pos_w"][k][:, 2]) if "height_sensor_pos_w" in d else None,
        ray_hits_z=t(d["ray_hits_w"][k][..., 2]) if "ray_hits_w" in d else None,
    )


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="CE12 adapter 서명 JSON 쓰기")
    ap.add_argument("--model", choices=["cts", "v2"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--joint_names_from", default="", help="v2: native 기록 npz (obs_joint_names · action_joint_names 를 읽는다)")
    a = ap.parse_args(argv)
    if a.model == "cts":
        ad = CTSStudentAdapter.from_source(1)
    else:
        if not a.joint_names_from:
            print("v2 관절 순서는 런타임 기록 (dump_native_v2.py 의 npz) 에서만 받는다. --joint_names_from 이 없어 쓰지 않는다.")
            return 2
        d = np.load(a.joint_names_from)
        ad = V2Adapter.from_env_yaml([str(x) for x in d["obs_joint_names"]], 1, [str(x) for x in d["action_joint_names"]])
    sig = write_signature(ad, a.out)
    print(a.out, sig["signature_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
