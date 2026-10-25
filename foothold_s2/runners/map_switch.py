"""EX-33 S-B: 에피소드 단위 «지도 끔» 뽑기와 켬 · 끔 집단별 기록 (순수 torch, Kit 없이 시험된다).

정의: env 마다 에피소드 시작(reset) 때 확률 p_off 로 «지도 끔» 을 뽑고 그 에피소드가 끝날 때까지 유지한다.
지도 끔 env 는 est 를 만들 때 지도 토큰을 attention 키에서 뺀다(StartPerception → IEEstimator.estimate 의 map_off).
p_off 가 0 이면 뽑지 않는다(난수를 쓰지 않아 B 와 같은 흐름).
"""

from __future__ import annotations

import torch


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

    @torch.no_grad()
    def add_step(self, map_off: torch.Tensor, rewards: torch.Tensor, dones: torch.Tensor, levels: torch.Tensor | None = None,
                 track_lin: torch.Tensor | None = None, track_ang: torch.Tensor | None = None) -> None:
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
            if c:
                self.ended[g] += c
                self.ep_rew_sum[g] += float(self.ep_rew[end].sum())
                self.ep_len_sum[g] += float(self.ep_len[end].sum())
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

        return out
