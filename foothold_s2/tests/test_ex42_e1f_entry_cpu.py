"""E1F entry in front of Kit: a materialized pair (E1 -> E1F) is adopted by the stage table, the launcher builds its
dry-run and real commands from that pair, and the parent is E1 with the mirror on. Real materialize on the verifier's
synthetic E1 finish; no Kit, no GPU. The real-data dry run is `ex42_stage_launcher.sh --dry-run` (see the PR body)."""
from __future__ import annotations

from pathlib import Path

import pytest

from foothold_s2.scripts import ex42_stage_launcher as L
from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.tests.test_ex42_materialize_cpu import known, run  # noqa: F401
from foothold_s2.tests.test_ex42_stage_launcher_cpu import _env, _flag


@pytest.fixture
def adopted():
    saved = {k: dict(v) for k, v in entry.E_STAGE_SPECS.items()}
    yield
    entry.E_STAGE_SPECS.clear()
    entry.E_STAGE_SPECS.update(saved)
    entry.E_STAGES.clear()
    entry.E_STAGES.update({k: (v["updates"], v["parent_local"], v["parent_cumulative"]) for k, v in saved.items()})


def test_the_materialized_pair_makes_e1f_startable_from_e1_with_the_mirror_on(known, tmp_path, adopted):
    assert "E1F" not in entry.E_STAGE_SPECS                                  # the shipped plan has no E1F parent pin
    result = run(known)
    table = entry.adopt_plan_stage_table(result["plan"])
    spec = table["E1F"]
    assert spec["previous"] == "E1" and spec["critic_mirror"] is True and table["E1"]["critic_mirror"] is True
    assert spec["parent_key"].startswith("model_") and spec["updates"] == 750
    assert entry._stage_caps("E1F") == {750, 1250}                          # base cap, one extension
    env = _env(tmp_path, stage="E1F")
    env.update(EX42_AUTO_PLAN=result["plan"], EX42_AUTO_APPROVALS=result["approvals"])
    for dry in (True, False):
        argv, child, summary = L.build(env, dry_run=dry, now=0)
        assert _flag(argv, "--ex42_stage") == "E1F" and _flag(argv, "--max_iterations") == "750"
        assert _flag(argv, "--ex42_plan") == result["plan"] and _flag(argv, "--ex42_approvals") == result["approvals"]
        assert ("--ex42_stage_dry_run" in argv) is dry and Path(result["plan"]).parent.name != "curriculum"
    assert summary["updates"] == 750


def test_a_segment_past_the_base_cap_runs_with_the_extension_bound_and_one_past_the_last_extension_is_refused(known, tmp_path, adopted):
    result = run(known)
    entry.adopt_plan_stage_table(result["plan"])
    env = _env(tmp_path, action="continue", stage="E1F")
    env.update(EX42_AUTO_PLAN=result["plan"], EX42_AUTO_APPROVALS=result["approvals"])
    expected = {"750": "750", "1000": "1250", "1250": "1250"}               # E1F: cap 750, one extension of 500
    for end, bound in expected.items():
        argv, _, summary = L.build({**env, "EX42_AUTO_SEGMENT_END": end})
        assert _flag(argv, "--max_iterations") == bound and _flag(argv, "--ex42_segment_end") == end and summary["updates"] == int(bound)
    with pytest.raises(L.LaunchRefused, match="not an update in 1..1250"):
        L.build({**env, "EX42_AUTO_SEGMENT_END": "1500"})


def test_stage_bound_grants_an_extension_only_to_an_authorized_cell_and_inside_the_table(known, tmp_path, adopted):
    import yaml
    result = run(known)
    entry.adopt_plan_stage_table(result["plan"])
    approvals = Path(result["approvals"])
    assert entry.stage_bound("E1F") == 750 and entry.stage_bound("E1F", 750, approvals) == 750
    doc = yaml.safe_load(approvals.read_text())
    assert doc["stage_e1f_authorization"]["extension_authorized"] is True                 # materialize opens it from the table
    assert entry.stage_bound("E1F", 1000, approvals) == 1250 and entry.stage_bound("E1F", 1250, approvals) == 1250
    with pytest.raises(ValueError, match="past the last extension"):
        entry.stage_bound("E1F", 1251, approvals)
    doc["stage_e1f_authorization"]["extension_authorized"] = False
    closed = tmp_path / "closed.yaml"
    closed.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError, match="not authorized"):
        entry.stage_bound("E1F", 1000, closed)
    assert entry.stage_bound("E1F", 750, closed) == 750                                  # inside the cap nothing is needed


def test_a_resume_from_the_base_cap_save_into_the_extension_is_accepted_by_the_saved_bound_check():
    from foothold_s2.scripts.ex42_training_entry import _saved_bound_fits
    assert _saved_bound_fits(1000, 1500, "E1") and _saved_bound_fits(1000, 1000, "E1") and _saved_bound_fits(1500, 2000, "E1")
    assert not _saved_bound_fits(1500, 1000, "E1") and not _saved_bound_fits(1250, 1500, "E1")
    assert _saved_bound_fits(1000, 1000, "EX42_0_T0_prime") and not _saved_bound_fits(1000, 1500, "EX42_0_T0_prime")
