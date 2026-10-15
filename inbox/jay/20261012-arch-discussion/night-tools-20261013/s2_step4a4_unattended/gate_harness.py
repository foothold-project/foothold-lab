"""TEST ONLY. Stand-in for s2_unattended_gate.py main: same run_gate, fake prelaunch and run functions.

The fake run function behaves like the A3 supervisor as far as the watcher can see: it writes a
status heartbeat for the chain, honours the STOP file, and (optionally) owns a real Windows Job
Object child so that killing this process must end that child. Never used for a live launch.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import s2_unattended_gate as g  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--approval", type=Path, required=True)
    ap.add_argument("--watch-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    outer = json.loads(a.manifest.read_text(encoding="utf-8"))
    approval = json.loads(a.approval.read_text(encoding="utf-8"))
    fake = outer.get("fake", {})
    marker = Path(fake["marker_dir"])
    mode, life = fake.get("mode", "healthy"), float(fake.get("life_s", 2.0))

    def prelaunch(manifest, appr):
        (marker / "prelaunch_called").write_text("1", encoding="utf-8")
        return {"status": "GO"} if fake.get("prelaunch", "GO") == "GO" else {"status": "NO_GO", "reason": "fake"}

    def run(manifest, appr):
        (marker / "run_called").write_text("1", encoding="utf-8")
        status, stop = Path(manifest["status_path"]), Path(manifest["stop_path"])
        if fake.get("job_child"):
            sys.path.insert(0, os.environ["S2_A3_DIR"])
            from s2_job_owner import JobOwner, WinKernel
            owner = JobOwner(WinKernel())
            owner.launch([sys.executable, "-B", "-c", "import time; time.sleep(600)"], HERE, os.environ.copy(),
                         log_path=marker / "child.log")
            (marker / "child_pid").write_text(str(owner.pid), encoding="utf-8")
        t0 = time.time()
        while time.time() - t0 < life:
            if mode != "hang" or time.time() - t0 < 1.0:
                g.atomic_write(status, {"chain_id": manifest["chain_id"], "state": "RUNNING",
                                        "heartbeat_epoch": time.time()})
            if stop.exists() and mode != "ignore_stop":
                return {"verdict": "HOLD", "reasons": ["STOP"]}
            if mode == "hang" and time.time() - t0 >= 1.0:
                time.sleep(600)
            time.sleep(0.2)
        return {"verdict": "PASS"}

    block = outer["unattended"]
    code = g.run_gate(outer, approval, watch_dir=a.watch_dir, gate_file=Path(__file__).resolve(),
                      watchdog_file=Path(block["watchdog_path"]), prelaunch_fn=prelaunch, run_fn=run)
    print(json.dumps({"gate_exit": code}), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
