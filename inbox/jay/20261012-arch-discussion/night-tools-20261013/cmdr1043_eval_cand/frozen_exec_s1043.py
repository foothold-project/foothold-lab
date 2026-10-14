"""First child after slot acquisition. Recheck frozen inputs before GPU guard."""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

from s1043_manifest import ROOT, assert_isolated, check_inputs, inside, launch_errors, load, sha256


def foreign_isaac():
    ancestors = {p.pid for p in psutil.Process().parents()}
    ancestors.add(os.getpid())
    found = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            info = proc.info
            if info["pid"] in ancestors:
                continue
            name = (info.get("name") or "").lower()
            if name.startswith(("kit", "isaac-sim")):
                found.append(info["pid"])
            elif name.startswith("python"):
                cmd = info.get("cmdline")
                if cmd is None:
                    found.append(f"unknown:{info['pid']}")
                elif "--headless" in cmd or any(Path(x).name.lower() in
                        ("q_eval.py", "q_eval_cmdr.py", "train.py", "play.py", "branch_run.py") for x in cmd):
                    found.append(info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            found.append(f"unknown:{proc.pid}")
    return found


def gpu_probe(m):
    device = m["contract"]["device"]
    result = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,memory.free", "--format=csv,noheader,nounits"],
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError("GPU probe failed")
    rows = [list(map(str.strip, line.split(","))) for line in result.stdout.splitlines()]
    row = next((r for r in rows if len(r) == 3 and r[0] == str(device["gpu_index"])), None)
    if row is None or row[1].removeprefix("GPU-") != str(device["gpu_uuid"]).removeprefix("GPU-"):
        raise RuntimeError("physical GPU index or UUID mismatch")
    if int(row[2]) < device["min_free_mib"]:
        raise RuntimeError("GPU free memory below floor")
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or os.environ.get("CUDA_VISIBLE_DEVICES") != str(device["gpu_index"]):
        raise RuntimeError("child CUDA environment mismatch")
    return row


def command_errors(m, checkpoint_label, cmd):
    """Allow only the registered guard, isolate and q evaluator chain."""
    problems = []
    c = m["contract"]
    source = Path("C:/isaac/ext/go2_rl_robotlab/_eval")
    try:
        if (Path(cmd[0]).resolve() != Path(c["runtime"]["python"]).resolve() or
                Path(cmd[1]).resolve() != (source / "gpu_guard.py").resolve()):
            problems.append("guard executable")
        first_sep = cmd.index("--")
        guard = cmd[2:first_sep]
        isolated = cmd[first_sep + 1:]
        second_sep = isolated.index("--") if "--" in isolated else len(isolated)
        if (Path(isolated[0]).resolve() != Path(c["runtime"]["python"]).resolve() or
                Path(isolated[1]).resolve() != (source / "usd_isolate_run_v3.py").resolve() or
                Path(isolated[2]).resolve() not in ((source / "q_eval_cmdr.py").resolve(), (source / "q_eval.py").resolve())):
            problems.append("isolate or evaluator executable")
        q = isolated[3:second_sep]
        def value(items, key):
            return items[items.index(key) + 1]
        if value(guard, "--gpu") != str(c["device"]["gpu_index"]) or int(value(guard, "--min_free_mib")) != c["device"]["min_free_mib"]:
            problems.append("guard device or floor")
        if not inside(value(guard, "--log")) or not inside(value(guard, "--summary")):
            problems.append("guard output path")
        branch = c["branches"]
        expected_ckpt = (c["parent"]["path"] if checkpoint_label == "p20000" else
                         c["inputs"][branch[checkpoint_label[:3] if checkpoint_label.startswith("off") else "on"][f"model_{checkpoint_label[-5:]}"]]["path"])
        if Path(value(q, "--checkpoint")).resolve() != Path(expected_ckpt).resolve():
            problems.append("checkpoint path")
        if Path(value(q, "--outdir")).resolve() != Path(c["paths"]["data"]).resolve():
            problems.append("q output path")
        for key, expected in (("--policy", "student"), ("--difficulty", "0.5"),
                              ("--terrain_set", "train"), ("--heading_hold", "0"), ("--spawn_offset", "")):
            if value(q, key) != expected:
                problems.append(f"q {key}")
        tag = value(q, "--tag")
        if not tag.startswith("cq_") or "_s" not in tag:
            problems.append("tag grammar")
        if not tag.startswith("cq_test_"):
            planned = {f"cq_{m}_{fam}_{cell}_{noise}_s{seed}": (m, fam, cell, noise, seed)
                       for m, fam, cell, noise, seed in c["plan"]["A"]}
            job = planned.get(tag)
            if job is None or job[0] != checkpoint_label:
                problems.append("tag outside registered A")
            elif (value(q, "--families"), value(q, "--cells"), int(value(q, "--eval_seed")),
                  int(value(q, "--episodes")), "--obs_noise" in q) != (job[1], job[2], job[4], 100, job[3] == "on"):
                problems.append("q run differs from registered A")
        if not tag.startswith("cq_test_") and "--physx_small_buffers" not in q:
            problems.append("small buffers absent")
    except (ValueError, IndexError, KeyError, TypeError, OSError):
        problems.append("command incomplete")
    return problems


def check(m, checkpoint_label, *, cpu_fixture=False):
    assert_isolated(m)
    if Path(m["contract"]["paths"]["stop"]).exists():
        raise RuntimeError("STOP")
    if cpu_fixture:
        if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1":
            raise RuntimeError("CPU fixture requires CUDA_VISIBLE_DEVICES=-1")
        problems = check_inputs(m, require_files=False)
        fixture_inputs = m["contract"].get("fixture_inputs")
        if not isinstance(fixture_inputs, dict) or not fixture_inputs:
            problems.append("fixture inputs missing")
        else:
            for name, rec in fixture_inputs.items():
                if not inside(rec.get("path", "")) or sha256(rec["path"]) != rec.get("sha256"):
                    problems.append(f"fixture input changed: {name}")
    else:
        problems = launch_errors(m)
        if isinstance(m["execution"].get("deadline_epoch"), (int, float)) and time.time() > m["execution"]["deadline_epoch"]:
            problems.append("deadline")
    if problems:
        raise RuntimeError(f"frozen inputs: {problems[:5]}")
    if checkpoint_label not in ("p20000", "off22000", "on22000", "off24000", "on24000"):
        raise RuntimeError("checkpoint label")
    if not cpu_fixture:
        if foreign_isaac():
            raise RuntimeError("unregistered Isaac after slot wait")
        gpu_probe(m)


def main(argv=None):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--checkpoint_label", required=True)
    parser.add_argument("--expect_self_sha", required=True)
    parser.add_argument("--cpu_fixture", action="store_true")
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    print("sys.executable", sys.executable)
    print("candidate.__file__", __file__)
    actual_sha = sha256(__file__)
    print("candidate.sha256", actual_sha)
    if (actual_sha != args.expect_self_sha or Path(__file__).resolve() != (ROOT / "cand/frozen_exec_s1043.py").resolve()):
        print("환경 불일치", file=sys.stderr)
        return 3
    m = load(args.manifest)
    if Path(sys.executable).resolve() != Path(m["contract"]["runtime"]["python"]).resolve():
        print("환경 불일치", file=sys.stderr)
        return 3
    try:
        check(m, args.checkpoint_label, cpu_fixture=args.cpu_fixture)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"FROZEN STOP: {exc}", file=sys.stderr)
        return 92
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if args.cpu_fixture:
        if cmd:
            bad = command_errors(m, args.checkpoint_label, cmd)
            if bad:
                print(f"FROZEN STOP: child command {bad}", file=sys.stderr)
                return 92
        print("READY_CPU_NO_CHILD")
        return 0
    bad = command_errors(m, args.checkpoint_label, cmd)
    if bad:
        print(f"FROZEN STOP: child command {bad}", file=sys.stderr)
        return 92
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
