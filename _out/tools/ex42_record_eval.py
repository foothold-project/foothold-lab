"""After an EX-42 boundary: run the three record children (e1_v2 L0, e1_v2 L5, d44) on a saved checkpoint, apart from the official score.

Why (planner 2026-11-15 22:45, lead 22:46): the E1F boundary evaluation has no low-speed cell and no D44 line, and adding them to the evaluation
would change the judgement structure and the score format. These three children are the ones the E1 boundary evaluation already runs; here they
run again, with the argv a finished boundary recorded (children/<name>/child.json), on the checkpoint of the boundary, and write under
eval/record/mN, never under eval/scores. Nothing here enters a judgement.

Only these values are replaced in the recorded argv: --checkpoint, --out, --replica-dir (d44), --device, and the Kit cache path of --kit_args.
The evaluation plan, mesh, seed, steps, envs, command suite come from the recorded argv (``--evaluation-plan`` replaces the two plan arguments).

Default is a print of the commands (JSON) and nothing runs. ``--execute`` starts them: one queue per device, the queues run side by side.

  python _out/tools/ex42_record_eval.py --score-dir <run>/eval/scores/m750 --checkpoint <run>/model_1000.pt \
      --repo <trainer copy> --out <run>/eval/record/m1000 --devices cuda:0,cuda:1 [--evaluation-plan <plan>] [--execute]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

NAMES = ("e1_v2_L0", "e1_v2_L5", "d44")
OUT_SUB = {"e1_v2_L0": "e1_v2/L0", "e1_v2_L5": "e1_v2/L5", "d44": "d44"}
MIN_FREE_MIB = 13500


class RecordRefused(ValueError):
    pass


def _value(argv, flag):
    if flag not in argv:
        raise RecordRefused(f"recorded argv has no {flag}")
    return argv[argv.index(flag) + 1]


def _set(argv, flag, value):
    argv = list(argv)
    argv[argv.index(flag) + 1] = str(value)
    return argv


def reference_children(score_dir: Path) -> dict:
    """The recorded argv of the three children of a finished boundary evaluation."""
    found = {}
    for name in NAMES:
        path = score_dir / "children" / name / "child.json"
        if not path.is_file():
            raise RecordRefused(f"{path} is missing: the reference boundary did not run {name}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("state") != "done" or doc.get("rc") != 0:
            raise RecordRefused(f"{path} is not a finished child (state={doc.get('state')!r}, rc={doc.get('rc')!r})")
        found[name] = doc
    return found


def plan_commands(score_dir, checkpoint, out, devices, *, evaluation_plan=None):
    """name -> {"argv", "device"} with the replaced values; nothing is started."""
    out, checkpoint = Path(out), Path(checkpoint)
    if "scores" in out.parts or "record" not in out.parts:
        raise RecordRefused("the record output must be under a folder named record (never under eval/scores)")
    if not checkpoint.is_file():
        raise RecordRefused(f"{checkpoint} does not exist")
    if out.exists() and any(out.iterdir()):
        raise RecordRefused(f"{out} is not empty")
    devices = list(devices)
    if not devices or any(not d.startswith("cuda:") or not d[5:].isdigit() for d in devices):
        raise RecordRefused("--devices must be cuda:N[,cuda:M]")
    assignment = {"e1_v2_L0": devices[0], "e1_v2_L5": devices[-1], "d44": devices[0]}
    result = {}
    for name, doc in reference_children(Path(score_dir)).items():
        argv = list(doc["argv"])
        argv = _set(argv, "--checkpoint", checkpoint)
        argv = _set(argv, "--out", out / OUT_SUB[name])
        argv = _set(argv, "--device", assignment[name])
        if name == "d44":
            argv = _set(argv, "--replica-dir", out / "d44_mesh")
        if evaluation_plan is not None:
            for flag in ("--ex42-evaluation-plan", "--plan"):
                if flag in argv:
                    argv = _set(argv, flag, evaluation_plan)
        kit = [a for a in argv if a.startswith("--kit_args=--/UJITSO/datastore/localCachePath=")]
        if len(kit) != 1:
            raise RecordRefused(f"{name}: recorded argv has no single Kit cache path")
        argv[argv.index(kit[0])] = ("--kit_args=--/UJITSO/datastore/localCachePath="
                                    f"{out / 'kit_runtime' / assignment[name].replace(':', '_') / name / 'cache'}")
        result[name] = {"argv": argv, "device": assignment[name]}
    return result


def child_env(parent=None):
    """The same environment the boundary evaluation gives its children (ex42_eval_once.child_env), with the repo as PYTHONPATH."""
    env = dict(os.environ if parent is None else parent)
    env.pop("CUDA_VISIBLE_DEVICES", None)
    env.update(CUDA_DEVICE_ORDER="PCI_BUS_ID", PYTHONUNBUFFERED="1", KMP_DUPLICATE_LIB_OK="TRUE", OMNI_KIT_ACCEPT_EULA="YES")
    return env


def free_mib(device):
    index = device.split(":")[1]
    done = subprocess.run(["nvidia-smi", f"--id={index}", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                          capture_output=True, text=True, timeout=30)
    if done.returncode != 0:
        raise RecordRefused(f"nvidia-smi failed for {device}: {done.stderr.strip()[:120]}")
    return int(done.stdout.strip().splitlines()[0])


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def execute(commands, repo, out, checkpoint):
    """One queue per device (the names of a device run one after the other), the devices side by side."""
    repo, out = Path(repo), Path(out)
    for device in sorted({c["device"] for c in commands.values()}):
        if free_mib(device) < MIN_FREE_MIB:
            raise RecordRefused(f"{device} has less than {MIN_FREE_MIB} MiB free")
    env = child_env()
    env["PYTHONPATH"] = str(repo)
    queues = {}
    for name, c in commands.items():
        queues.setdefault(c["device"], []).append(name)
    started, records = time.time(), {}
    running = {}
    pending = {d: list(names) for d, names in queues.items()}

    def start(device):
        name = pending[device].pop(0)
        folder = out / "children" / name
        folder.mkdir(parents=True, exist_ok=True)
        fh_out, fh_err = open(folder / "stdout.log", "wb"), open(folder / "stderr.log", "wb")
        proc = subprocess.Popen(commands[name]["argv"], cwd=str(repo), env=env, stdout=fh_out, stderr=fh_err, stdin=subprocess.DEVNULL)
        running[device] = (name, proc, fh_out, fh_err, time.time())

    for device in pending:
        start(device)
    while running:
        for device, (name, proc, fh_out, fh_err, t0) in list(running.items()):
            rc = proc.poll()
            if rc is None:
                continue
            fh_out.close()
            fh_err.close()
            records[name] = {"device": device, "rc": rc, "seconds": round(time.time() - t0, 1), "argv": commands[name]["argv"]}
            del running[device]
            if pending[device]:
                start(device)
        time.sleep(2)
    receipt = {"format": "ex42-record-eval/1", "checkpoint": str(checkpoint), "checkpoint_sha256": _sha256(checkpoint),
               "repo": str(repo), "seconds": round(time.time() - started, 1), "children": records,
               "note": "record only: nothing here enters a judgement"}
    (out / "record_receipt.json").write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8")
    return receipt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--score-dir", required=True, help="eval/scores/mN of a finished boundary: its children/<name>/child.json are the reference argv")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--repo", required=True, help="the trainer copy the children run in (cwd and PYTHONPATH)")
    ap.add_argument("--out", required=True, help="eval/record/mN")
    ap.add_argument("--devices", default="cuda:0,cuda:1")
    ap.add_argument("--evaluation-plan", default=None)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args(argv)
    try:
        commands = plan_commands(args.score_dir, args.checkpoint, args.out, args.devices.split(","), evaluation_plan=args.evaluation_plan)
        if not args.execute:
            print(json.dumps({"mode": "print only (add --execute to run)", "repo": args.repo, "commands": commands}, indent=1, ensure_ascii=False))
            return 0
        Path(args.out).mkdir(parents=True, exist_ok=True)
        receipt = execute(commands, args.repo, args.out, args.checkpoint)
    except RecordRefused as error:
        print(f"ex42_record_eval refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps({k: v for k, v in receipt.items() if k != "children"} | {"rc": {n: c["rc"] for n, c in receipt["children"].items()}}, indent=1))
    return 0 if all(c["rc"] == 0 for c in receipt["children"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
