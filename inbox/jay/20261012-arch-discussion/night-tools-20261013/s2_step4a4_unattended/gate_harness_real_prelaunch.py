"""REHEARSAL ONLY. Same run_gate as production, REAL A3 prelaunch, but the run function never starts Isaac.

It exercises the unattended contract, the READY handshake with the real watchdog process and the
real A3 prelaunch (hash list, NVML, locks, process scan) on the real machine, then returns a HOLD
verdict instead of calling the A3 supervisor. No GPU work, no Job Object, no lease is kept.
"""
from __future__ import annotations

import argparse
import json
import sys
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
    block = outer["unattended"]
    real_prelaunch, _unused_real_run = g._real_functions(Path(block["bundle_dir"]))

    def run(manifest, appr):
        return {"verdict": "HOLD", "reasons": ["rehearsal_no_isaac_started"]}

    code = g.run_gate(outer, approval, watch_dir=a.watch_dir, gate_file=Path(__file__).resolve(),
                      watchdog_file=Path(block["watchdog_path"]), prelaunch_fn=real_prelaunch, run_fn=run)
    print(json.dumps({"gate_exit": code}), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
