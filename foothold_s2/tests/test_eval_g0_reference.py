"""EX-25(G0, 지도 없이 학습) model_1500 을 eval_map_modes 와 같은 조건으로 읽는 길 (SONNET-X25). CPU 만."""

import ast
import json
import subprocess
from pathlib import Path

import pytest

from foothold_s2.eval import compare_map_modes as cmp
from foothold_s2.tests.test_ex3031_window1 import _fake_result

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "foothold_s2/eval/eval_map_modes.py"
SH = ROOT / "foothold_s2/run_eval_g0_reference.sh"
CMDS = ("fwd0.5", "fwd1.0", "spin+1.2", "spin-1.2")


def _g0():
    base = _fake_result()
    row = dict(base["modes"]["eval_gt"]["fwd0.5"], gt_used=0)
    res = json.loads(json.dumps(base))
    res.update({"task": "FootholdS2-Go2-S2-X23-v0", "map_input": "none", "checkpoint_sha256": "b" * 64,
                "terrain_hash": {f"none/{c}": "ead62030" + "0" * 56 for c in CMDS}, "modes": {"none": {c: dict(row) for c in CMDS}}})

    return res


def test_reference_table_is_added_with_the_friction_note_when_conditions_match():
    out = cmp.table({"parent": _fake_result(), "ex30": _fake_result()}, _g0())

    assert "지도 없음 참조 열" in out and "마찰 고정(0.8/0.6) 으로 학습, 평가는 마찰 무작위 끔 같은 조건" in out and "EX-25(지도 없음): vx적분 m" in out
    assert out.count("\n| spin-1.2 |") == 1 and "FootholdS2-Go2-S2-X23-v0" in out
    assert "지도 없음 참조" not in cmp.table({"parent": _fake_result(), "ex30": _fake_result()})


@pytest.mark.parametrize("key,bad,match", [("envs", 32, "envs"), ("steps", 100, "steps"), ("dr_off", [], "dr_off"), ("curriculum_off", [], "curriculum_off")])
def test_reference_refused_when_run_conditions_differ(key, bad, match):
    g0 = _g0()
    g0[key] = bad

    with pytest.raises(ValueError, match=match):
        cmp.table({"parent": _fake_result()}, g0)


def test_reference_refused_for_other_terrain_other_commands_other_modes_or_a_map_checkpoint():
    g0 = _g0()
    g0["terrain_hash"] = {k: "0" * 64 for k in g0["terrain_hash"]}

    with pytest.raises(ValueError, match="지형 해시"):
        cmp.table({"parent": _fake_result()}, g0)
    g0 = _g0()
    g0["modes"]["none"].pop("fwd1.0")

    with pytest.raises(ValueError, match="명령"):
        cmp.table({"parent": _fake_result()}, g0)
    g0 = _g0()
    g0["modes"] = {"eval_gt": g0["modes"]["none"]}

    with pytest.raises(ValueError, match="참조 열은"):
        cmp.table({"parent": _fake_result()}, g0)
    g0 = _g0()
    g0["map_input"] = "reconstruction"

    with pytest.raises(ValueError, match="참조 열은"):
        cmp.table({"parent": _fake_result()}, g0)


def test_main_accepts_reference_flag(tmp_path, capsys):
    paths = {}

    for name, res in (("p", _fake_result()), ("e30", _fake_result()), ("e31", _fake_result()), ("g0", _g0())):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(res), encoding="utf-8")
    cmp.main(["x", str(paths["p"]), str(paths["e30"]), str(paths["e31"]), "--reference", str(paths["g0"])])

    assert "지도 없음 참조 열" in capsys.readouterr().out


def test_eval_script_registers_x23_and_gates_the_none_mode_on_the_saved_map_input():
    src = EVAL.read_text(encoding="utf-8")
    ast.parse(src)

    assert "import foothold_s2.x23_tasks" in src
    assert '(saved_map_input == "none") != (mode == "none")' in src
    assert 'map_mode=None if mode == "none" else mode' in src and '("eval_pred", "probe_prop_only", "none") and counts["gt"] != 0' in src
    assert src.index("saved_map_input") < src.index("adapters.S2Policy(")


def test_g0_run_script_shape_and_lf():
    text = SH.read_bytes()

    assert b"\r" not in text
    s = text.decode("utf-8")
    assert "--task FootholdS2-Go2-S2-X23-v0" in s and "--modes none" in s and "ex25-g0/model_1500.pt" in s and "MAPMODE_DONE" in s
    bash = r"C:\Program Files\Git\bin\bash.exe"
    r = subprocess.run([bash, "-n", str(SH)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)

    assert r.returncode == 0, r.stderr
