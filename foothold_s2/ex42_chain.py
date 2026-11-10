"""CPU-testable EX-42 execution-chain adapters. This module never starts Kit."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, Callable

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.curriculum.ex42_runtime import EX42Runtime
from foothold_s2.ex42_score_watch import checkpoint_stage_context, read_transition_rows
from foothold_s2.ex42_status import read_status, write_status


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _validate_p1_score_command(argv: list[str], *, machine_profile: dict[str, Any],
                               iteration: int, checkpoint_path: Path) -> int:
    """Bind Linux P1 to the selected Python, real map evaluator, and profile GPU."""
    devices = machine_profile.get("devices", {})
    training = devices.get("training", {})
    p1 = devices.get("p1_evaluation", {})
    if training.get("device") != "cuda:0":
        raise ValueError("EX-42 P1 machine profile violates the cuda:0 training role")
    index = p1.get("cuda_index")
    if type(index) is not int or p1.get("device") != f"cuda:{index}":
        raise ValueError("EX-42 P1 machine profile device mapping is invalid")
    if machine_profile.get("machine_id") != "AI-WS01-linux":
        return index
    paths = machine_profile.get("paths", {})
    expected_python = paths.get("conda_python")
    if argv[0] != expected_python:
        raise ValueError("EX-42 Linux P1 must use machine-profile isaac311 Python")
    if argv[1:3] != ["-m", "foothold_s2.eval.eval_map_modes"]:
        raise ValueError("EX-42 Linux P1 must invoke the real map-mode evaluator module")

    def option(name: str) -> str:
        if argv.count(name) != 1:
            raise ValueError(f"EX-42 Linux P1 command requires exactly one {name}")
        offset = argv.index(name)
        if offset + 1 >= len(argv):
            raise ValueError(f"EX-42 Linux P1 command is missing the value for {name}")
        return argv[offset + 1]

    if option("--task") != "FootholdS2-Go2-S2-SB-v0":
        raise ValueError("EX-42 Linux P1 task differs from the approved stage-zero task")
    if Path(option("--checkpoint")).resolve() != checkpoint_path.resolve():
        raise ValueError("EX-42 Linux P1 command does not score this manifest-published checkpoint")
    output = option("--out")
    if not Path(output).is_absolute() or str(iteration) not in Path(output).name:
        raise ValueError("EX-42 Linux P1 output must be an iteration-specific absolute path")
    if option("--device") != p1["device"]:
        raise ValueError("EX-42 Linux P1 command device differs from the machine profile")
    if option("--envs") != "64" or option("--steps") != "300":
        raise ValueError("EX-42 Linux P1 must retain the 64-environment, 300-step map evaluation")
    if option("--modes") != "eval_gt,eval_pred,probe_prop_only":
        raise ValueError("EX-42 Linux P1 must score all three map modes")
    if "--headless" not in argv:
        raise ValueError("EX-42 Linux P1 must be headless")
    return index


class EX42TrainingChain:
    """Join pinned parent, approved transitions, score queue, W35, and receipts.

    The class is an integration boundary, not a launch authorization. Callers
    must provide their real score command; no default or fake evaluation is
    queued. The EX-42 plan and gate checks continue to block production launch.
    """

    def __init__(self, *, plan: EX42Plan, approvals_path: str | Path,
                 parent_manifest_path: str | Path, run_dir: str | Path,
                 repo_root: str | Path, queue_path: str | Path,
                 dispatch_path: str | Path | None = None,
                 alert_sender: Callable[[dict[str, Any]], Any] | None = None,
                 score_argv_factory: Callable[[int], list[str]] | None = None,
                 machine_profile: dict[str, Any] | None = None,
                 boundary_provider: Callable[[int, Any], dict[str, Any] | None] | None = None,
                 p1_interval: int = 250,
                 parent_pin: dict[str, Any] | None = None,
                 current_stage_id: str | None = None):
        self.plan = plan
        self.approvals_path = Path(approvals_path).resolve(strict=True)
        self.parent = plan.verify_parent_manifest(parent_manifest_path, parent_pin=parent_pin)
        self.run_dir = Path(run_dir)
        self.repo_root = Path(repo_root).resolve(strict=True)
        self.queue_path = Path(queue_path)
        self.dispatch_path = Path(dispatch_path or self.repo_root / "_out/tools/gpu_jobs/dispatch.py")
        self.alert_sender = alert_sender
        self.machine_profile = machine_profile
        if type(p1_interval) is not int or p1_interval <= 0:
            raise ValueError("EX-42 P1 interval must be a positive integer")
        self.score_argv_factory = score_argv_factory
        self.boundary_provider = boundary_provider
        self.p1_interval = p1_interval
        self.application_path = self.run_dir / "ex42_application.jsonl"
        self.status_path = self.run_dir / "train_start_status.json"
        self.alert_path = self.run_dir / "alerts.jsonl"
        self._queued_p1_keys: set[tuple[int, str]] = set()
        if self.application_path.is_file():
            self._queued_p1_keys = {
                (row["checkpoint_iteration"], row["checkpoint_sha256"])
                for row in read_transition_rows(self.application_path)
                if row.get("event") == "p1_queued"
                and type(row.get("checkpoint_iteration")) is int
                and isinstance(row.get("checkpoint_sha256"), str)
            }
        self.consumer = EX42Runtime.transition_consumer(
            plan, self.approvals_path, current_stage_id=current_stage_id)
        self._write_receipt("startup_receipt.json", {
            "state": "chain_ready_not_launch_authorized",
            "experiment": "EX-42",
            "plan_sha256": plan.sha256,
            "approval_decision_id": self.consumer.decision_id,
            "parent": self.parent,
            "production_launch_allowed": False,
        })

    @property
    def identity(self) -> dict[str, Any]:
        return {"experiment": "EX-42", "plan_sha256": self.plan.sha256,
                "parent_checkpoint_sha256": self.parent["checkpoint_sha256"]}

    def attach_runner(self, runner: Any) -> None:
        """Install hooks consumed by StartRunner without changing launch gates."""
        runner_dir = getattr(runner, "log_dir", None)
        if runner_dir is None or Path(runner_dir).resolve() != self.run_dir.resolve():
            raise ValueError("EX-42 chain and StartRunner must share one run directory")
        if self.score_argv_factory is None:
            raise ValueError("EX-42 runner hook requires the real score argv factory")
        runner.ex42_training_chain = self

    def on_runner_update_start(self, runner: Any, iteration: int) -> dict[str, Any] | None:
        """Apply an explicitly supplied stage boundary before that update's rollout."""
        if self.boundary_provider is None:
            if iteration == 0:
                self.record_runtime_config_snapshot(runner, iteration, boundary=None)
            return None
        boundary = self.boundary_provider(iteration, runner)
        if boundary is None:
            if iteration == 0:
                self.record_runtime_config_snapshot(runner, iteration, boundary=None)
            return None
        required = ("next_stage_id", "expected_score_iteration", "observed_score_iteration",
                    "checkpoint_sha256")
        if any(key not in boundary for key in required):
            raise ValueError("EX-42 boundary provider omitted required evidence")
        result = self.transition(
            runner.env, boundary["next_stage_id"], boundary_iteration=iteration,
            expected_score_iteration=boundary["expected_score_iteration"],
            observed_score_iteration=boundary["observed_score_iteration"],
            checkpoint_sha256=boundary["checkpoint_sha256"],
            runner=runner,
        )
        return result

    def record_runtime_config_snapshot(self, runner: Any, iteration: int, *,
                                       boundary: dict[str, Any] | None) -> dict[str, Any]:
        """Record active saved configs and runtime readbacks at n0/stage boundaries.

        This is observational evidence only. Missing fields remain unknown and
        reporting failures are isolated from the training update path.
        """
        from foothold_s2.ex42_gate_checks import extract_realized_config

        env_yaml = self.run_dir / "params" / "env.yaml"
        agent_yaml = self.run_dir / "params" / "agent.yaml"
        target_env = getattr(getattr(runner, "env", None), "unwrapped", getattr(runner, "env", None))
        stage_id = ((boundary or {}).get("stage_after")
                    or getattr(target_env, "_ex42_stage_id", None)
                    or self.consumer.current_stage_id)
        requested_stage = next((row for row in self.plan.runtime_stages
                                if row["id"] == stage_id), None)
        identity = {**self.identity, "event": "runtime_config_snapshot",
                    "iteration": iteration, "stage_id": stage_id,
                    "boundary_iteration": (boundary or {}).get("boundary_iteration")}
        try:
            if not env_yaml.is_file() or not agent_yaml.is_file():
                raise FileNotFoundError("EX-42 params/env.yaml or params/agent.yaml missing")
            observed = extract_realized_config(env_yaml, agent_yaml)
            missing = sorted(name for name, value in observed.items()
                             if value.get("observed") is not True)
            runtime_readback = {
                "stage_id": getattr(target_env, "_ex42_stage_id", None),
                "stage_config": getattr(target_env, "_ex42_stage_config", None),
                "dr_scale": getattr(target_env, "_ex40_dr_scale", None),
                "num_envs": getattr(getattr(runner, "env", None), "num_envs", None),
                "map_sampling": ({key: getattr(runner, "pcfg", {}).get(key)
                                  for key in ("force_gt", "p_map_off", "map_input")}
                                 if isinstance(getattr(runner, "pcfg", None), dict) else None),
            }
            row = {**identity, "state": "partial" if missing else "saved_configuration_snapshot",
                   "complete": False,
                   "config_sources": {
                       "env_yaml": {"path": str(env_yaml), "sha256": _sha(env_yaml)},
                       "agent_yaml": {"path": str(agent_yaml), "sha256": _sha(agent_yaml)},
                   },
                   "requested_stage_config": requested_stage,
                   "saved_active_config": observed,
                   "runtime_readback": runtime_readback,
                   "missing_saved_fields": missing,
                   "requested_realized_comparison": "not_verified",
                   "note": "saved params plus visible runtime fields only; unknowns are not filled from defaults"}
        except Exception as exc:
            row = {**identity, "state": "unknown", "complete": False,
                   "reason": f"{type(exc).__name__}: {exc}",
                   "requested_stage_config": requested_stage,
                   "requested_realized_comparison": "not_verified"}
        path = self.run_dir / "ex42_config_snapshots.jsonl"
        try:
            _append_jsonl(path, row)
            row["receipt"] = {"state": "written", "path": str(path)}
        except OSError as exc:
            row["receipt"] = {"state": "unknown", "retry": True,
                              "warning": f"{type(exc).__name__}: {exc}"}
        # A partial snapshot is useful evidence, not an operational failure.
        # Alert only when collection itself is unknown or persistence failed.
        if row["state"] == "unknown" or row["receipt"]["state"] != "written":
            row["alert_receipt"] = self._alert({**identity, "state": row["state"],
                                                "reason": row.get("reason", row.get("missing_saved_fields"))})
        return row

    def on_checkpoint_saved(self, runner: Any, iteration: int) -> dict[str, Any]:
        """Queue P1 only after StartRunner has saved and published model_N.

        Evaluation/dispatcher failures are receipts and alerts, never exceptions
        in the training loop. Checkpoint or manifest corruption is caught by the
        verifier before a job can enter the queue.
        """
        if iteration % self.p1_interval:
            return {"state": "not_due", "iteration": iteration}
        try:
            checkpoint_path = Path(runner.log_dir) / f"model_{iteration}.pt"
            digest = _sha(checkpoint_path)
            key = (iteration, digest)
            if key in self._queued_p1_keys:
                return {"state": "already_queued", "iteration": iteration,
                        "checkpoint_sha256": digest}
            argv = self.score_argv_factory(iteration) if self.score_argv_factory else None
            queued = self.register_checkpoint_p1(
                iteration=iteration, checkpoint_dir=runner.log_dir,
                score_argv=argv or [], application_log=self.application_path)
            return {"state": "queued", **queued}
        except Exception as exc:
            row = {**self.identity, "event": "p1_enqueue_failed",
                   "checkpoint_iteration": iteration,
                   "state": "collection_failed_retryable",
                   "retry_required": True,
                   "reason": f"{type(exc).__name__}: {exc}"}
            event = self._record_event(row)
            alert = self._alert(row)
            return {**row, "event_receipt": event, "alert_receipt": alert}

    def _write_receipt(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = write_status(self.run_dir / name, payload)
        return result

    def _record_event(self, row: dict[str, Any]) -> dict[str, Any]:
        try:
            _append_jsonl(self.application_path, {**self.identity, **row})
            return {"state": "written", "path": str(self.application_path)}
        except OSError as exc:
            return {"state": "unknown", "retry": True,
                    "warning": f"{type(exc).__name__}: {exc}",
                    "path": str(self.application_path)}

    def _alert(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = {**self.identity, **row}
        try:
            _append_jsonl(self.alert_path, payload)
        except OSError as exc:
            local = {"state": "unknown", "retry": True,
                     "warning": f"{type(exc).__name__}: {exc}"}
        else:
            local = {"state": "recorded", "path": str(self.alert_path)}
        if self.alert_sender is None:
            return {**local, "delivery": "not_configured"}
        try:
            sent = self.alert_sender(payload)
            return {**local, "delivery": "accepted", "sender_result": sent}
        except Exception as exc:  # reporting is isolated from the training path
            return {**local, "delivery": "unknown", "retry": True,
                    "warning": f"{type(exc).__name__}: {exc}"}

    def transition(self, env: Any, next_stage_id: str, *, boundary_iteration: int,
                   expected_score_iteration: int,
                   observed_score_iteration: int | None,
                   checkpoint_sha256: str, runner: Any = None) -> dict[str, Any]:
        """Apply only the next approved stage and keep missing scores as gaps."""
        if len(checkpoint_sha256) != 64 or any(c not in "0123456789abcdef" for c in checkpoint_sha256):
            raise ValueError("EX-42 boundary checkpoint SHA is required")
        row = self.consumer.transition(
            env, next_stage_id, boundary_iteration=boundary_iteration,
            expected_score_iteration=expected_score_iteration,
            observed_score_iteration=observed_score_iteration,
            runner=runner,
        )
        row = {**self.identity, "checkpoint_sha256": checkpoint_sha256,
               "score_checkpoint_iteration": expected_score_iteration, **row}
        event_result = self._record_event({"event": "stage_transition", **row})
        status_result = write_status(self.status_path, {
            **row, "state": "running", "transition_receipt": event_result,
        })
        if row["status"] == "measurement_gap":
            row["alert_receipt"] = self._alert({
                "event": "measurement_gap", "stage_id": next_stage_id,
                "boundary_iteration": boundary_iteration,
                "expected_score_iteration": expected_score_iteration,
                "observed_score_iteration": observed_score_iteration,
                "checkpoint_sha256": checkpoint_sha256,
            })
        row["status_receipt"] = status_result
        snapshot = self.record_runtime_config_snapshot(
            SimpleNamespace(env=env, log_dir=str(self.run_dir)), boundary=row,
            iteration=boundary_iteration)
        row["config_snapshot"] = snapshot
        return row

    def register_checkpoint_p1(self, *, iteration: int, checkpoint_dir: str | Path,
                               score_argv: list[str],
                               application_log: str | Path | None = None) -> dict[str, Any]:
        """Queue an exact, manifest-published checkpoint for priority-1 scoring."""
        checkpoint_dir = Path(checkpoint_dir).resolve(strict=True)
        manifest_path = checkpoint_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        checkpoint = checkpoint_dir / f"model_{iteration}.pt"
        checkpoint_sha = _sha(checkpoint) if checkpoint.is_file() else ""
        from foothold_s2.ex42_gate_checks import checkpoint_ready
        if not checkpoint_ready(manifest, iteration=iteration,
                                checkpoint_exists=checkpoint.is_file(),
                                checkpoint_sha256=checkpoint_sha):
            raise ValueError("EX-42 P1 requires the exact manifest-published model_N SHA")
        if not isinstance(score_argv, list) or not score_argv or any(
                not isinstance(arg, str) or not arg for arg in score_argv):
            raise ValueError("EX-42 P1 requires the real scoring command; no placeholder is allowed")
        p1_gpu = 1
        p1_gpu_uuid = None
        if self.machine_profile is not None:
            p1_gpu = _validate_p1_score_command(
                score_argv, machine_profile=self.machine_profile,
                iteration=iteration, checkpoint_path=checkpoint)
            p1_gpu_uuid = self.machine_profile["devices"]["p1_evaluation"]["uuid"]
        transition_path = Path(application_log) if application_log else self.application_path
        transitions = read_transition_rows(transition_path) if transition_path.is_file() else ()
        context = checkpoint_stage_context(
            self.plan, self.approvals_path, iteration, transition_rows=transitions)
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        spec = importlib.util.spec_from_file_location("ex42_chain_dispatch", self.dispatch_path)
        if spec is None or spec.loader is None:
            raise ValueError("EX-42 GPU dispatcher unavailable")
        dispatch = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = dispatch
        spec.loader.exec_module(dispatch)
        args = SimpleNamespace(
            qaction="add", title=f"EX-42 P1 model_{iteration} {checkpoint_sha[:12]}",
            priority=1, gpu=p1_gpu, owner="runner-ex42", cond="manifest SHA verified",
            start=None, end=None, needs_approval=False, kind="eval",
            argv_json=json.dumps(score_argv), cwd=str(self.repo_root),
            wait_absent=[], wait_pid=[], done_file=[],
        )
        message = dispatch.queue_cmd(args, {"queue": str(self.queue_path)})
        job_id = int(message.rsplit(" ", 1)[-1])
        self._queued_p1_keys.add((iteration, checkpoint_sha))
        event = {**self.identity, **context, "checkpoint_path": str(checkpoint),
                 "checkpoint_sha256": checkpoint_sha, "queue_id": job_id,
                 "queue_priority": 1, "queue_gpu": p1_gpu,
                 "queue_gpu_uuid": p1_gpu_uuid,
                 "queue_receipt": message, "state": "queued"}
        event_receipt = self._record_event({"event": "p1_queued", **event})
        event["event_receipt"] = event_receipt
        return event

    def record_p1_outcome(self, *, iteration: int, stage_id: str, checkpoint_sha256: str,
                          attempt: int, collection_state: str,
                          failure_reason: str | None = None,
                          score_path: str | Path | None = None,
                          score_sha256: str | None = None) -> dict[str, Any]:
        """Persist collection failures separately from completed score judgments.

        A technical collection failure remains retryable and is never promoted
        to a score HOLD. A completed, identity-matched score may legitimately
        contain a judgment HOLD and is then a completed measurement.
        """
        if type(iteration) is not int or iteration <= 0 or type(attempt) is not int or attempt <= 0:
            raise ValueError("EX-42 P1 iteration and attempt must be positive integers")
        if stage_id not in self.plan.runtime_stage_ids:
            raise ValueError("EX-42 P1 stage must be a stage from the pinned plan")
        if (len(checkpoint_sha256) != 64
                or any(c not in "0123456789abcdef" for c in checkpoint_sha256)):
            raise ValueError("EX-42 P1 checkpoint SHA is required")
        base = {**self.identity, "checkpoint_sha256": checkpoint_sha256,
                "checkpoint_iteration": iteration,
                "stage_id": stage_id,
                "attempt": attempt}
        if collection_state == "failed":
            if not isinstance(failure_reason, str) or not failure_reason.strip():
                raise ValueError("EX-42 P1 collection failure requires a reason")
            result = {**base, "state": "collection_failed_retryable",
                      "retry_required": True, "failure_reason": failure_reason}
        elif collection_state == "complete":
            if failure_reason is not None or score_path is None or score_sha256 is None:
                raise ValueError("EX-42 completed P1 requires score artifact evidence")
            path = Path(score_path).resolve(strict=True)
            if _sha(path) != score_sha256:
                raise ValueError("EX-42 P1 score artifact SHA differs")
            score = json.loads(path.read_text(encoding="utf-8-sig"))
            if score.get("state", "complete") != "complete":
                raise ValueError("EX-42 P1 score measurement is not complete")
            checkpoint = self.run_dir / f"model_{iteration}.pt"
            manifest = json.loads((self.run_dir / "manifest.json").read_text(encoding="utf-8-sig"))
            checkpoint_sha = _sha(checkpoint) if checkpoint.is_file() else ""
            from foothold_s2.ex42_gate_checks import validate_ex42_map_score, validate_score_pair
            validate_score_pair(
                expected_iteration=iteration,
                score={**score, "state": "complete"},
                manifest=manifest,
                checkpoint_exists=checkpoint.is_file(),
                checkpoint_sha256=checkpoint_sha,
            )
            validate_ex42_map_score(score, self.plan.document["evaluation"]["map_modes"])
            expected = {"checkpoint_sha256": checkpoint_sha256,
                        "checkpoint_iteration": iteration,
                        "plan_sha256": self.plan.sha256,
                        "stage_id": stage_id}
            if any(score.get(key) != value for key, value in expected.items()):
                raise ValueError("EX-42 P1 score artifact identity differs")
            judgment = score.get("judgment")
            if judgment not in {"PASS", "HOLD"}:
                raise ValueError("EX-42 P1 score judgment must be PASS or HOLD")
            result = {**base, "state": "judgment_hold" if judgment == "HOLD" else "scored",
                      "retry_required": False, "judgment": judgment,
                      "score_path": str(path), "score_sha256": score_sha256}
        else:
            raise ValueError("EX-42 P1 collection state must be failed or complete")
        receipt = self.run_dir / "p1_receipts" / f"model_{iteration}_{checkpoint_sha256[:12]}" / f"attempt_{attempt:04d}.json"
        result["receipt"] = self._write_new_receipt(receipt, result)
        self._record_event({"event": "p1_outcome", **result})
        return result

    @staticmethod
    def _write_new_receipt(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        return {"state": "written", "path": str(path)}

    def run_w35_components(self, *, stage_id: str, checkpoint_sha256: str, local_iteration: int,
                           number: dict[str, Any], terrain: dict[str, Any],
                           w78: dict[str, Any], sample: dict[str, Any],
                           delivery: dict[str, Any]) -> dict[str, Any]:
        """Call all five W35 consumers independently and persist per-component outcomes."""
        from foothold_s2.eval import ex42_component_receipts as component
        from foothold_s2.eval import ex42_terrain_evidence as terrain_evidence
        from foothold_s2.eval import ex42_w78_gate as w78_gate
        from foothold_s2.eval import ex42_video_sample as video_sample
        from foothold_s2.eval import ex42_video_delivery as video_delivery

        if stage_id not in self.plan.runtime_stage_ids:
            raise ValueError("EX-42 W35 stage must be a stage from the pinned plan")

        def require_identity(name: str, value: dict[str, Any], *,
                             checkpoint_key: str = "checkpoint_sha256",
                             stage_key: str = "stage_name",
                             iteration_key: str | None = None) -> None:
            if not isinstance(value, dict):
                raise ValueError(f"{name} input must be an object")
            expected = {
                checkpoint_key: checkpoint_sha256,
                "plan_sha256": self.plan.sha256,
                stage_key: stage_id,
            }
            if iteration_key:
                expected[iteration_key] = local_iteration
            mismatches = [key for key, wanted in expected.items()
                          if value.get(key) != wanted]
            if mismatches:
                raise ValueError(f"{name} identity mismatch: {', '.join(mismatches)}")

        def number_call():
            receipt = number["receipt"]
            require_identity("number", receipt)
            return component.register_number(
                self.run_dir / "components" / "number", receipt)

        def terrain_call():
            require_identity("terrain", terrain.get("identity", {}))
            return terrain_evidence.verify_raw_terrain(
                Path(terrain["review_json"]), Path(terrain["raw_npz"]), terrain["selection"])

        def w78_call():
            full = w78["full"]
            require_identity("W78 full", full, stage_key="stage_name",
                             iteration_key="checkpoint_iter")
            for unit in w78["units"]:
                require_identity("W78 unit", unit, stage_key="stage_name",
                                 iteration_key="checkpoint_iter")
            return {
                "comparison": w78_gate.compare_split(
                    full, w78["units"], repeats=w78.get("repeats", ())),
                "queue_admission": w78_gate.unit_queue_admission(
                    w78["queue"], w78["unit_id"]),
            }

        def sample_call():
            require_identity("video sample plan", sample["plan"])
            return video_sample.bulk_registration_allowed(
                sample["plan"], sample["receipt"], sample["approval"],
                loader_sha256=sample["loader_sha256"],
                composer_sha256=sample["composer_sha256"])

        def delivery_call():
            require_identity("video delivery plan", delivery["plan"])
            return video_delivery.validate_delivery(
                delivery["plan"], delivery["receipts"], Path(delivery["playlist"]),
                loader_sha256=delivery["loader_sha256"],
                composer_sha256=delivery["composer_sha256"],
                sample_approval=delivery.get("sample_approval"))

        calls: list[tuple[str, Callable[[], Any]]] = [
            ("number", number_call),
            ("terrain", terrain_call),
            ("w78", w78_call),
            ("video_sample", sample_call),
            ("video_delivery", delivery_call),
        ]
        results: dict[str, Any] = {}
        for name, call in calls:
            try:
                value = call()
                state = value.get("state") if isinstance(value, dict) else (
                    "PASS" if value is True or isinstance(value, Path) else "HOLD")
                if state is None and name == "w78":
                    state = ("PASS" if value["comparison"].get("state") == "PASS"
                             and value["queue_admission"].get("state") == "eligible" else "HOLD")
                if state is None:
                    state = "PASS" if name in {"number", "terrain"} else "HOLD"
                result = {"state": state, "result": str(value) if isinstance(value, Path) else value}
            except Exception as exc:
                result = {"state": "unknown", "reason": f"{type(exc).__name__}: {exc}"}
            row = {**self.identity, "checkpoint_sha256": checkpoint_sha256,
                   "checkpoint_iteration": local_iteration, "component": name,
                   "stage_id": stage_id, **result}
            persisted = self._write_receipt(f"components/{name}.json", row)
            row["receipt"] = persisted
            results[name] = row
            self._record_event({"event": "component_result", **row})
            if row["state"] in {"unknown", "HOLD", "FAIL"}:
                row["alert_receipt"] = self._alert({
                    "event": "component_unavailable", "component": name,
                    "state": row["state"], "stage_id": row["stage_id"],
                })
        return results

    def stage_report(self, *, stage_id: str, boundary_iteration: int,
                     checkpoint_sha256: str) -> dict[str, Any]:
        required = ("number", "terrain", "w78", "video_sample", "video_delivery")
        states: dict[str, str] = {}
        for name in required:
            stored = read_status(self.run_dir / "components" / f"{name}.json")
            value = stored.get("value", {})
            if (stored.get("state") != "read"
                    or value.get("checkpoint_sha256") != checkpoint_sha256
                    or value.get("plan_sha256") != self.plan.sha256
                    or value.get("stage_id") != stage_id
                    or value.get("checkpoint_iteration") != boundary_iteration):
                states[name] = "MISSING_OR_MISMATCHED"
            else:
                states[name] = value.get("state", "UNKNOWN")
        complete = all(value in {"PASS", "ready", "eligible", "complete"}
                       for value in states.values())
        payload = {
            **self.identity, "checkpoint_sha256": checkpoint_sha256,
            "stage_id": stage_id, "boundary_iteration": boundary_iteration,
            "local_iteration": boundary_iteration,
            "component_states": states,
            "state": "complete" if complete else "incomplete",
            "training_action": "none",
        }
        self._record_event({"event": "stage_report", **payload})
        payload["receipt"] = self._write_receipt(
            f"stage_reports/{stage_id}_{boundary_iteration}.json", payload)
        return payload
