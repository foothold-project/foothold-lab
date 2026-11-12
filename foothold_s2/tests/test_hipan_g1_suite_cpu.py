"""HiPAN G1 command suite: reference cells sit inside the EX-42 training slots, every other cell sits outside."""
from pathlib import Path

import yaml

from foothold_s2.eval.map_mode_cells import commands

PREP = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"


def _in(v, lo_hi):
    return lo_hi[0] <= v <= lo_hi[1]


def in_training_slot(cmd, r):
    vx, vy, wz = cmd
    if vx == vy == wz == 0:
        return True
    if vy == 0 and wz == 0 and (_in(vx, r["forward_vx"]) or _in(vx, r["reverse_vx"])):
        return True
    if vy == 0 and _in(vx, r["walk_vx"]) and _in(abs(wz), r["walk_wz_abs"]):
        return True
    if vx == 0 and vy == 0 and _in(abs(wz), r["spin_wz_abs"]):
        return True
    if vx == 0 and wz == 0 and _in(abs(vy), r["side_vy_abs"]):
        return True
    return wz == 0 and _in(abs(vx), r["diag_vx_abs"]) and _in(abs(vy), r["diag_vy_abs"])


def test_reference_cells_inside_and_probe_cells_outside_training_slots():
    doc = yaml.safe_load(PREP.read_text(encoding="utf-8"))
    ranges = next(v["ranges"] for v in doc.values() if isinstance(v, dict) and "ranges" in v and "shares" in v)
    cells = commands("hipan_g1")
    assert len(cells) == 20
    for name, cmd in cells.items():
        assert in_training_slot(cmd, ranges) == name.startswith("ref_"), name


def test_slot_check_catches_a_trained_command():
    doc = yaml.safe_load(PREP.read_text(encoding="utf-8"))
    ranges = next(v["ranges"] for v in doc.values() if isinstance(v, dict) and "ranges" in v and "shares" in v)
    assert in_training_slot((0.5, 0.55, 0.0), ranges) is False  # diag vy range ends at 0.5
    assert in_training_slot((0.5, 0.4, 0.0), ranges) is True
    assert in_training_slot((1.0, 0.0, 0.5), ranges) is False
