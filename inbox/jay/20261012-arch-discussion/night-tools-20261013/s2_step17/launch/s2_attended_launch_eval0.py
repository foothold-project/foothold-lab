"""Node 3 attended S2 update-0 evaluation launcher. No launch on import."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from s2_launch_common import (ASSET, BUNDLE, HOOK, LaunchHold, approval_for,
    base_manifest, check_bundle, consent_from, live_once, new_run, observer_call,
    prelaunch, sha, write_json)
from s2_eval0_checkpoint import create_pair, learning_seeds, check_eval_seeds

PARENT_SHA = "c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8"
URDF_SHA = "f130b1d2cc61f3c1e54dab8f8b9ad27b0b54f85c968d89ea242c6d70ab2a5810"
TERRAIN = Path("C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/sim/eval/generalization_env_cfg.py")
TERRAIN_SHA = "0009e1e11850191bb875e316038a08ae85308226e27d6a748fe474aa1301eed4"
EVAL_SEEDS = (3101, 3109, 3119, 3121)
SCOPE = "s2_eval_kit_smoke_once"


def build(run, chain, resources, max_wall_s, *, pair_factory=create_pair):
    if str(BUNDLE) not in sys.path:
        sys.path.insert(0, str(BUNDLE))
    from s2_eval_cases import seal
    from s2_eval_scope import CODE_NAMES, required_argv
    from s2_eval_driver import PARENT_E1_SHA256, AGENT_YAML_SHA256
    from s2_step4a34.s2_a34_provenance import asset_snapshot, closure_sha256
    if sha(ASSET) != URDF_SHA or sha(TERRAIN) != TERRAIN_SHA or PARENT_E1_SHA256 != PARENT_SHA:
        raise LaunchHold("source_asset_or_parent_pin_changed")
    pair = pair_factory(run)
    learning = learning_seeds()
    check_eval_seeds(EVAL_SEEDS, learning)
    cases = seal(phase="smoke", counts={"gap": 2, "stepping_stones": 2,
                "flat": 0, "stairs_up": 0}, eval_seeds=list(EVAL_SEEDS),
                learning_seeds=learning, command="fwd10", difficulty=.5,
                terrain_source_sha256=TERRAIN_SHA, terrain_source=str(TERRAIN),
                geometry_sha256=TERRAIN_SHA, friction=1.)
    cases_path = run / "in" / "cases.json"
    write_json(cases_path, cases)
    job = {"schema": "s2-eval-job-v1", "phase": "smoke", "update": 0,
           "inference": "act_inference", "cases_sha256": cases["cases_sha256"],
           "arms": pair["arms"], "parent": pair["parent"],
           "agent_yaml": pair["agent_yaml"]}
    job_path = run / "in" / "job.json"
    write_json(job_path, job)
    m = base_manifest(run, chain, SCOPE, "s2_eval_driver.py",
                      max_wall_s=max_wall_s, resources=resources)
    m.update(purpose="evaluation_information_only", phase="smoke",
             training_updates=0, job_path=str(job_path), job_sha256=sha(job_path),
             cases_path=str(cases_path), cases_file_sha256=sha(cases_path),
             episodes_path=str(run / "out" / "episodes.json"),
             asset_path=str(ASSET),
             asset_closure_sha256=closure_sha256(asset_snapshot(
                 ASSET,
                 "C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab/assets/unitree.py",
                 "C:/isaac/IsaacLab/source/isaaclab/isaaclab/sim/converters/asset_converter_base.py")),
             hook_source_path=str(HOOK), hook_source_sha256=sha(HOOK),
             code_hashes={name: sha(BUNDLE / name) for name in CODE_NAMES},
             expect_conversions="any", usd_conversion_cap=8)
    m["argv"] = required_argv(m)
    write_json(run / "in" / "manifest.json", m)
    return m


def execute(args, *, builder=build, prelaunch_fn=prelaunch,
            observer=observer_call, live_fn=live_once):
    if args.live and (not args.attendee.strip() or args.confirm != "LAUNCH-ATTENDED"):
        raise LaunchHold("attendee_or_confirmation_missing")
    consent = consent_from(args.consent_file, SCOPE) if args.live else None
    print("bundle checked: %d files" % check_bundle(), flush=True)
    resources = {key: getattr(args, key) for key in
        ("min_free_vram_bytes", "running_floor_vram_bytes", "min_free_disk_bytes", "max_disk_bytes")}
    run, chain = new_run("eval0-" + ("live" if args.live else "rehearse"))
    m = builder(run, chain, resources, args.max_wall_s)
    approval = approval_for(m, consent, args.attendee.strip())
    if args.live:
        write_json(run / "in" / "approval.json", approval)
        observer(run, "record")
    sys.path.insert(0, str(BUNDLE))
    from s2_eval_scope import validate
    report = prelaunch_fn(m, approval, validate)
    write_json(run / "ctl" / "prelaunch.json", report)
    summary = {"run": str(run), "scope": SCOPE,
               "mode": "live" if args.live else "rehearse",
               "prelaunch": report, "supervisor_started": False}
    if args.live:
        result = live_fn(run, m, approval, "s2_eval_supervisor.py", report, observer=observer)
        summary.update(result, supervisor_started=True)
    write_json(run / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0 if not args.live or (result["supervisor_rc"] == 0 and result["watchdog_rc"] == 0
                                 and result["operational_hold"] is None) else 42


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--rehearse", action="store_true")
    group.add_argument("--live", action="store_true")
    p.add_argument("--attendee", default="")
    p.add_argument("--confirm", default="")
    p.add_argument("--consent-file", type=Path)
    p.add_argument("--max-wall-s", type=int, required=True)
    for key in ("min_free_vram_bytes", "running_floor_vram_bytes", "min_free_disk_bytes", "max_disk_bytes"):
        p.add_argument("--" + key.replace("_", "-"), type=int, required=True)
    return p


if __name__ == "__main__":
    try:
        raise SystemExit(execute(parser().parse_args()))
    except (LaunchHold, OSError, ValueError) as ex:
        raise SystemExit("NO_GO: " + str(ex))
