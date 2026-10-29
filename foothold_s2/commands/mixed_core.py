"""명령 생성기의 계산 (torch). Kit 없이 CPU 에서 시험하고, 학습 때는 GPU 텐서로 같은 함수를 부른다.

Isaac Lab 쪽 `CommandTerm`(`mixed_command.py`)은 이 모듈을 부르기만 한다. 식을 한 곳에 두어 L0 시험이
실제 학습 코드와 같은 식을 보게 한다. 난수는 모두 `torch.Generator` 로 뽑는다 (시험 재현 · 학습 시드).

방식 (env 마다 하나, 14 §3)
  자유 속도  |vx| |vy| ~ U[0, vmax] 에 부호 무작위, wz ~ U[-2, 2], 칸마다 독립으로 0 처리(유지 확률 0.9 · 0.75 · 0.5).
             재추출(4 s)마다 정지 > 제자리 회전 > heading > 자유 wz 순으로 뽑는다 (14 §3.2).
  깃발       다음 깃발 방향 x v, v ~ U[0, 1.0], v < 0.3 이면 제자리 회전 wz ~ U[-1.2, 1.2] (START 식).
             0.5 m 안이면 다음 깃발. 마지막 깃발에서는 세 칸 0 을 2 s 이상 유지. 물러나기(확률 `backoff_prob`)는 S1-b 용.

JEPLO 는 GPLv3 라 코드를 복사하지 않았다. 식과 값만 14 문서에서 옮겼다.
"""

import math
from dataclasses import dataclass, field

import torch

TWO_PI = 2.0 * math.pi


@dataclass
class CommandParams:
    # 자유 속도 (14 §3 · 3.2)
    vmax_x: float = 1.0
    vmax_y: float = 1.0
    wz_max: float = 2.0
    keep_x: float = 0.9
    keep_y: float = 0.75
    keep_wz: float = 0.5
    resample_s: float = 4.0
    p_stand: float = 0.1
    p_spin: float = 0.2
    spin_after_iter: int = 1000
    heading_flag_after: float = 5.0 / 12.0   # 0.417 = 0.30 / (0.9 x 0.8)
    heading_flag_before: float = 1.0 / 3.0   # 0.333 = 0.30 / 0.9
    heading_stiffness: float = 0.5
    # 깃발
    flag_vmax: float = 1.0
    flag_spin_threshold: float = 0.3
    flag_spin_wz: float = 1.2
    flag_wz_clip: float = 1.0
    flag_reach_m: float = 0.5
    flag_final_hold_s: float = 2.0
    backoff_prob: float = 0.0
    backoff_vmin: float = 0.1
    backoff_vmax: float = 0.3
    backoff_s: float = 2.0
    # START 원문 명령 (lead 10/21 G0-start): vx U[0, 1.5] · vy 0 · vx < 0.3 이면 vx = 0 이고 wz U[-1.2, 1.2] (제자리 회전), 그 밖에는 wz 0. 정지 · heading · 깃발 없음.
    start_mode: bool = False
    start_vmax: float = 1.5
    start_spin_threshold: float = 0.3
    start_spin_wz: float = 1.2
    # S2a (EX-35, DESIGN-NEXT v0.3 3.2): START 원문에서 전진 5 %p 를 떼어 걸으며 돌기를 넣는다. 재추출 4 s · vy 0.
    # 전진 직진 vx U[0.3, 1.5] wz 0 75 % / 걸으며 돌기 vx U[0.3, 0.8] wz 부호 x U[0.2, 0.5] 2.5 % + 2.5 % / 제자리 회전 vx 0 wz U[-1.2, 1.2] 10 % + 10 % (START 그대로). 정지 0.
    walkturn_mode: bool = False
    wt_p_forward: float = 0.75
    wt_p_walkturn_each: float = 0.025
    wt_p_spin_each: float = 0.10
    wt_fwd_vmin: float = 0.3
    wt_fwd_vmax: float = 1.5
    wt_walk_vmin: float = 0.3
    wt_walk_vmax: float = 0.8
    wt_wz_min: float = 0.2
    wt_wz_max: float = 0.5
    wt_spin_wz: float = 1.2
    # 기본 보행 준비판. 기존 START 와 S2a 선택값에는 영향이 없다.
    basic_mode: bool = False
    basic_new_share: float = 0.30  # 정지 · 후진 · 옆걸음 합. 대안 0.15 는 인자로 받는다.
    ex39_arm: str | None = None


def make_generator(seed, device="cpu"):
    gen = torch.Generator(device=device)
    gen.manual_seed(int(seed))

    return gen


def _u(gen, shape, low=0.0, high=1.0, device=None):
    return torch.rand(shape, generator=gen, device=device or gen.device) * (high - low) + low


# ---------------------------------------------------------------- 기하


def wrap_to_pi(angle):
    """각도를 [-pi, pi] 로. Isaac Lab `math.wrap_to_pi` 와 같은 규칙(pi 는 pi 로, 101~122 행)."""
    angle = torch.as_tensor(angle, dtype=torch.float32)
    wrapped = (angle + math.pi) % TWO_PI

    return torch.where((wrapped == 0.0) & (angle > 0.0), torch.full_like(angle, math.pi), wrapped - math.pi)


def to_body(vec_world_xy, yaw):
    """세계 평면 벡터 (n, 2) 를 몸 좌표계로 (yaw 만큼 거꾸로 돌린다)."""
    c, s = torch.cos(yaw), torch.sin(yaw)
    x, y = vec_world_xy[..., 0], vec_world_xy[..., 1]

    return torch.stack([c * x + s * y, -s * x + c * y], dim=-1)


# ---------------------------------------------------------------- 자유 속도


def sample_free(gen, n, params, vmax_x=None, vmax_y=None):
    """자유 속도 한 번 뽑기. 반환 (n, 3) = (vx, vy, wz)."""
    vx_max = params.vmax_x if vmax_x is None else vmax_x
    vy_max = params.vmax_y if vmax_y is None else vmax_y

    def signed(limit):
        sign = torch.where(_u(gen, (n,)) < 0.5, -1.0, 1.0)

        return _u(gen, (n,), 0.0, limit) * sign

    cmd = torch.stack([signed(vx_max), signed(vy_max), _u(gen, (n,), -params.wz_max, params.wz_max)], dim=1)
    keep = torch.stack([_u(gen, (n,)) < params.keep_x, _u(gen, (n,)) < params.keep_y,
                        _u(gen, (n,)) < params.keep_wz], dim=1)

    return torch.where(keep, cmd, torch.zeros_like(cmd))


def heading_wz(psi_star, yaw, stiffness=0.5, wz_max=2.0):
    """heading 모드의 wz = clip(stiffness x wrap(psi* - yaw), -wz_max, wz_max) (14 §3.2, Isaac Lab 식 150~158 행)."""
    psi_star = torch.as_tensor(psi_star, dtype=torch.float32)
    yaw = torch.as_tensor(yaw, dtype=torch.float32)

    return torch.clip(stiffness * wrap_to_pi(psi_star - yaw), -wz_max, wz_max)


def resample_free_modes(gen, n, params, iteration, vmax_x=None, vmax_y=None, yaw=None):
    """자유 속도 env n 개의 재추출. 반환 dict: cmd(n,3) stand spin heading (bool) psi_star(n).

    순서(14 §3.2): 정지(p_stand) > 제자리 회전(1,000 회 이후 p_spin) > heading(플래그 확률) > 자유 wz.
    wz 는 heading env 에서 «매 스텝» `apply_heading` 이 덮어쓰므로 여기서는 자유 wz 를 담아 둔다.
    """
    if params.basic_mode:
        if params.ex39_arm is not None:
            return resample_ex39(gen, n, params.ex39_arm, yaw)
        return resample_basic(gen, n, params)
    if params.walkturn_mode:
        return resample_walkturn(gen, n, params)
    if params.start_mode:
        return resample_start(gen, n, params)

    cmd = sample_free(gen, n, params, vmax_x, vmax_y)
    stand = _u(gen, (n,)) < params.p_stand
    spin_p = params.p_spin if iteration >= params.spin_after_iter else 0.0
    spin = (~stand) & (_u(gen, (n,)) < spin_p)
    flag_p = params.heading_flag_after if iteration >= params.spin_after_iter else params.heading_flag_before
    heading = (~stand) & (~spin) & (_u(gen, (n,)) < flag_p)
    psi_star = _u(gen, (n,), -math.pi, math.pi)

    spin_wz = _u(gen, (n,), -params.wz_max, params.wz_max)
    zeros = torch.zeros(n, device=cmd.device)
    spin_cmd = torch.stack([zeros, zeros, spin_wz], dim=1)
    cmd = torch.where(spin[:, None], spin_cmd, cmd)
    cmd = torch.where(stand[:, None], torch.zeros_like(cmd), cmd)

    return {"cmd": cmd, "stand": stand, "spin": spin, "heading": heading, "psi_star": psi_star}


def resample_start(gen, n, params):
    """START 원문 명령: vx ~ U[0, start_vmax], vy = 0, vx < threshold 이면 vx = 0 · wz ~ U[-spin_wz, spin_wz] (제자리 회전 가지), 아니면 wz = 0.
    원문에 «전진 중 yaw 분포» 가 없어서 wz 0 으로 둔다 (지어내지 않음)."""
    vx = _u(gen, (n,), 0.0, params.start_vmax)
    spin = vx < params.start_spin_threshold
    wz = torch.where(spin, _u(gen, (n,), -params.start_spin_wz, params.start_spin_wz), torch.zeros_like(vx))
    cmd = torch.stack([torch.where(spin, torch.zeros_like(vx), vx), torch.zeros_like(vx), wz], dim=1)
    false = torch.zeros(n, dtype=torch.bool, device=cmd.device)

    return {"cmd": cmd, "stand": false, "spin": spin, "heading": false, "psi_star": torch.zeros(n, device=cmd.device)}


WT_SLOTS = ("forward", "walk_left", "walk_right", "spin_left", "spin_right")


def walkturn_slots(gen, n, params):
    """S2a 슬롯 번호 (n,) long: WT_SLOTS 의 위치. 한 번 뽑은 u 하나로 누적 구간에 넣는다(구간 합이 1 이어야 한다, 어긋나면 거절)."""
    total = params.wt_p_forward + 2.0 * params.wt_p_walkturn_each + 2.0 * params.wt_p_spin_each

    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"S2a 슬롯 비율의 합이 1 이 아니다: {total}")
    edges = torch.tensor([params.wt_p_forward, params.wt_p_walkturn_each, params.wt_p_walkturn_each, params.wt_p_spin_each, params.wt_p_spin_each], device=gen.device).cumsum(0)
    u = _u(gen, (n,))

    return torch.clamp(torch.searchsorted(edges, u, right=True), max=len(WT_SLOTS) - 1)


def resample_walkturn(gen, n, params):
    """S2a 명령 표집기(EX-35). 반환 형식은 `resample_start` 와 같다(spin = 제자리 회전 슬롯)."""
    slot = walkturn_slots(gen, n, params)
    fwd_vx = _u(gen, (n,), params.wt_fwd_vmin, params.wt_fwd_vmax)
    walk_vx = _u(gen, (n,), params.wt_walk_vmin, params.wt_walk_vmax)
    walk_wz = _u(gen, (n,), params.wt_wz_min, params.wt_wz_max)
    spin_wz = _u(gen, (n,), -params.wt_spin_wz, params.wt_spin_wz)
    zeros = torch.zeros(n, device=fwd_vx.device)
    walk = (slot == 1) | (slot == 2)
    spin = (slot == 3) | (slot == 4)
    vx = torch.where(slot == 0, fwd_vx, torch.where(walk, walk_vx, zeros))
    sign = torch.where(slot == 1, 1.0, -1.0)
    wz = torch.where(walk, sign * walk_wz, torch.where(spin, torch.where(slot == 3, spin_wz.abs(), -spin_wz.abs()), zeros))
    false = torch.zeros(n, dtype=torch.bool, device=vx.device)

    return {"cmd": torch.stack([vx, zeros, wz], dim=1), "stand": false, "spin": spin, "heading": false, "psi_star": torch.zeros(n, device=vx.device), "slot": slot}


BASIC_SLOTS = ("forward", "walk_left", "walk_right", "spin_left", "spin_right",
               "stand", "reverse", "side_left", "side_right")

EX39_SLOTS = (*BASIC_SLOTS, "diag_fwd_left", "diag_fwd_right", "diag_back_left", "diag_back_right")
EX39_SHARES = (0.30, 0.05, 0.05, 0.10, 0.10, 0.10, 0.12, 0.06, 0.06,
               0.015, 0.015, 0.015, 0.015)


def ex39_shares():
    if len(EX39_SLOTS) != len(EX39_SHARES) or abs(sum(EX39_SHARES) - 1.0) > 1e-12:
        raise ValueError("EX-39 slot proportions must sum to one")
    return dict(zip(EX39_SLOTS, EX39_SHARES))


def resample_ex39(gen, n, arm, yaw):
    """D55 basic-gait slots. Arm B changes only heading flags and targets."""
    if arm not in ("A", "B") or yaw is None or yaw.shape != (n,):
        raise ValueError("EX-39 needs arm A/B and current yaw for each env")
    shares = ex39_shares()
    edges = torch.tensor(tuple(shares.values()), device=gen.device, dtype=torch.float64).cumsum(0)
    slot = torch.clamp(torch.searchsorted(edges, _u(gen, (n,)).double(), right=True), max=len(EX39_SLOTS) - 1)
    zeros = torch.zeros(n, device=gen.device)
    forward = slot == 0
    walk = (slot == 1) | (slot == 2)
    spin = (slot == 3) | (slot == 4)
    stand = slot == 5
    reverse = slot == 6
    side = (slot == 7) | (slot == 8)
    diagonal = slot >= 9
    fwd_vx = _u(gen, (n,), 0.3, 1.5)
    walk_vx = _u(gen, (n,), 0.3, 0.8)
    back_vx = _u(gen, (n,), -1.0, -0.2)
    diag_vx = _u(gen, (n,), 0.3, 0.6)
    side_vy = _u(gen, (n,), 0.2, 0.6)
    diag_vy = _u(gen, (n,), 0.2, 0.5)
    walk_wz = _u(gen, (n,), 0.2, 0.5)
    spin_wz = _u(gen, (n,), 0.5, 1.5)
    vx = torch.where(forward, fwd_vx, torch.where(walk, walk_vx,
                     torch.where(reverse, back_vx, torch.where(diagonal,
                     torch.where(slot < 11, diag_vx, -diag_vx), zeros))))
    vy = torch.where(side, torch.where(slot == 7, side_vy, -side_vy),
                     torch.where(diagonal, torch.where((slot == 9) | (slot == 11), diag_vy, -diag_vy), zeros))
    wz = torch.where(walk, torch.where(slot == 1, walk_wz, -walk_wz),
                     torch.where(spin, torch.where(slot == 3, spin_wz, -spin_wz), zeros))
    heading = torch.zeros(n, dtype=torch.bool, device=gen.device)
    psi_star = zeros.clone()
    # Keep the shared command RNG stream aligned across arms when the same envs
    # resample on the same schedule. Heading changes may later change reset times.
    forward_heading_draw = _u(gen, (n,))
    spin_heading_draw = _u(gen, (n,))
    target_spin = _u(gen, (n,), -math.pi, math.pi)
    if arm == "B":
        # 15 percentage points of forward, 3 points from each spin direction.
        heading = (forward & (forward_heading_draw < 0.5)) | (spin & (spin_heading_draw < 0.3))
        psi_star = torch.where(forward & heading, yaw, torch.where(spin & heading, target_spin, zeros))
        wz = torch.where(heading, zeros, wz)
    return {"cmd": torch.stack([vx, vy, wz], dim=1), "stand": stand, "spin": spin,
            "heading": heading, "psi_star": psi_star, "slot": slot}


def basic_shares(new_share):
    """새 기술의 합을 세 묶음에 균등 배정한다. 기존 보행 몫 30 % 는 고정."""
    share = float(new_share)
    if not math.isfinite(share) or not 0.0 <= share <= 0.70:
        raise ValueError("basic_new_share must be finite and within [0, 0.70]")
    each = share / 3.0
    return (0.70 - share, 0.05, 0.05, 0.10, 0.10, each, each, each / 2.0, each / 2.0)


def resample_basic(gen, n, params):
    """기본 보행 준비판. 한 슬롯을 뽑고 그 슬롯의 속도만 소비한다."""
    shares = basic_shares(params.basic_new_share)
    edges = torch.tensor(shares, device=gen.device, dtype=torch.float64).cumsum(0)
    slot = torch.clamp(torch.searchsorted(edges, _u(gen, (n,)).double(), right=True),
                       max=len(BASIC_SLOTS) - 1)
    forward = slot == 0
    walk = (slot == 1) | (slot == 2)
    spin = (slot == 3) | (slot == 4)
    stand = slot == 5
    reverse = slot == 6
    side = (slot == 7) | (slot == 8)
    zeros = torch.zeros(n, device=gen.device)
    fwd_vx = _u(gen, (n,), 0.3, 1.5)
    walk_vx = _u(gen, (n,), 0.3, 0.8)
    back_vx = _u(gen, (n,), -0.8, -0.2)
    side_vy = _u(gen, (n,), 0.2, 0.5)
    walk_wz = _u(gen, (n,), 0.2, 0.5)
    spin_wz = _u(gen, (n,), 0.5, 1.2)
    vx = torch.where(forward, fwd_vx, torch.where(walk, walk_vx, torch.where(reverse, back_vx, zeros)))
    vy = torch.where(side, torch.where(slot == 7, side_vy, -side_vy), zeros)
    wz = torch.where(walk, torch.where(slot == 1, walk_wz, -walk_wz),
                     torch.where(spin, torch.where(slot == 3, spin_wz, -spin_wz), zeros))
    false = torch.zeros(n, dtype=torch.bool, device=gen.device)
    return {"cmd": torch.stack([vx, vy, wz], dim=1), "stand": stand, "spin": spin,
            "heading": false, "psi_star": zeros, "slot": slot}


# ---------------------------------------------------------------- 명령 시계 흩기 (EX-35)


def scatter_clock(gen, n, resample_s=4.0):
    """새 프로세스의 첫 reset 직후 env 마다 다음 명령 교체까지 남은 시간 U(0, resample_s). 모든 env 가 같은 시각에 교체되는 것을 푼다."""
    return _u(gen, (n,), 0.0, resample_s)


def scatter_episode(gen, n, max_episode_length):
    """새 프로세스의 첫 reset 직후 env 마다 에피소드 진행도(스텝) 정수 U[0, max_episode_length). rsl_rl 의 init_at_random_ep_len 과 같은 뜻(이어 가기는 그것을 끄므로 여기서 한다)."""
    return torch.clamp((_u(gen, (n,)) * max_episode_length).long(), max=max_episode_length - 1)


def scatter_receipt(time_left, resample_s=4.0, max_bin_frac=0.30, bins=None):
    """영수증: 범위 · 유한 · 1 s 구간 집중도(가장 많이 든 구간의 비율, 균등이면 1/구간 수). 어느 하나 어기면 ok False."""
    t = torch.as_tensor(time_left, dtype=torch.float32).detach().cpu()
    finite = bool(torch.isfinite(t).all())
    lo, hi = (float(t.min()), float(t.max())) if finite and t.numel() else (float("nan"), float("nan"))
    in_range = finite and lo >= 0.0 and hi <= resample_s
    bins = int(math.ceil(resample_s)) if bins is None else int(bins)
    counts = torch.histc(t.clamp(0.0, resample_s), bins=bins, min=0.0, max=float(resample_s)) if finite else torch.zeros(bins)
    frac = float(counts.max() / max(t.numel(), 1))
    return {"n": int(t.numel()), "min": lo, "max": hi, "finite": finite, "in_range": bool(in_range), "bin_counts": [int(c) for c in counts.tolist()],
            "max_bin_frac": frac, "max_bin_frac_limit": max_bin_frac, "ok": bool(in_range and frac <= max_bin_frac)}


# ---------------------------------------------------------------- 새 과제 표식 (JUDGE-SPEC v0.2 5 절)


def new_task_mask(cmd, params, eps=1.0e-6):
    """재추출된 명령이 «새 과제» 인가: 걸으며 돌기(vx > 0 이고 wz != 0). 기존 START 의 제자리 회전(vx 0 · wz != 0)과 직진(wz 0)은 새 과제가 아니다.

    START 명령 계약(`params.start_mode`)에서만 표시한다. 옛 혼합 명령(heading · 자유 wz)은 걷는 동안 도는 것이 원래 흔한 명령이라 표식 대상이 아니다(옛 커리큘럼을 바꾸지 않는다).
    """
    cmd = torch.as_tensor(cmd)
    n = cmd.shape[0]

    if params.basic_mode:
        # 새로 도입한 정지 · 후진 · 옆걸음과 걸으며 돌기를 기록한다.
        return ((cmd[:, :3].abs() <= eps).all(dim=1) | (cmd[:, 0] < -eps) |
                (cmd[:, 1].abs() > eps) | ((cmd[:, 0] > eps) & (cmd[:, 2].abs() > eps)))
    if not (params.start_mode or params.walkturn_mode):
        return torch.zeros(n, dtype=torch.bool, device=cmd.device)

    return (cmd[:, 0] > eps) & (cmd[:, 2].abs() > eps)


class NewTaskMark:
    """에피소드마다 «새 과제 명령을 받았는가» 표식 (N,) bool. 순수 torch.

    켜는 때: 명령 재추출(`on_resample`) 또는 매 스텝 바뀌는 과제가 실제로 소비된 스텝(`on_consumed`, 마지막 명령만 보고 분류하지 않는다).
    읽는 때: 지형 커리큘럼(`terrain_levels_mixed`)이 승급 · 강등을 정하기 전. 비우는 때: 에피소드 시작(`clear`) = Isaac 순서상 curriculum 이 읽은 뒤.
    """

    def __init__(self, n, device="cpu"):
        self.flag = torch.zeros(n, dtype=torch.bool, device=device)

    def clear(self, env_ids):
        self.flag[env_ids] = False

    def on_resample(self, env_ids, cmd, params):
        """재추출된 명령 cmd (m, 3) 가 새 과제인 env 를 참으로(이미 참이면 그대로: 한 번 받으면 에피소드 끝까지)."""
        env_ids = torch.as_tensor(env_ids, dtype=torch.long, device=self.flag.device)
        self.flag[env_ids] |= new_task_mask(cmd, params).to(self.flag.device)

    def on_consumed(self, mask):
        """이 스텝에 새 과제 모드가 실제로 소비된 env (N,) 를 참으로."""
        self.flag |= torch.as_tensor(mask, dtype=torch.bool, device=self.flag.device)


def world_cmd_step(yaw, vel_xy):
    """J-T10: 몸 기준 선속도 명령 (n, 2) 을 이 스텝의 실제 yaw (n,) 로 세계 좌표로 돌린 값. 합하면 세계 좌표 기대 변위(÷ step_dt 단위)다."""
    c, s = torch.cos(yaw), torch.sin(yaw)

    return torch.stack([c * vel_xy[:, 0] - s * vel_xy[:, 1], s * vel_xy[:, 0] + c * vel_xy[:, 1]], dim=1)


def apply_heading(cmd, heading, stand, psi_star, yaw, params):
    """매 스텝: heading env 의 wz 를 갱신. 정지 env 는 세 칸 0 을 지킨다 (정지가 heading 보다 우선)."""
    out = cmd.clone()
    wz = heading_wz(psi_star, yaw, params.heading_stiffness, params.wz_max)
    out[:, 2] = torch.where(heading, wz, out[:, 2])
    out[stand] = 0.0

    return out


# ---------------------------------------------------------------- 깃발


@dataclass
class FlagState:
    """깃발 env n 개의 상태. 전부 (n, ...) 텐서."""

    flags: torch.Tensor          # (n, K, 2) 세계 좌표
    n_flags: torch.Tensor        # (n,)
    idx: torch.Tensor            # (n,) 다음에 향할 깃발
    v: torch.Tensor              # (n,) 이번 재추출의 속력
    spin_wz: torch.Tensor        # (n,) 제자리 회전 wz (v < 0.3 일 때)
    hold_left: torch.Tensor      # (n,) 마지막 깃발 정지 남은 시간
    backoff_left: torch.Tensor   # (n,) 물러나기 남은 시간
    backoff_v: torch.Tensor      # (n,)
    passed: torch.Tensor         # (n,) 지난 깃발 수

    @classmethod
    def new(cls, flags, n_flags=None):
        flags = torch.as_tensor(flags, dtype=torch.float32)
        n, k = flags.shape[0], flags.shape[1]
        dev = flags.device

        return cls(flags=flags,
                   n_flags=torch.full((n,), k, device=dev) if n_flags is None
                   else torch.as_tensor(n_flags, device=dev),
                   idx=torch.zeros(n, dtype=torch.long, device=dev), v=torch.zeros(n, device=dev),
                   spin_wz=torch.zeros(n, device=dev), hold_left=torch.zeros(n, device=dev),
                   backoff_left=torch.zeros(n, device=dev), backoff_v=torch.zeros(n, device=dev),
                   passed=torch.zeros(n, dtype=torch.long, device=dev))

    def reset(self, ids, flags=None, n_flags=None):
        """에피소드가 새로 시작하는 env: 깃발 목록을 새 칸 것으로 바꾸고 「지난 깃발」 을 비운다 (14 §8)."""
        if flags is not None:
            self.flags[ids] = flags
        if n_flags is not None:
            self.n_flags[ids] = n_flags

        self.idx[ids] = 0
        self.passed[ids] = 0
        self.hold_left[ids] = 0.0
        self.backoff_left[ids] = 0.0


def flag_resample(state, ids, gen, params):
    """깃발 env 재추출: 속력 · 제자리 회전 wz · 물러나기 여부를 뽑는다 (4 s 마다)."""
    ids = torch.as_tensor(ids, dtype=torch.long)
    n = len(ids)
    dev = state.v.device
    state.v[ids] = _u(gen, (n,), 0.0, params.flag_vmax, dev)
    state.spin_wz[ids] = _u(gen, (n,), -params.flag_spin_wz, params.flag_spin_wz, dev)

    if params.backoff_prob > 0.0:
        can = state.passed[ids] >= 1
        want = _u(gen, (n,), device=dev) < params.backoff_prob
        on = can & want
        new_v = _u(gen, (n,), params.backoff_vmin, params.backoff_vmax, dev)
        state.backoff_left[ids] = torch.where(on, torch.full((n,), params.backoff_s, device=dev),
                                              state.backoff_left[ids])
        state.backoff_v[ids] = torch.where(on, new_v, state.backoff_v[ids])


def flag_step(state, pos_xy, yaw, dt, params):
    """한 제어 스텝: 깃발 진행을 갱신하고 명령 (n, 3) 을 돌려준다.

    - 0.5 m 안에 들면 다음 깃발. 마지막 깃발이면 세 칸 0 을 `flag_final_hold_s` 동안(이후도 0) 유지.
    - 물러나기 중이면 직전에 지난 깃발 쪽 단위 벡터 x backoff_v, wz 0 (몸을 돌리지 않는다).
    - v < 0.3 이면 (0, 0, spin_wz), 아니면 방향 x v 에 wz = clip(방향 각, +-1).
    깃발이 하나도 없는 env(n_flags == 0)는 세 칸 0.
    """
    n = pos_xy.shape[0]
    dev = pos_xy.device
    rows = torch.arange(n, device=dev)
    zeros = torch.zeros(n, device=dev)
    finished = state.idx >= state.n_flags

    safe_idx = torch.minimum(state.idx, torch.clamp(state.n_flags - 1, min=0))
    target = state.flags[rows, safe_idx]
    dist = torch.linalg.norm(target - pos_xy, dim=1)
    reached = (~finished) & (state.n_flags > 0) & (dist < params.flag_reach_m)
    state.idx = torch.where(reached, state.idx + 1, state.idx)
    state.passed = torch.where(reached, state.passed + 1, state.passed)
    just_finished = reached & (state.idx >= state.n_flags)
    state.hold_left = torch.where(just_finished, torch.full_like(state.hold_left, params.flag_final_hold_s),
                                  state.hold_left)
    finished = state.idx >= state.n_flags

    safe_idx = torch.minimum(state.idx, torch.clamp(state.n_flags - 1, min=0))
    target = state.flags[rows, safe_idx]
    to_target = to_body(target - pos_xy, yaw)
    norm = torch.clamp(torch.linalg.norm(to_target, dim=1), min=1.0e-9)
    unit = to_target / norm[:, None]
    angle = torch.atan2(to_target[:, 1], to_target[:, 0])

    moving = state.v >= params.flag_spin_threshold
    forward = torch.stack([unit[:, 0] * state.v, unit[:, 1] * state.v,
                           torch.clip(angle, -params.flag_wz_clip, params.flag_wz_clip)], dim=1)
    spinning = torch.stack([zeros, zeros, state.spin_wz], dim=1)
    cmd = torch.where(moving[:, None], forward, spinning)

    back = state.backoff_left > 0.0
    prev_idx = torch.clamp(state.idx - 1, min=0)
    prev = state.flags[rows, prev_idx]
    back_body = to_body(prev - pos_xy, yaw)
    back_unit = back_body / torch.clamp(torch.linalg.norm(back_body, dim=1), min=1.0e-9)[:, None]
    back_cmd = torch.stack([back_unit[:, 0] * state.backoff_v, back_unit[:, 1] * state.backoff_v, zeros], dim=1)
    use_back = back & (state.passed >= 1) & (~finished)
    cmd = torch.where(use_back[:, None], back_cmd, cmd)
    state.backoff_left = torch.where(back, torch.clamp(state.backoff_left - dt, min=0.0), state.backoff_left)

    cmd = torch.where((finished | (state.n_flags <= 0))[:, None], torch.zeros_like(cmd), cmd)
    state.hold_left = torch.where(finished, torch.clamp(state.hold_left - dt, min=0.0), state.hold_left)

    return cmd


def straight_flag_line(origin_xy, count=4, spacing=1.0, heading=0.0, first=0.5):
    """이어진 지형 칸의 직선 깃발 열 (15 §4 71 행: 칸 가운데를 지나는 직선, 1 m 간격). (count, 2).

    칸 가운데 기준 +0.5, +1.5, +2.5, +3.5 m (lead 확정 10/20): 8 m 칸 경계(+4 m)에서 0.5 m 안쪽이고 처음부터 앞을 향한다
    (예전 1~4 m 는 네 번째 깃발이 경계 위에 놓였다).
    """
    steps = first + torch.arange(count, dtype=torch.float32) * spacing
    origin = torch.as_tensor(origin_xy, dtype=torch.float32)

    return origin[None, :] + torch.stack([steps * math.cos(heading), steps * math.sin(heading)], dim=1)


# ---------------------------------------------------------------- 명령 범위 커리큘럼 (14 §4)


@dataclass
class RangeCurriculum:
    """자유 속도 지형군의 크기 상한 vmax 를 0.25 씩 올린다 (vx 1.5 까지, vy 1.0 까지). wz 는 고정."""

    vmax_x: float = 1.0
    vmax_y: float = 1.0
    step: float = 0.25
    cap_x: float = 1.5
    cap_y: float = 1.0
    gamma: float = 0.8
    history: list = field(default_factory=list)
    # 깃발 방식 속도 상한 (14 §4 표: 같은 조건 + 깃발 env 의 지형 레벨 중앙값 >= 5 에서 0.25 씩, 1.5 까지). 재개 때 같이 저장된다.
    flag_vmax: float = 1.0
    flag_cap: float = 1.5
    flag_median_level: float = 5.0

    def update_flag(self, mean_lin_ratio, mean_ang_ratio, median_level, iteration=None):
        """깃발 env 의 두 추종 보상 평균 >= gamma 이고 그 env 들의 레벨 중앙값 >= 5 이면 깃발 속도 상한을 올린다."""
        if mean_lin_ratio >= self.gamma and mean_ang_ratio >= self.gamma and median_level >= self.flag_median_level:
            before = self.flag_vmax
            self.flag_vmax = min(self.flag_vmax + self.step, self.flag_cap)

            if self.flag_vmax != before:
                self.history.append({"iteration": iteration, "flag_vmax": self.flag_vmax})

                return True

        return False

    def update(self, mean_lin_ratio, mean_ang_ratio, iteration=None):
        """두 추종 보상 에피소드 평균이 최대값의 gamma 이상이면 상한을 올린다. 올렸으면 True."""
        if mean_lin_ratio >= self.gamma and mean_ang_ratio >= self.gamma:
            before = (self.vmax_x, self.vmax_y)
            self.vmax_x = min(self.vmax_x + self.step, self.cap_x)
            self.vmax_y = min(self.vmax_y + self.step, self.cap_y)
            changed = (self.vmax_x, self.vmax_y) != before

            if changed:
                self.history.append({"iteration": iteration, "vmax_x": self.vmax_x, "vmax_y": self.vmax_y})

            return changed

        return False


# ---------------------------------------------------------------- 노출 로그 (14 §6)

DIRECTIONS = ("zero", "front", "back", "left", "right", "spin")
MODES = ("flag", "stand", "spin", "heading", "free_wz")


def direction_bin(cmd, eps=1.0e-6):
    """명령 (n, 3) 을 방향 번호로 (DIRECTIONS 순서): 0 / 앞 / 뒤 / 좌 / 우 / 제자리 회전. 선속도가 있으면 큰 성분이 이긴다."""
    vx, vy, wz = cmd[:, 0], cmd[:, 1], cmd[:, 2]
    lin = torch.hypot(vx, vy)
    out = torch.zeros(len(cmd), dtype=torch.long, device=cmd.device)
    out[(lin <= eps) & (wz.abs() > eps)] = DIRECTIONS.index("spin")
    moving = lin > eps
    x_major = vx.abs() >= vy.abs()
    out[moving & x_major & (vx > 0)] = DIRECTIONS.index("front")
    out[moving & x_major & (vx < 0)] = DIRECTIONS.index("back")
    out[moving & ~x_major & (vy > 0)] = DIRECTIONS.index("left")
    out[moving & ~x_major & (vy < 0)] = DIRECTIONS.index("right")

    return out


def mode_labels(is_flag, stand, spin, heading):
    """env 마다 현재 방식 번호 (MODES 순서). 깃발 env 는 `flag`, 아니면 정지 > 제자리 회전 > heading > 자유 wz."""
    out = torch.full((len(is_flag),), MODES.index("free_wz"), dtype=torch.long, device=is_flag.device)
    out[heading] = MODES.index("heading")
    out[spin] = MODES.index("spin")
    out[stand] = MODES.index("stand")
    out[is_flag] = MODES.index("flag")

    return out


class ExposureLog:
    """방식별 env 수 · 방향별 노출 시간(초)을 쌓는다. update 마다 `snapshot()` 으로 읽는다."""

    def __init__(self):
        self.mode_seconds = torch.zeros(len(MODES))
        self.direction_seconds = torch.zeros(len(DIRECTIONS))

    def add(self, mode_ids, cmd, dt):
        self.mode_seconds += torch.bincount(mode_ids.cpu(), minlength=len(MODES)).float() * dt
        self.direction_seconds += torch.bincount(direction_bin(cmd).cpu(), minlength=len(DIRECTIONS)).float() * dt

    def snapshot(self):
        tm = float(self.mode_seconds.sum()) or 1.0
        td = float(self.direction_seconds.sum()) or 1.0

        return {"mode_ratio": {m: float(v) / tm for m, v in zip(MODES, self.mode_seconds)},
                "direction_ratio": {d: float(v) / td for d, v in zip(DIRECTIONS, self.direction_seconds)}}
