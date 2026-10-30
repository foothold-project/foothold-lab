"""W55 in-process EX-40 stages. This module has no Kit dependency.

The active stage changes at an update boundary. Each environment adopts it only
inside CommandTerm.reset, so command resamples in an unfinished episode retain
that episode's stage. No environment or runner is recreated for promotion.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

import torch
import yaml

from foothold_s2.commands.mixed_core import EX39_SLOTS


RANGES = ("forward_vx", "walk_vx", "walk_wz_abs", "spin_wz_abs", "reverse_vx",
          "side_vy_abs", "diag_vx_abs", "diag_vy_abs")
STAGE_IDS = ("B0", "B1", "B2", "B3a", "B3b", "B3c", "T0")
KIT_SMOKE_BOUNDARIES = (3, 6, 9, 12, 15)
FIRST_REWARDS = {"track_ang_vel", "track_lin_vel", "joint_acc", "hip_pos_penalty",
                 "thigh_calf_pos_l1", "four_foot_contact_at_stop", "stand_gap", "stand_load"}


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
    heading_cfg: dict[str, float]
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
        if self.promotion == "gate" and self.shadow_gate:
            raise ValueError("EX-40 gate promotion cannot be shadow-only")
        self.gate_cfg = doc.get("gate") or {}
        self.stand_cfg = doc.get("stand_penalty") or {}
        self.heading_cfg = doc.get("heading") or {}
        if (set(self.gate_cfg) != {"minimum_exposure_updates", "separated_checkpoints"}
                or int(self.gate_cfg["minimum_exposure_updates"]) < 500
                or int(self.gate_cfg["separated_checkpoints"]) < 250):
            raise ValueError("EX-40 gate needs exposure and separated checkpoints")
        if (set(self.stand_cfg) != {"gap_weight", "load_weight", "load_fraction", "ramp_s"}
                or set(self.heading_cfg) != {"forward_fraction", "spin_target_fraction", "gain",
                                              "forward_wz_limit", "target_wz_limit"}):
            raise ValueError("EX-40 stand and heading parameters missing")
        if (not all(math.isfinite(float(v)) for v in (*self.stand_cfg.values(), *self.heading_cfg.values()))
                or self.stand_cfg["gap_weight"] >= 0 or self.stand_cfg["load_weight"] >= 0
                or not 0 < self.stand_cfg["load_fraction"] <= 1
                or self.stand_cfg["ramp_s"] <= 0
                or not 0 <= self.heading_cfg["forward_fraction"] <= 1
                or not 0 <= self.heading_cfg["spin_target_fraction"] <= 1
                or min(self.heading_cfg["gain"], self.heading_cfg["forward_wz_limit"],
                       self.heading_cfg["target_wz_limit"]) <= 0):
            raise ValueError("EX-40 stand or heading settings invalid")
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
        if not isinstance(raw, list) or [x.get("id") for x in raw] != list(STAGE_IDS):
            raise ValueError("D72 EX-40 needs B0, B1, B2, B3a, B3b, B3c, T0 in order")
        if smoke_boundaries is not None and (len(smoke_boundaries) != len(STAGE_IDS) - 2 or
                                             list(smoke_boundaries) != sorted(set(smoke_boundaries))):
            raise ValueError("D72 smoke needs five increasing boundaries")
        if smoke_boundaries is not None:
            raw = raw[:len(smoke_boundaries) + 1]
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
            if index == 0 and set(new_rewards) != FIRST_REWARDS:
                raise ValueError("D70 B0 reward terms incomplete")
            if index == 0 and (float(new_rewards["stand_gap"]) != self.stand_cfg["gap_weight"]
                               or float(new_rewards["stand_load"]) != self.stand_cfg["load_weight"]):
                raise ValueError("EX-40 stand weights disagree with reward terms")
            if index == 1 and new_rewards:
                raise ValueError("D70 B1 keeps B0 reward terms")
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
                if new[0] > old[0] + 1e-9 or new[1] < old[1] - 1e-9:
                    raise ValueError(f"W55 range narrows: {key}")
            force_gt = row.get("force_gt")
            is_t0 = row["id"] == "T0"
            if not isinstance(force_gt, bool) or force_gt == is_t0:
                raise ValueError("W55 T0 alone switches GT to reconstruction")
            if is_t0 and adds.get("map_source") != "reconstruction":
                raise ValueError("W55 T0 map addition missing")
            if not is_t0 and adds.get("map_source") is not None:
                raise ValueError("W55 reconstruction map switch is reserved for T0")
            if row.get("heading_arm") is not None:
                raise ValueError("W55 arm must remain undecided in the shared stage table")
            low = float(row.get("low_forward_fraction", 0.0))
            expected_low = 0.20 if row["id"] in ("B3c", "T0") else 0.0
            if not 0.0 <= low <= 1.0 or not math.isclose(low, expected_low, abs_tol=1e-12):
                raise ValueError("D72 low-speed forward fraction is allowed only in B3c and T0")
            self.stages.append(Stage(row["id"], update, shares, ranges, rewards, force_gt,
                                     low, arm, self.heading_cfg, adds))
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
        self.stage_entry_iteration = 0
        self.b1_entry_iteration: int | None = None
        self.passes: list[dict] = []
        self.latest_score: dict | None = None
        self.seen_scores: set[str] = set()
        self.runner = None
        self._started = False
        self._step_counts = torch.zeros((len(plan.stages), len(EX39_SLOTS), 3), dtype=torch.long, device=device)
        self._done_counts = torch.zeros_like(self._step_counts)
        self._contact_counts = torch.zeros((len(plan.stages), len(EX39_SLOTS), 3, 4), dtype=torch.long, device=device)
        self._side_counts = torch.zeros((len(plan.stages), 4, 2), dtype=torch.long, device=device)
        self._side_contact_counts = torch.zeros((len(plan.stages), 4, 4), dtype=torch.long, device=device)
        self._episode_side = torch.full((env_count,), -1, dtype=torch.long, device=device)
        self._raw_samples: list[dict] = []
        self._sample_step = 0

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
            self._episode_side[env_ids] = -1
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

    def record_pre_step(self):
        """Count the actual episode-stage command and map consumed by one env step."""
        raw = self.runner.env.unwrapped
        term = raw.command_manager.get_term("base_velocity")
        stage = self.env_stage
        slot = term.slot_current.long()
        mode = torch.where(self.runner.pstate.map_off.bool(), 2,
                           torch.where(self.runner.pstate.use_gt.bool(), 0, 1)).long()
        code = (stage * len(EX39_SLOTS) + slot) * 3 + mode
        self._step_counts += torch.bincount(code, minlength=self._step_counts.numel()).reshape_as(self._step_counts)
        sensor = raw.scene.sensors["contact_forces"]
        robot = raw.scene["robot"]
        if not hasattr(self, "_foot_sensor_ids"):
            feet = ["FL_foot", "FR_foot", "RL_foot", "RR_foot"]
            self._foot_sensor_ids = sensor.find_bodies(feet)[0]
        force = sensor.data.net_forces_w[:, self._foot_sensor_ids, :]
        contact = (torch.linalg.vector_norm(force, dim=-1) > 1.0).long()
        yaw_sign = (robot.data.heading_w >= 0).long()
        y_sign = (robot.data.root_pos_w[:, 1] - raw.scene.terrain.env_origins[:, 1] >= 0).long()
        new_episode = self._episode_side < 0
        self._episode_side[new_episode] = (y_sign * 2 + yaw_sign)[new_episode]
        side = self._episode_side.clone()
        for foot in range(4):
            self._contact_counts[..., foot] += torch.bincount(
                code, weights=contact[:, foot].float(), minlength=self._step_counts.numel()
            ).reshape_as(self._step_counts).long()
            self._side_contact_counts[..., foot] += torch.bincount(
                stage * 4 + side, weights=contact[:, foot].float(), minlength=len(self.plan.stages) * 4
            ).reshape(len(self.plan.stages), 4).long()
        for y in (0, 1):
            for h in (0, 1):
                labels = stage[side == y * 2 + h]
                self._side_counts[:, y * 2 + h, 0] += torch.bincount(
                    labels, minlength=len(self.plan.stages))
        self._pre_step_code = code
        self._pre_stage = stage.clone()
        self._pre_side = side
        if self._sample_step % 12 == 0:
            ids = torch.arange(min(8, raw.num_envs), device=stage.device)
            self._raw_samples.append({"env_ids": ids.cpu().tolist(),
                "force_w_n": force[ids].detach().cpu().tolist(),
                "joint_target_rad": robot.data.joint_pos_target[ids].detach().cpu().tolist(),
                "joint_actual_rad": robot.data.joint_pos[ids].detach().cpu().tolist()})
        self._sample_step += 1

    def record_post_step(self, done: torch.Tensor):
        finished = done.bool()
        self._done_counts += torch.bincount(self._pre_step_code[finished],
                                            minlength=self._step_counts.numel()).reshape_as(self._done_counts)
        for y in (0, 1):
            for h in (0, 1):
                labels = self._pre_stage[finished & (self._pre_side == y * 2 + h)]
                self._side_counts[:, y * 2 + h, 1] += torch.bincount(
                    labels, minlength=len(self.plan.stages))
        self._episode_side[finished] = -1

    def flush_consumption(self, iteration: int):
        self._write({"event": "actual_consumption", "iteration": iteration,
                     "axes": {"stage": [s.id for s in self.plan.stages], "slot": list(EX39_SLOTS),
                              "map": ["GT", "PRED", "OFF"], "side": ["y- yaw-", "y- yaw+", "y+ yaw-", "y+ yaw+"]},
                     "steps": self._step_counts.cpu().tolist(), "done": self._done_counts.cpu().tolist(),
                     "contact_steps": self._contact_counts.cpu().tolist(),
                     "side_steps_done": self._side_counts.cpu().tolist(),
                      "side_contact_steps": self._side_contact_counts.cpu().tolist(),
                     "raw_samples": self._raw_samples})
        self._step_counts.zero_()
        self._done_counts.zero_()
        self._contact_counts.zero_()
        self._side_counts.zero_()
        self._side_contact_counts.zero_()
        self._raw_samples.clear()

    def on_update_start(self, iteration: int):
        if self.plan.promotion == "fixed":
            target = self.active + 1
            if target < len(self.plan.stages) and iteration >= self.plan.stages[target].fixed_update:
                self._promote(iteration, {"kind": "fixed", "checkpoint": self.last_checkpoint})
        else:
            self._scan_scores(iteration)
            if self.pending_gate is not None and self._gate_pair_valid(iteration):
                evidence = self.pending_gate
                self.pending_gate = None
                self._promote(iteration, {"kind": "gate", **evidence})
            elif self.pending_gate is not None:
                self._write({"event": "gate_hold", "iteration": iteration,
                             "reason": "stale_or_invalid_cached_pass", "training_continues": True})
                self.pending_gate = None

    def _promote(self, iteration: int, evidence: dict):
        if self.active + 1 >= len(self.plan.stages):
            return
        if self.plan.arm is None:
            raise RuntimeError("EX-40 heading arm must be explicit")
        before = self.plan.stages[self.active]
        self.active += 1
        self.stage_entry_iteration = iteration
        if self.active == 1:
            self.b1_entry_iteration = iteration
        self.passes = []
        self.latest_score = None
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
                   "thigh_calf_pos_l1": "ex39_thigh_calf_pos_l1",
                   "four_foot_contact_at_stop": "ex39_four_foot_stop",
                   "stand_gap": "ex40_stand_gap", "stand_load": "ex40_stand_load"}
        for name, value in self.plan.stages[self.active].rewards.items():
            term_name = mapping.get(name, name)
            cfg = manager.get_term_cfg(term_name)
            cfg.weight = value
            manager.set_term_cfg(term_name, cfg)
        self.runner.basic_lin_vel_z_schedule = self.active >= 1
        if self.active >= 1 and self.b1_entry_iteration is None:
            raise ValueError("EX-40 B1 reward schedule origin missing")
        self.runner.basic_lin_vel_z_start_iteration = self.b1_entry_iteration if self.active >= 1 else 0

    def on_checkpoint(self, iteration: int, checkpoint: str | Path):
        path = Path(checkpoint).resolve(strict=True)
        self.last_checkpoint = {"iteration": iteration, "path": str(path), "sha256": sha256(path)}
        self._scan_scores(iteration)
        if self.plan.promotion == "gate" and self.pending_gate is None:
            self._write({"event": "gate_hold", "iteration": iteration,
                         "stage": self.plan.stages[self.active].id,
                         "reason": "no_two_valid_separated_passes", "training_continues": True})

    def _scan_scores(self, iteration: int):
        if self.score_dir is None or self.active + 1 >= len(self.plan.stages):
            return
        candidates = []
        for score_path in self.score_dir.glob("*.json"):
            try:
                digest = sha256(score_path)
            except OSError:
                self._write({"event": "gate_hold", "iteration": iteration,
                             "score_path": str(score_path), "reason": "score_unreadable"})
                continue
            if digest in self.seen_scores:
                continue
            try:
                score = json.loads(score_path.read_text(encoding="utf-8-sig"))
                if not isinstance(score, dict):
                    raise ValueError("score JSON must be an object")
                if score.get("from") != self.plan.stages[self.active].id:
                    continue
                if (score.get("format") != "foothold-ex40-score/2"
                        or score.get("to") != self.plan.stages[self.active + 1].id
                        or score.get("effective_schedule_sha256") != self.plan.effective_sha256
                        or score.get("verdict") not in ("PASS", "FAIL", "HOLD")):
                    raise ValueError("score stage, config, or verdict mismatch")
                stamp = datetime.fromisoformat(score["created_at"])
                if stamp.tzinfo is None:
                    raise ValueError("score time has no timezone")
                update = int(score["checkpoint_iteration"])
                source = Path(score["checkpoint"]).resolve(strict=True)
                if (source.name != f"model_{update}.pt" or sha256(source) != score.get("checkpoint_sha256")
                        or update > iteration or update < self.stage_entry_iteration
                        or iteration - update > 500):
                    raise ValueError("score checkpoint missing, future, stale, or SHA mismatch")
                candidates.append((update, stamp, score_path, digest, score))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.seen_scores.add(digest)
                self.passes.clear()
                self.pending_gate = None
                self._write({"event": "gate_hold", "iteration": iteration,
                             "score_path": str(score_path), "reason": type(exc).__name__,
                              "score_sha256": digest, "training_continues": True})
        for update, _, path, digest, score in sorted(candidates):
            if digest in self.seen_scores:
                continue
            self.seen_scores.add(digest)
            row = {"event": "gate_decision", "iteration": iteration,
                   "from": score["from"], "to": score["to"], "verdict": score["verdict"],
                   "checkpoint_iteration": update, "checkpoint": score["checkpoint"],
                   "score_path": str(path),
                   "score_sha256": digest, "checkpoint_sha256": score["checkpoint_sha256"],
                   "created_at": score["created_at"]}
            self._write(row)
            order = (update, score["created_at"])
            latest_order = ((self.latest_score["checkpoint_iteration"],
                             self.latest_score["created_at"]) if self.latest_score else None)
            if latest_order == order and score["verdict"] != self.latest_score["verdict"]:
                self.latest_score = {**row, "verdict": "HOLD",
                                     "conflict": "same_checkpoint_and_time"}
                self.passes.clear()
                self.pending_gate = None
                self._write({"event": "gate_hold", "iteration": iteration,
                             "reason": "same_checkpoint_conflicting_verdict",
                             "score_sha256": digest, "training_continues": True})
                continue
            if latest_order is not None and order <= latest_order:
                self._write({"event": "gate_hold", "iteration": iteration,
                             "reason": "older_than_latest_score", "score_sha256": digest,
                             "training_continues": True})
                continue
            self.latest_score = row
            if score["verdict"] != "PASS":
                self.passes.clear()
                self.pending_gate = None
                continue
            if update - self.stage_entry_iteration < self.plan.gate_cfg["minimum_exposure_updates"]:
                self._write({"event": "gate_hold", "iteration": iteration,
                             "stage": self.plan.stages[self.active].id,
                             "reason": "minimum_exposure_not_reached", "score_sha256": digest})
                continue
            self.passes = [old for old in self.passes if self._pass_valid(old, iteration)]
            self.passes.append(row)
            if (not self.plan.shadow_gate and self.plan.promotion == "gate"
                    and len(self.passes) >= 2
                    and self.passes[-1]["checkpoint_iteration"] - self.passes[-2]["checkpoint_iteration"]
                     >= self.plan.gate_cfg["separated_checkpoints"]
                     and self._pass_valid(self.passes[-2], iteration)):
                self.pending_gate = {"scores": self.passes[-2:]}

    def _pass_valid(self, row: dict, iteration: int) -> bool:
        try:
            update = row["checkpoint_iteration"]
            checkpoint = Path(row["checkpoint"])
            score_path = Path(row["score_path"])
            return (row["verdict"] == "PASS"
                    and row["from"] == self.plan.stages[self.active].id
                    and row["to"] == self.plan.stages[self.active + 1].id
                    and update >= self.stage_entry_iteration
                    and 0 <= iteration - update <= 500
                    and checkpoint.name == f"model_{update}.pt"
                    and sha256(checkpoint) == row["checkpoint_sha256"]
                    and sha256(score_path) == row["score_sha256"])
        except (KeyError, OSError, TypeError, ValueError):
            return False

    def _gate_pair_valid(self, iteration: int) -> bool:
        scores = self.pending_gate.get("scores") if isinstance(self.pending_gate, dict) else None
        return (isinstance(scores, list) and len(scores) == 2
                and self.latest_score is not None
                and self.latest_score["verdict"] == "PASS"
                and scores[-1]["score_sha256"] == self.latest_score["score_sha256"]
                and all(self._pass_valid(row, iteration) for row in scores)
                and scores[0]["checkpoint_iteration"] - self.stage_entry_iteration
                >= self.plan.gate_cfg["minimum_exposure_updates"]
                and scores[1]["checkpoint_iteration"] - scores[0]["checkpoint_iteration"]
                >= self.plan.gate_cfg["separated_checkpoints"])

    def state_dict(self) -> dict:
        return {"format": "foothold-w55-state/1", "plan_sha256": self.plan.sha256,
                "effective_sha256": self.plan.effective_sha256,
                "active": self.active, "env_stage": self.env_stage.clone(),
                "last_checkpoint": self.last_checkpoint, "pending_gate": self.pending_gate,
                "seen_scores": sorted(self.seen_scores), "stage_entry_iteration": self.stage_entry_iteration,
                 "b1_entry_iteration": self.b1_entry_iteration,
                 "latest_score": self.latest_score, "passes": self.passes}

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
        self.stage_entry_iteration = int(state.get("stage_entry_iteration", self.plan.stages[active].fixed_update))
        self.b1_entry_iteration = state.get("b1_entry_iteration")
        if active >= 1 and (type(self.b1_entry_iteration) is not int
                            or self.b1_entry_iteration > self.stage_entry_iteration):
            raise ValueError("EX-40 saved B1 schedule origin missing or invalid")
        self.latest_score = state.get("latest_score")
        self.passes = list(state.get("passes") or [])
        self._episode_side.fill_(-1)
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
        self._episode_side.fill_(-1)
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
                good = bounded(x, "forward_vx") & zero(y) & torch.where(
                    h, w.abs() <= stage.heading_cfg["forward_wz_limit"] + tol, zero(w))
            elif name.startswith("walk_"):
                good = bounded(x, "walk_vx") & zero(y) & absolute(w, "walk_wz_abs") & ~h
                good &= w > 0 if name.endswith("left") else w < 0
            elif name.startswith("spin_"):
                good = zero(x) & zero(y) & torch.where(
                    h, w.abs() <= stage.heading_cfg["target_wz_limit"] + tol,
                    absolute(w, "spin_wz_abs"))
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
