# Runs the randomization scenes one after another on GPU 1, each Isaac process through the lead's wrapper (isaac_slot v2)
#   isaac_slot.py (--usd_root <attempt>/usd · --attempt · lock · registry · scan of out_rand, out_branch, out_uncr · --stop_file ·
#   --deadline) -> gpu_guard.py (GPU 1, 4096 MiB floor) -> usd_isolate_run.py (USD conversion under the attempt's root) -> q_rand.py
# A stop file (default _eval/out_rand/STOP) or a passed --deadline: no new attempt is launched, exit 98.
# and accepts a run only when every check passes (rand_lib.validate_attempt): slot and guard records, no Traceback, the
# done line of THIS attempt, result.json matching the request, record.csv shape, command seen by the policy, student path,
# material read back = request, push count / range / measured delta / firing states, every frame of the master and web
# videos through the frame gate, web copy h264 · 1280 x 720 · 30 fps · faststart, stills.
# A failed attempt is kept (its own folder a<k>, its own log) and the scene is retried in a new process (--tries).
# Stages:
#   smoke (5 s each, unless --skip_smoke)
#     S1 smoke_base    : base scene, black frame injected at state 30 -> must pass with a re-render at 30 (gate works in the loop)
#     S2 smoke_probe   : base scene with the friction probe -> probe used for the main scenes only if S2 passes and its
#                        trajectory equals S1 bit for bit (the probe changes nothing, and two processes give the same run)
#     S3 smoke_skyfail : sky forced at state 20 on every re-render -> must FAIL with FRAME_GATE and leave no video in place
#   main : base · push_lat · fric_low · fric_high (default 20 s), then cross-scene checks (same start fingerprints, same
#          terrain mesh, base and push equal before the first push) -> summary.json · summary.csv
# Outputs only under _eval/out_rand/<run_id>/ (logs flat in _eval/out_rand so isaac_slot's --scan_dirs sees them).
# Usage:
#   python rand_driver.py                      # smoke + 4 scenes
#   python rand_driver.py --stop_after_smoke   # smoke only (look at a still first)
#   python rand_driver.py --dry_run            # print the plan and the commands, run nothing, write nothing
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rand_gate as RG  # noqa: E402
import rand_lib as RL  # noqa: E402

DEFAULT_PUSH = "vy=+0.4;vy=-0.4;vy=+0.4;vy=-0.4"
STATE_COLS = [c for c in RL.COLUMNS if "probe" not in c]  # probe columns are NaN without the probe


def parse_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_id", default=time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--scenes", default="base,push_lat,fric_low,fric_high")
    ap.add_argument("--duration_s", type=float, default=20.0)
    ap.add_argument("--smoke_s", type=float, default=5.0)
    ap.add_argument("--skip_smoke", action="store_true")
    ap.add_argument("--stop_after_smoke", action="store_true")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--probe", choices=["auto", "on", "off"], default="auto")
    ap.add_argument("--push", default=DEFAULT_PUSH)
    ap.add_argument("--push_frame", choices=["heading", "world"], default="heading")
    ap.add_argument("--fric_low", type=float, default=0.2)
    ap.add_argument("--fric_high", type=float, default=1.5)
    ap.add_argument("--cmd", default="0.5,0.0,0.0")
    ap.add_argument("--eval_seed", type=int, default=1000)
    ap.add_argument("--checkpoint", default=RL.CKPT_DEFAULT)
    ap.add_argument("--train_yaml", default=RL.TRAIN_YAML_DEFAULT)
    ap.add_argument("--min_free_mib", type=int, default=4096)
    ap.add_argument("--stop_file", default=os.path.join(RL.OUT_RAND, "STOP"),
                    help="if this file exists no new attempt is launched (isaac_slot also refuses to launch, exit 98)")
    ap.add_argument("--deadline", type=float, default=0.0, help="epoch seconds; 0 = none. After it no attempt is launched")
    ap.add_argument("--dry_run", action="store_true")
    return ap.parse_args(argv)


def scene_specs(a):
    return {
        "base": {"kind": "none", "friction": (1.0, 1.0), "push": ""},
        "push_lat": {"kind": "push", "friction": (1.0, 1.0), "push": a.push},
        "fric_low": {"kind": "friction", "friction": (a.fric_low, a.fric_low), "push": ""},
        "fric_high": {"kind": "friction", "friction": (a.fric_high, a.fric_high), "push": ""},
    }


def script_args(a, scene, spec, attempt_id, outdir, duration, probe, inject=""):
    s = ["--scene", scene, "--kind", spec["kind"], "--attempt_id", attempt_id, "--outdir", outdir,
         "--checkpoint", a.checkpoint, "--train_yaml", a.train_yaml, "--cmd", a.cmd, "--duration_s", repr(float(duration)),
         "--eval_seed", str(a.eval_seed), "--friction", f"{spec['friction'][0]!r},{spec['friction'][1]!r}",
         "--restitution", "0.0", "--push_frame", a.push_frame]
    if spec["kind"] == "push":
        s += ["--push", spec["push"]]
    if probe:
        s += ["--friction_probe"]
    if inject:
        s += ["--test_inject", inject]
    return s


def expect_for(a, ck_sha, loaded_iter, dr, scene, spec, attempt_id, duration, adir):
    T = int(round(duration / RL.DT))
    fires = RL.predict_fire_states(dr["push_interval_s"][0], RL.DT, T)
    sched = RL.parse_push_schedule(spec["push"])
    return {"scene": scene, "attempt_id": attempt_id, "kind": spec["kind"], "checkpoint_sha256": ck_sha,
            "loaded_iter": loaded_iter, "cmd": [float(x) for x in a.cmd.split(",")], "duration_s": float(duration),
            "eval_seed": a.eval_seed, "friction": {"static": spec["friction"][0], "dynamic": spec["friction"][1], "restitution": 0.0},
            "push_expected": sum(1 for k, _ in enumerate(fires) if k < len(sched) and not sched[k]["none"]),
            "vel_range": dr["push_velocity_range"], "no_video": False, "usd_root": os.path.join(adir, "usd")}


def check_plan(a):
    """Everything that can be checked before any Isaac process: inputs exist, push schedule and friction inside the training
    ranges, outputs only under _eval/out_rand."""
    probs = []
    for p in (a.checkpoint, a.train_yaml):
        if not os.path.exists(p):
            probs.append(f"missing {p}")
    m = re.search(r"model_(\d+)\.pt$", os.path.basename(a.checkpoint))
    if not m:
        probs.append("checkpoint name is not model_<N>.pt")
    dr = RL.load_train_dr(a.train_yaml) if os.path.exists(a.train_yaml) else None
    specs = scene_specs(a)
    for s in a.scenes.split(","):
        if s not in specs:
            probs.append(f"unknown scene {s}")
    if dr is not None:
        pv = RL.plan_violations(RL.parse_push_schedule(a.push), dr["push_velocity_range"], a.push_frame)
        if pv:
            probs.append(f"push schedule outside the training range: {pv}")
        lo, hi = dr["material_static_range"]
        for v in (a.fric_low, a.fric_high):
            if not (lo <= v <= hi):
                probs.append(f"friction {v} outside the training range {lo}..{hi}")
    run_root = os.path.join(RL.OUT_RAND, a.run_id)
    RL.check_out_path(run_root)
    if os.path.exists(run_root) and not a.dry_run:
        probs.append(f"{run_root} exists (use a new --run_id; attempts are never overwritten)")
    return probs, dr, (int(m.group(1)) if m else None), run_root


class Driver:
    def __init__(self, a, dr, loaded_iter, run_root, runner=None):
        self.a, self.dr, self.loaded_iter, self.run_root = a, dr, loaded_iter, run_root
        self.ck_sha = RL.sha256_file(a.checkpoint)
        self.runner = runner or (lambda cmd: subprocess.run(cmd, cwd=RL.EVAL, env=RL.child_env()).returncode)
        self.manifest = {"run_id": a.run_id, "args": vars(a), "checkpoint_sha256": self.ck_sha,
                         "train_yaml_sha256": RL.sha256_file(a.train_yaml), "t_start": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "python": sys.executable, "code_sha256": {f: RL.sha256_file(os.path.join(HERE, f)) for f in
                                                                   ("q_rand.py", "rand_lib.py", "rand_gate.py", "rand_overlay.py", "rand_driver.py")},
                         "attempts": [], "stages": {}}

    def save(self):
        p = os.path.join(self.run_root, "manifest.json")
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(self.manifest, f, ensure_ascii=False, indent=1, default=str)
        os.replace(p + ".tmp", p)

    def attempt(self, scene, spec, k, duration, probe, inject="", dry=False):
        attempt_id = f"{self.a.run_id}.{scene}.a{k}"
        adir = os.path.join(self.run_root, scene, f"a{k}")
        log = os.path.join(RL.OUT_RAND, f"{self.a.run_id}__{scene}__a{k}.log")
        usd_root = os.path.join(adir, "usd")  # this attempt's own USD conversion root (isaac_slot v2 + usd_isolate_run)
        RL.check_out_path(adir)
        RL.check_out_path(log)
        RL.check_out_path(usd_root)
        cmd = RL.slot_guard_cmd(sys.executable, log, os.path.join(adir, "slot.json"), os.path.join(adir, "guard.json"),
                                script_args(self.a, scene, spec, attempt_id, adir, duration, probe, inject),
                                usd_root, attempt_id, stop_file=self.a.stop_file, deadline=self.a.deadline,
                                gpu=1, min_free_mib=self.a.min_free_mib)
        rec = {"scene": scene, "attempt": k, "attempt_id": attempt_id, "dir": adir, "log": log, "probe": probe,
               "inject": inject, "duration_s": duration, "cmd": cmd}
        if dry:
            return rec
        why = self.stop_reason()
        if why:
            self.stop(98, f"{why}: {attempt_id} not launched")
        os.makedirs(adir, exist_ok=False)
        t0 = time.time()
        rec["t_start"] = time.strftime("%Y-%m-%d %H:%M:%S")
        rec["rc"] = self.runner(cmd)
        rec["wall_s"] = round(time.time() - t0, 1)
        exp = expect_for(self.a, self.ck_sha, self.loaded_iter, self.dr, scene, spec, attempt_id, duration, adir)
        rec["validation"] = RL.validate_attempt(adir, log, exp, audit_fn=RG.audit, probe_fn=RG.probe)
        g = RL._load_json(os.path.join(adir, "guard.json")) or {}
        rec["guard_stopped"] = bool(g.get("stopped_by_guard"))
        rec["gpu"] = {k2: g.get(k2) for k2 in ("gpu_uuid", "min_free_mib", "max_used_mib", "wall_s")}
        with open(os.path.join(adir, "attempt.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1, default=str)
        self.manifest["attempts"].append({k2: rec[k2] for k2 in ("scene", "attempt", "attempt_id", "dir", "log", "rc", "wall_s",
                                                                  "probe", "inject", "guard_stopped", "gpu")} |
                                         {"ok": rec["validation"]["ok"],
                                          "failed_checks": [c["name"] for c in rec["validation"]["checks"] if not c["ok"] and c.get("blocking", True)],
                                          "warnings": rec["validation"].get("warnings", [])})
        self.save()
        fl = [c["name"] for c in rec["validation"]["checks"] if not c["ok"] and c.get("blocking", True)]
        print(f"ATTEMPT {attempt_id} rc={rec['rc']} ok={rec['validation']['ok']} failed={fl} warn={rec['validation'].get('warnings', [])} wall={rec['wall_s']}s "
              f"{time.strftime('%H:%M:%S')}", flush=True)
        if rec["rc"] == 98:  # isaac_slot did not launch (stop file or deadline while waiting for the lock)
            self.stop(98, f"isaac_slot refused to launch {attempt_id} (stop file or deadline)")
        return rec

    def stop_reason(self):
        if self.a.stop_file and os.path.exists(self.a.stop_file):
            return f"stop file {self.a.stop_file}"
        if self.a.deadline and time.time() > self.a.deadline:
            return f"deadline {self.a.deadline}"
        return ""

    def stop(self, code, why):
        print(f"STOP: {why}", flush=True)
        self.manifest["stopped"] = why
        self.manifest["t_end"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.save()
        sys.exit(code)

    def run_scene(self, scene, spec, duration, probe, inject="", tries=None):
        tries = tries or self.a.tries
        for k in range(1, tries + 1):
            rec = self.attempt(scene, spec, k, duration, probe, inject)
            if rec["guard_stopped"]:
                print(f"STOP: GPU guard stopped {rec['attempt_id']} (free memory below {self.a.min_free_mib} MiB)", flush=True)
                self.manifest["stopped"] = "gpu_guard"
                self.save()
                sys.exit(99)
            if rec["validation"]["ok"]:
                return rec
        return None


def load_rows(adir):
    z = np.load(os.path.join(adir, "traj.npz"))
    cols = [str(c) for c in z["columns"]]
    return {c: z["rows"][:, i] for i, c in enumerate(cols)}


def max_diff(ra, rb, n, cols=STATE_COLS):
    """Largest absolute difference over states 0..n-1 of the state columns (NaN equal to NaN)."""
    m = 0.0
    for c in cols:
        a, b = ra[c][:n], rb[c][:n]
        both_nan = np.isnan(a) & np.isnan(b)
        d = np.where(both_nan, 0.0, np.abs(a - b))
        d = np.where(np.isnan(d), np.inf, d)
        m = max(m, float(d.max()) if d.size else 0.0)
    return m


def smoke(d):
    a = d.a
    specs = scene_specs(a)
    out = {}
    s1 = d.run_scene("smoke_base", specs["base"], a.smoke_s, probe=False, inject="black_once:30", tries=2)
    if s1 is None:
        out["S1"] = "failed: the script does not complete a short base run"
        return out, False, False
    res1 = RL._load_json(os.path.join(s1["dir"], "result.json"))
    rr = res1["video"].get("rerenders", [])
    hit = [x for x in rr if x[0] == 30 and x[1] == "dark" and x[3]]
    out["S1"] = {"ok": True, "rerenders": rr, "black_frame_recovered_at_30": bool(hit),
                 "push_interval_states_actual": [e["state_j"] for e in res1["push"]["events"]],
                 "push_interval_states_predicted": res1["push"]["predicted_fire_states"],
                 "material_readback": res1["material_readback"]}
    if not hit:
        out["S1"]["problem"] = "the injected black frame at state 30 was not re-rendered: the loop gate is not working"
        return out, False, False
    probe_ok = False
    if a.probe == "auto":
        s2 = d.attempt("smoke_probe", specs["base"], 1, a.smoke_s, probe=True)
        if s2["validation"]["ok"]:
            n = int(round(a.smoke_s / RL.DT)) + 1
            md = max_diff(load_rows(s1["dir"]), load_rows(s2["dir"]), n)
            res2 = RL._load_json(os.path.join(s2["dir"], "result.json"))
            out["S2"] = {"ok": True, "max_abs_diff_vs_S1": md, "probe_stats": res2["stats"]["walk"]}
            probe_ok = md == 0.0
            if not probe_ok:
                out["S2"]["note"] = ("S1 and S2 differ: either the probe changes the run or two processes differ; the probe is "
                                     "not used (unconfirmed which)")
        else:
            out["S2"] = {"ok": False, "failed_checks": [c["name"] for c in s2["validation"]["checks"] if not c["ok"] and c.get("blocking", True)],
                         "note": "probe run failed; main scenes without the probe"}
    else:
        probe_ok = a.probe == "on"
        out["S2"] = f"skipped (--probe {a.probe})"
    s3 = d.attempt("smoke_skyfail", specs["base"], 1, a.smoke_s, probe=False, inject="sky_always:20")
    log = open(s3["log"], encoding="utf-8", errors="replace").read() if os.path.exists(s3["log"]) else ""
    in_place = [f for f in os.listdir(s3["dir"]) if f.endswith(".mp4")]
    failed_as_expected = (not s3["validation"]["ok"] and "FRAME_GATE frame 20" in log and "[RAND] FAIL" in log
                          and not in_place and not os.path.exists(os.path.join(s3["dir"], "result.json")))
    out["S3"] = {"failed_as_expected": failed_as_expected, "rc": s3["rc"], "videos_in_place": in_place,
                 "rejected": sorted(os.listdir(os.path.join(s3["dir"], "rejected"))) if os.path.isdir(os.path.join(s3["dir"], "rejected")) else []}
    if not failed_as_expected:
        out["S3"]["problem"] = "the forced sky frame did not stop the run: the loop gate does not refuse"
        return out, False, probe_ok
    return out, True, probe_ok


def cross_checks(d, accepted, smoke_base_dir=None):
    out = {}
    res = {s: RL._load_json(os.path.join(r["dir"], "result.json")) for s, r in accepted.items()}
    fps = {s: {k: v for k, v in r["fingerprint"].items() if k != "robot_material"} for s, r in res.items()}
    if smoke_base_dir:
        rs = RL._load_json(os.path.join(smoke_base_dir, "result.json"))
        fps["smoke_base"] = {k: v for k, v in rs["fingerprint"].items() if k != "robot_material"}
    ref = next(iter(fps.values())) if fps else {}
    out["same_start_fingerprints"] = {"equal": all(v == ref for v in fps.values()), "scenes": sorted(fps)}
    meshes = {s: r["terrain_mesh"] for s, r in res.items()}
    out["same_terrain_mesh"] = len({json.dumps(v) for v in meshes.values()}) <= 1
    if "base" in accepted and "push_lat" in accepted:
        ev = [e for e in res["push_lat"]["push"]["events"] if e["applied"]]
        if ev:
            j0 = ev[0]["state_j"]
            md = max_diff(load_rows(accepted["base"]["dir"]), load_rows(accepted["push_lat"]["dir"]), j0)
            out["base_vs_push_before_first_push"] = {"states": j0, "max_abs_diff": md, "equal": md == 0.0}
    if "base" in accepted:
        rb = load_rows(accepted["base"]["dir"])
        for s in ("fric_low", "fric_high"):
            if s in accepted:
                rf = load_rows(accepted[s]["dir"])
                n = len(rb["t_s"])
                first = next((j for j in range(n) if max_diff(rb, rf, j + 1) > 0.0), None)
                out[f"base_vs_{s}_first_differing_state"] = first
        if smoke_base_dir:
            n = int(round(d.a.smoke_s / RL.DT)) + 1
            md = max_diff(load_rows(smoke_base_dir), rb, n)
            out["smoke_base_vs_base_first_states"] = {"states": n, "max_abs_diff": md, "equal": md == 0.0,
                                                      "note": "same scene in two processes (with and without the probe if the probe is on)"}
    return out


def summarize(d, accepted, cross):
    rows, summ = [], {"run_id": d.a.run_id, "cross_checks": cross, "scenes": {}}
    for s, r in accepted.items():
        res = RL._load_json(os.path.join(r["dir"], "result.json"))
        v = res["video"]
        e = res["material_readback"]["effective"]["by_robot_mode"]
        e0 = next(iter(e.values()), {})
        pushes = [{k: x.get(k) for k in ("index", "state_j", "t_s", "dv_world_requested", "dv_world_measured", "heading_rad")}
                  for x in res["push"]["events"] if x["applied"]]
        summ["scenes"][s] = {"attempt": r["attempt_id"], "dir": r["dir"], "web": os.path.join(r["dir"], v["web"]),
                             "master": os.path.join(r["dir"], v["master"]), "stills": [os.path.join(r["dir"], p) for p in v["stills"]],
                             "fall": res["fall"], "pushes": pushes, "stats": res["stats"],
                             "friction_robot": res["friction_requested"], "material_readback": res["material_readback"],
                             "web_bytes": v["web_probe"]["bytes"], "rerender_calls": v["rerender_calls"],
                             "wall_s": res["wall_s"], "gpu": r.get("gpu")}
        w = res["stats"]["walk"]
        rows.append({"scene": s, "kind": res["kind"], "robot_static": res["friction_requested"]["static"],
                     "contact_static_computed": e0.get("static"), "combine_mode": e0.get("mode"),
                     "pushes_applied": len(pushes), "fell": res["fall"]["fell"], "fall_t_s": res["fall"]["t_s"],
                     "fall_reason": res["fall"]["reason"], "mean_vx_body_mps": w.get("mean_vx_body_mps"),
                     "mae_vx_mps": w.get("mae_vx_mps"), "contact_foot_speed_median_mps": w.get("contact_foot_speed_median_mps"),
                     "probe_ratio_p99": w.get("probe_friction_over_normal_p99"),
                     "web": summ["scenes"][s]["web"], "web_bytes": v["web_probe"]["bytes"]})
    with open(os.path.join(d.run_root, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summ, f, ensure_ascii=False, indent=1, default=str)
    if rows:
        with open(os.path.join(d.run_root, "summary.csv"), "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
    return summ


def main(argv=None, runner=None):
    a = parse_args(argv)
    probs, dr, loaded_iter, run_root = check_plan(a)
    if probs:
        print("PLAN PROBLEMS:", json.dumps(probs, ensure_ascii=False), flush=True)
        return 2
    specs = scene_specs(a)
    if a.dry_run:
        d = Driver(a, dr, loaded_iter, run_root, runner=lambda c: 0)
        plan = []
        if not a.skip_smoke:
            plan += [d.attempt("smoke_base", specs["base"], 1, a.smoke_s, False, "black_once:30", dry=True),
                     d.attempt("smoke_probe", specs["base"], 1, a.smoke_s, True, dry=True),
                     d.attempt("smoke_skyfail", specs["base"], 1, a.smoke_s, False, "sky_always:20", dry=True)]
        for s in a.scenes.split(","):
            plan.append(d.attempt(s, specs[s], 1, a.duration_s, a.probe == "on", dry=True))
        T = int(round(a.duration_s / RL.DT))
        fires = RL.predict_fire_states(dr["push_interval_s"][0], RL.DT, T)
        print(json.dumps({"run_root": run_root, "predicted_push_states": fires,
                          "predicted_push_times_s": [round(j * RL.DT, 2) for j in fires],
                          "push_items": [RL.describe_push(x, a.push_frame) for x in RL.parse_push_schedule(a.push)],
                          "attempts": [{k: p[k] for k in ("scene", "attempt_id", "dir")} for p in plan],
                          "commands": [" ".join(p["cmd"]) for p in plan]}, ensure_ascii=False, indent=1), flush=True)
        return 0
    os.makedirs(run_root)
    d = Driver(a, dr, loaded_iter, run_root, runner=runner)
    d.save()
    probe = a.probe == "on"
    smoke_base_dir = None
    if not a.skip_smoke:
        sm, ok, probe_ok = smoke(d)
        d.manifest["stages"]["smoke"] = sm
        d.save()
        print("SMOKE", json.dumps(sm, ensure_ascii=False, default=str)[:2000], flush=True)
        if not ok:
            print("STOP: smoke stage failed; no main scene was run", flush=True)
            return 5
        probe = probe_ok
        smoke_base_dir = next(x["dir"] for x in d.manifest["attempts"] if x["scene"] == "smoke_base" and x["ok"])
        if a.stop_after_smoke:
            print("SMOKE DONE (stop_after_smoke)", flush=True)
            return 0
    d.manifest["stages"]["probe_used"] = probe
    accepted, failed = {}, []
    for s in a.scenes.split(","):
        r = d.run_scene(s, specs[s], a.duration_s, probe)
        if r is None:
            failed.append(s)
        else:
            accepted[s] = r
    cross = cross_checks(d, accepted, smoke_base_dir)
    d.manifest["stages"]["main"] = {"accepted": {s: r["attempt_id"] for s, r in accepted.items()}, "failed": failed, "cross": cross}
    d.manifest["t_end"] = time.strftime("%Y-%m-%d %H:%M:%S")
    d.save()
    summarize(d, accepted, cross)
    print("CROSS", json.dumps(cross, default=str), flush=True)
    print(f"DONE accepted={sorted(accepted)} failed={failed} root={run_root}", flush=True)
    return 0 if not failed and cross.get("same_start_fingerprints", {}).get("equal") else 4


if __name__ == "__main__":
    sys.exit(main())
