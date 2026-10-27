"""W04: 깃발 평가 (정책 · 학습 코드 무변경, 평가 쪽에서 깃발 방향을 속도 명령으로 바꾼다).

식 (설계 14 「깃발」, CARD-EVAL-FLAG-BASELINE 2 절): 다음 깃발 방향 -> 몸 기준 명령 (vx, 0, wz)
    vx = FLAG_SPEED_MPS (고정 0.6 m/s, 재현용 가정; 설계 원문의 방향 x v 가 아니라 카드 문구대로 vy = 0)
    wz = clip(wrap(깃발 방향각 - 몸 yaw), -1, 1)
    몸에서 깃발까지 xy 거리가 REACH_RADIUS_M(0.5 m) 이내면 그 깃발에 닿은 것으로 치고 다음 깃발로 넘어간다 (경계 포함).
    마지막 깃발에 닿은 뒤에는 명령 세 칸을 0 으로 둔다 (설계 14: 마지막 깃발 0.5 m 안이면 정지; 가정).
좌표는 env 원점 기준(월드 - env_origins). 저장할 때만 월드로 바꾼다.

깃발 배치:
    연속 지형: 칸 가운데(= env 원점)에서 +0.5 · 1.5 · 2.5 · 3.5 m 직선 (CONT_OFFSETS_M)
    듬성 지형: 발판 윗면 위(sparse_terrains._snap_to_support), 출발점에서 1 m 간격, 마지막은 도착 단 가운데.
              **개수(7)와 간격(1 m)은 팀장 결정 전 가정** (ASSUMED_LAYOUT_NOTE).
판정 (judge): 깃발 도달 순서 · 시각 · 마지막 깃발 도달 · 낙하(몸통 z < 0.25 m), 기존 거리 · 생존은 env_arrays 에 그대로 있다(나란히).

순수 numpy / torch 함수라 Kit 없이 시험한다 (torch 는 Tracker 에서만).
"""

from __future__ import annotations

import math

import numpy as np

FLAG_SPEED_MPS = 0.6
REACH_RADIUS_M = 0.5
WZ_CLIP = 1.0
FALL_Z_M = 0.25
CONT_OFFSETS_M = (0.5, 1.5, 2.5, 3.5)
SPARSE_SPACING_M = 1.0
SPARSE_START_X = 0.5                      # 듬성 칸 출발 x (sparse_terrains.SPAWN_XY[0])
SPARSE_START_Y = 4.0
SPARSE_GOAL_PLATFORM_X = 7.5              # 도착 단 가운데 (start_sheet.GOAL_X 7.0 ~ 칸 끝 8.0)
SPARSE_COUNT = 7                          # 1.5 ... 6.5 (6개) + 도착 단 1개
ASSUMED_LAYOUT_NOTE = "듬성 깃발 7개 · 1 m 간격 · 마지막은 도착 단 가운데(x 7.5)는 팀장 결정 전 가정(CARD-EVAL-FLAG-BASELINE 4 절)"
LAYOUT_VERSION = "w04/1"


def wrap_pi(a):
    """각도를 [-pi, pi) 로 (numpy 배열 · 스칼라, torch 텐서 모두)."""
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def continuous_flags_rel() -> np.ndarray:
    """(4, 2) env 원점 기준: 칸 가운데에서 +x 직선 4개."""
    return np.array([[x, 0.0] for x in CONT_OFFSETS_M], dtype=np.float64)


def sparse_flag_targets_x() -> list:
    """듬성 깃발의 목표 x (칸 좌표): 출발에서 1 m 간격 6개, 마지막 하나는 도착 단 가운데."""
    xs = [SPARSE_START_X + SPARSE_SPACING_M * (k + 1) for k in range(SPARSE_COUNT - 1)]

    return xs + [SPARSE_GOAL_PLATFORM_X]


def sparse_flags_rel(tile) -> np.ndarray:
    """(7, 2) env 원점(= 칸 출발 자리) 기준. tile = sparse_terrains.TileData (boxes: 칸 좌표 x0 x1 y0 y1 z0 z1).

    발판 윗면 위로 옮기는 규칙은 학습 코드와 같은 _snap_to_support (구덩이 바닥이 아닌 윗면). flat(구덩이 없음)은 칸 가운데 직선.
    """
    from foothold_s2.terrains import sparse_terrains as sp

    boxes = np.asarray(tile.boxes, dtype=np.float64)
    floor_top = float(boxes[:, 5].min())                       # 구덩이 바닥 윗면 (틀의 가운데 상자의 z1 = -depth)
    pits = floor_top < -1.0e-9
    out = []

    for fx in sparse_flag_targets_x():
        if pits:
            x, y = sp._snap_to_support(boxes, fx, SPARSE_START_Y, floor_top)
        else:
            x, y = fx, SPARSE_START_Y

        out.append((x - SPARSE_START_X, y - SPARSE_START_Y))

    return np.asarray(out, dtype=np.float64)


def continuous_env_flags(num_envs: int) -> np.ndarray:
    return np.repeat(continuous_flags_rel()[None], int(num_envs), axis=0)


def sparse_env_flags(tiles, tile_data_by_cell) -> np.ndarray:
    """tiles: [{env, kind, level, col}] (apply_sparse 기록). 같은 (level, col) 은 같은 깃발."""
    cache, rows = {}, []

    for t in sorted(tiles, key=lambda r: int(r["env"])):
        key = (int(t["level"]), int(t["col"]))

        if key not in cache:
            cache[key] = sparse_flags_rel(tile_data_by_cell[key])

        rows.append(cache[key])

    return np.stack(rows, 0)


# ---------------------------------------------------------------- 순수 함수 (torch 텐서 · numpy 모두)


def command_from_target(pos_xy, yaw, target_xy, has_target):
    """(vx, vy, wz) 각 (N,) 와 방향각. has_target False 인 env 는 세 칸 0.

    손으로 계산한 답: 몸이 원점 yaw 0, 깃발 (1, 0) -> 방향각 0 -> wz 0, vx 0.6.  깃발 (0, 1) -> 방향각 pi/2 -> wz clip 1.0.  깃발 (-1, 0) -> 방향각 -pi(= wrap) -> wz -1.0.
    """
    import torch

    d = target_xy - pos_xy
    ang = wrap_pi(torch.atan2(d[..., 1], d[..., 0]) - yaw)
    vx = torch.where(has_target, torch.full_like(ang, FLAG_SPEED_MPS), torch.zeros_like(ang))
    wz = torch.where(has_target, ang.clamp(-WZ_CLIP, WZ_CLIP), torch.zeros_like(ang))

    return vx, torch.zeros_like(vx), wz, ang


class FlagTracker:
    """env 마다 깃발 진행 상태. step(k, pos_xy, yaw, active) 는 이 틱의 명령 (N,3) 을 돌려주고 도달을 갱신한다.

    상태: idx (N,) 현재 목표 번호 (K 면 전부 닿음), reach_step (N,K) 닿은 틱 번호(-1 = 안 닿음), fall_step (N,) 몸통 z < 0.25 m 가 처음 본 틱(-1 = 없음).
    active False 인 env(이미 끝난 에피소드)는 명령 0, 상태 불변.
    """

    def __init__(self, flags_rel, device="cpu", num_steps=None, z_fall=True):
        import torch

        self.torch = torch
        self.flags = torch.as_tensor(np.asarray(flags_rel), dtype=torch.float32, device=device)           # (N,K,2)
        self.N, self.K = int(self.flags.shape[0]), int(self.flags.shape[1])
        self.device = device
        self.idx = torch.zeros(self.N, dtype=torch.long, device=device)
        self.reach_step = torch.full((self.N, self.K), -1, dtype=torch.long, device=device)
        self.fall_step = torch.full((self.N,), -1, dtype=torch.long, device=device)
        self.fall_kind = torch.zeros(self.N, dtype=torch.int8, device=device)               # 0 없음, 1 몸통 z < 0.25 m, 2 종료 조건(넘어짐)
        self.z_fall = bool(z_fall)                                                          # 몸통 z 기준은 원점이 평평한 듬성 칸에서만 믿는다(연속 지형은 내리막에서 z < 0.25 가 서 있는 채로 나온다: 예행 8 env 중 5)
        self.rows = torch.arange(self.N, device=device)
        self.num_steps = num_steps
        self.target_series = None if num_steps is None else torch.zeros(num_steps, self.N, dtype=torch.long, device=device)

    def new_episode(self, mask):
        """mask (N,) bool 인 env 의 진행을 처음으로 (기록기: 넘어져 reset 된 뒤 새 판)."""
        m = mask.bool()
        self.idx[m] = 0
        self.reach_step[m] = -1
        self.fall_step[m] = -1
        self.fall_kind[m] = 0

    def _advance(self, k, pos_xy, active):
        for _ in range(self.K):
            has = self.idx < self.K
            tgt = self.flags[self.rows, self.idx.clamp(max=self.K - 1)]
            dist = (tgt - pos_xy).norm(dim=-1)
            hit = has & active & (dist <= REACH_RADIUS_M)

            if not bool(hit.any()):
                break

            self.reach_step[self.rows[hit], self.idx[hit]] = k
            self.idx = self.idx + hit.long()

    def step(self, k, pos_xy, yaw, active=None):
        torch = self.torch
        act = torch.ones(self.N, dtype=torch.bool, device=self.device) if active is None else active.bool()
        self._advance(k, pos_xy, act)
        has = (self.idx < self.K) & act
        tgt = self.flags[self.rows, self.idx.clamp(max=self.K - 1)]
        vx, vy, wz, _ang = command_from_target(pos_xy, yaw, tgt, has)

        if self.target_series is not None and k < self.target_series.shape[0]:
            self.target_series[k] = self.idx

        return torch.stack([vx, vy, wz], dim=-1)

    def note_fall(self, k, z_rel, active):
        """몸통 높이(env 원점 기준) z < 0.25 m 가 처음인 틱을 기록 (active 일 때만, z_fall 이 켜졌을 때만)."""
        if not self.z_fall:
            return

        new = active.bool() & (z_rel < FALL_Z_M) & (self.fall_step < 0)
        self.fall_step[new] = k
        self.fall_kind[new] = 1

    def note_done(self, k, dones, active):
        """정책 종료 조건(몸통 접촉 등 넘어짐)이 처음 걸린 틱을 기록 (active 일 때만). 낙하가 이미 z 로 잡혔으면 그대로."""
        new = active.bool() & dones.bool() & (self.fall_step < 0)
        self.fall_step[new] = k
        self.fall_kind[new] = 2


def gauges(pos_xy, yaw, flag_xy):
    """계기판 값: (다음 깃발까지 거리 m, 방향 오차 도). 몸 yaw 기준, 깃발이 왼쪽이면 +.

    손으로 계산한 답: 몸 (0,0) yaw 0, 깃발 (3,4) -> 거리 5.0 m, 방향 오차 atan2(4,3)=53.13 도.
    """
    d = np.asarray(flag_xy, dtype=np.float64) - np.asarray(pos_xy, dtype=np.float64)
    dist = float(np.hypot(d[0], d[1]))
    ang = float(wrap_pi(math.atan2(d[1], d[0]) - float(yaw)))

    return dist, math.degrees(ang)


def judge(reach_step, fall_step, alive_steps, steps, dt):
    """env 별 깃발 판정 (numpy). reach_step (N,K) 틱 번호 또는 -1, fall_step (N,) 또는 -1, alive_steps (N,) 종료 조건 없이 산 틱 수, steps 총 틱 수.

    order_ok: 닿은 깃발이 0..n-1 번 연속이고 틱 번호가 줄지 않는다 (추적기 설계상 항상 참이어야 하는 자기검사).
    last_reached: 마지막 깃발에 닿음. fell: 몸통 z < 0.25 m 를 본 적 있음. fell_before_last: 마지막 깃발 도달 전에 낙하(마지막에 닿지 못하고 낙하 포함).
    """
    r = np.asarray(reach_step, dtype=np.int64)
    n_env, K = r.shape
    reached = r >= 0
    n = reached.sum(1)
    prefix = np.arange(K)[None, :] < n[:, None]
    order_ok = np.array_equal(reached, prefix) and all(bool(np.all(np.diff(r[i, : n[i]]) >= 0)) for i in range(n_env))
    last = reached[:, -1]
    fs = np.asarray(fall_step, dtype=np.int64)
    fell = fs >= 0
    t_reach = np.where(reached, r * float(dt), np.nan)
    last_t = np.where(last, r[:, -1] * float(dt), np.nan)
    fell_before_last = fell & (~last | (fs < np.where(last, r[:, -1], 1 << 60)))

    return {"flag_reached_n": n.astype(np.int32), "flag_last_reached": last, "flag_reach_time_s": t_reach.astype(np.float32),
            "flag_last_reach_time_s": last_t.astype(np.float32), "flag_fall": fell, "flag_fall_step": fs.astype(np.int32),
            "flag_fall_time_s": np.where(fell, fs * float(dt), np.nan).astype(np.float32), "flag_fell_before_last": fell_before_last,
            "flag_order_ok": np.array(bool(order_ok)), "flag_count": np.array(K, dtype=np.int32)}
