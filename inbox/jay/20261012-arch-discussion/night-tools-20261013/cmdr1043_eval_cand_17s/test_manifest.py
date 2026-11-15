"""CPU-only structural and fail-closed checks for the draft registration."""
import copy
import json
import sys
from pathlib import Path

from s1043_manifest import ROOT, assert_isolated, check_inputs, inside, launch_errors, load, sha256


def main():
    print("sys.executable", sys.executable)
    print("candidate.__file__", __file__)
    print("candidate.sha256", sha256(__file__))
    expected = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe").resolve()
    if Path(sys.executable).resolve() != expected or not inside(__file__):
        raise RuntimeError("환경 불일치")
    path = ROOT / "cand/manifest_s1043.json"
    m = load(path)
    print("ISOLATION", assert_isolated(m))
    assert check_inputs(m, require_files=False) == []
    assert len(m["contract"]["plan"]["A"]) == 45
    assert len(m["contract"]["plan"]["B_remaining"]) == 510
    assert len(m["contract"]["plan"]["screen_cells"]) == 96
    assert len(m["contract"]["plan"]["extra_possible"]) == 768
    blocked = launch_errors(m)
    assert any("undecided" in x for x in blocked), blocked
    bad = copy.deepcopy(m)
    bad["contract"]["paths"]["data"] = "C:/isaac/ext/go2_rl_robotlab/_eval/out"
    try:
        assert_isolated(bad)
        raise AssertionError("bad output path was accepted")
    except ValueError:
        pass
    bad = copy.deepcopy(m)
    bad["contract"]["train_seed"] = 1042
    tmp = ROOT / "cand/work/bad_manifest_hash.json"
    assert inside(tmp)
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(bad), encoding="utf-8")
    try:
        load(tmp)
        raise AssertionError("bad contract hash was accepted")
    except ValueError:
        pass
    print("PASS structural 555/45/510/96/768; launch blocked", len(blocked), "reasons; path and contract tamper rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
