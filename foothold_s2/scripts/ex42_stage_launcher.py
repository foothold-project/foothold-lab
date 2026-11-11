"""The launcher the EX-42 automatic stage start actually calls (`--next-stage-launcher .../ex42_stage_launcher.sh`).

`ex42_stage_handoff.start_launcher` runs it once per authorized decision with `EX42_AUTO_*` in the environment:
  next_stage : EX42_AUTO_ACTION=next_stage, TARGET_STAGE, PARENT_MANIFEST, PARENT_CHECKPOINT, GATE_RECEIPT, GATE_SHA256
  continue   : the same plus EX42_AUTO_RESUME_CHECKPOINT and EX42_AUTO_SEGMENT_END (same stage, same run folder)
This module turns those into the one `torch.distributed.run ... train_start.py` command line, sends the one-line
notice to the run inbox, and then `exec`s the trainer, so the PID the GPU queue registered for the launcher is the
training itself. Everything not in the plan or in `EX42_AUTO_*` comes from the machine profile; a missing value stops
the launch (rc 2) instead of falling back to a guess. It starts no GPU work by itself in `--print` mode.

Per stage values (mesh differs between stages) are read as `EX42_<NAME>_<STAGE>` first, then `EX42_<NAME>`.
Nothing here names a stage: the update bound, the stage flags and the parent come from the plan table."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
PLAN = SOURCE_ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
APPROVALS = SOURCE_ROOT / "foothold_s2" / "curriculum" / "ex42-approvals.yaml"
DISPATCH = SOURCE_ROOT / "_out" / "tools" / "gpu_jobs" / "dispatch.py"
TRAIN_START = SOURCE_ROOT / "foothold_s2" / "scripts" / "train_start.py"
TASK = "FootholdS2-Go2-S2-SB-v0"


class LaunchRefused(ValueError):
    """A missing or inconsistent launch value. The launcher exits 2 and starts nothing."""


def _need(env, name, stage=None):
    for key in ((f"EX42_{name}_{stage}",) if stage else ()) + (f"EX42_{name}",):
        if env.get(key):
            return env[key]
    raise LaunchRefused(f"missing {'EX42_%s_%s or ' % (name, stage) if stage else ''}EX42_{name}")


def _stage_updates(stage):
    from foothold_s2.scripts.ex42_training_entry import E_STAGE_SPECS
    if stage not in E_STAGE_SPECS:
        raise LaunchRefused(f"stage {stage!r} has no pinned parent in the plan (startable: {', '.join(E_STAGE_SPECS)})")
    return int(E_STAGE_SPECS[stage]["updates"])


def p1_argv(env, stage, run_dir, mesh_dir, mesh_sha, python):
    """The per-boundary evaluation command; `{iteration}` is filled by the training's boundary hook."""
    argv = [python, "-m", "foothold_s2.ex42_eval_once",
            "--checkpoint", f"{run_dir}/model_{{iteration}}.pt", "--sha-from-manifest",
            "--out", f"{run_dir}/eval/scores/m{{iteration}}",
            "--device", env.get("EX42_P1_DEVICE", "cuda:1"), "--eval-seed", env.get("EX42_EVAL_SEED", "42"),
            "--mesh-dir", mesh_dir, "--expected-mesh-sha256", mesh_sha,
            "--p1-plan", str(PLAN), "--p1-approvals", str(APPROVALS), "--p1-stage-id", stage]
    if env.get("EX42_P1_SPLIT_DEVICE"):
        argv += ["--split-device", env["EX42_P1_SPLIT_DEVICE"]]
    return argv + ["--execute"]


def build(env, *, dry_run=False, now=None):
    """(argv, child environment, summary) for the stage in `EX42_AUTO_*`; raises LaunchRefused. No side effects."""
    action = env.get("EX42_AUTO_ACTION")
    if action not in ("next_stage", "continue"):
        raise LaunchRefused(f"EX42_AUTO_ACTION must be next_stage or continue, got {action!r}")
    stage = _need(env, "AUTO_TARGET_STAGE")
    updates = _stage_updates(stage)
    parent_manifest = _need(env, "AUTO_PARENT_MANIFEST")
    python = env.get("ISAAC311_PYTHON")
    if not python:
        raise LaunchRefused("missing ISAAC311_PYTHON (machine profile)")
    mesh_dir = _need(env, "MESH_DIR", stage)
    mesh_sha = _need(env, "MESH_SHA256", stage)
    terrain_manifest = str(Path(mesh_dir) / "terrain_manifest.json")
    if not Path(terrain_manifest).is_file():
        raise LaunchRefused(f"{terrain_manifest} is missing (the mesh builder writes it)")
    queue = env.get("GPU_JOBS_QUEUE")
    if not queue:
        raise LaunchRefused("missing GPU_JOBS_QUEUE (machine profile)")
    if action == "continue":
        resume = _need(env, "AUTO_RESUME_CHECKPOINT")
        segment_end = _need(env, "AUTO_SEGMENT_END")
        if not segment_end.isdigit() or not 0 < int(segment_end) <= updates:
            raise LaunchRefused(f"EX42_AUTO_SEGMENT_END {segment_end!r} is not an update in 1..{updates}")
        run_dir = str(Path(resume).resolve().parent)
        if not (Path(run_dir) / "manifest.json").is_file():
            raise LaunchRefused(f"{run_dir} has no manifest.json: not the run folder of the checkpoint")
    else:
        resume = segment_end = None
        stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
        run_dir = f"{_need(env, 'MAIN_ROOT').rstrip('/')}/EX-42-B-{stage}_{stamp}"
    flags = [f"--task={TASK}", "--device=cuda:0", f"--num_envs={env.get('EX42_NUM_ENVS', '3072')}",
             f"--max_iterations={updates}", f"--seed={env.get('EX42_SEED', '42')}", "--headless", "--distributed",
             "--map_input=reconstruction", f"--ex42_plan={PLAN}", f"--ex42_approvals={APPROVALS}",
             f"--ex42_parent_manifest={parent_manifest}", f"--ex42_log_dir={run_dir}",
             f"--ex42_queue_path={queue}", f"--ex42_dispatch_path={DISPATCH}",
             "--ex42_p1_score_argv_json=" + json.dumps(p1_argv(env, stage, run_dir, mesh_dir, mesh_sha, python)),
             f"--ex42_source_ref={_need(env, 'SOURCE_REF')}", f"--ex42_stage={stage}",
             "--ex42_stage_dry_run" if dry_run else "--ex42_stage_approved",
             f"--ex42_terrain_manifest={terrain_manifest}", f"--ex42_terrain_mesh_dir={mesh_dir}"]
    if resume:
        flags += [f"--ex42_resume_from={resume}", f"--ex42_segment_end={segment_end}"]
    if dry_run:
        argv = [python, str(TRAIN_START)] + flags
    else:
        argv = [python, "-m", "torch.distributed.run", "--standalone", "--nnodes=1", "--nproc_per_node=2",
                str(TRAIN_START)] + flags
    child = dict(env, CUDA_DEVICE_ORDER="PCI_BUS_ID", OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1",
                 PYTHONPATH=str(SOURCE_ROOT) + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""))
    child.pop("CUDA_VISIBLE_DEVICES", None)
    if dry_run:
        child.update(WORLD_SIZE="2", RANK="0")
    return argv, child, {"action": action, "stage": stage, "run_dir": run_dir, "updates": updates,
                         "resume": resume, "segment_end": segment_end}


def notify(env, summary, *, runner=subprocess.run, clock=time.strftime):
    """One line to the run inbox. Best effort: a missing sender or a failed send is logged, the launch goes on."""
    cli, target = env.get("ORCA_CLI_COMMAND"), env.get("EX42_NOTIFY_TO")
    if not cli or not target:
        print("EX42 launcher: no ORCA_CLI_COMMAND or EX42_NOTIFY_TO, notice not sent", file=sys.stderr)
        return False
    what = (f"{summary['stage']} 이어 가기 {summary['segment_end']} 까지" if summary["action"] == "continue"
            else f"다음 단계 {summary['stage']} 자동 기동")
    text = f"({clock('%H:%M')}) EX-42 {what} · 실행 폴더 {summary['run_dir']} · 관문 영수증 {env.get('EX42_AUTO_GATE_RECEIPT', '')}"
    try:
        done = runner(shlex.split(env["ORCA_CLI_COMMAND"]) + ["orchestration", "send", "--to", target,
                                                               "--subject", text, "--body", text, "--type", "status"],
                      capture_output=True, text=True, timeout=30)
        if done.returncode != 0:
            print(f"EX42 launcher: notice send rc {done.returncode}: {done.stderr.strip()[:200]}", file=sys.stderr)
        return done.returncode == 0
    except Exception as error:                       # never block a stage start on the notice
        print(f"EX42 launcher: notice send failed: {error}", file=sys.stderr)
        return False


def main(argv=None, env=None, execvpe=os.execvpe):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--print", action="store_true", help="print the command and start nothing")
    parser.add_argument("--dry-run", action="store_true", help="the stage's CPU first-update dry run (no Kit rank 1)")
    args = parser.parse_args(argv)
    env = dict(os.environ if env is None else env)
    try:
        command, child, summary = build(env, dry_run=args.dry_run)
    except LaunchRefused as error:
        print(f"EX42 launcher refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if args.print:
        print(shlex.join(command))
        return 0
    if not args.dry_run:
        Path(summary["run_dir"]).parent.mkdir(parents=True, exist_ok=True)
        notify(env, summary)
    execvpe(command[0], command, child)              # the trainer replaces this process (queue-registered PID)
    return 0


if __name__ == "__main__":
    sys.exit(main())
