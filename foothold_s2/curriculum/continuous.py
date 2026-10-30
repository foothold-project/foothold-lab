"""W55 in-process EX-40 stages. This module has no Kit dependency.

The active stage changes at an update boundary. Each environment adopts it only
inside CommandTerm.reset, so command resamples in an unfinished episode retain
that episode's stage. No environment or runner is recreated for promotion.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import torch
import yaml

from foothold_s2.commands.mixed_core import EX39_SLOTS


RANGES = ("forward_vx", "walk_vx", "walk_wz_abs", "spin_wz_abs", "reverse_vx",
          "side_vy_abs", "diag_vx_abs", "diag_vy_abs")
FIRST_REWARDS = {"track_ang_vel", "track_lin_vel", "joint_acc", "hip_pos_penalty",
                 "thigh_calf_pos_l1"}


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class Stage:
    id: str
    fixed_update: int
    shares: dict[str, float]
    ranges: dict[str, tuple[float, float]]
    rewards: dict[str, float]
    force_gt: bool
    low_forward_fraction: float
    heading_arm: str | None
    adds: dict


class Plan:
    def __init__(self, path: str | Path, *, arm: str | None = None,
                 smoke_boundaries: tuple[int, ...] | None = None):
        self.path = Path(path).resolve(strict=True)
        self.sha256 = sha256(self.path)
        doc = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or doc.get("format") != "foothold-ex40-curriculum/1":
            raise ValueError("W55 curriculum format missing")
        if doc.get("promotion") not in ("fixed", "gate") or not isinstance(doc.get("shadow_gate"), bool):
            raise ValueError("W55 promotion must be fixed|gate and shadow_gate explicit")
        self.promotion = doc["promotion"]
        self.shadow_gate = doc["shadow_gate"]
        if doc.get("start") != "scratch" or "parent_sha256" in doc or "parent_update" in doc:
            raise ValueError("D68 EX-40 must start from scratch")
        self.parent_sha256 = None
        self.parent_update = None
        self.baseline_env_yaml_sha256 = doc.get("baseline_env_yaml_sha256")
        self.baseline_agent_yaml_sha256 = doc.get("baseline_agent_yaml_sha256")
        if any(not isinstance(x, str) or len(x) != 64 for x in
               (self.baseline_env_yaml_sha256, self.baseline_agent_yaml_sha256)):
            raise ValueError("D68 S-B10 baseline YAML SHA pins missing")
        if arm not in (None, "A", "B"):
            raise ValueError("W55 heading arm must be A or B")
        self.arm = arm
        self.effective_sha256 = hashlib.sha256(json.dumps(
            {"table_sha256": self.sha256, "arm": arm, "smoke_boundaries": smoke_boundaries},
            sort_keys=True).encode("utf-8")).hexdigest()
        raw = doc.get("stages")
        if not isinstance(raw, list) or [x.get("id") for x in raw] != ["B0", "B1", "B2", "B3", "T0"]:
            raise ValueError("D68 EX-40 needs B0, B1, B2, B3, T0 in order")
        if smoke_boundaries is not None and (len(smoke_boundaries) != 4 or
                                             list(smoke_boundaries) != sorted(set(smoke_boundaries))):
            raise ValueError("D68 smoke needs four increasing boundaries")
        self.stages: list[Stage] = []
        last_rewards: dict[str, float] = {}
        last_slots: set[str] = set()
        last_ranges: dict[str, tuple[float, float]] = {}
        last_update = -1
        for index, row in enumerate(raw):
            if not isinstance(row, dict) or not isinstance(row.get("start"), dict):
                raise ValueError("W55 stage/start must be mappings")
            update = int(row["start"]["fixed_update"])
            if smoke_boundaries is not None and index > 0:
                update = smoke_boundaries[index - 1]
            if update <= last_update and smoke_boundaries is None:
                raise ValueError("W55 fixed updates must increase")
            if index and smoke_boundaries is not None and update <= self.stages[-1].fixed_update:
                raise ValueError("W55 smoke boundaries must increase after B1")
            last_update = update
            adds = row.get("adds") or {}
            if not isinstance(adds, dict) or set(adds) - {"rewards", "command_slots", "map_source"}:
                raise ValueError("W55 unknown stage addition")
            new_rewards = adds.get("rewards") or {}
            if not isinstance(new_rewards, dict) or set(new_rewards) & set(last_rewards):
                raise ValueError("W55 reward terms may only be added once")
            if index == 0 and new_rewards:
                raise ValueError("D68 B0 must retain S-B10 reward weights")
            if index == 1 and set(new_rewards) != FIRST_REWARDS:
                raise ValueError("D68 B1 reward additions incomplete; stand reward undecided")
            if index > 1 and new_rewards:
                raise ValueError("W55 later reward terms need an env-time registration adapter")
            rewards = {**last_rewards, **{k: float(v) for k, v in new_rewards.items()}}
            new_slots = adds.get("command_slots") or []
            if not isinstance(new_slots, list) or set(new_slots) & last_slots:
                raise ValueError("W55 slots may only be added once")
            slots = last_slots | set(new_slots)
            if not slots <= set(EX39_SLOTS) or not slots:
                raise ValueError("W55 unknown or empty command slots")
            shares = {k: float(v) for k, v in (row.get("shares") or {}).items()}
            if set(shares) != slots or any(not math.isfinite(v) or v <= 0 for v in shares.values()):
                raise ValueError("W55 shares must cover exactly active slots with positive fractions")
            if abs(sum(shares.values()) - 1.0) > 1e-9:
                raise ValueError("W55 command shares must sum to 100 percent")
            ranges = {k: tuple(float(v) for v in values) for k, values in (row.get("ranges") or {}).items()}
            if set(ranges) - set(RANGES) or any(len(v) != 2 or not all(map(math.isfinite, v)) or v[0] >= v[1]
                                                   for v in ranges.values()):
                raise ValueError("W55 command ranges malformed")
            if index == 0 and set(ranges) != set(RANGES[:6]):
                raise ValueError("D68 B0 ranges incomplete")
            if index and set(ranges) != (set(RANGES) if "diag_fwd_left" in slots else set(RANGES[:6])):
                raise ValueError("W55 active ranges incomplete")
            for key, old in last_ranges.items():
                new = ranges[key]
                # B0 has the S-B10 spin range, including speeds below B1's
                # basic-gait minimum. B1 deliberately narrows that one range.
                if index != 1 and (new[0] > old[0] + 1e-9 or new[1] < old[1] - 1e-9):
                    raise ValueError(f"W55 range narrows: {key}")
            force_gt = row.get("force_gt")
            if not isinstance(force_gt, bool) or (index < 4 and not force_gt) or (index == 4 and force_gt):
                raise ValueError("W55 T0 alone switches GT to reconstruction")
            if index == 4 and adds.get("map_source") != "reconstruction":
                raise ValueError("W55 T0 map addition missing")
            if row.get("heading_arm") is not None:
                raise ValueError("W55 arm must remain undecided in the shared stage table")
            low = float(row.get("low_forward_fraction", 0.0))
            if not 0.0 <= low <= 1.0 or (index < 3 and low) or (index >= 3 and low != 0.20):
                raise ValueError("W55 low-speed forward fraction differs from D59")
            self.stages.append(Stage(row["id"], update, shares, ranges, rewards, force_gt,
                                     low, arm if index > 1 else None, adds))
            last_rewards, last_slots, last_ranges = rewards, slots, ranges


class Runtime:
    """Stage and per-env episode state, with checkpoint and score receipts."""

    def __init__(self, plan: Plan, env_count: int, device: str, log_dir: str | Path,
                 score_dir: str | Path | None = None):
        self.plan = plan
        self.active = 0
        self.env_stage = torch.zeros(env_count, dtype=torch.long, device=device)
        self._pending_adoption = torch.zeros(env_count, dtype=torch.bool, device=device)
        self._pending_adoption_count = 0
        self.log_dir = Path(log_dir)
        self.score_dir = Path(score_dir) if score_dir is not None else None
        self.last_checkpoint: dict | None = None
        self.pending_gate: dict | None = None
        self.seen_scores: set[str] = set()
        self.runner = None
        self._started = False

    def attach(self, runner, command_term):
        self.runner = runner
        command_term.stage_runtime = self
        runner.continuous_curriculum = self
        self._sync_map()
        self._sync_rewards()

    def _write(self, row: dict):
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with (self.log_dir / "stage_log.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()

    def start(self, parent_sha256: str | None = None):
        if parent_sha256 is not None:
            raise ValueError("D68 scratch run must not have a parent checkpoint")
        if not self._started:
            self._write({"event": "stage_enter", "iteration": self.plan.stages[self.active].fixed_update,
                         "from": None, "to": self.plan.stages[self.active].id,
                         "changed": self.plan.stages[self.active].adds,
                         "evidence_sha256": None, "curriculum_sha256": self.plan.sha256,
                         "effective_schedule_sha256": self.plan.effective_sha256,
                         "applied_on_reset": True})
            self._started = True

    def on_reset(self, env_ids: torch.Tensor):
        if env_ids.numel():
            old = self.env_stage[env_ids].clone()
            self.env_stage[env_ids] = self.active
            changed = int((old != self.active).sum().item())
            if changed:
                self._pending_adoption[env_ids[old != self.active]] = True
                self._pending_adoption_count += changed
                self._write({"event": "env_reset_applied", "to": self.plan.stages[self.active].id,
                             "map_source_policy": ("forced_gt" if self.plan.stages[self.active].force_gt
                                                   else "AdaSmpl_pred_eligible"),
                             "adasmpl_p": (float(self.runner.adasmpl.p) if self.runner is not None else None),
                             "changed_envs": changed, "remaining_old_envs": int((self.env_stage != self.active).sum().item())})

    def record_command_sample(self, env_ids: torch.Tensor, command: torch.Tensor,
                              slot: torch.Tensor, heading: torch.Tensor):
        """Receipt for commands actually stored after a new stage's reset resample."""
        if not self._pending_adoption_count:
            return
        adopted = self._pending_adoption[env_ids]
        if not bool(adopted.any()):
            return
        selected_ids = env_ids[adopted]
        stage_ids = self.env_stage[selected_ids]
        if not bool((stage_ids == self.active).all()):
            raise ValueError("W55 stage command sample did not use the active stage")
        selected_slot = slot[adopted]
        selected_command = command[adopted]
        selected_heading = heading[adopted]
        bad = int(command_bad(selected_command, selected_slot, selected_heading,
                              stage_ids, self.plan).sum().item())
        counts = torch.bincount(selected_slot, minlength=len(EX39_SLOTS)).cpu().tolist()
        count = int(selected_ids.numel())
        self._pending_adoption[selected_ids] = False
        self._pending_adoption_count -= count
        self._write({"event": "stage_command_consumed", "to": self.plan.stages[self.active].id,
                     "sampled_envs": count, "slot_counts": dict(zip(EX39_SLOTS, counts)),
                     "heading_count": int(selected_heading.sum().item()), "command_bad_count": bad})

    def record_map_reset(self, env_ids: torch.Tensor, use_gt: torch.Tensor):
        """Receipt after perception.reset_envs has installed the map flag for reset envs."""
        if not env_ids.numel():
            return
        stage_ids = self.env_stage[env_ids]
        for index, stage in enumerate(self.plan.stages):
            selected = env_ids[stage_ids == index]
            if not selected.numel():
                continue
            self._write({"event": "stage_map_consumed", "to": stage.id,
                         "reset_envs": int(selected.numel()),
                         "force_gt_runtime": bool(self.runner.adasmpl.force_gt),
                         "use_gt_envs": int(use_gt[selected].sum().item()),
                         "adasmpl_p": float(self.runner.adasmpl.p)})

    def on_update_start(self, iteration: int):
        if self.plan.promotion == "fixed":
            target = self.active + 1
            if target < len(self.plan.stages) and iteration >= self.plan.stages[target].fixed_update:
                self._promote(iteration, {"kind": "fixed", "checkpoint": self.last_checkpoint})
        elif self.pending_gate is not None:
            self._promote(iteration, {"kind": "gate", **self.pending_gate})
            self.pending_gate = None

    def _promote(self, iteration: int, evidence: dict):
        if self.active + 1 >= len(self.plan.stages):
            return
        if self.active == 1 and self.plan.arm is None:
            raise RuntimeError("W55 B2 arm unresolved; an explicit A/B decision is required")
        before = self.plan.stages[self.active]
        self.active += 1
        after = self.plan.stages[self.active]
        self._sync_map()
        self._sync_rewards()
        changed = {"rewards_added": after.adds.get("rewards", {}),
                   "slots_added": after.adds.get("command_slots", []),
                   "shares": {k: [before.shares.get(k), v] for k, v in after.shares.items()
                              if before.shares.get(k) != v},
                   "ranges": {k: [before.ranges.get(k), v] for k, v in after.ranges.items()
                              if before.ranges.get(k) != v},
                   "map_source": after.adds.get("map_source")}
        self._write({"event": "stage_enter", "iteration": iteration, "from": before.id, "to": after.id,
                     "changed": changed, "shares": after.shares, "ranges": after.ranges,
                     "force_gt": after.force_gt, "evidence": evidence,
                     "evidence_sha256": (self.last_checkpoint or {}).get("sha256"),
                     "curriculum_sha256": self.plan.sha256,
                     "effective_schedule_sha256": self.plan.effective_sha256,
                     "pending_envs": int((self.env_stage != self.active).sum().item())})

    def _sync_map(self):
        if self.runner is not None:
            value = self.plan.stages[self.active].force_gt
            self.runner.adasmpl.force_gt = value
            self.runner.pcfg["force_gt"] = value
            self.runner.perception.cfg.force_gt = value

    def _sync_rewards(self):
        if self.runner is None:
            return
        manager = self.runner.env.unwrapped.reward_manager
        mapping = {"hip_pos_penalty": "basic_hip_pos_penalty_l1",
                   "thigh_calf_pos_l1": "ex39_thigh_calf_pos_l1"}
        for name, value in self.plan.stages[self.active].rewards.items():
            term_name = mapping.get(name, name)
            cfg = manager.get_term_cfg(term_name)
            cfg.weight = value
            manager.set_term_cfg(term_name, cfg)
        self.runner.basic_lin_vel_z_schedule = self.active >= 1
        self.runner.basic_lin_vel_z_start_iteration = 1501

    def on_checkpoint(self, iteration: int, checkpoint: str | Path):
        path = Path(checkpoint).resolve(strict=True)
        self.last_checkpoint = {"iteration": iteration, "path": str(path), "sha256": sha256(path)}
        if self.score_dir is None or self.active + 1 >= len(self.plan.stages):
            return
        for score_path in sorted(self.score_dir.glob("*.json")):
            digest = sha256(score_path)
            if digest in self.seen_scores:
                continue
            score = json.loads(score_path.read_text(encoding="utf-8"))
            if score.get("format") != "foothold-w55-score/1" or score.get("verdict") not in ("EXPAND", "HOLD", "REVERT"):
                raise ValueError(f"W55 malformed score: {score_path}")
            if score.get("from") != self.plan.stages[self.active].id or score.get("to") != self.plan.stages[self.active + 1].id:
                continue
            source = Path(score["checkpoint"]).resolve(strict=True)
            if source.name != f"model_{score['checkpoint_iteration']}.pt" or sha256(source) != score.get("checkpoint_sha256"):
                raise ValueError("W55 score checkpoint SHA or numbered file mismatch")
            if int(score["checkpoint_iteration"]) > iteration:
                raise ValueError("W55 score came from a future checkpoint")
            self.seen_scores.add(digest)
            row = {"event": "shadow_gate" if self.plan.shadow_gate else "gate_decision",
                   "iteration": iteration, "from": score["from"], "to": score["to"],
                   "verdict": score["verdict"], "score_path": str(score_path),
                   "score_sha256": digest, "checkpoint_sha256": score["checkpoint_sha256"]}
            self._write(row)
            if not self.plan.shadow_gate and self.plan.promotion == "gate" and score["verdict"] == "EXPAND":
                self.pending_gate = row
            break

    def state_dict(self) -> dict:
        return {"format": "foothold-w55-state/1", "plan_sha256": self.plan.sha256,
                "effective_sha256": self.plan.effective_sha256,
                "active": self.active, "env_stage": self.env_stage.clone(),
                "last_checkpoint": self.last_checkpoint, "pending_gate": self.pending_gate,
                "seen_scores": sorted(self.seen_scores)}

    def load_state_dict(self, state: dict):
        if (state.get("format") != "foothold-w55-state/1"
                or state.get("plan_sha256") != self.plan.sha256
                or state.get("effective_sha256") != self.plan.effective_sha256):
            raise ValueError("W55 stage state and curriculum SHA mismatch")
        active = int(state["active"])
        env_stage = state["env_stage"].to(self.env_stage.device)
        if active not in range(len(self.plan.stages)) or env_stage.shape != self.env_stage.shape or (env_stage > active).any():
            raise ValueError("W55 stage state is invalid")
        self.active = active
        self.env_stage.copy_(env_stage)
        self._pending_adoption.zero_()
        self._pending_adoption_count = 0
        self.last_checkpoint = state.get("last_checkpoint")
        self.pending_gate = state.get("pending_gate")
        self.seen_scores = set(state.get("seen_scores") or [])
        self._sync_map()
        self._sync_rewards()

    def on_resume_checkpoint(self, checkpoint: str | Path, iteration: int):
        """Pin the checkpoint that actually starts this process, not its predecessor."""
        path = Path(checkpoint).resolve(strict=True)
        if path.name != f"model_{iteration}.pt":
            raise ValueError("W55 resume checkpoint number differs from saved iteration")
        self.last_checkpoint = {"iteration": iteration, "path": str(path), "sha256": sha256(path)}

    def after_physical_resume_reset(self):
        # A new process necessarily starts new episodes. This is not an in-process stage change.
        self.env_stage.fill_(self.active)
        self._pending_adoption.zero_()
        self._pending_adoption_count = 0
        self._write({"event": "physical_resume_reset", "stage": self.plan.stages[self.active].id,
                     "note": "new simulator episode; not a physically identical continuation"})


def command_bad(command: torch.Tensor, slot: torch.Tensor, heading: torch.Tensor,
                stage_ids: torch.Tensor, plan: Plan, tol: float = 1e-5) -> torch.Tensor:
    """Validate each consumed command against that env's current episode stage."""
    if command.ndim != 2 or command.shape[1] != 3 or any(
            x.shape != command.shape[:1] for x in (slot, heading, stage_ids)):
        raise ValueError("W55 command evidence shape mismatch")
    bad = ~torch.isfinite(command).all(dim=1)
    c = torch.nan_to_num(command, nan=1e9, posinf=1e9, neginf=-1e9)
    for stage_index, stage in enumerate(plan.stages):
        env = stage_ids == stage_index
        if not bool(env.any()):
            continue
        for number, name in enumerate(EX39_SLOTS):
            ids = env & (slot == number)
            if not bool(ids.any()):
                continue
            if name not in stage.shares:
                bad |= ids
                continue
            x, y, w = c[ids].unbind(1)
            zero = lambda z: z.abs() <= tol
            bounded = lambda z, key: (z >= stage.ranges[key][0] - tol) & (z <= stage.ranges[key][1] + tol)
            absolute = lambda z, key: (z.abs() >= stage.ranges[key][0] - tol) & (z.abs() <= stage.ranges[key][1] + tol)
            h = heading[ids]
            if name == "forward":
                good = bounded(x, "forward_vx") & zero(y) & torch.where(h, w.abs() <= 2.0 + tol, zero(w))
            elif name.startswith("walk_"):
                good = bounded(x, "walk_vx") & zero(y) & absolute(w, "walk_wz_abs") & ~h
                good &= w > 0 if name.endswith("left") else w < 0
            elif name.startswith("spin_"):
                good = zero(x) & zero(y) & torch.where(h, w.abs() <= 2.0 + tol, absolute(w, "spin_wz_abs"))
                good &= torch.where(h, torch.ones_like(good),
                                    w > 0 if name.endswith("left") else w < 0)
            elif name == "stand":
                good = zero(x) & zero(y) & zero(w) & ~h
            elif name == "reverse":
                good = bounded(x, "reverse_vx") & zero(y) & zero(w) & ~h
            elif name.startswith("side_"):
                good = zero(x) & absolute(y, "side_vy_abs") & zero(w) & ~h
                good &= y > 0 if name.endswith("left") else y < 0
            else:
                good = absolute(x, "diag_vx_abs") & absolute(y, "diag_vy_abs") & zero(w) & ~h
                good &= x > 0 if name.startswith("diag_fwd") else x < 0
                good &= y > 0 if name.endswith("left") else y < 0
            bad[ids] = bad[ids] | ~good
    bad |= (slot < 0) | (slot >= len(EX39_SLOTS)) | (stage_ids < 0) | (stage_ids >= len(plan.stages))
    return bad
