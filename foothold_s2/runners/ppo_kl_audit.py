"""Observe actual PPO minibatches without changing LR, RNG, losses or collectives.

The installed scheduler uses KL(old || current) with epsilon *inside* log.
This observer reads the same distribution before optimizer.step changes std.
Each rank writes separately. join_rank_records reconstructs the scheduler's
mean of rank means offline; a missing rank is never treated as zero.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid

import torch


SCHEMA = "foothold-ppo-minibatch-kl/1"
MAP_MODES = ("GT", "PRED", "OFF")
META_FIELDS = ("command", "command_slot", "terrain_column", "terrain_level",
               "heading", "flag", "map_mode", "episode_length")


@torch.inference_mode()
def scheduler_kl(old_mu, old_sigma, mu, sigma):
    """Exactly the installed PPO per-sample expression, not the update-end probe."""
    if not (old_mu.shape == old_sigma.shape == mu.shape == sigma.shape) or mu.ndim != 2:
        raise ValueError("KL needs equally shaped [sample, action] tensors")
    return torch.sum(torch.log(sigma / old_sigma + 1.0e-5)
                     + (old_sigma.square() + (old_mu - mu).square()) / (2.0 * sigma.square())
                     - 0.5, dim=-1)


def _finite(value):
    value = float(value)
    return value if math.isfinite(value) else None


class PpoKLAudit:
    """Optional observer attached to one initialized CriticMirrorPPO instance.

    provider() is called just before alg.act, never after env.step/reset. It
    returns iteration and META_FIELDS tensors with N rows. Existing validity
    masking and shuffle indices remain authoritative. Runtime observer errors
    produce audit_error + incomplete and a stderr warning, not a training stop.
    Startup/API incompatibilities fail before any observer is installed.
    """

    def __init__(self, alg, provider, output_dir, *, identity, top_k=8, columns=(), slots=()):
        from foothold_s2.runners.ex41_critic_mirror import CriticMirrorPPO
        from foothold_s2.runners.ex41_valid_storage import ValidRolloutStorage
        from rsl_rl.algorithms import PPO

        if not isinstance(alg, CriticMirrorPPO) or not isinstance(alg.storage, ValidRolloutStorage):
            raise TypeError("KL audit requires initialized CriticMirrorPPO/ValidRolloutStorage")
        if alg.policy.is_recurrent or alg.symmetry or alg.rnd:
            raise ValueError("KL audit supports feed-forward PPO without actor augmentation or RND")
        if getattr(alg, "kl_audit", None) is not None:
            raise ValueError("KL audit is already installed")
        if type(top_k) is not int or not 1 <= top_k <= 64:
            raise ValueError("top_k must be 1..64")
        self.alg, self.provider, self.top_k = alg, provider, top_k
        self.rank, self.world_size = alg.gpu_global_rank, alg.gpu_world_size
        self.columns, self.slots = list(columns), list(slots)
        self.identity = json.loads(json.dumps(identity, allow_nan=False))
        self.session = uuid.uuid4().hex
        self.iteration = None
        self.metadata = {}
        self.seen = set()
        self.reset_age = None
        self.current = None
        self.error_count = 0
        self.closed = False
        self.update_active = False
        self.batch_count = 0
        self.step_count = 0
        self._warned = set()
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"ppo_kl_rank{self.rank}.jsonl"
        self._stream = self.path.open("a", encoding="utf-8", buffering=1)
        source = Path(inspect.getfile(PPO))
        try:
            self._emit("installed", ppo_source=str(source),
                       ppo_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                       columns=self.columns, command_slots=self.slots, top_k=top_k,
                       reset_definition="first observed action, or action immediately after previous done",
                       aggregation="offline mean of rank means; no added collective",
                       measurement_point="optimizer step pre-hook, after existing adaptive scheduler",
                       lr_limits=[1e-5, 1e-2], limits_source="installed PPO; recorded only")
            self._handle = alg.optimizer.register_step_pre_hook(self._optimizer_pre_step)
        except Exception:
            self._stream.close()
            raise
        alg.kl_audit = self
        alg.storage.kl_audit = self

    def _emit(self, event, **data):
        row = {"schema": SCHEMA, "event": event, "time_ns": time.time_ns(),
               "session": self.session, "pid": os.getpid(), "identity": self.identity,
               "rank": self.rank, "world_size": self.world_size, "iteration": self.iteration, **data}
        self._stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")

    def observe(self, method, *args):
        if self.closed:
            return
        try:
            getattr(self, "_" + method)(*args)
        except Exception as exc:
            self.error_count += 1
            error = f"{method}: {type(exc).__name__}: {exc}"
            if error not in self._warned:
                print("PPO_KL_AUDIT_INCOMPLETE " + error, file=sys.stderr, flush=True)
                self._warned.add(error)
            try:
                self._emit("audit_error", operation=method, error=error, status="incomplete")
            except Exception as write_exc:
                # Never hide a full disk or broken output behind a PASS record.
                warning = f"write: {type(write_exc).__name__}: {write_exc}"
                if warning not in self._warned:
                    print("PPO_KL_AUDIT_WRITE_FAILED " + warning, file=sys.stderr, flush=True)
                    self._warned.add(warning)

    @torch.inference_mode()
    def _capture_rollout(self, step):
        if step == 0:
            self.metadata, self.seen, self.iteration = {}, set(), None
            self.error_count = 0
        raw = self.provider()
        iteration = raw["iteration"]
        if type(iteration) is not int or iteration < 0:
            raise ValueError("metadata iteration must be a nonnegative int")
        if self.iteration is not None and iteration != self.iteration:
            raise ValueError("metadata iteration changed inside rollout")
        self.iteration = iteration
        n, t = self.alg.storage.num_envs, self.alg.storage.num_transitions_per_env
        if step in self.seen or not 0 <= step < t:
            raise ValueError("duplicate or out-of-range rollout step")
        snapshot = {}
        for name in META_FIELDS:
            value = raw[name]
            shape = (n, 3) if name == "command" else (n,)
            if not isinstance(value, torch.Tensor) or tuple(value.shape) != shape:
                raise ValueError(f"metadata {name} needs shape {shape}")
            value = value.detach().to(self.alg.storage.valid.device).clone()
            if not bool(torch.isfinite(value).all()):
                raise ValueError(f"metadata {name} is nonfinite")
            snapshot[name] = value
        if not bool(((snapshot["map_mode"] >= 0) & (snapshot["map_mode"] <= 2)).all()):
            raise ValueError("map mode must be GT=0, PRED=1 or OFF=2")
        if self.reset_age is None:
            self.reset_age = torch.zeros(n, dtype=torch.int64, device=self.alg.storage.valid.device)
        snapshot["reset_age_steps"] = self.reset_age.clone()
        for name, value in snapshot.items():
            if name not in self.metadata:
                self.metadata[name] = torch.zeros((t, *value.shape), dtype=value.dtype, device=value.device)
            self.metadata[name][step].copy_(value)
        self.seen.add(step)

    @torch.inference_mode()
    def _after_env_step(self, dones):
        if self.reset_age is not None:
            done = dones.detach().reshape(-1).to(self.reset_age.device).bool()
            if done.shape != self.reset_age.shape:
                raise ValueError("done shape differs from recorded env count")
            self.reset_age = torch.where(done, 0, self.reset_age + 1)

    def _begin_update(self):
        self.update_active = True
        self.current = None
        self.batch_count = self.step_count = 0
        self.complete_metadata = len(self.seen) == self.alg.storage.num_transitions_per_env
        self._emit("update_start", num_epochs=self.alg.num_learning_epochs,
                   num_mini_batches=self.alg.num_mini_batches)

    def _begin_minibatch(self, epoch, index, batch_idx, old_mu, old_sigma):
        if not self.update_active:
            raise ValueError("minibatch outside observed update")
        if self.current is not None:
            raise ValueError("previous minibatch was not completed")
        self.current = {"epoch": epoch, "minibatch": index, "indices": batch_idx.detach(),
                        "old_mu": old_mu.detach(), "old_sigma": old_sigma.detach(),
                        "lr_before": float(self.alg.learning_rate), "observed": False}
        self.batch_count += 1

    def _end_minibatch(self):
        current, self.current = self.current, None
        if current is not None and not current["observed"]:
            raise ValueError("minibatch had no optimizer pre-step observation")

    def _skipped_minibatch(self, epoch, index):
        self.batch_count += 1
        self._emit("minibatch", epoch=epoch, minibatch=index, status="skipped_no_optimizer_step",
                   valid_count=0, scheduler_kl_local_mean=None,
                   metadata_status="complete" if self.complete_metadata else "incomplete",
                   lr_before=float(self.alg.learning_rate), lr_after=float(self.alg.learning_rate),
                   schedule=self.alg.schedule, desired_kl=self.alg.desired_kl, top_kl_samples=[])

    def _optimizer_pre_step(self, optimizer, args, kwargs):
        if self.update_active:
            self.observe("record_optimizer_step")
        # Returning None leaves optimizer arguments and behavior unchanged.

    @torch.inference_mode()
    def _record_optimizer_step(self):
        c = self.current
        if c is None or c["observed"]:
            raise ValueError("missing or duplicate minibatch at optimizer pre-step")
        idx = c["indices"]
        n = idx.numel()
        if n:
            kl = scheduler_kl(c["old_mu"], c["old_sigma"],
                              self.alg.policy.action_mean, self.alg.policy.action_std)
            kl_dtype = str(kl.dtype)
            mean = _finite(kl.mean().item())
            finite = torch.isfinite(kl)
            finite_values = kl[finite]
            finite_ids = torch.nonzero(finite, as_tuple=False).flatten()
            top = finite_ids[torch.topk(finite_values, min(self.top_k, finite_ids.numel())).indices]
            nonfinite = torch.nonzero(~finite, as_tuple=False).flatten()
            samples = self._samples(idx[top], kl[top]) if self.complete_metadata else []
            bad_samples = self._samples(idx[nonfinite[:self.top_k]], kl[nonfinite[:self.top_k]]) if self.complete_metadata else []
            high = ((kl > 2 * self.alg.desired_kl) & finite) if self.alg.desired_kl is not None else None
            high_count = int(high.sum()) if high is not None else None
            max_kl = _finite(finite_values.max().item()) if finite_values.numel() else None
            nonfinite_count = int(nonfinite.numel())
        else:
            # Existing mirror-DDP empty slot contributes zero to its KL collective.
            mean, max_kl, high_count, nonfinite_count, samples, bad_samples = 0.0, None, 0, 0, [], []
            kl_dtype = str(torch.get_default_dtype())
        self._emit("minibatch", epoch=c["epoch"], minibatch=c["minibatch"], status="optimizer_step",
                   valid_count=n, scheduler_kl_local_mean=mean, scheduler_kl_local_max=max_kl,
                   kl_dtype=kl_dtype,
                   nonfinite_count=nonfinite_count, high_kl_count=high_count,
                   high_kl_definition="per-sample KL > 2 * desired_kl; diagnostic only",
                   metadata_status="complete" if self.complete_metadata else "incomplete",
                   lr_before=c["lr_before"], lr_after=float(self.alg.learning_rate),
                   optimizer_group_lrs=[float(g["lr"]) for g in self.alg.optimizer.param_groups],
                   schedule=self.alg.schedule, desired_kl=self.alg.desired_kl,
                   top_kl_samples=samples, nonfinite_samples=bad_samples)
        c["observed"] = True
        self.step_count += 1

    def _samples(self, flat_ids, values):
        ids = flat_ids.detach().cpu().tolist()
        selected = {name: tensor.flatten(0, 1)[flat_ids].cpu().tolist() for name, tensor in self.metadata.items()}
        values = values.detach().cpu().tolist()
        rows = []
        for i, flat_id in enumerate(ids):
            row = {name: selected[name][i] for name in selected}
            column, slot = int(row["terrain_column"]), int(row["command_slot"])
            row.update(flat_index=flat_id, env_id=flat_id % self.alg.storage.num_envs,
                       rollout_step=flat_id // self.alg.storage.num_envs, kl=_finite(values[i]),
                       map_mode=MAP_MODES[int(row["map_mode"])],
                       after_reset=row["reset_age_steps"] == 0,
                       command_slot_name=self.slots[slot] if 0 <= slot < len(self.slots) else None,
                       terrain_kind=self.columns[column].get("kind") if 0 <= column < len(self.columns) else None,
                       terrain_family=self.columns[column].get("family") if 0 <= column < len(self.columns) else None)
            rows.append(row)
        return rows

    def _end_update(self):
        expected = self.alg.num_learning_epochs * self.alg.num_mini_batches
        complete = (self.complete_metadata and not self.error_count and self.current is None
                    and self.batch_count == expected)
        self._emit("update_complete", status="complete" if complete else "incomplete",
                   minibatches_observed=self.batch_count, optimizer_steps_observed=self.step_count,
                   minibatches_expected=expected, errors=self.error_count)
        self.update_active = False

    def close(self):
        if not self.closed:
            self._handle.remove()
            self.alg.kl_audit = self.alg.storage.kl_audit = None
            self._stream.close()
            self.closed = True


def install_runner_kl_audit(runner, *, runtime, top_k=8):
    """Call once from EX42 runtime.attach_runner after runner/storage exist.

    pstate is created later by learn(), so it is read lazily just before act.
    Both ranks call this, including ranks with runner.disable_logs=True.
    """
    from foothold_s2.commands.mixed_core import EX39_SLOTS

    existing = getattr(runner.alg, "kl_audit", None)
    if existing is not None:
        return existing
    if runner.log_dir is None:
        raise ValueError("KL audit needs the run log directory on each rank")
    raw = getattr(runner.env, "unwrapped", runner.env)
    term = raw.command_manager.get_term("base_velocity")
    terrain = raw.scene.terrain
    columns = raw._ex42_column_table
    if not columns or any(not r.get("kind") for r in columns):
        raise ValueError("KL audit needs the EX42 named column table")
    # EX42 runtime.plan is an EX41 compatibility SimpleNamespace, not EX42Plan.
    # The actual pinned identifiers are direct runtime attributes.
    for name in ("plan_sha256", "parent_sha256"):
        value = getattr(runtime, name, None)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"KL audit needs runtime.{name} as the pinned SHA256")

    def provider():
        state = runner.pstate
        mode = torch.where(state.map_off.bool(), 2, torch.where(state.use_gt.bool(), 0, 1))
        return {"iteration": int(runtime.iteration), "command": term.command,
                "command_slot": term.slot_current, "terrain_column": terrain.terrain_types,
                "terrain_level": terrain.terrain_levels, "heading": term.heading, "flag": term.is_flag_env,
                "map_mode": mode, "episode_length": raw.episode_length_buf}

    return PpoKLAudit(runner.alg, provider, Path(runner.log_dir) / "ppo_kl_audit",
                      identity={"run": str(Path(runner.log_dir).resolve()),
                                "plan_sha256": runtime.plan_sha256, "parent_sha256": runtime.parent_sha256,
                                "stage_id": runtime.stage_id},
                      top_k=top_k, columns=columns, slots=EX39_SLOTS)


def join_rank_records(records):
    """Join rank files offline. Duplicate/missing rank rows stay incomplete."""
    grouped, updates = {}, {}
    for r in records:
        if r.get("event") not in ("minibatch", "update_start", "update_complete"):
            continue
        update_key = (json.dumps(r["identity"], sort_keys=True), r["iteration"])
        update = updates.setdefault(update_key, {"start": [], "end": [], "identity": r["identity"]})
        if r["event"] == "minibatch":
            key = (*update_key, r["epoch"], r["minibatch"])
            grouped.setdefault(key, []).append(r)
        else:
            update["start" if r["event"] == "update_start" else "end"].append(r)
    for update_key, update in updates.items():
        starts = update["start"]
        if starts:
            epochs, batches = starts[0]["num_epochs"], starts[0]["num_mini_batches"]
            if type(epochs) is not int or type(batches) is not int or min(epochs, batches) < 1 or epochs * batches > 100_000:
                raise ValueError("invalid minibatch inventory")
            # Even if BOTH rank files lost a batch, the expected slot remains visible.
            for epoch in range(epochs):
                for batch in range(batches):
                    grouped.setdefault((*update_key, epoch, batch), [])
    result = []
    for (identity_key, it, epoch, batch), rows in sorted(grouped.items()):
        update = updates[(identity_key, it)]
        starts, ends = update["start"], update["end"]
        world = (rows or starts)[0]["world_size"]
        inventory_ok = (len(starts) == len(ends) == world
                        and sorted(r["rank"] for r in starts) == sorted(r["rank"] for r in ends) == list(range(world))
                        and len({(r["num_epochs"], r["num_mini_batches"]) for r in starts}) == 1)
        if inventory_ok:
            expected = starts[0]["num_epochs"] * starts[0]["num_mini_batches"]
            sessions = {r["rank"]: r.get("session") for r in starts}
            inventory_ok = (epoch < starts[0]["num_epochs"] and batch < starts[0]["num_mini_batches"]
                            and min(epoch, batch) >= 0
                            and all(r.get("session") == sessions.get(r["rank"]) for r in rows + ends)
                            and all(r["status"] == "complete" and r["minibatches_observed"] == expected
                                    and r["minibatches_expected"] == expected for r in ends))
        complete = (inventory_ok and all(r["world_size"] == world for r in rows + starts + ends) and len(rows) == world
                    and sorted(r["rank"] for r in rows) == list(range(world))
                    and all(r.get("status") == "optimizer_step" and r.get("metadata_status") == "complete"
                            and r.get("scheduler_kl_local_mean") is not None for r in rows)
                    and len({(r["desired_kl"], r["schedule"], r.get("kl_dtype")) for r in rows}) == 1
                    and all(r.get("kl_dtype") in ("torch.float32", "torch.float64") for r in rows))
        mean_tensor = None
        if complete:
            dtype = torch.float32 if rows[0]["kl_dtype"] == "torch.float32" else torch.float64
            means = torch.tensor([r["scheduler_kl_local_mean"] for r in sorted(rows, key=lambda r: r["rank"])], dtype=dtype)
            mean_tensor = means.sum() / world
        mean = float(mean_tensor) if complete else None
        decision = "unavailable"
        if complete:
            desired = rows[0]["desired_kl"]
            decision = "unchanged"
            if desired is not None and rows[0]["schedule"] == "adaptive":
                if mean_tensor > desired * 2: decision = "decrease"
                elif 0 < mean_tensor < desired / 2: decision = "increase"
        equal_lr = (complete and len({r["lr_after"] for r in rows}) == 1
                    and len({r["lr_before"] for r in rows}) == 1
                    and all(r.get("optimizer_group_lrs") and all(x == r["lr_after"] for x in r["optimizer_group_lrs"])
                            for r in rows))
        if equal_lr:
            before, after = rows[0]["lr_before"], rows[0]["lr_after"]
            expected = (max(1e-5, before / 1.5) if decision == "decrease" else
                        min(1e-2, before * 1.5) if decision == "increase" else before)
            equal_lr = math.isclose(expected, after, rel_tol=2e-6, abs_tol=1e-10)
        result.append({"identity": update["identity"], "iteration": it, "epoch": epoch, "minibatch": batch,
                       "status": "complete" if complete else "incomplete",
                       "scheduler_kl_rank_mean": mean, "scheduler_decision": decision,
                       "lr_consistent": bool(equal_lr), "ranks_present": [r["rank"] for r in rows]})
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Join PPO KL rank JSONL files without running training")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    records = [json.loads(line) for p in args.inputs for line in p.read_text(encoding="utf-8").splitlines() if line]
    rows = join_rank_records(records)
    if not rows:
        parser.error("no minibatch evidence")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if all(r["status"] == "complete" and r["lr_consistent"] for r in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
