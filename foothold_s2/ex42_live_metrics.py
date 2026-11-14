"""Per-update EX-42 skill evidence. No Isaac imports and no training decisions.

Counts are accumulated on each rank, reduced once per update, and only rank 0
writes the combined row. The velocity is the post-physics body velocity; reset
rows are excluded from tracking and counted separately for survival.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import torch

from foothold_s2.commands.mixed_core import EX39_SLOTS

MODES = ("gt", "pred", "off")
SKILLS = ("slow_forward", "side_left", "side_right")
FIELDS = ("samples", "ratio_sum", "stalled", "reward_sum", "reward_samples")
SLOW_SPEED_BANDS = (("0.1-0.15", 0.1, 0.15), ("0.15-0.2", 0.15, 0.2),
                    ("0.2-0.3", 0.2, 0.3))
SLOT_INDEX = {name: i for i, name in enumerate(EX39_SLOTS)}
SLOW_SLOTS = ("forward", "reverse", "side_left", "side_right", "diag_fwd_left", "diag_fwd_right",
              "diag_back_left", "diag_back_right")


def _finite(values):
    return bool(torch.isfinite(values).all())


def narrow_support_mask(table, contract, *, device="cpu"):
    """Use the measured mesh contract's push-off kinds, not a whole family label."""
    if not isinstance(table, list) or not table or not isinstance(contract, dict):
        raise ValueError("EX-42 live monitor needs the measured column table and push gate")
    columns = contract.get("push_off_columns")
    if (not isinstance(columns, list) or any(type(c) is not int or not 0 <= c < len(table) for c in columns)
            or len(set(columns)) != len(columns)):
        raise ValueError("EX-42 live monitor narrow-support columns invalid")
    selected = set(columns)
    return torch.tensor([c in selected for c in range(len(table))], device=device, dtype=torch.bool)


def decline_signal(peak, now, threshold):
    """A signal only when both map-on modes drop beyond the pinned amount."""
    return all(peak.get(mode) is not None and now.get(mode) is not None
               and peak[mode] - now[mode] > threshold for mode in ("gt", "pred"))


def send_orca_alert(run_id, iteration, alerts, evidence_path):
    """Best-effort durable lead Run inbox notification; a failed send stays in the local alert record."""
    if not isinstance(run_id, str) or re.fullmatch(r"run_[0-9a-f]+", run_id) is None:
        raise ValueError("EX-42 live alert needs an Orca Run id")
    executable = shutil.which("orca-ide")
    if not executable:
        return {"delivered": False, "reason": "orca-ide unavailable"}
    now = datetime.now().astimezone().strftime("%H:%M")
    label = ", ".join(item["signal"] for item in alerts)
    cmd = [executable, "orchestration", "send", "--run", run_id, "--to", f"run:{run_id}",
           "--type", "status", "--subject", f"({now}) [scripter-lx] EX-42 학습 경보 m{iteration}",
           "--body", f"({now}) {label}. 원자료: {evidence_path}", "--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        payload = data.get("result") if isinstance(data, dict) else None
        message_id = payload.get("messageId") if isinstance(payload, dict) else None
        return {"delivered": result.returncode == 0 and isinstance(data, dict) and data.get("ok") is True
                and isinstance(message_id, str) and bool(message_id),
                "message_id": message_id, "returncode": result.returncode}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return {"delivered": False, "reason": f"{type(exc).__name__}: {exc}"}


class LiveMetrics:
    def __init__(self, log_dir, *, rank=0, world_size=1, stage_id="E1", slow_min=0.1, slow_max=0.3,
                 slow_sigma=0.5, slow_weight=0.0, stall_mps=0.05, moving_updates=20, decline_from_peak=None,
                 off_survival_updates=50, off_survival_drop=None, initial=None, alert_run_id=None,
                 plan_sha256=None, include_heading=False, step_dt=None, noise_envs=None, noise_sigma_scale=None):
        if (type(moving_updates) is not int or moving_updates < 1
                or type(off_survival_updates) is not int or off_survival_updates < 1
                or (decline_from_peak is not None and not 0 < decline_from_peak < 1)
                or (off_survival_drop is not None and not 0 < off_survival_drop < 1)):
            raise ValueError("EX-42 live monitor plan thresholds invalid")
        self.log_dir = Path(log_dir)
        self.rank, self.world_size, self.stage_id = rank, world_size, stage_id
        self.plan_sha256 = plan_sha256
        self.slow_min, self.slow_max, self.slow_sigma = slow_min, slow_max, slow_sigma
        self.slow_weight = slow_weight
        self.include_heading = bool(include_heading)
        self.step_dt = None if step_dt is None else float(step_dt)
        # Record only: envs that roll out with the small action noise (bool [num_envs]), tracked apart from the rest.
        self.noise_envs = None if noise_envs is None else torch.as_tensor(noise_envs, dtype=torch.bool)
        self.noise_sigma_scale = noise_sigma_scale
        if self.step_dt is not None and (not math.isfinite(self.step_dt) or self.step_dt <= 0):
            raise ValueError("EX-42 stand start needs a finite positive step_dt")
        self._start_active = None  # per-env trials span PPO updates
        self.stall_mps = stall_mps
        self.alert_run_id = alert_run_id
        self.moving_updates = moving_updates
        self.decline_from_peak = decline_from_peak
        self.off_survival_updates = off_survival_updates
        self.off_survival_drop = off_survival_drop
        self.history = deque(maxlen=moving_updates)
        self.slow_history = deque(maxlen=moving_updates)
        self.off_block = []
        self.previous_off_block = None
        self.last_failed_alert_iteration = None
        self.high = {skill: None for skill in SKILLS}
        self.stage = dict(initial or {"slow_forward": "learning", "side_left": "learning", "side_right": "learning"})
        if set(self.stage) != set(SKILLS) or not set(self.stage.values()) <= {"learning", "consolidating", "solid", "maintenance"}:
            raise ValueError("EX-42 live monitor initial stages invalid")
        self._restore()
        self.iteration = None

    def _restore(self):
        path = self.log_dir / "ex42_live_metrics.jsonl"
        if not path.is_file():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("format") != "ex42-live-metrics/1" or row.get("stage_id") != self.stage_id:
                raise ValueError("EX-42 live metric history schema or stage differs")
            if self.plan_sha256 is not None and row.get("plan_sha256") != self.plan_sha256:
                raise ValueError("EX-42 live metric history belongs to another plan")
            self.history.append(row["skills"])
            self.slow_history.append(row["slow_track_slots"])
            self.high = row["monitor"]["high"]
            self.stage = row["monitor"]["stage"]
            delivery = row["monitor"].get("delivery")
            if isinstance(delivery, dict) and delivery.get("attempted") is True:
                self.last_failed_alert_iteration = None if delivery.get("delivered") else row["iteration"]
            if row["iteration"] % self.off_survival_updates == 0:
                self.previous_off_block = row.get("off_50_block")
                self.off_block = []
            else:
                self.off_block.append(row["survival"]["off"])

    def begin(self, iteration, *, device):
        if self.iteration is not None:
            raise RuntimeError("EX-42 live metrics previous update was not completed")
        self.iteration = int(iteration)
        self.values = torch.zeros((3, 3, len(FIELDS)), dtype=torch.float64, device=device)
        self.forward_bands = torch.zeros((3, len(SLOW_SPEED_BANDS), 3), dtype=torch.float64, device=device)
        # total, active, value, heading total, heading active
        self.slow_slots = torch.zeros((3, len(EX39_SLOTS), 5), dtype=torch.float64, device=device)
        self.survival = torch.zeros((3, 3), dtype=torch.float64, device=device)  # steps, resets, falls
        self.survival_family = torch.zeros((3, 2, 3), dtype=torch.float64, device=device)  # mode, continuous/sparse, same
        self.start_counts = torch.zeros((3, 4), dtype=torch.float64, device=device)  # starts, forward, not forward, censored
        self.invalid = torch.zeros((), dtype=torch.float64, device=device)
        self.noise_groups = torch.zeros((2, 3), dtype=torch.float64, device=device)  # noisy / rest: samples, ratio, stalled

    def _record_stand_start(self, cmd, vel, slot, flag, mode, done, finite, pre_speed, reset):
        if self.step_dt is None:
            raise ValueError("EX-42 stand start needs the environment step_dt")
        n = len(done)
        if pre_speed.shape != done.shape or reset.shape != done.shape or not torch.isfinite(pre_speed).all():
            raise ValueError("EX-42 stand start pre-step evidence shape or value invalid")
        if self._start_active is None:
            self._start_active = torch.zeros(n, dtype=torch.bool, device=done.device)
            self._start_age = torch.zeros(n, dtype=torch.long, device=done.device)
            self._start_mode = torch.zeros(n, dtype=torch.long, device=done.device)
            self._start_prev_stop = torch.zeros(n, dtype=torch.bool, device=done.device)
            self._start_prev_done = torch.zeros(n, dtype=torch.bool, device=done.device)
        elif self._start_active.shape != done.shape:
            raise ValueError("EX-42 stand start environment count changed")
        # A trial starts at the first slow-forward command after a stand command or reset.
        # Forward means post-physics body vx exceeds the same 0.05 m/s stillness threshold.
        slow_forward = (finite & ~flag & (slot == SLOT_INDEX["forward"])
                        & (cmd[:, 0] >= .1) & (cmd[:, 0] < .15) & (cmd[:, 1].abs() < 1e-6))
        new = (slow_forward & (pre_speed < .05) & (reset.bool() | self._start_prev_done | self._start_prev_stop)
               & ~self._start_active & ~done)
        self._start_mode[new] = mode[new]
        self._start_age[new] = 0
        self._start_active[new] = True
        self.start_counts[:, 0] += torch.bincount(mode[new], minlength=3)
        old_reset = reset.bool() & ~new
        changed = self._start_active & (~slow_forward | (mode != self._start_mode)) & ~done & ~old_reset
        forward = self._start_active & ~done & ~old_reset & ~changed & (vel[:, 0] > .05)
        elapsed = self._start_age + 1
        not_forward = self._start_active & ~forward & ~changed & (done | old_reset | (elapsed >= math.ceil(2.0 / self.step_dt)))
        for column, mask in ((1, forward), (2, not_forward), (3, changed)):
            self.start_counts[:, column] += torch.bincount(self._start_mode[mask], minlength=3)
        self._start_active[forward | not_forward | changed] = False
        self._start_age[self._start_active] = elapsed[self._start_active]
        self._start_prev_stop = (cmd.abs().amax(dim=1) < 1e-6) & finite
        self._start_prev_done = done.clone()

    def add(self, cmd, vel, slots, heading, flag, gt, off, done, *, time_out=None, sparse=None,
            pre_speed=None, reset=None):
        if self.iteration is None:
            raise RuntimeError("EX-42 live metrics update not started")
        cmd, vel = cmd.detach(), vel.detach()
        if cmd.shape != vel.shape or cmd.ndim != 2 or cmd.shape[1] < 3:
            raise ValueError("EX-42 live metric command and velocity shape mismatch")
        finite = torch.isfinite(cmd).all(dim=1) & torch.isfinite(vel).all(dim=1)
        cmd = torch.where(finite[:, None], cmd, torch.zeros_like(cmd))
        vel = torch.where(finite[:, None], vel, torch.zeros_like(vel))
        done = done.bool()
        time_out = torch.zeros_like(done) if time_out is None else time_out.bool()
        sparse = torch.zeros_like(done) if sparse is None else sparse.bool()
        if time_out.shape != done.shape or sparse.shape != done.shape:
            raise ValueError("EX-42 live metric timeout or terrain family shape differs")
        self.invalid += (time_out & ~done).sum()
        falls = done & ~time_out
        self.invalid += (~finite & ~done).sum()
        mode = torch.where(off.bool(), 2, torch.where(gt.bool(), 0, 1))
        if (pre_speed is None) != (reset is None):
            raise ValueError("EX-42 stand start needs both pre_speed and reset")
        if pre_speed is not None:
            self._record_stand_start(cmd, vel, slots.long(), flag.bool(), mode, done, finite,
                                     pre_speed.detach(), reset.detach())
        active = ~done & finite
        slot = slots.long()
        valid_slot = (slot >= 0) & (slot < len(EX39_SLOTS)) & ~flag.bool()
        slot = slot.clamp(0, len(EX39_SLOTS) - 1)
        slot_index = mode * len(EX39_SLOTS) + slot
        speed = torch.linalg.vector_norm(cmd[:, :2], dim=-1)
        straight = (cmd[:, 2].abs() < 1e-6) | (heading.bool() & self.include_heading)
        slow = ((speed >= self.slow_min) & (speed < self.slow_max) & straight
                & (~heading.bool() | self.include_heading) & valid_slot & finite)
        slow_error = torch.linalg.vector_norm(vel[:, :2] - cmd[:, :2], dim=-1)
        slow_value = torch.exp(-((slow_error / speed.clamp_min(self.slow_min)) / self.slow_sigma) ** 2)
        self.survival[:, 0] += torch.bincount(mode, minlength=3).to(torch.float64)
        self.survival[:, 1] += torch.bincount(mode[done], minlength=3).to(torch.float64)
        self.survival[:, 2] += torch.bincount(mode[falls], minlength=3).to(torch.float64)
        family_index = mode * 2 + sparse.long()
        self.survival_family[:, :, 0] += torch.bincount(family_index, minlength=6).reshape(3, 2)
        self.survival_family[:, :, 1] += torch.bincount(family_index[done], minlength=6).reshape(3, 2)
        self.survival_family[:, :, 2] += torch.bincount(family_index[falls], minlength=6).reshape(3, 2)
        shape = (3, len(EX39_SLOTS))
        self.slow_slots[:, :, 0] += torch.bincount(slot_index[valid_slot], minlength=39).reshape(shape)
        self.slow_slots[:, :, 1] += torch.bincount(slot_index[slow], minlength=39).reshape(shape)
        self.slow_slots[:, :, 2] += torch.bincount(
            slot_index[slow & active], weights=slow_value[slow & active].double(), minlength=39).reshape(shape)
        self.slow_slots[:, :, 3] += torch.bincount(
            slot_index[valid_slot & heading.bool()], minlength=39).reshape(shape)
        self.slow_slots[:, :, 4] += torch.bincount(
            slot_index[slow & heading.bool()], minlength=39).reshape(shape)
        stall = torch.linalg.vector_norm(vel[:, :2], dim=-1) < self.stall_mps
        for k, name in enumerate(SKILLS):
            if name == "slow_forward":
                chosen, target, actual = active & slow & (slot == SLOT_INDEX["forward"]), cmd[:, 0], vel[:, 0]
            else:
                chosen = (active & valid_slot & (~heading.bool() | self.include_heading) & (slot == SLOT_INDEX[name])
                          & (cmd[:, 1].abs() >= self.slow_min))
                target, actual = cmd[:, 1], vel[:, 1]
            safe_target = torch.where(target.abs() >= self.slow_min, target, torch.ones_like(target))
            index = mode[chosen] * len(SKILLS) + k
            ratio = (actual / safe_target)[chosen].double()
            self.values[:, :, 0].reshape(-1).scatter_add_(0, index, torch.ones_like(ratio))
            self.values[:, :, 1].reshape(-1).scatter_add_(0, index, ratio)
            self.values[:, :, 2].reshape(-1).scatter_add_(0, index, stall[chosen].double())
            if name == "slow_forward" and self.noise_envs is not None:
                if self.noise_envs.numel() != len(chosen):
                    raise ValueError("EX-42 small-noise env mask differs from the environment count")
                noisy = self.noise_envs.to(chosen.device)
                for group, member in enumerate((noisy, ~noisy)):
                    pick = chosen & member
                    self.noise_groups[group, 0] += pick.sum()
                    self.noise_groups[group, 1] += (actual / safe_target)[pick].double().sum()
                    self.noise_groups[group, 2] += stall[pick].double().sum()
            if name == "slow_forward":
                for band, (_, low, high) in enumerate(SLOW_SPEED_BANDS):
                    in_band = chosen & (target >= low) & (target < high)
                    band_index = mode[in_band] * len(SLOW_SPEED_BANDS) + band
                    band_ratio = (actual / safe_target)[in_band].double()
                    self.forward_bands[:, :, 0].reshape(-1).scatter_add_(
                        0, band_index, torch.ones_like(band_ratio))
                    self.forward_bands[:, :, 1].reshape(-1).scatter_add_(0, band_index, band_ratio)
                    self.forward_bands[:, :, 2].reshape(-1).scatter_add_(0, band_index, stall[in_band].double())
            reward_chosen = chosen & slow
            reward_index = mode[reward_chosen] * len(SKILLS) + k
            self.values[:, :, 3].reshape(-1).scatter_add_(0, reward_index, slow_value[reward_chosen].double())
            self.values[:, :, 4].reshape(-1).scatter_add_(0, reward_index,
                                                           torch.ones_like(slow_value[reward_chosen], dtype=torch.float64))

    def end(self):
        if self.iteration is None:
            raise RuntimeError("EX-42 live metrics update not started")
        local_slots = self.slow_slots.detach().cpu().tolist()
        local_bands = self.forward_bands.detach().cpu().tolist()
        local_survival = self.survival.detach().cpu().tolist()
        local_family = self.survival_family.detach().cpu().tolist()
        local_starts = self.start_counts.detach().cpu().tolist()
        pending = (torch.bincount(self._start_mode[self._start_active], minlength=3).to(torch.float64)
                   if self._start_active is not None else torch.zeros(3, dtype=torch.float64, device=self.start_counts.device))
        local_pending = pending.detach().cpu().tolist()
        if self.world_size > 1:
            import torch.distributed as dist
            if not dist.is_initialized() or dist.get_world_size() != self.world_size:
                raise RuntimeError("EX-42 live metrics all ranks must participate")
            for tensor in (self.values, self.forward_bands, self.slow_slots, self.survival,
                           self.survival_family, self.start_counts, pending, self.invalid, self.noise_groups):
                dist.all_reduce(tensor, op=dist.ReduceOp.SUM)
            rank_rows = [None] * self.world_size
            dist.all_gather_object(rank_rows, {"rank": self.rank, "slow_forward_bands": local_bands,
                                               "slow_track_slots": local_slots,
                                               "survival": local_survival, "survival_by_family": local_family,
                                               "stand_start_counts": local_starts, "stand_start_pending": local_pending})
        else:
            rank_rows = [{"rank": self.rank, "slow_forward_bands": local_bands,
                          "slow_track_slots": local_slots, "survival": local_survival,
                          "survival_by_family": local_family,
                          "stand_start_counts": local_starts, "stand_start_pending": local_pending}]
        it = self.iteration
        self.iteration = None
        if float(self.invalid) != 0:
            raise ValueError("EX-42 live metric nonfinite active velocity or command")
        if self.rank != 0:
            return None
        rows = {}
        speed_bands = {}
        for m, mode in enumerate(MODES):
            rows[mode] = {}
            speed_bands[mode] = {}
            for b, (label, _, _) in enumerate(SLOW_SPEED_BANDS):
                n, ratio, stalled = self.forward_bands[m, b].tolist()
                speed_bands[mode][label] = {"samples": int(n),
                                            "tracking_ratio": ratio / n if n else None,
                                            "stall_fraction": stalled / n if n else None}
            for k, name in enumerate(SKILLS):
                n, ratio, stalled, reward, reward_n = self.values[m, k].tolist()
                rows[mode][name] = {"samples": int(n), "tracking_ratio": ratio / n if n else None,
                                    "stall_fraction": stalled / n if n else None,
                                    "slow_track_value_mean": reward / reward_n if reward_n else None}
        self.history.append(rows)
        moving = {}
        for mode in MODES:
            moving[mode] = {}
            for skill in SKILLS:
                series = [r[mode][skill] for r in self.history]
                weight = sum(v["samples"] for v in series)
                moving[mode][skill] = {"updates": len(series), "samples": weight,
                                       "tracking_ratio": (sum(v["tracking_ratio"] * v["samples"] for v in series if v["samples"]) / weight
                                                          if weight else None),
                                       "stall_fraction": (sum(v["stall_fraction"] * v["samples"] for v in series if v["samples"]) / weight
                                                          if weight else None)}
        alerts = []
        for skill in SKILLS:
            gt = moving["gt"][skill]["tracking_ratio"]
            pred = moving["pred"][skill]["tracking_ratio"]
            if gt is None or pred is None:
                continue
            peak = self.high.get(skill)
            if (self.decline_from_peak is not None and peak is not None
                    and decline_signal(peak, {"gt": gt, "pred": pred}, self.decline_from_peak)):
                if self.stage.get(skill) != "learning":
                    alerts.append({"skill": skill, "signal": "demote_to_learning", "peak": peak,
                                   "now": {"gt": gt, "pred": pred}})
                    self.stage[skill] = "learning"
            if peak is None or (gt > peak["gt"] and pred > peak["pred"]):
                self.high[skill] = {"gt": gt, "pred": pred}
        slot_rows = {}
        for m, mode in enumerate(MODES):
            slot_rows[mode] = {}
            for i, name in enumerate(EX39_SLOTS):
                total, count, value, heading_total, heading_count = self.slow_slots[m, i].tolist()
                slot_rows[mode][name] = {"env_steps": int(total), "active_env_steps": int(count),
                                         "active_fraction": count / total if total else None,
                                         "heading_env_steps": int(heading_total),
                                         "heading_active_env_steps": int(heading_count),
                                         "free_active_env_steps": int(count - heading_count),
                                         "active_value_mean": value / count if count else None,
                                         "weighted_reward_rate_mean": self.slow_weight * value / count if count else None}
        self.slow_history.append(slot_rows)
        slow_moving = {}
        for mode in MODES:
            slow_moving[mode] = {}
            for name in EX39_SLOTS:
                total = sum(item[mode][name]["env_steps"] for item in self.slow_history)
                count = sum(item[mode][name]["active_env_steps"] for item in self.slow_history)
                slow_moving[mode][name] = {"env_steps": total, "active_env_steps": count,
                                           "active_fraction": count / total if total else None}
        steps = self.survival.tolist()
        survival = {mode: {"env_steps": int(steps[m][0]), "resets": int(steps[m][1]),
                           "falls": int(steps[m][2]), "time_outs": int(steps[m][1] - steps[m][2]),
                           "survival_fraction": (1 - steps[m][2] / steps[m][0] if steps[m][0] else None)}
                    for m, mode in enumerate(MODES)}
        by_family = {}
        family_values = self.survival_family.tolist()
        for m, mode in enumerate(MODES):
            by_family[mode] = {}
            for f, family in enumerate(("continuous", "sparse")):
                total, resets, falls = family_values[m][f]
                by_family[mode][family] = {"env_steps": int(total), "resets": int(resets), "falls": int(falls),
                                           "time_outs": int(resets - falls),
                                           "survival_fraction": 1 - falls / total if total else None}
        stand_start = {}
        for m, mode in enumerate(MODES):
            starts, forward, not_forward, censored = (int(x) for x in self.start_counts[m].tolist())
            completed = forward + not_forward
            stand_start[mode] = {"starts": starts, "forward_within_2s": forward,
                                 "not_forward_within_2s": not_forward, "censored": censored,
                                 "pending": int(pending[m]), "completed": completed,
                                 "forward_fraction": forward / completed if completed else None}
        self.off_block.append(survival["off"])
        off_signal = None
        off_block_fraction = None
        if it % self.off_survival_updates == 0:
            total = sum(item["env_steps"] for item in self.off_block)
            falls = sum(item["falls"] for item in self.off_block)
            current = 1 - falls / total if total else None
            off_block_fraction = current
            if (current is not None and self.previous_off_block is not None
                    and self.off_survival_drop is not None
                    and current < self.previous_off_block - self.off_survival_drop):
                off_signal = {"signal": "map_off_survival_50_drop", "previous": self.previous_off_block,
                              "current": current, "threshold": self.off_survival_drop, "decision": "alert_only"}
                alerts.append(off_signal)
            elif (current is not None and self.previous_off_block is not None
                  and self.off_survival_drop is None):
                off_signal = {"signal": "map_off_survival_50_change", "previous": self.previous_off_block,
                              "current": current, "delta": current - self.previous_off_block,
                              "decision": "record_only_threshold_pending"}
            self.previous_off_block = current
            self.off_block = []
        row = {"format": "ex42-live-metrics/1", "stage_id": self.stage_id,
               "plan_sha256": self.plan_sha256, "iteration": it,
               "world_size": self.world_size, "skills": rows, "moving20": moving,
               "slow_track_weight": self.slow_weight,
               "slow_track_slots": slot_rows, "slow_track_moving20": slow_moving,
               "slow_forward_speed_bands": speed_bands,
               "stand_start_2s": stand_start,
               "stand_start_definition": {"initial_body_speed_below_mps": .05,
                                          "command_vx_mps": [0.1, 0.15], "command_upper_exclusive": True,
                                          "forward_body_vx_above_mps": .05, "window_s": 2.0,
                                          "step_dt_s": self.step_dt},
               "rank_local": rank_rows, "survival": survival, "survival_by_family": by_family,
               "off_50_block": off_block_fraction,
               "monitor": {"stage": self.stage.copy(), "high": self.high.copy(), "alerts": alerts,
                           "off_change": off_signal,
                           "threshold_pending": self.decline_from_peak is None or self.off_survival_drop is None}}
        if self.noise_envs is not None:
            (n_s, n_r, n_t), (r_s, r_r, r_t) = self.noise_groups.tolist()
            row["small_noise"] = {
                "env_share": float(self.noise_envs.float().mean()), "sigma_scale": self.noise_sigma_scale,
                "slow_forward": {"noisy": {"samples": int(n_s), "tracking_ratio": n_r / n_s if n_s else None,
                                           "stall_fraction": n_t / n_s if n_s else None},
                                 "rest": {"samples": int(r_s), "tracking_ratio": r_r / r_s if r_s else None,
                                          "stall_fraction": r_t / r_s if r_s else None}}}
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if alerts and self.alert_run_id is not None:
            last = self.last_failed_alert_iteration
            if last is not None and it - last < self.off_survival_updates * 2:
                row["monitor"]["delivery"] = {"attempted": False, "delivered": False,
                                                  "reason": "send failure cooldown",
                                                  "retry_after_iteration": last + self.off_survival_updates * 2}
            else:
                delivery = send_orca_alert(self.alert_run_id, it, alerts, self.log_dir / "ex42_live_metrics.jsonl")
                row["monitor"]["delivery"] = {"attempted": True, **delivery}
                self.last_failed_alert_iteration = None if delivery["delivered"] else it
        with (self.log_dir / "ex42_live_metrics.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n")
        if alerts or off_signal is not None:
            with (self.log_dir / "alerts.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"format": "ex42-live-alert/1", "iteration": it,
                                         "alerts": alerts, "off_change": off_signal},
                                        ensure_ascii=False, sort_keys=True) + "\n")
        return row
