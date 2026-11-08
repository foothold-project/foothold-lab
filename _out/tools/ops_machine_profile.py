"""One opt-in Linux path profile for the lead operations tools.

The Windows launch contract is unchanged. The runner's machine profile and
this operations profile are selected separately; neither loads the other's
runtime dependencies.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

PROFILE_ENV = "FOOTHOLD_OPS_MACHINE_PROFILE"
PROFILE_PIN_ENV = "FOOTHOLD_OPS_PROFILE_SHA256"
REQUIRED = (
    "gpu_root", "c_layer_priority", "c_layer_ledger", "stage_table",
    "eval_root", "c_layer_manifest", "c_layer_out", "w78_video",
    "p1_attempt_glob", "worklist", "baseline_m6000", "canon_retry",
)


def load_linux_profile() -> dict | None:
    selected = os.environ.get(PROFILE_ENV)
    if os.name == "nt" or not selected:
        return None
    profile = Path(selected).expanduser()
    if not profile.is_absolute():
        raise ValueError(f"{PROFILE_ENV} must be an absolute path")
    profile = profile.resolve()
    raw_profile = profile.read_bytes()
    digest = hashlib.sha256(raw_profile).hexdigest()
    expected = os.environ.get(PROFILE_PIN_ENV)
    if expected is not None and digest != expected:
        raise ValueError("operations profile changed since wrapper launch was configured")
    doc = json.loads(raw_profile.decode("utf-8-sig"))
    if (not isinstance(doc, dict) or doc.get("format") != "foothold-ops-machine-profile/1"
            or doc.get("platform") != "linux" or not isinstance(doc.get("paths"), dict)):
        raise ValueError("invalid Linux operations machine profile")
    paths = {}
    for key in REQUIRED:
        raw = doc["paths"].get(key)
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"Linux operations profile missing paths.{key}")
        path = Path(raw).expanduser()
        if not path.is_absolute() or path.anchor != "/" or "\\" in raw or ".." in path.parts:
            raise ValueError(f"Linux operations profile needs a native absolute path: {key}")
        paths[key] = str(path)
    handles = doc.get("worker_handles", {})
    if not isinstance(handles, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) or not v.startswith("term_")
        for k, v in handles.items()
    ):
        raise ValueError("invalid worker_handles in Linux operations profile")
    mailbox = doc.get("lead_mailbox")
    if mailbox is not None and (not isinstance(mailbox, str) or not mailbox.startswith("run:")
                                or len(mailbox) <= 4):
        raise ValueError("lead_mailbox must be a run: mailbox or null")
    return {"paths": paths, "worker_handles": handles, "lead_mailbox": mailbox,
            "file": str(profile), "sha256": digest}


def require_linux_profile(profile: dict | None) -> None:
    if os.name != "nt" and profile is None:
        raise SystemExit(f"Set {PROFILE_ENV} to a Linux operations machine profile")


def gpu_path(profile: dict, name: str) -> str:
    return str(Path(profile["paths"]["gpu_root"]) / name)


def orca_executable() -> str:
    return os.environ.get("ORCA_CLI_COMMAND") or "orca-ide"


def bind_registry(config: dict, profile: dict | None) -> dict:
    """Bind bundled v2 registry paths without changing its Windows JSON contract."""
    if profile is None or config.get("schema") != "foothold-gpu-jobs-v2":
        return config
    marker = gpu_path(profile, "PRIORITY_BUSY_GPU1")
    outputs = {"ex41-eval": marker, "c-layer": profile["paths"]["c_layer_out"],
               "w78-video": profile["paths"]["w78_video"]}
    jobs = [dict(job, output_path=outputs[job["id"]]) if job["id"] in outputs else job
            for job in config["jobs"]]
    return dict(config, jobs=jobs,
                sources=dict(config.get("sources", {}), ex41_p1_marker=marker))
