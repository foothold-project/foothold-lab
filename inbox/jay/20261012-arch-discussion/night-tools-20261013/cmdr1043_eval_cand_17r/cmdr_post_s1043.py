"""1043 A-only aggregate, ported from cmdr_post_v10.py."""
# Historical v2-v10 notes below describe the source, not enabled 1043 behavior.
# CMD-R morning tables v2 (lead, 2026-10-13 00:20; rules from VERIFY-astra-7 2(c) and VERIFY-astra-8 section 5).
# Reads only runs the driver marked "valid" in out/cmdr_eval_driver.json (validated, stamped with the current pins,
# initial-state fingerprints equal within the group). Writes out/cmdr_post.json and out/CMDR-tables.md.
#   main pass (span time definition, ASTRA 7 proposal):  stop03 -> span_q2_pass,  fwd01 / fwd02 -> span_q1a_pass
#               (commanded-axis MAE <= min(0.15, 0.5 x command)),  other cells -> span_q1_pass.
#               n50 columns (q2_pass / q1a_pass / q1_pass) are kept as reference.
#   startup   : from traj.npz, states 1..50 (0 to 1 s) before the first invalid state (q_metrics.fall_index, span):
#               planar tracking error integral [m], yaw-rate error integral [rad], max yaw-rate error, base-contact
#               termination in the first second, 5 s survival, progress along the command at 5 s [m].
#               Failed episodes stay in: their counts are reported, integrals cover the valid part only.
#   paired    : episode i of seed s against episode i of seed s. on - off at the same update and branch - parent.
#               Newcombe method 10 interval, exact McNemar p (q_metrics). Holm over the three targets per update.
#   lines     : +10 pp on the target mean, -5 pp regression bound on the interval, MAE +10 % are the ASTRA 7 PROPOSAL
#               (team lead: "권고" confirmed 10/12; 2(c) is labelled 제안 and not yet confirmed). Shown, never adopted.
# v3 (00:30, VERIFY-astra-8b 3): startup split into episodes that completed the first second and early failures
# (counts, valid time, integrals of each group); empty groups give None, not an error; 5 s progress carries its n.
# MAE regression: relative +10 % when the control MAE > 0, otherwise absolute 10 % of the Q tolerance
# (vx, vy 0.15 m/s -> 0.015; wz 0.20 rad/s -> 0.02), as VERIFY-astra-7 2(c).
# v4 (10/13 09:58): the 2(c) lines are no longer a proposal. Team lead 01:10 「제안 · 권고대로 진행」 (HANDOFF-night-20261013
# line 34): 500 episodes per target cell; 「개선」 = every one of the three cells has a 95 % interval low end > 0 AND the
# equal-weight mean of the three on - off differences is >= +10 pp (VERIFY-astra-7 2(c) line 60 · VERIFY-astra-15 6.1).
# Per-cell interval readings are description, not the judgment; Holm over the three is shown beside it. (An earlier
# lead note said 「per cell, no three-cell average」: that misquoted the rule and is withdrawn, 10/13 10:02.) Regression = n=100 screen at 24000, cells with a point estimate <= -5 pp are measured
# again at n=500 (seeds 1001-1004, cmdr_eval_driver_v33 --plan remeasure) and judged on the interval against -5 pp
# (crossing = 「비퇴행 미확인」); MAE +10 % flagged; the basic contract (survival >= 95 %, command pass >= 90 %) is judged
# separately per arm and cell. Reads the valid runs of both driver logs (base + GPU 0 remeasure). Nothing here writes
# 「채택」 or 「기각」: that needs every family measured and the team lead.
# v5 (10/13 10:36, VERIFY-astra-16 1 / 4 / 5 / 7):
#   - paired intervals: Tango score interval (paired_ci.py; exact coverage checked, test_paired_ci.py) instead of the
#     pinned q_metrics.newcombe_paired, which is zero-width without discordant pairs (ASTRA 16 7.2). The Newcombe pair
#     is kept beside it as "newcombe" for comparison with earlier published numbers.
#   - the joint target judgment is written only when all three targets have both arms on all five seeds (500 pairs
#     each); before that it says 「수집 중 · 결합 판정 보류」 with the seeds and pairs it has.
#   - regression rows carry three statuses: pass rate (interval against -5 pp; a screen cell that was not flagged is
#     「비퇴행」 only if its own n=100 interval clears -5 pp, otherwise 「비퇴행 미확인」), MAE (contract line +10 %,
#     missing when not finite) and overall. Flagged cells also show the four new seeds alone (independent of the
#     screen) and seed-by-seed differences. Planned 99 cells: the measured and unmeasured lists are written.
#   - basic contract: k / n and Wilson intervals for survival and pass per cell, planned vs measured cells.
#   - inputs: episode ids 0..99 per run, equal lengths when pairing, the two logs' pins and checkpoint hashes must
#     agree, a run whose stamp carries output hashes is used only if they still match; log file hashes and as_of are
#     written. Never writes 「채택」 or 「기각」.
# v6 (10/13 11:17, VERIFY-astra-16c):
#   - MAE: a run counts only with all 100 episodes finite on that axis in BOTH arms; any shortfall is listed (arm, seed,
#     axis, finite n) and the axis is 「결측」 (overall 미확인), never judged on the remaining episodes (16c 2.1).
#     The +10 % line allows exactly 10 %: worse only when y - 1.1 x > 1e-9 x (float residue, 0.30 -> 0.33 is not over);
#     the absolute line (control 0) likewise with 1e-12 (16c 2.5).
#   - inputs: every log needs the five pinned files in pins, and a v3.3+ log needs experiment = cmdr_s1042_pair_eval.
#     Every valid run needs a readable stamp whose pins equal its log's pins and whose ckpt_sha256 equals its log's
#     checkpoint for that model; a stamp with stamp_version must also carry all four output hashes and they must match.
#     A stamp without stamp_version is the v3.2 form ("legacy", counted). Anything else is excluded and listed with the
#     reason in auth_fail (16c 2.2).
#   - target_verdict always has all three targets, with 0 pairs for a target that has no comparison yet (16c 4.3).
#   - overall labels say what they cover: 「퇴행 방지 조건 충족 (통과율 · MAE)」 / 「퇴행 방지 조건 미충족」 / 「미확인」.
#   - schema = "cmdr_post v6" so a page can refuse an older aggregate (16c 5).
#   - Markdown: the remeasure column carries n and seeds; the basic contract lists every measured cell (k/n, Wilson).
# v7 (10/13 11:59, VERIFY-astra-16e):
#   - one read per run: the stamp and the four output files are read once into memory; the hashes are taken from those
#     bytes and episodes.csv / traj.npz are parsed from the same bytes (no second read from disk, 16e 3.2). Every used
#     run's four hashes go into inputs_manifest (the input set this aggregate was computed from).
#   - legacy (v3.2) stamps are accepted only for runs owned by a v3.2 log and only when the stamp carries no new-format
#     field (stamp_version, out_sha256, attempt). Anything with a new-format trace but no stamp_version is rejected as
#     an ambiguous stamp; a run owned by a v3.3+ log needs a full new stamp (16e 3.1). legacy_tags lists them.
#   - both logs are hashed again after the computation; if either changed, nothing is written and the exit code is 3
#     (the caller runs the aggregate again) (16e 3.2).
#   - MAE: the line kind (relative +10 % or absolute 10 % of the axis tolerance) and its limit are written per axis;
#     the shortfall list (arm, seed, finite n) is kept on every regression row (16e 3.3).
#   - regression rows carry done = True when the row needs no more samples (screen not flagged, or 500 judged);
#     regression_coverage.done counts them apart from measured (16e 4).
#   - schema = "cmdr_post v7".
# v8 (10/13 13:15, VERIFY-astra-16g 3 / 4 / 5):
#   - a new-format stamp is used only when it is the run its log published: the owner log's last record for that tag
#     is valid and carries the same four output hashes and the same attempt as the stamp (16g 3.1: v7 accepted a newer
#     normal stamp over a log that still published the older run). Records without hashes never vouch for a new stamp.
#   - every file is read between two os.stat calls (inode, size, mtime_ns) and stat-checked again at the end; a change
#     of those attributes during its read or before the end stops the aggregate with exit 3 and nothing written (16g 3.2).
#     This DETECTS stat changes; it does not prove the bytes stayed the same (16i 5.3: a same-size rewrite with the same
#     mtime_ns is not seen). New-format runs are also bound to their published hashes; a frozen bundle is checked against
#     the hand-over manifest. Limit: a writer that replaces only files not yet read is not seen; the evaluator writes
#     meta.json last, and v3.7 moves a run's old folder away before it measures it again, so a run in progress has no stamp.
#   - an owner log whose attempt file says "revalidating", or names another attempt than the log, is being rebuilt by a
#     restarted driver: the aggregate is held (exit 5, nothing written) instead of mixing the old log with new stamps.
#     A v3.3+ owner log without a readable attempt file is held too (16i 5.2). The attempt files and the hold list are
#     read once and compared byte for byte at the end (exit 3 when changed). Records are looked up per owner log (16i 5.1).
#   - inputs_manifest keeps per run: form, origin (the stamp's origin field; "v3.2 legacy stamp" for a legacy stamp),
#     owner log, the record's and the stamp's attempt and the stamp's sha256 besides the four output hashes (16g 3.3 /
#     4). origin_counts sums them; legacy_stamps still counts stamps that are legacy now, not runs of legacy origin.
#   - out/cmdr_post_hold.json {tag: {stamp_sha256, why, released?}} keeps named runs out of every table (res["held"]
#     with the reason) until the entry carries an explicit "released" record (who, why, the new measurement's attempt).
#     A changed stamp alone is NOT a new measurement (v3.7 rewrites stamps when it re-validates); it is listed under
#     hold_candidates (16h 4.3, 16i 3).
#   - schema = "cmdr_post v8".
# v10 (10/13 16:15, VERIFY-astra-16k 4 / 7.2 and 16l 3.1 / 3.3 / 3.4 / 5.3; v9 was the 16l draft):
#   - a release frees a held run only when it names the new collection by its attempt AND its four output hashes and points
#     at saved evidence (a compare_stand result for that attempt and those hashes); the bytes on disk are those; the stamp
#     and the owner record vouch for them AND both name that collection attempt (v3.7 keeps the collection attempt when
#     it re-validates and names the checker in revalidated_by, driver 1224: no exception for another attempt, 16l 3.1);
#     and the collection is not the held original (whose stamp copy is found by the held stamp hash).
#   - the held original stamp and the evidence are each read once: the hash and the parse come from the same bytes, and
#     both are hashed again at the end like the other inputs (16l 3.3).
#   - CMDR_POST_BUNDLE=<frozen hand-over folder> reads the hold list, the held original stamps and the evidence from the
#     copies the freeze made (cmdr_post_hold.json, held_stamps/<tag>.json, evidence/<tag>.json; 16l 5.3).
#     CMDR_POST_HOLD=<file> names the hold list alone. A named hold list must exist, parse to a record and, when
#     CMDR_POST_HOLD_SHA256 is given, have those bytes; otherwise exit 6 and nothing is written (16l 3.4).
#   - a released run that then fails authentication is listed under release_auth_fail as well as auth_fail (16k 4).
#   - schema = "cmdr_post v10".
# Usage: python cmdr_post_v10.py    (CMDR_POST_OUT=<folder> for tests)
import csv
import json
import os

import hashlib
import io
import math
import sys
import time
import argparse
from pathlib import Path
import tempfile

import numpy as np

from s1043_manifest import load as load_manifest, check_inputs, sha256, inside

ap = argparse.ArgumentParser(allow_abbrev=False)
ap.add_argument("--manifest", required=True)
ap.add_argument("--expect_self_sha", required=True)
ap.add_argument("--cpu_fixture", action="store_true")
args = ap.parse_args()
print("sys.executable", sys.executable)
print("candidate.__file__", str(Path(__file__).resolve()))
print("candidate.sha256", sha256(__file__))
if sha256(__file__) != args.expect_self_sha:
    raise SystemExit("environment mismatch: self hash")
MANIFEST = load_manifest(args.manifest)
CONTRACT = MANIFEST["contract"]
problems = check_inputs(MANIFEST, require_files=not args.cpu_fixture)
if problems:
    raise SystemExit(f"registered inputs rejected: {problems[:4]}")
if any(os.environ.get(k) for k in ("CMDR_POST_OUT", "CMDR_POST_DEST", "CMDR_POST_BUNDLE", "CMDR_POST_HOLD")):
    raise SystemExit("legacy post environment override refused")
src_dir = str(Path(CONTRACT["inputs"]["source_paired_ci.py"]["path"]).parent)
sys.path.insert(0, src_dir)
import paired_ci as PCI
import q_metrics as Q

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = CONTRACT["paths"]["data"]
DEST = CONTRACT["paths"]["reports"]
if not all(inside(p) for p in (OUT, DEST)):
    raise SystemExit("post output root outside codexE")
MODELS = list(dict.fromkeys(j[0] for j in CONTRACT["plan"]["base"]))
CELLS = CONTRACT["evaluation"]["all_cell_names"]
TARGETS = list(CONTRACT["evaluation"]["commands"])
FAMILIES = list(dict.fromkeys(j[1] for j in CONTRACT["plan"]["base"]))
SEEDS = CONTRACT["evaluation"]["seeds"]


def main_col(cell):
    return "span_q2_pass" if cell == "stop03" else ("span_q1a_pass" if cell in ("fwd01", "fwd02") else "span_q1_pass")


def ref_col(cell):
    return "q2_pass" if cell == "stop03" else ("q1a_pass" if cell in ("fwd01", "fwd02") else "q1_pass")


def startup(z):
    traj, term = z["traj"].astype(np.float64), z["term"]
    cmd = z["cmd_hist"].astype(np.float64)
    out = []
    for e in range(traj.shape[1]):
        tr, c = traj[:, e], cmd[:, e]
        jf, _ = Q.fall_index(term[:, e], tr[:, 10], tr[:, 11], Q.DT, "span")
        jl = min(50, jf - 1)
        js = np.arange(1, jl + 1)
        lin = np.abs(tr[js, 4] - c[js, 0]) + np.abs(tr[js, 5] - c[js, 1])
        yaw = np.abs(tr[js, 9] - c[js, 2])
        j5 = 250
        prog = float("nan")
        if jf > j5 and np.linalg.norm(c[1, :2]) > 0:
            y0 = tr[0, 3]
            v = c[1, :2] / np.linalg.norm(c[1, :2])
            dw = np.array([np.cos(y0) * v[0] - np.sin(y0) * v[1], np.sin(y0) * v[0] + np.cos(y0) * v[1]])
            prog = float((tr[j5, :2] - tr[0, :2]) @ dw)
        out.append({"lin_err_int_m": float(lin.sum() * Q.DT), "yaw_err_int_rad": float(yaw.sum() * Q.DT),
                    "yaw_err_max": float(yaw.max()) if len(js) else float("nan"),
                    "contact_1s": bool(term[1:51, e].any()), "survive_5s": bool(jf > j5), "progress_5s_m": prog,
                    "valid_steps_1s": int(len(js))})
    return out


def load(tag, blobs):
    """parse the run from the bytes already hashed (16e 3.2): no second read from disk."""
    eps = sorted(csv.DictReader(io.StringIO(blobs["episodes.csv"].decode("utf-8"))), key=lambda r: int(r["episode"]))
    if [int(r["episode"]) for r in eps] != list(range(100)):
        raise ValueError(f"{tag}: episode ids are not 0..99")
    cell = eps[0]["cell"]
    if any(r["cell"] != cell for r in eps):
        raise ValueError(f"{tag}: mixed episode cells")
    if CONTRACT["evaluation"].get("mae_missing_policy") != "invalidate_entire_run":
        raise ValueError("MAE policy undecided")
    st = startup(np.load(io.BytesIO(blobs["traj.npz"])))
    mae, mae_n = {}, {}
    for k in ("vx", "vy", "wz"):
        v = [float(r[f"mae_{k}"]) for r in eps]
        f = [x for x in v if math.isfinite(x)]
        if len(f) != len(eps):
            raise ValueError(f"{tag}: nonfinite mae_{k}, entire run invalid")
        mae[k], mae_n[k] = (float(np.mean(f)) if f else float("nan")), len(f)
    return {"cell": cell, "main": [r[main_col(cell)] == "True" for r in eps], "ref": [r[ref_col(cell)] == "True" for r in eps],
            "surv": [r["span_survived"] == "True" for r in eps], "mae": mae, "mae_n": mae_n, "startup": st}


def filehash(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


LOGS = ["s1043A_base"]
EXPERIMENT = CONTRACT["experiment"]
OUT4 = ("meta.json", "cells.json", "episodes.csv", "traj.npz")
expected = {"cq_" + "_".join(map(str, j[:-1])) + "_s" + str(j[-1]): tuple(j)
            for j in CONTRACT["plan"]["A"]}
if len(expected) != 45:
    raise SystemExit("A plan must contain 45 unique tags")
name = LOGS[0]
p_log = Path(OUT) / (name + ".json")
raw_log = p_log.read_bytes()
d = json.loads(raw_log.decode("utf-8"))
if (d.get("version") != "1043-A1" or d.get("experiment") != EXPERIMENT or
        d.get("contract_sha256") != MANIFEST["contract_sha256"] or d.get("stage") != "A"):
    raise SystemExit("1043 A log identity mismatch")
if d.get("pair_fail") or d.get("skipped") or d.get("not_run") or d.get("not_valid"):
    raise SystemExit("A log has failures or missing runs")
if not d.get("complete") or not d.get("ended") or d.get("end_kind") != "complete":
    raise SystemExit("A log incomplete")
if d.get("matrix") != {t: "valid" for t in expected}:
    raise SystemExit("A matrix must contain exactly 45 valid tags")
records = d.get("runs")
if not isinstance(records, list) or len(records) != 45 or [r.get("tag") for r in records] != list(dict.fromkeys(r.get("tag") for r in records)):
    raise SystemExit("A records missing or duplicate")
if {r.get("tag") for r in records} != set(expected) or not all(r.get("valid") and r.get("attempt") for r in records):
    raise SystemExit("A run records invalid")
expected_pins = {k.removeprefix("source_").removeprefix("config_"): v["sha256"]
                 for k, v in CONTRACT["inputs"].items() if k.startswith(("source_", "config_"))}
for filename in ("s1043_manifest.py", "cmdr_bundle_compare_s1043.py", "cmdr_eval_driver_s1043.py",
                 "cmdr_post_s1043.py", "frozen_exec_s1043.py"):
    expected_pins[filename] = sha256(Path(HERE) / filename)
expected_pins["manifest_s1043.json"] = sha256(args.manifest)
if d.get("pins") != expected_pins:
    raise SystemExit("A log pins mismatch")
expected_ckpt = {"p20000": "parent_model", "off22000": "off_model_22000",
                 "on22000": "on_model_22000", "off24000": "off_model_24000", "on24000": "on_model_24000"}
for model in ("p20000", "off24000", "on24000"):
    rec = (d.get("ckpt") or {}).get(model)
    if not isinstance(rec, dict) or rec.get("sha256") != CONTRACT["inputs"][expected_ckpt[model]]["sha256"]:
        raise SystemExit("A checkpoint mismatch: " + model)
p_attempt = Path(OUT) / (name + ".attempt.json")
raw_attempt = p_attempt.read_bytes()
attempt = json.loads(raw_attempt.decode("utf-8"))
if attempt.get("attempt") != d.get("attempt") or attempt.get("state") != "ended":
    raise SystemExit("A attempt mismatch or rebuilding")
drv = {"matrix": d["matrix"], "pair_fail": [], "skipped": [], "owner": {t: name for t in expected},
       "log_pins": {name: d["pins"]}, "log_ckpt": {name: {m: v.get("sha256") for m, v in d["ckpt"].items()}},
       "rec": {(name, r["tag"]): r for r in records}, "inputs": {name: hashlib.sha256(raw_log).hexdigest()},
       "sidecar": {name: raw_attempt},
       "logs": {name: {"version": d["version"], "experiment": EXPERIMENT,
                       "runs": len(records), "ended": d["ended"], "attempt": d["attempt"]}}}
valid = sorted(expected)


STATS = {}


def _st(p):
    s_ = os.stat(p)
    return (s_.st_ino, s_.st_size, s_.st_mtime_ns)


def read_run(tag):
    """the stamp and the four output files, each read once (bytes) between two stats; the stats are kept for the end check."""
    b, st = {}, {}
    for f in ("driver_stamp.json",) + OUT4:
        p = os.path.join(OUT, tag, f)
        try:
            s1 = _st(p)
            with open(p, "rb") as fh:
                b[f] = fh.read()
            s2 = _st(p)
        except FileNotFoundError:
            b[f], st[f] = None, None
            continue
        if s1 != s2:
            print(f"INPUT CHANGED during the aggregate: {tag}/{f} while it was read; nothing written", file=sys.stderr)
            sys.exit(3)
        st[f] = s2
    STATS[tag] = st
    return b


NEW_FIELDS = ("stamp_version", "out_sha256", "attempt")


def auth(tag, m, blobs):
    if any(blobs[f] is None for f in ("driver_stamp.json",) + OUT4):
        return "stamp or output missing"
    try:
        stp = json.loads(blobs["driver_stamp.json"].decode("utf-8"))
    except (ValueError, UnicodeError):
        return "stamp unreadable"
    if not isinstance(stp, dict) or stp.get("stamp_version") != "1043-A1":
        return "legacy or wrong stamp version"
    if (stp.get("experiment") != EXPERIMENT or stp.get("contract_sha256") != MANIFEST["contract_sha256"] or
            stp.get("stage") != "A" or stp.get("origin") != "hashed-at-collection"):
        return "stamp 1043 identity mismatch"
    if stp.get("pins") != drv["log_pins"][name]:
        return "stamp pins mismatch"
    want = drv["log_ckpt"][name].get(m)
    if not want or stp.get("ckpt_sha256") != want:
        return "stamp checkpoint mismatch"
    hashes = stp.get("out_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(OUT4):
        return "stamp output hashes missing"
    if hashes != {f: hashlib.sha256(blobs[f]).hexdigest() for f in OUT4}:
        return "output hash mismatch"
    rec = drv["rec"].get((name, tag))
    if not rec or not rec.get("valid") or rec.get("out_sha256") != hashes:
        return "owner record mismatch"
    if not stp.get("attempt") or rec.get("attempt") != stp["attempt"]:
        return "collection attempt mismatch"
    return ""


R = {}
manifest = {}
pair_groups = {}
for tag in valid:
    m, fam, cell, noise, seed = expected[tag]
    blobs = read_run(tag)
    why = auth(tag, m, blobs)
    if why:
        raise SystemExit(f"A authentication rejected: {tag}: {why}")
    try:
        meta = json.loads(blobs["meta.json"].decode("utf-8"))
        ma = meta["args"]
        model_key = expected_ckpt[m]
        want_ckpt = CONTRACT["inputs"][model_key]
        if (ma["tag"], ma["families"], ma["cells"], ma["obs_noise"], ma["eval_seed"], ma["episodes"]) != (
                tag, fam, cell, noise == "on", seed, 100):
            raise ValueError("meta job contract")
        if (Path(ma["outdir"]).resolve() != Path(OUT).resolve() or
                Path(ma["checkpoint"]).resolve() != Path(want_ckpt["path"]).resolve() or
                meta["checkpoint_sha256"] != want_ckpt["sha256"] or
                ma["policy"] != "student" or ma["difficulty"] != 0.5 or
                ma["terrain_set"] != "train" or ma["heading_hold"] != 0 or
                ma["spawn_offset"] != "" or not ma["physx_small_buffers"]):
            raise ValueError("meta evaluator contract")
        device = CONTRACT["device"]
        if (device["gpu_index"] == "UNDECIDED" or device["gpu_uuid"] == "UNDECIDED") and not args.cpu_fixture:
            raise ValueError("device undecided")
        if device["gpu_index"] != "UNDECIDED":
            if (type(ma["physics_gpu"]) is not int or ma["physics_gpu"] != device["child_logical_cuda"] or
                    type(ma["active_gpu"]) is not int or ma["active_gpu"] != device["child_logical_cuda"] or
                    meta["devices"]["torch_cuda0_uuid"].removeprefix("GPU-") != str(device["gpu_uuid"]).removeprefix("GPU-")):
                raise ValueError("device index or UUID")
        pair = (meta["pairing_sha256"], meta["pairing_sha256_ext"], meta["terrain_mesh"],
                meta["terrain_origins_sha256"], meta["obs_shapes"], meta["eval_changes"])
        group = (fam, cell, noise, seed)
        if group in pair_groups and pair_groups[group] != pair:
            raise ValueError("pair fingerprint mismatch")
        pair_groups[group] = pair
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise SystemExit(f"A meta rejected: {tag}: {exc}")
    try:
        parsed = load(tag, blobs)
    except (ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"A run invalid: {tag}: {exc}") from exc
    if parsed["cell"] != cell:
        raise SystemExit(f"A cell mismatch: {tag}")
    R[(m, fam, cell, noise, seed)] = parsed
    stp = json.loads(blobs["driver_stamp.json"].decode("utf-8"))
    rec = drv["rec"][(name, tag)]
    manifest[tag] = {"form": "new", "origin": stp["origin"], "owner": name,
                     "record_attempt": rec["attempt"], "stamp_attempt": stp["attempt"],
                     "stamp_sha256": hashlib.sha256(blobs["driver_stamp.json"]).hexdigest(),
                     **{f: hashlib.sha256(blobs[f]).hexdigest() for f in OUT4}}
if len(R) != 45:
    raise SystemExit("A requires 45 valid unique runs")


def paired(xs, ys):
    """xs, ys: lists of per-episode booleans, same keys in the same order. Returns y - x (Tango score interval)."""
    if len(xs) != len(ys) or not xs:
        raise ValueError(f"pairing lengths {len(xs)} {len(ys)}")
    a = sum(x and y for x, y in zip(xs, ys))
    b = sum((not x) and y for x, y in zip(xs, ys))
    c = sum(x and (not y) for x, y in zip(xs, ys))
    d = sum((not x) and (not y) for x, y in zip(xs, ys))
    n = a + b + c + d
    diff, lo, hi = PCI.tango(b, c, n)  # b y only, c x only -> y - x
    _, nlo, nhi = Q.newcombe_paired(a, b, c, d)
    return {"n": n, "diff": diff, "lo": lo, "hi": hi, "method": "tango", "newcombe": [nlo, nhi], "p": Q.mcnemar_exact(b, c),
            "b_y_only": b, "c_x_only": c}


def pooled(m, fam, cell, noise, seeds):
    have = [s for s in seeds if (m, fam, cell, noise, s) in R]
    return have, sum((R[(m, fam, cell, noise, s)]["main"] for s in have), [])


def compare(mx, my, fam, cell, noise, seeds):
    sx, _ = pooled(mx, fam, cell, noise, seeds)
    sy, _ = pooled(my, fam, cell, noise, seeds)
    common = [s for s in sx if s in sy]
    if not common:
        return None
    xs = sum((R[(mx, fam, cell, noise, s)]["main"] for s in common), [])
    ys = sum((R[(my, fam, cell, noise, s)]["main"] for s in common), [])
    r = paired(xs, ys)
    r["seeds"] = common
    r["per_seed"] = {s: (sum(R[(my, fam, cell, noise, s)]["main"]) - sum(R[(mx, fam, cell, noise, s)]["main"])) / 100 for s in common}
    r["mae"] = {}
    for k, tol in (("vx", 0.15), ("vy", 0.15), ("wz", 0.20)):
        short = [{"arm": m_, "seed": s, "finite": R[(m_, fam, cell, noise, s)]["mae_n"][k]}
                 for s in common for m_ in (mx, my) if R[(m_, fam, cell, noise, s)]["mae_n"][k] != 100]
        if short:  # 16c 2.1: no judgement on the episodes that happen to remain
            r["mae"][k] = {"x": None, "y": None, "missing": True, "short": short, "worse_than_line": False}
            continue
        x = float(np.mean([R[(mx, fam, cell, noise, s)]["mae"][k] for s in common]))
        y = float(np.mean([R[(my, fam, cell, noise, s)]["mae"][k] for s in common]))
        worse = (y - 1.1 * x > 1e-9 * x) if x > 0 else (y - x > 0.1 * tol + 1e-12)  # exactly +10 % is allowed (16c 2.5)
        r["mae"][k] = {"x": x, "y": y, "rel": (y / x - 1.0) if x > 0 else None, "abs": y - x, "worse_than_line": bool(worse),
                       "missing": False, "line": "rel" if x > 0 else "abs", "limit": (1.1 * x) if x > 0 else (x + 0.1 * tol)}
    return r


def mae_status(p):
    over = sorted(k for k, v in p["mae"].items() if v.get("worse_than_line"))
    miss = sorted(k for k, v in p["mae"].items() if v.get("missing"))
    parts = ([f"{', '.join(over)} MAE 계약선 초과"] if over else []) + ([f"{', '.join(miss)} MAE 결측"] if miss else [])
    return {"over": over, "missing": miss, "text": " · ".join(parts) or "MAE 계약선 안",
            "lines": {k: {"line": v.get("line"), "limit": v.get("limit"), "x": v.get("x"), "y": v.get("y")} for k, v in p["mae"].items() if k in over},
            "short": {k: v["short"] for k, v in p["mae"].items() if v.get("short")}}


OK_LABEL, BAD_LABEL = "퇴행 방지 조건 충족 (통과율 · MAE)", "퇴행 방지 조건 미충족"


def overall(pass_status, ms):
    if pass_status == "퇴행" or ms["over"]:
        return BAD_LABEL
    if pass_status == "비퇴행" and not ms["missing"]:
        return OK_LABEL
    return "미확인"


res = {"targets": {}, "startup": {}, "cells": [], "holm": {}, "completion": {}, "target_verdict": {}, "regression_24000": {},
       "contract_24000": {}}


def cell_reading(p):
    """description of one target cell's interval (not the judgment)."""
    if p["lo"] > 0:
        return "구간 하한 0 위"
    return "구간 전체가 0 아래" if p["hi"] < 0 else "구간이 0 을 걸침"


def joint_verdict(ps):
    """2(c) as confirmed: 개선 = all three low ends > 0 and the equal-weight mean difference >= +10 pp (exact fractions)."""
    from fractions import Fraction
    mean = sum(Fraction(p["b_y_only"] - p["c_x_only"], p["n"]) for p in ps) / len(ps)
    low = all(p["lo"] > 0 for p in ps)
    return {"all_low_above_0": low, "mean_pp": float(100 * mean), "mean_ge_10": mean >= Fraction(1, 10),
            "verdict": "개선" if low and mean >= Fraction(1, 10) else "개선 아님"}


def regression_tag(p):
    """against the -5 pp line on the n=500 interval."""
    if p["hi"] < -0.05:
        return "퇴행"
    if p["lo"] >= -0.05:
        return "비퇴행"
    return "비퇴행 미확인"

for cell in TARGETS:
    row = {}
    for m in MODELS:
        have, xs = pooled(m, "flat", cell, "on", SEEDS)
        if have:
            row[m] = {"seeds": have, "n": len(xs), "rate": sum(xs) / len(xs), "ci": Q.wilson(sum(xs), len(xs)),
                      "per_seed": {s: float(np.mean(R[(m, "flat", cell, "on", s)]["main"])) for s in have},
                      "ref_rate_s1000": float(np.mean(R[(m, "flat", cell, "on", 1000)]["ref"])) if 1000 in have else None}
            st = sum((R[(m, "flat", cell, "on", s)]["startup"] for s in have), [])
            full = [x for x in st if x["valid_steps_1s"] == 50]
            early = [x for x in st if x["valid_steps_1s"] < 50]
            prog = [x["progress_5s_m"] for x in st if not np.isnan(x["progress_5s_m"])]
            mean = lambda v: float(np.mean(v)) if v else None  # noqa: E731
            res["startup"].setdefault(cell, {})[m] = {
                "n": len(st), "completed_1s": len(full), "early_fail_1s": len(early),
                "early_valid_s_mean": mean([x["valid_steps_1s"] * Q.DT for x in early]),
                "contact_1s": sum(x["contact_1s"] for x in st), "survive_5s": sum(x["survive_5s"] for x in st),
                "lin_err_int_m_completed": mean([x["lin_err_int_m"] for x in full]),
                "yaw_err_int_rad_completed": mean([x["yaw_err_int_rad"] for x in full]),
                "lin_err_int_m_early_partial": mean([x["lin_err_int_m"] for x in early]),
                "yaw_err_max_p90_completed": float(np.percentile([x["yaw_err_max"] for x in full], 90)) if full else None,
                "progress_5s_m_mean": mean(prog), "progress_5s_n": len(prog)}
    for u in ("22000", "24000"):
        r = compare(f"off{u}", f"on{u}", "flat", cell, "on", SEEDS)
        if r:
            row[f"on_minus_off_{u}"] = r
        for arm in ("off", "on"):
            r = compare("p20000", f"{arm}{u}", "flat", cell, "on", SEEDS)
            if r:
                row[f"{arm}{u}_minus_parent"] = r
    res["targets"][cell] = row
for u in ("22000", "24000"):
    got = {c: res["targets"][c].get(f"on_minus_off_{u}") for c in TARGETS}
    have = {c: (got[c]["seeds"] if got[c] else []) for c in TARGETS}
    complete = all(got[c] and have[c] == SEEDS and got[c]["n"] == 100 * len(SEEDS) for c in TARGETS)
    tv = {"cells": {c: (cell_reading(got[c]) if got[c] else "비교 없음") for c in TARGETS}, "complete": complete,
          "n_pairs": {c: (got[c]["n"] if got[c] else 0) for c in TARGETS}, "seeds_expected": SEEDS, "seeds_have": have,
          "seeds_missing": {c: [x for x in SEEDS if x not in have[c]] for c in TARGETS},
          "per_seed_diff": {c: (got[c]["per_seed"] if got[c] else {}) for c in TARGETS}}
    if all(got.values()):
        ps = [got[c]["p"] for c in TARGETS]
        res["holm"][u] = {"rejected": dict(zip(TARGETS, Q.holm_reject(ps))), "seeds": [have[c] for c in TARGETS]}
        tv["holm_rejected"] = res["holm"][u]["rejected"]
    if complete:
        tv.update(joint_verdict([got[c] for c in TARGETS]))
    else:
        tv["verdict"] = "수집 중 · 결합 판정 보류"
    res["target_verdict"][u] = tv
for fam in FAMILIES:
    for cell in CELLS:
        for noise in ("on", "off"):
            row = {"family": fam, "cell": cell, "noise": noise}
            for m in MODELS:
                k = (m, fam, cell, noise, 1000)
                if k in R:
                    row[m] = {"rate": float(np.mean(R[k]["main"])), "ref": float(np.mean(R[k]["ref"])),
                              "surv": float(np.mean(R[k]["surv"])), "mae": R[k]["mae"]}
            for u in ("22000", "24000"):
                r = compare(f"off{u}", f"on{u}", fam, cell, noise, [1000])
                if r:
                    r["regression_bound_crossed"] = bool(r["lo"] < -0.05)
                    r["mae_worse_than_line"] = bool(any(v["worse_than_line"] for v in r["mae"].values()))
                    row[f"on_minus_off_{u}"] = r
            if any(m in row for m in MODELS):
                res["cells"].append(row)
for m in MODELS:
    for fam in FAMILIES:
        res["completion"][f"{m}/{fam}"] = sum((m, fam, c, "on", 1000) in R for c in CELLS)
# regression at 24000 (2(c)): screen on seed 1000 (n=100); flagged cells judged on seeds 1000-1004 (n=500)
PLANNED = [(f, c, n) for f in FAMILIES for c in CELLS for n in ("on", "off") if n == "on" or f == "flat"]
for fam, cell, noise in PLANNED:
    key = f"{fam}/{cell}/{noise}"
    if fam == "flat" and noise == "on" and cell in TARGETS:
        p5 = res["targets"][cell].get("on_minus_off_24000")
        if not p5:
            continue
        done = p5["seeds"] == SEEDS
        ms = mae_status(p5)
        ps = regression_tag(p5) if done else "수집 중"
        res["regression_24000"][key] = {"stage": "n500 (target)" if done else "target (수집 중)", "n": p5["n"], "diff": p5["diff"],
                                        "lo": p5["lo"], "hi": p5["hi"], "per_seed": p5["per_seed"], "pass_status": ps,
                                        "mae": ms, "overall": overall(ps, ms), "verdict": ps, "done": done}
        continue
    s1 = compare("off24000", "on24000", fam, cell, noise, [1000])
    if not s1:
        continue
    row = {"screen_n": s1["n"], "screen_diff": s1["diff"], "screen_lo": s1["lo"], "screen_hi": s1["hi"]}
    if 100 * (s1["b_y_only"] - s1["c_x_only"]) > -5 * s1["n"]:  # not flagged (point estimate above -5 pp; same rule as the driver)
        ps = "비퇴행" if s1["lo"] >= -0.05 else "비퇴행 미확인"
        ms = mae_status(s1)
        row.update(stage="선별 비해당 · 추가 측정 없음", pass_status=ps, mae=ms, overall=overall(ps, ms))
    else:
        p5 = compare("off24000", "on24000", fam, cell, noise, SEEDS)
        if p5 and p5["seeds"] == SEEDS:
            ps = regression_tag(p5)
            ms = mae_status(p5)
            new = compare("off24000", "on24000", fam, cell, noise, [x for x in SEEDS if x != 1000])
            row.update(stage="선별 → 500 판", n=p5["n"], diff=p5["diff"], lo=p5["lo"], hi=p5["hi"], per_seed=p5["per_seed"],
                       pass_status=ps, mae=ms, overall=overall(ps, ms),
                       new400={"n": new["n"], "diff": new["diff"], "lo": new["lo"], "hi": new["hi"]} if new else None)
        else:
            ms = mae_status(s1)
            row.update(stage="선별 → 다시 재는 중", pass_status="다시 재는 중", mae=ms, overall="미확인",
                       seeds_have=(p5 or {}).get("seeds", [1000]))
    row["verdict"] = row["pass_status"]
    row["done"] = row["pass_status"] not in ("다시 재는 중", "수집 중")
    res["regression_24000"][key] = row
res["regression_coverage"] = {"planned": len(PLANNED), "measured": len(res["regression_24000"]),
                              "done": sum(1 for r in res["regression_24000"].values() if r["done"]),
                              "unmeasured": [f"{f}/{c}/{n}" for f, c, n in PLANNED if f"{f}/{c}/{n}" not in res["regression_24000"]]}
# basic contract per arm (survival >= 95 %, command pass >= 90 %, judged apart), seed 1000 n=100 per cell, point estimate
# with the Wilson interval beside it (ASTRA 16 4: the recorded rule sets a line, not an interval rule)
for m in ("off24000", "on24000"):
    rows = {}
    for fam, cell, noise in PLANNED:
        k = (m, fam, cell, noise, 1000)
        if k not in R:
            continue
        sv, ps = R[k]["surv"], R[k]["main"]
        rows[f"{fam}/{cell}/{noise}"] = {"surv_k": sum(sv), "pass_k": sum(ps), "n": len(ps), "surv": sum(sv) / len(sv), "pass": sum(ps) / len(ps),
                                         "surv_ok": sum(sv) >= 0.95 * len(sv), "pass_ok": sum(ps) >= 0.90 * len(ps),
                                         "surv_ci": Q.wilson(sum(sv), len(sv)), "pass_ci": Q.wilson(sum(ps), len(ps))}
    res["contract_24000"][m] = {"cells": rows, "n_cells": len(rows), "planned": len(PLANNED),
                                "unmeasured": [f"{f}/{c}/{n}" for f, c, n in PLANNED if f"{f}/{c}/{n}" not in rows],
                                "surv_below": sorted(k for k, v in rows.items() if not v["surv_ok"]),
                                "pass_below": sorted(k for k, v in rows.items() if not v["pass_ok"])}
res["n_valid_runs"] = len(R)
res["as_of"] = time.strftime("%Y-%m-%d %H:%M:%S")
res["inputs"] = drv.get("inputs", {})
res["changed_after_validation"] = []
res["interval_method"] = "tango score (paired_ci.py); newcombe kept for comparison"
res["schema"] = "cmdr_post_s1043 A1"
res["contract_sha256"] = MANIFEST["contract_sha256"]
res["experiment"] = EXPERIMENT
res["train_seed"] = 1043
res["stage"] = "A"
res["claim"] = CONTRACT["reporting"]["claim"]
res["a_complete"] = len(R) == 45
res["auth_fail"] = []
res["legacy_stamps"] = 0
res["legacy_tags"] = []
res["origin_counts"] = {}
for v_ in manifest.values():
    res["origin_counts"][v_["origin"]] = res["origin_counts"].get(v_["origin"], 0) + 1
res["inputs_manifest"] = manifest
for name in LOGS:
    p = os.path.join(OUT, f"{name}.json")
    if hashlib.sha256(Path(p).read_bytes()).hexdigest() != drv["inputs"][name]:
        raise SystemExit("INPUT CHANGED: driver log")
for tag_, st_ in STATS.items():
    for f_, s0 in st_.items():
        if _st(os.path.join(OUT, tag_, f_)) != s0:
            raise SystemExit("INPUT CHANGED: run file")
for name_, raw0 in drv["sidecar"].items():
    if (Path(OUT) / f"{name_}.attempt.json").read_bytes() != raw0:
        raise SystemExit("INPUT CHANGED: attempt")
res["driver_logs"] = drv["logs"]
res["driver_pair_fail"] = drv.get("pair_fail", [])
res["driver_invalid"] = drv.get("skipped", [])
json_bytes = (json.dumps(res, ensure_ascii=False, indent=1, default=float) + "\n").encode("utf-8")


def pct(v):
    return "" if v is None else f"{100 * v:.0f}"


def dfmt(p):
    return "" if not p else f"{100 * p['diff']:+.0f} [{100 * p['lo']:+.0f}, {100 * p['hi']:+.0f}] p={p['p']:.2g}"


L = ["# CMD-R 표 (자동 생성 · cmdr_post_s1043.py)", "",
     CONTRACT["reporting"]["claim"], "",
     "주 통과 = span 정의 (stop03 span_q2 · fwd01/02 span_q1a · 그 밖 span_q1). 차이는 같은 시드 · 같은 episode 끼리 짝지은 %p 와 95 % 구간.",
     "판정선은 팀장 확정 2(c) (10/13 01:10): 목표 칸마다 500 판 · 「개선」 = 세 칸 모두 95 % 구간 하한 > 0 이고 세 칸 평균 +10 %p 이상 · 퇴행은 100 판 훑기에서 점추정 −5 %p 이하 칸만 500 판으로 다시 재서 구간으로 판정 (−5 %p 를 걸치면 「비퇴행 미확인」) · MAE +10 % · 기본 계약 (생존 95 % · 통과 90 %) 은 따로. 이 표는 채택 · 기각을 쓰지 않는다.", "",
     "## 목표 세 칸 (평지 · noise 켬 · 시드 묶음)", "",
     "| 칸 | 부모 20000 | off 22000 | on 22000 | off 24000 | on 24000 | on−off 22000 | on−off 24000 |", "|---|---|---|---|---|---|---|---|"]
for c in TARGETS:
    r = res["targets"][c]
    L.append(f"| {c} | " + " | ".join(f"{pct(r[m]['rate'])} (n {r[m]['n']})" if m in r else "" for m in MODELS)
             + f" | {dfmt(r.get('on_minus_off_22000'))} | {dfmt(r.get('on_minus_off_24000'))} |")
L += ["", f"Holm (on−off, 목표 셋): {json.dumps(res['holm'], ensure_ascii=False)}",
      f"목표 판정 (세 칸 결합 · 칸별은 서술): {json.dumps(res['target_verdict'], ensure_ascii=False)}", "",
      "## 시작 직후 (0~1 s) · 5 s", "",
      "평면 오차 적분은 vx · vy 절대오차 합 (L1) × 0.02 s. 1 초를 다 채운 판과 1 초 안에 끝난 판을 나눠 적는다.", "",
      "| 칸 | 모델 | n | 1 s 채움 | 1 s 안 끝남 (평균 유효 s) | 1 s 안 몸통 접촉 | 5 s 생존 | 평면 오차 적분 m (채운 판) | yaw 오차 적분 rad (채운 판) | 5 s 진행 m (n) |",
      "|---|---|---|---|---|---|---|---|---|---|"]
f3 = lambda v, d=3: "" if v is None else f"{v:.{d}f}"  # noqa: E731
for c, d in res["startup"].items():
    for m, s in d.items():
        L.append(f"| {c} | {m} | {s['n']} | {s['completed_1s']} | {s['early_fail_1s']} ({f3(s['early_valid_s_mean'], 2)}) | "
                 f"{s['contact_1s']} | {s['survive_5s']} | {f3(s['lin_err_int_m_completed'])} | {f3(s['yaw_err_int_rad_completed'])} | "
                 f"{f3(s['progress_5s_m_mean'], 2)} ({s['progress_5s_n']}) |")
L += ["", "## 모든 칸 (시드 1000)", "", "| 지형 | 칸 | noise | 부모 | off 22000 | on 22000 | off 24000 | on 24000 | on−off 24000 |", "|---|---|---|---|---|---|---|---|---|"]
for r in res["cells"]:
    L.append(f"| {r['family']} | {r['cell']} | {r['noise']} | " + " | ".join(pct(r[m]["rate"]) if m in r else "" for m in MODELS)
             + f" | {dfmt(r.get('on_minus_off_24000'))} |")
L += ["", "## 채워진 칸 수 (noise 켬 · 시드 1000 · 지형마다 11 칸)", "", "| 모델 | " + " | ".join(FAMILIES) + " |", "|---|" + "---|" * len(FAMILIES)]
for m in MODELS:
    L.append(f"| {m} | " + " | ".join(str(res["completion"][f"{m}/{f}"]) for f in FAMILIES) + " |")
L += ["", f"## 24,000 퇴행 (on − off · Tango 구간) · 계획 {res['regression_coverage']['planned']} 칸 중 {res['regression_coverage']['measured']} 칸 잼", "",
      "| 칸 | 단계 | 선별 (n 100) | 다시 잼 (n · 시드) | 새 시드만 (n) | 통과율 | MAE | 퇴행 방지 |", "|---|---|---|---|---|---|---|---|"]
for k, r in res["regression_24000"].items():
    sc = "" if "screen_diff" not in r else f"{100 * r['screen_diff']:+.0f} [{100 * r['screen_lo']:+.1f}, {100 * r['screen_hi']:+.1f}]"
    n5 = "" if "lo" not in r else f"{100 * r['diff']:+.1f} [{100 * r['lo']:+.1f}, {100 * r['hi']:+.1f}] · n {r['n']} · 시드 {sorted(int(x) for x in r.get('per_seed', {}))}"
    nw = r.get("new400") or {}
    n4 = "" if not nw else f"{100 * nw['diff']:+.1f} [{100 * nw['lo']:+.1f}, {100 * nw['hi']:+.1f}] · n {nw['n']}"
    L.append(f"| {k} | {r['stage']} | {sc} | {n5} | {n4} | {r['pass_status']} | {r['mae']['text']} | {r['overall']} |")
L += ["", "## 24,000 기본 계약 (시드 1000 · 칸마다 100 판 · 점추정 · Wilson 95 % 구간)", ""]
for m, c in res["contract_24000"].items():
    L.append(f"- {m}: 계획 {c['planned']} 칸 중 {c['n_cells']} 칸 잼 · 생존 95 % 아래 {len(c['surv_below'])} 칸 · 통과 90 % 아래 {len(c['pass_below'])} 칸")
    for k, v in c["cells"].items():
        if True:  # every measured cell (16c 5)
            L.append(f"  - {k}: 생존 {v['surv_k']}/{v['n']} [{100 * v['surv_ci'][0]:.1f}, {100 * v['surv_ci'][1]:.1f}] · "
                     f"통과 {v['pass_k']}/{v['n']} [{100 * v['pass_ci'][0]:.1f}, {100 * v['pass_ci'][1]:.1f}]")
L += ["", f"유효 실행 {res['n_valid_runs']} · 짝 불일치 {len(res['driver_pair_fail'])} · 무효 {len(res['driver_invalid'])} · 기록 {json.dumps(res['driver_logs'], ensure_ascii=False)}"]
table_bytes = ("\n".join(L) + "\n").encode("utf-8")
Path(DEST).mkdir(parents=True, exist_ok=True)
for filename, content in (("cmdr_post.json", json_bytes), ("CMDR-tables.md", table_bytes)):
    target = Path(DEST) / filename
    with tempfile.NamedTemporaryFile(dir=DEST, prefix=filename + ".", suffix=".tmp", delete=False) as f:
        f.write(content)
        temp = Path(f.name)
    os.replace(temp, target)
print(f"valid runs {len(R)} · targets {[c for c in TARGETS if res['targets'][c]]} · holm {res['holm']}")
