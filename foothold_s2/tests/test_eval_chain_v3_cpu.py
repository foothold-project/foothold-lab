"""Known input checks using the actual first failed and corrected m1750 attempts."""

import json
from pathlib import Path
import shutil

import pytest

from foothold_s2 import basic_gait_eval_chain_v3 as chain


ROOT = Path("C:/Users/AI-WS01/s2_lab/basic_gait_runs/eval_w15/ex36a/m1750")
BAD = ROOT / "attempt_1793241260708584300/map64/map_modes.json"
GOOD = ROOT / "attempt_1793245411030099500/map64/map_modes.json"


def test_actual_four_command_attempt_is_caught():
    assert BAD.is_file(), BAD
    with pytest.raises(ValueError, match="lacks configured commands"):
        chain.command_gate(BAD)


def test_actual_thirteen_command_attempt_passes():
    assert GOOD.is_file(), GOOD
    row = chain.command_gate(GOOD)
    assert row["commands"] == 13 and len(row["modes"]) == 3
    with pytest.raises(ValueError, match="configured"):
        chain.command_gate(GOOD, 4)


def test_done_without_output_path_is_rejected(tmp_path):
    path = tmp_path / "status.json"
    with pytest.raises(ValueError, match="output_path"):
        chain.write_status(path, {"started": 1, "first_evidence": None,
                                  "done": 2, "output_path": None})
    assert not path.exists()
    chain.write_status(path, {"started": 1, "first_evidence": {"commands": 13},
                              "done": 2, "output_path": str(GOOD)})
    assert json.loads(path.read_text(encoding="utf-8"))["output_path"] == str(GOOD)


@pytest.mark.parametrize("sample,expected,called", [(BAD, "hold", 1), (GOOD, "done", 2)])
def test_chain_stops_after_first_bad_real_receipt(tmp_path, monkeypatch, sample, expected, called):
    checkpoints = [tmp_path / f"model_{i}.pt" for i in (1750, 2000)]
    for checkpoint in checkpoints:
        checkpoint.write_bytes(b"known checkpoint fixture")
    seen = []

    def copy_actual(_device, _checkpoint, _iteration, out):
        seen.append(out)
        (out / "map64").mkdir(parents=True)
        shutil.copyfile(sample, out / "map64" / "map_modes.json")
        (out / "w15_verified.json").write_text("{}", encoding="utf-8")
        return {"commands": list(chain.commands("extended"))}

    monkeypatch.setattr(chain, "run_once", copy_actual)
    monkeypatch.setattr(chain, "source_head", lambda _root: "a" * 40)
    row = chain.run_chain("cuda:0", checkpoints, tmp_path / "new_out")
    assert row["state"] == expected and len(seen) == called
    assert (row["first_evidence"].get("gate") == "failed") == (expected == "hold")
    assert (row["done"] is not None) == (expected == "done")
    assert (row["output_path"] is not None) == (expected == "done")
