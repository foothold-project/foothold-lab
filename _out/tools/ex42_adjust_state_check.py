#!/usr/bin/env python3
"""3b check for a resumed EX-42 segment: the live adjustment state must equal the adjust file folded up to the start update.

Fold = the file's entries with key <= start_iter, in key order, later cells over earlier ones (what each applied change leaves live).
Live = the last ex42_update_adjust_m*.json receipt's `after` in the run folder; when a log is given and carries EX42_LIVE_RESTORE
(the live state right after the restore), that line is compared too. Cells the file never names are not compared.
  ex42_adjust_state_check.py --adjust FILE --out RUN_DIR --start-iter 1000 [--log LOG]      exit 0 equal / 1 differs / 2 unreadable
Read-only. The plain segment readback line shows the plan value, not the live one: do not use it for this.
"""
import argparse
import json
import re
import sys
from pathlib import Path

GROUPS = ("rewards", "commands", "runtime", "monitor")


def fold(doc, start_iter):
    state = {g: {} for g in GROUPS}
    for key in sorted((int(k) for k in doc["changes"]), key=int):
        if key > start_iter:
            continue
        for g in GROUPS:
            state[g].update(doc["changes"][str(key)].get(g, {}))
    return state


def last_receipt(out):
    found = sorted(Path(out).glob("ex42_update_adjust_m*.json"), key=lambda p: int(p.stem.rsplit("m", 1)[-1]))
    return None if not found else (int(found[-1].stem.rsplit("m", 1)[-1]), json.loads(found[-1].read_text(encoding="utf-8")))


def live_from_log(log):
    """The last EX42_LIVE_RESTORE line of rank 0 (all ranks read back the same values); None when the log has none."""
    last = None
    for line in Path(log).read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"EX42_LIVE_RESTORE (\{.*\})", line)
        if m:
            rec = json.loads(m.group(1))
            if rec.get("rank", 0) == 0:
                last = rec["values"]
    return last


def diff(expected, live, label):
    bad = []
    for g in GROUPS:
        for name, want in expected[g].items():
            have = (live or {}).get(g, {}).get(name)
            if have != want:
                bad.append(f"{label}: {g}.{name} file {want} live {have}")
    return bad


def check(adjust, out, start_iter, log=None):
    doc = json.loads(Path(adjust).read_text(encoding="utf-8"))
    expected = fold(doc, start_iter)
    receipt = last_receipt(out)
    bad = diff(expected, None if receipt is None else receipt[1]["after"], "last receipt after")
    if log is not None:
        live = live_from_log(log)
        if live is not None:
            bad += diff(expected, live, "log EX42_LIVE_RESTORE")
    return expected, receipt, bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--adjust", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start-iter", type=int, required=True)
    ap.add_argument("--log")
    a = ap.parse_args(argv)
    try:
        expected, receipt, bad = check(a.adjust, a.out, a.start_iter, a.log)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ADJUST_STATE unreadable: {type(exc).__name__}: {exc}")
        return 2
    cells = {g: v for g, v in expected.items() if v}
    if bad:
        print("ADJUST_STATE differs (live is not the adjust file's last state): " + "; ".join(bad))
        return 1
    print(f"ADJUST_STATE ok (receipt m{receipt[0] if receipt else 'none'} · file cells {json.dumps(cells, sort_keys=True)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
