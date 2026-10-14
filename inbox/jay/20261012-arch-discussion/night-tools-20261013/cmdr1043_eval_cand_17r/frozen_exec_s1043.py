"""First child after slot acquisition. Recheck frozen inputs before GPU guard."""
import argparse
import os
import re
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
    """Compare the complete child argv with one registered A or startup command."""
    c = m["contract"]
    try:
        qpos = cmd.index(c["inputs"]["source_q_eval_cmdr.py"]["path"]) if c["inputs"]["source_q_eval_cmdr.py"]["path"] in cmd else cmd.index(c["inputs"]["source_q_eval.py"]["path"])
        qtail = cmd[qpos + 1:]
        if qtail.count("--tag") != 1:
            return ["tag missing or duplicated"]
        tag = qtail[qtail.index("--tag") + 1]
        startup = c["startup_tests"]
        spec = None
        if tag.startswith(startup["tag_prefix"]):
            if m["execution"].get("stage") != "A":
                return ["startup test outside A stage"]
            for suffix, item in startup["suffixes"].items():
                prefix = tag.removesuffix("_" + suffix)
                token = prefix.removeprefix(startup["tag_prefix"])
                if prefix != tag and re.fullmatch(r"[0-9a-f]{8}_g[01]t\d{6}p\d+", token):
                    spec = item
                    break
            if spec is None or spec["checkpoint"] != checkpoint_label:
                return ["tag outside registered startup tests"]
            evaluator = spec["evaluator"]
            fam = startup["common"]["family"]
            cells = ",".join(startup["smoke_cells"]) if spec["cells"] == "all_11" else spec["cells"]
            episodes = spec["episodes"]
            seed = startup["common"]["eval_seed"]
            noise = startup["common"]["obs_noise"]
            small = spec["small"]
            yaml_kind = spec["yaml"]
        elif tag.startswith(c["diagnostic"]["tag_prefix"]):
            if m["execution"].get("stage") != "diagnostic" or checkpoint_label != "p20000":
                return ["diagnostic stage or checkpoint mismatch"]
            for suffix, item in c["diagnostic"]["runs"].items():
                prefix = tag.removesuffix("_" + suffix)
                token = prefix.removeprefix(c["diagnostic"]["tag_prefix"])
                if prefix != tag and re.fullmatch(r"[0-9a-f]{8}_g[01]t\d{6}p\d+", token):
                    spec = item
                    break
            if spec is None or (suffix == "orig_repeat" and m["execution"].get("diagnostic_repeat_original") is not True):
                return ["tag outside approved diagnostic"]
            evaluator, fam, cells = spec["evaluator"], c["diagnostic"]["family"], c["diagnostic"]["cell"]
            episodes, seed, noise, small = c["diagnostic"]["episodes"], c["diagnostic"]["eval_seed"], True, spec["small"]
            yaml_kind = "none"
        else:
            if m["execution"].get("stage") != "A":
                return ["A job outside A stage"]
            planned = {f"cq_{model}_{family}_{cell}_{noise}_s{seed}": (model, family, cell, noise, seed)
                       for model, family, cell, noise, seed in c["plan"]["A"]}
            job = planned.get(tag)
            if job is None or job[0] != checkpoint_label:
                return ["tag outside registered A"]
            _, fam, cells, noise_word, seed = job
            evaluator, episodes, noise, small = "q_eval_cmdr.py", 100, noise_word == "on", True
            yaml_kind = "none" if checkpoint_label == "p20000" else "parent"
        branch = c["branches"]
        model_path = (c["parent"]["path"] if checkpoint_label == "p20000" else
                      c["inputs"][branch["off" if checkpoint_label.startswith("off") else "on"][f"model_{checkpoint_label[-5:]}"]]["path"])
        py = c["runtime"]["python"]
        source = c["inputs"]
        q = [py, source[f"source_{evaluator}"]["path"], "--headless", "--tag", tag, "--policy", "student",
             "--checkpoint", model_path, "--outdir", c["paths"]["data"], "--families", fam,
             "--cells", cells, "--episodes", str(episodes), "--eval_seed", str(seed),
             "--difficulty", "0.5", "--terrain_set", "train", "--heading_hold", "0", "--spawn_offset", ""]
        if small:
            q.append("--physx_small_buffers")
        if noise:
            q.append("--obs_noise")
        if checkpoint_label != "p20000":
            yaml_path = {"parent": source["parent_env_yaml"]["path"],
                         "sibling": source["parent_agent_yaml"]["path"],
                         "other_run": startup["other_run_yaml"]}[yaml_kind]
            q += ["--train_yaml", yaml_path]
        log_file = str(Path(c["paths"]["data"]) / f"{tag}.log")
        summary_file = str(Path(c["paths"]["data"]) / f"{tag}.guard.json")
        isolated = [py, source["source_usd_isolate_run_v3.py"]["path"]] + q[1:]
        expected = [py, source["source_gpu_guard.py"]["path"], "--gpu", str(c["device"]["gpu_index"]),
                    "--min_free_mib", str(c["device"]["min_free_mib"]), "--log", log_file,
                    "--summary", summary_file, "--"] + isolated
        return [] if cmd == expected else ["complete child argv differs from registration"]
    except (ValueError, IndexError, KeyError, TypeError, OSError) as exc:
        return [f"command incomplete: {type(exc).__name__}: {exc}"]


def check(m, checkpoint_label, *, cpu_fixture=False, approved_digest=None):
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
        problems = launch_errors(m, approved_digest=approved_digest)
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
    parser.add_argument("--approved_digest")
    parser.add_argument("--cpu_fixture", action="store_true")
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    print("sys.executable", sys.executable)
    print("candidate.__file__", __file__)
    actual_sha = sha256(__file__)
    print("candidate.sha256", actual_sha)
    m = load(args.manifest)
    if (actual_sha != args.expect_self_sha or
            Path(__file__).resolve() != (Path(m["contract"]["deployment"]["candidate_dir"]) / "frozen_exec_s1043.py").resolve()):
        print("환경 불일치", file=sys.stderr)
        return 3
    if Path(sys.executable).resolve() != Path(m["contract"]["runtime"]["python"]).resolve():
        print("환경 불일치", file=sys.stderr)
        return 3
    try:
        check(m, args.checkpoint_label, cpu_fixture=args.cpu_fixture, approved_digest=args.approved_digest)
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
