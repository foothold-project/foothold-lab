"""CPU-side EX-42 source, score, map, configuration, approval and batch gates."""
from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path
import subprocess
from typing import Any, Callable, Iterable


_GATE_SCHEMA_PATH = Path(__file__).with_name("curriculum") / "ex42_gate_schema.json"
_GATE_ID = re.compile(r"G[0-9]{2}")
_GATE_ROW_PREFIX = re.compile(r"G[^\s|]*", re.IGNORECASE)
_OPEN_MARKERS = ("없음 · 막음", "예행 대기", "미확인")

# Code-owned inventory. A command-line caller cannot narrow the locked files.
EX42_LOCKED_SOURCE_PATHS = (
    "experiments/EX-42.yaml",
    "foothold_s2/curriculum/ex42-prep.yaml",
    "foothold_s2/curriculum/ex42-boundary.yaml",
    "foothold_s2/curriculum/ex42-approvals.yaml",
    "foothold_s2/curriculum/ex42_gate_schema.json",
    "foothold_s2/curriculum/ex42_prep.py",
    "foothold_s2/curriculum/ex42_runtime.py",
    "foothold_s2/ex42_gate_checks.py",
    "foothold_s2/ex42_chain.py",
    "foothold_s2/ex42_score_watch.py",
    "foothold_s2/ex42_status.py",
    "foothold_s2/runners/start_runner.py",
    "foothold_s2/scripts/train_start.py",
    "foothold_s2/scripts/ex42_training_entry.py",
    "foothold_s2/scripts/ex42_ops.py",
)


def _load_gate_schema() -> tuple[str, ...]:
    try:
        schema = json.loads(_GATE_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"EX-42 gate schema unavailable: {exc}") from exc
    if not isinstance(schema, dict):
        raise ValueError("EX-42 gate schema must be a JSON object")
    rows = schema.get("required_rows")
    expected_rows = schema.get("expected_rows")
    ids = tuple(rows) if isinstance(rows, list) and all(isinstance(row, str) for row in rows) else ()
    if (schema.get("schema") != "foothold-ex42-gate-register/1"
            or expected_rows != 33 or len(ids) != expected_rows
            or len(set(ids)) != len(ids) or any(_GATE_ID.fullmatch(row) is None for row in ids)):
        raise ValueError("EX-42 gate schema is not the canonical 33-row register")
    return ids


try:
    REQUIRED_GATE_ROWS = _load_gate_schema()
except ValueError:
    # Keep imports usable so ops-check can report the schema failure as a blocker.
    REQUIRED_GATE_ROWS = ()


def open_gate_rows(path: str | Path) -> list[str]:
    """Read all canonical gate rows; absent, duplicate, open, or unregistered rows block."""
    required = _load_gate_schema()
    found: dict[str, list[str]] = {}
    malformed: set[str] = set()
    unregistered: set[str] = set()
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise ValueError(f"EX-42 gate report unavailable: {exc}") from exc
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or cells[0].lower() == "gate" or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        match = _GATE_ID.fullmatch(cells[0])
        if match is None:
            prefix = _GATE_ROW_PREFIX.match(cells[0])
            if prefix:
                unregistered.add("UNREGISTERED_" + re.sub(r"[^A-Za-z0-9]+", "_", prefix.group(0)).upper())
            continue
        row_id = match.group(0)
        if row_id not in required:
            unregistered.add(row_id)
        if len(cells) < 5:
            malformed.add(row_id)
            continue
        found.setdefault(row_id, []).append(cells[4])

    blockers = []
    for row_id in required:
        states = found.get(row_id, [])
        if len(states) != 1 or row_id in malformed or any(
                marker in states[0] for marker in _OPEN_MARKERS):
            blockers.append(row_id)
    blockers.extend(sorted(unregistered))
    return blockers


def locked_source_contract(*, launch_head: str, remote_head: str,
                           clean: bool, file_modes: dict[str, int],
                           file_sha256: dict[str, str], expected_sha256: dict[str, str]) -> dict[str, Any]:
    """Validate launch pin and immutable source inventory from measured git/file data."""
    if not launch_head or launch_head != remote_head:
        raise ValueError("EX-42 launch HEAD differs from remote HEAD")
    if clean is not True:
        raise ValueError("EX-42 locked source worktree is dirty")
    if set(file_modes) != set(expected_sha256) or set(file_sha256) != set(expected_sha256):
        raise ValueError("EX-42 locked source inventory differs")
    mismatched = sorted(name for name, expected in expected_sha256.items()
                        if file_sha256[name] != expected)
    if mismatched:
        raise ValueError("EX-42 locked source SHA differs: " + ",".join(mismatched))
    writable = sorted(name for name, mode in file_modes.items() if mode & stat.S_IWRITE)
    if writable:
        raise ValueError("EX-42 locked source has writable files: " + ",".join(writable))
    return {"launch_head": launch_head, "remote_head": remote_head,
            "clean": True, "writable_count": 0,
            "files": dict(sorted(file_sha256.items()))}


def audit_locked_checkout(root: str | Path, *, remote_ref: str,
                          protected_paths: Iterable[str]) -> dict[str, Any]:
    """Measure HEAD/remote/dirty state, readonly bits, and SHA for a fixed checkout."""
    root_path = Path(root).resolve(strict=True)
    def git(*args: str) -> str:
        result = subprocess.run(["git", "-C", str(root_path), *args], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", check=False)
        if result.returncode:
            raise ValueError("EX-42 lock audit git failure: " + result.stderr.strip())
        return result.stdout.strip()
    launch_head = git("rev-parse", "HEAD")
    remote_head = git("rev-parse", remote_ref)
    clean = not bool(git("status", "--porcelain=v1", "--untracked-files=all"))
    modes, shas = {}, {}
    expected = {}
    for relative in protected_paths:
        path = (root_path / relative).resolve(strict=True)
        if not path.is_relative_to(root_path):
            raise ValueError("EX-42 protected source path escapes checkout")
        modes[relative] = path.stat().st_mode
        shas[relative] = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        pinned = subprocess.run(["git", "-C", str(root_path), "show", f"{remote_ref}:{relative}"],
                                capture_output=True, check=False)
        if pinned.returncode:
            raise ValueError(f"EX-42 locked source missing from remote commit: {relative}")
        expected[relative] = hashlib.sha256(pinned.stdout.replace(b"\r\n", b"\n")).hexdigest()
    return locked_source_contract(launch_head=launch_head, remote_head=remote_head,
                                 clean=clean, file_modes=modes, file_sha256=shas,
                                 expected_sha256=expected)


def audit_ex42_launch_source(root: str | Path, *, remote_ref: str) -> dict[str, Any]:
    """Require the training caller's source root to be detached and lock-pinned."""
    if (not isinstance(remote_ref, str) or not remote_ref.startswith("origin/")
            or ".." in Path(remote_ref).parts):
        raise ValueError("EX-42 source lock must name an origin tracking ref")
    root_path = Path(root).resolve(strict=True)
    symbolic = subprocess.run(
        ["git", "-C", str(root_path), "symbolic-ref", "-q", "HEAD"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if symbolic.returncode == 0:
        raise ValueError("EX-42 source checkout must be detached and lock-pinned")
    if symbolic.returncode != 1:
        raise ValueError("EX-42 source checkout HEAD state is unreadable")
    result = audit_locked_checkout(
        root_path, remote_ref=remote_ref, protected_paths=EX42_LOCKED_SOURCE_PATHS)
    return {**result, "detached": True, "remote_ref": remote_ref,
            "protected_paths": list(EX42_LOCKED_SOURCE_PATHS)}


def verify_launch_argv(argv: list[str], *, python: str, isaac_cli: str,
                       expected_sha256: str) -> dict[str, Any]:
    """Check file presence and argv digest; this is not runtime/import evidence."""
    payload = {"python": python, "isaac_cli": isaac_cli, "argv": argv}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
    if not Path(python).is_file() or not Path(isaac_cli).is_file():
        raise ValueError("EX-42 selected Python or Isaac CLI is missing")
    if digest != expected_sha256:
        raise ValueError("EX-42 final argv hash differs")
    return {**payload, "argv_sha256": digest,
            "evidence_scope": "path_and_argv_digest_only",
            "runtime_import_verified": False,
            "new_output_sha256": None}


def launch_argv_sha256(argv: list[str], *, python: str, isaac_cli: str) -> str:
    payload = {"python": python, "isaac_cli": isaac_cli, "argv": argv}
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def checkpoint_ready(manifest: dict[str, Any], *, iteration: int,
                     checkpoint_exists: bool, checkpoint_sha256: str) -> bool:
    """Readiness depends on a named verified checkpoint, not delayed progress alone."""
    if type(iteration) is not int or iteration < 0 or not checkpoint_exists:
        return False
    checkpoints = manifest.get("checkpoints")
    return (isinstance(checkpoints, dict)
            and checkpoints.get(f"model_{iteration}.pt") == checkpoint_sha256
            and isinstance(checkpoint_sha256, str) and len(checkpoint_sha256) == 64)


def validate_score_pair(*, expected_iteration: int, score: dict[str, Any],
                        manifest: dict[str, Any], checkpoint_exists: bool,
                        checkpoint_sha256: str) -> None:
    """Reject stale PASS, corrupt newest evidence and N/N+1 identity mismatch."""
    if not checkpoint_ready(manifest, iteration=expected_iteration,
                            checkpoint_exists=checkpoint_exists,
                            checkpoint_sha256=checkpoint_sha256):
        raise ValueError("expected model_N checkpoint and SHA are not ready")
    if score.get("checkpoint_iteration") != expected_iteration:
        raise ValueError("score iteration is not the requested N checkpoint")
    if score.get("checkpoint_sha256") != checkpoint_sha256:
        raise ValueError("score checkpoint SHA differs")
    if score.get("state") != "complete":
        raise ValueError("latest score receipt is not complete")


def validate_map_matrix(expected: Iterable[tuple[str, str]], rows: Iterable[dict[str, Any]]) -> None:
    """Require every expected map-mode/command cell exactly once, with no extras."""
    expected_pairs = list(expected)
    actual_pairs = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("map_mode"), str) or not isinstance(row.get("command"), str):
            raise ValueError("map score row is missing mode or command")
        actual_pairs.append((row["map_mode"], row["command"]))
    if len(set(actual_pairs)) != len(actual_pairs) or set(actual_pairs) != set(expected_pairs):
        raise ValueError("map score matrix has missing, duplicate, or unexpected cells")


def extract_realized_config(env_yaml: str | Path, agent_yaml: str | Path) -> dict[str, Any]:
    """Return observed values only, with source file path per selected setting."""
    import yaml
    env_path, agent_path = Path(env_yaml), Path(agent_yaml)
    env = yaml.safe_load(env_path.read_text(encoding="utf-8-sig"))
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8-sig"))
    if not isinstance(env, dict) or not isinstance(agent, dict):
        raise ValueError("realized configuration inputs must be mappings")
    candidates = {
        "commands": (env, ("commands",)),
        "map_selection": (env, ("observations", "policy", "map_mode")),
        "domain_randomization": (env, ("events",)),
        "actuators": (env, ("scene", "robot", "actuators")),
        "rewards": (env, ("rewards",)),
        "level_cap": (env, ("curriculum", "terrain_levels")),
        "algorithm": (agent, ("algorithm",)),
    }
    out = {}
    for name, (doc, paths) in candidates.items():
        value: Any = doc
        for key in paths:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                value = None
                break
        out[name] = {"value": value, "source": str(env_path if doc is env else agent_path),
                     "observed": value is not None}
    return out


def validate_automatic_rule(*, rule: dict[str, Any], approval: dict[str, Any],
                            value: float, boundary: str) -> bool:
    """Only explicitly approved rule/value pairs may request automatic action."""
    key = rule.get("field")
    choices = rule.get("choices")
    permit = approval.get("fields", {}).get(key) if isinstance(approval, dict) else None
    if (not isinstance(key, str) or not isinstance(choices, list)
            or not isinstance(permit, dict) or permit.get("approved") is not True
            or permit.get("decision_id") != rule.get("decision_id")
            or not any(type(value) is type(choice) and value == choice for choice in choices)
            or boundary not in rule.get("boundaries", [])):
        raise ValueError("EX-42 automatic rule is missing a matching approved boundary choice")
    return True


def process_score_batch(rows: Iterable[Any], validate: Callable[[Any], Any],
                        *, reset: Callable[[], Any], alert: Callable[[str], None]) -> dict[str, Any]:
    """Keep valid rows from mixed batches; all-invalid and reset failures alert safely."""
    accepted, rejected = [], []
    for index, row in enumerate(rows):
        try:
            accepted.append(validate(row))
        except Exception as exc:
            rejected.append({"index": index, "error": f"{type(exc).__name__}: {exc}"})
    if not accepted:
        alert("EX42 batch has no valid rows")
        return {"accepted": [], "rejected": rejected, "state": "unknown"}
    try:
        reset()
    except Exception as exc:
        alert(f"EX42 batch reset failed: {type(exc).__name__}: {exc}")
        return {"accepted": accepted, "rejected": rejected, "state": "unknown"}
    return {"accepted": accepted, "rejected": rejected, "state": "partial" if rejected else "complete"}
