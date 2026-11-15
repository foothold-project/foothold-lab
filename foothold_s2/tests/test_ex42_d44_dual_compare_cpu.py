"""Known-input comparison of old and proposed D44 landing definitions."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from foothold_s2.scripts import ex42_d44_dual_compare as dual
from foothold_s2.tests.test_ex42_d44_cells_cpu import ANCHORS, _plan, _trace

OLD = "ff8390f41ccdc11507c141dd9446add5b5e5cbd8"
PROPOSED = "b62e922567535f0c2b779c8c94d86b2cf2ca42b0"


def _scorers():
    repo = Path(__file__).resolve().parents[2]
    old, _ = dual._scorer(repo, OLD)
    proposed, _ = dual._scorer(repo, PROPOSED)
    return old, proposed


def test_trot_without_four_simultaneous_contacts_separates_definitions():
    old, proposed = _scorers()
    settings = old["contract"](_plan())
    trace = _trace("stop_restart")
    # The historical scorers used the old continuous-restart command timeline.
    trace["phase_id"][70:] = 3
    trace["foot_pos_w"][70:, :, :, :2] = 4.0
    trace["contact"][70:, :, :] = False
    trace["contact"][70::2, :, [0, 2]] = True
    trace["contact"][71::2, :, [1, 3]] = True
    kwargs = dict(spec={"task": "stop_restart"}, anchors=ANCHORS, settings=settings,
                  old_summarize=old["summarize"], proposed_summarize=proposed["summarize"], dt=.1)
    result = dual.compare_trace(trace, **kwargs)
    assert (result["valid_count"], result["old_success"], result["proposed_success"]) == (64, 0, 64)
    assert result["added_envs"] == list(range(64))
    assert result["removed_envs"] == []
    trace["foot_pos_w"][70:, 0, 3, 0] = 5.0
    assert dual.compare_trace(trace, **kwargs)["proposed_success"] == 63
    trace["foot_pos_w"][70:, 1, 0, 2] = 1.0
    assert dual.compare_trace(trace, **kwargs)["proposed_success"] == 62


def test_turn_score_is_identical_and_missing_boundaries_are_explicit(tmp_path, monkeypatch):
    old, proposed = _scorers()
    settings = old["contract"](_plan())
    result = dual.compare_trace(_trace("turn_left"), spec={"task": "turn_left"},
                                anchors=ANCHORS, settings=settings,
                                old_summarize=old["summarize"],
                                proposed_summarize=proposed["summarize"], dt=.1)
    assert result["old_success"] == result["proposed_success"] == 64
    run = tmp_path / "run"
    run.mkdir()
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("test")
    policy = SimpleNamespace(document=_plan(), sha256="p" * 64, path=policy_path)
    monkeypatch.setattr(dual.EX42Plan, "load", lambda _: policy)
    monkeypatch.setattr(dual, "source_tile", lambda _: (
        {"mesh_sha256": "a" * 64}, {"anchors_local_m": ANCHORS}))
    output = dual.build(run, tmp_path / "out", evaluation_plan=policy_path,
                        repo=Path(__file__).resolve().parents[2],
                        old_commit=OLD, proposed_commit=PROPOSED)
    assert output["completed_iterations"] == []
    assert output["missing_iterations"] == list(dual.BOUNDARIES)
    assert sum(1 for line in Path(output["csv"]).read_text().splitlines()) == 37
