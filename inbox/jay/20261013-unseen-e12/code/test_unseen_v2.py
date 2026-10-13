"""Known-answer tests for unseen_driver_v2.py without Isaac / GPU (lead 10/13).
1 the validator against the 100 real runs of the 10/12 night (all were valid: it must pass all 100)
2 broken copies of one real run must each fail with the right reason
3 frame counts: real videos match the source rows; a truncated copy does not
4 post: a non-zero exit and a missing row are failures
5 audit: a missing expected file is a failure, not a skipped file"""
import csv
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types

EV = "C:/isaac/ext/go2_rl_robotlab/_eval"
sys.path.insert(0, EV)
SRC = os.environ.get("UNSEEN_V2", os.path.join(EV, "unseen_driver.py"))


def load():
    spec = importlib.util.spec_from_file_location("ud2", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


fails = []


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:150], "want", repr(want)[:90])
    if not ok:
        fails.append(name)


if __name__ == "__main__":
    U = load()
    real = {t: U.validate_run(*s) for s in U.tags() for t in [s[-1]]}
    check("1 all 100 real runs validate", sorted(set(real.values())), [""])
    check("1b 100 tags", len(real), 100)

    tmp = tempfile.mkdtemp(prefix="u2t_", dir="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp")
    try:
        spec = ("E1", "20499", "gap", "fwd05", "un_e1_m20499_gap_fwd05")
        tag = spec[-1]

        def fresh():
            shutil.rmtree(os.path.join(tmp, "out"), ignore_errors=True)
            o = os.path.join(tmp, "out")
            os.makedirs(os.path.join(o, "full"))
            shutil.copytree(os.path.join(EV, "out", tag), os.path.join(o, tag))
            shutil.copytree(os.path.join(EV, "out", "full", tag), os.path.join(o, "full", tag))
            for ext in (".log", ".guard.json"):
                shutil.copy(os.path.join(EV, "out", tag + ext), os.path.join(o, tag + ext))
            U.OUT = o
            return o

        o = fresh()
        check("2a copy validates", U.validate_run(*spec), "")
        lp = os.path.join(o, tag + ".log")
        s = open(lp, encoding="utf-8", errors="replace").read()
        open(lp, "w", encoding="utf-8").write(s.replace("[Q-EVAL] done", "[Q-EVAL] dune"))
        check("2b no completion line", U.validate_run(*spec), "log has no completion line for this tag and N")
        open(lp, "w", encoding="utf-8").write(s + "\nTraceback (most recent call last):\n  x\n")
        check("2c traceback", U.validate_run(*spec), "Python Traceback in log")
        o = fresh()
        mp = os.path.join(o, tag, "meta.json")
        m = json.load(open(mp, encoding="utf-8"))
        m["args"]["obs_noise"] = True
        json.dump(m, open(mp, "w", encoding="utf-8"))
        check("2d wrong arg", U.validate_run(*spec), "arg obs_noise=True want False")
        o = fresh()
        check("2e other model's checkpoint", U.validate_run("E2", "20499", "gap", "fwd05", tag).startswith("arg checkpoint"), True)
        o = fresh()
        ep = os.path.join(o, tag, "episodes.csv")
        rows = open(ep, encoding="utf-8").read().splitlines()
        open(ep, "w", encoding="utf-8").write("\n".join(rows[:-1]) + "\n")
        check("2f 99 episodes", U.validate_run(*spec), "episodes.csv ids / family / cell")
        o = fresh()
        fs = list(csv.DictReader(open(os.path.join(o, "full", tag, "episodes_summary.csv"), encoding="utf-8")))
        lab = next(r["file"] for r in fs if r["labels"])
        os.remove(os.path.join(o, "full", tag, lab))
        check("2g labelled full record file missing", U.validate_run(*spec), f"full record file missing {lab}")
        o = fresh()
        sp = os.path.join(o, "full", tag, "episodes_summary.csv")
        fs = list(csv.DictReader(open(sp, encoding="utf-8")))
        fs[0]["survived"] = "True" if fs[0]["survived"] == "False" else "False"
        with open(sp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, list(fs[0].keys()))
            w.writeheader()
            w.writerows(fs)
        check("2g2 summary survival disagrees with episodes.csv", U.validate_run(*spec), f"full record episode {int(fs[0]['episode'])} does not match episodes.csv")
        o = fresh()
        gp = os.path.join(o, tag + ".guard.json")
        g = json.load(open(gp, encoding="utf-8"))
        g["stopped_by_guard"] = True
        json.dump(g, open(gp, "w", encoding="utf-8"))
        check("2h guard stopped", U.validate_run(*spec).startswith("guard exit"), True)
        # stamp / reuse
        o = fresh()
        U.stamp(tag, "t")
        check("2i stamped copy reusable", U.reusable(spec), True)
        with open(os.path.join(o, tag, "cells.json"), "a", encoding="utf-8") as f:
            f.write(" ")
        check("2j changed output not reusable", U.reusable(spec), False)

        # 3 frame counts
        sel = json.load(open(os.path.join(EV, "out", "unseen_sel.json"), encoding="utf-8"))
        x = dict(sel[0])
        x["rows"] = int(next(r for r in csv.DictReader(open(os.path.join(EV, "out", "full", x["tag"], "episodes_summary.csv"), encoding="utf-8"))
                             if r["file"] == x["file"])["rows"])
        check("3a replay / HUD / web frames == source rows", [U.video_ok(x, k) for k in ("video", "hud", "web")], [True, True, True])
        cut = os.path.join(tmp, "cut.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", x["video"], "-frames:v", "500", "-c", "copy", cut], check=True)
        y = dict(x, video=cut)
        check("3b truncated copy fails", U.video_ok(y, "video"), False)
        check("3c missing file -> -1", U.frames(os.path.join(tmp, "none.mp4")), -1)

        # 4 post: stub the post-process, check the row contract
        o = fresh()
        U.LOG["failures"] = []
        real_run = U.subprocess.run
        U.subprocess = types.SimpleNamespace(run=lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="ok", stderr=""))
        want = [t for *_, t in U.tags()]
        with open(os.path.join(o, "UNSEEN-cells.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, ["tag"])
            w.writeheader()
            w.writerows({"tag": t} for t in want)
        U.stage_post()
        check("4a all rows -> no failure", U.LOG["failures"], [])
        with open(os.path.join(o, "UNSEEN-cells.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, ["tag"])
            w.writeheader()
            w.writerows({"tag": t} for t in want[:-1])
        U.stage_post()
        check("4b one row missing -> failure", [f["stage"] for f in U.LOG["failures"]], ["post"])
        U.LOG["failures"] = []
        U.subprocess = types.SimpleNamespace(run=lambda *a, **k: types.SimpleNamespace(returncode=1, stdout="", stderr="boom"))
        U.stage_post()
        check("4c exit 1 -> failure", [f["what"][:22] for f in U.LOG["failures"]], ["unseen_post.py exit 1:"])
        U.subprocess = types.SimpleNamespace(run=real_run)

        # 5 audit: one real item with its web copy missing -> expected 3, audited 2, failure
        U.LOG["failures"] = []
        z = dict(sel[0], web=os.path.join(tmp, "missing_web.mp4"))
        json.dump([z], open(os.path.join(o, "unseen_sel.json"), "w", encoding="utf-8"))
        U.stage_audit()
        a = U.LOG["stages"]["audit"]
        check("5a expected / audited / missing", (a["expected"], a["audited"], len(a["missing"]), a["bad"]), (3, 2, 1, []))
        check("5b missing file is a failure", [f["stage"] for f in U.LOG["failures"]], ["audit"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("FAILS", fails)
