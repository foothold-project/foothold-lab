"""The canon sentence -> training value check has to turn red on the E1 level cap that never rose (5, 5, 5, 5)."""
import copy
import json
from pathlib import Path

import pytest
import yaml

from foothold_s2 import ex42_canon_params_check as cpc

CAP_QUOTE = "| 레벨 | 상한 5 → **9** · 경계마다 +1 · 성과 승급"
CANON = f"## E1\n{CAP_QUOTE}(결정)\n| critic | E1 경계에서 켠다 |\n| 벌점 | `foot_slip` 0 → −0.25 |\n"
CLAIMS = {"schema": "ex42-canon-claims/1", "claims": [
    {"id": "cap", "stage": "E1", "canon_quote": CAP_QUOTE,
     "actual": {"source": "stage_config", "path": "terrain.exposure_at_E1.positive.0.level_cap"},
     "expect": {"kind": "raise_per_boundary", "start": 5, "step": 1, "end": 9,
                "plan_schedule_path": "terrain.continuous_level_cap", "hold_event": None},
     "observe": {"source": "map_switch", "field": "on.terrain_level_mean"}},
    {"id": "mirror", "stage": "E1", "canon_quote": "E1 경계에서 켠다",
     "actual": {"source": "stage_config", "path": "critic_mirror"}, "expect": {"kind": "equals", "value": True}},
    {"id": "slip", "stage": "E1", "variant": "slip_retrain", "canon_quote": "`foot_slip` 0 → −0.25",
     "actual": {"source": "env_yaml", "path": "rewards.ex41_foot_slip.weight"},
     "expect": {"kind": "equals", "value": -0.25}},
]}


def stage_row(cap, mirror=True):
    return {"id": "E1", "critic_mirror": mirror,
            "terrain": {"exposure_at_E1": {"positive": [{"family": "A", "kinds_of": "continuous", "exposure": 1.0, "level_cap": cap}]}}}


def run_dir(tmp_path, caps, slip=-0.25, events=()):
    folder = tmp_path / "run"
    (folder / "params").mkdir(parents=True)
    (folder / "params" / "env.yaml").write_text(   # the real file carries python tags
        f"rewards:\n  ex41_foot_slip:\n    weight: {slip}\n    range: !!python/tuple [0.0, 1.0]\n", encoding="utf-8")
    (folder / "params" / "agent.yaml").write_text("max_iterations: 1000\n", encoding="utf-8")
    rows = [{"event": "p1_queued", "stage_id": "E1", "checkpoint_iteration": 250 * (i + 1), "stage_config": stage_row(cap)}
            for i, cap in enumerate(caps)]
    rows += [{"event": name, "stage_id": stage, "checkpoint_iteration": update} for name, update, stage in events]
    rows.append({"event": "p1_queued", "stage_id": "E0", "checkpoint_iteration": 250, "stage_config": stage_row(0, False)})
    (folder / "ex42_application.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (folder / "map_switch.jsonl").write_text(
        "".join(json.dumps({"it": i, "on": {"terrain_level_mean": 4.9}}) + "\n" for i in (1, 2)), encoding="utf-8")
    return folder


def verdicts(report):
    return {row["id"]: row["verdict"] for row in report["rows"]}


def run(tmp_path, caps, claims=CLAIMS, canon=CANON, variant="slip_retrain", **kw):
    return cpc.check(claims, canon, cpc.Sources("E1", run_dir=run_dir(tmp_path, caps, **kw)), variant)


def test_a_cap_that_rises_one_per_boundary_passes(tmp_path):
    report = run(tmp_path, [5, 6, 7, 8])
    assert report["passed"] and verdicts(report) == {"cap": "PASS", "mirror": "PASS", "slip": "PASS"}
    assert report["rows"][0]["observed"] == {"field": "on.terrain_level_mean", "min": 4.9, "max": 4.9, "n": 2}


def test_the_finished_e1_shape_is_red(tmp_path):
    report = run(tmp_path, [5, 5, 5, 5])
    row = report["rows"][0]
    assert not report["passed"] and row["verdict"] == "FAIL"
    assert all(f"boundary {u}: 5 after 5, expected 6" in row["detail"] for u in (500, 750, 1000))


@pytest.mark.parametrize("caps", [[5, 7, 8, 9], [5, 6, 5, 6], [4, 5, 6, 7], [5, 6, 7, 8, 9, 10], [5, 6, 6, 7]])
def test_broken_cap_series_are_red(tmp_path, caps):
    assert verdicts(run(tmp_path, caps))["cap"] == "FAIL"


def test_the_cap_stays_at_the_end_value(tmp_path):
    assert verdicts(run(tmp_path, [5, 6, 7, 8, 9, 9]))["cap"] == "PASS"


def test_a_boundary_without_a_raise_needs_its_recorded_hold(tmp_path):
    claims = copy.deepcopy(CLAIMS)
    claims["claims"][0]["expect"]["hold_event"] = "level_cap_hold"
    assert verdicts(run(tmp_path / "a", [5, 5, 6, 7], claims=claims, events=[("level_cap_hold", 500, "E1")]))["cap"] == "PASS"
    assert verdicts(run(tmp_path / "b", [5, 5, 6, 7], claims=claims, events=[("level_cap_hold", 750, "E1")]))["cap"] == "FAIL"
    assert verdicts(run(tmp_path / "d", [5, 5, 6, 7], claims=claims, events=[("level_cap_hold", 500, "E0")]))["cap"] == "FAIL"
    assert verdicts(run(tmp_path / "c", [5, 5, 6, 7], claims=claims))["cap"] == "FAIL"


def test_a_changed_canon_sentence_turns_the_row_stale(tmp_path):
    report = run(tmp_path, [5, 6, 7, 8], canon=CANON.replace("**9**", "**6**"))
    assert not report["passed"] and verdicts(report)["cap"] == "STALE"


def test_a_value_that_differs_from_the_canon_is_red(tmp_path):
    report = run(tmp_path, [5, 6, 7, 8], slip=-0.15)
    assert not report["passed"] and verdicts(report)["slip"] == "FAIL"
    assert "-0.15" in report["rows"][2]["detail"] and "-0.25" in report["rows"][2]["detail"]


def test_a_missing_place_is_not_a_pass(tmp_path):
    folder = run_dir(tmp_path, [5, 6, 7, 8])
    (folder / "params" / "env.yaml").write_text("rewards: {}\n", encoding="utf-8")
    report = cpc.check(CLAIMS, CANON, cpc.Sources("E1", run_dir=folder), "slip_retrain")
    assert not report["passed"] and verdicts(report)["slip"] == "NO_DATA"
    (folder / "ex42_application.jsonl").write_text("", encoding="utf-8")
    report = cpc.check(CLAIMS, CANON, cpc.Sources("E1", run_dir=folder), None)
    assert not report["passed"] and verdicts(report) == {"cap": "NO_DATA", "mirror": "NO_DATA"}


def test_true_is_not_one(tmp_path):
    folder = run_dir(tmp_path, [5, 6, 7, 8])
    text = (folder / "ex42_application.jsonl").read_text(encoding="utf-8").replace('"critic_mirror": true', '"critic_mirror": 1')
    (folder / "ex42_application.jsonl").write_text(text, encoding="utf-8")
    assert verdicts(cpc.check(CLAIMS, CANON, cpc.Sources("E1", run_dir=folder), None))["mirror"] == "FAIL"


def test_variant_rows_run_only_for_their_variant(tmp_path):
    assert "slip" not in verdicts(run(tmp_path, [5, 6, 7, 8], variant=None))


def plan_file(tmp_path, schedule):
    row = stage_row(5)
    if schedule is not None:
        row["terrain"]["continuous_level_cap"] = schedule
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump({"stages": [{"id": "E0"}, row]}), encoding="utf-8")
    return path


def test_plan_mode_wants_the_raise_registered_before_launch(tmp_path):
    def cap(schedule):
        return cpc.check(CLAIMS, CANON, cpc.Sources("E1", plan=plan_file(tmp_path, schedule)))["rows"][0]
    assert cap(None)["verdict"] == "FAIL" and "fixed 5" in cap(None)["detail"]
    assert cap({"start": 5, "step_per_boundary": 1, "end": 6})["verdict"] == "FAIL"
    assert cap({"start": 5, "step_per_boundary": 1, "end": 9})["verdict"] == "PASS"


def test_plan_mode_skips_run_only_rows_but_never_passes_on_skips_alone(tmp_path):
    plan = plan_file(tmp_path, {"start": 5, "step_per_boundary": 1, "end": 9})
    report = cpc.check(CLAIMS, CANON, cpc.Sources("E1", plan=plan), "slip_retrain")
    assert report["passed"] and verdicts(report)["slip"] == "SKIP"
    only = {"schema": CLAIMS["schema"], "claims": [CLAIMS["claims"][2]]}
    assert not cpc.check(only, CANON, cpc.Sources("E1", plan=plan), "slip_retrain")["passed"]


def test_refusals(tmp_path):
    folder = run_dir(tmp_path, [5, 6, 7, 8])
    with pytest.raises(ValueError, match="exactly one"):
        cpc.Sources("E1", run_dir=folder, plan=plan_file(tmp_path, None))
    with pytest.raises(ValueError, match="no row for stage"):
        cpc.check(CLAIMS, CANON, cpc.Sources("E3", run_dir=folder))
    with pytest.raises(ValueError, match="unknown schema"):
        cpc.check({"schema": "x", "claims": []}, CANON, cpc.Sources("E1", run_dir=folder))
    bad = copy.deepcopy(CLAIMS)
    bad["claims"][1]["expect"]["kind"] = "about"
    with pytest.raises(ValueError, match="unregistered kind"):
        cpc.check(bad, CANON, cpc.Sources("E1", run_dir=folder))


def test_main_exit_code_follows_the_verdict(tmp_path, capsys):
    canon = tmp_path / "canon.md"
    canon.write_text(CANON, encoding="utf-8")
    claims = tmp_path / "claims.yaml"
    claims.write_text(yaml.safe_dump(CLAIMS, allow_unicode=True), encoding="utf-8")
    base = ["--canon", str(canon), "--claims", str(claims), "--stage", "E1"]
    out = tmp_path / "report.json"
    assert cpc.main(base + ["--run-dir", str(run_dir(tmp_path / "ok", [5, 6, 7, 8])), "--json-out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["passed"] is True
    assert cpc.main(base + ["--run-dir", str(run_dir(tmp_path / "red", [5, 5, 5, 5]))]) == 1
    assert "EX42_CANON_PARAMS FAIL" in capsys.readouterr().out


def test_the_shipped_table_is_well_formed():
    table = yaml.safe_load(cpc.CLAIMS.read_text(encoding="utf-8"))
    assert table["schema"] == "ex42-canon-claims/1" and table["canon"]["version"] == "v0.17e"
    ids = [c["id"] for c in table["claims"]]
    assert len(ids) == len(set(ids)) and "E1.continuous_level_cap" in ids
    for claim in table["claims"]:
        assert claim["canon_quote"].strip() and claim["expect"]["kind"] in cpc.KINDS
        assert claim["actual"]["source"] in ("stage_config", "env_yaml", "agent_yaml")
