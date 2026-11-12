"""The canon sentence -> training value check: red when a segment did not run at the cap the canon fixes."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from foothold_s2 import ex42_canon_params_check as cpc

CAP_QUOTE = "250 회 네 구간 · 지형 상한 6 → 7 → 8 → 9"
CANON = f"## E1\n| 27 | {CAP_QUOTE} · critic 대칭 켬 · `foot_slip` −0.15 |\n| critic | E1 경계에서 켠다 |\n"
CLAIMS = {"schema": "ex42-canon-claims/2", "gated_stages": ["E1"], "claims": [
    {"id": "cap", "stage": "E1", "canon_quote": CAP_QUOTE,
     "actual": {"source": "exposure_receipts", "plan_path": "terrain.continuous_level_cap"},
     "expect": {"kind": "raise_per_boundary", "start": 6, "step": 1, "end": 9},
     "observe": {"source": "map_switch", "field": "on.terrain_level_mean"}},
    {"id": "mirror", "stage": "E1", "canon_quote": "E1 경계에서 켠다",
     "actual": {"source": "stage_config", "path": "critic_mirror"}, "expect": {"kind": "equals", "value": True}},
    {"id": "slip", "stage": "E1", "canon_quote": "`foot_slip` −0.15",
     "actual": {"source": "env_yaml", "path": "rewards.ex41_foot_slip.weight",
                "plan_file": "source.yaml", "plan_path": "first_rewards.foot_slip"},
     "expect": {"kind": "equals", "value": -0.15}},
    {"id": "updates", "stage": "E1", "canon_quote": "E1 경계에서 켠다",
     "actual": {"source": "agent_yaml", "path": "max_iterations"}, "expect": {"kind": "equals", "value": 1000}},
]}


def stage_row(mirror=True, schedule=(6, 1, 9)):
    row = {"id": "E1", "critic_mirror": mirror, "terrain": {}}
    if schedule is not None:
        row["terrain"]["continuous_level_cap"] = dict(zip(("start", "step_per_boundary", "end"), schedule))
    return row


def receipt(k, caps, stage="E1"):
    rows = [{"column": i, "open": cap is not None, "level_cap": cap if cap is not None else 0} for i, cap in enumerate(caps)]
    return {"stage_id": stage, "kind": "start", "iteration": 250 * k, "boundary_index": k, "column_rows": rows}


def run_dir(tmp_path, caps=(6, 7, 8, 9), slip=-0.15, receipts=None):
    folder = tmp_path / "run"
    (folder / "params").mkdir(parents=True)
    (folder / "params" / "env.yaml").write_text(   # the real file carries python tags
        f"rewards:\n  ex41_foot_slip:\n    weight: {slip}\n    range: !!python/tuple [0.0, 1.0]\n", encoding="utf-8")
    (folder / "params" / "agent.yaml").write_text("max_iterations: 1000\n", encoding="utf-8")
    rows = [{"event": "p1_queued", "stage_id": "E1", "checkpoint_iteration": 250 * (i + 1), "stage_config": stage_row()}
            for i in range(len(caps))]
    rows.append({"event": "p1_queued", "stage_id": "E0", "checkpoint_iteration": 250, "stage_config": stage_row(False)})
    (folder / "ex42_application.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    bodies = receipts if receipts is not None else [receipt(k, [cap, cap, None]) for k, cap in enumerate(caps)]
    bodies = bodies + [receipt(0, [5, 5, None], stage="E0")]                    # another stage's receipt is not read
    for n, body in enumerate(bodies):
        (folder / f"exposure_receipt_start_{body['iteration']}_{n}.json").write_text(json.dumps(body), encoding="utf-8")
    (folder / "exposure_receipt_250.json").write_text(json.dumps(receipt(9, [1, 1, None])), encoding="utf-8")   # a boundary receipt
    (folder / "map_switch.jsonl").write_text(
        "".join(json.dumps({"it": i, "on": {"terrain_level_mean": 5.5}}) + "\n" for i in (1, 2)), encoding="utf-8")
    return folder


def verdicts(report):
    return {row["id"]: row["verdict"] for row in report["rows"]}


def run(tmp_path, claims=CLAIMS, canon=CANON, **kw):
    return cpc.check(claims, canon, cpc.Sources("E1", run_dir=run_dir(tmp_path, **kw)))


def test_four_segments_at_six_to_nine_pass(tmp_path):
    report = run(tmp_path)
    assert report["passed"] and set(verdicts(report).values()) == {"PASS"}
    assert report["rows"][0]["observed"] == {"field": "on.terrain_level_mean", "min": 5.5, "max": 5.5, "n": 2}
    assert verdicts(run(tmp_path / "two", caps=(6, 7)))["cap"] == "PASS"         # a run still under way


@pytest.mark.parametrize("caps", [(5, 5, 5, 5), (5, 6, 7, 8), (6, 6, 7, 8), (6, 8, 9, 9), (6, 7, 8, 10), (7, 8, 9, 9)])
def test_segments_at_any_other_cap_are_red(tmp_path, caps):
    report = run(tmp_path, caps=caps)
    assert not report["passed"] and verdicts(report)["cap"] == "FAIL"


def test_the_cap_stays_at_the_end_value_in_an_extension(tmp_path):
    assert verdicts(run(tmp_path, caps=(6, 7, 8, 9, 9, 9)))["cap"] == "PASS"


def test_a_schedule_whose_first_raise_waits_is_judged_segment_by_segment(tmp_path):
    claims = copy.deepcopy(CLAIMS)
    claims["claims"][0]["expect"].update(start=5, first_raise_boundary=3)
    assert verdicts(run(tmp_path / "ok", claims=claims, caps=(5, 5, 5, 6, 7, 8, 9)))["cap"] == "PASS"
    for n, caps in enumerate([(6, 7, 8, 9), (5, 6, 7, 8, 9), (5, 5, 5, 5), (5, 5, 6, 7)]):
        assert verdicts(run(tmp_path / f"red{n}", claims=claims, caps=caps))["cap"] == "FAIL"
    row = lambda *schedule: stage_row(schedule=None) | {"terrain": {"continuous_level_cap": dict(   # noqa: E731
        zip(("start", "step_per_boundary", "end", "first_raise_boundary"), schedule))}}
    plan_cap = lambda folder, r: cpc.check(claims, CANON, cpc.Sources("E1", plan=plan_file(tmp_path / folder, row=r)))["rows"][0]["verdict"]   # noqa: E731
    assert plan_cap("p3", row(5, 1, 9, 3)) == "PASS"
    assert plan_cap("p1", row(5, 1, 9)) == "FAIL" and plan_cap("p2", row(5, 1, 9, 2)) == "FAIL" and plan_cap("p6", row(6, 1, 9, 3)) == "FAIL"


def test_a_segment_without_a_receipt_or_with_mixed_caps_is_red(tmp_path):
    gap = [receipt(0, [6, 6]), receipt(2, [8, 8])]
    assert "has no receipt" in run(tmp_path / "a", receipts=gap)["rows"][0]["detail"]
    mixed = [receipt(0, [6, 5])]
    row = run(tmp_path / "b", receipts=mixed)["rows"][0]
    assert row["verdict"] == "FAIL" and "[5, 6]" in row["detail"]
    assert verdicts(run(tmp_path / "c", receipts=[]))["cap"] == "NO_DATA"


def test_a_changed_canon_sentence_or_another_canon_file_turns_rows_stale(tmp_path):
    report = run(tmp_path, canon=CANON.replace("6 → 7 → 8 → 9", "5 → 9"))
    assert not report["passed"] and verdicts(report)["cap"] == "STALE" and verdicts(report)["mirror"] == "PASS"
    pinned = {**CLAIMS, "canon": {"sha256": hashlib.sha256(CANON.encode()).hexdigest()}}
    assert run(tmp_path / "same", claims=pinned)["passed"]
    report = run(tmp_path / "other", claims=pinned, canon=CANON + "\n")
    assert not report["passed"] and set(verdicts(report).values()) == {"STALE"}


def test_a_value_that_differs_or_is_missing_is_not_a_pass(tmp_path):
    report = run(tmp_path, slip=-0.25)
    assert not report["passed"] and verdicts(report)["slip"] == "FAIL"
    assert "-0.25" in report["rows"][2]["detail"] and "-0.15" in report["rows"][2]["detail"]
    folder = run_dir(tmp_path / "missing")
    (folder / "params" / "env.yaml").write_text("rewards: {}\n", encoding="utf-8")
    (folder / "ex42_application.jsonl").write_text("", encoding="utf-8")
    (folder / "params" / "agent.yaml").unlink()
    report = cpc.check(CLAIMS, CANON, cpc.Sources("E1", run_dir=folder))
    assert not report["passed"] and verdicts(report) == {"cap": "PASS", "mirror": "NO_DATA", "slip": "NO_DATA", "updates": "NO_DATA"}


def test_true_is_not_one(tmp_path):
    folder = run_dir(tmp_path)
    text = (folder / "ex42_application.jsonl").read_text(encoding="utf-8").replace('"critic_mirror": true', '"critic_mirror": 1')
    (folder / "ex42_application.jsonl").write_text(text, encoding="utf-8")
    assert verdicts(cpc.check(CLAIMS, CANON, cpc.Sources("E1", run_dir=folder)))["mirror"] == "FAIL"


def test_variant_rows_run_only_for_their_variant(tmp_path):
    claims = copy.deepcopy(CLAIMS)
    claims["claims"][2]["variant"] = "restart"
    folder = run_dir(tmp_path)
    assert "slip" not in verdicts(cpc.check(claims, CANON, cpc.Sources("E1", run_dir=folder)))
    assert verdicts(cpc.check(claims, CANON, cpc.Sources("E1", run_dir=folder), "restart"))["slip"] == "PASS"


def plan_file(tmp_path, row=None, slip=-0.15):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump({"stages": [{"id": "E0"}, row or stage_row()]}), encoding="utf-8")
    if slip is not None:
        (tmp_path / "source.yaml").write_text(f"first_rewards:\n  foot_slip: {slip}\n", encoding="utf-8")
    return path


def plan(tmp_path, **kw):
    return cpc.check(CLAIMS, CANON, cpc.Sources("E1", plan=plan_file(tmp_path, **kw)))


def test_plan_mode_reads_the_schedule_the_stage_row_and_the_file_beside_the_plan(tmp_path):
    report = plan(tmp_path / "ok")
    assert report["passed"] and verdicts(report) == {"cap": "PASS", "mirror": "PASS", "slip": "PASS", "updates": "SKIP"}
    assert verdicts(plan(tmp_path / "none", row=stage_row(schedule=None)))["cap"] == "FAIL"
    assert verdicts(plan(tmp_path / "five", row=stage_row(schedule=(5, 1, 9))))["cap"] == "FAIL"
    assert verdicts(plan(tmp_path / "six", row=stage_row(schedule=(6, 1, 8))))["cap"] == "FAIL"
    assert verdicts(plan(tmp_path / "slip", slip=0.0))["slip"] == "FAIL"
    assert verdicts(plan(tmp_path / "nofile", slip=None))["slip"] == "NO_DATA"
    assert verdicts(plan(tmp_path / "mirror", row=stage_row(mirror=False)))["mirror"] == "FAIL"


def test_plan_mode_never_passes_on_skips_alone(tmp_path):
    only = {"schema": CLAIMS["schema"], "claims": [CLAIMS["claims"][3]]}
    assert not cpc.check(only, CANON, cpc.Sources("E1", plan=plan_file(tmp_path)))["passed"]


def test_refusals(tmp_path):
    folder = run_dir(tmp_path)
    with pytest.raises(ValueError, match="exactly one"):
        cpc.Sources("E1", run_dir=folder, plan=plan_file(tmp_path / "p"))
    with pytest.raises(ValueError, match="no row for stage"):
        cpc.check(CLAIMS, CANON, cpc.Sources("E3", run_dir=folder))
    with pytest.raises(ValueError, match="unknown schema"):
        cpc.check({"schema": "ex42-canon-claims/1", "claims": []}, CANON, cpc.Sources("E1", run_dir=folder))
    bad = copy.deepcopy(CLAIMS)
    bad["claims"][1]["expect"]["kind"] = "about"
    with pytest.raises(ValueError, match="unregistered kind"):
        cpc.check(bad, CANON, cpc.Sources("E1", run_dir=folder))


def _gate_files(tmp_path, claims=CLAIMS, canon=CANON):
    root = tmp_path / "root"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "canon.md").write_text(canon, encoding="utf-8")
    table = root / "claims.yaml"
    table.write_text(yaml.safe_dump({**claims, "canon": {"path": "docs/canon.md"}}, allow_unicode=True), encoding="utf-8")
    return root, table


def test_the_launch_gate_judges_gated_stages_only_and_fails_closed(tmp_path):
    root, table = _gate_files(tmp_path)
    good, old = plan_file(tmp_path / "good"), plan_file(tmp_path / "old", row=stage_row(schedule=None))
    assert cpc.launch_gate("E1", good, claims_path=table, root=root)["passed"] is True
    report = cpc.launch_gate("E1", old, claims_path=table, root=root)
    assert report["passed"] is False and cpc.failures(report).startswith("cap FAIL: plan row has no raise schedule")
    assert cpc.launch_gate("E0", good, claims_path=table, root=root) is None       # not gated: no judgement at all
    with pytest.raises(ValueError, match="canon file"):
        cpc.launch_gate("E1", good, claims_path=table, root=tmp_path)
    _, table = _gate_files(tmp_path / "x", claims={**CLAIMS, "gated_stages": ["E1", "E3"]})
    with pytest.raises(ValueError, match="rows for stage E3|no row for stage"):
        cpc.launch_gate("E3", good, claims_path=table, root=tmp_path / "x" / "root")


def test_main_exit_code_follows_the_verdict(tmp_path, capsys):
    root, table = _gate_files(tmp_path)
    base = ["--canon", str(root / "docs" / "canon.md"), "--claims", str(table), "--stage", "E1"]
    out = tmp_path / "report.json"
    assert cpc.main(base + ["--run-dir", str(run_dir(tmp_path / "ok")), "--json-out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["passed"] is True
    assert cpc.main(base + ["--run-dir", str(run_dir(tmp_path / "red", caps=(5, 5, 5, 5)))]) == 1
    assert "EX42_CANON_PARAMS FAIL" in capsys.readouterr().out
    assert cpc.main(base + ["--plan", str(plan_file(tmp_path / "plan"))]) == 0


def test_the_shipped_table_matches_the_canon_in_this_tree_and_the_shipped_plan():
    table = yaml.safe_load(cpc.CLAIMS.read_text(encoding="utf-8"))
    canon = cpc.SOURCE_ROOT / table["canon"]["path"]
    text = canon.read_text(encoding="utf-8")
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == table["canon"]["sha256"] and table["gated_stages"] == ["E1"]
    ids = [c["id"] for c in table["claims"]]
    assert len(ids) == len(set(ids)) and all(c["canon_quote"] in text for c in table["claims"])
    report = cpc.launch_gate("E1", cpc.CLAIMS.parent / "ex42-prep.yaml")
    verdicts = {row["id"]: row["verdict"] for row in report["rows"]}
    skipped = {"E1.segment_command_adjustment"}          # segment command records exist only in a run folder
    assert report["passed"] and len(verdicts) == 11
    assert all(verdict == ("SKIP" if name in skipped else "PASS") for name, verdict in verdicts.items())
