"""창 2 자동 기동 판정 장치 (SONNET-X25). CPU 만. 판정은 순수 계산이고, 오케스트레이션은 가짜 실행기로 순서 · 중단을 시험한다."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from foothold_s2 import ex3031_window1_contract as w1
from foothold_s2 import window2_criteria as C
from foothold_s2 import window2_gate as G
from foothold_s2.tests.test_ex3031_window1 import _fake_result


def _res(iter_, vx05=2.0, vx10=4.0, alive05=64, alive10=60, mode="eval_gt"):
    r = _fake_result(iter_)
    for m in r["modes"]:
        r["modes"][m]["fwd0.5"].update(body_vx_integral_median_m=vx05, alive_envs_at_end=alive05)
        r["modes"][m]["fwd1.0"].update(body_vx_integral_median_m=vx10, alive_envs_at_end=alive10)
    r["fixed_terrain"] = {"rows": 10, "cols": 23, "levels_used": 3, "num_envs": 64, "assignment_sha256": "ab" * 32}

    return r


def _kids(**kw):
    return {"EX-30": _res(1750, **kw), "EX-31": _res(1750, **kw)}


def test_criteria_are_the_ones_the_lead_wrote_and_hash_is_line_ending_independent(tmp_path):
    assert C.COMMANDS == ("fwd0.5", "fwd1.0") and C.VX_RATIO_MIN == 0.90 and C.ALIVE_DROP_MAX == 0.10 and C.PARENT_MODE == "eval_gt" and C.CHILD_MODE == "eval_pred"
    raw = Path(C.__file__).read_bytes()

    assert len(C.criteria_sha256()) == 64 and C.criteria_sha256() == __import__("hashlib").sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def test_passes_at_the_exact_boundaries():
    parent = _res(1500, vx05=2.0, vx10=4.0, alive05=64, alive10=60)
    kids = _kids(vx05=1.8, vx10=3.6, alive05=58, alive10=54)                  # 정확히 0.90 배 · fwd0.5 부모 1.0 - 0.10 = 0.9 -> 58/64 · fwd1.0 부모 0.9375 - 0.10 = 0.8375 -> 54/64

    v = G.judge(parent, kids)

    assert v["passed"] and v["reasons"] == [] and len(v["rows"]) == 4


@pytest.mark.parametrize("kw,needle", [(dict(vx05=1.79), "fwd0.5 전진"), (dict(vx10=3.59), "fwd1.0 전진"), (dict(alive10=53), "fwd1.0 생존"), (dict(alive05=57), "fwd0.5 생존")])
def test_each_component_fails_alone_and_names_the_experiment(kw, needle):
    parent = _res(1500, vx05=2.0, vx10=4.0, alive05=64, alive10=60)
    base = dict(vx05=2.0, vx10=4.0, alive05=64, alive10=60)
    kids = {"EX-30": _res(1750, **base), "EX-31": _res(1750, **{**base, **kw})}
    v = G.judge(parent, kids)

    assert not v["passed"] and len(v["reasons"]) == 1 and v["reasons"][0].startswith("EX-31") and needle in v["reasons"][0]


def test_child_is_judged_with_eval_pred_and_parent_with_eval_gt_not_the_other_modes():
    parent = _res(1500)
    parent["modes"]["eval_pred"]["fwd0.5"]["body_vx_integral_median_m"] = 99.0           # 부모 eval_pred 는 기준이 아니다
    kids = _kids()
    for k in kids.values():
        k["modes"]["eval_gt"]["fwd0.5"]["body_vx_integral_median_m"] = 99.0              # 자식 eval_gt 가 좋아도 소용없다
        k["modes"]["eval_pred"]["fwd0.5"]["body_vx_integral_median_m"] = 0.1

    assert not G.judge(parent, kids)["passed"]
    ok = G.judge(parent, _kids())

    assert ok["passed"]


def test_spin_commands_do_not_matter_and_parent_without_forward_progress_is_not_passable():
    kids = _kids()
    for k in kids.values():
        k["modes"]["eval_pred"]["spin+1.2"]["body_vx_integral_median_m"] = -5.0
        k["modes"]["eval_pred"]["spin+1.2"]["alive_envs_at_end"] = 0

    assert G.judge(_res(1500), kids)["passed"]
    bad = G.judge(_res(1500, vx05=0.0), _kids(vx05=0.0))

    assert not bad["passed"] and any("뜻이 없다" in r for r in bad["reasons"])


def test_unequal_conditions_or_wrong_iterations_are_not_judged():
    parent, kids = _res(1500), _kids()
    kids["EX-30"]["envs"] = 32

    assert "조건 불일치" in G.judge(parent, kids)["reasons"][0]
    other = _kids()
    other["EX-30"]["fixed_terrain"] = None

    assert "조건 불일치" in G.judge(parent, other)["reasons"][0]
    assert any("회차" in r for r in G.judge(_res(1400), _kids())["reasons"]) and any("회차" in r for r in G.judge(parent, {"EX-30": _res(1700), "EX-31": _res(1750)})["reasons"])


def test_count_bad_finds_traceback_and_oom_case_insensitively():
    assert G.count_bad("ok\nTraceback (most recent call last)\nCUDA Out Of Memory") == {"Traceback": 1, "out of memory": 1, "OutOfMemory": 0}
    assert not any(G.count_bad("Learning iteration 1/250 ... all good").values())


# ------------------------------------------------------------------ 오케스트레이션 (가짜 실행기)
def _w1_dirs(tmp_path, exp, ok=True, traceback=False):
    run, log = tmp_path / f"run_{exp}", tmp_path / f"log_{exp}"
    run.mkdir()
    log.mkdir()
    (run / "rc.txt").write_text("rc=0\n" if ok else "rc=1\n")
    (run / "train.log").write_text("EX3031_W1_DONE {}\n" + ("Traceback (most recent call last)\n" if traceback else ""))
    for n in (*w1.EXPECTED_CHECKPOINTS, w1.CHILD_SPEC_NAME, "transfer_receipt.json", "window1_result.json", "cfg_pair_diff.json"):
        (log / n).write_text("x")

    return run, log


def _opts(tmp_path, **kw):
    r30, l30 = _w1_dirs(tmp_path, "EX-30", **kw.get("w30", {}))
    r31, l31 = _w1_dirs(tmp_path, "EX-31", **kw.get("w31", {}))

    return SimpleNamespace(ex30_run=str(r30), ex30_log=str(l30), ex31_run=str(r31), ex31_log=str(l31), out=str(tmp_path / "gate"), wait_limit_s=None)


class FakeRunner:
    def __init__(self, parent, kids, w2_fail_exp=None, eval_bad=None):
        self.calls, self.parent, self.kids, self.w2_fail_exp, self.eval_bad = [], parent, kids, w2_fail_exp, eval_bad

    def __call__(self, cmd, **kw):
        self.calls.append([str(c) for c in cmd])
        script = Path(cmd[1]).name

        if script == "run_eval_window1.sh":
            out = Path(cmd[-1])
            for name, data in (("parent_b1500", self.parent), ("ex30_1750", self.kids["EX-30"]), ("ex31_1750", self.kids["EX-31"])):
                (out / name).mkdir(parents=True)
                (out / name / "rc.txt").write_text("rc=0\n")
                (out / name / "run.log").write_text("MAPMODE_DONE\n" + ("Traceback\n" if self.eval_bad == name else ""))
                (out / name / "map_modes.json").write_text(json.dumps(data))
        elif script == "run_ex3031_window2.sh":
            exp, out = cmd[2], Path(cmd[-1])
            out.mkdir(parents=True)
            fail = self.w2_fail_exp == exp
            (out / "rc.txt").write_text("rc=0\n" + ("DONE 줄 없음\n" if fail else ""))
            (out / "train.log").write_text("" if fail else "EX3031_W2_DONE {}\n")

        return 0


def _go(tmp_path, runner, opts=None, **kw):
    sleeps = []

    return G.orchestrate(opts or _opts(tmp_path), run=runner, sleep=sleeps.append, now=lambda: f"t{len(runner.calls)}", **kw)


def test_pass_launches_ex30_then_ex31_on_cuda0_with_their_own_model_1750(tmp_path):
    runner = FakeRunner(_res(1500), _kids())
    opts = _opts(tmp_path)
    d = _go(tmp_path, runner, opts)

    assert d["passed"] and d["reasons"] == [] and [Path(c[1]).name for c in runner.calls] == ["run_eval_window1.sh", "run_ex3031_window2.sh", "run_ex3031_window2.sh"]
    assert [c[2] for c in runner.calls[1:]] == ["EX-30", "EX-31"] and all(c[3] == "cuda:0" for c in runner.calls[1:])
    assert runner.calls[1][4] == str(Path(opts.ex30_log) / "model_1750.pt") and runner.calls[2][4] == str(Path(opts.ex31_log) / "model_1750.pt")
    saved = json.loads((Path(opts.out) / "window2_decision.json").read_text(encoding="utf-8"))

    assert saved["criteria_file_sha256"] == C.criteria_sha256() and saved["passed"] is True and [x["exp"] for x in saved["launched"]] == ["EX-30", "EX-31"]


def test_failed_judgement_launches_nothing_and_leaves_the_reason(tmp_path):
    runner = FakeRunner(_res(1500), _kids(vx05=1.0))
    opts = _opts(tmp_path)
    d = _go(tmp_path, runner, opts)

    assert not d["passed"] and [Path(c[1]).name for c in runner.calls] == ["run_eval_window1.sh"] and any("전진" in r for r in d["reasons"])
    assert json.loads((Path(opts.out) / "window2_decision.json").read_text(encoding="utf-8"))["passed"] is False


@pytest.mark.parametrize("kw", [dict(w30=dict(traceback=True)), dict(w31=dict(ok=False))])
def test_window1_traceback_or_nonzero_rc_stops_before_even_evaluating(tmp_path, kw):
    runner = FakeRunner(_res(1500), _kids())
    d = _go(tmp_path, runner, _opts(tmp_path, **kw))

    assert not d["passed"] and runner.calls == [] and d["reasons"]


def test_window1_missing_final_checkpoint_stops(tmp_path):
    opts = _opts(tmp_path)
    (Path(opts.ex31_log) / "model_1750.pt").unlink()
    runner = FakeRunner(_res(1500), _kids())
    d = _go(tmp_path, runner, opts)

    assert not d["passed"] and runner.calls == [] and "model_1750.pt" in d["reasons"][0]


def test_traceback_in_an_eval_log_stops_before_judging(tmp_path):
    runner = FakeRunner(_res(1500), _kids(), eval_bad="ex30_1750")
    d = _go(tmp_path, runner)

    assert not d["passed"] and [Path(c[1]).name for c in runner.calls] == ["run_eval_window1.sh"] and any("Traceback" in r for r in d["reasons"])


def test_ex30_window2_failure_does_not_launch_ex31(tmp_path):
    runner = FakeRunner(_res(1500), _kids(), w2_fail_exp="EX-30")
    d = _go(tmp_path, runner)

    assert not d["passed"] and [c[2] for c in runner.calls if Path(c[1]).name == "run_ex3031_window2.sh"] == ["EX-30"] and "EX-30 창 2 실패" in d["reasons"][0]


def test_abort_file_and_wait_limit_stop_without_launching(tmp_path):
    opts = _opts(tmp_path)
    (Path(opts.out)).mkdir(parents=True)
    (Path(opts.out) / "ABORT").write_text("x")
    runner = FakeRunner(_res(1500), _kids())
    d = _go(tmp_path, runner, opts)

    assert not d["passed"] and runner.calls == [] and "ABORT" in d["reasons"][0]
    t2 = tmp_path / "second"
    t2.mkdir()
    o2 = SimpleNamespace(ex30_run=str(t2 / "none1"), ex30_log=str(t2 / "l"), ex31_run=str(t2 / "none2"), ex31_log=str(t2 / "l"), out=str(t2 / "gate"), wait_limit_s=60)
    d2 = G.orchestrate(o2, run=runner, sleep=lambda s: None, poll_s=30.0)

    assert not d2["passed"] and "60 초" in d2["reasons"][0] and runner.calls == []


def test_waits_until_both_window1_runs_have_rc(tmp_path):
    opts = _opts(tmp_path)
    rc31 = Path(opts.ex31_run) / "rc.txt"
    text = rc31.read_text()
    rc31.unlink()
    runner = FakeRunner(_res(1500), _kids())
    seen = []

    def sleep(s):
        seen.append(s)
        rc31.write_text(text)

    d = G.orchestrate(opts, run=runner, sleep=sleep, now=lambda: "t", poll_s=30.0)

    assert d["passed"] and seen == [30.0]


def test_scripts_exist_and_have_unix_line_endings():
    root = Path(G.ROOT)

    for n in ("run_eval_window1.sh", "run_ex3031_window2.sh"):
        assert (root / "foothold_s2" / n).is_file() and b"\r" not in (root / "foothold_s2" / n).read_bytes()


@pytest.mark.parametrize("who", ["parent", "EX-30", "EX-31"])
def test_missing_or_different_fixed_terrain_record_stops_the_judgement(who):
    parent, kids = _res(1500), _kids()
    target = {"parent": parent, "EX-30": kids["EX-30"], "EX-31": kids["EX-31"]}[who]
    target["fixed_terrain"] = None                                             # 셋 모두 None 이어도 «같다» 로 통과시키면 안 된다 -> 한 칸만 None 인 경우
    v = G.judge(parent, kids)

    assert not v["passed"] and v["rows"] == [] and "고정 지형 칸" in v["reasons"][0]
    parent2, kids2 = _res(1500), _kids()
    kids2[who if who != "parent" else "EX-30"]["fixed_terrain"] = {**parent2["fixed_terrain"], "assignment_sha256": "ee" * 32}

    assert "고정 지형 칸" in G.judge(parent2, kids2)["reasons"][0]


def test_all_three_without_fixed_terrain_is_also_refused():
    parent, kids = _res(1500), _kids()
    for r in (parent, *kids.values()):
        r["fixed_terrain"] = None

    assert "고정 지형 칸" in G.judge(parent, kids)["reasons"][0]
