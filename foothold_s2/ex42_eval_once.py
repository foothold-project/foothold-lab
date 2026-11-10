"""EX-42 maintenance evaluator. Plan is CPU only; --execute starts Kit children."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from foothold_s2.ex42_score import MODES, config, digest, measure
from foothold_s2.experiment_registry import load_experiment, device_contract, queue_gpu_identity
from foothold_s2.machine_profile import machine_path

ROOT = Path(__file__).resolve().parents[1]


def commands(checkpoint, output, device, cfg=None):
    cfg = cfg or config()[0]
    queue_gpu_identity(device)  # Only the two registered physical GPU ordinals are supported.
    common = ["--task", cfg["task"], "--checkpoint", str(checkpoint),
              "--envs", str(cfg["envs"])]
    maps = [*common, "--modes", ",".join(MODES), "--fixed-terrain",
            "--eval-seed", str(cfg["eval_seed"])]
    kit = ["--headless", f"--kit_args=--/UJITSO/datastore/localCachePath={machine_path('isaac_cache_root')}"]
    rows = [("map64", "foothold_s2.eval.eval_map_modes", [*maps, "--steps", str(cfg["steps"]),
             "--command-suite", "extended", "--commands", "all"])]
    for mode in MODES:
        rows.append((f"stand_{mode}", "foothold_s2.eval.ex40_stand_eval",
                     [*common, "--mode", mode, "--seconds", str(cfg["stand_seconds"]),
                      "--skip-seconds", str(cfg["stand_skip_seconds"]),
                      "--contact-n", str(cfg["stand_contact_n"]),
                      "--seed", str(cfg["eval_seed"])]))
    rows.append(("axis_v2", "foothold_s2.eval.eval_map_modes",
                 [*maps, "--axis-v2", "--ex42-maintenance", "--fixed-level",
                  str(cfg["axis_fixed_level"]), "--terrain-set", "default",
                  "--steps", str(cfg["steps"])]))
    return [{"name": name, "device": device,
             "argv": [str(machine_path("conda_python")), "-m", module, *args, "--out", str(Path(output) / name),
                      "--device", device, *kit]} for name, module, args in rows]


def _atomic(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def gpu_identity(device, *, query=None):
    """Check the PCI-ordered physical ordinal before Kit starts; no CUDA context is made."""
    index, registered_uuid = queue_gpu_identity(device)
    if query is None:
        query = lambda: subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index,uuid,pci.bus_id", "--format=csv,noheader,nounits"],
            text=True, timeout=20)
    rows = {}
    for line in query().splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 3:
            raise ValueError("nvidia-smi GPU identity row malformed")
        rows[int(fields[0])] = {"gpu_uuid": fields[1], "pci_bus_id": fields[2]}
    actual = rows.get(index)
    if not actual or actual["gpu_uuid"].lower().removeprefix("gpu-") != registered_uuid.lower():
        raise ValueError(f"EX-42 {device} physical GPU UUID differs from registry")
    return {"device": device, "gpu_index": index, **actual}


def child_env(parent=None):
    env = dict(os.environ if parent is None else parent)
    env.pop("CUDA_VISIBLE_DEVICES", None)
    env.update(PYTHONPATH=str(ROOT), CUDA_DEVICE_ORDER="PCI_BUS_ID", PYTHONUNBUFFERED="1",
               KMP_DUPLICATE_LIB_OK="TRUE", OMNI_KIT_ACCEPT_EULA="YES")
    return env


def receipt_device_fields(device, physical_gpu):
    registered = device_contract(load_experiment("EX-42"))["evaluation"]
    fields = {"device": device, "registered_evaluation_device": registered,
              "physical_gpu": physical_gpu}
    if device != registered:
        fields["device_override"] = {"registered": registered, "used": device}
    return fields


def observed_child_identity(output, name, expected):
    """Verify Kit's own CUDA identity where its result exports one."""
    basename = "map_modes.json" if name == "map64" else "axis_v2.json" if name == "axis_v2" else "stand.json"
    path = Path(output) / name / basename
    row = json.loads(path.read_text(encoding="utf-8-sig"))
    identity = row.get("run_identity") or {}
    observed = identity.get("gpu_uuid")
    if identity.get("device") != expected["device"] or observed in (None, "", "None"):
        raise ValueError(f"{name} Kit device identity missing")
    if str(observed).lower().removeprefix("gpu-") != expected["gpu_uuid"].lower().removeprefix("gpu-"):
        raise ValueError(f"{name} Kit physical GPU UUID differs from preflight")
    return {"device": identity["device"], "gpu_uuid": observed}


def run(checkpoint, expected_sha256, output, device):
    from foothold_s2 import ex41_eval_once as process
    checkpoint, output = Path(checkpoint).resolve(strict=True), Path(output).resolve()
    if digest(checkpoint) != expected_sha256:
        raise ValueError("EX-42 checkpoint SHA differs")
    if output.exists():
        raise ValueError("EX-42 evaluation requires fresh output directory")
    if Path(sys.executable).resolve() != machine_path("conda_python").resolve():
        raise ValueError("EX-42 Kit requires configured isaac311 Python")
    if subprocess.check_output(["git", "status", "--short", "--", "foothold_s2", "experiments/EX-42.yaml"],
                               cwd=ROOT, text=True).strip():
        raise ValueError("EX-42 evaluator source must be committed before execution")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    physical_gpu = gpu_identity(device)
    output.mkdir(parents=True)
    cfg, cfg_path = config()
    row = {"format": "foothold-ex42-eval/1", "state": "running", "source_git_head": head,
           "checkpoint": str(checkpoint), "checkpoint_sha256": expected_sha256,
           "score_config_sha256": digest(cfg_path), "steps": {},
           **receipt_device_fields(device, physical_gpu)}
    _atomic(output / "eval_receipt.json", row)
    env = child_env()
    row["child_cuda_visible_devices"] = None
    row["child_cuda_device_order"] = env["CUDA_DEVICE_ORDER"]
    row["parent_cuda_visible_devices"] = os.environ.get("CUDA_VISIBLE_DEVICES")
    _atomic(output / "eval_receipt.json", row)
    for phase in commands(checkpoint, output, device, cfg):
        name = phase["name"]
        process.prepare_phase_output(phase["argv"])
        child = process.hidden_child(phase["argv"], output / "children" / name, env=env)
        child = process.reconcile_child_result(name, child, output / name)
        if child.get("state") == "done":
            try:
                child["observed_gpu"] = observed_child_identity(output, name, physical_gpu)
            except (OSError, ValueError, KeyError) as exc:
                child.update(state="HOLD", gpu_identity_error=str(exc))
        row["steps"][name] = child
        _atomic(output / "eval_receipt.json", row)
        if child.get("state") != "done":
            row.update(state="HOLD", reason=f"{name} failed or lacks durable receipt")
            _atomic(output / "eval_receipt.json", row)
            return 5
    try:
        score = measure(checkpoint, output)
        _atomic(output / "ex42_score.json", score)
        row.update(state="done", score=str(output / "ex42_score.json"), judgement="HOLD")
    except (ValueError, KeyError, OSError) as exc:
        row.update(state="HOLD", reason=f"EX-42 evidence invalid: {exc}")
    _atomic(output / "eval_receipt.json", row)
    return 0 if row["state"] == "done" else 5


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", choices=("cuda:0", "cuda:1"), required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--score-existing", action="store_true")
    args = parser.parse_args(argv)
    if args.execute and args.score_existing:
        parser.error("select either --execute or --score-existing")
    if not args.checkpoint.is_file() or digest(args.checkpoint) != args.expected_sha256:
        parser.error("checkpoint missing or SHA differs")
    if args.score_existing:
        score = measure(args.checkpoint, args.out)
        _atomic(args.out / "ex42_score.json", score)
        print(json.dumps({"state": "measured", "judgement": score["judgement"]}))
        return 0
    if not args.execute:
        print(json.dumps({"state": "plan", "score_config": str(config()[1]),
                          "commands": commands(args.checkpoint, args.out, args.device)}))
        return 0
    return run(args.checkpoint, args.expected_sha256, args.out, args.device)


if __name__ == "__main__":
    raise SystemExit(main())
