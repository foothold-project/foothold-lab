"""EX-42 boundary evaluation split over two GPUs.

Assignment, merge and comparison are CPU only. `run_shards` starts Kit children and is
only reached through `ex42_eval_once --execute --split-device`. The split changes where a
phase runs, never what it measures: every shard runs the same phase commands with a subset
of map modes, and the merged directory is then read by the unchanged `ex42_score.measure`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

from foothold_s2.ex42_score import MODES

PHASES = ("map64", "axis_v2", "stand")
# Rough seconds per (phase, one mode) from the E0 m250 one-GPU receipt (map64 497 s, axis_v2 340 s,
# three stand runs 46 s). Only used to balance two GPUs; an estimate, not a measurement of the split.
UNIT_SECONDS = {"map64": 166.0, "axis_v2": 113.0, "stand": 5.0}
# Keys that legitimately differ between shards (device, GPU identity, input-checkpoint preparation
# paths). Everything else that is not mode-keyed must be identical or the merge refuses.
LENIENT_KEYS = ("run_identity", "ex41_checkpoint_preparation")
IDENTITY_MUST_MATCH = ("checkpoint_sha256", "eval_seed", "torch", "torch_cuda", "code_head", "code_dirty_files")


def shard_tag(device):
    return str(device).replace(":", "")


def assign_shards(devices, modes=MODES):
    """Greedy longest-first balance of (phase, mode) units over the devices. Deterministic."""
    devices = list(devices)
    if len(devices) < 1 or len(set(devices)) != len(devices):
        raise ValueError("EX-42 split needs distinct devices")
    load = {device: 0.0 for device in devices}
    shard = {device: {phase: [] for phase in PHASES} for device in devices}
    for phase in PHASES:
        for mode in modes:
            device = min(devices, key=lambda d: (load[d], devices.index(d)))
            shard[device][phase].append(mode)
            load[device] += UNIT_SECONDS[phase]
    return shard, load


# Screen and remote-desktop sessions (this machine: sunshine 262 MiB per GPU; rustdesk --server ~600 MiB on GPU 0, 11/11) hold a compute context but are not the
# training or evaluation processes this wait is about; they never free up, so counting them blocks forever. Only these
# names are skipped, by basename. Everything else on the GPU still blocks, whatever its memory: a Kit or python
# process that has just started also uses little memory.
DISPLAY_PROCESS_NAMES = frozenset({"sunshine", "Xorg", "Xwayland", "gnome-shell", "gnome-remote-desktop-daemon", "rustdesk"})


def _gpu_busy_uuids(query=None):
    """gpu uuid -> [(pid, process basename, MiB)] of compute processes that are not display/streaming sessions."""
    if query is None:
        query = lambda: subprocess.check_output(
            ["nvidia-smi", "--query-compute-apps=pid,gpu_uuid,used_memory,process_name",
             "--format=csv,noheader,nounits"], text=True, timeout=20)
    busy = {}
    for line in query().splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) >= 2 and fields[0]:
            name = os.path.basename(fields[3]) if len(fields) >= 4 else ""
            if name in DISPLAY_PROCESS_NAMES:
                continue
            memory = fields[2] if len(fields) >= 3 else "?"
            busy.setdefault(fields[1].lower().removeprefix("gpu-"), []).append((fields[0], name or "?", memory))
    return busy


def all_gpu_uuids(query=None):
    """uuids of every GPU on the machine (the next stage trains on all of them)."""
    if query is None:
        query = lambda: subprocess.check_output(["nvidia-smi", "--query-gpu=uuid", "--format=csv,noheader"],
                                                text=True, timeout=20)
    uuids = [line.strip() for line in query().splitlines() if line.strip()]
    if not uuids:
        raise ValueError("EX-42 found no GPU uuid")
    return uuids


def wait_gpus_free(uuids, *, timeout_s=1800.0, poll_s=15.0, query=None, sleep=time.sleep,
                   clock=time.monotonic):
    """Training may still be releasing its GPUs when the queue starts this job: wait, never overlap."""
    wanted = [uuid.lower().removeprefix("gpu-") for uuid in uuids]
    deadline = clock() + timeout_s
    while True:
        busy = _gpu_busy_uuids(query)
        holders = {uuid: busy[uuid] for uuid in wanted if uuid in busy}
        if not holders:
            return
        if clock() >= deadline:
            raise ValueError(f"EX-42 split evaluation GPUs still hold compute processes: {holders}")
        sleep(poll_s)


# ---- merge -----------------------------------------------------------------------------------
def _sort_modes(value):
    if isinstance(value, dict) and value and set(value) <= set(MODES):
        return {mode: value[mode] for mode in MODES if mode in value}
    return value


def merge_docs(docs, *, label):
    """Union the mode-keyed parts of per-shard result JSON; everything else must agree."""
    docs = list(docs)
    if not docs:
        raise ValueError(f"EX-42 {label}: nothing to merge")
    merged, lenient_differences = {}, []
    for key in docs[0]:
        values = [doc[key] for doc in docs if key in doc]
        if len(values) != len(docs):
            raise ValueError(f"EX-42 {label}: key {key!r} is missing from a shard")
        if all(value == values[0] for value in values):
            merged[key] = values[0]
        elif all(isinstance(value, dict) for value in values) and sum(map(len, values)) == len(
                {k for value in values for k in value}):
            merged[key] = _sort_modes({k: v for value in values for k, v in value.items()})
        elif key in LENIENT_KEYS:
            merged[key] = values[0]
            lenient_differences.append(key)
        else:
            raise ValueError(f"EX-42 {label}: shards disagree on {key!r}")
    for doc in docs[1:]:
        if set(doc) != set(docs[0]):
            raise ValueError(f"EX-42 {label}: shards have different keys")
    identities = [doc.get("run_identity") or {} for doc in docs]
    for field in IDENTITY_MUST_MATCH:
        if len({json.dumps(identity.get(field), sort_keys=True) for identity in identities}) > 1:
            raise ValueError(f"EX-42 {label}: shard run_identity differs on {field}")
    merged["run_identity_shards"] = identities
    return merged, lenient_differences


def _copy_files(src, dst, skip):
    for path in sorted(Path(src).iterdir()):
        if path.name in skip:
            continue
        target = Path(dst) / path.name
        if target.exists():
            raise ValueError(f"EX-42 split merge: {target} would be overwritten")
        (shutil.copytree if path.is_dir() else shutil.copy2)(path, target)


def merge_shards(output, shard_dirs):
    """Build output/{map64,axis_v2,stand_*} from shard directories; returns a receipt dict."""
    output = Path(output)
    receipt = {"format": "foothold-ex42-split-merge/1", "shards": [str(p) for p in shard_dirs],
               "phases": {}}
    for phase, filename in (("map64", "map_modes.json"), ("axis_v2", "axis_v2.json")):
        folders = [Path(d) / phase for d in shard_dirs if (Path(d) / phase / filename).is_file()]
        if not folders:
            raise ValueError(f"EX-42 split merge: no shard produced {phase}")
        docs = [json.loads((f / filename).read_text(encoding="utf-8-sig")) for f in folders]
        seen = [mode for doc in docs for mode in doc.get("modes", {})]
        if sorted(seen) != sorted(MODES):
            raise ValueError(f"EX-42 split merge: {phase} modes {sorted(seen)} do not cover {sorted(MODES)} exactly once")
        merged, lenient = merge_docs(docs, label=phase)
        target = output / phase
        target.mkdir(parents=True, exist_ok=False)
        for folder in folders:
            _copy_files(folder, target, skip={filename})
        tmp = target / (filename + ".tmp")
        tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(tmp, target / filename)
        receipt["phases"][phase] = {"from": [str(f) for f in folders], "lenient_differences": lenient}
    for mode in MODES:
        sources = [Path(d) / f"stand_{mode}" for d in shard_dirs if (Path(d) / f"stand_{mode}" / "stand.json").is_file()]
        if len(sources) != 1:
            raise ValueError(f"EX-42 split merge: stand_{mode} must come from exactly one shard, found {len(sources)}")
        shutil.copytree(sources[0], output / f"stand_{mode}")
        receipt["phases"][f"stand_{mode}"] = {"from": [str(sources[0])]}
    return receipt


# ---- Kit shards ------------------------------------------------------------------------------
def run_shards(plan, *, output, commands_for, env, physical, process, observed, record):
    """Run every device's phases in its own thread. `plan` maps device -> {phase: [modes]}.

    commands_for(device, shard, out_dir) -> list of {"name", "argv"}; `record(step_key, child)` stores
    the receipt step. Returns the list of failed step keys (empty means every phase is durable).
    """
    failed, stop = [], threading.Event()

    def worker(device, shard):
        out = Path(output) / "shards" / shard_tag(device)
        out.mkdir(parents=True, exist_ok=False)
        for phase in commands_for(device, shard, out):
            name = phase["name"]
            key = f"{name}@{device}"
            if stop.is_set():
                return
            process.prepare_phase_output(phase["argv"])
            child = process.hidden_child(phase["argv"], out / "children" / name, env=env)
            child = process.reconcile_child_result(name, child, out / name)
            if child.get("state") == "done":
                try:
                    child["observed_gpu"] = observed(out, name, physical[device])
                except (OSError, ValueError, KeyError) as exc:
                    child.update(state="HOLD", gpu_identity_error=str(exc))
            record(key, child)
            if child.get("state") != "done":
                failed.append(key)
                stop.set()
                return

    threads = [threading.Thread(target=worker, args=(device, shard), name=f"ex42-split-{shard_tag(device)}")
               for device, shard in plan.items()]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return failed


# ---- comparison with a one-GPU run -------------------------------------------------------------
# paths differ with the output directory; maintenance_source_sha256 is the hash of a source file that moves
# with the code head, not a measurement
IGNORED_COMPARE_KEYS = ("checkpoint", "raw_file", "maintenance_source_sha256")


MEASURED_KEYS = ("conditions", "map64", "stand", "axis_v2")


def compare_measurements(a, b):
    """Compare only what Kit measured (conditions and the map64 / stand / axis_v2 cells). Judgement, baseline and
    maintenance fields come from the scoring code at hand, which may differ from the code that wrote the other file."""
    return compare_scores({k: a.get(k) for k in MEASURED_KEYS}, {k: b.get(k) for k in MEASURED_KEYS})


def compare_scores(a, b, *, path="", out=None):
    """Exact structural comparison of two ex42_score.json documents. Returns a list of differences."""
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key in IGNORED_COMPARE_KEYS:
                continue
            if key not in a or key not in b:
                out.append({"path": f"{path}/{key}", "only_in": "a" if key in a else "b"})
            else:
                compare_scores(a[key], b[key], path=f"{path}/{key}", out=out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for index, (x, y) in enumerate(zip(a, b)):
            compare_scores(x, y, path=f"{path}[{index}]", out=out)
    elif a != b:
        row = {"path": path, "a": a, "b": b}
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
            row["abs_diff"] = abs(a - b)
        out.append(row)
    return out


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="EX-42 split evaluation helpers (CPU only)")
    sub = parser.add_subparsers(dest="command", required=True)
    cmp_ = sub.add_parser("compare", help="compare two ex42_score.json files; exit 1 when they differ")
    cmp_.add_argument("a", type=Path)
    cmp_.add_argument("b", type=Path)
    cmp_.add_argument("--limit", type=int, default=50)
    cmp_.add_argument("--all-fields", action="store_true", help="also compare judgement and baseline fields")
    args = parser.parse_args(argv)
    docs = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (args.a, args.b)]
    diffs = compare_scores(*docs) if args.all_fields else compare_measurements(*docs)
    print(json.dumps({"fields": "all" if args.all_fields else "measured", "state": "same" if not diffs else "differs", "count": len(diffs),
                      "differences": diffs[:args.limit]}, ensure_ascii=False))
    return 0 if not diffs else 1


if __name__ == "__main__":
    raise SystemExit(main())
