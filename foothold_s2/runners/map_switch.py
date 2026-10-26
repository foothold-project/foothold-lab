"""EX-33 S-B: 에피소드 단위 «지도 끔» 뽑기와 켬 · 끔 집단별 기록 (순수 torch, Kit 없이 시험된다).

정의: env 마다 에피소드 시작(reset) 때 확률 p_off 로 «지도 끔» 을 뽑고 그 에피소드가 끝날 때까지 유지한다.
지도 끔 env 는 est 를 만들 때 지도 토큰을 attention 키에서 뺀다(StartPerception → IEEstimator.estimate 의 map_off).
p_off 가 0 이면 뽑지 않는다(난수를 쓰지 않아 B 와 같은 흐름).
"""

from __future__ import annotations

import torch

from foothold_s2.terrains import columns

# M-T6 끔 대상 지형(DESIGN-MAPRATIO v0.6 3.2): 새 에피소드가 놓인 칸의 지형 이름이 연속 7 종 또는 flat 이면 허용, 듬성 5 종은 불허. 레벨은 보지 않는다
ELIGIBLE_NAMES = frozenset(columns.CONTINUOUS) | {"flat"}
SPARSE_NAMES = frozenset(columns.SPARSE) - {"flat"}


def check_column_names(names) -> list[str]:
    """생성기의 열 이름 목록을 확인한다. 모르는 이름이 있으면 기동 거절(허용 여부를 정할 수 없다)."""
    names = list(names)
    unknown = sorted({n for n in names if n not in ELIGIBLE_NAMES and n not in SPARSE_NAMES})

    if unknown:
        raise ValueError(f"끔 대상 지형을 정할 수 없는 열 이름: {unknown} (허용 {sorted(ELIGIBLE_NAMES)}, 불허 {sorted(SPARSE_NAMES)})")

    return names


def eligible_map_off(terrain_types, terrain_levels, names) -> torch.Tensor:
    """(n,) bool: env 의 현재 칸(열 번호 terrain_types)이 «끔을 허용하는 지형» 인가. 지형 이름으로만 정한다. terrain_levels 는 받지만 쓰지 않는다(레벨 조건 없음)."""
    ok = torch.tensor([n in ELIGIBLE_NAMES for n in check_column_names(names)], dtype=torch.bool, device=terrain_types.device)

    return ok[terrain_types.long()]


def nearest_tile_cols(xy, origins_xy) -> torch.Tensor:
    """위치 (k, 2) -> 가장 가까운 칸 중심의 열 번호 (k,). origins_xy (rows, cols, 2) 는 칸 중심들이라 가장 가까운 중심 = 그 위치를 품은 칸."""
    rows, cols, _ = origins_xy.shape
    d = torch.cdist(xy.float(), origins_xy.reshape(rows * cols, 2).float().to(xy.device))

    return d.argmin(dim=1) % cols


class OffEligibilityStats:
    """한 update 동안의 끔 대상 지형 통계(M-T6 기록): 새로 시작한 에피소드 수 · 허용 수 · 끔 시작 수(레벨별) · 끝난 끔 에피소드 중 듬성 칸에 있던 수."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.starts = self.eligible_starts = self.off_starts = self.sparse_starts = 0
        self.off_by_level: dict[int, int] = {}
        self.off_ended = self.off_ended_on_sparse = 0

    def add_draw(self, off, reset, eligible, levels) -> None:
        reset, off, eligible, levels = reset.bool().cpu(), off.bool().cpu(), eligible.bool().cpu(), levels.long().cpu()
        self.starts += int(reset.sum())
        self.eligible_starts += int((reset & eligible).sum())
        self.sparse_starts += int((reset & ~eligible).sum())
        self.off_starts += int((reset & off).sum())

        for lv in levels[reset & off].unique().tolist():
            self.off_by_level[int(lv)] = self.off_by_level.get(int(lv), 0) + int((reset & off & (levels == lv)).sum())

    def add_ended(self, off_ended, on_sparse) -> None:
        self.off_ended += int(off_ended.bool().sum())
        self.off_ended_on_sparse += int((off_ended.bool() & on_sparse.bool()).sum())

    def take(self) -> dict | None:
        if self.starts == 0 and self.off_ended == 0:
            return None
        out = {"starts": self.starts, "eligible_starts": self.eligible_starts, "sparse_starts": self.sparse_starts, "off_starts": self.off_starts,
               "off_starts_by_level": {str(k): v for k, v in sorted(self.off_by_level.items())}, "off_ended": self.off_ended, "off_ended_on_sparse": self.off_ended_on_sparse}
        self.reset()

        return out


def make_generator(device, seed: int) -> torch.Generator:
    """전용 난수열. 전역 난수(환경 · PPO)를 건드리지 않아 p_off 를 바꿔도 다른 곳의 난수열이 같다."""
    g = torch.Generator(device=device)
    g.manual_seed(int(seed))

    return g


def draw_map_off(n: int, p_off: float, device, generator: torch.Generator | None) -> torch.Tensor:
    """(n,) bool. p_off 는 [0, 1]. 0 이면 전부 거짓(난수 안 씀), 1 이면 전부 참(난수 안 씀)."""
    if not 0.0 <= float(p_off) <= 1.0:
        raise ValueError(f"p_off 는 [0, 1]: {p_off}")
    if p_off == 0.0:
        return torch.zeros(n, dtype=torch.bool, device=device)
    if p_off == 1.0:
        return torch.ones(n, dtype=torch.bool, device=device)

    return torch.rand(n, generator=generator, device=device) < p_off


class MapSwitchRecorder:
    """한 update(rollout) 동안 켬 · 끔 집단을 따로 센다. 집단은 그 step 에 정책이 받은 map_off 로 정한다(에피소드 안에서 안 바뀐다).

    add_step(map_off, rewards, dones, ...) 를 step 마다 부른다. map_off 는 env.step 전의 값(그 step 의 행동을 만든 값).
    에피소드 보상 · 길이는 끝난 에피소드(done) 만 센다. 지형 레벨 · track 항은 매 step 의 env 평균(집단별)을 rollout 평균한다.
    """

    GROUPS = ("on", "off")

    def __init__(self, num_envs: int, device) -> None:
        self.n = num_envs
        self.device = device
        self.ep_rew = torch.zeros(num_envs, device=device)
        self.ep_len = torch.zeros(num_envs, device=device)
        self.reset_window()

    def reset_window(self) -> None:
        z = lambda: {g: 0.0 for g in self.GROUPS}  # noqa: E731
        self.steps = 0
        self.env_steps = z()
        self.ended = z()
        self.ep_rew_sum = z()
        self.ep_len_sum = z()
        self.level_sum = z()
        self.level_n = z()
        self.track_sum = {"lin": z(), "ang": z()}
        self.track_n = z()
        self.off_frac_sum = 0.0
        self.ended_timeout = z()          # 시간 제한으로 끝난 에피소드 수(extras["time_outs"])
        self.ended_other = z()            # 그 밖의 종료(낙상 · 접촉 종료 등)
        self.cause_steps = 0              # 종료 원인을 받은 step 수(0 이면 원인 기록 없음)
        self.source_steps = {"gt": 0, "recon": 0, "off": 0}   # 정답 · 복원 · 끔 env-step 수. 끔이 먼저(끔 env 는 지도를 안 쓰므로 정답 · 복원과 겹치지 않는다)
        self.source_known_steps = 0

    @torch.no_grad()
    def add_step(self, map_off: torch.Tensor, rewards: torch.Tensor, dones: torch.Tensor, levels: torch.Tensor | None = None,
                 track_lin: torch.Tensor | None = None, track_ang: torch.Tensor | None = None, time_outs: torch.Tensor | None = None, use_gt: torch.Tensor | None = None) -> None:
        off = map_off.bool()
        self.steps += 1
        self.off_frac_sum += float(off.float().mean())
        self.ep_rew += rewards
        self.ep_len += 1
        done = dones.bool()

        for g, sel in (("on", ~off), ("off", off)):
            k = int(sel.sum())
            self.env_steps[g] += k
            if levels is not None and k:
                self.level_sum[g] += float(levels[sel].float().sum())
                self.level_n[g] += k
            if track_lin is not None and track_ang is not None and k:
                self.track_sum["lin"][g] += float(track_lin[sel].sum())
                self.track_sum["ang"][g] += float(track_ang[sel].sum())
                self.track_n[g] += k
            end = sel & done
            c = int(end.sum())
            if time_outs is not None:
                to = time_outs.bool().to(end.device)
                self.ended_timeout[g] += int((end & to).sum())
                self.ended_other[g] += int((end & ~to).sum())
            if c:
                self.ended[g] += c
                self.ep_rew_sum[g] += float(self.ep_rew[end].sum())
                self.ep_len_sum[g] += float(self.ep_len[end].sum())
        if time_outs is not None:
            self.cause_steps += 1
        if use_gt is not None:
            gt = use_gt.bool().to(off.device)
            self.source_steps["off"] += int(off.sum())
            self.source_steps["gt"] += int((gt & ~off).sum())
            self.source_steps["recon"] += int((~gt & ~off).sum())
            self.source_known_steps += 1
        self.ep_rew[done] = 0.0
        self.ep_len[done] = 0.0

    def summary(self) -> dict:
        def mean(total, count):
            return total / count if count else float("nan")

        out = {"steps": self.steps, "off_frac_steps": self.off_frac_sum / max(self.steps, 1)}
        for g in self.GROUPS:
            out[g] = {"env_steps": self.env_steps[g], "episodes_ended": int(self.ended[g]),
                      "ep_reward_mean": mean(self.ep_rew_sum[g], self.ended[g]), "ep_length_mean": mean(self.ep_len_sum[g], self.ended[g]),
                      "terrain_level_mean": mean(self.level_sum[g], self.level_n[g]),
                      "track_lin_vel_per_s": mean(self.track_sum["lin"][g], self.track_n[g]), "track_ang_vel_per_s": mean(self.track_sum["ang"][g], self.track_n[g])}

        known = self.cause_steps == self.steps and self.steps > 0
        for g in self.GROUPS:
            out[g]["ended_timeout"] = int(self.ended_timeout[g]) if known else None
            out[g]["ended_terminated"] = int(self.ended_other[g]) if known else None
        src_ok = self.source_known_steps == self.steps and self.steps > 0
        out["source_steps"] = ({**self.source_steps, "total": sum(self.source_steps.values())} if src_ok else None)

        return out
