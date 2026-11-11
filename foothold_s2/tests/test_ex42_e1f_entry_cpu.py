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


def test_a_segment_past_the_base_cap_is_refused_by_the_launcher_until_the_extension_path_is_wired(known, tmp_path, adopted):
    """Extension segments (cap < end <= cap + step x count) are a recorded gap: the launcher stops (rc 2) instead of
    starting a process whose update bound is the base cap."""
    result = run(known)
    entry.adopt_plan_stage_table(result["plan"])
    env = _env(tmp_path, action="continue", stage="E1F")
    env.update(EX42_AUTO_PLAN=result["plan"], EX42_AUTO_APPROVALS=result["approvals"], EX42_AUTO_SEGMENT_END="1000")
    with pytest.raises(L.LaunchRefused, match="not an update in 1..750"):
        L.build(env)
