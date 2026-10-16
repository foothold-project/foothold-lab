"""Node 4 attended, one-shot S2 foot-ray Kit diagnostic launcher."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from s2_launch_common import (ASSET, BUNDLE, LaunchHold, approval_for,
    base_manifest, check_bundle, consent_from, live_once, new_run, observer_call,
    prelaunch, sha, write_json)

SCOPE = "s2_foot_kit_check_once"
URDF_SHA = "f130b1d2cc61f3c1e54dab8f8b9ad27b0b54f85c968d89ea242c6d70ab2a5810"
TOLERANCES = {"hit_xy_m": .001, "hit_z_m": .001,
              "collision_center_distance_m": .001,
              "edge_xy_band_m": .005, "height_boundary_band_m": .002,
              "contact_boundary_band_n": .05}


def build(run, chain, resources, max_wall_s, *, seed, steps_per_scene):
    if str(BUNDLE) not in sys.path:
        sys.path.insert(0, str(BUNDLE))
    from s2_foot_scenes import SCENES
    from s2_foot_kit_scope import CODE_NAMES, required_argv
    if sha(ASSET) != URDF_SHA:
        raise LaunchHold("urdf_sha256_changed")
    if type(seed) is not int or seed < 0 or type(steps_per_scene) is not int or not 2 <= steps_per_scene <= 37:
        raise LaunchHold("foot_seed_or_step_scope")
    request = {"scope": SCOPE, "scenes": list(SCENES), "seed": seed,
               "training_updates": 0, "optimizer_steps": 0,
               "max_envs": 2, "steps_per_scene": steps_per_scene,
               "max_wall_s": max_wall_s, "tolerances": TOLERANCES,
               "asset_path": str(ASSET), "asset_sha256": URDF_SHA}
    request_path = run / "in" / "request.json"
    write_json(request_path, request)
    m = base_manifest(run, chain, SCOPE, "s2_foot_kit_driver.py",
                      max_wall_s=max_wall_s, resources=resources)
    m.update(purpose="one_shot_no_learning", request_path=str(request_path),
             request_sha256=sha(request_path), result_path=str(run / "out" / "foot_result.json"),
             max_envs=2, max_control_steps=300, training_updates=0, optimizer_steps=0,
             code_hashes={name: sha(BUNDLE / name) for name in CODE_NAMES},
             asset_path=str(ASSET), asset_sha256=URDF_SHA)
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
    run, chain = new_run("foot-" + ("live" if args.live else "rehearse"))
    m = builder(run, chain, resources, args.max_wall_s,
                seed=args.seed, steps_per_scene=args.steps_per_scene)
    approval = approval_for(m, consent, args.attendee.strip())
    if args.live:
        write_json(run / "in" / "approval.json", approval)
        observer(run, "record")
    sys.path.insert(0, str(BUNDLE))
    from s2_foot_kit_scope import validate
    report = prelaunch_fn(m, approval, validate)
    write_json(run / "ctl" / "prelaunch.json", report)
    summary = {"run": str(run), "scope": SCOPE,
               "mode": "live" if args.live else "rehearse",
               "prelaunch": report, "supervisor_started": False}
    if args.live:
        result = live_fn(run, m, approval, "s2_foot_kit_supervisor.py", report, observer=observer)
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
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--steps-per-scene", type=int, required=True)
    p.add_argument("--max-wall-s", type=int, required=True)
    for key in ("min_free_vram_bytes", "running_floor_vram_bytes", "min_free_disk_bytes", "max_disk_bytes"):
        p.add_argument("--" + key.replace("_", "-"), type=int, required=True)
    return p


if __name__ == "__main__":
    try:
        raise SystemExit(execute(parser().parse_args()))
    except (LaunchHold, OSError, ValueError) as ex:
        raise SystemExit("NO_GO: " + str(ex))
