"""EX-42 E1 v28 live average-action probe: a separate process, never inside the training loop.

Every 50 updates the run saves model_N.pt (save_interval 50). This watcher takes each such checkpoint that the run
manifest publishes (SHA checked), runs the fixed evaluation child on it (`eval_map_modes`: flat-ish L0 continuous
terrain, command fwd0.1 and fwd0.2, GT / PRED / map off, mean action = act_inference, 6 s, DR off) on the evaluation GPU
and appends one row to `<run>/ex42_live_probe.jsonl`. The training run keeps no sample, reward or random number of the
probe and is never paused: it only sees a checkpoint file that it wrote anyway.

Row cells (per mode/command): R_median (distance of the 6 s over command x 6 s, median over envs), the median forward
speed of each second, how many envs moved less than 0.05 m/s in seconds 2 to 4 and in the last second, survivors.
`wall_seconds` is the wall-clock time of the whole probe (decisions.tsv 2026-11-14 12:11, ledger commit b6024dd2).
When the run also keeps a weight average (foothold_s2/runners/weight_ema.py), model_N_ema.pt sits next to model_N.pt; after the
model_N.pt row the watcher probes that file the same way and appends a second row for N with "ema": true (its sha is the file's
own: the average is not in the run manifest). Rows of model_N.pt carry no new key.
The row decides nothing: the thresholds of the live adjustment stay with the lead (no new number is made here)."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

FORMAT = "ex42-live-probe/1"
LOG_NAME = "ex42_live_probe.jsonl"
INTERVAL_UPDATES = 50
MODES = ("eval_gt", "eval_pred", "probe_prop_only")
COMMANDS = {"fwd0.1": 0.1, "fwd0.2": 0.2}
ENVS, STEPS, DT = 32, 300, 0.02
STALL_MPS = 0.05                      # the stillness threshold the pair readback and the live metrics already use
TIMEOUT_SECONDS = 1200


def due(iteration: int, interval: int = INTERVAL_UPDATES) -> bool:
    return type(iteration) is int and iteration > 0 and iteration % interval == 0


def cell_metrics(vx, alive, dt, command_speed, *, stall_mps: float = STALL_MPS) -> dict:
    """One cell from the raw trace vx[steps, envs] and alive[steps, envs]. Raises on a trace that is not 6 s of the
    expected shape or not finite (a bad trace is a failed probe, not a zero)."""
    vx, alive = np.asarray(vx, dtype=float), np.asarray(alive, dtype=bool)
    if (vx.ndim != 2 or vx.shape != alive.shape or vx.shape[0] != STEPS or not 1 <= vx.shape[1]
            or not np.isfinite(vx).all() or not math.isclose(float(dt), DT, rel_tol=0, abs_tol=1e-9)
            or not math.isfinite(command_speed) or command_speed <= 0):
        raise ValueError("EX-42 live probe trace shape, dt, command or values invalid")
    moved = vx * alive
    seconds = moved.reshape(STEPS // 50, 50, -1).mean(axis=1)            # (6, envs): mean forward speed of each second
    ratio = moved.sum(axis=0) * dt / (command_speed * STEPS * dt)
    middle, last = moved[100:200].mean(axis=0), moved[-50:].mean(axis=0)
    envs = int(vx.shape[1])
    return {"envs": envs, "R_median": float(np.median(ratio)), "distance_m_median": float(np.median(moved.sum(axis=0) * dt)),
            "second_vx_median": [float(x) for x in np.median(seconds, axis=1)],
            "stalled_2to4": int((middle < stall_mps).sum()), "stalled_last1": int((last < stall_mps).sum()),
            "stalled_last1_ratio": float((last < stall_mps).sum() / envs), "survived": int(alive[-1].sum())}


def summarize(folder) -> dict:
    """All six cells from the env_arrays_<mode>_<command>.npz files the evaluation child left in `folder`."""
    folder, cells = Path(folder), {}
    for mode in MODES:
        for name, speed in COMMANDS.items():
            path = folder / f"env_arrays_{mode}_{name}.npz"
            if not path.is_file():
                raise ValueError(f"EX-42 live probe cell is missing: {mode}/{name}")
            with np.load(path, allow_pickle=False) as z:
                cells[f"{mode}/{name}"] = cell_metrics(z["vx"], z["alive"], float(z["dt"]), speed)
    if len({cell["envs"] for cell in cells.values()}) != 1:
        raise ValueError("EX-42 live probe cells disagree on the env count")
    return cells


def probe_argv(python, checkpoint, out, *, device, task, evaluation_plan, mesh_dir, seed=42, envs=ENVS) -> list[str]:
    argv = [str(python), "-B", "-m", "foothold_s2.eval.eval_map_modes", "--ex42-evaluation-plan", str(evaluation_plan),
            "--task", task, "--checkpoint", str(checkpoint), "--envs", str(envs), "--steps", str(STEPS),
            "--modes", ",".join(MODES), "--fixed-terrain", "--fixed-level", "0", "--eval-seed", str(seed),
            "--command-suite", "e1_v2", "--commands", ",".join(COMMANDS), "--out", str(out), "--device", device,
            "--headless"]
    if mesh_dir is not None:
        argv[argv.index("--out"):argv.index("--out")] = ["--mesh-dir", str(mesh_dir)]
    return argv


def recorded_iterations(run_dir, *, ema: bool = False) -> set[int]:
    """Updates with a row in the log: the model_N.pt rows (default) or the model_N_ema.pt rows ("ema": true)."""
    path = Path(run_dir) / LOG_NAME
    if not path.is_file():
        return set()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(row.get("format") != FORMAT for row in rows):
        raise ValueError("EX-42 live probe log has another format")
    return {row["iteration"] for row in rows if bool(row.get("ema")) == ema}


def append_row(run_dir, row: dict) -> None:
    ema = bool(row.get("ema"))
    if row["iteration"] in recorded_iterations(run_dir, ema=ema):
        raise ValueError(f"EX-42 live probe already recorded m{row['iteration']}{'_ema' if ema else ''}")
    with (Path(run_dir) / LOG_NAME).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def run_probe(run_dir, iteration, checkpoint_sha, argv, folder, *, timeout=TIMEOUT_SECONDS, stage_id="E1") -> dict:
    """Run the child under `timeout` (killed when it overruns), read its cells, return the row. Never raises on a
    child or trace failure: the row says failed/timeout with the reason and the wall seconds so far."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    row = {"format": FORMAT, "stage_id": stage_id, "iteration": iteration, "checkpoint_sha256": checkpoint_sha,
           "level": 0, "envs": ENVS, "steps": STEPS, "action": "mean", "modes": list(MODES), "commands": list(COMMANDS),
           "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "folder": str(folder)}
    started = time.monotonic()
    try:
        with (folder / "child.stdout.log").open("wb") as out, (folder / "child.stderr.log").open("wb") as err:
            child = subprocess.Popen(argv, stdout=out, stderr=err, stdin=subprocess.DEVNULL, cwd=Path(__file__).resolve().parents[1])
            try:
                code = child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                child.kill()                      # our own child only
                child.wait()
                row.update(state="timeout", reason=f"child exceeded {timeout} s")
                code = None
        if code is not None:
            row["returncode"] = code
            if code != 0:
                row.update(state="failed", reason=f"child exit code {code}")
            else:
                row.update(state="done", cells=summarize(folder))
    except Exception as exc:                      # noqa: BLE001 (a probe failure is a record, never a stop of the watcher)
        row.update(state="failed", reason=f"{type(exc).__name__}: {exc}")
    row["wall_seconds"] = round(time.monotonic() - started, 1)
    return row


def next_checkpoint(run_dir, done: set[int], *, manifest_sha=None):
    """The lowest published model_N.pt (N a multiple of 50) not probed yet, as (N, sha); None when nothing is ready."""
    from foothold_s2.ex42_eval_once import manifest_checkpoint_sha
    manifest_sha = manifest_sha or manifest_checkpoint_sha
    found = sorted(int(m.group(1)) for p in Path(run_dir).glob("model_*.pt") if (m := re.fullmatch(r"model_(\d+)\.pt", p.name)))
    for iteration in found:
        if due(iteration) and iteration not in done:
            try:
                return iteration, manifest_sha(Path(run_dir) / f"model_{iteration}.pt")[0]
            except (ValueError, OSError, KeyError):
                return None                        # saved but not published yet: wait, never probe a half-written file
    return None


def next_ema_checkpoint(run_dir, done: set[int], done_ema: set[int]):
    """The lowest N whose model_N.pt row exists, whose model_N_ema.pt is on disk (it is written whole, then renamed into place)
    and has no ema row yet, as (N, sha of the file); None when nothing is ready."""
    from foothold_s2.runners.manifest import sha256_file
    from foothold_s2.runners.weight_ema import ema_file_name
    for iteration in sorted(done):
        path = Path(run_dir) / ema_file_name(iteration)
        if iteration not in done_ema and path.is_file():
            return iteration, sha256_file(path)
    return None


def watch(run_dir, *, python, device, task, evaluation_plan, mesh_dir, until, poll_seconds=30, stop_file=None,
          timeout=TIMEOUT_SECONDS, sleep=time.sleep, runner=run_probe, manifest_sha=None) -> list[int]:
    run_dir, probed = Path(run_dir), []
    while True:
        done, done_ema = recorded_iterations(run_dir), recorded_iterations(run_dir, ema=True)
        ema_ready = next_ema_checkpoint(run_dir, done, done_ema)
        if (until in done and ema_ready is None) or (stop_file is not None and Path(stop_file).exists()):
            return probed
        ready = next_checkpoint(run_dir, done, manifest_sha=manifest_sha)
        if ema_ready is not None and (ready is None or ema_ready[0] <= ready[0]):   # an update's average right after its model_N.pt
            from foothold_s2.runners.weight_ema import ema_file_name
            iteration, sha = ema_ready
            folder = run_dir / "live_probe" / f"m{iteration}_ema"
            argv = probe_argv(python, run_dir / ema_file_name(iteration), folder, device=device, task=task,
                              evaluation_plan=evaluation_plan, mesh_dir=mesh_dir)
            row = runner(run_dir, iteration, sha, argv, folder, timeout=timeout)
            row.update(ema=True, checkpoint_file=ema_file_name(iteration))
            append_row(run_dir, row)
            print("EX42_LIVE_PROBE " + json.dumps({"iteration": iteration, "ema": True, "state": row["state"],
                                                  "wall_seconds": row["wall_seconds"]}), flush=True)
            continue
        if ready is None:
            sleep(poll_seconds)
            continue
        iteration, sha = ready
        folder = run_dir / "live_probe" / f"m{iteration}"
        argv = probe_argv(python, run_dir / f"model_{iteration}.pt", folder, device=device, task=task,
                          evaluation_plan=evaluation_plan, mesh_dir=mesh_dir)
        row = runner(run_dir, iteration, sha, argv, folder, timeout=timeout)
        append_row(run_dir, row)
        print("EX42_LIVE_PROBE " + json.dumps({"iteration": iteration, "state": row["state"],
                                              "wall_seconds": row["wall_seconds"]}), flush=True)
        probed.append(iteration)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--evaluation-plan", type=Path, required=True)
    parser.add_argument("--mesh-dir", type=Path, required=True)
    parser.add_argument("--task", default="FootholdS2-Go2-S2-SB-v0")
    parser.add_argument("--device", default="cuda:1")
    parser.add_argument("--python", default=None)
    parser.add_argument("--until", type=int, default=1750, help="stop after this local update has been probed")
    parser.add_argument("--stop-file", type=Path, default=None)
    args = parser.parse_args(argv)
    from foothold_s2.machine_profile import machine_path
    watch(args.run_dir, python=args.python or machine_path("conda_python"), device=args.device, task=args.task,
          evaluation_plan=args.evaluation_plan, mesh_dir=args.mesh_dir, until=args.until, stop_file=args.stop_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
