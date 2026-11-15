"""행동 포화 기록 (SONNET-X11 X5): raw 행동 a 와 실제로 env 에 들어간 clip(a) 를 따로 잰다. Kit 없이 시험된다.

iteration 마다 `add(raw_a, dones, probe)` 를 스텝마다 부르고 끝에 `summary()` 로 집계한다.
- raw · 실행(clip 후) |a| 의 p50 · p99 · p99.9 · max (원소 단위)
- 원소 포화율: |raw| > clip 인 원소 비율
- 한 관절이라도 포화한 env-step 비율
- 관절별 연속 포화 길이: 관절마다, 한 env 에서 연속으로 포화한 스텝 수의 최댓값(iteration 사이에도 이어 세고 env 가 끝나면 0)
- probe(실제 PD target · 토크): target 이 관절 한계 밖인 비율, 토크가 한계로 잘린 비율 (Kit 객체에서만, 없으면 None)
"""

from __future__ import annotations

import torch

MAX_QUANTILE_ELEMS = 4_000_000          # torch.quantile 입력 상한(16M) 아래로 자른다. 자르는 방법: 균일 간격 부분 추출


def _quantiles(x: torch.Tensor, qs=(0.5, 0.99, 0.999)):
    flat = x.flatten().float()

    if flat.numel() > MAX_QUANTILE_ELEMS:
        flat = flat[:: (flat.numel() + MAX_QUANTILE_ELEMS - 1) // MAX_QUANTILE_ELEMS]

    return [float(torch.quantile(flat, q)) for q in qs]


def phys_probe(env):
    """실제 PD target 이 관절 한계 밖인 비율과 토크가 한계로 잘린 비율. 속성이 없으면 해당 값은 None. (env 는 ManagerBasedRLEnv)"""
    out = {"target_out_of_limit_frac": None, "torque_clipped_frac": None}

    try:
        data = env.scene["robot"].data
    except Exception:                                                      # noqa: BLE001
        return out

    target, limits = getattr(data, "joint_pos_target", None), getattr(data, "joint_pos_limits", None)

    if target is not None and limits is not None:
        out["target_out_of_limit_frac"] = float(((target < limits[..., 0]) | (target > limits[..., 1])).float().mean())

    computed, applied = getattr(data, "computed_torque", None), getattr(data, "applied_torque", None)

    if computed is not None and applied is not None:
        out["torque_clipped_frac"] = float(((computed.abs() - applied.abs()) > 1e-6).float().mean())

    return out


class ActionStats:
    def __init__(self, clip: float, num_envs: int, num_joints: int = 12, device="cpu"):
        self.clip = float(clip)
        self.run = torch.zeros(num_envs, num_joints, dtype=torch.long, device=device)      # 연속 포화 길이(env 별 · 관절별)
        self.reset_window()

    def reset_window(self):
        self.raw, self.exe = [], []
        self.any_sat_steps = 0
        self.steps = 0
        self.max_run = torch.zeros(self.run.shape[1], dtype=torch.long, device=self.run.device)
        self.sat_elems = 0
        self.total_elems = 0
        self.probes = {"target_out_of_limit_frac": [], "torque_clipped_frac": []}

    def add(self, raw_a: torch.Tensor, dones: torch.Tensor | None = None, probe: dict | None = None):
        sat = raw_a.abs() > self.clip
        self.raw.append(raw_a.abs().detach().float().cpu())
        self.exe.append(raw_a.clamp(-self.clip, self.clip).abs().detach().float().cpu())
        self.sat_elems += int(sat.sum())
        self.total_elems += sat.numel()
        self.any_sat_steps += int(sat.any(dim=1).sum())
        self.steps += sat.shape[0]
        self.run = torch.where(sat, self.run + 1, torch.zeros_like(self.run))
        self.max_run = torch.maximum(self.max_run, self.run.max(dim=0).values)

        if dones is not None:
            self.run[dones.bool()] = 0

        for k, v in (probe or {}).items():
            if v is not None:
                self.probes[k].append(float(v))

    def summary(self) -> dict:
        raw, exe = torch.stack(self.raw), torch.stack(self.exe)
        out = {"raw_abs_p50_p99_p999": _quantiles(raw), "raw_abs_max": float(raw.max()),
               "exec_abs_p50_p99_p999": _quantiles(exe), "exec_abs_max": float(exe.max()),
               "element_saturation_rate": self.sat_elems / max(self.total_elems, 1),
               "any_joint_saturated_env_step_frac": self.any_sat_steps / max(self.steps, 1),
               "max_consecutive_saturation_steps_by_joint": [int(x) for x in self.max_run]}

        for k, v in self.probes.items():
            out[k] = (sum(v) / len(v)) if v else None

        self.reset_window()

        return out
