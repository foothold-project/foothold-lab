"""D125: DR-on evidence must not become a maintenance score, CPU only."""
import copy
import json
from types import SimpleNamespace

import pytest

from foothold_s2 import ex40_score
from foothold_s2.curriculum import ex41_scoring
from foothold_s2.tests.test_ex40_scorer_cpu import _evidence, _source
from foothold_s2.ex40_eval_once import DEFAULT_CONFIG, DEFAULT_TABLE


MUTATIONS = ["dr", "dr_null", "dr_off_missing", "dr_off_changed",
             "dr_scale", "dr_fired", "dr_push", "dr_recovery", "sequence_dr"]


def contaminate(doc, mutation):
    bad = copy.deepcopy(doc)
    if mutation == "dr":
        bad["dr"] = {"scale": 1.0}
    elif mutation == "dr_null":
        bad["dr"] = None
    elif mutation == "dr_off_missing":
        del bad["dr_off"]
    elif mutation == "dr_off_changed":
        bad["dr_off"] = []
    elif mutation == "sequence_dr":
        bad["sequences"]["eval_gt"]["stop_and_restart"]["dr_scale"] = 1.0
    else:
        bad["modes"]["eval_gt"]["fwd0.5"][mutation] = 0
    return bad


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_ex40_public_judge_holds_dr_on_evidence(tmp_path, mutation):
    checkpoint, _ = _source(tmp_path)
    out = tmp_path / "eval"
    doc = _evidence(out, checkpoint)
    control, _ = ex40_score.judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert control["verdict"] == "PASS"
    (out / "map64/map_modes.json").write_text(json.dumps(contaminate(doc, mutation)), encoding="utf-8")
    rejected, _ = ex40_score.judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert rejected["verdict"] == "HOLD"
    assert rejected["problems"][0]["cell"] == "evidence"


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_ex41_entry_rejects_before_any_score_calculation(tmp_path, monkeypatch, mutation):
    checkpoint, _ = _source(tmp_path)
    out = tmp_path / "eval"
    doc = _evidence(out, checkpoint)
    path = out / "map64/map_modes.json"
    path.write_text(json.dumps(contaminate(doc, mutation)), encoding="utf-8")
    plan = SimpleNamespace(effective_sha256="plan", parent_sha256="parent")
    draft = dict(format="foothold-ex41-score/1", iteration=500, metrics={}, evidence=[],
                 maintenance_pass=False, stage_pass=False, safety_stop=False,
                 schedule_sha256="plan", parent_sha256="parent",
                 baseline_checkpoint_sha256="parent", checkpoint_path=str(checkpoint))

    def forbidden(*args, **kwargs):
        pytest.fail("DR-on document reached score calculation")

    # Independent of _map_rows: deleting only the EX41 entry guard must fail.
    monkeypatch.setattr(ex41_scoring, "baseline_counts", forbidden)
    with pytest.raises(RuntimeError, match="map_modes.json"):
        ex41_scoring.enrich_score_metrics(draft, path, {}, plan)
    assert draft["metrics"] == {} and draft["evidence"] == []
