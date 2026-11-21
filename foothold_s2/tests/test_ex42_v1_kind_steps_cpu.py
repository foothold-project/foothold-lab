"""ex42_v1_boundary_eval.sh --kind-steps (lead 2026-11-22 08:31 ledger 6adc47e29): steps per kind, 300 for every kind when not given (as before),
a bad value refuses. The real script in --print mode (no Kit). CPU only."""
from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ex42_v1_boundary_eval.sh"


def _print(tmp_path, *extra):
    ck = tmp_path / "model_250.pt"; ck.write_bytes(b"x")
    return subprocess.run(["bash", str(SCRIPT), "--checkpoint", str(ck), "--iter", "250", "--caps", "A/balance_beams=2,B/pallets=1",
                           "--out", str(tmp_path / "out"), "--print", *extra], capture_output=True, text=True)


def _steps(out):
    rows = [l.split("|") for l in out.splitlines() if l.count("|") >= 10]
    return {(r[2] + "/" + r[3], r[-1]) for r in rows}


def test_default_is_300_for_every_kind(tmp_path):
    r = _print(tmp_path)
    assert r.returncode == 0 and _steps(r.stdout) == {("A/balance_beams", "300"), ("B/pallets", "300")}


def test_kind_steps_only_for_the_named_kind(tmp_path):
    r = _print(tmp_path, "--kind-steps", "B/pallets=600,A/stepping_beams=600")
    assert r.returncode == 0 and _steps(r.stdout) == {("A/balance_beams", "300"), ("B/pallets", "600")}


def test_bad_value_refuses(tmp_path):
    r = _print(tmp_path, "--kind-steps", "B/pallets=6x")
    assert r.returncode == 2 and "bad --kind-steps" in r.stderr
