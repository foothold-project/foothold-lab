"""CPU-testable S2 rollout runner. Isaac scene access is supplied by an environment."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import random
import sys

import numpy as np
import torch

from s2_map_obs import MapObsFault, RunValidityGate
from s2_env_adapter_17v import AdapterFault, training_map
from s2_packet_17v import AtomicPacket
from s2_ppo_17v import S2PPO, S2PPOError
from s2_terrain_overlay_17v import EncounterLog, TerrainOverlayError


class S2RunnerError(RuntimeError):
    pass


def timeout_corrected_reward(reward: torch.Tensor, done: torch.Tensor,
                             time_outs: torch.Tensor, stored_value: torch.Tensor,
                             gamma: float) -> torch.Tensor:
    """Parent moe_cts.py:187-193 uses stored pre-step value, never reset-state value."""
    if reward.shape != done.shape or reward.shape != time_outs.shape or reward.shape != stored_value.shape:
        raise S2RunnerError("timeout shape mismatch")
    if time_outs.dtype != torch.bool or done.dtype != torch.bool or bool((time_outs & ~done).any()):
        raise S2RunnerError("time_outs must be a subset of done")
    if not bool(torch.isfinite(stored_value).all()) or not bool(torch.isfinite(reward).all()):
        raise S2RunnerError("timeout value or reward nonfinite")
    return reward + gamma * stored_value * time_outs.to(reward.dtype)


def normalize_advantages(values: torch.Tensor) -> torch.Tensor:
    """Parent full-batch sample std(), with no population-std substitution."""
    if values.numel()<2 or not bool(torch.isfinite(values).all()):
        raise S2RunnerError("advantage sample invalid")
    return (values-values.mean())/(values.std()+1e-8)


def _clone_obs(obs):
    return {k: v.detach().clone() for k, v in obs.items()}


def _flatten(records, key):
    return torch.stack([r[key] for r in records]).reshape(-1, *records[0][key].shape[1:])


def _hash_plan(plan: dict) -> str:
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _same_state(left, right):
    if isinstance(left, torch.Tensor) and isinstance(right, torch.Tensor):
        return torch.equal(left, right)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same_state(left[k], right[k]) for k in left)
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(_same_state(a, b) for a, b in zip(left, right))
    return left == right


class S2Runner:
    """Both arms use this class; only training_map(mode=...) changes the actor map."""
    def __init__(self, env, algo: S2PPO, *, mode: str, env_config_sha256: str,
                 geometry_tolerance_m: float):
        if mode not in ("A", "B") or algo.policy.mode != mode:
            raise S2RunnerError("arm and policy mode differ")
        if not isinstance(env_config_sha256, str) or len(env_config_sha256) != 64 or any(
                x not in "0123456789abcdef" for x in env_config_sha256):
            raise ValueError("environment config SHA256 required")
        if env.num_envs != algo.config.num_envs:
            raise S2RunnerError("environment count differs from fixed plan")
        self.env, self.algo, self.mode = env, algo, mode
        self.env_config_sha256 = env_config_sha256
        self.geometry_tolerance_m = geometry_tolerance_m
        self._next_frame = None
        self.history = []
        self.discarded_transitions = 0
        self.encounters = EncounterLog()
        self._held_reason = None
        self._last_packet = None
        self._last_done = None
        self.plan = {"mode": mode, "ppo": algo.config.as_dict(),
                     "encoder_mode": algo.ctl.encoder_mode,
                     "freeze_updates": algo.ctl.freeze_updates,
                     "encoder_lr_ratio": algo.ctl.encoder_lr_ratio,
                     "geometry_tolerance_m": geometry_tolerance_m}
        self.plan_sha256 = _hash_plan(self.plan)

    def _frame(self, obs: dict, gate: RunValidityGate):
        try:
            packet = self.env.capture_packet_after_sensor_update()
            if not isinstance(packet, AtomicPacket):
                raise S2RunnerError("atomic sensor packet required")
            if not _same_state(packet.obs, obs):
                raise S2RunnerError("packet observation differs from step observation")
            source = self.env.read_sensor_source_receipt()
            if source != packet.source_receipt:
                raise S2RunnerError("independent sensor source receipt differs")
            yaw = packet.validate(previous=self._last_packet, previous_done=self._last_done)
            mapped, faults = training_map(packet.sensor, mode=self.mode,
                                           yaw_w=yaw,
                                          geometry_tolerance_m=self.geometry_tolerance_m)
        except MapObsFault as ex:
            if hasattr(ex, "faults"):
                gate.add_map(ex.faults)
            raise
        gate.add_map(faults)
        frame = _clone_obs(obs)
        frame["map"] = mapped.detach().clone()
        if frame["map"].shape != (self.algo.config.num_envs, 374):
            raise S2RunnerError("map shape does not match rollout")
        gate.add_nonfinite("map", frame["map"])
        critic = self.algo.policy.get_critic_obs(frame)
        gate.add_critic({"critic_input_nonfinite": int((~torch.isfinite(critic)).sum()), "value_nonfinite": 0})
        self._last_packet = packet
        return {"obs": frame, "episode_ids": packet.episode_ids.clone(),
                "frame_tokens": torch.full_like(packet.episode_ids, packet.sensor_generation),
                "packet_id": packet.packet_id, "sim_step": packet.sim_step}

    def _invalid(self, gate, cause, collected):
        self._next_frame = None
        self._held_reason = str(cause)
        discarded = collected * self.algo.config.num_envs
        self.discarded_transitions += discarded
        record = {"arm": self.mode, "status": "invalid", "s2_update_index": self.algo.ctl.next_update_index,
                  "fault_counts": dict(gate.counts), "other_nonfinite": dict(gate.other_nonfinite),
                  "discarded_transitions": discarded, "discarded_total": self.discarded_transitions,
                  "stop_reason": str(cause), "optimizer_steps": 0}
        record["encounters"] = self.encounters.report()
        self.history.append(record)
        return record

    def collect(self):
        if self._held_reason is not None:
            raise S2RunnerError("persistently held: " + self._held_reason)
        cfg, policy = self.algo.config, self.algo.policy
        gate = RunValidityGate()
        records = []
        try:
            frame = self._next_frame or self._frame(self.env.get_observations(), gate)
            if self._next_frame is not None:
                # Saved bootstrap map belongs to the same environment state.
                gate.counts["map_steps"] += 1
                gate.add_nonfinite("map", frame["obs"]["map"])
                critic = policy.get_critic_obs(frame["obs"])
                gate.add_critic({"critic_input_nonfinite": int((~torch.isfinite(critic)).sum()), "value_nonfinite": 0})
            for _ in range(cfg.rollout_steps):
                obs = frame["obs"]
                with torch.no_grad():
                    actions = policy.act(obs)
                    value = policy.evaluate(obs).squeeze(-1)
                    old_mu = policy.action_mean.clone()
                    old_sigma = policy.action_std.clone()
                    old_log_prob = policy.get_actions_log_prob(actions).clone()
                gate.add_critic({"critic_input_nonfinite": 0, "value_nonfinite": int((~torch.isfinite(value)).sum())})
                gate.add_nonfinite("actions", actions)
                if not gate.valid:
                    raise MapObsFault("nonfinite rollout observation, value or action")
                new_obs, reward, done, extras = self.env.step(actions)
                for event in extras.get("encounters", []):
                    self.encounters.record(**event)
                reward, done = reward.reshape(-1).clone(), done.reshape(-1).bool().clone()
                if "time_outs" not in extras:
                    raise S2RunnerError("time_outs missing; cannot distinguish terminal")
                time_outs = extras["time_outs"].reshape(-1).bool().clone()
                reward = timeout_corrected_reward(reward, done, time_outs, value.detach(), cfg.gamma)
                gate.add_nonfinite("reward", reward)
                records.append({"obs": _clone_obs(obs), "actions": actions.detach().clone(),
                                "old_values": value.detach().clone(), "old_mu": old_mu.detach().clone(),
                                "old_sigma": old_sigma.detach().clone(), "old_log_prob": old_log_prob.detach().clone(),
                                "rewards": reward, "dones": done})
                self._last_done = done
                new_frame = self._frame(new_obs, gate)
                if bool(done.any()):
                    if bool((new_frame["episode_ids"][done] <= frame["episode_ids"][done]).any()):
                        raise S2RunnerError("reset reused previous episode id")
                    if bool((new_frame["frame_tokens"][done] == frame["frame_tokens"][done]).any()):
                        raise S2RunnerError("reset reused previous sensor frame")
                frame = new_frame
            with torch.no_grad():
                last_value = policy.evaluate(frame["obs"]).squeeze(-1).detach()
            gate.add_critic({"critic_input_nonfinite": 0, "value_nonfinite": int((~torch.isfinite(last_value)).sum())})
            values = torch.stack([r["old_values"] for r in records])
            rewards = torch.stack([r["rewards"] for r in records])
            dones = torch.stack([r["dones"] for r in records])
            returns = torch.empty_like(values)
            advantage = torch.zeros_like(last_value)
            for t in reversed(range(cfg.rollout_steps)):
                next_value = last_value if t == cfg.rollout_steps-1 else values[t+1]
                nonterminal = (~dones[t]).float()
                delta = rewards[t] + cfg.gamma * next_value * nonterminal - values[t]
                advantage = delta + cfg.gamma * cfg.lam * nonterminal * advantage
                returns[t] = advantage + values[t]
            advantages = returns - values
            advantages = normalize_advantages(advantages)
            gate.add_nonfinite("return", returns)
            gate.add_nonfinite("advantage", advantages)
            gate.require_valid()  # Every arm checks before any PPO update.
        except (MapObsFault, AdapterFault, TerrainOverlayError, S2RunnerError, ValueError, RuntimeError) as ex:
            return None, self._invalid(gate, ex, len(records))
        self._next_frame = frame
        batch = {"obs": {key: torch.stack([r["obs"][key] for r in records]).flatten(0, 1)
                         for key in records[0]["obs"]},
                 "actions": _flatten(records, "actions"),
                 "old_values": values.flatten(), "old_mu": _flatten(records, "old_mu"),
                 "old_sigma": _flatten(records, "old_sigma"),
                 "old_log_prob": _flatten(records, "old_log_prob"),
                 "returns": returns.flatten(), "advantages": advantages.flatten()}
        audit = {"arm": self.mode, "status": "valid", "fault_counts": dict(gate.counts),
                 "other_nonfinite": dict(gate.other_nonfinite), "discarded_transitions": 0,
                 "stop_reason": None, "bootstrap_map": frame["obs"]["map"].clone(),
                 "rollout_maps": batch["obs"]["map"].clone(),
                 "encounters": self.encounters.report()}
        return batch, audit

    def update_once(self):
        if self._held_reason is not None:
            return {"arm": self.mode, "status": "held_collect", "stop_reason": self._held_reason,
                    "optimizer_steps": 0, "s2_update_index": self.algo.ctl.next_update_index}
        if self.algo.ctl.in_update is not None:
            record = {"arm": self.mode, "status": "held_update", "optimizer_steps": self.algo.ctl.steps_this_update,
                      "stop_reason": "previous update incomplete; restart from prior checkpoint required",
                      "discarded_transitions": 0, "discarded_total": self.discarded_transitions,
                      "encounters": self.encounters.report(), "plan_sha256": self.plan_sha256}
            self.history.append(record)
            return record
        batch, audit = self.collect()
        if batch is None:
            return audit
        try:
            result = self.algo.update(batch, self.algo.ctl.next_update_index)
        except Exception as ex:
            self._held_reason = f"{type(ex).__name__}: {ex}"
            discarded = self.algo.config.rollout_steps * self.algo.config.num_envs
            self.discarded_transitions += discarded
            record = {"arm": self.mode, "status": "held_update",
                      "s2_update_index": self.algo.ctl.next_update_index,
                      "fault_counts": audit["fault_counts"], "other_nonfinite": audit["other_nonfinite"],
                      "discarded_transitions": discarded, "discarded_total": self.discarded_transitions,
                      "stop_reason": f"{type(ex).__name__}: {ex}",
                      "optimizer_steps": self.algo.ctl.steps_this_update,
                      "encounters": self.encounters.report(),
                      "plan_sha256": self.plan_sha256, "env_config_sha256": self.env_config_sha256}
            self.history.append(record)
            return record
        public = {k: v for k, v in audit.items() if k not in ("bootstrap_map", "rollout_maps")}
        record = {**public, **result, "status": "updated", "plan_sha256": self.plan_sha256,
                  "env_config_sha256": self.env_config_sha256}
        self.history.append(record)
        return record

    @staticmethod
    def _rng_state():
        return {"torch_cpu": torch.get_rng_state(),
                "torch_cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else None,
                "numpy": np.random.get_state(), "python": random.getstate()}

    @staticmethod
    def _set_rng(state):
        torch.set_rng_state(state["torch_cpu"])
        if state["torch_cuda"] is not None:
            if not torch.cuda.is_initialized():
                raise S2RunnerError("checkpoint has CUDA RNG but CUDA is not initialized")
            torch.cuda.set_rng_state_all(state["torch_cuda"])
        np.random.set_state(state["numpy"])
        random.setstate(state["python"])

    def save(self, path):
        if self.algo.ctl.in_update is not None:
            raise S2RunnerError("cannot save during PPO update")
        state = {"format": "s2-17v-checkpoint-only", "mode": self.mode, "plan": self.plan,
                 "plan_sha256": self.plan_sha256, "env_config_sha256": self.env_config_sha256,
                 "policy": self.algo.policy.state_dict(), "s2_control": self.algo.ctl.state_dict(),
                 "optimizer": self.algo.optimizer.state_dict(), "rng": self._rng_state(),
                  "resume_supported": False,
                 "discarded_transitions": self.discarded_transitions,
                  "encounter_states": copy.deepcopy(self.encounters.states)}
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        torch.save(state, temp)
        temp.replace(path)

    def load(self, path):
        raise S2RunnerError("Isaac environment resume is unsupported; extend only in the same live process")
