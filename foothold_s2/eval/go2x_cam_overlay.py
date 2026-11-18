"""실기 Go2 X 카메라 장착 차이 평가 덧대기 (planner-lx DESIGN-GO2X-CAM-EVAL-1118.md · lead 11/18). 정본 코드 · contract 는 안 고친다.

평가기가 env 를 만든 뒤 `install(env)` 한 줄을 부르면, 환경 변수로 고른 판 (GO2X_CAM_VARIANT = A | R | B | C | D) 이 붙는다.
  A  시뮬 장착 (0.25, 0, 0.12) 그대로. 아무 것도 안 바꾼다 (기준). 첫 스텝에 offset 되읽기 줄만 찍는다.
  R  실측 장착 (0.35, 0, 0.07) · 깊이를 시뮬 시점으로 재투영 (화소당 가장 가까운 점 · 빈 화소 = inf = 정규화 1.0).
  B  실측 장착 · 깊이 그대로.
  C  실측 장착 · 무효 가면 (smooth_noise 분위수 문턱: 평균 무효 화소 11 %, 고정 문턱 0.11 은 5 % 쯤이라 안 씀) + 프레임 dropout.
  D  장착 오차 (x 0.25~0.35 · z 0.07~0.12 · 아래각 35 ± 1 도, 리셋마다 env 별 뽑기) · 무효 가면 · stall.
stall (가) GO2X_CAM_STALL=depth: 깊이 전달만 마지막 프레임에 붙든다. (나) =obs: 그 env 의 관측 · 행동이 다 멈춘다 (정책이 낸 행동은 버리고 마지막 행동 유지, 관측은 얼린 값).
쓰는 값 (환경 변수, 괄호는 기본):
  GO2X_CAM_SEED (0) · GO2X_CAM_INVALID_LEVEL (0.11) · GO2X_CAM_DROPOUT_P (C 0.03 · 그 밖 0: 깊이 갱신마다 프레임 전체가 무효가 될 확률 · 미확인 값, planner 가 정함)
  GO2X_CAM_STALL (D depth · 그 밖 none) · GO2X_CAM_STALL_RATE (0.2: env 당 초당 stall 시작 횟수 · 미확인 값) · GO2X_CAM_STALL_S ("0.1,1.0")
  GO2X_CAM_REAL_POS ("0.35,0,0.07") · GO2X_CAM_SIM_POS ("0.25,0,0.12") · GO2X_CAM_PITCH_DEG (35)
  GO2X_CAM_RECORD (경로): `dump()` 가 장착 값 · stall 구간 · 행동을 npz 로 쓴다.
Kit 없이 CPU 로 시험 가능한 부분 (기하 · 재투영 · 가면 · 상태기계) 은 순수 torch 이고, env 에 붙는 부분은 Isaac Lab 의 속성 이름 (camera._offset_pos · _offset_quat ·
camera.reset · observation_manager._group_obs_term_cfgs · event_manager._mode_term_cfgs) 을 그대로 쓴다 (tasks/s2_23f_camera.py 42~50 과 같은 버퍼).
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

import torch

from foothold_s2.sensors import depth_aug
from foothold_s2.sensors.depth_cam_cfg import CX, CY, FX, FY, HEIGHT, WIDTH

VARIANTS = ("A", "R", "B", "C", "D")
CAMERA_NAME = "depth_cam"
READBACK_TOL = 1e-5


def _floats(text: str, n: int) -> tuple[float, ...]:
    out = tuple(float(x) for x in text.replace(" ", "").split(",") if x != "")
    if len(out) != n:
        raise ValueError(f"expected {n} numbers, got {text!r}")
    return out


@dataclass
class OverlayCfg:
    variant: str = "A"
    seed: int = 0
    real_pos: tuple = (0.35, 0.0, 0.07)
    sim_pos: tuple = (0.25, 0.0, 0.12)
    pitch_deg: float = 35.0
    x_range: tuple = (0.25, 0.35)               # D: 장착 오차 범위
    z_range: tuple = (0.07, 0.12)
    pitch_jitter_deg: float = 1.0
    invalid_level: float = 0.11
    dropout_p: float = 0.0
    stall: str = "none"                          # none | depth | obs
    stall_rate: float = 0.2
    stall_s: tuple = (0.1, 1.0)
    noise_grid: int = 6                          # depth_aug.DepthAugCfg.noise_grid 와 같음
    record_path: str | None = None

    @classmethod
    def from_env(cls, environ=None) -> "OverlayCfg":
        e = os.environ if environ is None else environ
        v = e.get("GO2X_CAM_VARIANT", "A").upper()
        if v not in VARIANTS:
            raise ValueError(f"GO2X_CAM_VARIANT must be one of {VARIANTS}, got {v!r}")
        cfg = cls(variant=v, seed=int(e.get("GO2X_CAM_SEED", 0)), pitch_deg=float(e.get("GO2X_CAM_PITCH_DEG", 35.0)),
                  invalid_level=float(e.get("GO2X_CAM_INVALID_LEVEL", 0.11)), stall_rate=float(e.get("GO2X_CAM_STALL_RATE", 0.2)),
                  stall_s=_floats(e.get("GO2X_CAM_STALL_S", "0.1,1.0"), 2), real_pos=_floats(e.get("GO2X_CAM_REAL_POS", "0.35,0,0.07"), 3),
                  sim_pos=_floats(e.get("GO2X_CAM_SIM_POS", "0.25,0,0.12"), 3), record_path=e.get("GO2X_CAM_RECORD"))
        cfg.dropout_p = float(e.get("GO2X_CAM_DROPOUT_P", 0.03 if v == "C" else 0.0))
        cfg.stall = e.get("GO2X_CAM_STALL", "depth" if v == "D" else "none").lower()
        if cfg.stall not in ("none", "depth", "obs"):
            raise ValueError(f"GO2X_CAM_STALL must be none, depth or obs, got {cfg.stall!r}")
        if not 0.0 <= cfg.dropout_p <= 1.0 or not 0.0 <= cfg.invalid_level <= 1.0 or cfg.stall_s[0] <= 0 or cfg.stall_s[1] < cfg.stall_s[0]:
            raise ValueError("GO2X_CAM probability / stall range out of range")
        return cfg

    @property
    def masks(self) -> bool:
        return self.variant in ("C", "D")

    @property
    def moves_camera(self) -> bool:
        return self.variant != "A"


# ---------------------------------------------------------------- 기하 (순수 torch)

def pitch_quat(pitch_deg: torch.Tensor) -> torch.Tensor:
    """world 규약 (x 앞 · z 위) 에서 +y 축으로 pitch 만큼 (w, x, y, z). tasks/s2_23f_camera.py 의 local_quat 과 같은 식."""
    p = torch.deg2rad(pitch_deg)
    return torch.stack((torch.cos(p / 2), torch.zeros_like(p), torch.sin(p / 2), torch.zeros_like(p)), dim=-1)


def _basis(pitch_rad: torch.Tensor):
    """카메라 광학 축 (오른 · 아래 · 앞) 의 몸 좌표 벡터. pitch (N,) -> 세 개의 (N, 3)."""
    c, s = torch.cos(pitch_rad), torch.sin(pitch_rad)
    z, o = torch.zeros_like(c), torch.ones_like(c)
    right = torch.stack((z, -o, z), -1)
    down = torch.stack((-s, z, -c), -1)
    fwd = torch.stack((c, z, -s), -1)
    return right, down, fwd


def pixel_rays() -> tuple[torch.Tensor, torch.Tensor]:
    """화소 중심의 (x/z, y/z) 광학 좌표 (H, W). 행 0 = 위."""
    v, u = torch.meshgrid(torch.arange(HEIGHT).float() + 0.5, torch.arange(WIDTH).float() + 0.5, indexing="ij")
    return (u - CX) / FX, (v - CY) / FY


def flat_ground_depth(pos, pitch_deg: float, base_height: float) -> torch.Tensor:
    """평지 (몸 기준 z = -base_height) 를 이 장착으로 찍은 영상면 거리 (H, W) m. 시험 · 점검용 (몸 수평 가정)."""
    cx, cy = pixel_rays()
    right, down, fwd = (t[0] for t in _basis(torch.tensor([math.radians(pitch_deg)])))
    dz = fwd[2] + cx * right[2] + cy * down[2]                  # 광선 방향의 몸 z 성분 (z 깊이 1 당)
    t = (-base_height - pos[2]) / dz
    return torch.where(t > 0, t, torch.full_like(t, float("inf")))


def reproject(depth: torch.Tensor, src_pos, src_pitch_deg, dst_pos, dst_pitch_deg) -> torch.Tensor:
    """src 장착으로 찍은 영상면 거리 (N, H, W) 를 dst 장착 시점의 영상으로 다시 찍는다 (점 -> 몸 좌표 -> dst 카메라 -> 화소).
    화소당 가장 가까운 점 (z 버퍼). 점이 하나도 안 떨어진 화소 · 카메라 뒤 · 화면 밖 = inf. src/dst 는 (3,) 또는 (N, 3), 각은 float 또는 (N,)."""
    n, h, w = depth.shape
    dev = depth.device

    def vec(x, k):
        t = torch.as_tensor(x, dtype=depth.dtype, device=dev)
        return t.expand(n, k) if t.dim() == 1 else t

    def ang(x):
        t = torch.as_tensor(x, dtype=depth.dtype, device=dev)
        return torch.deg2rad(t.expand(n) if t.dim() == 0 else t.reshape(n))

    sp, dp = vec(src_pos, 3), vec(dst_pos, 3)
    sa, da = ang(src_pitch_deg), ang(dst_pitch_deg)
    cx, cy = (t.to(dev, depth.dtype) for t in pixel_rays())
    sr, sd, sf = _basis(sa)
    dr, dd, df = _basis(da)
    z = depth
    pts = (sp[:, None, None, :] + z[..., None] * (sf[:, None, None, :] + cx[None, ..., None] * sr[:, None, None, :] + cy[None, ..., None] * sd[:, None, None, :]))
    rel = pts - dp[:, None, None, :]
    xc, yc, zc = (rel * dr[:, None, None, :]).sum(-1), (rel * dd[:, None, None, :]).sum(-1), (rel * df[:, None, None, :]).sum(-1)
    ok = torch.isfinite(z) & (zc > 1e-6)
    zc_safe = torch.where(ok, zc, torch.ones_like(zc))
    u = torch.floor(FX * xc / zc_safe + CX).long()
    v = torch.floor(FY * yc / zc_safe + CY).long()
    ok = ok & (u >= 0) & (u < w) & (v >= 0) & (v < h)
    flat = (torch.arange(n, device=dev)[:, None, None] * (h * w) + v.clamp(0, h - 1) * w + u.clamp(0, w - 1))
    out = torch.full((n * h * w,), float("inf"), dtype=depth.dtype, device=dev)
    out.scatter_reduce_(0, flat[ok], zc[ok], reduce="amin", include_self=True)
    return out.view(n, h, w)


# ---------------------------------------------------------------- 무효 가면 · dropout

_THR_CACHE: dict = {}


def calibrated_threshold(level: float, grid: int) -> float:
    """smooth_noise 값은 0.5 근처에 몰려 (성긴 균등 격자의 bicubic) `noise < 0.11` 은 화소의 5 % 쯤만 무효로 만든다 (시험으로 잼).
    설계의 「무효 11 %」 는 화소 비율이라, 같은 잡음의 분위수로 문턱을 잡아 평균 무효 비율이 level 이 되게 한다 (고정 시드 표본 한 번 · 캐시)."""
    key = (round(level, 6), grid)
    if key not in _THR_CACHE:
        g = torch.Generator().manual_seed(12345)
        sample = depth_aug.smooth_noise(512, HEIGHT, WIDTH, grid, g, "cpu").flatten()
        k = max(1, int(round(level * sample.numel())))
        _THR_CACHE[key] = float(sample.kthvalue(k).values) if level > 0 else -1.0
    return _THR_CACHE[key]


def invalid_mask(n: int, level: float, grid: int, generator=None, device="cpu") -> torch.Tensor:
    """depth_aug.smooth_noise 재사용: 매끈한 잡음이 문턱 (평균 무효 비율이 level 이 되는 분위수) 아래인 화소가 무효 (N, H, W) bool."""
    return depth_aug.smooth_noise(n, HEIGHT, WIDTH, grid, generator, device) <= calibrated_threshold(level, grid)


def apply_invalid(depth: torch.Tensor, mask: torch.Tensor, dropout: torch.Tensor | None = None) -> torch.Tensor:
    """무효 화소 = inf (정규화 1.0 = 미검출). dropout (N,) bool 이면 그 env 의 프레임 전체가 무효."""
    out = torch.where(mask, torch.full_like(depth, float("inf")), depth)
    if dropout is not None:
        out = torch.where(dropout[:, None, None], torch.full_like(out, float("inf")), out)
    return out


# ---------------------------------------------------------------- stall 상태기계

class StallClock:
    """env 별 stall 구간. 매 스텝 `tick()` 이 새 stall 을 시작시키고, 진행 중인 env 의 bool (N,) 을 돌려준다. 구간은 records 에 (env, 시작 스텝, 길이) 로 쌓인다."""

    def __init__(self, n: int, step_dt: float, rate: float, dur_s: tuple, generator, device="cpu"):
        self.n, self.dt, self.rate, self.dur, self.g, self.dev = n, step_dt, rate, dur_s, generator, device
        self.left = torch.zeros(n, dtype=torch.long, device=device)
        self.step = 0
        self.records: list[tuple[int, int, int]] = []

    def tick(self) -> torch.Tensor:
        starts = (self.left == 0) & (torch.rand(self.n, generator=self.g, device=self.dev) < self.rate * self.dt)
        if bool(starts.any()):
            dur = self.dur[0] + (self.dur[1] - self.dur[0]) * torch.rand(self.n, generator=self.g, device=self.dev)
            steps = torch.clamp(torch.ceil(dur / self.dt).long(), min=1)
            for i in torch.nonzero(starts).flatten().tolist():
                self.records.append((i, self.step, int(steps[i])))
            self.left = torch.where(starts, steps, self.left)
        active = self.left > 0
        self.left = torch.clamp(self.left - 1, min=0)
        self.step += 1
        return active


def _hold(new, last, active):
    """active 인 행은 last, 아니면 new (첫 프레임 last = None 이면 new)."""
    if last is None:
        return new
    shape = (-1,) + (1,) * (new.dim() - 1)
    return torch.where(active.view(shape), last, new)


def _freeze(obj, last, active):
    """관측 (텐서 · dict · 튜플) 의 행 별 얼림. 텐서는 leading N."""
    if isinstance(obj, torch.Tensor):
        return _hold(obj, last, active)
    if isinstance(obj, dict):
        return {k: _freeze(v, None if last is None else last[k], active) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return type(obj)(_freeze(v, None if last is None else last[i], active) for i, v in enumerate(obj))
    return obj


def _clone(obj):
    if isinstance(obj, torch.Tensor):
        return obj.clone()
    if isinstance(obj, dict):
        return {k: _clone(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return type(obj)(_clone(v) for v in obj)
    return obj


# ---------------------------------------------------------------- env 에 붙이기

@dataclass
class Overlay:
    cfg: OverlayCfg
    env: object
    seed: int = 0
    mount_pos: torch.Tensor = None             # (N, 3) 지금 붙인 값
    mount_pitch: torch.Tensor = None           # (N,) 도
    clock: StallClock | None = None
    last_depth: torch.Tensor | None = None
    first_readback_done: bool = False
    action_log: list = field(default_factory=list)
    stall_obs_active_log: list = field(default_factory=list)
    original_depth_fn: object = None
    _gens: dict = field(default_factory=dict)

    def gen(self, device) -> torch.Generator:
        key = str(device)
        if key not in self._gens:
            g = torch.Generator(device=key)
            g.manual_seed(self.seed)
            self._gens[key] = g
        return self._gens[key]

    # -- 장착
    def sample_mount(self, n: int, device):
        c = self.cfg
        if c.variant in ("R", "B", "C"):
            pos = torch.tensor(c.real_pos, device=device).expand(n, 3).clone()
            pitch = torch.full((n,), c.pitch_deg, device=device)
        elif c.variant == "D":
            u = torch.rand(n, 3, generator=self.gen(device), device=device)
            pos = torch.stack((c.x_range[0] + (c.x_range[1] - c.x_range[0]) * u[:, 0], torch.zeros(n, device=device),
                               c.z_range[0] + (c.z_range[1] - c.z_range[0]) * u[:, 1]), -1)
            pitch = c.pitch_deg + (u[:, 2] * 2 - 1) * c.pitch_jitter_deg
        else:
            raise ValueError("variant A does not move the camera")
        return pos, pitch

    def apply_mount(self, env_ids) -> None:
        camera = self.env.scene.sensors[CAMERA_NAME]
        ids = torch.as_tensor(env_ids, dtype=torch.long, device=camera._offset_pos.device)
        if len(ids) == 0:
            return
        pos, pitch = self.sample_mount(len(ids), camera._offset_pos.device)
        camera._offset_pos[ids] = pos.to(camera._offset_pos.dtype)
        camera._offset_quat[ids] = pitch_quat(pitch).to(camera._offset_quat.dtype)
        camera.reset(ids)                                           # tasks/s2_23f_camera.py 와 같은 순서: 버퍼를 쓴 뒤 reset
        if self.mount_pos is None:
            n = camera._offset_pos.shape[0]
            self.mount_pos = torch.zeros(n, 3, device=pos.device)
            self.mount_pitch = torch.zeros(n, device=pos.device)
        self.mount_pos[ids], self.mount_pitch[ids] = pos, pitch

    def readback_line(self) -> str:
        """첫 스텝에 찍는 줄: 카메라가 실제로 들고 있는 offset 을 되읽는다. 덧댄 값과 어긋나면 RuntimeError (판을 버린다)."""
        camera = self.env.scene.sensors[CAMERA_NAME]
        pos = camera._offset_pos.detach().float().cpu()
        quat = camera._offset_quat.detach().float().cpu()
        pitch = torch.rad2deg(2 * torch.atan2(quat[:, 2], quat[:, 0]))
        line = (f"GO2X_CAM_OFFSET_READBACK variant={self.cfg.variant} n={len(pos)} pos_mean={[round(float(x), 4) for x in pos.mean(0)]} "
                f"pos_min={[round(float(x), 4) for x in pos.min(0).values]} pos_max={[round(float(x), 4) for x in pos.max(0).values]} "
                f"pitch_deg_mean={float(pitch.mean()):.3f} min={float(pitch.min()):.3f} max={float(pitch.max()):.3f}")
        if self.cfg.moves_camera:
            want_p, want_a = self.mount_pos.detach().float().cpu(), self.mount_pitch.detach().float().cpu()
            bad = float((pos - want_p).abs().max()) > READBACK_TOL or float((pitch - want_a).abs().max()) > 1e-3
            line += f" applied_match={'OK' if not bad else 'MISMATCH'}"
            if bad:
                raise RuntimeError(line + " : the overlay did not reach the camera buffers (discard this variant)")
        else:
            sx = self.cfg.sim_pos
            near = bool(((pos - torch.tensor(sx)).abs().max() <= 0.0101) and ((pitch - self.cfg.pitch_deg).abs().max() <= 1.001))
            line += f" sim_mount_within_training_jitter={'OK' if near else 'NO'}"
        return line

    # -- 깊이
    def depth_term(self, env, sensor_cfg):
        """start_obs.depth_obs 를 대신하는 갈고리. A 는 원래 함수 그대로. 그 밖에는 미터 깊이 -> (재투영 | 무효 가면 · dropout) -> (가) stall 붙들기 -> augment (평가기는 끔)."""
        aug = getattr(self.original_depth_fn, "__globals__", {}).get("AUG") or depth_aug.DepthAugCfg(enabled=False)   # 평가기는 start_obs.AUG 를 끈다
        c = self.cfg
        if not self.first_readback_done:
            print(self.readback_line(), flush=True)
            self.first_readback_done = True
        d = env.scene.sensors[sensor_cfg.name].data.output["distance_to_image_plane"][..., 0]
        n = d.shape[0]
        if c.masks:
            m = invalid_mask(n, c.invalid_level, c.noise_grid, self.gen(d.device), d.device)
            drop = (torch.rand(n, generator=self.gen(d.device), device=d.device) < c.dropout_p) if c.dropout_p > 0 else None
            d = apply_invalid(d, m, drop)
        if c.variant == "R":
            d = reproject(d, self.mount_pos.to(d.device), self.mount_pitch.to(d.device), c.sim_pos, c.pitch_deg)
        if c.stall == "depth" and self.clock is not None:
            active = self._stall_active()
            d = _hold(d, self.last_depth, active)
            self.last_depth = d.clone()
        return depth_aug.augment(d, aug).flatten(1)

    def _stall_active(self):
        return self.clock.tick()                  # 깊이 판은 깊이 갈고리 호출마다, (나) 판은 env.step 마다 한 번

    # -- 기록
    def dump(self, path=None) -> str | None:
        path = path or self.cfg.record_path
        if not path:
            return None
        import numpy as np

        actions = torch.stack(self.action_log).cpu().numpy() if self.action_log else np.zeros((0,))
        stalls = np.array(self.clock.records, dtype=np.int64) if self.clock is not None and self.clock.records else np.zeros((0, 3), dtype=np.int64)
        obs_stall = torch.stack(self.stall_obs_active_log).cpu().numpy() if self.stall_obs_active_log else np.zeros((0,), dtype=bool)
        np.savez_compressed(path, variant=self.cfg.variant, mount_pos=self.mount_pos.cpu().numpy() if self.mount_pos is not None else np.zeros((0, 3)),
                            mount_pitch_deg=self.mount_pitch.cpu().numpy() if self.mount_pitch is not None else np.zeros((0,)),
                            stall_records_env_start_len=stalls, stall_kind=self.cfg.stall, actions_applied=actions, obs_stall_active=obs_stall,
                            cfg=repr(self.cfg))
        return str(path)


def _find_depth_term(env):
    om = env.observation_manager
    for group, terms in om._group_obs_term_cfgs.items():
        names = om._group_obs_term_names[group]
        for name, cfg in zip(names, terms):
            if name == "depth":
                return cfg
    raise RuntimeError("no 'depth' observation term found in the observation manager")


def install(env, cfg: OverlayCfg | None = None) -> Overlay:
    """env (ManagerBasedRLEnv, 만든 뒤 · 첫 reset 전이든 뒤든 상관없음) 에 덧대기를 붙인다. 판 A 는 장착 · 깊이를 안 바꾼다 (되읽기 줄만)."""
    cfg = cfg or OverlayCfg.from_env()
    env_u = getattr(env, "unwrapped", env)
    device = env_u.device
    ov = Overlay(cfg=cfg, env=env_u, seed=cfg.seed)
    n = env_u.num_envs
    if cfg.moves_camera:
        ov.apply_mount(torch.arange(n))
        for terms in env_u.event_manager._mode_term_cfgs.values():       # 리셋 이벤트가 장착을 다시 흔들므로 그 뒤에 덧댄다
            for term in terms:
                if getattr(term.func, "__name__", "") == "randomize_topdown_camera":
                    orig = term.func

                    def wrapped(env_, env_ids, *a, _orig=orig, **kw):
                        _orig(env_, env_ids, *a, **kw)
                        ov.apply_mount(env_ids)
                    term.func = wrapped
    else:
        ov.mount_pos = ov.mount_pitch = None
    if cfg.stall != "none":
        ov.clock = StallClock(n, float(env_u.step_dt), cfg.stall_rate, cfg.stall_s, ov.gen("cpu"), device="cpu")
    term = _find_depth_term(env_u)
    ov.original_depth_fn = term.func
    if cfg.variant != "A":
        term.func = ov.depth_term
    else:                                                          # A: 깊이는 원래 함수 그대로, 되읽기 줄만 첫 호출에 끼운다
        orig_a = term.func

        def first_call(env_, sensor_cfg):
            if not ov.first_readback_done:
                print(ov.readback_line(), flush=True)
                ov.first_readback_done = True
            return orig_a(env_, sensor_cfg)
        term.func = first_call
    if cfg.stall == "obs":
        _wrap_step(env_u, ov)
    elif cfg.record_path:
        _wrap_step(env_u, ov)
    print(f"GO2X_CAM_OVERLAY_INSTALLED {cfg}", flush=True)
    return ov


def _wrap_step(env, ov: Overlay) -> None:
    """(나) env.step 감싸기: stall 중인 env 는 정책 행동을 버리고 마지막 행동을 쓰며, 돌려주는 관측은 stall 시작 직전 값으로 얼린다. 기록용 (행동 로그) 으로도 쓴다."""
    orig_step = env.step
    state = {"last_action": None, "frozen_obs": None}

    def step(action):
        if ov.cfg.stall == "obs" and ov.clock is not None:
            active = ov._stall_active().to(action.device)
            if state["last_action"] is not None:
                action = torch.where(active[:, None], state["last_action"], action)
        else:
            active = None
        state["last_action"] = action.clone()
        ov.action_log.append(action.detach().clone())
        out = orig_step(action)
        if active is not None:
            obs = out[0]
            frozen = state["frozen_obs"]
            obs_f = _freeze(obs, frozen, active)
            state["frozen_obs"] = _clone(obs_f)
            ov.stall_obs_active_log.append(active.clone())
            out = (obs_f,) + tuple(out[1:])
        return out
    env.step = step
