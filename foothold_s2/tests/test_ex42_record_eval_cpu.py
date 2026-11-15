"""ex42_record_eval: the record children keep the recorded argv except the replaced values, and never write under scores."""
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("ex42_record_eval", Path(__file__).resolve().parents[2] / "_out" / "tools" / "ex42_record_eval.py")
rec = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rec)


def _score(tmp_path, state="done", rc=0):
    for name in rec.NAMES:
        argv = ["py", "-m", "x", "--checkpoint", "old.pt", "--out", "old_out", "--device", "cuda:9", "--seed", "42",
                "--kit_args=--/UJITSO/datastore/localCachePath=/old/cache"]
        if name == "d44":
            argv += ["--replica-dir", "old_mesh", "--expected-replica-sha256", "abc"]
        folder = tmp_path / "scores" / "m1" / "children" / name
        folder.mkdir(parents=True)
        (folder / "child.json").write_text(json.dumps({"argv": argv, "state": state, "rc": rc}))
    return tmp_path / "scores" / "m1"


def test_only_the_named_values_change(tmp_path):
    score, ckpt = _score(tmp_path), tmp_path / "m.pt"
    ckpt.write_bytes(b"x")
    out = tmp_path / "eval" / "record" / "m2"
    cmds = rec.plan_commands(score, ckpt, out, ["cuda:0", "cuda:1"])
    assert cmds["e1_v2_L5"]["device"] == "cuda:1" and cmds["d44"]["device"] == "cuda:0"
    d44 = cmds["d44"]["argv"]
    assert d44[d44.index("--checkpoint") + 1] == str(ckpt)
    assert d44[d44.index("--out") + 1] == str(out / "d44")
    assert d44[d44.index("--replica-dir") + 1] == str(out / "d44_mesh")
    assert d44[d44.index("--expected-replica-sha256") + 1] == "abc"
    assert d44[d44.index("--seed") + 1] == "42"
    assert not any("/old/cache" in a for a in d44)


def test_refusals(tmp_path):
    ckpt = tmp_path / "m.pt"
    ckpt.write_bytes(b"x")
    score = _score(tmp_path)
    with pytest.raises(rec.RecordRefused):
        rec.plan_commands(score, ckpt, tmp_path / "eval" / "scores" / "m2", ["cuda:0"])
    with pytest.raises(rec.RecordRefused):
        rec.plan_commands(score, tmp_path / "none.pt", tmp_path / "record" / "m2", ["cuda:0"])
    bad = _score(tmp_path / "b", state="failed", rc=1)
    with pytest.raises(rec.RecordRefused):
        rec.plan_commands(bad, ckpt, tmp_path / "record" / "m3", ["cuda:0"])
